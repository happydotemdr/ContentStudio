# Resume prompt — audit-remediation programme, start P6 (Wave B4, first of four)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-16. **P5 (Skill editor & git) is merged into `main`**
([PR #39](https://github.com/happydotemdr/ContentStudio/pull/39), merge commit `0180b4e`).
Combined with P0, P1, P2, P3, P4, P10, P11, P12 already in `main`, **Wave B3 (P4, then P5) is
done. Wave B4 is next — start P6 now.**

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
P6 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

**Start P6 in a fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not
reuse P5's worktree/branch (`worktree-pipeline-audit-p5`), which is now fully merged and should be
left alone (its own PR is closed; its SDD workspace has been deleted, its git history survives in
`main`'s log). `origin/main` at merge commit `0180b4e` already contains every fix P5 landed.

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed
editable) may have uncommitted operator work in progress — re-run the fetch+status check yourself
at the start of your session (`cd C:\Projects\ContentStudio && git fetch origin main && git status
--short && git log --oneline -3`) to see its current state before assuming anything about it; **do
not `git pull`/`merge`/`reset` there yourself** — ask the operator rather than acting on it. Note:
from inside a worktree-isolated session, you cannot `cd` out to the main checkout at all (the
harness refuses it) — if you need to inspect main-checkout state, ask the operator to run the
check, or accept you cannot verify it directly this session.

**Baseline suite counts, verified this session at `origin/main`'s `0180b4e` (P5 merged):**
- Root suite (`python -m pytest tests/ -q` from repo root): **445 passed, 1 failed, 1 skipped** —
  the same documented, deliberately-deferred pre-existing exception as every prior session
  (`test_lint_prompt_sheet.py::test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[fenced-heading]`,
  unowned by P5 or P6). Re-verify the count yourself rather than trusting this as gospel — it has
  fluctuated by ±1 across sessions for reasons not yet diagnosed.
- App suite (`cd pipeline-app && python -m pytest -q`): **31 failed, 1374 passed, 4 skipped.** All
  31 failures are the SAME pre-existing failures every resume prompt since P3 has documented (by
  test name, not just count) — `write_pointer()` missing a required `repo_root` argument in test
  setup code across `test_approval_service.py` (6), `test_browse_service.py` (12),
  `test_discovery_digest.py` (2), `test_routes_browse.py` (7), `test_routes_stages.py` (3), plus one
  unrelated `AttributeError` on a removed `grounding_service.identify_new_brief` function in
  `tests/integration/test_stubbed_cli_e2e.py` (1). **P6 does not own or need to fix these.** The
  passed count (1374) is higher than P5's own final count (1328 pre-P5) purely because P5's own 19
  landed tasks added their own regression tests — not because anything outside the remediation
  programme changed this time (contrast with the P4→P5 handoff, where PR #36's unrelated work also
  inflated the count). **One genuinely flaky, order-dependent failure was observed and ruled out
  this session**: `test_turn_service.py::test_one_malformed_dependent_does_not_abort_the_staleness_
  cascade` failed once in a full-suite run (32 failed, 1373 passed) and passed cleanly both in
  isolation and on two immediate full-suite re-runs (back to 31/1374). Not in P6's files, not
  reproducible, not added to the documented baseline — noted here so a future session that hits it
  again doesn't waste a round chasing a phantom regression. If it starts failing consistently,
  that's a different, real signal.
- CI (`gh run list --branch main --limit 5`): **still not green** — same standing gap, see
  "Definition of done" below. Re-run yourself, don't trust this note.

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | **merged** |
| B1 | P2, then P10 | **merged** |
| B2 | P3 + P11 + P12 together | **merged** |
| B3 | P4, then P5 | **merged** |
| B4 | **P6**, P7, then P8, and P9 | **P6 has not started — start it now.** |
| B5 | P15 | not started |
| C | P13, then P14 | not started |

**Why P6 is next, precisely:** the master plan's wave table
(`docs/superpowers/plans/2026-08-08-audit-remediation.md`, search "Wave B4") puts P6/P7/P8/P9 in
one wave, with a real ordering constraint inside it: *"P8 consumes seams from P6 (`BlueskyFetchError`
reaching the engine) and P7 (`drain_diagnostics`, `preflight`), so land P6 and P7 before P8; P9 is
independent."* Nothing in the master plan requires P6 before P7 specifically (they don't share
files — file-exclusivity was verified across all 16 packages), but this programme has executed one
package per session throughout, so the recommended order for this wave is **P6, then P7, then P8,
then P9** (P9 could in principle move earlier since it has no dependency, but there is no reason to
reorder — keep it last and simple). Confirm this reasoning still holds by re-reading the master
plan's wave table yourself before committing to the order — "verify, don't inherit" applies to this
resume prompt's own claims too.

