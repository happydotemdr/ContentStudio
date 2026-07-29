# 90s cyberpunk/synthwave theme + layout redesign — design spec

Date: 2026-07-28
Status: Approved

## Problem

`pipeline-app`'s UI (`pipeline_app/static/style.css`, `pipeline_app/templates/`)
is presentation-only and minimal: system-ui sans-serif on white, an unstyled
`<body>` with no layout container, and a `<header>` that is just a link back
to `/`. Specifically:

- No page has a real layout — `base.html` stacks `<header>`, the sidebar
  partial, and `<main>` as plain flow elements with no flex/grid container,
  so content width is whatever the browser default is and the sidebar (where
  present) just sits above the content rather than beside it.
- The header carries no navigation. `/skills`, `/doctor`, and `/inspector`
  are reachable only by typing the URL — there's no way to get to them by
  clicking anywhere in the UI.
- The header is not visually consistent with anything else — no shared
  identity between pages beyond the repeated wordmark link.
- The palette (`#f6f6f6` panels, `#ddd` borders, pastel status pills) is
  generic light-mode default styling with no character.

The user wants a fun, edgy 90s-cyberpunk/synthwave feel, better use of
screen space, and a consistent header with working navigation — without
adding build tooling or complicating the codebase.

## Goals

- Dark synthwave visual theme (neon magenta/cyan/purple accents on a
  near-black navy background), applied via CSS custom properties so the
  palette lives in one place.
- A real page shell: fixed-width sidebar + content column with a sensible
  `max-width` (not full-bleed), replacing the current unstyled stack.
- One shared header, present on every page, containing:
  - the "ContentStudio" wordmark (links home)
  - top-level nav links: Projects, Skills, Doctor, Inspector, with the
    current page visually marked active
  - breadcrumb-lite context on stage pages (`run_id / stage_id`)
  - a small status dot reflecting Claude CLI availability (reuses the
    `cli.available` value the `/doctor` route already computes)
- Keep it CSS-only plus the minimal template/context changes needed to wire
  up the header (no build step, no JS framework, no new dependencies).

## Non-goals

- No new pages, routes, or behavior changes. This is presentation only.
- No animation beyond simple CSS `:hover`/`:focus` transitions already
  implied by "polish" — no scanline/CRT effects, no animated backgrounds.
- No change to the pipeline nav's *ordering logic* (established in
  `2026-07-27-pipeline-nav-redesign-design.md`) — only its visual styling.
- No responsive/mobile-specific layout work — this is a local dev tool used
  at desktop widths.

## Design

### 1. Palette & typography (CSS custom properties)

Add a `:root` block to `style.css` with the theme as variables:

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
```

Body copy keeps `system-ui` (readability for transcripts/generated prose);
headings, nav, buttons, status pills, and the header wordmark switch to
`var(--font-mono)` for the terminal/cyberpunk feel. This is the same
restraint principle already used by the corpus/skills docs in this repo:
flavor on structural chrome, plain and legible on content.

Base font size increases from the browser default (16px) to `18px` on `body`,
for readability — the current UI has no explicit `font-size` anywhere, so
this is a net-new baseline rather than an override. `pre`/code blocks get
`1rem` (matching the new 18px base) instead of typically-smaller monospace
defaults, so transcript/script output is easy to read at a glance.

`pre` blocks (script/prompt output) get `background: var(--bg-panel)`,
`border: 1px solid var(--border)`, `color: var(--text)` — dark-mode versions
of what they already do, no new behavior.

### 2. Page shell (`base.html` + `style.css`)

Wrap the sidebar + main content in a flex container so they sit side by
side:

```html
<body>
  {% include "partials/header.html" %}
  <div class="app-shell">
    <aside class="app-sidebar">{% block sidebar %}{% include "partials/sidebar.html" %}{% endblock %}</aside>
    <main class="app-main">{% block content %}{% endblock %}</main>
  </div>
