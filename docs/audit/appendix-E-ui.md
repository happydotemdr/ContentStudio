# Appendix E — User Interface

## T13 — UI/UX quick pass

**Scope.** This section audits presentation and information architecture only: the 15 Jinja
templates under `pipeline-app/pipeline_app/templates/`, `pipeline_app/static/style.css`,
`pipeline_app/browse_service.py`, and the four page routes owned here (`routes/projects.py`,
`routes/browse.py`, `routes/inspector.py`, `routes/doctor.py`). `routes/stages.py`,
`routes/discovery.py` and `routes/skills.py` were read as evidence for what the templates
receive and what a form POST actually returns, but their behavior is **not** owned here — the
behavioral half of each such finding is handed off. `base.html`'s CDN `<script>` line and the
`| safe` autoescape question belong to T12 and are deliberately not touched; the layout and
information architecture of `base.html`'s shell are covered. Documentation only; nothing was
changed. Findings extend the confirmed seed SEED-15 rather than re-deriving it.

The user's framing was that the UI "has gotten a little unwieldy as we've added pieces
together." That is the correct diagnosis and it is structural: the app has one deep hierarchy
(project → stage) and one flat subsystem (discovery), and the top nav renders both as the same
kind of thing at the same rank, alongside four utility pages. The consolidated IA in §2 is the
main deliverable. The more serious defects, though, are not navigational: on a stage page a
**gate that never ran is completely invisible**, and a **successfully completed turn leaves the
Output and Gates panels showing the previous state with no cue to reload** (E-01, E-02, E-03).

---

## 1. Route + template inventory

15 templates (11 pages, 4 partials). 20 routes across 7 routers.

| Route | Method | Router:line | Renders | Notes |
|---|---|---|---|---|
| `/` | GET | `projects.py:11` | `project_list.html` | Project list + create form |
| `/projects` | POST | `projects.py:25` | 303 → project home; **400 `PlainTextResponse`** on bad slug | E-04 |
| `/projects/{id}` | GET | `projects.py:39` | `project_home.html` | 4-line shell; body is one `<h1>` (E-08) |
| `/projects/{id}/stages/{sid}` | GET | `stages.py:62` | `stage.html` | The main work surface |
| `…/stages/{sid}/chat` | POST | `stages.py:129` | SSE stream; **409 plain text** if locked/running | Only path with a real client-side error branch (`base.html:44-50`) |
| `…/stages/{sid}/approve` | POST | `stages.py:204` | 303 → stage; **409 plain text** on gate block | E-03, E-04 |
| `…/stages/{sid}/edit` | POST | `stages.py:229` | 303 → stage; **409 plain text** | **No template posts to this route** (E-07) |
| `/discovery/handles` | GET | `discovery.py:25` | `discovery_handles.html` | 85 lines: table + add form + run-now + schedule |
| `/discovery/handles` | POST | `discovery.py:39` | 303; **400 plain text** on duplicate/slug clash | E-04 |
| `/discovery/handles/{id}/toggle` | POST | `discovery.py:73` | 303 | Silent no-op if id unknown |
| `/discovery/handles/{id}/status` | GET | `discovery.py:82` | JSON | Polled by inline script (E-12) |
| `/discovery/run-now` | POST | `discovery.py:91` | 303 → `/discovery/runs` | Fire-and-forget `Popen` (E-11) |
| `/discovery/run-now-backfill` | POST | `discovery.py:97` | 303 → `/discovery/runs` | Same (E-11) |
| `/discovery/settings` | POST | `discovery.py:105` | 303 → handles | No confirmation |
| `/discovery/runs` | GET | `discovery.py:112` | `discovery_runs.html` | 24 lines; unbounded list (`db.py:266-267`) |
| `/skills` | GET | `skills.py:28` | `skill_list.html` | 9 lines, bare `<ul>` |
| `/skills/{name}` | GET | `skills.py:42` | `skill_editor.html` | Phantom second editor on 5 of 13 skills (E-15) |
| `/skills/{name}/save` | POST | `skills.py:77` | 303 → editor | No confirmation; silent no-op on unknown `target` |
| `/inspector` | GET/POST | `inspector.py:11,19` | `inspector.html` | Open any `.md` by absolute path |
| `/doctor` | GET | `doctor.py:8` | `doctor.html` | 11 lines, static (E-16) |
| `/browse` | GET | `browse.py:38` | `browse.html` | Two-root tree + doc pane |
| `/browse/tree` | GET | `browse.py:49` | `partials/browse_tree_items.html` | htmx, no error path (E-13) |
| `/browse/file` | GET | `browse.py:58` | `partials/browse_file.html` | htmx, no error path (E-13) |

