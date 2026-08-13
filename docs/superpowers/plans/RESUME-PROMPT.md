# Resume prompt — audit-remediation programme, P10 (T1 → T19)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, where it must stop, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-13, after P2 closed in full, PR #27 opened (not yet merged — see the operator
decision below), and a post-PR adversarial review filed 20 new findings.

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
3. `docs/superpowers/plans/remediation/P10-roster.md` — the plan being executed.

## Where execution is

**P0: complete (23 findings). P1: complete (13 findings). P2: complete (15 findings, T1–T18). 51 of
328 closed.**

Suites, verified in the worktree at P2's HEAD (`4829079`):
**root 247 passed**; **app suite, P2's own three test files (`test_artifacts.py`,
`test_migrations.py`, `test_grounding_service.py`): 109 passed**; **app suite, full run: 1054
passed / 32 failed / 3 skipped**. The 32 failures are **deliberate, expected cross-package
breakage** from P2's own breaking API changes (`write_pointer` gains a required `repo_root`,
`record_gate_override` gains a required `at=`, `identify_new_brief` deleted and renamed
`classify_brief_change`) landing before the packages that consume them adopt — this is the
programme's own landing-order design, not a defect. It affects `routes/stages.py`,
`approval_service.py`, `browse_service.py`, `discovery_digest.py`, `routes/inspector.py`, and their
tests. **Do not "fix" any of these files or tests from P10** — none of them are P10's, and the
window closes when P3/P4/P5/P9/P15 land and adopt the new signatures.

CI exists (3 jobs). It covers more than local — two symlink tests skip on Windows and execute only
on the runner, so a local pass is strictly weaker than a CI pass. **On PR #27, `app-suite` WILL show
red once CI finishes** — it runs the full app suite including the 32 expected cross-package
failures above. That is correct, expected behavior for this PR specifically; do not treat it as a
CI regression to chase.

### PR #27 — open, NOT merged. This is an operator decision, not yours to make silently.

`https://github.com/happydotemdr/ContentStudio/pull/27` — "fix(pipeline): P2 — artifact durability
(18 tasks, 15 findings, 3 of 4 S0s closed)". `root-suite` and `no-live-credentials` are green;
`app-suite` will be red for the reason above. **Unlike P0→P1 and P1→P2, this session's predecessor
did not wait for the PR to merge before handing off** (the post-PR adversarial review below
happened first, adding one more commit to the same branch). **Ask the operator whether PR #27
should be reviewed/merged before P10 starts**, or whether P10 should continue directly on this same
branch regardless (technically fine — P10 doesn't touch any file P2 touched, so there's no merge
conflict risk either way, but the established pattern every prior package has followed is
merge-before-continuing, and diverging from that pattern silently is exactly the kind of thing this
programme's own discipline exists to prevent). Do not merge it yourself without being told to; do
not proceed as if it's already merged.

The live database at `C:\Projects\ContentStudio\pipeline-app\pipeline.db` is still legacy v0. A dry
run against a copy already proved it migrates cleanly.

## NEW since the P2 resume prompt: a post-PR-#27 adversarial review filed 20 findings — read this before touching anything

After PR #27 was opened, the operator asked for a narrowly-focused, parallel, Opus-tier adversarial
review of every one of P2's 18 task diffs (18 independent subagents, each blind to the SDD-time
reviews, hunting for plan deviations, hardcoded values, silent failures, and anything else
suspicious). The controller spot-verified the highest-severity claims directly (not just trusted the
reports) before filing — reproduced a Unicode-digit regex collision live, confirmed two production
call sites were never migrated to a new safety mechanism, confirmed three files are genuinely
failing today, not hypothetically.

**All 20 are filed, none are fixed** — documentation only, per explicit instruction. Full detail
with file:line citations, verified failure scenarios, and validation notes:
`docs/superpowers/plans/remediation/P2-artifact-durability.md`, section **"7a"**.

**None of the 20 are P10's files or responsibility.** But five are worth knowing about now because
they name specific future packages by the files they touch, and that package's own session should
NOT rediscover them from scratch or treat them as new:

| ID | Severity | One-line | Belongs to (by file ownership) |
|---|---|---|---|
| P2R-01 | Important | A-65 only partially closed — neither `routes/stages.py` nor `turn_service.py` was migrated to the new exclusive `reserve_version()`; when the new `ArtifactExistsError` guard *does* fire, nothing catches it in either caller (the async turn-route case is worse than a clean 500 — the turn is already billed and marked complete before the silent failure) | P3 (`routes/stages.py`), P4 (`turn_service.py`) |
| P2R-06 | Important | The backfill migration's idempotent adoption always adopts unconditionally, silently discarding a better recomputed reconstruction on retry, and defeats P2's own T13 `depends_on` fix for exactly the population it targets | P2's own file (`migrations.py`) — no package currently owns follow-up work on it; flag for the final whole-branch review or a dedicated cleanup task |
| P2R-15 | Important | The grounding pointer's containment check doesn't survive a symlink/junction — verified with a live exploit on this host | Same as above — `artifacts.py`/`grounding_service.py`, no current owner for a follow-up |
| P2R-17 | Important | `parse_frontmatter`'s new raise breaks graceful degradation in `discovery_digest.py`, `browse_service.py`, `routes/inspector.py` — **verified as currently-failing tests**, and the `discovery_digest.py` case is a severity *upgrade* (one bad item now kills the whole daily email, not just that item) | P9 (`discovery_digest.py`), P15 (`browse_service.py`), P5 (`routes/inspector.py`) |
| P2R-19 | Minor | `browse_service.py`'s own artifact-version regex remains un-synced with P2's tightened one, with a visible UI tie-break bug | P15 (`browse_service.py`) |

The remaining 15 (P2R-02/03/04/05/07/08/09/10/11/12/13/14/16/18/20) are P2-internal (its own files,
tests, or docstrings) with no current owning package — same disposition as P2R-06/15 above. **Do
not fix any of these from P10.** If P10's own work happens to touch a file one of them names,
re-read that specific finding before assuming it's unrelated.

## YOUR TASK THIS SESSION: P10 (T1 → T19), then STOP

**Start at T1.** P10 is untouched — nothing in it has been pre-reviewed or dispatched yet.

P10 carries the audit's **4th and last S0 (data-destroying) finding, D-04** — a corpus-destroying
roster/frontmatter backfill — and is Wave B1's second half, landing after P2 specifically so P2's
artifact-durability S0 fixes are already in place before P10 increases write traffic against
adjacent parts of the repo.

### Files this package owns (no other package may touch these)

```
manifests/brand_sources.json                                  (REPO ROOT)
pipeline-app/scripts/migrate_handles_from_manifest.py
pipeline-app/scripts/backfill_youtube_frontmatter.py
pipeline-app/tests/test_migrate_handles.py
pipeline-app/tests/test_backfill_youtube_frontmatter.py
```

### Files this package reads but must NOT modify

| File | Owner | Why we read it |
|---|---|---|
| `pipeline_app/db.py` | P1 | `get_connection`, `init_db`, `list_platform_handles`, `get_handle_by_platform_and_handle` |
| `pipeline_app/schema.sql` | P1 | `creators`, `handles.creator_id`, the platform CHECK |
| `pipeline_app/obs.py` | P1 | `obs.log`, `obs.record_event` |
| `pipeline_app/discovery_paths.py` | P8 | `handle_slug`, `find_slug_collision` |
| `run_discovery_cron.py` | P8 | `build_adapters()` — the platform registry `PLATFORMS` is pinned against |
| `pipeline_app/discovery_youtube_api.py` | P6 | `api_key()`, `fetch_metadata`, `MAX_IDS_PER_CALL` |
| `pipeline_app/artifacts.py` | **P2 — now hardened, see below** | `parse_frontmatter`, `render_frontmatter` |
| `download_brandintel.py` | **unowned by any package** | the manifest's *other* consumer — see the hard constraint in P10-roster.md §1 |

**`parse_frontmatter` now raises `MalformedArtifactError` instead of degrading (P2, A-68/A-69).** If
`backfill_youtube_frontmatter.py` calls it anywhere, verify it's already handling the new exception
type — this is exactly the class of regression P2R-17 (above) found in three *other* files. Check
before assuming the old degrade-to-`({}, text)` behavior still holds.

**Hard constraint — the manifest schema change must be additive.** `download_brandintel.py:387-402`
reads `roster.get("youtube")` etc. as flat arrays using only `handle`/`display_name`/
`keyword_filter`. That file is in no package's list, so it may not be edited — the new schema keeps
every existing top-level array in place with its existing entry shape and adds new keys/fields
alongside. Restructuring into a creator-keyed tree would silently break the corpus downloader.

### Finding IDs owned (11)

