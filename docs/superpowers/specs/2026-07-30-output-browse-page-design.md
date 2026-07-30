# Browse page for output/ — design

Date: 2026-07-30
Status: revised after Opus review — closes all findings from the 2026-07-30 review pass
Revision note: v1 of this spec described `pipeline-app`'s template structure (a
`partials/header.html` with a nav list, a two-pane `<aside>`/`<main>` shell) that
belongs to `main`, not to this worktree's branch (`claude/cyberpunk-theme-layout-64289e`).
That branch is mid-refactor: it deleted `partials/header.html` and stripped `base.html`
down to a bare `<header><a href="/">ContentStudio Pipeline</a></header>` with no nav at
all. Every section below is written against the actual current state of this worktree.

## Problem

`output/` (the downloaded 420-video corpus + related brand-intel/thinkers/youth-sports
material) holds 553 `.md` files across ~10 nested subfolders (plus 106 non-`.md` files —
`.txt`, `.json`, `.vtt`, `.csv`). The pipeline app already has an Inspector page
(`/inspector`) that renders one `.md` file's frontmatter + body, but only via manually
pasting a full absolute path — there's no way to see the folder structure or navigate it.

## Goal

A new page in `pipeline-app` where the user can:
- see the folder tree under `C:\Projects\ContentStudio\output` (and subfolders)
- navigate that tree
- see all `.md` files contained in any folder or subfolder
- select any `.md` file and read a properly formatted (frontmatter + rendered markdown)
  version of it

## Non-goals

- Editing or writing files (read-only)
- Browsing outside `output/` (Inspector already covers "any path on disk")
- Showing non-`.md` files (stay hidden, per above)
- Deep-linking / back-button support for tree-expansion or file-selection state (no
  `hx-push-url`). Browse state is ephemeral within a page load — reloading `/browse`
  always returns to the collapsed root view. This is a deliberate YAGNI call, not an
  oversight; add it later if it turns out to matter.
- Sanitizing rendered markdown output. `body_html | safe` (via `markdown.markdown`,
  no HTML sanitizer) is Inspector's existing, unchanged behavior — same risk profile
  (raw HTML/`<script>` in a `.md` file executes as-is), accepted under the same
  "single-user, 127.0.0.1-only local app" threat model Inspector already documents.
  Browse inherits this unchanged; it is not this spec's job to fix it.

## Placement

This worktree's `base.html` currently has **no nav list at all** — the whole
`partials/header.html`/top-nav that exists on `main` was removed here as part of an
in-progress theme change, leaving:

```html
<body>
  <header><a href="/">ContentStudio Pipeline</a></header>
  {% block sidebar %}{% include "partials/sidebar.html" %}{% endblock %}
  <main>{% block content %}{% endblock %}</main>
</body>
```

Rebuilding the full nav is out of scope for this spec. The minimal, scoped change:
add one link next to the existing wordmark link in `base.html`'s header —
`<a href="/browse">Browse</a>` — so the page is reachable. No new partial, no nav
list, no `active_nav` styling system (none of that infrastructure currently exists on
this branch). If the nav is rebuilt later as part of the theme work, this link moves
into it then.

Inspector is unchanged — it stays the freeform "paste an absolute path" power-user
tool; Browse is the point-and-click tree explorer scoped to `output/`.

## Architecture

New route module `pipeline_app/routes/browse.py`, registered in `main.py` next to the
other routers. New template `templates/browse.html` (extends `base.html`).

Layout: `{% block content %}` renders a single wrapper `<div class="browse-shell">`
containing two child `<div>`s — `.browse-tree` and `.browse-doc` — laid out side by
side via CSS (flex/grid in `static/style.css`). **Not** `<aside>`/`<main>`: `base.html`
already wraps `{% block content %}` in its own `<main>`, so nesting another `<main>`
inside it would be invalid HTML. `{% block sidebar %}` is left at its default
(`partials/sidebar.html`); that partial is guarded by `{% if nav %}` and Browse's route
handlers never set a `nav` context variable, so it silently renders nothing — no
override needed.

Reuses `markdown.markdown` for body rendering — same library call Inspector uses, so
markdown formatting looks identical between the two pages. Frontmatter parsing is
**not** reused as-is from `artifacts.parse_frontmatter`; see "Frontmatter parsing
hardening" below for why `browse.py` wraps it instead of calling it directly.

Three endpoints, all GET, all read-only, all returning **HTTP 200** even for the
error/empty cases described below (see "Why 200, not 400" below):

