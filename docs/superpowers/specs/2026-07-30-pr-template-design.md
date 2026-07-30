# PR Template — Design

## Problem

ContentStudio PRs (e.g. #2, #3) are opened by Claude Code sessions on branches
like `claude/pipeline-90s-cyberpunk-redesign-4ef404`. Brian is the sole
reviewer/merger. There is no `.github/PULL_REQUEST_TEMPLATE.md`, so each PR
description is whatever the session happened to write, with no consistent way
to quickly confirm a PR actually matches what was asked for.

## Goal

Add a lean PR template whose primary job is letting Brian quickly verify a PR
matches the original request, before merging.

## Scope

- ContentStudio only (not a portable/general-purpose template).
- Single file: `.github/PULL_REQUEST_TEMPLATE.md`.
- No CI/workflow changes — this repo has no `.github/workflows/` and none are
  being added here.

## Design

Three sections, in this order:

1. **Summary** — 1-3 bullets: what changed, and the plain-language request or
   problem it addresses. Scannable enough to judge "does this match what I
   asked for" without reading the diff first.
2. **Related plan/spec** — link to a `docs/superpowers/plans/...` or
   `docs/superpowers/specs/...` doc if the change traces back to a
   brainstorming/planning session; otherwise the placeholder text
   `N/A — no written plan for this change.`
3. **Verification** — free-text description of what was actually run or
   checked (e.g. `pytest`, `scripts/lint_prompt_sheet.py` / Gate C, a manual
   skill walkthrough) to confirm the change works, not just an assertion that
   it does. Deliberately prose, not a checkbox list, to avoid box-checking
   theater.

### Explicitly out of scope

- **Corpus-provenance checklist** ([C]/[I]/[T] marker verification) — already
  enforced during skill editing per the repo's `CLAUDE.md` anti-generic
  guarantee; not re-litigated at PR time.
- **Risk/blast-radius section** — not requested; the repo is small enough
  that Brian can judge this from the Summary and diff directly.
- Any required/enforced checkbox gating (e.g. GitHub required-field syntax) —
  this is a solo-reviewer repo, not a team process; the template is a
  scaffold, not a gate.

## Content sketch

```markdown
## Summary

<!-- What changed, and the request/problem this addresses. 1-3 bullets. -->

-

## Related plan/spec

<!-- Link to docs/superpowers/plans/... or specs/... if this came from a
     brainstorming/planning session. Otherwise: N/A — no written plan for
     this change. -->

## Verification

<!-- What you actually ran or checked to confirm this works (commands,
     output, manual walkthrough) — not just an assertion. -->
```

## Testing

N/A — this is a static Markdown template with no executable behavior. GitHub
auto-populates it into the PR description box on next PR creation; the way to
confirm it "works" is opening a new PR and seeing the template appear, which
is a manual one-time check, not an automated test.
