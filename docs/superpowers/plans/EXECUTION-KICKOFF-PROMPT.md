# Execution kickoff prompt

Copy everything below the line into a fresh Claude Code session opened in the worktree.
It assumes zero prior context.

---

You are the **execution orchestrator** for a remediation programme that is already fully planned and validated. Your job is to execute it, not to re-plan it.

**REQUIRED FIRST STEP:** invoke the `superpowers:subagent-driven-development` skill and follow it. Announce which skill you are using. Do not begin work before that.

---

## 1. Where you are

- **Repo (worktree):** `C:\Projects\ContentStudio\.claude\worktrees\pipeline-audit-review-4dd767`
- **Branch:** `claude/pipeline-audit-review-4dd767` (main branch is `main`)
- **Platform:** Windows 11, Python 3.14.4 at `C:\Python314\python.exe`. PowerShell is primary; a Bash tool is available and takes POSIX syntax.
- Two commits already exist and must not be altered:
  - `1d39c9d` — the audit: 328 findings across 6 appendices plus a master report
  - `6c61f14` — the remediation programme: 16 package plans plus an orchestration plan

## 2. What the project is

**ContentStudio** turns a faceless-YouTube-Shorts idea into a produced Short. Two halves:

- `pipeline-app/` — a FastAPI + Jinja2 + htmx + SQLite app driving a 9-stage content pipeline declared in `pipeline.yaml`. Each stage invokes a Claude skill via a `claude -p` subprocess, which writes `raw_output.md`; the app versions it into `runs/{run_id}/{dir_prefix}-{stage}/artifact.v{N}.md`. Handoff between stages is by **markdown file paths** passed into per-stage kickoff templates. It also contains a 6-platform discovery subsystem (Bright Data + native APIs), a Windows Task Scheduler cron, and a daily digest email.
- `.claude/skills/` — 13 Claude skills: 8 pipeline stages, 3 tool specialists, 2 RaisingGoodSports-specific.

