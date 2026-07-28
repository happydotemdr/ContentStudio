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

`YYYY-MM-DD-<topic-slug>.md` for a grounding brief's first version (`v1`,
implicit — no `-v1` suffix). A regenerated grounding brief for the same
topic — whether the rerun happens the same day or a later one — gets
`YYYY-MM-DD-<topic-slug>-v2.md` (then `-v3`, …), never an overwrite of the
existing file, and the date in the filename is always the day *that
version* was written (so a `-v2` produced on a later date carries that
later date, not the `v1` file's original date).

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

Grounding brief:

```yaml
---
date: 2026-07-25
topic: "why kids quit travel sports around age 13"
thinker: "Thorstein Veblen"
concept: "Invidious comparison"
research_codes: [F4]
archetype: A1
version: 1
status: candidate
---
```

Stage artifact (concept-brief, script, voiceover-brief, visual-prompts,
assembly, social-repurpose):

```yaml
---
date: 2026-07-28
kind: script
slug: decline-the-next-level
stage: 02-scripting
version: 1
concept_brief: rgs-briefs/2026-07-28-decline-the-next-level-concept-brief.md
grounding: rgs-briefs/2026-07-28-decline-the-next-level.md
status: complete
---
```

- `version` is a required integer on every file in this directory, starting
  at `1`. `supersedes: rgs-briefs/<path>` is added only when `version > 1`,
  pointing at the immediately-prior version's path.
- Files here are **immutable once written** — a revision always produces a
  new, higher-version file (`...-v2.md`, `...-v3.md`, …), never an edit to
  an existing one. This is enforced by a `PreToolUse` hook
  (`.claude/hooks/protect_briefs.py`), not just by convention.
- `scripts/resolve_brief_version.py` is the canonical way to find the latest
  version of a given slug/kind, or to compute the next version's filename —
  consumers should use it rather than re-implementing glob-and-sort logic.
- `status` is `candidate` until the Short is actually produced. Marking a
  Short produced is a new version write like any other change — write a
  `-v2` with `status: produced` and a `supersedes:` pointer back at the
  `candidate` version, rather than hand-editing the existing file. There is
  no exception to immutability here or anywhere else in this directory
  (`rgs-briefs/README.md` itself is the one file in this directory that
  isn't a versioned artifact and can be edited normally).

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
- Any consumer scanning this directory for "the current state of topic X" or
  "the current state of Short Y's stage Z" must resolve to the **latest
  version** (via `scripts/resolve_brief_version.py`, or by parsing
  frontmatter `version:` directly) — an older version of the same
  topic/slug/kind must never be double-counted as a second, separate entry.

## Thinkers spent to date

`rgs-grounding` deprioritizes recently-used thinkers. As of 2026-07-28 the ledger has used
Veblen, Rousseau, Aristotle, Adler, Ellen Key, Plutarch, **Dewey** (2026-07-28, Short A) and
**Charlotte Mason** (2026-07-28, Short B). **William James remains unused and is `quote-ok`.**
This list is a convenience, not the source of truth — the front-matter glob is.
