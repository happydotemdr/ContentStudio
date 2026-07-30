# Browse Page for output/ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only "Browse" page to `pipeline-app` that lets the user navigate the folder tree under `output/` and read any `.md` file in it, rendered the same way Inspector renders one.

**Architecture:** A new pure-logic module `pipeline_app/browse_service.py` (path safety, folder listing, file rendering — no FastAPI/Jinja imports, fully unit-testable) backs a new thin route module `pipeline_app/routes/browse.py` with three GET endpoints (`/browse` full page, `/browse/tree` and `/browse/file` htmx partials). Two new templates (`browse.html`, `partials/browse_tree_items.html`, `partials/browse_file.html`) render the tree and the selected document.

**Tech Stack:** FastAPI + Jinja2Templates + htmx 2.0 (already loaded site-wide via `base.html`) + Python's stdlib `pathlib`/`os.scandir` + existing `markdown`/`pyyaml` deps (already in `requirements.txt`, no new dependency).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-30-output-browse-page-design.md` (read this before starting — every task below implements a section of it).
- Read-only. No write/delete/edit endpoints anywhere in this feature.
- Scoped to `output/` only — every path the routes accept is relative to `(repo_root / "output").resolve()`, never absolute, never touching Inspector's existing open-path behavior.
- Every route always returns HTTP 200, even for error/empty states — the response body is an error/empty partial, never a 4xx/5xx (htmx 2.x's default `responseHandling` does not swap non-2xx bodies into the DOM, so a 400 would silently do nothing).
- Symlinks are never followed, anywhere in this feature (no symlink support in v1).
- `.md` matching is always case-insensitive (`.suffix.lower() == ".md"` / `name.lower().endswith(".md")`).
- Files over 5 MB (`5 * 1024 * 1024` bytes, checked via `stat()` before reading) render an oversize message instead of their content — never read into memory.
- All relative paths emitted into HTML (in `hx-get` URLs) use `PurePath.as_posix()` — never a raw `str(path)`, which would emit backslashes on Windows.
- This worktree's `output/` directory does not exist (git-ignored, only present in the main checkout). Every automated test builds its own fake `output/` tree under `tmp_path`; nothing in this plan touches the real corpus.
- This worktree's `base.html` currently has no nav list at all (a prior refactor removed `partials/header.html`) — the only UI change to it is one added `<a href="/browse">Browse</a>` link, not a rebuilt nav system.

---

## File Structure

- **Create** `pipeline_app/browse_service.py` — path safety, folder listing, file rendering. No FastAPI/Jinja imports; pure functions over `pathlib`/`os.scandir`, importing only `pipeline_app.artifacts`, `markdown`, `yaml`.
- **Create** `pipeline_app/routes/browse.py` — three thin FastAPI route handlers calling into `browse_service`.
- **Create** `pipeline_app/templates/browse.html` — full page, extends `base.html`.
- **Create** `pipeline_app/templates/partials/browse_tree_items.html` — renders one folder's children (used by both the initial page load and the `/browse/tree` htmx partial response — same context shape, same template, no duplication).
- **Create** `pipeline_app/templates/partials/browse_file.html` — renders a selected file's frontmatter + body, or its error/oversize state.
- **Modify** `pipeline_app/main.py` — register `browse.router`.
- **Modify** `pipeline_app/templates/base.html` — add the one `<a href="/browse">Browse</a>` link.
- **Modify** `pipeline_app/static/style.css` — append Browse layout rules (two-pane shell, `<details>`/`<summary>` tree styling, htmx-indicator spinner rule).
- **Create** `tests/test_browse_service.py` — unit tests for the pure-logic module.
- **Create** `tests/test_routes_browse.py` — HTTP-level tests for the three routes, following the existing `tests/test_routes_inspector.py` fixture pattern.

## Interfaces produced by `browse_service.py` (used by every later task)

```python
class PathSafetyError(Exception): ...

def output_root(repo_root: Path) -> Path: ...

def resolve_under_output(root: Path, rel_path: str) -> Path: ...
# raises PathSafetyError for absolute/".."/colon-containing/escaping input

@dataclass(frozen=True)
class Entry:
    name: str
    rel_path: str   # forward-slash path, relative to output root
    is_dir: bool

def list_children(folder: Path, root: Path) -> list[Entry]: ...
# folders first then files, each case-insensitive alphabetical;
# symlinks always skipped; subfolders with no .md anywhere below are omitted

MAX_FILE_BYTES: int  # 5 * 1024 * 1024

def render_md_file(path: Path) -> dict: ...
# returns one of:
#   {"frontmatter": dict, "body_html": str}
#   {"oversize": True, "size_mb": float, "cap_mb": float, "abs_path": str}
#   {"error": str}
```

---

### Task 1: Path safety (`browse_service.py`)

**Files:**
- Create: `pipeline_app/browse_service.py`
- Test: `tests/test_browse_service.py`

**Interfaces:**
- Produces: `PathSafetyError`, `output_root(repo_root: Path) -> Path`, `resolve_under_output(root: Path, rel_path: str) -> Path`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_browse_service.py
from pathlib import Path

import pytest

from pipeline_app import browse_service


@pytest.fixture
def root(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    return browse_service.output_root(tmp_path)


def test_output_root_resolves_under_repo_root(tmp_path):
    (tmp_path / "output").mkdir()
    result = browse_service.output_root(tmp_path)
    assert result == (tmp_path / "output").resolve()


def test_resolve_under_output_empty_path_returns_root(root):
    assert browse_service.resolve_under_output(root, "") == root


def test_resolve_under_output_nested_path(root):
    nested = root / "thinkers" / "anchorandwave"
    nested.mkdir(parents=True)
    result = browse_service.resolve_under_output(root, "thinkers/anchorandwave")
    assert result == nested.resolve()


def test_resolve_under_output_rejects_dotdot(root):
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "../../../etc")


def test_resolve_under_output_rejects_posix_absolute(root):
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "/etc/passwd")


