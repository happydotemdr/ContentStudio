# Resume prompt — audit-remediation programme, P2 (T1 → T18)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, where it must stop, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-12, after P1 closed in full, PR #26 merged, and both the worktree and the
operator's main checkout synced.

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
3. `docs/superpowers/plans/remediation/P2-artifact-durability.md` — the plan being executed.

## Where execution is

**P0: complete (23 findings). P1: complete (13 findings, T1–T18 incl. T4b/T13b). 49 of 328
closed.**

Suites, verified in the worktree, the operator's main checkout, and CI:
**app 1005 passed / 3 skipped / 0 xfailed**, **root 247 passed**, zero warnings, tree clean.
Baseline at programme start was 201 root / 833 app with ~65,700 warnings.

CI exists and is green (3 jobs). It covers more than local — two symlink tests skip on Windows and
execute only on the runner, so a local pass is strictly weaker than a CI pass.

**PR #26 is merged** as a genuine two-parent merge commit (`6dde406` — *not* a squash, unlike #25),
so this branch's commits are already ancestors of `main`. No reconciliation needed this time:
`git merge-base --is-ancestor <branch-tip> origin/main` is true as-is. The operator's main checkout
was fast-forwarded `69a834c..6dde406` and both suites verified green there too. **Do not rebase
this branch** — its history is where every RED observation and defect rationale lives, and the
plan files cite specific SHAs.

The live database at `C:\Projects\ContentStudio\pipeline-app\pipeline.db` is still legacy v0 (the
migration has not run against it yet — it runs automatically on the operator's next real boot). A
dry run against a copy already proved it migrates cleanly: every row preserved, only pre-existing
benign FK-violation warnings.

## YOUR TASK THIS SESSION: P2 (T1 → T18), then STOP

**Start at T1.** P2 is untouched — nothing in it has been pre-reviewed or dispatched yet.

P2 carries **3 of the audit's 4 S0 (data-destroying) findings** and is Wave B1's first half —
execute it before P10, never in parallel with it, per the landing order below.

### Files this package owns (no other package may touch these)

```
pipeline-app/pipeline_app/artifacts.py
pipeline-app/pipeline_app/migrations.py
pipeline-app/pipeline_app/grounding_service.py
pipeline-app/tests/test_artifacts.py
pipeline-app/tests/test_migrations.py
pipeline-app/tests/test_grounding_service.py
```

### The 18 tasks, 15 finding IDs, all in `P2-artifact-durability.md`

| Task | Finding | Sev / mode | What it does |
|---|---|---|---|
| T1 | A-63 (1/4) | **S0** silent | `_atomic_write_text` — temp file + `fsync` + `os.replace`, unlinked on any failure |
| T2 | A-63 (2/4), A-65 partial | **S0** silent | `write_artifact` becomes atomic and refuses to clobber |
| T3 | A-63 (3/4) | **S0** silent | `stamp_final` and `record_gate_override` become atomic |
| T4 | A-63 (4/4) | **S0** silent | `write_pointer` becomes atomic (grounding half) |
| T5 | A-65 | **S0** silent ⭐ | Exclusive version allocation: `reserve_version()`/`write_reserved_artifact()`/`release_version()` via `O_CREAT\|O_EXCL` |
| T6 | A-66 | S3 latent | Version high-water mark survives deletion; frontmatter `version` cross-checked against filename |
| T7 | A-67 | S3 silent | Strict, injective version regex; unparseable siblings warned and enumerable |
| T8 | A-68 | S2 silent ⭐ | Unterminated frontmatter block raises `MalformedArtifactError`, not "unversioned" |
| T9 | A-69 | S2 loud | Non-mapping frontmatter and `yaml.YAMLError` contained into one typed, path-naming error |
| T10 | A-38, A-37 | S2 silent | Overrides become an append-only `{reason, at, actor}` list; `read_gate_overrides(path)` accessor |
| T11 | A-73 (1/2) | **S0** silent ⭐ | Backfill refuses to overwrite a populated stage dir |
| T12 | A-73 (2/2) | **S0** silent | Idempotent adoption closes the write-then-row crash window |
| T13 | A-61 | S2 silent | Backfilled `depends_on` computed from the scripting artifact on disk; participates in staleness cascade |
| T14 | A-74 | S2 silent ⭐ | A skipped project's backfill is findable via an `events` row, not stderr-only |
| T15 | A-80 | S1 silent ⭐ | `pointer.yaml` records `sha256`/`size`/`written_at`; `verify_pointer()` detects an edited brief |
| T16 | A-81 | S2 silent ⭐ | `classify_brief_change()` by set difference, explicit N-brief reason, recursive snapshot |
| T17 | A-82 | S4 loud | `read_pointer` validates shape and refuses any path outside `rgs-briefs/` |
| T18 | F-18 | S1 coverage-gap | `TestDurabilityContract` — parametrized crash-injection class over all four writers |

⭐ = the plan itself flags these as needing extra care (Three-Test Rule or S0 severity).

### Verified non-issues in this package — do not "fix" these

- Version comparison is **integer**, so `v10` correctly outranks `v9`. `_versions_in` returns `int`
  keys and `max` is numeric. Leave it.
- `parse_frontmatter` returning `({}, text)` for a file that simply does **not** open with `---` is
  correct and must keep working (a legitimately plain markdown artifact). Only the *other* three
  collapsed cases (A-68, A-69, and the truncation case) change.

### Design constraints forced by file ownership — read before touching anything cross-package

Three findings in this package's own audit entries propose fixes that reach outside its file list.
Each is closed by an equivalent that stays inside it — **do not "fix it properly" by editing P1's
or another package's files**, that is exactly the file-exclusivity violation the whole 16-package
split exists to prevent:

- **A-66** proposes a `stage_artifacts` table. `schema.sql` and `db.py` belong to **P1**. Closed
  instead with a filesystem high-water mark inside `artifacts.py` (T6).
- **A-73** proposes ordering the DB row insert before the disk write. `db_mod.create_stage_row`
  calls `conn.commit()` internally, so a deferred-commit transaction is impossible without editing
  P1's file. Closed instead by **idempotent adoption** (T12) — same property, no P1 edit.
- **A-74** proposes new `app.state` keys rendered on `/doctor`. `main.py` and `routes/doctor.py`
  belong to **P1**. Closed instead by an `events` row (T14), which the orchestration plan already
  names as a valid human-reachable surfacing signal, and which `/doctor` can query with **no
  signature change** (T17's `recent_events`/`unacknowledged_error_total` machinery, already landed
  in P1, is exactly the query surface this relies on).

## THE PAUSE / COMMIT / PR POINT: end of P2, before P10

**Stop when T18's review is clean.** Then: run both suites, confirm green, push, and open a PR
titled for P2's completion. Do **not** start package P10 in this session, even though it lands
immediately after in the same wave.

**Why this exact point, and not P10 too.** Wave B1 is "P2, then P10" — sequential, not parallel,
specifically so the three artifact-durability S0s land before P10's own S0 (the corpus-destroying
roster rebuild), which *increases write traffic* against the same `runs/` tree P2 just made crash-safe.
Landing them in one session risks the same "amendment introduces the defect it was written to
catch" failure mode this programme has hit repeatedly — better to close, verify, and pause than to
carry momentum into a second package's very different risk profile.

