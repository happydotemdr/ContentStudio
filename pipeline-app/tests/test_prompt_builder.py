from pathlib import Path

from pipeline_app.prompt_builder import render_kickoff_prompt

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "stage_templates"


def test_ideation_template_starts_with_skill_slash_command():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "a Short about travel-sport burnout",
        "grounding_pointer": None,
        "input_file": None,
        "raw_output_path": "runs/x/01-ideation/raw_output.md",
    })
    assert prompt.strip().startswith("/shorts-ideation")
    assert "travel-sport burnout" in prompt


def test_ideation_template_omits_grounding_block_when_none():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "idea",
        "grounding_pointer": None,
        "input_file": None,
        "raw_output_path": "out.md",
    })
    assert "companion grounding artifact" not in prompt


def test_ideation_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
        "skill": "shorts-ideation",
        "user_message": "idea",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "input_file": None,
        "raw_output_path": "out.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt


def test_scripting_template_references_input_file():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "scripting", {
        "skill": "shorts-scripting",
        "user_message": "",
        "grounding_pointer": None,
        "input_file": "runs/x/01-ideation/artifact.v1.md",
        "raw_output_path": "runs/x/02-scripting/raw_output.md",
    })
    assert "runs/x/01-ideation/artifact.v1.md" in prompt


def test_visual_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "visual", {
        "skill": "visual-prompts",
        "user_message": "",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "raw_output_path": "runs/x/03-visual/raw_output.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt


def test_visual_template_deliverable_names_i2v_and_cover_not_just_stills():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "visual", {
        "skill": "visual-prompts",
        "user_message": "",
        "grounding_pointer": None,
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "raw_output_path": "runs/x/03-visual/raw_output.md",
    })
    assert "i2v" in prompt.lower()
    assert "cover" in prompt.lower()


def test_voiceover_template_omits_grounding_block_when_none():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "voiceover", {
        "skill": "voiceover-brief",
        "user_message": "",
        "grounding_pointer": None,
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "raw_output_path": "runs/x/03-voiceover/raw_output.md",
    })
    assert "companion grounding artifact" not in prompt


def test_voiceover_template_includes_grounding_block_when_present():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "voiceover", {
        "skill": "voiceover-brief",
        "user_message": "",
        "grounding_pointer": "rgs-briefs/2026-07-25-idea.md",
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "raw_output_path": "runs/x/03-voiceover/raw_output.md",
    })
    assert "rgs-briefs/2026-07-25-idea.md" in prompt


def test_grounding_template_has_no_input_file_reference():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "grounding", {
        "skill": "rgs-grounding",
        "user_message": "a Short about travel-sport burnout",
        "grounding_pointer": None,
        "input_file": None,
        "input_files": [],
        "raw_output_path": None,
    })
    assert prompt.strip().startswith("/rgs-grounding")


def test_assembly_template_lists_both_upstream_inputs_not_the_script():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "assembly", {
        "skill": "shorts-assembly",
        "user_message": "",
        "grounding_pointer": None,
        "input_file": "runs/x/03-voiceover/artifact.v1.md",
        "input_files": [
            "runs/x/03-voiceover/artifact.v1.md",
            "runs/x/03-visual/artifact.v1.md",
        ],
        "raw_output_path": "runs/x/04-assembly/raw_output.md",
    })
    assert "runs/x/03-voiceover/artifact.v1.md" in prompt
    assert "runs/x/03-visual/artifact.v1.md" in prompt
    assert "the script" not in prompt.lower()
