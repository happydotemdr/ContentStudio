# Audit Remediation — Orchestration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement each package plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 328 findings from the 2026-08-08 audit ([`docs/audit/2026-08-08-pipeline-audit.md`](../../audit/2026-08-08-pipeline-audit.md)) with regression tests that make each defect impossible to reintroduce silently.

**Architecture:** The 328 findings were partitioned across 114 files into **16 file-exclusive packages**. No two packages share a single file, so their plans can be written in parallel and executed without merge collisions. Two packages (P0, P1) build shared infrastructure everyone else consumes; their interfaces are frozen in this document so no package has to guess. Each package gets its own plan file under `docs/superpowers/plans/remediation/`.

**Tech Stack:** Python 3.14, FastAPI, Jinja2, SQLite, pytest + pytest-asyncio + pytest-cov, htmx, GitHub Actions (to be created).

---

## Global Constraints

Every task in every package plan implicitly includes this section.

- **No behavior change without a test that fails first.** TDD order is mandatory: write failing test → run it → see it fail for the right reason → implement → see it pass → commit.
- **Python 3.14**, stdlib-only for `scripts/**` linters (they are loaded by file path and must stay import-free of app code).
- **Aware UTC timestamps** everywhere: `datetime.now(timezone.utc).isoformat(timespec="seconds")`. Never naive, never local.
- **Windows is the target platform.** Paths via `pathlib`. Any subprocess that reads text output MUST pass `encoding="utf-8", errors="replace"` — never bare `text=True` (finding B-10).
- **Two test suites, two rootdirs.** Root: `python -m pytest tests/`. App: `cd pipeline-app && python -m pytest`. Always `python -m` (finding F-63).
- **Never widen a `# noqa: BLE001`.** This codebase catches deliberately; the defect is that it does not *tell*. Fix the telling, not the catching.
- **No new outbound network dependency.** CLAUDE.md's "local only" rule stands; the audit already found 14 undocumented call sites.
- Commit after each task. Conventional commits (`fix:`, `test:`, `feat:`, `docs:`).

---

## The test standard — how we prove a gap is actually closed

This is the point of the exercise. A fix without these tests is not done.

### The Three-Test Rule (mandatory for every `failure_mode: silent` finding)

164 of the 328 findings are classed `silent`. For **each** of them the package plan must include three distinct tests:

1. **Fault test** — inject the fault; assert the operation *reports failure*. Not "returns empty", not "returns a default" — fails.
2. **Distinguishability test** — assert the fault state is observably **different** from the legitimate-but-empty state. Same shape as: `assert result_when_broken != result_when_genuinely_empty`. This is the test that would have caught B-10, B-40, C-70 and D-01.
3. **Surfacing test** — assert a human-reachable signal exists afterward: an `events` row, a non-zero exit code, or a rendered UI element. Asserting a `print()` happened is **not** sufficient (that is exactly the 35-site defect D-02).

### Anti-tautology rules

The audit found six tests that assert the defective behavior is correct, and one that asserts a security control that does not exist. Every package plan must obey:

- **Never assert on a value the function hard-codes.** `test_scoped_permissions_settings` (F-11) deserialized a literal and asserted the literal survived. Assert on *effect*, not on echo.
- **Never assert a mock was called** when you can assert what the system did.
- **A test named for a behavior must assert that behavior.** `test_enumerate_newest_first_returns_empty_on_fetch_failure` (F-12) named the bug and froze it. If a test's name describes a defect, the test is deleted or inverted — and the plan must say which, explicitly, by file:line.
- **Parse layers get adversarial tests.** Any function that turns text into structure needs a test proving malformed input is *rejected*, not silently skipped. This is C-70: 118 tests, 98% coverage, and a one-character typo still deleted a shot from all 20 checks because ~90 of those tests started downstream of the parser.

### Coverage is not the bar

95% line coverage coexisted with 328 defects. Do not add a coverage gate as the success measure. The measure is: **for each finding, a named test that fails before the fix and passes after.** Every package plan must include a finding→test table proving that mapping is total.

---

