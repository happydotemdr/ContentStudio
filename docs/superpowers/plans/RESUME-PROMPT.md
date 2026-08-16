# Resume prompt — audit-remediation programme, start P7 (Wave B4, second of four)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-16. **P6 (native adapters: YouTube, Bluesky) is merged into `main`**
([PR #41](https://github.com/happydotemdr/ContentStudio/pull/41), merge commit `6d2bfdd`).
Combined with P0, P1, P2, P3, P4, P5, P10, P11, P12 already in `main`, **Wave B3 and the first
package of Wave B4 (P6) are done. P7 is next.**

**One unrelated PR landed in the same window** ([PR #40](https://github.com/happydotemdr/ContentStudio/pull/40),
merge commit `f8388c4`, "pipeline-architecture-eval") — merged to `main` immediately before P6's
own merge commit. Not part of this remediation programme; re-confirm it doesn't touch any file
this programme's packages own before assuming it's inert, but nothing in P6's or P7's file lists
overlapped with it this session.

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
P7 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

**Start P7 in a fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not
reuse P6's worktree/branch (`worktree-pipeline-audit-p6`), which is now fully merged and should be
left alone (its own PR is closed; its SDD workspace has been deleted, its git history survives in
`main`'s log). `origin/main` at merge commit `6d2bfdd` already contains every fix P6 landed.

**If you are already inside a worktree session when you start** (e.g. resuming this same
conversation), `EnterWorktree` refuses to create a second one directly — `ExitWorktree` first
(pass `action: "keep"` if the current worktree's branch is not yet merged and you might need it
again; `"remove"` only after confirming its branch is merged, and even then the tool will refuse
and ask for confirmation if the branch has unmerged commits it thinks you might lose — when in
doubt, `"keep"` costs nothing but a little disk).

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed
editable) may have uncommitted operator work in progress — re-run the fetch+status check yourself
at the start of your session (`cd C:\Projects\ContentStudio && git fetch origin main && git status
--short && git log --oneline -3`) to see its current state before assuming anything about it; **do
not `git pull`/`merge`/`reset` there yourself** — ask the operator rather than acting on it. Note:
from inside a worktree-isolated session, you cannot `cd` out to the main checkout at all (the
harness refuses it) — if you need to inspect main-checkout state, ask the operator to run the
check, or accept you cannot verify it directly this session.

**Baseline suite counts, verified this session at `origin/main`'s `6d2bfdd` (P6 merged):**
- Root suite (`python -m pytest tests/ -q` from repo root): **445 passed, 1 failed, 1 skipped** —
  the same documented, deliberately-deferred pre-existing exception as every prior session
  (`test_lint_prompt_sheet.py::test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[fenced-heading]`,
  unowned by P6 or P7). Re-verify the count yourself rather than trusting this as gospel — it has
  fluctuated by ±1 across sessions for reasons not yet diagnosed.
- App suite (`cd pipeline-app && python -m pytest -q`): **31 failed, 1489 passed, 4 skipped.** All
  31 failures are the SAME pre-existing failures every resume prompt since P3 has documented (by
  test name, not just count) — `write_pointer()` missing a required `repo_root` argument in test
  setup code across `test_approval_service.py`, `test_browse_service.py`,
  `test_discovery_digest.py`, `test_routes_browse.py`, `test_routes_stages.py`, plus one unrelated
  `AttributeError` on a removed `grounding_service.identify_new_brief` function in
  `tests/integration/test_stubbed_cli_e2e.py`. **P7 does not own or need to fix these.** The passed
  count (1489) is higher than P6's own final count (1449, per its PR) purely because that PR's own
  20 landed tasks plus its final-review fix wave added their own regression tests — not because
  anything outside the remediation programme changed this time.
- CI (`gh run list --branch main --limit 5`): **still not green** — same standing gap, see
  "Definition of done" below. Re-run yourself, don't trust this note.

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | **merged** |
| B1 | P2, then P10 | **merged** |
| B2 | P3 + P11 + P12 together | **merged** |
| B3 | P4, then P5 | **merged** |
| B4 | P6 (**merged**), **P7**, then P8, and P9 | **P6 done. P7 has not started — start it now.** |
| B5 | P15 | not started |
| C | P13, then P14 | not started |

**Why P7 is next, precisely:** the master plan's wave table
(`docs/superpowers/plans/2026-08-08-audit-remediation.md`, search "Wave B4") puts P6/P7/P8/P9 in
one wave, with a real ordering constraint inside it: *"P8 consumes seams from P6 (`BlueskyFetchError`
reaching the engine) and P7 (`drain_diagnostics`, `preflight`), so land P6 and P7 before P8; P9 is
independent."* P6 is now done. Nothing in the master plan requires P7 before P9 specifically (P9
has no dependency), but this programme has executed one package per session throughout, so the
recommended order for the remainder of this wave is **P7, then P8, then P9** — keep it simple, no
reason to reorder. Confirm this reasoning still holds by re-reading the master plan's wave table
yourself before committing to the order — "verify, don't inherit" applies to this resume prompt's
own claims too.

**Unlike P4→P5, there is no cross-package contract handoff gating P7 from P6.** P7 does not depend
on anything P6 delivered — they don't share files (verified: P6 owned
`discovery_{youtube,youtube_api,bluesky}.py`; P7 owns `brightdata_job.py` and
`discovery_{instagram,linkedin,facebook,x}.py`). P7's own plan file is otherwise self-contained,
**except for one operator-approval gate** — see immediately below, this is new to P7 and did not
exist in P6.

