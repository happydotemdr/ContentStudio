# ContentStudio Pipeline Audit — 2026-08-08

328 findings across six appendices: [A — Pipeline Core](appendix-A-pipeline.md) · [B — Discovery, Bright Data, Cron & Email](appendix-B-discovery.md) · [C — Skills, Contracts & Linters](appendix-C-skills.md) · [D — Silent Failures & Trust Boundary](appendix-D-silent-failures.md) · [E — User Interface](appendix-E-ui.md) · [F — Test Suite](appendix-F-tests.md)

---

## 1. What this audit was and how it was run

Sixteen atomic tasks (T0–T15), each with a **file-exclusive scope**: a task that traced into
another task's files cited them as evidence and handed the finding off rather than filing it,
so a defect is owned in exactly one place. Every finding uses one record schema — severity,
confidence, evidence at `path:line`, component, failure mode, blast radius, trigger, proposed
fix, fix cost, dependencies, owning task, detection method. Findings extend a set of
pre-confirmed seeds (SEED-3, SEED-4, SEED-6, SEED-7, SEED-8, SEED-12, SEED-15) rather than
re-deriving them.

Method was manual tracing plus execution of the two test suites. **T0 ran both suites from
their own rootdirs with line coverage** — root suite 201 passed / 95%, app suite 833 passed +
3 skipped / 95%, 1,034 green in ~23 s. `pytest-cov` was not installed; it was installed as
part of this audit, which means coverage had never been measured on this repo before now
(F-01). Beyond the suites, execution was limited to targeted linter runs: T10 executed **25
mutation experiments** against the repo's own green fixtures, and every "confirmed" Gate C or
Gate D evasion in Appendix C was run and observed rather than reasoned about. T12 verified
Python-Markdown's non-sanitizing behavior locally and confirmed the ambient shell's encoding
and credential state. Nothing else was executed and **no code was changed** — this is a
documentation-only audit.

One process fact worth stating plainly: **two appendices were lost to a concurrent-write race
mid-audit** and were **recovered from the authoring agents' own context** rather than
re-derived from source. Specifically:

- **Appendix B** — T4 (25 findings), T5 (25) and T6 (16) had each appended their sections;
  T7 then read a stale copy and wrote back over all three. All 66 findings were re-emitted by
  their original authors and merged in ID order (T4 → T5 → T6 → T7), giving the 89 present now.
- **Appendix D** — T11 (6 findings) was overwritten by T12. T11's section was restored from a
  snapshot taken before T12 landed, giving the 21 present now.

Appendices A, C, E and F were never affected: A took three appends (T1, T2, T3) and C took
three (T8, T9, T10) without collision, and E and F had a single concurrent writer at a time.
The cause is a lost-update race — read file, append section, write whole file back — not a
tooling failure; after it was detected, every remaining task wrote to an exclusive file that
was merged deterministically. Section headings and finding-ID ranges were re-counted after
each merge and match the authors' reported totals exactly, but the recovered *prose* was not
re-diffed against the originals, so a transcription slip inside a recovered record would not
have been caught. That is a limitation of this audit, not of the code.

Separately, the T0 baseline in Appendix F carried an error of its own: per-file test counts
were first taken with `grep -c 'def test_'`, which silently misses `async def test_`. It
undercounted `test_turn_service.py` as 2 tests when it has 11. T14 caught it; §6 of Appendix F
now uses `pytest --collect-only` and records the retraction. An audit about measurements that
look right and aren't should say when its own did the same.

---

## 2. The verdict

The most important thing this audit found is that **this codebase catches errors unusually
well and tells almost nobody about them**: there is not one bare `except:` in 8,550 lines of
Python, `contextlib.suppress` appears zero times, and the great majority of broad handlers
carry a documented rationale naming the exact failure they contain — but there is no logging
module, no error or event table, no health endpoint and no alert path, so 35 of the 39
`print(..., file=sys.stderr)` calls on the scheduled path write into a console Windows Task
Scheduler destroys (D-02, B-42, B-93). That single missing layer is why the system's dominant
failure shape is *looking fine* — 169 of 328 findings are classed `silent`, and a scheduled
discovery run exits `0` in eight distinct real-failure states including "every handle raised"
and "the email never sent" (B-40, B-41, D-01). The skill handoffs are correct for seven of
nine stages and wrong for the last two in a way that ships: `assembly` and `repurpose` are
told by their own kickoff templates that the script is present when `depends_on` cannot reach
it, the styleboard bindings and music bed arc are unreachable at the stage that needs them,
and the RGS grounding pointer — which carries the "constraints that survive to publish" line —
is computed, passed and discarded at both stages with no warning (A-01 through A-04). There is
hardcoded and stubbed material, and one piece of it is load-bearing: `scoped_permissions_settings()`
restricts nothing despite its name, its docstring and a green test asserting that it does
(D-43, F-11), and the migration writes `artifact.v1.md` at a literal version that overwrites a
real styleboard without checking (A-73). Yes, the system can look fine when it isn't — Gate C
prints `PASS` on a sheet whose aspect ratio is landscape, whose style code was invented, or
one of whose shots was deleted from all twenty checks by a one-character heading typo, and all
three were reproduced (C-81, C-79, C-70). Discovery's creator coverage cannot be answered from
this repository at all: two of six platforms have a declarative roster, the other four exist
only in a git-ignored SQLite file, there is no notion of "same creator across platforms", and
of 90 creator×platform cells 74 are unanswerable (B-70, B-72). The cron and email mechanism
itself is sound and carefully written — the email is the *only* channel that surfaces
`completed_with_errors` — but it has no failure channel of its own, so an unsent email and a
quiet day are the same inbox (B-94, B-95). The UI's CSS system is coherent and does not need
rework; its information architecture and its state display do, and the worst case is a stage
page where a gate that never ran renders as a clean pass and the approve button leads to an
inescapable 409 (E-02, E-03). The tests are the sharpest surprise: 1,034 green tests at 95%
coverage on both suites, **all 32 S0/S1 defects within one assertion of being caught, none of
them caught, and six tests that assert the defective behavior is correct** (F-10, F-12, F-13,
F-21). None of this is fatal and most of it is cheap — 230 of 328 fixes are S-sized, the four
data-destruction defects live in two modules, and the highest-leverage single change in the
list is a CI workflow that does not exist yet (F-60).

---

## 3. The register

All 328 findings, sorted by severity (S0 first) then component then ID. Severity key: **S0**
data loss or corruption · **S1** wrong output ships silently · **S2** operator misled or
failure invisible · **S3** correctness-adjacent but recoverable · **S4** hygiene.

Distribution: **S0 4 · S1 43 · S2 134 · S3 98 · S4 49.** By failure mode: silent 169 · latent
69 · docs-drift 35 · coverage-gap 30 · loud 25. By confidence: confirmed 305 · probable 22 ·
suspected 1. By fix cost: S 230 · M 95 · L 3.

