# Prompt for a fresh agent: close the outstanding pipeline-app follow-ups

Copy everything below the line into a new session.

---

You're working in `C:\Projects\ContentStudio\pipeline-app\` (a FastAPI + Jinja2 local app,
part of the `C:\Projects\ContentStudio` git repo, on branch `main`). Read
`C:\Projects\CLAUDE.md` and `C:\Projects\ContentStudio\CLAUDE.md` first for project
conventions.

## Background

Two implementation plans just landed on `main` (commits `2cba05b..8956d2d`): one hardened
the pipeline's stage-handoff logic (artifact resolution, approval gating, crash recovery,
staleness propagation), the other polished the app's CSS. Both went through TDD,
per-task review, and a final whole-branch Opus review. Full history — what was built, why,
and every decision made along the way — is in
`C:\Projects\ContentStudio\.superpowers\sdd\progress.md` under the sections "Progress
Ledger — Pipeline Handoff Hardening + CSS Polish" and "Progress Ledger — Pipeline App CSS
Polish". Skim those two sections before starting if you want the full reasoning behind any
item below — this prompt gives you the current state and the fix, not the history.

Both final reviews came back "Ready to merge: Yes" with a short list of follow-up items
that were deliberately **not** fixed at the time — explicitly deferred, not forgotten. This
prompt is that list. Close them now.

Run `cd pipeline-app && python -m pytest` before you start (should be 156 passed, 1
skipped) and after every item, so you always know whether a change broke something. Use
TDD for anything that touches Python. Commit each item separately with a clear message —
don't bundle unrelated items into one commit. Don't refactor anything not listed here.

If the `superpowers` skill set is available to you, `superpowers:systematic-debugging` and
`superpowers:test-driven-development` both apply to the Python items below; you don't need
`brainstorming` or `writing-plans` for this — everything here is already fully diagnosed,
not a design problem, with one exception (Item 4) flagged below.

---

## Should-fix (real robustness gaps)

### Item 1: The locked/running invariant lives only at the route layer

**File:** `pipeline-app/pipeline_app/routes/stages.py`

Three routes (`stage_chat` line 104, `approve_stage_route` line 174,
`edit_stage_output_route` line 194) each independently check
`stage_row["status"] in (StageStatus.LOCKED.value, StageStatus.RUNNING.value)` and return a
409 if so — copy-pasted, not shared. This is exactly how the bug that motivated this check
arose in the first place (a route was added without it). `approval_service.approve_stage`
(`pipeline-app/pipeline_app/approval_service.py`) and `turn_service.run_stage_turn`
(`pipeline-app/pipeline_app/turn_service.py`) accept any status — the invariant isn't
structural.

