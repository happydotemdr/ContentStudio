# Resume prompt — audit-remediation programme, P1 T14 → end of P1

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, where it must stop, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-10, after P1 T13b closed, PR #25 merged, and field finding C-88b was filed.

---

/superpowers:subagent-driven-development

You are resuming a fully-planned, already-validated **328-finding audit-remediation programme**.
Do not re-plan and do not re-audit.

**You are the orchestrator, not the implementor.** Give sub-agents only the context they need —
never share full context windows back and forth, never hand one the audit or another package's
plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation accurate
and the plan updated at every step. When you find a new gap or defect, **file it in the relevant
plan for review/validation before addressing it**, and only fix it inline if it is a critical or
important blocker.

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
3. `docs/superpowers/plans/remediation/P1-observability.md` — the plan being executed.

## Where execution is

**P0: complete (23 findings). P1: complete through T13b (13 findings). 36 of 328 closed.**

Suites, verified in both the worktree and the operator's main checkout:
**app 982 passed / 3 skipped / 0 xfailed**, **root 247 passed**, zero warnings, tree clean.
Baseline at programme start was 201 root / 833 app with ~65,700 warnings.

CI exists and is green (3 jobs). It covers more than local — two symlink tests skip on Windows and
execute only on the runner, so a local pass is strictly weaker than a CI pass.

**PR #25 is merged.** It was **squash**-merged as `69a834c`, so none of this branch's commits are
ancestors of main. That was already reconciled by merging `origin/main` back in, and
`git diff origin/main HEAD` is empty apart from later work. **Do not rebase this branch** — its
history is where every RED observation and defect rationale lives, and the plan files cite specific
SHAs. A future PR will list the historical commits in its Commits tab; that is cosmetic, the diff
is what governs.

## YOUR TASK THIS SESSION: P1 T14 → T18, then STOP

**Start at T14.** Everything through T13b is closed with a clean review.

| Task | Finding | Sev / mode | What it does |
|---|---|---|---|
| **T14** | A-76 | S3 silent | `app_instances` reconcile lease; a second instance skips the sweep **and says so** |
| **T15** | A-83 | S4 docs-drift | one cached live CLI probe feeding both the banner and the `/doctor` panel in a single request |
| **T16** | D-48 | S3 latent | same-origin `Origin`/`Referer` middleware on every mutating request, with an event on rejection |
| **T17** | — | — | `recent_events` on `/doctor` — the surface P15 renders |
| **T18** | F-26 | S2 silent | both mock-echo tests in `test_main.py` replaced with real app-factory coverage |

**T13 already created the FastAPI lifespan.** T14 adds `_release_reconcile_lease` and
`app.state.instance_token` into it — T13 deliberately omitted both, so do not treat their absence
as a defect.

**T16 changes the behaviour of the running app.** The operator is now using it for real, so a CSRF
middleware that rejects legitimate local requests is a live outage, not a test failure. Verify the
app still works end-to-end after it, and say so explicitly in the report.

## THE PAUSE / COMMIT / PR POINT: end of P1, after T18

**Stop when T18's review is clean.** Then: run both suites, confirm green, push, and open a PR
titled for P1's completion. Do **not** start package P2.

**Why this exact point, and not later.** The next wave opens a deliberate red window:

> P2 changes `artifacts.py` in breaking ways (`parse_frontmatter` now raises instead of returning
> `{}`; `record_gate_override` gains a required `at=`; `write_pointer` gains `repo_root`;
> `identify_new_brief` → `classify_brief_change`; `next_version_number`+`write_artifact` →
> `reserve_version`/`write_reserved_artifact`/`release_version`). **P3 and P4 are red until they
> adopt. P2 lands before P3 and P4.**

So between P2 and P4 the suite is **intentionally red** and the app is not in a syncable state. End
of P1 is the last green, fully-usable boundary before that. P1 is additive hardening; P2 onward is
not.

At the pause, the PR body should state plainly: findings closed, suite numbers, what the operator
will notice on next boot, and what is knowingly still open.

## The bar, restated because it is what everything else serves

**"Any representation shared by 'nothing here' and 'something is wrong' is a defect by default."**
169 of the 328 findings are classed silent. If you find a new instance, treat it as in scope, file
it in the relevant plan, and fix it.

The count so far is **~31 confirmed instances, fourteen of them written by the remediation
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
   implementer's output — the *plan's*. It has been wrong in **every task since T5**: four ways in
   T6, six in T7, four in T8, five in T9, six in T10, five in T11, four in T12, five in T13, five
   in T13b. **Probe SQLite, the filesystem and the parser empirically rather than reasoning about
   them** — beliefs about pragmas, transactions, `executescript`, WAL lifecycle and `ALTER TABLE`
   have repeatedly turned out false.
