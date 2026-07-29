# 90s cyberpunk/synthwave theme + layout redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `pipeline_app` a dark synthwave visual theme, a real sidebar+content page shell, and one shared header (wordmark/nav/breadcrumb/CLI-status) on every page — CSS + minimal template/context changes only, no new routes or behavior.

**Architecture:** All theme colors live in CSS custom properties in `pipeline_app/static/style.css`. `base.html` gains a `.app-shell` flex wrapper and includes a new `partials/header.html`. Each route adds two plain context keys (`active_nav`, `cli_available`) to the dict it already passes to `TemplateResponse`. `cli_available` is computed once at startup in `main.py`'s `create_app()` (mirrors the existing `app.state.orphaned_count` pattern) and read from `request.app.state.cli_available` by every route.

**Tech Stack:** FastAPI, Jinja2 (`fastapi.templating.Jinja2Templates`), vanilla CSS (CSS custom properties, `color-mix()`), pytest + `fastapi.testclient.TestClient`. No build step, no new dependencies.

## Global Constraints

- Vanilla CSS only — no build step, no CSS framework, no new dependencies (spec Goals).
- CSS-only + minimal context wiring — no new routes, no behavior changes (spec Non-goals).
- No animation beyond `:hover`/`:focus` transitions — no scanline/CRT effects, no animated backgrounds (spec Non-goals).
- No change to pipeline-nav ordering logic — styling only (spec Non-goals).
- No responsive/mobile layout work (spec Non-goals).
- Base body font size 18px; `pre`/`textarea` at `1rem` (matches the 18px base) — spec addition for readability.
- `doctor.html` keeps using its own per-request `cli` context value unchanged; `cli_available` is a separate, coarser, cached signal for the header dot only (spec §3).
- All working directories below are relative to `pipeline-app/` (the FastAPI project root), e.g. `pipeline_app/main.py` means `pipeline-app/pipeline_app/main.py`.

---

### Task 1: Compute `cli_available` once at app startup

**Files:**
- Modify: `pipeline_app/main.py:15-26`
- Test: `pipeline-app/tests/test_main.py` (new)

**Interfaces:**
- Consumes: `pipeline_app.preflight.check_cli_available() -> dict` (existing, returns `{"available": bool, "path": str|None, "error": str|None}`), already imported into `main.py` via `from pipeline_app import preflight`.
- Produces: `app.state.cli_available: bool`, set once in `create_app()`. Later tasks (routes) read this as `request.app.state.cli_available`.

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_main.py`:

```python
from pathlib import Path

import pytest

from pipeline_app.main import create_app