| ID | Title | Sev | Component | Failure mode | Evidence (first) | Fix cost | Task |
|---|---|---|---|---|---|---|---|
| A-63 | `write_artifact`, `stamp_final` and `record_gate_override` truncate in place — no temp+rename | S0 | artifacts | silent | `pipeline-app/pipeline_app/artifacts.py:72-76` | S | T3 |
| A-65 | `next_version_number` is an unlocked read-then-write spanning a gate run; concurrent writes collide and one is lost | S0 | artifacts | silent | `pipeline-app/pipeline_app/artifacts.py:44-46` | M | T3 |
| A-73 | Backfill writes `artifact.v1.md` at a hardcoded version and overwrites unconditionally | S0 | artifacts | silent | `pipeline-app/pipeline_app/migrations.py:63-82` | S | T3 |
| D-04 | Corpus backfill destroys metadata and reports success when the Data API is unavailable | S0 | infra | silent | `pipeline-app/scripts/backfill_youtube_frontmatter.py:158` | S | T11 |
| A-60 | Hand edit copies `depends_on` from the prior artifact; empty on a first edit and sticky forever | S1 | artifacts | silent | `pipeline-app/pipeline_app/routes/stages.py:248-251` | S | T3 |
| A-62 | Hand-edit path runs Gate C with no upstream map — a different gate recorded under the same name | S1 | artifacts | silent | `pipeline-app/pipeline_app/routes/stages.py:266` | S | T3 |
| A-80 | The grounding pointer has no hash or version pinning — the brief can change under an approved stage | S1 | artifacts | silent | `pipeline-app/pipeline_app/grounding_service.py:24-31` | M | T3 |
| B-02 | MAX_ITEMS_PER_RUN=10 silently truncates active accounts with no recovery path | S1 | discovery | silent | `pipeline-app/pipeline_app/discovery_x.py:39` | M | T4 |
| B-06 | A transient Bluesky failure during validate_handle permanently disables the handle | S1 | discovery | silent | `pipeline-app/pipeline_app/discovery_bluesky.py:40` | S | T4 |
| B-10 | cp1252 subprocess decoding crashes or corrupts YouTube enumeration on emoji titles | S1 | discovery | silent | `pipeline-app/pipeline_app/discovery_youtube.py:61` | S | T4 |
| B-12 | A bot-blocked YouTube download writes a permanent transcript-less capture | S1 | discovery | silent | `pipeline-app/pipeline_app/discovery_youtube.py:217` | M | T4 |
| B-47 | Unvalidated timezone / time_of_day settings permanently wedge the scheduler | S1 | discovery | silent | `pipeline-app/pipeline_app/routes/discovery.py:105-109` | S | T5 |
| B-50 | Sleep/hibernate or a wedged heartbeat lets a live run be reclaimed — two concurrent runs | S1 | discovery | silent | `pipeline-app/pipeline_app/discovery_engine.py:299-300` | M | T5 |
| A-30 | Hand-edit Gate C reads an operator-authored world lock, not the styleboard | S1 | gates | silent | `pipeline-app/pipeline_app/routes/stages.py:266` | S | T2 |
| A-44 | Approval never checks staleness, and an unapproved draft is never marked stale | S1 | gates | silent | `pipeline-app/pipeline_app/turn_service.py:66-68` | M | T2 |
| A-51 | `save_skill` accepts empty content and silently truncates a SKILL.md or template | S1 | gates | silent | `pipeline-app/pipeline_app/routes/skills.py:78` | S | T2 |
| A-52 | Kickoff-template saves are never committed, so they have no recovery path | S1 | gates | silent | `pipeline-app/pipeline_app/routes/skills.py:90` | S | T2 |
| D-03 | The "empty ≠ failed" discipline was applied to Bright Data but never to YouTube | S1 | infra | silent | `pipeline-app/pipeline_app/brightdata_job.py:6` | M | T11 |
| D-45 | A stage turn can rewrite the Gate linters the app then exec's in-process | S1 | infra | silent | `pipeline-app/pipeline_app/cli_runner.py:39-45` | M | T12 |
| D-46 | A stage turn can rewrite the PreToolUse hook script, which then executes as code | S1 | infra | silent | `pipeline-app/pipeline_app/cli_runner.py:39-45` | M | T12 |
| F-60 | No CI exists: 1,034 tests run only when a human remembers, from two directories | S1 | infra | latent | `.github/PULL_REQUEST_TEMPLATE.md` | S | T15 |
| F-63 | `pipeline_app` is installed editable against the MAIN checkout; a worktree can test the wrong tree | S1 | infra | silent | `pip freeze` | S | T15 |
| C-70 | A one-character shot-heading typo deletes the shot from Gate C, silently | S1 | linters | silent | `scripts/lint_prompt_sheet.py:17-20` | S | T10 |
| C-75 | `--style-library` is an unconstrained CLI-only escape hatch that voids C20 | S1 | linters | silent | `scripts/lint_prompt_sheet.py:978-984` | S | T10 |
| C-79 | C16 accepts any digit string, so an invented numeric `--sref` passes | S1 | linters | silent | `scripts/lint_prompt_sheet.py:638` | M | T10 |
| C-80 | A bare `--p` satisfies C17 while providing no recorded style lock | S1 | linters | silent | `scripts/lint_prompt_sheet.py:652-671` | S | T10 |
| C-81 | C13 checks that `--ar` is present, never what it says | S1 | linters | silent | `scripts/lint_prompt_sheet.py:591-592` | S | T10 |
| C-88 | An unrecognized beat heading deletes the beat from Gate D with no finding | S1 | linters | silent | `scripts/lint_script_language.py:24` | S | T10 |
| C-89 | The dropped-text detector is opt-in via the artifact it audits | S1 | linters | silent | `scripts/lint_script_language.py:35` | S | T10 |
| C-96 | A wrong `--dir` or CWD silently reports "no prior version" and proposes v1 | S1 | linters | silent | `scripts/resolve_brief_version.py:39-40` | S | T10 |
| C-98 | `next_filename` never checks the proposed path, nor the `-vN` suffix against frontmatter | S1 | linters | silent | `scripts/resolve_brief_version.py:60-65` | S | T10 |
| A-01 | Script unreachable at `assembly`/`repurpose` while both templates assert it is present | S1 | pipeline | silent | `pipeline.yaml:40` | S | T1 |
| A-04 | `grounding_pointer` is supplied to `assembly`/`repurpose` but neither template uses it | S1 | pipeline | silent | `pipeline-app/pipeline_app/turn_service.py:151` | S | T1 |
| A-05 | Re-run never re-renders kickoff, yet records provenance on the new upstream | S1 | pipeline | silent | `pipeline-app/pipeline_app/turn_service.py:145` | M | T1 |
| F-10 | All 32 S0/S1 defects were within reach of a test; none was written | S1 | tests | coverage-gap | `docs/audit/appendix-F-tests.md:22-24` | L | T14 |
| F-11 | A test asserts a security control that does not exist, and its name is the evidence | S1 | tests | silent | `pipeline-app/tests/test_cli_runner.py:458-467` | M | T14 |
| F-12 | A test codifies the "empty ≠ failed" violation the codebase's own docstring forbids | S1 | tests | silent | `pipeline-app/tests/test_discovery_bluesky.py:56-60` | M | T14 |
| F-13 | Three Gate-C tests assert evadable checks are correct behavior | S1 | tests | silent | `tests/test_lint_prompt_sheet.py:554-557` | S | T14 |
| F-14 | The Gate-C suite bypasses the parser, making the largest hole structurally unreachable | S1 | tests | coverage-gap | `tests/test_lint_prompt_sheet.py:133-144` | M | T14 |
| F-15 | `test_turn_service.py`'s CLI double discards the prompt, so the handoff engine's output is never asserted | S1 | tests | coverage-gap | `pipeline-app/tests/test_turn_service.py:30-37` | S | T14 |
| F-16 | No test asserts a nonzero exit or a surfaced error on any unattended path | S1 | tests | silent | `pipeline-app/tests/test_run_discovery_cron.py:24,33,42,59,74,88,101,112,124,139,151,167` | M | T14 |
| F-17 | No test exercises `visual/edit` or `styleboard/edit` — the only edit paths whose gate reads an upstream | S1 | tests | coverage-gap | `pipeline-app/tests/test_routes_approve_edit.py:104,143,182,215,289,309` | M | T14 |
| F-18 | No test asserts artifact writes are atomic, exclusive, or non-destructive | S1 | tests | coverage-gap | `pipeline-app/tests/test_artifacts.py` | M | T14 |
| F-19 | No test asserts the CLI and app Gate C implementations agree | S1 | tests | coverage-gap | `pipeline-app/tests/test_gates.py:129-137` | M | T14 |
| F-20 | No adapter-contract test: the discovery invariants are asserted per-adapter and inconsistently | S1 | tests | coverage-gap | `pipeline-app/tests/test_discovery_bluesky.py:56-60` | M | T14 |
| F-61 | Bare `pytest` at repo root: 201 passed, exit 0, 833 app tests silently omitted | S1 | tests | silent | `pytest.ini:9` | S | T15 |
| F-68 | The suite can spawn a real, billed Bright Data run; the only guard is nine hand-written stubs | S1 | tests | latent | `pipeline_app/routes/discovery.py:19-22` | S | T15 |
| A-61 | Backfilled styleboard artifacts record `depends_on: []` and are approved, exempting the stage from staleness | S2 | artifacts | silent | `pipeline-app/pipeline_app/migrations.py:63-82` | S | T3 |
| A-64 | `raw_output.md` is written non-atomically before the artifact, and the crash window loses the edit entirely | S2 | artifacts | silent | `pipeline-app/pipeline_app/routes/stages.py:263-266` | M | T3 |
| A-68 | `parse_frontmatter` returns `({}, text)` for an unterminated block, masking a truncated artifact as an unversioned one | S2 | artifacts | silent | `pipeline-app/pipeline_app/artifacts.py:13-23` | S | T3 |
| A-69 | `parse_frontmatter` neither validates that the YAML is a mapping nor contains `YAMLError` | S2 | artifacts | loud | `pipeline-app/pipeline_app/artifacts.py:21` | S | T3 |
| A-70 | One shared autocommit connection: no transaction boundary around any multi-row invariant | S2 | artifacts | silent | `pipeline-app/pipeline_app/db.py:15-20` | M | T3 |
| A-71 | `turns` has no partial unique index on `status='running'`, though `discovery_runs` does | S2 | artifacts | silent | `pipeline-app/pipeline_app/schema.sql:58-59` | S | T3 |
| A-72 | No migration versioning: `CREATE TABLE IF NOT EXISTS` on every boot means a later column change silently never lands | S2 | artifacts | latent | `pipeline-app/pipeline_app/schema.sql:1` | M | T3 |
| A-74 | Backfill failure is stderr-only; the project loses `styleboard` and the UI blames the wrong thing | S2 | artifacts | silent | `pipeline-app/pipeline_app/migrations.py:196-205` | S | T3 |
| A-77 | Orphan recovery is invisible to the operator and leaves the dead turn's `raw_output.md` in place | S2 | artifacts | silent | `pipeline-app/pipeline_app/preflight.py:38-40` | S | T3 |
| A-78 | `create_project` commits the project row before its stage rows and directories, with no repair path | S2 | artifacts | silent | `pipeline-app/pipeline_app/project_service.py:42-49` | M | T3 |
| A-81 | `identify_new_brief` returns `None` on 0 or ≥2 changed briefs, recording a successful turn as `no_artifact` | S2 | artifacts | silent | `pipeline-app/pipeline_app/grounding_service.py:17-21` | S | T3 |
| B-90 | Spotlight excerpt ships the complete post body for any post under 400 chars | S2 | digest | docs-drift | `pipeline-app/pipeline_app/email_render.py:68-74` | S | T7 |
| B-91 | Derived "title" is the post's first 90 characters, so every inventory row can carry the whole post | S2 | digest | docs-drift | `pipeline-app/pipeline_app/discovery_digest.py:70-87` | S | T7 |
| B-93 | Every diagnostic in the email path writes to a stderr the Scheduled Task discards | S2 | digest | silent | `pipeline-app/pipeline_app/discovery_notify.py:62` | M | T7 |
| B-94 | A failed send is a silent no-op — the bool is discarded and no email is the same as no run | S2 | digest | silent | `pipeline-app/pipeline_app/discovery_notify.py:55-78` | M | T7 |
| B-95 | The email carries no denominator, so an empty roster reads as a quiet day | S2 | digest | silent | `pipeline-app/pipeline_app/discovery_notify.py:119-125` | M | T7 |
| B-99 | Per-item parse failures are dropped with no log, no counter, and no file identity | S2 | digest | silent | `pipeline-app/pipeline_app/discovery_digest.py:221-240` | M | T7 |
| B-01 | Adapter failure diagnostics are stderr-only and reach no durable surface | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_facebook.py:236` | M | T4 |
| B-05 | Bluesky enumerate reports every fetch error as an empty feed | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_bluesky.py:40` | S | T4 |
| B-07 | Bluesky download_item re-walks the entire paginated feed once per item | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_bluesky.py:83` | S | T4 |
| B-08 | Bluesky keyword_filter matches only the first 60 characters of a post | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_bluesky.py:59` | S | T4 |
| B-11 | A failed YouTube /videos enumeration is reported as a quiet day | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_youtube.py:62` | M | T4 |
| B-13 | The transcript fallback's bare except hides rate-limiting and IP blocks | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_youtube.py:197` | S | T4 |
| B-14 | A new YouTube handle with no API key and an active bot-block captures nothing, silently | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_youtube_api.py:191` | S | T4 |
| B-18 | Bright Data poll loop has no HTTP retry, so a transient 429/503 fails a billed handle | S2 | discovery | loud | `pipeline-app/pipeline_app/brightdata_job.py:81` | S | T4 |
| B-19 | A timed-out Bright Data snapshot loses its paid data and is never cleaned up | S2 | discovery | loud | `pipeline-app/pipeline_app/brightdata_job.py:113` | M | T4 |
| B-22 | Instagram alone lacks the billed-and-captured-nothing escalation | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_instagram.py:222` | S | T4 |
| B-40 | Scheduled run's exit code is a constant; every failure reads as success | S2 | discovery | silent | `pipeline-app/run_discovery_cron.py:110` | S | T5 |
| B-41 | `notify()`'s success boolean is discarded — an unsent email exits 0 | S2 | discovery | silent | `pipeline-app/run_discovery_cron.py:103-107` | S | T5 |
| B-42 | No log file exists for scheduled runs; every stderr diagnostic is destroyed | S2 | discovery | silent | `pipeline-app/scripts/setup_discovery_task.py:22-27` | S | T5 |
| B-43 | `completed_with_errors` is visually identical to `completed` in the run history | S2 | discovery | silent | `pipeline-app/pipeline_app/routes/discovery.py:112-126` | S | T5 |
| B-44 | schtasks registration sets no run-level, logon type, working dir, or power policy | S2 | discovery | silent | `pipeline-app/scripts/setup_discovery_task.py:22-27` | M | T5 |
| B-53 | No wall-clock cap on a run; a hung adapter wedges discovery indefinitely | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_engine.py:339-380` | M | T5 |
| B-54 | A handle that raises after partial downloads is recorded as 0 items, forever | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_engine.py:373-380` | M | T5 |
| B-57 | A transient error during validation permanently marks a handle invalid and excluded | S2 | discovery | silent | `pipeline-app/pipeline_app/discovery_engine.py:272-281` | M | T5 |
| B-58 | Unvalidated `platform` form field kills the validate subprocess and strands the handle | S2 | discovery | silent | `pipeline-app/pipeline_app/routes/discovery.py:39-70` | S | T5 |
| B-60 | Backfill date inputs are unvalidated: inverted ranges bill for guaranteed-zero results | S2 | discovery | silent | `pipeline-app/pipeline_app/routes/discovery.py:97-102` | S | T5 |
| B-61 | A spawned subprocess that dies is completely invisible to the user who triggered it | S2 | discovery | silent | `pipeline-app/pipeline_app/routes/discovery.py:17-22` | M | T5 |
| B-70 | Four of six discovery platforms have no declarative roster source | S2 | discovery | coverage-gap | `manifests/brand_sources.json:3` | M | T6 |
| B-71 | A new platform key in brand_sources.json is silently ignored by both consumers | S2 | discovery | silent | `pipeline-app/scripts/migrate_handles_from_manifest.py:68` | S | T6 |
| B-72 | No cross-platform creator identity — handles are keyed only by (platform, handle) | S2 | discovery | coverage-gap | `pipeline-app/pipeline_app/schema.sql:29-42` | M | T6 |
| B-73 | handles.platform is unconstrained free text; a typo strands the row at 'pending' | S2 | discovery | silent | `pipeline-app/pipeline_app/schema.sql:31` | S | T6 |
| B-76 | Re-running the migration never applies manifest edits or removals | S2 | discovery | silent | `pipeline-app/scripts/migrate_handles_from_manifest.py:1-8` | M | T6 |
| B-79 | The manifest's rss key is advertised as live but the discovery path drops it | S2 | discovery | silent | `manifests/brand_sources.json:23-25` | S | T6 |
| B-80 | The roster seeding script is undocumented outside a historical plan doc | S2 | discovery | docs-drift | `pipeline-app/README.md:6-19` | S | T6 |
| B-82 | handles.status is never downgraded after registration — a dead handle looks healthy | S2 | discovery | silent | `pipeline-app/pipeline_app/schema.sql:36-37` | M | T6 |
| B-83 | run_all.sh aborts at the youth-sports step and never reaches the brand-intel download | S2 | discovery | loud | `copy_youthsports.sh:11` | S | T6 |
| B-84 | output/raisinggoodsports-brand-definition.md is cited by both RGS skills but produced by nothing | S2 | discovery | coverage-gap | `.claude/skills/rgs-grounding/references/brand-voice-and-tone.md:3` | S | T6 |
| A-32 | Gates lint against the latest upstream artifact, which may be an unapproved draft | S2 | gates | silent | `pipeline-app/pipeline_app/turn_service.py:138-143` | M | T2 |
| A-33 | Seven of nine stages are ungated; `styleboard` is the load-bearing omission | S2 | gates | coverage-gap | `pipeline-app/pipeline_app/gates.py:128-131` | M | T2 |
| A-34 | C20 blames the sheet for a label the styleboard chose | S2 | gates | latent | `scripts/lint_prompt_sheet.py:911` | S | T2 |
| A-35 | A gate result with an unrecognized `status` approves as if it passed | S2 | gates | silent | `pipeline-app/pipeline_app/approval_service.py:53` | S | T2 |
| A-37 | `gate_override_reason` is write-only — never rendered back to the operator | S2 | gates | silent | `pipeline-app/pipeline_app/artifacts.py:87` | S | T2 |
| A-38 | Overrides are last-write-wins with no actor and, on one path, no timestamp | S2 | gates | silent | `pipeline-app/pipeline_app/artifacts.py:103-105` | M | T2 |
| A-40 | A `BaseException` from a gate escapes fail-closed and wedges the stage at `running` | S2 | gates | latent | `pipeline-app/pipeline_app/gates.py:160` | S | T2 |
| A-45 | Nothing ever re-locks a stage whose dependency has left `approved` | S2 | gates | silent | `pipeline-app/pipeline_app/state_machine.py:24-31` | M | T2 |
| A-46 | An aborted turn launders `stale` into `awaiting_review`, erasing the only staleness cue | S2 | gates | silent | `pipeline-app/pipeline_app/turn_service.py:200-204` | M | T2 |
| A-48 | `STAGE_ID_BY_SKILL` duplicates `pipeline.yaml` and has already drifted from it | S2 | gates | silent | `pipeline-app/pipeline_app/routes/skills.py:8-18` | S | T2 |
| A-49 | An unknown `target` value redirects with a 303 as though the save succeeded | S2 | gates | silent | `pipeline-app/pipeline_app/routes/skills.py:87-95` | S | T2 |
| A-50 | Saving a kickoff template for an unmapped skill writes `stage_templates/None.md` | S2 | gates | silent | `pipeline-app/pipeline_app/routes/skills.py:91-94` | S | T2 |
| A-53 | `commit_skill_edit` commits the entire index, not just the skill file | S2 | gates | silent | `pipeline-app/pipeline_app/git_helper.py:10-20` | S | T2 |
| D-01 | Notification failure is unobservable: `notify()`'s bool return is discarded | S2 | infra | silent | `pipeline-app/run_discovery_cron.py:105` | S | T11 |
| D-02 | No centralized error surface exists; 35 stderr signals are discarded by Task Scheduler | S2 | infra | silent | `pipeline-app/scripts/setup_discovery_task.py:22` | M | T11 |
| D-06 | A run that dies before its first DB write leaves no trace that it was ever attempted | S2 | infra | silent | `pipeline-app/run_discovery_cron.py:82` | M | T11 |
| D-40 | Repo makes 14 outbound calls; CLAUDE.md documents two | S2 | infra | docs-drift | `CLAUDE.md:193-194` | S | T12 |
| D-41 | htmx loaded from unpkg with no SRI and no local fallback | S2 | infra | latent | `pipeline-app/pipeline_app/templates/base.html:7` | S | T12 |
| D-42 | Offline, the Browse tree and document viewer die with zero UI signal | S2 | infra | silent | `pipeline-app/pipeline_app/templates/base.html:7` | S | T12 |
| D-43 | `scoped_permissions_settings()` restricts nothing; its name, docstring and test all claim it does | S2 | infra | silent | `pipeline-app/pipeline_app/cli_runner.py:122-139` | M | T12 |
| D-44 | Stage-turn write denial covers three subtrees; everything else on disk is writable | S2 | infra | latent | `pipeline-app/pipeline_app/cli_runner.py:39-45` | M | T12 |
| D-47 | Scraped third-party post text renders unsanitized into the operator's browser | S2 | infra | latent | `pipeline-app/pipeline_app/templates/partials/browse_file.html:18` | M | T12 |
| D-49 | `commit_skill_edit` commits the entire git index, not the file it staged | S2 | infra | silent | `pipeline-app/pipeline_app/git_helper.py:10` | S | T12 |
| D-54 | Pipeline turns read untrusted corpus text with none of `comment_draft`'s injection containment | S2 | infra | latent | `pipeline-app/pipeline_app/comment_draft.py:94-111` | M | T12 |
| F-62 | CLAUDE.md's "bare `pytest` does the right thing in both places" is false for the app suite | S2 | infra | docs-drift | `CLAUDE.md` | S | T15 |
| F-64 | The two-rootdir split is a workaround for a `scripts` package-name collision | S2 | infra | latent | `scripts/__init__.py` | M | T15 |
| F-76 | `yt-dlp` floats in both manifests while tests pin its exact JSON schema | S2 | infra | silent | `requirements.txt` | S | T15 |
| F-77 | `run_all.sh` — the README's documented entry point — cannot complete in this repo | S2 | infra | loud | `run_all.sh:11` | S | T15 |
| C-71 | No reconciliation of parsed shot count or index contiguity | S2 | linters | silent | `scripts/lint_prompt_sheet.py:69-80` | S | T10 |
| C-74 | CLI lacks the empty-world fail-closed guard the app path has | S2 | linters | loud | `scripts/lint_prompt_sheet.py:989-992` | S | T10 |
| C-76 | `parse_style_library` drops individual entries silently on benign reformatting | S2 | linters | silent | `scripts/lint_prompt_sheet.py:838` | S | T10 |
| C-78 | A cover block with a mistyped or empty fence is silently unlinted | S2 | linters | silent | `scripts/lint_prompt_sheet.py:111-140` | S | T10 |
| C-82 | C11's anti-clone check is defeated by one word per clause | S2 | linters | silent | `scripts/lint_prompt_sheet.py:267-269` | M | T10 |
| C-83 | C12's density check is a token count, satisfied by filler | S2 | linters | silent | `scripts/lint_prompt_sheet.py:503-506` | M | T10 |
| C-84 | C9 and C10 are literal-string no-lists of two and three entries | S2 | linters | coverage-gap | `scripts/lint_prompt_sheet.py:431-436` | M | T10 |
| C-85 | `Register PLATE` is an unaudited exemption from C8, C9, C10, C14 and C17 | S2 | linters | silent | `scripts/lint_prompt_sheet.py:303` | M | T10 |
| C-90 | D5's `skipped` branch lets one ratable line disable the wpm ceiling | S2 | linters | silent | `scripts/lint_script_language.py:397-420` | S | T10 |
| C-94 | A missing input file exits 1, indistinguishable from a failing gate | S2 | linters | silent | `scripts/lint_prompt_sheet.py:987` | S | T10 |
| C-97 | Version ties resolve silently to whichever filename sorts first | S2 | linters | silent | `scripts/resolve_brief_version.py:44-57` | S | T10 |
| C-100 | Exit 1 means both "no prior version" and "a brief is malformed" | S2 | linters | silent | `scripts/resolve_brief_version.py:86-91` | S | T10 |
| C-101 | The plugin ships 11 skills while calling itself "Seven" in three places | S2 | linters | docs-drift | `scripts/build-cowork-plugin.sh:2` | S | T10 |
| C-102 | plugin.json version is hard-pinned and the build is never verified | S2 | linters | silent | `scripts/build-cowork-plugin.sh:30-37` | S | T10 |
| C-103 | Nothing runs the build; a stale `.plugin` is undetectable | S2 | linters | silent | `scripts/build-cowork-plugin.sh:57-71` | S | T10 |
| A-02 | `music` is a graph leaf — its bed arc can never reach `assembly` | S2 | pipeline | silent | `pipeline.yaml:31-36` | M | T1 |
| A-03 | Styleboard `BINDINGS` unreachable at `assembly`, whose SKILL.md requires them | S2 | pipeline | silent | `pipeline.yaml:30` | S | T1 |
| A-06 | An unresumable `claude_session_id` permanently wedges a stage | S2 | pipeline | loud | `pipeline-app/pipeline_app/turn_service.py:145` | M | T1 |
| A-08 | Jinja default `Undefined` makes a typo in an operator-edited template render empty | S2 | pipeline | silent | `pipeline-app/pipeline_app/prompt_builder.py:7-11` | S | T1 |
| A-10 | Topology validation never checks a kickoff template exists for each stage | S2 | pipeline | loud | `pipeline-app/pipeline_app/pipeline_config.py:36-66` | S | T1 |
| A-11 | `specialist` is validated against `.claude/skills/`, `skill` is not | S2 | pipeline | silent | `pipeline-app/pipeline_app/pipeline_config.py:49-56` | S | T1 |
| A-13 | `finalize_artifact=False` skips staleness propagation, and `grounding` has no dependents anyway | S2 | pipeline | silent | `pipeline-app/pipeline_app/turn_service.py:222-223` | M | T1 |
| C-01 | voiceover-brief's output contract has no tone-per-beat section, yet three skills consume it | S2 | skills | silent | `.claude/skills/voiceover-brief/SKILL.md:16` | S | T8 |
| C-02 | rgs-grounding's downstream list omits shorts-styleboard, the skill that consumes its motif | S2 | skills | docs-drift | `.claude/skills/rgs-grounding/SKILL.md:20` | S | T8 |
| C-03 | shorts-assembly declares the script REQUIRED but the assembly stage has no scripting dependency | S2 | skills | loud | `.claude/skills/shorts-assembly/SKILL.md:17` | S | T8 |
| C-04 | social-repurpose states three different input lists in one file | S2 | skills | silent | `.claude/skills/social-repurpose/SKILL.md:3` | S | T8 |
| C-07 | The WORLD LOCK key count is wrong in both skills that state it (11/12 claimed, 13 actual) | S2 | skills | silent | `.claude/skills/shorts-styleboard/SKILL.md:31` | S | T8 |
| C-13 | voiceover-brief writes into three of the four rows elevenlabs-audio's boundary table assigns to the specialist | S2 | skills | silent | `.claude/skills/elevenlabs-audio/SKILL.md:25-30` | M | T8 |
| C-17 | midjourney-prompting's deterministic mapping emits a literal `--sref <code>` that Gate C rejects in pipeline mode | S2 | skills | loud | `.claude/skills/midjourney-prompting/SKILL.md:94` | S | T8 |
| C-20 | The three specialists emit no file artifact and carry no File I/O contract | S2 | skills | latent | `.claude/skills/elevenlabs-audio/SKILL.md:187-226` | M | T8 |
| C-21 | shorts-assembly's output has no stated structure — only "the same way references/worked-example.md is" | S2 | skills | silent | `.claude/skills/shorts-assembly/SKILL.md:49-55` | M | T8 |
| C-42 | Half of all normative bullets in the skill set carry no provenance marker | S2 | skills | silent | `.claude/skills/visual-prompts/SKILL.md:1-400` | L | T9 |
| C-46 | `elevenlabs-audio` carries 187 `[T]` lines and a verification date in only 2 of 11 files | S2 | skills | silent | `.claude/skills/elevenlabs-audio/references/voice-settings.md` | S | T9 |
| C-48 | `test_skill_provenance.py` guards 13 bullets in 1 of 64 reference files, under a name that implies coverage | S2 | skills | coverage-gap | `tests/test_skill_provenance.py:15` | M | T9 |
| C-53 | Ten stage artifacts carry no `kind:` field, so `kind:`-skipping consumers read them as grounding briefs | S2 | skills | silent | `rgs-briefs/2026-07-25-let-kids-play-act-script.md:1-3` | M | T9 |
| E-01 | A finished turn leaves Output and Gates showing the previous state | S2 | templates | silent | `pipeline-app/pipeline_app/templates/base.html:76-83` | S | T13 |
| E-02 | Gate verdicts render below the whole artifact, and vanish entirely when no gate ran | S2 | templates | silent | `pipeline-app/pipeline_app/templates/stage.html:34-55` | M | T13 |
| E-03 | Never-ran gate creates an unescapable approve loop: no override field, plain-text 409 | S2 | templates | loud | `pipeline-app/pipeline_app/templates/stage.html:59-65` | S | T13 |
| E-04 | Every expected failure returns bare `PlainTextResponse`, destroying the page | S2 | templates | loud | `pipeline-app/pipeline_app/routes/stages.py:138-141,155,225,233-236,238-241` | M | T13 |
| E-05 | A missing upstream artifact is silently dropped from the Input panel | S2 | templates | silent | `pipeline-app/pipeline_app/routes/stages.py:69-78` | S | T13 |
| E-09 | `completed` and `completed_with_errors` are visually identical on the runs page | S2 | templates | silent | `pipeline-app/pipeline_app/templates/discovery_runs.html:9` | S | T13 |
| E-10 | A failed handle is identified only by a numeric database id | S2 | templates | silent | `pipeline-app/pipeline_app/templates/discovery_runs.html:13-15` | S | T13 |
| E-13 | No htmx request in the app has an error path — a 500 or a dead server renders nothing | S2 | templates | silent | `pipeline-app/pipeline_app/templates/partials/browse_tree_items.html:16-29` | S | T13 |
| E-14 | Browse cannot distinguish empty from broken, in three different ways | S2 | templates | silent | `pipeline-app/pipeline_app/browse_service.py:171-195,111-132,219,229-236` | M | T13 |
| F-02 | 95% line coverage coexists with 18 confirmed defects — coverage is misleading here | S2 | tests | silent | coverage totals above (690/36 and 2890/147) | S | T0 |
| F-03 | The only end-to-end test is opt-in, off by default, and never run | S2 | tests | coverage-gap | `pipeline-app/tests/integration/test_real_cli_e2e.py:21` | M | T0 |
| F-21 | `test_save_kickoff_template_does_not_commit` pins a missing recovery path | S2 | tests | silent | `pipeline-app/tests/test_routes_skills.py:54-68` | S | T14 |
| F-22 | `test_skill_provenance.py` guards one of 64 reference files under a name implying whole-set coverage | S2 | tests | docs-drift | `tests/test_skill_provenance.py:15` | M | T14 |
| F-23 | `resolve_brief_version.main()` — the entry point ten skills invoke — is 23 uncovered statements | S2 | tests | coverage-gap | `scripts/resolve_brief_version.py:68-91` | S | T14 |
| F-24 | `fetch_upload_dates` has no test at all — the function whose empty return drops every Short | S2 | tests | coverage-gap | `pipeline-app/pipeline_app/discovery_youtube_api.py:182-214` | S | T14 |
| F-25 | No property-based, mutation, or adversarial-input testing anywhere in either suite | S2 | tests | coverage-gap | `requirements.txt` | L | T14 |
| F-26 | Two suites assert on the value they injected into a mock | S2 | tests | silent | `pipeline-app/tests/test_main.py:15-30` | S | T14 |
| F-27 | Test volume is inverted against consequence across the five thinnest suites | S2 | tests | coverage-gap | `pipeline-app/tests/test_routes_doctor.py` | S | T14 |
| F-30 | Nothing runs the app suite by default, so a bare `pytest` hides 80% of the tests | S2 | tests | silent | `docs/audit/appendix-F-tests.md:103` | S | T14 |
| F-65 | No `conftest.py` anywhere: the DB fixture is duplicated 11 times, the FastAPI client 9 times | S2 | tests | coverage-gap | no `conftest.py` in the repo | M | T15 |
| F-67 | Module-global adapter caches and a once-only warn flag are never reset between tests | S2 | tests | latent | `pipeline_app/discovery_instagram.py:215` | S | T15 |
| F-69 | Vendor `KEY_FILE` constants are anchored to the real repo, so `tmp_path` does not isolate credentials | S2 | tests | latent | `pipeline_app/discovery_instagram.py:38` | M | T15 |
| F-72 | The "e2e" test covers 1 of 9 stages, asserts only that a file exists, and writes into the real repo | S2 | tests | coverage-gap | `pipeline-app/tests/integration/test_real_cli_e2e.py:18` | M | T15 |
| A-66 | Version numbers derive from the filesystem alone; deleting the newest artifact silently reuses its number | S3 | artifacts | latent | `pipeline-app/pipeline_app/artifacts.py:35-46` | M | T3 |
| A-67 | Non-numeric `artifact.v*.md` siblings are silently ignored; zero-padded duplicates make `latest_artifact_path` nondeterministic | S3 | artifacts | silent | `pipeline-app/pipeline_app/artifacts.py:10` | S | T3 |
| A-76 | The startup orphan sweep runs per-process, so a second uvicorn worker orphans a live turn | S3 | artifacts | silent | `pipeline-app/pipeline_app/main.py:28-30` | M | T3 |
| A-79 | Distinct project names collapse to one slug; `run_id` uniqueness rests on second resolution and collides as a 500 | S3 | artifacts | loud | `pipeline-app/pipeline_app/project_service.py:13-20` | S | T3 |
| A-84 | The entire `/edit` artifact-write path has no UI entry point | S3 | artifacts | coverage-gap | `pipeline-app/pipeline_app/routes/stages.py:229-290` | S | T3 |
| B-92 | facebook and x are unranked and unlabelled, sorting the two paid sources below free Bluesky | S3 | digest | silent | `pipeline-app/pipeline_app/email_render.py:21-30` | S | T7 |
| B-96 | The LinkedIn absolute-priority gate is invisible to the recipient | S3 | digest | docs-drift | `pipeline-app/pipeline_app/discovery_digest.py:250-253` | S | T7 |
| B-98 | The `upload_date` alias is absent from the stated contract; a third field name drops the date silently | S3 | digest | coverage-gap | `pipeline-app/pipeline_app/discovery_digest.py:191` | S | T7 |
| B-100 | The item-count mismatch warning conflates one expected condition with three real defects | S3 | digest | silent | `pipeline-app/pipeline_app/discovery_notify.py:112-117` | S | T7 |
| B-101 | Slug-colliding handles produce duplicate inventory entries and an inflated subject count | S3 | digest | silent | `pipeline-app/pipeline_app/discovery_digest.py:209` | M | T7 |
| B-102 | The drafting turn's `--disallowedTools` list is not exhaustive, so "every tool denied" overstates the guarantee | S3 | digest | latent | `pipeline-app/pipeline_app/comment_draft.py:113-122` | S | T7 |
| B-104 | The drafting child's stderr is DEVNULL'd, so a persistently draft-less email cannot be diagnosed | S3 | digest | silent | `pipeline-app/pipeline_app/comment_draft.py:258` | S | T7 |
| B-105 | The kill-tree result is discarded and a surviving grandchild silently leaks the scratch directory | S3 | digest | silent | `pipeline-app/pipeline_app/comment_draft.py:245` | S | T7 |
| B-107 | Production sends default to Resend's shared sandbox sender | S3 | digest | latent | `pipeline-app/pipeline_app/discovery_notify.py:34-37` | M | T7 |
| B-112 | The Errors section names handles but never says why any of them failed | S3 | digest | silent | `pipeline-app/pipeline_app/discovery_notify.py:107-110` | S | T7 |
| B-16 | YouTube subprocess return codes ignored and peek's JSON parse unguarded | S3 | discovery | latent | `pipeline-app/pipeline_app/discovery_youtube.py:139` | S | T4 |
| B-20 | Bright Data response shapes are indexed without validation | S3 | discovery | loud | `pipeline-app/pipeline_app/brightdata_job.py:72` | S | T4 |
| B-21 | A missing Bright Data token is discovered per handle at job time, not at preflight | S3 | discovery | loud | `pipeline-app/pipeline_app/discovery_instagram.py:104` | S | T4 |
| B-23 | Instagram records no author, so a foreign-account regression is undetectable | S3 | discovery | latent | `pipeline-app/pipeline_app/discovery_instagram.py:198` | S | T4 |
| B-45 | Dry-run prints a command string that is not runnable as printed | S3 | discovery | loud | `pipeline-app/scripts/setup_discovery_task.py:41-44` | S | T5 |
| B-48 | Changing the timezone setting can fire a second run the same day | S3 | discovery | silent | `pipeline-app/pipeline_app/discovery_scheduling.py:12-17` | M | T5 |
| B-49 | Any run longer than 15 minutes manufactures a `locked` row and md file per wake | S3 | discovery | latent | `pipeline-app/pipeline_app/discovery_engine.py:408-417` | S | T5 |
| B-51 | `abandoned` run records report zero work, contradicting their own DB rows | S3 | discovery | silent | `pipeline-app/pipeline_app/discovery_engine.py:140-149` | S | T5 |
| B-52 | A stale `running` row is not reclaimed by the scheduled path once the day's run succeeded | S3 | discovery | latent | `pipeline-app/run_discovery_cron.py:85-87` | S | T5 |
| B-55 | Per-handle `error_message` is a bare `str(exc)` — no type, no traceback | S3 | discovery | silent | `pipeline-app/pipeline_app/discovery_engine.py:375` | S | T5 |
| B-56 | `skipped` handles are counted but never surfaced; frontmatter totals do not add up | S3 | discovery | silent | `pipeline-app/pipeline_app/discovery_records.py:14` | S | T5 |
| B-59 | Run Now has no concurrency guard, and losing the lock race can crash instead | S3 | discovery | latent | `pipeline-app/pipeline_app/routes/discovery.py:91-102` | M | T5 |
| B-63 | The directory-collision guard lives only in the add-handle route; migration bypasses it | S3 | discovery | silent | `pipeline-app/pipeline_app/routes/discovery.py:51-64` | S | T5 |
| B-74 | The platform picker is a hardcoded list decoupled from the adapter registry | S3 | discovery | latent | `pipeline-app/pipeline_app/templates/discovery_handles.html:33-41` | S | T6 |
| B-75 | The migration marks every seeded handle 'validated' without ever validating it | S3 | discovery | silent | `pipeline-app/scripts/migrate_handles_from_manifest.py:58-61` | S | T6 |
| B-78 | The declared out-of-scope roster entry is seeded as an included daily source | S3 | discovery | coverage-gap | `manifests/brand_sources.json:2` | S | T6 |
| B-81 | No test exercises the real manifests/brand_sources.json | S3 | discovery | latent | `pipeline-app/tests/test_migrate_handles.py:34-55` | S | T6 |
| A-31 | CLI and app Gate C disagree on an empty world lock — same name, different diagnosis | S3 | gates | loud | `pipeline-app/pipeline_app/gates.py:87-96` | S | T2 |
| A-36 | A malformed `gates` frontmatter value 500s the approve route instead of 409-ing | S3 | gates | loud | `pipeline-app/pipeline_app/approval_service.py:52-54` | S | T2 |
| A-39 | A whitespace-only override reason bypasses the gate block at the service layer | S3 | gates | silent | `pipeline-app/pipeline_app/approval_service.py:59` | S | T2 |
| A-41 | The hand-edit gate call is untried; an escape 500s after `raw_output.md` is clobbered | S3 | gates | loud | `pipeline-app/pipeline_app/routes/stages.py:263-266` | S | T2 |
| A-43 | Gate C findings render without a shot number — the template reads a field they lack | S3 | gates | silent | `scripts/lint_prompt_sheet.py:40-44` | S | T2 |
| A-54 | A git failure 500s the save route after the file is already written | S3 | gates | loud | `pipeline-app/pipeline_app/routes/skills.py:89-90` | S | T2 |
| A-55 | Every browser save doubles carriage returns on Windows | S3 | gates | silent | `pipeline-app/pipeline_app/routes/skills.py:89` | S | T2 |
| D-05 | Backfill reconstructs missing metadata from filenames instead of reporting a parse failure | S3 | infra | silent | `pipeline-app/scripts/backfill_youtube_frontmatter.py:63` | S | T11 |
| D-48 | No CSRF protection on any state-changing POST route | S3 | infra | latent | `pipeline-app/pipeline_app/main.py:16-43` | S | T12 |
| D-50 | `git_helper` subprocesses have no timeout; a prompting git wedges the request | S3 | infra | silent | `pipeline-app/pipeline_app/git_helper.py:10` | S | T12 |
| F-71 | `pytest-asyncio` pinned to 0.24 against Python 3.14, with no `asyncio_mode` or loop-scope set | S3 | infra | latent | `pipeline-app/requirements.txt:8` | S | T15 |
| F-74 | Root `requirements.txt` omits `pytest`; neither manifest lists coverage tooling | S3 | infra | coverage-gap | `requirements.txt` | S | T15 |
| F-75 | `setup.py` has no `install_requires` and excludes two things the tests import | S3 | infra | latent | `pipeline-app/setup.py:3-8` | M | T15 |
| F-78 | `start_pipeline.bat` checks no exit code: a missing venv, a bound port, or a crash all still open the browser | S3 | infra | silent | `pipeline-app/start_pipeline.bat:3` | S | T15 |
| F-80 | The PR template asks a human to hand-transcribe verification a machine should produce | S3 | infra | docs-drift | `.github/PULL_REQUEST_TEMPLATE.md:13-17` | S | T15 |
| C-72 | `parse_sheet` is not fence-aware; a documented example becomes a real shot | S3 | linters | silent | `scripts/lint_prompt_sheet.py:55-84` | S | T10 |
| C-73 | World-lock walk truncates at the first non-matching line; duplicates last-win | S3 | linters | silent | `scripts/lint_prompt_sheet.py:24` | S | T10 |
| C-77 | The Style Library does not warn that its headings are load-bearing on Gate C | S3 | linters | docs-drift | `docs/style-library.md:83` | S | T10 |
| C-86 | C19 accepts a bare `Cover = Hook` line with no hook shot verification | S3 | linters | coverage-gap | `scripts/lint_prompt_sheet.py:108` | S | T10 |
| C-87 | C8's world-lock test is a lowercase substring plus one signature object | S3 | linters | coverage-gap | `scripts/lint_prompt_sheet.py:441-465` | S | T10 |
| C-91 | D6's pipe heuristic false-fails a legitimate result, and D6 is unscoped | S3 | linters | loud | `scripts/lint_script_language.py:445-454` | S | T10 |
| C-92 | D3 and D4 no-lists are closed and small; the coverage limit is undocumented | S3 | linters | coverage-gap | `scripts/lint_script_language.py:304-337` | S | T10 |
| C-93 | Gate C findings carry no `kind`; the two linters' finding records diverge | S3 | linters | latent | `scripts/lint_prompt_sheet.py:41-45` | M | T10 |
| C-95 | Exit code 2 is overloaded across usage error and unparseable input | S3 | linters | latent | `scripts/lint_prompt_sheet.py:994-996` | S | T10 |
| C-99 | `--date` is interpolated into the filename without validation | S3 | linters | silent | `scripts/resolve_brief_version.py:74` | S | T10 |
| A-07 | Missing upstream artifact renders the literal string `None` into the prompt | S3 | pipeline | silent | `pipeline-app/pipeline_app/turn_service.py:139-143` | S | T1 |
| A-09 | `input_files[0]` ordering is unguarded against a stage gaining a second dependency | S3 | pipeline | latent | `pipeline-app/pipeline_app/turn_service.py:133` | M | T1 |
| A-12 | `brand_scope` is unvalidated free text and invisible to graph validation | S3 | pipeline | latent | `pipeline-app/pipeline_app/pipeline_config.py:13` | M | T1 |
| A-14 | Upstream resolution uses `latest_artifact_path`, bypassing pointer indirection | S3 | pipeline | latent | `pipeline-app/pipeline_app/turn_service.py:140` | S | T1 |
| C-05 | shorts-scripting declares two downstream consumers; four skills claim it upstream | S3 | skills | docs-drift | `.claude/skills/shorts-scripting/SKILL.md:23-28` | S | T8 |
| C-06 | shorts-styleboard cites an "Optional input" section it does not contain | S3 | skills | docs-drift | `.claude/skills/shorts-styleboard/SKILL.md:56` | S | T8 |
| C-12 | Three skills cite `references/production-and-loudness.md` relative to their own directory, where it does not exist | S3 | skills | loud | `.claude/skills/elevenlabs-audio/SKILL.md:32` | S | T8 |
| C-14 | voiceover-brief and elevenlabs-audio descriptions trigger on the same phrases | S3 | skills | silent | `.claude/skills/voiceover-brief/SKILL.md:3` | S | T8 |
| C-15 | visual-prompts' description advertises shorts-styleboard's trigger phrases and then disclaims them | S3 | skills | silent | `.claude/skills/visual-prompts/SKILL.md:3` | S | T8 |
| C-16 | elevenlabs-music's Gate 1 re-litigates music-brief's tone call using an input it never declares | S3 | skills | latent | `.claude/skills/elevenlabs-music/SKILL.md:139` | S | T8 |
| C-18 | shorts-assembly asks the voiceover brief for two fields it does not emit | S3 | skills | silent | `.claude/skills/shorts-assembly/SKILL.md:18` | S | T8 |
| C-19 | elevenlabs-audio declares shorts-assembly downstream; shorts-assembly never names its spec as an input | S3 | skills | latent | `.claude/skills/elevenlabs-audio/SKILL.md:33` | M | T8 |
| C-22 | Artifact `--kind` values mix stage names, skill names and artifact nouns; app paths add a fourth vocabulary | S3 | skills | loud | `.claude/skills/shorts-ideation/SKILL.md:223` | M | T8 |
| C-23 | The grounding brief has no `kind:`, no `stage:` and no resolver kind, unlike every other artifact | S3 | skills | latent | `.claude/skills/rgs-grounding/SKILL.md:85-95` | M | T8 |
| C-24 | voiceover-brief reads the script "in full" and chases unbounded upstream pointers it does not need | S3 | skills | latent | `.claude/skills/voiceover-brief/SKILL.md:58` | S | T8 |
| C-26 | shorts-styleboard's step 1 names three input sources; its File I/O contract can locate one | S3 | skills | silent | `.claude/skills/shorts-styleboard/SKILL.md:51-53` | S | T8 |
| C-27 | shorts-styleboard instructs writing into visual-prompts' artifact | S3 | skills | docs-drift | `.claude/skills/shorts-styleboard/SKILL.md:54-55` | S | T8 |
| C-28 | visual-prompts still claims ownership of the register system shorts-styleboard now owns | S3 | skills | docs-drift | `.claude/skills/visual-prompts/SKILL.md:53-54` | S | T8 |
| C-34 | `docs/style-library.md` is cross-skill mutable state with no declared owner in any I/O contract | S3 | skills | latent | `.claude/skills/shorts-styleboard/SKILL.md:91` | M | T8 |
| C-35 | shorts-assembly's description implies the script alone is sufficient input | S3 | skills | silent | `.claude/skills/shorts-assembly/SKILL.md:3` | S | T8 |
| C-40 | Six bare `references/…` citations name a file absent from the citing skill | S3 | skills | docs-drift | `.claude/skills/music-brief/SKILL.md:25` | S | T9 |
| C-41 | `visual-prompts/references/visual-registers.md` is a tombstone; 14 citations resolve to a file with no sections | S3 | skills | silent | `.claude/skills/visual-prompts/references/visual-registers.md:1-14` | S | T9 |
| C-43 | `rgs-grounding`'s 116 normative bullets carry no marker and CLAUDE.md never grants the exemption | S3 | skills | docs-drift | `.claude/skills/rgs-grounding/SKILL.md:31-33` | S | T9 |
| C-44 | 33 `[C]`-marked normative blocks carry no `(Channel, video_id)` citation | S3 | skills | latent | `.claude/skills/midjourney-prompting/references/prompt-architecture.md:116,117,119` | M | T9 |
| C-45 | `image-to-video.md` cites bare video IDs with the channel dropped, breaking traceability | S3 | skills | latent | `.claude/skills/visual-prompts/references/image-to-video.md:98,99,100,101,102,103` | M | T9 |
| C-47 | `[T]` applied to a branding assertion that no vendor or platform document states | S3 | skills | latent | `.claude/skills/voiceover-brief/references/voice-selection.md:10-12` | S | T9 |
| C-52 | `rgs-briefs/` contains zero styleboard and zero music artifacts — two stages have never run for real | S3 | skills | coverage-gap | `rgs-briefs/README.md:27-31` | M | T9 |
| C-54 | Every `worked-example.md` is unmarked — nine files, the pattern skills are told to copy | S3 | skills | silent | `.claude/skills/social-repurpose/references/worked-example.md` | M | T9 |
| E-06 | Stage page never states its own status, artifact version, or generation time | S3 | templates | silent | `pipeline-app/pipeline_app/templates/stage.html:3,32-34` | S | T13 |
| E-07 | The hand-edit route has no UI — a whole feature is unreachable | S3 | templates | latent | `pipeline-app/pipeline_app/routes/stages.py:229-290` | S | T13 |
| E-08 | Seven flat nav peers, and the project home is a heading with nothing under it | S3 | templates | latent | `pipeline-app/pipeline_app/templates/partials/header.html:3-11` | M | T13 |
| E-11 | "Run Now" redirects to a page showing no evidence the run started | S3 | templates | silent | `pipeline-app/pipeline_app/routes/discovery.py:17-22,91-102` | M | T13 |
| E-12 | Handle validation: no styling, no failure reason, and a poll loop that can stall forever | S3 | templates | silent | `pipeline-app/pipeline_app/templates/discovery_handles.html:16,70-84` | M | T13 |
| E-15 | Skill editor shows a phantom "Kickoff template" editor on 5 of 13 skills | S3 | templates | silent | `pipeline-app/pipeline_app/templates/skill_editor.html:12-17` | S | T13 |
| E-16 | Doctor is mostly duplicated state and omits the one thing only it could report | S3 | templates | silent | `pipeline-app/pipeline_app/templates/doctor.html:4-10` | S | T13 |
| F-01 | Coverage had never been measured; `pytest-cov` was not installed | S3 | tests | coverage-gap | `requirements.txt` | S | T0 |
| F-28 | `preflight._unwedge_stage`'s three defensive returns silently no-op and are untested | S3 | tests | silent | `pipeline-app/pipeline_app/preflight.py:28-35` | S | T14 |
| F-29 | Appendix F §6 undercounts `test_turn_service.py` at 2 tests; it has 11 | S3 | tests | docs-drift | `docs/audit/appendix-F-tests.md:120` | S | T14 |
| F-66 | Only 2 of 11 files close their sqlite connection; the rest leak into `ResourceWarning` | S3 | tests | silent | `conn.close()` | S | T15 |
| F-70 | 58,169 warnings from three third-party lines bury the suite's only real warning signal | S3 | tests | silent | measured at collection only — `pytest_asyncio/plugin.py:179` 48 | S | T15 |
| F-73 | The app suite reads repo-root files outside `pipeline-app/`, so the two suites are not independent | S3 | tests | latent | `pipeline-app/tests/test_gates.py:7` | S | T15 |
| A-75 | `schema.sql`: no index on `turns.stage_row_id`, no status `CHECK`s, no `ON DELETE` behavior | S4 | artifacts | latent | `pipeline-app/pipeline_app/schema.sql:19-27` | S | T3 |
| A-82 | `read_pointer` trusts both the YAML shape and the path it contains | S4 | artifacts | loud | `pipeline-app/pipeline_app/grounding_service.py:34-39` | S | T3 |
| A-83 | `cli_available` is a startup snapshot rendered beside a live probe of the same fact | S4 | artifacts | docs-drift | `pipeline-app/pipeline_app/main.py:31` | S | T3 |
| A-85 | `app.state.conn` is opened at construction and never closed; no lifespan handler | S4 | artifacts | latent | `pipeline-app/pipeline_app/main.py:16-43` | S | T3 |
| B-97 | On an all-zero-metric day the spotlight falls to alphabetical platform order, favouring Bluesky | S4 | digest | latent | `pipeline-app/pipeline_app/discovery_digest.py:256-265` | S | T7 |
| B-103 | The drafting subprocess inherits the full parent environment and all user-global Claude config | S4 | digest | latent | `pipeline-app/pipeline_app/comment_draft.py:244-266` | S | T7 |
| B-106 | `RECIPIENT` is hardcoded with no environment override while `SENDER` has one | S4 | digest | latent | `pipeline-app/pipeline_app/discovery_notify.py:33` | S | T7 |
| B-108 | The spotlight header renders in a different field order in the text and HTML parts | S4 | digest | latent | `pipeline-app/pipeline_app/email_render.py:108-112` | S | T7 |
| B-109 | `notify` re-reads the run row `build_summary` already fetched | S4 | digest | latent | `pipeline-app/pipeline_app/discovery_notify.py:99` | S | T7 |
| B-110 | The 12,000-char cap and its `[transcript truncated]` marker apply to every platform, not just YouTube | S4 | digest | docs-drift | `pipeline-app/pipeline_app/comment_draft.py:88-92` | S | T7 |
| B-111 | `skipped` handle results are invisible in the email | S4 | digest | latent | `pipeline-app/pipeline_app/discovery_notify.py:105-117` | S | T7 |
| B-03 | Every cost, cap, and timeout knob is a module literal with no configuration surface | S4 | discovery | latent | `pipeline-app/pipeline_app/discovery_instagram.py:54` | M | T4 |
| B-04 | YouTube writes `upload_date`, not the contract's `published` | S4 | discovery | docs-drift | `pipeline-app/pipeline_app/discovery_youtube.py:272` | S | T4 |
| B-09 | Bluesky peek_upload_date's "dead code" comment is false | S4 | discovery | docs-drift | `pipeline-app/pipeline_app/discovery_bluesky.py:69` | S | T4 |
| B-15 | The "no YouTube Data API key" warning is printed once per video | S4 | discovery | latent | `pipeline-app/pipeline_app/discovery_youtube_api.py:151` | S | T4 |
| B-17 | YouTube re-enumerates the entire channel catalogue on every run | S4 | discovery | latent | `pipeline-app/pipeline_app/discovery_youtube.py:60` | M | T4 |
| B-24 | The Instagram `gd_REPLACE` placeholder guard is unreachable | S4 | discovery | latent | `pipeline-app/pipeline_app/discovery_instagram.py:60` | S | T4 |
| B-25 | Unused re-exports and an unused constant | S4 | discovery | latent | `pipeline-app/pipeline_app/discovery_instagram.py:27` | S | T4 |
| B-46 | `/F` silently overwrites operator customization; no query, verify, or uninstall path | S4 | discovery | silent | `pipeline-app/scripts/setup_discovery_task.py:26` | S | T5 |
| B-62 | No traversal risk in path construction; Windows reserved device names are a live hazard | S4 | discovery | latent | `pipeline-app/pipeline_app/discovery_paths.py:13-17` | S | T5 |
| B-64 | Hygiene: mid-file imports, an unchecked Protocol signature, unconfigurable tunables, naive-datetime crash | S4 | discovery | latent | `pipeline-app/pipeline_app/discovery_engine.py:117-123` | S | T5 |
| B-77 | derive_cohort infers cohort from free-text notes and defaults to the out-of-scope label | S4 | discovery | latent | `pipeline-app/scripts/migrate_handles_from_manifest.py:23-37` | S | T6 |
| B-85 | Manifest comment says "six skills"; the repo ships eight pipeline skills | S4 | discovery | docs-drift | `manifests/brand_sources.json:2` | S | T6 |
| A-42 | `_load_linter` re-executes each linter per gate run and leaves it in `sys.modules` | S4 | gates | latent | `pipeline-app/pipeline_app/gates.py:28-43` | S | T2 |
| A-47 | `stages.status` has no CHECK constraint; any string is a legal status | S4 | gates | latent | `pipeline-app/pipeline_app/schema.sql` | S | T2 |
| A-56 | A symlinked skill directory escapes the discovered-set traversal defense | S4 | gates | latent | `pipeline-app/pipeline_app/routes/skills.py:21-25` | S | T2 |
| D-51 | Web-route commits land on whatever branch is checked out, under the ambient identity | S4 | infra | latent | `pipeline-app/pipeline_app/git_helper.py:6-20` | S | T12 |
| D-52 | YouTube Data API key travels in the request URL query string | S4 | infra | latent | `pipeline-app/pipeline_app/discovery_youtube_api.py:160-166` | S | T12 |
| D-53 | FamilyBrain-sourced content in `rgs-briefs/` is not covered by CLAUDE.md's Origin narration | S4 | infra | docs-drift | `rgs-briefs/2026-07-28-rgs-debut-visual-system.md:23` | S | T12 |
| F-79 | Coverage artifacts are untracked and not gitignored | S4 | infra | docs-drift | `.gitignore` | S | T15 |
| C-104 | The two archive branches produce different artifacts | S4 | linters | latent | `scripts/build-cowork-plugin.sh:60-71` | S | T10 |
| C-105 | `scripts/__init__.py` creates the package-shadowing footgun the docs work around | S4 | linters | latent | `scripts/__init__.py:1` | M | T10 |
| A-15 | `run_stage_turn` dereferences a possibly-`None` stage row | S4 | pipeline | loud | `pipeline-app/pipeline_app/turn_service.py:119-120` | S | T1 |
| A-16 | Multi-input templates list bare paths with no stage labels | S4 | pipeline | latent | `pipeline-app/stage_templates/visual.md:6-10` | S | T1 |
| A-17 | `_validate_topology`'s `repo_root` is actually the YAML file's parent directory | S4 | pipeline | docs-drift | `pipeline-app/pipeline_app/pipeline_config.py:32` | S | T1 |
| C-08 | shorts-assembly's output is "five things" followed by a list of six | S4 | skills | docs-drift | `.claude/skills/shorts-assembly/SKILL.md:49-55` | S | T8 |
| C-09 | midjourney-prompting says "Nine inputs" then instructs inferring "the eight inputs" | S4 | skills | docs-drift | `.claude/skills/midjourney-prompting/SKILL.md:64` | S | T8 |
| C-10 | visual-prompts says "Two things you still own at this step" then lists three | S4 | skills | docs-drift | `.claude/skills/visual-prompts/SKILL.md:174-191` | S | T8 |
| C-11 | shorts-ideation's worked-example pointer says "all five workflow steps"; there are six | S4 | skills | docs-drift | `.claude/skills/shorts-ideation/SKILL.md:183` | S | T8 |
| C-25 | music-brief reads the full script and the full voiceover brief for two fields | S4 | skills | latent | `.claude/skills/music-brief/SKILL.md:44` | S | T8 |
| C-29 | Four skill descriptions state no negative scope | S4 | skills | silent | `.claude/skills/shorts-ideation/SKILL.md:3` | S | T8 |
| C-30 | visual-prompts' optional-input section points at "step 4's prompt anatomy", which step 4 disclaims | S4 | skills | docs-drift | `.claude/skills/visual-prompts/SKILL.md:63-65` | S | T8 |
| C-31 | visual-prompts' VALIDATION block mislabels Gate B as an "upstream visual-quality check" | S4 | skills | docs-drift | `.claude/skills/visual-prompts/SKILL.md:289` | S | T8 |
| C-32 | rgs-grounding's citation index points at an unnamed "implementation plan" | S4 | skills | docs-drift | `.claude/skills/rgs-grounding/SKILL.md:178` | S | T8 |
| C-33 | rgs-pairing-review is an orphan in both directions | S4 | skills | coverage-gap | `.claude/skills/rgs-pairing-review/SKILL.md:8-12` | S | T8 |
| C-49 | `docs/style-library.md` invents a sixth provenance marker for a `[P]` decision | S4 | skills | docs-drift | `docs/style-library.md:149` | S | T9 |
| C-50 | `rgs-present-soccer-a` omits the `seed:` field its own Entry format declares | S4 | skills | latent | `docs/style-library.md:48-57` | S | T9 |
| C-51 | Two `[T]` lines in `docs/style-library.md` carry no verification date | S4 | skills | docs-drift | `docs/style-library.md:67` | S | T9 |
| C-55 | Four reference filenames are reused across skills, making bare citations ambiguous by name | S4 | skills | latent | `.claude/skills/visual-prompts/references/worked-example.md:6` | S | T9 |

