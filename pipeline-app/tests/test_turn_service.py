import datetime
import json
import shutil
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import ANY

import pytest

from pipeline_app import artifacts, db, gates, grounding_service
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


def _fake_stream(events: list[dict], writes_file: Path | None = None, content: str = "generated body",
                  captured: list[dict] | None = None):
    async def _gen(prompt, cwd, resume_session_id, **kwargs):
        if captured is not None:
            captured.append({"prompt": prompt, "cwd": cwd,
                             "resume_session_id": resume_session_id, "kwargs": kwargs})
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
    meta, body = artifacts.read_artifact(v1)
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
async def test_run_stage_turn_rejects_a_stage_the_project_has_no_row_for(conn, project, tmp_path):
    """db.get_stage returns None for a brand-scoped stage on an out-of-scope
    project -- the exact case migrations.py exists to repair. Indexing it gave a
    TypeError and a 500, while propagate_staleness handles the same case at :67."""
    with pytest.raises(turn_service.StageNotRunnableError, match="no row for stage 'grounding'"):
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
            project["project_id"], "abc-20260725-120000",
            StageDef(id="grounding", skill="rgs-grounding", dir_prefix="00"),
            STAGES, "topic"))


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


@pytest.mark.asyncio
async def test_aborted_turn_still_persists_session_id_captured_from_init_event(conn, project, monkeypatch, tmp_path):
    """A disconnect must not throw away a session id the CLI already handed
    back -- without it, the next attempt can't resume and re-pays for the
    whole kickoff prompt (see turn_service.py's is_first_turn check)."""
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
    await agen.__anext__()  # consume only the init event, then simulate a dropped connection
    await agen.aclose()

    updated_stage = db.get_stage(conn, project["project_id"], "ideation")
    assert updated_stage["claude_session_id"] == "session-1"


@pytest.mark.asyncio
async def test_aborted_turn_persists_cost_when_a_result_event_was_captured(conn, project, monkeypatch, tmp_path):
    """Rare but real: the disconnect can land after the CLI already sent its
    `result` event (with the turn's cost) but before run_stage_turn finished
    its own bookkeeping. That cost must not be thrown away."""
    events = [
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "result", "result": "done", "total_cost_usd": 0.42, "is_error": False},
        {"type": "system", "subtype": "extra"},
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
    await agen.__anext__()  # init
    await agen.__anext__()  # result -- cost is now inside `collected`
    await agen.aclose()      # disconnect happens after the result, before natural completion

    turns = db.list_turns(conn, project["stage_row_id"])
    assert turns[-1]["status"] == "aborted"
    assert turns[-1]["cost_usd"] == 0.42


@pytest.mark.asyncio
async def test_a_session_that_never_opened_is_cleared_so_the_next_turn_re_renders(
        conn, project, tmp_path, monkeypatch):
    """A-06: --resume <dead-id> fails, the stage lands in no_artifact, and
    is_first_turn stays False forever -- there was no in-app recovery at all."""
    db.update_stage_session(conn, project["stage_row_id"], "dead-session")
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream(
        [{"type": "result", "result": "No conversation found with session ID", "is_error": True}]))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000", STAGES[0], STAGES, "go"))
    assert db.get_stage(conn, project["project_id"], "ideation")["claude_session_id"] is None


@pytest.mark.asyncio
async def test_a_failed_turn_on_a_live_session_keeps_the_session_id(conn, project, tmp_path, monkeypatch):
    """Distinguishability: an ordinary failed turn (the session DID open) must
    not be mistaken for a dead session id and lose its resume point."""
    db.update_stage_session(conn, project["stage_row_id"], "session-1")
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn", _fake_stream([
        {"type": "system", "subtype": "init", "session_id": "session-1"},
        {"type": "result", "result": "tool error", "is_error": True}]))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], "abc-20260725-120000", STAGES[0], STAGES, "go"))
    assert db.get_stage(conn, project["project_id"], "ideation")["claude_session_id"] == "session-1"


CHAIN_STAGES = [
    # "ideation" carries depends_on=[] and is not itself a dependent of
    # "scripting" here (scripting's own depends_on stays [] -- see the
    # deviation note on test_a_turn_records_the_grounding_brief_it_was_built_on
    # below for why). It exists in this list only so stages that DO declare
    # "ideation" as an upstream (repurpose, widened below) can resolve it --
    # gates.resolve_upstream_by_stage looks the id up in all_stage_defs, and
    # an id with no matching StageDef here is silently dropped from inputs
    # rather than erroring, which would otherwise make repurpose's kickoff
    # prompt quietly miss its ideation fragment instead of failing loudly.
    StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[]),
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=[]),
    StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b", depends_on=["scripting"]),
    StageDef(id="voiceover", skill="voiceover-brief", dir_prefix="03", depends_on=["scripting"]),
    StageDef(id="visual", skill="visual-prompts", dir_prefix="03", depends_on=["scripting", "styleboard"]),
    StageDef(id="music", skill="music-brief", dir_prefix="03", depends_on=["scripting", "voiceover"]),
    StageDef(
        id="assembly", skill="shorts-assembly", dir_prefix="04",
        depends_on=["scripting", "styleboard", "voiceover", "visual"],
        optional_depends_on=["music"],
    ),
    StageDef(id="repurpose", skill="social-repurpose", dir_prefix="05",
             depends_on=["ideation", "scripting", "assembly"]),
]


def _by_id(stage_id: str) -> StageDef:
    return next(s for s in CHAIN_STAGES if s.id == stage_id)


