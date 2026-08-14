# tests/test_worker.py
from unittest.mock import patch

import pytest

from doc_ingest.config import Config
from doc_ingest import jobs, sync, worker


def _seed_pending_job(conn, tmp_input_root, rel_path="Folder/Notes.txt", content=b"hello world this is real text"):
    (tmp_input_root / "Folder").mkdir(parents=True, exist_ok=True)
    (tmp_input_root / rel_path).write_bytes(content)
    sync.sync_source_files(conn, tmp_input_root)
    jobs.enqueue_pending_jobs(conn)
    return jobs.claim_job(conn, worker_id="w1")


def test_process_job_happy_path_writes_commits_locks_and_indexes(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)
    job_id = _seed_pending_job(conn, input_root)

    with patch("doc_ingest.lock.apply_readonly_lock") as mock_lock, \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    job_row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "complete"

    conversion = conn.execute(
        "SELECT status, locked_confirmed_at, output_path, conversion_tool FROM conversions WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert conversion[0] == "current"
    assert conversion[1] is not None
    assert conversion[3] == "passthrough"  # .txt bypasses firecrawl entirely

    output_file = output_root / "converted" / conversion[2]
    assert output_file.exists()
    assert "hello world" in output_file.read_text(encoding="utf-8")
    mock_lock.assert_called_once_with(output_file)

    fts_row = conn.execute(
        "SELECT body FROM conversions_fts WHERE conversions_fts MATCH 'hello'"
    ).fetchone()
    assert fts_row is not None


def test_process_job_handles_an_extensionless_pdf_via_sniffed_signature(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)
    job_id = _seed_pending_job(conn, input_root, rel_path="Folder/report", content=b"%PDF-1.4 fake pdf bytes")

    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_client.parse.return_value = MagicMock(markdown="# Parsed from a sniffed PDF\n\nreal words here")
    with patch("firecrawl.Firecrawl", return_value=mock_client), \
         patch("doc_ingest.metadata_readers.read_pdf_page_count", return_value=1), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    job_row = conn.execute("SELECT status, failure_reason FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "complete", job_row[1]
    conversion = conn.execute("SELECT source_type FROM conversions WHERE job_id = ?", (job_id,)).fetchone()
    assert conversion[0] == "pdf"


def test_process_job_marks_failed_on_gauntlet_rejection(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root, size_ratio_floor=0.9)
    job_id = _seed_pending_job(conn, input_root, content=b"a source file with plenty of real bytes in it, much more than the tiny converted output below")

    def _fake_convert(staged_path, source_type, cfg_arg):
        from doc_ingest.convert import ConversionResult
        return ConversionResult(success=True, markdown_body="x", tool="firecrawl-parse", error=None)

    with patch("doc_ingest.worker._convert", side_effect=_fake_convert), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    job_row = conn.execute("SELECT status, failure_reason FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "failed"
    assert job_row[1] == "below_size_ratio_floor"
    assert not (output_root / "converted").exists() or not any((output_root / "converted").rglob("*.md"))


def test_process_job_supersedes_the_prior_current_version(conn, tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)

    with patch("doc_ingest.lock.apply_readonly_lock"), patch("doc_ingest.lock.verify_locked", return_value=True):
        job_id_1 = _seed_pending_job(conn, input_root, content=b"version one text content")
        worker.process_job(conn, job_id_1, cfg, worker_id="w1")

        (input_root / "Folder" / "Notes.txt").write_bytes(b"version two, different text content entirely")
        sync.sync_source_files(conn, input_root)
        jobs.enqueue_pending_jobs(conn)
        job_id_2 = jobs.claim_job(conn, worker_id="w1")
        worker.process_job(conn, job_id_2, cfg, worker_id="w1")

    statuses = conn.execute(
        "SELECT version_number, status FROM conversions ORDER BY version_number"
    ).fetchall()
    assert statuses == [(1, "superseded"), (2, "current")]


def test_process_job_leaves_the_job_at_placing_when_lock_confirmation_fails(conn, tmp_path):
    """verify_locked() returning False (no exception -- icacls "succeeded"
    but the read-back didn't confirm it) must NOT mark the job complete,
    per spec §4 step 9: a conversion with locked_confirmed_at unset is not
    done yet, whether or not an exception was involved."""
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)
    job_id = _seed_pending_job(conn, input_root)

    with patch("doc_ingest.lock.apply_readonly_lock"), patch("doc_ingest.lock.verify_locked", return_value=False):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    job_row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "placing"
    conversion = conn.execute("SELECT locked_confirmed_at FROM conversions WHERE job_id = ?", (job_id,)).fetchone()
    assert conversion[0] is None


def test_process_job_resumes_lock_only_after_a_simulated_crash(conn, tmp_path):
    """A job whose .md was written and committed as 'current' but never
    confirmed locked (process died between step 9(b) and 9(d)) must be
    re-locked on the next pass, not re-converted -- and the job itself must
    move to 'complete' only once resume actually succeeds."""
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root)
    job_id = _seed_pending_job(conn, input_root)

    with patch("doc_ingest.lock.apply_readonly_lock", side_effect=RuntimeError("simulated crash")):
        with pytest.raises(RuntimeError):
            worker.process_job(conn, job_id, cfg, worker_id="w1")

    conversion = conn.execute(
        "SELECT status, locked_confirmed_at, output_path FROM conversions WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert conversion[0] == "current"
    assert conversion[1] is None  # written, not yet confirmed locked
    job_row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "placing"  # NOT complete -- the lock never confirmed
    output_file = output_root / "converted" / conversion[2]
    assert output_file.exists()  # the write already happened

    with patch("doc_ingest.lock.apply_readonly_lock"), patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.resume_unlocked_conversions(conn, cfg)

    conversion_after = conn.execute(
        "SELECT locked_confirmed_at FROM conversions WHERE job_id = ?", (job_id,)
    ).fetchone()
    assert conversion_after[0] is not None
    job_row_after = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row_after[0] == "complete"


def test_process_job_updates_heartbeat_while_converting(conn, tmp_path):
    """Without a running heartbeat thread, heartbeat_at is stamped once at
    claim time and never again -- a slow real conversion would eventually
    look stale to reclaim_stale_jobs (Task 7) and get reclaimed out from
    under its own still-running worker. A short interval keeps this test
    fast (~0.15s) and non-flaky rather than waiting through the real
    30-second default."""
    import time

    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    cfg = Config(input_root=input_root, output_root=output_root, reclaim_heartbeat_interval_s=0.02)
    job_id = _seed_pending_job(conn, input_root)

    claimed_heartbeat = conn.execute(
        "SELECT heartbeat_at FROM conversion_jobs WHERE id = ?", (job_id,)
    ).fetchone()[0]

    observed = {}
    real_convert = worker._convert

    def _slow_convert(staged_path, source_type, cfg_arg):
        time.sleep(0.15)  # several heartbeat ticks at the 0.02s interval above
        observed["mid_run"] = conn.execute(
            "SELECT heartbeat_at FROM conversion_jobs WHERE id = ?", (job_id,)
        ).fetchone()[0]
        return real_convert(staged_path, source_type, cfg_arg)

    with patch("doc_ingest.worker._convert", side_effect=_slow_convert), \
         patch("doc_ingest.lock.apply_readonly_lock"), \
         patch("doc_ingest.lock.verify_locked", return_value=True):
        worker.process_job(conn, job_id, cfg, worker_id="w1")

    assert observed["mid_run"] is not None
    assert observed["mid_run"] > claimed_heartbeat  # a heartbeat tick landed on the heartbeat thread's own connection during the slow step
    job_row = conn.execute("SELECT status FROM conversion_jobs WHERE id = ?", (job_id,)).fetchone()
    assert job_row[0] == "complete"
