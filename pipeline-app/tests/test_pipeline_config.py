from pathlib import Path

import pytest

from pipeline_app.pipeline_config import StageDef, build_stage_nav, load_topology, stage_dir_name

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_topology_has_nine_stages():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    assert len(stages) == 9
    ids = [s.id for s in stages]
    assert ids == [
        "grounding", "ideation", "scripting", "styleboard", "voiceover", "visual",
        "music", "assembly", "repurpose",
    ]


def test_music_stage_is_registered_with_its_specialist():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    music = next(s for s in stages if s.id == "music")
    assert music.skill == "music-brief"
    assert music.depends_on == ["scripting", "voiceover"]
    assert music.specialist == "elevenlabs-music"
    assert music.specialist_mode == "manual"
    assert music.dir_prefix == "03"


def test_music_stage_has_a_kickoff_template():
    """prompt_builder does env.get_template(f"{stage_id}.md"); a missing file is a
    TemplateNotFound raised at the stage's first turn, which is otherwise only
    discoverable at runtime."""
    assert (REPO_ROOT / "pipeline-app" / "stage_templates" / "music.md").exists()


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
    assert visual.depends_on == ["scripting", "styleboard"]
    assert voiceover.dir_prefix == visual.dir_prefix == "03"


def test_assembly_depends_on_every_artifact_its_skill_requires():
    """shorts-assembly/SKILL.md:16-29 requires the script, the voiceover brief and the
    prompt sheet, and :31-39 requires the styleboard's BINDINGS line to resolve slot
    tokens. depends_on used to carry only [voiceover, visual] (A-01/A-03)."""
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    assembly = next(s for s in stages if s.id == "assembly")
    assert set(assembly.depends_on) == {"scripting", "styleboard", "voiceover", "visual"}
    # The bed arc is a real edge but not a gate: SKILL.md calls it "genuinely
    # optional and its absence is never a blocker" (A-02).
    assert assembly.optional_depends_on == ["music"]


def test_repurpose_depends_on_the_script_and_the_packaging_direction():
    """social-repurpose/SKILL.md:12-13 needs the script text and the ideation
    packaging direction, not just the edit plan (A-01)."""
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    repurpose = next(s for s in stages if s.id == "repurpose")
    assert repurpose.depends_on == ["ideation", "scripting", "assembly"]


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


def test_voiceover_stage_specialist_mode_is_manual():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    voiceover = next(s for s in stages if s.id == "voiceover")
    assert voiceover.specialist_mode == "manual"


def test_visual_stage_specialist_mode_is_auto():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    visual = next(s for s in stages if s.id == "visual")
    assert visual.specialist_mode == "auto"


def _stage_def(id, dir_prefix, specialist=None, specialist_mode=None, depends_on=None):
    return StageDef(
        id=id, skill=f"skill-{id}", dir_prefix=dir_prefix,
        depends_on=depends_on or [], specialist=specialist, specialist_mode=specialist_mode,
    )


def test_build_stage_nav_groups_stages_sharing_dir_prefix():
    stage_defs = [
        _stage_def("ideation", "01"),
        _stage_def("scripting", "02"),
        _stage_def("voiceover", "03", specialist="elevenlabs-audio"),
        _stage_def("visual", "03", specialist="midjourney-prompting"),
        _stage_def("assembly", "04"),
    ]
    stage_rows = [
        {"stage_id": "ideation", "status": "approved"},
        {"stage_id": "scripting", "status": "approved"},
        {"stage_id": "voiceover", "status": "ready"},
        {"stage_id": "visual", "status": "ready"},
        {"stage_id": "assembly", "status": "locked"},
    ]
    nav = build_stage_nav(stage_defs, stage_rows)
    assert [len(group) for group in nav] == [1, 1, 2, 1]
    voiceover_visual_group = nav[2]
    assert {s["id"] for s in voiceover_visual_group} == {"voiceover", "visual"}


def test_build_stage_nav_carries_status_and_specialist():
    stage_defs = [_stage_def("visual", "03", specialist="midjourney-prompting", specialist_mode="auto")]
    stage_rows = [{"stage_id": "visual", "status": "awaiting_review"}]
    nav = build_stage_nav(stage_defs, stage_rows)
    assert nav == [[{
        "id": "visual", "status": "awaiting_review",
        "specialist": "midjourney-prompting", "specialist_mode": "auto",
    }]]


def test_build_stage_nav_omits_stages_with_no_matching_row():
    stage_defs = [_stage_def("grounding", "00"), _stage_def("ideation", "01")]
    stage_rows = [{"stage_id": "ideation", "status": "ready"}]
    nav = build_stage_nav(stage_defs, stage_rows)
    assert len(nav) == 1
    assert nav[0][0]["id"] == "ideation"