def _draft_artifact(stage_dir: Path, version: int, stage_name: str, body: str) -> Path:
    return artifacts.write_artifact(stage_dir, version, {"stage": stage_name}, body)


def _final_artifact(stage_dir: Path, version: int, stage_name: str, body: str) -> Path:
    path = _draft_artifact(stage_dir, version, stage_name, body)
    artifacts.stamp_final(path, "2026-08-08T00:00:00Z")
    return path


def _dep(run_dir: Path, relpath: str) -> dict:
    path = run_dir / relpath
    return {"path": relpath, "sha256": artifacts.compute_sha256(path)}


def _build_approved_chain(
    conn, tmp_path: Path, downstream_statuses: dict[str, str] | None = None, with_music: bool = False
):
    """Full scripting -> styleboard -> {voiceover, visual} -> assembly -> repurpose
    chain, every stage approved and every artifact's frontmatter recording the
    real hashes of the upstream artifacts it was built on. downstream_statuses
    overrides individual stage statuses. with_music additionally writes an
    approved 03-music bed-arc artifact and folds its dep into assembly's
    recorded depends_on, exercising the optional music->assembly edge."""
    statuses = {s.id: StageStatus.APPROVED.value for s in CHAIN_STAGES}
    statuses.update(downstream_statuses or {})
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    for stage in CHAIN_STAGES:
        db.create_stage_row(conn, project_id, stage.id, statuses[stage.id])

    run_dir = tmp_path / "runs" / "abc-1"
    _stamp = lambda path: artifacts.stamp_final(path, "2026-08-08T00:00:00Z")
    _stamp(artifacts.write_artifact(run_dir / "02-scripting", 1, {"stage": "shorts-scripting"}, "script v1"))
    script_dep = [_dep(run_dir, "02-scripting/artifact.v1.md")]
    _stamp(artifacts.write_artifact(run_dir / "02b-styleboard", 1,
                             {"stage": "shorts-styleboard", "depends_on": script_dep}, "styleboard v1"))
    styleboard_dep = [_dep(run_dir, "02b-styleboard/artifact.v1.md")]
    _stamp(artifacts.write_artifact(run_dir / "03-voiceover", 1, {"stage": "voiceover-brief", "depends_on": script_dep}, "vo v1"))
    _stamp(artifacts.write_artifact(run_dir / "03-visual", 1,
                             {"stage": "visual-prompts", "depends_on": script_dep + styleboard_dep}, "vis v1"))
    assembly_dep = [
        *script_dep, *styleboard_dep,
        _dep(run_dir, "03-voiceover/artifact.v1.md"),
        _dep(run_dir, "03-visual/artifact.v1.md"),
    ]
    if with_music:
        music_dep = script_dep + [_dep(run_dir, "03-voiceover/artifact.v1.md")]
        _stamp(artifacts.write_artifact(run_dir / "03-music", 1,
                                        {"stage": "music-brief", "depends_on": music_dep}, "bed v1"))
        assembly_dep = [*assembly_dep, _dep(run_dir, "03-music/artifact.v1.md")]
    _stamp(artifacts.write_artifact(run_dir / "04-assembly", 1, {"stage": "shorts-assembly", "depends_on": assembly_dep}, "asm v1"))
    _stamp(artifacts.write_artifact(
        run_dir / "05-repurpose", 1,
        {"stage": "social-repurpose", "depends_on": [_dep(run_dir, "04-assembly/artifact.v1.md")]},
        "rep v1",
    ))
    return project_id, run_dir


_approved_chain = _build_approved_chain


_INIT = {"type": "system", "subtype": "init", "session_id": "session-1"}
_RESULT_OK = {"type": "result", "result": "done", "total_cost_usd": 0.01, "is_error": False}


@pytest.mark.asyncio
async def test_aborting_a_turn_on_a_stale_stage_leaves_it_stale(conn, tmp_path, monkeypatch):
    """A-46: a stale stage always has an artifact, so the abort recovery's
    `latest is not None` branch always resolved to awaiting_review -- opening
    chat on a stale stage and closing the tab erased the only cue that the
    artifact was built on a since-changed input."""
    project_id, run_dir = _approved_chain(conn, tmp_path,
                                          downstream_statuses={"voiceover": StageStatus.STALE.value})
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK]))
    agen = turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "redo")
    await agen.__anext__()
    await agen.aclose()
    assert db.get_stage(conn, project_id, "voiceover")["status"] == StageStatus.STALE.value


@pytest.mark.asyncio
async def test_aborting_a_turn_on_an_approved_stage_leaves_it_approved(conn, tmp_path, monkeypatch):
    """Distinguishability: `approved -> running -> abort` laundered into
    awaiting_review too. Restoring the prior status must be exact, not a guess
    keyed to artifact existence."""
    project_id, run_dir = _approved_chain(conn, tmp_path)   # no override -> voiceover starts APPROVED
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK]))
    agen = turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "redo")
    await agen.__anext__()
    await agen.aclose()
    assert db.get_stage(conn, project_id, "voiceover")["status"] == StageStatus.APPROVED.value


@pytest.fixture
def capture() -> list[dict]:
    return []


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


