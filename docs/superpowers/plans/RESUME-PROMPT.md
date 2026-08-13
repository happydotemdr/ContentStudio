# Resume prompt — audit-remediation programme, P3 (T1 → T24), mid-package

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, where it must stop, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-13, mid-P3-execution: T1, T2, T2B, T3, T4 and T6 are done and merged into
this branch (not yet into `main` — P3 opens its own PR only once the whole package is complete,
matching every prior package's shape). Paused by explicit operator request mid-package, at a
clean point (no partial commits, no open fix loops, both suites verified green-for-this-package).

---

/superpowers:subagent-driven-development

You are resuming a fully-planned, already-validated **328-finding audit-remediation programme**.
Do not re-plan and do not re-audit.

**You are the orchestrator, not the implementor.** Give sub-agents only the context they need —
never share full context windows back and forth, never hand one the audit or another package's
plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation accurate
and the plan updated at every step. When you find a new gap or defect, **file it in the relevant
plan for review/validation before addressing it**, and only fix it inline if it is a critical or
important blocker. (This session did exactly that three times — see "Plan amendments made this
session" below — and it is very likely you will find more as you continue T5 onward; the pattern
is: verify empirically against the live repo, amend the plan file with a `>` blockquote note and
its own commit, then dispatch.)

## The repo

Worktree: `C:\Projects\ContentStudio\.claude\worktrees\pipeline-audit-review-4dd767`
Branch `claude/pipeline-audit-review-4dd767`. Main branch `main`. Windows 11, PowerShell primary.
Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation programme).

**Read these files before doing anything else:**

1. `docs/superpowers/plans/EXECUTION-KICKOFF-PROMPT.md` — the governing brief. Still binding.
2. `docs/superpowers/plans/remediation/P3-gates-approval.md` — the plan being executed. **This
   session amended it three times** (see below) — read the whole file, including the `>`
   blockquote amendment notes under T2, T2B and T7, not just the task list. Do not skip them;
   they change what T2B/T6's actual dispatch order must be and what T7's own scope now includes.
3. `.superpowers/sdd/P3-gates-approval/progress.md` — this package's own workspace ledger. Trust
   it over your own recollection; it has one entry per completed task plus a `## PAUSED here`
   section at the bottom explaining exactly why and how this session stopped.

## Where execution is

P0, P1, P2, P10, P11 — all complete and merged into `main` (unchanged from before this session;
see prior resume-prompt history in git log if you need those details, they are not repeated here).

**P3 is mid-execution, on this branch, not yet merged, no PR open yet.** Of P3's 25 task blocks
(T1, T2, T2B, T3, T4, T5, T6, T7, T7B, T8, T9, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19,
T20, T21, T22, T23, T24 — T7B is new, added by this session, see below):

**Done, reviewed clean, committed** (commit range `151a3b2`..`e8edfd6` on this branch):
- `f45f742`, `89c8966`, `4cb251f` — three plan-amendment commits, docs only, see below.
- `e523224` — T1+T2 (`fix(gates): require an upstream map at every run_gates_for_stage call site`)
- `8d44c95` — T6, dispatched **early**, before T2B (see amendment below) (`fix(gates): give Gate
  C's input errors a check id and a CLI cross-reference`)
- `d92e406` — T2B (`fix(gates): make a filtered-out upstream a third state, not an absent one`)
- `23ae7e0` — T3 (`fix(stages): recompute depends_on on the hand-edit path`)
- `e8edfd6` — T4 (`fix(stages): gate hand edits on a private scratch file`)

**Not started:** T5, T7, T7B, T8, T9, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20, T21,
T22, T23, T24 (20 task blocks remain).

