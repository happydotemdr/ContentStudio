# Pipeline Outputs on the Browse Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Pipeline Outputs" section to `/browse`, organized project → stage → artifact version, alongside the existing "Corpus Docs" (`output/`) section, reusing the same tree/viewer UI.

**Architecture:** Generalize `browse_service.py`'s single hardcoded `output/` root into two named roots (`output`, `pipeline` → `runs/`). Extend the existing recursive folder scan (`list_children`/`_has_md_below`) to thread through a `repo_root` parameter, needed because the `grounding` stage's `pointer.yaml` resolves to a file outside `runs/` (in `rgs-briefs/`) and needs its own containment check. Add one new function, `list_pipeline_projects`, for the project-listing top level (filesystem-driven, DB-annotated with brand). Routes gain a `root` query param; templates render two tree sections sharing one viewer pane.

**Deviation from the design spec, deliberate:** the spec's §6 described both tree sections as htmx-loaded on page open. This plan has `browse_root` compute both sections' top-level entries synchronously and render them inline instead — matching the app's *existing* pattern (today's single `output/` section is already rendered this way, not htmx-loaded) and avoiding two extra round trips on every page load for no benefit, since the data is cheap to compute server-side. Only folder-expand and file-open remain htmx-driven, exactly as today. Deeper tree levels are unaffected either way.

**Tech Stack:** FastAPI, Jinja2, htmx, pytest, sqlite3 — all already in use, no new dependencies.

**Working directory:** All file paths below are relative to `pipeline-app/` (e.g. `pipeline_app/browse_service.py` means `pipeline-app/pipeline_app/browse_service.py` from the repo root). Run tests from inside `pipeline-app/`: `pytest tests/ -v`.

## Global Constraints

- No changes to how artifacts are written, versioned, or approved (`artifacts.py`, `approval_service.py`, `turn_service.py` stay untouched).
- No changes to `/projects/{id}/stages/{stage_id}` or `/inspector` — purely additive.
- Read-only: no DB writes anywhere in this feature.
- `root=output` behavior must remain byte-identical to today wherever a test doesn't specifically target the new `pipeline` root or the version-sort fix.
- The one genuinely new trust boundary — a file path read from `pointer.yaml` content rather than derived from the request/tree structure — must be validated with an explicit `is_relative_to()` containment check against the real `rgs-briefs/` folder, not assumed safe because the link is server-generated.

---

### Task 1: Root registry (`output` / `pipeline`)

**Files:**
- Modify: `pipeline_app/browse_service.py` (add two functions after `output_root`, ~line 27)
- Test: `tests/test_browse_service.py` (append)

**Interfaces:**
- Produces: `browse_service.runs_root(repo_root: Path) -> Path`, `browse_service.root_path(repo_root: Path, root: str) -> Path` (raises `ValueError` for unknown `root`). Later tasks/routes call `root_path()` to resolve either named root.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_browse_service.py`:

```python
def test_runs_root_resolves_under_repo_root(tmp_path):
    (tmp_path / "runs").mkdir()
    result = browse_service.runs_root(tmp_path)
    assert result == (tmp_path / "runs").resolve()


def test_root_path_dispatches_output(tmp_path):
    (tmp_path / "output").mkdir()
    assert browse_service.root_path(tmp_path, "output") == browse_service.output_root(tmp_path)


def test_root_path_dispatches_pipeline(tmp_path):
    (tmp_path / "runs").mkdir()
    assert browse_service.root_path(tmp_path, "pipeline") == browse_service.runs_root(tmp_path)


def test_root_path_rejects_unknown_root(tmp_path):
    with pytest.raises(ValueError):
        browse_service.root_path(tmp_path, "bogus")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_browse_service.py -k "runs_root or root_path" -v`
Expected: FAIL with `AttributeError: module 'pipeline_app.browse_service' has no attribute 'runs_root'`

- [ ] **Step 3: Implement**

In `pipeline_app/browse_service.py`, immediately after the existing `output_root` function:

```python
def runs_root(repo_root: Path) -> Path:
    return (repo_root / "runs").resolve()