Template roles: `base.html` (shell — header + always-rendered `<aside>` + `<main>`),
`partials/header.html` (7-link top nav + CLI dot), `partials/sidebar.html` (stage rail; no-ops
when `nav` is undefined), `partials/browse_tree_items.html` and `partials/browse_file.html`
(htmx swap fragments).

---

## 2. Proposed consolidated IA (Q1)

The defensible shape is **three top-level sections, not seven**. Projects is a hierarchy;
Discovery is a subsystem with three co-equal views; everything else is a utility drawer that
should not compete with either for nav rank.

```
ContentStudio                                   [CLI: online/offline]  ← header, unchanged
│
├─ Projects                       /
│  ├─ (list + create)                            ← add per-project status summary + "next action"
│  └─ <run-id> (brand)            /projects/{id}
│     ├─ Overview                                ← currently an empty page; make it the real
│     │                                            project home: stage rail + gate roll-up +
│     │                                            "which stage needs you now"
│     └─ Stage: <stage-id>        /projects/{id}/stages/{stage}
│        ├─ Status strip          ← status pill · artifact vN · generated-at · gate verdict
│        ├─ Input                 ← per-upstream card: stage, version, present/missing
│        ├─ Chat
│        └─ Output                ← gates ABOVE the body; approve/edit/override live here
│
├─ Discovery                      /discovery      ← ONE nav entry, tabbed inside
│  ├─ Sources                     /discovery/handles     (table + add form only)
│  ├─ Runs                        /discovery/runs        (history + live run banner)
│  └─ Schedule                    /discovery/schedule    (split out of the handles page)
│
└─ Library                        /library         ← ONE nav entry, tabbed inside
   ├─ Files                       /browse          (corpus + pipeline outputs; absorbs
   │                                                Inspector as an "open by path" field)
   ├─ Skills                      /skills
   └─ System                      /doctor          (CLI, DB, topology, startup migrations)
```

Three changes carry most of the benefit:

1. **Collapse the two Discovery links into one section with tabs.** Handles and Runs are two
   views of one subsystem; ranking them as siblings of Projects implies they are peers of the
   entire production pipeline. Move the Schedule block off the handles page while doing it —
   at 85 lines that template is already four unrelated surfaces stacked vertically.
2. **Demote Skills / Doctor / Inspector / Browse into one "Library" section.** These are
   reference and maintenance surfaces used occasionally; four of the seven top-level slots is
   backwards. Inspector and Browse overlap enough (both render an `.md` with frontmatter) that
   Inspector should become a path field inside Browse rather than its own page.
3. **Give the project a real Overview.** Today the sidebar rail *is* the project home
   (E-08). Making `/projects/{id}` a page with a gate roll-up and a "next action" line is what
   turns the nine stages from a list of links into a pipeline.

Two supporting moves: make the header breadcrumb (`header.html:12-14`) clickable — right now
`run_id / stage_id` is inert text, so from a stage page there is no link back to the project —
and keep the stage rail visible while inside a project rather than only on project routes.

---

## 3. What state is visible on a stage page (Q2)