def test_resolve_under_output_rejects_windows_absolute(root):
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "C:/Windows")


def test_resolve_under_output_rejects_leading_backslash(root):
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "\\Windows\\System32")


def test_resolve_under_output_rejects_drive_relative(root):
    # "C:foo" has a drive but no root -- pathlib's is_absolute() returns
    # False for this form, so it needs its own explicit rejection (a colon
    # anywhere in the input is never valid in a real output/ filename).
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "C:foo")


def test_resolve_under_output_rejects_sibling_prefix_escape(tmp_path):
    (tmp_path / "output").mkdir()
    (tmp_path / "output-old").mkdir()
    (tmp_path / "output-old" / "secret.md").write_text("x", encoding="utf-8")
    root = browse_service.output_root(tmp_path)
    # A naive str.startswith(str(root)) check would wrongly admit this --
    # "output-old" shares the "output" prefix but is a different directory.
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "../output-old/secret.md")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_browse_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline_app.browse_service'`

- [ ] **Step 3: Write the minimal implementation**

```python
# pipeline_app/browse_service.py
"""Read-only folder/file access scoped under repo_root/output, for the
Browse page. Pure logic only -- no FastAPI or Jinja imports here."""

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

import markdown
import yaml

from pipeline_app import artifacts

MAX_FILE_BYTES = 5 * 1024 * 1024


class PathSafetyError(Exception):
    """Raised when a requested path would resolve outside output/."""


def output_root(repo_root: Path) -> Path:
    return (repo_root / "output").resolve()


def resolve_under_output(root: Path, rel_path: str) -> Path:
    rel_path = (rel_path or "").strip()
    if rel_path in ("", ".", "/"):
        return root

    normalized = rel_path.replace("\\", "/")

    # A colon anywhere (not just a leading drive letter) also catches
    # Windows drive-relative forms like "C:foo", which pathlib's
    # is_absolute() does NOT flag as absolute.
    if ":" in normalized:
        raise PathSafetyError("':' is not allowed in path")
    if PureWindowsPath(normalized).is_absolute() or PurePosixPath(normalized).is_absolute():
        raise PathSafetyError("absolute paths are not allowed")

    segments = [seg for seg in normalized.split("/") if seg]
    if any(seg == ".." for seg in segments):
        raise PathSafetyError("'..' is not allowed in path")

    candidate = (root / "/".join(segments)).resolve()
    if not candidate.is_relative_to(root):
        raise PathSafetyError("path escapes output/")
    return candidate
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_browse_service.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/browse_service.py pipeline-app/tests/test_browse_service.py
git commit -m "feat(pipeline-app): add path-safety layer for Browse page"
```

