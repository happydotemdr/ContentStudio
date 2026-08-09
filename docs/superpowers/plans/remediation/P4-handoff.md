# P4 — Handoff

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. The orchestration plan's
> **Global Constraints**, **test standard** and **Frozen interfaces**
> ([`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md)) apply to every task
> here and are not restated.

**The question this package answers:** *are the skill handoffs correct?* For seven of nine stages,
yes. For `assembly` and `repurpose`, no — and the failure ships silently, because the kickoff
templates tell the skill an input is present that the graph cannot deliver.

**The verdict: the graph is wrong, not the skills.** `shorts-assembly/SKILL.md:16-29` and
`social-repurpose/SKILL.md:12-13` declare inputs that are real craft requirements traced to the
corpus. `pipeline.yaml` under-declares them. This package fixes `pipeline.yaml` and the templates;
the SKILL.md prose that must follow is handed to P13 as a contract (§6), not edited here.

---

## 1. Scope

**Files owned by this package (no other package may touch these):**

- `pipeline.yaml` (REPO ROOT)
- `pipeline-app/pipeline_app/turn_service.py`
- `pipeline-app/pipeline_app/prompt_builder.py`
- `pipeline-app/pipeline_app/pipeline_config.py`
- `pipeline-app/pipeline_app/cli_runner.py`
- `pipeline-app/stage_templates/*.md` (all 9: `grounding.md`, `ideation.md`, `scripting.md`,
  `styleboard.md`, `voiceover.md`, `visual.md`, `music.md`, `assembly.md`, `repurpose.md`)
- `pipeline-app/tests/test_turn_service.py`
- `pipeline-app/tests/test_cli_runner.py`
- `pipeline-app/tests/test_prompt_builder.py`
- `pipeline-app/tests/test_pipeline_config.py`
- `pipeline-app/tests/test_routes_chat_sse.py`

**Finding IDs (26):** A-01, A-02, A-03, A-04, A-05, A-06, A-07, A-08, A-09, A-10, A-11, A-12,
A-13, A-14, A-15, A-16, A-17, A-32, A-44, A-46, D-43, D-44, D-45, D-46, F-11, F-15.

**Suite:** `cd pipeline-app && python -m pytest` (app rootdir). Never from the repo root.

### Frozen for this package: the kickoff context contract

Five keys, and only five. `input_file` and `input_files` are **deleted** — they are the mechanism
behind A-07, A-09 and A-16.

```python
{
  "skill":             str,              # the /slash-command the template opens with
  "user_message":      str,              # the operator's chat text
  "grounding_pointer": str | None,       # repo-relative rgs-briefs/ path, or None
  "inputs":            dict[str, str],   # stage_id -> absolute artifact path
  "raw_output_path":   str,
}
```

Templates address upstreams **by stage id** (`{{ inputs['scripting'] }}`), never by position. That
single change is what makes the §3 Task 3 conformance test possible.

---

## 2. Finding → task map

Total coverage: 26 findings, 26 rows.

| Finding | Sev | Mode | Task | What the task does |
|---|---|---|---|---|
| A-01 | S1 | silent | **T2** | `scripting` added to `assembly`+`repurpose` deps; both templates name it (graph half in T1) |
| A-02 | S2 | silent | **T1** | `optional_depends_on: [music]` on `assembly`; folded into `inputs` and into staleness (T10) |
| A-03 | S2 | silent | **T1** | `styleboard` added to `assembly.depends_on` |
| A-04 | S1 | silent | **T2** | `{% if grounding_pointer %}` block added to `assembly.md` and `repurpose.md` |
| A-05 | S1 | silent | **T7** | resumed turn is told, in the prompt, which upstream paths changed |
| A-06 | S2 | loud | **T8** | an unresumable session id is cleared so the next turn re-renders the kickoff |
| A-07 | S3 | silent | **T5** | a required dep with no approved artifact refuses the turn instead of rendering `None` |
| A-08 | S2 | silent | **T4** | `StrictUndefined` + context-key allowlist + `validate_template_source` |
| A-09 | S3 | latent | **T2** | `input_file`/`input_files[0]` deleted; templates key by stage id |
| A-10 | S2 | loud | **T13** | `_validate_topology` requires a kickoff template per stage |
| A-11 | S2 | silent | **T13** | `skill` gets the same `.claude/skills/<name>/SKILL.md` check as `specialist` |
| A-12 | S3 | latent | **T13** | `brand_scope` validated against `KNOWN_BRAND_SCOPES`; scope-incompatible edges rejected |
| A-13 | S2 | silent | **T11** | grounding brief recorded in each downstream artifact's `depends_on`; pointer-repoint sweep |
| A-14 | S3 | latent | **T10** | pointer-aware resolution in `_current_upstream_hashes` and upstream collection |
| A-15 | S4 | loud | **T12** | `run_stage_turn` raises `StageNotRunnableError` on a `None` stage row |
| A-16 | S4 | latent | **T2** | every input renders as an explicit `<stage label>: <path>` pair |
| A-17 | S4 | docs-drift | **T13** | `load_topology(path, repo_root=None)`; derived root is verified, not assumed |
| A-32 | S2 | silent | **T6** | upstream inputs and gate inputs resolve to the **approved** artifact |
| A-44 | S1 | silent | **T10** | `propagate_staleness` marks `awaiting_review` drafts stale, not just `approved` rows |
| A-46 | S2 | silent | **T9** | abort restores the pre-`running` status instead of re-deriving it |
| D-43 | S2 | silent | **T14** | one `WRITE_*_PATTERNS` policy; `permissions.deny`; function renamed, docstring corrected |
| D-44 | S2 | latent | **T14** | `--allowedTools` narrowed from bare `Write,Edit` to pattern-scoped forms |
| D-45 | S1 | silent | **T14** | `scripts/**` denied — closes the "turn rewrites the linter the app exec's" path |
| D-46 | S1 | silent | **T15** | `.claude/**` denied; vendor `*_API_KEY` stripped from the child environment |
| F-11 | S1 | silent | **T14** | tautological test **deleted** (`test_cli_runner.py:458-467`), replaced by `permits_write` table |
| F-15 | S1 | coverage-gap | **T16** | test doubles capture the prompt; per-stage assertions on what the handoff actually emits |

**Four tasks carry no P4 finding of their own** and are sequenced last so the finding work is never
blocked on another package's merge:

| Task | Origin | What it is |
|---|---|---|
| **T17** | P3 Handoff H2 | Swap P4's inline upstream map for `gates.resolve_upstream_by_stage`. Carries a **counter-contract back to P3** (three keywords) without which the swap reintroduces A-32, A-02 and A-14. |
| **T18** | P2 §6.1–§6.3 | Adopt the durable `artifacts.py` API. Includes P2's named highest-value wrap at `turn_service.py:74`. |
| **T19** | P1, F-26 second half | `test_turn_service.py:335-343` — the gate-result test that asserts its own mock. P1 closed the `test_main.py` half. |
| **T20** | P5 contract | `stage_id_by_skill`, `stage_template_path`, and the duplicate-`skill:` rejection rule. |

---

## 3. Tasks

Each task: write the failing test → run it → **see it fail for the right reason** → implement →
see it pass → commit. Every snippet below is real code, not a sketch.

---

### T1 — Declare the missing edges (A-02, A-03; graph half of A-01)

- [ ] **Test first.** In `pipeline-app/tests/test_pipeline_config.py`, replace
      `test_assembly_depends_on_both_branch_stages` (line 53-56) with:

```python
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
```

- [ ] **Run:** `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -k "assembly_depends_on_every or repurpose_depends_on_the_script" -q`
      → fails: `TypeError: StageDef.__init__() got an unexpected keyword` is *not* what we want yet;
      expect `AttributeError: 'StageDef' object has no attribute 'optional_depends_on'` and
      `AssertionError: {'voiceover','visual'} != {...}`.
- [ ] **Implement**, `pipeline-app/pipeline_app/pipeline_config.py`:

```python
@dataclass
class StageDef:
    id: str
    skill: str
    dir_prefix: str
    depends_on: list[str] = field(default_factory=list)
    # An edge that supplies an input but does NOT gate unlocking. state_machine.
    # stages_to_unlock reads `depends_on` only, so an optional upstream never
    # locks its dependent -- which is exactly what shorts-assembly/SKILL.md:26-29
    # asks for ("genuinely optional and its absence is never a blocker") and why
    # modelling music as a hard edge would have been wrong (A-02).
    optional_depends_on: list[str] = field(default_factory=list)
    brand_scope: str | None = None
    specialist: str | None = None
    specialist_mode: str | None = None

    @property
    def all_depends_on(self) -> list[str]:
        return [*self.depends_on, *self.optional_depends_on]
```

and in `load_topology`'s comprehension:

```python
            optional_depends_on=list(s.get("optional_depends_on", [])),
```

and in `_validate_topology`'s unknown-dependency loop, iterate `stage.all_depends_on` rather than
`stage.depends_on`.

- [ ] **Implement**, `pipeline.yaml` — the only two stanzas that change:

```yaml
  - id: assembly
    skill: shorts-assembly
    dir_prefix: "04"
    depends_on: [scripting, styleboard, voiceover, visual]
    optional_depends_on: [music]
  - id: repurpose
    skill: social-repurpose
    dir_prefix: "05"
    depends_on: [ideation, scripting, assembly]
```

- [ ] **Run** the two tests → pass. Run the whole `test_pipeline_config.py` → expect
      `test_load_topology_has_nine_stages` still green (order unchanged).
- [ ] **Commit:** `fix(pipeline): declare the script, styleboard and bed-arc edges assembly and repurpose actually need`

---

### T2 — Address upstreams by stage id (A-01 template half, A-04, A-09, A-16)

- [ ] **Test first.** Rewrite `pipeline-app/tests/test_prompt_builder.py`'s two multi-input tests.
      **Delete** `test_assembly_template_lists_both_upstream_inputs_not_the_script`
      (`test_prompt_builder.py:128-142`) — its name asserts the defect (see §5) — and add:

```python
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
```

Also update the seven single-input tests in that file from `"input_file": "..."` to
`"inputs": {"<upstream id>": "..."}` and add the now-required `"inputs"` key everywhere.

- [ ] **Run:** `cd pipeline-app && python -m pytest tests/test_prompt_builder.py -q` → fails:
      `jinja2.exceptions.UndefinedError` is not yet raised (StrictUndefined lands in T4), so expect
      plain `AssertionError` — the assembly prompt contains neither the script path nor a bed line.
- [ ] **Implement.** Rewrite the templates. Full new bodies for the four that change materially:

`pipeline-app/stage_templates/assembly.md`:

```jinja
/{{ skill }}

Read these upstream artifacts and produce the assembly/edit plan:
- script (beat timing, Delivery notes): `{{ inputs['scripting'] }}`
- styleboard — its BINDINGS line resolves every `{style:...}` / `{char:...}` slot in the
  prompt sheet against `docs/style-library.md`: `{{ inputs['styleboard'] }}`
- voiceover brief: `{{ inputs['voiceover'] }}`
- visual prompt sheet: `{{ inputs['visual'] }}`
{% if 'music' in inputs %}
- music bed brief: `{{ inputs['music'] }}` — use its bed arc, hook hold-out and asset
  filename in the loudness/mix section.
{% else %}
No music bed brief exists for this Short. Carry the rights-note checkpoint unchanged — an
absent bed is a legitimate outcome, not a blocker.
{% endif %}
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}`. If it carries a
"constraints that survive to publish" line, honor it in the caption/overlay treatment and
restate it verbatim in this edit plan's own notes.
{% endif %}
{{ user_message }}

Write your final edit plan to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
```

`pipeline-app/stage_templates/repurpose.md`:

```jinja
/{{ skill }}

Read these and produce the multi-surface post copy:
- script (hook language, AEO specifics): `{{ inputs['scripting'] }}`
- packaging direction (working title / angle): `{{ inputs['ideation'] }}`
- edit plan: `{{ inputs['assembly'] }}`
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}`. If it carries a
"constraints that survive to publish" line, honor it verbatim in the post copy.
{% endif %}
{{ user_message }}

Write your final post copy to `{{ raw_output_path }}` (overwrite it completely each time you
produce a new draft).
```

`pipeline-app/stage_templates/visual.md` — replace lines 6-10 (the anonymous `{% for %}` and the
"among those inputs" sentence) with:

```jinja
- script: `{{ inputs['scripting'] }}`
- styleboard — owns the WORLD LOCK and the slot declarations: `{{ inputs['styleboard'] }}`

Inherit the WORLD LOCK; do not re-emit it into your sheet, and write every style reference as a
`{style:...}` slot rather than a literal `--sref` code.
```

`pipeline-app/stage_templates/music.md` — replace lines 4-6 with:

```jinja
- script (beat timings): `{{ inputs['scripting'] }}`
- voiceover brief — its tone-per-beat call is what the tone-contradiction check runs
  against: `{{ inputs['voiceover'] }}`
```

`scripting.md:3` → `` Read the concept brief at `{{ inputs['ideation'] }}` ``;
`styleboard.md:3` and `voiceover.md:3` → `` `{{ inputs['scripting'] }}` ``.
`grounding.md` and `ideation.md` are unchanged (no inputs).

- [ ] **Implement**, `turn_service.py` — the context dict at `:148-155` becomes:

```python
        prompt = prompt_builder.render_kickoff_prompt(templates_dir, stage_def.id, {
            "skill": stage_def.skill,
            "user_message": user_message,
            "grounding_pointer": grounding_pointer,
            "inputs": inputs,
            "raw_output_path": str(raw_output_path),
        })
```

(`inputs` is built in T5; for this task build it inline as
`{up.id: str(p) for up, p in ...}` from the existing `upstream_by_stage` and delete the
`input_file`/`input_files` lines.)

- [ ] **Run** `tests/test_prompt_builder.py` → pass. `tests/test_turn_service.py` will now fail on
      the scripting-gate test; that is expected and fixed in T5/T16.
- [ ] **Commit:** `fix(handoff): address kickoff inputs by stage id instead of by position`

---

### T3 — The conformance test: every interpolated input is reachable (guards A-01, A-03, A-04, A-08, A-09, A-16 forever)

This is the highest-value test in the package. It is data-driven over all nine stages, so the
whole class of defect cannot be reintroduced.

- [ ] **Test first.** New block at the top of `pipeline-app/tests/test_prompt_builder.py`:

```python
import jinja2
from jinja2 import nodes

from pipeline_app.pipeline_config import load_topology
from pipeline_app.prompt_builder import KICKOFF_CONTEXT_KEYS

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_STAGES = load_topology(REPO_ROOT / "pipeline.yaml", repo_root=REPO_ROOT)


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
```

- [ ] **Run:** `cd pipeline-app && python -m pytest tests/test_prompt_builder.py -k conformance -q`
      — before T1/T2 landed it fails on `assembly`/`repurpose` with
      `assembly.md interpolates inputs['scripting','styleboard']...`. Verify by temporarily
      reverting `pipeline.yaml`'s `assembly.depends_on` to `[voiceover, visual]` and confirming
      the test goes red, then restoring it. **Do not skip this check** — it is the proof the test
      would have caught the shipped defect.
- [ ] **Implement:** nothing. T1 and T2 already satisfy it. Add
      `KICKOFF_CONTEXT_KEYS` to `prompt_builder.py` (T4) if not yet present.
- [ ] **Commit:** `test(handoff): assert every interpolated input is reachable, for all 9 stages`

---

### T4 — StrictUndefined and a validated context (A-08)

- [ ] **Test first**, `pipeline-app/tests/test_prompt_builder.py`:

```python
def test_a_typo_in_a_template_raises_instead_of_rendering_empty(tmp_path):
    """Kickoff templates are operator-editable through the skill editor and
    written straight to disk. Jinja's default Undefined made `{{ raw_output_path_ }}`
    render as "" -- the stage then finished with no artifact and no explanation."""
    (tmp_path / "typo.md").write_text(
        "/{{ skill }}\n\nWrite to `{{ raw_output_path_ }}`.\n", encoding="utf-8")
    with pytest.raises(jinja2.UndefinedError):
        render_kickoff_prompt(tmp_path, "typo", {
            "skill": "x", "user_message": "", "grounding_pointer": None,
            "inputs": {}, "raw_output_path": "out.md",
        })


def test_render_rejects_a_context_missing_a_frozen_key():
    with pytest.raises(ValueError, match=r"missing \['inputs'\]"):
        render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
            "skill": "shorts-ideation", "user_message": "", "grounding_pointer": None,
            "raw_output_path": "out.md",
        })


def test_render_rejects_an_unknown_context_key():
    with pytest.raises(ValueError, match=r"unknown keys \['input_file'\]"):
        render_kickoff_prompt(TEMPLATES_DIR, "ideation", {
            "skill": "shorts-ideation", "user_message": "", "grounding_pointer": None,
            "inputs": {}, "raw_output_path": "out.md", "input_file": "legacy",
        })


def test_validate_template_source_rejects_a_bad_name_before_it_is_saved():
    stage = next(s for s in REAL_STAGES if s.id == "scripting")
    with pytest.raises(jinja2.UndefinedError):
        prompt_builder.validate_template_source("{{ inputs['nope'] }}", prompt_builder.sample_context(stage))
    prompt_builder.validate_template_source(
        "{{ inputs['ideation'] }}", prompt_builder.sample_context(stage))  # does not raise
```

- [ ] **Run** → fails: no exception; the typo renders as empty string.
- [ ] **Implement**, `pipeline-app/pipeline_app/prompt_builder.py` (whole file):

```python
from pathlib import Path

import jinja2

# The complete kickoff context. Frozen: turn_service supplies exactly these and
# render_kickoff_prompt refuses anything else, so a template can never quietly
# consume a name nobody passes (A-08) and a supplied-but-unreferenced key can
# never be discarded in silence the way grounding_pointer was (A-04).
KICKOFF_CONTEXT_KEYS = frozenset(
    {"skill", "user_message", "grounding_pointer", "inputs", "raw_output_path"}
)


def _environment(templates_dir: Path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        # StrictUndefined, not the default: an operator-edited template that
        # misspells a variable must raise at render time rather than emit a
        # kickoff prompt with the write instruction silently missing.
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_kickoff_prompt(templates_dir: Path, stage_id: str, context: dict) -> str:
    supplied = set(context)
    missing = sorted(KICKOFF_CONTEXT_KEYS - supplied)
    if missing:
        raise ValueError(f"kickoff context for '{stage_id}' is missing {missing}")
    unknown = sorted(supplied - KICKOFF_CONTEXT_KEYS)
    if unknown:
        raise ValueError(f"kickoff context for '{stage_id}' has unknown keys {unknown}")
    env = _environment(templates_dir)
    return env.get_template(f"{stage_id}.md").render(**context)


def sample_context(stage_def, raw_output_path: str = "runs/SAMPLE/raw_output.md") -> dict:
    """A dummy context shaped exactly like the real one, for trial-rendering an
    edited template before it reaches disk."""
    return {
        "skill": stage_def.skill,
        "user_message": "SAMPLE",
        "grounding_pointer": "rgs-briefs/SAMPLE.md",
        "inputs": {sid: f"runs/SAMPLE/{sid}/artifact.v1.md" for sid in stage_def.all_depends_on},
        "raw_output_path": raw_output_path,
    }


def validate_template_source(source: str, context: dict) -> None:
    """Trial-render an edited template. Raises TemplateSyntaxError or
    UndefinedError; returns None on success. Callers that write templates to
    disk should call this first."""
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True
    )
    env.from_string(source).render(**context)
```

- [ ] **Run** → pass, and re-run T3's conformance tests (StrictUndefined is what makes the second
      half meaningful).
- [ ] **Commit:** `fix(prompt-builder): fail loudly on an undefined or unknown template variable`

---

### T5 — A required dependency with no artifact refuses the turn (A-07)

- [ ] **Test first**, `pipeline-app/tests/test_turn_service.py`:

```python
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
    ...  # same setup as the fault test
    with pytest.raises(turn_service.MissingUpstreamArtifactError):
        await _drain(...)
    rows = conn.execute(
        "SELECT kind, severity, message FROM events WHERE kind = 'handoff.upstream_missing'"
    ).fetchall()
    assert len(rows) == 1 and rows[0]["severity"] == "error"
    assert "ideation" in rows[0]["message"]
```

- [ ] **Run** → fails: no such exception class; the turn proceeds and renders `None`.
- [ ] **Implement**, `turn_service.py`. Add near the other exceptions:

```python
class MissingUpstreamArtifactError(StageNotRunnableError):
    """A declared, required dependency resolved to no artifact on disk. Refusing
    is the point: rendering a prompt that names a nonexistent path (or the
    literal string "None") makes the model invent its way around the gap."""
```

and, in `run_stage_turn`, move upstream resolution **above** `create_turn` (a raise must not leave
a `running` turn row behind) and replace `:133-143` with:

```python
    required_defs = [s for s in all_stage_defs if s.id in stage_def.depends_on]
    optional_defs = [s for s in all_stage_defs if s.id in stage_def.optional_depends_on]

    # Keyed by stage id, not a list: templates address upstreams by name
    # (prompt_builder.KICKOFF_CONTEXT_KEYS), so positional drift when an
    # upstream drops out is structurally impossible (A-09/A-16).
    inputs: dict[str, str] = {}
    missing: list[str] = []
    for up in required_defs:
        path = _resolve_upstream(repo_root, run_dir, up)
        if path is None:
            missing.append(up.id)
        else:
            inputs[up.id] = str(path)
    if missing:
        obs.record_event(
            conn, kind="handoff.upstream_missing", severity="error", source="turn_service",
            message=(f"stage '{stage_def.id}' cannot start: no approved artifact for "
                     f"{', '.join(missing)}"),
            detail={"stage": stage_def.id, "missing": missing},
        )
        raise MissingUpstreamArtifactError(
            f"Stage '{stage_def.id}' requires {missing} but no approved artifact exists for "
            "them. Approve or regenerate the upstream stage first."
        )
    for up in optional_defs:
        path = _resolve_upstream(repo_root, run_dir, up)
        if path is None:
            obs.log("handoff.optional_upstream_absent", level="info",
                    stage=stage_def.id, upstream=up.id)
        else:
            inputs[up.id] = str(path)
    upstream_paths = [Path(p) for p in inputs.values()]
    upstream_by_stage = {sid: Path(p) for sid, p in inputs.items()}
```

Add `from pipeline_app import obs` to the imports.

- [ ] **Run** → pass. Also update `test_scripting_turn_records_gate_results_in_frontmatter`
      (`test_turn_service.py:312`) to write an **approved** ideation artifact first — it currently
      relies on the missing-upstream hole.
- [ ] **Commit:** `fix(handoff): refuse a turn whose required upstream artifact is missing`

---

### T6 — Resolve upstreams to the approved artifact, not the newest draft (A-32)

- [ ] **Test first**, `test_turn_service.py`:

```python
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


def test_approved_artifact_path_distinguishes_no_artifact_from_only_drafts(tmp_path):
    """Distinguishability: a stage with three unapproved drafts is not the same
    as a stage with nothing -- but both must resolve to None, and the caller
    (T5) must say which stage it was."""
    empty, drafts = tmp_path / "a", tmp_path / "b"
    empty.mkdir(); drafts.mkdir()
    _draft_artifact(drafts, 1, "x", "d1"); _draft_artifact(drafts, 2, "x", "d2")
    assert turn_service._approved_artifact_path(empty) is None
    assert turn_service._approved_artifact_path(drafts) is None
    _final_artifact(drafts, 3, "x", "approved")
    assert turn_service._approved_artifact_path(drafts).name == "artifact.v3.md"
```

- [ ] **Run** → fails: `seen["styleboard"].name == 'artifact.v2.md'`.
- [ ] **Implement**, `turn_service.py`:

```python
_VERSION_RE = re.compile(r"^artifact\.v(\d+)\.md$")


def _approved_artifact_path(stage_dir: Path) -> Path | None:
    """The newest artifact a human actually approved -- approval_service.
    stamp_final writes `status: final` into the frontmatter -- not merely the
    newest file on disk. A gate keyed to an unapproved draft records a pass
    against a world the operator never accepted (A-32)."""
    versions = []
    for path in stage_dir.glob("artifact.v*.md"):
        match = _VERSION_RE.match(path.name)
        if match:
            versions.append((int(match.group(1)), path))
    for _version, path in sorted(versions, reverse=True):
        meta, _body = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("status") == "final":
            return path
    return None


def _resolve_upstream(repo_root: Path, run_dir: Path, up: StageDef) -> Path | None:
    """The artifact an upstream stage hands downstream. Grounding's real output
    lives in rgs-briefs/ behind a pointer, so it needs the pointer-aware
    resolver (A-14); every other stage hands down its approved version."""
    stage_dir = run_dir / stage_dir_name(up)
    if up.id == "grounding":
        return artifacts.resolve_latest_artifact(repo_root, up.id, stage_dir)
    return _approved_artifact_path(stage_dir)
```

Add `import re`.

> **Deliberate divergence:** `_current_upstream_hashes` keeps using
> `artifacts.latest_artifact_path`. Its docstring explains why — staleness must notice a
> *regenerate*, and an approved-only view would never see one. Inputs resolve to approved;
> staleness compares against latest. Recording the approved path in `depends_on` therefore means an
> unapproved upstream draft marks its dependents stale. That is the intended A-32 + A-44 semantics:
> the cue clears when the draft is approved or discarded.

- [ ] **Run** → pass. **Commit:** `fix(handoff): hand downstream the approved upstream artifact, not the newest draft`

---

### T7 — A resumed turn is told what changed upstream (A-05)

- [ ] **Test first**, `test_turn_service.py`:

```python
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
async def test_resumed_turn_with_unchanged_upstream_sends_only_the_message(...):
    """Distinguishability: 'nothing changed' must not look like 'we failed to
    notice a change'. An unchanged chain sends the bare message, with no notice."""
    ...
    assert capture[0]["prompt"] == "tighten the pacing"


@pytest.mark.asyncio
async def test_upstream_change_on_a_resumed_turn_records_a_warning_event(...):
    rows = conn.execute(
        "SELECT severity, detail FROM events WHERE kind = 'handoff.upstream_changed'").fetchall()
    assert len(rows) == 1 and rows[0]["severity"] == "warning"
    assert "scripting" in rows[0]["detail"]
```

- [ ] **Run** → fails: `capture[0]["prompt"] == "tighten the pacing"` on the second turn.
- [ ] **Implement**, `turn_service.py`:

```python
def _session_inputs_path(stage_dir: Path) -> Path:
    return stage_dir / "session_inputs.json"


def _write_session_inputs(stage_dir: Path, run_dir: Path, inputs: dict[str, str]) -> None:
    """What the CLI session for this stage has actually been shown. Kept beside
    the events log rather than in the DB so no schema change is needed."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {sid: _relpath(Path(p), run_dir) for sid, p in inputs.items()}
    _session_inputs_path(stage_dir).write_text(
        json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")


def _read_session_inputs(stage_dir: Path) -> dict[str, str]:
    path = _session_inputs_path(stage_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        obs.log("handoff.session_inputs_unreadable", level="warning", path=str(path))
        return {}
    return data if isinstance(data, dict) else {}


def _resumed_prompt(conn, stage_dir: Path, run_dir: Path, stage_def: StageDef,
                    inputs: dict[str, str], user_message: str) -> str:
    """A resumed session's transcript still names the artifact versions it was
    opened on. If any upstream has since been superseded, say so in the prompt --
    otherwise the model answers from the old paths while the artifact it writes
    records the new ones as its provenance (A-05)."""
    seen = _read_session_inputs(stage_dir)
    current = {sid: _relpath(Path(p), run_dir) for sid, p in inputs.items()}
    if seen == current:
        return user_message
    changed = sorted(sid for sid in current if seen.get(sid) != current[sid])
    dropped = sorted(sid for sid in seen if sid not in current)
    lines = ["UPSTREAM CHANGED SINCE THIS SESSION LAST READ IT."]
    lines += [f"- {sid}: now `{inputs[sid]}` (was `{seen.get(sid, 'absent')}`)" for sid in changed]
    lines += [f"- {sid}: no longer available (was `{seen[sid]}`)" for sid in dropped]
    lines.append("Re-read every path above before answering; do not rely on the earlier version.")
    obs.record_event(
        conn, kind="handoff.upstream_changed", severity="warning", source="turn_service",
        message=f"stage '{stage_def.id}' resumed against changed upstream(s): {changed + dropped}",
        detail={"stage": stage_def.id, "changed": changed, "dropped": dropped,
                "seen": seen, "current": current},
    )
    _write_session_inputs(stage_dir, run_dir, inputs)
    return "\n".join(lines) + "\n\n" + user_message
```

and the branch at `:146-159`:

```python
    if is_first_turn:
        prompt = prompt_builder.render_kickoff_prompt(templates_dir, stage_def.id, {...})
        resume_id = None
        _write_session_inputs(stage_dir, run_dir, inputs)
    else:
        prompt = _resumed_prompt(conn, stage_dir, run_dir, stage_def, inputs, user_message)
        resume_id = stage_row["claude_session_id"]
```

- [ ] **Run** → pass. **Commit:** `fix(handoff): tell a resumed session which upstream artifacts changed`

---

### T8 — Clear an unresumable session id (A-06)

- [ ] **Test first**, `test_turn_service.py`:

```python
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
    await _drain(...)
    assert db.get_stage(conn, project["project_id"], "ideation")["claude_session_id"] == "session-1"
```

- [ ] **Run** → fails: the id survives in both cases.
- [ ] **Implement**, `turn_service.py`, after `result = cli_runner.extract_turn_result(collected)`:

```python
def _resume_failed(events: list[dict]) -> bool:
    """The CLI never opened the resumed session: no system/init carrying a
    session id, and the turn ended in error. Both halves matter -- an error on a
    session that DID open is an ordinary failed turn, not a dead id."""
    opened = any(
        e.get("type") == "system" and e.get("subtype") == "init" and e.get("session_id")
        for e in events
    )
    errored = (not events) or any(e.get("type") == "result" and e.get("is_error") for e in events)
    return not opened and errored
```

```python
    if resume_id is not None and _resume_failed(collected):
        db_mod.update_stage_session(conn, stage_row["id"], None)
        obs.record_event(
            conn, kind="handoff.session_unresumable", severity="warning", source="turn_service",
            message=(f"stage '{stage_def.id}' session {resume_id} could not be resumed; cleared "
                     "so the next turn re-renders the kickoff prompt"),
            detail={"stage": stage_def.id, "session_id": resume_id},
        )
    elif result.session_id:
        db_mod.update_stage_session(conn, stage_row["id"], result.session_id)
```

- [ ] **Run** → pass. **Commit:** `fix(handoff): clear a dead session id instead of wedging the stage forever`

---

### T9 — An aborted turn restores the status it interrupted (A-46)

- [ ] **Test first**, `test_turn_service.py`:

```python
@pytest.mark.asyncio
async def test_aborting_a_turn_on_a_stale_stage_leaves_it_stale(conn, tmp_path, monkeypatch):
    """A-46: a stale stage always has an artifact, so the abort recovery's
    `latest is not None` branch always resolved to awaiting_review -- opening
    chat on a stale stage and closing the tab erased the only cue that the
    artifact was built on a since-changed input."""
    project_id, run_dir = _approved_chain(conn, tmp_path,
                                          statuses={"voiceover": StageStatus.STALE.value})
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK]))
    agen = turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("voiceover"), CHAIN_STAGES, "redo")
    await agen.__anext__()
    await agen.aclose()
    assert db.get_stage(conn, project_id, "voiceover")["status"] == StageStatus.STALE.value


@pytest.mark.asyncio
async def test_aborting_a_turn_on_an_approved_stage_leaves_it_approved(...):
    """Distinguishability: `approved -> running -> abort` laundered into
    awaiting_review too. Restoring the prior status must be exact, not a guess
    keyed to artifact existence."""
    assert db.get_stage(conn, project_id, "voiceover")["status"] == StageStatus.APPROVED.value
```

- [ ] **Run** → fails: both land at `awaiting_review`.
- [ ] **Implement**, `turn_service.py`. Capture before flipping to RUNNING:

```python
    prior_status = stage_row["status"]
```

and in the `except BaseException:` block, replace the `resolve_latest_artifact` derivation
(`:200-204`) with:

```python
        # Restore exactly what the turn interrupted. Re-deriving the status from
        # artifact existence (the old rule) always produced AWAITING_REVIEW for a
        # stage that had any artifact, which laundered `stale` -- and
        # `approved` -- into `awaiting_review` on nothing more than an aborted
        # turn, erasing the stage-page warning permanently (A-46).
        db_mod.update_stage_status(conn, stage_row["id"], prior_status)
```

- [ ] **Run** → pass; `test_disconnected_turn_is_marked_aborted_not_left_running`
      (`test_turn_service.py:137`) still passes (its stage starts READY).
- [ ] **Commit:** `fix(handoff): restore the pre-running status when a turn aborts`

---

### T10 — Staleness sees drafts, optional edges and pointers (A-44, A-14, A-02 half)

- [ ] **Test first**, `test_turn_service.py`. **Invert**
      `test_propagate_staleness_cascade_stops_at_a_non_approved_stage`
      (`test_turn_service.py:294-308`) — see §5 — and add:

```python
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


def test_staleness_hashing_without_a_repo_root_says_so_for_a_pointer_backed_upstream(conn, tmp_path, caplog):
    """A-14: latest_artifact_path cannot see grounding's pointer indirection, so
    a depends_on edge onto grounding would silently drop it from BOTH input
    collection and staleness hashing. It must warn, not shrug."""
    ...
    assert any(r.kind == "staleness.pointer_upstream_unresolvable" for r in obs_records)
```

- [ ] **Run** → the inverted test fails (assembly stays `awaiting_review`), the music test fails
      (assembly stays `approved`).
- [ ] **Implement**, `turn_service.py`:

```python
_INVALIDATABLE = (StageStatus.APPROVED.value, StageStatus.AWAITING_REVIEW.value)
```

In `_dependents_of`, follow optional edges too:

```python
def _dependents_of(all_stage_defs: list[StageDef], stage_id: str) -> list[StageDef]:
    return [s for s in all_stage_defs if stage_id in s.all_depends_on]
```

In both loops of `propagate_staleness`, replace
`row["status"] != StageStatus.APPROVED.value` with `row["status"] not in _INVALIDATABLE`.

In `propagate_staleness`, build `dep_upstream_defs` from `dep_stage.all_depends_on`, and thread a
pointer-aware root through:

```python
def propagate_staleness(
    conn: sqlite3.Connection,
    run_dir: Path,
    all_stage_defs: list[StageDef],
    project_id: int,
    changed_stage_id: str,
    repo_root: Path | None = None,
) -> None:
```

```python
def _current_upstream_hashes(
    run_dir: Path, upstream_defs: list[StageDef], repo_root: Path | None = None
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for up in upstream_defs:
        up_dir = run_dir / stage_dir_name(up)
        if up.id == "grounding":
            if repo_root is None:
                # Never silent: without a root the pointer cannot be followed, so
                # this upstream would simply vanish from the hash set and its
                # dependents would look permanently fresh (A-14).
                obs.log("staleness.pointer_upstream_unresolvable", level="warning",
                        upstream=up.id, run_dir=str(run_dir))
                continue
            up_latest = artifacts.resolve_latest_artifact(repo_root, up.id, up_dir)
        else:
            up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            hashes[_relpath(up_latest, run_dir)] = artifacts.compute_sha256(up_latest)
    return hashes
```

`run_stage_turn`'s call at `:256` becomes
`propagate_staleness(conn, run_dir, all_stage_defs, project_id, stage_def.id, repo_root=repo_root)`.

- [ ] **Run** → pass. **Commit:** `fix(staleness): invalidate unapproved drafts and follow optional and pointer edges`

---

### T11 — Grounding re-runs invalidate what was built on the old brief (A-13)

- [ ] **Test first**, `test_turn_service.py`:

```python
@pytest.mark.asyncio
async def test_a_turn_records_the_grounding_brief_it_was_built_on(conn, tmp_path, monkeypatch):
    """A-13: re-running grounding repoints rgs-briefs/ and leaves every downstream
    stage `approved` with the previous thinker/research pairing baked in. Nothing
    could detect it, because no artifact recorded which brief it used."""
    ...
    meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
    assert {"path": "rgs-briefs/2026-08-08-a.md", "sha256": ANY} in meta["depends_on"]


def test_repointing_grounding_marks_downstream_stale(conn, tmp_path):
    project_id, run_dir = _rgs_chain(conn, tmp_path, brief="rgs-briefs/2026-08-08-a.md")
    grounding_service.write_pointer(run_dir / "00-grounding", "rgs-briefs/2026-08-08-b.md")
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


def test_repointing_grounding_records_a_warning_event(conn, tmp_path):
    rows = conn.execute(
        "SELECT severity FROM events WHERE kind = 'handoff.grounding_repointed'").fetchall()
    assert rows and rows[0]["severity"] == "warning"
```

- [ ] **Run** → fails: no `propagate_grounding_staleness`; `depends_on` carries no brief.
- [ ] **Implement**, `turn_service.py`. In the `depends_on` construction at `:234-237`:

```python
    depends_on = [
        {"path": _relpath(p, run_dir), "sha256": artifacts.compute_sha256(p)}
        for p in upstream_paths
    ]
    # The grounding brief is a real input that arrives out-of-band (routes.stages
    # resolves the pointer and passes it as grounding_pointer), so it never
    # appears in upstream_paths. Recording it here is what lets a re-pointed
    # brief be detected at all -- modelling grounding as a depends_on edge is
    # forbidden by the brand-scope rule (A-12), since ideation is unscoped.
    if grounding_pointer:
        brief = repo_root / grounding_pointer
        if brief.exists():
            depends_on.append({"path": grounding_pointer,
                               "sha256": artifacts.compute_sha256(brief)})
        else:
            obs.record_event(
                conn, kind="handoff.grounding_brief_missing", severity="error",
                source="turn_service",
                message=f"stage '{stage_def.id}' was passed grounding pointer "
                        f"'{grounding_pointer}' but no such file exists",
                detail={"stage": stage_def.id, "pointer": grounding_pointer},
            )
```

and add the public sweep, called from `run_stage_turn` immediately after `propagate_staleness`:

```python
def propagate_grounding_staleness(
    conn: sqlite3.Connection, repo_root: Path, run_dir: Path,
    all_stage_defs: list[StageDef], project_id: int,
) -> list[str]:
    """Grounding's artifact lives in rgs-briefs/ behind a pointer and no stage
    lists it in depends_on, so the hash cascade cannot see it. Any stage whose
    artifact recorded a brief path that is no longer the pointer target was built
    on a superseded thinker/research pairing (A-13). Public because the grounding
    turn route is what repoints the pointer and should call it there too."""
    current = grounding_service.read_pointer(run_dir / "00-grounding")
    if current is None:
        return []
    stale: list[str] = []
    for stage_def in all_stage_defs:
        if stage_def.id == "grounding":
            continue
        row = db_mod.get_stage(conn, project_id, stage_def.id)
        if row is None or row["status"] not in _INVALIDATABLE:
            continue
        latest = artifacts.latest_artifact_path(run_dir / stage_dir_name(stage_def))
        if latest is None:
            continue
        meta, _body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
        briefs = [d.get("path") for d in (meta.get("depends_on") or [])
                  if str(d.get("path", "")).startswith("rgs-briefs/")]
        if briefs and current not in briefs:
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)
            stale.append(stage_def.id)
    if stale:
        obs.record_event(
            conn, kind="handoff.grounding_repointed", severity="warning", source="turn_service",
            message=f"grounding brief is now {current!r}; marked stale: {', '.join(stale)}",
            detail={"pointer": current, "stale": stale},
        )
    return stale
```

Add `from pipeline_app import grounding_service` to the imports.

- [ ] **Run** → pass. **Commit:** `fix(grounding): record the brief each artifact was built on and invalidate on a repoint`

---

### T12 — Guard the `None` stage row (A-15)

- [ ] **Test first**, `test_turn_service.py`:

```python
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
```

- [ ] **Run** → fails with `TypeError: 'NoneType' object is not subscriptable`.
- [ ] **Implement**, `turn_service.py`, immediately after `stage_row = db_mod.get_stage(...)`:

```python
    if stage_row is None:
        raise StageNotRunnableError(
            f"Project {project_id} has no row for stage '{stage_def.id}' — it is out of the "
            "project's brand scope, or the project predates the stage (see migrations.py)."
        )
```

- [ ] **Run** → pass. **Commit:** `fix(handoff): raise StageNotRunnableError instead of dereferencing a missing stage row`

---

### T13 — Topology validation catches what it silently allowed (A-10, A-11, A-12, A-17)

- [ ] **Test first**, `pipeline-app/tests/test_pipeline_config.py`:

```python
def _scaffold(root: Path, skills: tuple[str, ...] = (), templates: tuple[str, ...] = ()) -> Path:
    for name in skills:
        (root / ".claude" / "skills" / name).mkdir(parents=True, exist_ok=True)
        (root / ".claude" / "skills" / name / "SKILL.md").write_text("x", encoding="utf-8")
    tdir = root / "pipeline-app" / "stage_templates"
    tdir.mkdir(parents=True, exist_ok=True)
    for name in templates:
        (tdir / f"{name}.md").write_text("/x", encoding="utf-8")
    return root


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
    ...
    with pytest.raises(ValueError, match="brand_scope 'raisingoodsports' is not one of"):
        load_topology(path, repo_root=tmp_path)


def test_an_unscoped_stage_may_not_depend_on_a_brand_scoped_one(tmp_path):
    """A-12's worse half: stages_to_unlock requires every declared dependency
    approved, so such an edge leaves the dependent permanently `locked` on every
    out-of-scope project. migrations.py:166-170 records that exact wedge as a
    real incident."""
    ...
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
```

Update every existing `_write_topology` test to call `_scaffold(tmp_path, ...)` and pass
`repo_root=tmp_path`. The duplicate-id / unknown-dep / cycle tests keep working unchanged because
the new checks run **after** the structural ones.

- [ ] **Run:** `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -q` → the five new
      tests fail (`load_topology() got an unexpected keyword argument 'repo_root'`, then no raise).
- [ ] **Implement**, `pipeline-app/pipeline_app/pipeline_config.py`:

```python
# Explicit, not inferred from the projects table: a brand_scope typo has to be
# rejectable at load time, before any project exists to compare against (A-12).
KNOWN_BRAND_SCOPES = frozenset({"raisinggoodsports"})


def load_topology(path: Path, repo_root: Path | None = None) -> list[StageDef]:
    """repo_root is where `.claude/skills/` and `pipeline-app/stage_templates/`
    resolve from. It defaults to the YAML file's parent, which is correct only
    because pipeline.yaml happens to live at the repo root (A-17) -- so
    _validate_topology verifies the derived root really is a ContentStudio
    checkout instead of validating against the wrong tree in silence."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    stages = [...]
    _validate_topology(stages, repo_root if repo_root is not None else path.parent)
    return stages
```

Append to `_validate_topology`, after `_check_no_cycles(stages)`:

```python
    skills_dir = repo_root / ".claude" / "skills"
    templates_dir = repo_root / "pipeline-app" / "stage_templates"
    if not skills_dir.is_dir() or not templates_dir.is_dir():
        raise ValueError(
            f"pipeline.yaml: {repo_root} is not a ContentStudio checkout — expected "
            f"{skills_dir} and {templates_dir} to exist. Pass repo_root explicitly."
        )
    scope_by_id = {s.id: s.brand_scope for s in stages}
    for stage in stages:
        # `skill` gets exactly the check `specialist` already had. It is the
        # mandatory field, and the one every template renders as /{{ skill }}.
        for field_name in ("skill", "specialist"):
            name = getattr(stage, field_name)
            if name is None:
                continue
            skill_md = skills_dir / name / "SKILL.md"
            if not skill_md.exists():
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' {field_name} '{name}' has no skill "
                    f"at {skill_md}"
                )
        template = templates_dir / f"{stage.id}.md"
        if not template.exists():
            raise ValueError(
                f"pipeline.yaml: stage '{stage.id}' has no kickoff template at {template}"
            )
        if stage.brand_scope is not None and stage.brand_scope not in KNOWN_BRAND_SCOPES:
            raise ValueError(
                f"pipeline.yaml: stage '{stage.id}' brand_scope '{stage.brand_scope}' is not "
                f"one of {sorted(KNOWN_BRAND_SCOPES)}"
            )
        for dep in stage.all_depends_on:
            dep_scope = scope_by_id[dep]
            if dep_scope is not None and stage.brand_scope != dep_scope:
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' (brand_scope {stage.brand_scope!r}) "
                    f"depends on '{dep}' (brand_scope {dep_scope!r}), which has no row on every "
                    f"project '{stage.id}' does — '{stage.id}' would sit locked forever."
                )
```

Move the existing `specialist_mode` check out of the `specialist is not None` block only if it is
still guarded by it; otherwise leave it as-is.

- [ ] **Run** the whole file → pass. **Commit:** `fix(topology): validate skill, template, brand scope and repo root at load time`

---

### T14 — The write scope becomes real, and the tautological test dies (D-43, D-44, D-45, F-11)

The mechanism that actually restricts is `--allowedTools`: it is the auto-approve list, and
headless `claude -p` has nobody to approve anything absent from it (`cli_runner.py:224-229` already
says so). Bare `Write,Edit` therefore auto-approved every path on the machine. `permissions.allow`
never restricted anything.

- [ ] **Test first**, `pipeline-app/tests/test_cli_runner.py`. **Delete lines 458-467**
      (`test_scoped_permissions_settings_scopes_write_edit_to_runs_and_rgs_briefs`) and add:

```python
@pytest.mark.parametrize("path,allowed", [
    ("runs/abc-1/02-scripting/raw_output.md", True),
    ("rgs-briefs/2026-08-08-a.md", True),
    ("scripts/lint_prompt_sheet.py", False),      # D-45: gates.py exec_module's this in-process
    ("scripts/lint_script_language.py", False),
    (".claude/hooks/protect_briefs.py", False),   # D-46: runs as an unrestricted subprocess
    (".claude/settings.json", False),
    (".claude/skills/shorts-assembly/SKILL.md", False),
    ("docs/style-library.md", False),
    ("output/brand-intel/x.json", False),
    ("pipeline.yaml", False),
    ("pipeline-app/pipeline_app/cli_runner.py", False),   # its own runner
    ("../FamilyBrain/anything.md", False),
    ("C:/Windows/System32/x.dll", False),
])
def test_pipeline_turn_write_scope(path, allowed):
    """Effect, not echo. F-11's predecessor deserialized the JSON literal the
    function hard-codes and asserted the four strings survived -- so it could
    never have caught that `permissions.allow` grants rather than restricts."""
    from pipeline_app import cli_runner
    assert cli_runner.permits_write(path) is allowed


def test_the_shipped_flags_are_derived_from_the_policy_permits_write_evaluates():
    """Binds the behavioral test above to what actually ships: a future widening
    of the flags without widening the policy would break here."""
    from pipeline_app import cli_runner

    argv = cli_runner.build_claude_argv(
        "p", None, cli_runner.PIPELINE_ALLOWED_TOOLS, cli_runner.pipeline_permissions_settings(),
        cli_runner.PIPELINE_DISALLOWED_TOOLS, which_fn=lambda _n: "/usr/bin/claude")
    allowed = argv[argv.index("--allowedTools") + 1].split(",")
    assert "Write" not in allowed and "Edit" not in allowed      # never unpatterned
    assert {t for t in allowed if t.startswith(("Write(", "Edit("))} == {
        f"{tool}({pattern})"
        for pattern in cli_runner.WRITE_ALLOW_PATTERNS for tool in ("Write", "Edit")
    }
    denied = argv[argv.index("--disallowedTools") + 1]
    for pattern in cli_runner.WRITE_DENY_PATTERNS:
        assert f"Write({pattern})" in denied and f"Edit({pattern})" in denied


def test_settings_json_carries_a_deny_block_not_just_an_allow_list():
    """D-43: the only key emitted was `permissions.allow`, which grants."""
    from pipeline_app import cli_runner
    data = json.loads(cli_runner.pipeline_permissions_settings())
    assert data["permissions"]["deny"], "an allow-only settings blob restricts nothing"
    assert "Write(scripts/**)" in data["permissions"]["deny"]
    assert "Write(.claude/**)" in data["permissions"]["deny"]


def test_scoped_permissions_settings_is_gone():
    """The old name asserted a control that did not exist; a reviewer grepping
    for it must find nothing rather than a renamed shim."""
    from pipeline_app import cli_runner
    assert not hasattr(cli_runner, "scoped_permissions_settings")
```

- [ ] **Run:** `cd pipeline-app && python -m pytest tests/test_cli_runner.py -q` → fails: no
      `permits_write`, `scripts/**` and `.claude/hooks/**` not denied, no deny block.
- [ ] **Implement**, `pipeline-app/pipeline_app/cli_runner.py`. Replace
      `PIPELINE_DISALLOWED_TOOLS` (`:39-45`) and `scoped_permissions_settings` (`:122-139`) with:

```python
# ONE policy. --allowedTools, --disallowedTools and the --settings deny block are
# all derived from it, and permits_write() is what the tests assert on -- so the
# shipped flags cannot drift from the behaviour under test (F-11).
#
# --allowedTools is the auto-approve list and headless `claude -p` has nobody to
# approve anything absent from it, so NARROWING it is what actually restricts.
# The previous bare "Write,Edit" auto-approved every path on the machine, and the
# `permissions.allow` blob that claimed to scope writes only granted (D-43/D-44).
WRITE_ALLOW_PATTERNS = ("runs/**", "rgs-briefs/**")
WRITE_DENY_PATTERNS = (
    "docs/**",
    "output/**",
    # .claude/** entire, not just skills/**: settings.json registers
    # .claude/hooks/protect_briefs.py as a PreToolUse hook that then runs as an
    # unrestricted Python subprocess (D-46).
    ".claude/**",
    # gates.py loads scripts/lint_*.py by file path and exec_module's them INSIDE
    # the uvicorn process after every turn. A turn that edits a linter gets
    # arbitrary in-process code execution -- the exact capability the Bash and
    # PowerShell denials exist to remove (D-45).
    "scripts/**",
    "pipeline-app/**",
    "pipeline.yaml",
)
DENIED_TOOLS = ("Bash", "PowerShell", "WebFetch", "WebSearch", "NotebookEdit")

_WRITE_TOOLS = ("Write", "Edit")


def _scoped(tools: tuple[str, ...], patterns: tuple[str, ...]) -> list[str]:
    return [f"{tool}({pattern})" for pattern in patterns for tool in tools]


PIPELINE_ALLOWED_TOOLS = ",".join(
    # Task is required, not optional: midjourney-prompting's Gate B and
    # shorts-scripting's Gate E both dispatch a fresh reviewing agent through it.
    ["Read", "Glob", "Grep", "Skill", "Task"] + _scoped(_WRITE_TOOLS, WRITE_ALLOW_PATTERNS)
)
PIPELINE_DISALLOWED_TOOLS = ",".join(
    list(DENIED_TOOLS) + _scoped(_WRITE_TOOLS, WRITE_DENY_PATTERNS)
)


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def permits_write(path: str) -> bool:
    """Would a pipeline-stage turn be allowed to write `path`? Repo-relative,
    forward slashes. This is the single source of truth for the write scope --
    assert on this, never on the flag literals."""
    normalised = path.replace("\\", "/")
    if (normalised.startswith("/") or ".." in normalised.split("/")
            or re.match(r"^[A-Za-z]:", normalised)):
        return False        # nothing outside the project is auto-approved
    if any(_glob_to_regex(p).match(normalised) for p in WRITE_DENY_PATTERNS):
        return False
    return any(_glob_to_regex(p).match(normalised) for p in WRITE_ALLOW_PATTERNS)


def pipeline_permissions_settings() -> str:
    """Inline --settings JSON for a stage turn. `allow` pre-approves the two
    write roots; `deny` is the half that actually refuses. The former name
    (scoped_permissions_settings) and its docstring claimed an allow-only blob
    scoped writes, which it never did (D-43)."""
    return json.dumps({
        "permissions": {
            "allow": _scoped(_WRITE_TOOLS, WRITE_ALLOW_PATTERNS),
            "deny": list(DENIED_TOOLS) + _scoped(_WRITE_TOOLS, WRITE_DENY_PATTERNS),
        }
    })
```

Add `import re`. Change `stream_claude_turn`'s default:
`allowed_tools: str = PIPELINE_ALLOWED_TOOLS`. Update `turn_service.py:166` to
`settings_path=cli_runner.pipeline_permissions_settings()`.

- [ ] **Run** → pass. Re-run `test_default_allowed_tools_includes_task`
      (`test_cli_runner.py:470`) — still green, `Task` is in the list.
- [ ] **Commit:** `fix(security): make the stage-turn write scope real and delete the test that asserted a phantom one`

---

### T15 — The turn's subprocess stops inheriting vendor credentials (D-46)

- [ ] **Test first**, `pipeline-app/tests/test_cli_runner.py`:

```python
def test_child_env_strips_the_apps_vendor_keys(monkeypatch):
    """D-46: stream_claude_turn passed `dict(os.environ)` straight through, so a
    turn -- and any PreToolUse hook it induced -- inherited RESEND_API_KEY,
    YOUTUBE_API_KEY and BRIGHTDATA_API_KEY."""
    from pipeline_app import cli_runner
    for name in ("RESEND_API_KEY", "YOUTUBE_API_KEY", "BRIGHTDATA_API_KEY"):
        monkeypatch.setenv(name, "secret")
    env = cli_runner.child_env()
    assert "RESEND_API_KEY" not in env
    assert "YOUTUBE_API_KEY" not in env
    assert "BRIGHTDATA_API_KEY" not in env


def test_child_env_keeps_the_credentials_the_cli_needs_to_authenticate(monkeypatch):
    """Distinguishability: 'stripped a vendor key' must not become 'stripped the
    key the CLI logs in with'. A blanket *_API_KEY filter would break the app."""
    from pipeline_app import cli_runner
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "secret")
    env = cli_runner.child_env()
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-x"
    assert "BRIGHTDATA_API_KEY" not in env
    assert env["PYTHONIOENCODING"] == "utf-8"


@pytest.mark.asyncio
async def test_stream_claude_turn_launches_with_the_scrubbed_env(monkeypatch):
    """Surfacing/binding: assert the scrub is what the subprocess actually gets,
    not merely that a helper exists."""
    ...  # monkeypatch asyncio.create_subprocess_exec, capture the env kwarg
    assert "BRIGHTDATA_API_KEY" not in captured_env
```

- [ ] **Run** → fails: no `child_env`.
- [ ] **Implement**, `cli_runner.py`:

```python
# Credentials the claude CLI itself may need to authenticate. Everything else
# matching a secret-shaped suffix is stripped from a stage turn's environment:
# a turn has no legitimate use for the app's vendor keys, and .claude/hooks/**
# runs as an unrestricted subprocess that would otherwise inherit them (D-46).
_ENV_KEEP = frozenset({"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN"})
_ENV_SECRET_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


def child_env() -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if key in _ENV_KEEP or not key.upper().endswith(_ENV_SECRET_SUFFIXES)
    }
    env["PYTHONIOENCODING"] = "utf-8"
    return env
```

and in `stream_claude_turn` replace the two `env = dict(os.environ)` /
`env["PYTHONIOENCODING"] = "utf-8"` lines with `env = child_env()`.

- [ ] **Run** → pass. **Commit:** `fix(security): strip vendor credentials from a stage turn's environment`

---

### T16 — The test doubles stop discarding the prompt (F-15)

`turn_service.py:133-159` — upstream resolution, `is_first_turn`, the whole kickoff render —
executed on all 11 tests with **zero** assertions, contributing to 98% coverage. Every finding in
this package's first half lives inside those lines.

- [ ] **Test first**, `pipeline-app/tests/test_turn_service.py`. Replace `_fake_stream`
      (`:30-37`) and the three `_slow_gen` doubles (`:148-152`, `:184-188`, `:213-217`) with one
      capturing double:

```python
_INIT = {"type": "system", "subtype": "init", "session_id": "session-1"}
_RESULT_OK = {"type": "result", "result": "done", "total_cost_usd": 0.01, "is_error": False}


@pytest.fixture
def capture() -> list[dict]:
    """What the CLI was actually handed. The old doubles took `prompt` and
    `resume_session_id` and inspected neither (F-15)."""
    return []


def _fake_stream(events, writes_file=None, content="generated body", captured=None):
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
```

and add the per-stage handoff assertions:

```python
@pytest.mark.asyncio
async def test_assembly_kickoff_prompt_carries_every_input_its_skill_requires(
        conn, tmp_path, monkeypatch, capture):
    """The end-to-end proof of A-01/A-03/A-04: what the model is actually sent."""
    project_id, run_dir = _rgs_chain(conn, tmp_path, brief="rgs-briefs/2026-08-08-a.md")
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        _fake_stream([_INIT, _RESULT_OK],
                                     run_dir / "04-assembly" / "raw_output.md", captured=capture))
    await _drain(turn_service.run_stage_turn(
        conn, tmp_path, run_dir, TEMPLATES_DIR, project_id, "abc-1",
        _by_id("assembly"), CHAIN_STAGES, "cut it",
        grounding_pointer="rgs-briefs/2026-08-08-a.md"))

    prompt = capture[0]["prompt"]
    assert prompt.startswith("/shorts-assembly")
    for fragment in ("02-scripting/artifact.v1.md", "02b-styleboard/artifact.v1.md",
                     "03-voiceover/artifact.v1.md", "03-visual/artifact.v1.md",
                     "rgs-briefs/2026-08-08-a.md"):
        assert fragment in prompt, fragment
    assert capture[0]["resume_session_id"] is None


@pytest.mark.asyncio
async def test_repurpose_kickoff_prompt_carries_the_script_and_packaging_direction(...):
    for fragment in ("01-ideation/artifact.v1.md", "02-scripting/artifact.v1.md",
                     "04-assembly/artifact.v1.md"):
        assert fragment in prompt, fragment
    assert "rgs-briefs/2026-08-08-a.md" in prompt
```

- [ ] **Test first**, `pipeline-app/tests/test_routes_chat_sse.py` — the human-reachable end of the
      chain:

```python
def test_chat_on_a_stage_with_a_missing_required_upstream_leaves_an_error_event(client, tmp_path):
    """Surfacing: the refusal must be findable after the fact. The route raises
    inside the SSE body generator, so the events row is the only durable signal."""
    ...
    with pytest.raises(Exception):
        with client.stream("POST", f"/projects/{pid}/stages/scripting/chat",
                           data={"message": "go"}) as response:
            list(response.iter_lines())
    rows = client.app.state.conn.execute(
        "SELECT severity, message FROM events WHERE kind = 'handoff.upstream_missing'").fetchall()
    assert rows and rows[0]["severity"] == "error"


def test_chat_kickoff_prompt_reaches_the_cli_with_the_grounding_pointer(client, monkeypatch, capture):
    """A-04 through the real route: routes/stages.py resolves a pointer for every
    non-grounding stage on an RGS project and hands it to run_stage_turn."""
    ...
    assert "rgs-briefs/" in capture[0]["prompt"]
```

- [ ] **Run:** `cd pipeline-app && python -m pytest -q` → the capture tests fail first
      (the double drops the prompt), then pass.
- [ ] **Run the full suite from both rootdirs.**
- [ ] **Commit:** `test(handoff): assert what the CLI is actually handed, per stage`

---

### T17 — Adopt `gates.resolve_upstream_by_stage` as the single upstream-map builder (P3 Handoff H2)

T5 builds the stage-id-keyed upstream dict inline. P3 owns the one implementation
(`gates.resolve_upstream_by_stage`, its Task 2) because the map is defined by what a `GateRunner`
needs. Until this task lands, P3's **static** parity test cannot see the two maps drift in
*contents* — only its behavioural test covers the gap. Sequenced late so P4's finding work is not
blocked on P3's merge, exactly as P5 does at its T19.

> **Counter-contract to P3 — required before this task can land.** P3's current body resolves via
> `artifacts.latest_artifact_path` and iterates `stage_def.depends_on` only. Adopting it verbatim
> would **reintroduce three P4 findings**: A-32 (an unapproved draft becomes the gate input again),
> A-02 (`optional_depends_on: [music]` never reaches `assembly`), and A-14 (grounding's pointer
> indirection resolves to `None`). P3 must widen the signature — three keywords, all defaulting to
> today's behaviour so P3's own call site is unchanged:
>
> ```python
> def resolve_upstream_by_stage(
>     run_dir: Path, all_stage_defs: list[StageDef], stage_def: StageDef, *,
>     repo_root: Path | None = None,   # pointer-aware resolution for `grounding` (A-14)
>     approved_only: bool = False,     # frontmatter status == "final" (A-32)
>     include_optional: bool = False,  # also walk stage_def.optional_depends_on (A-02)
> ) -> dict[str, Path]: ...
> ```
>
> P4's T5/T6/T10 tests are the acceptance criteria for that widening. P3 will likely want
> `approved_only=True` on its own hand-edit call too — A-32's blast radius covers both writers —
> but that is P3's call, not P4's.

- [ ] **Test first**, `pipeline-app/tests/test_turn_service.py`:

```python
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
```

```python
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
```

- [ ] **Run** → fails: `AttributeError: module 'pipeline_app.gates' has no attribute
      'resolve_upstream_by_stage'` (P3 not yet merged) or `TypeError: unexpected keyword argument
      'approved_only'` (P3 merged without the widening). **Either failure is the signal to stop and
      hand back to P3** — do not work around it by keeping the local copy. Once P3 has landed, the
      three-state test fails next: both paths raise the same `MissingUpstreamArtifactError`.
- [ ] **Implement**, `turn_service.py`. Delete `_resolve_upstream` and the inline loop from T5, and
      replace with a single call plus the required/optional split P4 still owns:

```python
    resolved = gates.resolve_upstream_by_stage(
        run_dir, all_stage_defs, stage_def,
        repo_root=repo_root, approved_only=True, include_optional=True,
    )
    missing = [dep_id for dep_id in stage_def.depends_on if dep_id not in resolved]
    inputs = {sid: str(p) for sid, p in resolved.items()}
```

The `missing` refusal, the `handoff.upstream_missing` event and the optional-absent `obs.log` from
T5 are unchanged — only the *resolution* moves. `_approved_artifact_path` (T6) moves to `gates.py`
as the implementation behind `approved_only=True`; delete P4's copy so there is one.

- [ ] **Run** the full app suite. T5's, T6's and T10's tests must still pass unmodified — that is
      the proof the swap is behaviour-preserving.
- [ ] **Commit:** `refactor(handoff): build the upstream map once, in gates.resolve_upstream_by_stage`

---

### T18 — Adopt P2's `artifacts.py` API (breaking changes)

P2 §6.2 freezes four changes that break P4's files on contact, and P2 §6.3 item 5 names
`turn_service.py:74` as **the highest-value wrap in the whole programme**. This task closes no new
P4 finding — it is the mechanical cost of P2's fixes landing here — but skipping the `:74` wrap
would leave a malformed dependent aborting the staleness cascade mid-iteration, some stages
flipped and the rest silently `approved`.

- [ ] **Test first**, `pipeline-app/tests/test_turn_service.py`:

```python
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
    ...
    rows = conn.execute(
        "SELECT severity, message FROM events WHERE kind = 'staleness.dependent_unreadable'"
    ).fetchall()
    assert rows and rows[0]["severity"] == "error" and "03-voiceover" in rows[0]["message"]


def test_depends_on_is_computed_by_the_shared_helper(conn, tmp_path, monkeypatch):
    """P2 §6.1: one implementation of the [{path, sha256}] shape, not two."""
    calls = []
    real = artifacts.compute_depends_on
    monkeypatch.setattr(artifacts, "compute_depends_on",
                        lambda run_dir, paths: calls.append(list(paths)) or real(run_dir, paths))
    ...  # run one assembly turn
    assert calls and len(calls[0]) == 4


@pytest.mark.asyncio
async def test_a_concurrent_version_allocation_does_not_lose_the_write(conn, tmp_path):
    """next_version_number is ADVISORY ONLY under P2 (A-65). run_stage_turn must
    reserve, write, and release -- leaving it on next_version_number + write_artifact
    turns a silent lost write into an ArtifactExistsError 500, which is better but
    not closed."""
    ...
    with pytest.raises(artifacts.ArtifactExistsError):
        artifacts.write_artifact(stage_dir, 1, {"stage": "x"}, "clobber")
```

- [ ] **Run** → fails: `MalformedArtifactError` escapes `propagate_staleness`; no
      `compute_depends_on` call; `next_version_number` still in use.
- [ ] **Implement**, `turn_service.py`:

1. **`propagate_staleness` phase-1 loop** (`:74`) — the load-bearing wrap:

```python
        try:
            meta, _body = artifacts.read_artifact(latest)
        except artifacts.MalformedArtifactError as exc:
            # Contained PER DEPENDENT, deliberately. Letting this propagate would
            # abort the cascade mid-iteration: dependents earlier in the list end
            # up stale, later ones stay approved, and nothing says why (P2 §6.3).
            obs.record_event(
                conn, kind="staleness.dependent_unreadable", severity="error",
                source="turn_service.propagate_staleness",
                message=f"cannot read {exc.path}: {exc.reason}; "
                        f"stage '{dep_stage.id}' left at {row['status']}",
                detail={"stage": dep_stage.id, "path": str(exc.path), "reason": exc.reason},
            )
            continue
```

2. **`_approved_artifact_path`** (T6) and **`propagate_grounding_staleness`** (T11) — same
   `try/except artifacts.MalformedArtifactError` + `continue` around each candidate read, with
   kinds `handoff.artifact_unreadable` and `grounding.dependent_unreadable`. A damaged `v3` must
   not hide an intact approved `v2`.

3. **`depends_on` construction** (`:234-237`) — replace the comprehension with P2's helper, keeping
   the A-13 grounding record appended:

```python
    depends_on = artifacts.compute_depends_on(run_dir, upstream_paths)
    if grounding_pointer:
        brief = repo_root / grounding_pointer
        if brief.exists():
            depends_on.append({"path": grounding_pointer,
                               "sha256": artifacts.compute_sha256(brief)})
        else:
            obs.record_event(conn, kind="handoff.grounding_brief_missing", severity="error", ...)
```

4. **Version allocation** (`:233`, `:254`) — reserve/write/release instead of
   `next_version_number` + `write_artifact`:

```python
    reservation = artifacts.reserve_version(stage_dir)
    try:
        meta = {..., "version": reservation.version,
                "supersedes": f"artifact.v{reservation.version - 1}.md"
                              if reservation.version > 1 else None, ...}
        artifacts.write_reserved_artifact(reservation, meta, body)
    except BaseException:
        artifacts.release_version(reservation)
        raise
```

5. **`_relpath`** — delete it; call `artifacts.relpath_in_run(path, run_dir)` in
   `_write_session_inputs`, `_resumed_prompt` and `_current_upstream_hashes`.

6. **`propagate_grounding_staleness`** (T11) — `grounding_service.read_pointer` now raises
   `InvalidPointerError` rather than returning `None` for a damaged pointer:

```python
    try:
        current = grounding_service.read_pointer(run_dir / "00-grounding")
    except grounding_service.InvalidPointerError as exc:
        obs.record_event(conn, kind="grounding.pointer_invalid", severity="error",
                         source="turn_service", message=str(exc), detail={"run_dir": str(run_dir)})
        return []
```

7. **Tests** — `test_turn_service.py:352` and every other
   `artifacts.parse_frontmatter(path.read_text(...))` in P4's test files becomes
   `artifacts.read_artifact(path)`.

- [ ] **Run** both suites → pass. **Commit:** `refactor(handoff): adopt the durable artifacts API and contain malformed reads`

---

### T19 — F-26's second half: the gate-result test that asserts its own mock (P1 handoff)

P1 closed F-26's `test_main.py` half and hands this one over: `test_turn_service.py:335-343`
monkeypatches `gates.run_gates_for_stage` to return a hard-coded failing result, then line 353
asserts that same literal came back out of the frontmatter. It proves the dict survived a round
trip and nothing else — no gate ran, no linter was consulted, and the test would stay green if
`run_gates_for_stage` were never called at all.

Naming follows P1's T18 convention: the surviving echo test is renamed to say only what it does;
the real behaviour gets its own named tests.

- [ ] **Rename**, `test_turn_service.py:312` —
      `test_scripting_turn_records_gate_results_in_frontmatter` becomes
      `test_whatever_the_gate_runner_returns_is_recorded_verbatim`, with a docstring saying it is a
      round trip and nothing more (P1's `test_cli_availability_is_recorded_on_app_state` pattern).
- [ ] **Delete** the `monkeypatch.setattr(turn_service.gates, "run_gates_for_stage", ...)` block at
      `:335-343` from the two new tests below — they must exercise the real registry.
- [ ] **Test first:**

```python
@pytest.mark.asyncio
async def test_a_real_failing_gate_is_recorded_from_an_actual_lint_run(conn, tmp_path, monkeypatch):
    """FAULT. The predecessor injected `{"status": "fail"}` into a mock and
    asserted it came back (F-26). This runs the registered Gate D linter over a
    script that genuinely violates D1, so the recorded result is produced, not
    supplied."""
    ...  # approved ideation upstream; raw_output contains an em-dash HOOK line
    meta, _ = artifacts.read_artifact(artifacts.latest_artifact_path(stage_dir))
    recorded = {g["name"]: g["status"] for g in meta["gates"]}
    assert recorded["gate_d_script_language"] == "fail"
    assert any(f["check"] == "D1" for g in meta["gates"] for f in g["findings"])


@pytest.mark.asyncio
async def test_a_clean_script_records_the_same_gate_as_passing(conn, tmp_path, monkeypatch):
    """DISTINGUISHABILITY. A test that only ever sees `fail` cannot tell a real
    lint run from a stuck one. Same stage, same runner, opposite verdict."""
    ...
    assert recorded["gate_d_script_language"] == "pass"


@pytest.mark.asyncio
async def test_a_failing_gate_still_leaves_the_artifact_and_the_stage_reviewable(...):
    """SURFACING. The operator must be able to see what failed: the artifact is
    on disk, the stage is awaiting_review, and the findings are in frontmatter."""
    assert db.get_stage(conn, project_id, "scripting")["status"] == StageStatus.AWAITING_REVIEW.value
```

- [ ] **Run** → the fault test fails first (with the mock removed, no gate result is recorded
      because the fixture's upstream is missing — fix the fixture, not the assertion).
- [ ] **Commit:** `test(turn-service): assert gate results from a real lint run, not an injected literal (F-26)`

---

### T20 — Derived accessors and the duplicate-`skill` rule (P5 contract)

P5 needs two derived accessors and one topology rule, and ships a private copy until P4 provides
them (P5's T19 swaps over). The rule is P4's to own: `pipeline.yaml` is this package's file, and
two stages declaring the same `skill:` would make `{s.skill: s.id}` last-wins — silently binding
P5's skill editor to the wrong stage's kickoff template.

- [ ] **Test first**, `pipeline-app/tests/test_pipeline_config.py`:

```python
def test_stage_id_by_skill_maps_every_stage():
    stages = load_topology(REPO_ROOT / "pipeline.yaml", repo_root=REPO_ROOT)
    mapping = stage_id_by_skill(stages)
    assert mapping["shorts-assembly"] == "assembly"
    assert mapping["rgs-grounding"] == "grounding"
    assert len(mapping) == len(stages)          # no collision swallowed a stage


def test_two_stages_declaring_the_same_skill_are_rejected(tmp_path):
    """A skill: collision makes {s.skill: s.id} last-wins, so P5's skill editor
    would bind the skill to the WRONG stage's kickoff template with no error."""
    _scaffold(tmp_path, skills=("shorts-ideation",), templates=("ideation", "ideation2"))
    path = _write_topology(tmp_path,
        'stages:\n'
        '  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: "01"\n    depends_on: []\n'
        '  - id: ideation2\n    skill: shorts-ideation\n    dir_prefix: "01b"\n    depends_on: []\n')
    with pytest.raises(ValueError, match="skill 'shorts-ideation' is declared by 2 stages"):
        load_topology(path, repo_root=tmp_path)


def test_stage_template_path_points_at_the_stages_kickoff_file():
    assert stage_template_path(REPO_ROOT, "assembly") == \
        REPO_ROOT / "pipeline-app" / "stage_templates" / "assembly.md"
```

- [ ] **Run** → fails: the two functions do not exist; the collision loads silently.
- [ ] **Implement**, `pipeline-app/pipeline_app/pipeline_config.py`:

```python
def stage_template_path(repo_root: Path, stage_id: str) -> Path:
    """The one place the kickoff-template location is spelled. _validate_topology,
    prompt_builder's loader and the skill editor must all agree on it."""
    return repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"


def stage_id_by_skill(stage_defs: list[StageDef]) -> dict[str, str]:
    """Derived, never stored. Safe to build as a plain dict only because
    _validate_topology rejects a duplicate `skill:` -- otherwise last-wins would
    bind a skill to the wrong stage's template."""
    return {s.skill: s.id for s in stage_defs}
```

and in `_validate_topology`, beside the duplicate-id check:

```python
    by_skill: dict[str, list[str]] = {}
    for stage in stages:
        by_skill.setdefault(stage.skill, []).append(stage.id)
    for skill, stage_ids in by_skill.items():
        if len(stage_ids) > 1:
            raise ValueError(
                f"pipeline.yaml: skill '{skill}' is declared by {len(stage_ids)} stages "
                f"({', '.join(sorted(stage_ids))}); stage_id_by_skill would silently keep one"
            )
```

Also switch T13's template-existence check to call `stage_template_path(repo_root, stage.id)` so
there is one spelling.

- [ ] **Run** → pass. **Commit:** `feat(topology): derived skill/template accessors and a duplicate-skill rule`

---

## 4. Finding → test map

Three-Test-Rule roles: **F** = fault, **D** = distinguishability, **S** = surfacing. Findings
whose `failure_mode` is not `silent` carry a single regression test.

| Finding | Mode | Role | Test (file :: name) |
|---|---|---|---|
| A-01 | silent | F | `test_prompt_builder.py::test_every_input_a_kickoff_template_names_is_reachable_via_depends_on[assembly]` |
| A-01 | | F | `test_pipeline_config.py::test_repurpose_depends_on_the_script_and_the_packaging_direction` |
| A-01 | | D | `test_turn_service.py::test_missing_required_upstream_refuses_the_turn` vs `..._missing_optional_upstream_renders_a_valid_prompt` |
| A-01 | | S | `test_turn_service.py::test_assembly_kickoff_prompt_carries_every_input_its_skill_requires` |
| A-02 | silent | F | `test_pipeline_config.py::test_assembly_depends_on_every_artifact_its_skill_requires` |
| A-02 | | D | `test_prompt_builder.py::test_assembly_template_says_the_bed_is_absent_rather_than_omitting_it` |
| A-02 | | S | `test_turn_service.py::test_regenerating_the_bed_arc_marks_assembly_stale` |
| A-03 | silent | F | `test_pipeline_config.py::test_assembly_depends_on_every_artifact_its_skill_requires` |
| A-03 | | D | `test_prompt_builder.py::test_assembly_template_names_the_script_and_the_styleboard` |
| A-03 | | S | `test_turn_service.py::test_assembly_kickoff_prompt_carries_every_input_its_skill_requires` |
| A-04 | silent | F | `test_prompt_builder.py::test_grounding_pointer_reaches_the_last_two_stages[assembly]`/`[repurpose]` |
| A-04 | | D | same test's `assert with_ptr != without` (RGS vs generic project) |
| A-04 | | S | `test_routes_chat_sse.py::test_chat_kickoff_prompt_reaches_the_cli_with_the_grounding_pointer` |
| A-05 | silent | F | `test_turn_service.py::test_resumed_turn_names_the_new_upstream_version` |
| A-05 | | D | `test_turn_service.py::test_resumed_turn_with_unchanged_upstream_sends_only_the_message` |
| A-05 | | S | `test_turn_service.py::test_upstream_change_on_a_resumed_turn_records_a_warning_event` |
| A-06 | loud | — | `test_turn_service.py::test_a_session_that_never_opened_is_cleared_so_the_next_turn_re_renders` + `..._a_failed_turn_on_a_live_session_keeps_the_session_id` |
| A-07 | silent | F | `test_turn_service.py::test_missing_required_upstream_refuses_the_turn` |
| A-07 | | D | `test_turn_service.py::test_missing_optional_upstream_renders_a_valid_prompt` |
| A-07 | | S | `test_turn_service.py::test_missing_required_upstream_records_an_error_event` |
| A-08 | silent | F | `test_prompt_builder.py::test_a_typo_in_a_template_raises_instead_of_rendering_empty` |
| A-08 | | D | `test_prompt_builder.py::test_render_rejects_a_context_missing_a_frozen_key` + `..._an_unknown_context_key` |
| A-08 | | S | `test_prompt_builder.py::test_validate_template_source_rejects_a_bad_name_before_it_is_saved` |
| A-09 | latent | — | `test_prompt_builder.py::test_every_input_a_kickoff_template_names_is_reachable_via_depends_on` (all 9) + `..._test_repurpose_template_names_three_inputs_not_one_path_called_two_documents` |
| A-10 | loud | — | `test_pipeline_config.py::test_a_stage_with_no_kickoff_template_is_rejected_at_load_time` |
| A-11 | silent | F | `test_pipeline_config.py::test_a_stage_whose_skill_directory_does_not_exist_is_rejected` |
| A-11 | | D | `test_pipeline_config.py::test_the_real_topology_loads_with_an_explicit_repo_root` (valid names load; a typo does not) |
| A-11 | | S | the `ValueError` at `load_topology` is raised at app startup — asserted by the fault test's `pytest.raises` |
| A-12 | latent | — | `test_pipeline_config.py::test_an_unknown_brand_scope_is_rejected` + `..._an_unscoped_stage_may_not_depend_on_a_brand_scoped_one` |
| A-13 | silent | F | `test_turn_service.py::test_repointing_grounding_marks_downstream_stale` |
| A-13 | | D | `test_turn_service.py::test_a_generic_project_with_no_brief_is_not_marked_stale` |
| A-13 | | S | `test_turn_service.py::test_repointing_grounding_records_a_warning_event` |
| A-14 | latent | — | `test_turn_service.py::test_staleness_hashing_without_a_repo_root_says_so_for_a_pointer_backed_upstream` |
| A-15 | loud | — | `test_turn_service.py::test_run_stage_turn_rejects_a_stage_the_project_has_no_row_for` |
| A-16 | latent | — | `test_prompt_builder.py::test_assembly_template_names_the_script_and_the_styleboard` (asserts the `script: \`…\`` label form) |
| A-17 | docs-drift | — | `test_pipeline_config.py::test_loading_a_topology_from_outside_the_repo_fails_loudly` |
| A-32 | silent | F | `test_turn_service.py::test_upstream_resolves_to_the_approved_version_not_an_unapproved_draft` |
| A-32 | | D | `test_turn_service.py::test_approved_artifact_path_distinguishes_no_artifact_from_only_drafts` |
| A-32 | | S | `test_turn_service.py::test_missing_required_upstream_records_an_error_event` (drafts-only upstream refuses the turn and leaves the row) |
| A-44 | silent | F | `test_turn_service.py::test_propagate_staleness_marks_an_unapproved_draft_stale_too` |
| A-44 | | D | `test_turn_service.py::test_a_locked_dependent_is_not_marked_stale` |
| A-44 | | S | the `stale` status itself renders in `stage.html:57`; asserted via the DB row in the fault test |
| A-46 | silent | F | `test_turn_service.py::test_aborting_a_turn_on_a_stale_stage_leaves_it_stale` |
| A-46 | | D | `test_turn_service.py::test_aborting_a_turn_on_an_approved_stage_leaves_it_approved` |
| A-46 | | S | `test_turn_service.py::test_disconnected_turn_is_marked_aborted_not_left_running` (existing; the `aborted` turn row is the human-reachable record) |
| D-43 | silent | F | `test_cli_runner.py::test_settings_json_carries_a_deny_block_not_just_an_allow_list` |
| D-43 | | D | `test_cli_runner.py::test_pipeline_turn_write_scope` (allowed paths True, denied paths False — an allow-only blob returns True for both) |
| D-43 | | S | `test_cli_runner.py::test_scoped_permissions_settings_is_gone` |
| D-44 | latent | — | `test_cli_runner.py::test_the_shipped_flags_are_derived_from_the_policy_permits_write_evaluates` |
| D-45 | silent | F | `test_cli_runner.py::test_pipeline_turn_write_scope[scripts/lint_prompt_sheet.py-False]` |
| D-45 | | D | same parametrization: `runs/…` True while `scripts/…` False |
| D-45 | | S | `test_cli_runner.py::test_the_shipped_flags_are_derived_from_the_policy_permits_write_evaluates` (asserts `Write(scripts/**)` in the shipped `--disallowedTools`) |
| D-46 | silent | F | `test_cli_runner.py::test_child_env_strips_the_apps_vendor_keys` |
| D-46 | | D | `test_cli_runner.py::test_child_env_keeps_the_credentials_the_cli_needs_to_authenticate` |
| D-46 | | S | `test_cli_runner.py::test_stream_claude_turn_launches_with_the_scrubbed_env` |
| F-11 | silent | F | deletion is the fix; `test_cli_runner.py::test_pipeline_turn_write_scope` replaces it |
| F-11 | | D | `test_cli_runner.py::test_the_shipped_flags_are_derived_from_the_policy_permits_write_evaluates` |
| F-11 | | S | `test_cli_runner.py::test_scoped_permissions_settings_is_gone` |
| F-15 | coverage-gap | — | `test_turn_service.py::test_assembly_kickoff_prompt_carries_every_input_its_skill_requires` + `..._repurpose_kickoff_prompt_carries_the_script_and_packaging_direction` |

### Inherited rows (findings owned by another package, closed in P4's files)

| Finding | Owner | Role | Test (file :: name) |
|---|---|---|---|
| F-26 (2nd half) | P1 | F | `test_turn_service.py::test_a_real_failing_gate_is_recorded_from_an_actual_lint_run` |
| F-26 (2nd half) | P1 | D | `test_turn_service.py::test_a_clean_script_records_the_same_gate_as_passing` |
| F-26 (2nd half) | P1 | S | `test_turn_service.py::test_a_failing_gate_still_leaves_the_artifact_and_the_stage_reviewable` |
| A-69 (P2 §6.3 #5) | P2 | F | `test_turn_service.py::test_one_malformed_dependent_does_not_abort_the_staleness_cascade` |
| A-69 (P2 §6.3 #5) | P2 | D+S | `test_turn_service.py::test_a_malformed_dependent_is_recorded_not_skipped_in_silence` |
| A-65 (call site) | P2 | — | `test_turn_service.py::test_a_concurrent_version_allocation_does_not_lose_the_write` |
| A-61 (shape) | P2 | — | `test_turn_service.py::test_depends_on_is_computed_by_the_shared_helper` |
| A-30/A-62 (parity) | P3 | — | `test_turn_service.py::test_turn_service_and_gates_build_the_same_upstream_map` |
| — (P5 contract) | P5 | — | `test_pipeline_config.py::test_two_stages_declaring_the_same_skill_are_rejected` + `..._stage_id_by_skill_maps_every_stage` + `..._stage_template_path_points_at_the_stages_kickoff_file` |

---

## 5. Tests deleted or inverted

| File:line | Test | Action | Why |
|---|---|---|---|
| `pipeline-app/tests/test_cli_runner.py:458-467` | `test_scoped_permissions_settings_scopes_write_edit_to_runs_and_rgs_briefs` | **DELETE** (whole function, incl. its two local imports) | **F-11.** It deserializes the JSON literal the function hard-codes and asserts four strings survived the round trip. There is no true statement this test's *shape* can express: `permissions.allow` grants, so no assertion about its contents can say anything about restriction. Inverting it would just be a different meaningless echo. Replaced by `test_pipeline_turn_write_scope` (asserts effect, over 13 paths) and `test_the_shipped_flags_are_derived_from_the_policy_permits_write_evaluates` (binds effect to the shipped flags). |
| `pipeline-app/tests/test_prompt_builder.py:128-142` | `test_assembly_template_lists_both_upstream_inputs_not_the_script` | **DELETE and invert** | Its name states the A-01 defect as the requirement, and its last line — `assert "the script" not in prompt.lower()` — actively forbids the fix. Replaced by `test_assembly_template_names_the_script_and_the_styleboard`, which asserts the opposite. |
| `pipeline-app/tests/test_turn_service.py:294-308` | `test_propagate_staleness_cascade_stops_at_a_non_approved_stage` | **INVERT** | It asserts `assembly` at `awaiting_review` stays `awaiting_review` when its upstream is regenerated — the A-44 defect, frozen as correct. Becomes `test_propagate_staleness_marks_an_unapproved_draft_stale_too` (assembly → `stale`, repurpose → `stale` by cascade). The legitimate half of its intent survives as `test_a_locked_dependent_is_not_marked_stale`. |
| `pipeline-app/tests/test_pipeline_config.py:53-56` | `test_assembly_depends_on_both_branch_stages` | **INVERT** | Pins `depends_on == {voiceover, visual}` — the exact under-declaration A-01/A-03 report. Becomes `test_assembly_depends_on_every_artifact_its_skill_requires`. |
| `pipeline-app/tests/test_pipeline_config.py:294-301` | `test_every_stage_has_a_kickoff_template` | **KEEP, and add the load-time check** | A-10 explicitly says the test is fine — it is in the wrong *place*. Keep it as the regression guard; `_validate_topology` gains the same check so a missing template fails at startup, not inside an SSE body generator. |
| `pipeline-app/tests/test_turn_service.py:335-343` (assertion at `:353`) | `test_scripting_turn_records_gate_results_in_frontmatter` | **RENAME + narrow, and add three real tests** (T19) | **F-26, second half** — P1 closed the `test_main.py` half and handed this over. The test monkeypatches `run_gates_for_stage` to return a hard-coded `{"status": "fail"}`, then asserts that literal came back out of the frontmatter: a dict round trip, green even if no gate ever ran. Renamed to `test_whatever_the_gate_runner_returns_is_recorded_verbatim` (claiming only the round trip, mirroring P1's `test_cli_availability_is_recorded_on_app_state`); the real behaviour moves to `test_a_real_failing_gate_is_recorded_from_an_actual_lint_run`, `test_a_clean_script_records_the_same_gate_as_passing` and `test_a_failing_gate_still_leaves_the_artifact_and_the_stage_reviewable`, all running the registered Gate D linter for real. |

---

## 6. Contract for P13 (`.claude/skills/**`)

The graph now carries what the skills declare. These SKILL.md files must be updated so the prose
matches — P4 does not touch them. Each item is a *documentation* change; none alters skill craft.

1. **`shorts-assembly/SKILL.md`** — "Inputs required to run this skill" (≈:16-29) lists three
   required inputs and one optional, but :31-39 separately requires the styleboard's `BINDINGS`
   line. The styleboard is now a **declared required dependency**. Renumber: `1.` script,
   `2.` voiceover brief, `3.` visual prompt sheet, `4.` **styleboard (BINDINGS)**, `5.` music bed
   brief — *optional*. Change "If any of the first three is missing, ask for it" to "If any of the
   first four is missing…", and "The fourth is genuinely optional" to "The fifth…". The Pipeline
   position table's Upstream cell must gain `shorts-styleboard`.
2. **`social-repurpose/SKILL.md:12-13`** — "**Upstream input** (from `shorts-assembly`): the
   finished Short's script, its packaging direction … and the edit/assembly plan" is now false as
   to provenance. The three inputs arrive as three separate upstreams:
   `shorts-scripting` (script), `shorts-ideation` (packaging direction), `shorts-assembly` (edit
   plan). Restate as three named upstreams. The "constraints that survive to publish" line
   (:17) now also reaches this stage directly via the grounding pointer — say so.
3. **`music-brief/SKILL.md`** — its Downstream is documented as `elevenlabs-music` only. The bed
   arc now has a second, optional consumer: `shorts-assembly`. Add it, marked optional, so the
   skill's own pipeline-position table matches `optional_depends_on: [music]`.
4. **`shorts-styleboard/SKILL.md`** — Downstream is documented as `visual-prompts`. It is now also
   `shorts-assembly` (slot resolution). Add it.
5. **The standing rule.** A SKILL.md may not declare a *required* input that `pipeline.yaml` does
   not carry as a `depends_on` edge for that stage. Adding one is a P4 change first (edge +
   template + conformance test), a P13 change second. If P13 wants a machine check on its side, the
   natural shape is a test that parses each SKILL.md's required-input list and asserts it is a
   subset of that stage's `depends_on` — the SKILL.md-side mirror of
   `test_every_input_a_kickoff_template_names_is_reachable_via_depends_on`.

---

## 7. Cross-package notes (do not edit these files from P4)

### 7.1 Blocking — P4 cannot finish T17 without this

**P3 must widen `gates.resolve_upstream_by_stage` before T17 can land.** Its current body resolves
via `artifacts.latest_artifact_path` and walks `stage_def.depends_on` only. Adopting it as-is
reintroduces **A-32** (unapproved draft becomes the gate input), **A-02** (`music` never reaches
`assembly`) and **A-14** (grounding resolves to `None`). Required signature — three keywords, all
defaulting to today's behaviour so P3's own call site is unchanged:

```python
def resolve_upstream_by_stage(
    run_dir: Path, all_stage_defs: list[StageDef], stage_def: StageDef, *,
    repo_root: Path | None = None,   # pointer-aware resolution for `grounding`
    approved_only: bool = False,     # frontmatter status == "final"
    include_optional: bool = False,  # also walk stage_def.optional_depends_on
) -> dict[str, Path]: ...
```

P4's T5/T6/T10 tests are the acceptance criteria. P4 also hands P3 the `approved_only=True`
implementation body (`_approved_artifact_path`, T6) to move into `gates.py`, so there is one copy.
P3 will probably want `approved_only=True` on its hand-edit call too — A-32 covers both writers —
but that is P3's decision.

### 7.2 Accepted inbound contracts

- **P2 §6.1–§6.3 → T18.** Adopted in full: `read_artifact`/`MalformedArtifactError` at every P4
  read site (including P2's named highest-value wrap at `turn_service.py:74`, contained *per
  dependent*), `compute_depends_on` replacing P4's hand-rolled hashing, `relpath_in_run` replacing
  `_relpath`, `reserve_version`/`write_reserved_artifact`/`release_version` replacing
  `next_version_number` + `write_artifact`, and `grounding_service.InvalidPointerError` handled in
  `propagate_grounding_staleness`.
- **P1 F-26 → T19.** The second half (`test_turn_service.py:335-343`) is repaired here; naming
  follows P1's T18 convention.

### 7.3 Provided by P4 for other packages

- **P5** — `pipeline_config.stage_id_by_skill(stage_defs)` and
  `pipeline_config.stage_template_path(repo_root, stage_id)` ship in **T20**, together with the
  `_validate_topology` rule rejecting two stages that declare the same `skill:` (without it,
  `{s.skill: s.id}` is last-wins and the skill editor binds to the wrong template). P5 can drop its
  private copy at its T19.
- **P13** — the SKILL.md contract in §6.

### 7.4 Informational

- **P1 (`db.py`)** — `db.update_stage_session(conn, stage_row_id, session_id: str)` is called with
  `None` by T8. SQLite accepts it; only the annotation is wrong. Widen to `str | None` when
  convenient. No behaviour change required for P4's tests to pass.
- **P3 (`routes/stages.py:287`)** — `propagate_staleness` gained an optional `repo_root=` keyword.
  The existing call still works; passing `repo_root=repo_root` is what closes A-14 on the
  hand-edit path.
- **P3 (`routes/stages.py`, grounding branch ≈:186)** — after `grounding_service.write_pointer(...)`,
  call `turn_service.propagate_grounding_staleness(conn, repo_root, run_dir, stage_defs, project_id)`
  so a re-pointed brief invalidates downstream **immediately** rather than on the next turn
  anywhere in the run. Without it, A-13 is closed but fires one turn late.
- **P3 (`preflight.py:38-40`)** — the startup sweep still re-derives status from artifact existence,
  so it launders `stale` the same way the abort path did (A-46's other half). It needs a persisted
  pre-`running` status on the turn row to restore.
- **P5 (`routes/skills.py:91-94`)** — writes an edited kickoff template straight to disk with no
  validation. `prompt_builder.validate_template_source(source, prompt_builder.sample_context(stage_def))`
  now exists for exactly that call site (A-08).
