"""Weekly audit entry point.

Usage:
  python scripts/run_client_audit.py [--config path.yaml]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from coach_prep_app import audit, config, db, doc_ingest_reader, google_clients, notify


def _default_config_path() -> Path | None:
    # Windows Task Scheduler never passes --config -- without this
    # fallback, load_config(None) silently ignores the operator's real
    # config (in particular pending_review_drive_folder_id, required by
    # placement_check) the moment this runs unattended. Same fix as
    # run_coachprep_cron.py's (Task 22).
    default = HERE.parent / "config.yaml"
    return default if default.exists() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)

    config_path = Path(args.config) if args.config else _default_config_path()
    cfg = config.load_config(config_path)
    config.ensure_doc_ingest_importable(cfg.doc_ingest_app_root)

    conn = db.init_db(HERE.parent / "coach_prep.db")
    doc_ingest_conn = doc_ingest_reader.open_readonly(cfg.doc_ingest_db_path)
    try:
        drive_service = google_clients.build_drive_service(cfg)
        since_iso = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)).isoformat()
        report = audit.build_report(conn, doc_ingest_conn, drive_service, cfg, since_iso)
        subject, text = audit.render_report_email(report)
        notify.send_email(subject, text, recipient=cfg.notify_recipient)
        print(text)
    finally:
        conn.close()
        doc_ingest_conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