@pytest.fixture
def repo_root(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    return tmp_path


def test_cli_available_true_when_binary_found(repo_root: Path, monkeypatch):
    monkeypatch.setattr(
        "pipeline_app.preflight.check_cli_available",
        lambda: {"available": True, "path": r"C:\fake\claude.CMD", "error": None},
    )
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    assert app.state.cli_available is True


def test_cli_available_false_when_missing(repo_root: Path, monkeypatch):
    monkeypatch.setattr(
        "pipeline_app.preflight.check_cli_available",
        lambda: {"available": False, "path": None, "error": "not found"},
    )
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    assert app.state.cli_available is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_main.py -v`
Expected: FAIL — `AttributeError: 'State' object has no attribute 'cli_available'`

- [ ] **Step 3: Wire the startup computation**

In `pipeline_app/main.py`, the current `create_app` body (lines 15-26) is:

```python
def create_app(repo_root: Path, db_path: Path) -> FastAPI:
    app = FastAPI()
    app.state.repo_root = repo_root
    app.state.db_path = db_path
    app.state.stage_defs = load_topology(repo_root / "pipeline.yaml")

    schema_path = PACKAGE_DIR / "schema.sql"
    db_mod.init_db(db_path, schema_path)
    app.state.conn = db_mod.get_connection(db_path)
    app.state.orphaned_count = preflight.reconcile_orphaned_turns(
        app.state.conn, app.state.repo_root, app.state.stage_defs
    )

    app.state.templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
```

Add the `cli_available` computation right after `orphaned_count`:

```python
def create_app(repo_root: Path, db_path: Path) -> FastAPI:
    app = FastAPI()
    app.state.repo_root = repo_root
    app.state.db_path = db_path
    app.state.stage_defs = load_topology(repo_root / "pipeline.yaml")

    schema_path = PACKAGE_DIR / "schema.sql"
    db_mod.init_db(db_path, schema_path)
    app.state.conn = db_mod.get_connection(db_path)
    app.state.orphaned_count = preflight.reconcile_orphaned_turns(
        app.state.conn, app.state.repo_root, app.state.stage_defs
    )
    app.state.cli_available = preflight.check_cli_available()["available"]

    app.state.templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_main.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/main.py pipeline-app/tests/test_main.py
git commit -m "feat(pipeline-app): compute cli_available once at app startup"
```

---

### Task 2: Shared header partial + page shell in `base.html`

**Files:**
- Create: `pipeline_app/templates/partials/header.html`
- Modify: `pipeline_app/templates/base.html:109-113`
- Test: `pipeline-app/tests/test_header.py` (new)

**Interfaces:**
- Consumes: Jinja context vars `active_nav` (str, optional — not yet wired by any route until Task 3), `cli_available` (bool, optional), `project` (dict-like, optional), `stage_id` (str, optional). All are read with `is defined`/truthiness guards so the header renders correctly (nav all-inactive, breadcrumb hidden, dot "offline") even before Task 3 wires them in.
- Produces: `.site-header`, `.wordmark`, `.top-nav`, `.breadcrumb`, `.cli-status`, `.status-dot` — CSS hooks that Task 4 styles. `.app-shell`, `.app-sidebar`, `.app-main` — CSS hooks Task 4 also styles.

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_header.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app)


@pytest.mark.parametrize("url", ["/", "/skills", "/doctor", "/inspector"])
def test_every_page_renders_shared_header(client: TestClient, url: str):
    resp = client.get(url)
    assert resp.status_code == 200
    assert 'class="wordmark"' in resp.text
    assert 'class="top-nav"' in resp.text
    assert 'href="/skills"' in resp.text
    assert 'href="/doctor"' in resp.text
    assert 'href="/inspector"' in resp.text
    assert 'class="status-dot' in resp.text


def test_page_shell_wraps_sidebar_and_main(client: TestClient):
    resp = client.get("/")
    assert 'class="app-shell"' in resp.text
    assert 'class="app-sidebar"' in resp.text
    assert 'class="app-main"' in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_header.py -v`
Expected: FAIL — no `wordmark`/`app-shell` markup exists yet.

- [ ] **Step 3: Create the header partial**

Create `pipeline_app/templates/partials/header.html`:

```html
<header class="site-header">
  <a class="wordmark" href="/">ContentStudio</a>
  <nav class="top-nav">
    <a href="/" class="{{ 'active' if active_nav == 'projects' }}">Projects</a>
    <a href="/skills" class="{{ 'active' if active_nav == 'skills' }}">Skills</a>
    <a href="/doctor" class="{{ 'active' if active_nav == 'doctor' }}">Doctor</a>
    <a href="/inspector" class="{{ 'active' if active_nav == 'inspector' }}">Inspector</a>
  </nav>
  {% if project and stage_id %}
  <div class="breadcrumb">{{ project.run_id }} / {{ stage_id }}</div>
  {% endif %}
  <div class="cli-status">
    <span class="status-dot {{ 'online' if cli_available else 'offline' }}"></span>
    {{ "SYSTEM ONLINE" if cli_available else "CLI UNAVAILABLE" }}
  </div>
</header>
```

- [ ] **Step 4: Restructure `base.html`**

Replace `pipeline_app/templates/base.html:109-113`:

```html
<body>
  <header><a href="/">ContentStudio Pipeline</a></header>
  {% block sidebar %}{% include "partials/sidebar.html" %}{% endblock %}
  <main>{% block content %}{% endblock %}</main>
</body>
```

with:

```html
<body>
  {% include "partials/header.html" %}
  <div class="app-shell">
    <aside class="app-sidebar">{% block sidebar %}{% include "partials/sidebar.html" %}{% endblock %}</aside>
    <main class="app-main">{% block content %}{% endblock %}</main>
  </div>
</body>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_header.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Run the full existing test suite for regressions**

Run: `cd pipeline-app && python -m pytest -v`
Expected: PASS, no regressions (the old `<header><a href="/">ContentStudio Pipeline</a></header>` text is gone, but no existing test asserts on that exact string — confirm before moving on; if one does, update its assertion to check for `class="wordmark"` instead).

- [ ] **Step 7: Commit**

```bash
git add pipeline-app/pipeline_app/templates/partials/header.html pipeline-app/pipeline_app/templates/base.html pipeline-app/tests/test_header.py
git commit -m "feat(pipeline-app): add shared header partial and app-shell page layout"
```

---

### Task 3: Wire `active_nav` and `cli_available` into every route

**Files:**
- Modify: `pipeline_app/routes/projects.py:15-17,42-44`
- Modify: `pipeline_app/routes/stages.py:102-110`
- Modify: `pipeline_app/routes/skills.py:31-33,59-66`
- Modify: `pipeline_app/routes/inspector.py:13,39-42,44-46`
- Modify: `pipeline_app/routes/doctor.py:13-22`
- Test: `pipeline-app/tests/test_header.py` (extend from Task 2)

**Interfaces:**
- Consumes: `request.app.state.cli_available` (bool, produced by Task 1).
- Produces: every `TemplateResponse(...)` context dict now includes `"active_nav"` (one of `"projects"`, `"skills"`, `"doctor"`, `"inspector"`) and `"cli_available"` (bool) — read by `partials/header.html` from Task 2.

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_header.py`:

```python
def test_active_nav_marks_the_current_top_nav_link(client: TestClient):
    resp = client.get("/")
    assert '<a href="/" class="active">Projects</a>' in resp.text

    resp = client.get("/skills")
    assert '<a href="/skills" class="active">Skills</a>' in resp.text

    resp = client.get("/doctor")
    assert '<a href="/doctor" class="active">Doctor</a>' in resp.text

    resp = client.get("/inspector")
    assert '<a href="/inspector" class="active">Inspector</a>' in resp.text


def test_project_home_and_stage_page_mark_projects_active_with_breadcrumb(client: TestClient):
    client.post("/projects", data={"slug": "abc", "brand": "generic"})
    home = client.get("/")
    import re
    project_id = re.search(r'/projects/(\d+)', home.text).group(1)

    resp = client.get(f"/projects/{project_id}")
    assert '<a href="/" class="active">Projects</a>' in resp.text
    assert 'class="breadcrumb"' not in resp.text  # no stage_id on the project-home page
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_header.py -v`
Expected: FAIL — `active_nav` isn't wired yet, so every nav link renders `class=""`.

- [ ] **Step 3: Wire `projects.py`**

In `pipeline_app/routes/projects.py`, replace the `list_projects` return (lines 15-17):

```python
    return request.app.state.templates.TemplateResponse(
        request, "project_list.html", {"projects": projects}
    )
```

with:

```python
    return request.app.state.templates.TemplateResponse(
        request, "project_list.html",
        {
            "projects": projects,
            "active_nav": "projects",
            "cli_available": request.app.state.cli_available,
        },
    )
```

Replace the `project_home` return (lines 42-44):

```python
    return request.app.state.templates.TemplateResponse(
        request, "project_home.html", {"project": project, "nav": nav}
    )
```

with:

```python
    return request.app.state.templates.TemplateResponse(
        request, "project_home.html",
        {
            "project": project,
            "nav": nav,
            "active_nav": "projects",
            "cli_available": request.app.state.cli_available,
        },
    )
```

- [ ] **Step 4: Wire `stages.py`**

In `pipeline_app/routes/stages.py`, replace the `stage_page` return (lines 102-110):

```python
    return request.app.state.templates.TemplateResponse(
        request, "stage.html",
        {
            "project": project, "stage_id": stage_id, "stage_status": stage_row["status"],
            "input_body": input_body, "grounding_input_body": grounding_input_body,
            "output_body": output_body,
            "transcript": transcript, "nav": nav,
        },
    )
```

with:

```python
    return request.app.state.templates.TemplateResponse(
        request, "stage.html",
        {
            "project": project, "stage_id": stage_id, "stage_status": stage_row["status"],
            "input_body": input_body, "grounding_input_body": grounding_input_body,
            "output_body": output_body,
            "transcript": transcript, "nav": nav,
            "active_nav": "projects",
            "cli_available": request.app.state.cli_available,
        },
    )
```

- [ ] **Step 5: Wire `skills.py`**

In `pipeline_app/routes/skills.py`, replace the `skill_list` return (lines 31-33):

```python
    return request.app.state.templates.TemplateResponse(
        request, "skill_list.html", {"skill_names": skill_names}
    )
```

with:

```python
    return request.app.state.templates.TemplateResponse(
        request, "skill_list.html",
        {
            "skill_names": skill_names,
            "active_nav": "skills",
            "cli_available": request.app.state.cli_available,
        },
    )
```

Replace the `skill_detail` return (lines 59-66):

```python
    return request.app.state.templates.TemplateResponse(
        request, "skill_editor.html",
        {
            "skill_name": skill_name,
            "skill_md_content": skill_md_content,
            "kickoff_template_content": kickoff_template_content,
        },
    )
```

with:

```python
    return request.app.state.templates.TemplateResponse(
        request, "skill_editor.html",
        {
            "skill_name": skill_name,
            "skill_md_content": skill_md_content,
            "kickoff_template_content": kickoff_template_content,
            "active_nav": "skills",
            "cli_available": request.app.state.cli_available,
        },
    )
```

- [ ] **Step 6: Wire `inspector.py`**

In `pipeline_app/routes/inspector.py`, replace the `inspector_form` return (line 13):

```python
    return request.app.state.templates.TemplateResponse(request, "inspector.html", {})
```

with:

```python
    return request.app.state.templates.TemplateResponse(
        request, "inspector.html",
        {"active_nav": "inspector", "cli_available": request.app.state.cli_available},
    )
```

Replace the two `inspector_inspect` returns (lines 39-42 and 44-46):

```python
            return request.app.state.templates.TemplateResponse(
                request, "inspector.html",
                {"path": path, "frontmatter": meta, "body_html": markdown.markdown(body)},
            )

    return request.app.state.templates.TemplateResponse(
        request, "inspector.html", {"path": path, "error": error}
    )
```

with:

```python
            return request.app.state.templates.TemplateResponse(
                request, "inspector.html",
                {
                    "path": path, "frontmatter": meta, "body_html": markdown.markdown(body),
                    "active_nav": "inspector",
                    "cli_available": request.app.state.cli_available,
                },
            )

    return request.app.state.templates.TemplateResponse(
        request, "inspector.html",
        {
            "path": path, "error": error,
            "active_nav": "inspector",
            "cli_available": request.app.state.cli_available,
        },
    )
```

- [ ] **Step 7: Wire `doctor.py`**

In `pipeline_app/routes/doctor.py`, replace the `doctor_page` return (lines 13-22):

```python
    return request.app.state.templates.TemplateResponse(
        request, "doctor.html",
        {
            "repo_root": str(repo_root),
            "db_path": str(getattr(request.app.state, "db_path", "")),
            "cli": check_cli_available(),
            "skill_names": skill_names,
            "orphaned_count": getattr(request.app.state, "orphaned_count", 0),
        },
    )
```

with:

```python
    return request.app.state.templates.TemplateResponse(
        request, "doctor.html",
        {
            "repo_root": str(repo_root),
            "db_path": str(getattr(request.app.state, "db_path", "")),
            "cli": check_cli_available(),
            "skill_names": skill_names,
            "orphaned_count": getattr(request.app.state, "orphaned_count", 0),
            "active_nav": "doctor",
            "cli_available": request.app.state.cli_available,
        },
    )
```

Note: `doctor.html`'s own diagnostic content keeps reading `cli` (per-request, live `check_cli_available()` call, unchanged) — `cli_available` here is only for the shared header's status dot, matching the spec's §3 distinction.

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_header.py -v`
Expected: PASS (7 tests)

- [ ] **Step 9: Run the full existing test suite for regressions**

Run: `cd pipeline-app && python -m pytest -v`
Expected: PASS, no regressions.

- [ ] **Step 10: Commit**

```bash
git add pipeline-app/pipeline_app/routes/projects.py pipeline-app/pipeline_app/routes/stages.py pipeline-app/pipeline_app/routes/skills.py pipeline-app/pipeline_app/routes/inspector.py pipeline-app/pipeline_app/routes/doctor.py pipeline-app/tests/test_header.py
git commit -m "feat(pipeline-app): wire active_nav and cli_available into every route"
```

---

### Task 4: Dark synthwave theme (`style.css`)

**Files:**
- Modify: `pipeline_app/static/style.css` (full rewrite)

**Interfaces:**
- Consumes: the class hooks produced by Tasks 2-3 (`.app-shell`, `.app-sidebar`, `.app-main`, `.site-header`, `.wordmark`, `.top-nav`, `.breadcrumb`, `.cli-status`, `.status-dot`) and the existing class hooks already in `sidebar.html`/`stage.html`/etc. (`.pipeline-nav`, `.pipeline-step`, `.pipeline-stage`, `.status-*`, `.error`, `.stale-override-note`).
- Produces: nothing consumed by later tasks — this is the leaf styling layer. No HTML/class names change, so no route or template touches this task's output directly.

This is a CSS-only file with no unit-testable behavior; "tests" for this task are (a) the full existing test suite staying green (CSS changes can't break Python/Jinja assertions since no class names or markup change) and (b) a manual browser check at the end of the task.

- [ ] **Step 1: Confirm baseline — run the full test suite before touching CSS**

Run: `cd pipeline-app && python -m pytest -v`
Expected: PASS (baseline, confirms Tasks 1-3 left things green before this purely-visual change).

- [ ] **Step 2: Replace `pipeline_app/static/style.css` in full**

Replace the entire file contents with:

```css
:root {
  --bg: #0d0221;
  --bg-panel: #17092e;
  --bg-panel-raised: #1f0d3d;
  --border: #3a1d6e;
  --text: #e8e3f5;
  --text-dim: #9a8fc2;
  --accent-magenta: #ff2ee0;
  --accent-cyan: #00e5ff;
  --accent-purple: #a020f0;
  --accent-green: #39ff88;
  --accent-amber: #ffb020;
  --font-mono: "Courier New", ui-monospace, monospace;
}

body {
  font-family: system-ui, sans-serif;
  font-size: 18px;
  line-height: 1.5;
  margin: 0;
  background: var(--bg);
  color: var(--text);
}

h1, h2, h3 { font-family: var(--font-mono); }
h1 { color: var(--accent-cyan); text-shadow: 0 0 6px var(--accent-cyan); }
h2, h3 { color: var(--text); }

a { color: var(--accent-cyan); text-decoration: none; }
a:visited { color: var(--accent-purple); }
a:hover { text-decoration: underline; }

pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-width: 70ch;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 1rem;
  padding: 0.75rem;
  border-radius: 0.25rem;
  box-sizing: border-box;
}

