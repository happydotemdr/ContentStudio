# Browse page for output/ — design

Date: 2026-07-30
Status: approved, ready for implementation plan

## Problem

`output/` (the downloaded 420-video corpus + related brand-intel/thinkers/youth-sports
material) holds 553 `.md` files across ~10 nested subfolders. The pipeline app already
has an Inspector page (`/inspector`) that renders one `.md` file's frontmatter + body,
but only via manually pasting a full path — there's no way to see the folder structure
or navigate it.

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
- Showing non-`.md` files (`.txt`, `.json`, `.vtt`, `.csv` — 106 files total — stay hidden)

## Placement

New standalone nav item, **"Browse"**, added to `partials/header.html` alongside
Projects/Skills/Doctor/Inspector. Inspector is unchanged — it stays the freeform
"paste an absolute path" power-user tool; Browse is the point-and-click tree explorer
scoped to `output/`.

## Architecture

New route module `pipeline_app/routes/browse.py`, registered in `main.py` next to the
other routers. New template `templates/browse.html` (extends `base.html`, two-pane
layout: `<aside>` tree / `<main>` rendered doc). Reuses `artifacts.parse_frontmatter`
and `markdown.markdown` — the same rendering path Inspector already uses, so a file
looks identical whether opened from Inspector or Browse.

Three endpoints, all GET, all read-only:

- `GET /browse` — full page. Renders the root folder's immediate children
  (pre-expanded one level) in the sidebar; main pane shows a "select a file to view"
  placeholder.
- `GET /browse/tree?path=<rel>` — htmx partial. Returns the `<li>` entries (folders,
  then `.md` files, both alphabetical) for one folder's immediate children. Wired to a
  folder row's click via `hx-get`, swapped into a child `<ul>` under that row. A second
  click on an already-expanded folder toggles the existing `<ul>` hidden client-side
  (no refetch) rather than removing it from the DOM.
- `GET /browse/file?path=<rel>.md` — htmx partial. Returns the rendered frontmatter
  table + markdown body, swapped into the main pane via `hx-get` on the file row's
  click.

`base.html` already loads htmx 2.0 site-wide, so no new script dependency.

## `path` parameter contract

Always a `/`-separated path **relative to `output/`** (e.g.
`thinkers/anchorandwave/plato.md`; `""` for the root). Never an absolute or
OS-native path — this is the one place Browse's contract differs deliberately from
Inspector's (Inspector is intentionally an open "any absolute path" tool; Browse is
intentionally scoped and contained).

## Path safety

Every incoming `path` is joined onto `repo_root / "output"`, resolved with
`Path.resolve()`, and checked to still be inside `output/` before any filesystem read.
A `path` that resolves outside (`../../..`, an absolute-path override, a symlink
escape) returns HTTP 400 with an explicit error partial — never a raw 500, never a
silent traversal.

## Folder listing logic

For a given folder, list immediate children. Keep a subfolder in the listing only if
it contains at least one `.md` file anywhere in its subtree — folders that are
entirely non-`.md` (e.g. a raw-transcript `_work/` dir) are skipped entirely, not just
their non-md files. This is a plain `os.walk`-style check per subfolder, done fresh on
every request (553 files is cheap; no caching needed).

Sort order: folders first, then `.md` files, each alphabetical.

## Error handling

Mirrors Inspector's existing pattern — every expected failure is an explicit UI error
state, never a raw 500:

- `path` resolves outside `output/` → 400 + error partial: "Invalid path."
- folder doesn't exist (e.g. stale client-side tree state after an on-disk change) →
  error partial: "Folder not found."
- `.md` file doesn't exist / unreadable / bad encoding → error partial, same wording
  style as Inspector's `Could not read file: {exc}`

## Testing

New `tests/test_routes_browse.py`, following the existing per-route test file pattern
(e.g. `tests/test_routes_inspector.py`), using a fake `output/` tree under `tmp_path`
(same isolation approach the other route tests use, so this never touches the real
`output/` corpus or `pipeline.db`):

- root listing returns the expected top-level folders
- a folder containing only non-`.md` files is excluded from its parent's listing
- tree partial for a nested folder returns its immediate children correctly
- file partial renders frontmatter + body for a known fixture file
- path-traversal attempts (`../../../etc`, an absolute-path override) return 400 and
  never read any file
