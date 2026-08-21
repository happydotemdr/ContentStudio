# tests/test_jobs.py
import datetime as dt
import threading
import time

import pytest

from doc_ingest import jobs
from doc_ingest.config import Config


def _seed_source_file(conn, rel_path="a.pdf", content_hash="hash1"):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, content_hash, first_seen_at, last_seen_at) "
        "VALUES (?, 'pdf', 'convertible', ?, ?, ?)",
        (rel_path, content_hash, now, now),
    )
    conn.commit()
    return conn.execute("SELECT id FROM source_files WHERE rel_path = ?", (rel_path,)).fetchone()[0]


def test_enqueue_creates_a_pending_job_for_a_brand_new_file(conn):
    _seed_source_file(conn)
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1
    row = conn.execute("SELECT status FROM conversion_jobs").fetchone()
    assert row[0] == "pending"


def test_enqueue_does_not_duplicate_an_already_pending_job(conn):
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    created_again = jobs.enqueue_pending_jobs(conn)
    assert created_again == 0
    count = conn.execute("SELECT COUNT(*) FROM conversion_jobs").fetchone()[0]
    assert count == 1


def test_enqueue_skips_a_source_file_with_a_current_matching_conversion(conn):
    source_id = _seed_source_file(conn, content_hash="hash1")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "source_hash_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, 1, 'a.pdf.md', 'current', 'pdf', 'hash1', 'firecrawl-parse', ?)",
        (source_id, now),
    )
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 0


def test_enqueue_creates_a_new_job_when_content_hash_changed(conn):
    source_id = _seed_source_file(conn, content_hash="hash1")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "source_hash_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, 1, 'a.pdf.md', 'current', 'pdf', 'hash1', 'firecrawl-parse', ?)",
        (source_id, now),
    )
    conn.execute("UPDATE source_files SET content_hash = 'hash2' WHERE id = ?", (source_id,))
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1


def test_enqueue_skips_a_source_file_already_failed_at_this_exact_version(conn):
    source_id = _seed_source_file(conn, content_hash="hash1")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, source_hash_at_attempt, created_at) "
        "VALUES (?, 'failed', 'hash1', ?)",
        (source_id, now),
    )
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 0


def test_enqueue_retries_after_a_failure_once_the_source_changes(conn):
    source_id = _seed_source_file(conn, content_hash="hash1")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, source_hash_at_attempt, created_at) "
        "VALUES (?, 'failed', 'hash1', ?)",
        (source_id, now),
    )
    conn.execute("UPDATE source_files SET content_hash = 'hash2' WHERE id = ?", (source_id,))
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1


def _seed_gdoc_source_file(conn, rel_path="a.gdoc", drive_modified_time="2026-08-01T00:00:00Z"):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, drive_modified_time, "
        "first_seen_at, last_seen_at) VALUES (?, 'gdoc', 'gdoc_pointer', ?, ?, ?)",
        (rel_path, drive_modified_time, now, now),
    )
    conn.commit()
    return conn.execute("SELECT id FROM source_files WHERE rel_path = ?", (rel_path,)).fetchone()[0]


def test_enqueue_includes_gdoc_pointer_rows(conn):
    _seed_gdoc_source_file(conn)
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1


def test_enqueue_ignores_content_hash_for_a_gdoc_row(conn):
    """The bug this guards: a .gdoc source_files row's content_hash is the
    sha256 of its own static 176-byte stub -- NEVER meaningful for change
    detection (spec §4 step 3). If enqueue ever compared it against
    source_hash_at_conversion for a gdoc row (a hex digest never equals an
    ISO timestamp), every gdoc would re-enqueue on every single wake
    forever, even with an unchanged Drive modifiedTime."""
    source_id = _seed_gdoc_source_file(conn, drive_modified_time="2026-08-01T00:00:00Z")
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "drive_modified_time_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, 1, 'a.gdoc.md', 'current', 'gdoc', '2026-08-01T00:00:00Z', 'google-docs-export', ?)",
        (source_id, now),
    )
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 0  # unchanged Drive modifiedTime -- must NOT re-enqueue


