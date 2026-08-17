# Resume prompt — audit-remediation programme, start P8 (Wave B4, third of four)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-17. **P7 (Bright Data adapters) is merged into `main`**
([PR #45](https://github.com/happydotemdr/ContentStudio/pull/45), merge commit `e23851c`).
Combined with P0, P1, P2, P3, P4, P5, P6, P10, P11, P12 already in `main`, **Wave B3 and the first
two packages of Wave B4 (P6, P7) are done. P8 is next.**

**Business value of P8, in one paragraph:** every prior package (P0–P7) made the discovery
subsystem's individual *adapters* trustworthy — each platform now fails loudly and distinguishably
instead of silently returning empty. P8 is where that trustworthiness becomes *operationally real*:
today a scheduled Bright Data/YouTube/Bluesky discovery run can fail in eight distinct ways and
Windows Task Scheduler still reports success (`run_discovery_cron.py:110` is an unconditional
`return 0`), and 35 stderr diagnostics vanish because the registered task has no output redirection.
That means the person running this pipeline has **no reliable signal that a night's discovery run
actually worked** — an operator finds out days later, from a content gap, not from a health check.
P8 replaces the constant `0` with a real exit-code contract Task Scheduler can alert on, gives every
adapter failure a durable home in the `events` table, closes the run-locking race that can spawn two
concurrent Bright Data jobs (a real double-bill risk), and wires up the `preflight()`/
`drain_diagnostics()` seams P7 already built but left unconsumed. In short: P8 turns "the adapters
are honest" into "the operator finds out when something is wrong" — the actual point of the whole
programme's Discovery wave.

---

/superpowers:subagent-driven-development

You are resuming a fully-planned, already-validated **328-finding audit-remediation programme**.
Do not re-plan and do not re-audit.

**You are the orchestrator, not the implementor.** Give sub-agents only the context they need —
never share full context windows back and forth, never hand one the audit or another package's
plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation
accurate and the plan updated at every step. When you find a new gap or defect, **file it in the
relevant plan for review/validation before addressing it**, and only fix it inline if it is a
critical or important blocker. This has happened in every package executed so far — expect it in
P8 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

**Start P8 in a fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not
reuse P7's worktree/branch (`claude/p7-audit-remediation-2aca46`), which is merged, closed, and
already cleaned up (worktree removed, branch deleted). `origin/main` at merge commit `e23851c`
already contains every fix P7 landed.

**If you are already inside a worktree session when you start**, `EnterWorktree` refuses to create
a second one directly — `ExitWorktree` first (`action: "keep"` if the current worktree's branch is
not yet merged and you might need it again; `"remove"` only after confirming its branch is merged).

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed
editable) **is now caught up to `origin/main`** as of this session (fast-forwarded to `e23851c`,
verified clean fast-forward, no conflicts). It may still have uncommitted operator work in
progress unrelated to this programme — re-run the fetch+status check yourself at the start of your
session before assuming anything (`git -C "C:/Projects/ContentStudio" fetch origin main &&
git -C "C:/Projects/ContentStudio" status --short && git -C "C:/Projects/ContentStudio" log
--oneline -3`) — **do not `git pull`/`merge`/`reset` there yourself if it has uncommitted changes
that look like real work; ask the operator.** From inside a worktree-isolated session you cannot
`cd` out to the main checkout, but `git -C "C:/Projects/ContentStudio" <command>` and absolute-path
Read/Write/Edit calls both work fine without violating the harness's cd restriction — use those to
inspect or (with explicit operator sign-off) modify the main checkout without leaving your worktree.
As of this session, the main checkout carries one known unrelated WIP: a Firecrawl retry/backoff
change in `doc-ingest-app/` (uncommitted, reviewed and mostly ready — see
`docs/superpowers/plans/2026-08-17-doc-ingest-retry-backoff-closeout.md` for its own standalone
close-out prompt if the operator wants it finished). Not part of this programme; leave it alone
unless the operator asks.

**Baseline suite counts, verified this session at `origin/main`'s `e23851c` (P7 merged):**
- Root suite (`python -m pytest tests/ -q` from repo root): **445 passed, 1 skipped, 0 failed.**
  Fully green — no pre-existing exception. (The historically-carried `T6R-02` fenced-heading
  exception was retired by a separate PR, `#44`, before P7 even started; confirmed this session
  the test file no longer has that mutation case.)
- App suite (`cd pipeline-app && python -m pytest -q`): **1628 passed, 4 skipped, 0 failed.**
  Fully green — the historically-carried 31 pre-existing failures (`write_pointer()` missing
  `repo_root`, a removed `grounding_service.identify_new_brief`) were also fixed by PR #44.
  **There is no longer a documented pre-existing-failure baseline to tolerate on either suite.**
  Any failure you see is new — treat it as a real regression, not "the same old ones."
- CI (`gh run list --branch main --limit 5`): **green** — for the first time in this programme's
  history, the merge commits for both P7 (`e23851c`) and the PR #44 fix (`d52409d`) show `success`
  on all three jobs (`app-suite`, `root-suite`, `no-live-credentials`). Re-verify yourself at
  session start; don't trust this as gospel across sessions.

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | **merged** |
| B1 | P2, then P10 | **merged** |
| B2 | P3 + P11 + P12 together | **merged** |
| B3 | P4, then P5 | **merged** |
| B4 | P6 (**merged**), P7 (**merged**), **P8**, then P9 | **P6 and P7 done. P8 has not started — start it now.** |
| B5 | P15 | not started |
| C | P13, then P14 | not started |

**Why P8 is next, precisely:** the master plan's wave table
(`docs/superpowers/plans/2026-08-08-audit-remediation.md`, search "Wave B4") puts P6/P7/P8/P9 in
one wave, with a real ordering constraint: *"P8 consumes seams from P6 (`BlueskyFetchError`
reaching the engine) and P7 (`drain_diagnostics`, `preflight`), so land P6 and P7 before P8; P9 is
independent."* Both P6 and P7 are now merged, so that constraint is satisfied. P8 is also, by a
wide margin, the largest single package in this programme (**40 tasks**, 31 owned findings + 5
inbound seam obligations) — budget accordingly; this will likely take longer than any prior
package's session.

