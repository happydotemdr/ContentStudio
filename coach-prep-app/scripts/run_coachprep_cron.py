"""Windows Task Scheduler entry point, invoked every 4 hours.

Usage:
  python scripts/run_coachprep_cron.py [--config path.yaml]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from coach_prep_app import config, db, doc_ingest_reader, google_clients, orchestrator


def _default_config_path() -> Path | None:
    """Windows Task Scheduler never passes --config, so a real deployment's
    config (in particular pending_review_drive_folder_id, required by Tasks
    19/23) has to come from somewhere other than a CLI flag. Default to
    <app_root>/config.yaml when it exists; fall through to None (config.
    load_config's own env-var/dataclass-default resolution) otherwise."""
    candidate = HERE.parent / "config.yaml"
    return candidate if candidate.exists() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    config_path = Path(args.config) if args.config else _default_config_path()
    cfg = config.load_config(config_path)
    config.ensure_doc_ingest_importable(cfg.doc_ingest_app_root)

    if not cfg.pending_review_drive_folder_id:
        print(
            "run_coachprep_cron: pending_review_drive_folder_id is not configured -- "
            "set it in coach-prep-app/config.yaml before this can run for real",
            file=sys.stderr,
        )
        return 1

    conn = db.init_db(HERE.parent / "coach_prep.db")
    doc_ingest_conn = doc_ingest_reader.open_readonly(cfg.doc_ingest_db_path)
    try:
        calendar_service = google_clients.build_calendar_service(cfg)
        gmail_service = google_clients.build_gmail_service(cfg)
        drive_service = google_clients.build_drive_service(cfg)
        results = orchestrator.run_once(
            conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg,
            dt.datetime.now(dt.timezone.utc),
        )
        error_count = 0
        for r in results:
            print(r)
            if r.startswith("error: ") or r == "publish_ok_notify_failed":
                error_count += 1
    finally:
        conn.close()
        doc_ingest_conn.close()
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
