import json
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


def _db_path(conn) -> Path:
    return Path(conn.execute("PRAGMA database_list").fetchone()[2])


class _FlakyCommit:
    """A connection whose first `commit()` fails.

    A wrapper rather than a monkeypatch because `sqlite3.Connection` is a C type
    and does not accept attribute assignment. Everything else proxies through, so
    `id()` keying still works as long as the wrapper is what gets passed around."""

    def __init__(self, real):
        self._real = real
        self._failed = False

    def commit(self):
        if not self._failed:
            self._failed = True
            raise sqlite3.OperationalError("database is locked")
        return self._real.commit()

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_an_inner_block_unwinding_after_its_outer_one_does_not_strand_the_connection(
    conn, tmp_path, monkeypatch
):
    """A depth entry re-created after the outer block popped it is permanent and
    totally silent: every later commit becomes a no-op and the connection stops
    persisting anything, with no exception, no log line and no events row."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    outer, inner = db.transaction(conn), db.transaction(conn)
    outer.__enter__()
    inner.__enter__()
    outer.__exit__(None, None, None)   # the outer block unwinds first...
    inner.__exit__(None, None, None)   # ...and the inner one second

    db.create_project(conn, "after", "a", "generic", "2026-08-08T00:00:00+00:00")
    other = db.get_connection(_db_path(conn))
    try:
        assert len(db.list_projects(other)) == 1  # the connection still commits
    finally:
        other.close()

    text = "\n".join(p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log"))
    assert "db.transaction_bookkeeping_lost" in text  # ...and said so, rather than absorbing it


def test_a_poisoned_transaction_names_the_original_failure(conn, tmp_path, monkeypatch):
    """The synthetic TransactionPoisonedError is the only thing left to report, so
    if it does not carry the real fault, nothing does -- not `events`, not the log,
    not a traceback."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    with pytest.raises(db.TransactionPoisonedError) as caught:
        with db.transaction(conn):
            try:
                with db.transaction(conn):
                    raise RuntimeError("the stage row insert failed")
            except RuntimeError:
                pass

    assert "the stage row insert failed" in str(caught.value)
    assert isinstance(caught.value.__cause__, RuntimeError)

    other = db.get_connection(_db_path(conn))
    try:
        row = other.execute(
            "SELECT * FROM events WHERE kind = 'db.transaction_rolled_back'"
        ).fetchone()
    finally:
        other.close()
    detail = json.loads(row["detail"])
    assert detail["original_exception"] == "RuntimeError"
    assert "the stage row insert failed" in detail["original_message"]


def test_a_failing_boundary_commit_does_not_leave_the_work_for_the_next_caller(
    conn, tmp_path, monkeypatch
):
    """If the boundary's own commit raises and the statements are left pending, the
    next unrelated helper's commit persists them -- the caller was told the
    operation failed and the data landed anyway."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    flaky = _FlakyCommit(conn)
    with pytest.raises(sqlite3.OperationalError):
        with db.transaction(flaky):
            db.create_project(flaky, "doomed", "a", "generic", "2026-08-08T00:00:00+00:00")

    db.create_project(conn, "later", "b", "generic", "2026-08-08T00:00:00+00:00")
    other = db.get_connection(_db_path(conn))
    try:
        assert [r["run_id"] for r in db.list_projects(other)] == ["later"]
        # The defect was "no rollback AND no event". Assert both halves: a boundary
        # that discards work without saying so is the failure mode this package
        # exists to remove, and it is the half a passing rollback assertion hides.
        rows = other.execute(
            "SELECT * FROM events WHERE kind = 'db.transaction_rolled_back'"
        ).fetchall()
        assert len(rows) == 1
        assert "OperationalError" in rows[0]["message"]
    finally:
        other.close()


LEGACY_SCHEMA_V0 = """
CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL, brand TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE stages (id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id), stage_id TEXT NOT NULL,
  status TEXT NOT NULL, claude_session_id TEXT, approved_at TEXT,
  UNIQUE(project_id, stage_id));
CREATE TABLE turns (id INTEGER PRIMARY KEY AUTOINCREMENT,
  stage_row_id INTEGER NOT NULL REFERENCES stages(id), status TEXT NOT NULL,
  created_at TEXT NOT NULL, finished_at TEXT, events_path TEXT NOT NULL, cost_usd REAL);
CREATE TABLE handles (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL,
  handle TEXT NOT NULL, display_name TEXT, cohort TEXT NOT NULL, keyword_filter TEXT,
  included INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'pending',
  added_at TEXT NOT NULL, validated_at TEXT, last_seen_published_at TEXT,
  UNIQUE(platform, handle));
CREATE TABLE discovery_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL UNIQUE,
  trigger TEXT NOT NULL, mode TEXT NOT NULL, backfill_start TEXT, backfill_end TEXT,
  status TEXT NOT NULL, heartbeat_at TEXT, started_at TEXT NOT NULL, finished_at TEXT,
  md_path TEXT);
CREATE TABLE discovery_run_handles (id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES discovery_runs(id),
  handle_id INTEGER NOT NULL REFERENCES handles(id), status TEXT NOT NULL,
  items_downloaded INTEGER NOT NULL DEFAULT 0, error_message TEXT);
"""
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"


def _legacy_db(tmp_path: Path) -> Path:
    """A database written by the build that predates every constraint in this
    package -- the operator's real pipeline.db."""
    db_path = tmp_path / "pipeline.db"
    c = sqlite3.connect(db_path)
    c.executescript(LEGACY_SCHEMA_V0)
    c.commit()
    c.close()
    return db_path


