# Gate Coverage for Ungated Pipeline Stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register five deterministic gates — one each for `ideation`, `voiceover`, `music`,
`assembly`, `repurpose` — so those stages get an independent structural check before approval,
matching the pattern `scripting`/`visual`/`styleboard` already have; do it without breaking any
existing test or retroactively blocking any of the 21 already-approved rows in these five stages.

**Architecture:** Five plain functions in `pipeline-app/pipeline_app/gates.py`, each matching the
existing `GateRunner` signature (`Callable[[Path, Path, Mapping[str, Path]], list[dict]]`) and
registered in the existing `GATE_REGISTRY` dict. No new module for the gates themselves, no shared
generic table, no change to `run_gates_for_stage`'s signature or either of its two call sites. Each
gate reads its stage's `artifact_path` directly with plain string/substring checks — no external
linter module needed, since none of these five checks require real parsing (unlike Gate C/D, which
delegate to `scripts/lint_prompt_sheet.py` / `scripts/lint_script_language.py`). Two things precede
the gates themselves, both discovered necessary by adversarial review of an earlier draft of this
plan, not part of the original design: Tasks 0a-0c fix ~28 existing tests across three files that
construct an `ideation` artifact with no `gates:` key and would otherwise break the moment `ideation`
is registered; Task 0d adds one backfill migration (mirroring `migrations.backfill_styleboard_rows`'s
existing shape) that grandfathers the 21 pre-existing approved artifacts before any gate goes live.

**Tech Stack:** Python 3.14, pytest. No new dependencies.

## Global Constraints

- Spec source of truth: `docs/superpowers/specs/2026-08-16-gate-coverage-and-app-dispatched-critics-design.md`.
- Finding dict shape, exactly as every existing gate uses:
  `{"check": str, "beat": None, "shot_index": None, "kind": "fail", "message": str}`.
- Every new gate is registered in `GATE_REGISTRY` under the same name pattern the spec commits to:
  `gate_o_<stage>_contract`.
- **Registering these five gates would make every pre-existing approved artifact for these stages
  show `never_ran`/blocking on next view.** The live database has 21 already-approved rows across
  these five stages (checked directly against `pipeline.db`, not estimated), and at least some
  existing content genuinely fails the new gates' checks, not just `never_ran` — regenerating alone
  would not clear those. Task 0d backfills every existing approved artifact ahead of Tasks 1-5
  landing, so this consequence never reaches the operator as a surprise: it stamps a `"pass"`-shaped
  gate entry (the only way `classify_gates` treats a gate as non-blocking) plus a genuine, visible
  override recorded via the existing `artifacts.record_gate_override` mechanism, explaining the
  artifact predates the gate and was never actually checked against it. Real content gaps are
  surfaced on the artifact's override history, not silently hidden — but they are not force-blocked
  retroactively either. **Task 0d must land before Tasks 1-5 register any gate**, or the backfill
  runs too late to prevent the blocking state it exists to avoid.
- Test suite: `cd pipeline-app && python -m pytest` (app rootdir — never the repo root).
- Windows target platform; no behavior in this plan is platform-sensitive (plain string operations,
  no subprocess, no filesystem path manipulation beyond `Path.read_text`).

---

### Task 0a: Fix `test_approval_service.py` for the new `ideation` gate

**Files:**
- Modify: `pipeline-app/tests/test_approval_service.py`

**Interfaces:** none — test-only changes, no production code.

Registering `ideation`'s gate (Task 1) makes every artifact with no matching `gates:` entry
`never_ran`/blocking. Six existing tests in this file break — verified by actually applying Task 1's
change and running the suite. All six use stage `ideation`; none go through a shared fixture (each
hand-builds its artifact independently).

- [ ] **Step 1: Fix the four identical-pattern tests**

At lines 48, 157, 198, and 521, each builds:

```python
artifacts.write_artifact(stage_dir, 1, {"status": "draft", "stage": "shorts-ideation"}, "body")
```

Add a satisfying `gates:` entry to each of these four call sites (all four are otherwise about
approval/staleness/atomicity, not gate content):

```python
artifacts.write_artifact(
    stage_dir, 1,
    {"status": "draft", "stage": "shorts-ideation",
     "gates": [{"name": "gate_o_ideation_contract", "status": "pass", "findings": []}]},
    "body",
)
```

- [ ] **Step 2: Fix `test_regenerating_an_approved_stage_marks_approved_dependent_stale` (line 224)**

This one runs the real turn path (`turn_service.run_stage_turn`), so its fake body (`"v1 body"`)
genuinely fails the new gate — same situation the test already handles for `scripting` two lines
later. Find the ideation `approve_stage` call (around line 245):

```python
approve_stage(conn, tmp_path, run_dir, project_id, STAGES, "ideation")
```

Add the same kind of override the adjacent scripting call already uses:

```python
approve_stage(
    conn, tmp_path, run_dir, project_id, STAGES, "ideation",
    override_reason="test fixture body is not real ideation-gate input",
)
```

- [ ] **Step 3: Re-point `test_a_stage_with_no_registered_gates_still_approves_without_an_override` (line 506) at `grounding`**

Its entire premise ("`ideation` has none") is falsified by Task 1. `grounding` is the one stage this
plan keeps unregistered (spec §3) — but it resolves through a pointer, not plain
`artifacts.write_artifact`, so this needs the same construction the file's own
`test_approve_stage_grounding_resolves_artifact_via_pointer` (line 72) already uses, not a simple
stage-id swap. Replace the whole test body:

```python
def test_a_stage_with_no_registered_gates_still_approves_without_an_override(conn, tmp_path: Path):
    """The registry check must only bind stages that actually have gates.
    `grounding` has none -- it is the one stage this plan's gate-coverage
    work deliberately excludes (no path exists to attach a gate result to a
    pointer-indirected artifact) -- so an artifact with no `gates` key is
    complete, not missing anything."""
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
    assert db.get_stage(conn, project_id, "grounding")["status"] == StageStatus.APPROVED.value
```

