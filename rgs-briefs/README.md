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
`styleboard`, `voiceover-brief`, `visual-prompts`, `music`, `assembly`, `social-repurpose` — one
per producing stage in `pipeline.yaml`, in that order. Run-level documents shared by several
Shorts use a run slug instead of a topic slug — e.g.
`2026-07-28-rgs-debut-reference-scan.md`, and carry `kind:` values of their own
(`reference-scan`, `sparks`, `visual-system`).

> **`styleboard` and `music` have never been written.** As of 2026-08-08 this directory holds zero
> artifacts of either kind. Neither `shorts-styleboard` nor `music-brief` has run end to end
> against this ledger, so neither one's frontmatter contract has ever been exercised by a real
> file — the two rows above are a specification, not a precedent. Treat them as untested until the
> first Short produces one, and check the emitted frontmatter against §Front-matter schema by hand
> that first time.
>
> The two are not equally optional. In `pipeline.yaml`, `assembly.depends_on` includes
> **`styleboard`** — a Short cannot reach assembly without one — while `music` sits in
> `assembly.optional_depends_on`. So the missing `styleboard` artifact is a gap in a *required*
> stage that no Short has yet exercised; the missing `music` artifact is a gap in an optional one.
> `tests/test_doc_truth.py::test_rgs_briefs_readme_enumerates_every_producing_pipeline_stage`
> keeps this enumeration in step with `pipeline.yaml`; it cannot tell you whether the stage works.

### `kind:` vocabulary — the complete set

| `kind:` | Written by | Scope |
|---|---|---|
| `concept-brief` | `shorts-ideation` | one Short |
| `script` | `shorts-scripting` | one Short |
| `styleboard` | `shorts-styleboard` | one Short — **never yet written** |
| `voiceover-brief` | `voiceover-brief` | one Short |
| `visual-prompts` | `visual-prompts` | one Short |
| `music` | `music-brief` | one Short — **never yet written** |
| `assembly` | `shorts-assembly` | one Short |
| `social-repurpose` | `social-repurpose` | one Short |
| `reference-scan` | run-level, by hand | a batch of Shorts |
| `sparks` | run-level, by hand | a batch of Shorts |
| `visual-system` | run-level, by hand | a batch of Shorts |

No other value is valid. `2026-07-25-let-kids-play-act-specialization-visual-prompts.md` carries
the one-off `kind: visual-prompt-sheet`; it is immutable and stays as written, and is listed here
as a known deviation rather than a permitted spelling. Emit `visual-prompts`.

## Two file kinds — and the rule that keeps them apart

A **grounding brief** is a file whose front-matter carries all three of `thinker`, `concept` and
`research_codes` (plus `archetype`). Everything else in this directory — stage artifacts and
run-level documents alike — is not a grounding brief.

> **Consumers that glob this directory MUST select grounding briefs positively: a file counts only
> if it has `thinker` AND `concept` AND `research_codes`.**
> This applies to `rgs-grounding`'s recency and repeat checks and to `rgs-pairing-review`.
>
> **Do not use "has no `kind:`" as the test.** Ten stage artifacts written on 2026-07-25 — the
> whole `let-kids-play-act` and `let-kids-play-act-specialization` chains — predate the `kind:`
> contract and carry only `version: 1`. A `kind:`-skipping consumer reads all ten as grounding
> briefs, then finds no `thinker`/`concept`/`research_codes` to compare and either crashes or
> silently corrupts the recency window with ten phantom pairings. Those ten files are immutable
> (`.claude/hooks/protect_briefs.py`), so the discriminator is what changes, not the files.
>
> Every file written since 2026-07-28 does carry `kind:`, and new artifacts must keep carrying it —
> it is how a *human* tells the files apart at a glance, and it is what §"`kind:` vocabulary"
> enumerates. It is simply not what a *program* should branch on.

`tests/test_doc_truth.py::test_positive_and_negative_discriminators_disagree_on_exactly_the_known_ten`
pins the size of that disagreement, so neither an eleventh pre-contract file nor a quiet backfill
can change the rule's blast radius without a test failing.

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

Stage artifact (concept-brief, script, styleboard, voiceover-brief, visual-prompts,
music, assembly, social-repurpose):

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
- **The `status` vocabulary differs by file kind — the two are not
  interchangeable.** Grounding briefs use `status: candidate` → `status:
  produced` (the latter written as a new, higher `version`, per the bullet
  above). Stage artifacts (concept-brief, script, styleboard, voiceover-brief,
  visual-prompts, music, assembly, social-repurpose) use `status: complete` or
  `status: draft` instead — `complete` for a finished handoff-ready artifact,
  `draft` for a version written mid-revision that isn't yet ready to hand to
  the next stage. Neither vocabulary applies to the other file kind.
- `rgs-grounding`'s recency rules apply to a grounding brief regardless of
  its `status` — even a `candidate` that never advances to `produced` still
  reflects a recent pairing choice and counts toward the recency/variety
  window. Only the **latest version** of a given topic slug counts for this
  purpose (via `scripts/resolve_brief_version.py`); a superseded `v1` must
  never be double-counted alongside its `v2`.
- **For downstream consumers** (`shorts-ideation`, `shorts-scripting`,
  `visual-prompts`): resolve the grounding brief for a topic via
  `scripts/resolve_brief_version.py` (never a raw glob) so you always land on
  its latest version. A brief whose latest version has `status: candidate` or
  `status: produced` is safe to hand forward as a companion grounding
  artifact. A brief hand-edited to any other value, or whose `date` predates
  the most recent refresh of the research/thinker corpora it cites, should be
  flagged before use rather than consumed silently — see `shorts-ideation`'s
  "Optional input" section (the pipeline's entry point) for the exact
  staleness-check rule.

## History

**2026-07-28:** all pre-existing files in this directory as of this date were backfilled
with `version: 1` (a handful that predated any frontmatter contract also gained a minimal
`---\nversion: 1\n---` block) so that `scripts/resolve_brief_version.py` can resolve every
file here without error. No other content in any backfilled file was changed.

## Who reads this

- `rgs-grounding` (soft recency/variety rules — deprioritize a thinker used in the last ~5
  briefs by filename date; flag an exact concept×code repeat within the last ~15). **Must select positively on `thinker` + `concept` +
  `research_codes` — see "Two file kinds" above.**
- `rgs-pairing-review` (greps for a "Gap-fill flag" section — see
  `.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md` — to catch pairings that
  came from the live-glob fallback rather than the curated map, so they enter the next review).
  **Must select positively on `thinker` + `concept` +
  `research_codes` — see "Two file kinds" above.**
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
