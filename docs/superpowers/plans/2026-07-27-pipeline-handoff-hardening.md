# Pipeline Handoff Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the correctness and fragility gaps an Opus code review found in `pipeline-app`'s stage-handoff machinery (artifact resolution, approval gating, staleness recovery, topology validation) without adding new abstractions beyond what's demonstrably needed.

**Architecture:** No new files. Nine small, independently-testable changes across `pipeline_app/artifacts.py`, `pipeline_app/approval_service.py`, `pipeline_app/routes/stages.py`, `pipeline_app/pipeline_config.py`, `pipeline_app/preflight.py`, `pipeline_app/db.py`, `pipeline_app/main.py`, and `pipeline_app/grounding_service.py`. Task 1 introduces the one new piece of shared logic (`resolve_latest_artifact`); every other task is a targeted fix to existing functions.

**Tech Stack:** Python 3.14, FastAPI, SQLite (stdlib `sqlite3`), pytest, PyYAML.

## Global Constraints

- No new files, no new third-party dependencies, no new abstractions beyond `resolve_latest_artifact` (Task 1) — that one is justified because four call sites already special-case `stage_id == "grounding"` and two of them already diverge in behavior (a real correctness bug, not just duplication).
- Every new 409 response uses the existing `PlainTextResponse(..., status_code=409)` pattern already established in `routes/stages.py`.
- Every task must leave `pytest` fully green (`cd pipeline-app && python -m pytest`) before its commit step. Where a task intentionally changes existing behavior, it updates the existing test's assertions in the same commit — this plan calls out every such case explicitly so it is never mistaken for an accidental regression.
- Grounding's real content lives in `rgs-briefs/<file>.md` at the repo root (git-tracked, also read by the `rgs-pairing-review` skill) and is referenced by a `pointer.yaml` file the app writes into `runs/<run_id>/00-grounding/`. Every task touching grounding must preserve this split — never write pipeline-app-internal bookkeeping into the `rgs-briefs/` files themselves beyond what's already there.
- Two related findings from the review are deliberately **out of scope** for this plan — see "Deferred" at the end. Do not implement them as part of these tasks.

---

## File Structure

| File | Responsibility in this plan |
|---|---|
| `pipeline_app/artifacts.py` | Gains `resolve_latest_artifact()` — the one shared helper that knows grounding uses a pointer instead of `artifact.v{N}.md`. |
| `pipeline_app/approval_service.py` | `approve_stage()` uses the new resolver and stops mutating the RGS brief's own frontmatter on approval. |
| `pipeline_app/routes/stages.py` | `stage_page` uses the resolver and shows every upstream input, not just the first; `stage_chat` and `approve_stage_route` gain a status gate; `edit_stage_output_route` refuses grounding. |
| `pipeline_app/pipeline_config.py` | `load_topology()` validates the stage graph (duplicate ids, unresolvable `depends_on`, cycles) instead of trusting it silently. |
| `pipeline_app/preflight.py` | `reconcile_orphaned_turns()` also un-wedges any stage left at `running` by a crashed turn. |
| `pipeline_app/db.py` | Gains `get_stage_by_row_id()`, needed by the Task 9 reconciliation. |
| `pipeline_app/main.py` | Passes the two new arguments `reconcile_orphaned_turns()` needs. |
| `pipeline_app/grounding_service.py` | `snapshot_rgs_briefs`/`identify_new_brief` compare content hashes (not just filenames) so a same-day rerun on the same topic is detected; `supersede_previous_brief` archives instead of deleting. |

---

### Task 1: Shared artifact resolver

**Files:**
- Modify: `pipeline-app/pipeline_app/artifacts.py`
- Test: `pipeline-app/tests/test_artifacts.py`

**Interfaces:**
- Produces: `resolve_latest_artifact(repo_root: Path, stage_id: str, stage_dir: Path) -> Path | None` — for `stage_id == "grounding"`, resolves through `grounding_service.read_pointer(stage_dir)` and returns `None` if there's no pointer or the pointer's target file doesn't exist on disk; for every other `stage_id`, delegates to the existing `latest_artifact_path(stage_dir)`.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_artifacts.py` (add `resolve_latest_artifact` to the existing `from pipeline_app.artifacts import (...)` block, and add `from pipeline_app.grounding_service import write_pointer` as a new top-level import):

```python
def test_resolve_latest_artifact_delegates_for_non_grounding_stage(tmp_path: Path):
    stage_dir = tmp_path / "01-ideation"
    write_artifact(stage_dir, 1, {"stage": "shorts-ideation"}, "body")
    resolved = resolve_latest_artifact(tmp_path, "ideation", stage_dir)
    assert resolved == stage_dir / "artifact.v1.md"


def test_resolve_latest_artifact_grounding_resolves_via_pointer(tmp_path: Path):
    rgs_briefs = tmp_path / "rgs-briefs"
    rgs_briefs.mkdir()
    brief = rgs_briefs / "2026-07-27-x.md"
    brief.write_text("---\nstatus: candidate\n---\n\nbody", encoding="utf-8")
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-27-x.md")

    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) == brief


def test_resolve_latest_artifact_grounding_no_pointer_returns_none(tmp_path: Path):
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    stage_dir.mkdir(parents=True)
    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) is None


def test_resolve_latest_artifact_grounding_pointer_target_missing_returns_none(tmp_path: Path):
    """The pointer file exists but the brief it names was deleted or never
    written -- must return None, not raise. This is the exact case the old
    inline branches in approval_service.py and routes/stages.py got wrong in
    two of three copies (they skipped the .exists() check)."""
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/does-not-exist.md")
    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_artifacts.py -v`
