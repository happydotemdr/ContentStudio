# Resume prompt — audit-remediation programme, start P4 (Wave B3)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-15. **P12 (Gate D & tools) is merged into `main`**
([PR #34](https://github.com/happydotemdr/ContentStudio/pull/34), merge commit `c6b0d96`).
Combined with P0, P1, P2, P3, P10, P11 already in `main`, **Wave B2's tripwire cluster (P3 + P11 +
P12) is now fully complete.** **Wave B3 (P4, then P5) is next — start P4 now.**

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
P4 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

**Start P4 in a fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not
reuse P12's worktree/branch (`claude/pipeline-audit-review-4dd767`), which is now fully merged and
should be left alone (its own PRs are closed; its SDD workspace has been deleted, its git history
survives in `main`'s log). `origin/main` at merge commit `c6b0d96` already contains every fix P12
landed, including two post-review CI fixes (`4117af6`, `c296844`) for a Windows Git-Bash resolution
bug that only reproduced on GitHub's hosted runner, not on the local dev machine — worth knowing
about if a future package's tests ever shell out to `bash` on Windows (see "Traps" below).

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed
editable) had **real uncommitted operator work in progress** as of the P12 session
(`doc-ingest-app/` modifications, untracked `pipeline.db.backup-pre-migration*` files, two
untracked `rgs-briefs/*.md` drafts) — **do not `git pull`/`merge`/`reset` there yourself**. Re-run
the same fetch+status check at the start of your session
(`cd C:\Projects\ContentStudio && git fetch origin main && git status --short && git log --oneline
-3`) to see its current state before assuming anything about it; it may still be behind `main` by
now, with or without the same uncommitted work — ask the operator rather than acting on it.

**Baseline suite counts, verified this session at `origin/main`'s `c6b0d96`:**
- Root suite (`python -m pytest tests/ -q` from repo root): **446 passed, 1 failed** — the same
  documented, deliberately-deferred pre-existing exception as every prior session
  (`test_lint_prompt_sheet.py::test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[fenced-heading]`,
  unowned by P12 or P4). The count rose from 355 (P3's baseline) through 445 (P12's own work) to
  446 (one further CI-fix commit added a regression-guard test after P12's PR was already open).
- App suite (`cd pipeline-app && python -m pytest -q`): **31 failed, 1207 passed, 3 skipped.** All
  31 failures are pre-existing, in files a sibling package (P3) either doesn't fully own or wasn't
  asked to repair — see [PR #32](https://github.com/happydotemdr/ContentStudio/pull/32)'s body for
  the original breakdown (`write_pointer`/`gate_overrides` API-shape mismatches in test setup code
  across `test_routes_stages.py`, `test_approval_service.py`, `test_browse_service.py`,
  `test_routes_browse.py`, plus two unrelated single failures — same 31 test names, unchanged
  since P3 merged). **P4 does not own or need to fix these** — they're a separate, already-filed
  follow-up (see "Carried-forward open items" below).

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | **merged** |
| B1 | P2, then P10 | **merged** |
| B2 | P3 + P11 + P12 together | **merged** |
| **B3** | **P4, then P5** | **P4 has not started — start it now.** |
| B4 | P6, P7, then P8, and P9 | not started |
| B5 | P15 | not started |
| C | P13, then P14 | not started |

**Why P4 is next, precisely:** the master plan's own dependency table
(`docs/superpowers/plans/2026-08-08-audit-remediation.md`, search "P2 lands before P3 and P4" and
the wave table around line 177-195) puts P4 in Wave B3, gated only on P2 and P3 — both merged.
P4's own T17 task carries a "counter-contract back to P3" (three keywords P4 needs from
`gates.py`) — **confirmed the session before this one, live in the repo:
`pipeline_app/gates.py:466` already defines `resolve_upstream_by_stage(run_dir, all_stage_defs,
stage_def, *, repo_root=None, approved_only=False, include_optional=False) -> UpstreamMap`**,
exactly the signature the master plan's frozen-interfaces table (line 194) describes. **Re-confirm
this yourself before trusting it** — it's a one-line grep, and this whole document's discipline is
"verify, don't inherit."

## What P4 is — read `docs/superpowers/plans/remediation/P4-handoff.md` in full before dispatching Task 1

**Do not act from this summary alone** — it is oriented for triage, not execution. Read the actual
plan file yourself, following this programme's Sub-agent output contract (never hand a sub-agent
the whole plan file — extract only what each task needs, same discipline every prior package
used).

**The question P4 answers:** *are the skill handoffs correct?* For seven of nine pipeline stages,
yes. For `assembly` and `repurpose`, no — and the failure ships silently, because the kickoff
templates tell the skill an input is present that the graph (`pipeline.yaml`) cannot actually
deliver. **The verdict: the graph is wrong, not the skills** — `shorts-assembly/SKILL.md:16-29`
and `social-repurpose/SKILL.md:12-13` declare real, corpus-traced input requirements that
`pipeline.yaml` under-declares. P4 fixes `pipeline.yaml` and the kickoff templates; the SKILL.md
prose that must eventually follow is handed to **P13** as a contract, not edited by P4.

**Scope — files owned by this package, no other package may touch them:**
```
pipeline.yaml                                      (REPO ROOT)
pipeline-app/pipeline_app/turn_service.py
pipeline-app/pipeline_app/prompt_builder.py
pipeline-app/pipeline_app/pipeline_config.py
pipeline-app/pipeline_app/cli_runner.py
pipeline-app/stage_templates/*.md                  (all 9)
pipeline-app/tests/test_turn_service.py
pipeline-app/tests/test_cli_runner.py
pipeline-app/tests/test_prompt_builder.py
pipeline-app/tests/test_pipeline_config.py
pipeline-app/tests/test_routes_chat_sse.py
```

**Findings closed here (26):** A-01 through A-17, A-32, A-44, A-46, D-43 through D-46, F-11, F-15
— see the plan's own §2 finding→task map for the full breakdown; it is a real table with every ID
mapped to a task, not a rough correspondence.

**Tasks, in the plan's own order (20 total, T1-T20):**
1. **T1** — declare the missing `pipeline.yaml` edges (`assembly` needs `scripting`+`styleboard`
   as hard deps, `music` as a NEW `optional_depends_on` concept; `repurpose` needs
   `ideation`+`scripting`, not just `assembly`).
2. **T2** — address kickoff-template upstreams by stage id (`inputs['scripting']`), not position;
   deletes the `input_file`/`input_files` mechanism entirely; rewrites all 9 stage templates.
3. **T3** — the highest-value test in the package: a data-driven, AST-parsed conformance test over
   all 9 stages proving every `inputs[...]` a template references is actually reachable via
   `depends_on`/`optional_depends_on`, and every declared dependency is actually named in the
   template. This is the test that makes the whole defect class structurally impossible to
   reintroduce — read it before writing anything else in this package, it defines the contract
   every other task must satisfy.
4. **T4** — `StrictUndefined` + a frozen five-key kickoff context + `validate_template_source` for
   the skill-editor's trial-render path.
5. **T5** — a required dependency with no approved artifact now refuses the turn
   (`MissingUpstreamArtifactError`) instead of rendering the literal string `None` into a prompt.
6. **T6** — upstream resolution now returns the **approved** artifact, not merely the newest
   draft on disk — with a deliberate, documented divergence: staleness computation
   (`_current_upstream_hashes`) keeps comparing against the latest (not approved-only) version, so
   an unapproved re-generation still correctly marks dependents stale.
7. **T7** — a resumed turn is now told, in-prompt, which upstream artifacts changed since the
   session was last opened (was previously silent — the model kept reasoning from stale paths).
8. **T8** — an unresumable Claude session id is now cleared, so the next turn re-renders the
   kickoff prompt instead of wedging the stage forever.
9. **T9** — an aborted turn now restores the *pre-turn* status (stale stays stale) instead of
   always re-deriving `awaiting_review`.
10. **T10-T16** — pointer-aware staleness/upstream resolution for grounding briefs, topology
    validation (`_validate_topology` requiring a kickoff template per stage, brand-scope
    compatibility checks), `StageNotRunnableError` on a `None` stage row, `load_topology`'s
    `repo_root` handling, permission-policy hardening (`D-43` through `D-46` — a `Write,Edit`
    allowlist narrowed to pattern-scoped forms, `scripts/**` and `.claude/**` denied, vendor
    `*_API_KEY` stripped from the child environment), a tautological test deletion + replacement,
    and per-stage prompt-content assertions replacing today's weaker test doubles. Read each in
    the plan file itself — this resume prompt does not reproduce their code.
11. **T17-T20** — four tasks that carry **no P4 finding of their own**, sequenced last so the
    finding work is never blocked on another package's merge:
    - **T17** (P3 Handoff H2): swap P4's inline upstream map for `gates.resolve_upstream_by_stage`
      — **confirmed unblocked**, see above. Re-verify before dispatching.
    - **T18** (P2 §6.1-6.3): adopt the durable `artifacts.py` API P2 already shipped.
    - **T19** (P1, F-26 second half): a gate-result test in `test_turn_service.py` that asserts
      its own mock — P1 already closed the `test_main.py` half of this same finding.
    - **T20** (P5 contract): `stage_id_by_skill`, `stage_template_path`, and the duplicate-`skill:`
      rejection rule — P5 (next in this same wave) swaps its own private copy for this one.

**Suite:** `cd pipeline-app && python -m pytest` (app rootdir). **Never from the repo root** — P4
touches no root-suite files at all (everything it owns lives under `pipeline-app/` or is
`pipeline.yaml` at repo root, which the app suite reads via `REPO_ROOT`, not the root pytest
suite).

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this, and P3 alone hit five, P12
hit at least seven (five in-package plus one whole-package sequencing swap plus one carried-forward
from its own resume brief): **a task's own shown test/implementation code can reference a
function, class, fixture, or sibling-package API that doesn't exist yet at the point that task is
dispatched** — because the plan text was written assuming a landing order, a sibling package's
state, or another task's sequencing that turned out different from what's actually true in the live
repo by the time you get there. The mitigation, unchanged since P2:

1. **Grep for every symbol a task's own shown code references** before dispatching it — function
   names, class names, fixture names, other packages' modules — and confirm each either already
   exists live, or is defined within that same task's own text.
2. If something's missing: **amend the plan file FIRST**, as a `>` blockquote note inserted
   directly at the relevant task, **with its own commit** explaining what was wrong and why —
   then dispatch the corrected version. Never fix a gap silently inline without amending the plan.
3. Your own amendments can contain the same class of bug — re-verify their own claims (exact line
   numbers, exact counts, exact function signatures) against the live repo before committing them.
4. **Verify empirically before writing a brief, not after a fix-loop round.** P12's session found
   this is cheaper than it sounds: several of P12's own amendments (a broken test filename that
   didn't match the target regex, a mutation-matrix row whose direction was backwards, a sub-beat
   fixture's actual parse behavior) were caught by running a two-line Python scratch check BEFORE
   dispatching the implementer, not after a reviewer caught it. When a brief's own code references
   something you can trivially execute or grep for, do it — it's cheaper than a fix round.
5. **A mandatory final whole-branch review is not the last line of defense against everything —
   CI on a genuinely different machine is.** P12's own final review and every per-task review
   passed two tests that then failed on GitHub's hosted Windows runner (a Git-Bash resolution
   quirk invisible on the local dev box — see "Traps" below). If a task's tests shell out to any
   external binary, do not treat "it passed locally, including under the final review" as proof it
   will pass in CI. Watch the PR's CI checks after pushing, not just your own local suite runs.