def test_build_stage_nav_preserves_stage_defs_order_not_dir_prefix_sort():
    stage_defs = [_stage_def("scripting", "02"), _stage_def("ideation", "01")]
    stage_rows = [
        {"stage_id": "scripting", "status": "ready"},
        {"stage_id": "ideation", "status": "approved"},
    ]
    nav = build_stage_nav(stage_defs, stage_rows)
    assert [group[0]["id"] for group in nav] == ["scripting", "ideation"]


def _write_topology(tmp_path: Path, yaml_text: str) -> Path:
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    return path


def _scaffold(root: Path, skills: tuple[str, ...] = (), templates: tuple[str, ...] = ()) -> Path:
    # Always create .claude/skills itself, even with an empty `skills` tuple --
    # otherwise a test that scaffolds zero skill dirs (to exercise the
    # missing-skill check) would instead trip the "not a ContentStudio
    # checkout" check, since that dir would never get created at all.
    (root / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
    for name in skills:
        (root / ".claude" / "skills" / name).mkdir(parents=True, exist_ok=True)
        (root / ".claude" / "skills" / name / "SKILL.md").write_text("x", encoding="utf-8")
    tdir = root / "pipeline-app" / "stage_templates"
    tdir.mkdir(parents=True, exist_ok=True)
    for name in templates:
        (tdir / f"{name}.md").write_text("/x", encoding="utf-8")
    return root


def test_load_topology_rejects_duplicate_stage_id(tmp_path: Path):
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01b\"\n    depends_on: []\n",
    )
    with pytest.raises(ValueError, match="duplicate stage id 'ideation'"):
        load_topology(path)


def test_load_topology_rejects_unknown_depends_on(tmp_path: Path):
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
        "    depends_on: [ideaton]\n",
    )
    with pytest.raises(ValueError, match="unknown stage 'ideaton'"):
        load_topology(path)


def test_load_topology_rejects_dependency_cycle(tmp_path: Path):
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: a\n    skill: x\n    dir_prefix: \"01\"\n    depends_on: [b]\n"
        "  - id: b\n    skill: x\n    dir_prefix: \"02\"\n    depends_on: [a]\n",
    )
    with pytest.raises(ValueError, match="dependency cycle"):
        load_topology(path)


def test_load_topology_accepts_valid_graph(tmp_path: Path):
    _scaffold(tmp_path, skills=("shorts-ideation", "shorts-scripting"), templates=("ideation", "scripting"))
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
        "    depends_on: [ideation]\n",
    )
    stages = load_topology(path, repo_root=tmp_path)
    assert [s.id for s in stages] == ["ideation", "scripting"]


def test_load_topology_accepts_specialist_that_has_a_skill_dir(tmp_path: Path):
    _scaffold(tmp_path, skills=("visual-prompts", "some-specialist"), templates=("visual",))
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "    specialist: some-specialist\n    specialist_mode: auto\n",
    )
    stages = load_topology(path, repo_root=tmp_path)
    assert stages[0].specialist == "some-specialist"
    assert stages[0].specialist_mode == "auto"


def test_load_topology_rejects_specialist_with_no_skill_dir(tmp_path: Path):
    _scaffold(tmp_path, skills=("visual-prompts",), templates=("visual",))
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "    specialist: ghost-specialist\n",
    )
    with pytest.raises(ValueError, match="ghost-specialist"):
        load_topology(path, repo_root=tmp_path)


def test_load_topology_rejects_specialist_with_no_specialist_mode(tmp_path: Path):
    """sidebar.html renders specialist_mode == "manual" as "(manual hand-off)"
    and anything else (including None) as "(auto-delegated)" -- the stronger,
    wrong claim. A stage that declares a specialist but no specialist_mode
    must fail loudly at load time instead of silently rendering the wrong
    claim."""
    _scaffold(tmp_path, skills=("visual-prompts", "some-specialist"), templates=("visual",))
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "    specialist: some-specialist\n",
    )
    with pytest.raises(ValueError, match="visual"):
        load_topology(path, repo_root=tmp_path)


def test_load_topology_rejects_invalid_specialist_mode_value(tmp_path: Path):
    """A typo like "Manual" (wrong case) must not silently fall through to
    sidebar.html's else-branch ("(auto-delegated)") -- it must fail loudly at
    load time instead."""
    _scaffold(tmp_path, skills=("visual-prompts", "some-specialist"), templates=("visual",))
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "    specialist: some-specialist\n    specialist_mode: Manual\n",
    )
    with pytest.raises(ValueError, match="Manual"):
        load_topology(path, repo_root=tmp_path)