At the pause, the PR body should state plainly: findings closed, suite numbers, what the operator
will notice on next boot, and what is knowingly still open — same shape as PR #26's body.

## The bar, restated because it is what everything else serves

**"Any representation shared by 'nothing here' and 'something is wrong' is a defect by default."**
169 of the 328 findings are classed silent — **11 of P2's 15** are. If you find a new instance,
treat it as in scope, file it in the relevant plan, and fix it.

The count so far across the programme is **~37+ confirmed instances**, most of them written by the
remediation itself. That ratio is the entire reason for the pre-review discipline. Every single
task in P1's T14–T18 window had at least one plan defect caught before or after dispatch — expect
the same rate here, if not higher: P2 is denser (S0×3 in 18 tasks vs. P1's S3×1 in 18) and touches
raw filesystem durability, a domain this programme has not exercised yet.

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
   implementer's output — the *plan's*. P1's plan was wrong in every task from T5 onward; expect
   the same here. **Probe SQLite, the filesystem and the parser empirically rather than reasoning
   about them.** P2 is filesystem-heavy — probe `os.replace`'s actual Windows semantics (it IS
   atomic and DOES overwrite an existing target on Windows since Python 3.3, unlike `os.rename`,
   but confirm this holds for the specific temp-file-naming scheme T1 uses, on THIS host, before
   trusting it), and probe `O_CREAT|O_EXCL`'s actual raised-exception type on Windows (T5) rather
   than assuming POSIX behavior transfers unchanged.