**T5 has a ready-to-use brief already written**, deliberately scoped to its first two tests only:
`.superpowers/sdd/P3-gates-approval/task-5-brief.md`. Its third test
(`test_hand_editing_a_styleboard_runs_the_styleboard_gate`) depends on the styleboard gate T8/T9
add — do not write it until after T9 lands, exactly as the plan's own text anticipates ("Sequence
T5's third assertion after T9 if executing strictly in order"). **Dispatch this brief as-is to
start T5** — it was fully prepared and never actually dispatched (see "What happened at the pause
point" below).

Suites, verified this session on the current branch HEAD (`e8edfd6`), not assumed:

- Root suite (`python -m pytest tests/ -q` from repo root): **355 passed, 1 failed.** The one
  failure (`test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[fenced-heading]`) is the
  same pre-existing, documented, deliberately-deferred finding (T6R-02) as every prior session —
  not P3's file, not P3's problem.
- App suite (`cd pipeline-app && python -m pytest -q`): **1110 passed, 33 failed, 3 skipped.** All
  33 are the same pre-existing, documented P2-fallout signature mismatches
  (`write_pointer() missing 1 required positional argument: 'repo_root'` and siblings) in files
  P3 doesn't own yet at this point in the package (`test_approval_service.py`,
  `test_browse_service.py`, `test_discovery_digest.py`, `test_routes_browse.py`,
  `test_routes_chat_sse.py`, `test_routes_stages.py`, `test_stubbed_cli_e2e.py`). **T23/T24 are
  what close these** — they haven't run yet, so the count hasn't started dropping. Confirm this
  count actually falls once you land T23/T24; don't assume it did.

## Plan amendments made this session (read the plan's own blockquotes for full detail)

All three are docs-only commits, already pushed. Each is a `>` blockquote inserted directly into
`P3-gates-approval.md` at the relevant task, so the plan file itself stays the single source of
truth — this section is a pointer, not a duplicate.