2. **Run `compile_plan.py` on the plan before every dispatch.** It compiles every fenced `python`
   block. It once caught a raw newline in a string literal that would have broken *collection* of
   the entire `test_db.py` module — silently taking ~60 passing tests with it while the suite still
   reported success. It lives in the session scratchpad; if gone, rewrite it (30 lines, and it
   should `textwrap.dedent` each block). **Known-good baselines: `P1-observability.md` 52 blocks /
   2 fail; `P12-gate-d-tools.md` 44 / 5; `P13-skills-contracts.md` 12 / 0.** All of those failures
   are pre-existing fragments. Anything else is yours.
3. **Amend the plan FIRST, then execute the amended step.** Never improvise around a plan defect
   silently. Every amendment gets its own commit explaining what was wrong and why.
4. **Your own corrections will contain the defect they were written to catch.** This happened
   **four times**: T9's C1 fixed a fresh-database crash and left the legacy one in place; T13's C2
   told the implementer to verify a precondition while naming a check that holds trivially and
   always; T13b's C4 named one drain site when there were two; T12's C4 prescribed a scaffold that
   could not reach the dimension it was meant to test. **Every time, the implementer caught it.**
   Tell implementers explicitly to report reality rather than match the brief.
5. **When a fix round produces a NEW instance of the defect class, the signal is about the design,
   not the implementer.** T5's root error was trying to report *what survived*; the fix was to stop
   rendering a verdict, not to write a sixth classifier.
6. **`schema.sql` runs before migrations.** This has bitten the package five times. Whenever a task
   adds a constraint or index to `schema.sql`, ask what happens when *existing data or an old table
   shape violates it at `executescript` time* — not only what happens inside the migration.
7. **When a task adds N kinds of constraint, apply the fresh/migrated twin discipline N times** —
   per behaviour, not per table. T7 applied it per-table and all four of its `ON DELETE CASCADE`
   clauses could be deleted with 80 tests still passing.
8. **Check every `silent` finding's surfacing test for the same-connection read before dispatch.**
   Reading an `events` row back on the connection that wrote it passes whether or not the row was
   committed. This is **the single most repeated defect in the programme (4 instances)**.
   `tests/test_db.py` carries the correct second-connection idiom at `:339-364` and `:663-676`.
9. **Adding a second mechanism that produces the same end state can silently over-determine an
   existing guard.** T13's lifespan made P0's contract test unable to fail for its own reason.
   Whenever a task makes something true by a **new route**, ask which existing test was the only
   thing proving the **old route** still works.

## Traps, verbatim

- **`python -m` is mandatory.** A bare `pytest` at the repo root reports "201 passed", exit 0, while
  silently omitting all app tests. Run `cd pipeline-app && python -m pytest` and, from the repo
  root, `python -m pytest tests/ -v`. Each suite has its own `pytest.ini` pinning its rootdir.
- **`pipeline-app` is installed EDITABLE against the MAIN checkout**, not this worktree. From
  repo-root cwd `pipeline_app` resolves to the main checkout; from `pipeline-app/` cwd it resolves
  to the worktree. A bare `pytest` in `pipeline-app/` tests the WRONG CHECKOUT (a guard aborts it).
