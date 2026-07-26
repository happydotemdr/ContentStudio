import datetime
from pathlib import Path

import pytest

from pipeline_app import db
from pipeline_app.pipeline_config import StageDef
from pipeline_app.project_service import create_project

STAGES = [
    StageDef(id="grounding", skill="rgs-grounding", dir_prefix="00", depends_on=[], brand_scope="raisinggoodsports"),
    StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[]),
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=["ideation"]),
]


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_generic_project_has_no_grounding_stage_or_directory(conn, tmp_path: Path):
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    result = create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES, now=now)
    assert result["run_id"] == "why-kids-quit-20260725-143200"
    assert not (result["run_dir"] / "00-grounding").exists()
    assert (result["run_dir"] / "01-ideation").exists()
    rows = db.list_stages(conn, result["project_id"])
    assert {r["stage_id"] for r in rows} == {"ideation", "scripting"}


def test_rgs_project_includes_grounding_stage_and_directory(conn, tmp_path: Path):
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    result = create_project(conn, tmp_path, "why-kids-quit", "raisinggoodsports", STAGES, now=now)
    assert (result["run_dir"] / "00-grounding").exists()
    rows = db.list_stages(conn, result["project_id"])
    assert {r["stage_id"] for r in rows} == {"grounding", "ideation", "scripting"}


def test_stages_with_no_dependencies_start_ready_others_locked(conn, tmp_path: Path):
    result = create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES)
    ideation = db.get_stage(conn, result["project_id"], "ideation")
    scripting = db.get_stage(conn, result["project_id"], "scripting")
    assert ideation["status"] == "ready"
    assert scripting["status"] == "locked"
