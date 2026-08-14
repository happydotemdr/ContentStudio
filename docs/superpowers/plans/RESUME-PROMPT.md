# Resume prompt — audit-remediation programme, P3 complete, ready for P12+

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-14. **P3 (Gates & Approval, 24 task blocks, 22 findings) is complete**, its
final whole-branch review is clean, and its PR is open:
[#32](https://github.com/happydotemdr/ContentStudio/pull/32) (not yet merged as of this writing —
merge it, or confirm it merged, before starting P12).

---

/superpowers:subagent-driven-development

You are resuming a fully-planned, already-validated **328-finding audit-remediation programme**.
Do not re-plan and do not re-audit.

**You are the orchestrator, not the implementor.** Give sub-agents only the context they need —
never share full context windows back and forth, never hand one the audit or another package's
plan. Instruct every one of them explicitly not to let scope creep. Keep the documentation
accurate and the plan updated at every step. When you find a new gap or defect, **file it in the
relevant plan for review/validation before addressing it**, and only fix it inline if it is a
critical or important blocker.

## The repo

Worktree: `C:\Projects\ContentStudio\.claude\worktrees\pipeline-audit-review-4dd767`
Branch `claude/pipeline-audit-review-4dd767`. Main branch `main`. Windows 11, PowerShell primary.
Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

## Where execution is

P0, P1, P2, P10, P11 — merged into `main` (unchanged, see prior resume-prompt history in git log
for details).

