# Resume prompt — audit-remediation programme, P3 (T1 → T24)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, where it must stop, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-13, after P10 and P11 both closed and merged (PR #28, PR #29), and the main
checkout was resynced to `origin/main` in the same session that wrote this update.

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

**Read these files before doing anything else:**

1. `docs/superpowers/plans/EXECUTION-KICKOFF-PROMPT.md` — the governing brief. Still binding.
2. `.superpowers/sdd/2026-08-08-audit-remediation/progress.md` — the master ledger. Git-ignored,
   local-only, and **stale since P2** (P10 and P11 each used their own per-package workspace
   ledgers instead — `.superpowers/sdd/P10-roster/` and `.superpowers/sdd/P11-gate-c/` — and
   neither was folded back into this file). Trust `git log` and this document over it; do not
   assume it reflects current state.
3. `docs/superpowers/plans/remediation/P3-gates-approval.md` — the plan being executed. It already
   carries a **"Handoff H1b"** note (added this session) documenting two things P11 discovered late
   that affect P3's own T6/T7 — read it before touching those tasks.

## Where execution is

**P0 (23 findings), P1 (13), P2 (15), P10 (11), P11 (28) — all complete and merged into `main`.
90 of 328 findings closed.**

- P0 → PR #25/#26. P1 → PR #26. P2 → PR #27. P10 → PR #28. **P11 → PR #29, merged 2026-08-13.**
- The worktree's branch (`claude/pipeline-audit-review-4dd767`) is fully merged into `origin/main`
  as of this update (`git merge-base --is-ancestor HEAD origin/main` succeeds). Continue
  committing new work on this **same branch** — every prior package landed this way: accumulate
  commits, open a new PR comparing against `main` each time. Do not create a new worktree or
  branch.
- **The main checkout (`C:\Projects\ContentStudio`, separate from this worktree — this is where
  `pipeline-app` is installed editable) was found this session to be 100 commits behind
  `origin/main`, carrying one unpushed local-only commit (`feat(roster): populate creators...`,
  an early/incomplete duplicate of what P10 later did properly) and two stray uncommitted file
  edits matching an abandoned first attempt at P11's own T11 work.** All three were resolved with
  the operator's explicit sign-off: the stray edits were discarded, the local-only commit was
  dropped (its content was fully superseded by P10's reviewed, merged version), and the checkout
  was fast-forwarded to `origin/main` (`776bd2a`). **The main checkout should be clean and in
  sync as of this update — do not assume it stayed that way. Run the full sync check in "THE
  PAUSE / COMMIT / PR POINT" section below, now, before starting any task work** — that section
  frames it as an end-of-session step, but it is exactly as valid (and arguably more important) to
  run at the *start* of a session, since it's the operator's own activity between sessions, not
  just a prior session's carelessness, that can leave the main checkout behind or dirty. If a
  subagent's dispatch prompt tells it to verify its own working directory is the *worktree*, that
  check is about avoiding a repeat of exactly this class of mistake — take it seriously, it has
  now happened at least twice across this programme's sessions.

Suites, verified on merged `main` (`776bd2a`):

- **Root suite: 355 passed, 1 failed.** The one failure
  (`test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[fenced-heading]`) is a
  deliberately deferred, documented finding (**T6R-02**, below) — no task in P11 or any prior
  package is chartered to close it. Not P3's problem unless P3's own session decides to pick it up
  (it isn't — Gate C's own file, owned by P11, not touched again until a future package explicitly
  adopts it).
- **App suite: 33 failed / 1093 passed / 3 skipped.** 32 of the 33 are the same pre-existing,
  already-documented cross-package fallout from P2's breaking signature changes
  (`write_pointer` gains required `repo_root`, `record_gate_override` gains required `at=`,
  `identify_new_brief` → `classify_brief_change`) — unchanged since PR #27/#28, affecting
  `routes/stages.py`, `approval_service.py`, `browse_service.py`, `discovery_digest.py`,
  `routes/inspector.py`. **This is directly relevant to this session: P3 owns `routes/stages.py`
  and `approval_service.py`, and P3's own tasks that adopt P2's frozen `artifacts`/
  `grounding_service` APIs are expected to close a meaningful chunk of these 32 — confirm the
  count actually drops when you land them, don't assume it did.**
- **The 33rd app-suite failure is new, from P11, and is P3's to fix (see "Handoff H1b" below)**:
  `pipeline-app/tests/test_gates.py::test_visual_gate_without_a_styleboard_uses_a_legacy_sheets_own_world_lock`
  now fails because P11's C8 change (a stricter object-count floor) trips on
  `legacy_do_less_sheet.md`'s Hook shot, which the test's blanket `assert "C8" not in checks`
  wasn't written to guard against. Resolve as part of this package's own work — either narrow the
  assertion to the specific C8 sub-check the test actually cares about, or add a second
  signature-object mention to the fixture.

CI runs three jobs (`root-suite`, `app-suite`, `no-live-credentials`) and is **expected to show
`root-suite: failure` and `app-suite: failure`** on any PR that doesn't specifically resolve the
items above — this has been the accepted, documented state since P2 (PR #28 merged with
`app-suite: failure` and no objection). Do not treat either as a regression to chase blindly;
do read the actual failure output and confirm it matches what's documented here before assuming
it's fine, the way this session did when the operator asked about it directly.

## NEW since the P10 resume prompt: P11 shipped, plus two operator decisions still open

P11 fixed Gate C's flagship fail-open-at-the-parse-layer defect (a malformed shot heading used to
be silently skipped, deleting the shot from every one of ~20 checks, gate prints `PASS`) plus 27
other findings. Full detail: `docs/superpowers/plans/remediation/P11-gate-c.md`, especially its
**"## 0. Pre-review amendments"** and **"## 7a. Findings filed..."** sections, which document
every deviation discovered during execution.