## Frozen interfaces (produced by P0/P1, consumed by everyone)

Package plan authors: these are **fixed**. Do not redesign them; call them as specified.

### `pipeline_app/obs.py` — the error-surfacing layer (P1 creates)

The audit's single most systemic finding is that there is no logging module, no event table, no health endpoint and no alert path (D-02), so 35 stderr diagnostics on the scheduled path go to a console Task Scheduler destroys.

```python
# pipeline-app/pipeline_app/obs.py

def log(event: str, *, level: str = "info", **fields) -> None:
    """Structured line to stderr AND to pipeline-app/logs/app-YYYY-MM-DD.log.
    `event` is a dotted kind, e.g. "adapter.fetch_failed". Never raises."""

def record_event(conn, *, kind: str, severity: str, source: str,
                 message: str, detail: dict | None = None,
                 run_id: int | None = None) -> int:
    """Append one row to the `events` table and return its id.
    severity in {"info","warning","error","critical"}. Never raises —
    a failure to record must not mask the thing being recorded; it
    falls back to log() and returns -1."""
```

**The adoption rule every package follows:** anywhere the code currently signals a failure *only* by `print(..., file=sys.stderr)`, add a `obs.record_event(...)` call with `severity="error"` (or `"warning"` where genuinely benign). Keep the print — it is useful interactively. The event row is what makes it findable.

### `events` table (P1 adds to `schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at  TEXT    NOT NULL,
  kind         TEXT    NOT NULL,
  severity     TEXT    NOT NULL CHECK (severity IN ('info','warning','error','critical')),
  source       TEXT    NOT NULL,
  message      TEXT    NOT NULL,
  detail       TEXT,
  run_id       INTEGER,
  acknowledged INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity, occurred_at DESC);