**Fix:** move the check into the service layer. `approve_stage` should raise `ValueError`
for a locked/running stage (the route already catches `ValueError` from this function and
turns it into a 409 — see `approve_stage_route`'s existing `try`/`except ValueError`).
`run_stage_turn` should raise a comparable exception (check `TurnAlreadyRunningError` in the
same file for the existing pattern of a turn_service-specific exception the route layer
catches) rather than silently proceeding. `edit_stage_output_route` doesn't call a shared
service function today — decide whether to extract one or leave its own inline check (it's
already the odd one out, being a direct DB/filesystem writer). Once the checks are in the
service layer, the three routes' inline `if stage_row["status"] in (...)` blocks should be
deleted (the grounding-specific check in `edit_stage_output_route` stays — it's unrelated).

Update the existing tests that currently assert the 409 via the route (`test_routes_chat_sse.py`,
`test_routes_approve_edit.py`) to still pass, and add at least one test at the service level
(`test_approval_service.py`, `test_turn_service.py`) proving the guard fires there directly,
not just through the HTTP layer.

### Item 2: Re-approving an already-approved stage churns its hash and cascades false staleness

**File:** `pipeline-app/pipeline_app/approval_service.py`, function `approve_stage` (line 22-29)

`approve_stage` unconditionally calls `artifacts.stamp_final(latest, now)` (skipped only for
`stage_id == "grounding"`, added by a prior task — leave that guard alone). `stamp_final`
rewrites `finalized_at` in the artifact's frontmatter every time it's called, which changes
the file's sha256 every time — including on a stage that's already `approved` and gets
re-approved with no new content. Since staleness propagation
(`turn_service.propagate_staleness`) compares recorded hashes against current hashes, this
means re-approving a stage can spuriously invalidate every stage downstream of it, even
though nothing substantive changed. This risk got worse after the transitive-staleness work
landed (a false positive now cascades further than one level).

**Fix:** `stamp_final` should be a no-op (or simply not called) when the artifact is already
stamped final — i.e., skip it if the stage is already `StageStatus.APPROVED.value` at the
start of `approve_stage`, not just when `stage_id == "grounding"`. Write a failing test
first: approve a stage, record its artifact's hash, re-approve it, assert the hash is
unchanged and no downstream stage flips to stale as a side effect. Check
`test_approval_service.py` for the existing fixture/test patterns to match.

### Item 3: `rgs-briefs/.superseded/` isn't gitignored

**File:** `.gitignore` (repo root, `C:\Projects\ContentStudio\.gitignore`)

`grounding_service.supersede_previous_brief` moves outdated briefs into
`rgs-briefs/.superseded/` instead of deleting them (an earlier task's fix). That directory
isn't in `.gitignore`, so the first time a project regenerates its grounding stage, `git
status` shows a tracked-file deletion plus an untracked directory appearing, which is
confusing. One line: add `rgs-briefs/.superseded/` to `.gitignore`. No test needed — this
isn't application behavior, just repo hygiene. Confirm with `git status` before and after
using a scratch file if you want to prove it (don't leave scratch files behind).

---

## Optional (cosmetic / UX — use your judgment, or ask the user first)

### Item 4: No UI signal when approving a stale stage overrides the staleness cascade

A stage sitting at `stale` (built on since-changed upstream input) can still be approved
directly without regenerating — this is accepted, sound behavior (see the ledger for why),
not a bug. But there's currently no visual indicator in `stage.html` /
`partials/sidebar.html` that approving here is an override rather than a fresh approval.
This is a genuine design question, not a diagnosed fix — if you take it on, treat it as a
small design decision (what should the indicator look like, where does it show) rather than
assuming the answer. Skip it if you'd rather leave staleness-override silent.

### Item 5: `.status-no_artifact` and `.status-locked` are barely distinguishable by color

**File:** `pipeline-app/pipeline_app/static/style.css` line 9 (and line 3 for comparison)

```css
.status-locked { background: #ddd; }
...
.status-no_artifact { background: #eee; border: 1px dashed #999; }
```

`#eee` vs `#ddd` is a ~7% channel difference — not perceptible at badge size. The only real
distinction today is a 1px dashed border, which reads as a faint hairline. Suggested fix:
change line 9's background to `#fff` (white), which separates further from `locked`'s solid
`#ddd` and reads more clearly as "empty/placeholder" — the convention the dashed border is
already invoking. One-line change, no test needed (this app has no CSS regression tests —
verify visually via the running dev server, same as the CSS plan that introduced this rule
did: `.claude/launch.json` has a `pipeline-app` preview config).

### Item 6: Stylesheet has two organizing schemes stacked on top of each other

**File:** `pipeline-app/pipeline_app/static/style.css`, full file (58 lines)

Lines 1-35 are component/class rules (`.status`, `.pipeline-*`, `.specialist`). Lines 37-58
are element base rules (`pre`, `textarea`, `header`, `button`, `table`, `th, td`) plus two
more class rules (`.error`, `.input-panel`/`.chat-panel`/`.output-panel`) — all appended at
the bottom because each contributing task was told to "add at the end of the file". This has
**zero cascade effect** (element selectors are lower specificity than every class selector
here, so reordering changes nothing about how the page renders) but reads oddly top-to-bottom.

Suggested fix: move the element base rules (`pre`, `textarea`, `header`, `button`, `table`,
`th, td`) up near the top, right after the `body` rule on line 1, before the `.status`/
`.pipeline-*` component rules. Leave `.error` and the three panel classes where they are
(or move them up near their sibling component rules — your call). This is a pure reorder:
diff the rendered page before/after via the dev server to confirm nothing visually changed.

### Item 7: Three small CSS/markup nits (grouped since they're each one line)

- `pipeline-app/pipeline_app/static/style.css` line 41: `pre`'s `line-height: 1.5` is now
  redundant — `body` (line 1) already sets `line-height: 1.5` and `pre` would inherit it.
  Delete line 41 (it's currently a no-op, so deleting it changes nothing rendered — confirm
  that, then delete).
- `pipeline-app/pipeline_app/templates/skill_editor.html` lines 8 and 15: both `<textarea>`
  elements still carry `cols="100"`, which is now dead — the CSS `textarea { width: 100%;
  ... }` rule (style.css line 47-51) always wins. Remove the `cols="100"` attribute from
  both (leave `rows="20"` / `rows="10"` — those still matter, CSS doesn't set height).
- `pipeline-app/pipeline_app/static/style.css`: `textarea` has `box-sizing: border-box`
  (line 49) but `pre` (lines 37-45) doesn't. Not a bug today (no overflow observed either
  way), just an inconsistency — add `box-sizing: border-box;` to the `pre` rule for
  consistency, or decide it's not worth the diff and skip it.

---

## When you're done

Run `cd pipeline-app && python -m pytest` one final time (expect 156+ passed, 1 skipped —
higher if you added tests for Items 1-2). Report back a short summary: which items you
fixed, which you skipped and why (especially Item 4 if you skip it), and the final test
count. Don't push to `origin/main` without asking first.