1. **`f45f742` — a confirmed gates.py parity gap, added task T7B.** P11's own plan
   (`P11-gate-c.md` §6.2) lists six "what P3 must change for full parity" requirements
   (`P3-1`..`P3-6`); P3's plan text (even after last session's Handoff H1b) only carried `P3-6`
   forward. Verified empirically: `P3-1` (consume `parse_sheet(...).findings`), `P3-2`
   (`declared_shot_count`), and `P3-3` (`parse_style_library_checked`) are all still missing from
   the live `gates.py` — meaning **the app-side Gate C still has the flagship
   fail-open-on-malformed-heading defect P11 advertises as fixed**, just on the code path every
   real app run actually takes (the CLI's `main()` is never invoked by the app). New task **T7B**
   closes all four (`P3-1`/`P3-2`/`P3-3`/`P3-6`) together, sequenced right after T7 since it
   depends on T7's differential-test harness. This is real, unstarted work — do not skip it.
2. **`89c8966` — T2's forward-reference to P4's not-yet-existing `_approved_artifact_path`.** T2's
   original text said to lift this helper "verbatim from P4's T6" — but P4 has not executed this
   session (P3 runs alone, before P4, per the landing order), so there was nothing to lift.
   Amended T2 to have the implementer write it fresh in `gates.py`. **Already executed** — the
   function exists in `gates.py` now, written from scratch, tested. Nothing further to do here;
   flagged for completeness since it's the kind of thing worth knowing if P4 later needs to
   reconcile with it.
3. **`4cb251f` — T2B's undeclared forward dependency on T6.** T2B's own test code references
   `gates.GateInputError` and requires `run_gates_for_stage`'s handler to already use
   `getattr(exc, "check", "GATE")` — both are **T6** changes, and T6 is textually sequenced after
   T2B/T3/T4/T5 in the plan. **Corrected dispatch order: T6 runs immediately after T2, before
   T2B** (already executed this session, in that order). Task *numbers* are unchanged; only
   dispatch order differs. **If you are tempted to dispatch tasks in strict textual/numeric
   order, don't — re-check every remaining task for a similar forward-reference before dispatching
   it**, the way this session did for T2B. This class of bug (a task's test code referencing a
   symbol/behavior a later-numbered task introduces) has now been found twice in this package
   alone; assume it can happen again in T8 onward and verify empirically, the same way, before
   each dispatch.

## What happened at the pause point (why T5 shows "brief written, not dispatched")

The operator asked to pause mid-package. At that moment a dispatch for T5 had just been sent and
was interrupted before the subagent produced a report. The partial file edit it left behind in
`pipeline-app/tests/test_routes_approve_edit.py` was **untested and unreviewed** (no
`task-5-report.md` was ever written, confirming the subagent did not reach that point) — it was
discarded with `git checkout --` before this pause so the branch stays clean. **This is not a
regression or lost work**: `task-5-brief.md` is intact and is the exact same content: re-dispatch
it fresh, following the normal implementer → review → ledger-append loop, exactly as every prior
task in this package did. Do not assume any T5 code exists on disk; verify with `git status` and
`git log` before trusting this document's own claim, the same discipline this whole programme is
built on.

## Sync check, run this session (paste the actual output into your own final report at the next
## pause point too — this is a mandatory, repeatable step, not a one-off)

```
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767"
git status --short                                    # confirmed empty at pause
git push origin claude/pipeline-audit-review-4dd767    # confirmed "up to date" (already pushed: e8edfd6)
git rev-parse HEAD origin/claude/pipeline-audit-review-4dd767   # confirmed identical: e8edfd6...
```

**The MAIN checkout** (`C:\Projects\ContentStudio`, separate from this worktree — where
`pipeline-app` is installed editable) was checked this session: `git fetch origin` then
`git status --short` shows it is **2 commits ahead of `origin/main`**
(`1242626 docs(specs): add Freedom2BeU document-ingest design spec` and
`4c12a48 docs(specs): fix correctness gaps in the doc-ingest design spec`), plus a handful of
untracked files (`pipeline.db.backup-pre-migration*`, two `rgs-briefs/*.md` drafts, one more
untracked spec doc). **This is the operator's own unrelated work in that checkout between
sessions — not P3's concern, not broken, nothing to fix.** `origin/main` is NOT ahead of the main
checkout (verified: `git log HEAD..origin/main` is empty), so nothing is missing there either.
Re-run this same fetch+status check at the start of your session regardless — do not assume it
stayed exactly as described here; the operator's own activity between sessions is real and this
exact check has caught real drift before (see the P2→P3 resume prompt's own history for the
100-commits/one-unpushed-commit incident this check exists to prevent).

**No PR is open for P3 yet** (`gh pr list --head claude/pipeline-audit-review-4dd767 --state all`
— the most recent, #30, was the *previous* session's RESUME-PROMPT-only update, already merged).
Do not open one until P3's own final whole-branch review is clean, per "THE PAUSE / COMMIT / PR
POINT" below — same as every prior package.

## YOUR TASK THIS SESSION: finish P3 (T5 → T24), then STOP

Start by re-dispatching T5 from its already-written brief
(`.superpowers/sdd/P3-gates-approval/task-5-brief.md`). Then continue straight through T7, T7B,
T8, T9, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20, T21, T22, T23, T24, in that order —
**except** watch for the same class of forward-reference bug this session found twice (T2's
`_approved_artifact_path`, T2B's `GateInputError`). Before dispatching each task, do a quick
empirical check: does the task's own shown test/implementation code reference any function, class,
or fixture that doesn't exist yet at that point in the dispatch sequence? `grep` for it. If it's
missing, amend the plan (a `>` blockquote note plus its own commit, exactly like the three
examples above) before dispatching — don't let an implementer discover it as a `NameError`.

Follow the `superpowers:subagent-driven-development` skill's full loop for each task: dispatch a
fresh implementer (model `sonnet` for anything with real design judgment — which is most of what's
left; only genuinely mechanical single-file tasks like T22 or T14 might tolerate a cheaper tier,
your call), generate a review package (`scripts/review-package` from the skill's own directory,
BASE = the commit before that task's dispatch), dispatch a task reviewer, and only mark a task
complete in the ledger once its review is clean or its findings are fixed-and-reverified. Append
one line per completed task to `.superpowers/sdd/P3-gates-approval/progress.md` as you go — that
file is what survives compaction, not your own memory of this session.

**Two operator decisions are still open from P11's session, unresolved, not yours to silently
answer** — surface them again if the operator hasn't weighed in, exactly as the last three resume
prompts have each had to repeat:
1. T21R-01 — the `CLOSE`/`MACRO` 1-object-floor carve-out in Gate C's C8 check (P11's file, not
   P3's, but P3's T2 already had to work around its consequence in `test_gates.py` — see this
   session's own fix, already landed).
2. T6R-02 — what, if anything, should catch an extra fenced example block mid-sheet (the root
   suite's one documented failure). Not P3's file at all.

## THE PAUSE / COMMIT / PR POINT: end of P3, before P12

Unchanged from the brief that started this session — reproduced here so this document stays
self-contained:

Stop when P3's own final-review fix wave (if any) is clean. Then: run both suites, confirm the
app-suite failure count actually dropped from adopting P2's frozen API via T23/T24 (don't just
assume it did), push, and open a PR titled for P3's completion, same shape as PR #28/#29's
bodies — findings closed, suite numbers, what the operator will notice on next boot, what is
knowingly still open. **Do not start P12 in this session** — P12 T8 leaves a deliberate
`xfail(strict=True)` tripwire that only resolves once P3 changes `gates.py` to derive `blocking`
from a `kind` vocabulary rather than a hardcoded string; confirm P3's own T10 (`classify_gates`)
actually did this before assuming P12 is safe to start in a future session. Update this file
(`RESUME-PROMPT.md`) at that pause point.

Run the full local/remote sync check (see above) before declaring the pause point reached, and
paste the actual output into your own final report — don't just assert it's clean.

**A mandatory final whole-branch review, on the most capable available model, blind to every
task's own review, is not optional.** P10's own proactive pass found 15 new findings including 2
Critical ones that predated the whole package; P11's found 6 more including 2 genuine live defects
in code every prior per-task review had separately approved. Dispatch one fix wave for whatever it
finds (one subagent, the complete findings list, not one fixer per finding), then one scoped
re-review of that fix wave. This has caught real, load-bearing bugs in every single package
executed so far — do not skip it because the per-task reviews already looked thorough. This
session's own per-task reviews (T1+T2, T6, T2B, T3, T4) were all independently thorough and each
re-ran the suite itself rather than trusting the implementer's self-report verbatim — keep that
standard for the remaining tasks, and do not let the final review's existence become a reason to
relax any individual task review along the way.

## The bar, restated because it is what everything else serves

"Any representation shared by 'nothing here' and 'something is wrong' is a defect by default."
This root cause has now appeared, by the controller's own count, in 50+ confirmed instances across
P0–P11, the large majority written by the remediation itself, not the original bugs. Expect the
same pattern in the rest of P3 — T10's `classify_gates` (a never-ran gate must not render as a
clean pass), T18's three defensive early returns (each must say *which* reason fired, not just
return silently), T19 (an expected failure must re-render the real page with a banner, never a
bare text response) are all exactly this shape, and are all still ahead of you.

For every `silent` finding, the Three-Test Rule is mandatory: fault, distinguishability,
surfacing. Surfacing means an events row, a non-zero exit code, or a rendered UI element —
asserting that a `print()` happened does not count.

Coverage is not the bar. The bar is: for each finding, a named test that fails before the fix and
passes after — and you must actually observe the failure. Every task this session ran did observe
it; each implementer's report and each reviewer's independent re-run confirmed the specific
failure text before the fix landed. Keep doing this for every remaining task — it is not
optional ceremony, it is the actual verification.

## Process that is mandatory — all of it (unchanged since P0, still binding)

1. Adversarially pre-review the plan's own code before dispatching any implementer. This
   session's own pre-review found the T7B gap and the T2/T2B forward-references *before*
   dispatching a single implementer for those tasks — probe the actual current source
   empirically, don't trust the plan's prose, exactly as documented above.
2. Amend the plan FIRST, then execute the amended step. Every amendment gets its own commit
   explaining what was wrong and why — three examples already in this branch's history
   (`f45f742`, `89c8966`, `4cb251f`) to pattern-match against.
3. Your own corrections will contain the defect they were written to catch — re-verify every
   amendment's own claims (e.g. this session double-checked its own "seven, not six" call-site
   count, and its own message-string claims for the C8 narrowing, against the live linter source
   before writing them into a brief).
4. Check every silent finding's surfacing test for the same-connection read (`tests/test_db.py:339-364`,
   `:663-676` are the reference idiom).