---

### Task 2: Folder listing (`browse_service.py`)

**Files:**
- Modify: `pipeline_app/browse_service.py`
- Test: `tests/test_browse_service.py`

**Interfaces:**
- Consumes: nothing new from Task 1 directly (operates on already-resolved `Path`s)
- Produces: `Entry` dataclass, `list_children(folder: Path, root: Path) -> list[Entry]`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_browse_service.py

def _touch(path: Path, text: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_list_children_sorts_folders_then_files(root):
    _touch(root / "zeta.md")
    _touch(root / "alpha" / "notes.md")
    _touch(root / "beta.md")
    entries = browse_service.list_children(root, root)
    assert [e.name for e in entries] == ["alpha", "beta.md", "zeta.md"]
    assert [e.is_dir for e in entries] == [True, False, False]


def test_list_children_excludes_folder_with_no_md_anywhere(root):
    _touch(root / "transcripts" / "raw.txt")
    _touch(root / "thinkers" / "plato.md")
    entries = browse_service.list_children(root, root)
    assert [e.name for e in entries] == ["thinkers"]


def test_list_children_hides_non_md_files(root):
    _touch(root / "notes.md")
    _touch(root / "raw.json")
    _touch(root / "clip.vtt")
    entries = browse_service.list_children(root, root)
    assert [e.name for e in entries] == ["notes.md"]


def test_list_children_case_insensitive_md_suffix(root):
    _touch(root / "NOTES.MD")
    entries = browse_service.list_children(root, root)
    assert [e.name for e in entries] == ["NOTES.MD"]


def test_list_children_rel_path_uses_forward_slashes(root):
    _touch(root / "thinkers" / "plato.md")
    entries = browse_service.list_children(root, root)
    assert entries[0].rel_path == "thinkers"
    child_entries = browse_service.list_children(root / "thinkers", root)
    assert child_entries[0].rel_path == "thinkers/plato.md"


def test_list_children_skips_symlinked_dir(root, tmp_path):
    real = tmp_path / "elsewhere"
    _touch(real / "secret.md")
    try:
        (root / "link").symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks require admin rights / Developer Mode on this platform")
    entries = browse_service.list_children(root, root)
    assert entries == []


def test_list_children_skips_symlinked_file(root, tmp_path):
    real_file = tmp_path / "real.md"
    real_file.write_text("x", encoding="utf-8")
    try:
        (root / "link.md").symlink_to(real_file)
    except OSError:
        pytest.skip("symlinks require admin rights / Developer Mode on this platform")
    entries = browse_service.list_children(root, root)
    assert entries == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_browse_service.py -v`
Expected: FAIL — `AttributeError: module 'pipeline_app.browse_service' has no attribute 'list_children'`

- [ ] **Step 3: Write the minimal implementation**

```python
# append to pipeline_app/browse_service.py

@dataclass(frozen=True)
class Entry:
    name: str
    rel_path: str
    is_dir: bool


def _is_md_name(name: str) -> bool:
    return name.lower().endswith(".md")


def _has_md_below(folder: Path) -> bool:
    for entry in os.scandir(folder):
        if entry.is_symlink():
            continue
        if entry.is_file() and _is_md_name(entry.name):
            return True
        if entry.is_dir() and _has_md_below(Path(entry.path)):
            return True
    return False


def list_children(folder: Path, root: Path) -> list["Entry"]:
    dirs: list[Entry] = []
    files: list[Entry] = []
    for entry in os.scandir(folder):
        if entry.is_symlink():
            continue
        path = Path(entry.path)
        rel_path = path.relative_to(root).as_posix()
        if entry.is_dir():
            if _has_md_below(path):
                dirs.append(Entry(name=entry.name, rel_path=rel_path, is_dir=True))
        elif entry.is_file() and _is_md_name(entry.name):
            files.append(Entry(name=entry.name, rel_path=rel_path, is_dir=False))
    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=lambda e: e.name.lower())
    return dirs + files
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_browse_service.py -v`
Expected: PASS (17 tests total; the two symlink tests pass or skip depending on platform permissions)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/browse_service.py pipeline-app/tests/test_browse_service.py
git commit -m "feat(pipeline-app): add folder listing logic for Browse page"
```

