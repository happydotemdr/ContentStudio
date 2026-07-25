---
name: rgs-pairing-review
description: Use when the thinkers corpus or RaisingGoodSports research corpus has been refreshed or expanded — new thinker works added to manifests/thinkers.json, or a research theme file re-split at a new edition — to detect what's new since the last pairing-map review and propose curated additions, or when asked to "review the pairing map," "check for new thinker or research content," or "expand the pairing map." Brand-specific to RaisingGoodSports; never runs on a schedule, only on request.
---

# RGS Pairing Review

A thin maintenance skill, separate from `rgs-grounding`: disjoint trigger ("I refreshed the
corpus, review the map") and disjoint output (a proposal document, not a Grounding Brief). Has
no `references/` of its own — it reads `rgs-grounding`'s
`.claude/skills/rgs-grounding/references/pairing-map.md` as its format and quality-bar
contract, so the quality criteria live in exactly one place.

**Never writes directly to `pairing-map.md`.** Every run ends in a proposal document the human
reviews; the human (or this skill, once told which rows to accept) then edits `pairing-map.md`
directly, and the resulting `git diff` on that file is the actual approval surface — mirroring
`output/youth-sports/raisinggoodsports/README.md`'s existing corpus-refresh approval pattern
("re-split the changed themes, get owner approval on the per-theme git diffs, then run the
ingest").

## Workflow

### 1. Read the current ledger

Open `.claude/skills/rgs-grounding/references/pairing-map.md`'s front-matter:
`last_review`, `thinker_slugs_reviewed`, `research_codes_reviewed`.

### 2. Diff against current corpus state — three checks

- **New thinker works:** every `slug` in `manifests/thinkers.json` tagged `parenting`, plus any
  new work by one of the brand's 7 signature thinkers (per `output/raisinggoodsports-brand-definition.md`)
  regardless of its pillar tags, not present in `thinker_slugs_reviewed`. Don't diff against the
  full 53-slug manifest unscoped — most of it (Adam Smith, Barnum, etc.) is unrelated to this
  brand and would flood every review with irrelevant "new" items.
- **New research:** every `code` across `output/youth-sports/raisinggoodsports/rgs-*.md`
  front-matter not present in `research_codes_reviewed` — **excluding any file whose front-matter
  `section` is `Meta`** (`rgs-meta-landscape-map.md`, `rgs-meta-open-questions.md`,
  `rgs-meta-verify-policy.md` — codes `LANDSCAPE`, `OPENQ`, `VERIFY`). These are reference/policy
  documents, not pairable research themes, and are deliberately absent from
  `research_codes_reviewed` — don't flag them as new on this or any future run.
- **Changed research:** every code that IS in `research_codes_reviewed` whose current file
  `edition` no longer matches the recorded value. For each, list every existing `pairing-map.md`
  row citing that code — these need re-verification, not just the new-row consideration new
  codes get.

### 3. Secondary signal — organically-flagged gaps

Grep `rgs-briefs/*.md` for the literal heading `## Gap-fill flag` (see `rgs-grounding`'s
`references/thinker-corpus-protocol.md`). Each match is a pairing `rgs-grounding` used outside
the map — add it to this review pass as a candidate, even if its thinker/research slugs were
already in the reviewed lists.

### 4. Verify and draft, or reject with a reason

For every new/changed/flagged item, run the identical source-open verification `rgs-grounding`
uses (open the thinker's `.cleaned.md` and/or the research file's actual body): confirm a
genuine concept exists, find a real passage/anchor, and check whether it pairs with something
already in scope. Draft a candidate row in `pairing-map.md`'s exact format (thinker heading,
concept subheading, all five fields) — never propose a row that hasn't actually been checked
against source; an unverified proposal turns the human's approval into a rubber stamp on an
unearned pairing. Where nothing fits, write "considered, no pairing found" with a one-line
reason. Zero new rows is an explicitly valid outcome of a review — say so plainly if that's
what happened, don't manufacture a weak row to have something to show.

### 5. Write the proposal

Save to `output/pairing-proposals/YYYY-MM-DD-proposal.md` (git-ignored — disposable working
material, unlike the `pairing-map.md` it feeds):

```markdown
# Pairing Map Review Proposal — [date]

## New/changed since last review ([last_review date])
- Thinkers: [list, or "none"]
- Research codes (new): [list, or "none"]
- Research codes (edition-changed): [list with old→new edition, or "none"]
- Gap-fill flags found in rgs-briefs/: [list with source brief filenames, or "none"]

## Proposed additions
[Each in pairing-map.md's exact row format, or "none proposed this review."]

## Considered and rejected
[One line each: what was checked, why it didn't earn a row.]

## Re-verification verdicts (edition-changed codes only)
[For each existing row citing a changed code: still holds / needs revision / needs removal, with reasoning.]
```

### 6. Get human approval, then apply

Present the proposal in conversation. On approval (whole or partial), edit the accepted rows
directly into `pairing-map.md`, and update its front-matter: bump `last_review` to today, add
every newly-considered thinker slug and research code (accepted or not — "considered" tracks
what was reviewed, not just what was kept) to `thinker_slugs_reviewed` /
`research_codes_reviewed`, and update any changed `edition` values. The human reviews the
resulting `git diff` on `pairing-map.md` before it's committed — that diff is the real gate.

## Red flags — stop and reconsider

- About to add a row to `pairing-map.md` before the human has approved this run's proposal →
  stop, that's a direct write, never allowed.
- About to propose a row without having opened the actual source file this run → stop, open it.
- Tempted to skip section 3 (the `rgs-briefs/` grep) because the diff in section 2 already found
  enough → don't skip it; organically-discovered gaps are a distinct signal from corpus growth.
