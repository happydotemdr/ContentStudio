# rgs-briefs/

Saved Grounding Briefs produced by the `rgs-grounding` skill — one file per RaisingGoodSports
Short that has been through grounding. This directory is the production ledger: `rgs-grounding`
live-globs this directory's front-matter on every invocation to avoid over-repeating the same
thinker or the same concept×code pairing across recent Shorts.

Git-tracked deliberately — these are original editorial decisions, not downloaded/regenerable
corpus data (unlike `output/`, which is git-ignored).

## Naming

`YYYY-MM-DD-<topic-slug>.md` — one file per grounding brief, dated by the day it was produced.

## Front-matter schema

```yaml
---
date: 2026-07-25
topic: "why kids quit travel sports around age 13"
thinker: "Thorstein Veblen"
concept: "Invidious comparison"
research_codes: [F4]
archetype: A1
status: candidate
---
```

- `status` is `candidate` until the Short is actually produced, then hand-edit to `produced` or
  delete the file if the topic was abandoned. `rgs-grounding`'s recency rules apply to files
  regardless of `status` — even an abandoned candidate reflects a recent pairing choice.
- **For downstream consumers** (`shorts-ideation`, `shorts-scripting`, `visual-prompts`): a brief
  with `status: candidate` or `status: produced` is safe to hand forward as a companion grounding
  artifact. A brief hand-edited to any other value, or whose `date` predates the most recent
  refresh of the research/thinker corpora it cites, should be flagged before use rather than
  consumed silently — see each generic skill's "Optional input" section for the exact rule.

## Who reads this

- `rgs-grounding` (soft recency/variety rules — deprioritize a thinker used in the last ~5
  briefs by filename date; flag an exact concept×code repeat within the last ~15).
- `rgs-pairing-review` (greps for a "Gap-fill flag" section — see
  `.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md` — to catch pairings that
  came from the live-glob fallback rather than the curated map, so they enter the next review).
