from pathlib import Path

import jinja2
import pytest
from jinja2 import nodes

from pipeline_app.pipeline_config import load_topology
from pipeline_app.prompt_builder import KICKOFF_CONTEXT_KEYS, render_kickoff_prompt

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "stage_templates"

# parents[2] from pipeline-app/tests/test_prompt_builder.py is the repo root,
# where pipeline.yaml lives. load_topology takes only a path -- repo_root is
# derived internally from path.parent, which is already REPO_ROOT here, so no
# separate repo_root argument exists to pass.
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STAGES = load_topology(REPO_ROOT / "pipeline.yaml")


def _ast(stage_id: str) -> nodes.Template:
    source = (TEMPLATES_DIR / f"{stage_id}.md").read_text(encoding="utf-8")
    return jinja2.Environment().parse(source)


def _names(ast) -> set[str]:
    return {n.name for n in ast.find_all(nodes.Name)}


def _subscripted_stage_ids(ast) -> set[str]:
    """Stage ids the template addresses by name: inputs['x'] or inputs.x."""
    found = set()
    for node in ast.find_all(nodes.Getitem):
        if isinstance(node.node, nodes.Name) and node.node.name == "inputs" \
                and isinstance(node.arg, nodes.Const):
            found.add(node.arg.value)
    for node in ast.find_all(nodes.Getattr):
        if isinstance(node.node, nodes.Name) and node.node.name == "inputs":
            found.add(node.attr)
    return found


def _membership_tested_stage_ids(ast) -> set[str]:
    """Stage ids guarded by `{% if 'x' in inputs %}` -- the optional-edge idiom."""
    found = set()
    for node in ast.find_all(nodes.Compare):
        for op in node.ops:
            if op.op == "in" and isinstance(op.expr, nodes.Name) \
                    and op.expr.name == "inputs" and isinstance(node.expr, nodes.Const):
                found.add(node.expr.value)
    return found


@pytest.mark.parametrize("stage", REAL_STAGES, ids=lambda s: s.id)
def test_every_input_a_kickoff_template_names_is_reachable_via_depends_on(stage):
    """THE conformance test. turn_service builds `inputs` from depends_on +
    optional_depends_on and nothing else, so a template naming any other stage id
    is asking for an artifact the graph can never deliver -- the A-01/A-03 defect,
    which shipped for two stages while both templates asserted the input was
    present. Data-driven over all nine stages so it cannot come back."""
    ast = _ast(stage.id)
    declared, optional = set(stage.depends_on), set(stage.optional_depends_on)

    unreachable = _subscripted_stage_ids(ast) - (declared | optional)
    assert unreachable == set(), (
        f"{stage.id}.md interpolates inputs{sorted(unreachable)} but "
        f"pipeline.yaml declares depends_on={sorted(declared)} "
        f"optional_depends_on={sorted(optional)}"
    )

    # The reverse direction: a declared dependency the template never mentions is
    # an artifact the operator pays a stage for and the model is never shown.
    never_shown = declared - _subscripted_stage_ids(ast)
    assert never_shown == set(), f"{stage.id}.md never names required input(s) {sorted(never_shown)}"

    # An id guarded by `'x' in inputs` must be optional; a required input is
    # always present, and guarding it hides a missing-artifact bug.
    assert _membership_tested_stage_ids(ast) <= optional

    # A-08's static half: no template may reference a name outside the frozen
    # five-key context. Jinja's default Undefined would render it as "".
    assert _names(ast) <= (KICKOFF_CONTEXT_KEYS | {"stage_id", "path"}), (
        f"{stage.id}.md references {sorted(_names(ast) - KICKOFF_CONTEXT_KEYS)}"
    )


