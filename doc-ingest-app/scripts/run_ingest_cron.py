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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from doc_ingest import db, drive_client, drive_sync, jobs, manifest, sync, worker
from doc_ingest.config import load_config


def _run_one_worker(db_path: Path, cfg) -> None:
    # NOTHING in this function may raise into the pool. A future that carries
    # an exception re-raises it at future.result() in run_once's drain loop,
    # which would escape the whole drain block and skip manifest regeneration
    # for the wake. jobs.claim_job in particular issues a raw BEGIN IMMEDIATE
    # from up to worker_pool_size concurrent connections against a 5s
    # busy_timeout, so a transient sqlite3.OperationalError (SQLITE_BUSY) is a
    # real possibility under contention -- and db.get_connection can fail too
    # (locked/absent db file). All three steps are covered by one except.
    conn = None
    job_id = None
    try:
        conn = db.get_connection(db_path)
        worker_id = f"{uuid.uuid4()}"
        job_id = jobs.claim_job(conn, worker_id)
        if job_id is None:
            return
        worker.process_job(conn, job_id, cfg, worker_id)
    except Exception as exc:
        label = f"job {job_id}" if job_id is not None else "worker"
        print(f"{label} raised: {exc}", file=sys.stderr)
    finally:
        # conn is None only if get_connection itself failed -- nothing to close.
        if conn is not None:
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

        try:
            service = drive_client.build_default_service(cfg)
            drive_updated = drive_sync.sync_drive_metadata(conn, service, cfg)
            print(f"drive check: updated {drive_updated} gdoc/gsheet row(s)")
        except Exception as exc:
            # Missing/expired Drive credentials (e.g. SETUP.md's one-time
            # consent hasn't been done yet on this machine) must not block
            # local-file processing -- log and continue with whatever
            # local-file jobs are ready.
            print(f"drive check skipped: {exc}", file=sys.stderr)

        created = jobs.enqueue_pending_jobs(conn)
        print(f"enqueued {created} job(s)")
    finally:
        conn.close()

    deadline = time.monotonic() + cfg.run_time_budget_s
    # The whole drain block is guarded so that manifest regeneration below is
    # reached no matter what. _run_one_worker is already exception-proof, but a
    # failure in the probe query, in pool creation, or in an OS thread spawn
    # would otherwise abort the wake before the manifest is rewritten.
    try:
        # Deliberately NOT `with ThreadPoolExecutor(...) as pool:` -- the
        # context manager's __exit__ calls shutdown(wait=True), which blocks
        # until every worker thread finishes. That would re-introduce the exact
        # unbounded wait the job_timeout_s guard below exists to prevent: a
        # thread stuck in firecrawl.parse() or a Drive call would wedge the
        # wake at block exit even after we stopped waiting on its future.
        pool = ThreadPoolExecutor(max_workers=cfg.worker_pool_size)
        timed_out = False
        try:
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
                    try:
                        future.result(timeout=cfg.job_timeout_s)
                    except FutureTimeoutError:
                        timed_out = True
                        # HONEST LIMITATION: ThreadPoolExecutor cannot kill a
                        # running thread. This timeout only stops the MAIN
                        # thread from waiting on a stuck future forever, so the
                        # wake can finish (and regenerate the manifest) and the
                        # NEXT scheduled wake can fire -- Task Scheduler's
                        # default is skip-if-already-running, so an unbounded
                        # wait wedges the pipeline permanently with no signal.
                        # The stuck worker thread itself keeps running in the
                        # background; the interpreter's own atexit join may
                        # still delay process exit until it returns. Real
                        # cancellation would need a process-based pool, which
                        # is out of scope here. The job row is not orphaned
                        # either way: its heartbeat goes stale and the next
                        # wake's jobs.reclaim_stale_jobs picks it back up.
                        print(
                            f"job future exceeded job_timeout_s ({cfg.job_timeout_s}s), "
                            f"abandoning wait (worker thread may still be running)",
                            file=sys.stderr,
                        )
                if timed_out:
                    # Don't pile more work onto a pool whose threads are stuck;
                    # end the drain and let the next wake retry.
                    break
        finally:
            # wait=False only on the timeout path, so the normal case keeps its
            # existing guarantee that all workers are done before the manifest
            # is regenerated.
            pool.shutdown(wait=not timed_out, cancel_futures=True)
    except Exception as exc:
        print(f"drain loop aborted: {exc}", file=sys.stderr)

    manifest_conn = db.get_connection(db_path)
    try:
        manifest.regenerate(manifest_conn, cfg.output_root)
    finally:
        manifest_conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None, help="path to a YAML config overriding defaults")
    ap.add_argument(
        "--retry-failed", metavar="LIKE_PATTERN", default=None,
        help="clear failed-job rows for source files matching this SQL LIKE pattern "
             "(e.g. '%%.gsheet') so this run re-attempts them, then run normally. "
             "Use after fixing a converter or gauntlet bug -- enqueue_pending_jobs "
             "otherwise never retries a file that already failed at this source version.",
    )
    args = ap.parse_args(argv)

    cfg = load_config(Path(args.config) if args.config else None)
    db_path = HERE.parent / "doc_ingest.db"
    if args.retry_failed:
        conn = db.init_db(db_path)
        try:
            cleared = jobs.clear_failed_jobs(conn, args.retry_failed)
        finally:
            conn.close()
        print(f"cleared {len(cleared)} failed job(s) for retry:")
        for rel_path in cleared:
            print(f"  {rel_path}")
    run_once(db_path, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