def test_propagate_staleness_marks_an_unapproved_draft_stale_too(conn, tmp_path):
    """A-44: propagate_staleness skipped any dependent not `approved`, so a draft
    sitting at awaiting_review whose upstream had since been regenerated was never
    flagged -- and approving it recorded the draft's original hashes as current.
    A Short could ship built on a script replaced before the draft was approved."""
    project_id, run_dir = _build_approved_chain(
        conn, tmp_path, downstream_statuses={"assembly": StageStatus.AWAITING_REVIEW.value})
    artifacts.write_artifact(run_dir / "02-scripting", 2, {"stage": "shorts-scripting"}, "script v2")

    turn_service.propagate_staleness(conn, run_dir, CHAIN_STAGES, project_id, "scripting")

    assert db.get_stage(conn, project_id, "assembly")["status"] == StageStatus.STALE.value
    assert db.get_stage(conn, project_id, "repurpose")["status"] == StageStatus.STALE.value


def test_a_locked_dependent_is_not_marked_stale(conn, tmp_path):
    """Distinguishability: `locked` (never run) is not `stale` (run on stale
    input). Widening past approved must not swallow the never-started case."""
    project_id, run_dir = _build_approved_chain(
        conn, tmp_path, downstream_statuses={"assembly": StageStatus.LOCKED.value})
    artifacts.write_artifact(run_dir / "02-scripting", 2, {"stage": "shorts-scripting"}, "script v2")
    turn_service.propagate_staleness(conn, run_dir, CHAIN_STAGES, project_id, "scripting")
    assert db.get_stage(conn, project_id, "assembly")["status"] == StageStatus.LOCKED.value


def test_regenerating_the_bed_arc_marks_assembly_stale(conn, tmp_path):
    """A-02's other half: `music` was a graph leaf, so _dependents_of returned
    empty for it and a regenerated bed arc never invalidated the edit plan."""
    project_id, run_dir = _build_approved_chain(conn, tmp_path, with_music=True)
    artifacts.write_artifact(run_dir / "03-music", 2, {"stage": "music-brief"}, "bed v2")
    turn_service.propagate_staleness(conn, run_dir, CHAIN_STAGES, project_id, "music")
    assert db.get_stage(conn, project_id, "assembly")["status"] == StageStatus.STALE.value


def test_one_malformed_dependent_does_not_abort_the_staleness_cascade(conn, tmp_path):
    """P2 §6.3 item 5. parse_frontmatter now RAISES instead of returning {}, so
    an unguarded loop stops at the first damaged artifact -- leaving the stages
    before it stale and the stages after it silently approved. Worse than the
    bug it replaced, unless every per-dependent read is contained."""
    project_id, run_dir = _build_approved_chain(conn, tmp_path)
    (run_dir / "03-voiceover" / "artifact.v1.md").write_text(
        "---\nthis frontmatter never terminates\n", encoding="utf-8")
    artifacts.write_artifact(run_dir / "02-scripting", 2, {"stage": "shorts-scripting"}, "v2")

    turn_service.propagate_staleness(conn, run_dir, CHAIN_STAGES, project_id, "scripting",
                                     repo_root=tmp_path)

    # visual is AFTER voiceover in CHAIN_STAGES order -- it must still be reached.
    assert db.get_stage(conn, project_id, "visual")["status"] == StageStatus.STALE.value


def test_a_malformed_dependent_is_recorded_not_skipped_in_silence(conn, tmp_path):
    """Distinguishability + surfacing: 'this dependent is fine' and 'this
    dependent is unreadable' must not both produce a no-op."""
    project_id, run_dir = _build_approved_chain(conn, tmp_path)
    (run_dir / "03-voiceover" / "artifact.v1.md").write_text(
        "---\nthis frontmatter never terminates\n", encoding="utf-8")
    artifacts.write_artifact(run_dir / "02-scripting", 2, {"stage": "shorts-scripting"}, "v2")

    turn_service.propagate_staleness(conn, run_dir, CHAIN_STAGES, project_id, "scripting",
                                     repo_root=tmp_path)

    rows = conn.execute(
        "SELECT severity, message FROM events WHERE kind = 'staleness.dependent_unreadable'"
    ).fetchall()
    assert rows and rows[0]["severity"] == "error" and "03-voiceover" in rows[0]["message"]


@pytest.mark.asyncio
async def test_depends_on_is_computed_by_the_shared_helper(conn, tmp_path, monkeypatch):
    """P2 §6.1: one implementation of the [{path, sha256}] shape, not two."""
    calls = []
    real = artifacts.compute_depends_on
    monkeypatch.setattr(artifacts, "compute_depends_on",
                        lambda run_dir, paths: calls.append(list(paths)) or real(run_dir, paths))
    project_id, run_dir = _approved_chain(conn, tmp_path)
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_RESULT_OK], run_dir / "04-assembly" / "raw_output.md"))

    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("assembly"), CHAIN_STAGES, "cut it",
    ))

    assert calls and len(calls[0]) == 4


@pytest.mark.asyncio
async def test_a_concurrent_version_allocation_does_not_lose_the_write(conn, tmp_path, monkeypatch):
    """next_version_number is ADVISORY ONLY under P2 (A-65). run_stage_turn must
    reserve, write, and release -- leaving it on next_version_number + write_artifact
    turns a silent lost write into an ArtifactExistsError 500, which is better but
    not closed."""
    project_id, run_dir = _approved_chain(conn, tmp_path)
    stage_dir = run_dir / "03-voiceover"

    # Simulate a concurrent turn that has already reserved the next version slot
    # but not yet written it -- run_stage_turn's own allocation must skip past
    # the live reservation rather than colliding with it or losing either write.
    concurrent = artifacts.reserve_version(stage_dir)
    assert concurrent.version == 2

    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_RESULT_OK], stage_dir / "raw_output.md"))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "brief it",
    ))

    # run_stage_turn moved past the still-live reservation to v3, leaving the
    # concurrent turn's reserved slot untouched.
    assert not (stage_dir / "artifact.v2.md").exists()
    assert (stage_dir / "artifact.v3.md").exists()

    artifacts.release_version(concurrent)
    with pytest.raises(artifacts.ArtifactExistsError):
        artifacts.write_artifact(stage_dir, 3, {"stage": "x"}, "clobber")


