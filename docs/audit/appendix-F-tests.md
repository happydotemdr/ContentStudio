# Appendix F — Test Suite: Baseline, Holes & Harness

Part of the ContentStudio pipeline audit, 2026-08-08. Master report:
[`2026-08-08-pipeline-audit.md`](2026-08-08-pipeline-audit.md).

---

## T0 — Test & coverage baseline

**Scope.** Execution only; this task owns no source files. It runs both suites from
their own rootdirs, records the result, and measures line coverage so that T14's hole
analysis rests on measured data rather than on the presence of a plausibly-named test
file. Environment: Windows 11, Python 3.14.4 (`C:\Python314\python.exe`), pytest with
`pytest-asyncio`. **`pytest-cov` was not installed** — it and `coverage` were installed
as part of this audit (`coverage-7.15.4`, `pytest-cov-7.1.0`). That is itself a finding:
coverage had never been measured on this repo.

### 1. Headline result

| Suite | Command (from its own dir) | Result | Wall time | Line coverage |
|---|---|---|---|---|
| Root (linters + provenance) | `python -m pytest tests/ --cov=scripts` | **201 passed**, 0 failed | 0.93 s | **95%** (690 stmts, 36 missed) |
| App (`pipeline-app/`) | `python -m pytest --cov=pipeline_app` | **833 passed, 3 skipped**, 0 failed | 22.01 s | **95%** (2,890 stmts, 147 missed) |
| **Total** | | **1,034 passed, 3 skipped, 0 failed** | ~23 s | **95%** |

Both suites are green. No failures, no errors, no xfail, no xpass.

> **Read this number carefully.** 95% line coverage coexists with 18 independently
> confirmed defects (see Appendices A–E). Coverage here measures *lines executed*, not
> *behavior asserted*. The suite runs almost every line in the codebase and still lets
> a laxer-than-CLI gate, an always-zero exit code, and two structurally unreachable
> stage inputs through. **High coverage is, in this repo, actively misleading** —
> quantifying that is T14's job.

### 2. Per-module coverage — root suite

| Module | Stmts | Miss | Cover | Missing lines |
|---|---|---|---|---|
| `scripts/lint_prompt_sheet.py` | 430 | 9 | 98% | 129, 235, 238, 585, 589-590, 610, 621, 1040 |
| `scripts/lint_script_language.py` | 194 | 3 | 98% | 377, 406, 535 |
| `scripts/resolve_brief_version.py` | 66 | 24 | **64%** | 29, 40, 53, 69-91, 95 |
| `scripts/__init__.py` | 0 | 0 | 100% | — |

`resolve_brief_version.py` is the outlier: 24 consecutive uncovered statements
(69–91) are the bulk of its resolution logic. Handed to T14.

### 3. Per-module coverage — app suite (worst 12 shown; full data in the run)

| Module | Stmts | Miss | Cover | Missing lines |
|---|---|---|---|---|
| `discovery_youtube_api.py` | 105 | 28 | **73%** | 85-86, 93, 99-100, 104-108, 110-112, 190-214 |
| `routes/inspector.py` | 25 | 6 | **76%** | 30, 32, 34, 38-39, 51 |
| `discovery_youtube.py` | 164 | 26 | **84%** | 38, 146, 153-167, 194-196, 224-225, 230-231, 247, 319 |
| `cli_runner.py` | 92 | 11 | 88% | 107, 192-193, 206, 210-211, 216-217, 259, 264-265 |
| `discovery_bluesky.py` | 72 | 8 | 89% | 21-23, 29, 46, 55, 64, 69 |
| `comment_draft.py` | 115 | 10 | 91% | 80, 271-273, 281-282, 285-290 |
| `preflight.py` | 36 | 3 | 92% | 29, 32, 35 |
| `gates.py` | 62 | 4 | 94% | 32, 77, 107, 116 |
| `discovery_digest.py` | 127 | 8 | 94% | 142, 153, 161-162, 224-225, 228-229 |
| `main.py` | 34 | 2 | 94% | 56-57 |
| `browse_service.py` | 158 | 8 | 95% | 55, 79, 82-83, 156, 176, 189, 215 |
| `discovery_engine.py` | 213 | 10 | 95% | 93, 168-169, 171, 176-177, 184-190, 196, 313 |

**100% covered:** `approval_service`, `brightdata_job`, `db`, `discovery_facebook`,
`discovery_instagram`, `discovery_notify`, `discovery_paths`, `discovery_records`,
`discovery_scheduling`, `git_helper`, `pipeline_config`, `prompt_builder`,
`routes/doctor`, `routes/projects`, `state_machine`. **There are no 0%-covered files.**

**The uncovered lines that matter most** — each is a known-defect path:

- `discovery_youtube_api.py:99-112` — the no-API-key branch, i.e. the exact path in
  which **all Shorts are silently dropped** (SEED-8). Uncovered.
- `cli_runner.py:192-193, 210-211, 216-217` — the three `pass`-on-failure handlers
  (taskkill failure, broken-pipe on stdin write, stdin close). Uncovered.
- `discovery_bluesky.py` misses do not include :40-43, so the bare
  `except Exception: break` (SEED-7) *is* executed by tests — but evidently without
  asserting that a swallowed network error is distinguishable from a quiet day.
- `gates.py:107, 116` — the two fail-closed `raise ValueError` branches for a missing
  or unparseable Style Library. Uncovered.
- `preflight.py:29, 32, 35` — the orphaned-turn reconciliation branches. Uncovered.

### 4. Skipped tests (3)

| Test | Reason | Assessment |
|---|---|---|
| `tests/integration/test_real_cli_e2e.py:21` | "Costs real Claude Code subscription usage — set `PIPELINE_APP_RUN_INTEGRATION=1` to run." | The **only** end-to-end test in the repo, and it is opt-in and off by default. Nothing in the repo runs it; there is no CI to run it. In practice the full pipeline is never exercised end to end by any automated check. → T15. |
| `tests/test_browse_service.py:131` | "symlinks require admin rights / Developer Mode on this platform" | Legitimate platform skip; honestly reported. |
| `tests/test_browse_service.py:142` | same | same |

No `xfail`, no `xpass`, no quarantined tests, no `@pytest.mark.skip` without a reason.
The skips that exist are honest.

### 5. Rootdir behavior — verified

The two-rootdir arrangement documented in `CLAUDE.md` and in both `pytest.ini` headers
behaves as described, with one consequence that is **not** documented:

| Invocation | Result | Exit | Verdict |
|---|---|---|---|
| `cd <repo>; python -m pytest tests/` | 201 passed | 0 | correct |
| `cd pipeline-app; python -m pytest` | 833 passed, 3 skipped | 0 | correct |
| `cd <repo>; python -m pytest pipeline-app/tests/` | **4 collection ERRORS**, interrupted | non-zero | **Loud, and therefore fine.** Errors in `test_backfill_youtube_frontmatter.py`, `test_migrate_handles.py`, `test_run_discovery_cron.py`, `test_setup_discovery_task.py` — the root `scripts/` package shadowing `pipeline-app/scripts/`, exactly as documented. |
| `cd <repo>; python -m pytest` (**bare, no args**) | **"201 passed"**, exit **0** | 0 | **SILENT AND WRONG.** `testpaths = tests` scopes the run to the root suite. The 833-test app suite — 80% of all tests in the repo — never runs, and nothing says so. A developer who runs `pytest` at the repo root gets a green result that omits four fifths of the tests. |

The last row is the "looks fine but isn't" pattern applied to the test suite itself.
Filed by T15; recorded here because it was observed during the baseline run.

### 6. Test-count distribution (test functions per file)

> **Corrected 2026-08-08.** The first version of this table was built with a grep
> (`^def test_|^    def test_`) that silently missed every `async def test_`. T14
> caught it. All counts below now come from `pytest --collect-only`, which is
> authoritative. The correction matters: `test_turn_service.py` has **11** tests, not
> 2, so the "2 tests for the handoff engine" claim was wrong and is retracted. The
> other thin-suite counts survived re-measurement unchanged.
>
> This is worth recording rather than quietly fixing: an audit whose central theme is
> *measurement that looks right and isn't* used a flawed measurement in its own
> baseline. The lesson generalizes — `grep -c 'def test_'` is not a test count.

Root suite (authoritative): `test_lint_prompt_sheet.py` **118** ·
`test_lint_script_language.py` 58 · `test_resolve_brief_version.py` 12 ·
`test_protect_briefs.py` 7 · `test_skill_provenance.py` **6**.

App suite, the thinnest files relative to the weight of what they cover:

| Test file | Tests | Module under test | Module LOC |
|---|---|---|---|
| `test_discovery_instagram_sort.py` | 1 | (sort helper) | — |
| `test_routes_doctor.py` | 1 | `routes/doctor.py` | 24 |
| `test_discovery_records.py` | 2 | `discovery_records.py` | 57 |
| `test_git_helper.py` | 2 | `git_helper.py` | 20 |
| `test_main.py` | 2 | `main.py` | 57 |
| `test_routes_inspector.py` | 2 | `routes/inspector.py` | 58 |
| `test_setup_discovery_task.py` | 3 | `scripts/setup_discovery_task.py` | — |
| `tests/integration/test_real_cli_e2e.py` | 1 | the whole pipeline | — (skipped by default) |

**`test_turn_service.py` is NOT thin — it has 11 tests.** That makes the module a
*more* interesting case, not a less interesting one: 11 tests and 98% coverage over the
256-line module that assembles every stage's context and performs every skill handoff,
and it still carries six S1 handoff defects (Appendix A). T14's finding F-29 explains
why — the CLI double those 11 tests use accepts the rendered kickoff prompt and never
inspects it, so the 27-line handoff block executes green on every run without a single
assertion about what it produced. Thin coverage was never the problem here; blind
coverage was. → T14.

### 7. Reproduction

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767" && python -m pytest tests/ --cov=scripts --cov-report=term-missing -q
```

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest --cov=pipeline_app --cov-report=term-missing -q
```

### 8. Findings owned by T0

### F-01 · Coverage had never been measured; `pytest-cov` was not installed
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `requirements.txt`, `pipeline-app/requirements.txt` (neither lists `pytest-cov` or `coverage`); install log for this audit
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: No one could distinguish "tested" from "has a test file named after it". The 2-test `test_turn_service.py` reads as adequate against a 98%-covered module because nothing ever separated line execution from assertion.
- **trigger**: Any attempt to assess test adequacy before this audit.
- **proposed_fix**: Add `pytest-cov` to both `requirements.txt` files and record a coverage floor. Note that a line-coverage floor alone would *not* have caught any of the 18 seed defects — pair it with the assertion-quality review in T14.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T0
- **detected_by**: test-run

### F-02 · 95% line coverage coexists with 18 confirmed defects — coverage is misleading here
- **severity**: S2
- **confidence**: confirmed
- **evidence**: coverage totals above (690/36 and 2890/147); Appendices A–E seed findings
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: The single most likely way this system gets trusted when it should not be. A 95% number invites the conclusion that the suite is thorough; in fact it executes nearly every line while asserting the wrong things about several of them. Any future decision made on the strength of the coverage percentage is unsound.
- **trigger**: Reading the coverage report without reading the assertions.
- **proposed_fix**: Do not adopt a line-coverage target as the quality bar. Record in the repo (README or CLAUDE.md testing section) that coverage is diagnostic only, and let T14's defect→missing-test mapping define the real bar.
- **fix_cost**: S
- **depends_on_finding**: [F-01]
- **owner_task**: T0
- **detected_by**: coverage

