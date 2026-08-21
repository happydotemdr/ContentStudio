# coach-prep-app/coach_prep_app/orchestrator.py
"""Wires one 4-hourly wake end to end: detect -> classify -> gate on timing
-> assemble -> generate -> mechanical gates -> publish (draft only) ->
notify -> watermark. Every step that can fail leaves the watermark unset so
the next wake retries."""
from __future__ import annotations

import datetime as dt
import sys
from zoneinfo import ZoneInfo

from coach_prep_app import bundle as bundle_mod
from coach_prep_app import db, doc_ingest_reader, gates, generate, notify, publish, trigger


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _meeting_date_local(meeting_start_utc: dt.datetime, timezone_name: str) -> dt.date:
    return meeting_start_utc.astimezone(ZoneInfo(timezone_name)).date()


def process_candidate(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg,
                       client: dict, event: dict, now_utc: dt.datetime) -> str:
    if not trigger.is_due(conn, client["slug"], event["instance_id"], event["start_utc"],
                           now_utc, cfg.timezone_name, cfg.daily_ready_hour_local):
        return "not_due"

    # A prior wake may have published the draft but failed to send the
    # notification email -- retry ONLY the notify step against that SAME
    # draft. Without this check, a notify failure (watermark deliberately
    # left unset so the run isn't silently lost) would cause the next wake
    # to regenerate and republish a second, orphaned draft with no dedup.
    existing = _find_published_unnotified_run(conn, client["slug"], event["instance_id"])
    if existing is not None:
        run_id, file_id = existing
        subject, text = notify.render_review_email(
            client["display_name"], _meeting_date_local(event["start_utc"], cfg.timezone_name), file_id
        )
        sent = notify.send_email(subject, text, recipient=cfg.notify_recipient)
        if not sent:
            return "publish_ok_notify_failed"
        trigger.mark_done(conn, client["slug"], event["instance_id"], _now_iso())
        _mark_notified(conn, run_id)
        return "published"

    run_id = _start_run(conn, client["slug"], event["instance_id"], event["start_utc"])

    all_clients = doc_ingest_reader.get_active_clients(doc_ingest_conn)
    other_clients = [c for c in all_clients if c["slug"] != client["slug"]]

    the_bundle = bundle_mod.build_bundle(gmail_service, doc_ingest_reader, doc_ingest_conn, cfg, client, now_utc)
    bundle_mod.persist_inputs(conn, run_id, the_bundle, _now_iso())

    generated = generate.generate_draft(the_bundle, timeout_s=cfg.generation_timeout_s)
    if generated is None:
        _fail_run(conn, run_id, "generation_failed")
        return "generation_failed"  # watermark deliberately NOT set -- a transient failure, retried next wake

    allowed_labels = gates.allowed_labels(the_bundle)
    bad_citations = gates.citation_gate(generated, allowed_labels)
    leaked = gates.leakage_scan(generated, other_clients)
    if bad_citations or leaked:
        _fail_run(
            conn, run_id, f"gate_failed: bad_citations={bad_citations} leaked={leaked}", status="gates_failed"
        )
        # Terminal, per spec: "a hard stop, never auto-retried silently."
        # Setting the watermark HERE too (not only on success) is what makes
        # is_due() return False on every later wake for this event -- a gate
        # failure is a content-safety stop, not a transient error worth
        # re-attempting (and re-alerting on) every 4 hours until the meeting.
        trigger.mark_done(conn, client["slug"], event["instance_id"], _now_iso())
        alert_sent = notify.send_email(
            f"ALERT: coach-prep isolation gate failed for {client['display_name']}",
            f"Run {run_id} failed its mechanical gates. bad_citations={bad_citations} leaked={leaked}\n"
            f"No draft was published or sent. This will NOT be retried automatically -- "
            f"investigate and re-run by hand if appropriate.",
            recipient=cfg.notify_recipient,
        )
        if not alert_sent:
            # gates_failed is the exact event this whole isolation system
            # exists to catch -- if the ALERT about it also fails to send,
            # that must not make the event invisible. Record it in
            # failure_reason so the weekly audit or a human inspecting the
            # DB can still find it.
            _append_failure_reason(conn, run_id, "ALERT EMAIL FAILED")
        return "gate_failed"

    file_id = publish.publish_draft(
        drive_service, cfg.pending_review_drive_folder_id, client["display_name"],
        _meeting_date_local(event["start_utc"], cfg.timezone_name), generated,
    )
    _mark_published(conn, run_id, file_id)

    subject, text = notify.render_review_email(
        client["display_name"], _meeting_date_local(event["start_utc"], cfg.timezone_name), file_id
    )
    sent = notify.send_email(subject, text, recipient=cfg.notify_recipient)
    if not sent:
        return "publish_ok_notify_failed"  # watermark deliberately NOT set -- next wake retries notify only (see the existing-run check above)

    trigger.mark_done(conn, client["slug"], event["instance_id"], _now_iso())
    _mark_notified(conn, run_id)
    return "published"