2. **Run `compile_plan.py` on the plan before every dispatch.** It compiles every fenced `python`
   block. It once caught a raw newline in a string literal that would have broken *collection* of
   an entire test module — silently taking ~60 passing tests with it while the suite still reported
   success. It lives in the session scratchpad; if gone, rewrite it (~30 lines, `textwrap.dedent`
   each block, compare failing block COUNT and line numbers against a fresh baseline run rather than
   assuming zero). **P2 has not been baselined yet — the first pre-review pass's `compile_plan.py`
   run establishes the baseline for this package; note it in the ledger.**
3. **Amend the plan FIRST, then execute the amended step.** Never improvise around a plan defect
   silently. Every amendment gets its own commit explaining what was wrong and why.
4. **Your own corrections will contain the defect they were written to catch.** This happened
   repeatedly in P1 (T9's C1, T13's C2, T13b's C4, T12's C4, and independently in P1 T14's
   POST-REVIEW AMENDMENT process this pause window). Tell implementers explicitly to report reality
   rather than match the brief.
5. **When a fix round produces a NEW instance of the defect class, the signal is about the design,
   not the implementer.**
6. **`schema.sql` runs before migrations.** Not directly P2's concern (P2 doesn't touch
   `schema.sql`), but `migrations.py` IS P2's file — if any task interacts with migration-adjacent
   state, re-derive this rule's applicability rather than assuming it doesn't apply because the
   package boundary looks clean on paper.
7. **When a task adds N kinds of guarantee, apply the twin/parametrized discipline N times** — per
   behaviour, not per call site. T18's own `TestDurabilityContract` is explicitly a parametrized
   class over "all four writers" — verify during pre-review that all four are actually parametrized
   in the shown code, not three with the fourth asserted only in prose.