Expected: 4 new FAILs with `ImportError: cannot import name 'resolve_latest_artifact'`

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/artifacts.py`, add this import at the top (after the existing `import yaml`):

```python
from pipeline_app import grounding_service
```

Add this function after `latest_artifact_path` (after the existing function ending at line 51):

```python
def resolve_latest_artifact(repo_root: Path, stage_id: str, stage_dir: Path) -> Path | None:
    """A stage's current artifact, accounting for grounding's pointer-based
    storage. Every stage except grounding writes artifact.v{N}.md into its
    own stage_dir, resolved via latest_artifact_path. Grounding's real
    output lands in rgs-briefs/ at the repo root instead, referenced by a
    pointer.yaml file the turn route writes into stage_dir -- so this is
    the one place that split has to be reconciled back into a single Path."""
    if stage_id == "grounding":
        pointer = grounding_service.read_pointer(stage_dir)
        if not pointer:
            return None
        path = repo_root / pointer
        return path if path.exists() else None
    return latest_artifact_path(stage_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_artifacts.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite to check for import cycles**

Run: `cd pipeline-app && python -m pytest`
Expected: all PASS (this specifically confirms `artifacts.py` importing `grounding_service` doesn't create a cycle — `grounding_service.py` does not import `artifacts`)

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/artifacts.py pipeline-app/tests/test_artifacts.py
git commit -m "feat(pipeline-app): add resolve_latest_artifact shared resolver"
```

---

### Task 2: approval_service uses the shared resolver

**Files:**
- Modify: `pipeline-app/pipeline_app/approval_service.py`
- Test: `pipeline-app/tests/test_approval_service.py`

**Interfaces:**
- Consumes: `artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir) -> Path | None` (Task 1)

This closes a real bug the old inline branch had: it called `grounding_service.read_pointer` and built `repo_root / pointer` **without** checking `.exists()`, so `artifacts.stamp_final(latest, now)` (a few lines later) would raise an uncaught `FileNotFoundError` — a 500 — instead of the clean 409 every other "nothing to approve" case gets.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_approval_service.py`:

```python
def test_approve_stage_grounding_pointer_target_missing_returns_valueerror_not_crash(conn, tmp_path: Path):
    project_id = db.create_project(conn, "rgs-1", "rgs", "raisinggoodsports", "2026-07-25T12:00:00Z")
    db.create_stage_row(conn, project_id, "grounding", "awaiting_review")
    run_dir = tmp_path / "runs" / "rgs-1"
    grounding_dir = run_dir / "00-grounding"
    write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")

    with pytest.raises(ValueError, match="No artifact to approve"):
        approve_stage(conn, tmp_path, run_dir, project_id, GROUNDING_STAGES, "grounding")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_approval_service.py::test_approve_stage_grounding_pointer_target_missing_returns_valueerror_not_crash -v`
Expected: FAIL with `FileNotFoundError`, not the expected `ValueError`

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/approval_service.py`, replace lines 22-31:

```python
    if stage_id == "grounding":
        # Grounding's real output lands in rgs-briefs/, referenced by a
        # pointer.yaml the turn route writes into stage_dir -- not the
        # artifact.v{N}.md convention every other stage uses.
        pointer = grounding_service.read_pointer(stage_dir)
        latest = (repo_root / pointer) if pointer else None
    else:
        latest = artifacts.latest_artifact_path(stage_dir)
    if latest is None:
        raise ValueError(f"No artifact to approve for stage '{stage_id}'.")
```

with:

```python
    latest = artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir)
    if latest is None:
        raise ValueError(f"No artifact to approve for stage '{stage_id}'.")
```

The `grounding_service` import on line 5 is no longer used by this file after this change — remove it, leaving:

```python
from pipeline_app import artifacts, db as db_mod
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_approval_service.py -v`
Expected: all PASS, including the existing `test_approve_stage_grounding_resolves_artifact_via_pointer` (unaffected — same resolved path, just via the shared function now)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/approval_service.py pipeline-app/tests/test_approval_service.py
git commit -m "fix(pipeline-app): approve_stage uses resolve_latest_artifact, no longer 500s on a dangling grounding pointer"
```

---

### Task 3: Stop mutating the RGS brief's own frontmatter on approval

**Files:**
- Modify: `pipeline-app/pipeline_app/approval_service.py`
- Test: `pipeline-app/tests/test_approval_service.py`

**Interfaces:**
- Consumes: nothing new.

`rgs-briefs/*.md` files carry their own frontmatter schema (`status: candidate`, `thinker:`, `research_codes:`, etc. -- confirmed against real files in `rgs-briefs/`) written and read by the `rgs-grounding` and `rgs-pairing-review` skills. `approve_stage` currently runs `artifacts.stamp_final()` on whatever `latest` resolves to, which for grounding is that brief file -- overwriting its `status` field with pipeline-app's own `"final"` value (a different domain's meaning for that key) and re-serializing the whole YAML block (list style, quoting) through `yaml.safe_dump`. Grounding's approval state already lives in the `stages` DB row; the brief file needs no stamp at all.

**This task changes behavior asserted by the test written in the debugging session that fixed the original 409 bug** (`test_approve_stage_grounding_resolves_artifact_via_pointer` in `pipeline-app/tests/test_approval_service.py`) -- it currently asserts `meta["status"] == "final"` and `meta["finalized_at"] is not None` on the brief. Those assertions must be removed as part of this task; they describe the behavior this task deliberately removes, not a regression.

- [ ] **Step 1: Write the failing test, and fix the now-contradictory existing test**

First, in `pipeline-app/tests/test_approval_service.py`, find `test_approve_stage_grounding_resolves_artifact_via_pointer` and delete these two lines (they assert the old, now-wrong behavior):

```python
    meta, _ = artifacts.parse_frontmatter(brief_path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["finalized_at"] is not None
```

Then add a new test right after it:

```python
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
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `cd pipeline-app && python -m pytest tests/test_approval_service.py::test_approve_stage_grounding_does_not_mutate_brief_content -v`
Expected: FAIL — `brief_path.read_text(...)` no longer equals `original_text` because `stamp_final` rewrote it

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/approval_service.py`, replace:

```python
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    artifacts.stamp_final(latest, now)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.APPROVED.value, approved_at=now)
```

with:

```python
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if stage_id != "grounding":
        artifacts.stamp_final(latest, now)
    db_mod.update_stage_status(conn, stage_row["id"], StageStatus.APPROVED.value, approved_at=now)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_approval_service.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest`
Expected: all PASS — in particular `test_approve_route_stamps_artifact_final` in `test_routes_approve_edit.py` (a `generic`-brand, non-grounding stage) must still pass unchanged, since that path still calls `stamp_final`.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/approval_service.py pipeline-app/tests/test_approval_service.py
git commit -m "fix(pipeline-app): approving grounding no longer rewrites the rgs-briefs frontmatter"
```

---

### Task 4: stage_page uses the shared resolver

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/stages.py`
- Test: `pipeline-app/tests/test_routes_stages.py`

**Interfaces:**
- Consumes: `artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir) -> Path | None` (Task 1)

