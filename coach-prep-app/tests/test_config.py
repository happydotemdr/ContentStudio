from __future__ import annotations

import os
from pathlib import Path

import pytest

from coach_prep_app import config


def test_default_config_has_expected_fields():
    cfg = config.Config()
    assert cfg.coach_email == "admin@freedom2beu.com"
    assert cfg.lookahead_hours == 48
    assert cfg.daily_ready_hour_local == 7
    assert cfg.timezone_name == "America/Chicago"
    assert cfg.last_meeting_email_staleness_days == 30


def test_load_config_from_yaml_overrides_default(tmp_path):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("lookahead_hours: 72\n", encoding="utf-8")
    cfg = config.load_config(yaml_path)
    assert cfg.lookahead_hours == 72


def test_load_config_env_var_overrides_yaml(tmp_path, monkeypatch):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("lookahead_hours: 72\n", encoding="utf-8")
    monkeypatch.setenv("COACH_PREP_LOOKAHEAD_HOURS", "10")
    cfg = config.load_config(yaml_path)
    assert cfg.lookahead_hours == 10


def test_load_config_rejects_unknown_yaml_key(tmp_path):
    yaml_path = tmp_path / "cfg.yaml"
    yaml_path.write_text("not_a_real_field: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown config key"):
        config.load_config(yaml_path)


def test_ensure_doc_ingest_importable_adds_to_sys_path(tmp_path):
    import sys
    fake_root = tmp_path / "doc-ingest-app"
    fake_root.mkdir()
    config.ensure_doc_ingest_importable(fake_root)
    assert str(fake_root) in sys.path
    # Idempotent -- calling twice does not duplicate the entry.
    config.ensure_doc_ingest_importable(fake_root)
    assert sys.path.count(str(fake_root)) == 1
