import datetime
from pathlib import Path
from typing import AsyncIterator

import pytest

from pipeline_app import artifacts, db
from pipeline_app.pipeline_config import StageDef
from pipeline_app.state_machine import StageStatus
from pipeline_app import turn_service

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "stage_templates"

STAGES = [
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
def project(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-20260725-120000", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    run_dir = tmp_path / "runs" / "abc-20260725-120000"
    (run_dir / "01-ideation").mkdir(parents=True)
    return {"project_id": project_id, "run_dir": run_dir, "stage_row_id": stage_row_id}


@pytest.mark.asyncio
async def test_first_turn_writes_artifact_v1_and_sets_awaiting_review(conn, project, monkeypatch, tmp_path):
    raw_output = project["run_dir"] / "01-ideation" / "raw_output.md"
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "result", "result": "done", "total_cost_usd": 0.01, "is_error": False},
    ]
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, raw_output))

    stage_def = STAGES[0]
    stage_row = db.get_stage(conn, project["project_id"], "ideation")
    collected = await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000",
        stage_def, STAGES, "a raw idea",
    ))
    assert len(collected) == 2

    stage_dir = project["run_dir"] / "01-ideation"
    v1 = stage_dir / "artifact.v1.md"
    assert v1.exists()
    meta, body = artifacts.parse_frontmatter(v1.read_text(encoding="utf-8"))
    assert meta["stage"] == "shorts-ideation"
    assert meta["version"] == 1
    assert meta["depends_on"] == []
    assert "generated body" in body

    updated_stage = db.get_stage(conn, project["project_id"], "ideation")
    assert updated_stage["status"] == StageStatus.AWAITING_REVIEW.value
    assert updated_stage["claude_session_id"] == "session-1"


@pytest.mark.asyncio
async def test_no_artifact_written_sets_no_artifact_status(conn, project, monkeypatch, tmp_path):
    events = [{"type": "result", "result": "just chatted, wrote nothing", "is_error": False}]
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(events, writes_file=None))

    stage_def = STAGES[0]
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000",
        stage_def, STAGES, "a raw idea",
    ))
    updated_stage = db.get_stage(conn, project["project_id"], "ideation")
    assert updated_stage["status"] == StageStatus.NO_ARTIFACT.value


@pytest.mark.asyncio
async def test_run_stage_turn_rejects_concurrent_turn(conn, project, monkeypatch, tmp_path):
    db.create_turn(conn, project["stage_row_id"], "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    stage_def = STAGES[0]
    with pytest.raises(turn_service.TurnAlreadyRunningError):
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
            project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea",
        ))


@pytest.mark.asyncio
async def test_run_stage_turn_rejects_locked_stage(conn, project, monkeypatch, tmp_path):
    """The locked/running invariant must be enforced by the service itself,
    not only by callers -- a route added without the check must still be
    protected."""
    db.update_stage_status(conn, project["stage_row_id"], StageStatus.LOCKED.value)
    stage_def = STAGES[0]
    with pytest.raises(turn_service.StageNotRunnableError):
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
            project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea",
        ))


@pytest.mark.asyncio
async def test_run_stage_turn_rejects_running_stage(conn, project, monkeypatch, tmp_path):
    db.update_stage_status(conn, project["stage_row_id"], StageStatus.RUNNING.value)
    stage_def = STAGES[0]
    with pytest.raises(turn_service.StageNotRunnableError):
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
            project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea",
        ))


@pytest.mark.asyncio
async def test_disconnected_turn_is_marked_aborted_not_left_running(conn, project, monkeypatch, tmp_path):
    """Simulates an SSE client disconnect: the caller stops draining the
    generator (calls aclose()) instead of consuming it to completion. The
    turn must end up 'aborted', not stuck 'running' forever — a stuck
    'running' row would permanently wedge the app-wide single-flight lock."""
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "assistant", "message": {}},
        {"type": "result", "result": "done", "is_error": False},
    ]

    async def _slow_gen(prompt, cwd, resume_session_id, **kwargs):
        for event in events:
            yield event

    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _slow_gen)

    stage_def = STAGES[0]
    agen = turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000", stage_def, STAGES, "idea",
    )
    await agen.__anext__()  # consume exactly one event, then simulate a dropped connection
    await agen.aclose()

    turns = db.list_turns(conn, project["stage_row_id"])
    assert turns[-1]["status"] == "aborted"
    assert turn_service.any_turn_running(conn) is False

    # No artifact was ever written for this stage, so the recovery rule
    # (same as preflight._unwedge_stage) must reset it to READY, not leave
    # it wedged at RUNNING forever.
    updated_stage = db.get_stage(conn, project["project_id"], "ideation")
    assert updated_stage["status"] == StageStatus.READY.value