---

## 4. Top 10 by blast radius

Ranked by how wrong the system can be, for how long, before anyone notices — not by severity
alone. Several entries merge IDs filed separately across appendices; where that happens the
merge is stated.

**1 · A-73 with A-63 and A-72 — a routine act destroys real artifacts, silently, with no
backup.** `_write_synthetic_artifact` passes a literal `1` to `write_artifact`, guarded only by
"this project has no styleboard *DB row*" — never a filesystem check — and `write_artifact`
uses `Path.write_text`, which truncates the target to zero before writing and never `fsync`s.
`pipeline.db` and `runs/` are independently git-ignored and independently described as
disposable, so deleting or relocating the database while `runs/` survives makes the next boot
rewrite every project's genuine `02b-styleboard/artifact.v1.md` with a synthetic "not
recoverable" stub. It ranks first because the trigger is an ordinary maintenance action the
project's own conventions encourage, the loss is total and unrecoverable, and the resulting
file still parses as a valid artifact (A-68), so nothing downstream notices.

**2 · D-04 — the corpus backfill overwrites 420 files in place and reports success when the
API it depends on was never reachable.** `fetch_metadata` returns `{}` identically for a
missing key, an exhausted quota and a network failure; `--apply` then rewrites every file with
`view_count`, `like_count`, `comment_count` and `manual_captions` set to `None` and
`metadata_source` relabelled *away* from `youtube-data-api-v3`, so each record now asserts a
weaker provenance than the data it replaced. `output/` is git-ignored. The script exits `0`.
Second only because it is a hand-run script rather than something that fires on boot.

