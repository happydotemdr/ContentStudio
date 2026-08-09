"""The nine-stage walk, with the Claude CLI stubbed at the cli_runner seam.

Finding F-03: the repo's only end-to-end test was opt-in, off by default, and
covered one stage. Finding F-72: nothing in the repo ever walked the chain, and
the handoff defects in Appendix A are exactly what a walk catches.

Stubbed at `cli_runner.stream_claude_turn` rather than with a fake `claude` on
PATH: on Windows `claude` resolves to an npm .cmd shim that platform_argv runs
through `cmd /c`, so a PATH stub tests cmd.exe quoting, not the pipeline. The
seam also hands the test the rendered kickoff prompt, which is the thing worth
asserting on.

Driving the walk to all nine stages needs two things a bare "call
run_stage_turn nine times" loop does not give you for free:

* Every stage but the two with no dependencies starts LOCKED
  (state_machine.compute_initial_status) and only leaves LOCKED once its
  upstream(s) are APPROVED -- awaiting_review is not enough
  (state_machine.stages_to_unlock). So each stage is approved, via the real
  approval_service, immediately after its turn and before the next stage's
  turn runs -- exactly what a human clicking through the app does. `scripting`
  and `visual` carry a registered content gate (gates.GATE_REGISTRY) that the
  stub's generic filler body cannot satisfy, so those two approvals carry an
  override_reason, the same path a human takes to approve over a failing
  gate.
* `grounding` does not use the raw_output.md -> artifact.vN.md contract every
  other stage uses. Its kickoff template never names a raw_output path,
  because its real artifact lands in rgs-briefs/ at the repo root, referenced
  by a pointer.yaml (see grounding_service.py and routes/stages.py's
  "grounding" branch of stage_chat, which calls run_stage_turn with
  finalize_artifact=False and does its own snapshot-diff-and-point
  afterwards). The walk mirrors that route logic for this one stage rather
  than forcing it through the raw_output.md path the other eight use.
"""
import re
from pathlib import Path

import pytest

from pipeline_app import approval_service, artifacts, cli_runner, db, gates, grounding_service, turn_service
from pipeline_app.pipeline_config import load_topology
from pipeline_app.project_service import create_project

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parent
TEMPLATES_DIR = APP_ROOT / "stage_templates"
RAW_OUTPUT_RE = re.compile(r"([A-Za-z]:[^\s`'\"]+raw_output\.md)")


@pytest.fixture
def stub_cli(monkeypatch):
    """Replace the CLI turn with one that writes the artifact the real skill
    would write, and record every prompt it was handed."""
    prompts: list[str] = []

    async def fake_stream(prompt, repo_root, resume_id, settings_path=None):
        prompts.append(prompt)
        match = RAW_OUTPUT_RE.search(prompt)
        if match:
            raw = Path(match.group(1))
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text(
                "# Stubbed stage output\n\n"
                "Body written by the stubbed CLI so the next stage has an upstream "
                "artifact to consume.\n",
                encoding="utf-8",
            )
        else:
            # grounding.md is the one kickoff template with no raw_output_path --
            # its real output lands in rgs-briefs/ instead (see module docstring).
            briefs_dir = Path(repo_root) / "rgs-briefs"
            briefs_dir.mkdir(parents=True, exist_ok=True)
            (briefs_dir / f"stub-brief-{len(prompts)}.md").write_text(
                "# Stubbed grounding brief\n\nBody written by the stubbed CLI.\n",
                encoding="utf-8",
            )
        yield {"type": "system", "subtype": "init", "session_id": f"stub-{len(prompts)}"}
        yield {"type": "result", "subtype": "success", "result": "ok", "total_cost_usd": 0.0}

    monkeypatch.setattr(cli_runner, "stream_claude_turn", fake_stream)
    monkeypatch.setattr(cli_runner, "scoped_permissions_settings", lambda: None)
    return prompts