`B-70`, `B-71`, `B-75`, `B-76`, `B-77`, `B-78`, `B-79`, `B-81`, `B-85`, `D-04` (**S0**), `D-05`

### What "done" means for this package

The operator asks *"are we tracking all social platforms for our key creators?"* and gets an answer
from a committed file plus one command, with **zero `UNANSWERABLE` cells**:

```bash
cd pipeline-app && python scripts/migrate_handles_from_manifest.py --report
```

### The 19 tasks, all in `P10-roster.md`

| Task | Finding | Sev / mode | What it does |
|---|---|---|---|
| T1 | B-70 | S2 coverage-gap | `PLATFORMS` pinned to the adapter registry (7 keys, not 6) |
| T2 | B-71 | S2 silent ⭐ | An unrecognized top-level manifest key is a hard, event-recorded error |
| T3 | B-70, B-71 | — | Seeding loop is registry-driven, not two hardcoded keys |
| T4 | B-70, B-77, B-78 | — | Rewrite `manifests/brand_sources.json` to the new schema |
| T5 | B-77 | S4 latent | Explicit `cohort` wins; `derive_cohort` is fallback only |
| T6 | B-78 | S3 coverage-gap | `included` is honored; out-of-scope entries ship excluded |
| T7 | B-75 | S3 silent ⭐ | Seed as `pending`, never `validated` |
| T8 | B-76 | S2 silent ⭐ | Re-running applies manifest edits without stomping run-owned columns |
| T9 | B-76 | S2 silent (surfacing) | DB rows absent from the manifest are reported as drift |
| T10 | mechanism (B-70/B-72) | — | Populate `creators` and `handles.creator_id` |
| T11 | B-70, B-81 | — | `--report`: creator × platform coverage matrix, zero `UNANSWERABLE` cells |
| T12 | B-81 | S3 latent | Shipped-manifest integrity test, fixes a misleading test name |
| T13 | B-79, B-85 | S2/S4 | Manifest `_comment` truth: rss scope, skill count |
| T14 | D-04 | **S0** silent ⭐ (fault) | Backfill refuses to enrich without a working API key |
| T15 | D-04 | **S0** silent ⭐ (distinguishability) | A total enrichment miss aborts before any write |
| T16 | D-04 | **S0** silent ⭐ | Never downgrade provenance, never null an existing value |
| T17 | D-04 | **S0** silent ⭐ (surfacing) | Per-file failures are counted and reflected in the exit code |
| T18 | D-05 | S3 silent ⭐ | Unparsed metadata is counted, skipped, and marked `metadata_inferred` |
| T19 | — | — | Whole-package verification |

⭐ = flagged by the plan as needing the Three-Test Rule or extra S0 care. **T14–T17 together are
D-04, the corpus-destroying finding** — treat this four-task span with the same care P2 gave its
three S0s: adversarial pre-review of the plan's own code before any dispatch, and probe filesystem
behavior empirically rather than assuming.

## THE PAUSE / COMMIT / PR POINT: end of P10, before P3+P11+P12 (Wave B2)

**Stop when T19's verification is clean.** Then: run both suites, confirm P10's own two test files
are green (root suite is unaffected by P10 either way), push, and open a PR titled for P10's
completion, same shape as PR #27's body — findings closed, suite numbers, what the operator will
notice on next boot, what is knowingly still open. **Do not start Wave B2 (P3, P11, P12) in this
session.**

**Why this exact point.** Wave B1 is "P2, then P10" — sequential — specifically so P2's
artifact-durability S0s land before P10's own corpus-write S0. Wave B2 (P3+P11+P12) is a different
kind of unit: those three land **together**, because P3 and P12 carry deliberate tripwire tests that
go red on each other's successful merge (see §7 of `EXECUTION-KICKOFF-PROMPT.md`). Do not begin
Wave B2 with momentum from P10 — its risk profile (gate correctness, not filesystem durability or
corpus safety) is different enough that carrying over assumptions from P10 is exactly the failure
mode this programme keeps catching.

## The bar, restated because it is what everything else serves

**"Any representation shared by 'nothing here' and 'something is wrong' is a defect by default."**
This root cause has now appeared, by the controller's own count across P0–P2, in **40+ confirmed
instances**, the large majority of them written by the remediation itself — not the original bugs.
That ratio is the entire reason the pre-review discipline exists, and why the *post-PR* adversarial
review this pause window added 20 more findings on top: **a task review that only checks "does this
diff satisfy its own task's tests" is not the same as "is this diff actually correct," and P2's own
task-by-task reviews (which were thorough — 5 of 18 tasks needed a fix round) still missed all 20 of
the P2R findings.** Consider running an equivalent adversarial pass on P10 before declaring it done,
not only after — the earlier a defect is caught, the cheaper it is.

