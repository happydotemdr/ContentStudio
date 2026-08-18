# coach-prep-app/tests/test_run_client_audit.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_client_audit  # noqa: E402

# Self-sufficient cross-app import setup, mirroring test_run_coachprep_cron.py
# (Task 22) -- without this, the `import doc_ingest` / `from doc_ingest import
# db` calls below only resolve when this file happens to be collected after
# another file that already imported doc_ingest (alphabetical collection
# order), so this file fails with ModuleNotFoundError when run in isolation
# (as this task's own Step 2/4 validation command does: just these two test
# files).
from coach_prep_app import config as _config_mod
_config_mod.ensure_doc_ingest_importable(_config_mod.Config().doc_ingest_app_root)


def test_main_builds_report_and_sends_email(tmp_path, monkeypatch):
    from coach_prep_app import audit, google_clients, notify

    monkeypatch.setattr(audit, "build_report", lambda *a, **k: {
        "mechanical_problems": [], "content_problems": [], "placement": [],
        "unmatched_count": 0, "failed_runs": [],
    })
    sent = []
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: sent.append(subject) or True)
    monkeypatch.setattr(google_clients, "build_drive_service", lambda cfg: None)

    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text(
        f"doc_ingest_db_path: {tmp_path / 'doc_ingest_test.db'}\n"
        f"doc_ingest_app_root: {tmp_path}\n"
        f"pending_review_drive_folder_id: real-folder-id\n",
        encoding="utf-8",
    )
    from doc_ingest import db as doc_ingest_db
    doc_ingest_db.init_db(tmp_path / "doc_ingest_test.db").close()

    rc = run_client_audit.main(["--config", str(yaml_path)])
    assert rc == 0
    assert sent == ["Coach-prep weekly audit: clean"]


def test_main_uses_a_default_config_yaml_when_no_config_flag_given(tmp_path, monkeypatch):
    """Windows Task Scheduler never passes --config -- same gap Task 22's
    run_coachprep_cron.py already had and fixed: without a fallback,
    load_config(None) silently ignores the operator's real config (in
    particular pending_review_drive_folder_id, required by
    placement_check) the moment this runs unattended, and every notified
    draft would be misreported as moved to an unexpected location."""
    from coach_prep_app import audit, google_clients, notify

    captured_folder_ids = []
    monkeypatch.setattr(
        audit, "build_report",
        lambda conn, doc_ingest_conn, drive_service, cfg, since_iso: (
            captured_folder_ids.append(cfg.pending_review_drive_folder_id) or {
                "mechanical_problems": [], "content_problems": [], "placement": [],
                "unmatched_count": 0, "failed_runs": [],
            }
        ),
    )
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: True)
    monkeypatch.setattr(google_clients, "build_drive_service", lambda cfg: None)
    monkeypatch.setattr(run_client_audit, "HERE", tmp_path / "scripts")

    doc_ingest_db_path = tmp_path / "doc_ingest_test.db"
    (tmp_path / "config.yaml").write_text(
        f"doc_ingest_db_path: {doc_ingest_db_path}\n"
        f"doc_ingest_app_root: {tmp_path}\n"
        f"pending_review_drive_folder_id: real-folder-id\n",
        encoding="utf-8",
    )
    from doc_ingest import db as doc_ingest_db
    doc_ingest_db.init_db(doc_ingest_db_path).close()

    rc = run_client_audit.main([])  # no --config, exactly like Task Scheduler's invocation
    assert rc == 0
    assert captured_folder_ids == ["real-folder-id"]


def test_main_returns_nonzero_and_warns_when_audit_email_fails_to_send(tmp_path, monkeypatch):
    """A failed Resend send must not be silently swallowed -- Task Scheduler
    would otherwise record success for a weekly audit report that never
    reached anyone."""
    from coach_prep_app import audit, google_clients, notify

    monkeypatch.setattr(audit, "build_report", lambda *a, **k: {
        "mechanical_problems": [], "content_problems": [], "placement": [],
        "unmatched_count": 0, "failed_runs": [],
    })
    monkeypatch.setattr(notify, "send_email", lambda subject, text, recipient=notify.RECIPIENT: False)
    monkeypatch.setattr(google_clients, "build_drive_service", lambda cfg: None)

    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text(
        f"doc_ingest_db_path: {tmp_path / 'doc_ingest_test.db'}\n"
        f"doc_ingest_app_root: {tmp_path}\n"
        f"pending_review_drive_folder_id: real-folder-id\n",
        encoding="utf-8",
    )
    from doc_ingest import db as doc_ingest_db
    doc_ingest_db.init_db(tmp_path / "doc_ingest_test.db").close()

    rc = run_client_audit.main(["--config", str(yaml_path)])
    assert rc == 1


def test_main_returns_nonzero_and_never_builds_report_when_folder_id_unconfigured(tmp_path, monkeypatch):
    """An unconfigured pending_review_drive_folder_id must fail loud, before
    any DB/service work -- a real deployment that never creates config.yaml
    (or omits this key) would otherwise silently fail every draft publish
    with no clear error."""
    from coach_prep_app import audit

    calls = []
    monkeypatch.setattr(audit, "build_report", lambda *a, **k: calls.append(1))

    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text(
        f"doc_ingest_db_path: {tmp_path / 'doc_ingest_test.db'}\n"
        f"doc_ingest_app_root: {tmp_path}\n",
        encoding="utf-8",
    )
    from doc_ingest import db as doc_ingest_db
    doc_ingest_db.init_db(tmp_path / "doc_ingest_test.db").close()

    rc = run_client_audit.main(["--config", str(yaml_path)])
    assert rc == 1
    assert calls == []