textarea {
  width: 100%;
  box-sizing: border-box;
  min-height: 5rem;
  background: var(--bg-panel-raised);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 0.25rem;
  font-family: inherit;
  font-size: 1rem;
  padding: 0.5rem;
}

button {
  padding: 0.35rem 0.75rem;
  cursor: pointer;
  font-family: var(--font-mono);
  background: var(--bg-panel-raised);
  color: var(--accent-magenta);
  border: 1px solid var(--accent-magenta);
  border-radius: 0.25rem;
  transition: box-shadow 0.15s, background 0.15s;
}
button:hover { background: var(--bg-panel); box-shadow: 0 0 8px var(--accent-magenta); }

table { border-collapse: collapse; color: var(--text); }
th, td { text-align: left; padding: 0.25rem 0.75rem 0.25rem 0; vertical-align: top; }

.status {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.85rem;
  font-family: var(--font-mono);
  border: 1px solid transparent;
}
.status-locked { background: color-mix(in srgb, var(--text-dim) 20%, transparent); color: var(--text-dim); border-color: var(--border); }
.status-ready { background: color-mix(in srgb, var(--accent-cyan) 20%, transparent); color: var(--accent-cyan); border-color: var(--accent-cyan); }
.status-running { background: color-mix(in srgb, var(--accent-amber) 25%, transparent); color: var(--accent-amber); border-color: var(--accent-amber); }
.status-awaiting_review { background: color-mix(in srgb, var(--accent-magenta) 20%, transparent); color: var(--accent-magenta); border-color: var(--accent-magenta); }
.status-approved { background: color-mix(in srgb, var(--accent-green) 20%, transparent); color: var(--accent-green); border-color: var(--accent-green); }
.status-stale { background: color-mix(in srgb, #ff5f5f 25%, transparent); color: #ff5f5f; border-color: #ff5f5f; }
.status-no_artifact { background: transparent; color: var(--text-dim); border: 1px dashed var(--text-dim); }

.pipeline-nav { list-style: none; margin: 0; padding: 0; }
.pipeline-step {
  margin-left: 0.4rem;
  padding: 0 0 1.25rem 1rem;
  border-left: 2px solid var(--border);
}
.pipeline-step:last-child { border-left-color: transparent; padding-bottom: 0; }
.step-number {
  display: inline-block;
  min-width: 1.25rem;
  font-weight: bold;
  color: var(--text-dim);
  margin-right: 0.35rem;
}
.pipeline-step-group { display: flex; gap: 1rem; flex-wrap: wrap; }
.pipeline-stage {
  border-left: 3px solid transparent;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
}
.pipeline-stage.current {
  border-left-color: var(--accent-cyan);
  background: color-mix(in srgb, var(--accent-cyan) 12%, transparent);
}
.specialist { font-size: 0.75rem; color: var(--text-dim); margin: 0.15rem 0 0; }

.error { color: #ff5f5f; }
.input-panel, .chat-panel, .output-panel { margin-bottom: 1.5rem; }
.stale-override-note { color: var(--accent-amber); font-size: 0.9rem; }

.app-shell { display: flex; gap: 2rem; align-items: flex-start; padding: 1.5rem 2rem; }
.app-sidebar { flex: 0 0 260px; }
.app-main { flex: 1 1 auto; min-width: 0; max-width: 1400px; }

.site-header {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.75rem 1.5rem;
  background: linear-gradient(var(--bg-panel), var(--bg-panel)),
              repeating-linear-gradient(transparent 0 7px, var(--accent-purple) 7px 8px);
  background-blend-mode: normal, screen;
  border-bottom: 2px solid var(--accent-magenta);
  box-shadow: 0 0 12px var(--accent-magenta);
}
.wordmark {
  font-family: var(--font-mono);
  color: var(--accent-cyan);
  text-shadow: 0 0 6px var(--accent-cyan);
  text-decoration: none;
  font-weight: bold;
  font-size: 1.1rem;
}
.top-nav a { color: var(--text-dim); text-decoration: none; margin-right: 1rem; font-family: var(--font-mono); }
.top-nav a:hover { color: var(--text); text-decoration: none; }
.top-nav a.active { color: var(--accent-magenta); text-shadow: 0 0 4px var(--accent-magenta); }
.breadcrumb { color: var(--text-dim); font-family: var(--font-mono); font-size: 0.9rem; }
.cli-status { margin-left: auto; font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-dim); white-space: nowrap; }
.status-dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; margin-right: 0.35rem; }
.status-dot.online { background: var(--accent-green); box-shadow: 0 0 6px var(--accent-green); }
.status-dot.offline { background: #ff4444; box-shadow: 0 0 6px #ff4444; }
```

Note: the old bare `header { margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #ddd; }` rule is dropped — `base.html` no longer has an unstyled `<header>`; the new `<header class="site-header">` from Task 2 is styled explicitly above. The `a`/`a:visited`/`a:hover` rules are new (not in the original spec text) and required for legibility: default browser link-blue is illegible against the new near-black background, the same class of fix the spec already calls out for `.error`.

- [ ] **Step 3: Run the full test suite again**

Run: `cd pipeline-app && python -m pytest -v`
Expected: PASS, identical result to Step 1 (CSS-only change, no markup/class names touched).

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/pipeline_app/static/style.css
git commit -m "feat(pipeline-app): dark synthwave theme for pipeline-app UI"
```

---

### Task 5: Manual browser verification

**Files:** none (verification only).

- [ ] **Step 1: Start the app**

Run: `cd pipeline-app && python -m uvicorn pipeline_app.main:create_default_app --factory --reload`

- [ ] **Step 2: Verify header and nav on every page**

Open `http://127.0.0.1:8000/`, `/skills`, `/doctor`, `/inspector` in a browser. Confirm on each: the "ContentStudio" wordmark and all four nav links render in the header; the link matching the current page is magenta/highlighted; the CLI status dot shows green "SYSTEM ONLINE" or red "CLI UNAVAILABLE" depending on whether `claude` is on `PATH`.

- [ ] **Step 3: Verify project/stage pages**

Create a project from `/`, open its project-home page (confirm "Projects" stays highlighted, no breadcrumb), then open a stage page (confirm the breadcrumb shows `<run_id> / <stage_id>`).

- [ ] **Step 4: Verify layout**

On a project page with a populated pipeline nav, confirm the sidebar and main content sit side by side (not stacked), and the main content column does not exceed `max-width: 1400px` at a wide viewport.

- [ ] **Step 5: Verify legibility**

Open a stage page with long `pre`-rendered output (script/transcript) and confirm it's legible against the dark background at the new 18px base size. Confirm `.status-*` pills, error text, and stale-override notes are all readable.

- [ ] **Step 6: Stop the server**

Ctrl+C in the terminal running uvicorn.

---

## Self-Review Notes

- **Spec coverage:** §1 Palette/typography → Task 4. §2 Page shell → Task 2. §3 Header (`active_nav`, `cli_available`, decorative strip) → Tasks 1-3 (wiring) + Task 4 (CSS). §4 Existing color-bearing elements → Task 4. §5 Files touched → matches Tasks 1-4's file lists exactly. Testing section → Task 5 mirrors its manual checklist verbatim; automated tests in Tasks 1-3 cover the parts of Testing that are checkable without a browser (nav links exist, active-marking works, status dot renders).
- **Font-size spec addition:** covered in Task 4 (`body { font-size: 18px; }`, `pre`/`textarea` at `1rem`).
- **Type/name consistency:** `app.state.cli_available` (Task 1) is read identically as `request.app.state.cli_available` in every route (Task 3) and as bare `cli_available` in the Jinja context/template (Task 2). `active_nav` string values (`"projects"`, `"skills"`, `"doctor"`, `"inspector"`) match exactly between Task 3's route wiring and Task 2's `header.html` conditionals.
- **doctor.html distinction preserved:** Task 3 Step 7 keeps `doctor.py`'s existing `"cli": check_cli_available()` key untouched and only adds the new `"cli_available"` key alongside it, per spec §3.