def test_a_fresh_database_is_stamped_at_the_current_schema_version(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0] \
            == db.SCHEMA_VERSION
    finally:
        c.close()


@pytest.mark.xfail(reason="migration 1 constrains handles in T10", strict=True)
def test_an_existing_database_is_migrated_not_silently_left_behind(tmp_path: Path):
    """This is A-72: `CREATE TABLE IF NOT EXISTS` skips the new constraint and
    init_db reports success anyway."""
    db_path = _legacy_db(tmp_path)
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0] \
            == db.SCHEMA_VERSION
        ddl = c.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='handles'"
        ).fetchone()[0]
        assert "CHECK" in ddl  # the constraint actually landed on the existing table
    finally:
        c.close()


# NOTE (T5 self-review, not in the brief): the brief predicted this test would
# PASS at T5 -- only its neighbour above was expected to stay red, on the CHECK
# assertion. It does not: with `_MIGRATIONS` empty (no migration registered
# yet), a database stamped version 0 by `_legacy_db` has no migration to run
# and can never reach `db.SCHEMA_VERSION`, so this test fails on the SAME line
# as its neighbour, for the SAME root cause, before ever reaching the CHECK
# assertion. Unlike its neighbour this test only needs SOME migration to exist
# -- it never inspects `handles`' DDL -- so it comes back at T6 (which
# registers migration 1), not T10 (which is what actually constrains
# `handles`). Coordinator-amended per plan commit 1737fe6; T6 carries an
# explicit instruction to remove this marker. See P1-task-5-report.md.
def test_migrations_are_applied_exactly_once(tmp_path: Path):
    db_path = _legacy_db(tmp_path)
    db.init_db(db_path, SCHEMA_PATH)
    db.init_db(db_path, SCHEMA_PATH)  # a second boot must be a no-op, not a re-run
    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT count(*) FROM schema_version").fetchone()[0] == 1
        assert c.execute("SELECT version FROM schema_version").fetchone()[0] == db.SCHEMA_VERSION
    finally:
        c.close()