**P4-specific things worth grepping for before you start**, since this resume prompt could not
verify everything (it wrote to disk before dispatching any P4 task):
- `pipeline-app/pipeline_app/pipeline_config.py`'s current `StageDef` dataclass — does it already
  have anything resembling `optional_depends_on` from some other package's incidental touch? Grep
  before T1 assumes a clean slate.
- `pipeline-app/pipeline_app/turn_service.py`'s current `run_stage_turn` — the plan's T5/T6/T7/T8
  snippets all assume specific line ranges and existing helper shapes (`_resolve_upstream`,
  `is_first_turn`, the exception hierarchy). Read the live function before trusting any quoted
  line number.
- `pipeline-app/pipeline_app/artifacts.py` — P2 already shipped `compute_depends_on`,
  `read_artifact`/`MalformedArtifactError`, `reserve_version`/`write_reserved_artifact`/
  `release_version`, `record_gate_override(at=)`, `write_pointer(repo_root)`,
  `classify_brief_change` (master plan's frozen-interfaces table, line 193). Confirm these exist
  with the exact signatures P4's T18 expects before dispatching that task.
- `.claude/skills/shorts-assembly/SKILL.md` and `.claude/skills/social-repurpose/SKILL.md` —
  P4's whole premise rests on lines 16-29 and 12-13 respectively still saying what the plan quotes.
  These are P13's files to eventually edit, but P4 only READS them — confirm the cited line ranges
  still say what P4's plan claims before trusting the finding narrative.

## Frozen cross-package interfaces (updated for P4)

- `obs.log(event, *, level, **fields)` and `obs.record_event(conn, *, kind, severity, source,
  message, detail, run_id) -> int`. `record_event` must never raise.
- `gates.resolve_upstream_by_stage(*, repo_root=None, approved_only=False,
  include_optional=False)` returns an `UpstreamMap` with three states — absent/present/excluded —
  where reading an excluded key raises. **Confirmed live in the repo** (see above) — P4's T17 can
  consume it directly.
- `| safe` means "sanitized by its producer." P3 wrote its own private sanitizer in
  `routes/stages.py` (a HANDOFF, since the intended owner, P15, hasn't executed) — do not assume
  `browse_service.sanitize_html` exists; it still doesn't.
- **P3 → P15 stage context keys** (live, confirmed by P3's own final review): `gate_view[]`
  (`state ∈ passed|failed|errored|never_ran|unknown|malformed`), `has_blocking_gate`,
  `gate_override`/`gate_overrides[]`, `artifact_version`, `artifact_created_at`,
  `artifact_finalized_at`, `inputs[]` (`present`/`malformed`/`artifact`/`body`/`html` per declared
  dependency), `edit_allowed`/`edit_blocked_reason`/`edit_action`/`edit_field`, `error_banner`.
  **P12's final-review fix wave added one more key to this same context-building path**:
  `non_blocking_kinds` (sourced from `gates._NON_BLOCKING_KINDS`), threaded into `stage.html`'s
  Gates-panel rendering so the template no longer hardcodes its own copy of the non-blocking `kind`
  set. Not P4's concern, but if P4's own work touches anything in `routes/stages.py`'s stage
  context builder, be aware this key now exists there too.
- **P1 → P15:** `recent_events[]` and `orphaned_count: int | None`, `None` must render differently
  from `0`.
- **P4 is now the sole owner of two things P3 wanted from it**, deferred and documented in
  `P3-gates-approval.md`'s T24 amendment: `turn_service.propagate_staleness` needs an optional
  `repo_root=` keyword, and a `turn_service.propagate_grounding_staleness` function doesn't exist
  yet. **This is squarely P4's own scope** (T10-T14 territory) — resolve it as part of this
  package rather than deferring further.
- **P12 → downstream Gate D consumers:** `scripts/lint_script_language.py` now exports
  `NON_BLOCKING_KINDS: frozenset[str]` and `is_blocking(finding) -> bool`. Not P4's concern (P4
  never touches Gate D), noted here only for completeness.

## Carried-forward open items (none are P4's job; know they exist)

Two operator decisions remain open, unresolved, not any package's call — surface them again if the
operator hasn't weighed in (repeated in every resume prompt since P10/P11):

1. `T21R-01` — the `CLOSE`/`MACRO` 1-object-floor carve-out in Gate C's C8 check (P11's file).
2. `T6R-02` — what should catch an extra fenced example block mid-sheet (the one documented
   root-suite exception, `test_lint_prompt_sheet.py::...[fenced-heading]`, unchanged for many
   sessions now, confirmed still present and still out-of-scope for every package including P12).

From P3's final review (unchanged, still open, not P4's job unless a P4 task happens to touch the
exact same lines):