## What P8 is — read `docs/superpowers/plans/remediation/P8-engine-cron.md` in full before dispatching Task 1

**Do not act from this summary alone** — it is oriented for triage, not execution, and the plan
file is long (2563 lines, 40 tasks across 7 groups). Read the actual plan file yourself, following
this programme's Sub-agent output contract (never hand a sub-agent the whole plan file — extract
only what each task needs, same discipline every prior package used).

**The defect P8 exists to kill:** a scheduled discovery run exits `0` in **eight distinct
real-failure states**. `run_discovery_cron.py:110` is an unconditional `return 0`. The test suite
contains 12 assertions of `exit_code == 0` and zero assertions of any other value — one of them
named for the defect. Everything else in this package is downstream of two amplifiers: that
constant exit code (B-40/D-01) and the registered `schtasks` action's total lack of output
redirection (D-02), which destroys all 35 stderr diagnostics on the scheduled path.

**Scope — files owned by this package, no other package may touch them:**
```
pipeline-app/pipeline_app/discovery_engine.py
pipeline-app/pipeline_app/discovery_scheduling.py
pipeline-app/pipeline_app/discovery_records.py
pipeline-app/pipeline_app/discovery_paths.py
pipeline-app/pipeline_app/routes/discovery.py
pipeline-app/run_discovery_cron.py
pipeline-app/scripts/setup_discovery_task.py
pipeline-app/tests/test_discovery_engine.py
pipeline-app/tests/test_discovery_scheduling.py
pipeline-app/tests/test_discovery_records.py
pipeline-app/tests/test_discovery_paths.py
pipeline-app/tests/test_routes_discovery.py
pipeline-app/tests/test_run_discovery_cron.py
pipeline-app/tests/test_setup_discovery_task.py
```