def test_a_database_from_a_newer_build_fails_loudly_instead_of_booting(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    c.execute("UPDATE schema_version SET version = ? WHERE id = 1", (db.SCHEMA_VERSION + 5,))
    c.commit()
    c.close()
    with pytest.raises(db.SchemaVersionError):
        db.init_db(db_path, SCHEMA_PATH)


def test_a_migration_that_fails_partway_leaves_neither_the_ddl_nor_the_stamp(tmp_path, monkeypatch):
    """Half-applied and never-applied must not be the same state. If the DDL
    survives while the stamp does not, the next boot re-runs the migration, the
    already-applied ALTER fails with "duplicate column name", and the database is
    wedged at that version forever."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def half_a_migration(c):
            c.execute("ALTER TABLE projects ADD COLUMN doomed TEXT")
            raise RuntimeError("the second half failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, half_a_migration)])
        with pytest.raises(RuntimeError, match="the second half failed"):
            db.apply_migrations(conn)

        assert "doomed" not in [r[1] for r in conn.execute("PRAGMA table_info(projects)")]
        assert conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()[0] == db.SCHEMA_VERSION
    finally:
        conn.close()

    # Read the event back on a SECOND connection. Reading it on the one that wrote
    # it passes whether or not the row was ever committed -- and "durable enough to
    # find after the process dies" is the only property that makes it a surfacing
    # test at all.
    other = db.get_connection(db_path)
    try:
        rows = other.execute(
            "SELECT * FROM events WHERE kind = 'schema.migration_failed'"
        ).fetchall()
    finally:
        other.close()
    assert len(rows) == 1          # ...and it said so
    assert rows[0]["severity"] == "critical"


def test_a_migration_body_calling_a_leaf_helper_does_not_commit_mid_migration(
    tmp_path, monkeypatch
):
    """The raw BEGIN is invisible to _TXN_DEPTH unless apply_migrations registers
    it, and commit_unless_in_transaction consults _TXN_DEPTH rather than the
    connection. Without the registration, a migration body that calls any db.py
    helper commits half the migration, the rollback rolls back nothing, and
    half-applied is indistinguishable from never-ran all over again."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def migration_using_a_helper(c):
            db.create_project(c, "mid-migration", "a", "generic", "2026-08-08T00:00:00+00:00")
            raise RuntimeError("the second half failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, migration_using_a_helper)])
        with pytest.raises(RuntimeError, match="the second half failed"):
            db.apply_migrations(conn)

        assert db.list_projects(conn) == []   # the helper's write rolled back too
        # The boundary must also clean up after itself. Without this, deleting
        # _exit_migration_boundary leaves the whole suite green while every
        # subsequent commit on this connection silently stops.
        assert id(conn) not in db._TXN_DEPTH
        assert id(conn) not in db._TXN_POISON
    finally:
        conn.close()


def test_a_refused_migration_leaves_no_poison_on_the_connection_id(
    tmp_path, monkeypatch
):
    """Bookkeeping cleanup after a refusal. A db.transaction() inside a migration
    body is non-outermost, so its finally takes the nested branch and leaves
    _TXN_POISON behind. init_db then closes this
    connection and the app allocates a new one on the next line -- CPython reuses the
    freed address readily -- so a stranded entry makes the first SUCCESSFUL outermost
    transaction() on the app's real connection roll back correct work and raise
    TransactionPoisonedError blaming a boot-time migration.

    The _MIGRATIONS contract forbids nesting a transaction() here. This proves the
    cleanup holds anyway, because a comment enforces nothing."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def migration_that_nests(c):
            try:
                with db.transaction(c):
                    raise RuntimeError("inner half failed")
            except RuntimeError:
                pass  # swallowed -- this is what poisons the key

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, migration_that_nests)])
        # The migration is REFUSED -- see
        # test_a_migration_that_swallows_an_inner_failure_is_not_stamped_as_applied.
        # This test's subject is what happens to the bookkeeping afterwards.
        with pytest.raises(db.TransactionPoisonedError):
            db.apply_migrations(conn)

        assert id(conn) not in db._TXN_POISON
        # ...and the next ordinary boundary is not poisoned by it
        with db.transaction(conn):
            db.create_project(conn, "after", "a", "generic", "2026-08-08T00:00:00+00:00")
        assert [r["run_id"] for r in db.list_projects(conn)] == ["after"]
    finally:
        conn.close()


def test_a_migration_that_swallows_an_inner_failure_is_not_stamped_as_applied(
    tmp_path, monkeypatch
):
    """A body that catches an inner transaction()'s failure and carries on has, by
    definition, had that failure reported by nobody -- non-outermost blocks skip
    _rollback_and_report. Committing and stamping it would make a migration that
    swallowed a failure indistinguishable from one that ran cleanly."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def migration_that_swallows(c):
            try:
                with db.transaction(c):
                    raise RuntimeError("the inner half failed")
            except RuntimeError:
                pass

        target = db.SCHEMA_VERSION + 1
        monkeypatch.setattr(db, "_MIGRATIONS", [(target, migration_that_swallows)])
        with pytest.raises(db.TransactionPoisonedError) as caught:
            db.apply_migrations(conn)

        assert "the inner half failed" in str(caught.value)
        assert isinstance(caught.value.__cause__, RuntimeError)
        assert conn.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()[0] != target          # NOT stamped as applied
    finally:
        conn.close()

    other = db.get_connection(db_path)
    try:
        rows = other.execute(
            "SELECT * FROM events WHERE kind = 'schema.migration_failed'"
        ).fetchall()
    finally:
        other.close()
    assert len(rows) == 1                  # ...and it was reported


def test_a_failed_rollback_reports_without_committing_the_partial_migration(
    tmp_path, monkeypatch
):
    """record_event commits whatever is still pending, so writing the events row here
    would make the partial migration DURABLE -- turning a state SQLite discards on
    close into permanent corruption. The report has to go somewhere that does not
    touch the database, and the failure has to stay recoverable."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)

    class _RollbackFails:
        """sqlite3.Connection is a C type and rejects attribute assignment."""

        def __init__(self, real):
            self._real = real

        def rollback(self):
            raise sqlite3.OperationalError("disk I/O error")

        def __getattr__(self, name):
            return getattr(self._real, name)

    conn = db.get_connection(db_path)
    wrapped = _RollbackFails(conn)
    try:
        def doomed(c):
            c.execute("ALTER TABLE projects ADD COLUMN doomed TEXT")
            raise RuntimeError("the migration failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, doomed)])
        with pytest.raises(RuntimeError, match="the migration failed"):
            db.apply_migrations(wrapped)
    finally:
        conn.close()   # discards the transaction the failed rollback could not

    # No events row was written, deliberately: writing one would have COMMITTED the
    # half-applied ALTER. Closing the connection discarded it instead, so the
    # database self-heals -- assert that from a second connection.
    other = db.get_connection(db_path)
    try:
        cols = [r[1] for r in other.execute("PRAGMA table_info(projects)")]
        rows = other.execute(
            "SELECT * FROM events WHERE kind LIKE 'schema.%'"
        ).fetchall()
    finally:
        other.close()
    assert "doomed" not in cols
    assert [r["kind"] for r in rows] == []

    # ...and the failure is still on disk, in the sink that does not touch the database.
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log")
    )
    assert "db.migration_rollback_failed" in text
    assert "db.migration_failed_unrecoverable" in text


def test_a_migration_that_commits_its_own_boundary_is_not_reported_as_undone(
    tmp_path, monkeypatch
):
    """The shape that defeated every classifier. executescript() COMMITs the
    boundary, the following INSERT opens a fresh transaction, so rollback() succeeds
    and conn.in_transaction reads True -- every proxy signal says "rolled back" while
    the DDL is already durable. The record must not make that claim, and must keep
    the readings that show otherwise."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def commits_then_fails(c):
            # executescript() COMMITs the boundary, then the INSERT opens a FRESH
            # transaction -- so rollback() succeeds and conn.in_transaction reads True.
            # Every proxy signal says "rolled back" here. Only the cookie disagrees,
            # and only the cookie is right.
            c.executescript("ALTER TABLE projects ADD COLUMN half TEXT;")
            c.execute("INSERT INTO projects (run_id, slug, brand, created_at) "
                      "VALUES ('x', 'x', 'generic', '2026-08-08T00:00:00+00:00')")
            raise RuntimeError("the second half failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, commits_then_fails)])
        with pytest.raises(RuntimeError, match="the second half failed"):
            db.apply_migrations(conn)
    finally:
        conn.close()

    other = db.get_connection(db_path)
    try:
        cols = [r[1] for r in other.execute("PRAGMA table_info(projects)")]
        rows = other.execute(
            "SELECT * FROM events WHERE kind LIKE 'schema.migration%'"
        ).fetchall()
    finally:
        other.close()
    assert "half" in cols                    # the DDL really is durable...
    assert len(rows) == 1
    # The record must not claim the changes were undone -- and it must preserve the
    # raw evidence that they were not, since it deliberately renders no verdict.
    assert "may contain partial changes" in rows[0]["message"]
    detail = json.loads(rows[0]["detail"])
    assert detail["schema_cookie_before"] != detail["schema_cookie_after"]


def test_a_failure_that_left_durable_data_is_distinguishable_from_one_that_left_nothing(
    tmp_path, monkeypatch
):
    """The shape every classifier was blind to. executescript() COMMITs the boundary,
    so the INSERT is durable -- but it is DML, so the schema cookie does not move and
    reads identically to a migration that was cleanly rolled back.

    Without a reading that separates them, "nothing happened" and "half of it is on
    disk" produce byte-identical events rows. `pending_when_it_failed` is that
    reading: True when the work was still pending and about to be discarded, False
    when the body had already committed it."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    def run(body) -> dict:
        db_path = tmp_path / f"{body.__name__}.db"
        # NOTE (T5, not in the brief): _MIGRATIONS must be empty for this init_db.
        # The brief's version leaves the PREVIOUS run()'s patched list installed
        # while the second database boots, so init_db -> apply_migrations re-runs
        # the FIRST body against it and that body's RuntimeError escapes init_db
        # before this run is even set up. Reported in P1-task-5-report.md rather
        # than silently smoothed over.
        monkeypatch.setattr(db, "_MIGRATIONS", [])
        db.init_db(db_path, SCHEMA_PATH)
        conn = db.get_connection(db_path)
        try:
            monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, body)])
            with pytest.raises(RuntimeError, match="the second half failed"):
                db.apply_migrations(conn)
        finally:
            conn.close()
        other = db.get_connection(db_path)
        try:
            rows = other.execute(
                "SELECT * FROM events WHERE kind = 'schema.migration_failed'"
            ).fetchall()
            survivors = [r["run_id"] for r in db.list_projects(other)]
        finally:
            other.close()
        return {"detail": json.loads(rows[0]["detail"]), "survivors": survivors}

    def commits_its_data(c):
        c.executescript(
            "INSERT INTO projects (run_id, slug, brand, created_at) "
            "VALUES ('survivor', 's', 'generic', '2026-08-08T00:00:00+00:00');"
        )
        raise RuntimeError("the second half failed")

    def leaves_nothing(c):
        c.execute("INSERT INTO projects (run_id, slug, brand, created_at) "
                  "VALUES ('doomed', 'd', 'generic', '2026-08-08T00:00:00+00:00')")
        raise RuntimeError("the second half failed")

    durable, discarded = run(commits_its_data), run(leaves_nothing)

    assert durable["survivors"] == ["survivor"]   # half the migration really is on disk
    assert discarded["survivors"] == []           # ...and here nothing is
    # The cookie cannot tell them apart -- it is blind to DML. That is the point.
    assert (durable["detail"]["schema_cookie_before"]
            == durable["detail"]["schema_cookie_after"])
    # The records must still differ.
    assert durable["detail"] != discarded["detail"]
    assert durable["detail"]["pending_when_it_failed"] is False
    assert discarded["detail"]["pending_when_it_failed"] is True


def test_a_lost_events_row_does_not_look_like_a_migration_that_never_failed(
    tmp_path, monkeypatch
):
    """record_event never raises; it returns -1. Here the database is the component
    that just failed, so this is the likeliest site for the record itself to be lost
    -- and a missing record must not be indistinguishable from a clean boot."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        def doomed(c):
            raise RuntimeError("the second half failed")

        monkeypatch.setattr(db, "_MIGRATIONS", [(db.SCHEMA_VERSION + 1, doomed)])
        monkeypatch.setattr(obs, "record_event", lambda *a, **k: -1)
        with pytest.raises(RuntimeError, match="the second half failed"):
            db.apply_migrations(conn)
    finally:
        conn.close()

    text = "\n".join(
        p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log")
    )
    assert "db.migration_failure_unrecorded" in text


def test_apply_migrations_refuses_a_connection_carrying_stranded_poison(tmp_path, monkeypatch):
    """Stranded poison is neither a transaction nor a boundary, so refusing it with
    NestedMigrationError's "close the caller's boundary" would name something that
    does not exist and give an unactionable remedy. _exit_migration_boundary's own
    comment explains how such an entry survives onto a REUSED connection id."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        db._TXN_POISON[id(conn)] = RuntimeError("left over from a previous connection")
        try:
            with pytest.raises(db.StrandedPoisonError, match="predates this call"):
                db.apply_migrations(conn)
        finally:
            db._TXN_POISON.pop(id(conn), None)   # never leak module state between tests
    finally:
        conn.close()


def test_apply_migrations_refuses_a_connection_already_inside_a_boundary(tmp_path, monkeypatch):
    """The silent window this closes: with no DML done yet, BEGIN IMMEDIATE succeeds,
    the depth goes 1->2, and on the failure path record_event's commit no-ops so the
    caller's rollback destroys the schema.migration_failed row -- the one durable
    record, gone with nothing to indicate it."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        with pytest.raises(db.NestedMigrationError):
            with db.transaction(conn):          # no DML yet -- the silent window
                db.apply_migrations(conn)
    finally:
        conn.close()


def test_an_out_of_order_or_duplicated_migration_list_is_rejected_at_import():
    """An out-of-order entry stamps the version BACKWARDS: [(2, m2), (1, m1)] on a
    v0 database runs m2, stamps 2, then runs m1 and stamps 1 -- so migration 2 has
    run while the database claims it has not. The next boot re-runs it, hits
    `duplicate column name`, and is stuck at a version that is neither true nor
    recoverable. Failing loudly at import is strictly better."""
    def noop(_conn):
        pass

    with pytest.raises(RuntimeError):
        db._validate_migration_order([(2, noop), (1, noop)])
    with pytest.raises(RuntimeError):
        db._validate_migration_order([(1, noop), (1, noop)])
    db._validate_migration_order([(1, noop), (2, noop)])  # the good case must not raise


def test_the_migration_boundary_reports_lost_bookkeeping_instead_of_going_silent(
    tmp_path, monkeypatch
):
    """Not from the brief -- constructed so the `lost` detector is an observed
    alarm rather than an assumed one. `.get(key, 1) - 1` yields 0 whether the
    key was healthily at 1 or was never there at all, so without the flag
    "normal exit" and "my bookkeeping was clobbered" are the same silent
    return -- the same class `transaction()`'s own `lost` flag exists to catch.

    Scaffold: enter the boundary, then delete its `_TXN_DEPTH` entry out from
    under it (standing in for whatever external interference would clobber it
    in production), then exit. The key is gone before `_exit_migration_boundary`
    ever looks at it, which is exactly the state the detector exists to notice."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    conn = db.get_connection(db_path)
    try:
        db._enter_migration_boundary(conn)
        db._TXN_DEPTH.pop(id(conn), None)  # clobbered out from under the boundary
        db._exit_migration_boundary(conn)

        text = "\n".join(
            p.read_text(encoding="utf-8") for p in (tmp_path / "logs").glob("app-*.log")
        )
        assert "db.migration_bookkeeping_lost" in text
    finally:
        conn.close()


def test_stages_status_rejects_a_value_outside_the_enum(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_stage_row(conn, project_id, "ideation", "awaiting_reveiw")  # the typo


def test_update_stage_status_rejects_a_value_outside_the_enum(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    with pytest.raises(sqlite3.IntegrityError):
        db.update_stage_status(conn, stage_row_id, "aproved")
    assert db.get_stage_by_row_id(conn, stage_row_id)["status"] == "ready"


def test_every_StageStatus_member_is_accepted_by_the_check(conn):
    """The constraint must not be narrower than the enum -- a CHECK that rejects
    a legitimate status is worse than none."""
    from pipeline_app.state_machine import StageStatus
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    for i, member in enumerate(StageStatus):
        db.create_stage_row(conn, project_id, f"stage-{i}", member.value)


def test_deleting_a_project_removes_its_stages(conn):
    """The rebuild declares `ON DELETE CASCADE` on `stages.project_id`. That is a
    real behaviour change (a delete used to fail or orphan depending on pragma
    state), so the task that lands it is the task that tests it. T7 extends the
    same assertion down to `turns`."""
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    assert conn.execute("SELECT count(*) FROM stages").fetchone()[0] == 0


def test_migration_coerces_a_ghost_stage_status_and_records_it(tmp_path: Path, monkeypatch):
    """A legacy database can already contain the typo. The migration must not
    brick the boot on it, and must not discard it silently either."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.executescript(
        "INSERT INTO projects (run_id, slug, brand, created_at) "
        "VALUES ('a-1','a','generic','2026-08-08T00:00:00+00:00');"
        "INSERT INTO stages (project_id, stage_id, status) VALUES (1,'ideation','awaiting_reveiw');"
    )
    c.commit()
    c.close()

    db.init_db(db_path, SCHEMA_PATH)

    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT status FROM stages WHERE id = 1").fetchone()[0] == "no_artifact"
        ev = c.execute(
            "SELECT * FROM events WHERE kind = 'schema.stage_status_coerced'"
        ).fetchall()
        assert len(ev) == 1
        assert "awaiting_reveiw" in ev[0]["message"]
    finally:
        c.close()


def test_the_rebuild_preserves_child_rows_referencing_stages(tmp_path: Path, monkeypatch):
    """The load-bearing test of this task.

    `DROP TABLE stages` performs an implicit DELETE, so with foreign key
    enforcement on it raises `FOREIGN KEY constraint failed` the instant any
    `turns` row references a stage -- which the operator's real database has, and
    which `LEGACY_SCHEMA_V0` reproduces. With no child row present the rebuild
    succeeds while still being wrong, so this is the only test in the file that
    goes red if `apply_migrations` stops disabling enforcement around its
    transaction."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.executescript(
        "INSERT INTO projects (run_id, slug, brand, created_at) "
        "VALUES ('a-1','a','generic','2026-08-08T00:00:00+00:00');"
        "INSERT INTO stages (project_id, stage_id, status) VALUES (1,'ideation','approved');"
        "INSERT INTO turns (stage_row_id, status, created_at, events_path) "
        "VALUES (1,'complete','2026-08-08T00:00:00+00:00','e/1.jsonl');"
    )
    c.commit()
    c.close()

    db.init_db(db_path, SCHEMA_PATH)

    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT status FROM stages WHERE id = 1").fetchone()[0] == "approved"
        # The child still resolves to its parent through the rebuilt table.
        joined = c.execute(
            "SELECT s.stage_id FROM turns t JOIN stages s ON s.id = t.stage_row_id"
        ).fetchall()
        assert [r["stage_id"] for r in joined] == ["ideation"]
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        assert "CHECK" in c.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'stages'").fetchone()[0]
    finally:
        c.close()


def test_foreign_key_enforcement_is_restored_after_a_migration(tmp_path: Path, monkeypatch):
    """`apply_migrations` turns enforcement off around its transaction. A
    connection handed back with it still off accepts orphans everywhere
    afterwards, and nothing else in the app ever looks. The migration body is a
    no-op here on purpose: this pins the pragma contract, not migration 1."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    monkeypatch.setattr(db, "_MIGRATIONS", [(1, lambda conn: None)])
    c = db.get_connection(db_path)
    try:
        c.execute("UPDATE schema_version SET version = 0 WHERE id = 1")
        c.commit()
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.apply_migrations(c) == [1]
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1, \
            "connection is still running without referential integrity enforcement"
    finally:
        c.close()


def test_a_migration_that_introduces_a_foreign_key_violation_fails_the_boot(
        tmp_path: Path, monkeypatch):
    """Disabling enforcement for the rebuild is only defensible because
    `PRAGMA foreign_key_check` replaces it. Without that gate a migration could
    write orphans that nothing would ever notice -- trading a loud constraint for
    a silent one, which is the trade this whole package exists to reverse."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)

    def orphan_maker(conn):
        conn.execute("INSERT INTO stages (project_id, stage_id, status) "
                     "VALUES (9999, 'ideation', 'ready')")

    monkeypatch.setattr(db, "_MIGRATIONS", [(1, orphan_maker)])
    c = db.get_connection(db_path)
    try:
        c.execute("UPDATE schema_version SET version = 0 WHERE id = 1")
        c.commit()
        with pytest.raises(db.MigrationIntegrityError):
            db.apply_migrations(c)
        # Rolled back whole: neither the orphan nor the stamp survived.
        assert c.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM stages").fetchone()[0] == 0
    finally:
        c.close()


def test_pre_existing_foreign_key_violations_do_not_brick_the_boot(tmp_path: Path, monkeypatch):
    """A violation the migration did not cause must not stop the app starting --
    and must not vanish either. Same ruling as the status coercion above."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.executescript(
        "INSERT INTO projects (run_id, slug, brand, created_at) "
        "VALUES ('a-1','a','generic','2026-08-08T00:00:00+00:00');"
        "INSERT INTO stages (project_id, stage_id, status) VALUES (1,'ideation','ready');"
        # sqlite3 leaves enforcement OFF by default, so a legacy write path could
        # and did produce this.
        "INSERT INTO turns (stage_row_id, status, created_at, events_path) "
        "VALUES (4242,'complete','2026-08-08T00:00:00+00:00','e/1.jsonl');"
    )
    c.commit()
    c.close()

    db.init_db(db_path, SCHEMA_PATH)  # must not raise

    c = db.get_connection(db_path)
    try:
        ev = c.execute(
            "SELECT * FROM events WHERE kind = 'schema.pre_existing_fk_violations'"
        ).fetchall()
        assert len(ev) == 1
        assert ev[0]["severity"] == "warning"
        assert c.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0] \
            == db.SCHEMA_VERSION
    finally:
        c.close()