Same consolidation as Task 2, applied to `stage_page`'s two inline branches (`output_body`'s grounding check, and `grounding_input_body`'s pointer resolution). The `grounding_input_body` branch already had the `.exists()` check the other two lacked — this task doesn't change its behavior, just removes the duplicated logic.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_routes_stages.py`:

```python
def test_stage_page_grounding_output_pointer_target_missing_shows_no_output(client):
    """Mirrors Task 2's approval_service fix: a dangling pointer.yaml must
    render as no output, never crash the page."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "rgs", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    grounding_dir = run_dir / "00-grounding"
    write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")

    page = test_client.get(f"/projects/{project_id}/stages/grounding")
    assert page.status_code == 200
    assert "No output yet." in page.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py::test_stage_page_grounding_output_pointer_target_missing_shows_no_output -v`
Expected: FAIL with `FileNotFoundError` (500), not a clean 200 with "No output yet."

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/routes/stages.py`, replace the `grounding_input_body` block (current lines 70-79):

```python
    grounding_input_body = None
    if project["brand"] == "raisinggoodsports" and stage_id != "grounding":
        grounding_dir = run_dir / "00-grounding"
        pointer = grounding_service.read_pointer(grounding_dir)
        if pointer:
            grounding_path = request.app.state.repo_root / pointer
            if grounding_path.exists():
                _, grounding_input_body = artifacts.parse_frontmatter(
                    grounding_path.read_text(encoding="utf-8")
                )
```

with:

```python
    grounding_input_body = None
    if project["brand"] == "raisinggoodsports" and stage_id != "grounding":
        grounding_dir = run_dir / "00-grounding"
        grounding_path = artifacts.resolve_latest_artifact(
            request.app.state.repo_root, "grounding", grounding_dir
        )
        if grounding_path is not None:
            _, grounding_input_body = artifacts.parse_frontmatter(
                grounding_path.read_text(encoding="utf-8")
            )
```

And replace the `output_body` block (current lines 81-91):

```python
    output_body = None
    if stage_id == "grounding":
        # Grounding's real output lands in rgs-briefs/, referenced by a
        # pointer.yaml the turn route writes into stage_dir -- not the
        # artifact.v{N}.md convention every other stage uses.
        pointer = grounding_service.read_pointer(stage_dir)
        latest = (request.app.state.repo_root / pointer) if pointer else None
    else:
        latest = artifacts.latest_artifact_path(stage_dir)
    if latest is not None:
        _, output_body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
```

with:

```python
    output_body = None
    latest = artifacts.resolve_latest_artifact(request.app.state.repo_root, stage_id, stage_dir)
    if latest is not None:
        _, output_body = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
```

`grounding_service` is still used elsewhere in this file (`stage_chat`), so leave that import alone.

At the top of `pipeline-app/tests/test_routes_stages.py`, this test needs `write_pointer` — it's already imported (added in the prior debugging session): confirm the file has `from pipeline_app.grounding_service import write_pointer`. If not present, add it next to the existing `from pipeline_app import artifacts` import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_routes_stages.py
git commit -m "refactor(pipeline-app): stage_page uses resolve_latest_artifact for output and grounding-companion input"
```

---

### Task 5: stage_page shows every upstream input, not just the first

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/stages.py`
- Test: `pipeline-app/tests/test_routes_stages.py`

**Interfaces:**
- Consumes: nothing new.

`assembly` depends on both `voiceover` and `visual` (see `pipeline.yaml`), and the AI turn already receives both (`turn_service.py`'s `upstream_paths` iterates all of `stage_def.depends_on`) — but the Input panel only ever showed `depends_on[0]`, so the visual prompt sheet never appeared for a human reviewing the assembly stage.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_routes_stages.py`:

```python
def test_stage_page_shows_all_upstream_inputs_not_just_first(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "  - id: assembly\n    skill: shorts-assembly\n    dir_prefix: \"04\"\n"
        "    depends_on: [voiceover, visual]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]

    artifacts.write_artifact(run_dir / "03-voiceover", 1, {"stage": "voiceover-brief"}, "voiceover brief text")
    artifacts.write_artifact(run_dir / "03-visual", 1, {"stage": "visual-prompts"}, "visual prompt sheet text")

    page = test_client.get(f"/projects/{project_id}/stages/assembly")
    assert page.status_code == 200
    assert "voiceover brief text" in page.text
    assert "visual prompt sheet text" in page.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py::test_stage_page_shows_all_upstream_inputs_not_just_first -v`
Expected: FAIL — `"visual prompt sheet text" in page.text` is False (only voiceover's body is currently shown)

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/routes/stages.py`, replace the `input_body` block (current lines 58-64):

```python
    input_body = None
    if stage_def.depends_on:
        up_def = next(s for s in stage_defs if s.id == stage_def.depends_on[0])
        up_dir = run_dir / stage_dir_name(up_def)
        up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            _, input_body = artifacts.parse_frontmatter(up_latest.read_text(encoding="utf-8"))
```

with:

```python
    input_sections = []
    for dep_id in stage_def.depends_on:
        up_def = next(s for s in stage_defs if s.id == dep_id)
        up_dir = run_dir / stage_dir_name(up_def)
        up_latest = artifacts.latest_artifact_path(up_dir)
        if up_latest is not None:
            _, dep_body = artifacts.parse_frontmatter(up_latest.read_text(encoding="utf-8"))
            input_sections.append(f"## From {dep_id}\n\n{dep_body}")
    input_body = "\n\n---\n\n".join(input_sections) if input_sections else None
```

`input_body` stays a single optional string, so `stage.html` needs no change.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_stages.py -v`
Expected: all PASS, including the existing `test_stage_page_shows_input_output_and_transcript` (a single-`depends_on` stage — the new loop produces the same single section it did before, now with a `## From ideation` heading in front of it, which the test's `"concept brief text" in page.text` substring check still satisfies)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_routes_stages.py
git commit -m "fix(pipeline-app): stage_page Input panel shows every upstream artifact, not just the first"
```

---

### Task 6: Status gate on chat and approve

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/stages.py`
- Test: `pipeline-app/tests/test_routes_chat_sse.py`, `pipeline-app/tests/test_routes_approve_edit.py`

**Interfaces:**
- Consumes: `StageStatus` enum from `pipeline_app.state_machine` (`LOCKED`, `RUNNING` members already exist).

This is the highest-value fix from the review: neither route currently checks `stage_row["status"]`, so `POST /projects/{id}/stages/{stage_id}/chat` (and therefore `/approve`) works on a stage whose dependencies were never approved — e.g. chatting directly on `repurpose` on a brand-new project. Both routes are gated on the same two statuses: `locked` (dependencies not yet approved) and `running` (a turn is already in flight for this stage — distinct from the existing global `any_turn_running` check, which only catches a turn running on *some* stage).

Every status this codebase uses today (`ready`, `awaiting_review`, `approved`, `stale`, `no_artifact`) must still be chat-able and approve-able exactly as before — confirmed against every existing route-level test in `test_routes_approve_edit.py` and `test_routes_chat_sse.py`, none of which exercises chat or approve against a stage that starts `locked`.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_routes_chat_sse.py`. This test needs a stage that starts `locked`, which the file's shared `client` fixture doesn't have (both its stages have `depends_on: []`), so it defines its own two-stage `pipeline.yaml` inline, matching the pattern already used by `test_grounding_chat_writes_to_rgs_briefs_and_pointer`:

```python
def test_chat_endpoint_returns_409_for_locked_stage(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
        "    depends_on: [ideation]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/chat", data={"message": "hi"},
    )
    assert resp.status_code == 409
    assert "locked" in resp.text
```

This needs `create_app` imported — it already is, at the top of the file. Add `from fastapi.testclient import TestClient` too if not already present (it is, at line 5).

Add to `pipeline-app/tests/test_routes_approve_edit.py`:

```python
def test_approve_route_blocks_locked_stage(two_stage_client):
    test_client, tmp_path, app = two_stage_client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    # scripting depends_on: [ideation], which hasn't been approved, so it's
    # still locked -- even though its directory has no artifact either, the
    # gate must reject it for the right reason (locked, not "no artifact").
    resp = test_client.post(f"/projects/{project_id}/stages/scripting/approve")
    assert resp.status_code == 409
    assert "locked" in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_routes_chat_sse.py::test_chat_endpoint_returns_409_for_locked_stage tests/test_routes_approve_edit.py::test_approve_route_blocks_locked_stage -v`
Expected: both FAIL — the chat one streams a normal (200) SSE response instead of 409; the approve one currently 409s but with "No artifact to approve", so `"locked" in resp.text` is False

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/routes/stages.py`, add this import alongside the existing ones at the top:

```python
from pipeline_app.state_machine import StageStatus
```

In `stage_chat`, replace the signature line and its first body line (current lines 108-110):

```python
@router.post("/projects/{project_id}/stages/{stage_id}/chat")
async def stage_chat(request: Request, project_id: int, stage_id: str, message: str = Form(...)):
    project, stage_def, _stage_row = _resolve_project_stage(request, project_id, stage_id)
```

with:

```python
@router.post("/projects/{project_id}/stages/{stage_id}/chat")
async def stage_chat(request: Request, project_id: int, stage_id: str, message: str = Form(...)):
    project, stage_def, stage_row = _resolve_project_stage(request, project_id, stage_id)
    if stage_row["status"] in (StageStatus.LOCKED.value, StageStatus.RUNNING.value):
        return PlainTextResponse(
            f"Stage '{stage_id}' is {stage_row['status']} and cannot accept chat messages yet.",
            status_code=409,
        )
```

In `approve_stage_route`, replace the signature line and its first body line (current lines 173-175):

```python
@router.post("/projects/{project_id}/stages/{stage_id}/approve")
def approve_stage_route(request: Request, project_id: int, stage_id: str):
    project, _stage_def, _stage_row = _resolve_project_stage(request, project_id, stage_id)
```

with:

```python
@router.post("/projects/{project_id}/stages/{stage_id}/approve")
def approve_stage_route(request: Request, project_id: int, stage_id: str):
    project, _stage_def, stage_row = _resolve_project_stage(request, project_id, stage_id)
    if stage_row["status"] in (StageStatus.LOCKED.value, StageStatus.RUNNING.value):
        return PlainTextResponse(
            f"Stage '{stage_id}' is {stage_row['status']} and cannot be approved yet.",
            status_code=409,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_chat_sse.py tests/test_routes_approve_edit.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest`
Expected: all PASS — confirms no existing test relied on chatting/approving a `locked` stage

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_routes_chat_sse.py pipeline-app/tests/test_routes_approve_edit.py
git commit -m "fix(pipeline-app): reject chat and approve on locked/running stages instead of silently allowing out-of-order turns"
```

---

### Task 7: edit route refuses grounding

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/stages.py`
- Test: `pipeline-app/tests/test_routes_approve_edit.py`

**Interfaces:**
- Consumes: nothing new.

`edit_stage_output_route` unconditionally writes `runs/<run>/00-grounding/artifact.v{N}.md` — a path nothing else ever reads (both `stage_page` and `approve_stage` resolve grounding through `pointer.yaml`). Today this means an edit silently vanishes: the route returns 303, the redisplayed page still shows the *original* `rgs-briefs/` content, and the stage was flipped to `awaiting_review` for no visible reason. There's no edit form wired up in `stage.html` yet, so this is reachable only by a direct POST — cheap to close now.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_routes_approve_edit.py`:

```python
def test_edit_route_blocks_grounding(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: grounding\n    skill: rgs-grounding\n    dir_prefix: \"00\"\n"
        "    depends_on: []\n    brand_scope: raisinggoodsports\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "rgs", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    resp = test_client.post(
        f"/projects/{project_id}/stages/grounding/edit", data={"body": "hand-edited text"}
    )
    assert resp.status_code == 409
    assert "rgs-briefs" in resp.text
```

This needs `create_app` and `TestClient` imported in this file — add:

```python
from fastapi.testclient import TestClient

from pipeline_app.main import create_app
```

next to the existing imports at the top of `pipeline-app/tests/test_routes_approve_edit.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_approve_edit.py::test_edit_route_blocks_grounding -v`
Expected: FAIL — currently returns a 303 redirect, not 409

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/routes/stages.py`, in `edit_stage_output_route`, replace the signature line and its first body line (current lines 188-190):

```python
@router.post("/projects/{project_id}/stages/{stage_id}/edit")
def edit_stage_output_route(request: Request, project_id: int, stage_id: str, body: str = Form(...)):
    project, stage_def, stage_row = _resolve_project_stage(request, project_id, stage_id)
```

with:

```python
@router.post("/projects/{project_id}/stages/{stage_id}/edit")
def edit_stage_output_route(request: Request, project_id: int, stage_id: str, body: str = Form(...)):
    project, stage_def, stage_row = _resolve_project_stage(request, project_id, stage_id)
    if stage_id == "grounding":
        return PlainTextResponse(
            "Grounding's output lives in rgs-briefs/ -- edit that file directly, not through this app.",
            status_code=409,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_approve_edit.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/stages.py pipeline-app/tests/test_routes_approve_edit.py
git commit -m "fix(pipeline-app): edit route refuses grounding instead of silently writing to a path nothing reads"
```

---

### Task 8: Validate pipeline.yaml's topology at load time

**Files:**
- Modify: `pipeline-app/pipeline_app/pipeline_config.py`
- Test: `pipeline-app/tests/test_pipeline_config.py`

**Interfaces:**
- Produces: `load_topology` now raises `ValueError` (with a message naming the offending stage id) for a duplicate stage id, a `depends_on` referencing an unknown stage id, or a dependency cycle — instead of loading successfully and failing much later and less clearly (a stage permanently `LOCKED` with no explanation, or a `StopIteration` → 500 in `stage_page`).

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_pipeline_config.py` (add `import pytest` and `import tempfile` are not needed — use `tmp_path`, already a pytest fixture; add `Path` is already imported):

```python
def _write_topology(tmp_path: Path, yaml_text: str) -> Path:
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    return path


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
    path = _write_topology(
        tmp_path,
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
        "    depends_on: [ideation]\n",
    )
    stages = load_topology(path)
    assert [s.id for s in stages] == ["ideation", "scripting"]
```

Add `import pytest` at the top of the test file if not already present (check — the file currently has no `import pytest` since none of its existing tests need it).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: the 3 new `pytest.raises` tests FAIL (no exception is currently raised); `test_load_topology_accepts_valid_graph` passes already

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/pipeline_config.py`, replace `load_topology` (current lines 17-29):

```python
def load_topology(path: Path) -> list[StageDef]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        StageDef(
            id=s["id"],
            skill=s["skill"],
            dir_prefix=s["dir_prefix"],
            depends_on=list(s.get("depends_on", [])),
            brand_scope=s.get("brand_scope"),
            specialist=s.get("specialist"),
        )
        for s in data["stages"]
    ]
```

with:

```python
def load_topology(path: Path) -> list[StageDef]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    stages = [
        StageDef(
            id=s["id"],
            skill=s["skill"],
            dir_prefix=s["dir_prefix"],
            depends_on=list(s.get("depends_on", [])),
            brand_scope=s.get("brand_scope"),
            specialist=s.get("specialist"),
        )
        for s in data["stages"]
    ]
    _validate_topology(stages)
    return stages


def _validate_topology(stages: list[StageDef]) -> None:
    seen: set[str] = set()
    for stage in stages:
        if stage.id in seen:
            raise ValueError(f"pipeline.yaml: duplicate stage id '{stage.id}'")
        seen.add(stage.id)
    for stage in stages:
        for dep in stage.depends_on:
            if dep not in seen:
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' depends_on unknown stage '{dep}'"
                )
    _check_no_cycles(stages)


def _check_no_cycles(stages: list[StageDef]) -> None:
    by_id = {s.id: s for s in stages}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {s.id: WHITE for s in stages}

    def visit(stage_id: str, path: list[str]) -> None:
        color[stage_id] = GRAY
        for dep in by_id[stage_id].depends_on:
            if color[dep] == GRAY:
                cycle = " -> ".join(path + [dep])
                raise ValueError(f"pipeline.yaml: dependency cycle detected: {cycle}")
            if color[dep] == WHITE:
                visit(dep, path + [dep])
        color[stage_id] = BLACK

    for stage in stages:
        if color[stage.id] == WHITE:
            visit(stage.id, [stage.id])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest`
Expected: all PASS — confirms the real `pipeline.yaml` at the repo root, and every test fixture's inline pipeline.yaml across the whole test suite, are all valid graphs

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/pipeline_config.py pipeline-app/tests/test_pipeline_config.py
git commit -m "feat(pipeline-app): validate pipeline.yaml topology at load time (duplicate ids, unknown deps, cycles)"
```

---

### Task 9: Recover stages wedged at `running` after a crash

**Files:**
- Modify: `pipeline-app/pipeline_app/db.py`, `pipeline-app/pipeline_app/preflight.py`, `pipeline-app/pipeline_app/main.py`
- Test: `pipeline-app/tests/test_db.py`, `pipeline-app/tests/test_preflight.py`

**Interfaces:**
- Consumes: `artifacts.resolve_latest_artifact(repo_root, stage_id, stage_dir) -> Path | None` (Task 1)
- Produces: `db.get_stage_by_row_id(conn, stage_row_id) -> sqlite3.Row | None`; `preflight.reconcile_orphaned_turns(conn, repo_root, stage_defs) -> int` (signature changed — now takes two more required arguments)

If the app process dies mid-turn (or a bug lets an exception escape `run_stage_turn`'s post-stream finalization), the turn row and the stage row both stay at `running` forever — `reconcile_orphaned_turns` already resets the turn to `orphaned` on the next startup, but never looks at the stage. A stage stuck at `running` can't be chat'd or approved (Task 6's new gate blocks both), so the project is permanently stuck with no recovery path. On startup, for every stage whose orphaned turn just got reconciled, reset that stage back to `awaiting_review` if it already has an artifact (the turn produced something before dying) or `ready` if it doesn't (nothing usable exists yet, so back to square one).

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_db.py`:

```python
def test_get_stage_by_row_id_returns_the_row(conn):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "ready")
    row = db.get_stage_by_row_id(conn, stage_row_id)
    assert row["stage_id"] == "ideation"


def test_get_stage_by_row_id_returns_none_when_missing(conn):
    assert db.get_stage_by_row_id(conn, 999) is None
```

`test_db.py` already has a `conn` fixture (building a fresh `tmp_path` SQLite DB via `db.init_db`/`db.get_connection`) — these two tests use it as-is, no fixture changes needed.

Replace the existing `test_reconcile_marks_running_turns_as_orphaned` and `test_reconcile_is_a_no_op_when_nothing_running` in `pipeline-app/tests/test_preflight.py` with:

```python
STAGE_DEFS = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]


def test_reconcile_marks_running_turns_as_orphaned(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")

    count = reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)
    assert count == 1
    rows = db.list_turns(conn, stage_row_id)
    assert rows[0]["status"] == "orphaned"


def test_reconcile_resets_wedged_stage_to_ready_when_no_artifact(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    # No artifact.v1.md written anywhere under runs/ -- the turn died before producing one.

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    assert db.get_stage_by_row_id(conn, stage_row_id)["status"] == "ready"


def test_reconcile_resets_wedged_stage_to_awaiting_review_when_artifact_exists(conn, tmp_path: Path):
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    stage_row_id = db.create_stage_row(conn, project_id, "ideation", "running")
    db.create_turn(conn, stage_row_id, "running", "2026-07-25T12:00:00Z", "events/x.jsonl")
    artifacts.write_artifact(tmp_path / "runs" / "abc-1" / "01-ideation", 1, {"stage": "shorts-ideation"}, "body")

    reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS)

    assert db.get_stage_by_row_id(conn, stage_row_id)["status"] == "awaiting_review"


def test_reconcile_is_a_no_op_when_nothing_running(conn, tmp_path: Path):
    assert reconcile_orphaned_turns(conn, tmp_path, STAGE_DEFS) == 0
```

This needs new imports at the top of `pipeline-app/tests/test_preflight.py`:

```python
from pipeline_app import artifacts
from pipeline_app.pipeline_config import StageDef
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_db.py tests/test_preflight.py -v`
Expected: FAIL — `get_stage_by_row_id` doesn't exist yet, and `reconcile_orphaned_turns` doesn't accept the new arguments yet

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/db.py`, add after `get_stage` (after line 61):

```python
def get_stage_by_row_id(conn: sqlite3.Connection, stage_row_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM stages WHERE id = ?", (stage_row_id,)).fetchone()
```

In `pipeline-app/pipeline_app/preflight.py`, replace the full file content with:

```python
import shutil
import sqlite3
from pathlib import Path
from typing import Callable

from pipeline_app import artifacts, db as db_mod
from pipeline_app.cli_runner import resolve_claude_binary
from pipeline_app.pipeline_config import StageDef, stage_dir_name
from pipeline_app.state_machine import StageStatus


def reconcile_orphaned_turns(conn: sqlite3.Connection, repo_root: Path, stage_defs: list[StageDef]) -> int:
    stage_defs_by_id = {s.id: s for s in stage_defs}
    running = db_mod.list_running_turns(conn)
    for turn in running:
        db_mod.update_turn(conn, turn["id"], "orphaned")
        _unwedge_stage(conn, repo_root, stage_defs_by_id, turn["stage_row_id"])
    return len(running)


def _unwedge_stage(
    conn: sqlite3.Connection,
    repo_root: Path,
    stage_defs_by_id: dict[str, StageDef],
    stage_row_id: int,
) -> None:
    stage_row = db_mod.get_stage_by_row_id(conn, stage_row_id)
    if stage_row is None or stage_row["status"] != StageStatus.RUNNING.value:
        return
    stage_def = stage_defs_by_id.get(stage_row["stage_id"])
    if stage_def is None:
        return
    project = db_mod.get_project(conn, stage_row["project_id"])
    if project is None:
        return
    run_dir = repo_root / "runs" / project["run_id"]
    stage_dir = run_dir / stage_dir_name(stage_def)
    latest = artifacts.resolve_latest_artifact(repo_root, stage_def.id, stage_dir)
    new_status = StageStatus.AWAITING_REVIEW.value if latest is not None else StageStatus.READY.value
    db_mod.update_stage_status(conn, stage_row["id"], new_status)


def check_cli_available(which_fn: Callable[[str], str | None] = shutil.which) -> dict:
    try:
        path = resolve_claude_binary(which_fn)
        return {"available": True, "path": path, "error": None}
    except FileNotFoundError as exc:
        return {"available": False, "path": None, "error": str(exc)}
```

In `pipeline-app/pipeline_app/main.py`, replace line 24:

```python
    app.state.orphaned_count = preflight.reconcile_orphaned_turns(app.state.conn)
```

with:

```python
    app.state.orphaned_count = preflight.reconcile_orphaned_turns(
        app.state.conn, app.state.repo_root, app.state.stage_defs
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_db.py tests/test_preflight.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest`
Expected: all PASS — confirms `main.py`'s `create_app` (called by every route-level test fixture) still starts up cleanly with the new arguments

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/db.py pipeline-app/pipeline_app/preflight.py pipeline-app/pipeline_app/main.py pipeline-app/tests/test_db.py pipeline-app/tests/test_preflight.py
git commit -m "fix(pipeline-app): recover stages wedged at running after a crashed turn, instead of leaving projects permanently stuck"
```

---

### Task 10: Detect same-day brief reruns and stop deleting superseded briefs

**Files:**
- Modify: `pipeline-app/pipeline_app/grounding_service.py`
- Test: `pipeline-app/tests/test_grounding_service.py`

**Interfaces:**
- Produces: `snapshot_rgs_briefs(rgs_briefs_dir: Path) -> dict[str, str]` (was `-> set[str]`) — maps filename to content sha256; `identify_new_brief(before: dict[str, str], after: dict[str, str]) -> str | None` (was `set[str]` params) — now also detects a filename whose content changed, not just a filename that's new; `supersede_previous_brief` now moves the old file to `rgs-briefs/.superseded/<name>` instead of deleting it.

Two independent fixes to the same two functions, done together since they touch the same small file:

1. `identify_new_brief` currently requires the after-set minus the before-set to contain exactly one filename. The `rgs-grounding` skill names briefs `YYYY-MM-DD-<topic-slug>.md`; a same-day rerun on the same topic produces the *same filename* with different content, so the set difference is empty and the stage silently ends up `no_artifact` despite a successful turn. Comparing content hashes catches this.
2. `supersede_previous_brief` permanently `unlink()`s the previous brief — a git-tracked, human-authored file — every time a project regenerates its grounding stage. Move it into an archive subdirectory instead.

The call site in `routes/stages.py` (`stage_chat`'s grounding branch) passes `before`/`after` straight through to `identify_new_brief` without touching their contents, so it needs no change.

- [ ] **Step 1: Write the failing tests, and update the tests that assert the old behavior**

In `pipeline-app/tests/test_grounding_service.py`, replace `test_snapshot_lists_md_files` (current lines 12-16):

```python
def test_snapshot_lists_md_files(tmp_path: Path):
    (tmp_path / "2026-07-25-a.md").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    snap = snapshot_rgs_briefs(tmp_path)
    assert snap == {"2026-07-25-a.md", "README.md"}
```

with:

```python
def test_snapshot_returns_filename_to_content_hash(tmp_path: Path):
    import hashlib
    a = tmp_path / "2026-07-25-a.md"
    a.write_text("x", encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text("x", encoding="utf-8")
    expected_hash = hashlib.sha256(b"x").hexdigest()
    snap = snapshot_rgs_briefs(tmp_path)
    assert snap == {"2026-07-25-a.md": expected_hash, "README.md": expected_hash}
```

Replace `test_identify_new_brief_when_exactly_one_new_file`, `test_identify_new_brief_returns_none_when_zero_new_files`, and `test_identify_new_brief_returns_none_when_ambiguous` (current lines 19-32):

```python
def test_identify_new_brief_when_exactly_one_new_file():
    before = {"a.md": "h1", "b.md": "h2"}
    after = {"a.md": "h1", "b.md": "h2", "c.md": "h3"}
    assert identify_new_brief(before, after) == "c.md"


def test_identify_new_brief_returns_none_when_zero_new_files():
    assert identify_new_brief({"a.md": "h1"}, {"a.md": "h1"}) is None


def test_identify_new_brief_returns_none_when_ambiguous():
    before = {"a.md": "h1"}
    after = {"a.md": "h1", "b.md": "h2", "c.md": "h3"}
    assert identify_new_brief(before, after) is None


def test_identify_new_brief_detects_same_filename_changed_content():
    """A same-day rerun on the same topic overwrites the brief file in place
    -- same filename, new content. The old set-difference check missed this
    entirely (empty diff -> None -> stage wrongly marked no_artifact)."""
    before = {"2026-07-27-topic.md": "h1"}
    after = {"2026-07-27-topic.md": "h2"}
    assert identify_new_brief(before, after) == "2026-07-27-topic.md"
```

Replace `test_supersede_deletes_previously_pointed_file` (current lines 45-56):

```python
def test_supersede_archives_previously_pointed_file(tmp_path: Path):
    repo_root = tmp_path
    rgs_briefs = repo_root / "rgs-briefs"
    rgs_briefs.mkdir()
    old_brief = rgs_briefs / "2026-07-25-old.md"
    old_brief.write_text("old content", encoding="utf-8")
    stage_dir = repo_root / "runs" / "x" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-25-old.md")

    supersede_previous_brief(repo_root, stage_dir)

    assert not old_brief.exists()
    archived = rgs_briefs / ".superseded" / "2026-07-25-old.md"
    assert archived.read_text(encoding="utf-8") == "old content"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_grounding_service.py -v`
Expected: FAIL — `snapshot_rgs_briefs` still returns a set, `identify_new_brief` still takes sets, `supersede_previous_brief` still deletes

- [ ] **Step 3: Implement**

Replace the full content of `pipeline-app/pipeline_app/grounding_service.py`:

```python
import hashlib
from pathlib import Path

import yaml


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_rgs_briefs(rgs_briefs_dir: Path) -> dict[str, str]:
    if not rgs_briefs_dir.exists():
        return {}
    return {p.name: _hash_file(p) for p in rgs_briefs_dir.glob("*.md")}


def identify_new_brief(before: dict[str, str], after: dict[str, str]) -> str | None:
    changed = [name for name, sha in after.items() if before.get(name) != sha]
    if len(changed) != 1:
        return None
    return changed[0]


def write_pointer(stage_dir: Path, rgs_brief_relpath: str) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = stage_dir / "pointer.yaml"
    pointer_path.write_text(
        yaml.safe_dump({"rgs_brief_path": rgs_brief_relpath}, sort_keys=False),
        encoding="utf-8",
    )
    return pointer_path


def read_pointer(stage_dir: Path) -> str | None:
    pointer_path = stage_dir / "pointer.yaml"
    if not pointer_path.exists():
        return None
    data = yaml.safe_load(pointer_path.read_text(encoding="utf-8")) or {}
    return data.get("rgs_brief_path")


def supersede_previous_brief(repo_root: Path, stage_dir: Path) -> None:
    previous = read_pointer(stage_dir)
    if not previous:
        return
    previous_path = repo_root / previous
    if not previous_path.exists():
        return
    archive_dir = previous_path.parent / ".superseded"
    archive_dir.mkdir(parents=True, exist_ok=True)
    previous_path.rename(archive_dir / previous_path.name)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_grounding_service.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest`
Expected: all PASS — in particular `test_grounding_chat_writes_to_rgs_briefs_and_pointer` in `test_routes_chat_sse.py`, which exercises `snapshot_rgs_briefs`/`identify_new_brief` through the real route, must still pass with the new dict-based signature (the route never inspects `before`/`after` itself, just passes them through)

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/grounding_service.py pipeline-app/tests/test_grounding_service.py
git commit -m "fix(pipeline-app): detect same-day brief reruns via content hash, archive superseded briefs instead of deleting them"
```

---

### Task 11: Propagate staleness transitively, not just one level

**Files:**
- Modify: `pipeline-app/pipeline_app/turn_service.py`
- Test: `pipeline-app/tests/test_turn_service.py`

**Interfaces:**
- Consumes: nothing new (Tasks 1-10 must already be complete — this task edits the same `propagate_staleness` function Task 3/6/7 left in place, untouched by any of them).
- Produces: `propagate_staleness(...) -> None` (signature unchanged) — now also flips approved stages that depend on a stage this call just marked `stale`, repeating until nothing more flips.

`propagate_staleness` only ever inspected the DIRECT dependents of `changed_stage_id`. On the real `pipeline.yaml` (`scripting -> {voiceover, visual} -> assembly -> repurpose`), regenerating `scripting` flips `voiceover`/`visual` to `stale` but leaves `assembly` and `repurpose` `approved`, even though both were built on now-stale inputs. `stale` means "this approved output was built on an input that has since changed" — leaving `assembly`/`repurpose` approved reports a green final stage on a broken chain.

The second level cannot reuse the first level's hash check: `voiceover`'s own `artifact.v1.md` is never rewritten when it goes stale (only its DB status changes), so `assembly`'s recorded hash for it still matches and `is_stale` returns False. So the cascade is deliberately **status-driven**: once a stage flips `approved` -> `stale`, every approved stage depending on it flips too, transitively. It only ever flips `approved` -> `stale` and stops at any other status — a dependent already at `awaiting_review`/`ready`/`no_artifact` has nothing approved to invalidate. Termination is guaranteed independently of Task 8's cycle validation: a stage is enqueued only at the moment it flips out of `approved`, so it can be enqueued at most once.

This function keeps using `artifacts.latest_artifact_path`, not Task 1's `resolve_latest_artifact`: `grounding` has `depends_on: []` and appears in no other stage's `depends_on` (it reaches downstream stages through the `grounding_pointer` side-channel instead), so neither the dependent lookup nor `_current_upstream_hashes` can ever be handed a grounding stage dir here.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_turn_service.py` (no new imports needed — `artifacts`, `db`, `StageDef`, `StageStatus`, `Path` and `turn_service` are all already imported at the top of the file):

```python
CHAIN_STAGES = [
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=[]),
    StageDef(id="voiceover", skill="voiceover-brief", dir_prefix="03", depends_on=["scripting"]),
    StageDef(id="visual", skill="visual-prompts", dir_prefix="03", depends_on=["scripting"]),
    StageDef(id="assembly", skill="shorts-assembly", dir_prefix="04", depends_on=["voiceover", "visual"]),
    StageDef(id="repurpose", skill="social-repurpose", dir_prefix="05", depends_on=["assembly"]),
]


def _dep(run_dir: Path, relpath: str) -> dict:
    path = run_dir / relpath
    return {"path": relpath, "sha256": artifacts.compute_sha256(path)}


def _build_approved_chain(conn, tmp_path: Path, downstream_statuses: dict[str, str] | None = None):
    """Full scripting -> {voiceover, visual} -> assembly -> repurpose chain,
    every stage approved and every artifact's frontmatter recording the real
    hashes of the upstream artifacts it was built on. downstream_statuses
    overrides individual stage statuses."""
    statuses = {s.id: StageStatus.APPROVED.value for s in CHAIN_STAGES}
    statuses.update(downstream_statuses or {})
    project_id = db.create_project(conn, "abc-1", "abc", "generic", "2026-07-25T12:00:00Z")
    for stage in CHAIN_STAGES:
        db.create_stage_row(conn, project_id, stage.id, statuses[stage.id])

    run_dir = tmp_path / "runs" / "abc-1"
    artifacts.write_artifact(run_dir / "02-scripting", 1, {"stage": "shorts-scripting"}, "script v1")
    script_dep = [_dep(run_dir, "02-scripting/artifact.v1.md")]
    artifacts.write_artifact(run_dir / "03-voiceover", 1, {"stage": "voiceover-brief", "depends_on": script_dep}, "vo v1")
    artifacts.write_artifact(run_dir / "03-visual", 1, {"stage": "visual-prompts", "depends_on": script_dep}, "vis v1")
    assembly_dep = [
        _dep(run_dir, "03-voiceover/artifact.v1.md"),
        _dep(run_dir, "03-visual/artifact.v1.md"),
    ]
    artifacts.write_artifact(run_dir / "04-assembly", 1, {"stage": "shorts-assembly", "depends_on": assembly_dep}, "asm v1")
    artifacts.write_artifact(
        run_dir / "05-repurpose", 1,
        {"stage": "social-repurpose", "depends_on": [_dep(run_dir, "04-assembly/artifact.v1.md")]},
        "rep v1",
    )
    return project_id, run_dir


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


def test_propagate_staleness_cascade_stops_at_a_non_approved_stage(conn, tmp_path: Path):
    """The cascade only invalidates APPROVED work. assembly sitting at
    awaiting_review has nothing approved to invalidate, and repurpose is
    still built on assembly's unchanged v1 -- so repurpose stays approved."""
    project_id, run_dir = _build_approved_chain(
        conn, tmp_path, downstream_statuses={"assembly": StageStatus.AWAITING_REVIEW.value}
    )
    artifacts.write_artifact(run_dir / "02-scripting", 2, {"stage": "shorts-scripting"}, "script v2")

    turn_service.propagate_staleness(conn, run_dir, CHAIN_STAGES, project_id, "scripting")

    assert db.get_stage(conn, project_id, "voiceover")["status"] == StageStatus.STALE.value
    assert db.get_stage(conn, project_id, "visual")["status"] == StageStatus.STALE.value
    assert db.get_stage(conn, project_id, "assembly")["status"] == StageStatus.AWAITING_REVIEW.value
    assert db.get_stage(conn, project_id, "repurpose")["status"] == StageStatus.APPROVED.value
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_turn_service.py -v`
Expected: `test_propagate_staleness_cascades_past_direct_dependents` FAILS on `assembly` (still `approved`); `test_propagate_staleness_cascade_stops_at_a_non_approved_stage` already PASSES (it asserts the boundary the current single-level code happens to satisfy — it is the regression guard for Step 3, not a new behavior)

- [ ] **Step 3: Implement**

In `pipeline-app/pipeline_app/turn_service.py`, replace `propagate_staleness` (current lines 48-73) with:

```python
def propagate_staleness(
    conn: sqlite3.Connection,
    run_dir: Path,
    all_stage_defs: list[StageDef],
    project_id: int,
    changed_stage_id: str,
) -> None:
    """Flip approved downstream stages to stale when changed_stage_id's latest
    artifact no longer matches the hash they recorded, then cascade: anything
    approved that was built on a stage this call just made stale is stale too.
    Public because both paths that mint a new artifact version call it:
    run_stage_turn (chat / regenerate) and
    routes.stages.edit_stage_output_route (hand edit)."""
    newly_stale: list[str] = []
    for dep_stage in _dependents_of(all_stage_defs, changed_stage_id):
        row = db_mod.get_stage(conn, project_id, dep_stage.id)
        if row is None or row["status"] != StageStatus.APPROVED.value:
            continue
        stage_dir = run_dir / stage_dir_name(dep_stage)
        latest = artifacts.latest_artifact_path(stage_dir)
        if latest is None:
            continue
        meta, _ = artifacts.parse_frontmatter(latest.read_text(encoding="utf-8"))
        recorded = meta.get("depends_on") or []
        dep_upstream_defs = [s for s in all_stage_defs if s.id in dep_stage.depends_on]
        current_hashes = _current_upstream_hashes(run_dir, dep_upstream_defs)
        if is_stale(recorded, current_hashes):
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)
            newly_stale.append(dep_stage.id)

    # Second level and beyond is status-driven, not hash-driven: a stale
    # stage's own artifact file is never rewritten (only its DB row changes),
    # so its dependents' recorded hashes still match and is_stale would say
    # False. Being built on a stage that is itself stale is what makes them
    # stale. Terminates regardless of topology because a stage is enqueued
    # only at the moment it leaves `approved`, so at most once.
    queue = list(newly_stale)
    while queue:
        stale_stage_id = queue.pop()
        for dep_stage in _dependents_of(all_stage_defs, stale_stage_id):
            row = db_mod.get_stage(conn, project_id, dep_stage.id)
            if row is None or row["status"] != StageStatus.APPROVED.value:
                continue
            db_mod.update_stage_status(conn, row["id"], StageStatus.STALE.value)
            queue.append(dep_stage.id)