**Findings closed here (31):** B-40 through B-64 (not sequential — see the plan's own §2 table),
D-01, D-02, D-06, E-11, F-16, F-68. Three of these are **S1**: B-47 (unvalidated tz/time_of_day
wedges the scheduler), B-50 (sleep/wedged heartbeat → two concurrent runs — the double-billing-risk
one), F-16 (no test asserts a nonzero exit on any unattended path), plus F-68 (**S1**, the suite
can spawn a real billed Bright Data run if a stub is forgotten).

**Boundary notes — audit-proposed fixes that name other packages' files, re-planned to land inside
P8's own scope with the residual handed off explicitly** (full detail in the plan's §1 table):
- B-50: the atomic `WHERE status='running'` guard belongs to P1's `db.py`; P8 ships
  `_finish_run_guarded()` as a narrower wrapper and documents the residual race.
- B-63: P1/P10 must call `discovery_paths.assert_no_slug_collision()` (P8 delivers it); P8 proves
  a durable runtime detector fires for rows inserted by the non-route path.
- B-43, E-11: P8 computes `health`/`pending_spawns` into the route context; **P15** renders them.

**Inbound seam obligations — other packages' findings whose closing half lands here** (not counted
in the 31, each has its own task):

| Owner | Finding | What P8 must do | Task |
|---|---|---|---|
| P6 | B-06 (S1) | `BlueskyFetchError` (and every typed adapter error) must reach `discovery_engine.py:272`'s error branch WITHOUT `:255` converting it to `status='invalid'`+`included=False`. **P6's own final review found "route it to the other branch" is NOT sufficient by itself** — the `:272` branch's own auto-exclude behavior must change for a transport exception too; see P6's plan §7 amendment. | 36 |
| P7 | B-01 | Call `brightdata_job.drain_diagnostics()` in the run loop, write each record via `obs.record_event`. | 37 |
| P7 | B-21 | Call each adapter's `preflight()` once per run, before the handle loop. | 38 |
| P1 | B-73 (S2) | Route-level `platform` rejection ahead of P1's storage `CHECK`. | 27 |
| P1 | B-82 (S2) | Call `db.record_handle_failure()`/`db.clear_handle_failures()` from the per-handle branches. | 39 |
| P0 | F-64 (S2) | Move `setup_discovery_task.py` into `pipeline-app/tools/`, **one atomic commit with P10's six file updates and the directory move.** | 40 |

**NEW — an operator decision already made needs a plan amendment before Task 1:** P8's plan text
says the true per-handle Bright Data item cap (a `PlatformAdapter` protocol change threading
`handle_row` into `enumerate_newest_first`) is out of scope "**only** if the operator approves P7's
cost item C1." **The operator approved C1 during the P7 session** (recorded in
`docs/superpowers/plans/remediation/P7-brightdata.md` §6's amendment blockquote, and in P7's own
git history at commit `55109b8`). This means the per-handle cap is now IN SCOPE for P8 and is not
one of the 40 numbered tasks — **read P8's plan §1 and §7 "Open handoffs" for the P7 row, confirm
this reading is still accurate, then amend the plan with a new task (or extend an existing one)
before dispatching**, following the same "amend first, with its own commit" discipline as every
other mid-programme correction in this document. Do not silently skip this or silently bundle it
into an unrelated task without a plan note.

**Depends on P0** (conftest network/subprocess guard — P8's route tests are written against the
`subprocess.Popen` guard staying armed, not around it) **and P1** (`obs.py`, `events` table,
`db.record_handle_failure`/`clear_handle_failures`, the `failing` status). Both long merged.
**Also effectively depends on P6 and P7 being merged** (Task 36-39 use locally-constructed
stand-ins so P8 isn't blocked on exact merge timing, but `test_the_local_stand_in_names_match_p6s_real_exported_errors`
pins the stand-ins against the real modules — both are merged now, so this should just pass).

