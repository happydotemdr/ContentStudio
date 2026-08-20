# Resume prompt — P13 kickoff, PR #58 pending merge

You are resuming a fully-planned, already-validated 328-finding audit-remediation programme (329 as currently tracked — see "Definition of done" below for why). Do not re-plan and do not re-audit.

You are the orchestrator, not the implementor. Give sub-agents only the context they need — never share full context windows back and forth, never hand one the audit or another package's plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation accurate and the plan updated at every step. When you find a new gap or defect, file it in the relevant plan for review/validation before addressing it, and only fix it inline if it is a critical or important blocker. This has happened in every package executed so far — expect it in P13 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation programme).

**Step 0, before anything else: confirm PR #58 is merged.** `gh pr view 58 --json state,mergedAt` — it carries this session's P13 pre-flight amendment (below). If it isn't merged yet, either merge it yourself or wait for the human partner to. Do not start P13 off a base that doesn't include it — the whole point of writing it was so a fresh worktree wouldn't have to rediscover the drift it documents.

Start P13 in a **fresh worktree off `origin/main`** via `superpowers:using-git-worktrees` — do not reuse `worktree-p15-docs-followup` (the worktree this file itself was written and merged from; merged and gone by the time you read this) or any other prior package's worktree. Run `git log --oneline -5 origin/main -- docs/superpowers/plans/RESUME-PROMPT.md` first thing and confirm this file's own commit is present there before trusting anything below as current; if it isn't, something didn't merge and you're reading a stale copy from somewhere else.