The operator's question at a stage is "can I approve this, and if not, why not." Walking
`stage.html:1-67` against the context built at `routes/stages.py:114-126`:

| State the operator needs | Visible? | Where / why not |
|---|---|---|
| Stage status (`ready`/`running`/`awaiting_review`/`approved`/…) | **Partial** | Only as a pill in the stage rail (`sidebar.html:10`). The page body never states its own status; `stage_status` is passed (`stages.py:117`) and used for exactly one comparison (`stage.html:56`) |
| Gate **passed** | Yes | `stage.html:40`, green via `.status-pass` (`style.css:122`) |
| Gate **failed**, and why | **Partial** | Rendered (`stage.html:39-50`) but **below the entire artifact body** — on a long prompt sheet the verdict is far below the fold |
| Gate **never ran** (registered gate, no result in frontmatter) | **No** | `output_gates` is empty → the whole `{% if output_gates %}` block vanishes (`stage.html:35`). `approval_service.py:55-58` blocks on exactly this condition. **E-02/E-03** |
| Gate **error** (runner raised) | Yes | Same block; `.status-error` (`style.css:124`) |
| Which upstream artifacts it received | **Partial** | Bodies concatenated under `## From {dep}` headings (`stages.py:76`). No version, no path, no timestamp |
| An upstream artifact that is **missing** | **No** | The `if up_latest is not None` guard (`stages.py:73`) drops it silently; "No upstream input." only appears when *all* deps are missing. **E-05** |
| Stale | Yes | `stage.html:56-58` + red rail pill |
| **Which** upstream changed to cause staleness | **No** | `is_stale` knows the path (`state_machine.py:34-39`); nothing carries it to the page |
| Artifact version / `created_at` / `finalized_at` | **No** | Parsed at `stages.py:100` into `output_meta`, only `gates` is forwarded. **E-06** |
| A turn running right now (on page load) | **Partial** | Rail pill only; the chat form stays enabled and the Send button gives no hint it will 409 |
| A turn that just finished successfully | **No** | Output/Gates panels are not refreshed and nothing says to reload. **E-01** |
| Claude CLI availability | Yes | Global header dot (`header.html:15-18`) — but not attached to the Send button it actually gates |
| Turn cost (`turns.cost_usd`) | **No** | Recorded in the schema (`schema.sql:26`), rendered nowhere |
| A previously recorded gate override reason | **No** | Written into the artifact by `approval_service.py:70,76`; never displayed |

**Verdict on the worst case.** A stage whose artifact carries no `gates` key at all presents as
a completely clean `awaiting_review` page: no gates panel, no warning, no override field
(`has_failing_gate` is False because never-ran gates are not in `output_gates`,
`stages.py:108`). Pressing "Mark Approved" then yields a bare 409 text page. There is no path
forward from inside the UI. That is E-03 and it is the single worst defect in this appendix.

Q8 (`style.css`, 176 lines): there **is** a coherent system — a CSS-variable palette, one
`.status` pill primitive with per-state modifiers, and three layout shells. It is not ad-hoc
and does not need rework. Its one real usability failure is coverage, not design: the modifier
set (`style.css:84-90,122-124`) covers stage statuses and gate verdicts only, so every
*discovery* status falls back to the unstyled base pill (E-09). Fix by adding modifiers, not by
restyling.

---

## 4. Findings