### F-03 · The only end-to-end test is opt-in, off by default, and never run
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/integration/test_real_cli_e2e.py:21`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: The full ideation→repurpose chain — the thing the user is asking about — is never exercised automatically. Every handoff defect in Appendix A is exactly the class of bug an end-to-end run would surface and a unit test would not.
- **trigger**: Any pipeline change; nothing runs the chain.
- **proposed_fix**: Keep the real-CLI test opt-in (it costs subscription usage), but add a stubbed-CLI end-to-end test that walks all 9 stages with a fake `claude` binary and asserts each stage received the artifacts its SKILL.md declares required.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T0
- **detected_by**: test-run

---

## T14 — Test-suite hole analysis

**Scope.** This task owns `pipeline-app/tests/**` (48 files) and root `tests/**` (5 files)
and nothing else. It is documentation-only: no test was written, no defect was fixed, and
neither suite was re-run — T0's baseline (both suites green, 95% line coverage on both) is
taken as given and read against the 283 confirmed defect records in Appendices A–E. The
question it exists to answer is not "is there a test for X" but "would any test that exists
have failed if X were broken." Those are different questions, and in this repo they have
different answers almost everywhere. Method: for every S0 and S1 finding in A–E, plus a
27-record S2 sample, trace the defect's code path into the test file that nominally covers
it and read what that file actually asserts.

> **Count note.** The task brief cites 286 defects; the per-appendix counts it gives
> (A 70, B 89, C 87, D 21, E 16) sum to **283**, which matches a header extraction over the
> five appendices. 283 is used throughout. The S0/S1 split is unaffected: **4 S0, 28 S1.**

---

## 1. The central question

**1,034 passing tests. 95% line coverage on both suites. 283 confirmed defects, 4 of which
destroy data. All three numbers are correct simultaneously, and there is no contradiction —
because line coverage and defect detection measure different things, and this repo is a
clean demonstration of how far apart they can drift.**

The arithmetic:

| Quantity | Value |
|---|---|
| Tests passing | 1,034 (1,010 `def test_` functions + parametrize expansion) |
| Line coverage, root suite | 95% — 690 stmts, 36 missed |
| Line coverage, app suite | 95% — 2,890 stmts, 147 missed |
| Confirmed defects, Appendices A–E | 283 (S0 4 · S1 28 · S2 116 · S3 87 · S4 48) |
| **Defects per 1,000 covered statements** | **79** |
| S0/S1 defects a test would have caught, fully | **29 of 32** |
| S0/S1 defects a test would have caught, partially | **3 of 32** |
| S0/S1 defects genuinely not economically testable | **0 of 32** |

That last row is the finding. Not one of the 32 most severe defects in this audit is a
"you can't test for that" defect. Every one of them is a plain assertion away — in several
cases a *single line* away — and in **six** cases a test already sits on the exact code path
and asserts the defect is correct behavior.

**Why 95% coverage saw none of it.** Coverage instruments the *interpreter*: it records that
line 138 of `turn_service.py` executed. It records nothing about whether any assertion in the
process examined what line 138 produced. Four mechanisms turn that gap into 283 defects here:

1. **Test doubles that swallow the output under test.** `test_turn_service.py`'s fake CLI is
   `async def _gen(prompt, cwd, resume_session_id, **kwargs)` (`test_turn_service.py:31`) —
   it accepts the rendered kickoff prompt and the resume id and **inspects neither**. Lines
   133–159 of `turn_service.py`, the 27-line context-assembly block that *is* the handoff
   engine, execute on every one of the 11 tests and contribute to its 98% coverage. Zero
   tests assert one byte of what they build. A-01, A-04, A-05, A-07, A-08 and A-09 all live
   inside those 27 fully-covered, never-asserted lines.
2. **Construction that bypasses the layer where the bug is.** 100+ of the 115 Gate-C tests
   build `Shot(...)` objects through the `make_shot()` / `_shot()` factories
   (`tests/test_lint_prompt_sheet.py:133`, `:533`) instead of parsing text. `parse_sheet` is
   98% covered — by 11 calls, all against hand-written *valid* sheets. C-70's one-character
   heading typo cannot be reached from a `Shot` object. See §3.
3. **Assertions on presence rather than value.** `test_c13_flags_missing_aspect_ratio`
   (`:380`) asserts C13 fires when `--ar` is absent. It never asserts anything about what
   `--ar` *says* — which is C-81 verbatim, at S1: every asset in a vertical Short renders
   landscape and Gate C prints PASS.
4. **Tests that pin the defect.** Six tests assert the broken behavior is correct. The
   suite is not merely silent on these defects; it is load-bearing *for* them. §5.

The one-sentence answer: **the suite tests that the code runs and that its shapes are
well-formed; it almost never tests that a failure is detectable, that a value is right, or
that two paths that must agree do agree — and all 32 S0/S1 defects are in those three
categories.**

---

## 2. Q1 — Defect → missing-test map

**Every S0 and S1 finding in A–E appears below (32 of 32), followed by a 27-record S2
sample.** "Caught?" means: would a reasonably-scoped test, written at the time the code was,
have failed on this defect.

### S0 — data destruction (4 of 4)

| id | Caught? | The missing test |
|---|---|---|
| **A-63** `write_artifact`/`stamp_final`/`record_gate_override` truncate in place | **partially** | `test_an_interrupted_artifact_write_leaves_the_previous_bytes_intact` — patch the write to raise after the target is opened; assert the on-disk artifact still parses and equals the pre-write content. The crash window itself is not reproducible, but the temp+rename *contract* is directly assertable and no test states it. |
| **A-65** `next_version_number` is an unlocked read-then-write spanning a gate run | **yes** | `test_two_overlapping_edit_posts_produce_two_versions_or_a_409` — fire two threaded `POST /stages/{id}/edit` through `TestClient`; assert `artifact.v1.md` and `artifact.v2.md` both exist, or one request 409s. Neither outcome holds today. |
| **A-73** Backfill writes `artifact.v1.md` hardcoded and overwrites unconditionally | **yes** | `test_backfill_refuses_to_overwrite_an_existing_styleboard_artifact` — write a real `02b-styleboard/artifact.v1.md`, delete its DB row, run the migration, assert the file's bytes are byte-identical afterwards. `test_migrations.py`'s 7 tests never place a file the migration could destroy. |
| **D-04** Corpus backfill destroys metadata and reports success when the Data API is unavailable | **yes** | `test_apply_aborts_when_enrichment_returned_nothing_for_every_id` — run `--apply` with no `YOUTUBE_API_KEY`; assert exit code ≠ 0 and that zero `.md` files were rewritten. The shape already exists in that file (`test_backfill_youtube_frontmatter.py:176` asserts `main(...) == 1` for a missing corpus root) — it was simply never pointed at the destructive path. |

### S1 (28 of 28)

| id | Caught? | The missing test |
|---|---|---|
| **A-01** Script unreachable at `assembly`/`repurpose` while both templates assert it is present | yes | `test_every_stage_kickoff_names_every_input_its_skill_declares_required` — parametrize over `pipeline.yaml`; for each stage assert the rendered prompt contains a path for every artifact its `SKILL.md` marks REQUIRED. |
| **A-04** `grounding_pointer` supplied to `assembly`/`repurpose` but neither template uses it | yes | `test_no_context_key_passed_to_render_kickoff_is_unreferenced_by_its_template` — compare the supplied context keys against Jinja's `meta.find_undeclared_variables` per template; assert the difference is empty. |
| **A-05** Re-run never re-renders kickoff, yet records provenance on the new upstream | yes | `test_a_resumed_turn_after_an_upstream_regenerate_is_told_the_new_path` — run turn 1, write upstream v2, run turn 2, assert the `prompt` argument handed to `stream_claude_turn` names `artifact.v2.md`. Impossible today: the fake discards `prompt`. |
| **A-30** Hand-edit Gate C reads an operator-authored world lock, not the styleboard | yes | `test_hand_edit_of_visual_lints_against_the_styleboards_world_not_the_sheets` — POST a sheet whose embedded WORLD LOCK contradicts the approved styleboard; assert Gate C fails against the styleboard. |
| **A-44** Approval never checks staleness; an unapproved draft is never marked stale | yes | `test_approving_a_draft_whose_upstream_advanced_is_blocked` — draft downstream, write upstream v2, POST approve, assert 409 / `ValueError`. |
| **A-51** `save_skill` accepts empty content and silently truncates a SKILL.md | yes | `test_save_skill_rejects_an_empty_body` — POST `content=""`; assert 400 and that the file on disk is unchanged. `test_routes_skills.py`'s 8 tests never submit an empty textarea. |
| **A-52** Kickoff-template saves are never committed | **yes — a test exists and pins the defect** | `test_save_kickoff_template_does_not_commit` (`test_routes_skills.py:54-68`) asserts `calls == []`. Replace with `test_kickoff_template_save_is_committed_like_skill_md` asserting a commit naming the stage. |
| **A-60** Hand edit copies `depends_on`; empty on a first edit and sticky forever | yes | `test_hand_edit_recomputes_depends_on_from_the_current_upstream` — hand-edit a stage with an approved upstream present; assert the new artifact's `depends_on` names that upstream's path and sha, not `[]`. |
| **A-62** Hand-edit path runs Gate C with no upstream map | yes | `test_the_edit_path_and_the_turn_path_run_an_identical_gate_for_visual` — same body through both paths; assert the two findings lists are equal. No test posts to `visual/edit` or `styleboard/edit` at all (§7). |
| **A-80** Grounding pointer has no hash or version pinning | yes | `test_editing_a_grounding_brief_stales_the_stage_that_points_at_it` — write pointer, mutate the brief, assert staleness; plus `test_stage_chat_refuses_to_inject_a_dangling_grounding_path`. |
| **B-02** `MAX_ITEMS_PER_RUN=10` silently truncates active accounts | **partially** | `test_a_full_cap_batch_is_reported_as_saturated_not_ok` — feed exactly 10 items whose oldest is newer than `last_seen_published_at`; assert the handle status is not `ok`. The permanent-unrecoverability half is a design gap no unit test can express. |
| **B-06** A transient Bluesky failure permanently disables the handle | yes | `test_validate_handle_records_error_not_invalid_when_the_fetch_raises` — assert `status != 'invalid'` and `included` stays true. **The suite currently asserts the opposite premise** (`test_discovery_bluesky.py:56-60`). |
| **B-10** cp1252 subprocess decoding crashes or corrupts YouTube enumeration on emoji titles | yes | `test_enumerate_round_trips_an_emoji_video_title` — drive the fake subprocess with UTF-8 bytes containing U+1F60D; assert the title survives and `stdout is None` raises no `AttributeError`. All 31 fixtures in `test_discovery_youtube.py` are ASCII. |
| **B-12** A bot-blocked YouTube download writes a permanent transcript-less capture | yes | `test_metadata_without_a_transcript_is_retryable_not_a_completed_capture` — API metadata present, no `.vtt`; assert the item is not written as `ok: True` / is re-attempted on the next run. |
| **B-47** Unvalidated timezone / `time_of_day` permanently wedge the scheduler | yes | `test_settings_route_rejects_an_unknown_timezone` (assert 400) + `test_is_due_now_degrades_loudly_on_a_stored_bad_timezone` (assert it does not raise past the caller). |
| **B-50** Sleep/hibernate or a wedged heartbeat lets a live run be reclaimed | **partially** | `test_finish_run_cannot_resurrect_an_abandoned_run` — set a run to `abandoned`, call `finish_run`, assert it stays `abandoned`. One assertion closes the evidence-erasing half; the sleep-detection half needs ownership metadata that does not exist yet. |
| **C-70** A one-character shot-heading typo deletes the shot from Gate C | yes | `test_a_shot_heading_that_fails_the_strict_pattern_is_a_finding_not_a_skip` — feed `### Shot 4 - Payoff …` (hyphen); assert a PARSE finding and a nonzero exit. See §3. |
| **C-75** `--style-library` is an unconstrained CLI-only escape hatch that voids C20 | yes | `test_the_resolved_style_library_path_appears_in_the_gate_verdict_line` — assert the PASS/FAIL banner names the Library it used, so a non-default one is visible in the transcript. |
| **C-79** C16 accepts any digit string, so an invented numeric `--sref` passes | **yes — a test exists and pins the defect** | `test_c16_accepts_numeric_url_and_random_sref` (`:554-557`) asserts `--sref 1122334455` yields no findings. Needed: `test_a_numeric_sref_matching_no_library_code_fails_c16`. |
| **C-80** A bare `--p` satisfies C17 while providing no recorded style lock | **yes — adjacent test pins it** | `test_c17_accepts_literal_sref_moodboard_or_slot` (`:664-667`) enumerates C17's accepted mechanisms and never distinguishes recorded from unrecorded. Needed: `test_a_valueless_p_is_not_an_accepted_c17_style_mechanism`. |
| **C-81** C13 checks that `--ar` is present, never what it says | **yes — the existing test tests only presence** | `test_c13_flags_missing_aspect_ratio` (`:380`) covers absence only. Needed: `test_c13_flags_a_landscape_aspect_ratio` asserting `--ar 16:9` fires C13. |
| **C-88** An unrecognized beat heading deletes the beat from Gate D with no finding | yes | `test_a_markdown_styled_beat_label_is_a_parse_finding` — feed `**HOOK**`; assert a PARSE finding and that the parsed beat set still matches the five expected labels. |
| **C-89** The dropped-text detector is opt-in via the artifact it audits | yes | `test_a_beat_heading_with_no_word_budget_is_a_finding` — strip `\| N words`; assert Gate D fails rather than silently narrowing to quoted text. |
| **C-96** A wrong `--dir` or CWD silently reports "no prior version" and proposes v1 | yes | `test_main_errors_when_the_brief_directory_does_not_exist` — `main(["--dir","nope",…,"--next"])` must return nonzero. `main()` is 23 uncovered lines (§8). |
| **C-98** `next_filename` never checks the proposed path, nor `-vN` against frontmatter | yes | `test_next_filename_refuses_a_path_that_already_exists` + `test_find_latest_fails_when_the_filename_suffix_contradicts_the_frontmatter_version`. |
| **D-03** The "empty ≠ failed" discipline was applied to Bright Data but never to YouTube | **yes — a test exists and pins the violation** | `test_enumerate_newest_first_returns_empty_on_fetch_failure` (`test_discovery_bluesky.py:56-60`) asserts an `OSError` yields `[]`. Needed: `test_every_adapter_raises_on_a_transport_failure`, parametrized over the adapter registry. §5. |
| **D-45** A stage turn can rewrite the Gate linters the app then exec's in-process | yes | `test_scripts_is_denied_to_a_stage_turn` — one-line assertion that `Write(scripts/**)` / `Edit(scripts/**)` are in the deny set; plus `test_gates_refuses_a_linter_modified_relative_to_head`. |
| **D-46** A stage turn can rewrite the PreToolUse hook script | yes | `test_dot_claude_is_denied_wholesale_not_just_skills` — assert the deny set covers `.claude/**`; plus `test_the_turn_environment_carries_no_api_keys`. |

**S0/S1 tally: 29 fully catchable · 3 partially · 0 not economically testable.**

### S2 sample (27 records)

| id | Caught? | The missing test |
|---|---|---|
| A-07 Missing upstream renders literal `None` into the prompt | yes | `test_a_missing_upstream_artifact_is_an_error_not_the_string_None` — assert the rendered prompt contains no `"None"` path token. |
| A-08 Jinja default `Undefined` makes a template typo render empty | yes | `test_kickoff_templates_render_under_StrictUndefined` — parametrize over all 9 templates. |
| A-33 Seven of nine stages are ungated | yes | `test_every_stage_with_a_linter_available_has_a_registered_gate` — assert the gate registry covers `styleboard`. |
| A-35 A gate result with an unrecognized `status` approves as if it passed | yes | `test_an_unknown_gate_status_blocks_approval` — inject `status: "weird"`, assert approve raises. |
| A-45 Nothing re-locks a stage whose dependency left `approved` | yes | `test_unapproving_a_dependency_relocks_its_dependents`. |
| A-48 `STAGE_ID_BY_SKILL` duplicates `pipeline.yaml` and has drifted | yes | `test_stage_id_by_skill_matches_pipeline_yaml_exactly` — one set-equality assertion. |
| A-68 `parse_frontmatter` masks a truncated artifact as unversioned | yes | `test_an_unterminated_frontmatter_block_raises_rather_than_returning_empty_meta`. |
| A-70 One shared autocommit connection, no transaction boundary | partially | `test_create_project_leaves_no_row_when_directory_creation_fails` — patch `mkdir` to raise, assert no project row survives. |
| B-05 Bluesky enumerate reports every fetch error as an empty feed | yes — **pinned** | Same test as D-03; the current test asserts the defect. |
| B-11 A failed YouTube `/videos` enumeration is reported as a quiet day | yes | `test_a_nonzero_ytdlp_exit_raises_rather_than_returning_an_empty_list`. |
| B-40 Scheduled run's exit code is a constant | yes — **pinned** | 12 assertions of `exit_code == 0`, none of nonzero. Needed: `test_a_run_with_errored_handles_exits_nonzero`. §5. |
| B-41 `notify()`'s success boolean is discarded | yes — **pinned** | `test_notify_exception_does_not_propagate_or_change_exit_code` asserts the unobservability by name. Needed: `test_a_failed_send_exits_nonzero`. |
| B-99 Per-item parse failures dropped with no log, counter, or file identity | yes | `test_an_unparseable_capture_is_counted_and_named_in_the_digest`. |
| C-01 `voiceover-brief`'s output contract has no tone-per-beat section | yes | `test_every_declared_downstream_input_exists_in_its_upstreams_output_contract` — a cross-SKILL.md contract test; none exists. |
| C-42 Half of all normative bullets carry no provenance marker | yes | `test_every_normative_bullet_in_every_skill_reference_carries_a_marker` — the whole-set version of what `test_skill_provenance.py` does for one file. |
| C-48 `test_skill_provenance.py` guards 13 bullets in 1 of 64 files | n/a — this *is* a test defect | Broaden the glob from one file to `SKILLS/**/references/*.md`. §9 / F-20. |
| C-74 CLI lacks the empty-world fail-closed guard the app path has | yes | `test_the_cli_and_the_app_gate_agree_on_an_empty_world_lock` — a differential test; none exists. |
| C-78 A cover block with a mistyped or empty fence is silently unlinted | yes | `test_a_cover_block_whose_fence_does_not_parse_is_a_finding`. |
| C-94 A missing input file exits 1, indistinguishable from a failing gate | yes | `test_a_missing_input_path_exits_with_a_distinct_code_from_a_failing_gate`. |
| C-101 The plugin ships 11 skills while calling itself "Seven" | yes | `test_the_plugin_description_matches_the_skill_count_on_disk`. |
| D-01 Notification failure is unobservable | yes — **pinned** | See B-41. |
| D-02 No centralized error surface; 35 stderr signals discarded | yes | `test_every_handle_error_reaches_a_durable_surface` — assert a DB row or a file, not stderr. |
| D-43 `scoped_permissions_settings()` restricts nothing | **yes — the test asserts the control that does not exist** | `test_scoped_permissions_settings_scopes_write_edit_to_runs_and_rgs_briefs` (`test_cli_runner.py:458-467`). §5, flagship. |
| D-47 Scraped third-party post text renders unsanitized | yes | `test_a_captured_post_containing_script_tags_renders_escaped`. |
| D-54 Pipeline turns read untrusted corpus text with no containment | partially | `test_a_stage_turn_prompt_delimits_untrusted_corpus_text` — mirrors `comment_draft`'s own delimiter test, which exists (`test_comment_draft.py:267`) and was never generalized. |
| E-04 Every expected failure returns bare `PlainTextResponse` | yes | `test_an_expected_failure_returns_a_rendered_page_not_plain_text` — assert the response is HTML and contains the nav. |
| E-13/E-14 htmx has no error path; Browse cannot distinguish empty from broken | yes | `test_a_browse_tree_500_renders_a_visible_error` + `test_an_unreadable_folder_is_reported_as_unreadable_not_empty`. |

---

## 3. Q3 — The Gate-C case study: why 115 tests and 98% coverage missed 17 evadable checks

`scripts/lint_prompt_sheet.py` is the most heavily tested module in the repo — **115 tests,
430 statements, 98% coverage, 9 missed lines.** Appendix C's T10 proves *by execution* that
**17 of its 26 checks are trivially evadable**, and that breaking one shot heading's `—`
separator to a hyphen drops that shot from **all of C1–C20** while Gate C prints
`PASS — 10 shots, 0 findings` (C-70, S1).

### What the 115 tests actually test

Reading the file end to end, every test falls into one of four shapes:

| Shape | Approx. count | What it establishes |
|---|---|---|
| **Check-fires-on-a-crafted-violation** — build `Shot`s via `make_shot()`/`_shot()`, call one `check_*` function, assert the code is in the findings | ~62 | Each check's *positive* branch works on a well-formed input. |
| **Check-passes-on-a-crafted-conformant-input** — same construction, assert `== []` | ~28 | Each check's *negative* branch works on a well-formed input. |
| **Parse-a-known-good-sheet** — 11 `parse_sheet()` calls against the module-level `SHEET` literal and two fixtures | ~9 | The parser reads a sheet that is already correct. |
| **End-to-end on a fixture** — `main()` / `lint_fixture()` against `passing_sheet.md`, `failing_sheet.md`, `worked_example_sheet.md`, `legacy_do_less_sheet.md` | ~16 | Four canonical documents produce four expected verdicts. |

**The structural fact:** `make_shot()` (`tests/test_lint_prompt_sheet.py:133`) and `_shot()`
(`:533`) construct `Shot` dataclasses **directly from keyword arguments**. Roughly 90 of the
115 tests never touch `parse_sheet` at all. They start with a `Shot` that is, by
construction, perfectly parsed. C-70 is a defect in the transition *from text to `Shot`* —
a region those 90 tests are architecturally incapable of entering. The 98% coverage on
`parse_sheet` comes from 11 calls against text that always parses.

Coverage cannot see this. `SHOT_HEADING_RE.match(line)` at `lint_prompt_sheet.py:66-84` is
executed by those 11 calls and marked covered. The *failing* branch — `match` returns `None`,
the line is skipped, the shot vanishes — is also executed, by every non-heading line in every
sheet. Both branches show green. What is missing is any test that asserts a `### Shot`-shaped
line that fails the strict pattern is an **error** rather than a **skip**.

### The missing test class, named

Four distinct classes are absent, in descending order of what they would have recovered:

1. **Parse-layer adversarial / fuzz testing (the biggest win).** Take a known-good sheet and
   apply single-character mutations to structural tokens — `—`→`-`, `—`→`–`, `·`→`.`,
   uppercase→title case, `### `→`###`, `` ``` ``→`` ```text `` — then assert **the parsed shot
   count is unchanged or a PARSE finding is emitted**. This single property, applied to the
   existing fixtures, catches C-70, C-72 (fence-unawareness), C-73 (world-lock truncation),
   C-78 (cover fence) and C-88 (beat headings in the sibling linter) — five findings, two of
   them S1, from one test class.
2. **A conservation/reconciliation invariant.** `test_parsed_shot_count_matches_the_sheets_declared_shot_count`
   — the sheet states its shot count; the parser must agree. This is C-71 (S2) directly and
   is the general defense against *any* silent drop, including mutations the fuzzer never
   generates. It is the single highest-value missing assertion in the file.
3. **Mutation testing of the checks themselves.** Run `mutmut`/`cosmic-ray` over
   `lint_prompt_sheet.py`; every surviving mutant is a check no test constrains. Applied to
   `if "--ar" not in flags` (`:591-592`), mutating the operand to a different literal
   survives — which *is* C-81 (S1). Applied to `VALID_SREF_VALUE_RE` (`:638`), widening
   `\d+` survives — which is C-79 (S1).
4. **Property-based generation over the check inputs** (Hypothesis). Generate prompt strings
   satisfying each check's *stated intent* and assert the check agrees; generate strings
   violating the intent and assert it fires. C-82 (one word per clause defeats the
   anti-clone check), C-83 (filler satisfies the density count), C-84 (two- and three-entry
   literal no-lists) and C-87 (a lowercase substring is the world-lock test) are all
   "the implementation is a weaker predicate than the docstring" defects — exactly what
   property-based testing exists to find, and what 90 hand-written positive/negative pairs
   structurally cannot find, because each pair was written by the same person, at the same
   time, with the same mental model as the check.

### The aggravating factor

Three of the 115 tests **assert the evasions are correct**:

- `test_c16_accepts_numeric_url_and_random_sref` (`:554-557`) — `assert check_style_reference([shot]) == []` for `--sref 1122334455`. That is **C-79 (S1)** as a passing test.
- `test_c17_accepts_literal_sref_moodboard_or_slot` (`:664-667`) — enumerates C17's accepted mechanisms without distinguishing a *recorded* style lock from an unrecorded one, the distinction **C-80 (S1)** turns on.
- `test_c20_is_skipped_when_no_library_is_supplied` (`:1049-1053`) — `"lint(..., library=None) must behave exactly as it did before C20 existed"`. Correct in isolation; but the hand-edit path reaches `library=None` on **every** `visual` edit (A-30), so this test sanctions the branch that silently disables C20 in production.

**The lesson, stated plainly:** 115 tests bought high confidence in each check's behavior on
inputs that were already well-formed, and zero confidence that a real sheet reaches those
checks at all. The enforcement backbone was tested from the inside out, and the hole is on
the outside.

---

## 4. Q4 — Risk × uncovered: the top 12 modules

Ranked by (consequence of failure) × (what the tests do not assert). Defect counts are
evidence-citation counts across A–E; coverage is T0's.

| # | Module | Cov | Tests | Defects (S0/S1) | What the tests do **not** assert |
|---|---|---|---|---|---|
| 1 | `pipeline_app/turn_service.py` | **98%** | **11** | **28 (0/6)** | **The prompt.** The 256-line handoff engine's only externally visible output is the rendered kickoff string, and the test double discards it (`test_turn_service.py:31`). Also unasserted: `resume_id`, `upstream_paths` ordering, `input_files[0]`, `grounding_pointer`. 98% covered, ~0% of the handoff contract asserted. **The single worst coverage-vs-assertion gap in the repo.** |
| 2 | `pipeline_app/artifacts.py` | ~97% | 13 | **13 (3/1)** | **Durability.** No test asserts temp+rename, `fsync`, version-allocation exclusivity, or that an interrupted write preserves the prior bytes. All three S0 data-destruction findings live here and share one missing test class. |
| 3 | `scripts/lint_prompt_sheet.py` | **98%** | **115** | **25 (0/6)** | **That a real sheet reaches the checks.** ~90 tests bypass the parser entirely. See §3. High coverage from the densest test file in the repo, guarding the wrong layer. |
| 4 | `pipeline_app/routes/stages.py` | ≥95% | 20 | **26 (1/5)** | **The edit path on the stages that matter.** Edit tests use `ideation`, `scripting`, `grounding` only — never `visual` or `styleboard`, the two stages whose gates consume an upstream artifact. A-30, A-60, A-62, A-65 all live in the untested half. |
| 5 | `pipeline_app/gates.py` | **94%** | 15 | 16 (0/4) | **That the two Gate C implementations agree.** No differential test between `scripts/lint_prompt_sheet.py --styleboard` and `gates.run_prompt_sheet_gate`. `:107,116` (both fail-closed `raise`s) uncovered. `test_gates.py:129` *sanctions* the empty-upstream legacy branch every hand edit takes. |
| 6 | `pipeline_app/discovery_engine.py` | **95%** | 33 | **30 (0/5)** | **That a failure is distinguishable from a quiet day.** 33 tests, and the one status transition that matters — transport failure → `no_new_content` — is asserted *as correct* upstream in the adapter tests. |
| 7 | `pipeline_app/cli_runner.py` | **88%** | 23 | ~8 (0/2) | **Any actual restriction.** The one security test asserts an allow-list, not a deny (§5). `:192-193, 210-211, 216-217` — the three `pass`-on-failure handlers — uncovered. No test asserts what a turn *cannot* write. |
| 8 | `pipeline_app/discovery_youtube.py` | **84%** | 31 | 13 (0/3) | **Non-ASCII input, and subprocess return codes.** 31 tests, all ASCII fixtures (B-10). `:217`'s ignored return code is executed but never asserted on (B-12). |
| 9 | `pipeline_app/migrations.py` | ~95% | 7 | (1 S0: A-73) | **That the migration cannot destroy an existing file.** No test places a real artifact in the path the backfill writes to. |
| 10 | `scripts/resolve_brief_version.py` | **64%** | 12 | 9 (0/2) | **The CLI entry point.** `main()` (`:69-91`, 23 statements) is entirely uncovered except via one subprocess test. Every skill invokes this through `main()`; every test but one calls the helpers directly. |
| 11 | `pipeline_app/discovery_bluesky.py` | **89%** | **7** | 10 (0/2) | **That a raise is a raise.** The suite explicitly asserts the "empty ≠ failed" violation (§5). 7 tests for the only adapter that can truncate a *successful* run mid-pagination. |
| 12 | `pipeline_app/discovery_youtube_api.py` | **73%** | 19 | ~5 (1 S0 via D-04) | **The no-key path.** `fetch_upload_dates` (`:182-214`, 25 statements) has **no test at all** — the function whose `{}` return silently drops every Short from the global ordering. `test_fetch_metadata_returns_empty_without_key` asserts the sibling function's `{}` return is correct, which is D-04's root cause. |

**Where high coverage most badly masks low assertion quality:** rows 1, 2, 3 and 5. All four
are at 94–98% and all four are missing the *only* assertion that would matter. `turn_service.py`
is the extreme case: **98% covered, 11 tests, 28 defect citations, 6 of them S1, and not one
assertion on the artifact the module exists to produce.**

---

## 5. Q2 — Tests that pass for the wrong reason

Six tests assert broken behavior is correct. Two more assert nothing meaningful.

### Flagship — a test asserting a security control that does not exist

`pipeline-app/tests/test_cli_runner.py:458-467`:

```
def test_scoped_permissions_settings_scopes_write_edit_to_runs_and_rgs_briefs():
    data = _json.loads(scoped_permissions_settings())
    allow = data["permissions"]["allow"]
    assert "Write(runs/**)" in allow
    assert "Edit(runs/**)" in allow
    assert "Write(rgs-briefs/**)" in allow
    assert "Edit(rgs-briefs/**)" in allow
```

The function under test (`cli_runner.py:130-139`) returns a hard-coded JSON literal containing
exactly those four strings and nothing else. **The test re-reads the literal the function
writes.** It is tautological in the strictest sense: it cannot fail unless someone edits the
literal, and it would still pass if `permissions.allow` were renamed to `permissions.irrelevant`
in Claude Code's schema tomorrow.

Its name and the function's docstring both claim a restriction — *"scoping Write/Edit to
runs/\*\* and rgs-briefs/\*\*, per the design spec's §5 permission-scoping requirement — a
pipeline-stage turn must never touch docs/, output/, or .claude/skills/"* — and
`permissions.allow` is an **auto-approve** list, which grants rather than restricts. So a
reviewer asking "is a stage turn's write scope enforced?" gets **yes** from a docstring, a
function name, and a green test, and the answer is **no**. D-45 (S1, arbitrary code execution
via rewriting the Gate linters) and D-46 (S1, PreToolUse hook rewrite with `*_API_KEY` in the
inherited environment) are the direct consequence.

### The "empty ≠ failed" invariant, asserted in both directions

`brightdata_job.py`'s module docstring states the rule: a failed job *"MUST raise, never
return []"*, because returning `[]` *"would make a paid, failed job indistinguishable from a
quiet day."* The suite tests that rule correctly for Bright Data —
`test_brightdata_job.py:97` and `:127` both `pytest.raises`. And then:

`pipeline-app/tests/test_discovery_bluesky.py:56-60`:

```
def test_enumerate_newest_first_returns_empty_on_fetch_failure(monkeypatch):
    def raise_error(url):
        raise OSError("network down")
    monkeypatch.setattr(bsky, "_http_get", raise_error)
    assert bsky.enumerate_newest_first("dead.bsky.social", keyword_filter=None) == []
```

The test's name and its assertion together **codify D-03 (S1) as intended behavior**, in the
same suite that codifies the opposite for Bright Data. B-05 and B-06 (S1 — a valid handle
permanently disabled by a momentary outage) follow from it directly.

### The exit code, asserted never to change

`pipeline-app/tests/test_run_discovery_cron.py` contains **12 assertions of `exit_code == 0`
and zero assertions of a nonzero exit.** One of them is named for the property it pins:

```
def test_notify_exception_does_not_propagate_or_change_exit_code(...):
    ...
    assert exit_code == 0
    assert "discovery notification failed" in capsys.readouterr().err
```

That is B-40, B-41 and D-01 in a single test. It is also — see §7 — the **only** test in either
suite that asserts a diagnostic reaches stderr, and it asserts it alongside a success exit
code, on the exact path D-02 shows Task Scheduler discards.

### The absence, pinned

`pipeline-app/tests/test_routes_skills.py:54-68` — `test_save_kickoff_template_does_not_commit`,
ending `assert calls == []`. A-52 (S1): kickoff-template saves have no commit, no backup and no
recovery path, and a test holds that asymmetry in place with no stated rationale.

### The Gate-C three

Covered in §3: `test_c16_accepts_numeric_url_and_random_sref` (`:554`) pins C-79;
`test_c17_accepts_literal_sref_moodboard_or_slot` (`:664`) leaves C-80's distinction
unexpressed; `test_c20_is_skipped_when_no_library_is_supplied` (`:1049`) and
`test_gates.py:129`'s `test_visual_gate_without_a_styleboard_uses_a_legacy_sheets_own_world_lock`
between them sanction the empty-upstream branch that A-30/A-62 show every hand edit takes.

### Assertions on the mock rather than the behavior

- `pipeline-app/tests/test_main.py:15-30` — both tests monkeypatch `preflight.check_cli_available` to return a dict, then assert `app.state.cli_available` equals the boolean they just injected. The assertion is on the mock's value round-tripping through one attribute assignment; `create_app`'s 34 statements are otherwise unexamined.
- `pipeline-app/tests/test_turn_service.py:335-343` — `run_gates_for_stage` is monkeypatched to return a literal findings list, and the test then asserts that literal appears in the artifact's frontmatter. It verifies frontmatter plumbing (worthwhile) but is filed under a name — `test_scripting_turn_records_gate_results_in_frontmatter` — that reads as gate-integration coverage. **The gate is the thing mocked.**

---

## 6. Q5 — The five thin suites

T0 lists five. **One of its counts is wrong:** `test_turn_service.py` has **11** test
functions, not 2 (verified by AST-shaped grep over `def test_`; the other four counts are
correct). The correction makes the module *worse*, not better — 11 tests that never assert
the module's output is a stronger indictment than 2.

| Suite | Tests | Module (LOC) | What is actually asserted | Verdict |
|---|---|---|---|---|
| `test_turn_service.py` | **11** | `turn_service.py` (256) | Turn *lifecycle* only: single-flight rejection (3), abort/disconnect bookkeeping (3), staleness cascade (2), artifact-written / not-written (2), gate-result plumbing with the gate mocked (1). | **Not a smoke test — a well-built test of the wrong half.** The lifecycle is genuinely well covered. The handoff — lines 133–159, upstream resolution, kickoff rendering, `is_first_turn`/resume — has **zero** assertions because the test double discards `prompt` and `resume_session_id`. Six S1 findings live in the unasserted half. |
| `test_main.py` | 2 | `main.py` (57) | That `app.state.cli_available` equals the boolean injected into a monkeypatched preflight. | **Smoke test wearing a unit test's name.** Nothing about DB init, router mounting, the startup orphan sweep, or `pipeline.yaml` load failure. `:56-57` uncovered. |
| `test_git_helper.py` | 2 | `git_helper.py` (20) | A commit is created; a no-op re-save does not raise. | **Adequate for its size, wrong for its blast radius.** Never asserts *what* was committed — which is D-49/A-53 (`commit_skill_edit` commits the entire index, not the file it staged). One `assert` on `git show --stat` would have caught it. No timeout assertion (D-50). |
| `test_discovery_records.py` | 2 | `discovery_records.py` (57) | Frontmatter counters for a hand-built 3-handle result set; parent-dir creation. | **Fixture-shaped, not contract-shaped.** The counters are asserted against a literal the test wrote. Never asserts the totals *reconcile* (B-56: `skipped` handles are counted but the frontmatter totals do not add up) — the one property that would have caught a real defect. |
| `test_routes_doctor.py` | **1** | `routes/doctor.py` (24) | HTTP 200 and the substring `"Claude CLI"`. | **Pure smoke test.** Renders-without-crashing, nothing more. E-16 (Doctor is mostly duplicated state and omits the one thing only it could report) is invisible to a status-code-plus-substring assertion. |

Two of the five (`turn_service`, `git_helper`) are thin in the dangerous way: the assertions
present are correct and the assertion that matters is absent. Three (`main`, `routes_doctor`,
and `discovery_records`'s first test) are smoke tests carrying unit-test names.

---

## 7. Q6 — Does any test assert that a failure is observable?

**Effectively no.** Precisely:

- **Exit codes.** Nonzero exits *are* asserted — but only in the two linter CLIs and one
  script: `tests/test_lint_prompt_sheet.py:506,512,1103,1117,1129`,
  `tests/test_lint_script_language.py:602,608`, and
  `pipeline-app/tests/test_backfill_youtube_frontmatter.py:176`. That is **8 nonzero-exit
  assertions in 1,034 tests**, all on tools a human runs interactively and watches.
- **The scheduled path — the one that runs unattended — has the inverse.**
  `test_run_discovery_cron.py`: **12 assertions of `exit_code == 0`, zero of anything else**,
  including `test_notify_exception_does_not_propagate_or_change_exit_code`, whose name is the
  property B-40/B-41/D-01 identify as the defect.
- **Surfaced errors.** No test in either suite asserts an HTTP 5xx, an htmx error swap, or
  that an operator-visible surface names a failure. `pytest.raises` appears ~40 times, but on
  *service-layer* exceptions (`PathSafetyError`, `ValueError`, `BrightDataJobFailed`) — never
  on the question of whether that exception reaches a human. E-04, E-10, E-13 and E-14 are all
  untouched.
- **"Zero results" vs "the fetch failed".** One test addresses this directly, and it asserts
  the wrong side (`test_discovery_bluesky.py:56-60`, §5). `test_discovery_engine.py:374`
  asserts `status == "no_new_content"` for a genuinely empty run — correct — but **no test
  anywhere feeds a transport failure through the engine and asserts the resulting status
  differs.** For Bright Data the discipline is tested (`test_brightdata_job.py:127`); for
  YouTube and Bluesky, the two largest cohorts, it is tested in reverse.
- **stderr.** 12 files use `capsys`/`capfd`, and the assertions are almost all on *success*
  output (a printed count, a dry-run command string). The single assertion that a *failure*
  message reaches stderr is the `notify` test above — which pairs it with `exit_code == 0`.
  Appendix D's 39 stderr-only failure sites (35 unjustified) are otherwise entirely
  unasserted.

**Stated plainly, as requested: there is no test in this repository that asserts an unattended
failure is observable to a human. The one test that comes closest asserts that it is not.**

---

## 8. Q7 — Entirely untested paths, and the test each needs

| Path | What lives there | Missing test |
|---|---|---|
| `discovery_youtube_api.py:190-214` (`fetch_upload_dates`, incl. `:191-192` no-key `return {}`) | The no-API-key branch. Without dates there is no global ordering across the `/videos` and `/shorts` tabs, so **every Short is silently dropped** (SEED-8). 25 statements, **zero tests** — the function is never named in `test_discovery_youtube_api.py`. | `test_fetch_upload_dates_without_a_key_is_distinguishable_from_no_results` — assert the no-key path raises (or returns a sentinel the caller must handle), and separately `test_enumerate_drops_no_shorts_when_upload_dates_are_unavailable`. |
| `cli_runner.py:192-193` (taskkill failure), `:210-211` (broken pipe on stdin write), `:216-217` (stdin close) | Three bare `pass`-on-failure handlers in the subprocess teardown path. | `test_a_failed_taskkill_is_recorded_not_swallowed` / `test_a_broken_pipe_on_stdin_marks_the_turn_failed` — assert each handler leaves a trace the turn record can carry, rather than `pass`. |
| `gates.py:107` and `:116` | The two fail-closed `raise ValueError`s for a **missing** and an **unparseable/empty** Style Library. Both are the fail-closed guarantee C20 rests on, and neither is exercised. (`test_gates.py` has an analogous test for the empty *styleboard*, `:139` — the pattern exists and was not extended to the Library.) | `test_gate_c_errors_when_the_style_library_file_is_absent` and `test_gate_c_errors_when_the_style_library_parses_to_zero_entries` — assert `status == "error"` and that the message names the file. |
| `preflight.py:29, :32, :35` | `_unwedge_stage`'s three defensive early returns: stage row missing or not RUNNING, `stage_def` unknown, project row missing. A stage whose `stage_id` is no longer in `pipeline.yaml` silently stays wedged at RUNNING forever. | `test_unwedge_is_a_no_op_for_a_stage_id_no_longer_in_pipeline_yaml` — assert the row is left alone **and** that the condition is reported, not swallowed. |
| `resolve_brief_version.py:69-91` (all of `main()`) | The CLI entry point that **ten skills instruct the model to invoke.** 23 statements. `--dir` defaulting to a CWD-relative path (C-96, S1), `--date` interpolated unvalidated (C-99), the overloaded exit-1 (C-100). The 12 tests in `test_resolve_brief_version.py` call `find_latest`/`next_filename` directly; exactly one (`:83`) shells out, and only to check path separators. | `test_main_errors_when_the_brief_directory_does_not_exist` (assert nonzero, and that the resolved absolute directory is echoed) · `test_main_rejects_a_malformed_date` · `test_main_uses_a_distinct_exit_code_for_no_prior_version_and_for_a_malformed_brief`. |

---

## 9. Findings

### F-10 · All 32 S0/S1 defects were within reach of a test; none was written
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `docs/audit/appendix-F-tests.md:22-24`, Appendices A–E (4 S0, 28 S1); §2 above
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: The suite's 95% coverage and 1,034 green tests are read, reasonably, as evidence of thoroughness. In fact 29 of the 32 most severe defects are one assertion away and 3 more are partially so; **zero** are genuinely untestable. Every future decision that treats the green suite as a safety signal is unsound, including the decision not to write these tests.
- **trigger**: Any change to any module in §4's top 12. The suite will stay green.
- **proposed_fix**: Adopt the §2 table as the regression-test backlog and land it S0-first; make "which assertion would have failed?" a required field in any future defect writeup, so the gap is measured continuously rather than once.
- **fix_cost**: L
- **depends_on_finding**: [F-02]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-11 · A test asserts a security control that does not exist, and its name is the evidence
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_cli_runner.py:458-467`, `pipeline-app/pipeline_app/cli_runner.py:122-139`
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: `test_scoped_permissions_settings_scopes_write_edit_to_runs_and_rgs_briefs` deserializes the JSON literal the function under test hard-codes and asserts four strings survived the round trip. `permissions.allow` grants, never restricts. A reviewer verifying the design spec's §5 write-scoping requirement gets a green test, a matching function name and a matching docstring — and the control is absent. D-45 and D-46 (both S1, both arbitrary code execution in the app process or with `*_API_KEY` in the environment) are the direct consequence.
- **trigger**: Reading `test_cli_runner.py:458` to answer "is a stage turn's write scope enforced?"
- **proposed_fix**: Replace with a behavioral test that asserts the effective deny set — that `Write(scripts/**)`, `Edit(.claude/**)` and the like are refused — and rename the function to match whatever it actually does once D-43's fix lands.
- **fix_cost**: M
- **depends_on_finding**: [D-43]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-12 · A test codifies the "empty ≠ failed" violation the codebase's own docstring forbids
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_discovery_bluesky.py:56-60`, `pipeline-app/pipeline_app/brightdata_job.py:6`, `pipeline-app/tests/test_brightdata_job.py:97,127`
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: `test_enumerate_newest_first_returns_empty_on_fetch_failure` asserts that an `OSError` from the transport yields `[]`. `brightdata_job.py`'s docstring names that exact behavior as "the exact bug that shipped in the first Instagram adapter", and the Bright Data tests assert the opposite. The suite therefore holds one invariant in two directions, and the direction it pins is the one covering the corpus's two largest cohorts. D-03, B-05 and B-06 all rest on it; B-06 permanently disables a valid handle after one momentary outage.
- **trigger**: Any attempt to make a Bluesky transport failure raise — this test fails, and reads as a regression.
- **proposed_fix**: Delete it and replace with a registry-parametrized `test_every_adapter_raises_on_a_transport_failure`, so the invariant is stated once for all six platforms instead of per-adapter.
- **fix_cost**: M
- **depends_on_finding**: [D-03]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-13 · Three Gate-C tests assert evadable checks are correct behavior
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `tests/test_lint_prompt_sheet.py:554-557`, `tests/test_lint_prompt_sheet.py:664-667`, `tests/test_lint_prompt_sheet.py:380-382`
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: `test_c16_accepts_numeric_url_and_random_sref` asserts `--sref 1122334455` produces no findings — C-79 (S1) as a green test. `test_c17_accepts_literal_sref_moodboard_or_slot` enumerates C17's accepted mechanisms without distinguishing a recorded style lock from an unrecorded one — the distinction C-80 (S1) turns on. `test_c13_flags_missing_aspect_ratio` covers `--ar` absence only, never its value — C-81 (S1), under which every asset in a vertical Short renders landscape and Gate C prints PASS. Each fix must delete or invert an existing passing assertion, which makes the fix look like a regression.
- **trigger**: Fixing C-79, C-80 or C-81. The corresponding test fails.
- **proposed_fix**: Rewrite the three as intent assertions — a numeric `--sref` must resolve against a recorded Library code; a valueless `--p` is legitimate syntax but not a recorded lock; `--ar` must equal the format's required ratio.
- **fix_cost**: S
- **depends_on_finding**: [C-79, C-80, C-81]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-14 · The Gate-C suite bypasses the parser, making the largest hole structurally unreachable
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `tests/test_lint_prompt_sheet.py:133-144`, `tests/test_lint_prompt_sheet.py:533-544`, `scripts/lint_prompt_sheet.py:66-84`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: Roughly 90 of the 115 tests construct `Shot` dataclasses directly through `make_shot()` / `_shot()` rather than parsing text, so they begin downstream of the text→`Shot` transition where C-70 (S1) lives. `parse_sheet` shows 98% coverage from 11 calls, every one against a sheet that already parses. No mutation of a structural token — separator, vocabulary case, fence — is ever fed to the parser, so a one-character heading typo deleting a shot from all of C1–C20 is invisible to the densest test file in the repo.
- **trigger**: Any sheet emitted with an en-dash, a hyphen, or a non-uppercase vocabulary token in a shot heading.
- **proposed_fix**: Add a mutation-of-a-known-good-sheet test class over the existing fixtures, asserting that each single-character structural mutation either preserves the parsed shot count or emits a PARSE finding. Pair it with a shot-count reconciliation assertion so any silent drop fails regardless of cause.
- **fix_cost**: M
- **depends_on_finding**: [C-70]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-15 · `test_turn_service.py`'s CLI double discards the prompt, so the handoff engine's output is never asserted
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_turn_service.py:30-37`, `pipeline-app/tests/test_turn_service.py:148-152`, `pipeline-app/pipeline_app/turn_service.py:133-159`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: `_fake_stream`'s inner `_gen(prompt, cwd, resume_session_id, **kwargs)` accepts the rendered kickoff prompt and the resume id and inspects neither; the three `_slow_gen` doubles do the same. `turn_service.py:133-159` — upstream resolution, `is_first_turn`, `input_files[0]`, `grounding_pointer`, the whole kickoff render — executes on all 11 tests, contributing to 98% coverage, with zero assertions. A-01, A-04, A-05 (S1 each) plus A-07, A-08 and A-09 are all inside those 27 lines. This is the repo's single widest coverage-vs-assertion gap.
- **trigger**: Any change to a stage's `depends_on`, to a kickoff template, or to the resume logic.
- **proposed_fix**: Have the double capture `prompt` and `resume_session_id` into a list the test can assert on, then add per-stage assertions that the prompt names every required input and that a resumed turn is told about a new upstream version.
- **fix_cost**: S
- **depends_on_finding**: [A-01, A-04, A-05]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-16 · No test asserts a nonzero exit or a surfaced error on any unattended path
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_run_discovery_cron.py:24,33,42,59,74,88,101,112,124,139,151,167`, `pipeline-app/tests/test_run_discovery_cron.py` (`test_notify_exception_does_not_propagate_or_change_exit_code`)
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: The scheduled discovery path — the only thing in this repo that runs with no human watching — is covered by 22 tests containing **12 assertions of `exit_code == 0` and none of any other value**, one of which is named for the property Appendix B files as B-40. Across both suites there are 8 nonzero-exit assertions total, all in interactively-run linter CLIs. No test asserts an HTTP 5xx, an htmx error swap, or that any failure reaches an operator surface. D-02's 35 unjustified stderr-only sites are unasserted, and E-04/E-13/E-14 have no test at all.
- **trigger**: Any unattended failure. Nothing distinguishes it from success.
- **proposed_fix**: Add an exit-code truth table test for `run_discovery_cron.main` covering errored handles, a failed send and a wedged scheduler; add one route test per E-04 condition asserting a rendered error page rather than a bare `PlainTextResponse`.
- **fix_cost**: M
- **depends_on_finding**: [B-40, D-01, D-02]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-17 · No test exercises `visual/edit` or `styleboard/edit` — the only edit paths whose gate reads an upstream
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_routes_approve_edit.py:104,143,182,215,289,309`, `pipeline-app/tests/test_routes_stages.py:239`, `pipeline-app/pipeline_app/routes/stages.py:266`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: Every `POST .../edit` in the suite targets `ideation`, `scripting` or `grounding`. `visual` and `styleboard` are the two stages whose gates consume an upstream artifact, and are therefore the only two where the edit path's omitted `upstream_by_stage` argument changes the gate that runs. A-30, A-60, A-62 (S1 each) and A-65 (S0) all live on that untested path, and the fixture choice makes them structurally unreachable rather than merely unwritten.
- **trigger**: Saving a `visual` or `styleboard` artifact through the stage page's edit form.
- **proposed_fix**: Add a `visual`-stage edit fixture with a real styleboard upstream, and assert the edit path and the turn path produce identical gate findings for identical bodies.
- **fix_cost**: M
- **depends_on_finding**: [A-30, A-62]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-18 · No test asserts artifact writes are atomic, exclusive, or non-destructive
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_artifacts.py` (13 tests, no durability assertion), `pipeline-app/tests/test_migrations.py` (7 tests), `pipeline-app/pipeline_app/artifacts.py:44-46,72-105`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: All three S0 data-destruction findings — A-63 (in-place truncation, no temp+rename), A-65 (unlocked version allocation), A-73 (hardcoded `v1` overwrite in the backfill) — are properties of the same module and share one missing test class: nothing asserts that a write is atomic, that version allocation is exclusive, or that a migration cannot overwrite an existing file. `test_migrations.py` never places a real artifact where the backfill writes.
- **trigger**: A crash mid-write, two concurrent edit POSTs, or a `pipeline.db` reset with `runs/` intact.
- **proposed_fix**: Add a durability contract test class: an interrupted write preserves prior bytes; two overlapping edits yield two versions or a 409; the backfill refuses a directory already containing `artifact.v*.md`.
- **fix_cost**: M
- **depends_on_finding**: [A-63, A-65, A-73]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-19 · No test asserts the CLI and app Gate C implementations agree
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_gates.py:129-137`, `scripts/lint_prompt_sheet.py:978-984,989-992`, `pipeline-app/pipeline_app/gates.py:104-111`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: `gates.py`'s own docstring says "two gates wearing one name — a stricter CLI and a laxer app — is worse than having no app gate at all", and nothing tests the equivalence. C-74 (CLI lacks the empty-world fail-closed guard), C-75 (S1, `--style-library` voids C20 on the CLI only) and A-31 (the two disagree on an empty world lock) are all divergences the two test files cannot see because each tests its own side. `test_visual_gate_without_a_styleboard_uses_a_legacy_sheets_own_world_lock` additionally sanctions the empty-upstream branch A-30/A-62 show every hand edit silently takes.
- **trigger**: Any change to either implementation.
- **proposed_fix**: Add a differential test that runs both implementations over the same fixture set and asserts identical findings; keep the legacy-branch test but scope it explicitly to a legacy sheet so it cannot double as sanction for the edit path.
- **fix_cost**: M
- **depends_on_finding**: [C-74, C-75, A-31]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-20 · No adapter-contract test: the discovery invariants are asserted per-adapter and inconsistently
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_discovery_bluesky.py:56-60`, `pipeline-app/tests/test_brightdata_job.py:97,127`, `pipeline-app/pipeline_app/discovery_engine.py:365`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: Six adapters, ~185 adapter tests, and no parametrized sweep over the registry asserting the contract CLAUDE.md and `brightdata_job.py` both state: `fetched_at` present and aware-UTC, `url` warned-on-absence, and a transport failure raising rather than returning `[]`. Each adapter's tests were written against that adapter's actual behavior, so the two that violate the contract (YouTube, Bluesky) have tests that agree with the violation. B-04 (YouTube writes `upload_date`, not `published`), B-98 (a third field name drops the date silently) and D-03 are all contract drifts a registry sweep would have failed on immediately.
- **trigger**: Adding a seventh adapter, or any adapter changing its failure mode.
- **proposed_fix**: One parametrized test module over `build_adapters()` asserting the frontmatter contract and the raise-on-failure invariant for every registered platform.
- **fix_cost**: M
- **depends_on_finding**: [D-03, B-70]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-21 · `test_save_kickoff_template_does_not_commit` pins a missing recovery path
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_routes_skills.py:54-68`, `pipeline-app/pipeline_app/routes/skills.py:90,94`
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: The test asserts `calls == []` — that a kickoff-template save makes no commit — with no stated rationale. Kickoff templates determine what every future turn of a stage is asked to do; the `SKILL.md` branch commits and this one does not, so a bad or empty save (A-51) is unrecoverable. A-52 (S1) is held in place by an assertion, which means fixing it presents as breaking a test.
- **trigger**: Adding the commit call to the kickoff-template branch.
- **proposed_fix**: Invert to `test_kickoff_template_save_is_committed_like_skill_md`, asserting a commit whose message names the stage.
- **fix_cost**: S
- **depends_on_finding**: [A-52]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-22 · `test_skill_provenance.py` guards one of 64 reference files under a name implying whole-set coverage
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `tests/test_skill_provenance.py:15`, `tests/test_skill_provenance.py:75-86`, `tests/test_skill_provenance.py:89-91`
- **component**: tests
- **failure_mode**: docs-drift
- **blast_radius**: All six tests target `shorts-styleboard/references/visual-registers.md` plus one substring check in that skill's `SKILL.md`. The marker assertion covers bullets between the `## 3. Register A` and `## 5. PLATE` split points — 13 lines. The filename promises enforcement of CLAUDE.md's anti-generic guarantee across the skill set; C-42 reports that half of all normative bullets carry no marker and the suite is green. Independently confirms C-48.
- **trigger**: Adding an unmarked normative line anywhere except that one section.
- **proposed_fix**: Widen the glob to every `references/*.md` under `.claude/skills/`, with an explicit, documented allowlist for files the guarantee does not cover.
- **fix_cost**: M
- **depends_on_finding**: [C-42, C-48]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-23 · `resolve_brief_version.main()` — the entry point ten skills invoke — is 23 uncovered statements
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/resolve_brief_version.py:68-91`, `docs/audit/appendix-F-tests.md:41`, `tests/test_resolve_brief_version.py:83`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: 64% coverage, the worst in either suite, and the uncovered block is the whole CLI surface: `--dir` defaulting to a CWD-relative path (C-96, S1 — a run from the wrong directory confidently proposes v1 over a live brief), `--date` interpolated without validation (C-99), and exit 1 overloaded across "no prior version" and "a brief is malformed" (C-100). Eleven of the 12 tests call the helpers directly; the twelfth shells out only to check path separators.
- **trigger**: Invoking the script from any directory other than the repo root.
- **proposed_fix**: Add CLI-level tests for a nonexistent `--dir`, a malformed `--date`, and the two distinct exit-1 conditions.
- **fix_cost**: S
- **depends_on_finding**: [C-96, C-99, C-100]
- **owner_task**: T14
- **detected_by**: coverage

### F-24 · `fetch_upload_dates` has no test at all — the function whose empty return drops every Short
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/discovery_youtube_api.py:182-214`, `pipeline-app/tests/test_discovery_youtube_api.py:112-190`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: 25 statements, never named in the 19-test file that covers its module. It exists so `enumerate_newest_first` can establish one global ordering across the `/videos` and `/shorts` tabs; with no API key it returns `{}` and the ordering collapses, silently dropping Shorts (SEED-8). The sibling `fetch_metadata`'s identical no-key `{}` return *is* tested — `test_fetch_metadata_returns_empty_without_key` — and that assertion is D-04's (S0) root cause stated as intended behavior.
- **trigger**: Running discovery with no `YOUTUBE_API_KEY`, or with quota exhausted.
- **proposed_fix**: Test the no-key path for both functions as a *reportable* condition rather than an empty result, and add an enumeration-level test asserting no Short is dropped when dates are unavailable.
- **fix_cost**: S
- **depends_on_finding**: [D-04]
- **owner_task**: T14
- **detected_by**: coverage

### F-25 · No property-based, mutation, or adversarial-input testing anywhere in either suite
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `requirements.txt`, `pipeline-app/requirements.txt` (no `hypothesis`, `mutmut`, or `cosmic-ray`); `tests/test_lint_prompt_sheet.py` (115 hand-written positive/negative pairs)
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: Every test in the repo is a hand-written example chosen by the same author, at the same time, with the same mental model as the code. That is precisely the regime in which "the implementation is a weaker predicate than the docstring" defects survive — C-82, C-83, C-84, C-87, C-90, C-91 (the anti-clone, density, no-list, world-lock and wpm checks all being satisfiable by trivially degenerate input) are six such findings in one module. A single mutation run over `lint_prompt_sheet.py` would surface C-79 and C-81 mechanically.
- **trigger**: Any check whose implementation is narrower than its intent. There are at least 17.
- **proposed_fix**: Add `hypothesis` for the two linters' check functions and run a one-off mutation pass over `lint_prompt_sheet.py`, treating each surviving mutant as a missing assertion.
- **fix_cost**: L
- **depends_on_finding**: [F-14]
- **owner_task**: T14
- **detected_by**: manual-trace

### F-26 · Two suites assert on the value they injected into a mock
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_main.py:15-30`, `pipeline-app/tests/test_turn_service.py:335-343`
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: `test_main.py`'s two tests monkeypatch `preflight.check_cli_available` and then assert `app.state.cli_available` equals the boolean they injected — a one-attribute round trip standing in for the app factory's 34 statements (DB init, router mounting, startup sweep, `pipeline.yaml` load failure all unexercised; `:56-57` uncovered). `test_scripting_turn_records_gate_results_in_frontmatter` mocks `run_gates_for_stage` to return a literal and asserts the literal reaches frontmatter — useful plumbing coverage filed under a name that reads as gate integration, with the gate as the mocked component.
- **trigger**: Reading either file to judge whether the module is covered.
- **proposed_fix**: Rename both to describe what they verify (`test_cli_availability_is_recorded_on_app_state`, `test_gate_results_are_copied_into_artifact_frontmatter`) and add real coverage of the app factory's failure paths.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T14
- **detected_by**: manual-trace

### F-27 · Test volume is inverted against consequence across the five thinnest suites
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_routes_doctor.py` (1), `test_main.py` (2), `test_git_helper.py` (2), `test_discovery_records.py` (2), `test_turn_service.py` (11)
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: `test_routes_doctor.py` asserts a 200 and one substring. `test_git_helper.py` asserts a commit exists but never *what* was committed — one `git show --stat` assertion would have caught D-49/A-53 (`commit_skill_edit` commits the entire index). `test_discovery_records.py` asserts counters against a literal it wrote, never that the totals reconcile (B-56). Meanwhile the six largest adapter suites hold 273 tests between them. The distribution tracks how mechanical a module is to test, not how much damage it can do.
- **trigger**: Any change to the git write path, the doctor surface, or run-record accounting.
- **proposed_fix**: Add one consequence-shaped assertion to each: what was committed; what Doctor uniquely reports; that handle-result totals sum to `handles_processed`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T14
- **detected_by**: manual-trace

### F-28 · `preflight._unwedge_stage`'s three defensive returns silently no-op and are untested
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/pipeline_app/preflight.py:28-35`, `pipeline-app/tests/test_preflight.py:24-58`
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: The six preflight tests cover the reconciliation happy paths only. The three early returns — stage row missing or not RUNNING, `stage_def` not in `pipeline.yaml`, project row missing — each return `None` with no log. A stage whose `stage_id` was renamed or removed from `pipeline.yaml` stays wedged at RUNNING across every restart, and the sweep reports nothing. A-76 (the sweep is per-process) and A-77 (orphan recovery is invisible to the operator) compound it.
- **trigger**: Renaming or removing a stage id from `pipeline.yaml` while a turn is running.
- **proposed_fix**: Test each early return, asserting both the no-op and that the condition is reported rather than swallowed.
- **fix_cost**: S
- **depends_on_finding**: [A-76, A-77]
- **owner_task**: T14
- **detected_by**: coverage

### F-29 · Appendix F §6 undercounts `test_turn_service.py` at 2 tests; it has 11
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `docs/audit/appendix-F-tests.md:120`, `docs/audit/appendix-F-tests.md:127-131`, `pipeline-app/tests/test_turn_service.py` (11 `def test_` functions)
- **component**: tests
- **failure_mode**: docs-drift
- **blast_radius**: T0's headline example of coverage/assertion decoupling rests on a wrong number. The conclusion survives — arguably strengthens, since 11 tests that never assert the module's output is a worse signal than 2 — but the figure is quoted in the appendix's most-cited paragraph and would not withstand a reader opening the file. The other four thin-suite counts (`test_main.py` 2, `test_git_helper.py` 2, `test_discovery_records.py` 2, `test_routes_doctor.py` 1) are correct.
- **trigger**: Any reader verifying the appendix's most memorable claim.
- **proposed_fix**: Correct the count to 11 in `appendix-F-tests.md` §6 and restate the point as "11 tests, all of the turn lifecycle, none of the handoff" (see §6 above).
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T14
- **detected_by**: manual-trace

### F-30 · Nothing runs the app suite by default, so a bare `pytest` hides 80% of the tests
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `docs/audit/appendix-F-tests.md:103`, `pytest.ini` (root, `testpaths = tests`), `pipeline-app/pytest.ini`
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: Recorded by T0 and handed to T15; restated here because it is the test-suite instance of the pattern this whole audit documents. `pytest` at the repo root prints "201 passed" and exits 0 while never running the 833-test app suite. Combined with F-10, a developer can make a change to `turn_service.py`, run `pytest`, see green, and have executed **zero** tests touching the file — and even the correct invocation would not have caught any of the six S1 defects in it.
- **trigger**: Running `pytest` with no arguments at the repo root.
- **proposed_fix**: Add a repo-root script or `tox`/`nox` target that runs both suites from their own rootdirs and fails if either does, so "the tests pass" has one unambiguous meaning.
- **fix_cost**: S
- **depends_on_finding**: [F-10]
- **owner_task**: T14
- **detected_by**: test-run

---

## T15 — Suite health & harness ergonomics

**Scope.** The machinery around the tests rather than the tests themselves: the two
`pytest.ini` files and the rootdir split they encode, the absent CI, the absent
`conftest.py`, the two dependency manifests plus `setup.py`, the three runner scripts,
the lone integration test, and the harness-level questions of isolation — shared temp
and DB state, module-global leakage, collection order, and whether any test can reach a
real network or a billed vendor API. Per-test assertion quality and the defect→test map
belong to T14 and are not repeated here. The pass/coverage baseline in
[`appendix-F-tests.md`](appendix-F-tests.md) §T0 is taken as given; neither suite was
re-run. Where new measurement was needed (module resolution, collection under the bare
`pytest` console script, warning provenance) it was done with `--collect-only` probes and
direct interpreter checks, never a full suite run. Findings **F-60 … F-80**.

---

### 1. Q1 — The no-CI consequence, and a minimum viable CI

`.github/` contains exactly one file: `PULL_REQUEST_TEMPLATE.md`. There is no
`workflows/` directory. **1,034 tests run only when a human remembers to run them, from
two different directories, with two different commands.**

**What that costs, concretely.** This audit found 286 defects. Every fix for them is a
change to code that 1,034 tests currently cover at 95% line coverage — and nothing will
re-run those tests except the author's memory. The specific regressions that go unnoticed:

- **A fix in `pipeline-app/` breaks the root linters, or vice versa.** Gate C lives in
  `scripts/lint_prompt_sheet.py` (root suite) and is *also* invoked by
  `pipeline_app/gates.py` (app suite). `pipeline-app/tests/test_gates.py:195` asserts the
  real fixture passes against the real `docs/style-library.md`. An author fixing a Gate C
  defect naturally runs the root suite, sees 201 green, and ships. The app-side half of
  the gate is never re-checked. Nothing tells them.
- **A dependency drifts underneath the suite.** `yt-dlp>=2025.1.1` floats in both
  manifests, and `test_discovery_youtube.py` pins yt-dlp's exact JSON field names
  (`upload_date`, `duration`). A yt-dlp release renaming a field breaks discovery in
  production; with no scheduled CI run, the first signal is an empty download.
- **Duration of exposure is unbounded.** There is no green-badge, no required check, no
  scheduled run. A regression introduced today is discovered whenever someone next runs
  both suites from both directories — which, given the bare-`pytest` trap (F-61), may be
  never. The realistic detection latency is *the next time a human notices wrong output in
  the app*, i.e. weeks, and via the worst possible channel.
- **The 286 fixes themselves are unverifiable as a set.** They will land across many
  sessions. Without a machine re-running both suites per change, "all 286 fixed and
  nothing else broken" is an assertion no one in this repo can currently produce evidence
  for.

**Does the PR template ask a human to do a machine's job?** Yes, and it is the single
clearest symptom. Its Verification section
(`.github/PULL_REQUEST_TEMPLATE.md:13-17`) reads, in full, a request for "What you
actually ran or checked to confirm this works (commands, output, manual walkthrough) —
not just an assertion." That is a well-intentioned instruction to *hand-transcribe test
output that a CI job would produce for free and more reliably*. It is worse than that in
two ways: it names no command, so it cannot tell the author that there are two suites and
two directories; and it accepts prose, so "ran the tests, green" satisfies it while
having run 201 of 1,034.

#### Minimum viable CI

One workflow file, `.github/workflows/tests.yml`, three jobs. Runner is
**`windows-latest`** deliberately: `cli_runner.platform_argv` shells through `cmd /c`,
`scripts/setup_discovery_task.py` drives Windows Task Scheduler, `start_pipeline.bat` is
the launcher, and three tests covering `kill_process_tree` — the most failure-prone code
in the repo — are `skipif(os.name != "nt")`. An Ubuntu runner would silently skip exactly
the coverage that matters most. Python pinned to **3.14**, the operator's interpreter.

Every command uses `python -m pytest`, never the bare `pytest` console script — see F-62
and F-63 for why that distinction is load-bearing rather than stylistic. `pipeline_app`
must **not** be installed (editable or otherwise) on the runner; `python -m`'s cwd
prepend is then the only source of the package, which guarantees the checkout is what
gets tested.

| Job | `working-directory` | Install | Test command |
|---|---|---|---|
| `root-suite` | `.` (repo root) | `python -m pip install -r requirements.txt pytest pytest-cov` | `python -m pytest tests/ --cov=scripts --cov-report=term-missing` |
| `app-suite` | `pipeline-app` | `python -m pip install -r requirements.txt pytest-cov` | `python -m pytest --cov=pipeline_app --cov-report=term-missing` |
| `no-live-credentials` | `pipeline-app` | same as `app-suite` | same command, with `BRIGHTDATA_API_KEY`, `RESEND_API_KEY`, `YOUTUBE_API_KEY` explicitly set to the empty string in the job `env:` |

`root-suite` needs `pytest` added on the install line because root `requirements.txt`
does not list it (F-74). All three jobs run on `pull_request` and on `push` to `main`; all
three are required checks. Add a `schedule:` weekly trigger so a floating `yt-dlp` or
`youtube-transcript-api` release surfaces on a Monday rather than in production.

The third job is the cheapest high-value one and is worth stating plainly: it re-runs the
app suite with the vendor credentials blanked. If the suite is green with no keys present,
no test depends on a live credential; if it ever goes red, a test has started reaching a
real vendor. That is a permanent, automatic version of the manual audit in §2 below —
directly guarding F-68.

Finally, the PR template's Verification section should be replaced with a checkbox
referencing the three job names, so a human is asked to *confirm the machine ran*, not to
substitute for it.

---

### 2. Q4 — Real network and real subprocess reach (the headline)

**No test in either suite currently makes an unmocked outbound HTTP call.** Every Bright
Data path (`_trigger_job` / `_poll_job_status` / `_fetch_job_results` in the Instagram, X,
Facebook and LinkedIn adapters), the Resend send in `discovery_notify`, the YouTube Data
API `urlopen`, the Bluesky fetch, the `yt-dlp` `subprocess.run`, and the `claude -p`
`Popen` in `comment_draft` are all monkeypatched at every call site, via per-file helpers
(`_fake_key`, `_enumerate_with`, `fake_claude`, `_no_spawn`). Several tests go further and
install a `_fail_if_called` stub that turns an unexpected vendor call into an
`AssertionError`. That is genuinely good work and it should be said clearly.

**But the guarantee is discipline, not structure, and the environment is armed.** Three
facts hold simultaneously:

1. `BRIGHTDATA_API_KEY`, `RESEND_API_KEY` and `YOUTUBE_API_KEY` are all **set in the
   developer's ambient environment** (verified this session). The test process inherits
   them.
2. `api_key()` reads the env var first, and the fallback `KEY_FILE` constants are anchored
   to the *real* repo — `Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"`
   — so pointing a test's `repo_root` at `tmp_path` does **not** move them.
3. `pipeline_app/routes/discovery.py:19` spawns `[sys.executable, run_discovery_cron.py,
   …]` as a real detached subprocess with `cwd=repo_root`, inheriting that environment and
   the real `ADAPTERS` registry. Nine tests in `test_routes_discovery.py` post to
   `/discovery/handles`, `/discovery/run-now` or `/discovery/run-now-backfill`; **each one
   stubs `subprocess.Popen` by hand**, and there is no `conftest.py` in which an autouse
   guard could live.

So: one new route test written without the hand-rolled `Popen` stub launches a real,
detached, **billed** Bright Data collection job — per record — and the test still passes,
because the spawn is fire-and-forget and nothing asserts on it. `_no_spawn`'s own
docstring (`test_routes_discovery.py:49-51`) names the risk exactly: "A validate run costs
a billable Bright Data job on the paid platforms, so tests must never let one launch."
The comment is right; the enforcement is nine independent copy-pastes. That is F-68.

**Real subprocesses that do execute** (all local, none networked, all legitimate):
`git init` / `git config` / `git log` against `tmp_path` in `test_git_helper.py:11-13`;
a `cmd.exe` shim spawning a real Python child in `test_cli_runner.py:400`, Windows-only,
which is the correct way to test process-tree kill; and
`python -m scripts.resolve_brief_version` in `tests/test_resolve_brief_version.py:89`.

---

### 3. Q2 — The two-rootdir split: workaround, not design

The split is documented in both `pytest.ini` headers and in CLAUDE.md, and the stated
reason is accurate as far as it goes: `pipeline-app/scripts/` and root `scripts/` are
**both** importable packages named `scripts`, so collecting the app suite from the repo
root shadows one with the other and four test modules raise `ModuleNotFoundError`.

But that is a description of a **packaging collision**, not a justification for two
rootdirs. The collision is the bug; the split is the workaround; and the workaround has
its own three failure modes, all newly measured here (F-61, F-62, F-63).

A real fix is small and mechanical: **give `pipeline-app/scripts/` a name that cannot
collide** — either move it to `pipeline_app/scripts/` (making it a subpackage of the
already-unique distribution package) or rename it `pipeline_app_scripts/`. Update the
three importing test files and the two `Popen`/argv call sites. Then one `pytest.ini` at
the repo root with `testpaths = tests pipeline-app/tests` runs all 1,034 tests from one
directory with one command, bare `pytest` and `python -m pytest` agree, the F-61 silent
subset disappears, and CI needs one job rather than two.

Worth it? Yes, and for a reason beyond tidiness: the split is what makes F-61 possible,
and F-61 is the most dangerous property of this harness — a green exit 0 that ran 19% of
the tests. Every other fix here (CI, conftest, the credential guard) is easier once there
is one suite. Cost is **M** and the change is confined to import lines. The one thing the
merge would *not* fix on its own is F-73: `pipeline-app/tests/test_gates.py` already reads
`<repo>/tests/fixtures/` and `<repo>/docs/style-library.md`, so the suites are not
independent today anyway — which is a further argument that the separation is nominal.

---

### 4. Q5 — Warning volume, and whether `-W error` is feasible

Measured this session by `--collect-only` (no suite run): **collection alone** emits
49,257 warnings, from exactly three source lines, all third-party, all the same root cause:

| Source | Count (collection only) |
|---|---|
| `pytest_asyncio/plugin.py:179` | 48,447 |
| `pytest_asyncio/plugin.py:450` | 786 |
| `fastapi/routing.py:233` | 24 |

All three are `DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated
for removal in Python 3.16`. `pytest-asyncio` is pinned to `0.24.*` (installed: 0.24.0), a
release that predates Python 3.13, let alone the 3.14.4 interpreter in use. The plugin
calls the deprecated function once per collected object per hook, which is why the count
is five-digit rather than three-digit.

**Is real signal hidden?** Yes, and the ratio is the finding: the repo's own signal is
`ResourceWarning: unclosed database` for at least four sqlite connections — traceable to
F-66, where only 2 of the 11 files that open a connection ever close it — and it is four
lines inside 58,169. No one will ever see it. Nothing in either `pytest.ini` sets
`filterwarnings`, so there is no mechanism by which a repo-owned warning could be promoted
above the noise.

**Is `-W error` feasible?** Not as-is: it fails during *collection*, before a single test
runs, on a third-party deprecation the repo cannot fix. It becomes feasible in one step,
and that step is the right fix anyway: add to both `pytest.ini` a `filterwarnings` block
that `ignore`s `DeprecationWarning` originating in `pytest_asyncio` and `fastapi` and
`error`s on everything else. What breaks first, in order: (1) the two `pytest_asyncio`
lines and the `fastapi` line — silenced by the ignore; (2) `ResourceWarning: unclosed
database`, which would then correctly fail the ≥4 tests leaking connections — that is the
point, and F-66 is the fix; (3) pytest-asyncio 0.24's own config deprecation for an unset
`asyncio_default_fixture_loop_scope`, which neither `pytest.ini` sets.

---

### 5. Q6 — The integration test

`pipeline-app/tests/integration/test_real_cli_e2e.py` is 41 lines and is not what its
name promises.

**What it requires:** `PIPELINE_APP_RUN_INTEGRATION=1`; a real `claude` binary on PATH; a
live Claude Code subscription (the skip reason says so); network; and several seconds to
minutes of real model latency. **What it asserts:** one thing —
`artifacts.latest_artifact_path(stage_dir) is not None`, i.e. *a file exists*. Not its
content, not its frontmatter, not its gate result, not the handoff. **What it covers:**
`STAGES = [StageDef(id="ideation", …)]` — **one** of nine stages. It is a single-stage
smoke test wearing an `e2e` filename.

**Has it ever run?** No evidence that it has. It is collected and skipped (T0 §4), there
is no CI, and the environment variable appears nowhere else in the repo. Two structural
details suggest it has not been exercised recently: it passes `REPO_ROOT` — the *real*
repo root — as `create_project`'s `repo_root`, so `project_service.py:35` creates
`<repo>/runs/integration-test-topic-<timestamp>/` **in the working tree** and nothing
cleans it up; and `turn_service.run_stage_turn` then runs the real CLI with `cli_runner`'s
allow-list, which includes `Write(rgs-briefs/**)` and `Edit(rgs-briefs/**)` against that
same real root. Only `db_path` is in `tmp_path`. A test that had been run regularly would
have accumulated visible `runs/` litter and someone would have narrowed the write scope.

**Cheapest stubbed-CLI version that could run in CI.** Appendix A's handoff defects are
precisely what an end-to-end walk catches and a unit test does not, so this is worth
building — and it needs no model, no network and no credentials:

- Put a fake `claude` on PATH for the job: a small script that reads the prompt on stdin,
  ignores it, and writes a canned, gate-passing artifact for whichever stage it was
  invoked for (the stage is derivable from the `cwd`/`--append-system-prompt` the runner
  already passes). `cli_runner`'s existing `platform_argv` indirection is the seam.
- Drive all nine stages in order through `turn_service.run_stage_turn`, with `repo_root`
  set to **`tmp_path`**, not the real repo.
- Assert per stage what `SKILL.md` declares required: that the prompt handed to the fake
  CLI actually contained each upstream artifact the stage depends on, and that the gate
  verdict recorded for the stage matches the one the CLI linter produces for the same
  file. That second assertion is the app-vs-CLI parity check that `test_gates.py:176` only
  spot-checks for C20.
- Runtime is milliseconds; cost is zero; it runs in the `app-suite` job with no special
  configuration. Keep the real-CLI test exactly as it is, opt-in, and rename it so its
  filename stops claiming e2e coverage the suite does not have.

---

### 6. Q7 — Dependency manifests and `setup.py`

| | root `requirements.txt` | `pipeline-app/requirements.txt` |
|---|---|---|
| Style | floating (`>=`) | wildcard-pinned (`==0.115.*`) — except two floating entries |
| Test deps | **none** | `pytest`, `pytest-asyncio`, `httpx` mixed in with runtime |
| Covers its own suite? | **No** — no `pytest` | Yes, except coverage tooling |

- **Used but unlisted.** Root: `pytest` (the suite cannot run from a clean
  `pip install -r requirements.txt`). Both: `pytest-cov` / `coverage`, which is how
  coverage came to have never been measured (T0/F-01). `pytest-xdist` 3.8.0 is installed
  in the environment and listed nowhere — harmless, but see F-67 for why running under it
  would be unsafe today.
- **Listed and used.** Everything else checks out: root `pyyaml` →
  `scripts/resolve_brief_version.py:18`; root `requests` → `download_thinkers.py:29`
  (lazy); root `youtube-transcript-api` → `download_brandintel.py:127` (lazy); app
  `markdown`, `jinja2`, `python-multipart` (`Form(...)` in three route modules), `tzdata`
  (`ZoneInfo` in three modules), `httpx` (only `fastapi.testclient` needs it — a test-only
  dep in a runtime manifest).
- **Inconsistent across the two files for the same library.** `pyyaml>=6.0` vs
  `pyyaml==6.0.*`; `requests>=2.31` vs `requests==2.31.*`. `yt-dlp>=2025.1.1` and
  `youtube-transcript-api>=1.0` float in *both*.
- **`setup.py`.** No `install_requires` at all, so `pip install -e pipeline-app` installs
  the package and none of its 13 dependencies; the two manifests are unlinked. Its
  `find_packages(include=["pipeline_app", "pipeline_app.*"])` also **excludes**
  `pipeline-app/scripts/` and the top-level module `run_discovery_cron.py` — both of which
  are imported by tests and one of which is spawned by a route. Those imports work only
  because `python -m pytest` prepends the cwd.
- **Installed vs relied-on-by-path.** `pipeline_app` *is* pip-installed, in editable mode,
  and this is a live hazard rather than a nicety — see F-63.

---

### 7. Q8 — Runner scripts

**`run_all.sh`** — the best of the three. `set -euo pipefail` at line 11, absolute
`HERE`/`cd`, `"$@"` forwarding, and the only unchecked pipeline is the closing `find | awk
| uniq -c || true` summary, which is deliberate. Its problem is not exit codes but
sequencing: step 2 of 3 is `bash copy_youthsports.sh`, which by design exits 1 in this
repo (its source tree is a sibling checkout that does not exist here — README:38-41 calls
the script "dead weight here"). Under `set -e` that aborts the run **before** step 3, the
brand-intel download, which is the only step CLAUDE.md's FamilyBrain-firewall clause
points at for refreshing the corpus. The README's own Quick start advertises `./run_all.sh`
as "everything." It cannot complete. (F-77)

**`copy_youthsports.sh`** — correct in isolation: `set -euo pipefail`, an explicit
existence check on `$SRC`, a clear two-line stderr message and `exit 1`. Its only blemish
is that `cp -R "$SRC"/. "$DEST"/` merges into an existing destination without clearing it,
so a file deleted upstream survives forever in `output/`.

**`start_pipeline.bat`** — **checks nothing.** Six lines, zero error handling:
- `call .venv\Scripts\activate.bat` with no prior `if exist` test. On a machine without
  the venv, `call` fails, `errorlevel` is set, nothing reads it, and the script proceeds to
  launch `uvicorn` from whatever is on the global PATH — or from nothing.
- `start … cmd /k uvicorn …` is the one good decision: `/k` keeps the child window open,
  so a uvicorn traceback survives long enough to read. It does not "open a window that
  closes instantly."
- But the parent does not care whether the child came up. It sleeps a fixed
  `timeout /t 3` and unconditionally `start ""`s the browser at
  `http://127.0.0.1:8420`. On a crash the user's foreground signal is a browser
  connection error, not the traceback sitting in a background window. On a cold start,
  3 seconds is a race.
- Port 8420 is hardcoded with no bind check. Launch it twice and the second uvicorn dies
  in its own window while the browser opens onto the **first**, still-running instance —
  possibly against a different database. The operator sees a working app and concludes
  the launch succeeded. (F-78)

---

### 8. Findings

### F-60 · No CI exists: 1,034 tests run only when a human remembers, from two directories
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `.github/PULL_REQUEST_TEMPLATE.md` (the only file under `.github/`), `pytest.ini:9`, `pipeline-app/pytest.ini:8`
- **component**: infra
- **failure_mode**: latent
- **blast_radius**: Every one of the 286 defects this audit found will be fixed across many sessions with no machine re-running either suite. A cross-suite regression (Gate C is exercised by both) or a floating-dependency break is discovered only when someone notices wrong output in the running app — weeks later, through the worst channel.
- **trigger**: Any commit. There is no event that causes the tests to run.
- **proposed_fix**: Add one `windows-latest` workflow with the three jobs specified in §1: `root-suite`, `app-suite`, and `no-live-credentials`, all invoked with `python -m pytest`, all required checks, plus a weekly `schedule:` trigger for the floating vendor pins.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T15
- **detected_by**: manual-trace

### F-61 · Bare `pytest` at repo root: 201 passed, exit 0, 833 app tests silently omitted
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pytest.ini:9` (`testpaths = tests`), `appendix-F-tests.md` §T0.5
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: The most dangerous property of this harness. A developer who types the most natural possible command at the repo root gets an unambiguous green result that exercised 19% of the tests, with nothing in the output indicating an omission. Every app-side regression is invisible to that developer.
- **trigger**: Running `pytest` (or `python -m pytest`) with no arguments at the repo root.
- **proposed_fix**: Remove the possibility rather than document it — merge the suites per F-64 so `testpaths` can name both trees. Until then, the root `pytest.ini` should carry a header stating in the first line that a bare run covers the root suite only, and CI must invoke both suites explicitly.
- **fix_cost**: S
- **depends_on_finding**: [F-64]
- **owner_task**: T15
- **detected_by**: test-run

### F-62 · CLAUDE.md's "bare `pytest` does the right thing in both places" is false for the app suite
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `CLAUDE.md` (Conventions → tests: "A `pytest.ini` at each level pins the rootdir so a bare `pytest` does the right thing in both places"); measured: bare `pytest` in `pipeline-app/` → 786 collected, 4 collection errors, `ModuleNotFoundError: No module named 'scripts'`, interrupted
- **component**: infra
- **failure_mode**: docs-drift
- **blast_radius**: A developer following CLAUDE.md verbatim hits four collection errors and reasonably concludes the repo is broken. The real requirement is `python -m pytest` specifically — the `-m` form prepends the cwd to `sys.path`, the console script does not, and `pipeline-app/tests/` has no `__init__.py` so pytest inserts only `pipeline-app/tests`.
- **trigger**: Running `pytest` rather than `python -m pytest` from `pipeline-app/`.
- **proposed_fix**: Correct the CLAUDE.md sentence to state that `python -m pytest` is required, not optional, and say why in one clause. The durable fix is F-64.
- **fix_cost**: S
- **depends_on_finding**: [F-64]
- **owner_task**: T15
- **detected_by**: test-run

### F-63 · `pipeline_app` is installed editable against the MAIN checkout; a worktree can test the wrong tree
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pip freeze` → `-e git+…#egg=pipeline_app&subdirectory=pipeline-app`; `importlib.util.find_spec('pipeline_app')` → `C:\Projects\ContentStudio\pipeline-app\pipeline_app\__init__.py`; bare `pytest <worktree>/pipeline-app/tests/test_db.py` run from an unrelated cwd collected 34 tests successfully
- **component**: infra
- **failure_mode**: silent
- **blast_radius**: Any pytest invocation that does not put the working tree first on `sys.path` imports the *main checkout's* `pipeline_app`, not the branch under test. Tests then pass or fail against code the author is not editing. This audit itself runs in a worktree, and `python -m pytest` from `pipeline-app/` is the only invocation that happens to be safe.
- **trigger**: Bare `pytest`, or any invocation from a directory other than `pipeline-app/`, in a worktree or second checkout.
- **proposed_fix**: Uninstall the editable `pipeline_app` from the development environment and rely on the cwd prepend, or reinstall it per-worktree. CI must never install it, so that `python -m`'s cwd prepend is the sole source of the package.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T15
- **detected_by**: manual-trace

### F-64 · The two-rootdir split is a workaround for a `scripts` package-name collision
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/__init__.py`, `pipeline-app/scripts/__init__.py`, `pytest.ini:1-7`, `pipeline-app/pytest.ini:1-6`, `pipeline-app/setup.py:5`
- **component**: infra
- **failure_mode**: latent
- **blast_radius**: Two identically-named importable packages force two rootdirs, two commands, two CI jobs, and three downstream defects (F-61, F-62, F-63). `setup.py`'s `find_packages(include=["pipeline_app", "pipeline_app.*"])` also excludes `pipeline-app/scripts/` and `run_discovery_cron.py` entirely, so nothing about the arrangement is installable.
- **trigger**: Collecting the app suite from the repo root; four modules raise `ModuleNotFoundError`.
- **proposed_fix**: Rename `pipeline-app/scripts/` to a non-colliding name — ideally `pipeline_app/scripts/`, making it a subpackage of the already-unique distribution — and update the three importing tests plus the route/argv call sites. Then a single root `pytest.ini` with `testpaths = tests pipeline-app/tests` runs everything from one directory.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T15
- **detected_by**: manual-trace

### F-65 · No `conftest.py` anywhere: the DB fixture is duplicated 11 times, the FastAPI client 9 times
- **severity**: S2
- **confidence**: confirmed
- **evidence**: no `conftest.py` in the repo; `def conn(` in `test_approval_service.py:39`, `test_browse_service.py:398`, `test_db.py:10`, `test_migrate_handles.py:11`, `test_migrations.py:32`, `test_preflight.py:12`, `test_project_service.py:18`, `test_turn_service.py:21`; `def client(` in `test_header.py:10`, `test_routes_approve_edit.py:26`, `test_routes_browse.py:11`, `test_routes_chat_sse.py:12`, `test_routes_discovery.py:10`, `test_routes_inspector.py:10`, `test_routes_projects.py:11`, `test_routes_skills.py:11`, `test_routes_stages.py:14`
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: The `tmp_path / "pipeline.db"` + `parents[1] / "pipeline_app" / "schema.sql"` + `init_db` idiom appears in 11 files and the `chdir` + `pipeline.yaml` + `create_app` + `TestClient` idiom in 9, each free to drift. More importantly there is no place to put a repo-wide autouse guard — which is precisely why F-68's billed-API protection has to be nine hand-written copies, and why the module-global leakage in F-67 has no reset hook.
- **trigger**: Any schema, `create_app` signature, or safety-invariant change; each must be found and applied in 9–11 places.
- **proposed_fix**: Add `pipeline-app/tests/conftest.py` holding the shared `conn` and `client` fixtures, an autouse fixture clearing the adapter module globals, and an autouse guard that makes `subprocess.Popen` raise unless a test explicitly opts in.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T15
- **detected_by**: grep-sweep

### F-66 · Only 2 of 11 files close their sqlite connection; the rest leak into `ResourceWarning`
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `conn.close()` appears only in `test_db.py` (×2) and `test_discovery_notify.py` (×1); `test_discovery_engine.py:223-228` and `test_discovery_notify.py:71-75` use the correct `yield`/`close` shape, the other 9 `conn` fixtures return without closing
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: Produces the `ResourceWarning: unclosed database` lines that are the suite's only repo-owned warning signal — currently invisible inside 58,169 warnings (F-70). On Windows an unclosed handle can also keep a `tmp_path` file locked, which makes teardown failures platform-dependent and intermittent.
- **trigger**: Any test using one of the 9 non-closing `conn` fixtures; the warning is emitted at GC, not deterministically.
- **proposed_fix**: Move the connection fixture into `conftest.py` (F-65) in `yield` form with an unconditional `close()` in teardown, matching the two files that already do it correctly.
- **fix_cost**: S
- **depends_on_finding**: [F-65]
- **owner_task**: T15
- **detected_by**: grep-sweep

### F-67 · Module-global adapter caches and a once-only warn flag are never reset between tests
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline_app/discovery_instagram.py:215`, `discovery_facebook.py:212`, `discovery_x.py:222` (`_ENUMERATE_CACHE`); `discovery_youtube.py:173` (`_TRANSCRIPT_API_MISSING_WARNED`); asserted directly at `test_discovery_instagram.py:327,335-336`, `test_discovery_facebook.py:386,394-395,406,418`, `test_discovery_x.py:453,463,493`; hand-reset at `test_discovery_youtube.py:348,375`
- **component**: tests
- **failure_mode**: latent
- **blast_radius**: Eleven assertions read process-global dictionaries that no fixture clears; the suite passes only because each file happens to use distinct handle names and each `enumerate_newest_first` overwrites its own key. `_TRANSCRIPT_API_MISSING_WARNED` is a genuine order dependency, acknowledged by two tests that reset it inline — a third test asserting that warning would pass or fail depending on collection order. `pytest-xdist` is installed in the environment; running `-n auto`, or any `-k` / `--lf` subset, redistributes files across processes and changes which globals are warm.
- **trigger**: Running a subset (`-k`, `--lf`, `--sw`), reordering, or parallelising with the already-installed `pytest-xdist`.
- **proposed_fix**: Add an autouse `conftest.py` fixture that clears the three `_ENUMERATE_CACHE` dicts and resets `_TRANSCRIPT_API_MISSING_WARNED` before every test, and delete the two inline resets it makes redundant.
- **fix_cost**: S
- **depends_on_finding**: [F-65]
- **owner_task**: T15
- **detected_by**: grep-sweep

### F-68 · The suite can spawn a real, billed Bright Data run; the only guard is nine hand-written stubs
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `pipeline_app/routes/discovery.py:19-22` (detached `subprocess.Popen` of `run_discovery_cron.py`, inheriting env); `pipeline-app/tests/test_routes_discovery.py:35,53,128,142,155,168,179` (seven separate hand-rolled `Popen` stubs) and `:49-51` (the docstring naming the cost); `BRIGHTDATA_API_KEY`, `RESEND_API_KEY`, `YOUTUBE_API_KEY` all verified SET in the ambient environment
- **component**: tests
- **failure_mode**: latent
- **blast_radius**: Bright Data is billed per record. One new route test that posts a handle or hits `/discovery/run-now` without remembering the `Popen` stub launches a real detached collection job against live credentials — and passes, because the spawn is fire-and-forget and nothing asserts on it. The bill is the only signal, days later. No `conftest.py` exists in which a repo-wide guard could live (F-65).
- **trigger**: Any future test that exercises a `/discovery/*` POST route and omits the manual `subprocess.Popen` monkeypatch.
- **proposed_fix**: Add an autouse `conftest.py` fixture that replaces `subprocess.Popen` (and `asyncio.create_subprocess_exec`) with a raising stub, requiring tests to opt in explicitly via a marker or an override fixture. Reinforce with the `no-live-credentials` CI job from §1, which runs the suite with the three vendor keys blanked.
- **fix_cost**: S
- **depends_on_finding**: [F-65]
- **owner_task**: T15
- **detected_by**: manual-trace

### F-69 · Vendor `KEY_FILE` constants are anchored to the real repo, so `tmp_path` does not isolate credentials
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline_app/discovery_instagram.py:38`, `discovery_facebook.py:32`, `discovery_linkedin.py:32`, `discovery_x.py:35`, `discovery_notify.py:31`, `discovery_youtube_api.py:41` — all `Path(__file__).resolve().parent.parent / "<vendor>_api_key.txt"`
- **component**: tests
- **failure_mode**: latent
- **blast_radius**: Tests isolate state by passing `repo_root=tmp_path`, which is otherwise thorough — but the key lookup ignores `repo_root` entirely, reading the process environment first and a real-repo file second. A test can therefore be fully "sandboxed" by its own `repo_root` and still hold a live production credential. Six tests monkeypatch `KEY_FILE` individually to work around this; nothing enforces it.
- **trigger**: Any code path reaching `api_key()` without an explicit `KEY_FILE` or `api_key` monkeypatch, in an environment where the env var is set.
- **proposed_fix**: Thread `repo_root` through `api_key()` so key resolution honours the same root everything else does, and add a `conftest.py` autouse fixture that deletes the three vendor env vars for the whole suite.
- **fix_cost**: M
- **depends_on_finding**: [F-65, F-68]
- **owner_task**: T15
- **detected_by**: grep-sweep

### F-70 · 58,169 warnings from three third-party lines bury the suite's only real warning signal
- **severity**: S3
- **confidence**: confirmed
- **evidence**: measured at collection only — `pytest_asyncio/plugin.py:179` 48,447 · `pytest_asyncio/plugin.py:450` 786 · `fastapi/routing.py:233` 24, all `DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated`; neither `pytest.ini` sets `filterwarnings`
- **component**: tests
- **failure_mode**: silent
- **blast_radius**: The repo's own signal — `ResourceWarning: unclosed database` for ≥4 connections (F-66) — is four lines inside 58,169 and will never be read. Any future warning the code itself starts emitting (a deprecation in sqlite3, a `DeprecationWarning` the app introduces) is equally invisible. `-W error` is unusable as-is: it fails during collection on a third-party line before a single test runs.
- **trigger**: Every run of the app suite.
- **proposed_fix**: Add `filterwarnings` to both `pytest.ini` files: `ignore` `DeprecationWarning` scoped to `pytest_asyncio` and `fastapi`, `error` on everything else. Expect the ≥4 connection-leaking tests to fail immediately — that is the intended outcome, fixed by F-66.
- **fix_cost**: S
- **depends_on_finding**: [F-66, F-71]
- **owner_task**: T15
- **detected_by**: test-run

### F-71 · `pytest-asyncio` pinned to 0.24 against Python 3.14, with no `asyncio_mode` or loop-scope set
- **severity**: S3
- **confidence**: probable
- **evidence**: `pipeline-app/requirements.txt:8` (`pytest-asyncio==0.24.*`); installed `pytest-asyncio 0.24.0` on CPython 3.14.4; neither `pytest.ini` sets `asyncio_mode` or `asyncio_default_fixture_loop_scope`
- **component**: infra
- **failure_mode**: latent
- **blast_radius**: 0.24 predates Python 3.13, let alone 3.14, and is the sole source of 49,233 of the warnings in F-70. `asyncio.iscoroutinefunction` is scheduled for *removal* in 3.16, at which point the pinned plugin stops working entirely rather than warning. The unset `asyncio_default_fixture_loop_scope` is itself a 0.24 deprecation whose default changes in a later release, so an unpinned upgrade could silently alter event-loop sharing across the suite's async tests.
- **trigger**: Upgrading to Python 3.16, or relaxing the `pytest-asyncio` pin without setting the loop scope explicitly.
- **proposed_fix**: Upgrade `pytest-asyncio` to a release that supports the interpreter in use, and set `asyncio_mode` and `asyncio_default_fixture_loop_scope` explicitly in `pipeline-app/pytest.ini` so the upgrade cannot change semantics implicitly.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T15
- **detected_by**: manual-trace

### F-72 · The "e2e" test covers 1 of 9 stages, asserts only that a file exists, and writes into the real repo
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/integration/test_real_cli_e2e.py:18` (`STAGES = [StageDef(id="ideation", …)]`), `:28` (`create_project(conn, REPO_ROOT, …)` — the real root, not `tmp_path`), `:39` (`assert latest is not None`); `pipeline_app/project_service.py:35` (`run_dir = repo_root / "runs" / run_id`)
- **component**: tests
- **failure_mode**: coverage-gap
- **blast_radius**: The repo's only integration test is a single-stage smoke test with the weakest possible assertion, and it is also the most expensive test to run. Appendix A's handoff defects — a stage not receiving an artifact its `SKILL.md` declares required — are exactly what a nine-stage walk catches and unit tests do not, and nothing in the repo performs that walk. When enabled it creates `<repo>/runs/integration-test-topic-<timestamp>/` in the working tree, never cleaned up, and runs a real CLI holding `Write(rgs-briefs/**)` against the real root.
- **trigger**: Never, in practice — it is opt-in, off by default, and there is no CI to enable it.
- **proposed_fix**: Add a stubbed-CLI sibling that walks all nine stages with `repo_root=tmp_path` and a fake `claude` on PATH, asserting per stage that the prompt contained every declared upstream artifact and that the recorded gate verdict matches the CLI linter's for the same file. Keep the real-CLI test opt-in but pass it `tmp_path` as `repo_root`, and rename it so its filename stops claiming e2e coverage.
- **fix_cost**: M
- **depends_on_finding**: [F-03]
- **owner_task**: T15
- **detected_by**: manual-trace

### F-73 · The app suite reads repo-root files outside `pipeline-app/`, so the two suites are not independent
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/tests/test_gates.py:7` (`REPO_ROOT = parents[2]`), `:111` (`FIXTURES = REPO_ROOT / "tests" / "fixtures"`), `:176-202` (resolves labels against the real `docs/style-library.md`)
- **component**: tests
- **failure_mode**: latent
- **blast_radius**: Undercuts the stated rationale for the rootdir split: the app suite cannot run from a standalone `pipeline-app/` checkout, and editing `docs/style-library.md` — a documentation file no one associates with the app suite — breaks app tests. It also means an author who fixes a Gate C defect and runs only the root suite has changed inputs the app suite depends on without re-running it.
- **trigger**: Renaming a Style Library entry, moving `tests/fixtures/`, or attempting to run the app suite in isolation.
- **proposed_fix**: Accept the coupling and make it explicit — merging the suites per F-64 removes the contradiction entirely. Failing that, note in `pipeline-app/pytest.ini`'s header that the app suite reads two repo-root paths and is not independently relocatable.
- **fix_cost**: S
- **depends_on_finding**: [F-64]
- **owner_task**: T15
- **detected_by**: manual-trace

### F-74 · Root `requirements.txt` omits `pytest`; neither manifest lists coverage tooling
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `requirements.txt` (4 entries: `requests`, `yt-dlp`, `youtube-transcript-api`, `pyyaml` — no `pytest`); `pipeline-app/requirements.txt` (no `pytest-cov`, no `coverage`)
- **component**: infra
- **failure_mode**: coverage-gap
- **blast_radius**: A clean environment provisioned from root `requirements.txt` cannot run the root suite at all — which is also what CI would hit on its first run. Missing `pytest-cov` in both files is the mechanical reason coverage had never been measured on this repo before this audit (F-01).
- **trigger**: Provisioning a fresh environment, or standing up the CI runner in §1.
- **proposed_fix**: Add `pytest` and `pytest-cov` to root `requirements.txt`, add `pytest-cov` to the app manifest, and split test-only dependencies (`pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`) into a `requirements-dev.txt` at each level so the runtime manifests describe runtime only.
- **fix_cost**: S
- **depends_on_finding**: [F-01]
- **owner_task**: T15
- **detected_by**: manual-trace

### F-75 · `setup.py` has no `install_requires` and excludes two things the tests import
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/setup.py:3-8` (no `install_requires`; `find_packages(include=["pipeline_app", "pipeline_app.*"])`); `pipeline-app/scripts/` and `pipeline-app/run_discovery_cron.py` are outside that include; imported at `tests/test_run_discovery_cron.py:7`, `tests/test_migrate_handles.py`, `tests/test_setup_discovery_task.py:25`, `tests/test_backfill_youtube_frontmatter.py`
- **component**: infra
- **failure_mode**: latent
- **blast_radius**: `pip install -e pipeline-app` installs the package and none of its 13 dependencies, so the only real manifest is `requirements.txt` and the two are unlinked and free to drift. The excluded `scripts` package and `run_discovery_cron` module are importable only because `python -m pytest` prepends the cwd — the same fragile mechanism behind F-62 and F-63. Constraint style is also split for the same libraries: `pyyaml>=6.0` vs `pyyaml==6.0.*`, `requests>=2.31` vs `requests==2.31.*`.
- **trigger**: Installing the package and expecting it to work, or expecting the two manifests to agree.
- **proposed_fix**: Give `setup.py` an `install_requires` generated from `pipeline-app/requirements.txt` (or move to a `pyproject.toml` with a single dependency list), and bring `scripts`/`run_discovery_cron` inside the distribution as part of the F-64 rename.
- **fix_cost**: M
- **depends_on_finding**: [F-64]
- **owner_task**: T15
- **detected_by**: manual-trace

### F-76 · `yt-dlp` floats in both manifests while tests pin its exact JSON schema
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `requirements.txt` and `pipeline-app/requirements.txt` both `yt-dlp>=2025.1.1` and `youtube-transcript-api>=1.0` (installed: `yt-dlp 2026.7.4`, `youtube-transcript-api 1.2.4`); `pipeline-app/tests/test_discovery_youtube.py:249,309` pin `upload_date` and `duration` field names
- **component**: infra
- **failure_mode**: silent
- **blast_radius**: yt-dlp ships frequently and changes its `--dump-json` output. A field rename breaks YouTube discovery in production — and, with no CI and no scheduled run, the first signal is a quiet run reporting `no_new_content`, which is indistinguishable from a genuinely quiet day. The tests that would catch it are all mocked against a frozen schema, so they stay green.
- **trigger**: A yt-dlp or youtube-transcript-api release that renames or removes a consumed field.
- **proposed_fix**: Pin both to exact versions and add the weekly scheduled CI run from §1 so an upgrade surfaces as a deliberate, reviewed bump rather than an ambient one. A contract test that runs the real `yt-dlp --dump-json` against a known public video would close the mock-vs-reality gap, but belongs behind an opt-in marker.
- **fix_cost**: S
- **depends_on_finding**: [F-60]
- **owner_task**: T15
- **detected_by**: manual-trace

### F-77 · `run_all.sh` — the README's documented entry point — cannot complete in this repo
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `run_all.sh:11` (`set -euo pipefail`), `run_all.sh` step 2/3 (`bash copy_youthsports.sh`); `copy_youthsports.sh:12-20` (exits 1 when `$SRC` is absent); `README.md:38-41` ("not runnable standalone in this repo … the script itself is dead weight here"); `README.md:58` advertises `./run_all.sh # everything`; verified `corpus/raisinggoodsports/` exists neither as a sibling of this repo nor of the main checkout
- **component**: infra
- **failure_mode**: loud
- **blast_radius**: `set -e` aborts on step 2, so step 3 — the brand-intel download — never runs. That step is the only corpus-refresh path CLAUDE.md's FamilyBrain-firewall clause points at ("re-run the toolkit scripts at repo root against the public web"). The README simultaneously documents the script as dead weight and as the "everything" quick start. The failure is loud and legible; the defect is that the documented happy path is unreachable.
- **trigger**: Running `./run_all.sh` as the README's Quick start instructs.
- **proposed_fix**: Make step 2 non-fatal — detect the absent source and skip with a notice rather than aborting the run — or drop it from `run_all.sh` and leave `copy_youthsports.sh` as a standalone script, reconciling the README's Quick start with its own scope note either way.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T15
- **detected_by**: manual-trace

### F-78 · `start_pipeline.bat` checks no exit code: a missing venv, a bound port, or a crash all still open the browser
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `pipeline-app/start_pipeline.bat:3` (`call .venv\Scripts\activate.bat`, no `if exist`, no `errorlevel` check), `:4` (`start … cmd /k uvicorn … --port 8420`, no bind check), `:5-6` (fixed `timeout /t 3` then unconditional `start "" http://127.0.0.1:8420`)
- **component**: infra
- **failure_mode**: silent
- **blast_radius**: The `cmd /k` is correct — a uvicorn traceback does survive in the child window, so this is not the classic instantly-closing-window bug. The failure is subtler: the parent never learns whether startup succeeded, so on a missing venv or a crash the operator's foreground signal is a browser connection error while the real message sits in a background window. Worse, launching twice opens the browser onto the **first**, still-running instance — possibly against a different database — while the second dies silently. The operator sees a working app and concludes the launch worked.
- **trigger**: Launching without the venv provisioned, launching twice, or any uvicorn startup failure.
- **proposed_fix**: Gate on `if not exist .venv\Scripts\activate.bat` with an explicit message and non-zero exit; check the port is free before starting and refuse rather than double-launching; poll `http://127.0.0.1:8420` until it answers (with a timeout) instead of sleeping a fixed 3 seconds, and only then open the browser.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T15
- **detected_by**: manual-trace

### F-79 · Coverage artifacts are untracked and not gitignored
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.gitignore` (no `.coverage`, no `htmlcov/`, no `.pytest_cache/`); `git status --porcelain` → `?? .coverage`, `?? pipeline-app/.coverage`
- **component**: infra
- **failure_mode**: docs-drift
- **blast_radius**: Two binary files appear as untracked noise in every `git status` after a coverage run and can be swept into a commit by `git add -A`. Minor, but it becomes routine the moment F-74 makes `pytest-cov` a standard dependency.
- **trigger**: Running either suite with `--cov`, then `git add -A`.
- **proposed_fix**: Add `.coverage`, `.coverage.*`, `htmlcov/` and `coverage.xml` to `.gitignore`, alongside the existing `__pycache__/` entries.
- **fix_cost**: S
- **depends_on_finding**: [F-74]
- **owner_task**: T15
- **detected_by**: grep-sweep

### F-80 · The PR template asks a human to hand-transcribe verification a machine should produce
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.github/PULL_REQUEST_TEMPLATE.md:13-17` (Verification: free-text, "not just an assertion"); no `.github/workflows/`
- **component**: infra
- **failure_mode**: docs-drift
- **blast_radius**: The template names no command, so it cannot tell an author there are two suites in two directories — and it accepts prose, so "ran the tests, green" satisfies it while having run 201 of 1,034 (F-61). It is the repo's only quality gate and it substitutes human memory for a check a machine would perform identically every time.
- **trigger**: Every pull request.
- **proposed_fix**: Once the §1 workflow exists, replace the free-text Verification box with checkboxes naming the three required job names, so the human confirms the machine ran rather than standing in for it. Keep a free-text field only for manual walkthroughs no job can perform.
- **fix_cost**: S
- **depends_on_finding**: [F-60]
- **owner_task**: T15
- **detected_by**: manual-trace