**Suite: app suite** (`cd pipeline-app && python -m pytest -q`) — P8 touches no root-suite files.
Verification command from the plan's own §7:
```bash
cd pipeline-app && python -m pytest -q
```
Package-specific acceptance checks (plan §7, all 7 must hold): zero bare-`0`-exit-code assertions
in `test_run_discovery_cron.py` with ≥17 parametrized contracted-code assertions;
`grep -rn "does_not_propagate_or_change_exit_code" pipeline-app/tests/` empty;
`grep -rn "subprocess.Popen" pipeline-app/pipeline_app/routes/discovery.py` exactly one hit (inside
`_popen`); the programme-level "injected fault → nonzero exit + error events row" check passes;
every S1 (B-47, B-50, F-16, F-68's guard) has an observed-failing-first test; the exit-code table
in the plan's §3 and `EXIT_REASON` agree; every inbound seam obligation above has its own named
passing test.

**40 tasks across 7 groups — one line each here, full detail in the plan file:**

*Group A — the exit-code spine (B-40, B-41, D-01, D-06, B-47a, F-16):*
1. Publish the exit-code contract as code. 2. `run_discovery` reports per-status counts.
3. `classify_exit`, the pure mapping. 4. `main()` returns the contracted code. 5. An unsent email
is a non-zero exit and an event row. 6. A run that dies before its first DB write leaves a trace.
7. A wedged schedule setting degrades loudly. 8. **The data-driven exit-code contract test**
(F-16/B-40 capstone).

*Group B — the scheduled path's transcript (D-02, B-42, B-44, B-45, B-46):*
9. The registered task captures its own output. 10. Verify, refuse to clobber, and uninstall.
11. The dry run prints a runnable command. 12. The engine's three stderr sites become durable
events.

*Group C — the lock and the watermark (B-48, B-49, B-50, B-52, B-53):*
13. Run ownership: a sidecar and a Windows-safe liveness probe. 14. Reclaim refuses to steal a live
run. 15. A reclaimed run cannot resurrect itself. 16. Reclaim runs before the due-check. 17. A long
run stops manufacturing junk. 18. A timezone change cannot fire a second run the same day. 19. A
skipped day is visible as a gap. 20. Deadlines: a hung adapter no longer wedges discovery.

*Group D — per-handle truth (B-51, B-54, B-55, B-56, B-57):*
21. Partial downloads survive a raising handle. 22. `error_message` names the exception type.
23. Abandoned records stop contradicting their own DB rows. 24. Frontmatter totals reconcile.
25. A transient failure no longer permanently excludes a handle.

*Group E — the routes (F-68, B-58, B-60, B-47b, B-59, B-61, E-11, B-43):*
26. The spawn seam, so a forgotten stub fails instead of billing. 27. `platform` is validated
against the adapter registry. 28. Backfill dates are validated. 29. Schedule settings are
validated at the form. 30. Run Now stops stacking, and a lost race stops crashing. 31. A dead spawn
is visible. 32. The runs page can answer "is anything unhealthy?".

*Group F — paths and hygiene (B-62, B-63, B-64):*
33. Windows reserved device names. 34. One collision gate, and a durable detector for the paths
that bypass it. 35. Engine hygiene (imports, Protocol, tunables, naive datetime).

*Group G — inbound seams (P6 B-06, P7 B-01/B-21, P1 B-82, P0 F-64):*
36. A typed adapter error never marks a handle invalid. 37. Bright Data diagnostics become
`events` rows. 38. `preflight()` runs once per run, not once per handle. 39. A handle that keeps
failing stops looking healthy. 40. `pipeline-app/scripts/` → `pipeline-app/tools/`, **one commit
with P10's six file updates**.

**Sequencing note from the plan itself:** Tasks 36-39 are written against locally-constructed
stand-ins so P8 was not blocked on P6/P7/P1's exact merge order — since P6 and P7 are both merged
now, `test_the_local_stand_in_names_match_p6s_real_exported_errors` should pass cleanly against the
real modules; if it doesn't, that's a real signal something drifted, not a stand-in artifact to
wave away.

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this. P4 hit it **eleven times**
across 20 tasks; P5 hit it **twice**; P6 hit it **once**; P7 hit it **once cleanly** (T17's own
shown code measured saturation on the post-filter count instead of the raw API response count — a
false negative on the exact S1 finding the task existed to fix; caught by T17's own task review,
fixed via a plan blockquote + dispatched correction, never silently patched). The mitigation,
unchanged since P2:

1. **Grep for every symbol a task's own shown code references** before dispatching it — function
   names, class names, fixture names, other packages' modules — and confirm each either already
   exists live, or is defined within that same task's own text.
2. If something's missing: **amend the plan file FIRST**, as a `>` blockquote note inserted
   directly at the relevant task, **with its own commit** explaining what was wrong and why —
   then dispatch the corrected version. Never fix a gap silently inline without amending the plan.
3. Your own amendments can contain the same class of bug — re-verify their own claims (exact line
   numbers, exact counts, exact function signatures) against the live repo before committing them.
4. **A sibling package's return type/infrastructure can carry richer semantics than its signature
   alone reveals, and can be NEWER than the plan text that references it.** Read the actual current
   state of a file the task instructs you to change or stop calling.
5. **A later task can quietly widen what an earlier task's error-handling already covers, INCLUDING
   across the task/final-review boundary itself.** Only the final whole-branch review, reading the
   full cumulative interaction, tends to catch this. **P7's final review found exactly this shape
   twice** (both new — see "Carried-forward open items" below for full detail): a single-slot
   pending-store dict silently orphaned a paid-for snapshot on a SECOND consecutive timeout (a
   defect no single task's review could see, since T8 introduced the store and T9-T11 each only
   tested their own slice), and a `resume_pending` error-handling guarantee stated in its own
   docstring was only implemented for half the function (the poll call, not the fetch call). **P8's
   own Group C (the lock/watermark state machine, tasks 13-20) and Group D (per-handle truth,
   21-25) are exactly this kind of multi-task state machine — walk each one end to end at final
   review time, not just at each task's own review.**
6. **A test double's structure can force a change to production code, and that's fine — but write
   the production comment to justify itself first, the test second.**
7. **Verify empirically before writing a brief, not after a fix-loop round.** Cheaper every time
   this programme has measured it.
8. **A mandatory final whole-branch review is not the last line of defense against everything — CI
   on a genuinely different machine is.** Watch the PR's CI checks after pushing.
9. **A named heading style is plan-specific, not tool-default.** P6 used `### T1 · ...` (raised
   middot), P7 used `### T1 — ...` (em dash), **P8 uses `#### - [ ] Task N — ...`** (a fourth-level
   heading with an inline checkbox) — none match the built-in `task-brief` script's `^#+\s+Task\s+N`
   pattern closely enough to trust blindly; P8's actually might, since it does contain `Task N` —
   **verify the script's extraction output length looks sane before trusting it**, and fall back to
   a custom `awk` extraction (adapt P6/P7's sessions' scripts) if it over- or under-captures. The
   stop condition needs to catch the next `#### - [ ] Task N+1` heading AND the next `## <number>.`
   section heading.
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
    P6: 0 Critical + 3 Important + 8 Minor; **P7: 0 Critical + 3 Important + 8 Minor** (all 3
    Important were cross-task interaction bugs invisible to any single task's own review — see
    above — fixed in one consolidated dispatch, re-reviewed clean, zero new breakage). Do not skip
    it, do not shorten it, do not let a clean per-task review record talk you out of dispatching it
    on the most capable available model — and do not consider the package done until you've read
    its PR's CI logs and confirmed all three jobs are green (there is no longer a documented
    pre-existing-failure baseline to fall back on — see Baseline suite counts above).