def _dependents_of(all_stage_defs: list[StageDef], stage_id: str) -> list[StageDef]:
    return [s for s in all_stage_defs if stage_id in s.depends_on]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_turn_service.py -v`
Expected: all PASS

- [ ] **Step 5: Run the full suite**

Run: `cd pipeline-app && python -m pytest`
Expected: all PASS — in particular `test_regenerating_an_approved_stage_marks_approved_dependent_stale` in `test_approval_service.py` (a two-stage chain with nothing downstream of `scripting`, so the cascade loop finds no work and the assertion is unchanged), and every `test_routes_approve_edit.py` test exercising the hand-edit path, which calls this same function

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/turn_service.py pipeline-app/tests/test_turn_service.py
git commit -m "fix(pipeline-app): propagate staleness transitively so stages built on stale inputs stop reading approved"
```

---

## Deferred (not in scope for this plan)

One finding from the review was reviewed by Opus and deliberately left undone — not an oversight:

- **The grounding `grounding_pointer` side-channel isn't topology-driven.** `"00-grounding"` is a hardcoded string literal in three places in `routes/stages.py`. Opus's call: don't add an `optional_inputs` schema field for this. It would remove that one literal but leave every other piece of grounding-specific machinery hardcoded anyway (the brand check, the `stage_id == "grounding"` branch, the `rgs-briefs/` protocol), and preserving current behavior exactly would mean adding the field to all six non-grounding stages in `pipeline.yaml` for no behavior change — more config surface for the same coupling, without even generalizing to a hypothetical second optional-input stage (which would need its own storage protocol regardless). If `grounding`'s `dir_prefix` ever actually changes, the cheap fix is a one-line lookup helper, not a schema addition.
