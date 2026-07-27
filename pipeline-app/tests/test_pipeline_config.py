from pathlib import Path

from pipeline_app.pipeline_config import load_topology, stage_dir_name

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_topology_has_seven_stages():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    assert len(stages) == 7
    ids = [s.id for s in stages]
    assert ids == [
        "grounding", "ideation", "scripting", "voiceover", "visual", "assembly", "repurpose",
    ]


def test_scripting_depends_on_ideation():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    scripting = next(s for s in stages if s.id == "scripting")
    assert scripting.depends_on == ["ideation"]
    assert scripting.skill == "shorts-scripting"


def test_voiceover_and_visual_are_a_parallel_pair():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    voiceover = next(s for s in stages if s.id == "voiceover")
    visual = next(s for s in stages if s.id == "visual")
    assert voiceover.depends_on == ["scripting"]
    assert visual.depends_on == ["scripting"]
    assert voiceover.dir_prefix == visual.dir_prefix == "03"


def test_assembly_depends_on_both_branch_stages():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    assembly = next(s for s in stages if s.id == "assembly")
    assert set(assembly.depends_on) == {"voiceover", "visual"}


def test_grounding_is_brand_scoped_to_raisinggoodsports():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    grounding = next(s for s in stages if s.id == "grounding")
    assert grounding.brand_scope == "raisinggoodsports"
    assert grounding.depends_on == []


def test_ideation_has_no_brand_scope():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    ideation = next(s for s in stages if s.id == "ideation")
    assert ideation.brand_scope is None


def test_stage_dir_name_formats_prefix_and_id():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    scripting = next(s for s in stages if s.id == "scripting")
    assert stage_dir_name(scripting) == "02-scripting"


def test_visual_stage_has_specialist_midjourney_prompting():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    visual = next(s for s in stages if s.id == "visual")
    assert visual.specialist == "midjourney-prompting"


def test_voiceover_stage_has_specialist_elevenlabs_audio():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    voiceover = next(s for s in stages if s.id == "voiceover")
    assert voiceover.specialist == "elevenlabs-audio"


def test_ideation_has_no_specialist():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    ideation = next(s for s in stages if s.id == "ideation")
    assert ideation.specialist is None
