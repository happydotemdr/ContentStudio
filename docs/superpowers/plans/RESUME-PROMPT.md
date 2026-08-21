# Resume prompt — P14 kickoff, the last package

You are resuming a fully-planned, already-validated 328-finding audit-remediation programme (377 as currently tracked — 329 original + B-113 (folded into P9) + P13's 48 — see "Definition of done" below for why). Do not re-plan and do not re-audit.

You are the orchestrator, not the implementor. Give sub-agents only the context they need — never share full context windows back and forth, never hand one the audit or another package's plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation accurate and the plan updated at every step. When you find a new gap or defect, file it in the relevant plan for review/validation before addressing it, and only fix it inline if it is a critical or important blocker. This has happened in every package executed so far — expect it in P14 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation programme).

**Step 0, before anything else: confirm P13 is actually merged and you're reading a current copy of this file.** `gh pr view 60 --json state,mergedAt,mergeCommit` should report `MERGED` at `b9479b8` (2026-08-21T01:35:58Z). Also check `gh pr view 61` — a follow-up (the label-first sub-beat legality decision P13's own T6 flagged as an out-of-scope operator call) merged immediately after at `9893072`; it touches `.claude/skills/shorts-scripting/**`, which P14 does not own, but its existence is worth knowing before you start grepping for "why does this line already say something P13's plan didn't specify." Run `git log --oneline -5 origin/main -- docs/superpowers/plans/RESUME-PROMPT.md` and confirm this file's own latest commit is present there before trusting anything below as current.

Start P14 in a **fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not reuse the worktree this file itself was written and merged from (gone by the time you read this) or any other prior package's worktree.