**3 · C-70 with C-88 and F-14 — the enforcement backbone's parse layer fails open, and the
test suite cannot see it.** A one-character deviation in a shot heading (en-dash for em-dash, a
lowercase vocabulary token) makes the line invisible and deletes that shot from every one of
C1–C20 with no finding; reproduced, a shot with an invented `--sref`, no `No Text.`, no `--ar`
and no `--s` printed `Gate C: PASS — 10 shots, 0 findings`. Gate D has the same shape (C-88:
`**HOOK**` is not a beat, and the beat vanished along with a real 260-wpm violation). Roughly
90 of the 115 Gate C tests construct `Shot` dataclasses directly and therefore begin
*downstream* of where the bug lives, which makes the hole structurally unreachable from the
densest test file in the repo. It ranks this high because the unlinted shot is precisely the
shot most likely to be malformed, and the only signal is the word PASS.

**4 · B-40 + B-41 + B-42 + D-01 + D-02 — the unattended path has no failure channel of any
kind.** `main()` returns a compile-time `0`; the registered `schtasks` action has no
redirection so stdout and stderr go nowhere; `notify()`'s success boolean is discarded at the
one call site that reads it; there is no logging module, no event table, no `/healthz`. A run
in which every handle failed, a run that crashed before touching a handle, a run whose email
was dropped for a missing API key, and a perfectly clean run are one value in Task Scheduler's
Last Run Result column. Discovery can be wholly broken for months and the only symptom is mail
that quietly stops — and because there is no heartbeat email on a quiet day either, an absent
email is not an alarm.

