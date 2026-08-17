# Resume prompt — audit-remediation programme, start P9 (Wave B4, last of four)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-17. **P8 (Engine & Cron) is merged into `main`**
([PR #48](https://github.com/happydotemdr/ContentStudio/pull/48), merge commit `deb196f`).
Combined with P0, P1, P2, P3, P4, P5, P6, P7, P10, P11, P12 already in `main`, **Wave B4's first
three packages (P6, P7, P8) are done. P9 is the last package in Wave B4 — land it and Wave B5
(P15) is next.**

**Business value of P9, in one paragraph:** P8 made the discovery *run* itself trustworthy — a
scheduled run now fails loudly with a contracted exit code and a durable event, instead of
reporting success no matter what happened. P9 closes the last gap: the *email that reports the
run* is not yet trustworthy in the same way. Today a quiet day (healthy roster, nothing new) and a
broken collection (every file unreadable, or the roster silently empty) render the **identical**
five-word body — `No new content today.` — with no `[ISSUE]` prefix distinguishing them. And a
*failed send* produces no email at all, which looks exactly like a cron that never fired. P9 makes
the digest email as honest as P8 made the run: a coverage footer on every email states what was
scanned and how it resolved, a failed send writes its own `events` row, and 22 other findings close
gaps in disclosure accuracy, drafting isolation, and platform parity. This is the last package in
the Discovery wave — after P9, the whole subsystem (adapters, engine, email) tells the truth
end-to-end.

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
P9 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

**Start P9 in a fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not
reuse P8's worktree/branch (`worktree-p8-engine-cron`), which is merged, closed, and being cleaned
up. `origin/main` at merge commit `deb196f` already contains every fix P8 landed.

**If you are already inside a worktree session when you start**, `EnterWorktree` refuses to create
a second one directly — `ExitWorktree` first (`action: "keep"` if the current worktree's branch is
not yet merged and you might need it again; `"remove"` only after confirming its branch is merged).
**Known friction this session hit:** the harness's worktree-boundary guard now also blocks `git -C
"C:/Projects/ContentStudio" <command>` redirects from inside a worktree-isolated session (it did
not block this in the P8 session, per that session's own carried-forward note — the guard appears
to have tightened). If you need to touch the main checkout while worktree-isolated and `git -C`
is refused, use `ExitWorktree` first (the branch-merge check applies as above), or fall back to
absolute-path Read/Write/Edit calls for file edits (those still work) and defer any main-checkout
git operation (fetch/merge/branch cleanup) until you've exited the worktree.
**Also hit this session:** after a worktree's branch merges, `ExitWorktree action: "remove"` may
report "N commits on this branch, confirm with the user" even though the branch is genuinely
merged (the tool compares against its own recorded base, not against `origin/main`) — verify the
merge yourself first (`gh pr view <N> --json state,mergedAt,mergeCommit`), then re-invoke with
`discard_changes: true` once you've confirmed it's safe. The tool may still fail to delete the
directory afterward with "Device or resource busy" (Windows file-lock, session still physically
inside it) — the git-side worktree registration is what actually matters and gets cleaned up
regardless; the stray directory needs manual `rm -rf` from a *different* session once this one
ends, same as the documented merged-worktree-directory trap below.

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed
editable) **is now caught up to `origin/main`** as of this session (fast-forwarded to `deb196f`,
verified clean fast-forward, no conflicts). It may still have uncommitted operator work in
progress unrelated to this programme — re-run the fetch+status check yourself at the start of your
session before assuming anything (`git fetch origin main && git status --short && git log
--oneline -3`, run from the main checkout, not `-C`'d from a worktree per the note above) — **do
not `git pull`/`merge`/`reset` there yourself if it has uncommitted changes that look like real
work; ask the operator.** As of this session, the main checkout carries the same unrelated WIP
noted in every prior resume prompt: a Firecrawl retry/backoff change in `doc-ingest-app/`
(uncommitted — see `docs/superpowers/plans/2026-08-17-doc-ingest-retry-backoff-closeout.md` for
its own standalone close-out prompt if the operator wants it finished), plus a handful of untracked
operator files (`pipeline-app/pipeline.db.backup-*`, `rgs-briefs/*.md`,
`docs/superpowers/plans/2026-08-16-ci-test-suite-recovery.md`) — none of these are this programme's
concern; leave them alone unless the operator asks. **A stray `pipeline-app/scripts/` directory
(just an empty `__pycache__/`, untracked/gitignored) was found and deleted from the main checkout
this session** — a harmless leftover from before P8's F-64 rename, but if you ever see
`test_the_f64_scripts_rename_has_landed_completely` fail locally with `scripts_dir.exists() ==
True`, check for exactly this before assuming a real regression: `ls pipeline-app/scripts/` and
`rm -rf` it if it's `__pycache__`-only.

**Baseline suite counts, verified this session at `origin/main`'s `deb196f` (P8 merged):**
- Root suite (`python -m pytest tests/ -q` from repo root): **445 passed, 1 skipped, 0 failed.**
  Fully green.
- App suite (`cd pipeline-app && python -m pytest -q`): **1781 passed, 4 skipped, 0 failed.**
  Fully green. **There is no documented pre-existing-failure baseline to tolerate on either
  suite.** Any failure you see is new — treat it as a real regression, not "the same old ones."
- CI (`gh run list --branch main --limit 5`): **green** — P8's merge commit (`deb196f`) shows
  `success` on all three jobs (`app-suite`, `root-suite`, `no-live-credentials`), the second
  fully-green merge in this programme's history (after P7's). Re-verify yourself at session
  start; don't trust this as gospel across sessions.
- **A separate, unrelated local-only failure exists in the repo root's own tooling suite** (not
  this programme's): `tests/test_build_cowork_plugin.py::test_the_lock_file_matches_the_current_
  skills_tree` and `::test_a_locally_built_artifact_is_not_older_than_the_skills_it_ships` fail
  locally in the main checkout (a Cowork plugin build-lock staleness check against
  `.claude/skills/`, fixed by `bash scripts/build-cowork-plugin.sh` if the operator wants it
  fixed). **Not part of the 445/1/0 root-suite baseline above** — that count already excludes
  these two (run `tests/ -q` and you'll see 2 additional failures beyond the 445/1 baseline
  reported by CI/a worktree, because CI's `dist/`-artifact check no-ops there — see that test's
  own docstring). Do not treat this as a P9 regression if you see it; it was already present and
  is orthogonal to the audit-remediation programme.

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | **merged** |
| B1 | P2, then P10 | **merged** |
| B2 | P3 + P11 + P12 together | **merged** |
| B3 | P4, then P5 | **merged** |
| B4 | P6 (**merged**), P7 (**merged**), P8 (**merged**), **P9** | **P6, P7, P8 done. P9 has not started — start it now.** |
| B5 | P15 | not started |
| C | P13, then P14 | not started |

**Why P9 is next, precisely:** the master plan's wave table
(`docs/superpowers/plans/2026-08-08-audit-remediation.md`, search "Wave B4") puts P6/P7/P8/P9 in
one wave with the note *"P9 is independent"* — it does not consume any seam from P6/P7/P8, unlike
P8 which needed both of those merged first. P9's own plan states its actual dependency precisely:
**P0** (`conftest.py`'s network guard) **and P1** (`obs.py`, the `events` table, the `handles`
platform CHECK) — both merged since Wave A. P9 was simply next in file order once its true
dependencies were satisfied, and Wave B4 (P6→P7→P8→P9) is now the completion order, not a strict
prerequisite chain for this last package.

## What P9 is — read `docs/superpowers/plans/remediation/P9-digest-email.md` in full before dispatching Task 1

**Do not act from this summary alone** — it is oriented for triage, not execution, and the plan
file is long (2186 lines, 26 tasks). Read the actual plan file yourself, following this
programme's Sub-agent output contract (never hand a sub-agent the whole plan file — extract only
what each task needs, same discipline every prior package used).

**The defect P9 exists to close:** a quiet day and a broken collection are the same email. Zero
items with a healthy roster, and zero items because every file was unreadable or the roster was
empty, both render the identical five-word body `No new content today.` with no `[ISSUE]` prefix.
A *failed send* produces no email at all — indistinguishable from a cron that never fired. Task 15
is the pair test that makes the first impossible; Task 16 is the `events` row that makes the
second impossible.

**Scope — files owned by this package, no other package may touch them:**
```
pipeline-app/pipeline_app/discovery_digest.py
pipeline-app/pipeline_app/email_render.py
pipeline-app/pipeline_app/discovery_notify.py
pipeline-app/pipeline_app/comment_draft.py
pipeline-app/tests/test_discovery_digest.py
pipeline-app/tests/test_email_render.py
pipeline-app/tests/test_discovery_notify.py
pipeline-app/tests/test_comment_draft.py
```

**Findings closed here (24):** B-90 through B-112, D-54. Highest severity is **S2** (B-90, B-91,
B-93, B-94, B-95, B-99, D-54) — P9 has no S0/S1, unlike P8's four S1s. The finding→task map is in
the plan's own §2 table (24/24 coverage, confirmed). 26 tasks total (T1–T24 close the 24 findings
1:1 or in small groups; T25 pins the disclosure-accuracy behavior B-90/B-91 close on; T26 publishes
D-54's containment primitives).

**Suite:** app suite only (`cd pipeline-app && python -m pytest -q`) — P9 touches no root-suite
files. Targeted command from the plan's own §1:
```bash
cd pipeline-app && python -m pytest tests/test_discovery_digest.py tests/test_email_render.py tests/test_discovery_notify.py tests/test_comment_draft.py -q
```

### CRITICAL — verify this before dispatching P9's Task 16: P9's plan text is STALE about what P8 already shipped

P9's plan (`§6.1 → P8`) was written **before** P8 executed, and it describes a contract P8 "must"
implement that assumes P8's `run_discovery_cron.py` still discards `notify()`'s return value with
a bare `exit_code = 1` on failure, and that P8 will write an `email.notify_raised` event on the
exception path while `discovery_notify.notify()` itself (P9's own Task 16) will own
`email.sent`/`email.send_failed`.

**None of that matches the live, merged P8 code, verified this session.** The actual
`run_discovery_cron.py` (read it yourself, `notify_ok`/`classify_exit` area, roughly lines
177–268):
- Already captures `notify()`'s return value: `notify_ok = bool(notify(conn, repo_root,
  result["run_row_id"]))` — never discarded.
- Already exits via the full `Exit` enum contract, not a bare `exit_code = 1` —
  `classify_exit(result, notify_ok=notify_ok)` returns `Exit.NOTIFY_FAILED` (value `12`, `0xC`)
  on either a `False` return OR a raised exception from `notify()`.
- Already writes **one** event kind for **both** outcomes — `discovery.notify_failed` (severity
  `"error"`), not the plan's proposed `email.notify_raised` / `email.sent` / `email.send_failed`
  three-way split. The `discovery.*` namespace is what P8 actually used throughout (matching
  every other P8 event: `discovery.wake`, `discovery.runs_reclaimed`, `discovery.spawn_requested`,
  etc.) — `email.*` never appears anywhere in the merged code.

**This means P9's Task 16 (`B-94`: "Send failure writes an `error` `events` row") needs a plan
amendment before it's dispatched, not a silent reconciliation.** Two real open questions for the
plan amendment to resolve, not for you to decide unilaterally:
1. Should `discovery_notify.notify()` itself ALSO write `email.sent`/`email.send_failed` rows (as
   P9's plan intends), duplicating information `run_discovery_cron.py` already records via
   `discovery.notify_failed`? Or does P9's Task 16 become a no-op / redefinition now that the
   consuming side already closed this gap?
2. Does P9 adopt the `discovery.*` naming P8 actually shipped (recommended, for consistency with
   every other event this programme has emitted), or does it introduce the `email.*` namespace
   the plan originally proposed, requiring P8's own `discovery.notify_failed` to be renamed to
   match (which P9 cannot do — `run_discovery_cron.py` is P8's owned file, not P9's, so P9 cannot
   touch it even to rename an event kind)?

Read P8's actual Task 5 (in `docs/superpowers/plans/remediation/P8-engine-cron.md`, search "An
unsent email is a non-zero exit and an event row") for the full implemented behavior and its own
test names before amending P9's §6.1. This is exactly the "recurring bug class" item #4 below in
concrete form — a sibling package's plan characterization of another package's state can be wrong
even when nothing about the CODE changed since P9's plan was written, because P8's code didn't
exist yet when P9's plan was written.

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this. P4 hit it **eleven times**
across 20 tasks; P5 hit it **twice**; P6 hit it **once**; P7 hit it **once cleanly**; **P8 hit it
seven times** across 41 tasks (the most of any package after P4) — every single instance was a bug
in the PLAN's own shown/reference code (a missing helper function, a self-contradicting
`escape()`/CDATA choice, a stale premise from an earlier task's restructuring, a raw-vs-decoded
comparison bug, a test mock returning the wrong shape), never a case where the live repo had
silently drifted out from under a previously-correct plan. The mitigation, unchanged since P2:

1. **Grep for every symbol a task's own shown code references** before dispatching it — function
   names, class names, fixture names, other packages' modules — and confirm each either already
   exists live, or is defined within that same task's own text.
2. If something's missing: **amend the plan file FIRST**, as a `>` blockquote note inserted
   directly at the relevant task, **with its own commit** explaining what was wrong and why —
   then dispatch the corrected version. Never fix a gap silently inline without amending the plan.
3. Your own amendments can contain the same class of bug — re-verify their own claims (exact line
   numbers, exact counts, exact function signatures) against the live repo before committing them.
4. **A sibling package's plan can describe a contract that the OTHER package has since implemented
   differently than planned, because that package's code didn't exist yet when this plan was
   written.** P9's own `§6.1 → P8` section is exactly this, found and documented above — verify
   it before dispatching P9's Task 16, do not trust the plan's prose about what P8 "must" do.
5. **A later task can quietly widen what an earlier task's error-handling already covers, INCLUDING
   across the task/final-review boundary itself.** Only the final whole-branch review, reading the
   full cumulative interaction, tends to catch this. **P8's own final review found exactly this
   shape 4 times** (of 6 Important findings) — a CLI tunable threaded to only one of two duplicate
   call sites, a lock-guard that outlived the mode it was meant to protect, a deadline-exceeded
   run creating an unbounded retry loop because the watermark-write's failure-path carve-out
   didn't anticipate it, and a preflight-failure branch that didn't know about a later task's
   failure-counter. **P9's own Tasks 7-8 (B-99: `collect()` classifies and skips reach the email),
   Tasks 11+14 (B-95: coverage counts + footer, paired with T15's distinguishability test), and
   the T19 AST-sweep adoption task (T8, T10, T13, T16, T20, T21 all feed it) are exactly this kind
   of multi-task interaction — walk each cluster end to end at final review time, not just at each
   task's own review.**
6. **A test double's structure can force a change to production code, and that's fine — but write
   the production comment to justify itself first, the test second.**
7. **Verify empirically before writing a brief, not after a fix-loop round.** Cheaper every time
   this programme has measured it — P8's own session confirmed this twice more this round (Task 9's
   CDATA/escape conflict, Task 18's raw-vs-decoded watermark bug — both found by writing a 2-line
   empirical check before dispatching, not after a fix loop).
8. **A mandatory final whole-branch review is not the last line of defense against everything — CI
   on a genuinely different machine is.** Watch the PR's CI checks after pushing, AND after any
   subsequent "sync with main" merge commit — P8's session needed a second CI verification after
   merging an unrelated PR (#47) into the branch post-review, before GitHub would allow the merge.
9. **A named heading style is plan-specific, not tool-default.** Check P9's own heading style
   (`### T1 — ...`, matching P7's convention, per this session's read) against the built-in
   `task-brief` script's `^#+\s+Task\s+N` pattern before trusting it blindly — P9 uses `T1` not
   `Task 1`, so the built-in script will almost certainly need a custom extraction (adapt P7's
   session's approach, which used the same `T1 — ...` style).
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
    P6: 0 Critical + 3 Important + 8 Minor; P7: 0 Critical + 3 Important + 8 Minor; **P8: 0
    Critical + 6 Important + 8 Minor** (all 6 Important were cross-task interaction bugs invisible
    to any single task's own review — see item 5 above — fixed in one consolidated dispatch,
    re-reviewed clean, zero new breakage). Do not skip it, do not shorten it, do not let a clean
    per-task review record talk you out of dispatching it on the most capable available model —
    and do not consider the package done until you've read its PR's CI logs and confirmed all
    three jobs are green (there is no longer a documented pre-existing-failure baseline to fall
    back on — see Baseline suite counts above).

## Carried-forward open items (know they exist; check whether any land in P9's own files)

**Resolved this session, no longer open:**
- All of P8's own carried-forward items are closed by P8's merge — see
  `docs/superpowers/plans/remediation/P8-engine-cron.md`'s own new §8 "Outcome" section for the
  full record if anything ever needs to reference the exact defect/fix pairs.

**From P8's final review (Minor, deferred, not fixed this session — full list in PR #48's body;
none block P9 unless it happens to touch these exact files, which it should not, P9 owns different
files):**
- `discovery_engine.py:923-930`'s comment on the deadline-exceeded watermark carve-out slightly
  overstates its own narrowness (says "instant only, not claiming success" but the call does stamp
  today's local date the same as the success path — behavior is correct, wording is imprecise).
- A handful of cosmetic/typing nits across `discovery_engine.py`, `run_discovery_cron.py`,
  `routes/discovery.py`, `tools/setup_discovery_task.py` — see PR #48's body for the full list if
  ever relevant.

**None of P3/P4/P5/P6/P7's older carried-forward items are load-bearing for P9** unless P9's own
tasks happen to touch the exact same lines (they should not — full historical lists remain in each
package's own merged PR body if needed: P3 #32, P4 #37, P5 #39, P6 #41, P7 #45, P8 #48).

**From the gate-coverage final review (PR #40, unrelated to this remediation programme — still
carried forward, still nobody's job):** three issues in `pipeline_app/migrations.py` and
`pipeline_config.py`. All three dormant against the live `pipeline.yaml`. Neither file is in any
remaining package's owned-file list (P9/P13/P14/P15). Full detail in prior resume-prompt revisions'
git history if anyone ever picks this up.

**`T20` remains parked** (P5's own explicitly incomplete task): `routes/inspector.py:45` needs
`browse_service.sanitize_html`, P15's deliverable (Wave B5, still not started). Not P9's concern.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`),
  not any worktree. Bake an explicit working-directory check (`pwd && git rev-parse
  --show-toplevel && git branch --show-current`) into every dispatch prompt.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8",
  errors="replace"`. **Directly relevant to P9** — `comment_draft.py` shells out to `claude -p`
  as a subprocess (per `CLAUDE.md`'s documented outbound-network exception).
- **Bash resolution on Windows is genuinely two-layered** — never invoke `bash`/`sh` by bare name
  in a `subprocess.run([...])` call.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness. **P9's Task
  21 ("a kill that did not take... is recorded") likely needs this same Windows-safe liveness
  check P8's Task 13 already built for run ownership** — check whether P9 can reuse
  `discovery_engine._process_is_alive` (read its current signature/location before assuming it's
  importable/reusable — it may be private to that module) rather than reimplementing it.
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
  worktree entirely, AND (as of this session) also refuses `git -C <other-path>` redirects from a
  worktree-isolated session** — this is a change from what P8's own resume prompt reported working;
  re-verify at the start of your session rather than trusting either claim. Absolute-path
  Read/Write/Edit calls still work regardless. Running the ROOT suite from a Bash tool whose cwd
  had drifted into `pipeline-app` silently shadows the root `scripts/` package with
  `pipeline-app`'s own (well, `pipeline-app/tools/` now, post-F-64 — the collision this specifically
  guarded against is gone, but the general cwd-drift risk for other commands remains) and produces
  a `ModuleNotFoundError` that looks unrelated — `cd /path/to/repo-root && python -m pytest tests/
  -q` in one call is the reliable fix.
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
  **P9's own `§6.1 → P8` staleness (documented above) is exactly this shape — do not silently
  decide the naming/duplication question yourself; amend the plan with the two options stated and
  get a decision before dispatching Task 16.**
- **Once both suites are fully green, there is no longer a documented baseline to distinguish "the
  same old failures" from "a new regression."** Any test failure from this point forward in the
  programme is real until proven otherwise — do not assume it's pre-existing. The one exception is
  the local-only `test_build_cowork_plugin.py` staleness noted above, which is orthogonal to this
  programme and was present before P9 started.
- **`gh pr create --body-file` plus a manually-authored `.md` file works cleanly** for a PR body
  with backticks/code blocks — write the body to a scratch file (this programme puts these under
  the worktree's own `.superpowers/` directory, git-ignored) and delete it after `gh pr create`
  succeeds.
- **Finishing a branch via "push and create a PR," then continuing work in the SAME session after
  the PR merges, requires a second, fresh worktree** — the first worktree's branch is now merged
  and closed. `ExitWorktree` (`action: "keep"`) before creating the next one. **After a worktree's
  branch is merged, `git worktree remove` may fail with "Permission denied" if the session is still
  physically inside that directory** (Windows file-lock, not a git problem) — the git-side
  registration can still be removed (it'll disappear from `git worktree list` even if the
  directory itself lingers on disk); the orphaned directory needs manual deletion once the session
  that was inside it ends, or from a different session. **P8's worktree directory
  (`C:\Projects\ContentStudio\.claude\worktrees\p8-engine-cron`) is one such orphan as of this
  session's end** — safe to `rm -rf` from a fresh session once confirmed no longer in use.
- **GitHub can report a branch "out-of-date with base" even mid-review**, if an unrelated PR
  merges to `main` while your PR is open. Fix: `git fetch origin main && git merge origin/main`
  on the feature branch (not a rebase — this programme's convention is merge commits, per every
  prior "Merge origin/main into ..." commit in the history), re-run both suites, push. This
  triggers a fresh CI run on the merge commit — wait for it before considering the PR
  mergeable, same as the original review.

## Definition of done (the whole programme, not any one package)

1. All 328 findings closed — each verified by the mechanism its plan names. P3's own 22, P12's own
   16, P4's own 26, P5's own 15, P6's own 18, P7's own 14, and now **P8's own 31** (plus 5 inbound
   seam obligations and 1 plan-amendment task, not separately counted) are confirmed closed
   independently by each package's mandatory final review. **Running total:
   P0+P1+P2+P3+P4+P5+P10+P11+P12+P6+P7+P8 merged; P9's own 24 are next.** Count each package's own
   total from its merged PR, not from memory.
2. **Both suites are fully green with no documented exceptions** — root suite 445 passed/1
   skipped/0 failed; app suite 1781 passed/4 skipped/0 failed, as of P8's merge (`deb196f`). Track
   any future failure as real (except the one local-only Cowork-plugin staleness noted above,
   which predates and is orthogonal to this programme).
3. **CI is green** — `gh run list --branch main --limit 5` showed `success` on P8's merge commit,
   the second fully green CI run in this programme's history (after P7's). Re-verify at session
   start; confirm it stays green after P9 merges.
4. Every S0/S1 has an observed-failing-first regression test. (P9 has no S0/S1 findings — its
   highest severity is S2 — so this item is trivially satisfied for P9's own scope, but re-verify
   nothing in P9's 24 findings was mis-classified before assuming so.)
5. A scheduled discovery run with an injected fault exits non-zero with an error `events` row —
   **closed by P8**, confirmed via its own final review and CI.
6. Gate C rejects a malformed shot heading — done, verified end to end.
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing — **P8's Task 40 closed the code
   side** (`git grep` under `pipeline-app/` itself returns nothing); doc references at the repo
   root (`README.md`, `CLAUDE.md`) remain and are explicitly **P14's handoff**, not yet done.
8. **New, P9's own contribution to programme-wide honesty:** a quiet day and a broken collection
   render distinguishable emails (Task 15's pair test), and a failed send is itself surfaced as an
   `events` row (Task 16) — the last piece of "the operator finds out when something is wrong"
   that P8's Business Value paragraph promised for the whole Discovery wave.