## STOP — an operator decision gates T1. Do not dispatch until this is resolved.

**P7 is billed per record** (Bright Data charges per data item collected), and its own plan states
plainly: *"No task in this plan adds a blind retry of a billing call. The operator approves or
declines each item [in §6 Cost note] before execution starts."* This is a new kind of gate — every
prior package in this programme (P0 through P6) had no real-world cost attached to any task. Read
`docs/superpowers/plans/remediation/P7-brightdata.md` §6 in full and present its three tables to
your human partner as one batched question before dispatching Task 1, the same way you'd present a
plan-conflict scan:

- **C1** (increases spend, requires approval): a per-platform item-cap override
  `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` — the knob only exists if approved; raising a cap raises
  records collected **proportionally** (the plan's own example: setting Instagram to 50 quintuples
  Instagram spend). Default if declined: stays at 10, B-02's truncation has no operator-accessible
  remedy.
- **C2** (reporting only, on by default, no direct cost): a saturation escalation message that
  itself says "this increases Bright Data spend per run" when it fires — this is the mechanism that
  would prompt someone to raise C1 later; approve/decline is really about whether the message ships
  at all.
- **C3** (net saving, on by default): resume-pending re-fetch, recovering an already-paid-for
  snapshot instead of triggering a second billed job, with a 48-hour expiry
  (`PENDING_MAX_AGE_H`) and a one-run-stale-data tradeoff when it resumes.

C4 through C9 either have no billing effect or reduce spend and don't need approval, but skim them
too so you can answer questions about the full picture. **Do not silently default anything here** —
an approved-by-silence C1 could genuinely 5x a platform's Bright Data bill. If your human partner
is not available to answer before you'd otherwise start, treat this exactly like a plan conflict:
stop and ask, don't proceed on an assumption.

## What P7 is — read `docs/superpowers/plans/remediation/P7-brightdata.md` in full before dispatching Task 1

**Do not act from this summary alone** — it is oriented for triage, not execution, and the plan
file is long (1777 lines, 25 tasks). Read the actual plan file yourself, following this programme's
Sub-agent output contract (never hand a sub-agent the whole plan file — extract only what each
task needs, same discipline every prior package used).

**The question P7 answers:** `brightdata_job.py` is this codebase's *good* example — its own module
docstring (`:6-10`) already states the "empty ≠ failed" invariant P6 spent its whole scope bringing
YouTube and Bluesky into line with, and `await_results` already raises typed errors rather than
returning `[]`. P7 **extends** that already-correct module and its four downstream adapters
(Instagram, LinkedIn, Facebook, X) with the harder edges the audit found: unbounded/unretried
polling, an unpinned invariant (nothing tests it, so nothing guards against regression), billing-
sensitive retry boundaries, and platform-specific field-mapping gaps.

