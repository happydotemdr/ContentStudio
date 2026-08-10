# Resume prompt — audit-remediation programme, mid-P1

Paste the block below into a fresh session. It is self-contained: it assumes zero prior context.
`EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is still
binding verbatim; this document is the delta — where execution actually got to, and what the next
session must do first.

---

You are resuming a fully-planned, already-validated **328-finding audit-remediation programme**.
Execute it with `/superpowers:subagent-driven-development`. Do not re-plan and do not re-audit.

## The repo

Worktree: `C:\Projects\ContentStudio\.claude\worktrees\pipeline-audit-review-4dd767`
Branch `claude/pipeline-audit-review-4dd767`, main branch `main`. Windows 11, PowerShell.
Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation programme).

**Read these three files before doing anything else:**

1. `docs/superpowers/plans/EXECUTION-KICKOFF-PROMPT.md` — the governing brief. Still binding.
2. `.superpowers/sdd/2026-08-08-audit-remediation/progress.md` — the ledger. Git-ignored, so it
   exists only on this machine. It is the recovery map: the commits it names exist in `git log`
   even where nothing else remembers creating them. Trust it and `git log` over recollection.
3. `docs/superpowers/plans/remediation/P1-observability.md` — the plan currently being executed.

## Where execution actually is

**P0: complete.** **P1: T1–T7 closed, T8 implemented but NOT reviewed.**

Suites: **937 app passed / 3 skipped / 2 xfailed**, **247 root passed**. Both green.
Baseline at programme start was 201 root / 833 app.

CI exists and is green (3 jobs). It covers more than local — two symlink tests skip on Windows.

Remaining in P1: **T8's review**, then T9, T10, T11, T12, T13, T13b, T14, T15, T16, T17, T18.
Then the constrained landing order from the kickoff brief: B1 (P2, then P10), B2 (P3+P11+P12),
B3 (P4, then P5), B4 (P6, P7, P8, P9), B5 (P15), C (P13, then P14), then the final whole-branch
review.

## Your first job — do this before anything else

**Task-review T8. Do not start T9.**

T8 is implemented in `b22cee2` and has had no task review. Its implementer deviated from the brief
for a good reason, correctly reported it, and the deviation is structural. The plan file records
it under the heading **"T8 as built"** along with five open questions, none of which anyone has
checked. The implementer's full report is at
`.superpowers/sdd/2026-08-08-audit-remediation/P1-task-8-report.md`.

The short version: `init_db` runs the whole of `schema.sql` through one `executescript()` **before**
any migration. `executescript` aborts on the first failing statement, and DDL auto-commits as it
goes. `events` is defined near the *end* of `schema.sql`, after `turns`. So on a legacy database
holding two `'running'` turns — exactly what T8's own two migration tests construct — schema.sql's
copy of `ux_turns_single_running` raises `IntegrityError` while building itself over the violation.
`init_db` dies, `events`/`handles`/`discovery_runs`/`discovery_settings` are never created, the
database is left partially migrated and durably so, and the migration that would have cleaned up
the duplicates never runs. A boot crash on precisely the databases the task exists to repair.

The fix as built splits the orphan helper into a pure data-repair function and a separate recorder;
`init_db` repairs *before* `executescript` and records *after* it.

**The most important open question**, and the one to point the reviewer at hardest: that repair now
mutates data before `schema.sql`, outside any transaction and outside the migration boundary, on
every boot of a pre-existing database. If `executescript` then fails for any other reason, the rows
were already changed and the events were never written — a silent data mutation with no record,
which is the exact defect class this programme exists to remove.

Generate the review package from `5f8783d..b22cee2` and dispatch a task reviewer with the brief,
the report, and the five open questions.

## The two decisions that are NOT yours

Still unresolved. **Stop and ask the operator** when you reach them:

- **P10 T4/T6** sets `@bigthink` and `adamgrant.bsky.social` to `included: false` — a change to what
  gets tracked, not a defect fix.
- **P7 §6 C1** adds a per-platform `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` override — the only change in
  the programme that can increase spend.

There is also one operator action outstanding: **mark the three CI jobs as required checks** via
branch protection. That is a repo settings change; do not make it without explicit consent.

## Process that was adopted mid-programme — keep doing all of it

This was learned the hard way and is the single biggest quality lever found so far.

1. **Adversarially pre-review the plan's own code before dispatching any implementer.** Not the
   implementer's output — the *plan's* code. It has been wrong in every task since T5. In T6 it was
   wrong in four ways, in T7 six, in T8 four. Probe SQLite empirically rather than reasoning about
   it; several "obvious" beliefs about pragmas, transactions and `executescript` turned out false.
2. **Run `compile_plan.py` on the plan before every dispatch.** It compiles every fenced `python`
   block. It has caught a raw newline in a string literal that would have broken *collection* of
   the entire `test_db.py` module — silently taking ~60 passing tests with it while the suite still
   reported success. It lives in the session scratchpad; if it is gone, rewrite it, it is 30 lines.
   **Eight blocks in `P1-observability.md` fail by design** (partial fragments and indented
   snippets) — that is the expected baseline, not a regression.
3. **When a fix round produces a NEW instance of the defect class, the signal is about the design,
   not the implementer.** T5's root error was trying to report *what survived*; the fix was to stop
   rendering a verdict, not to write a sixth classifier.
4. **`schema.sql` runs before migrations.** This has now bitten the package four separate times.
   Whenever a task adds a constraint to `schema.sql`, ask what happens when *existing data violates
   it at `executescript` time* — not only what happens inside the migration.
5. **When a task adds N kinds of constraint, apply the fresh/migrated twin discipline N times.** T7
   applied it per-table rather than per-constraint-kind, and `ON DELETE CASCADE` fell straight
   through the gap: all four clauses could be deleted with all 80 tests still passing.

## The bar, restated because it is what everything else serves

**"Any representation shared by 'nothing here' and 'something is wrong' is a defect by default."**
169 of the 328 findings are classed silent. If you find a new instance, treat it as in scope, file
it in the relevant plan, and fix it.

The count so far is **26 confirmed instances, eleven of them written by the remediation itself.**
That ratio is the reason for the pre-review discipline above.

For every `silent` finding, the **Three-Test Rule** is mandatory: fault, distinguishability,
surfacing. Surfacing means an events row, a non-zero exit code, or a rendered UI element —
*asserting that a `print()` happened does not count*.

**Anti-tautology:** never assert on a hard-coded value; never assert a mock was called; if a test's
name describes a defect, delete or invert it. A plan must never mandate a tautology and defer the
fix to the implementer — that happened once in T8 and was corrected in the plan, not downstream.

**Coverage is not the bar.** There is no coverage gate. The bar is: for each finding, a named test
that fails before the fix and passes after — **and you must actually observe the failure.** A test
that passes on first write is a failed task. A red tripwire is success, not regression.

## Traps, verbatim

- **`python -m` is mandatory.** A bare `pytest` at the repo root reports "201 passed", exit 0, while
  silently omitting all app tests. Run `cd pipeline-app && python -m pytest` and, from the repo
  root, `python -m pytest tests/ -v`. Each suite has its own `pytest.ini` pinning its rootdir.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always
  `encoding="utf-8", errors="replace"`.
- `os.kill(pid, 0)` **terminates** the process on Windows. Use `OpenProcess` for liveness.
- **`BRIGHTDATA_API_KEY`, `RESEND_API_KEY` and `YOUTUBE_API_KEY` are set in the ambient
  environment. Bright Data bills per record. Never let a test reach a live vendor API.**
- Two untracked `.coverage` files exist at the repo root and in `pipeline-app/`. Leave them alone.
- `pipeline.yaml` is at the repo root.
- The linters in the root `scripts/` are stdlib-only and loaded by file path. They must not import
  app code, so they cannot use `obs.py`.
- Writing a commit message through `bash -c "..."` will **eat anything in backticks** as command
  substitution. Use a quoted heredoc (`git commit -F - <<'MSG'`).

## Frozen cross-package interfaces — do not redesign

- `obs.log(event, *, level, **fields)`
- `obs.record_event(conn, *, kind, severity, source, message, detail, run_id) -> int`. **Must never
  raise** — falls back to `log()` and returns `-1`.
- `gates.resolve_upstream_by_stage(...)`
- `| safe` means sanitized by `browse_service.sanitize_html()`
- P3→P15: a blocked approve is a 409 re-rendering `stage.html`
- P1→P15: `recent_events[]`, and `orphaned_count: int | None` where `None` **must render
  differently from `0`**

Two more, established during P1 and equally binding:

- **The `_MIGRATIONS` contract**, written in that list's own comment block in `db.py`: a migration
  body must not call `conn.commit()`, `conn.rollback()`, `conn.executescript()`, open a
  `db.transaction()`, or touch a pragma. Foreign-key handling belongs to `apply_migrations` and
  already covers every migration. `executescript` is the tempting one — it is the natural idiom for
  SQLite's create-copy-drop-rename recipe, which is why the contract names it explicitly.
- **Migration 1 stays version 1 until it ships.** T6–T8 built it up; T9 and T10 extend the same
  function. A new rebuild adds statements to a `_MIGRATION_<n>_..._STEPS` tuple and nothing else.

## Context discipline — a hard rule

Never give a subagent the audit, another package's plan, or this whole brief. Generate a task brief
with `.superpowers/sdd/2026-08-08-audit-remediation/brief-T.sh <plan> <N> <out>` and pass the path.
Subagent replies must be 8 lines or fewer; their full reports go to files in the SDD workspace.

## Definition of done

1. All 328 findings closed.
2. Both suites green.
3. CI exists (3 jobs) and is green.
4. Every S0/S1 has a regression test **observed failing first**.
5. Defect-affirming tests gone or inverted.
6. A scheduled discovery run with an injected fault exits non-zero **and** leaves an error events
   row.
7. Gate C rejects a malformed shot heading.
8. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing.