def test_staleness_hashing_without_a_repo_root_says_so_for_a_pointer_backed_upstream(tmp_path, capsys):
    """A-14: latest_artifact_path cannot see grounding's pointer indirection, so
    a depends_on edge onto grounding would silently drop it from BOTH input
    collection and staleness hashing. It must warn, not shrug."""
    grounding = StageDef(id="grounding", skill="rgs-grounding", dir_prefix="00", depends_on=[])
    hashes = turn_service._current_upstream_hashes(tmp_path, [grounding], repo_root=None)
    assert hashes == {}
    events = [json.loads(line) for line in capsys.readouterr().err.strip().splitlines() if line.strip()]
    assert any(e.get("event") == "staleness.pointer_upstream_unresolvable" for e in events)


@pytest.mark.asyncio
async def test_missing_required_upstream_refuses_the_turn(conn, tmp_path, monkeypatch):
    """A-07: input_file was passed as Python None, so scripting.md rendered
    ``Read the concept brief at `None` `` -- a plausible path the model tries,
    fails on, and works around."""
    project_id = db.create_project(conn, "m-1", "m", "generic", "2026-08-08T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", StageStatus.APPROVED.value)
    db.create_stage_row(conn, project_id, "scripting", StageStatus.READY.value)
    run_dir = tmp_path / "runs" / "m-1"
    (run_dir / "01-ideation").mkdir(parents=True)   # approved, but the file is gone

    with pytest.raises(turn_service.MissingUpstreamArtifactError, match="ideation"):
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "m-1",
            STAGES[1], STAGES, "go",
        ))
    assert turn_service.any_turn_running(conn) is False   # no wedged turn row


@pytest.mark.asyncio
async def test_missing_optional_upstream_renders_a_valid_prompt(conn, tmp_path, monkeypatch, capture):
    """Distinguishability: 'the bed arc was never produced' (legitimate) must be
    observably different from 'the script is gone' (fault). One renders, one raises."""
    project_id, run_dir = _approved_chain(conn, tmp_path)   # no music artifact
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_RESULT_OK], run_dir / "04-assembly" / "raw_output.md",
                                     captured=capture))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("assembly"), CHAIN_STAGES, "cut it",
    ))
    assert "No music bed brief" in capture[0]["prompt"]


@pytest.mark.asyncio
async def test_missing_required_upstream_records_an_error_event(conn, tmp_path):
    """Surfacing: the refusal must leave a row a human can find, not just an
    exception inside an SSE body generator."""
    project_id = db.create_project(conn, "m-2", "m", "generic", "2026-08-08T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", StageStatus.APPROVED.value)
    db.create_stage_row(conn, project_id, "scripting", StageStatus.READY.value)
    run_dir = tmp_path / "runs" / "m-2"
    (run_dir / "01-ideation").mkdir(parents=True)   # approved, but the file is gone

    with pytest.raises(turn_service.MissingUpstreamArtifactError):
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "m-2",
            STAGES[1], STAGES, "go",
        ))
    rows = conn.execute(
        "SELECT kind, severity, message FROM events WHERE kind = 'handoff.upstream_missing'"
    ).fetchall()
    assert len(rows) == 1 and rows[0]["severity"] == "error"
    assert "ideation" in rows[0]["message"]


@pytest.mark.asyncio
async def test_whatever_the_gate_runner_returns_is_recorded_verbatim(conn, tmp_path, monkeypatch):
    """Renamed from test_scripting_turn_records_gate_results_in_frontmatter
    (F-26). It monkeypatches gates.run_gates_for_stage to return a hard-coded
    literal and asserts that same literal round-trips into the frontmatter --
    a round trip and nothing more. It proves nothing about what a real gate
    run over a real script produces; the three tests below (P1's
    test_cli_availability_is_recorded_on_app_state pattern) run the actual
    registered Gate D linter for that."""
    project_id = db.create_project(conn, "gate-1", "gate", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    db.create_stage_row(conn, project_id, "scripting", "ready")

    run_dir = tmp_path / "runs" / "gate-1"
    stage_dir = run_dir / "02-scripting"
    raw = stage_dir / "raw_output.md"
    _final_artifact(run_dir / "01-ideation", 1, "shorts-ideation", "concept v1")

    monkeypatch.setattr(
        turn_service.cli_runner,
        "stream_claude_turn",
        _fake_stream(
            [{"type": "result", "result": "ok", "total_cost_usd": 0.1, "is_error": False}],
            writes_file=raw,
            content=(
                'HOOK (0–3s | 8 words): "It is not more serious play — it is labor."\n'
                "GATES\n  Gate E (fresh Opus critic): pass\n"
            ),
        ),
    )
    monkeypatch.setattr(
        turn_service.gates,
        "run_gates_for_stage",
        lambda root, sid, path, upstream: [{
            "name": "gate_d_script_language",
            "status": "fail",
            "findings": [{"check": "D1", "beat": "HOOK", "message": "em-dash", "kind": "fail"}],
        }],
    )

    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "gate-1",
        STAGES[1], STAGES, "go",
    ))

    latest = artifacts.latest_artifact_path(stage_dir)
    assert latest is not None
    meta, _ = artifacts.read_artifact(latest)
    assert meta["gates"][0]["status"] == "fail"
    assert db.get_stage(conn, project_id, "scripting")["status"] == StageStatus.AWAITING_REVIEW.value