---

### Task 3: File rendering (`browse_service.py`)

**Files:**
- Modify: `pipeline_app/browse_service.py`
- Test: `tests/test_browse_service.py`

**Interfaces:**
- Consumes: `artifacts.parse_frontmatter(text: str) -> tuple[dict, str]` (from `pipeline_app/artifacts.py:13`, already handles the `---`-delimited frontmatter split; unchanged by this task)
- Produces: `render_md_file(path: Path) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_browse_service.py

def test_render_md_file_returns_frontmatter_and_body(tmp_path):
    f = tmp_path / "fixture.md"
    f.write_text("---\nstage: shorts-ideation\n---\n\n# Title\n\nBody text.\n", encoding="utf-8")
    result = browse_service.render_md_file(f)
    assert result["frontmatter"] == {"stage": "shorts-ideation"}
    assert "<h1>Title</h1>" in result["body_html"]


def test_render_md_file_no_frontmatter(tmp_path):
    f = tmp_path / "plain.md"
    f.write_text("# Just a title\n", encoding="utf-8")
    result = browse_service.render_md_file(f)
    assert result["frontmatter"] == {}
    assert "<h1>Just a title</h1>" in result["body_html"]


def test_render_md_file_malformed_yaml_returns_error(tmp_path):
    f = tmp_path / "bad.md"
    f.write_text("---\nstage: [unterminated\n---\n\nBody.\n", encoding="utf-8")
    result = browse_service.render_md_file(f)
    assert result == {"error": "Frontmatter is not valid YAML."}


def test_render_md_file_non_mapping_frontmatter_returns_error(tmp_path):
    f = tmp_path / "listfm.md"
    f.write_text("---\n- one\n- two\n---\n\nBody.\n", encoding="utf-8")
    result = browse_service.render_md_file(f)
    assert result == {"error": "Frontmatter is not a key/value mapping."}


def test_render_md_file_bad_encoding_returns_error(tmp_path):
    f = tmp_path / "binary.md"
    f.write_bytes(b"\xff\xfe\x00\x01not utf-8 \xff")
    result = browse_service.render_md_file(f)
    assert "error" in result
    assert result["error"].startswith("Could not read file:")


def test_render_md_file_oversize_never_reads_content(tmp_path, monkeypatch):
    f = tmp_path / "huge.md"
    f.write_bytes(b"x" * (browse_service.MAX_FILE_BYTES + 1))

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("read_text should not be called for an oversize file")

    monkeypatch.setattr(Path, "read_text", _fail_if_called)
    result = browse_service.render_md_file(f)
    assert result["oversize"] is True
    assert result["cap_mb"] == pytest.approx(5.0)
    assert result["size_mb"] > 5.0
    assert result["abs_path"] == str(f)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_browse_service.py -v`
Expected: FAIL — `AttributeError: module 'pipeline_app.browse_service' has no attribute 'render_md_file'`

- [ ] **Step 3: Write the minimal implementation**