**5 · D-03 with B-12 and B-02 — the corpus is permanently and invisibly incomplete.**
`brightdata_job.py`'s docstring states the invariant ("MUST raise, never return `[]`") and
names the exact bug it fixes; YouTube and Bluesky, the two largest cohorts, violate it —
`_enumerate_tab` returns `[]` on a nonzero yt-dlp exit and Bluesky `break`s the paging loop on
any exception. Compounding it, B-12: a bot-blocked download with a working Data API key writes
a `transcript_status: missing` capture that counts as a success and is *never re-attempted*,
because `on_disk_ids` keys on the filename. B-02 caps every Bright Data platform at 10 items
per run with no saturation detection and no backfill route. The lost material cannot be
identified later, which is what puts this above several higher-severity defects.

**6 · A-01 + A-02 + A-03 + A-04 — the last two stages are told they have inputs they cannot
reach.** `repurpose.md:3` renders "the finished Short's script and edit plan at `<one path>`" —
one edit-plan path described as two documents — and `assembly.md` lists only the two reachable
artifacts under prose that assumes the script. Both stages then write from the edit plan or
reconstruct the script from memory, so hook language, beat timing and packaging in the
published copy are unverifiable against the actual script; and a compliance-shaped constraint
carried by the grounding brief can vanish between grounding and publish with nothing marking
its loss. This fires on **every first turn of both stages on every project**, and the output is
the thing that actually ships.

