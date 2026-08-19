# Resume prompt — P13 kickoff, PR #54 merged

You are resuming a fully-planned, already-validated 328-finding audit-remediation programme (329 as currently tracked — see "Definition of done" below for why). Do not re-plan and do not re-audit.

You are the orchestrator, not the implementor. Give sub-agents only the context they need — never share full context windows back and forth, never hand one the audit or another package's plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation accurate and the plan updated at every step. When you find a new gap or defect, file it in the relevant plan for review/validation before addressing it, and only fix it inline if it is a critical or important blocker. This has happened in every package executed so far — expect it in P13 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation programme).

Start P13 in a fresh worktree off `origin/main` via `superpowers:using-git-worktrees` — do not reuse P15's worktree/branch (`worktree-worktree-p15-ui`, merged and gone) or this session's own docs-followup worktree (`worktree-p15-docs-followup`, also merged and gone by the time you read this). P15 merged as PR #54 (`8893789`). This file and its companion docs-only commits (P15's plan §8 Outcome, the master plan's wave-table/contract/baseline updates, P13's own §0 pre-flight amendment) were written in a follow-up session **after** `8893789` and landed via their own separate PR — run `git log --oneline -5 origin/main -- docs/superpowers/plans/RESUME-PROMPT.md` first thing and confirm a commit rewriting this file for P13 is actually present there before trusting anything below as current; if it isn't, something didn't merge and you're reading a stale copy from somewhere else.