# The real repo root, for the three tests below that need
# gates.run_gates_for_stage to load the actual scripts/lint_script_language.py
# rather than error out against an isolated tmp_path repo_root that has no
# scripts/ directory of its own. Mirrors test_gates.py's and
# test_routes_approve_edit.py's REPO_ROOT / _install_real_script_linter of the
# same name and for the same reason -- gates.py only ever READS this path
# (never writes under it), so pointing repo_root at the live tree is safe, but
# these tests copy the linter into an isolated tmp_path/scripts instead, to
# match this file's existing convention of repo_root == tmp_path everywhere
# else in run_stage_turn's call sites.
REPO_ROOT = Path(__file__).resolve().parents[2]


def _install_real_script_linter(repo_root: Path) -> None:
    dest = repo_root / "scripts"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        REPO_ROOT / "scripts" / "lint_script_language.py",
        dest / "lint_script_language.py",
    )


# Genuinely five-beat, fully-compliant scripts (Gate D's T2 requires all five
# top-level beats; T4 requires a >50%-ratable pace floor) -- mirrors
# test_gates.py's CLEAN_SCRIPT/DASHED_SCRIPT of the same names and for the
# same reason: a HOOK-only fixture fails gate_d_script_language for real
# (missing-beat PARSE finding) before D1 is even reached, which would
# conflate "the script is incomplete" with "the script has an em-dash" --
# the two things these tests need to keep distinguishable.
CLEAN_SCRIPT = (
    'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
    'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
    'BUILD/VALUE (8–18s | 10 words): "A position stand reports that kids still reach elite level."\n'
    'PAYOFF (18–28s | 10 words): "The next tier exists because someone needs it sold now."\n'
    'LOOP/CTA (28–33s | 5 words): "Best part was the mud."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)
DASHED_SCRIPT = (
    # 0-5s (not 0-3s): the beat needs enough runway that the em-dash trips D1
    # without also tripping D5's wpm ceiling on this line's 9 spoken words --
    # this isolates D1. The other four beats are otherwise identical to
    # CLEAN_SCRIPT's, so this script's only defect is the HOOK line's em-dash.
    'HOOK (0–5s | 8 words): "It is not more serious play — it is labor."\n'
    'SETUP (5–10s | 6 words): "Kids do that every single time."\n'
    'BUILD/VALUE (10–20s | 10 words): "A position stand reports that kids still reach elite level."\n'
    'PAYOFF (20–30s | 10 words): "The next tier exists because someone needs it sold now."\n'
    'LOOP/CTA (30–35s | 5 words): "Best part was the mud."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)


@pytest.mark.asyncio
async def test_a_real_failing_gate_is_recorded_from_an_actual_lint_run(conn, tmp_path, monkeypatch):
    """FAULT. The predecessor injected `{"status": "fail"}` into a mock and
    asserted it came back (F-26). This runs the registered Gate D linter over
    a script that genuinely violates D1, so the recorded result is produced,
    not supplied."""
    project_id = db.create_project(conn, "gate-real-fail", "gate", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    db.create_stage_row(conn, project_id, "scripting", "ready")

    run_dir = tmp_path / "runs" / "gate-real-fail"
    stage_dir = run_dir / "02-scripting"
    raw = stage_dir / "raw_output.md"
    _final_artifact(run_dir / "01-ideation", 1, "shorts-ideation", "concept v1")
    _install_real_script_linter(tmp_path)

    monkeypatch.setattr(
        turn_service.cli_runner,
        "stream_claude_turn",
        _fake_stream(
            [{"type": "result", "result": "ok", "total_cost_usd": 0.1, "is_error": False}],
            writes_file=raw,
            content=DASHED_SCRIPT,
        ),
    )

    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "gate-real-fail",
        STAGES[1], STAGES, "go",
    ))

    meta, _ = artifacts.read_artifact(artifacts.latest_artifact_path(stage_dir))
    recorded = {g["name"]: g["status"] for g in meta["gates"]}
    assert recorded["gate_d_script_language"] == "fail"
    assert any(f["check"] == "D1" for g in meta["gates"] for f in g["findings"])


@pytest.mark.asyncio
async def test_a_clean_script_records_the_same_gate_as_passing(conn, tmp_path, monkeypatch):
    """DISTINGUISHABILITY. A test that only ever sees `fail` cannot tell a real
    lint run from a stuck one. Same stage, same runner, opposite verdict."""
    project_id = db.create_project(conn, "gate-real-clean", "gate", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    db.create_stage_row(conn, project_id, "scripting", "ready")

    run_dir = tmp_path / "runs" / "gate-real-clean"
    stage_dir = run_dir / "02-scripting"
    raw = stage_dir / "raw_output.md"
    _final_artifact(run_dir / "01-ideation", 1, "shorts-ideation", "concept v1")
    _install_real_script_linter(tmp_path)

    monkeypatch.setattr(
        turn_service.cli_runner,
        "stream_claude_turn",
        _fake_stream(
            [{"type": "result", "result": "ok", "total_cost_usd": 0.1, "is_error": False}],
            writes_file=raw,
            content=CLEAN_SCRIPT,
        ),
    )

    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "gate-real-clean",
        STAGES[1], STAGES, "go",
    ))

    meta, _ = artifacts.read_artifact(artifacts.latest_artifact_path(stage_dir))
    recorded = {g["name"]: g["status"] for g in meta["gates"]}
    assert recorded["gate_d_script_language"] == "pass"


