# Pipeline Nav Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the pipeline-app's stage sidebar so it shows the seven pipeline stages in correct dependency order, groups the parallel Voiceover/Visual pair visually, labels their `elevenlabs-audio`/`midjourney-prompting` specialist skills, and appears on every stage page (not just project-home) with the current stage highlighted.

**Architecture:** A new `specialist` field on `StageDef` (read from `pipeline.yaml`) plus a pure `build_stage_nav()` helper turn the existing ordered stage topology and a project's DB stage rows into a grouped nav structure. Both the project-home and stage-page routes call this same helper and pass the result as `nav` to a single shared Jinja partial, so there is exactly one place that renders the pipeline nav.

**Tech Stack:** Python 3, FastAPI, Jinja2 templates, SQLite (stdlib `sqlite3`), pytest + FastAPI `TestClient`. No new dependencies.

## Global Constraints

- Do not change `pipeline.yaml`'s stage semantics, dependency graph, or `state_machine.py` — this is a display-only change.
- Do not change how stages are created, approved, or run.
- `midjourney-prompting` and `elevenlabs-audio` remain specialist skills referenced *by* the Visual/Voiceover stages — they get no `dir_prefix`, DB row, status, or directory of their own.
- All styling lives in the existing `pipeline_app/static/style.css` — no new CSS files, no build step, no JS, no new dependencies.
- Follow existing test patterns: pytest + FastAPI `TestClient`, tests under `pipeline-app/tests/`, run via `python -m pytest` from `pipeline-app/`.

---

### Task 1: Add `specialist` field to `StageDef` and `pipeline.yaml`

**Files:**
- Modify: `pipeline-app/pipeline_app/pipeline_config.py`
- Modify: `pipeline.yaml`
- Test: `pipeline-app/tests/test_pipeline_config.py`

**Interfaces:**
- Produces: `StageDef.specialist: str | None` (default `None`), populated by `load_topology()` from an optional `specialist:` key per stage entry. Task 2's `build_stage_nav()` reads this field.

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_pipeline_config.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: the three new tests FAIL with `AttributeError: 'StageDef' object has no attribute 'specialist'`.

- [ ] **Step 3: Add the field to `StageDef` and read it in `load_topology()`**

In `pipeline-app/pipeline_app/pipeline_config.py`, change:

```python
@dataclass
class StageDef:
    id: str
    skill: str
    dir_prefix: str
    depends_on: list[str] = field(default_factory=list)
    brand_scope: str | None = None
```

to:

```python
@dataclass
class StageDef:
    id: str
    skill: str
    dir_prefix: str
    depends_on: list[str] = field(default_factory=list)
    brand_scope: str | None = None
    specialist: str | None = None
```

and change:

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
        )
        for s in data["stages"]
    ]
```

to:

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

- [ ] **Step 4: Add `specialist:` to the `voiceover` and `visual` entries in `pipeline.yaml`**

In `pipeline.yaml` (repo root), change:

```yaml
  - id: voiceover
    skill: voiceover-brief
    dir_prefix: "03"
    depends_on: [scripting]
  - id: visual
    skill: visual-prompts
    dir_prefix: "03"
    depends_on: [scripting]
```

to:

```yaml
  - id: voiceover
    skill: voiceover-brief
    specialist: elevenlabs-audio
    dir_prefix: "03"
    depends_on: [scripting]
  - id: visual
    skill: visual-prompts
    specialist: midjourney-prompting
    dir_prefix: "03"
    depends_on: [scripting]