```

### `creators` table + `handles` constraints (P1 adds to `schema.sql`; P10 populates)

74 of 90 creator×platform cells are unanswerable today (B-70) because four of six platforms have no declarative roster and there is no cross-platform identity.

```sql
CREATE TABLE IF NOT EXISTS creators (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  slug         TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL
);
-- handles gains: creator_id INTEGER REFERENCES creators(id)
-- handles gains: CHECK (platform IN ('youtube','bluesky','instagram',
--                'linkedin-profile','linkedin-company','facebook','x'))
-- handles gains: UNIQUE (platform, handle)
```

### `conftest.py` network guard (P0 creates, repo-wide)

There is no `conftest.py` anywhere, and `BRIGHTDATA_API_KEY` / `RESEND_API_KEY` / `YOUTUBE_API_KEY` are all set in the ambient environment. One forgotten stub spawns a real, per-record-billed job (F-68).

```python
# pipeline-app/tests/conftest.py  AND  tests/conftest.py
# autouse fixture that raises on requests.*, urllib.request.urlopen,
# subprocess.Popen/run unless the test carries @pytest.mark.allow_subprocess
# or @pytest.mark.allow_network. Both markers registered in pytest.ini.
```

### CI (P0 creates `.github/workflows/tests.yml`)

Three jobs on `windows-latest`: `root-suite` (`python -m pytest tests/`), `app-suite` (`cd pipeline-app && python -m pytest`), `no-live-credentials` (asserts the guard fires when a vendor key is present). Nothing runs these 1,034 tests today except a human who remembers (F-60).

---

## The 16 packages

Every file in the repo touched by a finding belongs to **exactly one** package. Verified: 114 files, 0 collisions.

| Pkg | Scope | Findings | Files | Worst |
|---|---|---|---|---|
| **P0** | Test harness, CI, conftest guards, pytest.ini, requirements, runner scripts | 23 | 17 | S1×3 |
| **P1** | Observability: `obs.py`, `events`+`creators` schema, `db.py`, `main.py`, `/doctor` health | 13 | 4 | S2×7 |
| **P2** | Artifact durability: `artifacts.py`, `migrations.py`, `grounding_service.py` | 15 | 4 | **S0×3** |
| **P3** | Gates & approval: `routes/stages.py`, `gates.py`, `approval_service.py`, `state_machine.py`, `preflight.py` | 22 | 7 | S1×5 |
| **P4** | Handoff: `turn_service.py`, `prompt_builder.py`, `pipeline_config.py`, `cli_runner.py`, `pipeline.yaml`, `stage_templates/` | 26 | 8 | S1×8 |
| **P5** | Skill editor & git: `routes/skills.py`, `git_helper.py`, `routes/projects.py`, `project_service.py`, `routes/inspector.py` | 15 | 4 | S1×2 |
| **P6** | Native adapters: `discovery_youtube.py`, `discovery_youtube_api.py`, `discovery_bluesky.py` | 18 | 4 | S1×5 |
| **P7** | Bright Data: `brightdata_job.py`, `discovery_{instagram,linkedin,facebook,x}.py` | 14 | 5 | S1×2 |
| **P8** | Engine & cron: `discovery_engine.py`, `run_discovery_cron.py`, `routes/discovery.py`, scheduling/records/paths, `setup_discovery_task.py` | 31 | 9 | S1×4 |
| **P9** | Digest & email: `discovery_digest.py`, `email_render.py`, `discovery_notify.py`, `comment_draft.py` | 24 (25 as merged — B-113 found and folded in mid-package, see P9's plan §0/§8) | 4 | S2×7 |
| **P10** | Roster: `manifests/`, `migrate_handles_from_manifest.py`, `backfill_youtube_frontmatter.py` | 11 | 4 | **S0×1** |
| **P11** | Gate C: `scripts/lint_prompt_sheet.py`, `docs/style-library.md` | 28 | 3 | S1×7 |
| **P12** | Gate D & tools: `lint_script_language.py`, `resolve_brief_version.py`, `build-cowork-plugin.sh` | 15 | 3 | S1×4 |
| **P13** | Skill contracts: all `.claude/skills/**` | 48 | 22 | S2×14 |
| **P14** | Doc truth: `CLAUDE.md`, READMEs, `rgs-briefs/` | 9 | 6 | S1×1 |
| **P15** | UI: `templates/**`, `static/style.css`, `routes/browse.py`, `browse_service.py` | 16 | 10 | S2×10 |

### Execution sequencing — APPROVED LANDING ORDER

All 16 plans are written and validated: **328/328 findings covered, ~349 tasks, file
exclusivity verified, zero placeholders.** Plans live in `remediation/`.

File exclusivity means the *plans* were written in parallel safely, but it does **not**
make the landing order free. Three constraints bind it:

1. **Frozen-API adopters.** P2 changes `artifacts.py` in breaking ways (`parse_frontmatter`
   raises, `record_gate_override(at=)`, `write_pointer(repo_root)`, `classify_brief_change`,
   `reserve_version`/`write_reserved_artifact`/`release_version`). P3 and P4 are red until
   they adopt. **P2 lands before P3 and P4.**
2. **Deliberate tripwires.** Three packages carry tests that go red on a *successful*
   neighbouring merge — by design, to force the cleanup: P3's divergence-ledger test fails
   once P11 lands; P12's `strict=True` xfail XPASS-fails once P3 lands. **P3, P11 and P12
   land together**, or the follower retires the tripwire in the same commit.
3. **The F-64 rename is atomic.** `pipeline-app/scripts/` → **`pipeline-app/tools/`**
   (chosen over `pipeline_app/scripts/` because it preserves module depth, so P8's
   `parents[1]` index is unchanged and the silent-scheduled-task-failure trap never arises).
   The directory move, P8's `setup_discovery_task.py` update and P10's six file updates are
   **one commit**.

| Wave | Packages | Why here |
|---|---|---|
| **A** ✅ | **P0** → **P1** — both merged | P0 gives everything else a CI that proves its tests ran and a guard that stops a test billing Bright Data. P1 gives everything else somewhere to report a failure. Fixing anything before these means fixing it twice. |
| **B1** ✅ | **P2**, then **P10** — both merged | The four S0s. P2 holds three (artifact truncation, lost-version race, backfill overwrite); P10 holds the corpus destroyer. Land the data-loss fixes before anything that increases write traffic. |
| **B2** ✅ | **P3 + P11 + P12** (together) — all three merged | Tripwire cluster. Also the gate correctness core: P11's fail-closed parser, P12's fail-closed beat parser, P3's required-`upstream` and `UpstreamMap`. |
| **B3** ✅ | **P4**, then **P5** — both merged | P4 adopts P2's + P3's APIs and fixes the stage graph; P5 swaps its private `stage_id_by_skill` copy for P4's at its T19. |
| **B4** ✅ | **P6**, **P7**, **P8**, **P9** (parallel) — **all four merged** | Discovery. P8 consumes seams from P6 (`BlueskyFetchError` reaching the engine) and P7 (`drain_diagnostics`, `preflight`), so land P6 and P7 before P8; P9 is independent. P9 merged as PR #51 (`62e91d0`), closing 25 findings (24 original + B-113, discovered and folded in mid-package — see P9's plan §0/§8). |
| **B5** ✅ | **P15** — merged | Binds to P3's gate context keys and P1's `recent_events`; both already merged (P3 in Wave B2, P1 in Wave A). **Pre-flight check done 2026-08-19** (before Wave B5 kickoff): all 16 of P15's own findings confirmed untouched by any package that has landed since this plan was written; P3's gate/approval/edit contract already supplied every key P15's templates were planned to consume, so T9/T10/T22's "Consumes P3" dependency was already satisfied with no wait — see P15's plan §0. P15 merged as PR #54 (`8893789`), closing all 16 findings; its final whole-branch review found and fixed two Important, security-relevant gaps beyond its own 16 — see P15's plan §8. |
| **C** | **P13** ✅ merged — then **P14**, next, not started | Documentation describes the fixed code, or it is fiction again. P14 is last because six packages owe it contract decisions. |

**Programme status as of 2026-08-21:** Waves A, B1, B2, B3, B4, B5, and P13 (Wave C's first half)
are fully merged (**15 of 16 packages**: P0, P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P11, P12,
P15, P13). P13 merged as [PR #60](https://github.com/happydotemdr/ContentStudio/pull/60)
(`b9479b8`, 2026-08-21), closing all 48 of its findings. A follow-up outside P13's own scope — the
label-first sub-beat legality decision P13's T6 flagged as a genuine operator call rather than
deciding unilaterally — landed immediately after as [PR #61](https://github.com/happydotemdr/ContentStudio/pull/61)
(`9893072`). **P14 is the one package left.** It is unblocked by P13's merge but still has one
open upstream input (I7, from P6+P9: whether the YouTube-shaped `upload_date` alias in
`discovery_digest.py` is removed or kept) before all of its gated tasks can execute. See P13's own
plan, `remediation/P13-skills-contracts.md`'s "Status" section, for full detail.

### Cross-package contracts (frozen during validation)

| Producer → Consumer | Contract |
|---|---|
| P1 → P15 | `recent_events[]` = `{id, occurred_at, kind, severity, source, message, detail, run_id, acknowledged}`, unacked error/critical, 7 days, newest first, cap 50. `orphaned_count: int \| None` — `None` (sweep skipped) **must render differently from `0`**. |
| P3 → P15 | `gate_view[]` (`state ∈ passed\|failed\|errored\|never_ran\|unknown\|malformed`, `status_raw`, `blocking`, `findings`), `has_blocking_gate`, `gate_override`/`gate_overrides[]`, `artifact_version`, `artifact_created_at`, `artifact_finalized_at`, `inputs[]`, `edit_*`, `error_banner`. Blocked approve = **409 re-rendering `stage.html`**, never `PlainTextResponse`. `has_blocking_gate` is derived from `classify_gates()`, the single judgement `approve_stage` also reads. **Corrected 2026-08-19 (P15 merged):** `approval_block_reasons` was never actually produced by P3 — verified absent from the live repo at P15's T10. P15 derives the equivalent reason list in-template from `gate_view \| selectattr("blocking")` instead (a strict improvement — one classifier drives both the gate strip and the blocking-reason text). Do not plan against `approval_block_reasons` existing; it does not. Also: `gate_view.state` has a sixth live value, `malformed` (emitted when an artifact's `gates:` frontmatter isn't a list), not originally documented here. |
| P2 → P3, P4 | `compute_depends_on`, `read_artifact`/`MalformedArtifactError`, `reserve_version`/`write_reserved_artifact`/`release_version`, `record_gate_override(at=)`, `write_pointer(repo_root)`, `classify_brief_change`. |
| P4 → P3 | `gates.resolve_upstream_by_stage(*, repo_root=None, approved_only=False, include_optional=False)`; `_approved_artifact_path` lifted verbatim from P4, one copy. Returns an `UpstreamMap` with **three** states — absent / present / excluded — where reading an excluded key **raises**. |
| P4 → P5, P13 | `pipeline_config.stage_id_by_skill()`, `stage_template_path()`, duplicate-`skill:` topology rejection; SKILL.md declaration updates. |
| P6 → P8 | Typed errors (`BlueskyFetchError`, `YouTubeEnumerationError`, `YtDlpUnavailable`, `TranscriptFetchBlocked`) must reach `discovery_engine.py:272`, never the `:255` auto-exclude. |
| P7 → P8 | `drain_diagnostics()` per handle → `obs.record_event`; `preflight()` once per run. |
| P15 → P3, P5 | `browse_service.sanitize_html()`. Repo-wide rule: **`| safe` means "sanitized by its producer"**, because a consumer-side filter fails open the moment a site is missed. **Update 2026-08-19 (P15 merged):** P3 adopted this independently as its own `routes/stages._HTMLSanitizer` rather than calling P15's function — the two now have different tag allowlists and, until P15's final review caught it, opposite URL-scheme policies (P3's was an allowlist; P15's own was a denylist, fixed to match). P5's `routes/inspector.py` had adopted neither — P15's final review applied `browse_service.sanitize_html()` there directly as an authorized cross-package fix (P5 already merged, no active owner). Consolidating the two sanitizer implementations toward `browse_service`'s (the more adversarially-tested one, having survived six real bypass-class findings) is unclaimed programme-level tech debt — no package currently owns it. |
| P11 → P3 | Gate C parity contract, P11's plan §6 (P3-1 through P3-6). `parse_sheet(text)` stays a 2-tuple-unpackable `SheetParse`; `lint(...)` gains keyword-only `declared_shot_count=None`; every finding carries `beat`; Gate C emits only `kind="fail"`/`"parse"`, both blocking; `run_gates_for_stage` must derive blocking status from `linter.is_blocking()`/`NON_BLOCKING_KINDS` (P12's vocabulary), never a hardcoded string. **P3-6, added post-landing (PR #29):** the CLI now flags a sheet's own stray `WORLD LOCK` block when `--styleboard` is also supplied — `gates.py` does not yet have the equivalent check, a fifth CLI/app divergence beyond the four the audit found. P3's own T7 differential test won't catch this on its own fixture set; see P3's plan, "Handoff H1b," for what to check before trusting T6/T7 as written. |
| P9 → P14 | CLAUDE.md's "never a full post body" is unachievable as worded — code stays, doc changes. Wording in P9 §6.2(a). |
| P13 → P14 | Scope README's unmarked-`[C]` default to `docs/*.md`; 215 real skill-side provenance bugs after triage (of 367 unmarked). |

### The recurring defect class

One root cause appeared **five** times, and the fifth was found *inside a fix*: Bluesky
returned `[]` for both empty and failed; the cron returned `0` for both; the digest rendered
the same email for both; `browse_service` returned `False` for both; and the new
`approved_only` resolver would have returned an absent key for both. **Any representation
shared by "nothing here" and "something is wrong" is a defect by default.** P4 records this
in a test docstring so the rule outlives this programme.

---

## Package plan files

Each package's detailed, TDD, bite-sized plan lives at:

```
docs/superpowers/plans/remediation/<package-id>.md
```

Each is written by a dedicated planning agent that receives **only** its own finding IDs, its own file list, and this document's Global Constraints, test standard and frozen interfaces. No agent receives the full audit; no agent returns full context.

Every package plan must contain, in this order:

1. **Scope** — the exact file list it owns, verbatim, and its finding IDs.
2. **Finding → task map** — a table with every one of its finding IDs and the task number that closes it. Total coverage required; a finding with no task is a plan failure.
3. **Tasks** — bite-sized, TDD, with real code in every step (no placeholders).
4. **Finding → test map** — every finding ID, the named test that proves it closed, and which of the Three-Test Rule roles that test plays (fault / distinguishability / surfacing) where the finding is `silent`.
5. **Tests deleted or inverted** — any existing test that encodes the defect, by file:line, with the replacement.

---

## Verification (whole-programme)

The remediation is complete when all of these hold:

1. `docs/superpowers/plans/remediation/` contains 16 plan files; the union of their file lists equals the 114 audited files with no duplicates.
2. The union of their finding→task maps covers all 328 IDs exactly once (plus B-113, discovered and folded into P9 mid-programme — 329 findings closed against the audit's original 328, not a discrepancy: see P9's plan §0/§8).
3. CI exists and is green on both suites, run from a fresh worktree or the main checkout root (not a specific named worktree — those are created and torn down per package; do not hardcode a worktree path here, it will go stale the moment that worktree is removed):
   ```bash
   python -m pytest tests/ -q
   ```
   ```bash
   cd pipeline-app && python -m pytest -q
   ```
4. Every one of the 4 S0 and 43 S1 findings has a named regression test that was observed failing before its fix.
5. The six defect-affirming tests are gone or inverted, and `grep -rn "returns_empty_on_fetch_failure\|scoped_permissions_settings_scopes" pipeline-app/tests/` returns only inverted forms.
6. A scheduled discovery run with an injected adapter fault exits **non-zero** and leaves an `events` row of severity `error`. ✅ Closed by P8 (PR #48), confirmed via its own final review and CI.
7. Gate C rejects a sheet with a malformed shot heading instead of printing `PASS`. ✅ Closed by P11 (Wave B2, Gate C's owning package), verified end to end.
8. The operator-facing UI stops hiding or misrepresenting the signals the rest of this programme made trustworthy underneath: a gate that never ran reads as "never ran," not as a pass; an htmx request failure is visible, not silent; Browse shows what it can't read instead of omitting it; doctor.html stops printing the literal string `"None"`. ✅ Closed by P15 (PR #54), see its plan §8 for the full record, including the D-47 sanitizer's six independently-found-and-fixed security bugs.

**Baselines, last verified 2026-08-19 at `8893789` (P15 merged, i.e. `main`'s state):** root suite
445 passed/1 skipped/0 failed; app suite 1954 passed/4 skipped/2 xfailed/0 failed (the 2 xfail are
P15's T13, a deliberate, documented block on P8 landing a `handles` join — see P15's plan §8). CI
green on all three jobs (`app-suite`/`root-suite`/`no-live-credentials`), across both triggered CI
runs (branch push + PR event), on P15's merge commit. Re-verify at the start of each future
session — this line is a snapshot, not a live status.

**Baselines, last verified 2026-08-21 at `9893072` (`main`, P13 + its PR #61 follow-up both
merged):** root suite 533 passed/0 failed; app suite 1954 passed/4 skipped/2 xfailed/0 failed
(unchanged from P15's baseline — P13 and its follow-up touch no app-suite files). The root-suite
count moved from 445 (P15's baseline) not because of P13's own tasks, but because of an unrelated
77-commit backlog (elevenlabs-tooling, stitcher/native-pipeline, audio-preconditioning — none of
it this programme's scope) that landed on `main` during P13's execution window. The cowork-plugin
lock file (`scripts/cowork-plugin.lock.json`) needed a rebuild (`bash
scripts/build-cowork-plugin.sh`) after merging — expected drift any time `.claude/skills/**`
changes, not a regression. Re-verify at the start of each future session — this line is a
snapshot, not a live status.
