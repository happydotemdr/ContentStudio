import sqlite3
from pathlib import Path

import pytest

from pipeline_app import db


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_create_and_get_project(conn):
    project_id = db.create_project(conn, "abc-20260725-120000", "abc", "generic", "2026-07-25T12:00:00Z")
    row = db.get_project(conn, project_id)
    assert row["run_id"] == "abc-20260725-120000"
    assert row["brand"] == "generic"


def test_list_projects_newest_first(conn):
    db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    db.create_project(conn, "b-2", "b", "generic", "2026-07-25T13:00:00Z")
    rows = db.list_projects(conn)
    assert [r["run_id"] for r in rows] == ["b-2", "a-1"]


def test_create_and_get_stage(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    row = db.get_stage(conn, project_id, "ideation")
    assert row["id"] == stage_row_id
    assert row["status"] == "ready"


def test_update_stage_status_and_approved_at(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    stage_row = db.get_stage(conn, project_id, "ideation")
    db.update_stage_status(conn, stage_row["id"], "approved", approved_at="2026-07-25T14:00:00Z")
    updated = db.get_stage(conn, project_id, "ideation")
    assert updated["status"] == "approved"
    assert updated["approved_at"] == "2026-07-25T14:00:00Z"


def test_update_stage_session(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    db.update_stage_session(conn, stage_row_id, "session-123")
    row = db.get_stage(conn, project_id, "ideation")
    assert row["claude_session_id"] == "session-123"


def test_list_stages_returns_all_for_project(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    db.create_stage_row(conn, project_id, "scripting", "locked")
    rows = db.list_stages(conn, project_id)
    assert {r["stage_id"] for r in rows} == {"ideation", "scripting"}


def test_create_and_update_turn(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    turn_id = db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:05:00Z", "events/1.jsonl")
    db.update_turn(conn, turn_id, "complete", finished_at="2026-07-25T12:06:00Z", cost_usd=0.05)
    rows = db.list_turns(conn, stage_row_id)
    assert len(rows) == 1
    assert rows[0]["status"] == "complete"
    assert rows[0]["cost_usd"] == 0.05


def test_list_running_turns(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:05:00Z", "events/1.jsonl")
    running = db.list_running_turns(conn)
    assert len(running) == 1


def test_get_stage_by_row_id_returns_the_row(conn):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    row = db.get_stage_by_row_id(conn, stage_row_id)
    assert row["stage_id"] == "ideation"


def test_get_stage_by_row_id_returns_none_when_missing(conn):
    assert db.get_stage_by_row_id(conn, 999) is None


def test_schema_init_is_idempotent_with_new_discovery_tables(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    db.init_db(db_path, schema_path)  # second init must not raise
    conn = db.get_connection(db_path)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert {"handles", "discovery_runs", "discovery_run_handles", "discovery_settings"} <= tables
    settings = conn.execute("SELECT * FROM discovery_settings WHERE id = 1").fetchone()
    assert settings["frequency"] == "daily"
    assert settings["time_of_day"] == "06:00"
    assert settings["timezone"] == "America/Chicago"
    conn.close()


def test_two_running_discovery_runs_violate_unique_index(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at) "
        "VALUES ('run-1', 'manual', 'incremental', 'running', '2026-07-30T06:00:00Z')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at) "
            "VALUES ('run-2', 'manual', 'incremental', 'running', '2026-07-30T06:01:00Z')"
        )
    conn.close()


def test_create_and_get_handle(conn):
    handle_id = db.create_handle(conn, "youtube", "@Romayroh", "Romayroh", "guru", None, "2026-07-30T00:00:00Z")
    row = db.get_handle(conn, handle_id)
    assert row["handle"] == "@Romayroh"
    assert row["platform"] == "youtube"
    assert row["cohort"] == "guru"
    assert row["included"] == 1
    assert row["status"] == "pending"


def test_get_handle_by_platform_and_handle(conn):
    db.create_handle(conn, "youtube", "@Romayroh", "Romayroh", "guru", None, "2026-07-30T00:00:00Z")
    row = db.get_handle_by_platform_and_handle(conn, "youtube", "@Romayroh")
    assert row is not None
    assert db.get_handle_by_platform_and_handle(conn, "bluesky", "@Romayroh") is None


def test_list_handles_filters_included(conn):
    a = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-07-30T00:00:00Z")
    db.create_handle(conn, "youtube", "@b", None, "guru", None, "2026-07-30T00:00:00Z")
    db.set_handle_included(conn, a, False)
    assert len(db.list_handles(conn)) == 2
    included_only = db.list_handles(conn, included_only=True)
    assert len(included_only) == 1
    assert included_only[0]["handle"] == "@b"


def test_set_handle_status_and_validated_at(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-07-30T00:00:00Z")
    db.set_handle_status(conn, handle_id, "validated", validated_at="2026-07-30T01:00:00Z")
    row = db.get_handle(conn, handle_id)
    assert row["status"] == "validated"
    assert row["validated_at"] == "2026-07-30T01:00:00Z"


def test_set_handle_last_seen(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-07-30T00:00:00Z")
    db.set_handle_last_seen(conn, handle_id, "2026-07-28")
    assert db.get_handle(conn, handle_id)["last_seen_published_at"] == "2026-07-28"


def test_upsert_handle_from_migration_is_idempotent(conn):
    first_id = db.upsert_handle_from_migration(
        conn, "youtube", "@a", "A Channel", "guru", None, "validated", True, "2026-07-30T00:00:00Z"
    )
    db.set_handle_status(conn, first_id, "invalid")  # simulate a manual edit after migration
    second_id = db.upsert_handle_from_migration(
        conn, "youtube", "@a", "A Channel", "guru", None, "validated", True, "2026-07-30T00:00:00Z"
    )
    assert second_id == first_id
    assert db.get_handle(conn, first_id)["status"] == "invalid"  # not clobbered by re-running