def test_foreign_keys_are_restored_when_the_transaction_cannot_be_opened(
        tmp_path: Path, monkeypatch):
    """The connection must never come back with enforcement off and nothing said.
    BEGIN IMMEDIATE fails under write contention, which is the whole reason it is
    IMMEDIATE, so this path is reachable rather than theoretical."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    monkeypatch.setattr(db, "_MIGRATIONS", [(1, lambda conn: None)])

    blocker = db.get_connection(db_path)
    c = db.get_connection(db_path)
    try:
        c.execute("UPDATE schema_version SET version = 0 WHERE id = 1")
        c.commit()
        blocker.execute("BEGIN IMMEDIATE")
        blocker.execute("UPDATE schema_version SET version = 0 WHERE id = 1")
        c.execute("PRAGMA busy_timeout = 0")  # fail now rather than in five seconds
        with pytest.raises(sqlite3.OperationalError):
            db.apply_migrations(c)
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1, \
            "connection handed back without referential integrity enforcement"
    finally:
        blocker.rollback()
        blocker.close()
        c.close()


def test_a_failing_pragma_restore_does_not_swallow_the_migration_failure(
        tmp_path: Path, monkeypatch):
    """Reporting must never mask the thing being reported. If restoring enforcement
    blows up, the migration's own exception still propagates and its events row is
    still written -- otherwise a migration failure and a clean run look identical."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)

    def boom(conn):
        raise RuntimeError("the migration itself failed")

    def exploding_set(conn, enabled):
        if enabled:  # only the restore, not the disable
            raise sqlite3.ProgrammingError("pragma exploded")
        return False

    monkeypatch.setattr(db, "_MIGRATIONS", [(1, boom)])
    c = db.get_connection(db_path)
    try:
        c.execute("UPDATE schema_version SET version = 0 WHERE id = 1")
        c.commit()
        monkeypatch.setattr(db, "_set_foreign_keys", exploding_set)
        with pytest.raises(RuntimeError, match="the migration itself failed"):
            db.apply_migrations(c)
        monkeypatch.undo()
        rows = c.execute(
            "SELECT * FROM events WHERE kind = 'schema.migration_failed'").fetchall()
        assert len(rows) == 1
        assert "RuntimeError" in rows[0]["message"]
    finally:
        c.close()


