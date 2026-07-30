# PR Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lean GitHub PR template so Brian can quickly verify a Claude-authored PR matches what was asked before merging.

**Architecture:** A single static Markdown file at `.github/PULL_REQUEST_TEMPLATE.md`. GitHub auto-populates its contents into the description box of every new PR on this repo — no app code, no CI, no other files involved.

**Tech Stack:** Markdown only. No build step, no dependencies.

## Global Constraints

- ContentStudio only — not a portable/general-purpose template (per spec's Scope section).
- Exactly one file: `.github/PULL_REQUEST_TEMPLATE.md`. No `.github/workflows/` or other GitHub config is added.
- Three sections only, in this exact order: Summary, Related plan/spec, Verification (per spec's Design section).
- Verification section is free-text prose, not a checkbox list (per spec: "avoid box-checking theater").
- No corpus-provenance checklist and no risk/blast-radius section — explicitly out of scope per spec.

---

### Task 1: Create the PR template file

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

**Interfaces:**
- Consumes: nothing (first and only task).
- Produces: nothing consumed by other tasks — this is the complete deliverable.

- [ ] **Step 1: Create the `.github` directory if it doesn't exist and write the template file**

Write `.github/PULL_REQUEST_TEMPLATE.md` with exactly this content:

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

- [ ] **Step 2: Verify the file content matches exactly**

Run: `cat .github/PULL_REQUEST_TEMPLATE.md` (or open the file)
Expected: Output matches the content in Step 1 exactly — three `##` headings in order (Summary, Related plan/spec, Verification), each with its HTML comment, and a single `- ` bullet stub under Summary.

There is no automated test for this file (it's static Markdown with no executable behavior, per the spec's Testing section) — visual diff against Step 1's content is the verification.

- [ ] **Step 3: Commit**

```bash
git add .github/PULL_REQUEST_TEMPLATE.md
git commit -m "$(cat <<'EOF'
feat(github): add lean PR template

Three sections (Summary, Related plan/spec, Verification) so Brian
can quickly confirm a Claude-authored PR matches the original ask
before merging. Spec: docs/superpowers/specs/2026-07-30-pr-template-design.md
EOF
)"
```