**Scope — files owned by this package, no other package may touch them:**
```
pipeline-app/pipeline_app/brightdata_job.py
pipeline-app/pipeline_app/discovery_instagram.py
pipeline-app/pipeline_app/discovery_linkedin.py
pipeline-app/pipeline_app/discovery_facebook.py
pipeline-app/pipeline_app/discovery_x.py
pipeline-app/tests/test_brightdata_job.py
pipeline-app/tests/test_discovery_instagram.py
pipeline-app/tests/test_discovery_instagram_sort.py
pipeline-app/tests/test_discovery_linkedin.py
pipeline-app/tests/test_discovery_facebook.py
pipeline-app/tests/test_discovery_x.py
```

**Findings closed here (14):** B-01, B-02, B-03, B-18 through B-25, D-03, F-67, F-69. B-02 is the
one S1; the rest are S2-S4. Full finding→task map in the plan's §2.

**Four invariants this package must preserve** (plan's own §1, read the full rationale there
before touching any of these):
1. "Empty ≠ failed" — a transport/vendor/timeout failure raises; `[]` means only a genuinely empty
   result.
2. **LinkedIn stays two adapter instances** (`profile_adapter()` / `company_adapter()`, each with
   its own `LinkedInAdapter._cache`) — a person and a company can share a URL slug, and collapsing
   the caches into module globals would let one mode's paid batch serve the other's `download_item`.
3. Frontmatter contract: `fetched_at` mandatory (aware UTC, `isoformat(timespec="seconds")`); `url`
   strongly expected; metrics/`published` optional. No task may make `fetched_at` conditional.
4. `discovery_x.POLL_TIMEOUT_S = 600`, not 300 — the comment at `discovery_x.py:40-43` records a
   real measurement (243s at production `limit_per_input`). Do not "make the constants consistent"
   by shrinking it.

**Depends on P0** (the conftest network/subprocess guard — P7's tests must never reach
`api.brightdata.com`, every test stubs `bd.requests.post`/`get`/`delete` or the adapter's own
trigger/poll/fetch methods) **and P1** (`pipeline_app/obs.py`, the `events` table). Both are long
merged.

**Suite: app suite only** — run the six owned test files together
(`cd pipeline-app && python -m pytest tests/test_brightdata_job.py tests/test_discovery_instagram.py
tests/test_discovery_instagram_sort.py tests/test_discovery_linkedin.py
tests/test_discovery_facebook.py tests/test_discovery_x.py -q`), never a bare `pytest`, never from
the repo root. P7 touches no root-suite files. Its own definition of done (§8) additionally wants
these six files to pass under `python -m pytest tests/ -n auto` (parallel/random-order execution,
F-67's real acceptance test for the ordering-hazard fix) — treat that as part of the final
whole-branch review's job, not every task's.

**25 tasks, T1-T25 — full detail in the plan file, one line each here:**
1. **T1** — pin the "empty ≠ failed" invariant with the two missing Three-Test-Rule roles: a
   timeout-never-fetches test, and a distinguishability test (D-03).
2. **T2** — typed response validation instead of trusting vendor JSON shape (B-20).
3. **T3** — one shared unprovisioned-dataset guard, preventing a trigger against a placeholder
   dataset id (B-24, also cost item C7).
4. **T4** — bounded retry on `poll_status`, part 1 (B-18).
5. **T5** — retry `fetch_results`; **`trigger` is explicitly NOT retried** and this must stay
   pinned by its own test — a retried trigger that reached Bright Data on attempt 1 would start
   and bill a second collection job (B-18 part 2, cost items C4/C5).
6. **T6** — (per finding→task map) contributes to B-01 alongside T21; read both before touching
   either.
7-12. **T7-T12** — all six map to B-19 in the finding→task table; read the plan's §2 and §3
   together for how they divide the work (this resume prompt does not re-derive the six-way split
   — the plan's own task descriptions are the source of truth). T12 includes `delete_snapshot`
   cleanup (cost item C6, **ships OFF** by default — never called on the timeout path, where the
   snapshot is the only copy of paid-for data).
13. **T13** — preflight credential check, cost item C8 (saving in operator time, not billed
    dollars — fails a platform before the handle loop instead of after N wasted attempts) (B-21).
14-15. **T14-T15** — B-03: the per-platform item-cap override (`BRIGHTDATA_MAX_ITEMS_<PLATFORM>`,
    cost item C1, **requires the operator approval above**) and a longer poll timeout override
    (`BRIGHTDATA_POLL_TIMEOUT_<PLATFORM>`, cost item C9, a saving).
16-17. **T16-T17** — the **S1**, B-02: saturation escalation (cost item C2) plus whatever else
    B-02 needs — read the plan directly, this is the one high-severity finding in the package.
18. **T18** — B-22.
19-20. **T19-T20** — B-23, including the field-mapping gaps noted in §7's residuals (Instagram
    author/view-count field names are genuinely unverified against a live response as of this
    writing — T19/T20 read candidate lists and report real keys when none matches; the next live
    Instagram run resolves the ambiguity, a one-line follow-up to
    `AUTHOR_FIELD_CANDIDATES`/`VIEW_COUNT_FIELD_CANDIDATES`, not a blocker for this task).
21. **T21** — B-01, alongside T6 (see above).
22. **T22** — B-25. **Only partially closes it**: per the plan's own cross-package seam table, T22
    closes the two `REQUEST_TIMEOUT_S` re-exports, but `discovery_youtube.USER_AGENT` (an
    unreferenced string that looks like it configures request identity, but yt-dlp is never passed
    `--user-agent`) lives in **P6's file** (`discovery_youtube.py`, already merged, not owned by
    P7). See "Carried-forward open items" below — this residual needs an explicit decision, not a
    silent skip.
