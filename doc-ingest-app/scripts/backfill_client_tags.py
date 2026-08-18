"""One-time (re-runnable) backfill of `client` tags onto already-converted
meeting-note and session-outline files. DB-ONLY -- never rewrites a
converted file, because lock.py's read-only lock is deliberately
one-directional (see that module's docstring). Re-running is always safe: it
re-derives the tag from the exact same classifier worker.py now runs on
every new/changed file, so backfill and ongoing tagging can never diverge.

Usage:
  python scripts/backfill_client_tags.py --dry-run
  python scripts/backfill_client_tags.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from doc_ingest import calendar_client, client_tagging, config, db, frontmatter


def _candidate_conversions(conn):
    return conn.execute(
        "SELECT c.id, c.output_path, c.client, sf.rel_path FROM conversions c "
        "JOIN source_files sf ON sf.id = c.source_file_id WHERE c.status = 'current'"
    ).fetchall()


def build_report(conn, cfg, calendar_service_factory) -> list[dict]:
    report = []
    for conversion_id, output_path, current_client, rel_path in _candidate_conversions(conn):
        if not (rel_path.startswith(client_tagging.SESSION_OUTLINES_PREFIX)
                or rel_path.startswith(client_tagging.MEETING_NOTES_PREFIX)):
            continue
        final_path = cfg.converted_root / output_path
        _, body = frontmatter.parse(final_path.read_text(encoding="utf-8"))
        tag_result = client_tagging.classify(conn, rel_path, body, calendar_service_factory)
        report.append({
            "conversion_id": conversion_id,
            "rel_path": rel_path,
            "current_client": current_client,
            "classified_client": tag_result.frontmatter_extra.get("client"),
            "event_type": tag_result.event_type,
        })
    return report


def apply_report(conn, report: list[dict]) -> int:
    updated = 0
    with db.transaction(conn):
        for row in report:
            new_client = row["classified_client"]
            if new_client is None or new_client == row["current_client"]:
                continue
            conn.execute("UPDATE conversions SET client = ? WHERE id = ?", (new_client, row["conversion_id"]))
            updated += 1
    return updated


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--dry-run", action="store_true",
        help="explicit no-op -- dry run is already the default when --apply is omitted",
    )
    args = ap.parse_args(argv)

    cfg = config.load_config()
    conn = db.init_db(HERE.parent / "doc_ingest.db")
    try:
        report = build_report(conn, cfg, calendar_client.build_default_service)
        for row in report:
            suffix = f" ({row['event_type']})" if row["event_type"] else ""
            print(f"{row['rel_path']}: {row['current_client']!r} -> {row['classified_client']!r}{suffix}")
        unmatched = sum(1 for r in report if r["classified_client"] == "unmatched")
        print(f"\n{len(report)} client-scoped file(s) scanned, {unmatched} unmatched")
        if args.apply:
            updated = apply_report(conn, report)
            print(f"applied {updated} tag update(s)")
        else:
            print("dry run -- re-run with --apply to write these tags")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