**7 · A-05 + A-44 + A-45 + A-46 + A-60 — the staleness system launders its own signal.** A
re-run never re-renders the kickoff (`is_first_turn` is `claude_session_id is None` and nothing
ever clears that column), yet writes `depends_on` computed against the *current* upstream — so
the artifact asserts a provenance it was not derived from and `is_stale` reports False forever.
`approve_stage` never calls `is_stale` at all, and `propagate_staleness` skips any dependent
not already `approved`, so a draft whose upstream was replaced before approval is never
flagged. An aborted turn rewrites `stale` back to `awaiting_review`. A first hand edit records
`depends_on: []`, which terminates the cascade at that node permanently. Net: the one mechanism
that exists to say "this was built on something that has since changed" can be cleared by
clicking through it.

**8 · C-79 + C-80 + C-81 + C-75, with F-13 — Gate C's style and format checks are defeated in
two characters, and three tests certify the defeat.** Verified: `--sref 11111111` passes (any
digit string is "plausible", and declaring no slots also skips C20 entirely); a bare `--p`
satisfies C17 while making the render depend on whoever's personalization profile is active;
rewriting `--ar 9:16` to `--ar 16:9` passes, so every asset in a vertical Short renders
landscape and is discovered at assembly; and `--style-library` pointed at a four-line
hand-written file turns a C20 failure into a pass. `test_c16_accepts_numeric_url_and_random_sref`,
`test_c17_accepts_literal_sref_moodboard_or_slot` and `test_c13_flags_missing_aspect_ratio`
each assert the defect is correct behavior, so every fix here reads as a regression.

**9 · D-43 + F-11, enabling D-45 + D-46 — a security control that does not exist, with a green
test asserting it does.** `permissions.allow` grants, it does not restrict, so
`scoped_permissions_settings()` scopes nothing; the test
`test_scoped_permissions_settings_scopes_write_edit_to_runs_and_rgs_briefs` deserializes the
JSON literal the function hard-codes and asserts four strings survived a round trip. With
`scripts/**` and `.claude/hooks/**` absent from the deny list, a stage turn can rewrite the
Gate C linter that `gates.py` then `exec_module`s **inside the uvicorn process**, or rewrite
the `PreToolUse` hook that runs as an unrestricted subprocess inheriting `RESEND_API_KEY`,
`YOUTUBE_API_KEY` and `BRIGHTDATA_API_KEY`. Ranked ninth rather than higher because D-45 and
D-46's write capability is inferred from the deny-list gap rather than demonstrated end to end
(both `probable`); the `exec_module` half and the vacuous control are confirmed.

**10 · B-70 + B-72 — the operator's actual question is structurally unanswerable.** Instagram,
LinkedIn, Facebook and X handles exist only as rows in a git-ignored runtime SQLite file, and
those are exactly the four platforms billed per record. There is no `creator_id`: `@jane` on
YouTube and `@jane` on X are unrelated rows, so one creator cross-posting is captured and
counted three times, no query can total a creator's output, and "which platform are we missing
for this creator" cannot be computed. Of 90 creator×platform cells, 16 are `tracked` and 74 are
unanswerable — and exactly one creator is tracked on more than one platform.

**Two near-misses and why they rank lower.** A-30/A-62 (the hand-edit path runs a *different*
Gate C under the same name, against an operator-authored world lock) would sit in the top five
except that A-84/E-07 establishes the `/edit` route has **no UI entry point at all** — no
template in the repo posts to it. That caps today's blast radius to direct POSTs and uncaps it
the moment the form is added, which is why the edit-path fixes must land before the UI does.
E-02/E-03 (a never-ran gate renders as a clean pass, then the approve button 409s into a dead
end with no override field) is the worst defect in Appendix E and is genuinely silent in half
its manifestation, but it stops at one operator on one page rather than propagating into
shipped output.

---

## 5. Themes

Ten clusters. Counts are the number of findings I place in each; a finding can inform more than
one theme but is counted once, in the theme that explains it best.

**There is no error-surfacing layer (≈28 findings: D-01, D-02, D-06, B-01, B-40, B-41, B-42,
B-43, B-55, B-56, B-61, B-93, B-94, B-95, B-99, B-100, B-104, B-105, B-112, A-74, A-77, C-94,
C-100, E-09, E-10, E-13, E-14, F-16).** This is the single explanatory theme of the audit and
the one Appendix D states outright: the catching is disciplined, the telling is not. Every
carefully-reasoned handler in the codebase terminates in a `print` to a stream nobody reads, an
exit code that is a constant, a status pill with no CSS rule, or an htmx swap with no error
path. Nearly every other theme below is *survivable* in a system that reports its own failures
and *unbounded* in one that does not — which is why §6 puts observability in Wave 1 ahead of
things with higher severities.

**Parse layers that fail open (≈14: C-70, C-71, C-72, C-73, C-76, C-78, C-86, C-88, C-89, C-90,
C-93, A-68, A-69, B-99).** Every deterministic quality check in this system sits on top of a
regex that silently drops what it does not recognize. A shot heading that fails
`SHOT_HEADING_RE` does not fail — it ceases to exist, and the checks then run vacuously over
the survivors. The same shape recurs in `parse_world_lock` (truncates at the first non-matching
line, last-wins on duplicates), `parse_style_library` (drops individual entries on benign
reformatting), `parse_cover` (returns `None` for four distinct states), `parse_script`
(`**HOOK**` is not a beat), `parse_frontmatter` (an unterminated block reads as
"no frontmatter" rather than as damage) and `collect_new_items` (five uncounted `continue`
paths). The correct shape — a line that *looks like* a heading and fails to parse is a hard
finding — appears nowhere.

**Declared contracts the code cannot satisfy (≈21: A-01, A-02, A-03, A-04, B-04, B-98, C-01,
C-02, C-03, C-04, C-05, C-06, C-07, C-12, C-13, C-16, C-18, C-19, C-21, C-26, C-35).** Skills
state their inputs and outputs in prose; nothing checks the prose against the graph, and where
they disagree the prose wins in the model's head and the graph wins in reality.
`shorts-assembly` declares the script REQUIRED at a stage with no scripting dependency;
`voiceover-brief` has no tone-per-beat section though three skills consume one;
`social-repurpose` states three different input lists in one file; the WORLD LOCK key count is
wrong in both skills that state it; `shorts-assembly` asks the voiceover brief for two fields
it does not emit. The adapter frontmatter contract belongs here too — its headline promise is
falsified by the in-tree reference adapter (§8d).

**Two callers, one name (≈10: A-30, A-31, A-48, A-53/D-49, A-62, C-74, C-75, C-93, F-19,
A-60).** `gates.py`'s own docstring says "two gates wearing one name — a stricter CLI and a
laxer app — is worse than having no app gate at all," and the repo has at least four such
pairs: the CLI Gate C lacks the app's empty-world guard and accepts an arbitrary
`--style-library`; the hand-edit path omits `upstream_by_stage` so the same named gate lints
against a different world lock; the hand-edit path copies `depends_on` where the turn path
recomputes it; `STAGE_ID_BY_SKILL` is a hand-copy of `pipeline.yaml` that has already drifted.
Nothing tests any pair for agreement (F-19).

**Tests that measure the wrong thing, or assert the defect (≈13: F-02, F-10, F-11, F-12, F-13,
F-14, F-15, F-21, F-22, F-26, F-30, F-61, C-48).** 95% line coverage, 1,034 green tests, and
every one of the 32 S0/S1 defects one assertion away. Four mechanisms produce that: doubles
that swallow the output under test (`test_turn_service.py`'s fake CLI accepts the rendered
kickoff prompt and inspects nothing, covering the entire 27-line handoff engine with zero
assertions), construction that bypasses the layer where the bug is, assertions on presence
rather than value, and six tests that pin the broken behavior — including one that codifies the
"empty ≠ failed" violation the codebase's own docstring calls "the exact bug that shipped in
the first Instagram adapter."

**Empty is indistinguishable from failed (≈11: D-03, D-04, B-05, B-06, B-11, B-12, B-13, B-14,
B-22, B-95, C-96).** A named sub-case of the theme above, worth separating because the codebase
*knows* about it, wrote it down, fixed it in one place and did not generalize. Bright Data
raises; YouTube and Bluesky return `[]`; the engine maps `[]` to the healthy status
`no_new_content`; the email says the day was quiet. The same shape appears in
`resolve_brief_version` (a nonexistent directory reports "no prior version" and proposes v1
over a live brief) and in the backfill (an API that answered nothing is treated as an API that
had nothing).

**Non-atomic, unlocked writes over the only copy (≈11: A-52, A-63, A-64, A-65, A-66, A-67,
A-70, A-71, A-73, A-78, D-04).** All four S0s live here. Artifacts are the sole durable record —
`runs/` and the DB are both git-ignored — and every write to them is `Path.write_text` with no
temp+rename and no `fsync`; version numbers are allocated by an unlocked directory glob across
a window wide enough to load and execute a linter; `create_project` commits the project row
before its stage rows and directories with no repair path; kickoff-template saves are never
committed at all, so a bad save has no recovery path.

