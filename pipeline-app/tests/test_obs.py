import json
import re
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


def test_record_event_returns_minus_one_when_the_events_table_is_missing(tmp_path, monkeypatch):
    """An operator database that predates the events table must not turn every
    reported failure into a second, uncaught failure."""
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    bare = sqlite3.connect(tmp_path / "bare.db")
    try:
        assert obs.record_event(bare, kind="k", severity="error", source="s", message="m") == -1
    finally:
        bare.close()


def test_record_event_falls_back_to_the_log_when_it_cannot_write(tmp_path, monkeypatch):
    """Returning -1 silently would recreate the exact defect this module exists
    to fix. The fallback has to leave a trace."""
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    bare = sqlite3.connect(tmp_path / "bare.db")
    try:
        obs.record_event(bare, kind="adapter.fetch_failed", severity="error",
                         source="discovery_youtube", message="yt-dlp exited 1")
    finally:
        bare.close()
    written = (tmp_path / "logs").glob("app-*.log")
    text = "\n".join(p.read_text(encoding="utf-8") for p in written)
    assert "obs.record_event_failed" in text
    assert "yt-dlp exited 1" in text  # the recorded thing is not lost


def test_record_event_rejects_an_unknown_severity_without_raising(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    assert obs.record_event(conn, kind="k", severity="catastrophic",
                            source="s", message="m") == -1
    assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == 0


def test_record_event_does_not_raise_on_a_closed_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    closed = sqlite3.connect(tmp_path / "closed.db")
    closed.close()
    assert obs.record_event(closed, kind="k", severity="error", source="s", message="m") == -1


def test_doctor_context_carries_unacknowledged_error_events_newest_first(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from pipeline_app.main import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    try:
        conn = app.state.conn

        obs.record_event(conn, kind="a.info", severity="info", source="s", message="ignored")
        obs.record_event(conn, kind="a.warn", severity="warning", source="s", message="ignored")
        old_id = obs.record_event(conn, kind="a.old", severity="error", source="s", message="stale")
        conn.execute("UPDATE events SET occurred_at = '2020-01-01T00:00:00+00:00' WHERE id = ?",
                     (old_id,))
        ack_id = obs.record_event(conn, kind="a.ack", severity="error", source="s", message="handled")
        conn.execute("UPDATE events SET acknowledged = 1 WHERE id = ?", (ack_id,))
        first = obs.record_event(conn, kind="adapter.fetch_failed", severity="error",
                                 source="discovery_youtube", message="first",
                                 detail={"handle": "@a"}, run_id=3)
        second = obs.record_event(conn, kind="run.aborted", severity="critical",
                                  source="discovery_engine", message="second")
        conn.commit()

        captured = {}
        real = app.state.templates.TemplateResponse

        def spy(request, name, context, *args, **kwargs):
            captured.update(context)
            return real(request, name, context, *args, **kwargs)

        monkeypatch.setattr(app.state.templates, "TemplateResponse", spy)
        TestClient(app).get("/doctor")

        events = captured["recent_events"]
        assert [e["id"] for e in events] == [second, first]      # newest first, filtered
        assert events[1] == {
            "id": first, "occurred_at": events[1]["occurred_at"], "kind": "adapter.fetch_failed",
            "severity": "error", "source": "discovery_youtube", "message": "first",
            "detail": {"handle": "@a"}, "run_id": 3, "acknowledged": False,
        }
    finally:
        app.state.conn.close()


def test_recent_events_parses_detail_and_never_drops_a_malformed_one(tmp_path, monkeypatch):
    """A detail column written by a future caller as non-JSON must not make the
    event disappear -- losing the event is the defect, not the formatting."""
    conn_path = tmp_path / "pipeline.db"
    schema = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(conn_path, schema)
    c = db.get_connection(conn_path)
    try:
        c.execute(
            "INSERT INTO events (occurred_at, kind, severity, source, message, detail) "
            "VALUES (?, 'k', 'error', 's', 'm', 'not json')",
            (db._utcnow_iso(),),
        )
        c.commit()
        rows = db.list_unacknowledged_events(c, since_iso="2000-01-01T00:00:00+00:00")
        assert len(rows) == 1
        assert rows[0]["detail"] == {"raw": "not json"}
    finally:
        c.close()


def test_acknowledging_an_event_removes_it_from_the_doctor_list(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from pipeline_app.main import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    try:
        event_id = obs.record_event(app.state.conn, kind="k", severity="error",
                                    source="s", message="m")
        client = TestClient(app)
        resp = client.post(f"/doctor/events/{event_id}/ack",
                           headers={"Origin": "http://testserver"})
        assert resp.status_code in (200, 303, 307)
        assert db.list_unacknowledged_events(
            app.state.conn, since_iso="2000-01-01T00:00:00+00:00") == []
    finally:
        app.state.conn.close()


def test_the_doctor_page_renders_a_skipped_sweep_distinguishably_from_a_clean_one(
        tmp_path, monkeypatch):
    """HANDOFF FROM T14's REVIEW, closed here. P0 originally flagged
    `getattr(request.app.state, "orphaned_count", 0)` for collapsing three
    states (attribute missing / explicitly 0 / explicitly None) into two
    renderings. T14 made the value itself correctly `None` vs `0`; this test
    is what actually proves the RENDERED PAGE tells them apart, which
    nothing before this task ever checked -- T14's own tests only assert on
    `app.state.orphaned_count` directly, never on `/doctor`'s HTML."""
    from fastapi.testclient import TestClient
    from pipeline_app.main import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)

    # Separate db files, deliberately: each instance then claims T14's reconcile
    # lease unopposed, so `orphaned_count` starts as a real `0` from the actual
    # sweep on both -- this test is about page RENDERING, not lease contention
    # (T14 already covers that), so `skipped` overrides the attribute directly
    # afterward rather than reproducing a second-instance race here.
    clean = create_app(repo_root=tmp_path, db_path=tmp_path / "clean.db")
    try:
        assert clean.state.orphaned_count == 0
        clean_text = TestClient(clean).get("/doctor").text
    finally:
        clean.state.conn.close()

    skipped = create_app(repo_root=tmp_path, db_path=tmp_path / "skipped.db")
    try:
        skipped.state.orphaned_count = None  # stand in for A-76's skipped-sweep path
        skipped_text = TestClient(skipped).get("/doctor").text
    finally:
        skipped.state.conn.close()

    # T21 fixed the exact confusion this test guards: the rendered page must
    # say "not checked" for a skipped sweep, never print the literal string
    # "None" (which would be indistinguishable from a stray Python repr, not
    # a deliberate status). See test_header.py's
    # test_a_skipped_orphan_sweep_renders_differently_from_a_clean_one.
    assert re.search(r"Orphaned turns reconciled at startup:\s*0\s*</li>", clean_text)
    assert "not checked" in skipped_text
    assert "None" not in skipped_text
    assert clean_text != skipped_text


def test_the_total_count_does_not_share_the_windows_blind_spot(tmp_path, monkeypatch):
    """An unacknowledged error older than RECENT_EVENT_WINDOW_DAYS is correctly
    excluded from `recent_events` (the window is a deliberate design choice),
    but the total count must not share that exclusion -- otherwise an old,
    ignored critical event renders identically to a clean system."""
    from fastapi.testclient import TestClient
    from pipeline_app.main import create_app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "obs-logs")
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    try:
        old_id = obs.record_event(app.state.conn, kind="a.old", severity="critical",
                                  source="s", message="ancient, still unacknowledged")
        app.state.conn.execute(
            "UPDATE events SET occurred_at = '2020-01-01T00:00:00+00:00' WHERE id = ?",
            (old_id,))
        app.state.conn.commit()

        captured = {}
        real = app.state.templates.TemplateResponse

        def spy(request, name, context, *args, **kwargs):
            captured.update(context)
            return real(request, name, context, *args, **kwargs)

        monkeypatch.setattr(app.state.templates, "TemplateResponse", spy)
        TestClient(app).get("/doctor")

        assert captured["recent_events"] == []                      # window correctly excludes it
        assert captured["unacknowledged_error_total"] == 1          # total does not share the gap
    finally:
        app.state.conn.close()
