import json
import sqlite3
from pathlib import Path

import pytest

from pipeline_app import db, obs


def test_log_writes_a_json_line_to_a_dated_file(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    obs.log("adapter.fetch_failed", level="error", handle="@a", platform="youtube")

    files = list((tmp_path / "logs").glob("app-*.log"))
    assert len(files) == 1
    assert files[0].name.startswith("app-20")  # app-YYYY-MM-DD.log
    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["event"] == "adapter.fetch_failed"
    assert record["level"] == "error"
    assert record["handle"] == "@a"
    assert record["ts"].endswith("+00:00")  # aware UTC, never naive


def test_log_also_writes_to_stderr(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    obs.log("adapter.fetch_failed", level="error")
    assert "adapter.fetch_failed" in capsys.readouterr().err


def test_log_does_not_raise_when_the_log_directory_cannot_be_created(tmp_path: Path, monkeypatch):
    """A read-only disk must not turn a reportable failure into a crash."""
    blocker = tmp_path / "logs"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(obs, "LOG_DIR", blocker)
    obs.log("adapter.fetch_failed", level="error")  # must not raise


def test_log_does_not_raise_on_an_unserializable_field(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    obs.log("adapter.fetch_failed", level="error", conn=object())  # must not raise
