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


def test_traversal_slug_cannot_escape_the_runs_directory(conn, tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_root = (repo_root / "runs").resolve()
    before = {p.name for p in tmp_path.iterdir()}

    result = create_project(conn, repo_root, "../../pwned", "generic", STAGES)

    run_dir = result["run_dir"].resolve()
    assert run_dir.parent == runs_root
    assert run_dir.is_relative_to(runs_root)
    assert ".." not in result["run_id"]
    # nothing new was created alongside/above the repo root
    assert {p.name for p in tmp_path.iterdir()} == before


def test_slug_with_no_usable_characters_is_rejected(conn, tmp_path: Path):
    with pytest.raises(ValueError):
        create_project(conn, tmp_path, "../..", "generic", STAGES)


def test_slug_is_normalised_to_lowercase_hyphenated_form(conn, tmp_path: Path):
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    result = create_project(conn, tmp_path, "  Why Kids QUIT!  ", "generic", STAGES, now=now)
    assert result["run_id"] == "why-kids-quit-20260725-143200"


def test_stages_with_no_dependencies_start_ready_others_locked(conn, tmp_path: Path):
    result = create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES)
    ideation = db.get_stage(conn, result["project_id"], "ideation")
    scripting = db.get_stage(conn, result["project_id"], "scripting")
    assert ideation["status"] == "ready"
    assert scripting["status"] == "locked"


def test_create_project_leaves_nothing_behind_when_it_fails_partway(conn, tmp_path: Path, monkeypatch):
    """FAULT (A-70). create_project inserts the project row, then a stage row per
    stage. Without a transaction boundary the project row commits immediately, so
    an interruption during stage-row creation leaves an orphaned project with no
    stages -- exactly A-70's failure mode. Force the failure on the second step
    (the first stage-row insert) and assert the first step's row (the project) did
    not survive either."""
    def raise_on_stage_row(*args, **kwargs):
        raise RuntimeError("boom mid-way through stage row creation")

    monkeypatch.setattr(db, "create_stage_row", raise_on_stage_row)

    with pytest.raises(RuntimeError):
        create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES)

    assert db.list_projects(conn) == []