def test_enqueue_creates_a_new_gdoc_job_when_drive_modified_time_advances(conn):
    source_id = _seed_gdoc_source_file(conn, drive_modified_time="2026-08-12T00:00:00Z")
    now = "2026-08-01T00:05:00+00:00"
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "drive_modified_time_at_conversion, conversion_tool, converted_at) "
        "VALUES (?, 1, 'a.gdoc.md', 'current', 'gdoc', '2026-08-01T00:00:00Z', 'google-docs-export', ?)",
        (source_id, now),
    )
    conn.commit()
    created = jobs.enqueue_pending_jobs(conn)
    assert created == 1  # Drive modifiedTime advanced -- must re-enqueue


def test_claim_job_returns_none_when_nothing_pending(conn):
    assert jobs.claim_job(conn, worker_id="w1") is None


def test_claim_job_claims_a_pending_job_and_stamps_ownership(conn):
    source_id = _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    assert job_id is not None
    row = conn.execute(
        "SELECT status, worker_id, claimed_at, heartbeat_at, source_hash_at_attempt FROM conversion_jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    assert row[0] == "claimed"
    assert row[1] == "w1"
    assert row[2] is not None
    assert row[3] is not None
    assert row[4] == "hash1"


def test_claim_deterministically_excludes_a_second_connection(tmp_db_path):
    """Deterministic version of the concurrency guarantee: connection A opens
    a manual BEGIN IMMEDIATE and claims the only pending job WITHOUT
    committing yet; connection B's claim_job runs concurrently on a second
    thread. B's BEGIN IMMEDIATE must block until A releases the write lock
    (busy_timeout=5000 on both connections, set in db.get_connection), and
    once it does, B must see the job already claimed and return None -- not
    race for it. This forces the exact contention window regardless of OS
    thread scheduling, unlike a bare threading.Barrier, which only
    synchronizes entry and can let one thread finish before the other starts."""
    from doc_ingest import db

    setup_conn = db.init_db(tmp_db_path)
    _seed_source_file(setup_conn)
    jobs.enqueue_pending_jobs(setup_conn)
    setup_conn.close()

    a_holds_lock = threading.Event()
    a_can_commit = threading.Event()
    b_result: dict = {}

    def _claim_a():
        # Created and closed entirely within this thread -- db.get_connection
        # deliberately leaves check_same_thread at its default (True, Task 2),
        # so a connection object must never cross a thread boundary.
        conn_a = db.get_connection(tmp_db_path)
        try:
            conn_a.execute("BEGIN IMMEDIATE")
            row = conn_a.execute("SELECT id FROM conversion_jobs WHERE status = 'pending' LIMIT 1").fetchone()
            conn_a.execute("UPDATE conversion_jobs SET status = 'claimed', worker_id = 'a' WHERE id = ?", (row[0],))
            a_holds_lock.set()
            a_can_commit.wait(timeout=5)
            conn_a.execute("COMMIT")
        finally:
            conn_a.close()

    def _claim_b():
        # Same rule as conn_a: created and closed entirely within this thread.
        conn_b = db.get_connection(tmp_db_path)
        try:
            a_holds_lock.wait(timeout=5)
            try:
                b_result["job_id"] = jobs.claim_job(conn_b, worker_id="b")
            except Exception as exc:
                b_result["error"] = exc
        finally:
            conn_b.close()

    t_a = threading.Thread(target=_claim_a)
    t_b = threading.Thread(target=_claim_b)
    t_a.start()
    t_b.start()
    time.sleep(0.05)  # give B time to enter its (blocked) BEGIN IMMEDIATE before A commits
    a_can_commit.set()
    t_a.join(timeout=5)
    t_b.join(timeout=5)

    assert "error" not in b_result, f"claim_job raised: {b_result.get('error')}"
    assert b_result["job_id"] is None  # A already claimed the only pending job before B's transaction opened


def test_two_connections_racing_one_pending_job_only_one_wins(tmp_db_path):
    """Closer-to-production shape than the deterministic test above: two
    real workers hitting claim_job concurrently with no artificial ordering.
    Exceptions are captured rather than left to escape the thread silently,
    so a broken claim implementation fails this test loudly instead of just
    producing a confusing wrong count."""
    from doc_ingest import db

    setup_conn = db.init_db(tmp_db_path)
    _seed_source_file(setup_conn)
    jobs.enqueue_pending_jobs(setup_conn)
    setup_conn.close()

    results = []
    barrier = threading.Barrier(2)

    def _race(worker_id):
        conn = db.get_connection(tmp_db_path)
        try:
            barrier.wait()
            results.append(jobs.claim_job(conn, worker_id=worker_id))
        except Exception as exc:
            results.append(exc)
        finally:
            conn.close()

    t1 = threading.Thread(target=_race, args=("w1",))
    t2 = threading.Thread(target=_race, args=("w2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not any(isinstance(r, Exception) for r in results), results
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert results.count(None) == 1


def test_heartbeat_updates_the_timestamp(conn):
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    first = conn.execute("SELECT heartbeat_at FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()[0]
    time.sleep(0.01)
    jobs.heartbeat(conn, job_id, worker_id="w1")
    second = conn.execute("SELECT heartbeat_at FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()[0]
    assert second >= first


def test_heartbeat_is_a_noop_for_a_job_this_worker_no_longer_owns(conn):
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    jobs.heartbeat(conn, job_id, worker_id="an-impostor")
    row = conn.execute("SELECT worker_id FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row[0] == "w1"


def test_reclaim_resets_a_job_whose_heartbeat_is_stale(conn, tmp_path):
    cfg = Config(reclaim_staleness_threshold_s=1)
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    stale_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)).isoformat()
    conn.execute("UPDATE conversion_jobs SET heartbeat_at = ? WHERE id = ?", (stale_time, job_id))
    conn.commit()
    reclaimed = jobs.reclaim_stale_jobs(conn, cfg, tmp_path)
    assert job_id in reclaimed
    row = conn.execute("SELECT status, worker_id FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row[0] == "pending"
    assert row[1] is None


def test_reclaim_leaves_a_live_job_alone(conn, tmp_path):
    cfg = Config(reclaim_staleness_threshold_s=600)
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    reclaimed = jobs.reclaim_stale_jobs(conn, cfg, tmp_path)
    assert job_id not in reclaimed
    row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row[0] == "claimed"


def test_reclaim_removes_the_orphaned_tmp_dir(conn, tmp_path):
    cfg = Config(reclaim_staleness_threshold_s=1)
    _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    job_tmp_dir = tmp_path / f"job-{job_id}"
    job_tmp_dir.mkdir()
    (job_tmp_dir / "staged.pdf").write_bytes(b"partial")
    conn.execute("UPDATE conversion_jobs SET tmp_dir = ?, heartbeat_at = ? WHERE id = ?",
                 (str(job_tmp_dir), "2020-01-01T00:00:00+00:00", job_id))
    conn.commit()
    jobs.reclaim_stale_jobs(conn, cfg, tmp_path)
    assert not job_tmp_dir.exists()


def test_reclaim_does_not_reprocess_a_placing_job_whose_conversion_already_landed(conn, tmp_path):
    """A job stuck at 'placing' with a stale heartbeat because the lock step
    (Task 15) hasn't been confirmed yet must NOT be reset to 'pending' --
    that would trigger a wasted reconversion of a source that already has a
    valid 'current' conversion; only its lock confirmation is outstanding,
    which worker.resume_unlocked_conversions retries independently every
    wake (spec §4 step 9)."""
    cfg = Config(reclaim_staleness_threshold_s=1)
    source_id = _seed_source_file(conn)
    jobs.enqueue_pending_jobs(conn)
    job_id = jobs.claim_job(conn, worker_id="w1")
    stale_time = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)).isoformat()
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "UPDATE conversion_jobs SET status = 'placing', heartbeat_at = ? WHERE id = ?",
        (stale_time, job_id),
    )
    conn.execute(
        "INSERT INTO conversions (source_file_id, job_id, version_number, output_path, status, "
        "source_type, conversion_tool, converted_at) "
        "VALUES (?, ?, 1, 'a.pdf.md', 'current', 'pdf', 'firecrawl-parse', ?)",
        (source_id, job_id, now),
    )
    conn.commit()

    reclaimed = jobs.reclaim_stale_jobs(conn, cfg, tmp_path)

    assert job_id not in reclaimed
    row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert row[0] == "placing"


# --- clear_failed_jobs: the operator escape hatch ---------------------------
#
# enqueue_pending_jobs suppresses a retry when a file already failed at
# exactly this source version. The suppression key is the SOURCE version
# alone, so nothing about it changes when the CONVERTER does -- a fixed
# gauntlet can never reach a file that failed under the old one. Discovered
# 2026-08-21: after fixing the gsheet gauntlet, a full ingest run enqueued 0
# jobs and all six gsheets stayed failed.

def _fail_job_for(conn, source_file_id, content_hash="hash1"):
    now = "2026-08-13T00:00:00+00:00"
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, source_hash_at_attempt, "
        "failure_reason, created_at) VALUES (?, 'failed', ?, 'row_count_mismatch', ?)",
        (source_file_id, content_hash, now),
    )
    conn.commit()


def test_enqueue_does_not_retry_a_file_that_failed_at_this_same_version(conn):
    """The behavior clear_failed_jobs exists to override -- pinned here so the
    escape hatch below is testing against a real block, not a no-op."""
    source_file_id = _seed_source_file(conn, "book-list.gsheet")
    _fail_job_for(conn, source_file_id)
    assert jobs.enqueue_pending_jobs(conn) == 0


def test_clear_failed_jobs_lets_a_fixed_converter_retry(conn):
    source_file_id = _seed_source_file(conn, "book-list.gsheet")
    _fail_job_for(conn, source_file_id)

    cleared = jobs.clear_failed_jobs(conn, "%.gsheet")

    assert cleared == ["book-list.gsheet"]
    assert jobs.enqueue_pending_jobs(conn) == 1


def test_clear_failed_jobs_leaves_non_matching_paths_alone(conn):
    """A targeted clear must not resurrect files that fail for unrelated
    reasons -- clearing '%.gsheet' after a gsheet fix must not re-attempt the
    docx files that still fail word-count parity."""
    gsheet_id = _seed_source_file(conn, "book-list.gsheet")
    docx_id = _seed_source_file(conn, "module.docx", content_hash="hash2")
    _fail_job_for(conn, gsheet_id)
    _fail_job_for(conn, docx_id, content_hash="hash2")

    cleared = jobs.clear_failed_jobs(conn, "%.gsheet")

    assert cleared == ["book-list.gsheet"]
    assert jobs.enqueue_pending_jobs(conn) == 1
    still_failed = conn.execute(
        "SELECT sf.rel_path FROM conversion_jobs cj JOIN source_files sf ON sf.id = cj.source_file_id "
        "WHERE cj.status = 'failed'"
    ).fetchall()
    assert still_failed == [("module.docx",)]


def test_clear_failed_jobs_matching_nothing_is_a_no_op(conn):
    source_file_id = _seed_source_file(conn, "book-list.gsheet")
    _fail_job_for(conn, source_file_id)

    assert jobs.clear_failed_jobs(conn, "%.xlsx") == []
    assert jobs.enqueue_pending_jobs(conn) == 0


def test_clear_failed_jobs_does_not_touch_complete_jobs(conn):
    """Only failed rows are droppable -- a completed job is the record that a
    conversion happened, and losing it would make the file look never-attempted."""
    source_file_id = _seed_source_file(conn, "book-list.gsheet")
    conn.execute(
        "INSERT INTO conversion_jobs (source_file_id, status, created_at) "
        "VALUES (?, 'complete', '2026-08-13T00:00:00+00:00')",
        (source_file_id,),
    )
    conn.commit()

    assert jobs.clear_failed_jobs(conn, "%.gsheet") == []
    remaining = conn.execute("SELECT status FROM conversion_jobs").fetchall()
    assert remaining == [("complete",)]