### E-01 · A finished turn leaves Output and Gates showing the previous state
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/base.html:76-83`, `pipeline-app/pipeline_app/templates/stage.html:32-55`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: After every successful generation the operator sees new assistant text in the chat panel while the Output panel still reads "No output yet." (or shows the prior version) and the Gates panel still shows the prior verdict. The natural read is that the turn produced nothing; the natural recovery is a manual reload that nothing prompts.
- **trigger**: Any stage turn that completes normally and emits a `result` event.
- **proposed_fix**: On the `result` event, replace the status line with an explicit "turn complete — output updated" affordance that reloads the page (or htmx-swaps the Output and Gates sections), rather than only removing the "running…" line.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-02 · Gate verdicts render below the whole artifact, and vanish entirely when no gate ran
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/stage.html:34-55`, `pipeline-app/pipeline_app/routes/stages.py:98-108`, `pipeline-app/pipeline_app/approval_service.py:52-58`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: The gate verdict is the page's most decision-relevant fact and it is placed after an artifact body that can run to hundreds of rendered lines. Worse, an artifact minted before a gate existed (or by any path that skipped gating) has no `gates` key, so the entire panel is omitted and the page is indistinguishable from a clean pass — the exact "silent pass of an unknown result" `approval_service.py:45-51` was written to refuse.
- **trigger**: Open any stage page; the never-ran case triggers on any artifact predating its stage's gate registration.
- **proposed_fix**: Move the gate summary above the artifact body as a status strip, and render the panel from the gate *registry* for the stage rather than from the frontmatter alone, so a registered gate with no recorded result shows as "never ran" instead of disappearing.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-03 · Never-ran gate creates an unescapable approve loop: no override field, plain-text 409
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/stage.html:59-65`, `pipeline-app/pipeline_app/routes/stages.py:108,225`, `pipeline-app/pipeline_app/approval_service.py:55-65`
- **component**: templates
- **failure_mode**: loud
- **blast_radius**: `has_failing_gate` is computed only from recorded fail/error results, so a never-ran gate renders the approve form *without* the override-reason input. The operator clicks "Mark Approved", `approval_service` raises, the route returns a bare 409 text page, and back-navigation returns to the same form with the same missing field. There is no way to complete the approval from the UI at all.
- **trigger**: Approve a stage whose latest artifact lacks a result for a gate registered in `GATE_REGISTRY`.
- **proposed_fix**: Compute the block condition in the route the same way `approval_service` does (failing **or** never-ran) and render the override input for both, with the reason stated inline above it.
- **fix_cost**: S
- **depends_on_finding**: [E-02, E-04]
- **owner_task**: T13
- **detected_by**: manual-trace

### E-04 · Every expected failure returns bare `PlainTextResponse`, destroying the page
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:138-141,155,225,233-236,238-241`, `pipeline-app/pipeline_app/routes/projects.py:35`, `pipeline-app/pipeline_app/routes/discovery.py:47,55-64`
- **component**: templates
- **failure_mode**: loud
- **blast_radius**: Eight distinct operator-reachable error states (bad slug, duplicate handle, slug collision, stage locked, stage running, another turn running, gate block, grounding-edit refusal) navigate the browser to an unstyled text document with no header, no nav, no back link and no form to retry from. The slug-collision message at `discovery.py:55-64` is eight lines of carefully written explanation delivered as a wall of monospace on a white page. Recovery is browser-back in every case, and any typed form content is at the mercy of bfcache.
- **trigger**: Any of the eight conditions above.
- **proposed_fix**: Re-render the originating template with an error banner (the pattern `inspector.py:51-58` already uses correctly) instead of returning plain text; keep the status codes.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-05 · A missing upstream artifact is silently dropped from the Input panel
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:69-78`, `pipeline-app/pipeline_app/templates/stage.html:5-12`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: For a multi-dependency stage (`visual` needs scripting + styleboard; `music` needs scripting + voiceover; `assembly` needs voiceover + visual), a dependency with no artifact on disk is skipped by the `is not None` guard and the panel renders the remaining ones with no gap indicated. "No upstream input." appears only when *every* dependency is missing. The operator reviews a partial input believing it complete, and the same partial context is what the turn was actually given.
- **trigger**: Open a multi-dependency stage where one upstream artifact is absent or unresolvable.
- **proposed_fix**: Render one labelled card per declared dependency — including absent ones, marked "missing" — instead of concatenating only the ones that resolved.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-06 · Stage page never states its own status, artifact version, or generation time
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/stage.html:3,32-34`, `pipeline-app/pipeline_app/routes/stages.py:100,117-121`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: The heading is `run_id — stage_id` and nothing else. Status is inferable only from a small pill in the left rail; the artifact's version, `created_at`, `finalized_at` and any recorded override reason are parsed into `output_meta` and then discarded. An operator cannot tell whether the body on screen is v1 or v7, or whether it was regenerated since they last looked.
- **trigger**: Open any stage page.
- **proposed_fix**: Add a status strip under the heading carrying the stage status pill, artifact version, generated-at, and the gate verdict summary; forward the already-parsed `output_meta` fields into the template context.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-07 · The hand-edit route has no UI — a whole feature is unreachable
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/stages.py:229-290`, `pipeline-app/pipeline_app/templates/stage.html:32-66`
- **component**: templates
- **failure_mode**: latent
- **blast_radius**: `POST …/stages/{id}/edit` mints a new artifact version, re-runs gates on the edited body, propagates staleness and resets the stage to `awaiting_review` — 60 lines of carefully-reasoned behavior. No template in the repo posts to it (grep across `templates/` returns nothing). The operator's only way to fix a small defect in an output is to re-run a whole turn or edit the file on disk outside the app, which bypasses the re-gating this route exists to guarantee.
- **trigger**: Wanting to correct a typo in a generated artifact.
- **proposed_fix**: Add an "Edit output" disclosure in the Output panel posting the artifact body to the existing route; hide it for `grounding`, which the route already refuses.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: grep-sweep

### E-08 · Seven flat nav peers, and the project home is a heading with nothing under it
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/partials/header.html:3-11`, `pipeline-app/pipeline_app/templates/base.html:112`, `pipeline-app/pipeline_app/templates/partials/sidebar.html:1`, `pipeline-app/pipeline_app/templates/project_home.html:1-4`, `pipeline-app/pipeline_app/static/style.css:135`
- **component**: templates
- **failure_mode**: latent
- **blast_radius**: Extends SEED-15. Two corrections to the seed: the empty `<aside>` does **not** leave a visible gutter — `style.css:135` collapses it via `:not(:has(*))`, so this is a structural, not a visual, defect. And the more consequential half is `project_home.html`: because it renders only `<h1>{{ project.run_id }}</h1>`, the stage rail *is* the project home. There is no gate roll-up, no "which stage needs you now", no brand or created-at, and no way to see the pipeline's overall state without opening a stage. The breadcrumb (`header.html:12-14`) is inert text, so from a stage there is no link back to the project either.
- **trigger**: Open `/projects/{id}`, or try to navigate from a stage back to its project.
- **proposed_fix**: Adopt the three-section IA in §2 (Projects · Discovery · Library) and make the project home a real Overview page carrying the stage rail plus a gate/status roll-up; make the breadcrumb segments links.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-09 · `completed` and `completed_with_errors` are visually identical on the runs page
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/discovery_runs.html:9`, `pipeline-app/pipeline_app/static/style.css:76-90,122-124`, `pipeline-app/pipeline_app/discovery_engine.py:250,257,400`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: The run status renders as `class="status status-{{ status }}"`, but no `.status-completed`, `.status-completed_with_errors` or `.status-failed` rule exists — only stage statuses and gate verdicts have modifiers. Both terminal run states therefore render as the same transparent, borderless pill; the only difference is 13 extra characters of body text in a dense list. The at-a-glance answer to "did last night's discovery run cleanly?" is unavailable, which is the entire purpose of the page. (`status-running` matches a stage modifier by coincidence and happens to render amber.)
- **trigger**: Open `/discovery/runs` after any run that had a per-handle error.
- **proposed_fix**: Add `.status-completed` / `.status-completed_with_errors` / `.status-failed` modifiers to the existing pill system, and hoist an error count onto the run line.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-10 · A failed handle is identified only by a numeric database id
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/discovery_runs.html:13-15`, `pipeline-app/pipeline_app/routes/discovery.py:116-119`, `pipeline-app/pipeline_app/schema.sql:61-68`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: Per-handle results render as `handle #7: error (0 items)`. `discovery_run_handles` stores only the FK, and the route does not join `handles`, so the platform and handle string are not available to the template. Answering "which source broke?" requires opening `pipeline.db` by hand. The error message is shown, which is good, but it is attached to an anonymous number.
- **trigger**: Any run where one handle errors.
- **proposed_fix**: Join `handles` in `discovery_runs_page` and render `platform/handle (display name)`; group or sort errored results to the top of each run.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-11 · "Run Now" redirects to a page showing no evidence the run started
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/routes/discovery.py:17-22,91-102`, `pipeline-app/pipeline_app/templates/discovery_handles.html:52-60`, `pipeline-app/pipeline_app/templates/discovery_runs.html:20-23`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: The button spawns a detached `Popen` and immediately 303s to `/discovery/runs`. The child must start a Python interpreter and import before it inserts its run row, so the redirected page almost always renders the *previous* state — no banner, no "starting…", nothing new in the list. The page has a manual "Refresh" link and no auto-refresh, so the operator's honest read is "nothing happened," and the natural response is to click Run Now again. If the child dies at startup, the page is identical and nothing ever appears.
- **trigger**: Click "Run Now (incremental)" or "Run Now (backfill)".
- **proposed_fix**: Insert the run row (status `queued`) in the request before spawning, land on a runs page that shows it, and poll or auto-refresh while any run is non-terminal.
- **fix_cost**: M
- **depends_on_finding**: [E-09]
- **owner_task**: T13
- **detected_by**: manual-trace

### E-12 · Handle validation: no styling, no failure reason, and a poll loop that can stall forever
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/discovery_handles.html:16,70-84`, `pipeline-app/pipeline_app/schema.sql:29-42`, `pipeline-app/pipeline_app/discovery_engine.py:243,248,255,279`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: The status cell uses the bare `.status` class with no modifier, so `pending`, `validating`, `validated` and `invalid` are typographically identical. The `handles` table has no error column, so an `invalid` handle never says *why* — the operator sees a word and no recourse. Separately, the inline poller's `await fetch(...)` has no `try`/`catch` and no `res.ok` check: if the app restarts or the request fails, the rejection is unhandled inside `setInterval`, the interval is never cleared, and the row displays "pending" indefinitely with no error surfaced.
- **trigger**: Add a handle that fails validation, or add one while the server is restarting.
- **proposed_fix**: Add `.status-*` modifiers for the four handle states, persist and display a validation failure reason, and give the poller an error branch that stops and marks the row "status unknown — reload".
- **fix_cost**: M
- **depends_on_finding**: [E-09]
- **owner_task**: T13
- **detected_by**: manual-trace

