# Resume prompt — audit-remediation programme, P1 T14 onward

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution actually got to, what the
next session must do first, and everything learned the hard way that is not written down anywhere
else.

Last updated 2026-08-10, after P1 T13b closed and PR #25 merged.

---

/superpowers:subagent-driven-development

You are resuming a fully-planned, already-validated **328-finding audit-remediation programme**.
Do not re-plan and do not re-audit.

**You are the orchestrator, not the implementor.** Give sub-agents only the context they need —
never share full context windows back and forth, never hand one the audit or another package's
plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation
accurate and the plan updated at every step. When you find a new gap or defect, **file it in the
relevant plan for review/validation before addressing it**, and only fix it inline if it is a
critical or important blocker.

## The repo

Worktree: `C:\Projects\ContentStudio\.claude\worktrees\pipeline-audit-review-4dd767`
Branch `claude/pipeline-audit-review-4dd767`. Main branch `main`. Windows 11, PowerShell primary.
Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation programme).

**Read these three files before doing anything else:**

1. `docs/superpowers/plans/EXECUTION-KICKOFF-PROMPT.md` — the governing brief. Still binding.
2. `.superpowers/sdd/2026-08-08-audit-remediation/progress.md` — the ledger. Git-ignored, so it
   exists only on this machine. It is the recovery map: the commits it names exist in `git log`
   even where nothing else remembers creating them. Trust it and `git log` over recollection.
3. `docs/superpowers/plans/remediation/P1-observability.md` — the plan currently being executed.

## Where execution actually is

**P0: complete (23 findings). P1: complete through T13b (13 findings). 36 of 328 closed.**

Suites, verified in both the worktree and the operator's main checkout:
**app 982 passed / 3 skipped / 0 xfailed**, **root 247 passed**, zero warnings, tree clean.
Baseline at programme start was 201 root / 833 app with ~65,700 warnings.

CI exists and is green (3 jobs). It covers more than local — two symlink tests skip on Windows and
execute only on the runner, so a local pass is strictly weaker than a CI pass.

**Remaining in P1: T14, T15, T16, T17, T18.** Then the constrained landing order from the kickoff
brief: B1 (P2, then P10), B2 (P3+P11+P12), B3 (P4, then P5), B4 (P6, P7, P8, P9), B5 (P15),
C (P13, then P14), then the final whole-branch review.

### Git state — read this before your first commit

PR #25 was **squash**-merged into main as `69a834c` on 2026-08-10, despite GitHub labelling it
"Merge pull request #25". Verified by parent count (1, not 2). Consequence: **none of this
branch's 134 commits are ancestors of main.** That was reconciled by merging `origin/main` back
into the working branch at `2295501`, so `git diff origin/main HEAD` is empty and the next PR's
**diff** contains only new work. The commit *list* in a future PR will still show the historical
commits; that is cosmetic and expected. Do not try to "clean it up" by rebasing — the branch
history is where every RED observation and defect rationale lives, and the plan files reference
specific SHAs.

### The operator is now running the app for real