```python
# append to pipeline_app/browse_service.py

def render_md_file(path: Path) -> dict:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        return {
            "oversize": True,
            "size_mb": size / (1024 * 1024),
            "cap_mb": MAX_FILE_BYTES / (1024 * 1024),
            "abs_path": str(path),
        }

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return {"error": f"Could not read file: {exc}"}

    try:
        meta, body = artifacts.parse_frontmatter(text)
    except yaml.YAMLError:
        return {"error": "Frontmatter is not valid YAML."}
    if not isinstance(meta, dict):
        return {"error": "Frontmatter is not a key/value mapping."}

    return {"frontmatter": meta, "body_html": markdown.markdown(body)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_browse_service.py -v`
Expected: PASS (23 tests total)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/browse_service.py pipeline-app/tests/test_browse_service.py
git commit -m "feat(pipeline-app): add file-rendering with frontmatter hardening and size cap"
```

---

### Task 4: `GET /browse` full page + tree partial template

**Files:**
- Create: `pipeline_app/routes/browse.py`
- Create: `pipeline_app/templates/browse.html`
- Create: `pipeline_app/templates/partials/browse_tree_items.html`
- Modify: `pipeline_app/main.py:10` (import), `pipeline_app/main.py:34` (register router)
- Modify: `pipeline_app/templates/base.html:110` (nav link)
- Modify: `pipeline_app/static/style.css` (append)
- Test: `tests/test_routes_browse.py`

**Interfaces:**
- Consumes: `browse_service.output_root`, `browse_service.resolve_under_output`, `browse_service.PathSafetyError`, `browse_service.list_children`, `browse_service.Entry` (all from Tasks 1–2)
- Produces: a reusable `_folder_context(request, rel_path: str) -> dict` helper in `routes/browse.py`, used again by Task 5

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routes_browse.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / "output").mkdir()
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path


def _touch(path: Path, text: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_browse_root_renders_top_level_entries(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md")
    _touch(tmp_path / "output" / "alone.md")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "thinkers" in resp.text
    assert "alone.md" in resp.text


def test_browse_root_excludes_md_less_folder(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "transcripts" / "raw.txt")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "transcripts" not in resp.text


def test_browse_root_missing_output_dir_shows_folder_not_found(client):
    test_client, tmp_path = client
    import shutil
    shutil.rmtree(tmp_path / "output")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "Folder not found." in resp.text


def test_browse_tree_items_carry_htmx_attributes_not_ids(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert 'hx-get="/browse/tree?path=thinkers"' in resp.text
    assert 'hx-trigger="toggle once"' in resp.text
    assert 'hx-target="this"' in resp.text
    assert 'hx-get="/browse/file?path=thinkers%2Fplato.md"' in resp.text
    assert 'hx-sync="#browse-doc:replace"' in resp.text


def test_browse_nav_link_present(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert 'href="/browse"' in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_routes_browse.py -v`
Expected: FAIL — 404 on `/browse` (route not registered yet)

- [ ] **Step 3: Write the minimal implementation**

```python
# pipeline_app/routes/browse.py
from fastapi import APIRouter, Request

from pipeline_app import browse_service

router = APIRouter()


def _folder_context(request: Request, rel_path: str) -> dict:
    root = browse_service.output_root(request.app.state.repo_root)
    try:
        folder = browse_service.resolve_under_output(root, rel_path)
    except browse_service.PathSafetyError:
        return {"error": "Invalid path."}
    if not folder.is_dir():
        return {"error": "Folder not found."}
    return {"entries": browse_service.list_children(folder, root)}


@router.get("/browse")
def browse_root(request: Request):
    context = _folder_context(request, "")
    return request.app.state.templates.TemplateResponse(request, "browse.html", context)


@router.get("/browse/tree")
def browse_tree(request: Request, path: str = ""):
    context = _folder_context(request, path)
    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_tree_items.html", context
    )
```

```html
<!-- pipeline_app/templates/browse.html -->
{% extends "base.html" %}
{% block content %}
<h1>Browse output/</h1>
<div class="browse-shell">
  <div class="browse-tree">
    {% include "partials/browse_tree_items.html" %}
  </div>
  <div class="browse-doc-wrap">
    <span id="browse-spinner" class="htmx-indicator">loading…</span>
    <div class="browse-doc" id="browse-doc">
      <p class="browse-placeholder">Select a .md file to view it here.</p>
    </div>
  </div>
</div>
{% endblock %}
```