**Unlike P4→P5, there is no cross-package contract handoff gating P6.** P6 is not blocked on
anything from P5 or earlier waves. Its own plan file is self-contained.

## What P6 is — read `docs/superpowers/plans/remediation/P6-native-adapters.md` in full before dispatching Task 1

**Do not act from this summary alone** — it is oriented for triage, not execution, and the plan
file is long (1913 lines). Read the actual plan file yourself, following this programme's
Sub-agent output contract (never hand a sub-agent the whole plan file — extract only what each
task needs, same discipline every prior package used). This session has now read it in full.

**The question P6 answers:** do the two native discovery adapters (YouTube, YouTube Data API,
Bluesky) obey the same contract the four Bright Data adapters already do? No.
`brightdata_job.py:6-10`'s own docstring states the invariant: *"a job that times out or reports
'failed' MUST raise, never return `[]`. An empty list means 'the job completed and there was
genuinely nothing' … the exact bug that shipped in the first Instagram adapter."* YouTube and
Bluesky violate it — a failed enumeration and a genuinely quiet day currently share the same `[]`
return value. **Closing that violation is the spine of this plan; every other finding hangs off it.**

**Scope — files owned by this package, no other package may touch them:**
```
pipeline-app/pipeline_app/discovery_youtube.py
pipeline-app/pipeline_app/discovery_youtube_api.py
pipeline-app/pipeline_app/discovery_bluesky.py
pipeline-app/tests/test_discovery_youtube.py
pipeline-app/tests/test_discovery_youtube_api.py
pipeline-app/tests/test_discovery_bluesky.py
```
**Explicitly NOT owned, do not touch:** `brightdata_job.py` (the reference implementation this
package is aligning with, not modifying) and `discovery_engine.py` (P8's file — P6 only prepares
the seam P8 consumes later).

**Findings closed here (18):** B-04 through B-17, D-52, F-12, F-20, F-24. Severities: S1×5 (B-06,
B-10, B-12, F-12, F-20), S2×7, S3×1, S4×5. 9 of the 18 are `failure_mode: silent`, so the
Three-Test Rule (fault / distinguishability / surfacing) applies to each.

**Depends on P0** (the `allow_subprocess` marker — T1/T2 spawn a real subprocess to prove
byte-identical UTF-8 round-tripping) **and P1** (`obs.log`, imported by all three adapter modules;
`obs.record_event` is deliberately NOT called here — adapters have no DB connection). Both are
long merged; re-confirm `pytest.mark.allow_subprocess` still resolves before dispatching T1.

**Suite: app suite only** (`cd pipeline-app && python -m pytest tests/<file> -q` per task, never a
bare `pytest`, never from the repo root). P6 touches no root-suite files.

