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


def test_list_platform_handles_scopes_to_one_platform(conn):
    """Output directories are namespaced by platform, so a collision check must
    compare within one platform only."""
    db.create_handle(conn, "facebook", "NASA", None, "guru", None, "2026-08-08T00:00:00Z")
    db.create_handle(conn, "instagram", "nasa", None, "guru", None, "2026-08-08T00:00:00Z")
    assert [r["handle"] for r in db.list_platform_handles(conn, "facebook")] == ["NASA"]


def test_list_platform_handles_includes_excluded_handles(conn):
    """An excluded handle still owns its directory: re-including it later must
    not start silently sharing files with one registered in the meantime."""
    handle_id = db.create_handle(conn, "facebook", "NASA", None, "guru", None, "2026-08-08T00:00:00Z")
    db.set_handle_included(conn, handle_id, False)
    assert [r["handle"] for r in db.list_platform_handles(conn, "facebook")] == ["NASA"]


def test_list_platform_handles_is_empty_for_an_unregistered_platform(conn):
    assert db.list_platform_handles(conn, "facebook") == []


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


def test_insert_running_run_then_second_raises(conn):
    db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_running_run(conn, "run-2", "manual", "incremental", "2026-07-30T06:01:00Z")


def test_insert_locked_run_after_conflict(conn):
    db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    locked_id = db.insert_locked_run(
        conn, "run-2", "manual", "incremental", "2026-07-30T06:01:00Z", "2026-07-30T06:01:00Z"
    )
    row = db.get_run(conn, locked_id)
    assert row["status"] == "locked"


def test_insert_terminal_run_has_no_running_phase(conn):
    run_id = db.insert_terminal_run(
        conn, "validate-1", "manual", "validate_handle", "completed",
        "2026-07-30T06:00:00Z", "2026-07-30T06:00:30Z",
    )
    assert db.get_running_run(conn) is None
    assert db.get_run(conn, run_id)["status"] == "completed"