@pytest.mark.asyncio
async def test_a_failing_gate_still_leaves_the_artifact_and_the_stage_reviewable(
        conn, tmp_path, monkeypatch):
    """SURFACING. The operator must be able to see what failed: the artifact is
    on disk, the stage is awaiting_review, and the findings are in
    frontmatter."""
    project_id = db.create_project(conn, "gate-real-surface", "gate", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    db.create_stage_row(conn, project_id, "scripting", "ready")

    run_dir = tmp_path / "runs" / "gate-real-surface"
    stage_dir = run_dir / "02-scripting"
    raw = stage_dir / "raw_output.md"
    _final_artifact(run_dir / "01-ideation", 1, "shorts-ideation", "concept v1")
    _install_real_script_linter(tmp_path)

    monkeypatch.setattr(
        turn_service.cli_runner,
        "stream_claude_turn",
        _fake_stream(
            [{"type": "result", "result": "ok", "total_cost_usd": 0.1, "is_error": False}],
            writes_file=raw,
            content=DASHED_SCRIPT,
        ),
    )

    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "gate-real-surface",
        STAGES[1], STAGES, "go",
    ))

    latest = artifacts.latest_artifact_path(stage_dir)
    assert latest is not None
    meta, _ = artifacts.read_artifact(latest)
    recorded = {g["name"]: g["status"] for g in meta["gates"]}
    assert recorded["gate_d_script_language"] == "fail"
    assert any(f["check"] == "D1" for g in meta["gates"] for f in g["findings"])
    assert db.get_stage(conn, project_id, "scripting")["status"] == StageStatus.AWAITING_REVIEW.value


@pytest.mark.asyncio
async def test_upstream_resolves_to_the_approved_version_not_an_unapproved_draft(
        conn, tmp_path, monkeypatch, capture):
    """A-32: latest_artifact_path returns the highest version regardless of
    approval, so regenerating an approved styleboard and re-running visual made
    Gate C validate the sheet against a world lock the operator never accepted."""
    project_id, run_dir = _approved_chain(conn, tmp_path)
    _draft_artifact(run_dir / "02b-styleboard", 2, "shorts-styleboard", "unapproved v2")
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_RESULT_OK], run_dir / "03-visual" / "raw_output.md",
                                     captured=capture))
    seen: dict = {}
    monkeypatch.setattr(turn_service.gates, "run_gates_for_stage",
                        lambda root, sid, path, upstream: seen.update(upstream) or [])

    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("visual"), CHAIN_STAGES, "go",
    ))
    assert seen["styleboard"].name == "artifact.v1.md"          # the approved one
    assert "artifact.v2.md" not in capture[0]["prompt"]


@pytest.mark.asyncio
async def test_resumed_turn_names_the_new_upstream_version(conn, tmp_path, monkeypatch, capture):
    """A-05: is_first_turn is `claude_session_id is None` and nothing ever clears
    it, so a re-run after an upstream regenerated sent only the operator's chat
    text with --resume. The transcript still named artifact.v1.md while the new
    artifact's frontmatter asserted it was built on v2."""
    project_id, run_dir = _approved_chain(conn, tmp_path)
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK],
                                     run_dir / "03-voiceover" / "raw_output.md", captured=capture))
    await _drain(turn_service.run_stage_turn(          # first turn -- records what it saw
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "brief it"))

    _final_artifact(run_dir / "02-scripting", 2, "shorts-scripting", "script v2")
    capture.clear()
    await _drain(turn_service.run_stage_turn(          # resumed turn
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "tighten the pacing"))

    prompt = capture[0]["prompt"]
    assert capture[0]["resume_session_id"] == "session-1"
    assert "UPSTREAM CHANGED" in prompt
    assert "02-scripting/artifact.v2.md" in prompt
    assert "was `02-scripting/artifact.v1.md`" in prompt
    assert "tighten the pacing" in prompt


@pytest.mark.asyncio
async def test_resumed_turn_with_unchanged_upstream_sends_only_the_message(
        conn, tmp_path, monkeypatch, capture):
    """Distinguishability: 'nothing changed' must not look like 'we failed to
    notice a change'. An unchanged chain sends the bare message, with no notice."""
    project_id, run_dir = _approved_chain(conn, tmp_path)
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK],
                                     run_dir / "03-voiceover" / "raw_output.md", captured=capture))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "brief it"))

    capture.clear()
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "tighten the pacing"))

    assert capture[0]["prompt"] == "tighten the pacing"


@pytest.mark.asyncio
async def test_upstream_change_on_a_resumed_turn_records_a_warning_event(
        conn, tmp_path, monkeypatch, capture):
    project_id, run_dir = _approved_chain(conn, tmp_path)
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK],
                                     run_dir / "03-voiceover" / "raw_output.md", captured=capture))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "brief it"))

    _final_artifact(run_dir / "02-scripting", 2, "shorts-scripting", "script v2")
    capture.clear()
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "tighten the pacing"))

    rows = conn.execute(
        "SELECT severity, detail FROM events WHERE kind = 'handoff.upstream_changed'").fetchall()
    assert len(rows) == 1 and rows[0]["severity"] == "warning"
    assert "scripting" in rows[0]["detail"]