CHAIN_STAGES = [
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=[]),
    StageDef(id="voiceover", skill="voiceover-brief", dir_prefix="03", depends_on=["scripting"]),
    StageDef(id="visual", skill="visual-prompts", dir_prefix="03", depends_on=["scripting"]),
    StageDef(id="assembly", skill="shorts-assembly", dir_prefix="04", depends_on=["voiceover", "visual"]),
    StageDef(id="repurpose", skill="social-repurpose", dir_prefix="05", depends_on=["assembly"]),
]


def _dep(run_dir: Path, relpath: str) -> dict:
    path = run_dir / relpath
    return {"path": relpath, "sha256": artifacts.compute_sha256(path)}


def _build_approved_chain(conn, tmp_path: Path, downstream_statuses: dict[str, str] | None = None):
    """Full scripting -> {voiceover, visual} -> assembly -> repurpose chain,
    every stage approved and every artifact's frontmatter recording the real
    hashes of the upstream artifacts it was built on. downstream_statuses
    overrides individual stage statuses."""
    statuses = {s.id: StageStatus.APPROVED.value for s in CHAIN_STAGES}
    statuses.update(downstream_statuses or {})
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    for stage in CHAIN_STAGES:
        db.create_stage_row(conn, project_id, stage.id, statuses[stage.id])

    run_dir = tmp_path / "runs" / "abc-1"
    artifacts.write_artifact(run_dir / "02-scripting", 1, {"stage": "shorts-scripting"}, "script v1")
    script_dep = [_dep(run_dir, "02-scripting/artifact.v1.md")]
    artifacts.write_artifact(run_dir / "03-voiceover", 1, {"stage": "voiceover-brief", "depends_on": script_dep}, "vo v1")
    artifacts.write_artifact(run_dir / "03-visual", 1, {"stage": "visual-prompts", "depends_on": script_dep}, "vis v1")
    assembly_dep = [
        _dep(run_dir, "03-voiceover/artifact.v1.md"),
        _dep(run_dir, "03-visual/artifact.v1.md"),
    ]
    artifacts.write_artifact(run_dir / "04-assembly", 1, {"stage": "shorts-assembly", "depends_on": assembly_dep}, "asm v1")
    artifacts.write_artifact(
        run_dir / "05-repurpose", 1,
        {"stage": "social-repurpose", "depends_on": [_dep(run_dir, "04-assembly/artifact.v1.md")]},
        "rep v1",
    )
    return project_id, run_dir


def test_propagate_staleness_cascades_past_direct_dependents(conn, tmp_path: Path):
    """Regenerating scripting must not stop at voiceover/visual: assembly and
    repurpose were built on those now-stale briefs, so leaving them approved
    reports a green final stage on a broken chain. The cascade cannot be a
    repeat of the hash check -- voiceover's own artifact file is untouched
    when it goes stale, so assembly's recorded hash for it still matches."""
    project_id, run_dir = _build_approved_chain(conn, tmp_path)

    # Regenerate scripting -> v2 becomes the current latest, so every
    # dependent's recorded 02-scripting/artifact.v1.md path stops matching.
    artifacts.write_artifact(run_dir / "02-scripting", 2, {"stage": "shorts-scripting"}, "script v2")

    turn_service.propagate_staleness(conn, run_dir, CHAIN_STAGES, project_id, "scripting")

    for stage_id in ("voiceover", "visual", "assembly", "repurpose"):
        assert db.get_stage(conn, project_id, stage_id)["status"] == StageStatus.STALE.value, stage_id


def test_propagate_staleness_cascade_stops_at_a_non_approved_stage(conn, tmp_path: Path):
    """The cascade only invalidates APPROVED work. assembly sitting at
    awaiting_review has nothing approved to invalidate, and repurpose is
    still built on assembly's unchanged v1 -- so repurpose stays approved."""
    project_id, run_dir = _build_approved_chain(
        conn, tmp_path, downstream_statuses={"assembly": StageStatus.AWAITING_REVIEW.value}
    )
    artifacts.write_artifact(run_dir / "02-scripting", 2, {"stage": "shorts-scripting"}, "script v2")

    turn_service.propagate_staleness(conn, run_dir, CHAIN_STAGES, project_id, "scripting")

    assert db.get_stage(conn, project_id, "voiceover")["status"] == StageStatus.STALE.value
    assert db.get_stage(conn, project_id, "visual")["status"] == StageStatus.STALE.value
    assert db.get_stage(conn, project_id, "assembly")["status"] == StageStatus.AWAITING_REVIEW.value
    assert db.get_stage(conn, project_id, "repurpose")["status"] == StageStatus.APPROVED.value