23-24. **T23-T24** — F-67 (ordering hazard): P7 adds public reset/threading hooks P0's conftest
    needs, plus six module-local autouse fixtures in P7's own test files so its suite is
    order-independent whether or not P0's repo-wide fixture is present.
25. **T25** — F-69.

**Cross-package seams P7 delivers, named in its own §1 table — read the plan's own wording, this
is a summary:**
- `brightdata_job.drain_diagnostics()` → shaped for `obs.record_event(...)`; **P8** drains it once
  per handle (P8 not yet started — this is a seam P7 produces, doesn't consume).
- `<adapter>.preflight()` → `None` or one operator-facing message; **P8**'s `run_discovery_cron.py`
  calls it once before the handle loop; P7 tests it directly.
- A per-platform item-cap env override (T14/T15, cost item C1) — a **true per-handle** cap needs
  `handle_row` threaded into `enumerate_newest_first`, a `PlatformAdapter` protocol change in
  `discovery_engine.py`; that's **P8**'s to add if the operator approved C1, explicitly out of
  scope here and recorded in P7's own §7.
- `discovery_youtube.USER_AGENT` (part of B-25) — **P6**'s file, not P7's; see T22 above.

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this. P4 hit it **eleven times**
across 20 tasks; P5 hit it **twice** plus one silent T1-fixture regression caught later; P6 hit it
**once**, cleanly, exactly as this mitigation predicts: a task's own shown test code (T2's original
fake-migration list) assumed two functions (`peek_upload_date`, `download_item`) were already
routed through a new chokepoint that a LATER task (T3) actually introduced. Found by grepping every
symbol T2's shown code referenced before dispatching it, fixed by amending the plan file with a
`>` blockquote note **before** dispatching the corrected task, committed separately
(`fb9dd94`) — never fixed silently inline. The mitigation, unchanged since P2:

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
   state of a file the task instructs you to change or stop calling — don't trust the plan's
   characterization of "what X currently does," even when the plan sounds confident.