- **The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db`** — main checkout,
  git-ignored. A backup is at `pipeline.db.backup-pre-migration`. Never write to either; open
  read-only and copy to scratch for experiments.
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
  not evidence the app ran.
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
- P1→P15: `recent_events[]` (T17 builds it), and `orphaned_count: int | None` where `None` **must
  render differently from `0`**. P0 found `doctor.py`'s `getattr(..., 0)` collapses three states
  into two — confirm that is actually fixed before closing the contract.
- **The `_MIGRATIONS` contract**, in that list's own comment block in `db.py`: a migration body must
  not call `conn.commit()`, `conn.rollback()`, `conn.executescript()`, open a `db.transaction()`,
  or touch a pragma. `apply_migrations` owns the `BEGIN IMMEDIATE` boundary and all foreign-key
  handling, and **FK enforcement is OFF during a migration**, so `ON DELETE CASCADE` does not fire
  inside one.
- **Migration 1 stays version 1 until it ships.** T6–T13b built it up. A new rebuild adds statements
  to a `_MIGRATION_<n>_..._STEPS` tuple and nothing else.
- **An index a legacy table shape cannot support does not belong in `schema.sql`.** Both
  `ux_turns_single_running` and `idx_handles_creator` are issued in `init_db` after
  `apply_migrations`, guarded `if not pre_existing:`. Do not move them back.

## Open findings — filed, NOT fixed, awaiting validation

Recorded in the plans and routed to the packages owning the files. Do not fix inline.

1. **`ux_discovery_single_running` (`schema.sql:90`) crashes `init_db`** on any legacy database
   holding two `'running'` discovery runs, before `events` exists. Pre-existing, same shape as
   A-71. **P6–P9.** Not triggered by the operator's current database.
2. **An unknown platform posted by hand returns 500** where the route convention is 400. **P8.**
3. **`discovery_handles.html`'s `<select>` is a fourth unpinned copy of the platform vocabulary.**
   **P8/P15.** P1 pinned the other three to each other.
4. **`list_handles_for_creator` returns `[]`** for both "creator owns no handles" and "no such
   creator". Deferred to the final review.
5. **Migration tests that do not pin `obs.LOG_DIR` write into the real `pipeline-app/logs/`.**
   Git-ignored, so nothing fails — which is why it went unnoticed. Fix is an autouse fixture in
   `conftest.py`, which **P0** owns.
6. **B-82 is NOT closed.** P1 shipped the storage half (`record_handle_failure`,
   `clear_handle_failures`, the column, the `'failing'` status). **Nothing in production calls
   them.** P8 must wire the discovery engine's error and success branches; P15 must render the
   counter. **The definition of done must check the call site exists, not merely that the helper
   does.**
7. **C-88b (S1, silent) → P12 T1b**, filed 2026-08-10 from a real field failure. `_beat_name`
   returns `None` for both "prose, correctly ignored" and "beat line in a shape I do not
   recognise", so a refused sub-beat line is deleted from the lint surface along with its own word
   budget. Root cause and design: `GATE-D-PARSE-rootcause.md` / `-design.md` in the SDD workspace.
   Verified that P12 T1/T2/T3 do not catch it and none touches `_beat_name` or `SUBRANGE_RE`.
   **Gate C needed nothing new** — P11's C-70 and C-71 already cover its identical twin defects,
   and the root cause independently reproduced both.
8. **The script format is authoritatively defined nowhere → P13.** Four partial definitions
   disagree; the sub-beat grammar exists only in `SUBRANGE_RE` plus six fixture lines; and **the
   `shorts-scripting` skill's own worked example produces 1 VO line and 5 `PARSE` findings under
   its own gate.** Filed adjacent to P13 T7.

## The decisions that are NOT yours

**Stop and ask the operator:**

- **Should label-first sub-beats (`mechanism: (11–18s | 19 words)`) become legal?** A ~4-line parser
  change with zero measured collateral, but a **format** decision to be made once and written down —
  not a parser fix, and not P12's to take. Filed in P13. **Currently pending.**
- **P10 T4/T6** sets `@bigthink` and `adamgrant.bsky.social` to `included: false` — a change to what
  gets tracked, not a defect fix.
- **P7 §6 C1** adds a per-platform `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` override — the only change in
  the programme that can increase spend.

**Already decided — do not re-ask:**

- **T13b's design: option 4, accept and detect** (2026-08-09).
- **CI required checks: deferred to the end of the programme** (2026-08-10).
- **A plan-mandated finding that is an instance of the recurring defect class does not get
  escalated** — the governing brief already rules on that category standing. Escalate plan-mandated
  findings that are genuine product or policy choices.

## Context discipline — a hard rule

Never give a subagent the audit, another package's plan, or this whole brief. Generate a task brief
with `.superpowers/sdd/2026-08-08-audit-remediation/brief-T.sh <plan> <N> <out>` and pass the path.
Subagent replies must be 8 lines or fewer; their full reports go to files in the SDD workspace.

`brief-T.sh` was fixed on 2026-08-10 — its heading match previously let `T13` also match `T13b`, so
a brief silently absorbed the following task. If a brief ever contains two task headings, that
regression is back.

Review packages come from the skill's `scripts/review-package <plan> <BASE> <HEAD>`. BASE is the
commit recorded *before* dispatching the implementer — never `HEAD~1`, which silently drops all but
the last commit of a multi-commit task.

## Definition of done (the whole programme, not this session)

1. All 328 findings closed — each verified by the mechanism its plan names, not merely by a helper
   existing (see B-82).
2. Both suites green: `python -m pytest tests/ -q` and, from `pipeline-app/`, `python -m pytest -q`.
3. CI exists (3 jobs) and is green.
4. Every S0/S1 has a regression test **observed failing first**.
5. Defect-affirming tests gone or inverted.
6. A scheduled discovery run with an injected fault exits non-zero **and** leaves an error events
   row.
7. Gate C rejects a malformed shot heading.
8. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing.
