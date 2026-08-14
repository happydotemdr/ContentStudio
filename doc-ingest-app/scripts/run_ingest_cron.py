"""Standalone CLI entry point for doc-ingest-app, invoked by Windows Task
Scheduler every 30 minutes (scripts/setup_ingest_task.py) or by hand for a
manual run. Mirrors pipeline-app/run_discovery_cron.py's shape.

Usage:
  python scripts/run_ingest_cron.py
  python scripts/run_ingest_cron.py --config path/to/config.yaml
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from doc_ingest import db, jobs, sync, worker
from doc_ingest.config import load_config


def _run_one_worker(db_path: Path, cfg) -> None:
    conn = db.get_connection(db_path)
    try:
        worker_id = f"{uuid.uuid4()}"
        job_id = jobs.claim_job(conn, worker_id)
        if job_id is None:
            return
        try:
            worker.process_job(conn, job_id, cfg, worker_id)
        except Exception as exc:
            print(f"job {job_id} raised: {exc}", file=sys.stderr)
    finally:
        conn.close()


def run_once(db_path: Path, cfg) -> None:
    conn = db.init_db(db_path)
    try:
        reclaimed = jobs.reclaim_stale_jobs(conn, cfg, cfg.tmp_root)
        if reclaimed:
            print(f"reclaimed {len(reclaimed)} stale job(s)")

        resumed = worker.resume_unlocked_conversions(conn, cfg)
        if resumed:
            print(f"resumed lock-verify for {len(resumed)} conversion(s)")

        counts = sync.sync_source_files(conn, cfg.input_root)
        print(f"scan: {counts}")

        created = jobs.enqueue_pending_jobs(conn)
        print(f"enqueued {created} job(s)")
    finally:
        conn.close()

    deadline = time.monotonic() + cfg.run_time_budget_s
    with ThreadPoolExecutor(max_workers=cfg.worker_pool_size) as pool:
        while time.monotonic() < deadline:
            probe_conn = db.get_connection(db_path)
            pending_exists = probe_conn.execute(
                "SELECT 1 FROM conversion_jobs WHERE status = 'pending' LIMIT 1"
            ).fetchone()
            probe_conn.close()
            if not pending_exists:
                break
            futures = [pool.submit(_run_one_worker, db_path, cfg) for _ in range(cfg.worker_pool_size)]
            for future in futures:
                future.result()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None, help="path to a YAML config overriding defaults")
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config) if args.config else None)
    db_path = HERE.parent / "doc_ingest.db"
    run_once(db_path, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
