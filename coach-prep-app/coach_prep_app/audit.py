# coach-prep-app/coach_prep_app/audit.py
"""Weekly mechanical scan + content leakage scan + placement check +
unmatched count, reported via the existing Resend pattern."""
from __future__ import annotations

from coach_prep_app import doc_ingest_reader, gates


def mechanical_scan(conn, doc_ingest_conn, since_iso: str) -> list[dict]:
    """Flags any generation run whose generation_inputs reference a
    client-scoped converted file tagged for a DIFFERENT client than the run
    itself. Global program_source inputs are excluded by design. Bounded to
    runs created at or after since_iso -- the weekly audit re-scans that
    week only, not every published draft ever."""
    problems = []
    runs = conn.execute(
        "SELECT id, client_slug FROM generation_runs "
        "WHERE status IN ('published', 'notified') AND created_at >= ?",
        (since_iso,),
    ).fetchall()
    for run_id, client_slug in runs:
        refs = conn.execute(
            "SELECT reference FROM generation_inputs WHERE run_id = ? AND source_kind = 'converted_file'",
            (run_id,),
        ).fetchall()
        for (ref,) in refs:
            row = doc_ingest_conn.execute(
                "SELECT client FROM conversions WHERE output_path = ? AND status = 'current'", (ref,)
            ).fetchone()
            actual_client = row[0] if row else None
            if actual_client not in (None, client_slug):
                problems.append({"run_id": run_id, "expected": client_slug, "found": actual_client, "reference": ref})
    return problems


def content_scan(conn, doc_ingest_conn, drive_service, since_iso: str) -> list[dict]:
    """Re-fetches each published draft's text from Drive and re-runs the
    leakage scan against every OTHER registered client. Same tripwire
    caveat as gates.leakage_scan -- not a guarantee. Bounded to runs
    created at or after since_iso -- see mechanical_scan. One run's Drive
    fetch failing (a deleted/inaccessible draft) is recorded as its own
    problem entry rather than raising -- the same per-item isolation
    lesson orchestrator.run_once already applies (Task 21): one bad draft
    must not kill the whole weekly scan and its email."""
    problems = []
    runs = conn.execute(
        "SELECT id, client_slug, draft_drive_file_id FROM generation_runs "
        "WHERE status IN ('published', 'notified') AND draft_drive_file_id IS NOT NULL AND created_at >= ?",
        (since_iso,),
    ).fetchall()
    clients = doc_ingest_reader.get_active_clients(doc_ingest_conn)
    for run_id, client_slug, file_id in runs:
        try:
            text = drive_service.files().export(fileId=file_id, mimeType="text/plain").execute().decode("utf-8")
        except Exception as exc:
            problems.append({"run_id": run_id, "client_slug": client_slug, "leaked": None, "error": str(exc)})
            continue
        other_clients = [c for c in clients if c["slug"] != client_slug]
        leaked = gates.leakage_scan(text, other_clients)
        if leaked:
            problems.append({"run_id": run_id, "client_slug": client_slug, "leaked": leaked, "error": None})
    return problems


def placement_check(conn, doc_ingest_conn, drive_service, pending_review_folder_id: str, since_iso: str) -> list[dict]:
    """For each notified draft, whether it's still sitting in Pending
    Review, moved to the correct client folder, or moved somewhere
    unexpected. Informational for the first two states; only the third
    (and a lookup failure) is surfaced as a problem by render_report_email.
    Bounded to runs created at or after since_iso -- see mechanical_scan.
    One run's Drive lookup failing is recorded as its own status rather
    than raising -- see content_scan's identical rationale."""
    clients_by_slug = {c["slug"]: c for c in doc_ingest_reader.get_active_clients(doc_ingest_conn)}
    results = []
    runs = conn.execute(
        "SELECT id, client_slug, draft_drive_file_id FROM generation_runs "
        "WHERE status = 'notified' AND draft_drive_file_id IS NOT NULL AND created_at >= ?",
        (since_iso,),
    ).fetchall()
    for run_id, client_slug, file_id in runs:
        try:
            meta = drive_service.files().get(fileId=file_id, fields="parents").execute()
        except Exception as exc:
            results.append({
                "run_id": run_id, "client_slug": client_slug,
                "status": "placement_check_failed", "error": str(exc),
            })
            continue
        parents = meta.get("parents", [])
        expected_folder = clients_by_slug.get(client_slug, {}).get("drive_folder_id")
        if expected_folder and expected_folder in parents:
            status = "moved_to_correct_folder"
        elif pending_review_folder_id in parents:
            status = "still_pending_review"
        else:
            status = "moved_to_unexpected_location"
        results.append({"run_id": run_id, "client_slug": client_slug, "status": status, "error": None})
    return results