**Unvalidated input crossing a trust boundary (≈13: A-11, A-12, A-47, A-79, A-82, B-47, B-58,
B-60, B-73, B-74, C-99, D-47, D-48).** Free text reaches code that assumes a closed set: a
mistyped timezone on the settings form raises inside `_is_due_now` on every 15-minute wake
forever, killing discovery with no run row and no symptom; an unknown `platform` raises a
`KeyError` *outside* the try that guards the rest of the branch, stranding the handle at
`pending` permanently; `stages.status` and `handles.platform` have no CHECK constraint; scraped
third-party post text renders unsanitized into the operator's browser through `| safe` with no
CSRF protection on any state-changing route.

**Provenance and documentation drift (≈35 `docs-drift` findings plus the marker gap: C-42,
C-43, C-44, C-46, C-47, C-49, C-51, C-54, C-101, C-08–C-11, C-27–C-32, C-40, C-41, D-40, D-53,
B-80, B-85, F-29, F-62, F-80, A-17, A-83).** 329 of 655 normative blocks in the skill set carry
no provenance marker, 14 citations resolve to a tombstone file with no sections, six bare
`references/…` citations name files absent from the citing skill, three skills cite a reference
path relative to their own directory where it does not exist, and the shipped Cowork plugin
calls itself "Seven" while shipping eleven skills and omitting the stage that produces Gate C's
primary input. The repo's discipline about *marking* claims is real; its machinery for
*checking* the marks covers 13 bullets in 1 of 64 reference files (C-48).

**The operator cannot see the state that decides the next action (≈19: E-01–E-16, A-37, A-43,
A-83).** On a stage page the operator's question is "can I approve this, and if not, why not."
The page never states its own status, its artifact version, its generation time, which upstream
changed, or any previously recorded override reason; a gate that never ran removes the entire
gates panel so the page is indistinguishable from a clean pass; a finished turn leaves the
Output and Gates panels showing the previous state with nothing prompting a reload; and every
expected failure returns a bare `PlainTextResponse` that destroys the page. Seven flat nav
peers rank a subsystem alongside the entire production pipeline, and the project home is a
heading with nothing under it.

---

## 6. Fix sequencing DAG

Five waves. Ordering is driven by `depends_on_finding` where it exists and by one principle
where it does not: **nothing can be verified until failures are visible and the tests actually
run**, so observability and CI precede every correctness fix regardless of severity. Fix costs
are the appendices'; `S` dominates throughout.

### Wave 1 — Stop the bleeding: prevent data loss, restore observability

| ID(s) | Why here | Cost |
|---|---|---|
| A-63 | temp+`fsync`+`os.replace` for `write_artifact`/`stamp_final`/`record_gate_override`. Unblocks A-64, A-68, A-73, F-18 | S |
| A-73 | refuse to write a synthetic artifact into a directory already holding `artifact.v*.md`; allocate via `next_version_number` | S |
| D-04 | abort `--apply` before writing when enrichment returned nothing for every id; never downgrade `metadata_source` | S |
| A-71 → A-65 | partial unique index on `turns.status='running'`, then exclusive version allocation + single-flight on the edit path | S, M |
| B-42 | register the scheduled task with `>> log 2>&1`. Unblocks B-41, B-47, B-55, B-61, B-63 | S |
| B-40, B-41, D-01 | map run status onto documented exit codes; persist `notified_at`/`notify_error` on `discovery_runs` | S |
| D-02, B-93 | adopt a logging module; add a health surface to `/doctor` (last run status, last successful notification, errored-handle count) | M |
| F-60 | one `windows-latest` workflow with `root-suite`, `app-suite`, `no-live-credentials` jobs. **Cheapest highest-leverage item in the audit** | S |
| F-68, F-65 | autouse `conftest.py` raising on `subprocess.Popen` so no future test can spawn a billed Bright Data run. F-65 unblocks F-66, F-67, F-69 | S, M |
| F-63, F-61, F-62 | uninstall the editable `pipeline_app` so a worktree cannot test the main checkout; correct the CLAUDE.md invocation sentence | S |

Rationale: A-63 is the root of the artifact-durability cluster and is `S`. F-60 is the only
item that changes whether any later fix is verified by a machine. B-42 alone converts five
downstream findings from "invisible forever" to "diagnosable."

### Wave 2 — Make the gates actually detect

| ID(s) | Why here | Cost |
|---|---|---|
| C-70, C-88 | a line that looks like a heading and fails to parse must be a hard finding. Root of the whole parse-open cluster | S, S |
| C-89, C-90, C-71 | require the `N words` beat declaration so the dropped-text detector cannot be disabled by the artifact; close D5's `skipped` escape; reconcile shot counts | S |
| C-81, C-80, C-79, C-75, C-74 | read `--ar`'s value; drop bare `--p` from C17's accepted mechanisms; resolve numeric `--sref` against the Library; pin or echo the Library path; add the CLI's empty-world guard | S/M |
| F-13, F-14, F-19 | invert the three tests that pin C-79/C-80/C-81; add a parser-mutation class; add a CLI↔app differential test | S/M |
| A-30, A-62 | build `upstream_by_stage` on the edit path from a shared helper, so both write paths run one gate | S |
| A-35, A-36, A-39, A-40 | unrecognized gate `status` must not approve; malformed `gates` frontmatter must 409 not 500; whitespace-only override must not bypass | S |
| A-33 | add the styleboard gate — the artifact C8/C18/C20 all read from is itself unchecked | M |

Rationale: Wave 1's CI is a precondition, because every fix in this wave deletes or inverts a
currently-passing assertion and will otherwise read as a regression. C-70 must precede the
per-check fixes: repairing C13 is pointless on a shot the parser already discarded.

### Wave 3 — Repair the handoff and the staleness cascade

| ID(s) | Why here | Cost |
|---|---|---|
| F-15 | make the test double capture `prompt` and `resume_session_id`. `S`, and the only way any fix below is provable | S |
| A-01 | add `scripting` to `assembly`/`repurpose`, `ideation` to `repurpose`; plural `input_files` in `repurpose.md`. Unblocks A-02, A-03, A-09 | S |
| A-02, A-03, A-04 | route the bed arc and styleboard bindings to `assembly`; add the `grounding_pointer` block to both templates | S/M |
| A-09, A-16, A-07, A-08 | label multi-input paths by stage; guard `input_files[0]` ordering; stop rendering literal `None`; `StrictUndefined` | S |
| A-05, A-44, A-45, A-46 | clear `claude_session_id` when a stage goes stale; evaluate `is_stale` at approval regardless of status; re-lock on dependency change; stop laundering `stale` into `awaiting_review` | M |
| A-60, A-61, A-80 | recompute `depends_on` on the edit path from the shared helper; give backfilled styleboards a real `depends_on`; hash-pin the grounding pointer | S/M |
| A-48, A-50, A-49, A-51, A-52 | derive `STAGE_ID_BY_SKILL` from `stage_defs`; reject an empty save; commit kickoff templates on the same terms as `SKILL.md` | S |
| A-84 / E-07 | **decide** the `/edit` route: build the UI (only after A-60/A-62/A-64/A-65 land) or remove it | M |

Rationale: A-01 is `S` and unblocks three others. F-15 is `S` and is the difference between
fixing the handoff and believing you fixed it. The A-84 decision is deliberately last in the
wave because building the edit UI before the edit-path fixes uncaps four defects at once.

### Wave 4 — Discovery adapters, roster, and the truth of the email

| ID(s) | Why here | Cost |
|---|---|---|
| D-03, B-05, F-12 | extend the `brightdata_job` raise-on-failure invariant to YouTube and Bluesky; delete the test that pins the violation | M |
| B-06, B-57, B-82 | stop permanently disabling a handle on one transient failure; downgrade a dead handle's status | S/M |
| B-10 | `encoding="utf-8", errors="replace"` on all three `subprocess.run` calls; guard `stdout is None` | S |
| B-12, B-13, B-14, B-11, B-16 | treat "metadata succeeded, no transcript" as retryable; stop hiding rate-limits behind a bare except | M |
| B-02, B-22, B-54 | saturation detection as a distinct handle status; Instagram's missing billed-and-captured-nothing escalation; partial-download accounting | M |
| B-47, B-58, B-73, B-74, B-60 | validate timezone, `HH:MM`, `platform` and backfill dates in the route; constrain `platform` in the schema; derive the picker from the registry | S |
| B-50, B-53, B-59 | ownership-aware reclaim + a `WHERE status='running'` guard on `finish_run`; wall-clock cap; Run Now concurrency guard | M |
| B-70, B-72, B-75, B-78 | declare all six platform keys in the manifest; add `creators`/`creator_id`; stop marking seeded handles `validated` without validating | M |
| B-95, B-99, B-100, B-112, B-96 | denominator in the email; count dropped items; say *why* a handle failed | M |
| B-90, B-91 | correct CLAUDE.md's privacy claim to match what actually ships | S |
| F-20, F-24, F-23 | one parametrized adapter-contract sweep over `build_adapters()`; cover `fetch_upload_dates` and `resolve_brief_version.main()` | S/M |

Rationale: nothing here is verifiable before Wave 1 — a fix to an adapter's failure mode is
invisible while the exit code is a constant and the log does not exist. B-42/B-40 are the hard
precondition; B-58 and B-73 are one change made in two layers (§7).

### Wave 5 — Trust boundary, UI, provenance, hygiene

| ID(s) | Why here | Cost |
|---|---|---|
| D-43, D-44, D-45, D-46, F-11 | deny `Write/Edit(scripts/**)` and `(.claude/**)`; stop passing the full parent env into a turn; verify linter files against `HEAD` before `exec_module`; replace the test that certifies the absent control | M |
| D-41, D-42 | vendor htmx into `static/` — one change closes both the SRI gap and the silent offline death | S |
| D-47, D-48, D-54, B-102, B-103 | sanitize every unescaped-Markdown render site; CSRF on state-changing POSTs; extend `comment_draft`'s injection containment to pipeline turns | M |
| E-02, E-03, E-01, E-04, E-05, E-06 | render gates from the registry (so never-ran shows as never-ran) above the artifact; refresh on `result`; real error pages; state the version and status on the page | S/M |
| E-08, E-13, E-14, E-09, E-10, E-11, E-12, E-15, E-16 | the three-section IA; htmx error paths; status pill modifiers; kill the phantom template editor | S/M |
| C-48, C-42, C-43, C-54, C-44, C-46 | write the marker policy (three categories), then widen the provenance test to all 64 reference files behind a shrinking allowlist | M/L |
| C-40, C-41, C-12, C-101, D-40, C-49, C-51 | repair broken citations and the tombstone file; correct the plugin's "Seven"; replace CLAUDE.md's "two outbound dependencies" with the T12 table | S |
| F-64, F-73, C-105, F-74, F-75, F-76, F-77, F-78, F-79, F-80 | merge the two suites (removes the `scripts` collision at its root); pin `yt-dlp`; fix `run_all.sh`; declare test deps | S/M |
| all remaining S3/S4 | independently landable, none blocks another | S |

Rationale: every item here is independently landable and none gates another wave. It is last
by dependency, not by importance — D-43/D-45/D-46 in particular is the one Wave 5 cluster an
operator may reasonably choose to pull forward into Wave 1, since its fix is a deny-list edit.

---

## 7. Cross-appendix duplicates and conflicts

**Seven duplicate groups covering sixteen IDs.** In each case two or three tasks reached the
same defect from different scopes. All are kept in the register at their original IDs — the
duplication is information about which surfaces the defect touches — but each is **one fix**.

| Group | IDs | What happened | Which framing to build from |
|---|---|---|---|
| 1 | **A-53 ≡ D-49** | `commit_skill_edit` issues `git commit` with no pathspec, committing the whole index. Filed identically by T2 (as a skill-editor defect) and T12 (as a git trust-boundary defect) | Identical; D-49 states the fix more precisely (`-- <rel_path>` on both the commit and the `diff --cached --quiet` guard) |
| 2 | **B-41 ≈ D-01 ≈ B-94** | `notify()`'s bool is discarded at `run_discovery_cron.py:105`. T5 sees an exit-code defect, T11 an observability defect, T7 an email-truth defect | **D-01.** Folding it into the exit code (B-41) is necessary but insufficient — a failed notification is the one failure that cannot announce itself by email, so it must be persisted on `discovery_runs` and rendered. B-94's heartbeat-email suggestion is the complement |
| 3 | **B-42 ≈ B-93 ≈ D-02** | stderr is destroyed by Task Scheduler. B-42 is the registration half, B-93 the email-path half, D-02 the repo-wide statement (35 sites, zero `import logging`, no event table) | **D-02**, with B-42's `/TR` redirection as the immediate mitigation. One change to `setup_discovery_task.py` closes the acute form of all three |
| 4 | **B-43 ≡ E-09** | `completed_with_errors` renders identically to `completed`; no `.status-*` CSS rule exists for run statuses | Same fix. E-09 correctly scopes it as "add modifiers to the existing pill system, don't restyle"; B-43 adds the unbounded `list_runs` and the missing aggregation, which E-09 does not |
| 5 | **A-84 ≈ E-07** | `POST …/edit` has no UI entry point | These point at **opposite** fixes — E-07 says build the form, A-84 says decide whether the route should exist. I believe A-84: the route carries A-60, A-62, A-64 and A-65, and building the UI first uncaps all four. Decide, then fix, then build |
| 6 | **C-48 ≡ F-22** | `test_skill_provenance.py` guards 13 bullets in 1 of 64 reference files under a name implying whole-set coverage. F-22 states outright that it independently confirms C-48 | C-48; it additionally catches that `MARKER_RE` omits `[P]`, so a correctly-marked `[P]` bullet inside the guarded slice would fail |
| 7 | **F-30 ≈ F-61** | a bare `pytest` at the repo root passes while omitting the 833-test app suite. Filed S2 by T14 and S1 by T15 | **F-61 and its S1.** The operator-facing fact is an unambiguous green result that exercised 19% of the tests with nothing in the output indicating an omission — that is "wrong output ships silently," not "operator misled" |