def test_STAGE_STATUSES_matches_the_enum():
    """The tuple the migration reads, pinned to the enum it claims to mirror."""
    from pipeline_app.state_machine import StageStatus
    assert db.STAGE_STATUSES == tuple(m.value for m in StageStatus)


def test_every_StageStatus_member_is_accepted_by_the_migrated_table(
        tmp_path: Path, monkeypatch):
    """The migration-side half of the fresh-database test above. A fresh and a
    migrated database must not disagree about what a legal status is."""
    from pipeline_app import obs
    from pipeline_app.state_machine import StageStatus
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.execute("INSERT INTO projects (run_id, slug, brand, created_at) "
              "VALUES ('a-1','a','generic','2026-08-08T00:00:00+00:00')")
    c.commit()
    c.close()

    db.init_db(db_path, SCHEMA_PATH)

    c = db.get_connection(db_path)
    try:
        for i, member in enumerate(StageStatus):
            db.create_stage_row(c, 1, f"stage-{i}", member.value)
    finally:
        c.close()


def test_get_connection_enables_foreign_key_enforcement(tmp_path: Path):
    """Every FK constraint in schema.sql is inert without this, and nothing else
    in the app ever checks."""
    db_path = tmp_path / "pipeline.db"
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        c.close()


def _indexed_columns(conn) -> set[tuple[str, str]]:
    out = set()
    for tbl, in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for idx in conn.execute(f"PRAGMA index_list('{tbl}')").fetchall():
            for col in conn.execute(f"PRAGMA index_info('{idx['name']}')").fetchall():
                out.add((tbl, col["name"]))
    return out