- `GET /browse` — full page. Renders the root folder's immediate children
  (pre-expanded one level) in `.browse-tree`; `.browse-doc` shows a "select a file to
  view" placeholder.
- `GET /browse/tree?path=<rel>` — htmx partial. Returns the child entries (folders,
  then `.md` files, both alphabetical) for one folder's immediate children, as a
  `<div class="children">...</div>` fragment. See "Tree expand/collapse mechanics"
  below for exactly how this is wired.
- `GET /browse/file?path=<rel>.md` — htmx partial. Returns the rendered frontmatter
  table + markdown body (or an error/oversize message), swapped into `#browse-doc`.

`base.html` already loads htmx 2.0 from a CDN (`unpkg.com`) site-wide for the existing
SSE chat forms, so no new script dependency is introduced. Unlike those chat forms
(which use a plain `<form>` that still works, degraded, without JS) and unlike
Inspector (a plain HTML `<form method="post">` that works with zero JS), **Browse's
tree and file panes are 100% htmx-driven** — if the CDN script fails to load, Browse
is entirely non-functional (no fallback links). This is a real, accepted limitation
given this is a local single-user app already depending on the same CDN for other
functionality; it is called out here explicitly rather than silently inherited.

### Why 200, not 400

htmx 2.x's default `responseHandling` config does **not** swap non-2xx responses into
the DOM — a 400 response body is simply discarded, which would make every error case
below silently do nothing (the exact "invisible failure" this design is trying to
avoid). Reconfiguring `htmx.config.responseHandling` site-wide is a bigger, unrelated
change (it'd affect the existing SSE chat forms' behavior too) and is out of scope.

Instead: every Browse endpoint always returns HTTP 200. The response body is either
the successful partial or an explicit error/empty-state partial (a `<div class="
browse-error">` or `<div class="browse-empty">` fragment) — htmx swaps it in either
way, so every failure is visibly rendered, never silently dropped.

## `path` parameter contract

Always a `/`-separated path **relative to `output/`** (e.g.
`thinkers/anchorandwave/plato.md`; `""` or absent for the root). Never an absolute or
OS-native path — this is the one place Browse's contract differs deliberately from
Inspector's (Inspector is intentionally an open "any absolute path" tool; Browse is
intentionally scoped and contained).