## Carried-forward open items (know they exist; check whether any land in P8's own files)

**Resolved this session, no longer open:**
- `T21R-01` (Gate C's CLOSE/MACRO 1-object-floor carve-out) — code at
  `scripts/lint_prompt_sheet.py:753` (`TIGHT_SCALES_ONE_OBJECT_FLOOR`) shows this is implemented;
  treat as resolved unless you find evidence otherwise.
- `T6R-02` (the fenced-heading gate-C mutation case) — retired by PR #44 before P7 started;
  confirmed this session `tests/test_lint_prompt_sheet.py` no longer has that case, and the root
  suite is fully green with no exception.
- **B-25's `discovery_youtube.USER_AGENT` residual** (was P7's, carried from P6) — resolved in P7's
  own PR (`cb0c3c3`, an operator-approved flagged out-of-scope-file exception), not merely tracked.

**New from P7's final review (not P8's job unless P8 happens to touch these exact files — full
list in [PR #45](https://github.com/happydotemdr/ContentStudio/pull/45)'s body; all Minor, none
block anything):**
- `brightdata_job.py` reset-hook docstrings claim a repo-wide conftest fixture calls
  `reset_caches()`/`reset_state()` before every test — untrue; isolation is per-file autouse only
  (P7's own six test files), not repo-wide. If P8 ever adds a test file that constructs Bright Data
  adapters (it might, for the inbound-seam tasks 37/38), it needs its own isolation, not an
  inherited one.
- `_with_retry`'s `what` parameter is accepted but never used (dead, likely meant for logging).
- T12's `delete_snapshot`/`cleanup_fn` capability is still entirely unused in production (no
  adapter wires it in) — inert, not a blocker.
