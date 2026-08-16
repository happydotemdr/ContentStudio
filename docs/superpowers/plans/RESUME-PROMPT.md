# Resume prompt — audit-remediation programme, start P5 (Wave B3, second half)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-16. **P4 (Pipeline Skill Handoffs) is merged into `main`**
([PR #37](https://github.com/happydotemdr/ContentStudio/pull/37), merge commit `03e40de`).
Combined with P0, P1, P2, P3, P10, P11, P12 already in `main`, **Wave B3's first half (P4) is
done. Wave B3's second half (P5) is next — start P5 now.**

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
P5 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

**Start P5 in a fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not
reuse P4's worktree/branch (`worktree-pipeline-audit-p4`), which is now fully merged and should be
left alone (its own PR is closed; its SDD workspace has been deleted, its git history survives in
`main`'s log). `origin/main` at merge commit `03e40de` already contains every fix P4 landed. Note
`origin/main` has since moved past that merge commit again — an unrelated feature
(`brand-scoped-discovery-email`, [PR #36](https://github.com/happydotemdr/ContentStudio/pull/36))
landed on top of it, outside this audit programme entirely; it touches `discovery_notify.py`,
`email_render.py` (new), `routes/discovery.py`, `schema.sql`, `db.py`, and their tests — none of
which P5 owns or should touch, but it does mean the app suite's passing count has grown again for
reasons unrelated to remediation work (see baseline below).

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed
editable) had real uncommitted operator work in progress as of the P4 session start — re-run the
fetch+status check yourself at the start of your session (`cd C:\Projects\ContentStudio && git
fetch origin main && git status --short && git log --oneline -3`) to see its current state before
assuming anything about it; **do not `git pull`/`merge`/`reset` there yourself** — ask the operator
rather than acting on it. Note: from inside a worktree-isolated session, you cannot `cd` out to the
main checkout at all (the harness refuses it) — if you need to inspect main-checkout state, ask the
operator to run the check, or accept you cannot verify it directly this session.

**Baseline suite counts, verified this session at `origin/main`'s `03e40de` (P4 merged) plus
PR #36's unrelated commits on top:**
- Root suite (`python -m pytest tests/ -q` from repo root): **445 passed, 1 failed, 1 skipped** —
  the same documented, deliberately-deferred pre-existing exception as every prior session
  (`test_lint_prompt_sheet.py::test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[fenced-heading]`,
  unowned by P4 or P5). The passed count has fluctuated slightly session to session (446 vs 445,
  1 skipped either present or absent) — this looks like it may be test-order or environment
  sensitive; it has never affected the one documented failure itself. Re-verify the count yourself
  rather than trusting either number as gospel.
- App suite (`cd pipeline-app && python -m pytest -q`): **31 failed, 1328 passed, 3 skipped.** All
  31 failures are the SAME pre-existing failures every resume prompt since P3 has documented (by
  test name, not just count) — `write_pointer()` missing a required `repo_root` argument in test
  setup code across `test_approval_service.py` (6), `test_browse_service.py` (12),
  `test_discovery_digest.py` (2), `test_routes_browse.py` (7), `test_routes_stages.py` (3), plus one
  unrelated `AttributeError` on a removed `grounding_service.identify_new_brief` function in
  `tests/integration/test_stubbed_cli_e2e.py` (1). **P5 does not own or need to fix these.** The
  passed count (1328) is higher than P4's own final count (1294) purely because of PR #36's
  unrelated new tests landing on top — not because anything in the remediation programme changed.

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | **merged** |
| B1 | P2, then P10 | **merged** |
| B2 | P3 + P11 + P12 together | **merged** |
| B3 | P4, then **P5** | P4 **merged**. **P5 has not started — start it now.** |
| B4 | P6, P7, then P8, and P9 | not started |
| B5 | P15 | not started |
| C | P13, then P14 | not started |

**Why P5 is next, precisely:** the master plan's wave table
(`docs/superpowers/plans/2026-08-08-audit-remediation.md`, search "Wave B3") puts P5 immediately
after P4 in the same wave — "P5 swaps its private `stage_id_by_skill` copy for P4's at its T19."
P5 is explicitly **not blocked** on P4 (its own plan says so, §6, "Sequencing") — it built a
private, identically-shaped `_stage_id_by_skill`/`_template_path` pair as a placeholder and only
its own T19 needs P4's shipped version. **That handoff is now fully satisfied — confirmed live in
the repo this session**, not just claimed: `pipeline_config.stage_id_by_skill(stage_defs) ->
dict[str, str]` and `pipeline_config.stage_template_path(repo_root, stage_id) -> Path` both exist
in `pipeline-app/pipeline_app/pipeline_config.py` with the exact signatures P5's §6 contract
describes, and `_validate_topology` already rejects two stages declaring the same `skill:` (the
exact wording P5's contract asked for). **Re-confirm this yourself before trusting it** — grep
`pipeline_config.py` for `def stage_id_by_skill` and `def stage_template_path` — this whole
document's discipline is "verify, don't inherit."

## What P5 is — read `docs/superpowers/plans/remediation/P5-skills-editor.md` in full before dispatching Task 1

**Do not act from this summary alone** — it is oriented for triage, not execution, and the plan
file is long (1828 lines). Read the actual plan file yourself, following this programme's
Sub-agent output contract (never hand a sub-agent the whole plan file — extract only what each
task needs, same discipline every prior package used).

**The question P5 answers:** does the in-app skill/kickoff-template editor actually protect what
it edits? No. `save_skill`'s `if`/`elif` has no `else` and an unconditional 303 redirect — a save
that wrote nothing returns the identical response to a save that wrote everything. A blank textarea
truncates a `SKILL.md` to zero bytes and reports success. A hand-maintained `STAGE_ID_BY_SKILL`
dict had already drifted from `pipeline.yaml` (missing `shorts-styleboard` entirely) before this
audit even started. Kickoff-template saves were never committed to git at all, while `SKILL.md`
saves were — the same UI offering two silently different durability guarantees. Git commits ran
with no timeout, no branch guard (a web save could land straight on `main`), and staged the entire
index rather than the one file being edited.

**The archetype this package exists to kill** (quoted directly from the plan, §1): every write path
gets a distinguishability test — the wire response for "wrote and committed," "wrote but did not
commit," and "wrote nothing" must be three observably different things, not one 303.

**Scope — files owned by this package, no other package may touch them:**
```
pipeline-app/pipeline_app/routes/skills.py
pipeline-app/pipeline_app/git_helper.py
pipeline-app/pipeline_app/routes/projects.py
pipeline-app/pipeline_app/project_service.py
pipeline-app/pipeline_app/routes/inspector.py
pipeline-app/tests/test_routes_skills.py
pipeline-app/tests/test_routes_projects.py
pipeline-app/tests/test_project_service.py
pipeline-app/tests/test_git_helper.py
pipeline-app/tests/test_routes_inspector.py
```

**`routes/inspector.py` carries none of the 15 findings** and its error handling is already the
shape this audit wants everywhere — treat it as a reference implementation, do not touch it beyond
its one assigned task (T20, below). Do not invent findings for it.

**Files this package reads but must NOT edit** (owned elsewhere — a change there is a merge
collision): `pipeline_app/db.py` and `pipeline_app/schema.sql` (P1), `pipeline_app/obs.py` (P1),
`pipeline_app/pipeline_config.py` and `pipeline.yaml` (P4 — **read-only for P5**, the contract
above is already shipped, do not modify P4's files to "fix" anything), `pipeline_app/templates/**`
and `browse_service.py` (P15), `.claude/skills/**` (P13).

**Repo-wide rule adopted here (orchestrator ruling on D-47, already established by P3):** `| safe`
means "sanitized by its producer." P5's T20 imports `browse_service.sanitize_html(html: str) ->
str` from P15's file and calls it at `routes/inspector.py:45` — **do not write a template-side
filter**, and do not vendor a copy of the sanitizer. **Confirm `browse_service.sanitize_html`
actually exists before dispatching T20** — the P4 resume prompt noted it did NOT exist yet as of
P4's kickoff (P3 had written its own private sanitizer as a stopgap); check whether P15 has landed
by the time you reach T20. If it hasn't, T20 is genuinely blocked and should be sequenced last
(the plan already says so) rather than worked around.

**Findings closed here (15):** A-48, A-49, A-50, A-51, A-52, A-53, A-54, A-55, A-56, A-78, A-79,
D-49, D-50, D-51, F-21 — see the plan's own §2 finding→task map for the full breakdown.

**Tasks, in the plan's own order (20 total, T1-T20):**
1. **T1** — fixture groundwork: replace `test_routes_skills.py`'s `client` fixture (currently
   `stages: []`, so no skill maps to a stage and the styleboard defect is unreachable) with a real
   three-stage topology and a working, non-default-branch git repo. Also updates
   `test_git_helper.py`'s `repo` fixture the same way. **Must land first or every later task's
   tests fail for the wrong reason.**
2. **T2** — A-48 fault: derive `_stage_id_by_skill` from the loaded topology instead of a
   hand-maintained dict (which had already lost `shorts-styleboard`). This is the private copy
   T19 later deletes in favor of P4's shipped `stage_id_by_skill`.
3. **T3** — A-48 distinguishability: three states that currently render as the same empty
   textarea — "skill has no stage," "skill has a stage but the template file is absent," and "the
   template file exists and is genuinely empty" — become three distinguishable context values.
4. **T4** — A-49, **the archetype task**: an unknown save `target` must 400, not 303. Restructures
   `save_skill` so the redirect is reachable only through a real write.
5. **T5** — A-50: never write `stage_templates/None.md` for a skill with no bound stage.
6. **T6-T8** — A-51 (fault/surfacing): a blank body must never truncate a file; a `SKILL.md` save
   must produce loadable frontmatter (name+description present, valid YAML) or be rejected; an
   editor opened on a missing `SKILL.md` says so instead of rendering an empty box.
7. **T9** — A-55: browser `<textarea>` CRLF submission, combined with `write_text`'s newline
   translation, was doubling carriage returns on Windows (`\r\r\n`) — every save became a
   whole-file diff. Normalize before writing.
8. **T10** — A-53/D-49: `git commit -m msg` carried no pathspec, so an operator's unrelated staged
   work was swept into a "skill edit" commit, and the emptiness check (`git diff --cached --quiet`)
   was index-wide rather than scoped to the one file being saved. Introduces the `CommitResult`
   dataclass (`status: committed|no_change|refused_protected_branch|failed`) that T11-T14 build on.
9. **T11** — A-56: `is_dir()` follows symlinks, so a symlinked directory placed in
   `.claude/skills/` joined the discovered set and the save route wrote through it to wherever it
   pointed, outside the repo included. Exclude symlinked entries from discovery.
10. **T12** — D-50: every `git` subprocess call gets a 15-second timeout; a timeout or a missing
    `git` binary is reported as a `CommitResult(status="failed")`, never an unhandled exception or
    an indefinite hang.
11. **T13** — A-54/D-51: a git failure warns and redirects with the file already saved, it does not
    500 a save that in fact succeeded. Adds a protected-branch guard (`main`/`master` refuse to
    commit — the file still saves, git just declines) and pins app-authored commits to a fixed
    `pipeline-app <noreply@localhost>` identity, distinguishable from hand-authored history.
12. **T14** — A-52 + F-21: kickoff-template saves are committed exactly like `SKILL.md` saves (they
    previously weren't — the same UI offered two different durability guarantees). **Inverts**
    `test_save_kickoff_template_does_not_commit`, a test that pinned the missing-commit defect as
    the requirement with no rationale given, and replaces a tautological
    `assert len(calls) == 1` test with one asserting the real, observable git effect.
13. **T15** — the shared surfacing task (per-route `obs.log`/`obs.record_event` calls threaded
    through all the above).
14. **T16-T18** — A-78 (project creation commits the project row before its stage rows/directories
    exist, so a crash mid-creation leaves a partial, permanently-broken project visible in the UI)
    and A-79 (a slug collision surfaces as a 500 instead of a handled conflict).
15. **T19** — **the P4 handoff swap**: delete `_stage_id_by_skill` and `_template_path` from
    `routes/skills.py`; import `stage_id_by_skill` and `stage_template_path` from
    `pipeline_app.pipeline_config` instead. **Confirmed unblocked**, see above — re-verify before
    dispatching, same discipline as every other cross-package swap this programme has done.
16. **T20** — the repo-wide `| safe` producer-side sanitization rule (D-47, owned by P3/P15),
    applied to `routes/inspector.py:45`, the one producer site living in a P5 file. **Blocked on
    P15's `browse_service.sanitize_html` existing** — sequence last, confirm it exists before
    dispatching (see above).

**Suite:** `cd pipeline-app && python -m pytest` (app rootdir) — **app suite only**, per the plan's
own header. P5 touches no root-suite files.

**Dependency on P0:** `tests/test_git_helper.py` shells out to real `git`. If P0's subprocess-guard
conftest fixture is active (it should be, P0 merged long ago), that module needs
`pytestmark = pytest.mark.allow_subprocess` at module level — T1 adds it and it must never be
removed.

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this, and P4 alone hit it **eleven
times** across its 20 tasks (T2, T3, T5, T6, T7, T9, T10, T11, T13, T16, T17, T18 all needed a
plan-text amendment before or during dispatch) — the highest rate of any package so far, likely
because P4's own tasks built on each other so tightly that later tasks' shown code assumed earlier
tasks would leave behind fixtures/helpers that the plan text described but had never actually been
written yet. **A task's own shown test/implementation code can reference a function, class,
fixture, or sibling-package API that doesn't exist yet at the point that task is dispatched, or that
exists but behaves differently than the plan assumes.** The mitigation, unchanged since P2, with two
new sub-lessons from P4:

1. **Grep for every symbol a task's own shown code references** before dispatching it — function
   names, class names, fixture names, other packages' modules — and confirm each either already
   exists live, or is defined within that same task's own text.
2. If something's missing: **amend the plan file FIRST**, as a `>` blockquote note inserted
   directly at the relevant task, **with its own commit** explaining what was wrong and why —
   then dispatch the corrected version. Never fix a gap silently inline without amending the plan.
3. Your own amendments can contain the same class of bug — re-verify their own claims (exact line
   numbers, exact counts, exact function signatures) against the live repo before committing them.
   **P4's own T17 amendment needed a second amendment** (from its implementer, not caught by the
   controller) because the corrected error-message text still didn't match what an earlier test
   asserted — a bug inside a bug-fix. Nobody's amendment is safe from this; the implementer and
   reviewer layers exist precisely to catch what the orchestrator's own fix missed.
4. **A sibling package's return type can carry richer semantics than its signature alone reveals.**
   P4's T17 assumed `gates.resolve_upstream_by_stage(...)` returned a plain `dict[str, Path]`
   because that's what its type hint suggested; the live class (`gates.UpstreamMap`) is a `dict`
   subclass whose `__contains__`/`__getitem__`/`get` are overridden to RAISE on a specific key
   state (an "excluded" key — present on disk but filtered out) rather than behaving like an
   ordinary dict. The plan's own shown code (`dep_id not in resolved`) would have crashed the first
   time it hit that state. **Read a sibling package's actual class definition, not just the
   function signature you're calling** — a docstring one level up ("returns `UpstreamMap`, not a
   bare dict") was the only clue, and it was easy to skim past.
5. **A later task can quietly widen what an earlier task's error-handling already covers.** P4's
   own final whole-branch review found a Critical: T4 added `StrictUndefined` template rendering
   (a real, intended-loud failure mode — an operator typo in an edited kickoff template must raise,
   not render empty) inside a code region T5 had NOT wrapped in abort-and-restore protection, because
   at the time T5 wrote that protection, nothing in that region could raise yet. Neither task's own
   review caught it — each was individually correct against its own diff. **Only the final
   whole-branch review, reading the FULL cumulative function, saw the seam.** Do not skip or shorten
   the final review on the theory that every task passed its own review; the seams between tasks are
   exactly what per-task review cannot see by construction.
6. **Verify empirically before writing a brief, not after a fix-loop round.** P4's session found this
   repeatedly cheaper than it sounds — a standalone Python scratch check (confirming `obs.log`
   writes bare JSON to stderr, not through Python's `logging` module, so `caplog` can't see it;
   confirming `write_pointer` requires its target file to already exist; confirming a conformance
   test's AST-walking logic actually goes red against the shipped defect before trusting it as a
   guard) caught real gaps before dispatch, cheaper than a fix round would have been.
7. **A mandatory final whole-branch review is not the last line of defense against everything — CI
   on a genuinely different machine is.** Watch the PR's CI checks after pushing, not just your own
   local suite runs, even when the final review came back clean.

**P5-specific things worth grepping for before you start**, since this resume prompt could not
verify everything (it wrote to disk before dispatching any P5 task):
- `pipeline-app/pipeline_app/routes/skills.py`'s current `STAGE_ID_BY_SKILL` and `save_skill` —
  the plan's T2/T4 snippets assume specific current shapes; read the live file before trusting any
  quoted line number, especially since P5 has not started and this file is exactly as broken as the
  audit found it.
- `pipeline-app/pipeline_app/pipeline_config.py`'s live `stage_id_by_skill`/`stage_template_path` —
  confirmed shipped this session (see above), but confirm the EXACT signatures again yourself before
  T19, since that's the one task in this whole package whose correctness depends on another
  package's file.
- `pipeline_app/browse_service.py` — does `sanitize_html(html: str) -> str` exist yet? T20 is
  blocked without it (see above). If P15 (Wave B5, after P5 in the landing order) genuinely hasn't
  started, T20 is legitimately not executable yet — sequence it last and consider parking it rather
  than inventing a workaround.
- `pipeline-app/pipeline_app/project_service.py`'s current `create_project`/stage-row creation flow
  — T16-T18's A-78/A-79 fixes assume a specific current shape (`db_mod.create_project` and
  `db_mod.create_stage_row` each commit per row, per P1's `db.py`). Confirm this is still how `db.py`
  behaves before trusting the plan's characterization — P1 merged a long time ago and nothing in
  this programme has touched `db.py`'s commit behavior since, but verify rather than assume.

## Frozen cross-package interfaces (updated for P5)

- `obs.log(event, *, level, **fields)` and `obs.record_event(conn, *, kind, severity, source,
  message, detail, run_id) -> int`. `record_event` must never raise.
- **`pipeline_config.stage_id_by_skill(stage_defs) -> dict[str, str]` and
  `pipeline_config.stage_template_path(repo_root, stage_id) -> Path`** — P4's shipped contract to
  P5, confirmed live this session. `_validate_topology` also now rejects two stages declaring the
  same `skill:`.
- **`gates.resolve_upstream_by_stage(*, repo_root=None, approved_only=False,
  include_optional=False)` returns a `gates.UpstreamMap`** (a `dict` subclass, not a bare dict) with
  three states — absent/present/excluded — where reading (`in`, `[]`, `.get()`) an excluded key
  RAISES `gates.UpstreamExcludedError`. A `.state_of(key) -> "resolved"|"excluded"|"absent"` method
  exists specifically so callers can inspect the state without triggering the raise. Not directly
  P5's concern (P5 doesn't call this function), but noted here since it's exactly the kind of
  "richer-than-the-signature-suggests" contract the lesson above warns about, and future packages
  touching `gates.py`-adjacent code should know it exists.
- `| safe` means "sanitized by its producer." **Still not confirmed to exist as of this session** —
  `browse_service.sanitize_html` is P15's deliverable (Wave B5, after P5). Check before T20.
- **P3 → P15 stage context keys** (live, confirmed by P3's own final review, unchanged by P4):
  `gate_view[]`, `has_blocking_gate`, `gate_override`/`gate_overrides[]`, `artifact_version`,
  `artifact_created_at`, `artifact_finalized_at`, `inputs[]`, `edit_*`, `error_banner`,
  `non_blocking_kinds` (added by P12's final-review fix wave). Not P5's concern unless P5's own work
  touches `routes/stages.py`'s stage context builder, which it should not (that file is not in P5's
  owned list).
- **P1 → P15:** `recent_events[]` and `orphaned_count: int | None`, `None` must render differently
  from `0`.
- **P4 delivered on both things P3 had deferred to it**: `turn_service.propagate_staleness` now
  takes an optional `repo_root=` keyword, and `turn_service.propagate_grounding_staleness` now
  exists. Not P5's concern.
- **P5 owes P4 nothing new** — P4's own contract to P5 (`stage_id_by_skill`, `stage_template_path`,
  duplicate-skill rejection) is the only cross-package dependency in either direction for this pair,
  and it's already satisfied.

## Carried-forward open items (none are P5's job; know they exist)

Two operator decisions remain open, unresolved, not any package's call — surface them again if the
operator hasn't weighed in (repeated in every resume prompt since P10/P11):

1. `T21R-01` — the `CLOSE`/`MACRO` 1-object-floor carve-out in Gate C's C8 check (P11's file).
2. `T6R-02` — what should catch an extra fenced example block mid-sheet (the one documented
   root-suite exception, `test_lint_prompt_sheet.py::...[fenced-heading]`, unchanged for many
   sessions now, confirmed still present and still out-of-scope for every package including P4).

From P3's final review (unchanged, still open, not P5's job unless a P5 task happens to touch the
exact same lines):

3. Nine test failures in files P3 owns (`test_routes_stages.py` x3, `test_approval_service.py`
   x6) assert a pre-P2 API shape.
4. A scratch-file interleaving hazard in `routes/stages.py`'s hand-edit route.
5. Gate messages on that same hand-edit path name the scratch filename instead of a stable display
   name.
6. Eight further Minor findings from P3's final review — full list in PR #32's body.
7. New CSS classes (`status-blocking`, `status-ok`, `input-missing`, `input-malformed`) introduced
   by P3's final-review fix wave still have no stylesheet rules.

From P12's final review (still open, not P5's job): nine Minor findings — full list in
[PR #34](https://github.com/happydotemdr/ContentStudio/pull/34)'s body.

**From P4's final review (still open, not P5's job unless a P5 task happens to touch the exact same
lines — full list in [PR #37](https://github.com/happydotemdr/ContentStudio/pull/37)'s body):**

8. `turn_service._resume_failed`'s `(not events)` branch (a fully-empty collected-events list) has
   no test exercising it — defensive code, correctly implemented, just untested.
9. A stale docstring comment on `test_disconnected_turn_is_marked_aborted_not_left_running` still
   describes the OLD artifact-derived recovery logic instead of the current prior-status-restore
   logic; the test's assertion itself is correct, only the comment is outdated.
10. `routes/stages.py`'s hand-edit path (owned by P3, not P4 or P5) still calls
    `gates.resolve_upstream_by_stage(...)` and `propagate_staleness(...)` without the three-keyword
    widening / `repo_root=` P4 shipped — meaning A-14 and A-32 are only closed on the turn (chat)
    path, not the hand-edit path. P4's plan flagged this as informational for P3; the final review
    recommended promoting it to an explicit blocking handoff. **Not P5's job**, but worth knowing if
    a future package revisits `routes/stages.py`.
11. `pipeline-app/pipeline_app/main.py:161` calls `load_topology(repo_root / "pipeline.yaml")`
    without an explicit `repo_root=` kwarg. Correct today (the derived parent equals the real repo
    root, and P4's own T13 verification catches a wrong derivation loudly if that ever changes), but
    passing it explicitly would close the loop entirely. One-line fix, not urgent, not P5's file.

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
  ahead of yours). **P5's own T1/T10-T14 shell out to real `git` directly, not `bash`** — this trap
  is about `bash`/`sh` specifically and should not apply to P5's git subprocess calls, but the
  general lesson (a test that fakes an external command via PATH shadowing can behave differently
  on GitHub's hosted runner than on the local dev machine) is worth keeping in mind for any of
  T10-T14's git-subprocess tests.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead of an inline heredoc.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field from a filename or frontmatter value.
- In this specific harness, the Bash tool's working directory can drift between calls depending on
  prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command
  fails with an unexpected "no such file or directory" on a path you expect to exist. **Also: this
  harness refuses `cd`s out of a worktree-isolated session's own worktree entirely** — do not
  attempt to inspect the main checkout's state directly from inside a worktree session.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()`
  (not `.fullmatch()`), will silently never capture the optional group.
- When two independently-written pieces of text/code both need to find something via a
  first-occurrence string match, and one can textually contain what the other searches for, they
  will collide.
- A hand-written HTML sanitizer built on `html.parser.HTMLParser` must escape TEXT NODES
  (`handle_data`), not just attribute values — `convert_charrefs=True` hands `handle_data` already
  entity-DECODED text. `HTMLParser.CDATA_CONTENT_ELEMENTS` is `("script", "style")`, not just
  `"script"`. **Directly relevant to P5's own T20** if P5 ends up writing anything sanitizer-adjacent
  rather than purely consuming P15's `sanitize_html` — but the plan's own instruction is to consume,
  not reimplement, so this should stay purely informational.
- A `dict` subclass can override `__contains__`/`__getitem__`/`get` to raise on a specific key
  state rather than behaving like an ordinary dict — check a sibling package's actual class
  definition before assuming standard dict semantics from a type hint alone (see "The recurring bug
  class," point 4, above).
- **A later task can quietly widen what an earlier task's exception-handling already covers** — a
  code region one task wrapped in error-handling because nothing inside it could raise yet can
  become unsafe once a LATER task adds a new raising code path into that same region. Only a final
  whole-branch review reading the cumulative function tends to catch this (see "The recurring bug
  class," point 5, above).
- **A plan's own execution-order assumption can be wrong even when nothing about the CODE has
  changed** — grepping the live repo or writing a two-line empirical check before dispatch remains
  cheaper than a fix round, every time this programme has measured it.
- **A mandatory final whole-branch review has found real issues in every package executed so far
  without exception** — P3: 2 Critical + 3 Important; P10: 15; P11: 6; P12: 0 Critical + 5 Important
  (plus 2 CI-only failures); P4: 1 Critical + 2 Important + 4 Minor (a kickoff-render failure could
  permanently wedge the app's single-flight lock — see above). Do not skip it, do not shorten it,
  do not let a clean per-task review record talk you out of dispatching it on the most capable
  available model — and do not consider the package done until you've read its PR's CI logs and
  confirmed the ONLY failures are the same documented pre-existing baseline (1 root + 31 app, by
  test name, not just by count).

## Definition of done (the whole programme, not any one package)

1. All 328 findings closed — each verified by the mechanism its plan names. P3's own 22, P12's own
   16, P4's own 26 (all 20 tasks + the final review's fix wave, confirmed by its own mandatory final
   review, re-reviewed clean) are confirmed closed independently by each package's mandatory final
   review. Count each package's own total from its merged PR, not from memory.
2. Both suites green everywhere they can be: root suite target ~445-446/1 (the one documented
   T6R-02 exception, count fluctuates slightly session to session for reasons not yet diagnosed —
   see baseline above); app suite target keeps the same 31 pre-existing failures until a dedicated
   follow-up closes them (see "Carried-forward open items" above). The passed count on both suites
   will keep climbing as each package adds its own regression tests, and now also from unrelated
   work landing on `main` outside this programme (PR #36) — track failures by name, not the passed
   count, when checking whether a session's work is "the same baseline."
3. CI exists (3 jobs, from P0) — **but is NOT green, and has not been since before P3's merge**,
   confirmed again this session (`gh run list --branch main --limit 3` and the P4 PR's own CI run,
   both independently checked). The cause is exactly the same pre-existing root-suite and app-suite
   failures every resume prompt has documented as deliberately out of scope — the CI job hard-fails
   on any non-zero pytest exit code with no allowance for the documented baseline. This is a real,
   standing gap in the programme's own definition of done, not a P5 concern specifically, but worth
   naming again for whichever session eventually closes the pre-existing failures or decides the CI
   job should tolerate a documented allowlist instead. Re-run `gh run list --branch main --limit 3`
   yourself at session start rather than trusting this note.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error events row.
6. Gate C rejects a malformed shot heading — done, verified end to end.
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing — the F-64 atomic rename is P8's
   task (Wave B4), well after P5. Not something to check for or worry about until P8's turn.
