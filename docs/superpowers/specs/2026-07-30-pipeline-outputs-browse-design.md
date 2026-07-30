# Pipeline outputs on the Browse page — design spec

Date: 2026-07-30
Status: Approved (revised after Opus review — see "Revision history")

## Problem

`/browse` currently only shows `output/` — the corpus reference docs. The
actual deliverables of the six-stage pipeline (`shorts-ideation` through
`social-repurpose`) live in a completely different tree, `runs/<run_id>/<NN-stage>/artifact.vN.md`,
and today the only way to view one is drilling into `/projects/{id}/stages/{stage_id}`
one stage at a time, or the open-path `/inspector` (no tree, no discovery). There's
no single place to see every artifact from every project, browsable the same
way the corpus docs already are.

One stage is a special case: `grounding` (RaisingGoodSports only) never writes
`artifact.vN.md` into its `runs/` folder — it writes a `pointer.yaml` whose
`rgs_brief_path` field is an already-repo-root-relative path (e.g.
`rgs-briefs/2026-07-28-....md`) into the real file, living in the repo-root
`rgs-briefs/` folder. A plain filesystem scan of `runs/` would show that stage
as always-empty, since `.md`-file discovery (`_has_md_below`) only looks for
`.md` files and `pointer.yaml` isn't one — this filters `00-grounding` out of
its *parent* folder's listing before any stage-level logic runs.

Each stage folder also contains a `raw_output.md` (`turn_service.py:132`) — a
pre-versioning scratch file whose content becomes the body of the next
`artifact.vN.md` once a turn finalizes. It persists on disk after that, so a
naive `.md`-file scan would surface it as an extra, confusing entry alongside
the real versioned artifacts.

## Goals

- Add a "Pipeline Outputs" section to `/browse`, organized project → stage →
  artifact version, using the existing tree-and-viewer UI pattern.
- Reuse the existing markdown-viewing pipeline (`render_md_file`,
  `browse_file.html`) unchanged — a pipeline artifact opens exactly like a
  corpus doc does today.
- Resolve the grounding stage's pointer-based storage into one real,
  clickable entry (not a synthetic path scheme) so grounding output isn't
  invisible in this view, with explicit path-containment validation on the
  pointer's target — this is a new trust boundary (a file read whose target
  path comes from YAML content) and gets checked accordingly.
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

`resolve_under_output` is unchanged — it already just takes a `root: Path`
and resolves safely under it, for either named root.

### 2. Routes gain a `root` query param

`routes/browse.py`'s three routes (`/browse`, `/browse/tree`, `/browse/file`)
each gain `root: str = "output"` (default preserves today's behavior for any
existing bookmarked links). `_folder_context` resolves
`browse_service.root_path(repo_root, root)` instead of always calling
`output_root(...)`. If `runs/` doesn't exist yet (fresh checkout, no projects
created), `/browse/tree?root=pipeline` returns a friendly "No pipeline runs
yet." context distinct from the generic "Folder not found." error, so an
empty pipeline section doesn't read as broken.

### 3. `list_children` / `_has_md_below` gain a `repo_root` parameter

Both functions currently take `(folder, root)`. They gain a third parameter,
`repo_root: Path`, needed because a grounding pointer's target is resolved
relative to `repo_root` (`rgs-briefs/...`), not relative to `root` (which is
`runs/` for the pipeline tree, `output/` for the corpus tree — neither is
`repo_root` itself, and the two named roots don't share a common ancestor
inside the repo tree either way, so this can't be derived from `root` alone).
For `output/` scanning, `repo_root` is simply threaded through and unused by
existing logic — no behavior change there.

**File-inclusion rules** (in `list_children`), in order:

1. A file named `raw_output.md` is always skipped — it's pre-versioning
   scratch state already captured in the corresponding `artifact.vN.md` body,
   and showing both is redundant clutter, not useful history.
2. A file matching `artifact.v{N}.md` or any other `.md` file: included as
   today.
3. A file named exactly `pointer.yaml`: read via
   `grounding_service.read_pointer(folder)`. If it resolves to an existing
   file under `repo_root`, include a synthetic `Entry` — name
   `current-brief.md → {target filename}`, but critically **`rel_path` is
   the pointer.yaml's own real, already-safe path** (e.g.
   `{run_id}/00-grounding/pointer.yaml`), not an invented scheme. It resolves
   through the existing `resolve_under_output` exactly like any other file,
   with no new path-safety surface at the tree-building layer. If the
   pointer is missing or its target doesn't exist, no entry is added (empty
   stage, accurately).