- Instagram's `adapter.author_field_unresolved` diagnostic can report an error-row's keys instead
  of a real content row's keys when `raw_rows[0]` happens to be an error row.
- `PENDING_STORE_PATH` is not `repo_root`-aware (T25's pattern wasn't extended to it) — worth
  threading if P8's task 37 (`drain_diagnostics` wiring) ever needs a sandboxed pending-store path
  for its own tests.
- `config_int` can emit duplicate `config.bad_override` diagnostics per call when a knob is read
  multiple times per `enumerate_newest_first` invocation.
- A raw-saturated-and-fully-filtered batch's escalation message interpolates "Posts older than
  None" — cosmetic.
- `BrightDataJobFailed`'s `snapshot_id`/`label`/`poll_timeout_s` attribute wiring (T7) has no
  dedicated test on the failed-job path (only timeout-path is tested) — diff-confirmed correct,
  just untested that way.

**None of P3/P4/P5/P6's older carried-forward items are load-bearing for P8** unless P8's own
tasks happen to touch the exact same lines (they should not — full historical lists remain in each
package's own merged PR body if needed: P3 #32, P4 #37, P5 #39, P6 #41).

**From the gate-coverage final review (PR #40, unrelated to this remediation programme — still
carried forward, still nobody's job):** three issues in `pipeline_app/migrations.py` and
`pipeline_config.py` (topological-order dependency in the hash-repair cascade; a malformed
downstream artifact permanently short-circuiting repair for a healthy upstream; `_check_no_cycles`
never walking `optional_depends_on`). All three dormant against the live `pipeline.yaml`. Neither
file is in any remaining package's owned-file list (P8/P9/P13/P14/P15). Full detail in prior
resume-prompt revisions' git history if anyone ever picks this up.

**`T20` remains parked** (P5's own explicitly incomplete task): `routes/inspector.py:45` needs
`browse_service.sanitize_html`, P15's deliverable (Wave B5, still not started). Not P8's concern.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`),
  not any worktree. Bake an explicit working-directory check (`pwd && git rev-parse
  --show-toplevel && git branch --show-current`) into every dispatch prompt.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8",
  errors="replace"`. **This is directly relevant to P8** — `run_discovery_cron.py` and
  `routes/discovery.py`'s spawn seam (Task 26) both shell out to subprocesses, unlike P6/P7.
- **Bash resolution on Windows is genuinely two-layered** — never invoke `bash`/`sh` by bare name
  in a `subprocess.run([...])` call. Directly relevant to P8's `setup_discovery_task.py` (Task
  9-11) if it shells out to `schtasks`.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness. **Directly
  relevant to P8's Task 13** (Windows-safe liveness probe for run ownership) and Task 31 (a dead
  spawn must be visible).
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead. The harness's
  worktree-boundary guard also rejects complex multi-command heredocs run via `cd ... && ...` —
  prefer the Write tool over Bash heredocs for anything beyond a single simple command, and prefer
  separate single-purpose Bash calls over one compound multi-line script.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field.
- In this specific harness, the Bash tool's working directory can drift between calls depending on
  prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command
  fails unexpectedly. **This harness refuses `cd`s out of a worktree-isolated session's own
  worktree entirely** — but `git -C <path>` and absolute-path Read/Write/Edit calls both work fine
  for touching the main checkout without violating this (used successfully this session to fast-
  forward the main checkout and clean up P7's worktree registration). Running the ROOT suite from
  a Bash tool whose cwd had drifted into `pipeline-app` silently shadows the root `scripts/`
  package with `pipeline-app`'s own and produces a `ModuleNotFoundError` that looks unrelated —
  `cd /path/to/repo-root && python -m pytest tests/ -q` in one call is the reliable fix.
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
  whole-branch review reading the cumulative function/interaction tends to catch this. **P8's own
  Group C (lock/watermark, tasks 13-20) and Group D (per-handle truth, 21-25) are exactly this
  shape — walk the full chain at final review time.**
- **A test that fakes an external call by counting invocations can silently stop testing what its
  own docstring claims** if production code later changes how many calls one logical operation
  makes.
- A finding that conflicts with the PLAN's own text (not the implementation) is the human's
  decision, same as any plan contradiction — present it, ask which governs, amend the plan first.
  **P7's T17 mid-review correction and the operator's approval of adding the per-handle cap
  mid-programme (see "operator decision already made" above) are both this shape.**
- **Once both suites are fully green (as they are now), there is no longer a documented baseline
  to distinguish "the same old failures" from "a new regression."** Any test failure from this
  point forward in the programme is real until proven otherwise — do not assume it's pre-existing.
- **`gh pr create --body-file` plus a manually-authored `.md` file works cleanly** for a PR body
  with backticks/code blocks — write the body to a scratch file (this programme puts these under
  the worktree's own `.superpowers/` directory, git-ignored) and delete it after `gh pr create`
  succeeds.
- **Finishing a branch via "push and create a PR," then continuing work in the SAME session after
  the PR merges, requires a second, fresh worktree** — the first worktree's branch is now merged
  and closed. `ExitWorktree` (`action: "keep"`) before creating the next one. **After a worktree's
  branch is merged, `git worktree remove` may fail with "Permission denied" if the session is still
  physically inside that directory** (Windows file-lock, not a git problem) — the git-side
  registration can still be removed (it'll disappear from `git worktree list`even if the directory
  itself lingers on disk); the orphaned directory needs manual deletion once the session that was
  inside it ends, or from a different session.

## Definition of done (the whole programme, not any one package)

1. All 328 findings closed — each verified by the mechanism its plan names. P3's own 22, P12's own
   16, P4's own 26, P5's own 15, P6's own 18, and now **P7's own 14** (B-01 through B-25 subset —
   fully closed now, no partial caveat — D-03, F-67, F-69) are confirmed closed independently by
   each package's mandatory final review. **Running total: P0+P1+P2+P3+P4+P5+P10+P11+P12+P6+P7
   merged; P8's own 31 (plus 5 inbound seam obligations, not separately counted) are next.** Count
   each package's own total from its merged PR, not from memory.
2. **Both suites are fully green with no documented exceptions** — root suite 445 passed/1 skipped/
   0 failed; app suite 1628 passed/4 skipped/0 failed, as of P7's merge (`e23851c`). This is new:
   every prior resume prompt in this programme had to carry forward a pre-existing-failure
   baseline; that baseline is gone. Track any future failure as real.
3. **CI is green** — also new. `gh run list --branch main --limit 5` showed `success` on P7's merge
   commit, the first fully green CI run in this programme's history. Re-verify at session start;
   confirm it stays green after P8 merges.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error `events` row.
   **This is directly P6/P7/P8's territory (Wave B4 is Discovery) — P6 and P7 delivered the
   adapter-side halves (typed exceptions, `drain_diagnostics()`, `preflight()`); P8 is where this
   item actually closes**, by wiring both packages' seams into the engine's run loop, the exit-code
   contract, and the `events` table. This is the whole point of P8 — see the "Business value"
   paragraph at the top of this document.
6. Gate C rejects a malformed shot heading — done, verified end to end.
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing — the F-64 atomic rename is P8's
   Task 40, landing in one commit with P10's six file updates.
