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