For every `silent` finding, the **Three-Test Rule** is mandatory: fault, distinguishability,
surfacing. Surfacing means an events row, a non-zero exit code, or a rendered UI element —
*asserting that a `print()` happened does not count*.

**Anti-tautology:** never assert on a hard-coded value; never assert a mock was called; if a test's
name describes a defect, delete or invert it. A plan must never mandate a tautology and defer the
fix to the implementer. **P2R-20 (filed this pause window) is a fresh list of five tautological
assertions the SDD-time reviews missed** — read it before writing new tests for D-04's four-task
span, since a "does the value hard-coded by the fixture match itself" assertion is exactly this
shape and is easy to write by accident under time pressure.

**Coverage is not the bar.** There is no coverage gate. The bar is: for each finding, a named test
that fails before the fix and passes after — **and you must actually observe the failure.**

## Process that is now mandatory — all of it (unchanged from P2, still binding)

1. **Adversarially pre-review the plan's own code before dispatching any implementer.** P2's plan
   had defects in T1, T5/T6 (a genuine circular dependency between two tasks), T8, T9, T14, and T17
   — found and fixed before dispatch. Expect the same rate here. **Probe SQLite, the filesystem, and
   the manifest-JSON parser empirically rather than reasoning about them.**
2. **Run `compile_plan.py` on the plan before every dispatch.** It compiles every fenced `python`
   block. Lives in the session scratchpad; rewrite it if gone (~30 lines, `textwrap.dedent` each
   block, compare failing block COUNT against a baseline). **P10 has not been baselined — the first
   pre-review pass's run establishes it; note it in the ledger.**
3. **Amend the plan FIRST, then execute the amended step.** Never improvise around a plan defect
   silently. Every amendment gets its own commit explaining what was wrong and why.
4. **Your own corrections will contain the defect they were written to catch.** Happened repeatedly
   in P1 and at least twice in P2 (the T5/T6 pre-review amendment's own claim about which tests
   exercise HWM survival was itself wrong, caught by the implementer). Tell implementers explicitly
   to report reality rather than match the brief.
5. **When a fix round produces a NEW instance of the defect class, the signal is about the design,
   not the implementer.**
6. **When a task adds N kinds of guarantee, apply the twin/parametrized discipline N times** — per
   behaviour, not per call site. P2's own T18 durability-contract class, believed complete, was found
   by the post-PR review to have a test (`test_the_target_is_never_observed_zero_length`) that is
   non-discriminating for **all four** writers, not the one writer previously known — verify this
   class of gap doesn't recur in D-04's per-file/per-failure-mode test span (T14-T17).
7. **Check every `silent` finding's surfacing test for the same-connection read before dispatch.**
   Still the single most repeated defect class across the whole programme. If D-04's tasks touch
   `events` rows, use the second-connection idiom (`tests/test_db.py:339-364`, `:663-676`).
8. **A crash/failure-injection test must actually inject the fault at the moment that matters**, not
   merely call the function and check the end state — verify the fault fires *between* the two
   states the guarantee is about.
9. **Consider a post-implementation adversarial review pass, not only a pre-review one.** New lesson
   from this pause window: 20 real findings survived P2's per-task reviews. If time allows, run a
   parallel adversarial review of P10's own diffs before opening its PR — same pattern as this pause
   window's review of P2, findings-only, no fixes, filed for validation.

## Traps, verbatim (unchanged from P2, still binding — re-verify each empirically if D-04's tasks touch new ground)

- **`python -m` is mandatory.** A bare `pytest` at the repo root reports "201 passed"/"247 passed",
  exit 0, while silently omitting all app tests. Run `cd pipeline-app && python -m pytest` and, from
  the repo root, `python -m pytest tests/ -v`.
- **`pipeline-app` is installed EDITABLE against the MAIN checkout**, not this worktree. A bare
  `pytest` in `pipeline-app/` tests the WRONG CHECKOUT (a guard aborts it).