def test_turn_service_and_gates_build_the_same_upstream_map(conn, tmp_path):
    """P3 Handoff H2: two implementations of one map is how A-30/A-62 happened.
    This asserts the CONTENTS agree, which P3's static parity test cannot see
    while turn_service still builds its own."""
    from pipeline_app import gates as gates_mod

    project_id, run_dir = _approved_chain(conn, tmp_path, with_music=True)
    stage_def = _by_id("assembly")
    assert turn_service._upstream_by_stage(tmp_path, run_dir, CHAIN_STAGES, stage_def) == \
        gates_mod.resolve_upstream_by_stage(
            run_dir, CHAIN_STAGES, stage_def,
            repo_root=tmp_path, approved_only=True, include_optional=True)


@pytest.mark.asyncio
async def test_an_unapproved_upstream_is_not_reported_as_a_missing_one(conn, tmp_path):
    """The three-state rule, on turn_service's side of the boundary.

    With approved_only=True an upstream that EXISTS but is unapproved resolves to
    an absent key -- byte-identical to "this stage was never run". P4 must not
    build a context that tells shorts-assembly "you have no styleboard" when the
    truth is "the styleboard has a draft nobody approved". Those are different
    situations for the skill, and the second is an operator action, not a gap.

    Fourth appearance of this pattern in the programme: Bluesky returned [] for
    empty and for failed; the cron returned 0 for both; the digest rendered the
    same email for both; now a resolver would return an absent key for both.
    Representing "nothing here" and "something is wrong" with one value is a
    defect by default.
    """
    project_id, run_dir = _approved_chain(conn, tmp_path)
    absent_dir = run_dir / "02b-styleboard"          # state 1: no artifact at all
    shutil.rmtree(absent_dir)
    with pytest.raises(turn_service.MissingUpstreamArtifactError) as absent:
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
            _by_id("assembly"), CHAIN_STAGES, "cut it"))

    _draft_artifact(absent_dir, 1, "shorts-styleboard", "drafted, never approved")  # state 3
    with pytest.raises(turn_service.UnapprovedUpstreamError) as unapproved:
        await _drain(turn_service.run_stage_turn(
            conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
            _by_id("assembly"), CHAIN_STAGES, "cut it"))

    assert type(absent.value) is not type(unapproved.value)
    assert "never produced an artifact" in str(absent.value)
    assert "artifact.v1.md" in str(unapproved.value) and "approve" in str(unapproved.value).lower()

    kinds = [r["kind"] for r in conn.execute(
        "SELECT kind FROM events ORDER BY id").fetchall()]
    assert kinds == ["handoff.upstream_missing", "handoff.upstream_unapproved"]


def _rgs_chain(conn, tmp_path: Path, brief: str):
    project_id = db.create_project(conn, "rgs-1", "rgs", "raisinggoodsports", "2026-08-08T00:00:00Z")
    for stage in CHAIN_STAGES:
        db.create_stage_row(conn, project_id, stage.id, StageStatus.APPROVED.value)
    run_dir = tmp_path / "runs" / "rgs-1"
    brief_path = tmp_path / brief
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    if not brief_path.exists():
        brief_path.write_text("brief content", encoding="utf-8")
    grounding_service.write_pointer(run_dir / "00-grounding", brief, tmp_path)
    script_dep = [{"path": brief, "sha256": artifacts.compute_sha256(brief_path)}]
    artifacts.stamp_final(
        artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1"),
        "2026-08-08T00:00:00Z",
    )
    artifacts.stamp_final(
        artifacts.write_artifact(run_dir / "02-scripting", 1,
                                 {"stage": "shorts-scripting", "depends_on": script_dep}, "script v1"),
        "2026-08-08T00:00:00Z",
    )
    return project_id, run_dir


@pytest.mark.asyncio
async def test_a_turn_records_the_grounding_brief_it_was_built_on(conn, tmp_path, monkeypatch, capture):
    """A-13: re-running grounding repoints rgs-briefs/ and leaves every downstream
    stage `approved` with the previous thinker/research pairing baked in. Nothing
    could detect it, because no artifact recorded which brief it used.

    Deviates from the Amendment's literal `CHAIN_STAGES`/`_by_id("scripting")` here:
    per the live `pipeline.yaml`, `scripting` always depends_on `ideation` (only
    `grounding` is brand_scope: raisinggoodsports -- A-12 keeps ideation unscoped),
    and the real `scripting.md` template unconditionally renders `inputs['ideation']`.
    CHAIN_STAGES's `scripting` StageDef has `depends_on=[]` (its downstream-chain
    tests never render this template from empty state), so driving a real kickoff
    turn through it raises a Jinja UndefinedError unrelated to this test's point.
    A local ideation+scripting StageDef pair with a real approved ideation artifact
    matches production topology instead."""
    ideation_def = StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])
    scripting_def = StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02",
                              depends_on=["ideation"])
    stage_defs = [ideation_def, scripting_def]
    project_id = db.create_project(conn, "rgs-1", "rgs", "raisinggoodsports", "2026-08-08T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", StageStatus.APPROVED.value)
    db.create_stage_row(conn, project_id, "scripting", StageStatus.READY.value)
    run_dir = tmp_path / "runs" / "rgs-1"
    _final_artifact(run_dir / "01-ideation", 1, "shorts-ideation", "concept v1")
    brief_path = tmp_path / "rgs-briefs" / "2026-08-08-a.md"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text("brief content", encoding="utf-8")
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_RESULT_OK], run_dir / "02-scripting" / "raw_output.md",
                                     captured=capture))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "rgs-1",
        scripting_def, stage_defs, "go",
        grounding_pointer="rgs-briefs/2026-08-08-a.md"))
    latest = artifacts.latest_artifact_path(run_dir / "02-scripting")
    meta, _ = artifacts.read_artifact(latest)
    assert {"path": "rgs-briefs/2026-08-08-a.md", "sha256": ANY} in meta["depends_on"]


