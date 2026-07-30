# Pipeline outputs on the Browse page — design spec

Date: 2026-07-30
Status: Approved

## Problem

`/browse` currently only shows `output/` — the corpus reference docs. The
actual deliverables of the six-stage pipeline (`shorts-ideation` through
`social-repurpose`) live in a completely different tree, `runs/<run_id>/<NN-stage>/artifact.vN.md`,
and today the only way to view one is drilling into `/projects/{id}/stages/{stage_id}`
one stage at a time, or the open-path `/inspector` (no tree, no discovery). There's
no single place to see every artifact from every project, browsable the same
way the corpus docs already are.

One stage is a special case: `grounding` (RaisingGoodSports only) never writes
`artifact.vN.md` into its `runs/` folder — it writes a `pointer.yaml` pointing
at the real file in the repo-root `rgs-briefs/` folder. A plain filesystem scan
of `runs/` would show that stage as always-empty.

## Goals

- Add a "Pipeline Outputs" section to `/browse`, organized project → stage →
  artifact version, using the existing tree-and-viewer UI pattern.
- Reuse the existing markdown-viewing pipeline (`render_md_file`,
  `browse_file.html`) unchanged — a pipeline artifact opens exactly like a
  corpus doc does today.
- Resolve the grounding stage's pointer-based storage into one synthetic,
  clickable entry so grounding output isn't invisible in this view.
- Keep `output/` browsing (existing behavior) completely intact.

## Non-goals

- No change to how artifacts are written, versioned, or approved
  (`artifacts.py`, `approval_service.py`, `turn_service.py` untouched).
- No change to `/projects/{id}/stages/{stage_id}` or `/inspector` — this is an
  additive third way to reach the same files, not a replacement.
- No DB writes. This is read-only, same as the rest of `/browse`.
- No pagination/search — matches the current `/browse` scope; can be a later
  iteration if the project count grows large enough to matter.

## Design

### 1. Root registry in `browse_service.py`

Generalize the single hardcoded `output/` root into a small registry of two
named roots:

```python
def root_path(repo_root: Path, root: str) -> Path:
    if root == "output":
        return (repo_root / "output").resolve()
    if root == "pipeline":
        return (repo_root / "runs").resolve()
    raise ValueError(f"unknown browse root: {root!r}")
```

`resolve_under_output`, `list_children`, and `render_md_file` are unchanged in
behavior — they already just take a `root: Path` and a folder/file `Path`
under it. Callers pass whichever root's path.

### 2. Routes gain a `root` query param

`routes/browse.py`'s three routes (`/browse`, `/browse/tree`, `/browse/file`)
each gain `root: str = "output"` (default preserves today's behavior for any
existing bookmarked links). `_folder_context` and the file route resolve
`browse_service.root_path(repo_root, root)` instead of always calling
`output_root(...)`.

### 3. Pipeline tree contents (project → stage → version)

A new function, `list_pipeline_projects(conn, repo_root) -> list[Entry]`,
builds the top level of the pipeline tree:

- Enumerate `runs/*` folders on disk (filesystem is the source of truth, same
  principle as `output/` browsing — no folder is hidden just because its DB
  row is missing).
- For each, look up its `brand` from the `projects` table by `run_id` (a
  best-effort annotation, not a requirement — a folder with no matching DB row
  still appears, just without a `(brand)` suffix).
- Label: `{run_id} ({brand})` or just `{run_id}` if no DB match.
- Sort **newest first**, parsed from the trailing `YYYYMMDD-HHMMSS` in
  `run_id` (falls back to name-sort if a folder doesn't match that pattern).

Below a project, `list_children` already recurses correctly with no changes:
stage folders (`00-grounding`, `01-ideation`, ...) sort correctly today because
`NN-` prefixes are already zero-padded strings. One real bug to fix while
here: `_versions_in`/`list_children`'s file sort is a plain string sort, so
`artifact.v10.md` sorts before `artifact.v2.md` once a stage passes 9
revisions. `list_children` gets a version-aware sort key for filenames
matching `artifact.v{N}.md` (numeric on `N`), falling back to the existing
alpha sort for anything else — this fixes the bug for both the new pipeline
view and the (currently theoretical, since `output/` doesn't contain
`artifact.vN.md` files) general case.

### 4. Grounding special case

When `list_children` scans a stage folder whose name matches the grounding
stage's dir (`00-grounding`, brand-scoped to `raisinggoodsports`), it reads
that folder's `pointer.yaml` via the existing `grounding_service.read_pointer`.
If present and the target file exists under `rgs-briefs/`, one synthetic
`Entry` is appended: name `current-brief.md → {target filename}`, with a
distinct `rel_path` scheme (`pointer:{run_id}/00-grounding`) that isn't a real
filesystem path — it signals to the file route "resolve via the pointer, not
directly." If no pointer or the target is missing, no synthetic entry is
added (stage shows genuinely empty, which is accurate).

`/browse/file` recognizes the `pointer:` prefix, re-reads the same
`pointer.yaml`, resolves the target under `repo_root / "rgs-briefs"`
(a third, internal-only root — never exposed as a browsable top-level
section, only ever reached via this server-generated link), and renders it
through the existing `render_md_file`.

### 5. Template changes

- `browse.html`: two stacked sections, each with its own `htmx`-loaded tree
  container — `Pipeline Outputs` (`hx-get="/browse/tree?root=pipeline"`) above
  `Corpus Docs` (`hx-get="/browse/tree?root=output"`, today's behavior,
  functionally unchanged apart from now passing `root=output` explicitly).
  Both feed the same `#browse-doc` viewer pane via the existing click/htmx
  wiring in `browse_tree_items.html` — no changes needed to
  `browse_file.html`.
- `partials/browse_tree_items.html`: needs `root` threaded through its
  recursive `hx-get` links (folder-expand and file-select) so descending into
  a subfolder or opening a file preserves which root it came from.

### 6. Error handling

No new error paths — this reuses `PathSafetyError`, `FolderReadError`, and the
5MB oversize cap exactly as they exist today. The one new failure mode
(pointer file references a deleted `rgs-briefs` file) degrades to "no
synthetic entry shown," not a 500.

## Testing

- `test_browse_service.py`: `root_path()` for both known roots and the
  unknown-root error; the numeric version-sort fix (`v2` before `v10`); the
  grounding pointer → synthetic entry logic (present pointer, missing pointer,
  pointer target deleted).
- `test_routes_browse.py`: `root=pipeline` end-to-end for tree and file
  routes, including the `pointer:` file-route path; confirm `root=output`
  behavior is byte-identical to pre-change responses.

## Risks / open questions

None blocking. Worth calling out: pipeline-outputs browsing is filesystem-driven
first, DB-annotated second — consistent with how `output/` already works, and
means an orphaned `runs/` folder (DB row deleted, folder left behind) still
shows up rather than silently vanishing.