def root_path(repo_root: Path, root: str) -> Path:
    if root == "output":
        return output_root(repo_root)
    if root == "pipeline":
        return runs_root(repo_root)
    raise ValueError(f"unknown browse root: {root!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_browse_service.py -k "runs_root or root_path" -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/browse_service.py pipeline-app/tests/test_browse_service.py
git commit -m "feat(browse): add output/pipeline root registry to browse_service"
```

---

### Task 2: Grounding pointer resolution with containment check

**Files:**
- Modify: `pipeline_app/browse_service.py` (add import + function)
- Test: `tests/test_browse_service.py` (append)

**Interfaces:**
- Consumes: `grounding_service.read_pointer(pointer_dir: Path) -> str | None` (existing, unchanged).
- Produces: `browse_service.resolve_grounding_pointer(pointer_dir: Path, repo_root: Path) -> Path | None`. Tasks 3 and 5 call this — Task 3 to decide whether a grounding folder "has content," Task 5's file route to resolve a clicked pointer.

- [ ] **Step 1: Write the failing tests**

Add near the top of `tests/test_browse_service.py`, alongside the existing imports:

```python
from pipeline_app import grounding_service
```

Append:

```python
def test_resolve_grounding_pointer_returns_target_when_valid(tmp_path):
    (tmp_path / "rgs-briefs").mkdir()
    brief = tmp_path / "rgs-briefs" / "2026-07-28-topic.md"
    brief.write_text("# Brief", encoding="utf-8")
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    grounding_service.write_pointer(pointer_dir, "rgs-briefs/2026-07-28-topic.md")
    result = browse_service.resolve_grounding_pointer(pointer_dir, tmp_path)
    assert result == brief.resolve()


def test_resolve_grounding_pointer_returns_none_when_no_pointer(tmp_path):
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    pointer_dir.mkdir(parents=True)
    assert browse_service.resolve_grounding_pointer(pointer_dir, tmp_path) is None


def test_resolve_grounding_pointer_returns_none_when_target_missing(tmp_path):
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    grounding_service.write_pointer(pointer_dir, "rgs-briefs/does-not-exist.md")
    assert browse_service.resolve_grounding_pointer(pointer_dir, tmp_path) is None


def test_resolve_grounding_pointer_rejects_path_outside_rgs_briefs(tmp_path):
    # A corrupted/hand-edited pointer.yaml pointing elsewhere under repo_root
    # (e.g. another project's runs/ folder) must not be followed, even
    # though the resolved path is still technically "under repo_root". The
    # target here is repo-root-relative ("runs/other-run/secret.md"), same
    # form pointer.yaml actually stores its values in -- not a "../" escape,
    # which is a distinct case already covered by the traversal test below.
    secret = tmp_path / "runs" / "other-run" / "secret.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("secret", encoding="utf-8")
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    grounding_service.write_pointer(pointer_dir, "runs/other-run/secret.md")
    assert browse_service.resolve_grounding_pointer(pointer_dir, tmp_path) is None


def test_resolve_grounding_pointer_rejects_traversal_outside_repo_root(tmp_path):
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    grounding_service.write_pointer(pointer_dir, "../../../etc/passwd")
    assert browse_service.resolve_grounding_pointer(pointer_dir, tmp_path) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_browse_service.py -k resolve_grounding_pointer -v`
Expected: FAIL with `AttributeError: module 'pipeline_app.browse_service' has no attribute 'resolve_grounding_pointer'`

- [ ] **Step 3: Implement**

In `pipeline_app/browse_service.py`, add to the import block (with the existing `from pipeline_app import artifacts`):

```python
from pipeline_app import grounding_service
```

Add the function anywhere after the root-registry functions from Task 1:

```python
def resolve_grounding_pointer(pointer_dir: Path, repo_root: Path) -> Path | None:
    """Resolve a grounding stage's pointer.yaml to the real rgs-briefs/ file
    it references. pointer.yaml's content is read from disk, not derived
    from the request/tree structure, so its target path is a new trust
    boundary here and gets an explicit containment check against the real
    rgs-briefs/ folder rather than being trusted outright."""
    target_rel = grounding_service.read_pointer(pointer_dir)
    if not target_rel:
        return None
    rgs_briefs_root = (repo_root / "rgs-briefs").resolve()
    target = (repo_root / target_rel).resolve()
    if not target.is_relative_to(rgs_briefs_root):
        return None
    if not target.exists():
        return None
    return target
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_browse_service.py -k resolve_grounding_pointer -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/browse_service.py pipeline-app/tests/test_browse_service.py
git commit -m "feat(browse): resolve grounding pointer.yaml with path containment check"
```

---

### Task 3: `_has_md_below` + `list_children` — repo_root, pointer entries, raw_output.md exclusion, version sort fix

This is the core fix for the bug the Opus review caught: `_has_md_below` currently hides `00-grounding` from its *parent* folder's listing before any stage-level logic runs, since it only looks for `.md` files. Fixing it and `list_children` together (they call each other) is one task because splitting them would leave a broken intermediate state.

**Files:**
- Modify: `pipeline_app/browse_service.py` (rewrite `_has_md_below` and `list_children`, add `_file_sort_key` and `_ARTIFACT_VERSION_RE`)
- Modify: `tests/test_browse_service.py` (update existing call sites, add new tests)
- Modify: `pipeline_app/routes/browse.py` (Step 7 only — minimal interim patch to the one `list_children` call site, so the app keeps working before Task 5's full rewrite)

**Interfaces:**
- Consumes: `resolve_grounding_pointer` (Task 2).
- Produces: `browse_service.list_children(folder: Path, root: Path, repo_root: Path) -> list[Entry]` and `browse_service._has_md_below(folder: Path, repo_root: Path) -> bool` — **signature changed** (both gained a `repo_root` parameter). Task 4/5 call `list_children` with all three args.

- [ ] **Step 1: Update existing tests for the new signatures**

In `tests/test_browse_service.py`, every existing call to `list_children(root, root)` becomes `list_children(root, root, tmp_path)`, and every call to `_has_md_below(subfolder)` becomes `_has_md_below(subfolder, tmp_path)`. Replace these specific test bodies (the `root` fixture's `tmp_path` is the stand-in "repo_root" for these tests, matching how `root` = `tmp_path / "output"`):

```python
def test_list_children_sorts_folders_then_files(root, tmp_path):
    _touch(root / "zeta.md")
    _touch(root / "alpha" / "notes.md")
    _touch(root / "beta.md")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["alpha", "beta.md", "zeta.md"]
    assert [e.is_dir for e in entries] == [True, False, False]


def test_list_children_excludes_folder_with_no_md_anywhere(root, tmp_path):
    _touch(root / "transcripts" / "raw.txt")
    _touch(root / "thinkers" / "plato.md")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["thinkers"]


def test_list_children_hides_non_md_files(root, tmp_path):
    _touch(root / "notes.md")
    _touch(root / "raw.json")
    _touch(root / "clip.vtt")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["notes.md"]


def test_list_children_case_insensitive_md_suffix(root, tmp_path):
    _touch(root / "NOTES.MD")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["NOTES.MD"]


def test_list_children_rel_path_uses_forward_slashes(root, tmp_path):
    _touch(root / "thinkers" / "plato.md")
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries[0].rel_path == "thinkers"
    child_entries = browse_service.list_children(root / "thinkers", root, tmp_path)
    assert child_entries[0].rel_path == "thinkers/plato.md"


def test_list_children_skips_symlinked_dir(root, tmp_path):
    real = tmp_path / "elsewhere"
    _touch(real / "secret.md")
    try:
        (root / "link").symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks require admin rights / Developer Mode on this platform")
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries == []


def test_list_children_skips_symlinked_file(root, tmp_path):
    real_file = tmp_path / "real.md"
    real_file.write_text("x", encoding="utf-8")
    try:
        (root / "link.md").symlink_to(real_file)
    except OSError:
        pytest.skip("symlinks require admin rights / Developer Mode on this platform")
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries == []


def test_list_children_scandir_oserror_raises_folder_read_error(root, tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(os, "scandir", _raise)
    with pytest.raises(browse_service.FolderReadError):
        browse_service.list_children(root, root, tmp_path)


def test_has_md_below_scandir_oserror_returns_false(root, tmp_path, monkeypatch):
    subfolder = root / "sub"
    subfolder.mkdir()
    _touch(subfolder / "note.md")

    real_scandir = os.scandir

    def _raise_for_subfolder(path, *args, **kwargs):
        if Path(path) == subfolder:
            raise OSError("permission denied")
        return real_scandir(path, *args, **kwargs)

    monkeypatch.setattr(os, "scandir", _raise_for_subfolder)
    assert browse_service._has_md_below(subfolder, tmp_path) is False
    # And the unreadable subfolder is excluded from its parent's listing
    # rather than blowing up the whole scan.
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries == []
```

- [ ] **Step 2: Run tests to verify they fail on the signature mismatch**

Run: `pytest tests/test_browse_service.py -v`
Expected: FAIL — `TypeError: list_children() takes 2 positional arguments but 3 were given` (and similarly for `_has_md_below`) across the tests just updated, since the implementation hasn't changed yet.

- [ ] **Step 3: Write the new failing tests for the added behavior**

Append to `tests/test_browse_service.py`:

```python
def test_list_children_excludes_raw_output_md(root, tmp_path):
    _touch(root / "01-ideation" / "artifact.v1.md")
    _touch(root / "01-ideation" / "raw_output.md")
    entries = browse_service.list_children(root / "01-ideation", root, tmp_path)
    assert [e.name for e in entries] == ["artifact.v1.md"]


def test_list_children_sorts_artifact_versions_numerically(root, tmp_path):
    _touch(root / "stage" / "artifact.v2.md")
    _touch(root / "stage" / "artifact.v10.md")
    _touch(root / "stage" / "artifact.v1.md")
    entries = browse_service.list_children(root / "stage", root, tmp_path)
    assert [e.name for e in entries] == ["artifact.v1.md", "artifact.v2.md", "artifact.v10.md"]


def test_has_md_below_true_when_valid_grounding_pointer_present(root, tmp_path):
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "topic.md").write_text("# Brief", encoding="utf-8")
    grounding_dir = root / "00-grounding"
    grounding_service.write_pointer(grounding_dir, "rgs-briefs/topic.md")
    assert browse_service._has_md_below(grounding_dir, tmp_path) is True


def test_has_md_below_false_when_only_raw_output_md_present(root, tmp_path):
    # _has_md_below and list_children must agree on raw_output.md: if
    # list_children hides it but _has_md_below still counts it as content,
    # a stage folder containing only raw_output.md would show up as an
    # expandable folder that renders completely empty when opened.
    stage_dir = root / "01-ideation"
    _touch(stage_dir / "raw_output.md")
    assert browse_service._has_md_below(stage_dir, tmp_path) is False
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries == []


def test_has_md_below_false_when_no_pointer_and_no_md(root, tmp_path):
    grounding_dir = root / "00-grounding"
    (grounding_dir / "events").mkdir(parents=True)
    assert browse_service._has_md_below(grounding_dir, tmp_path) is False


def test_has_md_below_false_when_pointer_target_missing(root, tmp_path):
    grounding_dir = root / "00-grounding"
    grounding_service.write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")
    assert browse_service._has_md_below(grounding_dir, tmp_path) is False


def test_list_children_includes_grounding_folder_when_pointer_valid(root, tmp_path):
    # This is the parent-level survival check the Opus review caught as
    # broken: without the _has_md_below fix, "00-grounding" never appears
    # here at all, regardless of what list_children itself would do with it.
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "topic.md").write_text("# Brief", encoding="utf-8")
    grounding_service.write_pointer(root / "00-grounding", "rgs-briefs/topic.md")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["00-grounding"]