```

- [ ] **Step 5: Run the tests and verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: all tests PASS (the 3 new ones plus the existing 7).

Run the full suite too, since `StageDef` is used across several test files:
Run: `cd pipeline-app && python -m pytest -q`
Expected: all tests PASS (adding an optional trailing field with a default breaks nothing — every existing `StageDef(...)` construction in the test suite uses keyword arguments).

- [ ] **Step 6: Commit**

```bash
git add pipeline.yaml pipeline-app/pipeline_app/pipeline_config.py pipeline-app/tests/test_pipeline_config.py
git commit -m "feat(pipeline-app): add optional specialist field to StageDef"
```

---

### Task 2: Add `build_stage_nav()` helper

**Files:**
- Modify: `pipeline-app/pipeline_app/pipeline_config.py`
- Test: `pipeline-app/tests/test_pipeline_config.py`

**Interfaces:**
- Consumes: `StageDef` (`.id`, `.dir_prefix`, `.specialist`) from Task 1; `stage_rows` — any iterable of mapping-like objects supporting `row["stage_id"]` and `row["status"]` (both `sqlite3.Row` and plain `dict` satisfy this).
- Produces: `build_stage_nav(stage_defs: list[StageDef], stage_rows) -> list[list[dict]]`. Each inner list is one "step" (1 item normally, 2 for the voiceover/visual pair); each dict is `{"id": str, "status": str, "specialist": str | None}`. Task 3's routes call this and pass the result as `nav` in template context.

- [ ] **Step 1: Write the failing tests**

First, add `StageDef` and `build_stage_nav` to the existing import line near the top of `pipeline-app/tests/test_pipeline_config.py`. Change:

```python
from pipeline_app.pipeline_config import load_topology, stage_dir_name
```
to:
```python
from pipeline_app.pipeline_config import StageDef, build_stage_nav, load_topology, stage_dir_name
```

Then append to the same file:

```python
def _stage_def(id, dir_prefix, specialist=None, depends_on=None):
    return StageDef(
        id=id, skill=f"skill-{id}", dir_prefix=dir_prefix,
        depends_on=depends_on or [], specialist=specialist,
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
    stage_defs = [_stage_def("visual", "03", specialist="midjourney-prompting")]
    stage_rows = [{"stage_id": "visual", "status": "awaiting_review"}]
    nav = build_stage_nav(stage_defs, stage_rows)
    assert nav == [[{"id": "visual", "status": "awaiting_review", "specialist": "midjourney-prompting"}]]


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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: a collection ERROR for the whole file — `ImportError: cannot import name 'build_stage_nav'` — since the import is module-level, every test in `test_pipeline_config.py` errors, not just the new ones. This confirms `build_stage_nav` doesn't exist yet.

- [ ] **Step 3: Implement `build_stage_nav()`**

Append to `pipeline-app/pipeline_app/pipeline_config.py`:

```python
def build_stage_nav(stage_defs: list[StageDef], stage_rows) -> list[list[dict]]:
    """Merge the ordered/filtered stage topology with a project's DB stage
    rows into grouped nav steps, in stage_defs order (already dependency-
    correct — NOT re-sorted by dir_prefix). Stages sharing a dir_prefix (the
    voiceover/visual parallel pair) group into one step. A stage_def with no
    matching row (a brand-scoped stage this project doesn't have) is
    omitted, same as it already is everywhere else in the app."""
    rows_by_id = {row["stage_id"]: row for row in stage_rows}
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for stage_def in stage_defs:
        row = rows_by_id.get(stage_def.id)
        if row is None:
            continue
        entry = {"id": stage_def.id, "status": row["status"], "specialist": stage_def.specialist}
        if stage_def.dir_prefix not in groups:
            groups[stage_def.dir_prefix] = []
            order.append(stage_def.dir_prefix)
        groups[stage_def.dir_prefix].append(entry)
    return [groups[prefix] for prefix in order]
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_pipeline_config.py -v`
Expected: all 14 tests PASS (7 original + 3 from Task 1 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/pipeline_config.py pipeline-app/tests/test_pipeline_config.py
git commit -m "feat(pipeline-app): add build_stage_nav helper for grouped pipeline nav"
```

---

### Task 3: Wire `nav` into both routes and render it on every page

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/projects.py`
- Modify: `pipeline-app/pipeline_app/routes/stages.py`
- Create: `pipeline-app/pipeline_app/templates/partials/sidebar.html`
- Modify: `pipeline-app/pipeline_app/templates/base.html`
- Modify: `pipeline-app/pipeline_app/templates/project_home.html`
- Test: `pipeline-app/tests/test_routes_projects.py`
- Test: `pipeline-app/tests/test_routes_stages.py`

**Interfaces:**
- Consumes: `build_stage_nav()` from Task 2; `db_mod.list_stages(conn, project_id)`; `request.app.state.stage_defs`.
- Produces: template context key `nav: list[list[dict]]`, present on both `project_home.html` and `stage.html` renders. `stage.html`'s render also carries `stage_id: str` (already does) — the partial uses it to mark the current stage.

Note: `pipeline-app/pipeline_app/setup.py` already lists `"templates/partials/*.html"` in `package_data`, so the new partial's location needs no packaging change.

- [ ] **Step 1: Write the failing tests**

Add near the top of `pipeline-app/tests/test_routes_projects.py`, replacing the standalone `import re` inside `test_project_home_shows_stage_names` with a module-level import (so both that test and the new one can use it):

Change:
```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app
```
to:
```python
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app
```

Change:
```python
def test_project_home_shows_stage_names(client: TestClient):
    client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    listing = client.get("/")
    # extract the project id from the link the template renders
    import re
    match = re.search(r'/projects/(\d+)', listing.text)
```
to:
```python
def test_project_home_shows_stage_names(client: TestClient):
    client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    listing = client.get("/")
    # extract the project id from the link the template renders
    match = re.search(r'/projects/(\d+)', listing.text)
```

Then append these two new tests to the same file:

```python
def test_project_home_groups_parallel_stages_and_shows_specialist(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: []\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    specialist: elevenlabs-audio\n"
        "    dir_prefix: \"03\"\n    depends_on: [scripting]\n"
        "  - id: visual\n    skill: visual-prompts\n    specialist: midjourney-prompting\n"
        "    dir_prefix: \"03\"\n    depends_on: [scripting]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app)

    test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    listing = test_client.get("/")
    match = re.search(r'/projects/(\d+)', listing.text)
    assert match is not None
    project_id = match.group(1)

    home = test_client.get(f"/projects/{project_id}")
    assert home.status_code == 200
    assert "elevenlabs-audio" in home.text
    assert "midjourney-prompting" in home.text
    # scripting is its own step; voiceover+visual share dir_prefix "03" and
    # must render inside ONE grouped step, not two.
    assert home.text.count('class="pipeline-step"') == 2


def test_project_home_nav_has_no_current_highlight(client: TestClient):
    client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    listing = client.get("/")
    match = re.search(r'/projects/(\d+)', listing.text)
    project_id = match.group(1)
    home = client.get(f"/projects/{project_id}")
    # project-home has no "current" stage, so no stage should render the
    # current-highlight class — checked as the exact class token (not a bare
    # "current" substring, which could false-positive on unrelated text).
    assert 'class="pipeline-stage current"' not in home.text
```

Append these tests to `pipeline-app/tests/test_routes_stages.py`:

```python
def test_stage_page_shows_pipeline_nav_with_current_highlight(client):
    test_client, _tmp_path, _app = client
    project_id = _generic_project_id(test_client)

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert 'class="pipeline-stage current"' in page.text


def test_stage_page_shows_grouped_parallel_pair_in_nav(tmp_path: Path, monkeypatch):
    # The shared `client` fixture's pipeline.yaml has no parallel pair, so it
    # can never exercise grouping through the stage route — this test uses
    # its own pipeline.yaml specifically to cover that gap.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: []\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    specialist: elevenlabs-audio\n"
        "    dir_prefix: \"03\"\n    depends_on: [scripting]\n"
        "  - id: visual\n    skill: visual-prompts\n    specialist: midjourney-prompting\n"
        "    dir_prefix: \"03\"\n    depends_on: [scripting]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    page = test_client.get(f"/projects/{project_id}/stages/voiceover")
    assert page.status_code == 200
    assert "elevenlabs-audio" in page.text
    assert "midjourney-prompting" in page.text
    # scripting is its own step; voiceover+visual share dir_prefix "03" and
    # must render inside ONE grouped step, not two.
    assert page.text.count('class="pipeline-step"') == 2
    # voiceover is the current stage on this page
    assert 'class="pipeline-stage current"' in page.text
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_routes_projects.py tests/test_routes_stages.py -v`
Expected: 3 of the 4 new tests FAIL — `test_project_home_groups_parallel_stages_and_shows_specialist`, `test_stage_page_shows_pipeline_nav_with_current_highlight`, and `test_stage_page_shows_grouped_parallel_pair_in_nav` fail with `AssertionError` because the sidebar markup doesn't exist yet on either page; `test_project_home_nav_has_no_current_highlight` passes trivially today (there's no "current" markup at all yet) but is included so it stays green once the highlight is added elsewhere.

- [ ] **Step 3: Wire `nav` into `routes/projects.py`**

In `pipeline-app/pipeline_app/routes/projects.py`, change the import line:

```python
from pipeline_app.project_service import create_project
```
to:
```python
from pipeline_app.pipeline_config import build_stage_nav
from pipeline_app.project_service import create_project
```

and change:

```python
@router.get("/projects/{project_id}")
def project_home(request: Request, project_id: int):
    conn = request.app.state.conn
    project = db_mod.get_project(conn, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    stages = db_mod.list_stages(conn, project_id)
    return request.app.state.templates.TemplateResponse(
        request, "project_home.html", {"project": project, "stages": stages}
    )
```
to:
```python
@router.get("/projects/{project_id}")
def project_home(request: Request, project_id: int):
    conn = request.app.state.conn
    project = db_mod.get_project(conn, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    stage_rows = db_mod.list_stages(conn, project_id)
    nav = build_stage_nav(request.app.state.stage_defs, stage_rows)
    return request.app.state.templates.TemplateResponse(
        request, "project_home.html", {"project": project, "nav": nav}
    )
```

- [ ] **Step 4: Wire `nav` into `routes/stages.py`**

In `pipeline-app/pipeline_app/routes/stages.py`, change the import line:

```python
from pipeline_app.pipeline_config import stage_dir_name
```
to:
```python
from pipeline_app.pipeline_config import build_stage_nav, stage_dir_name
```

and change:

```python
    transcript = _load_transcript(stage_dir)

    return request.app.state.templates.TemplateResponse(
        request, "stage.html",
        {
            "project": project, "stage_id": stage_id,
            "input_body": input_body, "output_body": output_body,
            "transcript": transcript,
        },
    )
```
to:
```python
    transcript = _load_transcript(stage_dir)
    stage_rows = db_mod.list_stages(request.app.state.conn, project_id)
    nav = build_stage_nav(stage_defs, stage_rows)

    return request.app.state.templates.TemplateResponse(
        request, "stage.html",
        {
            "project": project, "stage_id": stage_id,
            "input_body": input_body, "output_body": output_body,
            "transcript": transcript, "nav": nav,
        },
    )
```

- [ ] **Step 5: Create the shared sidebar partial**

Create `pipeline-app/pipeline_app/templates/partials/sidebar.html`:

```html
{% if nav %}
<ol class="pipeline-nav">
  {% for group in nav %}
  <li class="pipeline-step">
    <span class="step-number">{{ loop.index }}</span>
    <div class="pipeline-step-group">
      {% for stage in group %}
      <div class="pipeline-stage{% if stage_id is defined and stage.id == stage_id %} current{% endif %}">
        <a href="/projects/{{ project.id }}/stages/{{ stage.id }}">{{ stage.id }}</a>
        <span class="status status-{{ stage.status }}">{{ stage.status }}</span>
        {% if stage.specialist %}
        <div class="specialist">&#8618; {{ stage.specialist }}</div>
        {% endif %}
      </div>
      {% endfor %}
    </div>
  </li>
  {% endfor %}
</ol>
{% endif %}
```

Step numbering is deliberately the nav list's 1-based position (`loop.index`), not the raw `dir_prefix` string — `dir_prefix` only drives grouping (in `build_stage_nav`); the visible number is a pure template-rendering concern, giving the approved "1, 2, 3…" sequence rather than showing zero-padded prefixes like "00".

Note on the partial's location: the spec named it `templates/_sidebar.html`, but `pipeline-app/setup.py`'s `package_data` already lists `"templates/partials/*.html"` — an existing packaging convention for exactly this kind of file. Using `templates/partials/sidebar.html` here follows that existing convention instead of introducing a new one.

- [ ] **Step 6: Point `base.html`'s sidebar block at the partial**

In `pipeline-app/pipeline_app/templates/base.html`, change:

```html
  {% block sidebar %}{% endblock %}
```
to:
```html
  {% block sidebar %}{% include "partials/sidebar.html" %}{% endblock %}
```

- [ ] **Step 7: Remove the now-redundant sidebar override from `project_home.html`**

Replace the full contents of `pipeline-app/pipeline_app/templates/project_home.html` with:

```html
{% extends "base.html" %}
{% block content %}
<h1>{{ project.run_id }}</h1>
{% endblock %}
```

(`stage.html` needs no template change — it never defined a `sidebar` block, so it already inherits the new default.)

- [ ] **Step 8: Run the tests and verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_projects.py tests/test_routes_stages.py -v`
Expected: all tests PASS.

Then run the full suite:
Run: `cd pipeline-app && python -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add pipeline-app/pipeline_app/routes/projects.py pipeline-app/pipeline_app/routes/stages.py pipeline-app/pipeline_app/templates/partials/sidebar.html pipeline-app/pipeline_app/templates/base.html pipeline-app/pipeline_app/templates/project_home.html pipeline-app/tests/test_routes_projects.py pipeline-app/tests/test_routes_stages.py
git commit -m "feat(pipeline-app): render grouped pipeline nav on project-home and stage pages"
```

---

### Task 4: Style the pipeline nav

**Files:**
- Modify: `pipeline-app/pipeline_app/static/style.css`

**Interfaces:**
- Consumes: the class names used by `partials/sidebar.html` from Task 3 (`pipeline-nav`, `pipeline-step`, `pipeline-step-group`, `pipeline-stage`, `current`, `specialist`) and the existing `.status-*` classes (unchanged).
- Produces: no code interface — this task is pure CSS, verified manually per Step 2 below rather than by an automated test.

- [ ] **Step 1: Add the nav styling**

Append to `pipeline-app/pipeline_app/static/style.css`:

```css
.pipeline-nav { list-style: none; margin: 0; padding: 0; }
.pipeline-step {
  position: relative;
  margin-left: 0.4rem;
  padding: 0 0 1.25rem 1rem;
  border-left: 2px solid #ddd;
}
.pipeline-step:last-child { border-left-color: transparent; padding-bottom: 0; }
.step-number {
  display: inline-block;
  min-width: 1.25rem;
  font-weight: bold;
  color: #666;
  margin-right: 0.35rem;
}
.pipeline-step-group { display: flex; gap: 1rem; flex-wrap: wrap; }
.pipeline-stage.current {
  border-left: 3px solid #2b6fd1;
  background: #eef4fd;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
}
.specialist { font-size: 0.75rem; color: #777; margin: 0.15rem 0 0; }
```

- [ ] **Step 2: Manually verify in a browser**

This step has no automated test — CSS appearance isn't something pytest checks. Start the dev server:

```bash
cd pipeline-app
uvicorn pipeline_app.main:create_default_app --factory --host 127.0.0.1 --port 8420
```

Open `http://127.0.0.1:8420/`, create a project (any slug, brand `generic` or `raisinggoodsports`), and open its project-home page, then click into the Voiceover or Visual stage. Confirm:
- The seven (or six, for `generic`) stages appear in pipeline order, each step numbered sequentially (1, 2, 3…), with a visible connector line between steps.
- Voiceover and Visual render side-by-side under the same step number as one grouped step, each showing its `↳ specialist` sub-line (`elevenlabs-audio` / `midjourney-prompting`).
- The nav appears identically on the project-home page and on every individual stage page.
- On a stage page, that stage is visually highlighted (accent border/background) in the nav.

If you can't open a browser in your current environment, say so explicitly rather than reporting this task as fully verified — the pytest suite from Task 3 confirms the markup and grouping are structurally correct, but not that it looks right.

- [ ] **Step 3: Commit**

```bash
git add pipeline-app/pipeline_app/static/style.css
git commit -m "style(pipeline-app): add connector-line and grouped-pair styling to pipeline nav"
```
