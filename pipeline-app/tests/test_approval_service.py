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

    grounding_row = db.get_stage(conn, project_id, "grounding")
    assert grounding_row["status"] == StageStatus.APPROVED.value


def test_approve_stage_grounding_does_not_mutate_brief_content(conn, tmp_path: Path):
    """approval_service must never rewrite rgs-briefs/*.md -- that file's
    frontmatter belongs to the rgs-grounding/rgs-pairing-review skills, and
    approval state already lives in the stages DB row."""
    project_id = db.create_project(conn, "rgs-1", "rgs", "raisinggoodsports", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "grounding", "awaiting_review")
    run_dir = tmp_path / "runs" / "rgs-1"
    grounding_dir = run_dir / "00-grounding"
    rgs_briefs_dir = tmp_path / "rgs-briefs"
    rgs_briefs_dir.mkdir(parents=True)
    brief_path = rgs_briefs_dir / "2026-07-27-example-brief.md"
    original_text = "---\nstatus: candidate\nresearch_codes: [R3]\n---\n\nBrief body"
    brief_path.write_text(original_text, encoding="utf-8")
    write_pointer(grounding_dir, "rgs-briefs/2026-07-27-example-brief.md")

    approve_stage(conn, tmp_path, run_dir, project_id, GROUNDING_STAGES, "grounding")

    assert brief_path.read_text(encoding="utf-8") == original_text
    grounding_row = db.get_stage(conn, project_id, "grounding")
    assert grounding_row["status"] == StageStatus.APPROVED.value
    assert grounding_row["approved_at"] is not None


def test_approve_raises_when_no_artifact_exists(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "ready")
    run_dir = tmp_path / "runs" / "abc-1"
    (run_dir / "01-ideation").mkdir(parents=True)
    with pytest.raises(ValueError):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")


def test_approve_raises_when_stage_is_locked(conn, tmp_path: Path):
    """The locked/running invariant must be enforced by the service itself,
    not only by the route -- a caller that skips the route must still be
    protected."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", StageStatus.LOCKED.value)
    run_dir = tmp_path / "runs" / "abc-1"
    with pytest.raises(ValueError, match="locked"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")


def test_approve_raises_when_stage_is_running(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", StageStatus.RUNNING.value)
    run_dir = tmp_path / "runs" / "abc-1"
    with pytest.raises(ValueError, match="running"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")


def test_approve_stage_grounding_pointer_target_missing_returns_valueerror_not_crash(conn, tmp_path: Path):
    project_id = db.create_project(conn, "rgs-1", "rgs", "raisinggoodsports", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "grounding", "awaiting_review")
    run_dir = tmp_path / "runs" / "rgs-1"
    grounding_dir = run_dir / "00-grounding"
    write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")

    with pytest.raises(ValueError, match="No artifact to approve"):
        approve_stage(conn, tmp_path, run_dir, project_id, GROUNDING_STAGES, "grounding")


def test_reapproving_an_approved_stage_does_not_churn_hash_or_cascade_staleness(conn, tmp_path: Path):
    """Re-approving an already-approved stage must be a no-op on disk:
    stamp_final rewriting finalized_at every time changes the artifact's
    sha256 even when nothing substantive changed, which would spuriously
    flip an approved dependent stale the next time propagate_staleness runs
    a hash check that includes this stage."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "awaiting_review")
    db.create_stage_row(conn, project_id, "scripting", "locked")

    run_dir = tmp_path / "runs" / "abc-1"
    ideation_dir = run_dir / "01-ideation"
    artifacts.write_artifact(ideation_dir, 1, {"status": "draft", "stage": "shorts-ideation"}, "body")

    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")
    ideation_v1 = ideation_dir / "artifact.v1.md"
    hash_after_first_approval = artifacts.compute_sha256(ideation_v1)

    scripting_dir = run_dir / "02-scripting"
    artifacts.write_artifact(
        scripting_dir, 1,
        {
            "stage": "shorts-scripting",
            "depends_on": [
                {"path": "01-ideation/artifact.v1.md", "sha256": hash_after_first_approval}
            ],
        },
        "script body",
    )
    scripting_row_id = db.get_stage(conn, project_id, "scripting")["id"]
    db.update_stage_status(conn, scripting_row_id, StageStatus.APPROVED.value)

    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")  # re-approve; nothing changed

    assert artifacts.compute_sha256(ideation_v1) == hash_after_first_approval

    turn_service.propagate_staleness(conn, run_dir, STAGES, project_id, "ideation")
    scripting_row = db.get_stage(conn, project_id, "scripting")
    assert scripting_row["status"] == StageStatus.APPROVED.value