3. Nine test failures in files P3 owns (`test_routes_stages.py` x3, `test_approval_service.py`
   x6) assert a pre-P2 API shape.
4. A scratch-file interleaving hazard in `routes/stages.py`'s hand-edit route (concurrent edits to
   the same stage share one fixed scratch filename).
5. Gate messages on that same hand-edit path name the scratch filename instead of a stable display
   name.
6. Eight further Minor findings from P3's final review — full list in PR #32's body.
7. New CSS classes (`status-blocking`, `status-ok`, `input-missing`, `input-malformed`) introduced
   by P3's final-review fix wave still have no stylesheet rules — correct semantics, missing color.

From P12's final review (still open, not P4's job):

8. Nine Minor findings parked from P12's final whole-branch review — D5's floor message wording
   regression, a missing companion test the plan's own §5 called for, a stale docstring, an
   order-dependent tie-detection edge case, a confounded C-97 test fixture, dead `--check` code in
   `cowork_plugin_lock.py`, a loose-file gap in the plugin content-hash stamp, a pre-existing
   `yaml` import that narrows the "stdlib-only" claim's scope, and a near-trivially-green mtime
   test. Full list in [PR #34](https://github.com/happydotemdr/ContentStudio/pull/34)'s body.
   P12's own SDD workspace has been deleted — the git history (its ledger's every entry) survives
   in `main`'s log via P12's commits and PR #34's body, per this program's standing convention.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`),
  not any worktree. Bake an explicit working-directory check (`pwd && git rev-parse
  --show-toplevel && git branch --show-current`) into every dispatch prompt.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8",
  errors="replace"`.
- **Bash resolution on Windows is genuinely two-layered, both confirmed this programme:**
  1. **Never invoke `bash`/`sh` by BARE NAME** in a `subprocess.run([...])` call, even in test
     code you're writing fresh — a bare `"bash"` string can resolve to a broken WSL launcher stub
     (`C:\Windows\System32\bash.exe`) if that directory precedes Git's own on PATH, and that stub
     fails outright with no working WSL distro required to hit it.
  2. **Even `shutil.which("bash")` is not enough** — which Git-for-Windows `bash.exe` it finds
     matters, not just whether it finds *a* bash. `C:\Program Files\Git\usr\bin\bash.exe` (found
     when Git's `usr/bin` is on PATH, e.g. on a long-lived dev machine) preserves whatever PATH
     you hand its subprocess. `C:\Program Files\Git\bin\bash.exe` (found on a stock install,
     including GitHub's hosted CI runner) is a *wrapper* that PREPENDS `/mingw64/bin:/usr/bin`
     ahead of anything you set — so a test that shims a fake binary onto PATH and expects the
     child bash process to see it first can pass on one machine and silently fail on another,
     with no warning until CI runs on a different machine than whatever wrote the test. P12 hit
     this exact bug in its own final-review fix wave (a fake `git` shim for an isolated build
     test) — passed locally, failed on GitHub's runner, diagnosed and fixed by reproducing the
     failure locally with the PATH forced into the CI shape. **The general lesson: if a test needs
     to fake an external command, don't rely on PATH shadowing surviving into a shelled-out `bash`
     subprocess — either avoid the fake entirely (P12's actual fix: `git init` a real throwaway
     repo instead of faking `git`) or explicitly resolve and reject known-bad values (P12's
     belt-and-braces follow-up: reject a `System32` bash hit explicitly, don't just take whatever
     `which` returns).**
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead of an inline heredoc.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field from a filename or frontmatter value.
- In this specific harness, the Bash tool's working directory can drift between calls depending on
  prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command
  fails with an unexpected "no such file or directory" on a path you expect to exist.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()`
  (not `.fullmatch()`), will silently never capture the optional group.