**P3 — Gates & Approval — complete on this branch, PR
[#32](https://github.com/happydotemdr/ContentStudio/pull/32) open, not yet merged.** All 24 task
blocks (T1, T2, T2B, T3, T4, T5, T6, T7, T7B, T8, T9, T10, T11, T12, T13, T14, T15, T16, T17, T18,
T19, T20, T21, T22, T23, T24) done, each TDD-cycled, each with a clean or fixed-and-reverified
task review. The mandatory final whole-branch review (opus, blind to all 24 per-task reviews)
found and this session fixed 5 real issues (2 Critical XSS in a hand-written HTML sanitizer, 3
Important — including one where an earlier task's fix was silently reintroduced by a later task,
exactly the class of cross-task regression this final-review step exists to catch). A scoped
re-review confirmed all five closed with no new breakage. Full detail, including a Minor cosmetic
finding and 8 more Minor + 3 Important findings deliberately parked as backlog (not load-bearing
for this package's own 22 findings), is in the PR body ([#32](https://github.com/happydotemdr/ContentStudio/pull/32))
and in the commit messages of this branch's own git history. The plan's own workspace directory
(`.superpowers/sdd/P3-gates-approval/`) is gitignored — it was never committed, and has been
deleted per the skill's Finish step now that the durable record lives in the PR body and commit
history instead. The raw per-task briefs/reports/review-package diffs are gone; they were process
scratch, not the record of what changed or why.

**Before starting P12: merge PR #32 (or confirm it's already merged) and rebase/re-derive whatever
this next package needs from `main` at that point** — this branch (`claude/pipeline-audit-review-4dd767`)
has been reused across P0 through P3 sequentially per prior sessions' own pattern; check whether
the next package continues on this same branch or opens a fresh worktree, per whatever the
`EXECUTION-KICKOFF-PROMPT.md` / your own judgment on the landing order says at that point.

**Do not start P12 without first checking two things P3's own plan text flagged:**

1. P12 T8 leaves a deliberate `xfail(strict=True)` tripwire that only resolves once `gates.py`
   derives `blocking` from a `kind` vocabulary rather than a hardcoded string. **Confirmed this
   session: P3's own T10 (`classify_gates`) already does this** — `classify_gates` in
   `approval_service.py` derives `state`/`blocking` from an explicit status→state mapping, not a
   hardcoded string check. P12 should be safe to start on this specific point, but verify against
   the live `gates.py`/`approval_service.py` empirically before trusting this note — it may have
   drifted since this session.
2. P4 has still not executed. Two forward-references to P4's not-yet-existing work were found and
   deferred THIS session (in addition to the one already known from P3's own plan text,
   `resolve_upstream_by_stage`'s semantics):
   - `turn_service.propagate_staleness` needs an optional `repo_root=` keyword P3's hand-edit
     route wants to pass (closes A-14 on that path, but A-14 isn't P3's finding).
   - A `turn_service.propagate_grounding_staleness` function doesn't exist yet; P3's grounding
     branch wants to call it after a re-pointed brief.
   Both are documented in P3's own plan file (`docs/superpowers/plans/remediation/P3-gates-approval.md`,
   the amendment block under T24) as deferred, routed-back-to-P4 items. **When P4 executes, check
   this file's T24 amendment block** — either P4 adopts these two call sites itself, or hands them
   back to a P3 fast-follow once the keywords/function exist.

## Two more forward-reference/cross-package gaps found and resolved THIS session (pattern to watch for in every future package)

This session found and fixed FIVE forward-reference bugs in P3's own plan text (on top of the
three found in the prior P3 session) — the pattern is now well-established across this entire
programme: **a task's shown test/implementation code can reference a function, class, fixture, or
sibling-package API that doesn't exist yet at the point that task is dispatched.** Grep for every
symbol a task's own shown code references before dispatching it. Found this session:

1. T10's cross-surface invariant test needed `_stage_context`/`gate_view`/`has_blocking_gate`
   (not wired in until T19) and an undefined `_scripting_client` fixture — deferred to T19.
2. T19's own text said "replace all five `PlainTextResponse` sites" but T4's own already-landed
   text had explicitly deferred a SIXTH site to T19 — corrected to six.
3. T21 needed `browse_service.sanitize_html`, owned by a different, not-yet-executed package
   (P15) that P3 may not edit — resolved by writing a private local sanitizer, mirroring the T2/
   P4 `_approved_artifact_path` handoff pattern from the prior session.
4. T7B's fix to close a real CLI/app parity gap made a previously-committed T7 test fail on a
   BY-DESIGN wording split T7B's own brief mandated — resolved by normalizing only that one
   finding's message before comparison, not weakening the parity check for anything else.
5. T24's own text asked for two P4-owned keywords that don't exist yet (see above) — deferred.

**Expect more of these in every remaining package.** The mitigation that has worked every time:
verify empirically against the live repo BEFORE dispatching (grep for every referenced symbol),
amend the plan file with a `>` blockquote note and its own commit when a gap is found, then
dispatch the corrected version. Never fix the gap silently inline without amending the plan first.

## The bar, restated because it is what everything else serves

"Any representation shared by 'nothing here' and 'something is wrong' is a defect by default."
This session's own final review found the SAME defect class one level up from where prior
sessions found it: not "the code silently treats two different facts as one," but "the fix for
that defect is silently invisible on the actual rendered page" (P3's T19-T21 core classifiers,
`gate_view`/`inputs`, were computed correctly in every context dict and asserted correctly by
every test — but no template rendered them, so the operator's screen still showed the pre-fix
behavior). **Test the rendered output, not just the context dict, whenever a fix's whole point is
operator-visible surfacing.** This is now a confirmed, repeat-observed failure mode across this
programme and should be checked explicitly in every future package's final review.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout
  (`C:\Projects\ContentStudio`), not this worktree. Bake an explicit working-directory check
  (`pwd && git rev-parse --show-toplevel && git branch --show-current`) into every dispatch
  prompt.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always
  `encoding="utf-8", errors="replace"`.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness.
- Never invoke `bash`/`sh` by bare name in a subprocess. Resolve with `shutil.which()`.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead of an inline heredoc.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field from a filename or frontmatter
  value.
