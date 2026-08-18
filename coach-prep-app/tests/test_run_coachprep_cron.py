# coach-prep-app/tests/test_run_coachprep_cron.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_coachprep_cron  # noqa: E402

# Self-sufficient cross-app import setup, mirroring test_orchestrator.py /
# test_doc_ingest_reader.py -- without this, the `import doc_ingest` calls
# below only resolve when this file happens to be collected after one of
# those (alphabetical collection order), so this file fails with
# ModuleNotFoundError when run in isolation (as Step 2/4's own validation
# command does: just these two test files).
from coach_prep_app import config as _config_mod
_config_mod.ensure_doc_ingest_importable(_config_mod.Config().doc_ingest_app_root)


def test_main_calls_run_once_and_returns_zero(tmp_path, monkeypatch):
    calls = []

    def fake_run_once(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg, now_utc):
        calls.append(1)
        return ["published"]

    from coach_prep_app import orchestrator, config as config_mod, google_clients
    monkeypatch.setattr(orchestrator, "run_once", fake_run_once)
    monkeypatch.setattr(google_clients, "build_calendar_service", lambda cfg: None)
    monkeypatch.setattr(google_clients, "build_gmail_service", lambda cfg: None)
    monkeypatch.setattr(google_clients, "build_drive_service", lambda cfg: None)

    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text(
        f"doc_ingest_db_path: {tmp_path / 'doc_ingest_test.db'}\n"
        f"doc_ingest_app_root: {tmp_path}\n",
        encoding="utf-8",
    )
    import doc_ingest  # ensure a real doc_ingest package is importable for open_readonly's target dir check
    from doc_ingest import db as doc_ingest_db
    doc_ingest_db.init_db(tmp_path / "doc_ingest_test.db").close()

    rc = run_coachprep_cron.main(["--config", str(yaml_path)])
    assert rc == 0
    assert calls == [1]


def test_main_returns_nonzero_when_any_client_errored(tmp_path, monkeypatch):
    # Task 21's orchestrator.run_once isolates per-client failures and reports
    # them as "error: <slug>" entries in its result list rather than raising --
    # main() must surface that as a nonzero exit code so a partial-failure wake
    # is distinguishable from a clean one at the process level, while still
    # having let every other client complete.
    def fake_run_once(conn, doc_ingest_conn, calendar_service, gmail_service, drive_service, cfg, now_utc):
        return ["published: acme", "error: beta_client", "skipped: gamma"]

    from coach_prep_app import orchestrator, google_clients
    monkeypatch.setattr(orchestrator, "run_once", fake_run_once)
    monkeypatch.setattr(google_clients, "build_calendar_service", lambda cfg: None)
    monkeypatch.setattr(google_clients, "build_gmail_service", lambda cfg: None)
    monkeypatch.setattr(google_clients, "build_drive_service", lambda cfg: None)

    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text(
        f"doc_ingest_db_path: {tmp_path / 'doc_ingest_test.db'}\n"
        f"doc_ingest_app_root: {tmp_path}\n",
        encoding="utf-8",
    )
    import doc_ingest
    from doc_ingest import db as doc_ingest_db
    doc_ingest_db.init_db(tmp_path / "doc_ingest_test.db").close()

    rc = run_coachprep_cron.main(["--config", str(yaml_path)])
    assert rc == 1


def test_default_config_path_returns_none_when_config_yaml_missing(tmp_path, monkeypatch):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(run_coachprep_cron, "HERE", scripts_dir)
    assert run_coachprep_cron._default_config_path() is None


def test_default_config_path_returns_path_when_config_yaml_present(tmp_path, monkeypatch):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("coach_email: test@example.com\n", encoding="utf-8")
    monkeypatch.setattr(run_coachprep_cron, "HERE", scripts_dir)
    assert run_coachprep_cron._default_config_path() == config_path