**The orphaned-worktree-directory trap is real and has hit multiple consecutive sessions.** A session can start "already inside" a worktree-shaped directory (`.claude/worktrees/<name>`) per its own launch context, while that directory is **not** actually a registered git worktree (`git worktree list` doesn't show it). Symptom: `git rev-parse --show-toplevel` and `git branch --show-current` silently resolve to the main checkout instead of erroring, because git walks up looking for the nearest `.git` when the directory itself has no worktree registration — so ordinary git commands run there quietly operate on the wrong repo state without any error. **Always verify with `git worktree list` and confirm your directory appears in it before trusting `pwd`/`show-toplevel` alone, especially at the very start of a session.** If it doesn't appear, `ExitWorktree` is a no-op (nothing to exit from an unregistered directory) — the fix is `EnterWorktree` with a fresh name, which creates a genuine new worktree and moves the session into it. This is now a standing trap for every future session in this programme, not a one-off — stop re-discovering it and just check first.

If you are already inside a (genuine) worktree session when you start, `EnterWorktree` refuses to create a second one directly — `ExitWorktree` first (`action: "keep"` if the current worktree's branch is not yet merged and you might need it again; `"remove"` only after confirming its branch is merged). Note: `ExitWorktree` with `action: "remove"` has repeatedly reported "could not remove — kept" while still fully unregistering the worktree from `git worktree list` — verify with `git worktree list`, don't trust the tool's own success/failure framing.

The harness's worktree-boundary guard blocks `git -C "C:/Projects/ContentStudio" <command>` redirects from inside a worktree-isolated session — this has now held stable across every session in this programme, so treat it as permanent rather than re-verifying every time. The guard also rejects some single Bash calls that capture multiple git values via command substitution in one line, or that chain more than one or two commands with `&&`/heredocs — prefer separate single-purpose Bash calls, and prefer the Write tool over Bash heredocs for anything beyond a trivial one-liner. It also rejects reading another commit's file via `git show <ref>:<path>` if MSYS mangles the `ref:path` colon into a Windows path — prefix with `MSYS_NO_PATHCONV=1` on this host.

## Baseline suite counts — re-verify fresh at session start regardless

**Verified 2026-08-21 at `9893072` (`main`, P13 + its PR #61 follow-up both merged):** root suite 533 passed/0 failed; app suite 1954 passed/4 skipped/2 xfailed/0 failed. Run both fresh before touching anything — this is a snapshot, not a live status:

- Root suite: `python -m pytest tests/ -q` from repo root.
- App suite: `cd pipeline-app && python -m pytest -q`.

`python -m` is mandatory; a bare `pytest` at the repo root silently omits all app tests. `elevenlabs-tooling` (its own top-level package outside `pipeline-app/`, unrelated feature work) has its own test invocation if any — not this programme's scope, so a failure there is not P14's problem unless P14 itself touches a file the failure traces to (it should not; P14 touches only docs and `rgs-briefs/**`).

**CI:** re-verify at session start via `gh pr checks <N>` on whatever PR you're tracking — do not trust any status from a prior session as current.

**The cowork-plugin lock file predictably needed a rebuild after merging P13.** `bash scripts/build-cowork-plugin.sh` was run once already (2026-08-21) to resync `scripts/cowork-plugin.lock.json` against P13's + PR #61's skill edits — expected drift any time `.claude/skills/**` changes, not a regression. P14 does not touch `.claude/skills/**`, so this should stay quiet during P14's own execution; if `test_a_locally_built_artifact_is_not_older_than_the_skills_it_ships` goes red mid-P14, something unrelated touched skills again — rebuild and move on, don't chase it as a P14 bug.

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | merged |
| B1 | P2, then P10 | merged |
| B2 | P3 + P11 + P12 together | merged |
| B3 | P4, then P5 | merged |
| B4 | P6, P7, P8, P9 | all four merged — Wave B4 complete |
| B5 | P15 | merged as PR #54 (`8893789`) — Wave B5 complete |
| C | **P13 ✅ merged**, then **P14** | P13 merged as [PR #60](https://github.com/happydotemdr/ContentStudio/pull/60) (`b9479b8`, 2026-08-21), closing all 48 findings. **P14 is next — the last package in the programme.** |

**Why P14 is last, precisely:** Wave C's own stated rationale (master plan, search "Wave C") is "Documentation describes the fixed code, or it is fiction again. P14 is last because six packages owe it contract decisions." P13's landing is what actually unblocks most of those decisions — see the Inputs table below.

## What P14 is — read `docs/superpowers/plans/remediation/P14-docs-truth.md` §1-2 before dispatching Task 1

Do not act from this summary alone — read the actual plan file yourself, starting with §1 (Scope) and §2 (Inputs required — the gate), before reading anything else — following this programme's Sub-agent output contract (never hand a sub-agent the whole plan file — extract only what each task needs, same discipline every prior package used).

**P14 is shaped like P13: no application code.** It edits 8 doc files (`CLAUDE.md`, `README.md`, `pipeline-app/README.md`, `docs/README.md`, `rgs-briefs/README.md`, two `rgs-briefs/*.md` artifacts — read-only, hook-immutable — and `docs/audit/appendix-F-tests.md`), plus one new file, `tests/test_doc_truth.py`, in the **root** suite. Its own thesis: every other package changed code; this one makes the repo's documentation true about the code the other fifteen changed, and makes each claim executable so it fails a test the day it stops being true.

**Findings closed here: 9.** `B-80`, `C-52`, `C-53`, `D-40`, `D-53`, `F-10`, `F-29`, `F-30`, `F-62`. No S0 — highest severity is F-10 at S1. 13 tasks (T1–T8 map to findings; T9–T12 are relay/hygiene tasks driven by other packages' contract decisions; T13 is the full verification sweep).

**Suite:** root suite only (`python -m pytest tests/ -q`) — same as P11, P12, P13 before it. `test_documented_test_commands_collect_what_the_docs_claim` (T2) shells out via `subprocess`; it needs `@pytest.mark.allow_subprocess` to clear P0's conftest guard — apply the marker, do not weaken the guard.

## Inputs required — the gate (P14's own plan §2, condensed; verify each fresh, do not trust this table as still current)

P14 cannot start Tasks 2, 3, 5, 6, 9, 10, or 11 until the named package's decision is confirmed. As of P13's merge:

| # | From | Status as of P13's plan (2026-08-20) | What's needed before dispatch |
|---|---|---|---|
| I1/I2 | P0 | RESOLVED (structure/no single runner) | Just the live collected-test counts — measure fresh at T2 time, do not reuse any baseline number. |
| I3 | P10 | RESOLVED (path) / OPEN (spelling) | P10's exact verbatim invocation for the roster-seeding script under `pipeline-app/tools/`. Ask P10 directly or grep its own README/tests for the real command — do not guess. |
| I4 | P13 | RESOLVED | Unmarked-`[C]` default survives, scoped to `docs/*.md` only, with a reciprocal half-sentence in `CLAUDE.md`. P13's triage: 533 normative blocks, 367 unmarked, 215 real bugs. Mirror P13's `ALTERNATIVE_VOCABULARY` names exactly. |
| I5 | P13 | **OPEN as of P13's own plan text** | Canonical `kind:` token for the never-written `styleboard`/`music` stages, their `stage:` ordinals, and resolving the one on-disk `kind: visual-prompt-sheet` against six `kind: visual-prompts`. **Check this first at P14 kickoff** — P13 shipped `KIND_REGISTRY`/`SPECIALIST_KINDS` as its own canonical vocabulary source (its T13), so this may already be answerable directly from `tests/test_skill_provenance.py`'s constants rather than needing a fresh ask. Verify before assuming still-open. |
| I6 | P13 | **OPEN as of P13's own plan text** | Confirmation that `rgs-grounding`/`rgs-pairing-review` now select grounding briefs **positively** rather than by "lacks `kind:`". **Also check this first** — P13's scope included `rgs-grounding/**` and `rgs-pairing-review/SKILL.md` directly, so the live file may already show the answer. If P13 kept the negative rule, P14's T6 is blocked — escalate rather than guess. |
| I7 | P6 + P9 | **OPEN, unresolved as of P13's merge** | Is the YouTube-shaped `upload_date` alias removed from `discovery_digest.py`, or retained as a named exception? This is the one input with no candidate answer sitting in already-landed work — ask P6/P9's owners (or re-read their merged PRs, #41 and #51) directly. |
| I8 | P9 | RESOLVED | Code stays; `CLAUDE.md` changes. Take replacement wording verbatim from P9's §6.2(a) / `email_render.DISCLOSURE`, do not draft your own. |
| I9 | P4 | RESOLVED | `styleboard`/`music` remain stages under those ids. `assembly.depends_on` = `[scripting, styleboard, voiceover, visual]` with `optional_depends_on: [music]`; `repurpose.depends_on` = `[ideation, scripting, assembly]`. |

**Also resolved (T1/D-40):** P15 vendored htmx to `static/`, deleted the `unpkg.com` reference — the CDN leaves the outbound-call roster T1 documents. Recount against the merged tree, not the audit's original "14 call sites."

**Recording the answers.** Before implementing, append an "Inputs received" block to the bottom of `P14-docs-truth.md` with each input id, the answering package, the date and the verbatim decision — per that plan's own §2 instruction. A task implemented without its row filled in is a plan violation.

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this: a task's own citations (line numbers, section headings, other files' contents) drift stale between planning and execution because intervening commits — sibling packages, unrelated feature work, or even P14's own earlier tasks — touch the same ground. P13 hit it in T3 (stale line citations after an unrelated 77-commit backlog landed) and again in T6 (a genuine out-of-scope operator decision, correctly filed as a follow-up rather than decided unilaterally — see PR #61 above). The mitigation, unchanged since P2:

Grep for every symbol/heading/file path a task's own shown edit references before dispatching it, and confirm each either already exists live or is defined within that same task's own text. For P14 specifically: its tasks quote exact CLAUDE.md/README line ranges and exact prose to replace — verify those line numbers and that prose still match the live file before pasting a task brief, since P14's own T1–T13 were written against a specific snapshot of `CLAUDE.md` that has almost certainly drifted (P13's merge alone touched none of P14's owned files, but the 77-commit backlog and any work since might have).

If something's missing: amend the plan file FIRST, as a `>` blockquote note or a new dated §0/amendment entry, with its own commit explaining what was wrong and why — then dispatch the corrected version. Never fix a gap silently inline without amending the plan. This programme has used that discipline across eleven packages without exception (P13 included).

## Carried-forward open items (know they exist; check whether any land in P14's own files)

**Unclaimed programme-level tech debt, found during P15's final review, still nobody's job:** `browse_service._Sanitizer` (P15's) and `routes/stages._HTMLSanitizer` (P3's) are two divergent sanitizer implementations with different tag allowlists — see the master plan's `P15 → P3, P5` contract row. Neither P13 nor P14 owns the files involved; if P14 ever needs to describe the sanitizer situation in a doc, describe it as unresolved, not fixed.

**P13 → P14 contract, P13's plan §6.1:** three provenance-wording edits to `docs/README.md`/`CLAUDE.md` plus the newly-found `[S]` marker-vocabulary gap and a dangling `docs/style-library.md:198` pointer — this is I4 above, RESOLVED, but re-read P13's §6.1 directly for the exact wording before drafting T9 rather than trusting this summary's paraphrase.

None of P0–P9's older carried-forward items are load-bearing for P14 unless P14's own tasks happen to touch the exact same lines (unlikely — P14 touches no application code). Full historical lists remain in each package's own merged PR body if needed: P0/P1 (Wave A), P2 #? / P10 #?, P3 #32, P4 #37, P5 #39, P6 #41, P7 #45, P8 #48, P9 #51, P15 #54, P13 #60 (+ follow-up #61).

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests (not directly relevant to P14, which lives entirely in the root suite, but binding programme-wide).
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`), not any worktree — irrelevant to P14 itself (no Python touched), but bake the working-directory check (`pwd && git rev-parse --show-toplevel && git branch --show-current`, plus `git worktree list`) into every dispatch prompt regardless.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout, git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8", errors="replace"`. Directly relevant to P14's T2, which shells out to `pytest --collect-only`.
- Bash resolution on Windows is genuinely two-layered — never invoke `bash`/`sh` by bare name in a `subprocess.run([...])` call.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-heavy commit or PR bodies to a file and use `-F`/`--body-file` instead. The harness's worktree-boundary guard also rejects complex multi-command heredocs and some multi-variable-capture single-line commands — prefer the Write tool over Bash heredocs, and prefer separate single-purpose Bash calls. It also rejects `git show <ref>:<path>` unless prefixed `MSYS_NO_PATHCONV=1` on this host, or the colon gets mangled into a Windows path.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- In this harness, the Bash tool's working directory can drift between calls depending on prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command fails unexpectedly.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()` (not `.fullmatch()`), will silently never capture the optional group. P14's own doc-truth checks parse markdown/CLAUDE.md with regexes — watch for this shape, same as P13's conformance suite did.
- Two `rgs-briefs/*.md` files P14 owns are hook-immutable (`.claude/hooks/protect_briefs.py`) — P14 documents around them, never edits them. Re-read P14's plan §1 before touching anything under `rgs-briefs/`.
- A finding that conflicts with the PLAN's own text (not the implementation) is the human's decision, same as any plan contradiction — present it, ask which governs, amend the plan first.
- `gh pr create --body-file` plus a manually-authored `.md` file works cleanly for a PR body with backticks/code blocks — write the body to a scratch file and delete it after `gh pr create` succeeds. Check for `.github/PULL_REQUEST_TEMPLATE.md` and use it when present.
- Finishing a branch via "push and create a PR," then continuing work in the SAME session after the PR merges, requires a second, fresh worktree — the first worktree's branch is now merged and closed. `ExitWorktree` (`action: "remove"`, `discard_changes: true`, once the merge is independently confirmed via `gh pr view <N> --json state,mergedAt,mergeCommit`) before creating the next one.
- GitHub can report a branch "out-of-date with base" even mid-review, if an unrelated PR merges to main while your PR is open. Fix: `git fetch origin main && git merge origin/main` on the feature branch (merge commits, not rebase — this programme's established convention), re-run both suites, push. This triggers a fresh CI run on the merge commit — wait for it.
- Two separate CI workflow runs can trigger for one push (branch push event + PR event) — `gh pr checks <N>` shows all rows from both; confirm every row is a pass, not just the first run that completes.
- `ExitWorktree` with `action: "remove"` can report "could not remove — kept" while still fully unregistering the worktree from `git worktree list`. Verify with `git worktree list`, don't trust the tool's own success/failure framing.
- The `review-package` script (from `superpowers:subagent-driven-development`) only lists a commit's SUBJECT line in its diff file's "Commits" section, not the full body. If a task's requirements include something that must land in the commit BODY, tell the reviewer to check `git log -1 --format=%B <hash>` directly rather than trusting the review-package diff file.
- **Pushing an already-merged branch with one new commit and opening a fresh PR against `main` works cleanly** (P13's own PR #58 precedent) — GitHub diffs just the new commit against `main`, same branch name reused is not a problem.

## Definition of done (the whole programme, not any one package)

All 328 originally-audited findings closed, plus B-113 and P13's 48 — **377 findings tracked, 377 closed as of P13's merge, 0 remaining in merged packages.** Each verified by the mechanism its plan names. Running total: P0+P1+P2+P3+P4+P5+P10+P11+P12+P6+P7+P8+P9+P15+P13 merged (**15 of 16**); **P14 is the only package left.** Count each package's own total from its merged PR, not from memory.

Both suites fully green at `9893072` (P13 + PR #61 merged), verified 2026-08-21: root 533 passed, app 1954 passed/4 skipped/2 xfailed (P15's documented xfail, unchanged) — **re-verify fresh** at session start per the baseline section above.

CI was green at P13's merge (fifth fully-green merge in this programme's history, after P0/P1/…/P15's precedents). Re-verify at session start; confirm it stays green after P14 merges.

Every S0/S1 has an observed-failing-first regression test. P14's own highest severity is F-10 at S1 — its own Task 8 is what closes that finding, so this bar is not yet trivially satisfied the way it was for P13/P15; verify T8 lands with an observed-failing-first test before calling P14 done.

A scheduled discovery run with an injected fault exits non-zero with an error events row — closed by P8, confirmed via its own final review and CI.

Gate C rejects a malformed shot heading — closed by P11, verified end to end.

`git grep "pipeline-app/scripts" -- '*.md'` returns nothing — P8's Task 40 closed the code side; doc references at the repo root remain and are **P14's own T3's** handoff to close.

P9's own contribution, shipped: a quiet day and a broken collection render distinguishable emails, and a failed send is itself surfaced as an events row.

P15's own contribution, shipped: the operator-facing UI stops hiding or misrepresenting the signals the rest of the programme made trustworthy underneath. Its D-47 sanitizer survived six independently-found-and-fixed real security bugs across its own task lifecycle and the final review.

P13's own contribution, shipped: the skill definitions the whole pipeline runs on stop silently drifting from the code and from each other — every cross-skill reference a skill makes is now a machine-checked assertion instead of unverified prose, closing the same "declared but not actually true" defect class the rest of this programme spent 15 packages closing in code, now closed in the ~655 normative blocks of documentation the code's own operators — and the LLM agents running the skills — actually read.

**New, P14's own contribution once it lands — this is the programme's own closing act:** the repo's documentation stops describing a system that used to exist. Every doc claim the audit found false (network dependencies, test invocation, setup steps, pipeline stage contracts, FamilyBrain firewall completeness) becomes either true or explicitly flagged as untested, and — via T8 — the audit's own claim that all 328(+49) findings were actually addressed becomes an executable assertion instead of a belief. **When P14 merges, the programme is done.**

Use opus as your advisor for any critical decisions, key reviews, or blockers.
