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
import enum
import sys
from pathlib import Path

from pipeline_app import db, obs
from pipeline_app import (discovery_bluesky, discovery_facebook, discovery_instagram,
                          discovery_linkedin, discovery_x, discovery_youtube)
from pipeline_app.discovery_engine import run_discovery
from pipeline_app.discovery_notify import notify
from pipeline_app.discovery_scheduling import ScheduleConfigError, is_due

HERE = Path(__file__).resolve().parent


class Exit(enum.IntEnum):
    OK                  = 0
    LOCKED              = 10
    NO_WORK             = 11
    NOTIFY_FAILED       = 12
    HANDLES_ERRORED     = 13
    ALL_HANDLES_ERRORED = 14
    RUN_FAILED          = 15
    SCHEDULER_WEDGED    = 16
    STARTUP_FAILED      = 17


EXIT_REASON: dict[Exit, str] = {
    Exit.OK: "clean run, or nothing was due",
    Exit.LOCKED: "another discovery run holds the single-flight lock",
    Exit.NO_WORK: "every included handle was skipped -- no adapter call was made",
    Exit.NOTIFY_FAILED: "the run finished but the notification email was not sent",
    Exit.HANDLES_ERRORED: "one or more handles errored",
    Exit.ALL_HANDLES_ERRORED: "every handle this run attempted errored",
    Exit.RUN_FAILED: "the run crashed or exceeded its deadline",
    Exit.SCHEDULER_WEDGED: "the stored schedule settings cannot be evaluated",
    Exit.STARTUP_FAILED: "startup failed before any run could be recorded",
}


def classify_exit(result: dict | None, *, notify_ok: bool = True) -> Exit:
    """Map one terminal run outcome onto the documented exit-code contract.

    Pure -- no DB, no clock, no I/O -- so the contract table is testable as
    data. When several conditions hold the code is the numeric maximum, and
    Exit's values are ordered by severity precisely so that max() is the rule.
    """
    codes = [Exit.OK]
    if result is not None:
        status = result["status"]
        counts = result.get("counts") or {}
        attempted, failed = counts.get("attempted", 0), counts.get("failed", 0)
        if status == "locked":
            codes.append(Exit.LOCKED)
        elif status == "failed":
            codes.append(Exit.RUN_FAILED)
        elif failed and attempted and failed >= attempted:
            codes.append(Exit.ALL_HANDLES_ERRORED)
        elif failed:
            codes.append(Exit.HANDLES_ERRORED)
        elif attempted == 0 and counts.get("skipped", 0):
            codes.append(Exit.NO_WORK)
    if not notify_ok:
        codes.append(Exit.NOTIFY_FAILED)
    return Exit(max(codes))


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
        # Both plain modules, not instances: Facebook's one dataset serves Pages
        # and personal profiles alike, and X has one working mode, so neither
        # needs LinkedIn's per-instance cache or its bound-mode class.
        "facebook": discovery_facebook,
        "x": discovery_x,
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
    obs.log("discovery.wake", level="info", mode=args.mode, repo_root=str(repo_root))
    try:
        db.init_db(db_path, schema_path)
        conn = db.get_connection(db_path)
    except Exception as exc:  # noqa: BLE001 - a corrupt/locked pipeline.db, a
        # missing schema.sql or a broken venv kills the run before any row
        # exists, which is otherwise indistinguishable from "the scheduler
        # never fired" (D-06).
        obs.log("discovery.startup_failed", level="error",
                error=f"{type(exc).__name__}: {exc}", db_path=str(db_path))
        print(f"discovery startup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return Exit.STARTUP_FAILED
    obs.record_event(conn, kind="discovery.wake", severity="info",
                     source="run_discovery_cron", message=f"wake: mode={args.mode}")
    notify_ok = True
    result = None
    try:
        if args.mode == "scheduled":
            try:
                due = _is_due_now(conn)
            except ScheduleConfigError as exc:
                obs.record_event(conn, kind="discovery.scheduler_wedged", severity="critical",
                                 source="run_discovery_cron", message=str(exc))
                print(f"discovery scheduler is wedged: {exc}", file=sys.stderr)
                return Exit.SCHEDULER_WEDGED
            if not due:
                return classify_exit(result, notify_ok=notify_ok)
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
                notify_ok = bool(notify(conn, repo_root, result["run_row_id"]))
                if not notify_ok:
                    message = "notification email was not sent (no API key, or the send failed)"
            except Exception as exc:  # noqa: BLE001 - notification must never abort the run,
                # but it must not be invisible either: the email is the only push
                # channel this system has, so a failure to send is exactly the
                # failure that cannot announce itself (D-01).
                notify_ok = False
                message = f"notification raised: {type(exc).__name__}: {exc}"
            if not notify_ok:
                print(f"discovery notification failed: {message}", file=sys.stderr)
                obs.record_event(conn, kind="discovery.notify_failed", severity="error",
                                 source="run_discovery_cron", message=message,
                                 run_id=result["run_row_id"])
    finally:
        conn.close()
    code = classify_exit(result, notify_ok=notify_ok)
    if code is not Exit.OK:
        print(f"exit {int(code)} ({code.name}): {EXIT_REASON[code]}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