def test_list_children_synthesizes_current_brief_entry_for_pointer(root, tmp_path):
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "2026-07-28-topic.md").write_text("# Brief", encoding="utf-8")
    grounding_dir = root / "00-grounding"
    grounding_service.write_pointer(grounding_dir, "rgs-briefs/2026-07-28-topic.md")
    entries = browse_service.list_children(grounding_dir, root, tmp_path)
    assert len(entries) == 1
    assert entries[0].name == "current-brief.md (2026-07-28-topic.md)"
    assert entries[0].rel_path == "00-grounding/pointer.yaml"
    assert entries[0].is_dir is False


def test_list_children_omits_pointer_entry_when_target_missing(root, tmp_path):
    grounding_dir = root / "00-grounding"
    grounding_service.write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")
    entries = browse_service.list_children(grounding_dir, root, tmp_path)
    assert entries == []
```

- [ ] **Step 4: Run new tests to verify they fail**

Run: `pytest tests/test_browse_service.py -k "raw_output_md or numerically or grounding_pointer or grounding_folder or current_brief or pointer_entry" -v`
Note: `test_has_md_below_false_when_only_raw_output_md_present` matches this filter (`raw_output_md`).
Expected: FAIL (signature/behavior not implemented yet)

- [ ] **Step 5: Implement**

Add near the top of `pipeline_app/browse_service.py` (with the other imports):

```python
import re
```

Replace `_has_md_below` entirely:

```python
def _has_md_below(folder: Path, repo_root: Path) -> bool:
    try:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_symlink():
                    continue
                if entry.is_file() and entry.name == "raw_output.md":
                    # Must agree with list_children's exclusion below --
                    # otherwise a stage folder containing only this file
                    # would appear as an expandable folder that renders
                    # empty when opened.
                    continue
                if entry.is_file() and _is_md_name(entry.name):
                    return True
                if entry.is_file() and entry.name == "pointer.yaml":
                    if resolve_grounding_pointer(folder, repo_root) is not None:
                        return True
                if entry.is_dir() and _has_md_below(Path(entry.path), repo_root):
                    return True
    except OSError:
        # Can't even scan this folder (permission denied, removed mid-scan,
        # etc.) -- treat it as contributing no visible content to its
        # ancestor's listing. Defensive default, not a correctness claim.
        return False
    return False