- [ ] **Step 4: Run the file's tests**

Run: `cd pipeline-app && python -m pytest tests/test_approval_service.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/tests/test_approval_service.py
git commit -m "test(approval): satisfy the new ideation gate in existing approval-service tests"
```

---

### Task 0b: Fix `test_routes_approve_edit.py` for the new `ideation` gate

**Files:**
- Modify: `pipeline-app/tests/test_routes_approve_edit.py`

**Interfaces:** none — test-only changes.

Eleven tests break, all via the identical repeated pattern (no shared helper), all stage `ideation`:

```python
artifacts.write_artifact(ideation_dir, 1, {"stage": "shorts-ideation"}, "concept v1")
```

(or the `run_dir / "01-ideation"` form of the same call, sometimes with `"status": "draft"` also in
the dict — both variants get the same fix).

- [ ] **Step 1: Add a satisfying `gates:` entry at each of the 11 sites**

Lines: 96, 121, 138, 159, 222, 259, 296, 434, 457, 479, 729. At each, add
`"gates": [{"name": "gate_o_ideation_contract", "status": "pass", "findings": []}]` to the meta dict
literal, exactly as in Task 0a Step 1's example — same transformation, applied at each of these 11
locations. Some of these assert the ideation approve call's status code directly (`== 303`); others
leave it unasserted but a later assertion in the same test depends on ideation actually being
approved (unlocking or gating a dependent stage) — the fix is identical either way: the approve call
itself must succeed, which requires the gate to be satisfied.

- [ ] **Step 2: Run the file's tests**

Run: `cd pipeline-app && python -m pytest tests/test_routes_approve_edit.py -v`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add pipeline-app/tests/test_routes_approve_edit.py
git commit -m "test(routes): satisfy the new ideation gate in existing approve/edit route tests"
```

---

### Task 0c: Fix `test_routes_stages.py` for the new `ideation` gate

**Files:**
- Modify: `pipeline-app/tests/test_routes_stages.py`

**Interfaces:** none — test-only changes.

- [ ] **Step 1: Fix the 4 single tests plus the 8-way parametrize's ideation setup**

Lines 986, 1193, 1216, and the shared ideation setup inside the parametrized
`test_the_page_flag_the_per_gate_tag_and_the_approve_decision_never_disagree` (1159, whose ideation
approve happens once before the 8 parametrized cases at line ~1170) all use the same pattern already
shown in Task 0b Step 1:

```python
artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
assert test_client.post(f"/projects/{project_id}/stages/ideation/approve").status_code == 303
```

Add the same `"gates": [{"name": "gate_o_ideation_contract", "status": "pass", "findings": []}]`
entry to each of these 4 call sites.

- [ ] **Step 2: Fix `test_stage_page_hides_stale_override_cue_for_non_stale_stage` (line 415)**

Different shape — this test builds no artifact at all, only a `GET`. Once `ideation` is registered,
an artifact-less ideation page also synthesizes a blocking `never_ran` entry, so the override text
this test asserts is absent would now appear — not because the test's real intent (no override cue
on a healthy, non-stale stage) is wrong, but because "no artifact" no longer coincidentally implies
"nothing blocking." Give it a real, passing artifact instead of relying on that coincidence:

```python
def test_stage_page_hides_stale_override_cue_for_non_stale_stage(client):
    test_client, tmp_path, app = client
    project_id = _generic_project_id(test_client)
    project = db_mod.get_project(app.state.conn, project_id)
    run_dir = tmp_path / "runs" / project["run_id"]
    artifacts.write_artifact(
        run_dir / "01-ideation", 1,
        {"stage": "shorts-ideation",
         "gates": [{"name": "gate_o_ideation_contract", "status": "pass", "findings": []}]},
        "concept v1",
    )

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "override" not in page.text.lower()
```

- [ ] **Step 3: Run the file's tests**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/tests/test_routes_stages.py
git commit -m "test(routes): satisfy the new ideation gate in existing stage-page tests"
```

---

### Task 0d: Backfill existing approved artifacts so they don't retroactively block