@pytest.mark.parametrize("stage", REAL_STAGES, ids=lambda s: s.id)
def test_every_kickoff_template_renders_under_strict_undefined(stage):
    """Static reachability is not enough -- prove the exact dict turn_service
    builds actually renders. Under StrictUndefined a stray name raises here
    instead of silently vanishing at the operator's next turn."""
    context = {
        "skill": stage.skill,
        "user_message": "operator text",
        "grounding_pointer": "rgs-briefs/2026-08-08-sample.md",
        "inputs": {sid: f"runs/SAMPLE/{sid}/artifact.v1.md" for sid in stage.depends_on},
        "raw_output_path": "runs/SAMPLE/raw_output.md",
    }
    rendered = render_kickoff_prompt(TEMPLATES_DIR, stage.id, context)
    assert rendered.strip().startswith(f"/{stage.skill}")
    for sid in stage.depends_on:
        assert f"runs/SAMPLE/{sid}/artifact.v1.md" in rendered


def test_ideation_template_starts_with_skill_slash_command():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "a Short about travel-sport burnout",
        "grounding_pointer": None,
        "inputs": {},
        "raw_output_path": "runs/x/01-ideation/raw_output.md",
    })
    assert prompt.strip().startswith("/shorts-ideation")
    assert "travel-sport burnout" in prompt


def test_ideation_template_omits_grounding_block_when_none():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "idea",
        "grounding_pointer": None,
        "inputs": {},
        "raw_output_path": "out.md",
    })
    assert "companion grounding artifact" not in prompt


def test_ideation_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "idea",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "inputs": {},
        "raw_output_path": "out.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt


def test_scripting_template_references_input_file():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "scripting", {
        "skill": "shorts-scripting",
        "user_message": "",
        "grounding_pointer": None,
        "inputs": {"ideation": "runs/x/01-ideation/artifact.v1.md"},
        "raw_output_path": "runs/x/02-scripting/raw_output.md",
    })
    assert "runs/x/01-ideation/artifact.v1.md" in prompt


def test_voiceover_template_omits_grounding_block_when_none():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "voiceover", {
        "skill": "voiceover-brief",
        "user_message": "",
        "grounding_pointer": None,
        "inputs": {"scripting": "runs/x/02-scripting/artifact.v1.md"},
        "raw_output_path": "runs/x/03-voiceover/raw_output.md",
    })
    assert "companion grounding artifact" not in prompt


def test_voiceover_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "voiceover", {
        "skill": "voiceover-brief",
        "user_message": "",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "inputs": {"scripting": "runs/x/02-scripting/artifact.v1.md"},
        "raw_output_path": "runs/x/03-voiceover/raw_output.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt


def test_visual_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "visual", {
        "skill": "visual-prompts",
        "user_message": "",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "inputs": {
            "scripting": "runs/x/02-scripting/artifact.v1.md",
            "styleboard": "runs/x/02b-styleboard/artifact.v1.md",
        },
        "raw_output_path": "runs/x/03-visual/raw_output.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt


def test_visual_template_deliverable_names_i2v_and_cover_not_just_stills():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "visual", {
        "skill": "visual-prompts",
        "user_message": "",
        "grounding_pointer": None,
        "inputs": {
            "scripting": "runs/x/02-scripting/artifact.v1.md",
            "styleboard": "runs/x/02b-styleboard/artifact.v1.md",
        },
        "raw_output_path": "runs/x/03-visual/raw_output.md",
    })
    assert "i2v" in prompt.lower()
    assert "cover" in prompt.lower()


def test_grounding_template_has_no_input_file_reference():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "grounding", {
        "skill": "rgs-grounding",
        "user_message": "a Short about travel-sport burnout",
        "grounding_pointer": None,
        "inputs": {},
        "raw_output_path": None,
    })
    assert prompt.strip().startswith("/rgs-grounding")