def unmatched_count(doc_ingest_conn) -> int:
    row = doc_ingest_conn.execute(
        "SELECT COUNT(*) FROM conversions WHERE status = 'current' AND client = 'unmatched'"
    ).fetchone()
    return row[0]


def failed_runs_summary(conn, since_iso: str) -> list[dict]:
    """Surfaces runs mechanical_scan/content_scan/placement_check never see
    -- all three are scoped to status IN ('published', 'notified'). A
    gates_failed run is exactly the event orchestrator.py's
    _append_failure_reason fallback was built to keep visible when its own
    ALERT email fails to send; a failed or stuck-'assembling' run is
    otherwise invisible to anyone who isn't reading the DB by hand.
    Bounded to runs created at or after since_iso -- see mechanical_scan."""
    rows = conn.execute(
        "SELECT id, client_slug, status, failure_reason, created_at FROM generation_runs "
        "WHERE created_at >= ? AND status IN ('failed', 'gates_failed', 'assembling') "
        "ORDER BY created_at",
        (since_iso,),
    ).fetchall()
    return [
        {"run_id": r[0], "client_slug": r[1], "status": r[2], "failure_reason": r[3], "created_at": r[4]}
        for r in rows
    ]


def build_report(conn, doc_ingest_conn, drive_service, cfg, since_iso: str) -> dict:
    return {
        "mechanical_problems": mechanical_scan(conn, doc_ingest_conn, since_iso),
        "content_problems": content_scan(conn, doc_ingest_conn, drive_service, since_iso),
        "placement": placement_check(
            conn, doc_ingest_conn, drive_service, cfg.pending_review_drive_folder_id, since_iso
        ),
        "unmatched_count": unmatched_count(doc_ingest_conn),
        "failed_runs": failed_runs_summary(conn, since_iso),
    }


def render_report_email(report: dict) -> tuple[str, str]:
    unexpected_placements = [
        p for p in report["placement"]
        if p["status"] in ("moved_to_unexpected_location", "placement_check_failed")
    ]
    clean = (
        not report["mechanical_problems"] and not report["content_problems"]
        and not report["failed_runs"] and not unexpected_placements
    )
    subject = "Coach-prep weekly audit: clean" if clean else "Coach-prep weekly audit: ISSUES FOUND"
    lines = [f"Unmatched meeting notes: {report['unmatched_count']}", ""]
    if report["mechanical_problems"]:
        lines.append("Mechanical scan problems:")
        lines += [
            f"  run {p['run_id']}: expected {p['expected']}, found {p['found']} ({p['reference']})"
            for p in report["mechanical_problems"]
        ]
    if report["content_problems"]:
        lines.append("Content leakage problems:")
        lines += [
            f"  run {p['run_id']} ({p['client_slug']}): "
            + (f"leaked {p['leaked']}" if p.get("leaked") else f"scan failed: {p.get('error')}")
            for p in report["content_problems"]
        ]
    if unexpected_placements:
        lines.append("Drafts moved to an unexpected location:")
        lines += [
            f"  run {p['run_id']} ({p['client_slug']})"
            + (f": {p['error']}" if p["status"] == "placement_check_failed" else "")
            for p in unexpected_placements
        ]
    if report["failed_runs"]:
        lines.append("Failed / stuck runs:")
        lines += [
            f"  run {r['run_id']} ({r['client_slug']}): {r['status']}"
            + (f" -- {r['failure_reason']}" if r["failure_reason"] else "")
            for r in report["failed_runs"]
        ]
    if clean:
        lines.append("No problems found this week.")
    return subject, "\n".join(lines)
