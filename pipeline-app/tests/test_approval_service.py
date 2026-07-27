from pathlib import Path
from typing import AsyncIterator

import pytest

from pipeline_app import artifacts, db, turn_service
from pipeline_app.approval_service import approve_stage
from pipeline_app.grounding_service import write_pointer
from pipeline_app.pipeline_config import StageDef
from pipeline_app.state_machine import StageStatus

STAGES = [
    StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[]),
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=["ideation"]),
]

GROUNDING_STAGES = [
    StageDef(id="grounding", skill="rgs-grounding", dir_prefix="00", depends_on=[], brand_scope="raisinggoodsports"),
]

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "stage_templates"


def _fake_stream(events: list[dict], writes_file: Path | None = None, content: str = "generated body"):
    async def _gen(prompt, cwd, resume_session_id, **kwargs):
        if writes_file is not None:
            writes_file.parent.mkdir(parents=True, exist_ok=True)
            writes_file.write_text(content, encoding="utf-8")
        for event in events:
            yield event
    return _gen


async def _drain(agen: AsyncIterator[dict]) -> list[dict]:
    return [e async for e in agen]


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_approve_stamps_artifact_and_unlocks_dependent(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "awaiting_review")
    db.create_stage_row(conn, project_id, "scripting", "locked")

    run_dir = tmp_path / "runs" / "abc-1"
    stage_dir = run_dir / "01-ideation"
    artifacts.write_artifact(stage_dir, 1, {"status": "draft", "stage": "shorts-ideation"}, "body")

    unlocked = approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")
    assert unlocked == ["scripting"]

    meta, _ = artifacts.parse_frontmatter((stage_dir / "artifact.v1.md").read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["finalized_at"] is not None

    ideation_row = db.get_stage(conn, project_id, "ideation")
    assert ideation_row["status"] == StageStatus.APPROVED.value
    assert ideation_row["approved_at"] is not None

    scripting_row = db.get_stage(conn, project_id, "scripting")
    assert scripting_row["status"] == StageStatus.READY.value


def test_approve_stage_grounding_resolves_artifact_via_pointer(conn, tmp_path: Path):
    """Grounding's real output lands in rgs-briefs/<file>.md, referenced by a
    pointer.yaml the turn route writes into the stage dir (see
    grounding_service.write_pointer) -- not the artifact.v{N}.md convention
    every other stage uses. approve_stage must resolve through the pointer
    instead of glob-searching stage_dir directly."""
    project_id = db.create_project(conn, "rgs-1", "rgs", "raisinggoodsports", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "grounding", "awaiting_review")

    run_dir = tmp_path / "runs" / "rgs-1"
    grounding_dir = run_dir / "00-grounding"
    rgs_briefs_dir = tmp_path / "rgs-briefs"
    rgs_briefs_dir.mkdir(parents=True)
    brief_path = rgs_briefs_dir / "2026-07-27-example-brief.md"
    brief_path.write_text("---\nstatus: candidate\n---\n\nBrief body", encoding="utf-8")
    write_pointer(grounding_dir, "rgs-briefs/2026-07-27-example-brief.md")

    approve_stage(conn, tmp_path, run_dir, project_id, GROUNDING_STAGES, "grounding")

    meta, _ = artifacts.parse_frontmatter(brief_path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["finalized_at"] is not None

    grounding_row = db.get_stage(conn, project_id, "grounding")
    assert grounding_row["status"] == StageStatus.APPROVED.value


def test_approve_raises_when_no_artifact_exists(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    run_dir = tmp_path / "runs" / "abc-1"
    (run_dir / "01-ideation").mkdir(parents=True)
    with pytest.raises(ValueError):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")


def test_approve_stage_grounding_pointer_target_missing_returns_valueerror_not_crash(conn, tmp_path: Path):
    project_id = db.create_project(conn, "rgs-1", "rgs", "raisinggoodsports", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "grounding", "awaiting_review")
    run_dir = tmp_path / "runs" / "rgs-1"
    grounding_dir = run_dir / "00-grounding"
    write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")

    with pytest.raises(ValueError, match="No artifact to approve"):
        approve_stage(conn, tmp_path, run_dir, project_id, GROUNDING_STAGES, "grounding")


@pytest.mark.asyncio
async def test_regenerating_an_approved_stage_marks_approved_dependent_stale(conn, tmp_path: Path, monkeypatch):
    """End-to-end: approve ideation -> approve scripting (built on ideation
    v1) -> regenerate ideation to v2 -> scripting must flip to stale, since
    propagate_staleness compares against ideation's CURRENT latest artifact,
    not the exact (immutable) v1 file scripting's frontmatter recorded."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    db.create_stage_row(conn, project_id, "scripting", "locked")
    run_dir = tmp_path / "runs" / "abc-1"
    (run_dir / "01-ideation").mkdir(parents=True)
    (run_dir / "02-scripting").mkdir(parents=True)

    raw_output = run_dir / "01-ideation" / "raw_output.md"
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "result", "result": "done", "is_error": False},
    ]
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, raw_output, "v1 body"))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1", STAGES[0], STAGES, "idea",
    ))
    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")

    scripting_raw = run_dir / "02-scripting" / "raw_output.md"
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, scripting_raw, "script body"))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1", STAGES[1], STAGES, "",
    ))
    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")

    # Regenerate ideation -> v2
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, raw_output, "v2 body"))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1", STAGES[0], STAGES, "idea revised",
    ))

    ideation_dir = run_dir / "01-ideation"
    assert (ideation_dir / "artifact.v2.md").exists()
    meta_v2, _ = artifacts.parse_frontmatter((ideation_dir / "artifact.v2.md").read_text(encoding="utf-8"))
    assert meta_v2["supersedes"] == "artifact.v1.md"

    scripting_stage = db.get_stage(conn, project_id, "scripting")
    assert scripting_stage["status"] == StageStatus.STALE.value
