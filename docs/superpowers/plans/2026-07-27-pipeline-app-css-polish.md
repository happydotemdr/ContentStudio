# Pipeline App CSS Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the visual clarity/legibility problems an Opus CSS review found in `pipeline-app`'s single stylesheet, without adding a CSS framework, variables system, JS, or any new file.

**Architecture:** Every task is a small, additive change to the single existing `pipeline_app/static/style.css` (currently 33 lines; this plan adds roughly 25 more, split across 5 tasks). No template changes except where a template currently has zero styled hooks for content it renders.

**Tech Stack:** Plain CSS, Jinja2 templates, no build step.

## Global Constraints

- One file: `pipeline_app/static/style.css`. No new stylesheets, no CSS variables, no preprocessor, no JS, no framework.
- This app has no automated visual/CSS regression tests. Each task's verification step is a manual check against the running dev server via the Browser tools (`preview_start`/`navigate`/`get_page_text`/`read_page`), the same way CSS work was verified earlier in this project — not a gap to fill with new test infrastructure, since that would itself add the complexity this plan is explicitly avoiding.
- Every task must restart the dev server before verifying (Python/Jinja2/static files are not hot-reloaded by the existing `.claude/launch.json` config) — find the PID listening on port 8420 and stop it, then `preview_start` with `{"name": "pipeline-app"}` again.
- Keep every rule's intent obvious from reading it top to bottom — this is the explicit bar the review was told to hold itself to, and it holds for implementation too.

---

## File Structure

| File | Responsibility in this plan |
|---|---|
| `pipeline_app/static/style.css` | Every change in this plan. |

No other file is created or modified.

---

### Task 1: Wrap long artifact bodies instead of overflowing the page

**Files:**
- Modify: `pipeline-app/pipeline_app/static/style.css`

**Interfaces:** none (pure CSS).

Every real artifact body (grounding briefs, concept briefs, scripts) is rendered into a bare `<pre>` in `stage.html` with zero CSS. Browser default `white-space: pre` means one long unwrapped markdown line stretches the box past the viewport, and nothing caps `<main>`, so the whole page gains a horizontal scrollbar and the header/sidebar scroll off-screen with it.

- [ ] **Step 1: Confirm the current broken state**