5. **A later task can quietly widen what an earlier task's error-handling already covers, INCLUDING
   across the task/final-review boundary itself.** Only the final whole-branch review, reading the
   full cumulative interaction, tends to catch this — P6's own final review found exactly this
   shape twice: T20's new default item-cap silently narrowed a downstream package's (P8's)
   backfill path with no error (a genuinely new regression no task-scoped review could see, since
   the affected call site lives in a file P6 doesn't own), and a retry-state-machine helper
   (`_prior_transcript_attempts`, T10) caught a narrower exception set than its own sibling function
   (`_awaiting_transcript_retry`, T11) added one task later. **P7's own T4/T5 retry logic and
   T6-T12's six-way B-19 split are exactly the kind of multi-task state machine where this shape
   recurs — walk any retry/attempt-counting chain end to end at final review time, not just at each
   task's own review.**
6. **A test double's structure can force a change to production code, and that's fine — but write
   the production comment to justify itself first, the test second.** When a test fakes an external
   call by counting invocations, and production code changes how many calls a single logical
   operation makes, re-verify the count is still landing where the test's docstring claims — don't
   just check that the test still passes.
7. **Verify empirically before writing a brief, not after a fix-loop round.** Cheaper every time
   this programme has measured it.
8. **A mandatory final whole-branch review is not the last line of defense against everything — CI
   on a genuinely different machine is.** Watch the PR's CI checks after pushing, not just your own
   local suite runs, even when the final review came back clean. **P6's final review also found a
   real plan-text defect, not just an implementation one**: its own §7 cross-package note for B-06
   told P8 that "routing the exception to the existing error branch" was sufficient to fix the
   finding, when in fact that branch already produced the exact broken behavior on ANY exception —
   simply routing there would have let P8 believe B-06 was fixed when it was not. **A plan's own
   cross-package handoff notes are not self-certifying — verify a note's claim against the actual
   downstream file's current behavior before treating it as settled, even (especially) at final
   review time, when it's tempting to treat everything upstream as already checked.**
9. **A named heading style is plan-specific, not tool-default.** This programme's `task-brief`
   helper script (`scripts/task-brief` under the `subagent-driven-development` skill) only matches
   `^#+\s+Task\s+N` headings. P6's plan used `### T1 · ...` headings (a raised middot) and **P7's
   plan uses `### T1 — ...` headings (an em dash)** — neither matches the script's pattern. You
   will need a custom `awk` extraction (P6's session wrote one; adapt it) rather than the built-in
   script, and the boundary condition matters: stop the extraction not only at the next `### T<N+1>`
   heading but also at the next `## <number>.` section heading (P6's session initially over-captured
   an entire 264-line tail into a single task's brief before adding that second stop condition —
   verify your own extraction's output length looks sane, don't trust it blindly).

## Carried-forward open items (know they exist; check whether any land in P7's own files)

Two operator decisions remain open, unresolved, not any package's call — surface them again if the
operator hasn't weighed in (repeated in every resume prompt since P10/P11):

1. `T21R-01` — the `CLOSE`/`MACRO` 1-object-floor carve-out in Gate C's C8 check (P11's file).
2. `T6R-02` — what should catch an extra fenced example block mid-sheet (the one documented
   root-suite exception, `test_lint_prompt_sheet.py::...[fenced-heading]`, unchanged for many
   sessions now, confirmed still present and still out-of-scope for every package including P4/P5/P6).

**New this session — a decision P7 (or whoever picks it up) needs to make, not silently skip:**

3. **B-25's residual, `discovery_youtube.USER_AGENT`.** P7's own plan (§1 cross-package seam
   table, and §7 residual #4) says T22 closes B-25's `REQUEST_TIMEOUT_S` re-exports but explicitly
   leaves an unreferenced `USER_AGENT` string in `discovery_youtube.py` — **P6's file, already
   merged, not in P7's owned-files list.** Options: (a) ask the operator whether a one-line
   unreferenced-string removal in an already-merged sibling package's file is an acceptable, tiny,
   explicitly-flagged scope exception for P7's own PR; (b) file it as its own tiny tracked
   follow-up item for whichever later package (P13/P14, doc/cleanup waves) is willing to touch it;
   (c) leave it and record the decision either way in P7's own plan file so it isn't silently
   dropped. Do not just leave `USER_AGENT` unaddressed with no note — that recreates exactly the
   "residual quietly vanishes" failure this program's §7 sections exist to prevent.

From P3's final review (unchanged, still open): nine test failures in files P3 owns, a scratch-file
interleaving hazard, gate messages naming a scratch filename, eight further Minor findings (PR #32),
and four new CSS classes with no stylesheet rules yet.

From P12's final review (still open): nine Minor findings — full list in
[PR #34](https://github.com/happydotemdr/ContentStudio/pull/34)'s body.

From P4's final review (still open, not P7's job unless P7 happens to touch the exact same lines —
full list in [PR #37](https://github.com/happydotemdr/ContentStudio/pull/37)'s body): an untested
defensive branch in `turn_service._resume_failed`, a stale docstring on one turn-recovery test,
`routes/stages.py`'s hand-edit path not adopting P4's three-keyword widening, and `main.py:161`'s
implicit `repo_root=` derivation.

From P5's final review (still open, none are P7's job — full list in
[PR #39](https://github.com/happydotemdr/ContentStudio/pull/39)'s body): 8 Minor findings covering
a naming/assertion mismatch in one test, a partial Windows-junction defense, an unguarded
`path.write_text` in `routes/skills.py`, an anti-tautology violation inherited verbatim from the
plan text, two pre-existing non-conformant `subprocess.run` calls in `test_git_helper.py`, a stale
cross-package note in the master plan (since superseded — see below), a code comment ordering
nit, and an asymmetric collision-handling gap between DB-level and filesystem-level `run_id`
collisions.

**From P6's final review (still open, none are P7's job unless P7 happens to touch these exact
files — full list in [PR #41](https://github.com/happydotemdr/ContentStudio/pull/41)'s body, 8
Minor findings after the 3 Important ones were fixed in-session — 11 numbered issues total, not
11 Minor; verify counts like this yourself rather than trusting a prior session's arithmetic, per
the recurring-bug-class discipline below):**

4. `order_confidence: "exact"` is applied even to items the Data API returned no date for
   (deleted/private/API-miss ids inside the `if dates:` branch) — they sort last with
   `published=None` yet claim exact ordering.
5. `_warn_no_key`'s structured `obs.log` call is unthrottled while only the stderr `print` is
   throttled to once-per-process — a keyless run still emits one log record per `fetch_one` call
   (hundreds per corpus run), which is exactly the noise B-15 was trying to eliminate, just moved
   to a different channel.
6. `_FEED_CACHE` (Bluesky, module-level) is never cleared per run and grows unbounded across
   handles for the process lifetime — bounded by handle count today so not a practical leak, but
   worth confirming the Bright Data adapters (P7's own files!) bound their analogous caches the
   same way, since this resume prompt's author (P6's session) did not check.
7. Test-side `_FEED_CACHE` hygiene in `test_discovery_bluesky.py` is by convention (most tests call
   `clear_feed_cache()` first) not by fixture — an `autouse` fixture would make the file
   order-proof.
8. T19's parametrized native-adapter contract sweep uses `pytest.raises(Exception)` (loose — would
   pass on an unrelated `KeyError`/`AttributeError`, not just the typed contract error) and lives
   in `test_discovery_bluesky.py` rather than a dedicated file. **P7's own plan explicitly says it
   should hoist `_NATIVE_ADAPTERS` into a shared six-platform table** — when you do, tighten this
   at the same time (assert the per-platform expected exception type, not bare `Exception`).
9. Stray/late imports in `test_discovery_bluesky.py` (a re-import inside one test function despite
   a module-level import already existing; two imports sitting mid-file rather than at the top).
10. `on_disk_ids` (YouTube) now fully reads and YAML-parses every capture file instead of a
    filename-only glob — correctness fix, but a real cost increase for a large handle (tens of MB
    read per `process_handle` call for a 600-video handle). Flagged as a future perf concern, not
    a defect.
11. A fully-`pending_retry` handle (all its on-disk captures still awaiting transcript retry) now
    reads as brand-new (`is_new = len(on_disk) == 0`) to `discovery_engine.py` — **P8's file** —
    on the next run, taking the 90-day-lookback path instead of the narrower existing-handle path.
    Benign-to-correct for the actual scenario (a new handle onboarded during an outage), but an
    unlisted cross-package consequence P8's session should be aware of, not just P7's.
5-more items are pre-existing/task-level deferred minors (info.json parse asymmetry, a redundant
log field, a broad-but-safe stderr marker string, `max_items=0` treated as unbounded, an inert
test-only code path, a conditional-expression-as-statement) — full text in PR #41's body if any of
P7's own tasks happen to touch the same functions, which they should not (P7's scope is Bright
Data adapters, entirely separate files).

None of P3/P4/P5/P6's carried-forward items are load-bearing for P7 unless P7's own tasks happen
to touch the exact same lines, which they should not (P7's scope is Bright Data adapters, entirely
separate files from every prior package's).

**T20 remains parked** (P5's own explicitly incomplete task, tracked separately):
`routes/inspector.py:45` needs `browse_service.sanitize_html`, which is P15's deliverable (Wave
B5, still not started as of this session). Not P7's concern.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`),
  not any worktree. Bake an explicit working-directory check (`pwd && git rev-parse
  --show-toplevel && git branch --show-current`) into every dispatch prompt.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8",
  errors="replace"`. **P7 shells out to nothing** (Bright Data is an HTTP API, not a subprocess
  tool like yt-dlp) — this trap is inherited but likely inert for P7's own files; verify before
  assuming.
- **Bash resolution on Windows is genuinely two-layered** — never invoke `bash`/`sh` by bare name
  in a `subprocess.run([...])` call. Not expected to be relevant to P7 (no subprocess calls in its
  scope), but verify rather than assume.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead of an inline heredoc. The
  harness's worktree-boundary guard also rejects complex multi-command heredocs run via
  `cd ... && ...` — prefer the Write tool over Bash heredocs for anything beyond a single simple
  command, and prefer separate single-purpose Bash calls (`git rev-parse --git-dir`, then
  `git rev-parse --git-common-dir`, then `git rev-parse --show-toplevel`, then
  `git branch --show-current`) over one compound multi-line script when the harness's "too complex
  to verify stays inside the worktree" refusal fires on a chained version.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field from a filename or frontmatter value.
- In this specific harness, the Bash tool's working directory can drift between calls depending on
  prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command
  fails with an unexpected "no such file or directory" on a path you expect to exist. **This
  harness refuses `cd`s out of a worktree-isolated session's own worktree entirely**, and also
  refuses any single Bash call it judges "too complex to verify stays inside the worktree" — break
  such commands into the Write tool plus a simple `cd ... && command` instead of one compound Bash
  call. **P6's session also hit this repeatedly when running the ROOT suite from a Bash tool whose
  cwd had drifted into `pipeline-app`** — `cd /path/to/repo-root && python -m pytest tests/ -q` in
  one call is the reliable fix; running `pytest` against an absolute `tests/` path while cwd sits
  inside `pipeline-app` silently shadows the root `scripts/` package with `pipeline-app`'s own and
  produces a `ModuleNotFoundError` that looks unrelated to the real cause.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()`
  (not `.fullmatch()`), will silently never capture the optional group.
- When two independently-written pieces of text/code both need to find something via a
  first-occurrence string match, and one can textually contain what the other searches for, they
  will collide.
- A hand-written HTML sanitizer built on `html.parser.HTMLParser` must escape TEXT NODES
  (`handle_data`), not just attribute values. Not P7's concern.
- A `dict` subclass can override `__contains__`/`__getitem__`/`get` to raise on a specific key
  state rather than behaving like an ordinary dict — check a sibling package's actual class
  definition before assuming standard dict semantics from a type hint alone.
- **A later task can quietly widen what an earlier task's exception-handling already covers** — a
  code region one task wrapped in error-handling because nothing inside it could raise yet can
  become unsafe once a LATER task adds a new raising code path into that same region. Only a final
  whole-branch review reading the cumulative function/interaction tends to catch this. **P7's own
  T4/T5 (retry) and T6-T12 (the six-way B-19 split) are exactly this shape — walk the full chain at
  final review time.**
- **A plan's own execution-order assumption, OR its characterization of a sibling file's current
  behavior, can be wrong even when nothing about the CODE the plan is describing has changed.**
  Grepping the live repo or writing a two-line empirical check before dispatch remains cheaper than
  a fix round, every time this programme has measured it.
- **A test that fakes an external call by counting invocations can silently stop testing what its
  own docstring claims** if production code later changes how many calls one logical operation
  makes. Re-verify the count lands where claimed, don't just check green. **P7's cost-sensitivity
  makes this trap sharper than usual — a test asserting "one billed call" that's actually counting
  the wrong call could hide a real double-billing bug (see cost item C5, `trigger` deliberately not
  retried, pinned by `test_trigger_is_never_retried_because_a_retried_trigger_double_bills`; verify
  that test's call-counting is actually counting `trigger`, not some other method, before trusting
  it as the guard it claims to be).**
- **A mandatory final whole-branch review has found real issues in every package executed so far
  without exception** — P3: 2 Critical + 3 Important; P10: 15; P11: 6; P12: 0 Critical + 5 Important
  (plus 2 CI-only failures); P4: 1 Critical + 2 Important + 4 Minor; P5: 0 Critical + 3 Important
  + 11 Minor (as documented by P5's own resume-prompt handoff — not independently re-verified this
  session); **P6: 0 Critical + 3 Important + 8 Minor** (all 3 Important fixed in one fix wave,
  re-reviewed clean — two were plan-text corrections, one a one-line code fix; two of the three
  Important findings were genuinely invisible to any single task's own review, since they were
  cross-package/cross-task interaction bugs). Do not skip it, do not shorten it, do not let a clean
  per-task review record talk you out of dispatching it on the most capable available model — and
  do not consider the package done until you've read its PR's CI logs and confirmed the ONLY
  failures are the same documented pre-existing baseline (1 root + 31 app, by test name, not just
  by count).
- **A task-brief extraction script tuned for `Task N` headings will silently over- or under-capture
  against a plan using a different heading convention** (`T1 ·`, `T1 —`, etc.) — see recurring-bug-
  class point 9 above. Sanity-check every extracted brief's line count against a rough expectation
  before handing it to an implementer.
- **`gh pr create --body-file` plus a manually-authored `.md` file works cleanly** for a PR body
  with backticks/code blocks that would otherwise get mangled by `bash -c` — write the body to a
  scratch file (this programme has been putting these under the worktree's own `.superpowers/`
  directory, which is git-ignored, then deleting the scratch file after `gh pr create` succeeds)
  rather than trying to inline it.
- **Finishing a branch via "push and create a PR," then continuing documentation work in the SAME
  session after the PR merges, requires a second, fresh worktree** — the first worktree's branch is
  now a merged, closed PR branch; `git status`/`log` on it will look correct but it is not the
  place to make new commits. `EnterWorktree` refuses to create a second worktree while a session is
  still inside its first one — `ExitWorktree` (with `action: "keep"`, not `"remove"`, since the
  tool will otherwise ask for confirmation about discarding commits it thinks might be unmerged)
  before creating the next one.

## Definition of done (the whole programme, not any one package)

1. All 328 findings closed — each verified by the mechanism its plan names. P3's own 22, P12's own
   16, P4's own 26, P5's own 15, and now **P6's own 18** (all 20 executed tasks + the final
   review's 3-Important fix wave, confirmed by its own mandatory final review, re-reviewed clean)
   are confirmed closed independently by each package's mandatory final review. **Running total:
   P0+P1+P2+P3+P4+P5+P10+P11+P12+P6 merged; P7's own 14 (B-01 through B-25 subset, D-03, F-67, F-69)
   are next.** Count each package's own total from its merged PR, not from memory. One caveat
   carried forward from P6: B-25 is only PARTIALLY P7's — see "Carried-forward open items" #3 above.
2. Both suites green everywhere they can be: root suite target ~445-446/1 (the one documented
   T6R-02 exception); app suite target keeps the same 31 pre-existing failures until a dedicated
   follow-up closes them (see "Carried-forward open items" above). The passed count on both suites
   will keep climbing as each package adds its own regression tests — track failures by name, not
   the passed count, when checking whether a session's work is "the same baseline."
3. CI exists (3 jobs, from P0) — **but is NOT green, and has not been since before P3's merge**,
   confirmed again this session (`gh run list --branch main --limit 5`, all recent merges show
   `failure`, including P6's own merge commit). The cause is exactly the same pre-existing
   root-suite and app-suite failures every resume prompt has documented as deliberately out of
   scope — the CI job hard-fails on any non-zero pytest exit code with no allowance for the
   documented baseline. This is a real, standing gap in the programme's own definition of done, not
   a P7 concern specifically, but worth naming again for whichever session eventually closes the
   pre-existing failures or decides the CI job should tolerate a documented allowlist instead.
   Re-run `gh run list --branch main --limit 5` yourself at session start rather than trusting this
   note.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error events row.
   **This is directly P6/P7/P8's territory (Wave B4 is Discovery) — P6 delivered the typed
   exceptions and the adapter-side half; P7 delivers `drain_diagnostics()`/`preflight()` as seams;
   P8 is where this item actually closes, by wiring both packages' seams into the engine's run
   loop and the `events` table.**
6. Gate C rejects a malformed shot heading — done, verified end to end.
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing — the F-64 atomic rename is P8's
   task (Wave B4, lands after P6 and P7 per the ordering constraint above).
