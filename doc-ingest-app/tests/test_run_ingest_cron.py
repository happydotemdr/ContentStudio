import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]


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

    calls = {"process_job": 0}
    real_process_job = run_ingest_cron.worker.process_job

    def _counting_process_job(conn, job_id, cfg_arg, worker_id):
        calls["process_job"] += 1
        return real_process_job(conn, job_id, cfg_arg, worker_id)

    monkeypatch.setattr(run_ingest_cron.worker, "process_job", _counting_process_job)
    run_ingest_cron.run_once(db_path, cfg)
    assert calls["process_job"] == 1


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

    calls = {"count": 0}

    def _fake_process_job(conn, job_id, cfg_arg, worker_id):
        calls["count"] += 1

    monkeypatch.setattr(run_ingest_cron.worker, "process_job", _fake_process_job)
    run_ingest_cron.run_once(db_path, cfg)
    assert calls["count"] == 0  # budget already elapsed -- nothing claimed