```html
<!-- pipeline_app/templates/partials/browse_tree_items.html -->
{% if error %}
<p class="browse-error">{{ error }}</p>
{% elif not entries %}
<p class="browse-empty">No .md files found here.</p>
{% else %}
  {% for entry in entries %}
    {% if entry.is_dir %}
    <details>
      <summary>{{ entry.name }}</summary>
      <div class="children"
           hx-get="/browse/tree?path={{ entry.rel_path | urlencode }}"
           hx-trigger="toggle once"
           hx-target="this"
           hx-swap="innerHTML"></div>
    </details>
    {% else %}
    <div class="browse-file-row">
      <a href="#"
         hx-get="/browse/file?path={{ entry.rel_path | urlencode }}"
         hx-target="#browse-doc"
         hx-swap="innerHTML"
         hx-sync="#browse-doc:replace"
         hx-indicator="#browse-spinner">{{ entry.name }}</a>
    </div>
    {% endif %}
  {% endfor %}
{% endif %}
```

Modify `pipeline_app/main.py`:

```python
# line 10 -- add browse to the import
from pipeline_app.routes import browse, doctor, inspector, projects, skills, stages
```

```python
# line 34 -- register alongside the other routers
    app.include_router(browse.router)
```

Modify `pipeline_app/templates/base.html` line 110:

```html
<header><a href="/">ContentStudio Pipeline</a> <a href="/browse">Browse</a></header>
```

Append to `pipeline_app/static/style.css`:

```css
.browse-shell { display: flex; gap: 1.5rem; align-items: flex-start; }
.browse-tree { flex: 0 0 22rem; max-height: 80vh; overflow-y: auto; }
.browse-tree details { margin-left: 0.25rem; }
.browse-tree summary { cursor: pointer; }
.browse-file-row { margin-left: 1.25rem; }
.browse-file-row a { cursor: pointer; }
.browse-doc-wrap { flex: 1 1 auto; min-width: 0; }
.browse-error { color: #a00; }
.browse-empty, .browse-placeholder { color: #777; font-style: italic; }
.htmx-indicator { opacity: 0; }
.htmx-request.htmx-indicator, .htmx-request .htmx-indicator { opacity: 1; }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_routes_browse.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/browse.py pipeline-app/pipeline_app/templates/browse.html \
        pipeline-app/pipeline_app/templates/partials/browse_tree_items.html \
        pipeline-app/pipeline_app/main.py pipeline-app/pipeline_app/templates/base.html \
        pipeline-app/pipeline_app/static/style.css pipeline-app/tests/test_routes_browse.py
git commit -m "feat(pipeline-app): add Browse page root view and lazy folder tree"
```

---

### Task 5: `GET /browse/tree` deeper coverage (nesting, traversal, case-insensitivity)

**Files:**
- Modify: `tests/test_routes_browse.py` (route implementation from Task 4 already covers these; this task only adds the remaining spec-required route-level cases)

**Interfaces:**
- Consumes: `_folder_context` (Task 4), `browse_service.PathSafetyError` (Task 1)
- Produces: nothing new — this task is test-only, closing out the spec's traversal/edge-case test list at the HTTP layer

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_routes_browse.py

def test_browse_tree_nested_folder_returns_children(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "anchorandwave" / "plato.md")
    resp = test_client.get("/browse/tree", params={"path": "thinkers"})
    assert resp.status_code == 200
    assert "anchorandwave" in resp.text