def test_reapproving_a_stale_stage_does_not_churn_hash(conn, tmp_path: Path):
    """A stale stage (approved, then flipped stale by the cascade) can be
    re-approved directly to override the cascade -- stage.html's new note
    (Item 4) makes this the encouraged path for a stale stage, not an edge
    case. That artifact is already stamped final; re-approving it must be
    just as much a no-op on disk as re-approving a still-approved stage."""
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "awaiting_review")

    run_dir = tmp_path / "runs" / "abc-1"
    ideation_dir = run_dir / "01-ideation"
    artifacts.write_artifact(ideation_dir, 1, {"status": "draft", "stage": "shorts-ideation"}, "body")

    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")
    ideation_v1 = ideation_dir / "artifact.v1.md"
    hash_after_first_approval = artifacts.compute_sha256(ideation_v1)

    stage_row_id = db.get_stage(conn, project_id, "ideation")["id"]
    db.update_stage_status(conn, stage_row_id, StageStatus.STALE.value)

    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")

    assert artifacts.compute_sha256(ideation_v1) == hash_after_first_approval


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
    # The fake turn's body ("script body") is not real script-language-gate
    # input, so gate_d_script_language errors on it (no VO lines to parse) --
    # exactly the fail-closed behavior Task 9 requires. This test is about
    # staleness propagation, not gate content, so it overrides the block
    # rather than fabricating a gate-passing script body.
    approve_stage(
        conn, tmp_path, run_dir, project_id, STAGES, "scripting",
        override_reason="test fixture body is not real script-language-gate input",
    )

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


def _seed_scripting_awaiting_review(conn, tmp_path: Path) -> tuple[int, Path, Path]:
    project_id = db.create_project(conn, "gate-1", "gate", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    db.create_stage_row(conn, project_id, "scripting", "awaiting_review")
    run_dir = tmp_path / "runs" / "gate-1"
    stage_dir = run_dir / "02-scripting"
    stage_dir.mkdir(parents=True, exist_ok=True)
    return project_id, run_dir, stage_dir


def _write_artifact_with_gates(stage_dir: Path, status: str) -> Path:
    meta = {
        "schema_version": 1, "run_id": "r1", "stage": "shorts-scripting", "version": 1,
        "status": "draft", "created_at": "2026-08-06T00:00:00+00:00", "finalized_at": None,
        "supersedes": None, "depends_on": [],
        "gates": [{
            "name": "gate_d_script_language", "status": status,
            "findings": [{"check": "D1", "beat": "HOOK", "message": "em-dash", "kind": "fail"}],
        }],
    }
    return artifacts.write_artifact(stage_dir, 1, meta, "body")


def test_approve_raises_on_a_failing_gate_without_an_override(conn, tmp_path):
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "fail")
    with pytest.raises(ValueError, match="gate"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")


def test_approve_raises_on_an_errored_gate_without_an_override(conn, tmp_path):
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "error")
    with pytest.raises(ValueError, match="gate"):
        approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")


def test_approve_succeeds_with_an_override_and_records_the_reason(conn, tmp_path):
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    path = _write_artifact_with_gates(stage_dir, "fail")
    approve_stage(
        conn, tmp_path, run_dir, project_id, STAGES, "scripting",
        override_reason="dash is inside a verbatim 1886 quote",
    )
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["gate_override_reason"] == "dash is inside a verbatim 1886 quote"
    assert meta["gates"][0]["status"] == "fail"  # the record is not rewritten


def test_approve_succeeds_normally_on_a_passing_gate(conn, tmp_path):
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    _write_artifact_with_gates(stage_dir, "pass")
    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")
    assert db.get_stage(conn, project_id, "scripting")["status"] == StageStatus.APPROVED.value


def test_override_on_already_final_artifact_records_reason_without_rewriting_gates(conn, tmp_path):
    """Finding 3: re-approving an artifact that is ALREADY stamped final (the
    stale-stage re-approve path stage.html encourages) must still record a
    supplied override reason. approve_stage skips stamp_final entirely on
    this path to avoid churning finalized_at/sha256 on a no-op re-approve --
    but that must not silently drop a real override reason supplied on THIS
    call. The gates entry and finalized_at must stay untouched: an override
    says a human accepted the finding, not that the finding was rewritten
    away or that anything else changed."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    path = _write_artifact_with_gates(stage_dir, "fail")
    meta, body = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    meta["status"] = "final"
    meta["finalized_at"] = "2026-08-01T00:00:00+00:00"
    path.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")

    approve_stage(
        conn, tmp_path, run_dir, project_id, STAGES, "scripting",
        override_reason="re-approving a stale stage; dash is inside a verbatim quote",
    )

    meta_after, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta_after["gate_override_reason"] == (
        "re-approving a stale stage; dash is inside a verbatim quote"
    )
    assert meta_after["finalized_at"] == "2026-08-01T00:00:00+00:00"  # untouched, no churn
    assert meta_after["status"] == "final"
    assert meta_after["gates"][0]["status"] == "fail"  # the record is not rewritten


def test_reapproving_an_already_final_artifact_with_blank_override_does_not_record_one(conn, tmp_path):
    """The companion case to the test above: an already-final artifact
    re-approved with NO override reason (None, same as a blank form field
    after the route's .strip() or None) must not gain a
    gate_override_reason key at all -- record_gate_override must only be
    called when a reason is actually supplied."""
    project_id, run_dir, stage_dir = _seed_scripting_awaiting_review(conn, tmp_path)
    path = _write_artifact_with_gates(stage_dir, "pass")
    meta, body = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    meta["status"] = "final"
    meta["finalized_at"] = "2026-08-01T00:00:00+00:00"
    path.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")

    approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "scripting")

    meta_after, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert "gate_override_reason" not in meta_after
    assert meta_after["finalized_at"] == "2026-08-01T00:00:00+00:00"