**`_has_md_below`** gets the matching fix: a folder counts as "has content"
if it has an `.md` file below (existing rule, unchanged) **or** it directly
contains a `pointer.yaml` whose target resolves to an existing file under
`repo_root` (checked via the same `read_pointer` + existence check as above).
This is what makes `00-grounding` survive its *parent* folder's listing filter
— today it's invisible before `list_children` on the stage folder itself is
ever reached, since the parent-level scan is what decides whether to
recurse into it at all. No brand check is needed anywhere in this logic:
`pointer.yaml` only exists in `00-grounding` folders for RGS projects by
construction (`project_service.create_project` never materializes that stage
row/dir for other brands — `pipeline_config.py`'s `brand_scope` filtering
already guarantees this), so the file-based check is sufficient without
threading brand/project context through the recursive scan.

**Version sort fix**: `list_children`'s `files.sort(key=lambda e: e.name.lower())`
is replaced with a key that sorts `artifact.v{N}.md` names numerically on
`N` (matching a local regex, same pattern as `artifacts._VERSION_RE`) and
falls back to the existing alpha sort for anything else (e.g. the synthetic
`current-brief.md` entry). This was misattributed in the original draft of
this spec to `artifacts._versions_in` — that function is already numeric
(`int(m.group(1))`); the actual bug is `browse_service.py`'s file sort.
`output/` doesn't currently contain any `artifact.vN.md`-named files, so this
is a no-op there today, not a behavior change requiring justification beyond
"fixes the one real place it matters."

### 4. Pointer resolution in the file route — explicit containment check

`routes/browse.py`'s `/browse/file` handler, after resolving `file_path` via
`resolve_under_output` (which may now resolve to a real `pointer.yaml` under
`runs/`), gains one branch **before** its existing `.md`-suffix check:

```python
if file_path.name == "pointer.yaml":
    target_rel = grounding_service.read_pointer(file_path.parent)
    rgs_briefs_root = (repo_root / "rgs-briefs").resolve()
    target = (repo_root / (target_rel or "")).resolve() if target_rel else None
    if target is None or not target.is_relative_to(rgs_briefs_root) or not target.exists():
        context = {"error": "Grounding pointer could not be resolved."}
    else:
        file_path = target  # falls through to the existing .md/render checks
```

The `is_relative_to(rgs_briefs_root)` check is the actual security property
here — not "this link is server-generated," which the original draft of this
spec incorrectly treated as sufficient. `pointer.yaml`'s content is
YAML read from disk; treating its `rgs_brief_path` value as a trusted
relative path without containment validation would let a corrupted or
hand-edited pointer file read arbitrary files under `repo_root`. This mirrors
the validation `resolve_under_output` already does for ordinary tree
navigation, applied at the one new point where a file path comes from
content rather than from the request/tree structure.

No third named root is introduced — `rgs-briefs/` is validated inline against
`repo_root`, not exposed as a browsable root or reachable via any
user-suppliable query parameter.

### 5. Pipeline tree top level (project listing)

A new function, `list_pipeline_projects(conn, repo_root) -> list[Entry]`:

- Enumerates `runs/*` folders on disk (filesystem is the source of truth,
  same principle as `output/` browsing — no folder is hidden just because
  its DB row is missing).
- Builds a `run_id -> (brand, created_at)` lookup from `db_mod.list_projects(conn)`
  (already returns both columns — no new DB query function needed).