def test_music_template_lists_script_and_voiceover_inputs():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "music", {
        "skill": "music-brief",
        "user_message": "",
        "grounding_pointer": None,
        "inputs": {
            "scripting": "runs/x/02-scripting/artifact.v1.md",
            "voiceover": "runs/x/03-voiceover/artifact.v1.md",
        },
        "raw_output_path": "runs/x/03-music/raw_output.md",
    })
    assert prompt.strip().startswith("/music-brief")
    assert "runs/x/02-scripting/artifact.v1.md" in prompt
    assert "runs/x/03-voiceover/artifact.v1.md" in prompt
    assert "runs/x/03-music/raw_output.md" in prompt


ASSEMBLY_INPUTS = {
    "scripting": "runs/x/02-scripting/artifact.v1.md",
    "styleboard": "runs/x/02b-styleboard/artifact.v1.md",
    "voiceover": "runs/x/03-voiceover/artifact.v1.md",
    "visual": "runs/x/03-visual/artifact.v1.md",
}


def _ctx(skill, inputs, grounding_pointer=None, user_message="", raw="out.md"):
    return {
        "skill": skill, "user_message": user_message,
        "grounding_pointer": grounding_pointer, "inputs": inputs, "raw_output_path": raw,
    }


def test_assembly_template_names_the_script_and_the_styleboard():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "assembly", _ctx("shorts-assembly", ASSEMBLY_INPUTS))
    assert "runs/x/02-scripting/artifact.v1.md" in prompt
    assert "runs/x/02b-styleboard/artifact.v1.md" in prompt
    # A-16: each path carries its stage label, so the model never has to infer
    # which bullet is the styleboard from the directory name.
    assert "script: `runs/x/02-scripting/artifact.v1.md`" in prompt
    assert "styleboard" in prompt and "BINDINGS" in prompt


def test_assembly_template_says_the_bed_is_absent_rather_than_omitting_it():
    """A-02 distinguishability: 'no music stage was run' must read differently
    from 'the bed arc simply wasn't listed'."""
    without = render_kickoff_prompt(TEMPLATES_DIR, "assembly", _ctx("shorts-assembly", ASSEMBLY_INPUTS))
    with_bed = render_kickoff_prompt(
        TEMPLATES_DIR, "assembly",
        _ctx("shorts-assembly", {**ASSEMBLY_INPUTS, "music": "runs/x/03-music/artifact.v1.md"}),
    )
    assert "No music bed brief" in without
    assert "runs/x/03-music/artifact.v1.md" in with_bed
    assert with_bed != without


def test_repurpose_template_names_three_inputs_not_one_path_called_two_documents():
    """repurpose.md:3 used to say 'the script and edit plan at `<one path>`' (A-01)."""
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "repurpose", _ctx("social-repurpose", {
        "ideation": "runs/x/01-ideation/artifact.v1.md",
        "scripting": "runs/x/02-scripting/artifact.v1.md",
        "assembly": "runs/x/04-assembly/artifact.v1.md",
    }))
    for path in ("01-ideation", "02-scripting", "04-assembly"):
        assert path in prompt


@pytest.mark.parametrize("stage_id,skill,inputs", [
    ("assembly", "shorts-assembly", ASSEMBLY_INPUTS),
    ("repurpose", "social-repurpose", {
        "ideation": "i.md", "scripting": "s.md", "assembly": "a.md"}),
])
def test_grounding_pointer_reaches_the_last_two_stages(stage_id, skill, inputs):
    """A-04: the app computes and passes a pointer for every non-grounding stage
    on an RGS project; assembly.md and repurpose.md referenced no such variable,
    so it was discarded with no warning."""
    with_ptr = render_kickoff_prompt(
        TEMPLATES_DIR, stage_id, _ctx(skill, inputs, grounding_pointer="rgs-briefs/2026-08-08-x.md"))
    without = render_kickoff_prompt(TEMPLATES_DIR, stage_id, _ctx(skill, inputs))
    assert "rgs-briefs/2026-08-08-x.md" in with_ptr
    assert "companion grounding artifact" not in without
    assert with_ptr != without