@pytest.mark.asyncio
async def test_all_nine_stages_run_and_each_receives_its_declared_upstreams(tmp_path, conn, stub_cli):
    stage_defs = load_topology(REPO_ROOT / "pipeline.yaml")
    assert len(stage_defs) == 9, "pipeline.yaml no longer declares nine stages"

    project = create_project(conn, tmp_path, "stubbed-walk", "raisinggoodsports", stage_defs)
    run_dir = project["run_dir"]
    artifact_by_stage: dict[str, Path] = {}

    for stage in stage_defs:
        is_grounding = stage.id == "grounding"
        rgs_briefs_dir = tmp_path / "rgs-briefs"
        briefs_before = grounding_service.snapshot_rgs_briefs(rgs_briefs_dir) if is_grounding else None

        before = len(stub_cli)
        async for _ in turn_service.run_stage_turn(
            conn, tmp_path, run_dir, TEMPLATES_DIR,
            project["project_id"], project["run_id"], stage, stage_defs,
            f"produce the {stage.id} artifact",
            finalize_artifact=not is_grounding,
        ):
            pass
        prompt = stub_cli[before]

        for upstream_id in stage.depends_on:
            upstream_path = artifact_by_stage.get(upstream_id)
            assert upstream_path is not None, (
                f"{stage.id} declares depends_on={upstream_id} but that stage "
                "produced no artifact"
            )
            assert str(upstream_path) in prompt, (
                f"{stage.id}'s kickoff prompt does not contain its declared "
                f"upstream artifact {upstream_path} -- the handoff is broken"
            )

        stage_dir = run_dir / turn_service.stage_dir_name(stage)
        if is_grounding:
            # Mirrors routes/stages.py's "grounding" branch of stage_chat: the
            # turn above ran with finalize_artifact=False, so nothing in
            # run_dir was written for it -- identify the new rgs-briefs/ file
            # and point at it exactly as that route does.
            briefs_after = grounding_service.snapshot_rgs_briefs(rgs_briefs_dir)
            new_brief = grounding_service.identify_new_brief(briefs_before, briefs_after)
            assert new_brief is not None, "grounding produced no new rgs-briefs/ file"
            grounding_service.write_pointer(stage_dir, f"rgs-briefs/{new_brief}")
            stage_row = db.get_stage(conn, project["project_id"], "grounding")
            db.update_stage_status(conn, stage_row["id"], "awaiting_review")
            latest = artifacts.resolve_latest_artifact(tmp_path, "grounding", stage_dir)
        else:
            latest = artifacts.latest_artifact_path(stage_dir)
        assert latest is not None, f"{stage.id} produced no artifact"
        artifact_by_stage[stage.id] = latest

        # Approve now so any stage depending on this one leaves LOCKED before
        # its own turn runs later in this loop (see module docstring).
        override_reason = (
            "stubbed CLI output does not satisfy this stage's content gate -- "
            "bypassing for the walk"
            if gates.GATE_REGISTRY.get(stage.id) else None
        )
        approval_service.approve_stage(
            conn, tmp_path, run_dir, project["project_id"], stage_defs, stage.id,
            override_reason=override_reason,
        )

    assert set(artifact_by_stage) == {s.id for s in stage_defs}


@pytest.mark.asyncio
async def test_the_walk_writes_nothing_outside_tmp_path(tmp_path, conn, stub_cli):
    """The old integration test created <repo>/runs/... in the working tree
    and never cleaned it up (F-72)."""
    before = {p.name for p in (REPO_ROOT / "runs").iterdir()} if (REPO_ROOT / "runs").exists() else set()
    stage_defs = load_topology(REPO_ROOT / "pipeline.yaml")
    project = create_project(conn, tmp_path, "isolation-check", "generic", stage_defs)
    # "ideation" rather than stage_defs[0] ("grounding"): grounding is scoped
    # to brand "raisinggoodsports" (see pipeline.yaml), so a "generic" project
    # never gets a grounding stage row at all -- this test only needs one
    # ordinary, always-present, dependency-free stage to prove the isolation
    # property, and grounding also needs the finalize_artifact=False dance
    # from the test above, which is irrelevant noise here.
    ideation_stage = next(s for s in stage_defs if s.id == "ideation")
    async for _ in turn_service.run_stage_turn(
        conn, tmp_path, project["run_dir"], TEMPLATES_DIR,
        project["project_id"], project["run_id"], ideation_stage, stage_defs,
        "anything",
    ):
        pass
    after = {p.name for p in (REPO_ROOT / "runs").iterdir()} if (REPO_ROOT / "runs").exists() else set()
    assert before == after