def _find_published_unnotified_run(conn, client_slug: str, event_instance_id: str) -> tuple[int, str] | None:
    row = conn.execute(
        "SELECT id, draft_drive_file_id FROM generation_runs "
        "WHERE client_slug = ? AND calendar_event_instance_id = ? AND status = 'published' "
        "ORDER BY created_at DESC LIMIT 1",
        (client_slug, event_instance_id),
    ).fetchone()
    return (row[0], row[1]) if row is not None else None


def _start_run(conn, client_slug, event_instance_id, meeting_start_utc) -> int:
    now = _now_iso()
    with db.transaction(conn):
        conn.execute(
            "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, meeting_start_at, "
            "status, created_at, updated_at) VALUES (?, ?, ?, 'assembling', ?, ?)",
            (client_slug, event_instance_id, meeting_start_utc.isoformat(), now, now),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _fail_run(conn, run_id, reason, status="failed") -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE generation_runs SET status = ?, failure_reason = ?, updated_at = ? WHERE id = ?",
            (status, reason, _now_iso(), run_id),
        )


def _append_failure_reason(conn, run_id, note) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE generation_runs SET failure_reason = failure_reason || ' | ' || ?, updated_at = ? WHERE id = ?",
            (note, _now_iso(), run_id),
        )


def _mark_published(conn, run_id, file_id) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE generation_runs SET status = 'published', draft_drive_file_id = ?, updated_at = ? WHERE id = ?",
            (file_id, _now_iso(), run_id),
        )


def _mark_notified(conn, run_id) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE generation_runs SET status = 'notified', updated_at = ? WHERE id = ?",
            (_now_iso(), run_id),
        )


def _list_upcoming_events(calendar_service, cfg, now_utc: dt.datetime) -> list[dict]:
    time_min = now_utc.isoformat()
    time_max = (now_utc + dt.timedelta(hours=cfg.lookahead_hours)).isoformat()
    resp = calendar_service.events().list(
        calendarId=cfg.coach_email, timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy="startTime",
    ).execute()
    out = []
    for item in resp.get("items", []):
        start = item["start"].get("dateTime") or item["start"].get("date")
        out.append({
            "instance_id": item["id"],
            "start_utc": dt.datetime.fromisoformat(start).astimezone(dt.timezone.utc),
            "attendees": [a["email"] for a in item.get("attendees", []) if "email" in a],
        })
    return out


def _classify_event(clients: list[dict], event: dict, coach_email: str) -> str | None:
    from doc_ingest import client_matching
    slug = client_matching.match_attendees_to_client(event["attendees"], clients, coach_email)
    return None if slug == client_matching.UNMATCHED else slug


def run_once(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg,
             now_utc: dt.datetime) -> list[str]:
    results = []
    clients = doc_ingest_reader.get_active_clients(doc_ingest_conn)
    events = _list_upcoming_events(calendar_service, cfg, now_utc)
    for event in events:
        client_slug = _classify_event(clients, event, cfg.coach_email)
        if client_slug is None:
            continue
        client = next(c for c in clients if c["slug"] == client_slug)
        try:
            results.append(process_candidate(
                conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg, client, event, now_utc
            ))
        except Exception as exc:
            # Spec: "API failure mid-run -> log, skip that client this
            # wake." A single client's Calendar/Gmail/Drive HttpError must
            # never abort the whole wake and starve every client ordered
            # after it. Nothing is marked done for this client, so it is
            # retried in full on the next wake.
            print(f"orchestrator: process_candidate failed for {client['slug']}: {exc}", file=sys.stderr)
            results.append(f"error: {client['slug']}")
    return results