**Files:**
- Modify: `pipeline-app/pipeline_app/migrations.py` (add function, call it from `main.py`'s startup sequence)
- Modify: `pipeline-app/pipeline_app/main.py` (one line, in `create_app`)
- Test: `pipeline-app/tests/test_migrations.py`

**Interfaces:**
- Produces: `backfill_gate_coverage_artifacts(conn: sqlite3.Connection, repo_root: Path, stage_defs: list[StageDef]) -> list[str]` (returns the relative artifact paths it touched, mirroring `backfill_styleboard_rows`'s `list[int]` return-what-was-touched convention).
- Consumes: `artifacts.resolve_latest_artifact`, `artifacts.read_artifact`, `artifacts.record_gate_override`, `db.get_stage`, `db.list_projects` (all existing).

The live database (checked directly) has 21 already-approved rows across `ideation`/`voiceover`/
`music`/`assembly`/`repurpose` — not a number small enough to hand-wave. Per the chosen approach: for
every approved artifact in these five stages, stamp its `gates:` list with a `"pass"`-shaped entry
for the newly-registered gate (the only way `classify_gates` treats a gate as non-blocking) **and**
record a genuine, visible override explaining why, via `artifacts.record_gate_override` — the exact
mechanism this codebase already uses to keep an override auditable on the stage page
(`read_gate_overrides`/`gate_overrides` history). This is not the same as actually passing the gate:
content that would fail it stays failing-looking to a human who checks the override note, it is simply
not force-blocked retroactively.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migrations.py
def test_backfill_gate_coverage_stamps_existing_approved_artifacts(conn, tmp_path):
    from pipeline_app import artifacts, db, migrations
    from pipeline_app.pipeline_config import StageDef

    stage_defs = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-08-06T00:00:00Z")
    row = db.create_stage_row(conn, project_id, "ideation", "approved")
    run_dir = tmp_path / "runs" / "abc-1"
    stage_dir = run_dir / "01-ideation"
    path = artifacts.write_artifact(
        stage_dir, 1, {"status": "final", "stage": "shorts-ideation"}, "old body",
    )

    touched = migrations.backfill_gate_coverage_artifacts(conn, tmp_path, stage_defs)

    assert str(path.relative_to(tmp_path)).replace("\\", "/") in touched
    meta, _ = artifacts.read_artifact(path)
    gate_names = [g["name"] for g in meta["gates"]]
    assert "gate_o_ideation_contract" in gate_names
    passed = next(g for g in meta["gates"] if g["name"] == "gate_o_ideation_contract")
    assert passed["status"] == "pass"
    overrides = artifacts.read_gate_overrides(path)
    assert len(overrides) == 1
    assert "gate-coverage migration" in overrides[0]["reason"]


def test_backfill_gate_coverage_is_idempotent(conn, tmp_path):
    from pipeline_app import artifacts, db, migrations
    from pipeline_app.pipeline_config import StageDef

    stage_defs = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-08-06T00:00:00Z")
    db.create_stage_row(conn, project_id, "ideation", "approved")
    run_dir = tmp_path / "runs" / "abc-1"
    artifacts.write_artifact(
        run_dir / "01-ideation", 1, {"status": "final", "stage": "shorts-ideation"}, "old body",
    )

    migrations.backfill_gate_coverage_artifacts(conn, tmp_path, stage_defs)
    second_run = migrations.backfill_gate_coverage_artifacts(conn, tmp_path, stage_defs)

    assert second_run == []  # already-stamped artifacts are not touched twice
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline-app && python -m pytest tests/test_migrations.py -k backfill_gate_coverage -v`
Expected: FAIL — `AttributeError: module 'migrations' has no attribute 'backfill_gate_coverage_artifacts'`.

- [ ] **Step 3: Implement**

In `migrations.py`, following `backfill_styleboard_rows`'s existing per-project loop shape:

```python
# The five gates Task 1-5 register, mapped to the check they satisfy on
# backfill. Kept here rather than importing gates.GATE_REGISTRY: this
# migration must know exactly which entries IT is responsible for stamping,
# independent of whatever the registry grows to later.
GATE_COVERAGE_STAGE_GATES = {
    "ideation": "gate_o_ideation_contract",
    "voiceover": "gate_o_voiceover_contract",
    "music": "gate_o_music_contract",
    "assembly": "gate_o_assembly_contract",
    "repurpose": "gate_o_repurpose_contract",
}


def backfill_gate_coverage_artifacts(
    conn: sqlite3.Connection, repo_root: Path, stage_defs: list[StageDef],
) -> list[str]:
    """Grandfather every already-approved artifact in the five newly-gated
    stages so registering their gates does not retroactively block them.

    Stamps a pass-shaped entry (the only way classify_gates treats a gate as
    non-blocking) plus a genuine, visible override via
    artifacts.record_gate_override -- the artifact's real content is never
    re-checked against the new gate, and the override note says so, rather
    than silently pretending it was verified.

    Idempotent: skips any artifact whose gates list already names the
    relevant gate, so a repeat run (every app startup) touches nothing after
    the first.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    touched: list[str] = []
    by_id = {s.id: s for s in stage_defs}

    for project in db_mod.list_projects(conn):
        for stage_id, gate_name in GATE_COVERAGE_STAGE_GATES.items():
            stage_def = by_id.get(stage_id)
            if stage_def is None:
                continue
            row = db_mod.get_stage(conn, project["id"], stage_id)
            if row is None or row["status"] != StageStatus.APPROVED.value:
                continue
            stage_dir = repo_root / "runs" / project["run_id"] / stage_dir_name(stage_def)
            latest = artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir)
            if latest is None:
                continue
            meta, _body = artifacts.read_artifact(latest)
            existing_names = {g.get("name") for g in (meta.get("gates") or [])}
            if gate_name in existing_names:
                continue
            meta.setdefault("gates", []).append(
                {"name": gate_name, "status": "pass", "findings": []}
            )
            artifacts._atomic_write_text(latest, artifacts.render_frontmatter(meta, _body))
            artifacts.record_gate_override(
                latest,
                f"grandfathered by the 2026-08-16 gate-coverage migration -- approved before "
                f"{gate_name!r} existed; content was never checked against it",
                at=now,
            )
            touched.append(str(latest.relative_to(repo_root)).replace("\\", "/"))
    return touched
```

- [ ] **Step 4: Run to verify pass**

Run: `cd pipeline-app && python -m pytest tests/test_migrations.py -k backfill_gate_coverage -v`
Expected: both PASS.

- [ ] **Step 5: Wire it into startup, alongside the existing styleboard backfill**

In `main.py`'s `create_app`, immediately after the existing line
`app.state.backfilled_projects = migrations.backfill_styleboard_rows(...)`, add:

```python
app.state.gate_coverage_backfilled = migrations.backfill_gate_coverage_artifacts(
    app.state.conn, app.state.repo_root, app.state.stage_defs
)
```

- [ ] **Step 6: Run the full app test suite**

Run: `cd pipeline-app && python -m pytest -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/pipeline_app/migrations.py pipeline-app/pipeline_app/main.py pipeline-app/tests/test_migrations.py
git commit -m "feat(migrations): backfill existing approved artifacts ahead of gate coverage"
```

---

### Task 1: `ideation` — `gate_o_ideation_contract`

**Files:**
- Modify: `pipeline-app/pipeline_app/gates.py` (add function above `GATE_REGISTRY`, add registry entry)
- Modify: `pipeline-app/tests/test_gates.py` (add tests; fix one pre-existing test — see Step 1)

**Interfaces:**
- Produces: `run_ideation_contract_gate(repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]) -> list[dict]`
- Consumes: nothing from earlier tasks (first task in this plan).

The concept brief's required headings, verified against `shorts-ideation/SKILL.md:143-178`:
`## Angle / take`, `## Hook concept`, `## Packaging direction`, `## Validation`, `## Handoff`.
`## Grounding` is genuinely conditional — the skill's own template heading text is literally
`## Grounding (omit this section entirely if no companion artifact was provided)` — so its absence is
never checked or flagged.

- [ ] **Step 1: Fix the pre-existing test that assumes `ideation` is unregistered, and write the failing tests for the new gate**

`test_gates.py:232-234` currently reads:

```python
def test_unregistered_stage_returns_no_results(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("anything\n", encoding="utf-8")
    assert gates.run_gates_for_stage(REPO_ROOT, "ideation", path, {}) == []
```

This task registers `ideation`, so this test's premise breaks. `grounding` is the one stage this
plan's spec explicitly keeps unregistered (see spec §3) and will stay that way — swap the stage id:

```python
def test_unregistered_stage_returns_no_results(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("anything\n", encoding="utf-8")
    assert gates.run_gates_for_stage(REPO_ROOT, "grounding", path, {}) == []
```

Then append the new gate's tests to `test_gates.py`:

```python
IDEATION_HEADINGS = (
    "## Angle / take\n[body]\n\n"
    "## Hook concept\n[body]\n\n"
    "## Packaging direction\n[body]\n\n"
    "## Validation\n[body]\n\n"
    "## Handoff\n[body]\n"
)


def test_ideation_stage_is_registered():
    assert "ideation" in gates.GATE_REGISTRY


def test_ideation_gate_passes_a_complete_brief(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(IDEATION_HEADINGS, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "ideation", path, {})
    assert len(results) == 1
    assert results[0]["name"] == "gate_o_ideation_contract"
    assert results[0]["status"] == "pass"
    assert results[0]["findings"] == []


def test_ideation_gate_flags_a_missing_required_heading(tmp_path):
    path = tmp_path / "raw_output.md"
    text = IDEATION_HEADINGS.replace("## Validation\n[body]\n\n", "")
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "ideation", path, {})
    assert results[0]["status"] == "fail"
    checks = [f["check"] for f in results[0]["findings"]]
    assert "OI1" in checks or "OI2" in checks or "OI3" in checks or "OI4" in checks
    assert any("Validation" in f["message"] for f in results[0]["findings"])


def test_ideation_gate_does_not_require_the_conditional_grounding_section(tmp_path):
    """IDEATION_HEADINGS already omits '## Grounding' entirely -- confirms
    its absence alone, with every required heading present, still passes."""
    path = tmp_path / "raw_output.md"
    path.write_text(IDEATION_HEADINGS, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "ideation", path, {})
    assert results[0]["status"] == "pass"
```

- [ ] **Step 2: Run the new tests to verify they fail for the right reason**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k ideation -v`
Expected: FAIL, in two different ways since `ideation` isn't registered yet and
`run_gates_for_stage` returns `[]`: `test_ideation_stage_is_registered` and
`test_ideation_gate_passes_a_complete_brief` fail with a clean `AssertionError`
(`"ideation" not in GATE_REGISTRY` / `len(results) == 1` → `0 == 1`, since both assert length before
indexing); `test_ideation_gate_flags_a_missing_required_heading` and
`test_ideation_gate_does_not_require_the_conditional_grounding_section` fail with `IndexError: list
index out of range` on `results[0]`, since neither asserts length first. Both are the correct "fails
for the right reason" signal — an unregistered stage producing no results. Also run
`python -m pytest tests/test_gates.py -k test_unregistered_stage_returns_no_results -v` and confirm
it now passes against `"grounding"`.

- [ ] **Step 3: Implement the gate**

In `gates.py`, add above the `GATE_REGISTRY` definition:

```python
IDEATION_REQUIRED_HEADINGS = (
    "## Angle / take",
    "## Hook concept",
    "## Packaging direction",
    "## Validation",
    "## Handoff",
)


def run_ideation_contract_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    """Gate O-I: the concept brief's required sections are present.
    `## Grounding` is genuinely conditional per shorts-ideation/SKILL.md's
    own template ("omit this section entirely if no companion artifact was
    provided") -- its absence is never checked."""
    lines = {line.strip() for line in artifact_path.read_text(encoding="utf-8").splitlines()}
    return [
        {
            "check": f"OI{i + 1}", "beat": None, "shot_index": None, "kind": "fail",
            "message": f"{artifact_path.name} is missing the required {heading!r} section.",
        }
        for i, heading in enumerate(IDEATION_REQUIRED_HEADINGS)
        if heading not in lines
    ]
```

Add to `GATE_REGISTRY`:

```python
GATE_REGISTRY: dict[str, list[tuple[str, GateRunner]]] = {
    "scripting": [("gate_d_script_language", run_script_language_gate)],
    "visual": [("gate_c_prompt_sheet", run_prompt_sheet_gate)],
    "styleboard": [("gate_s_styleboard", run_styleboard_gate)],
    "ideation": [("gate_o_ideation_contract", run_ideation_contract_gate)],
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k "ideation or unregistered" -v`
Expected: all PASS.

- [ ] **Step 5: Run the full gates test file to confirm nothing else broke**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/gates.py pipeline-app/tests/test_gates.py
git commit -m "feat(gates): register Gate O-I, the ideation output-contract gate"
```

---

### Task 2: `voiceover` — `gate_o_voiceover_contract`

**Files:**
- Modify: `pipeline-app/pipeline_app/gates.py`
- Modify: `pipeline-app/tests/test_gates.py`

**Interfaces:**
- Produces: `run_voiceover_contract_gate(repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]) -> list[dict]`
- Consumes: nothing from Task 1 (independent stage).

Required headings, verified against `voiceover-brief/SKILL.md:90-103`: `## Voice pick`,
`## Settings`, `` ## Script, reformatted for TTS `` (comma included — this is the literal heading
text), `## Production & loudness`, `## Downstream`. All five are mandatory — no conditional section
exists for this stage.

- [ ] **Step 1: Write the failing tests**

```python
VOICEOVER_HEADINGS = (
    "## Voice pick\n[body]\n\n"
    "## Settings\n[body]\n\n"
    "## Script, reformatted for TTS\n[body]\n\n"
    "## Production & loudness\n[body]\n\n"
    "## Downstream\n[body]\n"
)


def test_voiceover_stage_is_registered():
    assert "voiceover" in gates.GATE_REGISTRY


def test_voiceover_gate_passes_a_complete_brief(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(VOICEOVER_HEADINGS, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "voiceover", path, {})
    assert len(results) == 1
    assert results[0]["name"] == "gate_o_voiceover_contract"
    assert results[0]["status"] == "pass"


def test_voiceover_gate_requires_the_literal_comma_in_the_tts_heading(tmp_path):
    """The heading is '## Script, reformatted for TTS' with a comma -- a
    brief that drops it must fail, not silently pass on a near-miss."""
    path = tmp_path / "raw_output.md"
    text = VOICEOVER_HEADINGS.replace(
        "## Script, reformatted for TTS", "## Script reformatted for TTS"
    )
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "voiceover", path, {})
    assert results[0]["status"] == "fail"
    assert any("reformatted for TTS" in f["message"] for f in results[0]["findings"])


def test_voiceover_gate_flags_a_missing_downstream_section(tmp_path):
    path = tmp_path / "raw_output.md"
    text = VOICEOVER_HEADINGS.replace("## Downstream\n[body]\n", "")
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "voiceover", path, {})
    assert results[0]["status"] == "fail"


def test_voiceover_gate_does_not_require_non_empty_section_bodies(tmp_path):
    """The gate checks structure (all five headings present), not content
    quality -- a thin body under a present heading is legitimately valid,
    not a fault, and must not be conflated with a missing section."""
    path = tmp_path / "raw_output.md"
    thin = (
        "## Voice pick\n\n## Settings\n\n## Script, reformatted for TTS\n\n"
        "## Production & loudness\n\n## Downstream\n"
    )
    path.write_text(thin, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "voiceover", path, {})
    assert results[0]["status"] == "pass"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k voiceover -v`
Expected: FAIL for every test — `"voiceover" not in GATE_REGISTRY`, `0 == 1` on the length-checked
tests, `IndexError` on the two tests (comma-heading, missing-Downstream) that index `results[0]`
without a length check first. All are the correct "unregistered stage" signal.

- [ ] **Step 3: Implement**

```python
VOICEOVER_REQUIRED_HEADINGS = (
    "## Voice pick",
    "## Settings",
    "## Script, reformatted for TTS",
    "## Production & loudness",
    "## Downstream",
)


def run_voiceover_contract_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    """Gate O-V: the voiceover brief's five required sections are present,
    all mandatory -- voiceover-brief/SKILL.md:90-103 has no conditional
    section."""
    lines = {line.strip() for line in artifact_path.read_text(encoding="utf-8").splitlines()}
    return [
        {
            "check": f"OV{i + 1}", "beat": None, "shot_index": None, "kind": "fail",
            "message": f"{artifact_path.name} is missing the required {heading!r} section.",
        }
        for i, heading in enumerate(VOICEOVER_REQUIRED_HEADINGS)
        if heading not in lines
    ]
```

Add to `GATE_REGISTRY`: `"voiceover": [("gate_o_voiceover_contract", run_voiceover_contract_gate)],`

- [ ] **Step 4: Run to verify pass**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k voiceover -v`
Expected: all PASS.

- [ ] **Step 5: Full file regression check**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/gates.py pipeline-app/tests/test_gates.py
git commit -m "feat(gates): register Gate O-V, the voiceover output-contract gate"
```

---

### Task 3: `music` — `gate_o_music_contract`

**Files:**
- Modify: `pipeline-app/pipeline_app/gates.py`
- Modify: `pipeline-app/tests/test_gates.py`

**Interfaces:**
- Produces: `run_music_contract_gate(repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]) -> list[dict]`
- Consumes: nothing from Tasks 1-2.

Required headings, verified against `music-brief/SKILL.md:62-80`: `## Bed arc`, `## Hook hold-out`,
`## Tone-contradiction check`, `## Deferred to elevenlabs-music`, `## Downstream`. Five sections, all
mandatory — the second adversarial review of the design spec caught an earlier draft omitting
`## Downstream`; it is included here.

- [ ] **Step 1: Write the failing tests**

```python
MUSIC_HEADINGS = (
    "## Bed arc\n[body]\n\n"
    "## Hook hold-out\n[body]\n\n"
    "## Tone-contradiction check\n[body]\n\n"
    "## Deferred to elevenlabs-music\n[body]\n\n"
    "## Downstream\n[body]\n"
)


def test_music_stage_is_registered():
    assert "music" in gates.GATE_REGISTRY


def test_music_gate_passes_a_complete_brief(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(MUSIC_HEADINGS, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "music", path, {})
    assert len(results) == 1
    assert results[0]["name"] == "gate_o_music_contract"
    assert results[0]["status"] == "pass"


def test_music_gate_flags_a_missing_tone_contradiction_check(tmp_path):
    path = tmp_path / "raw_output.md"
    text = MUSIC_HEADINGS.replace("## Tone-contradiction check\n[body]\n\n", "")
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "music", path, {})
    assert results[0]["status"] == "fail"
    assert any("Tone-contradiction check" in f["message"] for f in results[0]["findings"])


def test_music_gate_flags_all_five_missing_sections_independently(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text("nothing here\n", encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "music", path, {})
    assert results[0]["status"] == "fail"
    assert len(results[0]["findings"]) == 5


def test_music_gate_does_not_require_non_empty_section_bodies(tmp_path):
    """Structure only, not content quality -- a thin body under a present
    heading is legitimately valid and must not read as a fault."""
    path = tmp_path / "raw_output.md"
    thin = (
        "## Bed arc\n\n## Hook hold-out\n\n## Tone-contradiction check\n\n"
        "## Deferred to elevenlabs-music\n\n## Downstream\n"
    )
    path.write_text(thin, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "music", path, {})
    assert results[0]["status"] == "pass"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k music -v`
Expected: FAIL for every test — `"music" not in GATE_REGISTRY`, `0 == 1` on the length-checked test,
`IndexError` on the two tests that index `results[0]` without a length check first. All are the
correct "unregistered stage" signal.

- [ ] **Step 3: Implement**

```python
MUSIC_REQUIRED_HEADINGS = (
    "## Bed arc",
    "## Hook hold-out",
    "## Tone-contradiction check",
    "## Deferred to elevenlabs-music",
    "## Downstream",
)


def run_music_contract_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    """Gate O-M: the bed-arc brief's five required sections are present."""
    lines = {line.strip() for line in artifact_path.read_text(encoding="utf-8").splitlines()}
    return [
        {
            "check": f"OM{i + 1}", "beat": None, "shot_index": None, "kind": "fail",
            "message": f"{artifact_path.name} is missing the required {heading!r} section.",
        }
        for i, heading in enumerate(MUSIC_REQUIRED_HEADINGS)
        if heading not in lines
    ]
```

Add to `GATE_REGISTRY`: `"music": [("gate_o_music_contract", run_music_contract_gate)],`

- [ ] **Step 4: Run to verify pass**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k music -v`
Expected: all PASS.

- [ ] **Step 5: Full file regression check**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/gates.py pipeline-app/tests/test_gates.py
git commit -m "feat(gates): register Gate O-M, the music output-contract gate"
```

---

### Task 4: `assembly` — `gate_o_assembly_contract`

**Files:**
- Modify: `pipeline-app/pipeline_app/gates.py`
- Modify: `pipeline-app/tests/test_gates.py`

**Interfaces:**
- Produces: `run_assembly_contract_gate(repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]) -> list[dict]`
- Consumes: nothing from Tasks 1-3.

`shorts-assembly/SKILL.md` has no `##`-heading output template — verified at
`shorts-assembly/SKILL.md:57-88`. Its "Writing the plan for a real request" section (`:72-81`)
mandates five checkable content elements instead of headings: an aspect-ratio statement (checked via
the substring `"1080"`, per step 4's "State the aspect ratio (1080×1920, 9:16)"), a loudness target
(checked via the substring `"LUFS"`, per step 5's "State the loudness targets"), **both** a $0 and a
paid tool-stack path (checked via the case-insensitive substrings `"$0"` and `"paid"`, per step 6 —
an earlier draft of this gate implemented four of these five elements and dropped this one), the
QA-gate + publish-gate checklist (checked via a case-insensitive regex `qa[\s-]?gate`, **not** a
literal `"qa-gate"` substring — verified against real assembly artifacts on disk, which write
"QA gate" with a space, never a hyphen; the hyphenated form appears only in the skill's own prose,
never in emitted output, so a literal-hyphen check would reject every real artifact), and the
explicit hand-off statement naming `social-repurpose` (checked via the substring
`"social-repurpose"`, per step 8). These are content/keyword checks, not a parser — matching the
spec's explicit call that assembly's contract needs keyword-presence checking, not heading structure.

- [ ] **Step 1: Write the failing tests**

```python
import re

COMPLETE_ASSEMBLY_PLAN = (
    "Shot-by-shot table: [rows]\n\n"
    "Aspect ratio: 1080x1920 (9:16).\n\n"
    "Loudness target: -14 LUFS, ducking to -22 dB under voice.\n\n"
    "$0 stack: CapCut. Paid stack: Premiere Pro.\n\n"
    "Run the QA gate + publish gate checklist before scheduling.\n\n"
    "This edit plan feeds social-repurpose next.\n"
)


def test_assembly_stage_is_registered():
    assert "assembly" in gates.GATE_REGISTRY


def test_assembly_gate_passes_a_complete_plan(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(COMPLETE_ASSEMBLY_PLAN, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "assembly", path, {})
    assert len(results) == 1
    assert results[0]["name"] == "gate_o_assembly_contract"
    assert results[0]["status"] == "pass"


def test_assembly_gate_flags_a_missing_aspect_ratio_statement(tmp_path):
    path = tmp_path / "raw_output.md"
    text = COMPLETE_ASSEMBLY_PLAN.replace("Aspect ratio: 1080x1920 (9:16).\n\n", "")
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "assembly", path, {})
    assert results[0]["status"] == "fail"
    assert any("aspect ratio" in f["message"].lower() for f in results[0]["findings"])


def test_assembly_gate_flags_a_missing_zero_dollar_stack(tmp_path):
    path = tmp_path / "raw_output.md"
    text = COMPLETE_ASSEMBLY_PLAN.replace("$0 stack: CapCut. Paid stack: Premiere Pro.\n\n", "")
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "assembly", path, {})
    assert results[0]["status"] == "fail"
    assert any("$0" in f["message"] for f in results[0]["findings"])


def test_assembly_gate_matches_the_real_unhyphenated_qa_gate_wording(tmp_path):
    """Real assembly artifacts write 'QA gate' with a space -- a check for
    the literal hyphenated 'qa-gate' would reject every correct one."""
    path = tmp_path / "raw_output.md"
    path.write_text(COMPLETE_ASSEMBLY_PLAN, encoding="utf-8")  # already uses "QA gate"
    results = gates.run_gates_for_stage(REPO_ROOT, "assembly", path, {})
    assert results[0]["status"] == "pass"


def test_assembly_gate_flags_a_missing_qa_gate_checklist(tmp_path):
    path = tmp_path / "raw_output.md"
    text = COMPLETE_ASSEMBLY_PLAN.replace(
        "Run the QA gate + publish gate checklist before scheduling.\n\n", ""
    )
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "assembly", path, {})
    assert results[0]["status"] == "fail"
    assert any("QA-gate" in f["message"] for f in results[0]["findings"])


def test_assembly_gate_flags_a_missing_repurpose_handoff(tmp_path):
    path = tmp_path / "raw_output.md"
    text = COMPLETE_ASSEMBLY_PLAN.replace("This edit plan feeds social-repurpose next.\n", "")
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "assembly", path, {})
    assert results[0]["status"] == "fail"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k assembly -v`
Expected: FAIL for every test — `"assembly" not in GATE_REGISTRY`, `0 == 1` on the length-checked
tests, `IndexError` on the tests that index `results[0]` without a length check first (every "flags a
missing X" test). All are the correct "unregistered stage" signal.

- [ ] **Step 3: Implement**

```python
def run_assembly_contract_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    """Gate O-A: shorts-assembly/SKILL.md has no heading template
    (verified :57-88), so this checks the five content elements its
    'Writing the plan for a real request' section (:72-81) actually
    mandates, by keyword presence. The QA-checklist check is a regex, not a
    literal substring: real assembly artifacts write "QA gate" with a
    space, never the hyphenated "qa-gate" the skill's own prose uses."""
    text = artifact_path.read_text(encoding="utf-8")
    checks = [
        ("OA1", "1080" in text, "an aspect-ratio statement (e.g. 1080x1920 / 9:16)"),
        ("OA2", "LUFS" in text, "a stated loudness target (LUFS)"),
        ("OA3", "$0" in text and "paid" in text.lower(),
         "both a $0 and a paid tool-stack path"),
        ("OA4", re.search(r"qa[\s-]?gate", text, re.IGNORECASE) is not None,
         "the QA-gate + publish-gate checklist"),
        ("OA5", "social-repurpose" in text, "the explicit hand-off to social-repurpose"),
    ]
    return [
        {
            "check": code, "beat": None, "shot_index": None, "kind": "fail",
            "message": f"{artifact_path.name} is missing {description}.",
        }
        for code, present, description in checks
        if not present
    ]
```

`gates.py` does not import `re` today (verified — its current imports are `asyncio`,
`importlib.util`, `sys`, `collections.abc.Mapping`, `dataclasses`, `pathlib.Path`,
`typing.Any`/`Callable`, plus `pipeline_app.artifacts`/`obs`/`pipeline_config`). Add `import re` to
that block.

Add to `GATE_REGISTRY`: `"assembly": [("gate_o_assembly_contract", run_assembly_contract_gate)],`

- [ ] **Step 4: Run to verify pass**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k assembly -v`
Expected: all PASS.

- [ ] **Step 5: Full file regression check**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/gates.py pipeline-app/tests/test_gates.py
git commit -m "feat(gates): register Gate O-A, the assembly output-contract gate"
```

---

### Task 5: `repurpose` — `gate_o_repurpose_contract`

**Files:**
- Modify: `pipeline-app/pipeline_app/gates.py`
- Modify: `pipeline-app/tests/test_gates.py`

**Interfaces:**
- Produces: `run_repurpose_contract_gate(repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]) -> list[dict]`
- Consumes: nothing from Tasks 1-4.

`social-repurpose/SKILL.md:98-101` fixes a real package structure without fixed headings: the YouTube
block appears first, followed by one block per requested platform, and every caption carries a
provenance marker. Checked as: the substring `"YouTube"` occurs before the first occurrence of any
other named platform (`TikTok`, `Instagram`, `X`, `Bluesky`, `Threads` — the platform list named in
`social-repurpose/SKILL.md`'s own scope), and at least one provenance marker (`[C]`, `[I]`, `[T]`,
`[C→I]`, or `[gap]`) appears somewhere in the body. `X` is matched as a **whole word** (`\bX\b`), not
a bare substring — a plain `text.find("X")` would false-positive on any capital X appearing anywhere
before the YouTube block for an unrelated reason (inside a word, a title in all-caps, etc.); the other
four platform names are long enough that this risk doesn't apply to them, so only `X` needs the
word-boundary treatment.

- [ ] **Step 1: Write the failing tests**

```python
COMPLETE_REPURPOSE_PACKAGE = (
    "## YouTube\nTitle: [C] grounded in the corpus.\n\n"
    "## TikTok\nCaption: [I] extrapolated.\n\n"
    "## Instagram\nCaption: [gap] no corpus coverage here.\n"
)


def test_repurpose_stage_is_registered():
    assert "repurpose" in gates.GATE_REGISTRY


def test_repurpose_gate_passes_a_complete_package(tmp_path):
    path = tmp_path / "raw_output.md"
    path.write_text(COMPLETE_REPURPOSE_PACKAGE, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "repurpose", path, {})
    assert len(results) == 1
    assert results[0]["name"] == "gate_o_repurpose_contract"
    assert results[0]["status"] == "pass"


def test_repurpose_gate_flags_youtube_not_appearing_first(tmp_path):
    path = tmp_path / "raw_output.md"
    text = "## TikTok\nCaption: [I] extrapolated.\n\n## YouTube\nTitle: [C] grounded.\n"
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "repurpose", path, {})
    assert results[0]["status"] == "fail"
    assert any("YouTube" in f["message"] for f in results[0]["findings"])


def test_repurpose_gate_does_not_false_positive_on_a_capital_x_before_youtube(tmp_path):
    """A bare substring search for 'X' would wrongly flag this as X-before-
    YouTube; 'MAX' and 'EXPLAINED' both contain a capital X that has nothing
    to do with the X/Twitter platform."""
    path = tmp_path / "raw_output.md"
    text = (
        "MAX EXPLAINED: the concept in one line.\n\n"
        "## YouTube\nTitle: [C] grounded.\n\n## TikTok\nCaption: [I] extrapolated.\n"
    )
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "repurpose", path, {})
    assert results[0]["status"] == "pass"


def test_repurpose_gate_flags_no_provenance_marker_anywhere(tmp_path):
    path = tmp_path / "raw_output.md"
    text = "## YouTube\nTitle: a great video.\n\n## TikTok\nCaption: also great.\n"
    path.write_text(text, encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "repurpose", path, {})
    assert results[0]["status"] == "fail"
    assert any("provenance marker" in f["message"] for f in results[0]["findings"])


def test_repurpose_gate_passes_a_youtube_only_package(tmp_path):
    """No other platform requested -- YouTube-first is vacuously true, and
    the gate must not demand a platform block that was never asked for."""
    path = tmp_path / "raw_output.md"
    path.write_text("## YouTube\nTitle: [C] grounded.\n", encoding="utf-8")
    results = gates.run_gates_for_stage(REPO_ROOT, "repurpose", path, {})
    assert results[0]["status"] == "pass"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k repurpose -v`
Expected: FAIL for every test — `"repurpose" not in GATE_REGISTRY`, `0 == 1` on the length-checked
tests, `IndexError` on the tests that index `results[0]` without a length check first (every "flags"
test and the capital-X test). All are the correct "unregistered stage" signal.

- [ ] **Step 3: Implement**

```python
_REPURPOSE_OTHER_PLATFORMS = ("TikTok", "Instagram", "X", "Bluesky", "Threads")
_PROVENANCE_MARKERS = ("[C]", "[I]", "[T]", "[C→I]", "[gap]")


def _first_platform_index(text: str, platform: str) -> int:
    """`X` must match as a whole word (\\bX\\b) -- a bare substring search
    would false-positive on any capital X appearing before the YouTube
    block for an unrelated reason (inside a word, an all-caps title). The
    other four platform names are long enough that this risk doesn't apply
    to them, so only X needs the word-boundary treatment."""
    if platform == "X":
        match = re.search(r"\bX\b", text)
        return match.start() if match else -1
    return text.find(platform)


def run_repurpose_contract_gate(
    repo_root: Path, artifact_path: Path, upstream: Mapping[str, Path]
) -> list[dict]:
    """Gate O-R: social-repurpose/SKILL.md:98-101 fixes YouTube-block-first
    package ordering and per-caption provenance markers, not a heading set."""
    text = artifact_path.read_text(encoding="utf-8")
    findings: list[dict] = []

    youtube_index = text.find("YouTube")
    if youtube_index != -1:
        for platform in _REPURPOSE_OTHER_PLATFORMS:
            platform_index = _first_platform_index(text, platform)
            if platform_index != -1 and platform_index < youtube_index:
                findings.append({
                    "check": "OR1", "beat": None, "shot_index": None, "kind": "fail",
                    "message": (
                        f"{artifact_path.name}: {platform!r} appears before 'YouTube' -- the "
                        "package must lead with the YouTube block."
                    ),
                })
                break
    else:
        findings.append({
            "check": "OR1", "beat": None, "shot_index": None, "kind": "fail",
            "message": f"{artifact_path.name} has no YouTube block at all.",
        })

    if not any(marker in text for marker in _PROVENANCE_MARKERS):
        findings.append({
            "check": "OR2", "beat": None, "shot_index": None, "kind": "fail",
            "message": (
                f"{artifact_path.name} carries no provenance marker "
                f"({', '.join(_PROVENANCE_MARKERS)}) anywhere in the body."
            ),
        })
    return findings
```

Uses the same `import re` this plan already adds to `gates.py` in Task 4 — if tasks are executed out
of order, add it here instead; either location satisfies both.

Add to `GATE_REGISTRY`: `"repurpose": [("gate_o_repurpose_contract", run_repurpose_contract_gate)],`

- [ ] **Step 4: Run to verify pass**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k repurpose -v`
Expected: all PASS.

- [ ] **Step 5: Full file regression check**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/gates.py pipeline-app/tests/test_gates.py
git commit -m "feat(gates): register Gate O-R, the repurpose output-contract gate"
```

---

### Task 6: Full-suite regression and registry-shape confirmation

**Files:**
- Modify: `pipeline-app/tests/test_gates.py` (one final cross-gate test; no production code changes)

**Interfaces:**
- Consumes: all five gates registered by Tasks 1-5.
- Produces: nothing further downstream — this is the plan's closing verification task.

- [ ] **Step 1: Write the failing test**

```python
def test_all_five_new_stages_are_registered_and_grounding_still_is_not():
    for stage_id in ("ideation", "voiceover", "music", "assembly", "repurpose"):
        assert stage_id in gates.GATE_REGISTRY, f"{stage_id} should be registered"
    assert "grounding" not in gates.GATE_REGISTRY, (
        "grounding is explicitly out of scope per the design spec §3 -- it has no path "
        "to attach a gate result (finalize_artifact=False), and registering one would "
        "block every grounding approval forever"
    )
```

- [ ] **Step 2: Run to verify it passes immediately**

Run: `cd pipeline-app && python -m pytest tests/test_gates.py -k test_all_five_new_stages -v`
Expected: PASS (this is a closing confirmation, not new behavior — if it fails, an earlier task's
registration was missed or reverted).

- [ ] **Step 3: Run the full app test suite**

Run: `cd pipeline-app && python -m pytest -v`
Expected: all PASS. Task 0d Step 6 already ran this suite once, before any gate was registered, to
confirm the backfill migration alone didn't break anything; this run is the real end-to-end
confirmation — every one of Tasks 0a-0d's fixes and Tasks 1-5's registrations together, against
`routes/stages.py`, `turn_service.py`, and `approval_service.py` (which all consume `GATE_REGISTRY`
indirectly through `classify_gates`/`gate_view`).

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/tests/test_gates.py
git commit -m "test(gates): confirm all five stages registered, grounding still excluded"
```

Plan complete. Task 0d already resolved every pre-existing approved artifact's exposure to
retroactive blocking before Tasks 1-5 landed — nothing further is owed to the operator here beyond
what Task 0d's own commit message and Global Constraints already record.
