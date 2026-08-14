"""The DB-claimed job queue: enqueue, atomic claim, heartbeat, and
heartbeat-based reclaim (spec §4 steps 1, 4, 5). Deliberately NOT modeled on
pipeline_app.preflight.reconcile_orphaned_turns' unconditional startup sweep
-- that is safe only because pipeline-app is single-process; this app's
concurrent worker pool needs a liveness signal, not a blind reset."""
from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from doc_ingest import db


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def enqueue_pending_jobs(conn) -> int:
    """Local files (classification='convertible') and Drive-native files
    (classification='gdoc_pointer') use CONSISTENTLY SEPARATE change-detection
    signals -- never mixed. A local file's content_hash is meaningless for a
    176-byte .gdoc/.gsheet stub (spec §4 step 3: the stub never changes when
    the real document does), and a gdoc's drive_modified_time_at_conversion
    is never set for a local file. Branching on classification, rather than
    checking "if either signal differs," is what keeps these two comparisons
    from cross-contaminating each other."""
    created = 0
    now = _now_iso()
    with db.transaction(conn):
        rows = conn.execute(
            "SELECT id, classification, content_hash, drive_modified_time FROM source_files "
            "WHERE classification IN ('convertible', 'gdoc_pointer')"
        ).fetchall()
        for source_file_id, classification, content_hash, drive_modified_time in rows:
            in_flight = conn.execute(
                "SELECT 1 FROM conversion_jobs WHERE source_file_id = ? "
                "AND status IN ('pending','claimed','converting','placing')",
                (source_file_id,),
            ).fetchone()
            if in_flight:
                continue

            current = conn.execute(
                "SELECT source_hash_at_conversion, drive_modified_time_at_conversion "
                "FROM conversions WHERE source_file_id = ? AND status = 'current'",
                (source_file_id,),
            ).fetchone()

            needs_job = current is None
            if not needs_job:
                if classification == "gdoc_pointer":
                    prior_modified = current[1]
                    needs_job = drive_modified_time is not None and (
                        prior_modified is None or drive_modified_time > prior_modified
                    )
                else:
                    needs_job = content_hash is not None and content_hash != current[0]

            if needs_job:
                last_failed = conn.execute(
                    "SELECT source_hash_at_attempt, drive_modified_time_at_attempt "
                    "FROM conversion_jobs WHERE source_file_id = ? AND status = 'failed' "
                    "ORDER BY id DESC LIMIT 1",
                    (source_file_id,),
                ).fetchone()
                if last_failed is not None:
                    if classification == "gdoc_pointer":
                        already_failed_this_version = (
                            drive_modified_time is not None and drive_modified_time == last_failed[1]
                        )
                    else:
                        already_failed_this_version = (
                            content_hash is not None and content_hash == last_failed[0]
                        )
                    if already_failed_this_version:
                        continue  # already failed at exactly this version -- don't retry every wake

                conn.execute(
                    "INSERT INTO conversion_jobs (source_file_id, status, created_at) VALUES (?, 'pending', ?)",
                    (source_file_id, now),
                )
                created += 1
    return created


def claim_job(conn, worker_id: str) -> int | None:
    now = _now_iso()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT cj.id, sf.content_hash, sf.drive_modified_time FROM conversion_jobs cj "
            "JOIN source_files sf ON sf.id = cj.source_file_id "
            "WHERE cj.status = 'pending' ORDER BY cj.id LIMIT 1"
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return None
        job_id, content_hash, drive_modified_time = row
        cursor = conn.execute(
            "UPDATE conversion_jobs SET status = 'claimed', worker_id = ?, claimed_at = ?, "
            "heartbeat_at = ?, source_hash_at_attempt = ?, drive_modified_time_at_attempt = ? "
            "WHERE id = ? AND status = 'pending'",
            (worker_id, now, now, content_hash, drive_modified_time, job_id),
        )
        # BEGIN IMMEDIATE already made the SELECT-then-UPDATE atomic (no other
        # connection can hold the write lock at the same time), so rowcount
        # should always be 1 here -- checked anyway as the last line of
        # defense, not because the reasoning above is expected to be wrong.
        if cursor.rowcount != 1:
            conn.execute("ROLLBACK")
            return None
        conn.execute("COMMIT")
        return job_id
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def heartbeat(conn, job_id: int, worker_id: str) -> None:
    with db.transaction(conn):
        conn.execute(
            "UPDATE conversion_jobs SET heartbeat_at = ? WHERE id = ? AND worker_id = ? "
            "AND status IN ('claimed','converting','placing')",
            (_now_iso(), job_id, worker_id),
        )


def reclaim_stale_jobs(conn, cfg, tmp_root: Path) -> list[int]:
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=cfg.reclaim_staleness_threshold_s)).isoformat()
    reclaimed: list[int] = []
    with db.transaction(conn):
        rows = conn.execute(
            "SELECT id, tmp_dir, status FROM conversion_jobs "
            "WHERE status IN ('claimed','converting','placing') AND heartbeat_at < ?",
            (cutoff,),
        ).fetchall()
        for job_id, tmp_dir, status in rows:
            if status == "placing":
                already_written = conn.execute(
                    "SELECT 1 FROM conversions WHERE job_id = ? AND status = 'current'", (job_id,)
                ).fetchone()
                if already_written:
                    # The write + DB commit (spec §4 step 9(a)/(b)) already
                    # landed -- only the lock confirmation (9(c)/(d)) is
                    # outstanding, and worker.resume_unlocked_conversions
                    # retries that independently on every wake. Resetting to
                    # 'pending' here would trigger a wasted reconversion of a
                    # source that already has a valid current conversion.
                    continue
            if tmp_dir:
                tmp_path = Path(tmp_dir)
                if tmp_path.exists():
                    shutil.rmtree(tmp_path, ignore_errors=True)
            conn.execute(
                "UPDATE conversion_jobs SET status = 'pending', worker_id = NULL, "
                "claimed_at = NULL, heartbeat_at = NULL, tmp_dir = NULL WHERE id = ?",
                (job_id,),
            )
            reclaimed.append(job_id)
    return reclaimed