### E-13 · No htmx request in the app has an error path — a 500 or a dead server renders nothing
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/partials/browse_tree_items.html:16-29`, `pipeline-app/pipeline_app/templates/browse.html:16-21`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: All six `hx-*` usages in the repo are on the Browse page. htmx does not swap on a non-2xx response and does nothing on a network error, and there is no `hx-on::response-error`, no `htmx:responseError` listener, and no global error target anywhere. So: a 500 from `/browse/file` leaves the doc pane on the previously-viewed document (or the "Select a .md file" placeholder) — a click that appears to do nothing while showing content belonging to a different file. A `<details>` whose `/browse/tree` request fails stays open and permanently empty, and `hx-trigger="… once"` means it will never retry. If the server is down, the whole tree is inert with no indication.
- **trigger**: Any unhandled exception in `browse_file` / `browse_tree`, or clicking a tree item after the dev server stops.
- **proposed_fix**: Add a global `htmx:responseError` / `htmx:sendError` handler that writes a visible message into `#browse-doc` (and into the failed subtree), and drop `once` from the tree trigger so a failed expansion can be retried.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: grep-sweep

### E-14 · Browse cannot distinguish empty from broken, in three different ways
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/browse_service.py:171-195,111-132,219,229-236`, `pipeline-app/pipeline_app/routes/browse.py:16-24`, `pipeline-app/pipeline_app/templates/partials/browse_tree_items.html:2-6`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: (a) `_has_md_below` returns `False` on `OSError` (`:190-194`), and `list_children` uses it as the include test (`:219`) — so a folder that cannot be read is not shown as unreadable, it is **omitted from its parent's listing entirely**. The operator sees a shorter tree, not an error. (b) `resolve_grounding_pointer` returns `None` for malformed or truncated YAML (`:117-131`); `list_children:229-236` then skips the `pointer.yaml` entry, so a broken grounding pointer is invisible and its folder may disappear too — the route's "Grounding pointer could not be resolved." message at `browse.py:82` is unreachable through the tree because there is nothing left to click. (c) When a root directory exists but yields zero entries, `_folder_context` returns `{"entries": []}` with no `empty_message`, so `browse_tree_items.html` falls through to a for-loop over nothing and the "Pipeline Outputs" / "Corpus Docs" heading is followed by literal blank space.
- **trigger**: A permission-denied folder under `runs/`, a hand-edited `pointer.yaml`, or a fresh checkout with an empty `runs/`.
- **proposed_fix**: Have `_has_md_below` distinguish "unreadable" from "no content" and render unreadable folders as a disabled row with the reason; list a malformed `pointer.yaml` as a broken entry rather than skipping it; render an explicit empty-state line when a root resolves to zero entries.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-15 · Skill editor shows a phantom "Kickoff template" editor on 5 of 13 skills
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/skill_editor.html:12-17`, `pipeline-app/pipeline_app/routes/skills.py:8-18,58-63,87-95`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: `STAGE_ID_BY_SKILL` maps 8 skills to a stage; `.claude/skills/` contains 13. For `elevenlabs-audio`, `elevenlabs-music`, `midjourney-prompting`, `rgs-pairing-review` and `shorts-styleboard`, the lookup yields `None`, so the page unconditionally renders an empty "Kickoff template" textarea with a live Save button that targets a template that does not exist. The operator cannot tell "this skill has no kickoff template" from "the template is empty". Saving also produces no confirmation of any kind on either form — the redirect returns a page that looks exactly the same whether the write succeeded, silently no-oped on an unrecognized `target`, or had its git commit fail.
- **trigger**: Open `/skills/midjourney-prompting` (or any of the other four) and press Save.
- **proposed_fix**: Render the kickoff-template form only when the skill maps to a stage, with an explanatory line otherwise; add a save confirmation banner reporting what was written and whether it was committed.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: manual-trace

### E-16 · Doctor is mostly duplicated state and omits the one thing only it could report
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/templates/doctor.html:4-10`, `pipeline-app/pipeline_app/routes/doctor.py:8-24`, `pipeline-app/pipeline_app/main.py:25-27`
- **component**: templates
- **failure_mode**: silent
- **blast_radius**: Of five lines, one duplicates the header CLI dot and one duplicates `/skills`. Meanwhile `main.py:25` runs `backfill_styleboard_rows` at startup and stores the affected project list in `app.state.backfilled_projects` — a grep across the app finds **no other reference**, so a startup migration that mutates project state is reported to no one. Doctor also cannot say whether `pipeline.yaml` loaded, how many stages the topology declares, or whether any turn is currently running. As built it is close to vestigial; the fix is to give it the content it is uniquely positioned to show rather than to delete it.
- **trigger**: Open `/doctor` after a startup that backfilled rows.
- **proposed_fix**: Report the startup backfill result and the reconciled-orphan detail, add topology load status and stage count, and drop the skill-name list in favor of a link to `/skills`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T13
- **detected_by**: grep-sweep