**The three structural changes everything else builds on** (the plan's own framing, §1):
1. **`_run_ytdlp()`** — one chokepoint for all three `subprocess.run` sites in
   `discovery_youtube.py`, carrying `encoding="utf-8", errors="replace"`, normalizing `stdout`/
   `stderr` from `None` to `""`, and returning the return code to a caller now obliged to check it.
   Closes B-10 and B-16 at the source instead of in three places.
2. **Typed failures — `YouTubeEnumerationError`, `TranscriptFetchBlocked`, `BlueskyFetchError`,
   `YtDlpUnavailable`.** Enumeration/transport failures *raise*; a genuinely empty listing
   *returns `[]`*. The two states stop sharing a representation.
3. **A retryable transcript state.** `transcript_status` gains a third value, `pending_retry`, and
   `on_disk_ids()` re-offers items carrying it — a bot-blocked capture stops being permanent.

**Tasks, in the plan's own order (20 total, T1-T20) — one line each, full detail in the plan file:**
1. **T1** — `_run_ytdlp()` chokepoint: UTF-8 round-tripping, `stdout`/`stderr` never `None` (B-10).
2. **T2** — every existing subprocess-mocking test migrates to the new `_run_ytdlp` signature (B-10).
3. **T3** — return codes are read; `peek`'s unguarded `json.loads` is guarded (B-16).
4. **T4** — enumeration failure raises; only a genuinely absent `/shorts` tab is legitimately empty
   (B-11). **Inverts** `test_enumerate_newest_first_returns_empty_on_failure`.
5. **T5** — without Data API dates, Shorts are kept and interleaved (marked order-approximate), not
   silently dropped (B-14, F-24, the "enshrined Shorts drop" test is deleted and replaced).
6. **T6** — the "no Data API key" warning fires once per process, not once per video (B-15).
7. **T7** — `fetch_upload_dates` reports its no-key path instead of failing silently (B-14, F-24).
8. **T8** — the Data API key moves from the request URL query string to a header (D-52).
9. **T9** — a blocked transcript fetch (`TranscriptFetchBlocked`) is distinguished from a genuinely
   captionless video; unrecognized transcript-library exceptions fail toward retryable (B-13).
10. **T10** — a blocked capture is written with `transcript_status="pending_retry"`, not `"missing"`
    (B-12).
11. **T11** — `on_disk_ids()` re-offers a `pending_retry` capture for retry (B-12).
12. **T12** — YouTube frontmatter carries `published` alongside `upload_date` (B-04) — see §6 below,
    this is the one task with a real cross-package handoff (to P9).
13. **T13** — **the archetype task, Bluesky's twin of B-11**: `enumerate_newest_first` raises on a
    transport failure instead of returning `[]` (B-05). **Inverts** F-12's named test,
    `test_enumerate_newest_first_returns_empty_on_fetch_failure` — the test whose *name states the
    bug as the requirement*, the exact defect class `brightdata_job.py`'s own docstring calls out.
14. **T14** — a partial multi-page Bluesky walk is never presented as a complete one (B-05).
15. **T15** — a transient Bluesky failure cannot permanently mark a valid handle invalid (B-06). No
    production change expected here — this task exists to name the invariant and leaves an explicit
    **Note for P8** in its own text (see the contract section below).
16. **T16** — the keyword filter reads the whole post body, not just the first 60 display characters
    (B-08).
17. **T17** — undated Bluesky rows are dropped and counted, making `peek_upload_date`'s "dead code"
    comment actually true (B-09).
18. **T18** — `download_item` reads a cache instead of re-walking the entire feed once per item
    (B-07).
19. **T19** — a parametrized contract sweep across all native adapters (F-20) — the guard that fires
    loudly if a native platform is ever added without an entry (P7's plan explicitly says it should
    hoist this into a shared table covering all six platforms once it lands).
20. **T20** — bound/opt-in the full-catalogue channel walk instead of re-enumerating everything
    every run (B-17).

**Tests deleted or inverted (4, full detail in plan §5):**
`test_enumerate_newest_first_returns_empty_on_fetch_failure` (Bluesky, F-12, inverted in T13);
`test_enumerate_newest_first_returns_empty_on_failure` (YouTube, unnamed twin of F-12, inverted in
T4 — `test_missing_shorts_tab_is_not_an_error` is explicitly KEPT and strengthened, don't delete
it); `test_without_api_dates_falls_back_to_videos_only_and_warns` (deleted and replaced in T5, it
asserted the Shorts-drop defect as correct); `test_transcript_status_missing_when_no_transcript`
(split, not deleted, in T10 — kept with a corrected fake and an explicit
`transcript_attempts == 0`). After T13, `grep -rn "returns_empty_on_fetch_failure"
pipeline-app/tests/` must return nothing.

**The cross-package contract P6 owes P8 — read P6's own plan §7 for the authoritative wording, not
just the master plan's summary table.** The master plan's cross-package contracts table
(`2026-08-08-audit-remediation.md`, "P6 → P8" row) lists four exception types reaching
`discovery_engine.py:272`: `BlueskyFetchError`, `YouTubeEnumerationError`, `YtDlpUnavailable`,
`TranscriptFetchBlocked`. **P6's own plan file (§7, "Cross-package notes") is more precise and
should be treated as authoritative where the two differ**: it names only THREE types P8 actually
receives — `YouTubeEnumerationError`, `YtDlpUnavailable`, `BlueskyFetchError` — because
`TranscriptFetchBlocked` (T9) is caught and converted to `transcript_status="pending_retry"`
entirely inside `discovery_youtube.py`'s own `download_item` (T10); it never propagates up to
`discovery_engine.py` at all. This is exactly the "verify, don't inherit" lesson applied to the
master plan's own summary table, not just to a sibling package's code — **confirm this yourself
against both documents before dispatching T15 or briefing whoever executes P8 next.** The concrete
contract, quoted from P6's plan §7: *"`discovery_engine.py:255` must not convert a
`BlueskyFetchError` into `status='invalid'` + `included=False` (B-06); the error branch at `:272`
is the correct destination. It also gains an optional `max_items=None` opt-in for a deliberate full
backfill (B-17) and may pass `order_confidence` through to its run record (B-14)."*

**T12's contract for P9** (plan §6, in full — read it before P9's own session, not just this
excerpt): T12 makes YouTube write BOTH `"published"` and `"upload_date"` keys with the same value
(not a rename — files already on disk carry only `upload_date`, and renaming would blank every
historical YouTube capture's date). P9 then owns three follow-ups, none of which are P6's or P8's
job: (1) `discovery_digest.py:191`'s `meta.get("published") or meta.get("upload_date")` fallback
must STAY for at least one full re-capture cycle, with a comment explaining why and a test that a
`published`-less file still renders its date; (2) P9 decides which key is canonical in the render
and must not read `upload_date` for any non-YouTube platform; (3) P14 should later amend
CLAUDE.md's contract text to document `published` as canonical with `upload_date` as YouTube's
legacy alias, so a future adapter author isn't shown two contradictory examples.

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this. P4 hit it **eleven times**
across 20 tasks; P5 hit it **twice** (T17's `db.transaction()` infrastructure assumption, T15's
`obs.LOG_DIR` path assumption) plus one silent T1-fixture regression that slipped past task review
and was caught later (a stale content-assertion test broken by T1's own fixture change, found
during T3's dispatch; a stale `len(log) == 1` count broken the same way, found during T10's
dispatch) — **both times the controller verified independently before accepting the implementer's
"pre-existing" claim, rather than trusting it at face value.** That verify-before-trusting habit is
now as load-bearing as the amendment habit itself. **A task's own shown test/implementation code
can reference a function, class, fixture, or sibling-package API that doesn't exist yet at the
point that task is dispatched, or that exists but behaves differently than the plan assumes.** The
mitigation, unchanged since P2, with P5's new sub-lessons:

1. **Grep for every symbol a task's own shown code references** before dispatching it — function
   names, class names, fixture names, other packages' modules — and confirm each either already
   exists live, or is defined within that same task's own text.
2. If something's missing: **amend the plan file FIRST**, as a `>` blockquote note inserted
   directly at the relevant task, **with its own commit** explaining what was wrong and why —
   then dispatch the corrected version. Never fix a gap silently inline without amending the plan.
3. Your own amendments can contain the same class of bug — re-verify their own claims (exact line
   numbers, exact counts, exact function signatures) against the live repo before committing them.
4. **A sibling package's return type/infrastructure can carry richer semantics than its signature
   alone reveals, and can be NEWER than the plan text that references it.** P5's T17 amendment is
   the clean example: the plan assumed `db.py` still auto-committed per row via
   `db_mod.create_project`/`db_mod.create_stage_row`, and instructed hand-rolling
   `conn.execute`/`commit`/`rollback` as a replacement. By the time P5 actually executed, `db.py`
   already shipped a `db.transaction(conn)` context manager with its own rollback-and-report
   infrastructure (added by later work on `db.py` after the plan text was written). Following the
   stale plan text would have fought that infrastructure instead of using it. **Read the actual
   current state of a file the task instructs you to change or stop calling — don't trust the
   plan's characterization of "what X currently does," even when the plan sounds confident.**
5. **A later task can quietly widen what an earlier task's error-handling already covers, INCLUDING
   across the task/final-review boundary itself.** P5's own final whole-branch review (opus) found
   this in the T17+T18 seam: T17 wrapped project creation in `db_mod.transaction(conn)`; T18 (two
   tasks later, in a LATER SDD dispatch) added a retry loop around it for the exact, expected,
   self-healing case of a same-second `run_id` collision. Neither task's own review caught that the
   *combination* meant a routine, successful retry now left a burst of `error`-severity
   `db.transaction_rolled_back` events behind, because `db.transaction()`'s own exception handler
   fires unconditionally on any exception inside the block — including one the retry loop was
   specifically designed to swallow. **Only the final whole-branch review, reading the full
   cumulative interaction between the transaction boundary and the retry loop, saw it.** Do not
   skip or shorten the final review on the theory that every task passed its own review.
6. **A test double's structure can force a change to production code, and that's fine — but write
   the production comment to justify itself first, the test second.** P5's T17 amendment specified
   `run_dir.mkdir(parents=True, exist_ok=False)` as one call; the implementer had to split it into
   two (`run_dir.parent.mkdir(parents=True, exist_ok=True)` then `run_dir.mkdir(exist_ok=False)`)
   because CPython's own `pathlib.Path.mkdir(parents=True)` recurses back through `Path.mkdir`
   itself for each missing directory level — confirmed empirically by the controller with a
   standalone spy script (5 separate `Path.mkdir` invocations for one 3-level `mkdir(parents=True)`
   call). Under a test that monkeypatches `Path.mkdir` to fail on a specific call NUMBER, that
   recursion silently shifts which physical directory the injected fault actually lands on — and
   this shift can go completely unnoticed by both the implementer and the task reviewer, because
   every test still passes; it just stops exercising the code path it claims to (P5's own final
   review caught this as a genuine Important finding: two tests injected a fault meant to hit the
   filesystem-cleanup branch, but a task-boundary API split silently moved the fault one call
   earlier, so `shutil.rmtree` never actually ran in either test until a follow-up fix wave
   retargeted the trigger). **When a test fakes an external call by counting invocations, and
   production code changes how many calls a single logical operation makes, re-verify the count is
   still landing where the test's docstring claims — don't just check that the test still passes.**
7. **Verify empirically before writing a brief, not after a fix-loop round.** Cheaper every time
   this programme has measured it — e.g. P5's controller ran a standalone `subprocess`/`pathlib`
   spy script to confirm the `mkdir(parents=True)` recursion claim in point 6 above BEFORE writing
   the corresponding brief, catching what would otherwise have been round-4-of-5 fix-loop churn.
8. **A mandatory final whole-branch review is not the last line of defense against everything — CI
   on a genuinely different machine is.** Watch the PR's CI checks after pushing, not just your own
   local suite runs, even when the final review came back clean.

## Carried-forward open items (know they exist; check whether any land in P6's own files)

Two operator decisions remain open, unresolved, not any package's call — surface them again if the
operator hasn't weighed in (repeated in every resume prompt since P10/P11):

1. `T21R-01` — the `CLOSE`/`MACRO` 1-object-floor carve-out in Gate C's C8 check (P11's file).
2. `T6R-02` — what should catch an extra fenced example block mid-sheet (the one documented
   root-suite exception, `test_lint_prompt_sheet.py::...[fenced-heading]`, unchanged for many
   sessions now, confirmed still present and still out-of-scope for every package including P4/P5).