- **The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db`** — main checkout,
  git-ignored. Never write to it; open read-only and copy to scratch. **P10 also touches
  `manifests/brand_sources.json` and real corpus frontmatter files under `output/`** in the same
  spirit — never let a test write into the operator's real corpus; always `tmp_path`.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always
  `encoding="utf-8", errors="replace"`.
- `os.kill(pid, 0)` **terminates** the process on Windows. Use `OpenProcess` for liveness.
- **Never invoke `bash`/`sh` by bare name in a subprocess.** Resolve with `shutil.which()`.
- **`BRIGHTDATA_API_KEY`, `RESEND_API_KEY`, `YOUTUBE_API_KEY` are set in the ambient environment.**
  D-04's whole point is a YouTube-metadata-enrichment backfill — **this task family is the highest
  live-vendor-API risk in the programme so far.** Never let a test reach the real YouTube API; the
  conftest guard blocks unstubbed calls, but D-04's tests specifically must prove the *key-missing*
  and *total-miss* paths without ever making a real call — verify the mock/stub boundary carefully.
- Writing a commit message through `bash -c "..."` **eats anything in backticks**. Use a quoted
  heredoc (`git commit -F - <<'MSG'`).
- **An apostrophe inside a single-quoted shell block terminates it.**
- **`grep -c` exits 1 when the count is zero**, silently truncating a `&&` chain. Use `;` instead.
- `pipeline.yaml` is at the repo root. App modules are flat in `pipeline-app/pipeline_app/*.py`.
- The linters in the root `scripts/` are stdlib-only, loaded by file path, cannot use `obs.py`.
- **Anything non-trivial embedded in YAML/JSON is untestable by construction.** Extract it.
- **`os.replace(src, dst)` on Windows is atomic and silently overwrites an existing `dst`** —
  verified repeatedly across P2. If any D-04 task writes frontmatter atomically, this still holds,
  but P2R-08 (filed this pause window) found real gaps in how P2's own atomic-write callers handle a
  *retry-exhausted* sidecar-write failure — read it before assuming "atomic write" alone is
  sufficient for D-04's "never downgrade provenance" guarantee (T16).
- **NEW this pause window: a `str` regex pattern's `\d` is Unicode-aware in Python**, and `int()`
  parses non-ASCII decimal digits. P2R-02 found this makes `artifacts._VERSION_RE` non-injective
  despite its own comment claiming otherwise (`artifact.v1٧.md` → `int` 17, colliding with
  `artifact.v17.md`). If D-04's tasks parse any numeric field from a filename, handle name, or
  frontmatter value using `\d`, use `[0-9]` instead and verify empirically — do not trust a regex
  comment's injectivity claim without testing it against a non-ASCII digit string.

## Frozen cross-package interfaces — do not redesign

From P0/P1 (already shipped, consumed by everyone):

- `obs.log(event, *, level, **fields)`
- `obs.record_event(conn, *, kind, severity, source, message, detail, run_id) -> int`. **Must never
  raise** — falls back to `log()` and returns `-1`.
- `| safe` means sanitized by `browse_service.sanitize_html()`.
- P1→P15: `recent_events[]`, `unacknowledged_error_total: int`, `orphaned_count: int | None`.

**From P2 (shipped this pause window — landed, stable, but see P2R findings above for known gaps):**

- `parse_frontmatter(text)` — **now raises `MalformedArtifactError`** for an unterminated
  frontmatter block or non-mapping YAML, instead of returning `({}, text)`. The genuinely-no-
  frontmatter case is unchanged. **If P10 calls this anywhere, verify the new exception is handled**
  — see P2R-17 above for three files that weren't.
- `record_gate_override(..., at=...)` — required keyword-only `at`. Not P10's concern (P10 doesn't
  touch gate overrides), noted for completeness.
- `write_pointer(..., repo_root=...)` — required `repo_root`. Not P10's concern.
- `identify_new_brief` → **deleted**, renamed `classify_brief_change`. Not P10's concern.
- `reserve_version()` / `write_reserved_artifact()` / `release_version()` — the new exclusive
  version-allocation protocol. **P10 does not write pipeline artifacts** (it writes
  `manifests/brand_sources.json` and corpus frontmatter under `output/`, a different tree), so this
  almost certainly doesn't apply — but if any D-04 task turns out to touch `runs/` artifacts, use
  this protocol, not the old `next_version_number`/`write_artifact` pair (see P2R-01: **the two
  production callers that still use the old pair were never migrated** — do not add a third).
- `compute_depends_on`, `read_artifact` — stable, P3/P4's contract. Not P10's concern.

The `_MIGRATIONS` contract and schema.sql-vs-migration split are P1's. `runs/` artifact durability is
P2's. Carried here only so you recognize them and don't touch P1's or P2's files if a D-04 task's
reasoning tempts you to.

## Open findings — filed, NOT fixed, awaiting validation (carried forward from before P2, still open)

1. **`ux_discovery_single_running` (`schema.sql:90`) crashes `init_db`** on a legacy DB with two
   `'running'` discovery runs, before `events` exists. **P6–P9.** Not triggered by the operator's
   current database.
2. **An unknown platform posted by hand returns 500** where convention is 400. **P8.**
3. **`discovery_handles.html`'s `<select>` is a fourth unpinned copy of the platform vocabulary.**
   **P8/P15.**
4. **`list_handles_for_creator` returns `[]`** for both "no handles" and "no such creator". Deferred
   to the final review.
5. **Migration tests that don't pin `obs.LOG_DIR` write into real `pipeline-app/logs/`.** Fix is an
   autouse fixture in `conftest.py`, **P0**'s file.
6. **B-82 is NOT closed.** P1 shipped the storage half; nothing in production calls it. **P8** must
   wire the discovery engine's branches; **P15** must render the counter.
7. **C-88b (S1, silent) → P12 T1b.** `_beat_name` returns `None` for two different conditions.
8. **The script format is authoritatively defined nowhere → P13.**
9. **`create_app` (`main.py`) has five unguarded statements after its topology-load `try/except`** —
   a leak on any of their exceptions. Flagged for the final whole-branch review.

**Plus the 20 P2R findings filed this pause window** (`P2-artifact-durability.md` §7a) — see the
table above for the five that name a specific future package; the rest have no current owner.

## The decisions that are NOT yours

**Stop and ask the operator:**

- **Should PR #27 be merged before P10 starts, or does P10 continue on this same branch regardless?**
  (New this pause window — see above.)
- **Should label-first sub-beats (`mechanism: (11–18s | 19 words)`) become legal?** Filed in P13,
  currently pending.
- **P10 T4/T6 itself** sets `@bigthink` and `adamgrant.bsky.social` to `included: false` — this is a
  change to what gets tracked, already decided and written into the plan's own worked example
  (`P10-roster.md` §3.3) as `"included": false` with rationale — **not a fresh decision to make**,
  just confirm the plan's existing text is what ships.
- **P7 §6 C1** adds a per-platform `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` override — the only change in
  the programme that can increase spend. Not P10's concern.

**Already decided — do not re-ask:**

- **T13b's design: option 4, accept and detect** (2026-08-09).
- **CI required checks: deferred to the end of the programme** (2026-08-10).
- **A plan-mandated finding that is an instance of the recurring defect class does not get
  escalated** — fix it. Escalate only genuine product/policy choices.

## Context discipline — a hard rule

Never give a subagent the audit, another package's plan, or this whole brief. Generate a task brief
with `.superpowers/sdd/2026-08-08-audit-remediation/brief-T.sh <plan> <N> <out>` and pass the path
(P10's headings are `### T<N> — ...`, the same shape `brief-T.sh` already handles). Subagent replies
must be 8 lines or fewer; their full reports go to files in the SDD workspace.

Review packages come from the skill's `scripts/review-package <plan> <BASE> <HEAD>`. BASE is the
commit recorded *before* dispatching the implementer — never `HEAD~1`.

**If you run a post-PR adversarial review pass (recommended, see above):** dispatch one subagent per
task diff, in parallel, on the most capable available model, each blind to the SDD-time reviews and
to each other's findings, instructed to find and document only — never fix. Spot-verify the highest-
severity claims yourself before filing them (empirically — run the reproduction, don't just trust
the report), the way this pause window's review verified the Unicode-regex collision and the
unmigrated production callers live before writing them into the plan.

## Definition of done (the whole programme, not this session)

1. All 328 findings closed — each verified by the mechanism its plan names, not merely by a helper
   existing (see B-82). Plus the 20 P2R findings and the 9 pre-existing open findings above, once
   each is routed to and closed by whichever package ends up owning it.
2. Both suites green: `python -m pytest tests/ -q` and, from `pipeline-app/`, `python -m pytest -q`.
3. CI exists (3 jobs) and is green.
4. Every S0/S1 has a regression test **observed failing first**.
5. Defect-affirming tests gone or inverted.
6. A scheduled discovery run with an injected fault exits non-zero **and** leaves an error events
   row.
7. Gate C rejects a malformed shot heading.
8. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing.
</content>