def test_real_topology_has_styleboard_between_scripting_and_visual():
    repo_root = Path(__file__).resolve().parents[2]
    stages = load_topology(repo_root / "pipeline.yaml")
    by_id = {s.id: s for s in stages}

    assert "styleboard" in by_id
    assert by_id["styleboard"].depends_on == ["scripting"]
    assert by_id["styleboard"].dir_prefix == "02b"
    assert by_id["visual"].depends_on == ["scripting", "styleboard"]

    ids = [s.id for s in stages]
    assert ids.index("styleboard") < ids.index("visual")


def test_every_stage_has_a_kickoff_template():
    """render_kickoff_prompt does env.get_template(f'{stage_id}.md'); a stage with no
    template raises TemplateNotFound on its first turn, not at startup."""
    repo_root = Path(__file__).resolve().parents[2]
    stages = load_topology(repo_root / "pipeline.yaml")
    templates_dir = repo_root / "pipeline-app" / "stage_templates"
    missing = [s.id for s in stages if not (templates_dir / f"{s.id}.md").exists()]
    assert missing == []


def test_a_stage_whose_skill_directory_does_not_exist_is_rejected(tmp_path):
    """A-11: `specialist` got a hard existence check; `skill` -- the one every
    template renders as `/{{ skill }}` -- got none. A typo produced a slash
    command resolving to nothing, so the stage ran with NO skill loaded and
    answered from general knowledge: exactly what the anti-generic guarantee
    exists to prevent, with no marker in the output to detect it by."""
    _scaffold(tmp_path, skills=(), templates=("ideation",))
    path = _write_topology(tmp_path,
        'stages:\n  - id: ideation\n    skill: shorts-ideatoin\n    dir_prefix: "01"\n    depends_on: []\n')
    with pytest.raises(ValueError, match="skill 'shorts-ideatoin' has no skill at"):
        load_topology(path, repo_root=tmp_path)


def test_a_stage_with_no_kickoff_template_is_rejected_at_load_time(tmp_path):
    """A-10: the check existed only as a test. At runtime, TemplateNotFound was
    raised inside the SSE body generator -- after a 200 and event-stream headers
    were already committed, so the operator saw a broken stream, not an error."""
    _scaffold(tmp_path, skills=("shorts-ideation",), templates=())
    path = _write_topology(tmp_path,
        'stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: "01"\n    depends_on: []\n')
    with pytest.raises(ValueError, match="has no kickoff template"):
        load_topology(path, repo_root=tmp_path)


def test_an_unknown_brand_scope_is_rejected(tmp_path):
    """A-12: project_service materialises a stage row only when
    `brand_scope is None or brand_scope == brand`, so `raisingoodsports` yields a
    stage that exists in the topology, has a row on no project, vanishes from nav
    and is never runnable -- with no error anywhere."""
    _scaffold(tmp_path, skills=("shorts-ideation",), templates=("ideation",))
    path = _write_topology(tmp_path,
        'stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: "01"\n'
        '    depends_on: []\n    brand_scope: raisingoodsports\n')
    with pytest.raises(ValueError, match="brand_scope 'raisingoodsports' is not one of"):
        load_topology(path, repo_root=tmp_path)


def test_an_unscoped_stage_may_not_depend_on_a_brand_scoped_one(tmp_path):
    """A-12's worse half: stages_to_unlock requires every declared dependency
    approved, so such an edge leaves the dependent permanently `locked` on every
    out-of-scope project. migrations.py:166-170 records that exact wedge as a
    real incident."""
    _scaffold(tmp_path, skills=("shorts-ideation", "shorts-scripting"), templates=("grounding", "scripting"))
    path = _write_topology(tmp_path,
        'stages:\n'
        '  - id: grounding\n    skill: shorts-ideation\n    dir_prefix: "00"\n'
        '    depends_on: []\n    brand_scope: raisinggoodsports\n'
        '  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: "02"\n'
        '    depends_on: [grounding]\n')
    with pytest.raises(ValueError, match="would sit locked forever"):
        load_topology(path, repo_root=tmp_path)


def test_loading_a_topology_from_outside_the_repo_fails_loudly(tmp_path):
    """A-17: load_topology passed `path.parent` into a parameter named repo_root,
    so skill validation silently followed the YAML file's location."""
    path = _write_topology(tmp_path, 'stages:\n  - id: ideation\n    skill: shorts-ideation\n'
                                     '    dir_prefix: "01"\n    depends_on: []\n')
    with pytest.raises(ValueError, match="is not a ContentStudio checkout"):
        load_topology(path)                       # no scaffold -> derived root is wrong


def test_the_real_topology_loads_with_an_explicit_repo_root():
    stages = load_topology(REPO_ROOT / "pipeline.yaml", repo_root=REPO_ROOT)
    assert len(stages) == 9