def test_browse_tree_dotdot_traversal_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"path": "../../../etc"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_tree_windows_drive_override_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"path": "C:/Windows"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_tree_leading_backslash_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"path": "\\Windows\\System32"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_tree_sibling_prefix_folder_not_admitted(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output-old" / "secret.md")
    resp = test_client.get("/browse/tree", params={"path": "../output-old"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text
    assert "secret.md" not in resp.text


def test_browse_tree_missing_folder_returns_folder_not_found(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"path": "does/not/exist"})
    assert resp.status_code == 200
    assert "Folder not found." in resp.text


def test_browse_tree_uppercase_md_extension_listed(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "notes" / "NOTES.MD")
    resp = test_client.get("/browse/tree", params={"path": "notes"})
    assert resp.status_code == 200
    assert "NOTES.MD" in resp.text


def test_browse_tree_folder_with_no_md_anywhere_is_empty_not_error(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "empty_ish" / "raw.txt")
    resp = test_client.get("/browse/tree", params={"path": "empty_ish"})
    assert resp.status_code == 200
    assert "No .md files found here." in resp.text
```

- [ ] **Step 2: Run tests to verify they fail (or pass already)**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_routes_browse.py -v`
Expected: These should already PASS given Task 4's implementation — this step is a verification pass, not a new-code step. If any fail, it means Task 4's `_folder_context`/`list_children` has a gap; fix `browse_service.py` or `routes/browse.py` (not the tests) until all pass.

- [ ] **Step 3: (only if Step 2 found failures) Fix the implementation**

Only touch `browse_service.py` or `routes/browse.py` — the tests above encode the spec directly and should not be changed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_routes_browse.py -v`
Expected: PASS (13 tests total)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/tests/test_routes_browse.py
git commit -m "test(pipeline-app): cover Browse tree traversal, casing, and empty-folder cases"
```

---

### Task 6: `GET /browse/file`

**Files:**
- Modify: `pipeline_app/routes/browse.py`
- Create: `pipeline_app/templates/partials/browse_file.html`
- Test: `tests/test_routes_browse.py`

**Interfaces:**
- Consumes: `browse_service.output_root`, `browse_service.resolve_under_output`, `browse_service.PathSafetyError`, `browse_service.render_md_file` (Tasks 1 and 3)
- Produces: nothing consumed by later tasks (this is the last route)

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_routes_browse.py

def test_browse_file_renders_frontmatter_and_body(client):
    test_client, tmp_path = client
    _touch(
        tmp_path / "output" / "thinkers" / "plato.md",
        "---\nera: classical\n---\n\n# Plato\n\nBody.\n",
    )
    resp = test_client.get("/browse/file", params={"path": "thinkers/plato.md"})
    assert resp.status_code == 200
    assert "classical" in resp.text
    assert "<h1>Plato</h1>" in resp.text


def test_browse_file_malformed_yaml_shows_error_not_500(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "bad.md", "---\nstage: [unterminated\n---\n\nBody.\n")
    resp = test_client.get("/browse/file", params={"path": "bad.md"})
    assert resp.status_code == 200
    assert "Frontmatter is not valid YAML." in resp.text


def test_browse_file_non_mapping_frontmatter_shows_error(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "listfm.md", "---\n- one\n- two\n---\n\nBody.\n")
    resp = test_client.get("/browse/file", params={"path": "listfm.md"})
    assert resp.status_code == 200
    assert "Frontmatter is not a key/value mapping." in resp.text


def test_browse_file_oversize_shows_message(client):
    test_client, tmp_path = client
    import pipeline_app.browse_service as browse_service
    f = tmp_path / "output" / "huge.md"
    f.write_bytes(b"x" * (browse_service.MAX_FILE_BYTES + 1))
    resp = test_client.get("/browse/file", params={"path": "huge.md"})
    assert resp.status_code == 200
    assert "too large to preview" in resp.text


def test_browse_file_missing_file_returns_path_does_not_exist(client):
    test_client, _ = client
    resp = test_client.get("/browse/file", params={"path": "nope.md"})
    assert resp.status_code == 200
    assert "Path does not exist." in resp.text


def test_browse_file_directory_path_returns_error(client):
    test_client, tmp_path = client
    (tmp_path / "output" / "thinkers").mkdir()
    resp = test_client.get("/browse/file", params={"path": "thinkers"})
    assert resp.status_code == 200
    assert "Path is a directory, not a file." in resp.text


def test_browse_file_wrong_suffix_returns_error(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "raw.txt")
    resp = test_client.get("/browse/file", params={"path": "raw.txt"})
    assert resp.status_code == 200
    assert "Not a valid .md file path." in resp.text


def test_browse_file_traversal_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/file", params={"path": "../../../etc/passwd"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_file_uppercase_extension_renders(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "NOTES.MD", "# Upper\n\nBody.\n")
    resp = test_client.get("/browse/file", params={"path": "NOTES.MD"})
    assert resp.status_code == 200
    assert "<h1>Upper</h1>" in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_routes_browse.py -v`
Expected: FAIL — 404 on `/browse/file` (route not implemented yet)

- [ ] **Step 3: Write the minimal implementation**

```python
# append to pipeline_app/routes/browse.py

@router.get("/browse/file")
def browse_file(request: Request, path: str = ""):
    root = browse_service.output_root(request.app.state.repo_root)
    try:
        file_path = browse_service.resolve_under_output(root, path)
    except browse_service.PathSafetyError:
        file_path = None
        context = {"error": "Invalid path."}

    if file_path is not None:
        if not file_path.exists():
            context = {"error": "Path does not exist."}
        elif file_path.is_dir():
            context = {"error": "Path is a directory, not a file."}
        elif not file_path.name.lower().endswith(".md"):
            context = {"error": "Not a valid .md file path."}
        else:
            context = browse_service.render_md_file(file_path)

    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_file.html", context
    )
```

```html
<!-- pipeline_app/templates/partials/browse_file.html -->
{% if error %}
<p class="browse-error">{{ error }}</p>
{% elif oversize %}
<p class="browse-error">
  File too large to preview ({{ "%.1f"|format(size_mb) }} MB — cap is {{ "%.0f"|format(cap_mb) }} MB).
  Open it directly at <code>{{ abs_path }}</code>.
</p>
{% else %}
{% if frontmatter %}
<h2>Frontmatter</h2>
<table>
  {% for key, value in frontmatter.items() %}
  <tr><th>{{ key }}</th><td>{{ value }}</td></tr>
  {% endfor %}
</table>
{% endif %}
<div>{{ body_html | safe }}</div>
{% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest tests/test_routes_browse.py -v`
Expected: PASS (22 tests total)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/browse.py \
        pipeline-app/pipeline_app/templates/partials/browse_file.html \
        pipeline-app/tests/test_routes_browse.py
git commit -m "feat(pipeline-app): add Browse page file rendering endpoint"
```

---

### Task 7: Full regression pass and manual verification note

**Files:**
- None created/modified — verification only.

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: nothing (terminal task).

- [ ] **Step 1: Run the full test suite**

Run: `cd pipeline-app && .venv/Scripts/python.exe -m pytest -q`
Expected: PASS — every existing test (Inspector, projects, stages, skills, doctor, etc.) plus all new `browse_service`/`routes_browse` tests, with no regressions.

- [ ] **Step 2: Manual verification note (cannot be automated in this worktree)**

`output/` does not exist in this worktree (git-ignored; only present in the main checkout at `C:\Projects\ContentStudio\output`). To manually click through the feature in a browser:

```bash
# from the main checkout, not this worktree, OR after copying/symlinking
# a real output/ subtree into this worktree first
cd pipeline-app
.venv/Scripts/python.exe -m uvicorn pipeline_app.main:create_default_app --factory --reload
```

Then open `http://127.0.0.1:8000/browse`, expand a few folders, click into a `.md` file, and confirm the frontmatter table + rendered body appear in the right-hand pane. This step has no pass/fail assertion beyond "no exception in the server log and the page renders" — the automated test suite above is what actually verifies correctness; this is a sanity spot-check.

- [ ] **Step 3: Commit (only if Step 1 required fixes)**

If the full-suite run in Step 1 needed any fixes, commit them now:

```bash
git add -A pipeline-app
git commit -m "fix(pipeline-app): resolve regression found in full Browse suite run"
```

If Step 1 passed clean with no changes needed, skip this step — there is nothing to commit.