def test_get_running_run_returns_the_running_row(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    row = db.get_running_run(conn)
    assert row["id"] == run_id


def test_update_run_heartbeat(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    db.update_run_heartbeat(conn, run_id, "2026-07-30T06:00:30Z")
    assert db.get_run(conn, run_id)["heartbeat_at"] == "2026-07-30T06:00:30Z"


def test_reclaim_stale_runs_flips_to_abandoned(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    db.update_run_heartbeat(conn, run_id, "2026-07-30T06:00:30Z")
    reclaimed = db.reclaim_stale_runs(conn, "2026-07-30T06:20:00Z", staleness_seconds=600)
    assert reclaimed == [run_id]
    assert db.get_run(conn, run_id)["status"] == "abandoned"
    assert db.get_running_run(conn) is None


def test_reclaim_stale_runs_leaves_fresh_runs_alone(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    db.update_run_heartbeat(conn, run_id, "2026-07-30T06:09:30Z")
    reclaimed = db.reclaim_stale_runs(conn, "2026-07-30T06:10:00Z", staleness_seconds=600)
    assert reclaimed == []
    assert db.get_run(conn, run_id)["status"] == "running"


def test_finish_run(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    db.finish_run(conn, run_id, "completed", "2026-07-30T06:04:00Z", "output/discovery-runs/run-1.md")
    row = db.get_run(conn, run_id)
    assert row["status"] == "completed"
    assert row["finished_at"] == "2026-07-30T06:04:00Z"
    assert row["md_path"] == "output/discovery-runs/run-1.md"


def test_list_runs_newest_first(conn):
    db.insert_terminal_run(conn, "r1", "manual", "incremental", "completed", "2026-07-30T06:00:00Z", "2026-07-30T06:01:00Z")
    db.insert_terminal_run(conn, "r2", "manual", "incremental", "completed", "2026-07-30T07:00:00Z", "2026-07-30T07:01:00Z")
    rows = db.list_runs(conn)
    assert [r["run_id"] for r in rows] == ["r2", "r1"]


def test_record_and_list_run_handle_results(conn):
    run_id = db.insert_terminal_run(conn, "r1", "manual", "incremental", "completed", "2026-07-30T06:00:00Z", "2026-07-30T06:01:00Z")
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-07-30T00:00:00Z")
    db.record_handle_result(conn, run_id, handle_id, "ok", items_downloaded=2)
    results = db.list_run_handle_results(conn, run_id)
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["items_downloaded"] == 2


def test_get_settings_returns_defaults(conn):
    row = db.get_settings(conn)
    assert row["frequency"] == "daily"
    assert row["time_of_day"] == "06:00"
    assert row["timezone"] == "America/Chicago"
    assert row["last_scheduled_run_date"] is None


def test_update_settings(conn):
    db.update_settings(conn, "daily", "07:30", "America/New_York")
    row = db.get_settings(conn)
    assert row["time_of_day"] == "07:30"
    assert row["timezone"] == "America/New_York"


def test_set_last_scheduled_run_date(conn):
    db.set_last_scheduled_run_date(conn, "2026-07-30")
    assert db.get_settings(conn)["last_scheduled_run_date"] == "2026-07-30"


def test_transaction_rolls_back_every_statement_in_the_block(conn):
    """FAULT. A multi-row operation that fails partway leaves nothing behind."""
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
            db.create_stage_row(conn, project_id, "ideation", "ready")
            raise RuntimeError("mkdir failed halfway through create_project")
    assert db.list_projects(conn) == []
    assert conn.execute("SELECT count(*) FROM stages").fetchone()[0] == 0


def test_a_failed_transaction_is_distinguishable_from_the_unwrapped_path(conn):
    """DISTINGUISHABILITY. Without the boundary the same failure leaves a
    half-written project behind -- which is A-70 exactly. The two paths must not
    produce the same database."""
    def half_a_project(wrapped: bool) -> int:
        try:
            if wrapped:
                with db.transaction(conn):
                    db.create_project(conn, "wrapped", "a", "generic", "2026-08-08T00:00:00+00:00")
                    raise RuntimeError("boom")
            else:
                db.create_project(conn, "unwrapped", "a", "generic", "2026-08-08T00:00:00+00:00")
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        return len(db.list_projects(conn))

    assert half_a_project(wrapped=False) == 1      # today's behaviour, preserved
    assert half_a_project(wrapped=True) == 1       # still 1 -- the wrapped one rolled back
    assert [r["run_id"] for r in db.list_projects(conn)] == ["unwrapped"]


def test_a_rolled_back_transaction_records_an_error_event(conn, tmp_path, monkeypatch):
    """SURFACING. A silently discarded half-operation is how A-70 stayed
    invisible; the rollback has to leave a row a human can find -- and it has to
    still be there once this connection is gone.

    Read it back on a SECOND connection. Reading it on the connection that wrote
    it passes whether or not the row was ever committed, so that version of this
    test cannot tell a durable event from one that dies with the process."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
            raise RuntimeError("boom")

    other = db.get_connection(Path(conn.execute("PRAGMA database_list").fetchone()[2]))
    try:
        rows = other.execute(
            "SELECT * FROM events WHERE kind = 'db.transaction_rolled_back'"
        ).fetchall()
    finally:
        other.close()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "RuntimeError" in rows[0]["message"]
    assert db.list_projects(conn) == []  # ...and the half-written project is still gone


def test_recording_an_event_inside_a_transaction_does_not_commit_the_caller(
    conn, tmp_path, monkeypatch
):
    """`record_event` is called from inside operations that are failing. If it
    committed, it would persist the half-finished work the boundary exists to
    discard -- A-70 defeated by the very module built to report it."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            db.create_project(conn, "half", "a", "generic", "2026-08-08T00:00:00+00:00")
            obs.record_event(conn, kind="k", severity="warning", source="s", message="mid-flight")
            raise RuntimeError("boom")

    assert db.list_projects(conn) == []  # the half project did NOT survive
    # That event row rolled back with everything else -- correct, but it must not
    # be the only trace. `record_event` logs unconditionally, so the file survives.
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log")
    )
    assert "mid-flight" in text


def test_leaf_helpers_still_commit_immediately_outside_a_transaction(conn, tmp_path):
    """Fourteen other packages' tests depend on this. A second connection to the
    same file must see the row without any explicit boundary."""
    db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    other = db.get_connection(Path(conn.execute("PRAGMA database_list").fetchone()[2]))
    try:
        assert len(db.list_projects(other)) == 1
    finally:
        other.close()


def test_a_nested_transaction_joins_the_outer_one(conn):
    with db.transaction(conn):
        db.create_project(conn, "outer", "a", "generic", "2026-08-08T00:00:00+00:00")
        with db.transaction(conn):
            db.create_project(conn, "inner", "b", "generic", "2026-08-08T00:00:00+00:00")
        assert len(db.list_projects(conn)) == 2  # inner did not commit on its own
    assert len(db.list_projects(conn)) == 2


def test_a_swallowed_inner_failure_still_rolls_the_outer_transaction_back(conn):
    """A poisoned transaction must not be committable. Without this, an outer
    block that catches its inner block's exception commits half a cascade --
    the same defect one level up."""
    with pytest.raises(db.TransactionPoisonedError):
        with db.transaction(conn):
            db.create_project(conn, "outer", "a", "generic", "2026-08-08T00:00:00+00:00")
            try:
                with db.transaction(conn):
                    db.create_project(conn, "inner", "b", "generic", "2026-08-08T00:00:00+00:00")
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
    assert db.list_projects(conn) == []