**The orphaned-worktree-directory trap is real and has now hit two consecutive sessions.** A session can start "already inside" a worktree-shaped directory (`.claude/worktrees/<name>`) per its own launch context, while that directory is **not** actually a registered git worktree (`git worktree list` doesn't show it). Symptom: `git rev-parse --show-toplevel` and `git branch --show-current` silently resolve to the main checkout instead of erroring, because git walks up looking for the nearest `.git` when the directory itself has no worktree registration — so ordinary git commands run there quietly operate on the wrong repo state without any error. **Always verify with `git worktree list` and confirm your directory appears in it before trusting `pwd`/`show-toplevel` alone, especially at the very start of a session.** If it doesn't appear, `ExitWorktree` is a no-op (nothing to exit from an unregistered directory) — the fix is `EnterWorktree` with a fresh name, which creates a genuine new worktree and moves the session into it. This is now a standing trap for every future session in this programme, not a one-off — stop re-discovering it and just check first.

If you are already inside a (genuine) worktree session when you start, `EnterWorktree` refuses to create a second one directly — `ExitWorktree` first (`action: "keep"` if the current worktree's branch is not yet merged and you might need it again; `"remove"` only after confirming its branch is merged). Note: `ExitWorktree` with `action: "remove"` has twice now reported "could not remove — kept" while still fully unregistering the worktree from `git worktree list` (confirmed both times by a follow-up `git worktree list` check) — the directory may linger on disk but is inert; do not treat the "could not remove" message as a failure requiring cleanup action.

The harness's worktree-boundary guard blocks `git -C "C:/Projects/ContentStudio" <command>` redirects from inside a worktree-isolated session — this has now held stable across five consecutive sessions (P8, P9, P9-followup, P15, P15-followup), so treat it as permanent rather than re-verifying every time. The guard also rejects some single Bash calls that capture multiple git values via command substitution in one line, or that chain more than one or two commands with `&&`/heredocs — prefer separate single-purpose Bash calls, and prefer the Write tool over Bash heredocs for anything beyond a trivial one-liner.

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed editable) has a **known, unresolved sync question as of this resume prompt**, raised by the human partner and not yet fully diagnosed: `git -C "C:/Projects/ContentStudio" log --oneline -3` showed local `main` one commit **ahead** of `origin/main` —
```
564722d (HEAD -> main) Merge branch 'main' of https://github.com/happydotemdr/ContentStudio
8893789 (origin/main, origin/HEAD) Merge pull request #54 from happydotemdr/worktree-worktree-p15-ui
```
— meaning the main checkout has an unpushed local merge commit (`564722d`) that was never diagnosed further in that session. **Before doing anything else in a fresh session, run `git -C "C:/Projects/ContentStudio" log 8893789..564722d --oneline` (or the equivalent from inside the main checkout directly, not via `-C` from a worktree session — that redirect is blocked, see above) to see what's actually in it, and ask the human partner before pushing or altering it.** The same `git status --short` also showed nine pre-existing untracked files (`.db.backup-*`, two `docs/superpowers/plans/2026-08-1{6,7}-*.md` files, two `rgs-briefs/*.md` files) — carried forward unverified from prior sessions' notes about an unrelated Firecrawl retry/backoff change in `doc-ingest-app/`; do not assume these are safe to touch or safe to ignore without checking what they are.

## Baseline suite counts, verified this session at `8893789` (P15 merged) and re-confirmed at this session's own HEAD

- **Root suite** (`python -m pytest tests/ -q` from repo root): **445 passed, 1 skipped, 0 failed.** Fully green.
- **App suite** (`cd pipeline-app && python -m pytest -q`): **1954 passed, 4 skipped, 2 xfailed, 0 failed.** Fully green — the 2 xfail are P15's own T13, a deliberate, documented, `strict=True` block on P8 landing a `handles` join that doesn't exist yet (see P15's plan §8). Do not treat these two xfails as a P13 problem; P13 touches none of the files involved.
- There is no documented pre-existing-failure baseline to tolerate beyond those two xfails on either suite. Any *new* failure you see is real — treat it as a regression, not "the same old ones."
- **CI** (`gh pr checks 54`, at merge time): green — both triggered runs (branch push + PR event, six check rows total) all `SUCCESS` across `app-suite`/`root-suite`/`no-live-credentials`. Re-verify yourself at session start; don't trust this as gospel across sessions.
- `tests/test_build_cowork_plugin.py`'s two staleness checks (against `.claude/skills/`) are **currently green** at this baseline — re-verified this session, not a pre-existing red. **They are directly relevant to P13 in a way they weren't for prior packages**, since P13 edits `.claude/skills/**` extensively: expect them to go red partway through the package (any skill-file edit staleness-invalidates the build lock) and stay that way until either P13 finishes or someone runs `bash scripts/build-cowork-plugin.sh` to refresh it. If you see this test fail mid-package, that is expected drift from your own edits, not a regression to chase down — but confirm it was actually green before you started, the same way this session did, rather than assuming.

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | merged |
| B1 | P2, then P10 | merged |
| B2 | P3 + P11 + P12 together | merged |
| B3 | P4, then P5 | merged |
| B4 | P6, P7, P8, P9 | all four merged — Wave B4 complete |
| B5 | P15 | **merged this session as PR #54 (`8893789`) — Wave B5 complete** |
| C | **P13, then P14** | **P13 is next — pre-flight checked this session, not yet started** |

**Why P13 is next, precisely:** Wave C's own stated rationale (master plan, search "Wave C") is "Documentation describes the fixed code, or it is fiction again. P14 is last because six packages owe it contract decisions." P13 comes first within Wave C because P14's own plan (§ "Contract for P14," inside P13's file, §6.1) is written as a **request P13 makes of P14** — three specific edits P14 must make to `docs/README.md`/`CLAUDE.md` to resolve a provenance-wording contradiction P13 discovers but cannot fix (it owns neither file). Landing P14 first would mean resolving that contradiction blind.

## What P13 is — read `docs/superpowers/plans/remediation/P13-skills-contracts.md` §0 and §1-2 before dispatching Task 1

Do not act from this summary alone — it is oriented for triage, not execution, and the plan file is long (2366 lines including this session's §0 amendment, 18 tasks). Read the actual plan file yourself — start with §0, the pre-flight amendment written this session, before reading anything else — following this programme's Sub-agent output contract (never hand a sub-agent the whole plan file — extract only what each task needs, same discipline every prior package used).

**P13 is shaped differently from every prior package.** It edits no Python, no Jinja, no CSS. Its entire scope is markdown — 13 skill directories under `.claude/skills/**` (`SKILL.md` + `references/*.md`, ~64 reference files) — plus one test file, `tests/test_skill_provenance.py`, which lives in the **root** suite, not the app suite. Its own intro paragraph states the governing idea: *"add the conformance check, run it, watch it name the real offenders, then edit the markdown until it is green."* Every one of its 18 tasks follows that order. The centre of the package is turning `test_skill_provenance.py` from 6 tests covering 1 skill of 13 (2.0% coverage) into a data-driven suite covering all 13 skills' four structural properties: every declared output field a consumer names actually exists in the producer; every bare `references/x.md` citation resolves inside its own skill; every `§`-anchor citation resolves in the file it points at; every normative block carries a marker or a recorded triage exemption. That suite, once built, is what stops all 48 findings recurring — the markdown edits alone are a one-time cleanup that drifts back within two sessions without it.

**Scope — files owned by this package, no other package may touch them:**
```
.claude/skills/elevenlabs-audio/**
.claude/skills/elevenlabs-music/**
.claude/skills/midjourney-prompting/**
.claude/skills/music-brief/**
.claude/skills/rgs-grounding/**
.claude/skills/rgs-pairing-review/SKILL.md
.claude/skills/shorts-assembly/**
.claude/skills/shorts-ideation/**
.claude/skills/shorts-scripting/**
.claude/skills/shorts-styleboard/**
.claude/skills/social-repurpose/**
.claude/skills/visual-prompts/**            (one file, references/visual-registers.md, is DELETED by T14 — a tombstone removal, not an edit)
.claude/skills/voiceover-brief/**
tests/test_skill_provenance.py
```
**Not owned, read-only from here:** `pipeline.yaml` (P4), `docs/style-library.md` (P11), `scripts/lint_prompt_sheet.py` (P11), `scripts/resolve_brief_version.py` (P12), `CLAUDE.md` / `docs/README.md` (P14), `rgs-briefs/**` (P14), `cowork-plugin/skills/**` (build artifact, git-ignored).

**Findings closed here: 48.** `B-84`, `C-01`–`C-35`, `C-40`–`C-48`, `C-54`, `C-55`, `F-22`. No S0/S1 — severities run S2–S4. 18 tasks total (T1 fixes the marker regex and the module docstring; T2 builds the handoff-contract block machinery; T3–T18 each pair one conformance check with the markdown edits that turn it green).

**Suite:** root suite only (`python -m pytest tests/ -q`) — P13 touches no app-suite files, same as P11 (`tests/test_lint_prompt_sheet.py`) and P12 (`tests/test_lint_script_language.py`, `tests/test_resolve_brief_version.py`, `tests/test_build_cowork_plugin.py`) before it. Do not reflexively `cd pipeline-app` before running P13's tests. **P13's own §7 verification block used to hardcode a dead worktree path in its `cd`** (already fixed this session — run the command as shown there now, no `cd` needed, just `python -m pytest tests/ -q` from whatever worktree root you're actually in).

## Pre-flight check result, already done — read P13's plan §0 for the full detail, this is the summary

P13's own owned scope — every file listed above — is **completely untouched** since the plan was authored (2026-08-10): `git log <authoring-commit>..HEAD -- .claude/skills/ tests/test_skill_provenance.py` returns zero commits. `test_skill_provenance.py` still has exactly the 6 tests the plan's own intro describes.

**One real discrepancy found, already documented in the plan, requiring two task-text corrections before dispatch (not a re-plan, not a re-audit — a five-day-later drift in a sibling package's file that P13's own §6.2 explicitly anticipated as a possibility):** `pipeline.yaml` changed on 2026-08-15 (commit `28d1862`) — `assembly`'s `depends_on` gained `scripting` and `styleboard` directly (previously `[voiceover, visual]` only), and `repurpose`'s gained `ideation` and `scripting` directly (previously `[assembly]` only).

- **T5 (C-03):** the plan's fix routes `shorts-assembly`'s script input through the voiceover brief's `script:` pointer, because at authoring time `assembly` had no direct `scripting` edge. That workaround is now unnecessary and wrong — `assembly` declares `scripting` directly now (it also gained `optional_depends_on: [music]` in the same commit). Simplify T5's "Input 2 in app-driven mode" paragraph to a direct read before dispatching it.
- **T7 (C-05):** `test_downstream_list_matches_the_stage_graph` asserts `shorts-scripting`'s Downstream bullet names every stage whose `depends_on` contains `scripting` — the plan's task row says "all **four** consumers" (true at authoring time: `styleboard`, `voiceover`, `visual`, `music`). The live graph now has **six**: those four plus `assembly` and `repurpose`. Correct T7's task text before dispatch; the test itself is graph-driven and will assert the true count regardless, but the prose would mislead whoever implements it otherwise.
- **Not yet checked, flagged for a narrower pass before their own dispatch (not a full re-audit):** T2's `KIND_REGISTRY` must mirror the current 9-stage graph. C-08/C-09/C-10/C-11's "N things → N+1 things" counts in T5/T7/T9 look unrelated to `depends_on` (verify each against its own file rather than assuming). `repurpose`'s edge also changed and wasn't analyzed for downstream effects on C-04/T6 (`social-repurpose`'s stated inputs) — check before dispatching T6.

**Two more discrepancies, found by this file's own Opus review, not by the pre-flight pass above — both are inbound handoffs FROM sibling packages TO P13, recorded in those packages' own plans, which a check that only diffs P13's own scope can never discover on its own:**

- **From P11** (`P11-gate-c.md` §6.4, filed as "not a blocker"): P11's own T18 (a different task in a different package, not this plan's T18) widened the gate's banned-vocabulary lists in `scripts/lint_prompt_sheet.py` (confirmed live, `:743-747`); their declared source of truth, `.claude/skills/shorts-styleboard/references/visual-registers.md:47,64`, is still the old, narrower list. Mirror the widened lists in. No current task (T1–T18) covers this — fold it into T8, which already touches this file for C-06/C-07/C-26/C-27.
- **From P12** (`P12-gate-d-tools.md`): `shorts-scripting/SKILL.md:262` still describes `resolve_brief_version.py`'s old single-exit-code behavior ("exits 1" for the no-prior-version case); confirmed live that the script now has three distinct exit codes (`0`/`2`/`3`) and the no-prior-version case exits `3`, not `1`. Correct the sentence — no current task covers this file specifically; T7 is the closest (general `shorts-scripting` work).

Both are now recorded in P13's own plan §0 (extended after this file's Opus review) — read that section for the exact live-verified detail before deciding which task absorbs each.

**Nothing else in this plan's 48 findings, 18 tasks, or the P14 contract (§6.1) shows any sign of drift that either check (P13's own scope-diff, or a sibling package's recorded handoff) could surface — but note the limits of what "nothing else" means here: a sibling package's *silent*, unrecorded drift into a fact P13's own text assumes would not be caught by either check. Full finding-by-finding re-verification of all 48 findings was not performed this session.**

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this. P4 hit it eleven times across 20 tasks; P5 twice; P6 once; P7 once cleanly; P8 seven times across 41 tasks; P9 three times across 27 tasks; **P15 hit it sixteen times across 22 tasks — the highest volume of any package so far, and every single instance was still a proportionate, minimal fix to a concrete, falsifiable discrepancy, never a scope expansion** (see P15's plan §8 for the full breakdown: 8 bugs in the plan's own shown code/fixtures, 2 sibling-package contract mismatches, 5 authorized cross-package test ripples, 1 honestly-carried-forward block on P8). The mitigation, unchanged since P2:

Grep for every symbol a task's own shown code references before dispatching it — function names, section headings, other skills' file paths, `pipeline.yaml` stage ids — and confirm each either already exists live, or is defined within that same task's own text. **For P13 specifically: since its "code" is markdown prose and its "symbols" are section headings and file paths rather than Python identifiers, the equivalent check is grepping the actual heading text / actual file path a task's shown edit assumes exists, before pasting that edit in.** The `pipeline.yaml` drift above is exactly this class, just caught before Task 1 rather than mid-task.

If something's missing: amend the plan file FIRST, as a `>` blockquote note inserted directly at the relevant task, with its own commit explaining what was wrong and why — then dispatch the corrected version. Never fix a gap silently inline without amending the plan. This programme has now used that discipline across nine packages without exception.

**New pattern this package should watch for, not yet seen but structurally likely given P13's shape:** a task's shown markdown edit could cite a section heading or file path that a LATER task in the same package renames, moves, or deletes (e.g. T14 deletes `visual-prompts/references/visual-registers.md` as a tombstone — any earlier task's shown edit that still references that path by its old name would be exactly this class, one level removed from the "forward-reference to a later task's not-yet-introduced symbol" shape P9 hit). Check citation targets against what the *final* state of the package will look like, not just the current live repo, when a task's own edit references another P13-owned file.

**Also watch for:** P15's session (this one) hit a genuine, reviewer-caused false positive twice (a reviewer conflating two unrelated files' diff hunks because the review-package range accidentally bundled two commits; a reviewer missing a commit's body because the `review-package` script's diff file only lists the commit subject line, not the full body). Both were caught by the controller independently verifying against the actual `git show`/`git log --format=%B` output before accepting the finding. Do the same — a reviewer's claim is a hypothesis to verify against the actual diff/commit, not a fact to relay.

## Two mid-wave checkpoints and a mandatory final review — the human partner's standing request from P15, worth carrying forward as a suggestion, not an instruction

P15's session ran two mid-wave Opus checkpoint reviews (after roughly a third and two-thirds of its tasks) at the human partner's explicit request, and both found and fixed 3 Important findings each that the per-task reviews alone would have missed (cross-task page coherence, documentation-accuracy drift, one genuinely undiscoverable P8 handoff). P13 is 18 tasks, smaller than P15's 22 but still substantial, and unlike P15 it has a single unifying test file (`test_skill_provenance.py`) that every task extends — meaning a mid-wave checkpoint's highest-value question for P13 is likely "does the suite still assert what its own docstrings claim, cumulatively, or has an early task's assertion been quietly weakened by a later one's edit to the same test function." Consider proposing one mid-wave checkpoint (roughly after T9, the halfway point) and the mandatory final whole-branch review to the human partner rather than assuming either is wanted — P15's checkpoints were requested, not defaulted into.

## Carried-forward open items (know they exist; check whether any land in P13's own files)

**Resolved this session, no longer open:** All of P15's own carried-forward items are closed by its merge — see `docs/superpowers/plans/remediation/P15-ui.md`'s own §8 "Outcome" section for the full record if anything ever needs to reference the exact defect/fix pairs, including the six real security bugs found and fixed in its D-47 sanitizer.

**New, unclaimed programme-level tech debt, found during P15's final review, not any package's job yet:** `browse_service._Sanitizer` (P15's, adversarially tested six times over) and `routes/stages._HTMLSanitizer` (P3's, independently written) are now two divergent sanitizer implementations with different tag allowlists — see the master plan's `P15 → P3, P5` contract row for the full record. Neither P13 nor P14 owns the files involved (`browse_service.py`, `routes/stages.py`) — flagging only so a future session doesn't rediscover it from scratch.

**Two of P10/P11/P12's own carried-forward handoffs ARE load-bearing for P13 — both confirmed live and now folded into P13's own plan §0 (see the pre-flight section above for the detail):** P11 §6.4's banned-vocabulary mirror into `visual-registers.md`, and P12's stale exit-code sentence in `shorts-scripting/SKILL.md:262`. These were found only by this file's own Opus review, not by the original pre-flight pass — a reminder that "check the sibling packages whose files P13 reads" is not automatically covered by "check P13's own scope for drift," and worth re-doing as its own explicit step before P14 starts, not just before P13.

None of P3/P4/P5/P6/P7/P8/P9's older carried-forward items are load-bearing for P13 unless P13's own tasks happen to touch the exact same lines (they should not — P13 touches no Python at all). Full historical lists remain in each package's own merged PR body if needed: P3 #32, P4 #37, P5 #39, P6 #41, P7 #45, P8 #48, P9 #51, P15 #54.

From the gate-coverage final review (PR #40, unrelated to this remediation programme — still carried forward, still nobody's job): three issues in `pipeline_app/migrations.py` and `pipeline_config.py`. All three dormant against the live `pipeline.yaml`. Neither file is in P13's or P14's owned-file list.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests (not directly relevant to P13, which lives entirely in the root suite, but binding programme-wide).
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`), not any worktree — irrelevant to P13 itself (no Python), but bake the working-directory check (`pwd && git rev-parse --show-toplevel && git branch --show-current`, plus `git worktree list`) into every dispatch prompt regardless, since P13's own sub-agents will still be editing files and need to know which worktree they're in.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout, git-ignored. Never write to it. Not reachable from P13's scope, but still binding programme-wide.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8", errors="replace"`. Not relevant to P13 (no subprocess work in scope), but still binding programme-wide.
- Bash resolution on Windows is genuinely two-layered — never invoke `bash`/`sh` by bare name in a `subprocess.run([...])` call. Not relevant to P13's own scope.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-heavy commit or PR bodies to a file and use `-F`/`--body-file` instead. The harness's worktree-boundary guard also rejects complex multi-command heredocs and some multi-variable-capture single-line commands — prefer the Write tool over Bash heredocs, and prefer separate single-purpose Bash calls.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- In this harness, the Bash tool's working directory can drift between calls depending on prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command fails unexpectedly. This has bitten every session in this programme so far, including this one (twice, both recovered immediately by re-checking `pwd`).
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()` (not `.fullmatch()`), will silently never capture the optional group. Directly relevant to P13: several of its new conformance tests parse markdown with regexes (marker detection, citation resolution, count extraction) — watch for this shape when writing or reviewing them.
- When two independently-written pieces of text/code both need to find something via a first-occurrence string match, and one can textually contain what the other searches for, they will collide. P15 hit this exact shape twice this session (a rationale comment containing the word "once" colliding with a test's own `"once" not in resp.text` assertion; a plan-amendment blockquote's quoted test code confusing a reviewer reading a bundled diff). **P13 is unusually exposed to this class**, since its entire job is grepping markdown prose for markers/citations/counts — a task's own example text inside a `[C]`-marked bullet could accidentally match a later regex meant for something else. Watch for it.
- A finding that conflicts with the PLAN's own text (not the implementation) is the human's decision, same as any plan contradiction — present it, ask which governs, amend the plan first.
- Once both suites are fully green, there is no longer a documented baseline to distinguish "the same old failures" from "a new regression" — with one expected exception for THIS package specifically: the Cowork-plugin staleness check (green now, see the baseline section above) will predictably go red once P13 starts editing `.claude/skills/**`, and that predictable failure is not a regression to chase.
- `gh pr create --body-file` plus a manually-authored `.md` file works cleanly for a PR body with backticks/code blocks — write the body to a scratch file (this programme puts these under the worktree's own `.superpowers/` directory, git-ignored) and delete it after `gh pr create` succeeds.
- Finishing a branch via "push and create a PR," then continuing work in the SAME session after the PR merges, requires a second, fresh worktree — the first worktree's branch is now merged and closed. `ExitWorktree` (`action: "remove"`, `discard_changes: true`, once the merge is independently confirmed via `gh pr view <N> --json state,mergedAt,mergeCommit`) before creating the next one.
- GitHub can report a branch "out-of-date with base" even mid-review, if an unrelated PR merges to main while your PR is open. Fix: `git fetch origin main && git merge origin/main` on the feature branch (merge commits, not rebase — this programme's established convention), re-run both suites, push. This triggers a fresh CI run on the merge commit — wait for it.
- **New this session:** two separate CI workflow runs can trigger for one push (branch push event + PR event) — `gh pr checks <N>` shows all rows from both; confirm every row is a pass, not just the first run that completes. Confirmed stable across two consecutive sessions now (P9-followup and P15).
- **New this session:** `ExitWorktree` with `action: "remove"` can report "could not remove — kept" while still fully unregistering the worktree from `git worktree list`. Verify with `git worktree list`, don't trust the tool's own success/failure framing.
- **New this session:** the `review-package` script (from `superpowers:subagent-driven-development`) only lists a commit's SUBJECT line in its diff file's "Commits" section, not the full body. If a task's requirements include something that must land in the commit BODY (a falsification record, a rationale), tell the reviewer to check `git log -1 --format=%B <hash>` directly rather than trusting the review-package diff file to show it — a reviewer missed exactly this once this session and produced a false-positive Critical finding.

## Definition of done (the whole programme, not any one package)

All 328 originally-audited findings closed, plus B-113 (discovered during P9's own plan-reconciliation work, folded in mid-package with the human partner's confirmation) — **329 findings tracked, 329 closed as of P15's merge, 0 remaining in merged packages.** Each verified by the mechanism its plan names. Running total: P0+P1+P2+P3+P4+P5+P10+P11+P12+P6+P7+P8+P9+**P15** merged (14 of 16); **P13, then P14 are next.** Count each package's own total from its merged PR, not from memory. P15's own 16 (plus 2 more Important, security-relevant findings caught at its final review, beyond its original 16) are confirmed closed independently by its mandatory final review — see its plan §8.

Both suites are fully green with no documented exceptions beyond P15's own 2 documented xfail — root suite 445 passed/1 skipped/0 failed; app suite 1954 passed/4 skipped/2 xfailed/0 failed, as of P15's merge (`8893789`). Track any future failure as real, with one expected exception scoped to this package only: the Cowork-plugin staleness check (green at this baseline) predictably going red once P13 edits `.claude/skills/**` — see the baseline section above.

CI is green — all three jobs succeeded across both triggered runs on P15's merge commit, the fourth fully-green merge in this programme's history (after P7's, P8's, and P9's). Re-verify at session start; confirm it stays green after P13 merges.

Every S0/S1 has an observed-failing-first regression test. (P13, like P15, has no S0/S1 findings — its highest severity is S2 — so this item is trivially satisfied for P13's own scope, but re-verify nothing in P13's 48 findings was mis-classified before assuming so; 48 is a lot to have checked at plan-authoring time without at least a spot-check.)

A scheduled discovery run with an injected fault exits non-zero with an error events row — closed by P8, confirmed via its own final review and CI.

Gate C rejects a malformed shot heading — closed by P11, verified end to end.

`git grep "pipeline-app/scripts" -- '*.md'` returns nothing — P8's Task 40 closed the code side; doc references at the repo root (`README.md`, `CLAUDE.md`) remain and are explicitly **P14's** handoff, not yet done.

P9's own contribution, shipped: a quiet day and a broken collection render distinguishable emails, and a failed send is itself surfaced as an events row.

**P15's own contribution, shipped:** the operator-facing UI stops hiding or misrepresenting the signals the rest of the programme made trustworthy underneath — a gate that never ran reads as "never ran," not as a pass; an htmx failure is visible; Browse shows what it can't read instead of omitting it; Doctor stops printing the literal string "None." Its D-47 sanitizer survived six independently-found-and-fixed real security bugs across its own task lifecycle and the final review — the deepest security scrutiny any single piece of code has received in this programme so far.

**New, P13's own contribution once it lands:** the skill definitions the whole pipeline runs on stop silently drifting from the code and from each other — every cross-skill reference a skill makes (a section it consumes from another skill's output, a citation to its own reference file, a claim about how many things something is) becomes a machine-checked assertion instead of unverified prose, closing the same "declared but not actually true" defect class the rest of this programme spent 15 packages closing in code, now closed in the 655 normative blocks of documentation the code's own operators — and the LLM agents running the skills — actually read.

Use opus as your advisor for any critical decisions, key reviews, or blockers.