def test_repointing_grounding_records_a_warning_event(conn, tmp_path):
    project_id, run_dir = _rgs_chain(conn, tmp_path, brief="rgs-briefs/2026-08-08-a.md")
    brief_b = tmp_path / "rgs-briefs" / "2026-08-08-b.md"
    brief_b.write_text("brief b content", encoding="utf-8")
    grounding_service.write_pointer(run_dir / "00-grounding", "rgs-briefs/2026-08-08-b.md", tmp_path)
    turn_service.propagate_grounding_staleness(conn, tmp_path, run_dir, CHAIN_STAGES, project_id)
    rows = conn.execute(
        "SELECT severity FROM events WHERE kind = 'handoff.grounding_repointed'").fetchall()
    assert rows and rows[0]["severity"] == "warning"


def test_repointing_grounding_marks_downstream_stale(conn, tmp_path):
    project_id, run_dir = _rgs_chain(conn, tmp_path, brief="rgs-briefs/2026-08-08-a.md")
    brief_b = tmp_path / "rgs-briefs" / "2026-08-08-b.md"
    brief_b.write_text("brief b content", encoding="utf-8")
    grounding_service.write_pointer(run_dir / "00-grounding", "rgs-briefs/2026-08-08-b.md", tmp_path)
    stale = turn_service.propagate_grounding_staleness(
        conn, tmp_path, run_dir, CHAIN_STAGES, project_id)
    assert "scripting" in stale
    assert db.get_stage(conn, project_id, "scripting")["status"] == StageStatus.STALE.value


def test_a_generic_project_with_no_brief_is_not_marked_stale(conn, tmp_path):
    """Distinguishability: 'this project never had a grounding brief' must not
    read the same as 'its brief was replaced'."""
    project_id, run_dir = _approved_chain(conn, tmp_path)   # generic brand, no pointer
    assert turn_service.propagate_grounding_staleness(
        conn, tmp_path, run_dir, CHAIN_STAGES, project_id) == []
    assert db.get_stage(conn, project_id, "scripting")["status"] == StageStatus.APPROVED.value


@pytest.mark.asyncio
async def test_assembly_kickoff_prompt_carries_every_input_its_skill_requires(
        conn, tmp_path, monkeypatch, capture):
    """The end-to-end proof of A-01/A-03/A-04: what the model is actually sent.

    Deviates from the brief: `_rgs_chain` writes only 00-grounding + 01-ideation
    + 02-scripting artifacts. Assembly's own depends_on in CHAIN_STAGES also
    requires styleboard/voiceover/visual, so those three approved artifacts are
    written here inline (the assembly-specific fixture data does not belong in
    the shared `_rgs_chain`, which other tests rely on staying scripting-only)."""
    project_id, run_dir = _rgs_chain(conn, tmp_path, brief="rgs-briefs/2026-08-08-a.md")
    _final_artifact(run_dir / "02b-styleboard", 1, "shorts-styleboard", "styleboard v1")
    _final_artifact(run_dir / "03-voiceover", 1, "voiceover-brief", "vo v1")
    _final_artifact(run_dir / "03-visual", 1, "visual-prompts", "vis v1")
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK],
                                     run_dir / "04-assembly" / "raw_output.md", captured=capture))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("assembly"), CHAIN_STAGES, "cut it",
        grounding_pointer="rgs-briefs/2026-08-08-a.md"))

    prompt = capture[0]["prompt"]
    assert prompt.startswith("/shorts-assembly")
    # Kickoff inputs are rendered via raw str(Path) (turn_service.run_stage_turn's
    # `inputs[up.id] = str(path)`), not the forward-slash-normalized _relpath used
    # by the resumed-turn path -- so on Windows these come out backslash-separated.
    # Deviation from the brief's literal forward-slash fragments (which only match
    # on POSIX): build each expected fragment via Path join to match the OS.
    for rel in (Path("02-scripting", "artifact.v1.md"), Path("02b-styleboard", "artifact.v1.md"),
                Path("03-voiceover", "artifact.v1.md"), Path("03-visual", "artifact.v1.md")):
        assert str(rel) in prompt, rel
    assert "rgs-briefs/2026-08-08-a.md" in prompt
    assert capture[0]["resume_session_id"] is None


@pytest.mark.asyncio
async def test_repurpose_kickoff_prompt_carries_the_script_and_packaging_direction(
        conn, tmp_path, monkeypatch, capture):
    """Deviates from the brief in the same way as the assembly test above:
    `_rgs_chain` writes ideation + scripting only, so the 04-assembly artifact
    repurpose actually depends on (per the now-widened CHAIN_STAGES entry) is
    written here inline rather than folded into the shared fixture."""
    project_id, run_dir = _rgs_chain(conn, tmp_path, brief="rgs-briefs/2026-08-08-a.md")
    _final_artifact(run_dir / "04-assembly", 1, "shorts-assembly", "asm v1")
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK],
                                     run_dir / "05-repurpose" / "raw_output.md", captured=capture))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("repurpose"), CHAIN_STAGES, "post it",
        grounding_pointer="rgs-briefs/2026-08-08-a.md"))
    prompt = capture[0]["prompt"]
    # Same OS-separator deviation as the assembly test above.
    for rel in (Path("01-ideation", "artifact.v1.md"), Path("02-scripting", "artifact.v1.md"),
                Path("04-assembly", "artifact.v1.md")):
        assert str(rel) in prompt, rel
    assert "rgs-briefs/2026-08-08-a.md" in prompt