**Two things from P11 are explicit operator decisions, not yet resolved — surface them again if
the operator hasn't weighed in, do not silently assume an answer:**

1. **T21R-01.** Fixing C8 (sport/object-name matching, finding C-87) required inventing new gate
   policy not specified by the original audit — a relaxed 1-object floor for `CLOSE`/`MACRO`
   shots, because the real corpus fixtures have legitimate close-ups that only ever name one
   object. Empirically justified and narrowly scoped (the sport-naming sub-check stays
   unconditional at every scale, so the literal C-87 evasion is fixed regardless), but it has a
   real, currently-unmitigated consequence: nothing in Gate C cross-validates a shot's declared
   scale against its prompt content, so an author could mislabel any shot to dodge the floor. This
   is also the root cause of the new app-suite failure above. The independent final-review
   reviewer's own take: the trade-off is directionally correct (it's *strictly weaker* than the
   pre-P11 status quo, which had an effective 1-object floor everywhere), but the operator should
   still explicitly accept it — see P11's plan §7a for full detail.
2. **T6R-02.** One mutation test case (`fenced-heading`, in Gate C's own 26-case regression suite)
   has no task anywhere chartered to close it — it's the one root-suite failure above. Needs a
   decision: add a check for "an unexpected extra fenced example block mid-`PER-SHOT PROMPTS` is
   suspicious," retire the mutation case with a comment explaining why, or explicitly accept the
   gap. Not P3's file (`scripts/lint_prompt_sheet.py`, owned by P11) — flag it, don't fix it from
   here unless specifically asked to.

**Five more findings were filed during P11 for documentation/test-anchor accuracy, all non-blocking
and none touching P3's files** (T6R-01: three stale mutation-test fixture anchors; T11R-01: a
regression test's own vacuousness, already fixed in P11's final-review pass; T18R-01, T19R-01,
T20R-01: minor plan-text/mutation-table inaccuracies, all resolved or filed for later). None of
these need P3's attention — full detail in P11's plan §7a if curious.

## Handoff H1b (from P11, already written into P3's own plan — read it there, summarized here)

Two things P11 discovered *after* P3's plan text was written, neither reflected in P3's T6/T7 as
currently shown:

1. **A fifth CLI/app Gate C divergence beyond the four this plan's own interfaces table lists**,
   filed as `P3-6` in P11's plan §6.2: the CLI's `main()` now flags a sheet's own stray
   `WORLD LOCK` block when `--styleboard` is also supplied; `gates.py` does not yet have the
   equivalent. **P3's own T7 differential test won't catch this automatically** — its
   `_cli_findings` helper manually re-derives `main()`'s pipeline instead of calling `main()`
   itself, and none of `DIFFERENTIAL_CASES`' four fixtures happen to carry a stray sheet-side
   world lock. Before executing T6/T7: either add a fifth differential fixture exercising this, or
   change `_cli_findings` to actually call into `main()`'s logic so future divergences are caught
   mechanically instead of needing to be separately remembered.
2. **The confirmed `test_gates.py` regression** described above under "Where execution is" — same
   root cause, same fixture (`legacy_do_less_sheet.md`), same file P3 already owns.

## YOUR TASK THIS SESSION: P3 (T1 → T24), then STOP

**Start at T1.** P3 is untouched — nothing in it has been pre-reviewed or dispatched yet.

P3 is **larger than any single-session package executed so far** (24 tasks, vs. P11's 22 and
P10's 19, both of which consumed a full session each). Recommendation, matching every prior
package's own session shape: **execute P3 alone and stop. Do not start P12 in this session** unless
you've explicitly confirmed with the operator that they want the larger scope attempted — P12 T8
leaves a deliberate `xfail(strict=True)` tripwire that only resolves once P3 changes `gates.py` to
derive `blocking` from a `kind` vocabulary rather than a hardcoded string; landing them in the same
session invites exactly the "carrying over assumptions" failure mode this programme's own
discipline exists to catch (see the P10 and P11 sessions' own resume-prompt precedent for this same
recommendation, both followed).

### Files this package owns (no other package may touch these)

```
pipeline-app/pipeline_app/routes/stages.py
pipeline-app/pipeline_app/gates.py
pipeline-app/pipeline_app/approval_service.py
pipeline-app/pipeline_app/state_machine.py
pipeline-app/pipeline_app/preflight.py
pipeline-app/tests/test_gates.py
pipeline-app/tests/test_routes_approve_edit.py
pipeline-app/tests/test_routes_stages.py
pipeline-app/tests/test_approval_service.py
pipeline-app/tests/test_state_machine.py
pipeline-app/tests/test_preflight.py
```

Explicitly does **not** touch `turn_service.py` (P4), `artifacts.py`/`migrations.py` (P2, already
shipped — P3 *adopts* its frozen API, doesn't modify the file), `scripts/lint_prompt_sheet.py`
(P11, already shipped), `templates/**`/`browse_service.py` (P15), or `pytest.ini` (P0).

### Finding IDs owned (22)

`A-30`, `A-31`, `A-33`, `A-35`, `A-36`, `A-39`, `A-40`, `A-41`, `A-42`, `A-45`, `A-60`, `A-62`,
`A-64`, `A-77`, `A-84`, `E-04`, `E-05`, `E-07`, `F-17`, `F-19`, `F-28`, `F-73`

### One-line goal (from the plan's own header)

Make the two artifact-write paths run *the same* gates against *the same* inputs, make an unknown
gate result impossible to approve through, and make an ungated styleboard impossible to hand to
Gate C.

### Frozen cross-package interfaces P3 must adopt (from P2, already shipped)

- `artifacts.compute_depends_on(run_dir, upstream_paths) -> list[dict]`
- `artifacts.reserve_version` / `write_reserved_artifact` / `release_version` — exclusive version
  allocation; `next_version_number` is advisory only. **P2R-01 (filed, still open): neither
  `routes/stages.py` nor `turn_service.py` was ever migrated to this** — P3 owns the former, check
  whether your own tasks close this or whether it needs its own explicit task.
- `artifacts.parse_frontmatter` — now raises `MalformedArtifactError` instead of degrading.
- `artifacts.record_gate_override(path, reason, *, at, actor=None)` — `at` is required.
- `artifacts.read_gate_overrides(path) -> list[dict]`
- `grounding_service.write_pointer(stage_dir, relpath, repo_root)` — `repo_root` is required.
- `grounding_service.classify_brief_change` — replaces the deleted `identify_new_brief`.
- `grounding_service.verify_pointer(stage_dir, repo_root) -> PointerStatus`
- `lint_prompt_sheet.parse_world_lock` / `parse_style_library` / `VALID_SLOT_VALUE_RE` (P11,
  read-only) — the styleboard gate loads them via `_load_linter`.

### P3's own plan already resolved two things worth knowing before you start

- **Assumption A1 (resolved):** an earlier plan draft invented two function names
  (`artifacts.resolve_upstream_by_stage`, `artifacts.depends_on_records`) that P2 never shipped.
  The plan's current text defines `gates.resolve_upstream_by_stage(...)` in P3's own file instead —
  already correct, no action needed, just don't be confused if you see the old names referenced in
  older discussion.
- **Handoff H2 (P4's counter-contract, already reconciled):** an earlier draft asked P4 to adopt
  P3's resolver verbatim; P4 found this would reopen three closed findings (A-32, A-02, A-14) and
  the plan now widens the resolver with three keyword-only parameters instead, matching P4's own
  signature. Already resolved in the plan text — no action needed.

### THE PAUSE / COMMIT / PR POINT: end of P3, before P12

**Stop when P3's own final-review fix wave (if any) is clean.** Then: run both suites, confirm the
app-suite failure count actually dropped from adopting P2's frozen API (don't just assume it did),
push, and open a PR titled for P3's completion, same shape as PR #28/#29's bodies — findings
closed, suite numbers, what the operator will notice on next boot, what is knowingly still open.
**Do not start P12 in this session.** Update this file (`RESUME-PROMPT.md`) at that pause point,
the way this update should have happened at the end of P11's own session and didn't — the gap was
only caught because the operator asked directly.

**Before declaring the pause point reached, run a full local/remote sync check — this is now a
mandatory, repeatable step, not a one-off. It was skipped at the end of every session from P2
through P11, and the drift it let accumulate (100 commits, one unpushed commit, two stray
uncommitted edits, all in the *other* checkout) was only caught because the operator happened to
ask.** Run, and paste the actual output into your own final report, don't just assert it's clean:

```bash
# 1. Worktree: no uncommitted changes, nothing unpushed.
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767"
git status --short                                    # expect empty (untracked scratch files aside)
git push origin claude/pipeline-audit-review-4dd767    # expect "Everything up-to-date" after your last push
git rev-parse HEAD origin/claude/pipeline-audit-review-4dd767   # expect identical

# 2. Remote: your PR is actually open (or merged) against the commit you think it is.
gh pr view <number> --json state,mergeable,headRefOid

# 3. The MAIN checkout (separate from this worktree, where pipeline-app is actually installed) —
#    this is the one that silently drifted for three sessions. Never assume it's fine.
cd "C:/Projects/ContentStudio"
git fetch origin
git status --short                                     # expect clean, or only known operator artifacts
git rev-parse HEAD origin/main                          # expect identical, or explain the gap
```

If the main checkout is behind or has local changes, do not silently pull/reset it — investigate
what the changes are first (exactly as this session did: traced two "modified" files back to a
stray, superseded implementer attempt before touching anything), then ask the operator before
running anything that discards or rewrites history, the same way this session asked before
dropping the unpushed roster commit and before discarding the stray edits. A clean `git fetch` +
inspection costs nothing; a wrong guess about what's safe to discard does not undo.

**A mandatory final whole-branch review, on the most capable available model, blind to every
task's own review, is not optional** — P10's own proactive pass found 15 new findings including 2
Critical ones that predated the whole package; P11's found 6 more including 2 genuine *live*
defects in code every prior per-task review had separately approved. Dispatch one fix wave for
whatever it finds (one subagent, the complete findings list, not one fixer per finding), then one
scoped re-review of that fix wave. This has caught real, load-bearing bugs in **every single
package executed so far** — do not skip it because the per-task reviews already looked thorough.

## The bar, restated because it is what everything else serves

**"Any representation shared by 'nothing here' and 'something is wrong' is a defect by default."**
This root cause has now appeared, by the controller's own count, in **50+ confirmed instances**
across P0–P11, the large majority written by the remediation itself, not the original bugs. P11
added at least 3 more: a malformed shot heading swallowed silently when its own fence was
independently broken; a sheet's stale world lock discarded with zero signal when a styleboard was
also supplied; a regex whose "explicit index" capture group could never actually capture anything,
making a whole resolution path dead code with no test able to reach it. **Expect the same pattern
in P3** — an unknown gate result silently treated as "nothing to block," a `blocking` derivation
that hardcodes a string instead of deriving it, an approval route that can't tell "gate never ran"
from "gate passed," are all exactly this shape.

For every `silent` finding, the **Three-Test Rule** is mandatory: fault, distinguishability,
surfacing. Surfacing means an events row, a non-zero exit code, or a rendered UI element —
*asserting that a `print()` happened does not count*.

**Coverage is not the bar.** The bar is: for each finding, a named test that fails before the fix
and passes after — **and you must actually observe the failure.**

## Process that is mandatory — all of it (unchanged since P0, still binding)

1. **Adversarially pre-review the plan's own code before dispatching any implementer.** Every
   package so far has had real defects found this way (P0: 15, P1: several, P2: 5, P10: 8 before
   dispatch plus 2 more mid-implementation, P11: 1 major plan-amendment before any dispatch plus
   several more found empirically mid-package). Probe the actual current source empirically rather
   than trusting the plan's prose — P11's own pre-review verified every line-number and quoted-text
   claim in its plan against the live repo before dispatching a single task, and it held up almost
   perfectly (a testament to how the plan was written, not a reason to skip the check next time).
2. **Run `compile_plan.py` on the plan before every dispatch.** Lives in the session scratchpad;
   rewrite it if gone (~30 lines, `textwrap.dedent` each fenced python block, compare failing-block
   COUNT against a baseline; several blocks failing by design — mid-function fragments, or
   markdown-fence artifacts from a triple-backtick embedded inside a test string literal — is
   normal, verify each one individually rather than assuming).
3. **Amend the plan FIRST, then execute the amended step.** Every amendment gets its own commit
   explaining what was wrong and why. P11 found a genuine gap this way before dispatching a single
   task: no task's shown code actually wired `main()` to consume the new fail-closed parse-findings
   channel its own flagship fix introduced — fixed by amending the task that already substantially
   rewrote `main()`, before execution began.
4. **Your own corrections will contain the defect they were written to catch.** Happened repeatedly
   across every package so far. P11's own T11 task hit this twice in one session: the plan's
   mandated blockquote text collided with a pre-existing mutation test via a first-occurrence
   string-match bug, and *the test written to fix that specific collision* had the identical
   collision bug in a different place, caught only by the final whole-branch review.
5. **Check every silent finding's surfacing test for the same-connection read.** Still the single
   most repeated defect class across the whole programme. Use the second-connection idiom
   (`tests/test_db.py:339-364`, `:663-676`).
6. **Consider a post-implementation adversarial review pass before opening the PR, not only a
   pre-review one.** Every package that ran one found real findings the per-task reviews missed.
7. **Model tiers matter — a cheap-tier model genuinely can produce broken, duplicated output on a
   fiddly multi-location edit.** P11's own T11 was dispatched on a cheap model first, produced
   duplicated blockquote content, missed a required placement entirely, added zero tests despite
   claiming DONE, and caused a real regression in a previously-green test. Reverted cleanly,
   redone on a more capable model with a much more explicit brief, succeeded on the first attempt.
   Default to a standard-or-better tier for anything involving precise multi-location text edits
   with duplication risk; reserve the cheapest tier for genuinely mechanical, single-location,
   fully-scripted changes.

## Traps, verbatim (carried forward, still binding — re-verify each empirically if new ground is
touched)

- **`python -m` is mandatory.** A bare `pytest` at the repo root silently omits all app tests.
- **`pipeline-app` is installed EDITABLE against the MAIN checkout**, not this worktree. As of this
  update the main checkout is clean and synced to `origin/main` — verify it stayed that way before
  trusting anything you run there, and if you dispatch a subagent whose work touches
  `pipeline-app/`, bake an explicit working-directory check (`pwd && git rev-parse --show-toplevel
  && git branch --show-current`) into every dispatch prompt — this exact mistake (a subagent
  operating in the main checkout instead of the worktree) has now happened at least twice.
- **The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db`** — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always
  `encoding="utf-8", errors="replace"`.
- `os.kill(pid, 0)` **terminates** the process on Windows. Use `OpenProcess` for liveness.
- **Never invoke `bash`/`sh` by bare name in a subprocess.** Resolve with `shutil.which()`.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead of an inline heredoc.
- **`grep -c` exits 1 when the count is zero**, silently truncating a `&&` chain. Use `;` instead.
- **A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits.** Use
  `[0-9]` and verify empirically if parsing any numeric field from a filename or frontmatter value.
- **NEW this session: in this specific harness, the Bash tool's working directory resets to the
  worktree path after every separate call — `cd` does not persist between calls.** Any multi-step
  operation touching a different directory (e.g. the main checkout) must be chained in one command
  (`cd X && step1 && step2 && ...`), never split across multiple Bash calls assuming the `cd`
  carried over. This bit the session that wrote this update while investigating the main
  checkout's sync state — every command had to be re-prefixed with `cd "C:/Projects/ContentStudio"`.
- **NEW from P11: a regex with a fully-optional trailing group after a non-greedy `.*?`, matched
  with `.match()` (not `.fullmatch()`), will silently never capture the optional group** — the
  engine satisfies the whole pattern at minimum expansion and never bothers trying to consume more.
  If P3's own code parses anything with an optional trailing capture, verify the capture group
  actually fires on a real example, don't just eyeball the regex.
- **NEW from P11: when two independently-written, plan-mandated pieces of text/code both need to
  find something via a first-occurrence string match, and one of them can textually contain what
  the other one is searching for, they will collide** — happened three separate times across P11
  (a mutation test's anchor colliding with a new doc blockquote's own prose; the doc blockquote's
  own C-77 regression test colliding with itself across two blockquote insertions). If a new task
  adds text that could plausibly contain a string another task's test searches for, check for this
  before assuming independence.

## Open findings — filed, NOT fixed, carried forward from before P11 (still open, none routed to
P3 specifically except where noted)

1. `ux_discovery_single_running` (`schema.sql:90`) crashes `init_db` on a legacy DB with two
   `'running'` discovery runs. **P6–P9.** Not triggered by the operator's current database.
2. An unknown platform posted by hand returns 500 where convention is 400. **P8.**
3. `discovery_handles.html`'s `<select>` is a fourth unpinned copy of the platform vocabulary.
   **P8/P15.**
4. `list_handles_for_creator` returns `[]` for both "no handles" and "no such creator". Deferred to
   the final review.
5. **B-82 not closed.** P1 shipped storage; **P8** must wire the discovery engine, **P15** must
   render the counter.
6. **C-88b (S1, silent) → P12 T1b** — confirmed present in P12's task list, already scoped
   correctly. Not P3's concern.
7. **The script format is authoritatively defined nowhere → P13.**
8. `create_app` (`main.py`) has five unguarded statements after its topology-load `try/except`.
   Flagged for the final whole-branch review.
9. **P2R-01 (Important) → directly relevant to P3.** `routes/stages.py` and `turn_service.py` were
   never migrated to the new exclusive `reserve_version()`; when the new `ArtifactExistsError`
   guard fires, nothing catches it in either caller. P3 owns `routes/stages.py` — check whether
   your own tasks close this or whether it needs its own task.
10. 19 more P2R findings (`P2R-02` through `P2R-20`, minus `01`) — none name P3 specifically; see
    `docs/superpowers/plans/remediation/P2-artifact-durability.md` §7a if any surface during this
    session's own work.
11. 15 P10R findings, filed in `docs/superpowers/plans/remediation/P10-roster.md` §9 — none name
    P3; unrelated files.
12. **6 P11-filed findings** (T6R-01, T6R-02, T11R-01 — already fixed, T18R-01, T19R-01, T20R-01) —
    see "NEW since the P10 resume prompt" above. Only the app-suite `test_gates.py` regression
    (part of Handoff H1b, folded from T21R-01) is P3's to act on; the rest are informational.

## The decisions that are NOT yours

- **T21R-01 (P11) — accept/reject/mitigate the `CLOSE`/`MACRO` object-count exemption in Gate C.**
  Not P3's file, but P3 must still fix the `test_gates.py` regression it caused (Handoff H1b) —
  fixing the *symptom* in P3's own test file doesn't require settling the *policy* question, which
  belongs to whoever ends up owning `scripts/lint_prompt_sheet.py`'s future.
- **T6R-02 (P11) — what, if anything, should catch an extra fenced example block mid-sheet.** Not
  P3's file at all.
- **Should label-first sub-beats (`mechanism: (11–18s | 19 words)`) become legal?** This is
  genuinely unresolved and was already flagged as a live discrepancy going into the *previous*
  session (P11): P12's own plan text (T1b) treats it as already decided and rejected, but an
  earlier resume prompt's understanding treated it as pending, filed in P13. **P11's session did
  not touch P12 or resolve this — it is exactly as unresolved now as it was two sessions ago.**
  When P12 is eventually reached, resolve this explicitly with the operator rather than trusting
  either plan's framing silently — this is the second time this exact discrepancy has been noted
  without being settled.
- **P3's own Open Decision D1** (in its plan text): whether the hand-edit call site should flip to
  `approved_only=True`, closing A-32. The plan explicitly declines to decide this itself and keeps
  the default `False` — routed to A-32's owner. Confirm with the operator if your own pre-review
  surfaces this as blocking anything.
- **P7 §6 C1** adds a per-platform `BRIGHTDATA_MAX_ITEMS_<PLATFORM>` override — the only change in
  the programme that can increase spend. Not P3's concern.
- **Any plan-mandated finding that is a genuine instance of the recurring defect class does not get
  escalated** — fix it as part of the normal task loop. Escalate only genuine product/policy
  choices, the way T21R-01 and T6R-02 above were escalated rather than silently resolved.

## Context discipline — a hard rule

Never give a subagent the audit, another package's plan, or this whole brief. Generate a task brief
extracting the task's own section text (P3's headings are `### T<N> — ...`, matching P11's own
shape — if the packaged `task-brief` script expects `### Task N` and fails, that's expected; P10
and P11 both hit this and extracted briefs by hand instead, matching the plan's actual heading
convention). Subagent replies must be 8 lines or fewer; full reports go to files in that package's
own SDD workspace (`.superpowers/sdd/P3-gates-approval/`).

Review packages come from the skill's `scripts/review-package <plan> <BASE> <HEAD>`. BASE is the
commit recorded *before* dispatching the implementer — never `HEAD~1`.

## Definition of done (the whole programme, not this session)

1. All 328 findings closed — each verified by the mechanism its plan names. **90 of 328 done as of
   this update.** Plus every filed-but-unfixed finding (P2R's 20, P10R's 15, P11's 6) routed to and
   closed by whichever package ends up owning it.
2. Both suites green: `python -m pytest tests/ -q` and, from `pipeline-app/`, `python -m
   pytest -q`. Currently: root suite 355/1/0 (1 documented, filed exception — T6R-02); app suite
   1093/33/3 (32 documented pre-existing + 1 from P11, both explained above).
3. CI exists (3 jobs) and is green — currently red on `root-suite`/`app-suite` for the documented
   reasons above; this has been the accepted state since P2 and gets resolved incrementally as
   each remaining package adopts P2's frozen API and P11's own filed gaps get routed and closed.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error events row.
6. Gate C rejects a malformed shot heading — **done, shipped in P11**, verified end to end by
   direct execution during that session's final review.
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing.
</content>
