# rgs-briefs/

The RaisingGoodSports production ledger. It holds **two kinds of file**, distinguished by
front-matter (see "Two file kinds" below):

1. **Grounding Briefs** produced by the `rgs-grounding` skill — one per Short that has been
   through grounding. `rgs-grounding` live-globs this directory's front-matter on every
   invocation to avoid over-repeating the same thinker or the same concept×code pairing
   across recent Shorts.
2. **Run and stage artifacts** — everything downstream of grounding (concept briefs, scripts,
   voiceover briefs, visual prompt sheets, assembly plans, repurpose copy) plus run-level
   documents shared across a batch of Shorts (reference scans, sparks, visual systems).

Git-tracked deliberately — these are original editorial decisions, not downloaded/regenerable
corpus data (unlike `output/`, which is git-ignored).

## Naming

`YYYY-MM-DD-<topic-slug>.md` — one file per grounding brief, dated by the day it was produced.

Stage artifacts append the stage name to their Short's slug:
`YYYY-MM-DD-<topic-slug>-<stage>.md`, where `<stage>` is one of `concept-brief`, `script`,
`voiceover-brief`, `visual-prompts`, `assembly`, `social-repurpose`. Run-level documents shared
by several Shorts use a run slug instead of a topic slug — e.g.
`2026-07-28-rgs-debut-reference-scan.md`.

## Two file kinds — and the rule that keeps them apart

A **grounding brief** carries `thinker`, `concept`, `research_codes` and `archetype`, and has
**no** `kind` field. Every other file here carries a **`kind:`** field naming what it is
(`reference-scan`, `sparks`, `visual-system`, …) and omits the grounding fields.

> **Consumers that glob this directory MUST skip any file with a `kind:` field.**
> This applies to `rgs-grounding`'s recency and repeat checks and to `rgs-pairing-review`.
> A `kind:`-bearing file has no `thinker`/`concept`/`research_codes` to compare, and treating
> one as a grounding brief will either crash the check or silently corrupt the recency window.

## Provenance markers used in this directory

Artifacts here carry the repo-wide `[C]` / `[I]` / `[T]` / `[T-unverified]` markers defined in
`CLAUDE.md`, plus two that are **scoped to RaisingGoodSports artifacts only**:

| Marker | Means | Cite as |
|---|---|---|
| `[C]` | The **420-video ContentStudio corpus**. Repo-canonical — never redefine it locally. | `(Channel, video_id)` |
| `[REF]` | A **reference-scan cohort** — the competitor videos scanned for a specific run. Not a corpus citation, and **not generalizable beyond that cohort**. | `(Channel, video_id)` |
| `[B]` | A claim from `output/raisinggoodsports-brand-definition.md`. | — |
| `[C→I]` | A corpus principle **extrapolated** to a surface the corpus does not cover. Must state both the principle and the extrapolation. | `(Channel, video_id)` for the principle |

`[REF]` exists so that scanning a competitor cohort can never masquerade as corpus grounding.
Every artifact using these should still carry its own marker legend.

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
  consumed silently — see `shorts-ideation`'s "Optional input" section (the pipeline's entry
  point) for the exact staleness-check rule.

## Who reads this

- `rgs-grounding` (soft recency/variety rules — deprioritize a thinker used in the last ~5
  briefs by filename date; flag an exact concept×code repeat within the last ~15). **Must skip
  `kind:`-bearing files.**
- `rgs-pairing-review` (greps for a "Gap-fill flag" section — see
  `.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md` — to catch pairings that
  came from the live-glob fallback rather than the curated map, so they enter the next review).
  **Must skip `kind:`-bearing files.**
- `pipeline-app`'s `grounding_service.snapshot_rgs_briefs()` hashes `*.md` here and
  `identify_new_brief()` requires **exactly one** file to have changed. A batch run that writes
  several files at once will return `None` from that function — expected, not a bug, but worth
  knowing before relying on it.

## Thinkers spent to date

`rgs-grounding` deprioritizes recently-used thinkers. As of 2026-07-28 the ledger has used
Veblen, Rousseau, Aristotle, Adler, Ellen Key, Plutarch, **Dewey** (2026-07-28, Short A) and
**Charlotte Mason** (2026-07-28, Short B). **William James remains unused and is `quote-ok`.**
This list is a convenience, not the source of truth — the front-matter glob is.
