# Resume prompt — audit-remediation programme, start P12 (Wave B2, tripwire cluster)

Paste everything below the line into a fresh session. It is self-contained and assumes zero prior
context. `EXECUTION-KICKOFF-PROMPT.md` beside this file is the original programme brief and is
still binding verbatim; this document is the delta — where execution got to, what the next session
must do, and everything learned the hard way that is written down nowhere else.

Last updated 2026-08-14. **P3 (Gates & Approval) is merged into `main`**
([PR #32](https://github.com/happydotemdr/ContentStudio/pull/32), merge commit `02791e7`).
Combined with P0, P1, P2, P10, P11 already in `main`, **Wave B2's other two members (P3, P11) are
both done — P12 is the only member of that tripwire cluster left, and is next.**

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
P12 too; the mitigation that has worked every time is in "The recurring bug class" below.

## The repo

Worktree: `C:\Projects\ContentStudio\.claude\worktrees\pipeline-audit-review-4dd767`
Branch `claude/pipeline-audit-review-4dd767` — **already fast-forwarded to `origin/main` this
session** (HEAD `02791e7`, identical to `origin/main`). Verify this is still true before trusting
it (`git fetch origin main && git rev-parse HEAD origin/main` — they should match); if the
operator did other work on `main` between sessions, fast-forward again the same way. Main branch
`main`. Windows 11, PowerShell primary. Python is `C:/Python314/python.exe`.

Two commits must never be altered: `1d39c9d` (the audit) and `6c61f14` (the remediation
programme).

**The separate MAIN CHECKOUT** (`C:\Projects\ContentStudio`, where `pipeline-app` is installed
editable) was **not** touched this session and is **one commit behind** `origin/main` as of this
writing (`ab77f06`, missing the P3 merge `02791e7`) — it also has the operator's own uncommitted
work in progress (`doc-ingest-app/` modifications, untracked `pipeline.db.backup-pre-migration*`
files, two untracked `rgs-briefs/*.md` drafts). **Do not `git pull`/`merge`/`reset` there yourself**
— it has real uncommitted changes that aren't yours to touch. Re-run the same fetch+status check
at the start of your session (`cd C:\Projects\ContentStudio && git fetch origin main && git status
--short && git log --oneline -3`) to see its current state before assuming anything about it; if
it still needs the P3 merge and that's blocking something, ask the operator rather than pulling
over their uncommitted work.

**Baseline suite counts, verified this session at `HEAD 02791e7`:**
- Root suite (`python -m pytest tests/ -q` from repo root): **371 passed, 1 failed** — the same
  documented, deliberately-deferred exception as every prior session
  (`test_lint_prompt_sheet.py::test_a_single_mutation_of_a_green_sheet_always_fails_gate_c[fenced-heading]`,
  P11-owned, not P3's or P12's file). The pass count rose from 355 to 371 because `main` also
  picked up an unrelated merge (PR #31, a `doc-ingest-app/` feature) between P3's branch-push and
  its merge — not your concern, just why the number moved.
- App suite (`cd pipeline-app && python -m pytest -q`): **31 failed, 1204 passed, 3 skipped.** All
  31 are pre-existing, in files P3 either doesn't fully own or wasn't asked to repair (see
  [PR #32](https://github.com/happydotemdr/ContentStudio/pull/32)'s body for the full breakdown —
  `write_pointer`/`gate_overrides` API-shape mismatches in test setup code across
  `test_routes_stages.py`, `test_approval_service.py`, `test_browse_service.py`,
  `test_routes_browse.py`, plus two unrelated single failures). **P12 does not own or need to fix
  these** — they are a separate, already-filed follow-up (see "Carried-forward open items" below).

## Where execution is — the landing order (unchanged from the original brief, reproduced here for convenience)

| Wave | Packages | Status |
|---|---|---|
| A | P0 → P1 | **merged** |
| B1 | P2, then P10 | **merged** |
| **B2** | **P3 + P11 + P12 together** | **P3 and P11 merged. P12 has not started — start it now.** |
| B3 | P4, then P5 | not started |
| B4 | P6, P7, then P8, and P9 | not started |
| B5 | P15 | not started |
| C | P13, then P14 | not started |

**Why P12 is next, precisely:** §7.2 of `EXECUTION-KICKOFF-PROMPT.md` says P3, P11 and P12 carry a
deliberate tripwire cluster and must land together, or the follower retires the tripwire in the
same commit. P11 landed first (tripwired P3's divergence-ledger test, which P3 already handled).
P3 has now landed. **P12's own T8 leaves a `strict=True` xfail that was meant to go red the moment
P3 landed — but P12 hasn't executed yet, so that xfail doesn't exist in the repo yet either.** See
the next section for exactly what this means for how you should execute P12 T6/T8 — it is NOT the
same sequence the plan's own prose describes, because the timing assumption behind that prose
(P12 running before P3) is now false.

## READ THIS BEFORE DISPATCHING P12 T6 OR T8 — the plan's own xfail choreography no longer applies

P12's plan file (`docs/superpowers/plans/remediation/P12-gate-d-tools.md`) was written assuming
P12 would execute *before* P3, so its T8 instructs: implement a source-scanning test that checks
`pipeline_app/gates.py` doesn't hardcode `!= "skipped"`, watch it fail, then **mark it
`@pytest.mark.xfail(reason="P3 owns gates.py; see P12 plan §6", strict=True)`** — the idea being
that this xfail turns into a loud `XPASS` failure "the moment P3 lands," which is the signal for
someone to go fix `gates.py` for real and delete the marker.

**That trigger condition — P3 landing — is already true, before you dispatch a single P12 task.**
Confirmed empirically this session: `pipeline-app/pipeline_app/gates.py` (currently line ~430)
still reads:
```python
blocking = [f for f in findings if f.get("kind") != "skipped"]
```
Marking a fresh test `xfail` and watching it immediately need to become `XPASS`-and-deleted in the
very same task is theater with no purpose here — **skip the xfail step entirely.** But — and this
is the part that actually matters — **you cannot fix `gates.py`'s line yet either**, because the
real fix (`blocking = [f for f in findings if f.get("kind") not in linter.NON_BLOCKING_KINDS]`,
per the plan's own §6.1) needs `linter.NON_BLOCKING_KINDS` and `linter.is_blocking()` to exist in
`scripts/lint_script_language.py` first — and **those don't exist yet either**; they are created
by **P12's own T6**, not by anything already in `main`.

**The correct sequence, different from both the plan's literal T8 text and from doing nothing:**

1. Execute P12 T1 through T6 in order as written (T6 is what adds `NON_BLOCKING_KINDS`/
   `is_blocking`/`BUZZWORD_LEMMAS` to `scripts/lint_script_language.py`).
2. **Immediately after T6 lands** (before T7/T8, or interleaved with them — your call on exact
   ordering, but T6 must precede this step), do the small `gates.py` fix as its own mini-task,
   since `gates.py` is P3's file but P3 is now merged — it is no longer under any active branch's
   exclusive ownership, and no other in-flight package needs it, so there is nothing to coordinate
   around beyond doing it carefully and documenting why:
   - **Important, confirmed this session — the plan's own §6.1 phrasing (`linter.NON_BLOCKING_KINDS`)
     is misleading about WHERE the fix goes.** The `blocking = [f for f in findings if
     f.get("kind") != "skipped"]` line lives inside `run_gates_for_stage`'s generic dispatch loop
     (around line 428, currently), which iterates over **every gate registered for a stage_id**
     (Gate C, Gate D, Gate S — whichever apply) and judges already-returned `dict` findings
     generically. There is **no `linter` variable in scope at that point** — each `runner(...)`
     call already returned plain dicts, with no linter module handle attached. You cannot write
     `linter.NON_BLOCKING_KINDS` literally as the plan's prose suggests; grep the function body
     yourself to confirm before trusting this note, since it may have changed. The fix instead
     needs a **`gates.py`-level constant**, e.g. `_NON_BLOCKING_KINDS = frozenset({"skipped",
     "info"})` defined near the top of `gates.py`, with `blocking = [f for f in findings if
     f.get("kind") not in _NON_BLOCKING_KINDS]`. Confirmed this session: neither Gate C
     (`lint_prompt_sheet.py`) nor Gate S (`gates.py`'s own `_check_styleboard_slots`) currently
     emits a `"skipped"` or `"info"` kind finding — only Gate D (`lint_script_language.py:417`,
     pre-P12) uses `"skipped"`, and P12's own T6 is what introduces `"info"`. So today the
     gate-agnostic constant and Gate D's own `NON_BLOCKING_KINDS` happen to be the same two
     strings — but they are two SEPARATE definitions (one in `scripts/lint_script_language.py`
     for the CLI, one in `pipeline_app/gates.py` for the generic dispatch loop), not one shared
     import, because `run_gates_for_stage` genuinely cannot know which linter produced a given
     finding. Document this distinction in your commit — a future gate adding a new non-blocking
     `kind` must update BOTH constants, and that is exactly the kind of drift a comment here
     should call out explicitly, not paper over.
   - Add the §6.2 "mirror test" to the **app suite** (`pipeline-app/tests/test_gates.py`):
     assert that `run_script_language_gate(repo_root, path, {})`'s findings (in order, with
     `kind`s) equal `linter.lint(*linter.parse_script(text), text)`'s serialized output, run over
     `CLEAN_SCRIPT` plus at least three of T7's mutation rows, and that `status` is `"fail"`
     exactly when the CLI's `main()` returns `1`. This is what makes the two-caller parity
     property real on the app side, not just asserted about the CLI side.
   - Also fix what the contract note flags as a rendering hazard: Gate D now emits findings with
     `beat is None` for some checks (`check_beat_set`, the ratable-fraction finding, the D3/D4
     scope note) — confirm nothing in `gates.py`'s `_as_dicts` or `routes/stages.py`'s gate
     rendering (the `gate_view`/Gates-panel work from P3) assumes a beat string and would `KeyError`
     or literally render the word `"None"`. Check empirically against the live template
     (`pipeline_app/templates/stage.html`, the Gates panel P3's final review just rewired to
     render `gate_view`) before assuming it's fine.
   - `_as_dicts` must pass `kind` through verbatim — confirm it does not default a missing `kind`
     to `"skipped"` (read the function; this is a one-line check, not a rewrite).
3. **Now write P12's own T8** exactly as its plan text describes for the CLI half
   (`test_the_cli_exit_code_is_exactly_the_blocking_predicate` — no xfail needed there, it was
   never gated on P3), but for the `gates.py`-hardcoding test
   (`test_gates_py_does_not_hardcode_the_blocking_kind`), write it as a **plain, non-xfail
   assertion** — it should pass immediately because you already fixed `gates.py` in step 2. Do
   not mark it xfail and do not expect it to fail; if it does fail at this point, your step-2 fix
   is incomplete or came after a rebase that reverted it — investigate, don't paper over it with
   xfail.
4. Continue T9 onward as written.

This whole detour is itself an instance of "The recurring bug class" below — treat it as the
worked example, not a one-off.

## The recurring bug class — check for it before dispatching every task, not just this once

Every package executed since P2 has hit at least one instance of this, and P3 alone hit five: **a
task's own shown test/implementation code can reference a function, class, fixture, or
sibling-package API that doesn't exist yet at the point that task is dispatched** — because the
plan text was written assuming a landing order, a sibling package's state, or another task's
sequencing that turned out different from what's actually true in the live repo by the time you
get there. The mitigation, unchanged since P2:

1. **Grep for every symbol a task's own shown code references** before dispatching it — function
   names, class names, fixture names, other packages' modules — and confirm each either already
   exists live, or is defined within that same task's own text.
2. If something's missing: **amend the plan file FIRST**, as a `>` blockquote note inserted
   directly at the relevant task, **with its own commit** explaining what was wrong and why —
   then dispatch the corrected version. Never fix a gap silently inline without amending the plan.
3. Your own amendments can contain the same class of bug — re-verify their own claims (exact line
   numbers, exact counts, exact function signatures) against the live repo before committing them,
   the same discipline P3's five amendments this session were held to.

P3's own five instances, for pattern-matching (full detail in `P3-gates-approval.md`'s own
blockquote history and in [PR #32](https://github.com/happydotemdr/ContentStudio/pull/32)'s body):
a test needing UI wiring three tasks away; a plan-text count of "five" that was actually six once
an earlier task's own already-landed text was accounted for; a task needing a sibling,
not-yet-executed package's function; a fix that broke an earlier task's own exact-equality test on
a by-design wording split; and a task asking for two keywords owned by a different, not-yet-run
package. **P12's own T6/T8 sequencing issue (above) is a sixth instance, found and resolved before
this resume prompt was even written — read it as the concrete template for what "grep every
referenced symbol first" looks like in practice.**

## Frozen cross-package interfaces (unchanged, reproduced for convenience)

- `obs.log(event, *, level, **fields)` and `obs.record_event(conn, *, kind, severity, source,
  message, detail, run_id) -> int`. `record_event` must never raise.
- `gates.resolve_upstream_by_stage(*, repo_root=None, approved_only=False,
  include_optional=False)` returns an `UpstreamMap` with three states — absent/present/excluded —
  where reading an excluded key raises.
- `| safe` means "sanitized by its producer." P3 wrote its own private sanitizer in
  `routes/stages.py` (a HANDOFF, since the intended owner, P15, hasn't executed) — do not assume
  `browse_service.sanitize_html` exists; it still doesn't.
- **P3 → P15 stage context keys** (now live, confirmed): `gate_view[]` (`state ∈
  passed|failed|errored|never_ran|unknown|malformed`), `has_blocking_gate`, `gate_override`/
  `gate_overrides[]`, `artifact_version`, `artifact_created_at`, `artifact_finalized_at`,
  `inputs[]` (`present`/`malformed`/`artifact`/`body`/`html` per declared dependency),
  `edit_allowed`/`edit_blocked_reason`/`edit_action`/`edit_field`, `error_banner`. A blocked
  approve is 409 re-rendering `stage.html`, never a `PlainTextResponse` — confirmed, zero
  `PlainTextResponse` sites remain in `routes/stages.py`.
- **P1 → P15:** `recent_events[]` and `orphaned_count: int | None`, `None` must render differently
  from `0`.
- **P4 still hasn't executed.** Two things P3 wanted from it are deferred and documented in
  `P3-gates-approval.md`'s T24 amendment: `turn_service.propagate_staleness` needs an optional
  `repo_root=` keyword, and a `turn_service.propagate_grounding_staleness` function doesn't exist
  yet. Not P12's concern, but don't be surprised if you see the gap while reading `routes/stages.py`.

## Carried-forward open items (none are P12's job; know they exist)

Two operator decisions remain open, unresolved, not any package's call — surface them again if the
operator hasn't weighed in (repeated in every resume prompt since P10/P11):

1. `T21R-01` — the `CLOSE`/`MACRO` 1-object-floor carve-out in Gate C's C8 check (P11's file).
2. `T6R-02` — what should catch an extra fenced example block mid-sheet (the one documented
   root-suite exception, `test_lint_prompt_sheet.py::...[fenced-heading]`, unchanged for many
   sessions now).

From P3's final review, filed for a small future follow-up task (not P12's; do not fold these
into P12's own work unless a P12 task happens to touch the exact same lines):

3. Nine test failures in files P3 owns (`test_routes_stages.py` x3, `test_approval_service.py`
   x6) assert a pre-P2 API shape.
4. A scratch-file interleaving hazard in `routes/stages.py`'s hand-edit route (concurrent edits to
   the same stage share one fixed scratch filename).
5. Gate messages on that same hand-edit path name the scratch filename instead of a stable display
   name.
6. Eight Minor findings (an unused `_approved_artifact_path` parameter — a trap for P4 — plus
   seven more; full list in PR #32's body).
7. New CSS classes (`status-blocking`, `status-ok`, `input-missing`, `input-malformed`) introduced
   by P3's final-review fix wave have no stylesheet rules yet — correct semantics, missing color.

## Traps, verbatim (carried forward from every prior session, still binding)

- `python -m` is mandatory. A bare `pytest` at the repo root silently omits all app tests.
- `pipeline-app` is installed EDITABLE against the MAIN checkout (`C:\Projects\ContentStudio`),
  not this worktree. Bake an explicit working-directory check (`pwd && git rev-parse
  --show-toplevel && git branch --show-current`) into every dispatch prompt.
- The live database is `C:\Projects\ContentStudio\pipeline-app\pipeline.db` — main checkout,
  git-ignored. Never write to it.
- `subprocess` with `text=True` decodes as cp1252 on this host. Always `encoding="utf-8",
  errors="replace"`.
- `os.kill(pid, 0)` terminates the process on Windows. Use `OpenProcess` for liveness.
- Never invoke `bash`/`sh` by bare name in a subprocess. Resolve with `shutil.which()`.
- Writing a commit message through `bash -c "..."` eats anything in backticks; write long/quote-
  heavy commit or PR bodies to a file and use `-F`/`--body-file` instead of an inline heredoc.
- `grep -c` exits 1 when the count is zero, silently truncating a `&&` chain. Use `;` instead.
- A `str` regex's `\d` is Unicode-aware in Python; `int()` parses non-ASCII decimal digits. Use
  `[0-9]` and verify empirically if parsing any numeric field from a filename or frontmatter value.
- In this specific harness, the Bash tool's working directory resets to the worktree path after
  every separate call — `cd` does not persist between calls. Chain multi-step operations touching
  a different directory in one command.
- A regex with a fully-optional trailing group after a non-greedy `.*?`, matched with `.match()`
  (not `.fullmatch()`), will silently never capture the optional group.
- When two independently-written pieces of text/code both need to find something via a
  first-occurrence string match, and one can textually contain what the other searches for, they
  will collide.
- A hand-written HTML sanitizer built on `html.parser.HTMLParser` must escape TEXT NODES
  (`handle_data`), not just attribute values — `convert_charrefs=True` hands `handle_data`
  already entity-DECODED text, so markdown-escaped `&lt;script&gt;` inside a code block
  round-trips back to a live `<script>` tag if re-emitted verbatim. Also:
  `HTMLParser.CDATA_CONTENT_ELEMENTS` is `("script", "style")`, not just `"script"`. (Only
  relevant if a future package touches `routes/stages.py`'s sanitizer again — P12 shouldn't need
  to, but if you find yourself there, this bit P3's final review twice.)
- **New from this session:** a plan's own choreography for a cross-package tripwire (mark xfail →
  wait for the sibling to land → XPASS signals cleanup) can itself go stale if the sibling lands
  *before* the tripwire-owning package even starts. Check the actual trigger condition against the
  live repo before mechanically following the plan's literal steps — see "READ THIS BEFORE
  DISPATCHING P12 T6 OR T8" above for the worked example.

## Definition of done (the whole programme, not any one package)

1. All 328 findings closed — each verified by the mechanism its plan names. P3's own 22 are
   confirmed closed independently by its mandatory final review. Count each package's own total
   from its merged PR, not from memory.
2. Both suites green everywhere they can be: root suite 371/1 (the one documented T6R-02
   exception); app suite 31/1204/3 as of P3's merge (see "Carried-forward open items" #3 above for
   what would close the remaining 9 that are P3-owned).
3. CI exists (3 jobs, from P0) and is green — check its current state at session start rather than
   assuming; not reconfirmed this session.
4. Every S0/S1 has an observed-failing-first regression test.
5. A scheduled discovery run with an injected fault exits non-zero with an error events row.
6. Gate C rejects a malformed shot heading — done, verified end to end (CLI-side by P11, app-side
   by P3).
7. `git grep "pipeline-app/scripts" -- '*.md'` returns nothing — the F-64 atomic rename
   (`pipeline-app/scripts/` → `pipeline-app/tools/`, §7.3 of the kickoff brief) is **not** P12's
   task; confirmed this session it's referenced in `P0-harness-ci.md`, `P8-engine-cron.md`, and
   `P14-docs-truth.md` — P8 is the one that actually performs the move (per the kickoff brief's
   own "P8's `setup_discovery_task.py` update" phrasing), in Wave B4, well after P12. Not
   something to check for or worry about until P8's turn.