All paths emitted by the server (in `hx-get` URLs, in link targets) are built by
joining path segments with a literal `"/"` — never `str(some_path_object)`, which
would emit OS-native (backslash) separators on Windows. This matches the convention
already established elsewhere in this repo (see the recent fix: "resolver CLI prints
forward-slash paths, not OS-native separators").

## Path safety

```python
output_root = (repo_root / "output").resolve()

def resolve_under_output(rel_path: str) -> Path:
    # Fast-fail on the obviously-hostile forms before ever touching the
    # filesystem: an absolute path (leading "/" or "\", or a Windows drive
    # letter like "C:") would silently replace output_root on join instead
    # of extending it; ".." segments are rejected outright rather than
    # relying solely on resolve()+containment to catch every case.
    if not rel_path or rel_path in (".", "/"):
        rel_path = ""
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
    if any(p == ".." for p in parts):
        raise PathSafetyError("'..' is not allowed in path")
    if PureWindowsPath(rel_path).is_absolute() or PurePosixPath(rel_path).is_absolute():
        raise PathSafetyError("absolute paths are not allowed")

    candidate = (output_root / rel_path).resolve()
    if candidate != output_root and not candidate.is_relative_to(output_root):
        raise PathSafetyError("path escapes output/")
    return candidate
```

Key points the implementation must follow (each closes a specific gap):

- **Both sides of the containment check are resolved**: `output_root` is resolved
  once at startup/request time, the candidate is resolved fresh per request, and the
  comparison is `candidate.is_relative_to(output_root)` — never a string
  `startswith()` check, which would wrongly admit a sibling directory like
  `output-old/` (same prefix, different folder).
- **`..` segments and absolute-looking input are rejected before resolution**, not
  just caught after — defense in depth, and it produces a clearer error message than
  "path escapes output/" for the common accidental case.
- **Windows-specific absolute forms are checked explicitly**: a drive letter
  (`C:...`), a leading backslash, or a leading forward slash are all treated as
  absolute and rejected, since naively joining any of these onto `output_root` would
  silently discard `output_root` and target an unrelated location.
- **Symlinks are not followed, ever** — see "Folder listing logic" below; this
  removes both the symlink-escape concern and the symlink-loop concern in one rule
  (there are no symlinks in the downloaded corpus; supporting them is out of scope).
- Any `PathSafetyError` results in the standard error partial (200 OK, "Invalid
  path.") per "Why 200, not 400" above.

## Folder listing logic

For a given folder, list immediate directory entries via `os.scandir` (not
`os.walk`, to keep symlink handling explicit and local):

- **Skip any entry that is a symlink** (`entry.is_symlink()`), whether it's a file or
  a directory — no symlink support in v1, and this is what prevents a
  symlink-to-an-ancestor loop.
- Keep a subfolder in the listing only if `_has_md_below(subfolder)` is true, where
  `_has_md_below` does a manual, non-symlink-following recursive scan that **returns
  on the first match** (it's a generator-based walk, not a full-tree collection) —
  folders that are entirely non-`.md` (e.g. a raw-transcript `_work/` dir) are
  skipped entirely from the listing, not just their non-md files.
- `.md` matching is **case-insensitive** (`entry.name.lower().endswith(".md")`) —
  the corpus is consistently lowercase today, but the check doesn't assume that.
- If a folder is requested directly (e.g. a stale/typed-in URL) that itself has no
  `.md` files anywhere below it, that is **not an error** — it's a valid, empty
  result: the `.browse-tree` partial for that folder renders zero children with no
  special messaging (an empty folder is just an empty list, same as any other
  folder that happens to have no visible children).

Sort order: folders first, then `.md` files, each case-insensitive alphabetical.

553 files across ~10 subfolders is cheap enough that this listing is recomputed fresh
on every request — no caching.

## Frontmatter parsing hardening

`artifacts.parse_frontmatter` (used unchanged by Inspector) calls `yaml.safe_load`
with no exception handling, and returns whatever the YAML parses to without checking
it's a `dict`. Inspector has only ever been exercised against hand-authored fixtures,
where this has never mattered. Browse points at 553 files scraped from third-party
video transcripts, where a malformed `---`-delimited block or a non-mapping YAML
value (e.g. a bare list) is a realistic occurrence — and either would currently
produce a raw 500 (a `yaml.YAMLError` propagating uncaught, or a template-level
`AttributeError` when `inspector.html`-style code calls `.items()` on a non-dict).

Resolution (an open question from the review, resolved here): **`browse.py` adds its
own thin wrapper around `parse_frontmatter`, rather than changing
`artifacts.parse_frontmatter` or Inspector's behavior.** Inspector's behavior and
risk profile stay exactly as they are today — this is a Browse-local concern, not a
shared-module change:

```python
def render_md_file(text: str) -> dict:
    try:
        meta, body = artifacts.parse_frontmatter(text)
    except yaml.YAMLError:
        return {"error": "Frontmatter is not valid YAML."}
    if not isinstance(meta, dict):
        return {"error": "Frontmatter is not a key/value mapping."}
    return {"frontmatter": meta, "body_html": markdown.markdown(body)}
```

## File size cap

One corpus file (`thinkers/anchorandwave/adam-smith/smith-wealth-of-nations.cleaned.md`)
is 2.1 MB; seven more exceed 1 MB. Reading, parsing, and markdown-rendering a
multi-megabyte file inline on an htmx click with no loading indicator is a multi-second
UI hang that looks identical to a hung request.

- Files over **5 MB** (checked via `entry.stat().st_size` before reading, not after)
  render an explicit message instead of their content: "File too large to preview
  (X.X MB — cap is 5 MB). Open it directly at `<absolute path>`." This comfortably
  covers every file in the current corpus while still guarding against a future
  addition.
- Files under the cap (including the 2.1 MB one) still render fully, but the file-row
  link carries an `hx-indicator` targeting a small inline spinner next to
  `.browse-doc`, so a multi-second render reads as "loading," not "stuck."

## Tree expand/collapse mechanics

Each expandable folder row is a native `<details>` element; the folder name is its
`<summary>`. Children are fetched **once**, the first time a folder is opened, using
htmx's native support for this exact pattern:

```html
<details>
  <summary>thinkers</summary>
  <div class="children"
       hx-get="/browse/tree?path=thinkers"
       hx-trigger="toggle once"
       hx-target="find div.children"
       hx-swap="innerHTML"></div>
</details>
```

- `hx-trigger="toggle once"` fires exactly once, the first time `<details>` is
  opened (native browser behavior — no custom JS required).
- Every subsequent open/close of that `<details>` is handled entirely by the
  browser's native `<details>` behavior: no refetch, no visible flash, no server
  round-trip.
- `hx-target="find div.children"` scopes the swap to the triggering element's own
  child — **no path-derived DOM ids anywhere in the tree.** This is deliberate: two
  different folders in the corpus can each contain a `README.md`, and any id scheme
  built from filenames or relative paths risks collisions. Relative (`find`/
  `closest`) targeting sidesteps the whole problem instead of trying to make ids
  collision-proof.
- The file-render target is the one fixed, page-level `#browse-doc` element — no
  collision risk there since there's exactly one instance of it.
- File-row links add `hx-sync="#browse-doc:replace"` so that clicking a second file
  before the first one's response has arrived **aborts the in-flight request** and
  replaces it, rather than racing two responses into `#browse-doc` with
  last-writer-wins nondeterminism.

## Error handling

Every expected failure is an explicit UI partial, always returned as HTTP 200 (see
"Why 200, not 400"):

- `path` fails the safety check (`..` traversal, absolute-path override, resolves
  outside `output/`) → error partial: "Invalid path."
- requested folder doesn't exist (e.g. stale client-side tree state after an
  on-disk change, or the `output/` root itself missing — see "Development
  environment note" below) → error partial: "Folder not found."
- requested folder exists but has no `.md` files anywhere below it → empty result,
  not an error (see "Folder listing logic" above)
- `.md` file doesn't exist / unreadable / bad encoding → error partial, same wording
  style as Inspector's `Could not read file: {exc}`
- `.md` file's frontmatter fails to parse, or parses to a non-mapping → error
  partial per "Frontmatter parsing hardening" above
- `.md` file exceeds the 5 MB cap → oversize message per "File size cap" above

## Development environment note

`output/` is git-ignored and is **not present in this worktree** — it only exists in
the main checkout at `C:\Projects\ContentStudio\output`. `create_default_app()`
resolves `repo_root` from the package's own location, so running this worktree's app
as-is will hit a missing `output/` root on the very first `/browse` request. This is
expected, not a bug to fix here:

- The root-missing case is handled the same way as any other missing folder (see
  "Error handling" above) — the page loads, `.browse-tree` shows "Folder not found."
  instead of erroring out.
- For manual/browser verification during implementation, either run the app from the
  main checkout, or copy/symlink a representative `output/` subtree into this
  worktree before testing by hand. Automated tests are unaffected — they build a
  fake `output/` tree under `tmp_path` (see "Testing" below) and never touch the real
  corpus.

## Testing

New `tests/test_routes_browse.py`, following the existing per-route test file pattern
(e.g. `tests/test_routes_inspector.py`), using `create_app(repo_root=tmp_path, ...)`
with a fake `output/` tree built under `tmp_path` in fixtures (same isolation approach
the other route tests use — this never touches the real `output/` corpus or
`pipeline.db`):

- root listing returns the expected top-level folders, sorted folders-then-files
- a folder containing only non-`.md` files is excluded from its parent's listing
- a folder containing no `.md` files anywhere, requested directly, returns an empty
  (not error) result
- `output/` root itself missing → "Folder not found." partial, HTTP 200
- tree partial for a nested folder returns its immediate children correctly
- file partial renders frontmatter + body for a known fixture file
- `.MD` (uppercase extension) fixture file is both listed and renders correctly
- malformed-YAML frontmatter → "Frontmatter is not valid YAML." partial, HTTP 200,
  not a 500
- non-mapping frontmatter (e.g. a YAML list between the delimiters) → "Frontmatter is
  not a key/value mapping." partial, HTTP 200, not a 500
- a file over the 5 MB cap → oversize-message partial, file is never actually read
  into memory for rendering
- path-traversal attempts return the "Invalid path." partial, HTTP 200, and never
  read any file: `../../../etc`, a Windows drive-letter override (`C:/Windows`), a
  leading-backslash absolute path, and a sibling-prefix folder name (`output-old/...`)
  that a naive `startswith()` check would wrongly admit
- a symlinked file or directory under the fake `output/` tree is skipped from
  listings entirely (test guarded with a symlink-creation skip on platforms/
  permissions where creating one isn't possible, since Windows symlinks require
  admin rights or Developer Mode)
- rendered tree/file HTML contains the expected `hx-get`/`hx-trigger`/`hx-target`
  attributes with relative (`find`/`closest`) targeting, not path-derived ids