The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` (git-ignored, lives in
the **main checkout**, not the worktree). A backup exists at `pipeline.db.backup-pre-migration`.

A dry run against a copy confirmed migration 1 succeeds on it and preserves every row (5 projects,
31 turns, 15 handles, 36 discovery runs; no ghost platforms, no status coercion needed). Two risks
filed during P1 do **not** fire on this database — it has zero running turns and zero running
discovery runs — but that is luck, not safety.

The boot surfaces **6 pre-existing foreign-key violations** as a `warning` event: historical
`discovery_run_handles` rows referencing handles deleted long ago. Harmless; `ON DELETE CASCADE`
prevents new ones; nothing cleans up the existing six.

**Because the operator is now using the app, a regression in `db.py`, `main.py` or the migration
is no longer theoretical.** Weight your review effort accordingly.

## Your first job

**Task-review nothing. Start T14.** T13b was reviewed and approved (zero Critical/Important, first
pass) before the pause, and every task through T13b is closed with a clean review.

Before dispatching T14's implementer, do the pre-review described below — it has found defects in
the plan's own code in **every single task since T5**, without exception.

## The bar, restated because it is what everything else serves

**"Any representation shared by 'nothing here' and 'something is wrong' is a defect by default."**
169 of the 328 findings are classed silent. If you find a new instance, treat it as in scope, file
it in the relevant plan, and fix it.

The count so far is **~30 confirmed instances, fourteen of them written by the remediation
itself.** That ratio is the entire reason for the pre-review discipline.

For every `silent` finding, the **Three-Test Rule** is mandatory: fault, distinguishability,
surfacing. Surfacing means an events row, a non-zero exit code, or a rendered UI element —
*asserting that a `print()` happened does not count*.

**Anti-tautology:** never assert on a hard-coded value; never assert a mock was called; if a test's
name describes a defect, delete or invert it. A plan must never mandate a tautology and defer the
fix to the implementer.

**Coverage is not the bar.** There is no coverage gate. The bar is: for each finding, a named test
that fails before the fix and passes after — **and you must actually observe the failure.** A test
that passes on first write is a failed task. A red tripwire is success, not regression.

## Process that is now mandatory — all of it

1. **Adversarially pre-review the plan's own code before dispatching any implementer.** Not the
   implementer's output — the *plan's*. It has been wrong in every task since T5: four ways in T6,
   six in T7, four in T8, five in T9, six in T10, five in T11, four in T12, five in T13.
   **Probe SQLite and the filesystem empirically rather than reasoning about them** — beliefs about
   pragmas, transactions, `executescript`, WAL lifecycle and `ALTER TABLE` have repeatedly turned
   out false.
2. **Run `compile_plan.py` on the plan before every dispatch.** It compiles every fenced `python`
   block. It once caught a raw newline in a string literal that would have broken *collection* of
   the entire `test_db.py` module — silently taking ~60 passing tests with it while the suite still
   reported success. It lives in the session scratchpad; if gone, rewrite it, it is 30 lines and
   should `textwrap.dedent` each block. **Expected baseline: 52 blocks, 2 fail** — both pre-existing
   fragments (a diff-style block and a signature block with a `<repo>` placeholder). Anything else
   is yours.
3. **Amend the plan FIRST, then execute the amended step.** Never improvise around a plan defect
   silently. Every amendment gets its own commit explaining what was wrong and why.
4. **Your own corrections will contain the defect they were written to catch.** This happened
   three times: T9's C1 fixed a fresh-database crash and left the legacy-database crash in place;
   T13's C2 told the implementer to verify a precondition while naming a check that holds trivially
   and always; T13b's C4 named one drain site when there were two. **Every time, the implementer
   caught it.** Tell implementers explicitly to report reality rather than matching the brief.
5. **When a fix round produces a NEW instance of the defect class, the signal is about the design,
   not the implementer.** T5's root error was trying to report *what survived*; the fix was to stop
   rendering a verdict, not to write a sixth classifier.
6. **`schema.sql` runs before migrations.** This has now bitten the package five times. Whenever a
   task adds a constraint or index to `schema.sql`, ask what happens when *existing data or an old
   table shape violates it at `executescript` time* — not only what happens inside the migration.
7. **When a task adds N kinds of constraint, apply the fresh/migrated twin discipline N times** —
   per behaviour, not per table. T7 applied it per-table and all four of its `ON DELETE CASCADE`
   clauses could be deleted with 80 tests still passing.
8. **Check every `silent` finding's surfacing test for the same-connection read before dispatch.**
   Reading an `events` row back on the connection that wrote it passes whether or not the row was
   committed. This is now **the single most repeated defect in the programme (4 instances)**.
   `tests/test_db.py` carries the correct second-connection idiom at `:339-364` and `:663-676`.

## Traps, verbatim

- **`python -m` is mandatory.** A bare `pytest` at the repo root reports "201 passed", exit 0, while
  silently omitting all app tests. Run `cd pipeline-app && python -m pytest` and, from the repo
  root, `python -m pytest tests/ -v`. Each suite has its own `pytest.ini` pinning its rootdir.
- **`pipeline-app` is installed EDITABLE against the MAIN checkout**, not this worktree. From
  repo-root cwd `pipeline_app` resolves to the main checkout; from `pipeline-app/` cwd it resolves
  to the worktree. A bare `pytest` in `pipeline-app/` tests the WRONG CHECKOUT (a guard now aborts
  that).
- `subprocess` with `text=True` decodes as cp1252 on this host. Always
  `encoding="utf-8", errors="replace"`.
- `os.kill(pid, 0)` **terminates** the process on Windows. Use `OpenProcess` for liveness.
- **Never invoke `bash`/`sh` by bare name in a subprocess** — CreateProcess consults System32 first
  and finds the WSL stub. Resolve with `shutil.which()` and pass the absolute path.
- **`BRIGHTDATA_API_KEY`, `RESEND_API_KEY` and `YOUTUBE_API_KEY` are set in the ambient
  environment. Bright Data bills per record. Never let a test reach a live vendor API.**
- Writing a commit message through `bash -c "..."` will **eat anything in backticks** as command
  substitution. Use a quoted heredoc (`git commit -F - <<'MSG'`).
- **An apostrophe inside a single-quoted shell block terminates it.** This broke `brief-T.sh` when
  a comment containing "T13's" was added to its awk program.
- **`grep -c` exits 1 when the count is zero**, which silently truncates a `&&` chain. Use `;` when
  chaining checks whose expected answer is zero.
- Opening a WAL database **read-only still creates 0-byte `-wal`/`-shm` sidecars.** Harmless, but
  do not mistake them for evidence the app ran.
- `pipeline.yaml` is at the repo root. App modules are flat in `pipeline-app/pipeline_app/*.py`.
- The linters in the root `scripts/` are stdlib-only and loaded by file path. They must not import
  app code, so they cannot use `obs.py`.
- **Anything non-trivial embedded in YAML is untestable by construction.** Extract it to a module
  with tests. P0 shipped three CI checks that could not fail before this rule was adopted.

## Frozen cross-package interfaces — do not redesign

- `obs.log(event, *, level, **fields)`
- `obs.record_event(conn, *, kind, severity, source, message, detail, run_id) -> int`. **Must never
  raise** — falls back to `log()` and returns `-1`.
- `gates.resolve_upstream_by_stage(...)`
- `| safe` means sanitized by `browse_service.sanitize_html()`
- P3→P15: a blocked approve is a 409 re-rendering `stage.html`
- P1→P15: `recent_events[]`, and `orphaned_count: int | None` where `None` **must render
  differently from `0`** — and note P0 found `doctor.py`'s `getattr(..., 0)` collapses three states
  into two; confirm P1 actually fixed that before closing the contract.
- **The `_MIGRATIONS` contract**, in that list's own comment block in `db.py`: a migration body must
  not call `conn.commit()`, `conn.rollback()`, `conn.executescript()`, open a `db.transaction()`,
  or touch a pragma. `apply_migrations` owns the `BEGIN IMMEDIATE` boundary and all foreign-key
  handling, and **FK enforcement is OFF during a migration**, so `ON DELETE CASCADE` does not fire
  inside one.
- **Migration 1 stays version 1 until it ships.** T6–T13b all built it up; later tasks extend the
  same function. A new rebuild adds statements to a `_MIGRATION_<n>_..._STEPS` tuple and nothing
  else.
- **An index a legacy table shape cannot support does not belong in `schema.sql`.** Both
  `ux_turns_single_running` and `idx_handles_creator` are issued in `init_db` after
  `apply_migrations`, guarded `if not pre_existing:`, with migration 1 owning the migrated copy.
  Do not move them back.

## Open findings awaiting operator validation — filed, NOT fixed

All are recorded in `P1-observability.md` and routed to the packages owning the files. Raise them
when the owning package comes up; do not fix them inline.

1. **`ux_discovery_single_running` (`schema.sql:90`) crashes `init_db`** on any legacy database
   holding two `'running'` discovery runs, before `events` exists — partial schema, no record.
   Same shape as A-71, **pre-existing**. Owned by P6–P9. Not triggered by the operator's current
   database.
2. **An unknown platform posted by hand now returns 500** where the route convention is 400 (P8,
   `routes/discovery.py`).
3. **`discovery_handles.html`'s `<select>` is a fourth unpinned copy of the platform vocabulary**
   (P8/P15). P1 pinned the other three to each other.
4. **`list_handles_for_creator` returns `[]`** for both "creator owns no handles" and "no such
   creator". Graded weaker than its sibling and deferred to the final review.
5. **Migration tests that do not pin `obs.LOG_DIR` write into the real `pipeline-app/logs/`.**
   The directory is git-ignored so nothing fails, which is why it went unnoticed. The fix is an
   autouse fixture in `conftest.py`, which P0 owns.
6. **B-82 is NOT closed.** P1 shipped the storage half (`record_handle_failure`,
   `clear_handle_failures`, the column, the `'failing'` status). **Nothing in production calls
   them.** P8 must call them from the discovery engine's per-handle error and success branches, and
   P15 must render the counter. **The definition of done must check the call site exists, not merely
   that the helper does.**

## The decisions that are NOT yours

**Stop and ask the operator** when you reach these:

- **P10 T4/T6** sets `@bigthink` and `adamgrant.bsky.social` to `included: false` — a change to what
  gets tracked, not a defect fix.
- **P7 §6 C1** adds a per-platform `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` override — the only change in
  the programme that can increase spend.

Two operator items already decided, do not re-ask:

- **T13b's design: option 4, accept and detect** (2026-08-09). The cross-thread write loss is made
  loud, not prevented.
- **CI required checks: deferred to the end of the programme** (2026-08-10), so the check names are
  set against the final job list. The three jobs are green but not required.

A settled precedent worth knowing: **a plan-mandated finding that is an instance of the recurring
defect class does not get escalated.** The governing brief already rules on that category standing.
Escalate plan-mandated findings that are genuine product or policy choices.

## Context discipline — a hard rule

Never give a subagent the audit, another package's plan, or this whole brief. Generate a task brief
with `.superpowers/sdd/2026-08-08-audit-remediation/brief-T.sh <plan> <N> <out>` and pass the path.
Subagent replies must be 8 lines or fewer; their full reports go to files in the SDD workspace.

**`brief-T.sh` was fixed on 2026-08-10** — its heading match previously let `T13` also match
`T13b`, so a brief silently absorbed the following task. If you ever see a brief containing two
task headings, that regression is back.

Review packages come from the skill's `scripts/review-package <plan> <BASE> <HEAD>`. BASE is the
commit recorded *before* dispatching the implementer — never `HEAD~1`, which silently drops all but
the last commit of a multi-commit task.

## Definition of done

1. All 328 findings closed — each verified by the mechanism its plan names, not merely by a helper
   existing (see B-82 above).
2. Both suites green: `python -m pytest tests/ -q` and, from `pipeline-app/`, `python -m pytest -q`.
3. CI exists (3 jobs) and is green.
4. Every S0/S1 has a regression test **observed failing first**.
5. Defect-affirming tests gone or inverted.
6. A scheduled discovery run with an injected fault exits non-zero **and** leaves an error events
   row.
7. Gate C rejects a malformed shot heading.
8. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing.