**Checked and confirmed NOT duplicates.**

- **`routes/skills.py:8-18`** — A-48 (S2) files `STAGE_ID_BY_SKILL` as a hand-maintained copy
  of `pipeline.yaml` that has already drifted (it is missing `shorts-styleboard`); E-15 (S3)
  files the user-visible consequence for the other five skills that map to nothing (a phantom
  "Kickoff template" textarea with a live Save button). Same constant, two distinct defects with
  two distinct fixes — derive the map from `stage_defs`, *and* render the form conditionally.
- **`run_discovery_cron.py:110`** — B-40 files it; Appendix D's C3 inventory lists the same line
  as UNJUSTIFIED and tags it **T5**, i.e. explicitly handed off rather than filed. The
  file-exclusive scoping worked here; the two agree and there is no second record.
- **`base.html:7`** — three distinct defects on one line (D-40 undocumented outbound dependency,
  D-41 no SRI and no local fallback, D-42 silent death of Browse when the CDN is unreachable),
  plus **E-01, which cites `base.html:76-83`** — a different region entirely, the SSE `finally`
  block that fails to refresh the Output and Gates panels. Four distinct defects, confirmed.
  Note that D-41 and D-42 share one fix (vendor htmx locally), which is a fix overlap, not a
  finding overlap.
- **`handles.platform`** — **B-58 (T5) vs B-73 (T6)** is the one pairing the brief flagged as a
  possible disagreement, and it is not one. B-58 owns the route/orchestration layer: the
  unvalidated form field, and the fact that `adapters[handle_row["platform"]]` at
  `discovery_engine.py:242` raises **outside** the enclosing `try`, so the detached validate
  subprocess dies with no run row. B-73 owns the data-model layer: `platform` is `TEXT NOT NULL`
  with no CHECK, no enum and no FK, and the roster consequence is a ghost handle the operator
  sees as tracked forever. They cite the same line, reach the same diagnosis, and propose
  complementary halves of one fix (validate in the route + constrain in the schema + move the
  lookup inside the try). Keep both; land them together.

**Severities I would have filed differently.** Original IDs and severities are preserved in the
register; these are noted, not changed.

- **A-33** (seven of nine stages ungated; `styleboard` is the load-bearing omission) is filed
  S2. Given that Gate C's C8, C18 and C20 all read *from* the styleboard, that the styleboard is
  itself never checked, and that A-61 makes backfilled styleboards `approved` with no `gates`
  key at all, this meets the S1 definition — wrong output ships silently.
- **D-43** (`scoped_permissions_settings()` restricts nothing) is filed S2 while **F-11** (the
  test that certifies it) is filed S1. The absent control should not rank below the test that
  misreports it; I would put both at S1.
- **B-90 / B-91** are filed `docs-drift`. The mechanism is deliberate and documented, and only
  the CLAUDE.md privacy claim is wrong — so the classification is right — but "the email ships
  the complete body of every X post" is a privacy statement, not documentation hygiene, and
  reads oddly beside genuine drift like a miscounted list.

**One arithmetic conflict, not about code.** T14's brief cites 286 defects for Appendices A–E;
the per-appendix counts sum to **283**, which a header extraction confirms, and T14 uses 283
throughout while F-60's blast-radius text still says 286. With Appendix F's 45 findings the
register total is **328**. No finding is affected.

---

## 8. Contradictions in the project's own documentation

**(a) `[C]` is "usually unmarked" versus "a skill rule with no marker is a bug."** These are the
two most consequential sentences about provenance in the repo and they appear to collide.
`docs/README.md:55-56` defines `[C]` as "**default; usually unmarked in the audit**";
`CLAUDE.md:53` says flatly that "a skill rule with no marker is a bug: it means something was
invented instead of sourced."

They do not actually collide, and the reason matters: **README's exemption is scoped by the
phrase "in the audit," which names `docs/headless-youtube-audit.md`** — the corpus document
that carries 679 inline citations — **not `.claude/skills/`.** CLAUDE.md's bug rule is scoped
to skills. Two documents, two scopes, no overlap. But the wording is close enough that a reader
can carry the corpus-doc exemption across into the skill set, and that is exactly the reading
that would turn C-42's measurement into a non-event.

So: **C-42's 329 unmarked normative blocks are all inside `.claude/skills/`**, where the README
exemption does not reach. They are not, however, 329 bugs, for two reasons Appendix C itself
establishes. First, CLAUDE.md's Anti-generic guarantee scopes explicitly to "the eight pipeline
skills" and "the tool-specialist skills" — eleven of thirteen — and never names the two RGS
skills, whose 116 unmarked bullets use a **deliberately declared alternative vocabulary**
(`[THINKER:]` / `[RESEARCH:]`, stated at `rgs-grounding/SKILL.md:32-33` as intentionally *not*
`[C]`/`[I]`/`[T]`). That is a coherent design decision CLAUDE.md simply never ratified (C-43).
Subtracting it leaves **213 unmarked blocks inside CLAUDE.md's stated scope**. Second, of those,
a substantial share are the nine `worked-example.md` files (C-54), which are illustrative
applications of rules marked elsewhere — and C-42's own proposed fix says the right treatment
there is a single header disclaimer, not per-line markers.

**Resolution.** 329 is a real, measured gap and not a documentation artifact; the number of
genuine "invented content" bugs inside it is smaller, is bounded above by 213, and **is not
currently knowable because nobody has triaged the three categories.** Three concrete
corrections follow: amend `docs/README.md:56` to name `headless-youtube-audit.md` explicitly so
the exemption cannot be read as skill-wide; add a sentence to CLAUDE.md naming the two RGS
skills and their vocabulary; then write the per-file marker policy and let the residual count
fall out of it, enforced by the widened provenance test (C-48). Until that triage exists,
neither "329 bugs" nor "no bugs" is a defensible statement.

**(b) "Two outbound network dependencies" versus fourteen.** CLAUDE.md's Conventions open with
"Local only. No deploying, no external hosting, no cloud sync," and enumerate two exceptions in
the discovery-email path. T12's inventory finds **14 distinct outbound call sites across 9
destination hosts**, of which those two are documented (D-40). The undocumented twelve include
the Anthropic API call that *is* the app's primary function (`cli_runner.py:239`, fired by
every pipeline-stage turn), four `api.brightdata.com` endpoints that are **billed per record**,
the YouTube Data API, the Bluesky XRPC AppView, two `yt-dlp`/transcript paths, Gutenberg and
archive.org, and an `unpkg.com` htmx fetch on **every page load of every page**. The two
documented exceptions are the ones with the most careful rationale in the repo, which makes
the omission of the rest more misleading, not less: an operator making a privacy or air-gap
decision from that clause is working from a network model wrong by a factor of seven. The fix
is D-40's — replace the enumeration with the T12 table, split app-runtime versus manual
toolkit, and mark which are billed.

**(c) "A bare `pytest` does the right thing in both places" — measured false in both places.**
CLAUDE.md's testing convention states that a `pytest.ini` at each level pins the rootdir so a
bare `pytest` works from either directory. T15 measured it: at the repo root, bare `pytest`
gives **201 passed, exit 0, and silently omits all 833 app tests** (F-61); in `pipeline-app/`,
bare `pytest` gives **786 collected, 4 collection errors, `ModuleNotFoundError: No module named
'scripts'`, interrupted** (F-62). Neither outcome is "the right thing," and they fail in
opposite directions — one is falsely green, the other falsely broken. The real requirement is
`python -m pytest`, specifically: the `-m` form prepends the cwd to `sys.path` and the console
script does not. A third hazard compounds it — `pipeline_app` is pip-installed editable against
the **main checkout**, so any invocation that does not put the working tree first on `sys.path`
tests the wrong tree entirely, which in a worktree (like this audit's) is silent (F-63). Two
corrections: state that `python -m pytest` is required and say why in one clause, and fix the
root cause, which is the `scripts` package-name collision the two-rootdir split exists to work
around (F-64, C-105).

**(d) The adapter contract's headline promise is falsified by the reference adapter.**
CLAUDE.md's "Adding a discovery platform" convention — restated at `discovery_digest.py:8-10` —
promises that an adapter honoring the `fetched_at` frontmatter contract "appears in the daily
email — inventory entry, link, title, and spotlight eligibility — with **no change to any
email-side module**." T4 verified all seven adapters do write `fetched_at` in the mandated
shape, so the mandatory half of the contract is genuinely clean. But YouTube — the in-tree
reference implementation and the largest cohort — writes `upload_date`, never `published`
(B-04), and the only reason nothing breaks is that the email side hard-codes a YouTube-shaped
fallback at `discovery_digest.py:191`: `meta.get("published") or meta.get("upload_date")`. The
reference adapter required exactly the email-side change the contract says is never needed, and
B-98 shows the cost of leaving it undocumented: a third field name would drop the date silently,
with no warning, because the alias set is invisible to anyone reading the contract. Two honest
fixes, either sufficient: make YouTube write `published`, or state the alias set in the contract
and in the frontmatter convention.

**(e) Two smaller ones, for completeness.** `docs/style-library.md` invents a **sixth**
provenance marker while CLAUDE.md documents five (C-49), and carries two `[T]` lines with no
verification date against a convention that requires dating (C-51). And the shipped Cowork
plugin calls itself "**Seven** atomic, corpus-grounded skills" in three places — including the
`plugin.json` description a Cowork user actually reads — while shipping **eleven**, and its
bundled README omits `shorts-styleboard` from the pipeline chain entirely (C-101). That
omission is the load-bearing one: `shorts-styleboard` produces the world lock Gate C reads, so
the shipped documentation describes a pipeline in which Gate C's primary input has no origin.

---

## 9. What this audit did NOT cover

**No code was executed beyond the two test suites and a small number of targeted linter runs.**
T0 ran both suites with coverage; T10 ran 25 mutation experiments against the repo's own
fixtures; T12 verified Python-Markdown's non-sanitizing behavior and the ambient encoding and
credential state locally. Nothing else was run. In particular the FastAPI app was never
started, no stage turn was executed, no discovery run was triggered, and no migration was
exercised against a real `runs/` tree.

**No live vendor API was called.** Every `[T]` fact in the corpus and the skills is carried
forward on the appendices' authority and its stated verification date (2026-07-23 for the
corpus, 2026-07-26 for `elevenlabs-audio` and `midjourney-prompting`, 2026-08-06 for
`elevenlabs-music`) — **none was re-verified here**, and CLAUDE.md's own instruction is to
re-verify before relying on them. Bright Data, Resend, the YouTube Data API, the Bluesky
AppView and the Anthropic API were all read as code and never exercised, so every claim about
their *behavior* (billing on an errored batch, the `dead_page` response to a date-ranged X
backfill, snapshot expiry after a timeout) is inference from the adapter code and its comments,
not observation. C-46's note that 187 `[T]` lines carry a verification date in only 2 of 11
files is a measurement of the documentation, not a check of the facts.

**`output/` was not inspected.** The git-ignored corpus — per-channel transcripts, the content
index, merged findings JSON, and `output/brand-intel/` — was never opened. Findings about it
(D-04's destruction path, B-12's permanently transcript-less captures, B-84's missing
`raisinggoodsports-brand-definition.md`) are derived from the code that writes and reads it. It
follows that **no claim here about the corpus's actual current contents is verified.**

**The corpus documents' content was not audited for accuracy.** `headless-youtube-audit.md`,
the gameplan, the production playbook and the two vendor guides were checked only for whether
skills cite them correctly and whether cited paths and sections exist. Whether a given `[C]`
claim is a faithful extraction of what a transcript actually says was **not** checked for any
of the 679 citations.

**No browser session and no manual UI walkthrough.** Appendix E is a read of 15 Jinja templates,
`style.css`, `browse_service.py` and four route modules. Nothing was clicked. The offline
behavior in T12's Q2 was traced through the templates and the stylesheet, not observed with the
network down. Layout, responsiveness, keyboard access and accessibility were entirely out of
scope.

**The runtime database was not read.** `pipeline-app/pipeline.db` is git-ignored and was never
opened, which is precisely why T6's coverage matrix has 74 unanswerable cells: the live roster
for four of six platforms exists only there. Nor was Windows Task Scheduler queried, so
**whether the discovery task is currently registered on this machine, and what its last run
result was, is unknown.** `cowork-plugin/` and `dist/` were not rebuilt or diffed against
`.claude/skills/` — C-102 and C-103 are read from the build script, not from a comparison.

**Findings marked `probable` or `suspected` were not proven.** 22 findings are `probable` and 1
(A-56, symlink traversal) is `suspected`. Four of the `probable` set carry real consequence and
should be treated as hypotheses until demonstrated: **D-45** and **D-46** (a stage turn writing
`scripts/` or `.claude/hooks/` achieving code execution — the deny-list gap and the
`exec_module` are confirmed, the end-to-end write was never performed), **A-65** (the concurrent
double-POST version collision, reasoned from the threadpool dispatch, never raced), and **B-50**
(sleep/hibernate letting a live run be reclaimed).

**Single reviewer per area.** Each of the sixteen tasks had one reviewer with an exclusive file
scope. That is what makes the audit tractable and non-duplicative, and it means **an area's
blind spots are that reviewer's blind spots** — there is no second pass over any file. The
seven duplicate groups in §7 are the only places two reviewers looked at the same defect, and
in every one of those seven they agreed, which is weak evidence for consistency and no evidence
at all about what all sixteen missed together. Appendix F's central finding — that 1,034 green
tests and 95% coverage saw none of 32 severe defects — is a caution that applies to this
document too.

**Two appendices' text was recovered from agent context rather than from disk** (§1). Their
findings were not re-verified against source after recovery.