```

Add a sort helper and the version-number regex right before `list_children`:

```python
_ARTIFACT_VERSION_RE = re.compile(r"artifact\.v(\d+)\.md$", re.IGNORECASE)


def _file_sort_key(entry: "Entry") -> tuple:
    m = _ARTIFACT_VERSION_RE.match(entry.name)
    if m:
        return (0, int(m.group(1)), entry.name.lower())
    return (1, 0, entry.name.lower())
```

Replace `list_children` entirely:

```python
def list_children(folder: Path, root: Path, repo_root: Path) -> list["Entry"]:
    dirs: list[Entry] = []
    files: list[Entry] = []
    try:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                rel_path = path.relative_to(root).as_posix()
                if entry.is_dir():
                    if _has_md_below(path, repo_root):
                        dirs.append(Entry(name=entry.name, rel_path=rel_path, is_dir=True))
                elif entry.is_file():
                    if entry.name == "raw_output.md":
                        # Pre-versioning scratch state, already captured in
                        # the corresponding artifact.vN.md body -- showing
                        # both is redundant clutter, not useful history.
                        continue
                    if _is_md_name(entry.name):
                        files.append(Entry(name=entry.name, rel_path=rel_path, is_dir=False))
                    elif entry.name == "pointer.yaml":
                        target = resolve_grounding_pointer(folder, repo_root)
                        if target is not None:
                            files.append(Entry(
                                name=f"current-brief.md ({target.name})",
                                rel_path=rel_path,
                                is_dir=False,
                            ))
    except OSError as exc:
        # Unlike an empty folder, this must surface as an error rather than
        # silently returning [] -- to the caller those would look identical.
        raise FolderReadError(str(exc)) from exc
    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=_file_sort_key)
    return dirs + files
```

- [ ] **Step 6: Run all `browse_service` tests to verify they pass**

Run: `pytest tests/test_browse_service.py -v`
Expected: PASS (all tests, including every pre-existing one updated in Step 1)

- [ ] **Step 7: Patch the one existing route call site so the app keeps working**

`list_children`'s signature just changed from 2 args to 3, but `routes/browse.py`'s `_folder_context` (not yet rewritten — that's Task 5) still calls it with 2. Left as-is, every request to `/browse`, `/browse/tree`, or `/browse/file` would 500 between this commit and Task 5's. Patch just the one call site in `pipeline_app/routes/browse.py`'s `_folder_context` function:

```python
def _folder_context(request: Request, rel_path: str) -> dict:
    root = browse_service.output_root(request.app.state.repo_root)
    try:
        folder = browse_service.resolve_under_output(root, rel_path)
    except browse_service.PathSafetyError:
        return {"error": "Invalid path."}
    if not folder.is_dir():
        return {"error": "Folder not found."}
    try:
        return {"entries": browse_service.list_children(folder, root, request.app.state.repo_root)}
    except browse_service.FolderReadError as exc:
        return {"error": f"Could not read folder: {exc}"}
```

(Only the `list_children(...)` call line actually changes — the rest of the function is unchanged. This whole function gets fully replaced again in Task 5 as part of adding the `root` query param; this is a minimal interim fix, not the final form.)

- [ ] **Step 8: Run the route tests to confirm nothing broke**

Run: `pytest tests/test_routes_browse.py -v`
Expected: PASS — every existing `root=output`-default test still passes unchanged, confirming the interim patch didn't regress anything before Task 5 lands.

- [ ] **Step 9: Commit**

```bash
git add pipeline-app/pipeline_app/browse_service.py pipeline-app/pipeline_app/routes/browse.py pipeline-app/tests/test_browse_service.py
git commit -m "fix(browse): thread repo_root through list_children/_has_md_below for grounding pointer support; exclude raw_output.md; fix artifact version sort"
```

---

### Task 4: `list_pipeline_projects` — project-listing top level

**Files:**
- Modify: `pipeline_app/browse_service.py` (add import + function)
- Test: `tests/test_browse_service.py` (append, needs a DB `conn` fixture)

**Interfaces:**
- Consumes: `db_mod.list_projects(conn) -> list[sqlite3.Row]` (existing, unchanged; each row has `run_id`, `brand`, `created_at`). `runs_root` (Task 1).
- Produces: `browse_service.list_pipeline_projects(conn, repo_root: Path) -> list[Entry]`. Task 5's route calls this for the pipeline tree's top level (empty `path`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_browse_service.py`, near the top:

```python
from pipeline_app import db as db_mod
```

Add a fixture and tests (append):

