"""Standalone CLI entry point for the discovery engine. This is the single
execution path for every trigger -- Windows Task Scheduler's 15-minute
wake (--mode scheduled), the UI's Run Now (--mode incremental), Run Now
(backfill) (--mode backfill), and handle validation (--mode validate_handle)
-- always invoked as a subprocess, never imported into the running
pipeline-app web process (see the design spec's "Concurrency and execution
model"). Run from anywhere; --repo-root defaults to this file's grandparent.

Usage:
  python run_discovery_cron.py --mode scheduled
  python run_discovery_cron.py --mode incremental
  python run_discovery_cron.py --mode backfill --backfill-start 2026-06-01 --backfill-end 2026-06-30
  python run_discovery_cron.py --mode validate_handle --handle-id 42
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from pipeline_app import db
from pipeline_app import discovery_bluesky, discovery_instagram, discovery_linkedin, discovery_youtube
from pipeline_app.discovery_engine import run_discovery
from pipeline_app.discovery_notify import notify
from pipeline_app.discovery_scheduling import is_due

HERE = Path(__file__).resolve().parent


def build_adapters():
    # LinkedIn's two modes are separate instances, not one shared object: each
    # keeps its own enumerate cache, and a person and a company can have the
    # same URL slug.
    return {
        "youtube": discovery_youtube,
        "bluesky": discovery_bluesky,
        "instagram": discovery_instagram,
        "linkedin-profile": discovery_linkedin.profile_adapter(),
        "linkedin-company": discovery_linkedin.company_adapter(),
    }


def _is_due_now(conn) -> bool:
    settings = db.get_settings(conn)
    return is_due(
        _dt.datetime.now(_dt.timezone.utc), settings["timezone"],
        settings["time_of_day"], settings["last_scheduled_run_date"],
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", required=True,
                     choices=["scheduled", "incremental", "backfill", "validate_handle"])
    ap.add_argument("--backfill-start")
    ap.add_argument("--backfill-end")
    ap.add_argument("--handle-id", type=int)
    ap.add_argument("--repo-root", default=str(HERE.parent))
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root)
    if args.mode == "backfill" and not (args.backfill_start and args.backfill_end):
        ap.error("--mode backfill requires --backfill-start and --backfill-end")
    if args.mode == "validate_handle" and args.handle_id is None:
        ap.error("--mode validate_handle requires --handle-id")

    # Schema init happens BEFORE any due-check or run attempt -- on the very
    # first-ever scheduled wake (no pipeline.db yet), sqlite3.connect silently
    # creates an empty file, and db.get_settings against a table-less DB
    # raises OperationalError. init_db is idempotent (Task 1's IF NOT EXISTS
    # everywhere), so running it on every invocation, scheduled or not, is
    # always safe.
    db_path = repo_root / "pipeline-app" / "pipeline.db"
    schema_path = HERE / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    try:
        if args.mode == "scheduled":
            if not _is_due_now(conn):
                return 0
            trigger, mode = "scheduled", "incremental"
        elif args.mode == "incremental":
            trigger, mode = "manual", "incremental"
        elif args.mode == "backfill":
            trigger, mode = "manual", "backfill"
        else:
            trigger, mode = "manual", "validate_handle"

        result = run_discovery(
            conn, repo_root, build_adapters(), trigger=trigger, mode=mode,
            backfill_start=args.backfill_start, backfill_end=args.backfill_end,
            handle_id=args.handle_id,
        )
        print(f"run {result['run_row_id']}: {result['status']}")

        if args.mode == "scheduled" and result["status"] != "locked":
            try:
                notify(conn, repo_root, result["run_row_id"])
            except Exception as exc:  # noqa: BLE001 - notification must never affect run status/exit code
                print(f"discovery notification failed: {exc}", file=sys.stderr)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