**The orphaned-worktree-directory trap is real and has hit multiple consecutive sessions.** A session can start "already inside" a worktree-shaped directory (`.claude/worktrees/<name>`) per its own launch context, while that directory is **not** actually a registered git worktree (`git worktree list` doesn't show it). Symptom: `git rev-parse --show-toplevel` and `git branch --show-current` silently resolve to the main checkout instead of erroring, because git walks up looking for the nearest `.git` when the directory itself has no worktree registration — so ordinary git commands run there quietly operate on the wrong repo state without any error. **Always verify with `git worktree list` and confirm your directory appears in it before trusting `pwd`/`show-toplevel` alone, especially at the very start of a session.** If it doesn't appear, `ExitWorktree` is a no-op (nothing to exit from an unregistered directory) — the fix is `EnterWorktree` with a fresh name, which creates a genuine new worktree and moves the session into it. This is now a standing trap for every future session in this programme, not a one-off — stop re-discovering it and just check first.

If you are already inside a (genuine) worktree session when you start, `EnterWorktree` refuses to create a second one directly — `ExitWorktree` first (`action: "keep"` if the current worktree's branch is not yet merged and you might need it again; `"remove"` only after confirming its branch is merged). Note: `ExitWorktree` with `action: "remove"` has repeatedly reported "could not remove — kept" while still fully unregistering the worktree from `git worktree list` — verify with `git worktree list`, don't trust the tool's own success/failure framing.

The harness's worktree-boundary guard blocks `git -C "C:/Projects/ContentStudio" <command>` redirects from inside a worktree-isolated session — this has now held stable across every session in this programme, so treat it as permanent rather than re-verifying every time. The guard also rejects some single Bash calls that capture multiple git values via command substitution in one line, or that chain more than one or two commands with `&&`/heredocs — prefer separate single-purpose Bash calls, and prefer the Write tool over Bash heredocs for anything beyond a trivial one-liner. It also rejects reading another commit's file via `git show <ref>:<path>` if MSYS mangles the `ref:path` colon into a Windows path — prefix with `MSYS_NO_PATHCONV=1` on this host.

## A large, unrelated backlog landed on `origin/main` this session — read before trusting any stale baseline

**Between this file's previous version (written after PR #54) and now, 77 commits landed on `origin/main` via PR #55, #56, and #57** — an entire standalone `elevenlabs-tooling` package (a payload executor for ElevenLabs, its own app under a new top-level directory), plus a `stitcher`/`native-pipeline` build-out, an audio-preconditioning stage, and a channel-specific single-take VO architecture decision. **None of it is part of this remediation programme** — it is legitimate, independently-reviewed feature work that happened to land in the same window. Do not confuse it with programme scope, and do not assume any baseline count, CI status, or "nothing changed since last time" claim from before this backlog without re-verifying it fresh.

**The one place this backlog actually touches P13:** 7 files inside `.claude/skills/voiceover-brief/**` and `.claude/skills/elevenlabs-{audio,music}/**` changed (the pinned narrator voice was re-cloned IVC→PVC; a new single-take VO architecture reference file was added). This session's own audit found and recorded the concrete impact — **read `P13-skills-contracts.md`'s §0 amendment, the entry dated 2026-08-20, before dispatching Task T3.** Short version: two of T3's line citations are stale (`:89-105`→`:91-107`, `:135-138`→`:140-143`), and T3's own step-renumbering will orphan a live "step 4" cross-reference in a newly-landed Reference-files bullet unless T3's dispatch updates it to "step 5". Fold both into T3's task text before dispatch, per this programme's standing discipline (amend the plan, never fix silently) — do not treat this as new work to rediscover; it is already diagnosed.

**The separate MAIN CHECKOUT's sync state (`C:\Projects\ContentStudio`, where `pipeline-app` is installed editable) was not re-verified this session** — a prior session flagged local `main` as one unpushed merge commit ahead of `origin/main` (`564722d`), and the human partner was advised to fetch/merge/push to resolve it. Whether that happened is unknown as of this file's own writing. **Check it fresh at session start**, from the main checkout directly (not via `-C` from a worktree session — that redirect is blocked): `git status --short` and `git log --oneline -5`. If local `main` is still out of sync with `origin/main`, diagnose before doing anything else — do not assume the earlier advice was followed.

## Baseline suite counts — re-verify fresh, do not trust any number from before this session's backlog

The counts recorded in this file's prior version (445/1954 passing at `8893789`) are **stale** — the 77-commit backlog above added a substantial amount of new app-suite code (`stitcher`, `elevenlabs-tooling`'s own package, precondition/vo_alignment/vo_split/vo_assemble/vo_timing modules and their tests) that did not exist at that baseline. **Run both suites fresh before touching anything:**

- Root suite: `python -m pytest tests/ -q` from repo root.
- App suite: `cd pipeline-app && python -m pytest -q`.

Record whatever you get as the new baseline in this file's own next revision (or in P13's plan if you'd rather keep it colocated with the package) — do not carry forward the 445/1954 numbers as if they still hold. `python -m` is mandatory; a bare `pytest` at the repo root silently omits all app tests. `elevenlabs-tooling` (if it lives as its own top-level package outside `pipeline-app/`) may have its own test invocation — check its own docs/README before assuming either of the two commands above covers it; it is not part of this remediation programme's scope either way, so a failure there is not P13's problem unless P13 itself touches a file the failure traces to (it should not).

**CI:** re-verify at session start via `gh pr checks <N>` on whatever PR you're tracking — do not trust any status from a prior session as current, especially given the volume of recent unrelated activity.

`tests/test_build_cowork_plugin.py`'s two staleness checks (against `.claude/skills/`) were green at the last confirmed baseline (`8893789`) and the 77-commit backlog's own commits repeatedly rebuilt the lock file after each skill edit (`fix(cowork-plugin): rebuild the lock file after...` appears three times in that backlog) — so they are **likely** still green, but re-confirm rather than assume. They are directly relevant to P13 in a way they weren't for prior packages, since P13 edits `.claude/skills/**` extensively: expect them to go red partway through the package (any skill-file edit staleness-invalidates the build lock) and stay that way until either P13 finishes or someone runs `bash scripts/build-cowork-plugin.sh` to refresh it. That is expected drift from your own edits, not a regression to chase down.

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | merged |
| B1 | P2, then P10 | merged |
| B2 | P3 + P11 + P12 together | merged |
| B3 | P4, then P5 | merged |
| B4 | P6, P7, P8, P9 | all four merged — Wave B4 complete |
| B5 | P15 | merged as PR #54 (`8893789`) — Wave B5 complete |
| C | **P13, then P14** | **P13 is next — pre-flight checked across two sessions, not yet started** |

**Why P13 is next, precisely:** Wave C's own stated rationale (master plan, search "Wave C") is "Documentation describes the fixed code, or it is fiction again. P14 is last because six packages owe it contract decisions." P13 comes first within Wave C because P14's own plan (§ "Contract for P14," inside P13's file, §6.1) is written as a **request P13 makes of P14** — three specific edits P14 must make to `docs/README.md`/`CLAUDE.md` to resolve a provenance-wording contradiction P13 discovers but cannot fix (it owns neither file). Landing P14 first would mean resolving that contradiction blind.

## What P13 is — read `docs/superpowers/plans/remediation/P13-skills-contracts.md` §0 and §1-2 before dispatching Task 1

Do not act from this summary alone — it is oriented for triage, not execution, and the plan file is long (2400+ lines including two rounds of §0 pre-flight amendment, 18 tasks). Read the actual plan file yourself — start with §0 (**both** dated entries — 2026-08-19 and 2026-08-20 — the second one is this session's own, covering the 77-commit backlog above), before reading anything else — following this programme's Sub-agent output contract (never hand a sub-agent the whole plan file — extract only what each task needs, same discipline every prior package used).

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
.claude/skills/voiceover-brief/**           (includes references/single-take-architecture.md, a new file that landed in the 77-commit backlog — not separately listed when this plan was authored, but covered by the directory glob)
tests/test_skill_provenance.py
```
**Not owned, read-only from here:** `pipeline.yaml` (P4), `docs/style-library.md` (P11), `scripts/lint_prompt_sheet.py` (P11), `scripts/resolve_brief_version.py` (P12), `CLAUDE.md` / `docs/README.md` (P14), `rgs-briefs/**` (P14), `cowork-plugin/skills/**` (build artifact, git-ignored), the new `elevenlabs-tooling` package (unrelated, outside this programme).

**Findings closed here: 48.** `B-84`, `C-01`–`C-35`, `C-40`–`C-48`, `C-54`, `C-55`, `F-22`. No S0/S1 — severities run S2–S4. 18 tasks total (T1 fixes the marker regex and the module docstring; T2 builds the handoff-contract block machinery; T3–T18 each pair one conformance check with the markdown edits that turn it green).

**Suite:** root suite only (`python -m pytest tests/ -q`) — P13 touches no app-suite files, same as P11 and P12 before it. Do not reflexively `cd pipeline-app` before running P13's tests.

## Pre-flight check result — two rounds now, both already done, read P13's plan §0 for full detail

**Round 1 (2026-08-19, before this backlog landed):** `pipeline.yaml` changed on 2026-08-15 (`28d1862`) — `assembly`'s `depends_on` gained `scripting`/`styleboard` directly, `repurpose`'s gained `ideation`/`scripting` directly. Two concrete task-text corrections required before dispatch:

- **T5 (C-03):** simplify "Input 2 in app-driven mode" to a direct read — the pointer-chase workaround it currently describes is now unnecessary and wrong.
- **T7 (C-05):** correct "all four consumers" to the live count (now six: the original four plus `assembly` and `repurpose`) — the test itself is graph-driven and will assert correctly regardless, but the task prose would mislead.

Plus two inbound cross-package handoffs (found by an Opus review of this file, not the pre-flight pass itself): P11's widened banned-vocabulary lists need mirroring into `visual-registers.md` (fold into T8), and a stale exit-code sentence in `shorts-scripting/SKILL.md:262` needs correcting (fold into T7 or a dedicated addendum).

**Round 2 (2026-08-20, this session, covering the 77-commit backlog):** see the section above — T3's two stale line citations and the "step 4"→"step 5" cross-reference fix. **Both rounds' corrections must be folded into their respective tasks' text before dispatch, not fixed silently mid-task**, per this programme's standing discipline.

**Not yet checked, flagged for a narrower pass before their own dispatch (not a full re-audit):** T2's `KIND_REGISTRY` must mirror the current 9-stage graph. C-08/C-09/C-10/C-11's "N things → N+1 things" counts in T5/T7/T9 look unrelated to `depends_on` (verify each against its own file rather than assuming). `repurpose`'s edge also changed and wasn't analyzed for downstream effects on C-04/T6 (`social-repurpose`'s stated inputs) — check before dispatching T6.

**Nothing else in this plan's 48 findings, 18 tasks, or the P14 contract (§6.1) shows any sign of drift that either round's check could surface — but note the limits of what "nothing else" means here: a sibling package's *silent*, unrecorded drift into a fact P13's own text assumes would not be caught by either check. Full finding-by-finding re-verification of all 48 findings has not been performed across either round.**

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this. P4 hit it eleven times across 20 tasks; P5 twice; P6 once; P7 once cleanly; P8 seven times across 41 tasks; P9 three times across 27 tasks; P15 sixteen times across 22 tasks — the highest volume of any package so far, and every single instance was still a proportionate, minimal fix to a concrete, falsifiable discrepancy, never a scope expansion. **This session's own P13 pre-flight (round 2, above) is another clean instance of the same class** — a sibling body of work (unrelated feature commits, not even another remediation package this time) drifted into P13's owned files between planning and execution, caught before dispatch rather than mid-task. The mitigation, unchanged since P2:

Grep for every symbol a task's own shown code references before dispatching it — function names, section headings, other skills' file paths, `pipeline.yaml` stage ids — and confirm each either already exists live, or is defined within that same task's own text. **For P13 specifically: since its "code" is markdown prose and its "symbols" are section headings and file paths rather than Python identifiers, the equivalent check is grepping the actual heading text / actual file path a task's shown edit assumes exists, before pasting that edit in.**

If something's missing: amend the plan file FIRST, as a `>` blockquote note or a new dated §0 entry inserted directly at the relevant task, with its own commit explaining what was wrong and why — then dispatch the corrected version. Never fix a gap silently inline without amending the plan. This programme has now used that discipline across ten packages (counting this session's own amendment) without exception.

**Watch for:** a task's shown markdown edit could cite a section heading or file path that a LATER task in the same package renames, moves, or deletes (e.g. T14 deletes `visual-prompts/references/visual-registers.md` as a tombstone — any earlier task's shown edit that still references that path by its old name would be exactly this class). Check citation targets against what the *final* state of the package will look like, not just the current live repo, when a task's own edit references another P13-owned file. Also watch for two independently-written pieces of text both needing to find something via first-occurrence string match colliding — P13 is unusually exposed to this, since its entire job is grepping markdown prose for markers/citations/counts.

## Two mid-wave checkpoints and a mandatory final review — the human partner's standing request from P15, worth carrying forward as a suggestion, not an instruction

P15's session ran two mid-wave Opus checkpoint reviews (after roughly a third and two-thirds of its tasks) at the human partner's explicit request, and both found and fixed 3 Important findings each that the per-task reviews alone would have missed. P13 is 18 tasks and has a single unifying test file (`test_skill_provenance.py`) that every task extends — meaning a mid-wave checkpoint's highest-value question for P13 is likely "does the suite still assert what its own docstrings claim, cumulatively, or has an early task's assertion been quietly weakened by a later one's edit to the same test function." Consider proposing one mid-wave checkpoint (roughly after T9, the halfway point) and the mandatory final whole-branch review to the human partner rather than assuming either is wanted.

## Carried-forward open items (know they exist; check whether any land in P13's own files)

**New, unclaimed programme-level tech debt, found during P15's final review, not any package's job yet:** `browse_service._Sanitizer` (P15's) and `routes/stages._HTMLSanitizer` (P3's) are two divergent sanitizer implementations with different tag allowlists — see the master plan's `P15 → P3, P5` contract row. Neither P13 nor P14 owns the files involved.

**Two of P10/P11/P12's own carried-forward handoffs ARE load-bearing for P13 — both confirmed live and folded into P13's own plan §0 (round 1):** P11 §6.4's banned-vocabulary mirror into `visual-registers.md`, and P12's stale exit-code sentence in `shorts-scripting/SKILL.md:262`.

None of P3/P4/P5/P6/P7/P8/P9's older carried-forward items are load-bearing for P13 unless P13's own tasks happen to touch the exact same lines (they should not — P13 touches no Python at all). Full historical lists remain in each package's own merged PR body if needed: P3 #32, P4 #37, P5 #39, P6 #41, P7 #45, P8 #48, P9 #51, P15 #54.

From the gate-coverage final review (PR #40, unrelated to this remediation programme): three issues in `pipeline_app/migrations.py` and `pipeline_config.py`. All three dormant against the live `pipeline.yaml`. Neither file is in P13's or P14's owned-file list.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests (not directly relevant to P13, which lives entirely in the root suite, but binding programme-wide).
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`), not any worktree — irrelevant to P13 itself (no Python), but bake the working-directory check (`pwd && git rev-parse --show-toplevel && git branch --show-current`, plus `git worktree list`) into every dispatch prompt regardless.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout, git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8", errors="replace"`.
- Bash resolution on Windows is genuinely two-layered — never invoke `bash`/`sh` by bare name in a `subprocess.run([...])` call.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-heavy commit or PR bodies to a file and use `-F`/`--body-file` instead. The harness's worktree-boundary guard also rejects complex multi-command heredocs and some multi-variable-capture single-line commands — prefer the Write tool over Bash heredocs, and prefer separate single-purpose Bash calls. It also rejects `git show <ref>:<path>` unless prefixed `MSYS_NO_PATHCONV=1` on this host, or the colon gets mangled into a Windows path.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- In this harness, the Bash tool's working directory can drift between calls depending on prior `cd`s within the same tool call — prefer absolute paths, and re-run `pwd` if a command fails unexpectedly.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()` (not `.fullmatch()`), will silently never capture the optional group. Directly relevant to P13: several of its new conformance tests parse markdown with regexes — watch for this shape.
- When two independently-written pieces of text/code both need to find something via a first-occurrence string match, and one can textually contain what the other searches for, they will collide. P13 is unusually exposed to this class, since its entire job is grepping markdown prose for markers/citations/counts.
- A finding that conflicts with the PLAN's own text (not the implementation) is the human's decision, same as any plan contradiction — present it, ask which governs, amend the plan first.
- Once both suites are fully green, there is no longer a documented baseline to distinguish "the same old failures" from "a new regression" — with one expected exception for THIS package specifically: the Cowork-plugin staleness check will predictably go red once P13 starts editing `.claude/skills/**`, and that predictable failure is not a regression to chase.
- `gh pr create --body-file` plus a manually-authored `.md` file works cleanly for a PR body with backticks/code blocks — write the body to a scratch file and delete it after `gh pr create` succeeds. Check for `.github/PULL_REQUEST_TEMPLATE.md` and use it when present.
- Finishing a branch via "push and create a PR," then continuing work in the SAME session after the PR merges, requires a second, fresh worktree — the first worktree's branch is now merged and closed. `ExitWorktree` (`action: "remove"`, `discard_changes: true`, once the merge is independently confirmed via `gh pr view <N> --json state,mergedAt,mergeCommit`) before creating the next one.
- GitHub can report a branch "out-of-date with base" even mid-review, if an unrelated PR merges to main while your PR is open. Fix: `git fetch origin main && git merge origin/main` on the feature branch (merge commits, not rebase — this programme's established convention), re-run both suites, push. This triggers a fresh CI run on the merge commit — wait for it. **Given the volume of unrelated activity on this repo right now (77 commits in one window), expect this to happen more than once during P13's own branch lifetime — check before every push, not just once.**
- Two separate CI workflow runs can trigger for one push (branch push event + PR event) — `gh pr checks <N>` shows all rows from both; confirm every row is a pass, not just the first run that completes.
- `ExitWorktree` with `action: "remove"` can report "could not remove — kept" while still fully unregistering the worktree from `git worktree list`. Verify with `git worktree list`, don't trust the tool's own success/failure framing.
- The `review-package` script (from `superpowers:subagent-driven-development`) only lists a commit's SUBJECT line in its diff file's "Commits" section, not the full body. If a task's requirements include something that must land in the commit BODY, tell the reviewer to check `git log -1 --format=%B <hash>` directly rather than trusting the review-package diff file.
- **Pushing an already-merged branch with one new commit and opening a fresh PR against `main` works cleanly** (this session's PR #58) — GitHub diffs just the new commit against `main`, same branch name reused is not a problem.

## Definition of done (the whole programme, not any one package)

All 328 originally-audited findings closed, plus B-113 — **329 findings tracked, 329 closed as of P15's merge, 0 remaining in merged packages.** Each verified by the mechanism its plan names. Running total: P0+P1+P2+P3+P4+P5+P10+P11+P12+P6+P7+P8+P9+P15 merged (14 of 16); **P13, then P14 are next.** Count each package's own total from its merged PR, not from memory.

Both suites were fully green with no documented exceptions beyond P15's own 2 documented xfail, as of `8893789` — **re-verify fresh** per the baseline section above; the 77-commit backlog almost certainly changed the app-suite count.

CI was green at P15's merge (fourth fully-green merge in this programme's history). Re-verify at session start; confirm it stays green after PR #58 and after P13 merges.

Every S0/S1 has an observed-failing-first regression test. (P13, like P15, has no S0/S1 findings — its highest severity is S2 — so this item is trivially satisfied for P13's own scope, but re-verify nothing in P13's 48 findings was mis-classified before assuming so.)

A scheduled discovery run with an injected fault exits non-zero with an error events row — closed by P8, confirmed via its own final review and CI.

Gate C rejects a malformed shot heading — closed by P11, verified end to end.

`git grep "pipeline-app/scripts" -- '*.md'` returns nothing — P8's Task 40 closed the code side; doc references at the repo root remain and are explicitly **P14's** handoff, not yet done.

P9's own contribution, shipped: a quiet day and a broken collection render distinguishable emails, and a failed send is itself surfaced as an events row.

P15's own contribution, shipped: the operator-facing UI stops hiding or misrepresenting the signals the rest of the programme made trustworthy underneath. Its D-47 sanitizer survived six independently-found-and-fixed real security bugs across its own task lifecycle and the final review.

**New, P13's own contribution once it lands:** the skill definitions the whole pipeline runs on stop silently drifting from the code and from each other — every cross-skill reference a skill makes becomes a machine-checked assertion instead of unverified prose, closing the same "declared but not actually true" defect class the rest of this programme spent 15 packages closing in code, now closed in the ~655 normative blocks of documentation the code's own operators — and the LLM agents running the skills — actually read.

Use opus as your advisor for any critical decisions, key reviews, or blockers.