- When two independently-written pieces of text/code both need to find something via a
  first-occurrence string match, and one can textually contain what the other searches for, they
  will collide.
- A hand-written HTML sanitizer built on `html.parser.HTMLParser` must escape TEXT NODES
  (`handle_data`), not just attribute values — `convert_charrefs=True` hands `handle_data`
  already entity-DECODED text. Also: `HTMLParser.CDATA_CONTENT_ELEMENTS` is `("script", "style")`,
  not just `"script"`. (Only relevant if a future package touches `routes/stages.py`'s sanitizer
  again — unlikely for P4, noted for completeness.)
- **A plan's own execution-order assumption can be wrong even when nothing about the CODE has
  changed** — three separate times in P12, a task's own text assumed either a different task-number
  ordering (T16 needing T17's file), a different execution timing (T2 assuming T7 would run first
  to supply a shared test fixture), or a test fixture that was simply unreachable given how the
  underlying function actually behaves (T11's sequential-write collision tests, defeated by
  `find_latest`'s full-rescan design). None of these were found by reading the plan text alone —
  each required either grepping the live repo or writing a two-line empirical check before
  dispatch. Do this proactively for P4's own T3 (the conformance test) and T17 (the P3 handoff) —
  both are exactly the shape most likely to have quietly drifted.
- **A mandatory final whole-branch review has found real issues in every package executed so
  far without exception** — P3: 2 Critical + 3 Important; P10: 15; P11: 6; P12: 0 Critical + 5
  Important (plus 2 more CI-only failures the final review's own local run couldn't have caught —
  see the bash-resolution trap above). Do not skip it, do not shorten it, do not let a clean
  per-task review record talk you out of dispatching it on the most capable available model — and
  do not consider the package done until you've read its PR's CI logs and confirmed the ONLY
  failures are the same documented pre-existing baseline (1 root + 31 app, by test name, not just
  by count), not just trusted your own local suite runs. CI's overall status has read `failure` on
  every push to `main` since before P3 for exactly that pre-existing-baseline reason (see
  Definition of Done #3) — a red CI check is the norm here, not evidence of a new regression by
  itself, but it also means CI's own pass/fail signal cannot substitute for actually reading which
  tests failed.

## Definition of done (the whole programme, not any one package)

1. All 328 findings closed — each verified by the mechanism its plan names. P3's own 22, P12's own
   16 (15 from its own plan table + C-88b) are confirmed closed independently by each package's
   mandatory final review. Count each package's own total from its merged PR, not from memory.
2. Both suites green everywhere they can be: root suite target 446/1 (the one documented T6R-02
   exception — this number will shift again once P4 lands its own root-suite-adjacent work, though
   P4 owns no root-suite files directly); app suite target keeps the same 31 pre-existing failures
   until a dedicated follow-up closes them (see "Carried-forward open items" #3 above).
3. CI exists (3 jobs, from P0) — **but is NOT green, and has not been since before P3's merge**,
   confirmed this session (`gh run list --branch main --limit 3`): the `tests` workflow's
   `root-suite` and `app-suite` jobs report `failure` on every push to `main` going back through
   PR #32, #33, and #34's merges alike, and only `no-live-credentials` passes. The cause is exactly
   the same 1 pre-existing root-suite failure + 31 pre-existing app-suite failures every resume
   prompt has documented as deliberately out of scope — **but the CI job itself hard-fails on any
   non-zero pytest exit code, with no allowance for that documented baseline**, so the repo's CI
   status has read red for at least three package-merges running. This is a real, standing gap in
   the programme's own definition of done (item 3 has silently never been true), not a P4 concern
   specifically, but worth naming for whichever session eventually closes the 9+31 "carried-forward
   open items" pre-existing failures (see below) or decides the CI job should tolerate a documented
   allowlist instead. Re-run `gh run list --branch main --limit 3` yourself at session start rather
   than trusting this note — it may have changed.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error events row.
6. Gate C rejects a malformed shot heading — done, verified end to end (CLI-side by P11, app-side
   by P3).
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing — the F-64 atomic rename
   (`pipeline-app/scripts/` → `pipeline-app/tools/`) is P8's task (Wave B4), well after P4. Not
   something to check for or worry about until P8's turn.