8. **Check every `silent` finding's surfacing test for the same-connection read before dispatch** —
   this was the single most repeated defect in P1 (4 instances). P2 is mostly filesystem, not
   sqlite, but T14 (A-74) and T18 (F-18) both touch `events` rows — apply the second-connection idiom
   there. `tests/test_db.py` carries the correct idiom at `:339-364` and `:663-676` if you need a
   reference (P1's file, read-only reference is fine, do not edit it).
9. **Adding a second mechanism that produces the same end state can silently over-determine an
   existing guard.** Whenever a task makes something true by a **new route** (e.g. T12's idempotent
   adoption creating a second path to "backfill completed"), ask which existing test was the only
   thing proving the **old route** still works.
10. **A crash-injection test (T1, T18's whole point) must actually inject the crash at the moment
    that matters**, not merely call the function and check the end state. Verify each injected
    fault (a monkeypatched `os.fsync`/`os.replace`/`open` that raises) fires *between* the two
    states the atomicity claim is about — before vs. after the point of no return — not before the
    function is even entered or after it has already fully succeeded.

## Traps, verbatim

- **`python -m` is mandatory.** A bare `pytest` at the repo root reports "201 passed", exit 0, while
  silently omitting all app tests. Run `cd pipeline-app && python -m pytest` and, from the repo
  root, `python -m pytest tests/ -v`. Each suite has its own `pytest.ini` pinning its rootdir.
- **`pipeline-app` is installed EDITABLE against the MAIN checkout**, not this worktree. From
  repo-root cwd `pipeline_app` resolves to the main checkout; from `pipeline-app/` cwd it resolves
  to the worktree. A bare `pytest` in `pipeline-app/` tests the WRONG CHECKOUT (a guard aborts it).
- **The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db`** — main checkout,
  git-ignored. A backup is at `pipeline.db.backup-pre-migration`. Never write to either; open
  read-only and copy to scratch for experiments. **P2 also touches real files under `runs/`** in
  the same spirit — never let a test write into the operator's actual `runs/` tree; always `tmp_path`.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always
  `encoding="utf-8", errors="replace"`.
- `os.kill(pid, 0)` **terminates** the process on Windows. Use `OpenProcess` for liveness.
- **Never invoke `bash`/`sh` by bare name in a subprocess** — CreateProcess consults System32 first
  and finds the WSL stub. Resolve with `shutil.which()` and pass the absolute path.
- **`BRIGHTDATA_API_KEY`, `RESEND_API_KEY` and `YOUTUBE_API_KEY` are set in the ambient
  environment. Bright Data bills per record. Never let a test reach a live vendor API.**
- Writing a commit message through `bash -c "..."` will **eat anything in backticks** as command
  substitution. Use a quoted heredoc (`git commit -F - <<'MSG'`).
- **An apostrophe inside a single-quoted shell block terminates it.** This broke `brief-T.sh` once.
- **`grep -c` exits 1 when the count is zero**, which silently truncates a `&&` chain. Use `;` when
  chaining checks whose expected answer is zero.
- Opening a WAL database **read-only still creates 0-byte `-wal`/`-shm` sidecars.** Harmless, but
  not evidence the app ran.
- `pipeline.yaml` is at the repo root. App modules are flat in `pipeline-app/pipeline_app/*.py`.
- The linters in the root `scripts/` are stdlib-only and loaded by file path. They must not import
  app code, so they cannot use `obs.py`.
- **Anything non-trivial embedded in YAML is untestable by construction.** Extract it to a module
  with tests.
- **NEW, discovered across every P1 T14–T18 task this pause window: `tests/test_main.py`'s leak
  allowlist entry was deleted (shrink-only rule) and every one of five consecutive briefs still
  used the pre-deletion "bare `create_app()`, no close" idiom.** Not directly P2's file, but the
  general lesson applies: **when a plan was drafted before a later-landing package's constraint
  tightened, the plan's examples silently violate the NEW constraint even though they were correct
  when written.** Check every new test this package adds against the CURRENT state of
  `tests/conftest.py`'s `_CONNECTION_LEAKS_BY_PACKAGE` and any other cross-cutting guard, not the
  state the plan's author saw when the plan was drafted (2026-08-08).
- **NEW: `os.replace(src, dst)` on Windows is atomic and silently overwrites an existing `dst`**
  (unlike `os.rename`, which raises `FileExistsError` on Windows if `dst` exists). T1's
  `_atomic_write_text` relies on this. Verify it empirically on this host before trusting the
  plan's claim, per the probe-don't-reason rule — this is exactly the kind of platform-behavior
  belief that has repeatedly turned out false elsewhere in this programme.

## Frozen cross-package interfaces — do not redesign

From P0/P1 (already shipped, consumed by everyone):

- `obs.log(event, *, level, **fields)`
- `obs.record_event(conn, *, kind, severity, source, message, detail, run_id) -> int`. **Must never
  raise** — falls back to `log()` and returns `-1`.
- `gates.resolve_upstream_by_stage(...)` (not yet implemented — P3/P4's contract, listed here so P2
  does not accidentally collide with the name).
- `| safe` means sanitized by `browse_service.sanitize_html()`.
- P3→P15: a blocked approve is a 409 re-rendering `stage.html`.
- P1→P15: `recent_events[]` = `{id, occurred_at, kind, severity, source, message, detail, run_id,
  acknowledged}`, unacked error/critical, 7-day window, newest first, cap 50, PLUS
  `unacknowledged_error_total: int` (all-time, unbounded — added during P1's own review this pause
  window to close a silent-window blind spot; not in the original orchestration doc, but real and
  landed). `orphaned_count: int | None` — `None` **must render differently from `0`** (confirmed
  closed: `routes/doctor.py` now reads the attribute directly, no `getattr` default).

**New from P2, which THIS session produces — get these exactly right, P3 and P4 adopt them
verbatim and go red until they do:**

- `parse_frontmatter` — **now raises `MalformedArtifactError`** for an unterminated frontmatter
  block or non-mapping YAML, instead of returning `({}, text)`. The genuinely-no-frontmatter case
  (file doesn't open with `---` at all) is unchanged and must keep returning `({}, text)` — do not
  widen the raise to cover it.
- `record_gate_override(..., at=...)` — gains a **required** keyword-only `at` parameter (T10).
- `write_pointer(..., repo_root=...)` — gains a **required** `repo_root` parameter (T4).
- `identify_new_brief` → renamed **`classify_brief_change`** (T16) — different name, not a
  drop-in-compatible rename; grep for the old name across the whole repo before considering this
  task done, since a caller still using the old name will get a bare `AttributeError`, not a
  helpful one.
- `next_version_number` + `write_artifact` → **`reserve_version()` / `write_reserved_artifact()` /
  `release_version()`** (T5) — a three-function protocol replacing a single call, not a
  same-signature swap. `write_artifact` itself gains clobber-refusal (T2) but is not removed.
- `compute_depends_on`, `read_artifact` — consumed by P3/P4, must exist with stable signatures by
  the end of this package (T13 and earlier tasks build these).

The `_MIGRATIONS` contract, migration-1-stays-version-1 rule, and the `ux_turns_single_running` /
`idx_handles_creator` schema.sql-vs-migration split are all **P1's**, not P2's — carried here only
so you recognize them and don't touch `schema.sql` or `db.py` if a task's reasoning tempts you to.

## Open findings — filed, NOT fixed, awaiting validation

Recorded in the plans and routed to the packages owning the files. Do not fix inline.

1. **`ux_discovery_single_running` (`schema.sql:90`) crashes `init_db`** on any legacy database
   holding two `'running'` discovery runs, before `events` exists. Pre-existing, same shape as
   A-71. **P6–P9.** Not triggered by the operator's current database.
2. **An unknown platform posted by hand returns 500** where the route convention is 400. **P8.**
3. **`discovery_handles.html`'s `<select>` is a fourth unpinned copy of the platform vocabulary.**
   **P8/P15.**
4. **`list_handles_for_creator` returns `[]`** for both "creator owns no handles" and "no such
   creator". Deferred to the final review.
5. **Migration tests that do not pin `obs.LOG_DIR` write into the real `pipeline-app/logs/`.**
   Git-ignored, so nothing fails. Fix is an autouse fixture in `conftest.py`, which **P0** owns.
6. **B-82 is NOT closed.** P1 shipped the storage half. **Nothing in production calls it.** P8 must
   wire the discovery engine's error and success branches; P15 must render the counter. **The
   definition of done must check the call site exists, not merely that the helper does.**
7. **C-88b (S1, silent) → P12 T1b**, filed 2026-08-10 from a real field failure. `_beat_name`
   returns `None` for both "prose, correctly ignored" and "beat line in a shape I do not
   recognise". Root cause and design: `GATE-D-PARSE-rootcause.md` / `-design.md` in the SDD
   workspace.
8. **The script format is authoritatively defined nowhere → P13.** The `shorts-scripting` skill's
   own worked example produces 1 VO line and 5 `PARSE` findings under its own gate.
9. **NEW, filed 2026-08-12 from P1 T18's task review:** `create_app` (`pipeline_app/main.py`) has
   **five statements after the topology-load `try/except`** — the styleboard backfill, the
   reconcile-lease claim, the CLI probe construction, router mounting — that are completely
   unguarded. If any of them raises, `app.state.conn` leaks exactly the way the topology-load path
   used to, with no caller able to close it. Confirmed pre-existing (predates the whole P1 T14–T18
   window; A-85 never covered exceptions raised *inside* `create_app` before it returns, only the
   normal-exit shutdown path), and not any single task's responsibility — **flagged for the final
   whole-branch review**, worth checking before P2's own `migrations.backfill_styleboard_rows`
   (called from this exact unguarded stretch) grows a new way to raise.

## The decisions that are NOT yours

**Stop and ask the operator:**

- **Should label-first sub-beats (`mechanism: (11–18s | 19 words)`) become legal?** Filed in P13.
  **Currently pending.**
- **P10 T4/T6** sets `@bigthink` and `adamgrant.bsky.social` to `included: false` — a change to what
  gets tracked, not a defect fix.
- **P7 §6 C1** adds a per-platform `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` override — the only change in
  the programme that can increase spend.

**Already decided — do not re-ask:**

- **T13b's design: option 4, accept and detect** (2026-08-09).
- **CI required checks: deferred to the end of the programme** (2026-08-10).
- **A plan-mandated finding that is an instance of the recurring defect class does not get
  escalated** — fix it. Escalate plan-mandated findings only when they are genuine product or
  policy choices, not technical-correctness gaps with an obvious right answer (e.g. P1 T14's
  heartbeat-refresh gap was plan-mandated and NOT escalated, because there was no real tradeoff to
  ask about — only "should this be fixed", which the standing rule already answers).

## Context discipline — a hard rule

Never give a subagent the audit, another package's plan, or this whole brief. Generate a task brief
with `.superpowers/sdd/2026-08-08-audit-remediation/brief-T.sh <plan> <N> <out>` and pass the path.
Subagent replies must be 8 lines or fewer; their full reports go to files in the SDD workspace.

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
