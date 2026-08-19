# Resume prompt — audit-remediation programme, start P15 (Wave B5, last package before Wave C)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-19. **P9 (Digest & Email) is merged into `main`**
([PR #51](https://github.com/happydotemdr/ContentStudio/pull/51), merge commit `62e91d0`).
Combined with P0, P1, P2, P3, P4, P5, P6, P7, P8, P10, P11, P12 already in `main`, **all four
packages of Wave B4 (P6, P7, P8, P9) are now done — Wave B4 is complete. P15 is Wave B5's only
package, and its pre-flight live-state check has already been done (this session) — dispatch can
start immediately with no further investigation needed.**

**Business value of P15, in one paragraph:** P9 made the digest email itself trustworthy — a
quiet day and a broken collection now render distinguishably, and a failed send leaves its own
`events` row. P15 closes the last remaining defect class before documentation (Wave C): the
**operator interface** is not yet trustworthy in the same way. Today Gate C's verdict is often
invisible or misleadingly absent (a gate that never ran renders identically to a clean pass), an
htmx failure is silent (a network hiccup just does nothing, no banner, no error), Browse silently
omits unreadable folders and broken pointer files instead of showing them as broken, and
`doctor.html` — the one page built for "something broke overnight, where do I look" — literally
prints the string `"None"` for a null orphan count and duplicates a skill list it could just link.
P15 closes 16 findings across the shared template shell, the stage page's gate/status rendering,
Browse, the discovery handles/runs pages, and Doctor. **Genuinely good news found during this
session's pre-flight check:** P3's gate/approval contract (merged months ago, in Wave B2) already
supplies every data key P15's templates need — `gate_view`, `has_blocking_gate`, `error_banner`,
`edit_allowed` and friends all already exist and are already computed by `routes/stages.py`, just
not yet rendered. P15 is template-and-CSS work almost start to finish, not template-plus-backend
work — see "What P15 is" below for the one task (T9) whose target file already has a partial,
differently-shaped implementation to work around rather than a truly empty starting point.

---

/superpowers:subagent-driven-development

You are resuming a fully-planned, already-validated **328-finding audit-remediation programme**
(329 as currently tracked — see "Definition of done" below for why).
Do not re-plan and do not re-audit.

**You are the orchestrator, not the implementor.** Give sub-agents only the context they need —
never share full context windows back and forth, never hand one the audit or another package's
plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation
accurate and the plan updated at every step. When you find a new gap or defect, **file it in the
relevant plan for review/validation before addressing it**, and only fix it inline if it is a
critical or important blocker. This has happened in every package executed so far — expect it in
P15 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

**Start P15 in a fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not
reuse P9's worktree/branch (`worktree-p9-digest-email`), which is merged, closed, and gone (the
git-side registration was removed at merge time). `origin/main` at merge commit `62e91d0` already
contains every fix P9 landed, plus this session's own docs-only follow-up commits (P9's plan §8
Outcome, P15's plan §0 pre-flight amendment, and this file).

**NEW TRAP this session, not seen before — an orphaned worktree directory that looks live but
isn't registered.** A session can start "already inside" a worktree-shaped directory
(`.claude/worktrees/<name>`) per its own launch context, while that directory is **not actually a
registered git worktree** (`git worktree list` doesn't show it). Symptom: `git rev-parse
--show-toplevel` and `git branch --show-current` silently resolve to the **main checkout** instead
of erroring, because git walks up looking for the nearest `.git` when the directory itself has no
worktree registration — so ordinary git commands run there quietly operate on the wrong repo
state without any error. **Always verify with `git worktree list` and confirm your directory
appears in it before trusting `pwd`/`show-toplevel` alone**, especially at the very start of a
session. If it doesn't appear, `ExitWorktree` is a no-op (nothing to exit from an unregistered
directory) — the fix is `EnterWorktree` with a fresh name, which creates a genuine new worktree
and moves the session into it.

**If you are already inside a (genuine) worktree session when you start**, `EnterWorktree` refuses
to create a second one directly — `ExitWorktree` first (`action: "keep"` if the current worktree's
branch is not yet merged and you might need it again; `"remove"` only after confirming its branch
is merged). The harness's worktree-boundary guard blocks `git -C "C:/Projects/ContentStudio"
<command>` redirects from inside a worktree-isolated session — this has now held across P9 and P9's
own docs-followup session, so treat it as stable rather than re-verifying every time. **Also
new this session:** the guard rejects some *single* Bash calls that capture multiple git values
via command substitution in one line (e.g. `GIT_DIR=$(...); GIT_COMMON=$(...); WORKTREE_PATH=$(...)`
all in one call) as "too complex to verify" even with no `-C` redirect anywhere — split into
separate single-purpose Bash calls, one variable capture per call, if you hit this.

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed
editable) was **not touched this session** (the P9 docs-followup work happened entirely in a fresh
worktree) — its sync state relative to `origin/main`'s `62e91d0` is **unverified as of this
resume prompt**. Re-run the fetch+status check yourself at the start of your session (`git fetch
origin main && git status --short && git log --oneline -3`, run from the main checkout, not
`-C`'d from a worktree per the note above) before assuming anything — **do not `git pull`/
`merge`/`reset` there yourself if it has uncommitted changes that look like real work; ask the
operator.** Prior sessions noted an unrelated Firecrawl retry/backoff change in `doc-ingest-app/`
and a handful of untracked operator files there — check whether those are still present or have
since been resolved; do not assume either way from this prompt alone.

**Baseline suite counts, verified this session at `origin/main`'s `62e91d0` (P9 merged):**
- Root suite (`python -m pytest tests/ -q` from repo root): **445 passed, 1 skipped, 0 failed.**
  Fully green.
- App suite (`cd pipeline-app && python -m pytest -q`): **1874 passed, 4 skipped, 0 failed.**
  Fully green. **There is no documented pre-existing-failure baseline to tolerate on either
  suite.** Any failure you see is new — treat it as a real regression, not "the same old ones."
- CI (`gh pr view 51 --json statusCheckRollup`, at merge time): **green** — all three jobs
  (`app-suite`, `root-suite`, `no-live-credentials`) succeeded, across (unusually) **two**
  separately-triggered CI runs for the same push — GitHub can trigger a workflow run for both the
  branch push and the PR event; check `gh pr view <N> --json statusCheckRollup` and confirm ALL
  rows are `SUCCESS`, not just the first run you see complete. Re-verify yourself at session
  start; don't trust this as gospel across sessions.
- **A separate, unrelated local-only failure exists in the repo root's own tooling suite** (not
  this programme's): `tests/test_build_cowork_plugin.py::test_the_lock_file_matches_the_current_
  skills_tree` and `::test_a_locally_built_artifact_is_not_older_than_the_skills_it_ships` — a
  Cowork plugin build-lock staleness check against `.claude/skills/`, fixed by `bash
  scripts/build-cowork-plugin.sh` if the operator wants it fixed. **Not part of the 445/1/0
  root-suite baseline above.** Do not treat this as a P15 regression if you see it; it predates
  this programme and is orthogonal to it. (Carried forward unverified this session — it was not
  re-checked, since P9's docs-followup work never ran the root suite from the main checkout.)

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | **merged** |
| B1 | P2, then P10 | **merged** |
| B2 | P3 + P11 + P12 together | **merged** |
| B3 | P4, then P5 | **merged** |
| B4 | P6, P7, P8, P9 | **all four merged — Wave B4 complete** |
| B5 | **P15** | **pre-flight checked this session, not yet started — start it now** |
| C | P13, then P14 | not started |

**Why P15 is next, precisely:** the master plan's wave table
(`docs/superpowers/plans/2026-08-08-audit-remediation.md`, search "Wave B5") says P15 "binds to
P3's gate context keys and P1's `recent_events`" — both merged (P3 in Wave B2, P1 in Wave A), so
P15's true dependencies have been satisfied for months; it was simply next in landing order once
Wave B4 finished. **This session ran P15's own pre-flight check** — reading all 16 of its findings
against the live repo before dispatching Task 1, the same discipline every package in this
programme has used — and found something better than the usual drift: **no P15-owned file has
been touched by anything since the plan was written**, but P3's already-merged backend contract
already supplies every key three of P15's tasks (T9, T10, T22) were written assuming they'd have
to wait for. See P15's own plan `docs/superpowers/plans/remediation/P15-ui.md` §0 for the full,
finding-by-finding verdict — do not re-run this check yourself, it is already done and committed.

## What P15 is — read `docs/superpowers/plans/remediation/P15-ui.md` §0 and §1-2 before dispatching Task 1

**Do not act from this summary alone** — it is oriented for triage, not execution, and the plan
file is long (2515 lines including this session's §0 amendment, 22 tasks). Read the actual plan
file yourself — **start with §0**, the pre-flight amendment written this session, before reading
anything else — following this programme's Sub-agent output contract (never hand a sub-agent the
whole plan file — extract only what each task needs, same discipline every prior package used).

**The defect P15 exists to close:** the operator-facing UI hides or misrepresents exactly the
signals the rest of this programme spent 14 packages making trustworthy underneath. A gate that
never ran can render identically to a clean pass. An htmx request that fails does nothing visible.
Browse silently omits what it can't read instead of showing it as broken. `doctor.html` — the
"something broke overnight" page — literally prints the string `"None"` for a null count.

**Scope — files owned by this package, no other package may touch them:**
```
pipeline-app/pipeline_app/templates/**            (all of it, 14 templates + 4 partials)
pipeline-app/pipeline_app/static/style.css
pipeline-app/pipeline_app/routes/browse.py
pipeline-app/pipeline_app/browse_service.py
pipeline-app/tests/test_routes_browse.py
pipeline-app/tests/test_browse_service.py
pipeline-app/tests/test_header.py
```
Plus two NEW files P15 creates: `static/htmx-2.0.0.min.js` (vendored, T1) and
`templates/partials/gate_strip.html` (extracted, T9).

**Findings closed here (16):** `B-74`, `D-41`, `D-42`, `D-47`, `E-01`, `E-02`, `E-03`, `E-06`,
`E-08`, `E-09`, `E-10`, `E-12`, `E-13`, `E-14`, `E-15`, `E-16`. No S0/S1 — highest severity is S2.
22 tasks total (T0 is bookkeeping; T1-T21 close the 16 findings, several in groups of 2-4; T22
renders P3's contract with no P15 finding attached, listed so the keys aren't published into a
template that ignores them).

**Suite:** app suite only (`cd pipeline-app && python -m pytest -q`) — P15 touches no root-suite
files. Targeted command from the plan's own header:
```bash
cd pipeline-app && python -m pytest tests/test_header.py tests/test_routes_browse.py tests/test_browse_service.py -q
```

### Pre-flight check result, already done — read P15's plan §0 for the full detail, this is the summary

**13 of 16 findings are untouched — dispatch exactly as written for those.** Three tasks need
awareness before dispatch, not a plan rewrite:

- **T9 (E-02)** — `templates/stage.html:47-70` already has a WORKING gate-rendering block (added
  incidentally by whichever commit adopted P3's `gate_view` contract, not a P15 change). It
  renders **below** the artifact body (plan wants above), uses `status-blocking`/`status-ok`
  classes (plan wants one class per `gate_view.state`, five values), and vanishes entirely when
  `gate_view` is empty (plan wants an explicit "No gate is registered" line for that case). T9's
  own "delete the old block" step names stale line numbers (the plan assumed a pre-P3 shape) —
  find the current block by content (`<div class="gates-panel">` through its matching `{% endif
  %}`) instead of trusting the plan's line numbers.
- **T10 (E-03)** — half already done: `has_blocking_gate` already gates the override input, and a
  blocked approve already re-renders `stage.html` at 409 (not a bare `PlainTextResponse`). Still
  open: no inline blocking-reason paragraph, no `approval_block_reasons` read anywhere, wrong CSS
  class on the error banner. T10's own failing tests will catch exactly the still-open half.
- **T22 (no P15 finding, P3 contract rendering)** — `edit_allowed`/`edit_blocked_reason`/
  `edit_action`/`edit_field` are already computed by `routes/stages.py` and completely unused in
  `stage.html`. `inputs[]` already has a differently-shaped rendering loop (present/malformed/
  missing, no `input-card` classes) to re-shape rather than build from scratch.

**B-74 (T15)** carries no live bug today — the `<option>` values already match the adapter
registry exactly, only the pinning test is missing. Proceed as written; you're guarding a
coincidence, not fixing a drift.

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this. P4 hit it **eleven times**
across 20 tasks; P5 hit it **twice**; P6 hit it **once**; P7 hit it **once cleanly**; P8 hit it
**seven times** across 41 tasks; **P9 hit it three times** across 27 tasks (one exception-type bug
in a task's own shown code, one forward-reference to two later tasks' not-yet-introduced variable
names, and one self-correction where the controller's OWN first-pass plan amendment
contradicted a task's own test before that task was dispatched — caught and fixed before
dispatch, not after). Every single instance across the whole programme has been a bug in the
PLAN's own shown/reference code or in the controller's own amendment text, never a case where the
live repo had silently drifted out from under a previously-correct plan **against** the package —
though P15's own pre-flight check (this session) found the *opposite* shape for the first time:
drift that pre-satisfies part of a task rather than breaking it. The mitigation, unchanged since P2:

1. **Grep for every symbol a task's own shown code references** before dispatching it — function
   names, class names, fixture names, other packages' modules — and confirm each either already
   exists live, or is defined within that same task's own text.
2. If something's missing: **amend the plan file FIRST**, as a `>` blockquote note inserted
   directly at the relevant task, **with its own commit** explaining what was wrong and why —
   then dispatch the corrected version. Never fix a gap silently inline without amending the plan.
3. Your own amendments can contain the same class of bug — re-verify their own claims (exact line
   numbers, exact counts, exact function signatures) against the live repo before committing them.
   **P9's session hit exactly this: its own first-pass §0 amendment told Task 12 to defer
   rendering to a later task, contradicting Task 12's own test, which required the rendering to
   exist immediately. Found and fixed before Task 12 was dispatched, not after.**
4. **A sibling package's plan can describe a contract that the OTHER package has since implemented
   differently than planned, because that package's code didn't exist yet when this plan was
   written.** P9's own `§6.1 → P8` section was exactly this (resolved during P9's own session —
   see P9's plan for the resolution if it's ever relevant again). **P15 has a related but inverted
   case: three of its own tasks (T9, T10, T22) assumed they'd be BLOCKED on P3, but P3 landed
   months ago with the exact contract shape assumed — verify a "Consumes X" note is still
   accurate (blocking or already-satisfied) before treating it as a blocker.**
5. **A later task can quietly widen what an earlier task's error-handling already covers, INCLUDING
   across the task/final-review boundary itself.** Only the final whole-branch review, reading the
   full cumulative interaction, tends to catch this. **P9's own final review found exactly this
   shape twice** (of 3 findings) — a run-level fact (`errors`, threaded into per-brand sections by
   one task) and another run-level fact (a "Run status" banner, pre-existing) each printed once
   PER BRAND SECTION instead of once per email — reproducing P9's own headline defect one layer
   down, because an earlier plan amendment's "keep this key per-section" list was invalidated by a
   later task changing what that key meant, and nothing re-checked the list. **Watch for this
   exact shape in P15 too: T8 (status strip), T9 (gate strip) and T12/T13/T14 (run status
   pills, handle results) all touch overlapping page real estate — walk the cumulative page
   render at final review time, not just each task's own diff.**
6. **A test double's structure can force a change to production code, and that's fine — but write
   the production comment to justify itself first, the test second.**
7. **Verify empirically before writing a brief, not after a fix-loop round.** Cheaper every time
   this programme has measured it. **P15's own pre-flight check (this session) is the largest-ever
   application of this principle** — a full 16-finding, 22-task live-state audit run BEFORE Task 1
   was ever dispatched, specifically because P9's session established that packages landing in
   between a plan's authoring and its execution is now the norm, not the exception, four packages
   running strong (P8→P9 found real drift; P9→P15 found a blocking dependency already cleared).
8. **A mandatory final whole-branch review is not the last line of defense against everything — CI
   on a genuinely different machine is.** Watch the PR's CI checks after pushing, AND after any
   subsequent "sync with main" merge commit. **P9's session hit a new variant: two separate CI
   workflow runs triggered for one push (branch push + PR event) — check `statusCheckRollup` for
   ALL rows across both runs, not just the first run that completes.**
9. **A named heading style is plan-specific, not tool-default.** P15 uses `### T0 — ...` /
   `### T1 — ...` (matching P7/P8/P9's convention) against the built-in `task-brief` script's
   `^#+\s+Task\s+N` pattern — you will need the same custom-extraction adaptation P7, P8 and P9's
   sessions all used (match `^#+\s+T\d+\s+—`, not `Task \d+`).
10. **A plan's own execution-order assumption, OR its characterization of a sibling file's current
    behavior, can be wrong even when nothing about the CODE the plan describes has changed.** Grep
    the live repo or write a two-line empirical check before dispatch — cheaper than a fix round,
    every time this programme has measured it.
11. **A test that fakes an external call by counting invocations can silently stop testing what its
    own docstring claims** if production code later changes how many calls one logical operation
    makes.
12. **A mandatory final whole-branch review has found real issues in every package executed so far
    without exception** — P3: 2 Critical + 3 Important; P10: 15; P11: 6; P12: 0 Critical + 5
    Important; P4: 1 Critical + 2 Important + 4 Minor; P5: 0 Critical + 3 Important + 11 Minor;
    P6: 0 Critical + 3 Important + 8 Minor; P7: 0 Critical + 3 Important + 8 Minor; P8: 0 Critical
    + 6 Important + 8 Minor; **P9: 0 Critical + 3 Important + several Minor** (2 of the 3
    Important findings were cross-task interaction bugs invisible to any single task's own review
    — see item 5 above — fixed in one consolidated dispatch, re-reviewed clean, zero new breakage;
    the third was a genuine product question — a recurring daily warning event — correctly
    escalated to the human partner rather than decided unilaterally, and left as-is per that
    decision). Do not skip it, do not shorten it, do not let a clean per-task review record talk
    you out of dispatching it on the most capable available model — and do not consider the
    package done until you've read its PR's CI logs and confirmed all jobs are green across every
    triggered run (there is no longer a documented pre-existing-failure baseline to fall back on —
    see Baseline suite counts above).

## Carried-forward open items (know they exist; check whether any land in P15's own files)

**Resolved this session, no longer open:**
- All of P9's own carried-forward items are closed by P9's merge — see
  `docs/superpowers/plans/remediation/P9-digest-email.md`'s own new §8 "Outcome" section for the
  full record if anything ever needs to reference the exact defect/fix pairs.

**From P9's final review (Minor, deferred, not fixed — full list in P9's plan's own task-review
ledger during execution; none block P15 unless it happens to touch these exact files, which it
should not, P15 owns different files):**
- `discovery_digest.py`'s `SKIP_NO_URL`/`SKIP_NO_PUBLISHED_FIELD` constants are named `SKIP_`
  despite being warnings, not skips — naming only.
- `comment_draft._ENV_PASSTHROUGH` omits proxy environment variables (`HTTP_PROXY` etc.) — would
  only matter if the drafting subprocess ever runs behind a corporate proxy.
- A handful of test-coverage gaps (a multi-brand `brand_coverage` fan-out test, an HTML-side
  filename assertion, a couple of required-keys-test omissions before they were fixed in the
  final-review pass) — see P9's plan §8 for the full list if ever relevant.

**None of P3/P4/P5/P6/P7/P8's older carried-forward items are load-bearing for P15** unless P15's
own tasks happen to touch the exact same lines (they should not — full historical lists remain in
each package's own merged PR body if needed: P3 #32, P4 #37, P5 #39, P6 #41, P7 #45, P8 #48,
P9 #51).

**From the gate-coverage final review (PR #40, unrelated to this remediation programme — still
carried forward, still nobody's job):** three issues in `pipeline_app/migrations.py` and
`pipeline_config.py`. All three dormant against the live `pipeline.yaml`. Neither file is in any
remaining package's owned-file list (P13/P14/P15). Full detail in prior resume-prompt revisions'
git history if anyone ever picks this up.

**`T20` is no longer parked — it is literally P15's own T19.** P5's session left
`routes/inspector.py:45` calling a `browse_service.sanitize_html` that didn't exist yet, explicitly
deferred to "P15's deliverable." **P15's plan already has this as Task 19 (D-47)** — a stdlib-only
allowlist sanitizer in `browse_service.py`, applied at the Browse producer site. Confirmed this
session: `browse_service.py` still has no such function, and `partials/browse_file.html` still
renders `{{ body_html | safe }}` unsanitized — T19 is genuinely still open, dispatch it as written.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`),
  not any worktree. Bake an explicit working-directory check (`pwd && git rev-parse
  --show-toplevel && git branch --show-current`) into every dispatch prompt — and per this
  session's new trap above, also check `git worktree list` includes your directory, not just that
  these commands return something plausible-looking.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8",
  errors="replace"`. Not directly relevant to P15 (no subprocess work in its scope), but still
  binding programme-wide if any task's plan text shows a `subprocess` call.
- **Bash resolution on Windows is genuinely two-layered** — never invoke `bash`/`sh` by bare name
  in a `subprocess.run([...])` call.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness. Not directly
  relevant to P15's scope, but still binding if any future task needs process liveness checks.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead. The harness's
  worktree-boundary guard also rejects complex multi-command heredocs run via `cd ... && ...`, AND
  (new this session) rejects some multi-variable-capture single-line commands even with no `-C` —
  prefer the Write tool over Bash heredocs for anything beyond a single simple command, and prefer
  separate single-purpose Bash calls over one compound multi-line script.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field.
- In this specific harness, the Bash tool's working directory can drift between calls depending on
  prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command
  fails unexpectedly. This harness refuses `cd`s out of a worktree-isolated session's own worktree
  entirely, and refuses `git -C <other-path>` redirects from a worktree-isolated session — both
  confirmed stable across P9 and this docs-followup session. Absolute-path Read/Write/Edit calls
  still work regardless. Running the ROOT suite from a Bash tool whose cwd had drifted into
  `pipeline-app` silently shadows the root `scripts/` package and produces a `ModuleNotFoundError`
  that looks unrelated — `cd /path/to/repo-root && python -m pytest tests/ -q` in one call is the
  reliable fix. **Hit again this session, twice** — after any `cd pipeline-app && ...` command,
  the NEXT Bash call still starts in `pipeline-app`, not the repo root; never assume cwd resets
  between calls.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()`
  (not `.fullmatch()`), will silently never capture the optional group.
- When two independently-written pieces of text/code both need to find something via a
  first-occurrence string match, and one can textually contain what the other searches for, they
  will collide.
- A `dict` subclass can override `__contains__`/`__getitem__`/`get` to raise on a specific key
  state rather than behaving like an ordinary dict — check a sibling package's actual class
  definition before assuming standard dict semantics from a type hint alone.
- **A later task can quietly widen what an earlier task's exception-handling already covers** — a
  code region one task wrapped in error-handling because nothing inside it could raise yet can
  become unsafe once a LATER task adds a new raising code path into that same region. Only a final
  whole-branch review reading the cumulative function/interaction tends to catch this.
- **A test that fakes an external call by counting invocations can silently stop testing what its
  own docstring claims** if production code later changes how many calls one logical operation
  makes.
- A finding that conflicts with the PLAN's own text (not the implementation) is the human's
  decision, same as any plan contradiction — present it, ask which governs, amend the plan first.
  **P9's session hit this twice: the §6.1→P8 staleness (resolved by reading P8's actual shipped
  code, no naming/duplication conflict actually existed) and Task 27's recurring daily-warning
  event (a genuine product question, escalated and decided by the human partner, not the
  controller).**
- **Once both suites are fully green, there is no longer a documented baseline to distinguish "the
  same old failures" from "a new regression."** Any test failure from this point forward in the
  programme is real until proven otherwise — do not assume it's pre-existing. The one exception is
  the local-only `test_build_cowork_plugin.py` staleness noted above, orthogonal to this programme.
- **`gh pr create --body-file` plus a manually-authored `.md` file works cleanly** for a PR body
  with backticks/code blocks — write the body to a scratch file (this programme puts these under
  the worktree's own `.superpowers/` directory, git-ignored) and delete it after `gh pr create`
  succeeds.
- **Finishing a branch via "push and create a PR," then continuing work in the SAME session after
  the PR merges, requires a second, fresh worktree** — the first worktree's branch is now merged
  and closed. `ExitWorktree` (`action: "remove"`, `discard_changes: true`, once the merge is
  independently confirmed via `gh pr view <N> --json state,mergedAt,mergeCommit`) before creating
  the next one — this worked cleanly end-to-end for P9's own worktree this session, no
  "Device or resource busy" issue hit this time (contrast with P8's session, which hit it).
- **GitHub can report a branch "out-of-date with base" even mid-review**, if an unrelated PR
  merges to `main` while your PR is open. Fix: `git fetch origin main && git merge origin/main`
  on the feature branch (not a rebase — this programme's convention is merge commits, per every
  prior "Merge origin/main into ..." commit in the history), re-run both suites, push. This
  triggers a fresh CI run on the merge commit — wait for it before considering the PR
  mergeable, same as the original review. (Not hit this session — P9's PR merged without an
  intervening unrelated merge — but still binding, it has hit prior sessions.)

## Definition of done (the whole programme, not any one package)

1. All 328 originally-audited findings closed, plus **B-113** (discovered during P9's own
   plan-reconciliation work, not part of the original audit, folded into P9 mid-package with the
   human partner's confirmation — see P9's plan §0/§8) — **329 findings tracked, 329 closed as of
   P9's merge, 0 remaining in merged packages.** Each verified by the mechanism its plan names.
   P3's own 22, P12's own 16, P4's own 26, P5's own 15, P6's own 18, P7's own 14, P8's own 31
   (plus 5 inbound seam obligations and 1 plan-amendment task, not separately counted), and now
   **P9's own 25** (24 original + B-113) are confirmed closed independently by each package's
   mandatory final review. **Running total: P0+P1+P2+P3+P4+P5+P10+P11+P12+P6+P7+P8+P9 merged;
   P15's own 16 are next.** Count each package's own total from its merged PR, not from memory.
2. **Both suites are fully green with no documented exceptions** — root suite 445 passed/1
   skipped/0 failed; app suite 1874 passed/4 skipped/0 failed, as of P9's merge (`62e91d0`). Track
   any future failure as real (except the one local-only Cowork-plugin staleness noted above,
   which predates and is orthogonal to this programme).
3. **CI is green** — all three jobs succeeded across both triggered runs on P9's merge commit, the
   third fully-green merge in this programme's history (after P7's and P8's). Re-verify at session
   start; confirm it stays green after P15 merges.
4. Every S0/S1 has an observed-failing-first regression test. (P15 has no S0/S1 findings — its
   highest severity is S2 — so this item is trivially satisfied for P15's own scope, but
   re-verify nothing in P15's 16 findings was mis-classified before assuming so.)
5. A scheduled discovery run with an injected fault exits non-zero with an error `events` row —
   closed by P8, confirmed via its own final review and CI.
6. Gate C rejects a malformed shot heading — closed by P11, verified end to end.
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing — P8's Task 40 closed the code
   side (`git grep` under `pipeline-app/` itself returns nothing); doc references at the repo
   root (`README.md`, `CLAUDE.md`) remain and are explicitly **P14's handoff**, not yet done.
8. P9's own contribution, now shipped: a quiet day and a broken collection render distinguishable
   emails, and a failed send is itself surfaced as an `events` row — the last piece of "the
   operator finds out when something is wrong" that P8's Business Value paragraph promised for the
   whole Discovery wave.
9. **New, P15's own contribution once it lands:** the operator-facing UI stops hiding or
   misrepresenting the signals the rest of the programme made trustworthy underneath — a gate
   that never ran reads as "never ran," not as a pass; an htmx failure is visible; Browse shows
   what it can't read instead of omitting it; Doctor becomes an actual "what broke overnight" page
   instead of printing the string `"None"`.
