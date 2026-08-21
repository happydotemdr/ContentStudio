import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

HERE = Path(__file__).resolve().parents[1]


def _stub_drive_service(monkeypatch, run_ingest_cron, factory=None):
    """run_once calls the REAL drive_client.build_default_service since Task
    22 wired the Drive check in. On this machine that's harmless (no
    token.json -> raises immediately -> the cron's except swallows it), but on
    an operator machine that has completed SETUP.md step 6 it would reach
    get_credentials, which can refresh over the network AND REWRITE THE
    OPERATOR'S REAL token.json -- a genuine side effect on live credentials
    from a hermetic unit test. Every run_once test stubs it."""
    monkeypatch.setattr(
        run_ingest_cron.drive_client,
        "build_default_service",
        factory if factory is not None else (lambda cfg_arg: MagicMock()),
    )


def test_module_exposes_a_main_function():
    sys.path.insert(0, str(HERE / "scripts"))
    import run_ingest_cron
    assert callable(run_ingest_cron.main)


def test_run_once_reclaims_scans_enqueues_and_drains(tmp_path, monkeypatch):
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)

    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "a.txt").write_bytes(b"some real text content for the doc")
    output_root = tmp_path / "output"
    db_path = tmp_path / "doc_ingest.db"

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=output_root, worker_pool_size=1)

    _stub_drive_service(monkeypatch, run_ingest_cron)

    calls = {"process_job": 0}
    real_process_job = run_ingest_cron.worker.process_job

    def _counting_process_job(conn, job_id, cfg_arg, worker_id):
        calls["process_job"] += 1
        return real_process_job(conn, job_id, cfg_arg, worker_id)

    monkeypatch.setattr(run_ingest_cron.worker, "process_job", _counting_process_job)
    run_ingest_cron.run_once(db_path, cfg)
    assert calls["process_job"] == 1


def test_run_once_continues_past_a_failing_drive_check(tmp_path, monkeypatch, capsys):
    """The binding constraint on Task 22's Drive-check step: missing or
    expired Drive credentials must NOT block local-file processing. Asserted
    directly by forcing build_default_service to raise and proving the
    local-file job still got processed afterwards -- the other run_once tests
    only pass a MagicMock through, which can't distinguish "the failure was
    caught and we continued" from "the failure never happened"."""
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)

    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "a.txt").write_bytes(b"some real text content for the doc")
    output_root = tmp_path / "output"
    db_path = tmp_path / "doc_ingest.db"

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=output_root, worker_pool_size=1)

    def _no_credentials(cfg_arg):
        raise RuntimeError("doc-ingest-app has no cached Drive token")

    _stub_drive_service(monkeypatch, run_ingest_cron, factory=_no_credentials)

    calls = {"process_job": 0}

    def _counting_process_job(conn, job_id, cfg_arg, worker_id):
        calls["process_job"] += 1

    monkeypatch.setattr(run_ingest_cron.worker, "process_job", _counting_process_job)
    run_ingest_cron.run_once(db_path, cfg)  # must not raise

    assert calls["process_job"] == 1  # enqueue + drain still ran after the failed Drive check
    captured = capsys.readouterr()
    assert "drive check skipped" in captured.err
    assert "enqueued 1 job(s)" in captured.out


def test_run_once_survives_a_claim_job_that_raises_and_still_regenerates_the_manifest(
    tmp_path, monkeypatch, capsys
):
    """jobs.claim_job issues a raw BEGIN IMMEDIATE from up to
    worker_pool_size concurrent connections against a 5s busy_timeout, so a
    transient sqlite3.OperationalError (SQLITE_BUSY) is possible under real
    contention. It used to sit OUTSIDE _run_one_worker's guard: the exception
    re-raised at future.result(), escaped the drain block, and manifest
    regeneration -- which follows that block -- was silently skipped for the
    whole wake."""
    import sqlite3
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)

    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "a.txt").write_bytes(b"some real text content for the doc")
    output_root = tmp_path / "output"
    db_path = tmp_path / "doc_ingest.db"

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=output_root, worker_pool_size=1, run_time_budget_s=5)

    _stub_drive_service(monkeypatch, run_ingest_cron)

    real_claim_job = run_ingest_cron.jobs.claim_job
    state = {"raised": False}

    def _flaky_claim_job(conn, worker_id):
        if not state["raised"]:
            state["raised"] = True
            raise sqlite3.OperationalError("database is locked")
        return real_claim_job(conn, worker_id)

    monkeypatch.setattr(run_ingest_cron.jobs, "claim_job", _flaky_claim_job)
    monkeypatch.setattr(
        run_ingest_cron.worker, "process_job", lambda conn, job_id, cfg_arg, worker_id: None
    )

    run_ingest_cron.run_once(db_path, cfg)  # must not raise

    assert state["raised"]
    assert "database is locked" in capsys.readouterr().err
    assert (output_root / "_freedom2beu-content-index.csv").exists()