- In this specific harness, the Bash tool's working directory resets to the worktree path after
  every separate call — `cd` does not persist between calls. Chain multi-step operations touching
  a different directory in one command.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()`
  (not `.fullmatch()`), will silently never capture the optional group.
- When two independently-written pieces of text/code both need to find something via a
  first-occurrence string match, and one can textually contain what the other searches for, they
  will collide.
- A task's own shown test/implementation code can reference a function, class, fixture, or
  sibling-package API introduced by a later task or a different, not-yet-executed package. Found
  five separate instances of this in P3 alone across two sessions (see above). Grep for every
  referenced symbol before dispatching.
- **New this session:** a hand-written HTML sanitizer built on `html.parser.HTMLParser` must
  escape TEXT NODES (`handle_data`), not just attribute values — `convert_charrefs=True` hands
  `handle_data` already entity-DECODED text, so markdown-escaped `&lt;script&gt;` inside a code
  block round-trips back to a live `<script>` tag if the text is re-emitted verbatim. Also:
  `HTMLParser.CDATA_CONTENT_ELEMENTS` is `("script", "style")`, not just `"script"` — anything
  that special-cases script-tag skipping for a sanitizer must do the same for `style`, or raw
  markup leaks through `style`'s CDATA content as unescaped "text."

## Open findings — filed, NOT fixed, carried forward

Unchanged from before this session's start (see P10/P11-era resume-prompt history in git log for
the full list) — none of them were P3's to resolve, and P3 added no new ones to this list.

Two operator decisions remain open from before P3, still unresolved, not any single package's
call — surface them again if the operator hasn't weighed in:

1. `T21R-01` — the `CLOSE`/`MACRO` 1-object-floor carve-out in Gate C's C8 check (P11's file).
2. `T6R-02` — what, if anything, should catch an extra fenced example block mid-sheet (the one
   documented root-suite exception, unchanged all session:
   `test_lint_prompt_sheet.py::test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[fenced-heading]`).

New from this session, filed for a future small follow-up task (not urgent, not this session's to
fix — see PR #32's body for full detail):

3. Nine test failures in files P3 owns (`test_routes_stages.py` x3, `test_approval_service.py`
   x6) assert against a pre-P2 API shape and were left broken since fixing them was outside T23/
   T24's own explicit checklist.
4. A scratch-file interleaving hazard: concurrent hand edits to the same stage share one fixed
   scratch filename (`.edit_scratch.tmp`), so two overlapping edit POSTs can race.
5. Gate messages on the hand-edit path name the scratch filename instead of a stable display
   name — operator-facing text points at a file already deleted by response time.
6. Eight further Minor findings from P3's final review (see PR #32 body / this branch's git
   history for the full list: an unused `_approved_artifact_path` parameter that's a trap for P4,
   `optional_depends_on` added to `pipeline_config.py` slightly outside P3's declared file
   ownership, a non-transactional re-lock cascade, a dropped grounding override reason on an
   already-final artifact, a `gates: {}`/`gates: 0` laundering edge case, an
   attribute-denylist-not-allowlist gap in the new sanitizer, unbounded linter-module caching
   with no mtime invalidation, and a `UpstreamMap` guard bypassable via ordinary dict idioms like
   `dict(upstream)`/`{**upstream}`).
7. New CSS classes (`status-blocking`, `status-ok`, `input-missing`, `input-malformed`) introduced
   by the final-review fix wave have no stylesheet rules yet — gate badges and input cards render
   with correct semantics but lose color coding until a small styling follow-up lands.

## Definition of done (the whole programme, not any one package)

1. All 328 findings closed — each verified by the mechanism its plan names. P3's own 22 are now
   confirmed closed (independently, by the mandatory final review). Running total across the
   whole programme is not restated here — count from each merged package's own PR, not from
   memory, to avoid a premature "done" claim.
2. Both suites green everywhere they can be: `python -m pytest tests/ -q` (355/1, the one
   documented T6R-02 exception, unchanged for many sessions now) and, from `pipeline-app/`,
   `python -m pytest -q` (31 failed/1204 passed/3 skipped as of P3's completion — down from 33;
   the remaining 31 need either a small P3 follow-up (item 3 above) or other packages' own future
   work to fully close, per PR #32's body).
3. CI exists (3 jobs) and is green — still not confirmed in this resume prompt's own history;
   check its current state at the start of the next session rather than assuming.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error events row.
6. Gate C rejects a malformed shot heading — done, verified end to end (CLI-side by P11, app-side
   by P3's T7B).
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing.