- Label: `{run_id} ({brand})` if a DB match exists, else just `{run_id}`.
- Sort **newest first**: DB-matched projects sort by their `created_at`
  (ISO 8601, sorts correctly as a string); folders with no DB match fall back
  to the `YYYYMMDD-HHMMSS` suffix parsed from the folder name, and sort
  amongst the rest by that parsed timestamp. A folder matching neither
  pattern sorts last, by name.

### 6. Template changes

- `browse.html`: drops the hardcoded `<h1>Browse output/</h1>` and the
  single server-rendered `{% include %}`. Becomes two independently
  htmx-loaded sections, each with its own heading and its own error/empty
  state — `Pipeline Outputs` (`hx-get="/browse/tree?root=pipeline"`, fires on
  page load) above `Corpus Docs` (`hx-get="/browse/tree?root=output"`, same
  load-on-page-open behavior that today's server-side include effectively
  provided). Both feed the same shared `#browse-doc` viewer pane.
- `partials/browse_tree_items.html`: threads `root` through its recursive
  `hx-get` links (folder-expand and file-select), so descending into a
  subfolder or opening a file preserves which root it came from.
- `partials/browse_file.html`: unchanged — it already renders whatever
  `render_md_file` returns, regardless of which root or which special-case
  path produced the file being viewed.

### 7. Error handling

- Reuses `PathSafetyError`, `FolderReadError`, and the 5MB oversize cap
  exactly as they exist today for all ordinary tree/file navigation.
- New failure mode, handled explicitly (not a 500): a pointer references a
  deleted or out-of-bounds target — surfaces as "Grounding pointer could not
  be resolved." in the viewer pane (§4).
- New empty state, handled explicitly: `runs/` doesn't exist yet — "No
  pipeline runs yet." in the Pipeline Outputs section (§2).

## Testing

- `test_browse_service.py`: `root_path()` for both known roots and the
  unknown-root error; `list_children`'s numeric version-sort fix (`v2` before
  `v10`); `raw_output.md` exclusion; the grounding pointer → synthetic entry
  logic (present pointer, missing pointer, pointer target deleted) at both
  the `_has_md_below` (parent-filter) and `list_children` (entry-generation)
  layers.
- `test_routes_browse.py`: `root=pipeline` end-to-end for tree and file
  routes, including the `pointer.yaml`-resolution path — both the success
  case and the containment-violation/missing-target error case; confirm
  `root=output` behavior is byte-identical to pre-change responses; confirm
  the "no `runs/` folder" empty state.

## Risks / open questions

None blocking. Worth calling out: pipeline-outputs browsing is filesystem-driven
first, DB-annotated second — consistent with how `output/` already works, and
means an orphaned `runs/` folder (DB row deleted, folder left behind) still
shows up rather than silently vanishing.

## Revision history

- **2026-07-30, initial draft → Opus review → this revision.** An Opus-model
  review caught three implementability bugs in the initial draft, all fixed
  above: (1) the grounding synthetic-entry logic was placed one level too
  deep to ever fire, since the parent folder's `.md`-only filter hides
  `00-grounding` first — fixed by extending `_has_md_below` itself (§3); (2)
  the proposed "third internal-only root" for `rgs-briefs/` resolution
  double-prefixed the path, since `pointer.yaml` already stores a
  repo-root-relative path — fixed by resolving directly under `repo_root`
  with an explicit containment check (§4); (3) the original `pointer:`
  synthetic rel_path scheme was asserted safe on the basis of being
  "server-generated" without actually validating that a client-supplied query
  string couldn't smuggle a traversal payload through it — fixed by not
  introducing that scheme at all, instead treating `pointer.yaml` as a real,
  already-safely-contained file and moving the actual new trust boundary
  (YAML-sourced target path) to one explicit, tested containment check (§4).
  The review also corrected a misattribution (the version-sort bug is in
  `browse_service.list_children`, not `artifacts._versions_in`, which was
  already correct) and identified two gaps (no existing `run_id`-keyed DB
  lookup — resolved by reusing `list_projects()`, §5; `raw_output.md` was
  unaccounted for — resolved by explicit exclusion, §3).