def test_run_one_worker_survives_a_connection_open_that_raises(tmp_path, monkeypatch, capsys):
    """The other unguarded step in _run_one_worker: db.get_connection itself.
    It runs BEFORE `conn` exists, so the guard's finally block has to tolerate
    there being nothing to close -- an unguarded `conn.close()` there would
    turn the original failure into an UnboundLocalError/AttributeError that
    still escapes into the pool."""
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)

    from doc_ingest.config import Config
    cfg = Config(input_root=tmp_path / "input", output_root=tmp_path / "output")

    def _cannot_open(path, *a, **kw):
        raise OSError("unable to open database file")

    monkeypatch.setattr(run_ingest_cron.db, "get_connection", _cannot_open)

    run_ingest_cron._run_one_worker(tmp_path / "doc_ingest.db", cfg)  # must not raise

    err = capsys.readouterr().err
    assert "worker raised" in err
    assert "unable to open database file" in err


def test_run_once_abandons_a_future_that_exceeds_job_timeout_s(tmp_path, monkeypatch, capsys):
    """cfg.job_timeout_s was a dead field: future.result() blocked forever, so
    one hung firecrawl.parse() or Drive call wedged the wake permanently --
    and Windows Task Scheduler's skip-if-already-running default then means NO
    subsequent wake ever fires. The timeout does NOT kill the worker thread
    (ThreadPoolExecutor can't); it only stops the main loop waiting on it, so
    the wake finishes, the manifest is written, and the next wake fires."""
    import time as _time
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)

    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "a.txt").write_bytes(b"some real text content for the doc")
    output_root = tmp_path / "output"
    db_path = tmp_path / "doc_ingest.db"

    from doc_ingest.config import Config
    cfg = Config(
        input_root=input_root,
        output_root=output_root,
        worker_pool_size=1,
        job_timeout_s=0.05,
        run_time_budget_s=30,
    )

    _stub_drive_service(monkeypatch, run_ingest_cron)

    def _hanging_process_job(conn, job_id, cfg_arg, worker_id):
        _time.sleep(2.0)  # far past job_timeout_s; stands in for an unbounded hang

    monkeypatch.setattr(run_ingest_cron.worker, "process_job", _hanging_process_job)

    started = _time.monotonic()
    run_ingest_cron.run_once(db_path, cfg)  # must return without waiting out the sleep
    elapsed = _time.monotonic() - started

    assert elapsed < 2.0, f"run_once waited for the stuck worker ({elapsed:.2f}s)"
    assert "exceeded job_timeout_s" in capsys.readouterr().err
    assert (output_root / "_freedom2beu-content-index.csv").exists()


def test_run_once_respects_the_time_budget(tmp_path, monkeypatch):
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)

    input_root = tmp_path / "input"
    input_root.mkdir()
    for i in range(5):
        (input_root / f"f{i}.txt").write_bytes(b"content " * 20)
    output_root = tmp_path / "output"
    db_path = tmp_path / "doc_ingest.db"

    from doc_ingest.config import Config
    cfg = Config(input_root=input_root, output_root=output_root, worker_pool_size=1, run_time_budget_s=0)

    _stub_drive_service(monkeypatch, run_ingest_cron)

    calls = {"count": 0}

    def _fake_process_job(conn, job_id, cfg_arg, worker_id):
        calls["count"] += 1

    monkeypatch.setattr(run_ingest_cron.worker, "process_job", _fake_process_job)
    run_ingest_cron.run_once(db_path, cfg)
    assert calls["count"] == 0  # budget already elapsed -- nothing claimed


def test_main_retry_failed_clears_matching_jobs_before_running(tmp_path, monkeypatch, capsys):
    """--retry-failed is the operator's way to make a converter or gauntlet
    fix reach files that already failed under the old code. Without it,
    enqueue_pending_jobs suppresses the retry forever (the source version
    hasn't changed), and a full ingest run enqueues 0 jobs -- exactly what
    happened after the 2026-08-21 gsheet gauntlet fix."""
    sys.path.insert(0, str(HERE / "scripts"))
    import importlib
    import run_ingest_cron
    importlib.reload(run_ingest_cron)
    _stub_drive_service(monkeypatch, run_ingest_cron)

    db_path = tmp_path / "doc_ingest.db"
    monkeypatch.setattr(run_ingest_cron, "HERE", tmp_path / "scripts")

    conn = run_ingest_cron.db.init_db(db_path)
    now = "2026-08-13T00:00:00+00:00"
    for rel_path, extension in (("books.gsheet", "gsheet"), ("module.docx", "docx")):
        conn.execute(
            "INSERT INTO source_files (rel_path, extension, classification, content_hash, "
            "first_seen_at, last_seen_at) VALUES (?, ?, 'convertible', 'h', ?, ?)",
            (rel_path, extension, now, now),
        )
        source_file_id = conn.execute(
            "SELECT id FROM source_files WHERE rel_path = ?", (rel_path,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO conversion_jobs (source_file_id, status, source_hash_at_attempt, "
            "created_at) VALUES (?, 'failed', 'h', ?)",
            (source_file_id, now),
        )
    conn.commit()
    conn.close()

    input_root = tmp_path / "input"
    input_root.mkdir()
    cfg = run_ingest_cron.load_config(None)
    monkeypatch.setattr(
        run_ingest_cron, "load_config",
        lambda path: type(cfg)(**{**cfg.__dict__, "input_root": input_root, "output_root": tmp_path / "out"}),
    )

    assert run_ingest_cron.main(["--retry-failed", "%.gsheet"]) == 0

    out = capsys.readouterr().out
    assert "cleared 1 failed job(s)" in out
    assert "books.gsheet" in out
    assert "module.docx" not in out