From P3's final review (unchanged, still open): nine test failures in files P3 owns, a scratch-file
interleaving hazard, gate messages naming a scratch filename, eight further Minor findings (PR #32),
and four new CSS classes with no stylesheet rules yet.

From P12's final review (still open): nine Minor findings — full list in
[PR #34](https://github.com/happydotemdr/ContentStudio/pull/34)'s body.

From P4's final review (still open, not P6's job unless P6 happens to touch the exact same lines —
full list in [PR #37](https://github.com/happydotemdr/ContentStudio/pull/37)'s body): an untested
defensive branch in `turn_service._resume_failed`, a stale docstring on one turn-recovery test,
`routes/stages.py`'s hand-edit path not adopting P4's three-keyword widening (A-14/A-32 only closed
on the turn/chat path), and `main.py:161`'s implicit `repo_root=` derivation.

**From P5's final review (still open, none are P6's job — full list in
[PR #39](https://github.com/happydotemdr/ContentStudio/pull/39)'s body, 8 Minor findings after the
3 Important + 3 cheap Minor ones were fixed in-session):**

3. `test_the_editor_reads_the_same_mapping_pipeline_config_publishes` (T19) asserts
   `pipeline_config.stage_id_by_skill` against itself rather than exercising it through a route —
   real coverage exists elsewhere (T2/T3/T5), so this is a naming/assertion mismatch, not a gap.
4. A-56 (symlinked skill directories) only partially closes on Windows: `Path.is_symlink()` returns
   `False` for an NTFS directory junction, so the actual defense against a junction is the
   `path.resolve().is_relative_to(root.resolve())` containment check one layer down — untested.
5. `routes/skills.py`'s `save_skill` has one unguarded `path.write_text(...)` call — a missing
   `stage_templates/` directory or a permissions error still produces a bare 500 with no `events`
   row, in the exact route P5 exists to make failure-proof.
6. `test_overlong_slug_returns_400_not_500` (T16, taken verbatim from the plan) asserts
   `"60" in resp.text` — a literal hardcode of `MAX_SLUG_LENGTH`, violating this programme's own
   anti-tautology rule. Plan-inherited, not implementer-introduced.
7. Two pre-existing `subprocess.run(..., text=True)` calls survive in `test_git_helper.py` (lines 31,
   50), against the programme's Windows-encoding rule — untouched by P5's diff, trivial to fix.
8. The master plan's own §7 cross-package notes for P5 are now stale after the T17 amendment (still
   says "P5 stops calling `db_mod.create_project`/`db_mod.create_stage_row`", which the amendment
   reversed).
9. `project_service.py`'s mkdir-split code comment leads with the test-double reasoning (see
   recurring-bug-class point 6 above) rather than the production justification
   (`exist_ok=False` needs to apply to `run_dir` specifically, independent of any test).
10. Collision handling is asymmetric between layers: a DB-level `run_id` collision retries
    (`sqlite3.IntegrityError`), but a filesystem-level collision (`run_dir.mkdir(exist_ok=False)`
    raising `FileExistsError`, an `OSError` subclass) escapes the retry loop and 500s. Low
    probability (needs a stale directory with no matching DB row) but real.

None of these are load-bearing for P6 unless P6's own tasks happen to touch the exact same lines,
which they should not (P6's scope is discovery adapters, entirely separate files).

**T20 remains parked** (not P5's final-review list — it's P5's own explicitly incomplete task,
tracked separately): `routes/inspector.py:45` needs `browse_service.sanitize_html`, which is P15's
deliverable (Wave B5, still not started as of this session). Not P6's concern.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`),
  not any worktree. Bake an explicit working-directory check (`pwd && git rev-parse
  --show-toplevel && git branch --show-current`) into every dispatch prompt.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8",
  errors="replace"`.
- **Bash resolution on Windows is genuinely two-layered** — never invoke `bash`/`sh` by bare name
  in a `subprocess.run([...])` call (a bare `"bash"` can resolve to a broken WSL launcher stub);
  even `shutil.which("bash")` is not enough, since which Git-for-Windows `bash.exe` it finds
  matters (the `usr/bin` copy preserves your PATH additions, the `bin` wrapper prepends its own
  ahead of yours). P6 is discovery adapters — check whether any of its tasks shell out to
  `yt-dlp`/external tools and apply this same discipline if so.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead of an inline heredoc (this
  session's own PR body for P5 was written to a file for exactly this reason — the harness's
  worktree-boundary guard also rejects complex multi-command heredocs run via `cd ... && ...`, so
  prefer the Write tool over Bash heredocs for anything beyond a single simple command).
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field from a filename or frontmatter value.
- In this specific harness, the Bash tool's working directory can drift between calls depending on
  prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command
  fails with an unexpected "no such file or directory" on a path you expect to exist. **This
  harness refuses `cd`s out of a worktree-isolated session's own worktree entirely**, and also
  refuses any single Bash call it judges "too complex to verify stays inside the worktree" (e.g. a
  multi-line heredoc chained with `&&` after a `cd`) — break such commands into the Write tool plus
  a simple `cd ... && command` instead of one compound Bash call.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()`
  (not `.fullmatch()`), will silently never capture the optional group.
- When two independently-written pieces of text/code both need to find something via a
  first-occurrence string match, and one can textually contain what the other searches for, they
  will collide.
- A hand-written HTML sanitizer built on `html.parser.HTMLParser` must escape TEXT NODES
  (`handle_data`), not just attribute values — `convert_charrefs=True` hands `handle_data` already
  entity-DECODED text. `HTMLParser.CDATA_CONTENT_ELEMENTS` is `("script", "style")`, not just
  `"script"`. Not P6's concern.
- A `dict` subclass can override `__contains__`/`__getitem__`/`get` to raise on a specific key
  state rather than behaving like an ordinary dict — check a sibling package's actual class
  definition before assuming standard dict semantics from a type hint alone.
- **A later task can quietly widen what an earlier task's exception-handling already covers** — a
  code region one task wrapped in error-handling because nothing inside it could raise yet can
  become unsafe once a LATER task adds a new raising code path into that same region, and this can
  also manifest as a shared context manager's OWN unconditional side effect (an event it always
  records on exception) becoming inappropriate once a later task starts deliberately triggering
  that exception as an expected, self-healing control-flow path (see recurring-bug-class point 5
  above). Only a final whole-branch review reading the cumulative function/interaction tends to
  catch this.
- **A plan's own execution-order assumption, OR its characterization of a sibling file's current
  behavior, can be wrong even when nothing about the CODE the plan is describing has changed** —
  the plan text can simply predate a later, unrelated change to that file. Grepping the live repo or
  writing a two-line empirical check before dispatch remains cheaper than a fix round, every time
  this programme has measured it.
- **A test that fakes an external call by counting invocations can silently stop testing what its
  own docstring claims** if production code later changes how many calls one logical operation
  makes — the test keeps passing, just against the wrong call. Re-verify the count lands where
  claimed, don't just check green.
- **A mandatory final whole-branch review has found real issues in every package executed so far
  without exception** — P3: 2 Critical + 3 Important; P10: 15; P11: 6; P12: 0 Critical + 5 Important
  (plus 2 CI-only failures); P4: 1 Critical + 2 Important + 4 Minor; P5: 0 Critical + 3 Important
  + 11 Minor (3 Important + 3 Minor fixed in one follow-up wave, independently re-verified clean).
  Do not skip it, do not shorten it, do not let a clean per-task review record talk you out of
  dispatching it on the most capable available model — and do not consider the package done until
  you've read its PR's CI logs and confirmed the ONLY failures are the same documented pre-existing
  baseline (1 root + 31 app, by test name, not just by count).

## Definition of done (the whole programme, not any one package)

1. All 328 findings closed — each verified by the mechanism its plan names. P3's own 22, P12's own
   16, P4's own 26, and now **P5's own 15** (all 19 executed tasks + the final review's fix wave,
   confirmed by its own mandatory final review, re-reviewed clean; T20 is the one task NOT closed,
   correctly parked pending P15) are confirmed closed independently by each package's mandatory
   final review. Count each package's own total from its merged PR, not from memory.
2. Both suites green everywhere they can be: root suite target ~445-446/1 (the one documented
   T6R-02 exception); app suite target keeps the same 31 pre-existing failures until a dedicated
   follow-up closes them (see "Carried-forward open items" above). The passed count on both suites
   will keep climbing as each package adds its own regression tests — track failures by name, not
   the passed count, when checking whether a session's work is "the same baseline."
3. CI exists (3 jobs, from P0) — **but is NOT green, and has not been since before P3's merge**,
   confirmed again this session (`gh run list --branch main --limit 5`, all recent merges show
   `failure`). The cause is exactly the same pre-existing root-suite and app-suite failures every
   resume prompt has documented as deliberately out of scope — the CI job hard-fails on any
   non-zero pytest exit code with no allowance for the documented baseline. This is a real,
   standing gap in the programme's own definition of done, not a P6 concern specifically, but worth
   naming again for whichever session eventually closes the pre-existing failures or decides the CI
   job should tolerate a documented allowlist instead. Re-run `gh run list --branch main --limit 5`
   yourself at session start rather than trusting this note.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error events row. **This
   is directly P6/P7/P8's territory (Wave B4 is Discovery) — expect this item to move for the first
   time since P0 during this wave.**
6. Gate C rejects a malformed shot heading — done, verified end to end.
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing — the F-64 atomic rename is P8's
   task (Wave B4, same wave as P6, but P8 lands after P6 and P7 per the ordering constraint above).