def _foreign_key_columns(conn) -> set[tuple[str, str]]:
    """Every (table, column) declared a foreign key, read from the database.

    Derived rather than hand-listed: a hand-list makes a test named "every foreign
    key column" pass for a foreign key nobody remembered to add to it. This
    self-extends as later tasks add creators and handles."""
    out = set()
    for (tbl,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'").fetchall():
        for fk in conn.execute(f"PRAGMA foreign_key_list('{tbl}')").fetchall():
            out.add((tbl, fk["from"]))
    return out


def test_every_foreign_key_column_is_covered_by_an_index(conn):
    """An unindexed FK makes both the join and every integrity check a full
    scan, and turns is never pruned."""
    indexed = _indexed_columns(conn)
    for table, column in _foreign_key_columns(conn):
        assert (table, column) in indexed, f"{table}.{column} is an unindexed foreign key"


@pytest.mark.xfail(reason="handles.creator_id does not exist until T9", strict=True)
def test_handles_creator_id_is_covered_by_an_index(conn):
    """Split out of the test above rather than left as a failing assertion inside
    it. `handles.creator_id` is created by T9, so asserting it here would leave the
    suite red for two whole tasks -- and "the suite is red but we know why" is how a
    real regression gets waved through."""
    assert ("handles", "creator_id") in _indexed_columns(conn)


def test_every_foreign_key_column_is_still_indexed_after_the_migration(
        tmp_path: Path, monkeypatch):
    """The migrated-database half, and the reason it exists is a defect T6 hit
    already: schema.sql runs BEFORE the migration, so its `CREATE INDEX IF NOT
    EXISTS` lands on the OLD table -- and the rebuild's `DROP TABLE` then takes the
    index with it. A fresh database keeps its indices and a migrated one silently
    loses them, and the fresh-database test above passes either way."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        indexed = _indexed_columns(c)
        for table, column in _foreign_key_columns(c):
            assert (table, column) in indexed, \
                f"{table}.{column} lost its index in the rebuild"
    finally:
        c.close()


def test_turns_status_rejects_a_value_outside_the_vocabulary(conn):
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_turn(conn, stage_row_id, "complet", "2026-08-08T00:00:00+00:00", "e/1.jsonl")


# Verified against the call sites, not the plan: turn_service.py writes running,
# aborted, complete and failed; preflight.py writes orphaned.
TURN_STATUSES_THE_APP_WRITES = ("complete", "failed", "aborted", "orphaned")


def test_every_turn_status_the_app_writes_is_accepted(conn):
    """turn_service writes running/aborted/complete/failed; preflight writes
    orphaned. A CHECK narrower than that would break the app at runtime."""
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    turn_id = db.create_turn(conn, stage_row_id, "running", "2026-08-08T00:00:00+00:00", "e/1.jsonl")
    for status in ("complete", "failed", "aborted", "orphaned"):
        db.update_turn(conn, turn_id, status)


def test_deleting_a_project_cascades_to_its_stages_and_turns(conn):
    """No FK declared ON DELETE, so a future delete path would either fail or
    orphan rows depending on pragma state. Pin the behaviour now."""
    project_id = db.create_project(conn, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    db.create_turn(conn, stage_row_id, "complete", "2026-08-08T00:00:00+00:00", "e/1.jsonl")
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    assert conn.execute("SELECT count(*) FROM stages").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM turns").fetchone()[0] == 0


def test_deleting_a_project_cascades_on_a_migrated_database(tmp_path: Path, monkeypatch):
    """The migrated-database twin of the cascade test. Without it, dropping
    ON DELETE CASCADE from the rebuild's DDL changes nothing that any test can
    see -- which was true until this test existed."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        project_id = db.create_project(c, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
        stage_row_id = db.create_stage_row(c, project_id, "ideation", "ready")
        db.create_turn(c, stage_row_id, "complete", "2026-08-08T00:00:00+00:00", "e/1.jsonl")
        c.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        c.commit()
        assert c.execute("SELECT count(*) FROM stages").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM turns").fetchone()[0] == 0
    finally:
        c.close()


def test_deleting_a_discovery_run_or_a_handle_cascades_to_discovery_run_handles(conn):
    """discovery_run_handles has two foreign keys, run_id and handle_id, and
    until this task neither declared ON DELETE -- so a future delete path
    would either fail or orphan rows depending on pragma state, same as
    turns.stage_row_id. Cover both parents rather than just one. Terminal-status
    runs are used throughout so ux_discovery_single_running (the partial unique
    index on discovery_runs(status) WHERE status = 'running') never engages."""
    run_a = db.insert_terminal_run(
        conn, "r1", "manual", "incremental", "completed",
        "2026-08-08T00:00:00+00:00", "2026-08-08T00:01:00+00:00")
    run_b = db.insert_terminal_run(
        conn, "r2", "manual", "incremental", "completed",
        "2026-08-08T01:00:00+00:00", "2026-08-08T01:01:00+00:00")
    handle_a = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-08-08T00:00:00+00:00")
    handle_b = db.create_handle(conn, "youtube", "@b", None, "guru", None, "2026-08-08T00:00:00+00:00")
    db.record_handle_result(conn, run_a, handle_a, "ok", items_downloaded=1)
    db.record_handle_result(conn, run_b, handle_b, "ok", items_downloaded=1)

    conn.execute("DELETE FROM discovery_runs WHERE id = ?", (run_a,))
    conn.commit()
    assert conn.execute(
        "SELECT count(*) FROM discovery_run_handles WHERE run_id = ?", (run_a,)
    ).fetchone()[0] == 0

    conn.execute("DELETE FROM handles WHERE id = ?", (handle_b,))
    conn.commit()
    assert conn.execute(
        "SELECT count(*) FROM discovery_run_handles WHERE handle_id = ?", (handle_b,)
    ).fetchone()[0] == 0


def test_deleting_a_discovery_run_or_a_handle_cascades_on_a_migrated_database(
        tmp_path: Path, monkeypatch):
    """The migrated-database twin of the test above, for the same reason
    `test_deleting_a_project_cascades_on_a_migrated_database` exists: the fresh
    test exercises schema.sql's copy of the two ON DELETE CASCADE clauses and
    never the migration's."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        run_a = db.insert_terminal_run(
            c, "r1", "manual", "incremental", "completed",
            "2026-08-08T00:00:00+00:00", "2026-08-08T00:01:00+00:00")
        run_b = db.insert_terminal_run(
            c, "r2", "manual", "incremental", "completed",
            "2026-08-08T01:00:00+00:00", "2026-08-08T01:01:00+00:00")
        handle_a = db.create_handle(c, "youtube", "@a", None, "guru", None, "2026-08-08T00:00:00+00:00")
        handle_b = db.create_handle(c, "youtube", "@b", None, "guru", None, "2026-08-08T00:00:00+00:00")
        db.record_handle_result(c, run_a, handle_a, "ok", items_downloaded=1)
        db.record_handle_result(c, run_b, handle_b, "ok", items_downloaded=1)

        c.execute("DELETE FROM discovery_runs WHERE id = ?", (run_a,))
        c.commit()
        assert c.execute(
            "SELECT count(*) FROM discovery_run_handles WHERE run_id = ?", (run_a,)
        ).fetchone()[0] == 0

        c.execute("DELETE FROM handles WHERE id = ?", (handle_b,))
        c.commit()
        assert c.execute(
            "SELECT count(*) FROM discovery_run_handles WHERE handle_id = ?", (handle_b,)
        ).fetchone()[0] == 0
    finally:
        c.close()


def test_migration_coerces_a_ghost_turn_status_and_records_it(tmp_path: Path, monkeypatch):
    """Same ruling as the stage coercion in T6: a legacy row already holding a
    status the new CHECK rejects must not brick the boot, and must not vanish. A
    turn whose status cannot be interpreted *is* an orphan, so that is where it
    goes."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    c = sqlite3.connect(db_path)
    c.executescript(
        "INSERT INTO projects (run_id, slug, brand, created_at) "
        "VALUES ('a-1','a','generic','2026-08-08T00:00:00+00:00');"
        "INSERT INTO stages (project_id, stage_id, status) VALUES (1,'ideation','approved');"
        "INSERT INTO turns (stage_row_id, status, created_at, events_path) "
        "VALUES (1,'complet','2026-08-08T00:00:00+00:00','e/1.jsonl');"
    )
    c.commit()
    c.close()

    db.init_db(db_path, SCHEMA_PATH)

    c = db.get_connection(db_path)
    try:
        assert c.execute("SELECT status FROM turns WHERE id = 1").fetchone()[0] == "orphaned"
        ev = c.execute(
            "SELECT * FROM events WHERE kind = 'schema.turn_status_coerced'").fetchall()
        assert len(ev) == 1
        assert "complet" in ev[0]["message"]
    finally:
        c.close()


def test_every_turn_status_the_app_writes_is_accepted_by_the_migrated_table(
        tmp_path: Path, monkeypatch):
    """The migrated-database half of the vocabulary check, for the same reason T6
    needed one: the fresh-database test exercises schema.sql's copy of the CHECK
    list and never the migration's."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")
    db_path = _legacy_db(tmp_path)
    db.init_db(db_path, SCHEMA_PATH)
    c = db.get_connection(db_path)
    try:
        project_id = db.create_project(c, "a-1", "a", "generic", "2026-08-08T00:00:00+00:00")
        stage_row_id = db.create_stage_row(c, project_id, "ideation", "ready")
        turn_id = db.create_turn(c, stage_row_id, "running",
                                 "2026-08-08T00:00:00+00:00", "e/1.jsonl")
        for status in TURN_STATUSES_THE_APP_WRITES:
            db.update_turn(c, turn_id, status)
    finally:
        c.close()
