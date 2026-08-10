import json
import sqlite3
from datetime import datetime, timezone
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


def test_a_caller_field_can_never_replace_the_real_timestamp(tmp_path: Path, monkeypatch):
    """`ts` is the one field that makes two log lines comparable.

    A caller passing `ts=` must not be able to replace it -- and must not have
    its value silently dropped either, or a mistaken call would be
    indistinguishable from a correct one.
    """
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    obs.log("adapter.fetch_failed", level="error", ts="1999-01-01T00:00:00+00:00", handle="@a")

    files = list((tmp_path / "logs").glob("app-*.log"))
    record = json.loads(files[0].read_text(encoding="utf-8").strip())
    assert record["ts"] != "1999-01-01T00:00:00+00:00"          # the caller did not win
    assert record["ts"].startswith(str(datetime.now(timezone.utc).year))
    assert record["field_ts"] == "1999-01-01T00:00:00+00:00"    # ...and was not silently dropped
    assert record["handle"] == "@a"                             # a non-colliding field is untouched


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_record_event_appends_a_row_and_returns_its_id(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    event_id = obs.record_event(
        conn, kind="adapter.fetch_failed", severity="error", source="discovery_youtube",
        message="yt-dlp exited 1 for @a", detail={"handle": "@a", "exit_code": 1}, run_id=7,
    )
    assert event_id > 0
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    assert row["kind"] == "adapter.fetch_failed"
    assert row["severity"] == "error"
    assert row["source"] == "discovery_youtube"
    assert row["run_id"] == 7
    assert json.loads(row["detail"]) == {"handle": "@a", "exit_code": 1}
    assert row["acknowledged"] == 0
    assert row["occurred_at"].endswith("+00:00")


def test_events_table_rejects_a_severity_outside_the_vocabulary(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO events (occurred_at, kind, severity, source, message) "
            "VALUES ('2026-08-08T00:00:00+00:00', 'k', 'catastrophic', 's', 'm')"
        )
