from pathlib import Path

from pipeline_app import discovery_instagram as ig


def test_api_key_prefers_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(ig.KEY_ENV_VAR, "env-key")
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.api_key() == "env-key"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("  file-key\n", encoding="utf-8")
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.api_key() == "file-key"


def test_api_key_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", tmp_path / "absent.txt")
    assert ig.api_key() is None
