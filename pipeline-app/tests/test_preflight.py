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


def test_reconcile_records_an_event_naming_the_project_and_stage(conn, tmp_path):
    """A-77 FAULT + SURFACING: _unwedge_stage restores awaiting_review whenever
    ANY artifact resolves -- but that artifact came from a PREVIOUS turn; the
    killed turn produced nothing. The resulting state is byte-identical to a
    healthy stage awaiting review, so the operator approves stale output
    believing the last turn succeeded. /doctor shows a bare orphaned_count."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    artifacts.write_artifact(
        tmp_path / "runs" / "abc-1" / "01-ideation", 1, {"stage": "shorts-ideation"}, "body"
    )

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    row = conn.execute("SELECT * FROM events WHERE kind = 'turn.orphaned'").fetchone()
    assert row is not None
    assert row["severity"] == "warning"
    assert "abc-1" in row["message"] and "ideation" in row["message"]


def test_an_orphaned_stage_is_distinguishable_from_a_healthy_awaiting_review(conn, tmp_path):
    """A-77 DISTINGUISHABILITY: the whole defect is that the two states are
    byte-identical. A healthy stage produces no turn.orphaned event."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "awaiting_review")
    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)
    assert conn.execute("SELECT COUNT(*) c FROM events "
                        "WHERE kind = 'turn.orphaned'").fetchone()["c"] == 0


def test_the_dead_turns_raw_output_is_quarantined_not_left_as_the_next_baseline(conn, tmp_path):
    """A-77: the dead turn's partially-written raw_output.md became the NEXT
    turn's before_mtime baseline, so a resumed turn writing identical content
    was detected as a change and one writing nothing was reported no_artifact."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    stage_dir = tmp_path / "runs" / "abc-1" / "01-ideation"
    stage_dir.mkdir(parents=True)
    (stage_dir / "raw_output.md").write_text("half a turn", encoding="utf-8")

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    assert not (stage_dir / "raw_output.md").exists()
    quarantined = list(stage_dir.glob("raw_output.orphaned-*.md"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8") == "half a turn"


def test_check_cli_available_true_when_binary_found():
    result = check_cli_available(which_fn=lambda name: r"C:\fake\claude.CMD")
    assert result["available"] is True
    assert result["path"] == r"C:\fake\claude.CMD"


def test_check_cli_available_false_when_missing():
    result = check_cli_available(which_fn=lambda name: None)
    assert result["available"] is False
    assert result["error"]
