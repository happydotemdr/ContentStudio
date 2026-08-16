from pathlib import Path

import pytest

from pipeline_app.prompt_builder import render_kickoff_prompt

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "stage_templates"


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