</body>
```

```css
.app-shell { display: flex; gap: 2rem; align-items: flex-start; }
.app-sidebar { flex: 0 0 260px; }
.app-main { flex: 1 1 auto; min-width: 0; max-width: 1400px; }
```

Pages with no `nav` context (Skills, Doctor, Inspector) render an empty
`<aside>` — the existing `{% if nav %}` guard in `sidebar.html` already
handles that; `app-sidebar` just collapses visually via its own padding
being conditional on content (no JS needed, empty aside takes no visible
space beyond the flex gap — acceptable, matches "don't overcomplicate").

### 3. Shared header (new `partials/header.html`)

Extracted out of `base.html` into its own partial so it's obviously "the one
header, everywhere" rather than inline markup easy to drift from:

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

- `active_nav` — a plain string each route already implicitly knows
  (`"projects"`, `"skills"`, `"doctor"`, `"inspector"`) passed into the
  template context alongside existing variables. Every route in
  `routes/*.py` that calls `templates.TemplateResponse(...)` gets one added
  key; no new logic, just a literal.
- `cli_available` — `routes/doctor.py` already calls
  `preflight.check_cli_available()` per-request to build its `cli` context
  value. CLI availability doesn't change while the server is running, and
  `main.py`'s `create_app()` already computes one such startup-time value
  the same way (`app.state.orphaned_count`, via `preflight.reconcile_orphaned_turns`).
  Follow that existing pattern: call `check_cli_available()` once in
  `create_app()` and store `app.state.cli_available = check_cli_available().available`.
  Every route adds one line to its context dict:
  `"cli_available": request.app.state.cli_available`. `doctor.html` keeps
  using its own per-request `cli` value (unchanged) since it also needs
  `cli.path`/`cli.error` for diagnostics — the header's dot is a coarser,
  cached signal, not a replacement for the Doctor page's live check.
- Decorative grid-horizon strip: a `background-image` CSS gradient (a few
  faint repeating linear-gradient lines) on `.site-header` only — no SVG
  asset, no image file, pure CSS so it stays a one-place, zero-dependency
  change.

```css
.site-header {
  display: flex; align-items: center; gap: 1.5rem;
  padding: 0.75rem 1.5rem;
  background: linear-gradient(var(--bg-panel), var(--bg-panel)),
              repeating-linear-gradient(transparent 0 7px, var(--accent-purple) 7px 8px);
  background-blend-mode: normal, screen;
  border-bottom: 2px solid var(--accent-magenta);
  box-shadow: 0 0 12px var(--accent-magenta);
}
.wordmark { font-family: var(--font-mono); color: var(--accent-cyan); text-shadow: 0 0 6px var(--accent-cyan); text-decoration: none; font-weight: bold; }
.top-nav a { color: var(--text-dim); text-decoration: none; margin-right: 1rem; font-family: var(--font-mono); }
.top-nav a.active { color: var(--accent-magenta); text-shadow: 0 0 4px var(--accent-magenta); }
.status-dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; margin-right: 0.35rem; }
.status-dot.online { background: var(--accent-green); box-shadow: 0 0 6px var(--accent-green); }
.status-dot.offline { background: #ff4444; box-shadow: 0 0 6px #ff4444; }
```

### 4. Existing color-bearing elements

Update in place, no structural change:

- `.status-*` pills (`.status-locked`, `.status-ready`, `.status-running`,
  `.status-awaiting_review`, `.status-approved`, `.status-stale`,
  `.status-no_artifact`) — remap their `background` values to
  dark-theme-appropriate translucent accent colors (e.g.
  `background: color-mix(in srgb, var(--accent-cyan) 20%, transparent)`  for
  `ready`, etc.), keep them a distinct family from each other as they are
  today.
- `button` — dark panel background, accent-magenta border, hover glow
  (`box-shadow` on `:hover`), matches the terminal-button aesthetic without
  new markup.
- `.pipeline-step` / `.pipeline-stage.current` — swap the current
  blue-highlight (`#2b6fd1`/`#eef4fd`) for `var(--accent-cyan)` border-left +
  translucent cyan background, consistent with the new palette.
- `.error` — switch to a legible bright red/orange on dark bg
  (`#ff5f5f`) instead of the current `#a00` (too dark to read on the new
  background).

### 5. Files touched

- `pipeline_app/static/style.css` — palette variables + all rule updates
  above (the only place theme colors live).
- `pipeline_app/templates/base.html` — shell wrapper markup, extract header
  into partial.
- `pipeline_app/templates/partials/header.html` — new, shared header.
- `pipeline_app/templates/partials/sidebar.html` — no structural change
  (already guarded by `{% if nav %}`); may pick up new classes if needed
  for spacing inside `.app-sidebar`.
- Each `routes/*.py` handler rendering a `base.html`-derived template —
  add `active_nav` (and `cli_available`, however it ends up wired) to the
  template context dict it already builds.

No changes to `pipeline_app/db.py`, `state_machine.py`, `pipeline.yaml`, or
any route's actual logic/response shape beyond the added template-context
keys.

## Testing

Presentation-only change with no new routes or business logic — existing
route/unit tests (`tests/test_routes_*.py`) should continue to pass
unmodified as long as added context keys don't break template rendering.
Manually verify in-browser: header nav links work and mark the active page,
status dot reflects CLI availability, sidebar+content sit side by side, long
`pre` content stays legible against the dark background, and no page
regresses past `max-width: 1400px` on a wide viewport.