5. Consider a post-implementation adversarial review pass before opening the PR — mandatory at
   the final-review stage (see above), not optional.
6. Model tiers matter. This session used `sonnet` for every implementer and reviewer dispatched
   so far (all judgment-heavy, multi-file, or both) — keep doing that unless a specific remaining
   task is genuinely single-file and fully mechanical.

## Traps, verbatim (carried forward, still binding — re-verify each empirically if new ground is
## touched)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout, not this worktree. Bake an
  explicit working-directory check (`pwd && git rev-parse --show-toplevel && git branch --show-current`)
  into every dispatch prompt — this session's own dispatches all did this from the start.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it. (Note: this session observed `pipeline.db.backup-pre-migration*`
  files as untracked in the main checkout — these are the operator's own backup artifacts, not
  something P3 created or should touch.)
- `subprocess` with `text=True` decodes as cp1252 on this host. Always
  `encoding="utf-8", errors="replace"`.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness.
- Never invoke `bash`/`sh` by bare name in a subprocess. Resolve with `shutil.which()`.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead of an inline heredoc.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field from a filename or frontmatter value.
- In this specific harness, the Bash tool's working directory resets to the worktree path after
  every separate call — `cd` does not persist between calls. Chain multi-step operations touching
  a different directory in one command.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()`
  (not `.fullmatch()`), will silently never capture the optional group. Verify empirically if T8/T9
  or anything else in the remaining tasks parses something with an optional trailing capture.
- When two independently-written pieces of text/code both need to find something via a
  first-occurrence string match, and one can textually contain what the other searches for, they
  will collide. Watch for this in T19/T21's template-context-key work, which touches a lot of
  shared string/dict-key surface.
- **NEW from this session:** a task's own shown test/implementation code can reference a
  function, class, or fixture that a *later-numbered* task in the same plan introduces. Found
  twice this session (T2 → P4's not-yet-existing helper; T2B → T6's `GateInputError`). Grep for
  every function/class name a task's code references before dispatching it, and confirm it either
  already exists in the live repo or is defined within that same task's own text.

## Open findings — filed, NOT fixed, carried forward from before this session (unchanged; see the
## P10/P11-era resume prompt history in git log for the full list if needed — not repeated here to
## keep this document from growing unboundedly). None of them block T5 → T24.

## Definition of done (the whole programme, not this session)

1. All 328 findings closed — each verified by the mechanism its plan names. 90 of 328 done before
   this session; this session's T1/T2/T2B/T3/T4/T6 close A-30, A-31 (app half), A-41, A-45's
   prerequisite work is not yet done (T15/T16 still pending), A-60, A-62, A-64 — **do not update
   the running total in this document until the whole package lands and every finding ID in P3's
   own §2 table is actually confirmed closed by its named task**; a partial-package count invites
   exactly the kind of premature "done" claim this programme's own discipline exists to prevent.
2. Both suites green: `python -m pytest tests/ -q` and, from `pipeline-app/`, `python -m pytest -q`.
   Currently (this session's pause point): root suite 355/1/0 (1 documented exception, T6R-02);
   app suite 1110/33/3 (33 documented pre-existing, expected to drop once T23/T24 land).
3. CI exists (3 jobs) and is green — currently red on `root-suite`/`app-suite` for the documented
   reasons above; resolved incrementally as each remaining package (starting with the rest of P3)
   adopts P2's frozen API and P11's own filed gaps get routed and closed.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error events row.
6. Gate C rejects a malformed shot heading — done, shipped in P11 CLI-side, verified end to end.
   **T7B (still pending this session) is what finally closes the app-side half of this same
   guarantee** — do not consider this item fully done until T7B lands and is reviewed.
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing.