```python
@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db_mod.init_db(db_path, schema_path)
    connection = db_mod.get_connection(db_path)
    yield connection
    connection.close()


def test_list_pipeline_projects_empty_when_no_runs_dir(conn, tmp_path):
    assert browse_service.list_pipeline_projects(conn, tmp_path) == []


def test_list_pipeline_projects_lists_folders_from_filesystem(conn, tmp_path):
    _touch(tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation" / "artifact.v1.md")
    entries = browse_service.list_pipeline_projects(conn, tmp_path)
    assert [e.name for e in entries] == ["my-run-20260728-120000"]
    assert entries[0].rel_path == "my-run-20260728-120000"
    assert entries[0].is_dir is True


def test_list_pipeline_projects_annotates_brand_from_db(conn, tmp_path):
    _touch(tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation" / "artifact.v1.md")
    db_mod.create_project(conn, "my-run-20260728-120000", "my-run", "raisinggoodsports", "2026-07-28T12:00:00Z")
    entries = browse_service.list_pipeline_projects(conn, tmp_path)
    assert entries[0].name == "my-run-20260728-120000 (raisinggoodsports)"


def test_list_pipeline_projects_orphan_folder_shown_without_brand(conn, tmp_path):
    _touch(tmp_path / "runs" / "orphan-20260728-120000" / "01-ideation" / "artifact.v1.md")
    entries = browse_service.list_pipeline_projects(conn, tmp_path)
    assert entries[0].name == "orphan-20260728-120000"


def test_list_pipeline_projects_sorted_newest_first_by_db_created_at(conn, tmp_path):
    _touch(tmp_path / "runs" / "older-20260701-090000" / "01-ideation" / "artifact.v1.md")
    _touch(tmp_path / "runs" / "newer-20260728-120000" / "01-ideation" / "artifact.v1.md")
    db_mod.create_project(conn, "older-20260701-090000", "older", "generic", "2026-07-01T09:00:00Z")
    db_mod.create_project(conn, "newer-20260728-120000", "newer", "generic", "2026-07-28T12:00:00Z")
    entries = browse_service.list_pipeline_projects(conn, tmp_path)
    assert [e.rel_path for e in entries] == ["newer-20260728-120000", "older-20260701-090000"]


def test_list_pipeline_projects_orphan_folder_sorted_by_parsed_timestamp(conn, tmp_path):
    # No DB rows at all -- both folders fall back to parsing the trailing
    # YYYYMMDD-HHMMSS from the folder name.
    _touch(tmp_path / "runs" / "older-20260701-090000" / "01-ideation" / "artifact.v1.md")
    _touch(tmp_path / "runs" / "newer-20260728-120000" / "01-ideation" / "artifact.v1.md")
    entries = browse_service.list_pipeline_projects(conn, tmp_path)
    assert [e.rel_path for e in entries] == ["newer-20260728-120000", "older-20260701-090000"]


def test_list_pipeline_projects_mixed_db_and_orphan_sort_by_real_chronology(conn, tmp_path):
    # A naive string-sort comparing ISO created_at ("2026-...") against a
    # compact orphan-fallback key ("2026...") would put every orphan above
    # every DB-matched project regardless of actual date, since "-" sorts
    # below "0" at the same string index. This must sort by real
    # chronological value across both formats: db-matched (July 28) is
    # newest, then the orphan (July 15), then db-matched (July 1) oldest.
    _touch(tmp_path / "runs" / "db-newest-20260728-120000" / "01-ideation" / "artifact.v1.md")
    _touch(tmp_path / "runs" / "orphan-mid-20260715-120000" / "01-ideation" / "artifact.v1.md")
    _touch(tmp_path / "runs" / "db-oldest-20260701-090000" / "01-ideation" / "artifact.v1.md")
    db_mod.create_project(conn, "db-newest-20260728-120000", "db-newest", "generic", "2026-07-28T12:00:00+00:00")
    db_mod.create_project(conn, "db-oldest-20260701-090000", "db-oldest", "generic", "2026-07-01T09:00:00+00:00")
    entries = browse_service.list_pipeline_projects(conn, tmp_path)
    assert [e.rel_path for e in entries] == [
        "db-newest-20260728-120000",
        "orphan-mid-20260715-120000",
        "db-oldest-20260701-090000",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_browse_service.py -k list_pipeline_projects -v`
Expected: FAIL with `AttributeError: module 'pipeline_app.browse_service' has no attribute 'list_pipeline_projects'`

- [ ] **Step 3: Implement**

Add to the import block in `pipeline_app/browse_service.py`:

```python
from datetime import datetime, timezone

from pipeline_app import db as db_mod
```

Add the function (anywhere after `runs_root`):

```python
_RUN_ID_TIMESTAMP_RE = re.compile(r"-(\d{8}-\d{6})$")


def _parse_created_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_run_id_timestamp(name: str) -> datetime | None:
    m = _RUN_ID_TIMESTAMP_RE.search(name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)


def list_pipeline_projects(conn, repo_root: Path) -> list["Entry"]:
    runs_dir = runs_root(repo_root)
    if not runs_dir.is_dir():
        return []

    brand_and_created: dict[str, tuple[str, str]] = {
        row["run_id"]: (row["brand"], row["created_at"]) for row in db_mod.list_projects(conn)
    }

    candidates: list[tuple[str, str | None, str | None]] = []
    try:
        with os.scandir(runs_dir) as it:
            for entry in it:
                if entry.is_symlink() or not entry.is_dir():
                    continue
                brand, created_at = brand_and_created.get(entry.name, (None, None))
                candidates.append((entry.name, brand, created_at))
    except OSError as exc:
        raise FolderReadError(str(exc)) from exc

    _EPOCH = datetime.min.replace(tzinfo=timezone.utc)

    def sort_tuple(item: tuple[str, str | None, str | None]):
        # DB created_at is ISO 8601 ("2026-07-28T12:00:00+00:00"); an
        # orphan folder's fallback key is parsed from its run_id suffix
        # ("20260728-120000"). These two string formats do NOT compare
        # correctly against each other lexically (e.g. "2026-...": the
        # "-" at index 4 sorts below the "0" a compact-format string has
        # at the same index) -- both are parsed to real datetimes here so
        # comparison is always by actual chronological value, never by
        # incidental string shape.
        name, _brand, created_at = item
        when = _parse_created_at(created_at) if created_at else _parse_run_id_timestamp(name)
        return (when is not None, when or _EPOCH, name.lower())

    candidates.sort(key=sort_tuple, reverse=True)
    return [
        Entry(
            name=f"{name} ({brand})" if brand else name,
            rel_path=name,
            is_dir=True,
        )
        for name, brand, _created_at in candidates
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_browse_service.py -k list_pipeline_projects -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full browse_service test suite**

Run: `pytest tests/test_browse_service.py -v`
Expected: PASS (all tests from Tasks 1-4)

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/browse_service.py pipeline-app/tests/test_browse_service.py
git commit -m "feat(browse): add list_pipeline_projects for the pipeline tree's project-listing top level"
```

---

### Task 5: Wire routes — `root` query param, pipeline top level, pointer.yaml resolution