Read `CLAUDE.md` at the repo root before touching anything. Note especially the **anti-generic guarantee** (every normative line in a skill needs a `[C]`/`[I]`/`[T]`/`[P]` provenance marker) and the **FamilyBrain firewall** (this repo has zero connection to `C:\Projects\FamilyBrain\`; never add a remote, submodule, or path reference to it).

## 3. What you are executing

An audit found **328 defects**, including 4 that destroy data. A remediation programme was then planned across **16 file-exclusive packages** totalling **~349 TDD tasks**.

- **Orchestration plan (read this first, in full):** `docs/superpowers/plans/2026-08-08-audit-remediation.md`
- **The 16 package plans:** `docs/superpowers/plans/remediation/P0-*.md` … `P15-*.md`
- **The audit (reference only, do not read whole):** `docs/audit/2026-08-08-pipeline-audit.md` and `docs/audit/appendix-{A..F}-*.md`

Every finding has an ID (`A-63`, `B-10`, `C-70`, `D-04`, `F-11`…). Every plan contains a **finding → task map** and a **finding → test map**. Coverage was verified programmatically: **328/328, zero gaps, zero placeholders.**

**Do not re-plan.** The plans were written by 16 specialist agents and then validated, which caught three integration breaks that would otherwise have shipped. If a plan step turns out to be wrong during execution, **amend the plan file first**, then execute the amended step — never improvise around it silently.

## 4. The one thing that matters most

The audit's deepest finding is not any single bug. It is that **this codebase catches errors carefully and tells nobody**: zero bare `except:` in 8,550 lines, but no logging module, no error table, no health endpoint, and a scheduled task registered with no output redirection — so 35 stderr diagnostics per run are written to a console Windows destroys. 169 of 328 findings are classed `silent`.

One root cause appeared **five separate times**, and the fifth was found *inside a proposed fix*:

- Bluesky returned `[]` for both "no new posts" and "the fetch failed"
- the cron returned exit `0` for both a clean run and total failure
- the digest rendered the identical email for a quiet day and a broken collection
- `browse_service` returned `False` for both an empty folder and an unreadable one
- a new `approved_only` resolver would have returned an absent key for both "no upstream" and "upstream exists but is unapproved"

**Any representation shared by "nothing here" and "something is wrong" is a defect by default.** Hold every task to that. If you find a sixth instance, treat it as in-scope, file it in the relevant plan, and fix it.

## 5. The test standard — non-negotiable

Reproduced from the orchestration plan. Every task must satisfy it.

### The Three-Test Rule
For **every** finding whose `failure_mode` is `silent`, the fix needs three distinct tests:
1. **Fault test** — inject the fault; assert the operation *reports failure*. Not "returns empty", not "returns a default".
2. **Distinguishability test** — assert the fault state is observably **different** from the legitimate-but-empty state.
3. **Surfacing test** — assert a human-reachable signal exists afterward: an `events` row, a non-zero exit code, or a rendered UI element. **Asserting that a `print()` happened does not count.**

### Anti-tautology rules
- Never assert on a value the function hard-codes. The audit found a security test that deserialised a literal and asserted the literal survived.
- Never assert a mock was called when you can assert what the system did.
- **If a test's name describes a defect, delete or invert it.** The audit found `test_enumerate_newest_first_returns_empty_on_fetch_failure` — the bug written down as the requirement. Every plan has a "tests deleted or inverted" section listing these by `file:line`. Honour it.
- Any function that turns text into structure needs an adversarial test proving malformed input is **rejected**, not silently skipped.

### Coverage is not the bar
The suite was at **95% line coverage on both halves with all 328 defects present**. Do not add a coverage gate and do not treat a coverage number as evidence. The bar is: for each finding, a named test that **fails before the fix and passes after**. You must actually observe the failure — that is the point of the TDD ordering.

## 6. Verification commands

**`python -m` is mandatory.** A bare `pytest` at the repo root reports "201 passed", exit 0, while silently omitting all 833 app tests. A bare `pytest` inside `pipeline-app/` fails collection on 4 files.

Root suite (linters + provenance):
```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767" && python -m pytest tests/ -q
```

App suite:
```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest -q
```

**Baseline before you start: 1,034 passed, 3 skipped, 0 failed** (201 root + 833 app). If that is not what you see on a clean checkout, stop and investigate before executing any task — something in the environment differs from what the plans assume.

There is currently **no CI**. Package P0 creates it. Until P0 lands, you are the only thing running these tests: run both suites after every task.

## 7. The landing order — constrained, not free

File exclusivity means the plans could be *written* in parallel. It does **not** make execution order free. Three things constrain it:

1. **P2 changes `artifacts.py` in breaking ways** (`parse_frontmatter` now raises instead of returning `{}`; `record_gate_override` gains a required `at=`; `write_pointer` gains `repo_root`; `identify_new_brief` → `classify_brief_change`; `next_version_number`+`write_artifact` → `reserve_version`/`write_reserved_artifact`/`release_version`). P3 and P4 are red until they adopt. **P2 lands before P3 and P4.**
2. **Three packages carry deliberate tripwire tests that go red on a *successful* neighbouring merge** — they exist to force cleanup, not because something broke. P3's divergence-ledger test fails once P11 lands; P12's `strict=True` xfail XPASS-fails once P3 lands. **P3, P11 and P12 land together**, or the follower retires the tripwire in the same commit. If you see one of these go red, do not "fix" it — complete the paired change.
3. **The F-64 rename is atomic.** `pipeline-app/scripts/` → **`pipeline-app/tools/`** (chosen over `pipeline_app/scripts/` because it preserves module depth, so `parents[1]` stays correct — the alternative would have left `schtasks` registered against a nonexistent path, failing forever and invisibly). The directory move, P8's `setup_discovery_task.py` update, and P10's six file updates are **one commit**.

**Execute in this order:**

| Wave | Packages | Rationale |
|---|---|---|
| **A** | **P0** → **P1** | P0 gives you CI that proves tests ran plus a conftest guard that stops a test billing Bright Data. P1 gives every later package somewhere to report a failure (`obs.py`, `events` table, `/doctor` health). Anything fixed before these gets fixed twice. |
| **B1** | **P2**, then **P10** | The four S0s. P2 has three (artifact truncate-in-place, lost-version race, backfill overwriting real styleboards); P10 has the corpus destroyer. |
| **B2** | **P3 + P11 + P12** together | Tripwire cluster, and the gate-correctness core. |
| **B3** | **P4**, then **P5** | P4 adopts P2's and P3's APIs and fixes the stage graph; P5 swaps its private helper for P4's at its T19. |
| **B4** | **P6**, **P7**, then **P8**, and **P9** | P8 consumes seams from P6 and P7, so those land first. P9 is independent. |
| **B5** | **P15** | Binds to P3's gate context keys and P1's `recent_events`; both must exist. |
| **C** | **P13**, then **P14** | Documentation describes the fixed code, or it is fiction again. P14 is last — six packages owe it contract decisions. |

## 8. Frozen cross-package interfaces

These were fixed during validation because 16 agents that cannot see each other would otherwise invent 16 incompatible versions. **Do not redesign them.** Full table is in §"Cross-package contracts" of the orchestration plan. The critical ones:

- **`obs.log(event, *, level, **fields)`** and **`obs.record_event(conn, *, kind, severity, source, message, detail, run_id) -> int`**. `record_event` must **never raise** — a failure to record must not mask the thing being recorded; it falls back to `log()` and returns `-1`.
- **Adoption rule:** anywhere the code signals failure *only* by `print(..., file=sys.stderr)`, add an `obs.record_event(...)`. Keep the print; the event row is what makes it findable.
- **`gates.resolve_upstream_by_stage(*, repo_root=None, approved_only=False, include_optional=False)`** returns an `UpstreamMap` with **three** states — absent / present / excluded — where reading an *excluded* key **raises**. This is deliberate: it makes the dangerous idiom (`upstream.get(x) is None`) impossible rather than adding a check someone can forget.
- **`| safe` means "sanitized by its producer."** Producers call `browse_service.sanitize_html()` before the value reaches a template. A consumer-side filter fails open the moment a site is missed.
- **P3 → P15 stage context keys:** `gate_view[]` (`state ∈ passed|failed|errored|never_ran|unknown`), `has_blocking_gate`, `gate_override`/`gate_overrides[]`, `approval_block_reasons`, `artifact_version`, `artifact_created_at`, `artifact_finalized_at`, `inputs[]`, `edit_*`, `error_banner`. A blocked approve is **409 re-rendering `stage.html`**, never a `PlainTextResponse`.
- **P1 → P15:** `recent_events[]` and `orphaned_count: int | None`, where `None` (sweep skipped) **must render differently from `0`**.

## 9. How to run each task (subagent-driven)

Follow the `superpowers:subagent-driven-development` skill. Per task:

1. **Read only the current task** from its package plan. Do not load the whole plan into your own context.
2. **Dispatch one fresh subagent per task.** Give it: the task's exact steps, the file list it may touch, the finding IDs it closes, the Three-Test-Rule and anti-tautology rules, and the relevant frozen interface. **Never give a subagent the audit, another package's plan, or this whole brief.**
3. **Require the subagent to reply in ≤8 lines**: what it changed, the test names, observed fail→pass, and any blocker. No plan content, no narration.
4. **Review between tasks.** Verify the test actually failed first — a task where the test passed immediately is a task that proved nothing. Re-run both suites.
5. **Commit per task** with a conventional message (`fix:`, `test:`, `feat:`, `docs:`) naming the finding IDs closed.

**Context discipline is a hard rule, not a preference.** The planning phase kept every agent to its own findings and file list, and that is why file exclusivity held across 114 files. Preserve it.

## 10. Traps that will bite you

- **A test that passes on first write is a failed task.** Re-derive it until it fails for the right reason.
- **A red tripwire is success, not regression** — see §7.2. Check the pairing before debugging.
- **`subprocess` with `text=True` decodes as cp1252 on this host.** Always `encoding="utf-8", errors="replace"`. An emoji in a YouTube title otherwise either kills the reader thread or mojibakes into the corpus.
- **`os.kill(pid, 0)` terminates the process on Windows.** Use `OpenProcess` for liveness.
- **`BRIGHTDATA_API_KEY`, `RESEND_API_KEY` and `YOUTUBE_API_KEY` are set in the ambient environment.** Bright Data bills per record. Until P0's conftest guard lands, one forgotten stub can spawn a real billed job and the test still passes. **Never let a test reach a live vendor API.**
- **Two untracked `.coverage` files** exist at the repo root and in `pipeline-app/`. P0 gitignores them; leave them alone until then.
- `pipeline.yaml` is at the **repo root**, not in `pipeline-app/`. App modules are **flat** in `pipeline-app/pipeline_app/*.py` — there is no `app/` or `services/`.
- The linters in root `scripts/` are **stdlib-only** and loaded by file path. They must not import app code, so they cannot use `obs.py`.

## 11. Two decisions are NOT yours

These are product decisions the operator has not yet made. **Do not execute them; stop and ask.**

1. **P10 T4/T6** sets `@bigthink` and `adamgrant.bsky.social` to `included: false` — a change to what gets tracked, not a defect fix.
2. **P7 §6 C1** adds a per-platform `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` override — the only change in the programme that can increase spend. Default is unchanged, and `trigger` is never retried (pinned by a test) because a retried trigger double-bills.

If a task in either package depends on one of these, execute everything around it and flag the gap explicitly.

## 12. Definition of done

The programme is complete when all of these hold — each checkable, not asserted:

1. All 328 finding IDs are closed, each by the task its plan's finding→task map names.
2. Both suites green: `python -m pytest tests/ -q` and, from `pipeline-app/`, `python -m pytest -q`.
3. CI exists (`.github/workflows/tests.yml`, 3 jobs) and is green on both suites.
4. Every one of the 4 S0 and 43 S1 findings has a named regression test that was **observed failing** before its fix.
5. Every defect-affirming test listed in the plans' "deleted or inverted" sections is gone or inverted.
6. A scheduled discovery run with an injected adapter fault exits **non-zero** and leaves an `events` row of severity `error`.
7. Gate C **rejects** a sheet with a malformed shot heading instead of printing `PASS`.
8. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing.

## 13. Start here

1. Invoke `superpowers:subagent-driven-development`.
2. Read `docs/superpowers/plans/2026-08-08-audit-remediation.md` in full.
3. Run both suites and confirm the 1,034/3-skipped/0-failed baseline.
4. Read `docs/superpowers/plans/remediation/P0-harness-ci.md` §1–§2 only.
5. Dispatch a subagent for P0 Task 1. Review. Commit. Continue.

Report progress as: package, task N of M, findings closed, suite status. Keep your own context lean — you are an orchestrator, not a reader.