Restart the dev server (find and stop whatever's listening on port 8420, then `preview_start` with `{"name": "pipeline-app"}`), navigate to a stage page with a real artifact body (e.g. `/projects/1/stages/grounding` if the project used during the earlier debugging session is still on disk, or any stage with a written artifact), and confirm via `read_page` or a screenshot that the page scrolls horizontally / the `<pre>` block overflows its container.

- [ ] **Step 2: Implement**

In `pipeline-app/pipeline_app/static/style.css`, add at the end of the file:

```css
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-width: 70ch;
  line-height: 1.5;
  background: #f6f6f6;
  padding: 0.75rem;
  border-radius: 0.25rem;
}
```

- [ ] **Step 3: Verify**

Restart the dev server, reload the same stage page, and confirm via `read_page`/screenshot that the artifact body now wraps within its box, the page has no horizontal scrollbar, and the header/sidebar stay visible.

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/pipeline_app/static/style.css
git commit -m "style(pipeline-app): wrap long artifact bodies instead of overflowing the page"
```

---

### Task 2: Fix `.status` badge padding bleeding into adjacent lines

**Files:**
- Modify: `pipeline-app/pipeline_app/static/style.css`

**Interfaces:** none (pure CSS).

`.status` (line 2 of the current stylesheet) sets `padding: 0.1rem 0.5rem` on an element that's inline by default (it's a `<span>` in `partials/sidebar.html`). Vertical padding on a non-replaced inline box doesn't grow the line box, so the tinted background overlaps the `.specialist` sub-line directly below it in the sidebar for voiceover/visual.

- [ ] **Step 1: Confirm the current broken state**

Restart the dev server, navigate to a project's home page or any stage page for a project whose pipeline includes the voiceover/visual pair (any project on the real `pipeline.yaml`), and zoom into the sidebar around the voiceover/visual entries to confirm the status badge's background visually overlaps the `↪ elevenlabs-audio` / `↪ midjourney-prompting` line beneath it.

- [ ] **Step 2: Implement**

In `pipeline-app/pipeline_app/static/style.css`, change:

```css
.status { padding: 0.1rem 0.5rem; border-radius: 0.25rem; font-size: 0.85rem; }
```

to:

```css
.status { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 0.25rem; font-size: 0.85rem; }
```

- [ ] **Step 3: Verify**

Restart the dev server, reload the same page, zoom into the same sidebar region, and confirm the badge's background no longer overlaps the specialist line.

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/pipeline_app/static/style.css
git commit -m "style(pipeline-app): status badge no longer bleeds into the line below it"
```

---

### Task 3: Stop the current stage's box shifting relative to its parallel sibling

**Files:**
- Modify: `pipeline-app/pipeline_app/static/style.css`

**Interfaces:** none (pure CSS).

`.pipeline-stage.current` (current lines 26-31) applies a left border and padding only to the *current* stage. Inside a `.pipeline-step-group` flex row (the voiceover/visual pair), its non-current sibling has no border/padding at all, so the current stage's text sits visibly offset from its sibling, and the row jumps as you navigate between the two.

- [ ] **Step 1: Confirm the current broken state**

Restart the dev server, navigate to `/projects/{id}/stages/voiceover` and then `/projects/{id}/stages/visual` for a project with both stages present, and confirm via screenshot/zoom that the current stage's label is visibly offset from its sibling's label in the sidebar (compare the two navigations side by side).

- [ ] **Step 2: Implement**

In `pipeline-app/pipeline_app/static/style.css`, change:

```css
.pipeline-stage.current {
  border-left: 3px solid #2b6fd1;
  background: #eef4fd;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
}
```

to:

```css
.pipeline-stage {
  border-left: 3px solid transparent;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
}
.pipeline-stage.current {
  border-left-color: #2b6fd1;
  background: #eef4fd;
}
```

- [ ] **Step 3: Verify**

Restart the dev server, repeat the same two navigations, and confirm both stages in the pair now occupy the same box geometry — only the border color and background change between current and non-current.

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/pipeline_app/static/style.css
git commit -m "style(pipeline-app): give every pipeline-stage the same box so the current one doesn't shift its row"
```

---

### Task 4: Fix textarea sizing (too small in chat, too wide in skill editor)

**Files:**
- Modify: `pipeline-app/pipeline_app/static/style.css`

**Interfaces:** none (pure CSS).

`stage.html`'s chat composer `<textarea>` has no `rows`/`cols`, so it renders at the browser default (~2 rows × 20 cols) — unusably small for a real message. `skill_editor.html`'s two textareas hardcode `cols="100"`, wider than most windows, forcing page-level horizontal scroll. A CSS `width: 100%` overrides both HTML-attribute-driven sizings without touching either template.

- [ ] **Step 1: Confirm the current broken state**

Restart the dev server, navigate to any stage page and confirm the chat textarea is small relative to the page; navigate to `/skills/{any-skill-name}` and confirm the page has a horizontal scrollbar caused by the `cols="100"` textareas.

- [ ] **Step 2: Implement**

In `pipeline-app/pipeline_app/static/style.css`, add at the end of the file:

```css
textarea {
  width: 100%;
  box-sizing: border-box;
  min-height: 5rem;
}
```

- [ ] **Step 3: Verify**

Restart the dev server, reload both pages, and confirm: the chat textarea now spans the content column at a readable height, and the skill editor page no longer scrolls horizontally.

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/pipeline_app/static/style.css
git commit -m "style(pipeline-app): size textareas to their container instead of browser defaults / hardcoded cols"
```

---

### Task 5: Basic styling for currently-unstyled templates

**Files:**
- Modify: `pipeline-app/pipeline_app/static/style.css`

**Interfaces:** none (pure CSS).

`doctor.html`, `skill_list.html`, `skill_editor.html`, and `project_list.html` use no styled classes at all. `inspector.html` has two orphaned hooks: `.error` (rendered on a failed inspect) is plain black text, indistinguishable from body copy, and its frontmatter `<table>` has default zero cell padding so keys and values run together. `stage.html`'s `.input-panel`/`.chat-panel`/`.output-panel` are class hooks with no rules at all, so the three sections read as one continuous, unseparated column.

- [ ] **Step 1: Confirm the current broken state**

Restart the dev server, navigate to `/doctor`, a stage page, and (if reachable) `/inspector` with a `path` that triggers `error` — confirm via screenshot/`get_page_text` that these render as unstyled default HTML with no visual separation between sections, and that an inspector error message doesn't stand out from body text.

- [ ] **Step 2: Implement**

In `pipeline-app/pipeline_app/static/style.css`, change the first line:

```css
body { font-family: system-ui, sans-serif; margin: 2rem; }
```

to:

```css
body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }
```

Then add at the end of the file:

```css
header { margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #ddd; }
button { padding: 0.35rem 0.75rem; cursor: pointer; }
table { border-collapse: collapse; }
th, td { text-align: left; padding: 0.25rem 0.75rem 0.25rem 0; vertical-align: top; }
.error { color: #a00; }
.input-panel, .chat-panel, .output-panel { margin-bottom: 1.5rem; }
```

- [ ] **Step 3: Verify**

Restart the dev server, reload `/doctor`, a stage page, and the inspector's error case, and confirm: the header is visually separated from the page body, buttons have visible padding, the frontmatter table's cells are readable, an inspector error stands out in a distinct color, and a stage page's Input/Chat/Output sections have clear vertical separation.

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/pipeline_app/static/style.css
git commit -m "style(pipeline-app): basic styling for header, buttons, tables, error text, and stage-page section spacing"
```

---

### Task 6: Distinguish `no_artifact` from `stale`

**Files:**
- Modify: `pipeline-app/pipeline_app/static/style.css`

**Interfaces:** none (pure CSS).

`.status-stale` and `.status-no_artifact` are both `#ffb3b3`. `stale` means approved work was invalidated and needs regenerating; `no_artifact` means a turn ran and simply didn't write a file — a routine, expected outcome of a working conversation (the AI answered a question instead of producing output), not a failure. Colouring both alarm-red overstates one and buries the other, and after the handoff-hardening plan's Task 11 (transitive staleness), `stale` can legitimately cascade across four stages at once — the distinction matters more, not less.

The fix is a neutral background plus a dashed border. A plain neutral alone isn't enough: `locked` already owns `#ddd`, and `locked` (blocked on an upstream approval) and `no_artifact` (actionable right now — just send another message) must not read the same either. The dashed outline is the "empty placeholder" convention and is the only bordered badge in the stylesheet, so it stays unambiguous at badge size. `.status` is `display: inline-block` after Task 2, so the extra 1px border cannot bleed into adjacent lines.

- [ ] **Step 1: Confirm the current broken state**

Restart the dev server (find and stop whatever's listening on port 8420, then `preview_start` with `{"name": "pipeline-app"}`). To get both badges on screen at once, temporarily set two stages of an existing project to the two statuses in the dev database:

```bash
cd pipeline-app && python -c "import sqlite3; c=sqlite3.connect('pipeline.db'); print(c.execute('SELECT id, project_id, stage_id, status FROM stages').fetchall())"
```

Pick two stage row ids from that output and set them (substitute the real ids for `<A>`/`<B>`):

```bash
cd pipeline-app && python -c "import sqlite3; c=sqlite3.connect('pipeline.db'); c.execute(\"UPDATE stages SET status='stale' WHERE id=<A>\"); c.execute(\"UPDATE stages SET status='no_artifact' WHERE id=<B>\"); c.commit()"
```

Navigate to that project's page and confirm via screenshot/zoom that the two badges are visually identical, and that neither is distinguishable from the other at a glance in the sidebar. Record the two original status values from the first command so Step 3 can restore them.

- [ ] **Step 2: Implement**

In `pipeline-app/pipeline_app/static/style.css`, change:

```css
.status-no_artifact { background: #ffb3b3; }
```

to:

```css
.status-no_artifact { background: #eee; border: 1px dashed #999; }
```

- [ ] **Step 3: Verify, then restore the stage statuses**

Restart the dev server, reload the same project page, and confirm via screenshot/zoom that: the `stale` badge is still the red `#ffb3b3`, the `no_artifact` badge is now a neutral grey chip with a dashed outline, it is clearly distinguishable from both the `stale` red and the solid `locked` grey, and the dashed border has not shifted the badge's baseline or overlapped the `.specialist` line beneath it.

Then restore both rows to the statuses recorded in Step 1 (same `python -c` UPDATE form) and reload once more to confirm the project is back to its real state.

- [ ] **Step 4: Commit**

```bash
git add pipeline-app/pipeline_app/static/style.css
git commit -m "style(pipeline-app): distinguish no_artifact from stale instead of sharing one alarm-red badge"
```