**Files:**
- Modify: `pipeline_app/routes/browse.py` (full rewrite of `_folder_context` and all three routes)
- Modify: `tests/test_routes_browse.py` (update one existing test's assertions, append new tests)

**Interfaces:**
- Consumes: `browse_service.root_path`, `list_pipeline_projects`, `list_children`, `resolve_grounding_pointer`, `render_md_file`, `resolve_under_output`, `PathSafetyError`, `FolderReadError` (all from Tasks 1-4 plus existing).
- Produces: `/browse` (renders both `output` and `pipeline` sections), `/browse/tree?root=&path=`, `/browse/file?root=&path=` — `root` defaults to `"output"` on all three for backward compatibility.

- [ ] **Step 1: Update the one existing test whose assertions change**

The htmx links now carry `&root=...`. Replace this test in `tests/test_routes_browse.py`:

```python
def test_browse_tree_items_carry_htmx_attributes_not_ids(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert 'hx-get="/browse/tree?path=thinkers&root=output"' in resp.text
    assert 'hx-trigger="toggle once from:closest details"' in resp.text
    assert 'hx-target="this"' in resp.text

    tree_resp = test_client.get("/browse/tree", params={"path": "thinkers", "root": "output"})
    assert tree_resp.status_code == 200
    assert 'hx-get="/browse/file?path=thinkers/plato.md&root=output"' in tree_resp.text
    assert 'hx-sync="#browse-doc:replace"' in tree_resp.text
```

- [ ] **Step 2: Write the new failing tests**

Append to `tests/test_routes_browse.py`:

```python
def test_browse_root_shows_pipeline_and_corpus_headings(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "Pipeline Outputs" in resp.text
    assert "Corpus Docs" in resp.text


def test_browse_root_no_runs_dir_shows_empty_message(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "No pipeline runs yet." in resp.text


def test_browse_tree_pipeline_root_lists_projects_from_filesystem(client):
    test_client, tmp_path = client
    _touch(tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation" / "artifact.v1.md")
    resp = test_client.get("/browse/tree", params={"root": "pipeline"})
    assert resp.status_code == 200
    assert "my-run-20260728-120000" in resp.text


def test_browse_tree_pipeline_root_annotates_brand_from_db(client):
    test_client, tmp_path = client
    _touch(tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation" / "artifact.v1.md")
    from pipeline_app import db as db_mod
    db_mod.create_project(
        test_client.app.state.conn, "my-run-20260728-120000", "my-run",
        "raisinggoodsports", "2026-07-28T12:00:00Z",
    )
    resp = test_client.get("/browse/tree", params={"root": "pipeline"})
    assert resp.status_code == 200
    assert "my-run-20260728-120000 (raisinggoodsports)" in resp.text


def test_browse_tree_pipeline_stage_lists_artifact_versions_numerically(client):
    test_client, tmp_path = client
    stage_dir = tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation"
    _touch(stage_dir / "artifact.v2.md")
    _touch(stage_dir / "artifact.v10.md")
    _touch(stage_dir / "artifact.v1.md")
    resp = test_client.get(
        "/browse/tree",
        params={"root": "pipeline", "path": "my-run-20260728-120000/01-ideation"},
    )
    assert resp.status_code == 200
    assert resp.text.index("artifact.v1.md") < resp.text.index("artifact.v2.md") < resp.text.index("artifact.v10.md")


def test_browse_tree_pipeline_excludes_raw_output(client):
    test_client, tmp_path = client
    stage_dir = tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation"
    _touch(stage_dir / "artifact.v1.md")
    _touch(stage_dir / "raw_output.md")
    resp = test_client.get(
        "/browse/tree",
        params={"root": "pipeline", "path": "my-run-20260728-120000/01-ideation"},
    )
    assert resp.status_code == 200
    assert "raw_output.md" not in resp.text


def test_browse_tree_pipeline_project_shows_grounding_folder_when_pointer_valid(client):
    test_client, tmp_path = client
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "2026-07-28-topic.md").write_text("# Brief", encoding="utf-8")
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "rgs-briefs/2026-07-28-topic.md",
    )
    resp = test_client.get(
        "/browse/tree", params={"root": "pipeline", "path": "my-run-20260728-120000"}
    )
    assert resp.status_code == 200
    assert "00-grounding" in resp.text


def test_browse_tree_pipeline_grounding_no_pointer_excluded_from_project(client):
    test_client, tmp_path = client
    (tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding" / "events").mkdir(parents=True)
    resp = test_client.get(
        "/browse/tree", params={"root": "pipeline", "path": "my-run-20260728-120000"}
    )
    assert resp.status_code == 200
    assert "00-grounding" not in resp.text


def test_browse_tree_pipeline_grounding_stage_shows_synthetic_current_brief_entry(client):
    test_client, tmp_path = client
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "2026-07-28-topic.md").write_text("# Brief", encoding="utf-8")
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "rgs-briefs/2026-07-28-topic.md",
    )
    resp = test_client.get(
        "/browse/tree",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding"},
    )
    assert resp.status_code == 200
    assert "current-brief.md (2026-07-28-topic.md)" in resp.text


def test_browse_file_pipeline_artifact_renders(client):
    test_client, tmp_path = client
    _touch(
        tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation" / "artifact.v1.md",
        "---\nstatus: draft\n---\n\n# Concept\n\nBody.\n",
    )
    resp = test_client.get(
        "/browse/file",
        params={"root": "pipeline", "path": "my-run-20260728-120000/01-ideation/artifact.v1.md"},
    )
    assert resp.status_code == 200
    assert "<h1>Concept</h1>" in resp.text


def test_browse_file_pipeline_grounding_pointer_renders_target(client):
    test_client, tmp_path = client
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "2026-07-28-topic.md").write_text("# Grounded Brief\n", encoding="utf-8")
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "rgs-briefs/2026-07-28-topic.md",
    )
    resp = test_client.get(
        "/browse/file",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding/pointer.yaml"},
    )
    assert resp.status_code == 200
    assert "<h1>Grounded Brief</h1>" in resp.text


def test_browse_file_pipeline_grounding_pointer_missing_target_shows_error(client):
    test_client, tmp_path = client
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "rgs-briefs/does-not-exist.md",
    )
    resp = test_client.get(
        "/browse/file",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding/pointer.yaml"},
    )
    assert resp.status_code == 200
    assert "Grounding pointer could not be resolved." in resp.text


def test_browse_file_pipeline_grounding_pointer_outside_rgs_briefs_shows_error(client):
    # End-to-end containment check: a pointer.yaml whose content resolves
    # somewhere else under repo_root (not rgs-briefs/) must not be followed
    # and must not leak that file's content into the viewer.
    test_client, tmp_path = client
    secret = tmp_path / "runs" / "other-run" / "secret.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("# Secret\n", encoding="utf-8")
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "runs/other-run/secret.md",
    )
    resp = test_client.get(
        "/browse/file",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding/pointer.yaml"},
    )
    assert resp.status_code == 200
    assert "Grounding pointer could not be resolved." in resp.text
    assert "Secret" not in resp.text


def test_browse_file_unknown_root_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/file", params={"root": "bogus", "path": "x.md"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_tree_unknown_root_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"root": "bogus", "path": ""})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_routes_browse.py -v`
Expected: FAIL — the updated htmx-attribute test fails on the missing `&root=` suffix; the new `pipeline`-root tests fail (route doesn't accept/handle `root` yet); `TypeError` from `list_children` missing `repo_root` inside the still-unmodified route.

- [ ] **Step 4: Implement**

Replace the entire contents of `pipeline_app/routes/browse.py`:

```python
# pipeline_app/routes/browse.py
from fastapi import APIRouter, Request

from pipeline_app import browse_service

router = APIRouter()


def _folder_context(request: Request, root: str, rel_path: str) -> dict:
    repo_root = request.app.state.repo_root
    try:
        root_dir = browse_service.root_path(repo_root, root)
    except ValueError:
        return {"error": "Invalid path."}

    is_pipeline_top = root == "pipeline" and rel_path.strip() in ("", ".", "/")
    if is_pipeline_top:
        if not root_dir.is_dir():
            return {"empty_message": "No pipeline runs yet."}
        try:
            entries = browse_service.list_pipeline_projects(request.app.state.conn, repo_root)
        except browse_service.FolderReadError as exc:
            return {"error": f"Could not read folder: {exc}"}
        return {"entries": entries}

    try:
        folder = browse_service.resolve_under_output(root_dir, rel_path)
    except browse_service.PathSafetyError:
        return {"error": "Invalid path."}
    if not folder.is_dir():
        return {"error": "Folder not found."}
    try:
        return {"entries": browse_service.list_children(folder, root_dir, repo_root)}
    except browse_service.FolderReadError as exc:
        return {"error": f"Could not read folder: {exc}"}


@router.get("/browse")
def browse_root(request: Request):
    context = {
        "output": _folder_context(request, "output", ""),
        "pipeline": _folder_context(request, "pipeline", ""),
        "active_nav": "browse",
        "cli_available": request.app.state.cli_available,
    }
    return request.app.state.templates.TemplateResponse(request, "browse.html", context)


@router.get("/browse/tree")
def browse_tree(request: Request, path: str = "", root: str = "output"):
    context = _folder_context(request, root, path)
    context["root"] = root
    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_tree_items.html", context
    )


@router.get("/browse/file")
def browse_file(request: Request, path: str = "", root: str = "output"):
    repo_root = request.app.state.repo_root
    try:
        root_dir = browse_service.root_path(repo_root, root)
    except ValueError:
        return request.app.state.templates.TemplateResponse(
            request, "partials/browse_file.html", {"error": "Invalid path."}
        )

    try:
        file_path = browse_service.resolve_under_output(root_dir, path)
    except browse_service.PathSafetyError:
        file_path = None
        context = {"error": "Invalid path."}

    if file_path is not None:
        if not file_path.exists():
            context = {"error": "Path does not exist."}
        elif file_path.is_dir():
            context = {"error": "Path is a directory, not a file."}
        elif file_path.name == "pointer.yaml":
            target = browse_service.resolve_grounding_pointer(file_path.parent, repo_root)
            if target is None:
                context = {"error": "Grounding pointer could not be resolved."}
            else:
                context = browse_service.render_md_file(target)
        elif not file_path.name.lower().endswith(".md"):
            context = {"error": "Not a valid .md file path."}
        else:
            context = browse_service.render_md_file(file_path)

    return request.app.state.templates.TemplateResponse(
        request, "partials/browse_file.html", context
    )
```

- [ ] **Step 5: Run tests — expect template-related failures still**

Run: `pytest tests/test_routes_browse.py -v`
Expected: The `pipeline`-root and htmx-attribute tests still FAIL at this point (templates haven't been updated — Task 6). Confirm no `TypeError`/`AttributeError` remain and failures are only assertion mismatches on rendered HTML content (e.g. missing "Pipeline Outputs" heading, missing `&root=` in links) — this confirms the route logic itself is correct before moving to templates.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/routes/browse.py pipeline-app/tests/test_routes_browse.py
git commit -m "feat(browse): add root query param, pipeline top-level listing, and pointer.yaml resolution to browse routes"
```

---

### Task 6: Templates — two tree sections, `root` threading, empty-state message

**Files:**
- Modify: `pipeline_app/templates/browse.html`
- Modify: `pipeline_app/templates/partials/browse_tree_items.html`

**Interfaces:**
- Consumes: `output`/`pipeline` context dicts from `browse_root` (Task 5, each shaped `{"entries": [...]}` or `{"error": "..."}` or `{"empty_message": "..."}`); `root` context key from `browse_tree` (Task 5).
- Produces: fully working `/browse` page. No downstream consumers — this is the last task.

- [ ] **Step 1: Run the full test suite to confirm it currently fails only on template content**

Run: `pytest tests/test_routes_browse.py -v`
Expected: FAIL on the specific assertions noted at the end of Task 5 (missing headings, missing `&root=` in links, missing "No pipeline runs yet." text) — confirms scope before editing templates.

- [ ] **Step 2: Rewrite `browse.html`**

Replace the entire contents of `pipeline_app/templates/browse.html`:

```html
<!-- pipeline_app/templates/browse.html -->
{% extends "base.html" %}
{% block content %}
<h1>Browse</h1>
<div class="browse-shell">
  <div class="browse-tree">
    <h2>Pipeline Outputs</h2>
    {% with entries=pipeline.entries, error=pipeline.error, empty_message=pipeline.empty_message, root="pipeline" %}
      {% include "partials/browse_tree_items.html" %}
    {% endwith %}
    <h2>Corpus Docs</h2>
    {% with entries=output.entries, error=output.error, empty_message=output.empty_message, root="output" %}
      {% include "partials/browse_tree_items.html" %}
    {% endwith %}
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

- [ ] **Step 3: Rewrite `browse_tree_items.html`**

Replace the entire contents of `pipeline_app/templates/partials/browse_tree_items.html`:

```html
<!-- pipeline_app/templates/partials/browse_tree_items.html -->
{% if error %}
<p class="browse-error">{{ error }}</p>
{% elif empty_message %}
<p class="browse-placeholder">{{ empty_message }}</p>
{% else %}
  {# A folder with no visible content below it (only reachable via a
     stale/typed-in path, since list_children already excludes such
     subfolders from their parent's listing) renders as an empty result
     with no special messaging -- an empty folder is just an empty list,
     same as any other folder with no visible children. #}
  {% for entry in entries %}
    {% if entry.is_dir %}
    <details>
      <summary>{{ entry.name }}</summary>
      <div class="children"
           hx-get="/browse/tree?path={{ entry.rel_path | urlencode }}&root={{ root }}"
           hx-trigger="toggle once from:closest details"
           hx-target="this"
           hx-swap="innerHTML"></div>
    </details>
    {% else %}
    <div class="browse-file-row">
      <a href="#"
         hx-get="/browse/file?path={{ entry.rel_path | urlencode }}&root={{ root }}"
         hx-target="#browse-doc"
         hx-swap="innerHTML"
         hx-sync="#browse-doc:replace"
         hx-indicator="#browse-spinner">{{ entry.name }}</a>
    </div>
    {% endif %}
  {% endfor %}
{% endif %}
```

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS — every test across `test_browse_service.py` and `test_routes_browse.py` (Tasks 1-6), plus all pre-existing suites (`test_routes_projects.py`, `test_routes_stages.py`, etc. — unaffected by this feature) passes.

- [ ] **Step 5: Manual smoke check**

Run the app and confirm visually: `uvicorn pipeline_app.main:create_default_app --factory --reload` from `pipeline-app/`, then open `http://127.0.0.1:8420/browse` (adjust port/host to match how it's normally launched in this repo) — confirm "Pipeline Outputs" lists real `runs/` projects newest-first with brand labels, a stage folder's artifact versions open in the same viewer pane as `output/` docs, and an RGS project's grounding stage (if one exists locally) shows a clickable `current-brief.md (...)` entry that renders the real brief.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/templates/browse.html pipeline-app/pipeline_app/templates/partials/browse_tree_items.html
git commit -m "feat(browse): render Pipeline Outputs and Corpus Docs as two tree sections sharing one viewer"
```

---

## Revision history

**2026-07-30, initial draft → Opus review → this revision.** A second Opus-model review (of the plan itself, after the earlier spec review) caught five issues, all fixed above:

1. **Real sort bug in `list_pipeline_projects`:** DB `created_at` (ISO 8601) and the orphan-folder fallback key (compact `YYYYMMDD-HHMMSS`) were compared as raw strings — since `"-"` sorts below `"0"` at the same index, every orphan folder would sort above every DB-matched project regardless of actual date. Fixed by parsing both to real `datetime` objects before comparing (Task 4); added a mixed-format regression test that a homogeneous-data test can't catch.
2. **Asymmetry between `_has_md_below` and `list_children` on `raw_output.md`:** `list_children` skipped it but `_has_md_below` still counted it as content, so a stage folder containing only `raw_output.md` would render as an expandable folder that opens empty. Fixed by skipping it in both (Task 3), with a test.
3. **Misleading test:** `test_resolve_grounding_pointer_rejects_path_outside_rgs_briefs` used a `"../other-run/secret.md"` value, which is a traversal-outside-`repo_root` case already covered by a separate test, not an "elsewhere-under-repo_root" case. Fixed to use `"runs/other-run/secret.md"` (Task 2), and added the equivalent end-to-end route test (Task 5).
4. **Broken intermediate commit:** Task 3 changed `list_children`'s signature but the not-yet-rewritten `routes/browse.py` (Task 5's job) still called it with the old arity — landing that commit alone would 500 every `/browse` request. Fixed by adding an interim one-line patch to the existing call site at the end of Task 3, verified by running `test_routes_browse.py` before committing (Task 3, Steps 7-8).
5. **Missing end-to-end coverage:** the design spec's Testing section asked for the pointer containment-violation case to be covered at the route level, not just the service level. Added (Task 5).

Also documented as a deliberate, declared deviation (not a defect): the design spec described both tree sections as htmx-loaded on page open; this plan renders them synchronously in the `/browse` route instead, matching the app's existing pattern for the current single `output/` section and avoiding two extra round trips for no benefit. See the Architecture note above.

## Self-Review Notes

- **Spec coverage:** §1 (root registry) → Task 1. §2 (root query param + empty state) → Task 5. §3 (`_has_md_below`/`list_children` repo_root, pointer entries, raw_output.md exclusion, version sort) → Task 3. §4 (pointer containment check in file route) → Tasks 2 + 5. §5 (project listing, brand lookup, sort order) → Task 4. §6 (templates) → Task 6. §7 (error handling) → covered inline across Tasks 3/5 tests. Testing section's two target files → Tasks 1-4 (`test_browse_service.py`) and Task 5 (`test_routes_browse.py`).
- **Placeholder scan:** no TBD/TODO; every step has literal code, not a description of code.
- **Type consistency:** `list_children(folder, root, repo_root)` and `_has_md_below(folder, repo_root)` signatures are identical everywhere they're defined (Task 3) and called (Tasks 3, 4 doesn't call them, Task 5's route). `resolve_grounding_pointer(pointer_dir, repo_root) -> Path | None` matches across Task 2 (definition), Task 3 (`_has_md_below`/`list_children` call sites), and Task 5 (route call site). `list_pipeline_projects(conn, repo_root) -> list[Entry]` matches between Task 4 (definition) and Task 5 (route call site).
