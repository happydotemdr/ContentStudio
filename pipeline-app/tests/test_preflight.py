from pathlib import Path

import pytest

from pipeline_app import artifacts
from pipeline_app import db
from pipeline_app.pipeline_config import StageDef
from pipeline_app.preflight import check_cli_available, reconcile_orphaned_turns


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


STAGE_DEFS = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]


def test_reconcile_marks_running_turns_as_orphaned(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")

    count = reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)
    assert count == 1
    rows = db.list_turns(conn, stage_row_id)
    assert rows[0]["status"] == "orphaned"


def test_reconcile_resets_wedged_stage_to_ready_when_no_artifact(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    # No artifact.v1.md written anywhere under runs/ -- the turn died before producing one.

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    assert db.get_stage_by_row_id(conn, stage_row_id)["status"] == "ready"


def test_reconcile_resets_wedged_stage_to_awaiting_review_when_artifact_exists(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    artifacts.write_artifact(tmp_path / "runs" / "abc-1" / "01-ideation", 1, {"stage": "shorts-ideation"}, "body")

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    assert db.get_stage_by_row_id(conn, stage_row_id)["status"] == "awaiting_review"


def test_reconcile_is_a_no_op_when_nothing_running(conn, tmp_path: Path):
    assert reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS) == 0


def test_check_cli_available_true_when_binary_found():
    result = check_cli_available(which_fn=lambda name: r"C:\fake\claude.CMD")
    assert result["available"] is True
    assert result["path"] == r"C:\fake\claude.CMD"


def test_check_cli_available_false_when_missing():
    result = check_cli_available(which_fn=lambda name: None)
    assert result["available"] is False
    assert result["error"]
