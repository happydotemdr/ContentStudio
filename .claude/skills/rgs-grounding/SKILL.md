---
name: rgs-grounding
description: Use when producing RaisingGoodSports content and a Short's script, hooks, or visual direction needs to be grounded in a specific historical thinker AND a specific youth-sports research finding — before writing a script for a RaisingGoodSports topic, when asked to "ground this Short," "find the thinker and research for this," "pair a thinker with research for this idea," or when starting the RaisingGoodSports content pipeline before shorts-ideation. Brand-specific to RaisingGoodSports only — not for the eight generic ContentStudio pipeline skills' brands.
---

# RGS Grounding

Turn a raw RaisingGoodSports topic into a **Grounding Brief**: one thinker citation and one
research citation, verified against source text, structured around the brand's hook → turn →
payoff → reframe spine. This is RaisingGoodSports's differentiator — "what a 100-year-old
thinker saw coming" — and the entire point is that every claim is earned by actually opening
the source, not recalled from what the model already knows about Veblen or Adler.

## Pipeline position

| | |
|---|---|
| **Upstream** | None — a raw RGS topic, pain point, or a specific thinker/finding already in mind |
| **This skill** | Topic → one verified Grounding Brief, saved to `rgs-briefs/` |
| **Downstream** | Feeds `shorts-ideation` (angle/archetype pick, via the concept brief's Grounding reference line). The same brief then travels forward to `shorts-scripting` (citation text per beat, mapped per `references/scripting-beat-mapping.md`), to **`shorts-styleboard`** (thinker/source and motif, which populate the world lock's `register_b_*` keys and `motif` directly), and to `visual-prompts` (**motif cue for shot composition only** — the register keys are the styleboard's job). Hand it forward at each stage; don't regenerate it |

## Why matching is map-first, not live-glob-first

An earlier draft of this skill live-queried the corpora and let judgment pick a fitting
pairing. That produces provenance theater: proving a thinker's work *exists* in a manifest is
not the same as grounding what you *say about it*. Read `references/pairing-map.md` first,
always — it's the only trusted set of matches. Live-glob (`references/thinker-corpus-protocol.md`
Path 2) is a flagged fallback for topics the map doesn't cover yet, never a first resort taken
for speed.

The map itself is maintained by `rgs-pairing-review` — a maintenance skill outside the staged
pipeline. When a run finds no fitting row, the right move is to raise it there (its Gap-fill flag
sweep picks up every `## Gap-fill flag` heading in `rgs-briefs/`), not to normalise the live-glob
fallback.

## Citation markers

`[THINKER: Name, Work, quotability]` and `[RESEARCH: Author Year, quality rating]` — not
`[C]`/`[I]`/`[T]` (those denote the unrelated 14-channel headless-YouTube corpus).

## Workflow

### 1. Confirm the topic is genuinely RGS-relevant

RaisingGoodSports covers youth-sports culture's effect on kids and families — status
competition, specialization/overuse, burnout/dropout, pay-to-play, the case for play/rest/
intrinsic worth. If the topic is generic parenting or generic sports content with no youth-
sports-culture angle, say so rather than forcing a pairing.

### 2. Build the Pairing Slate

Read `references/pairing-map.md`. Find 2–3 rows whose concept plausibly fits the topic (prefer
map rows; only reach for `references/thinker-corpus-protocol.md` Path 2 if nothing fits). For
each candidate, check `references/safety-sensitive-handling.md` if its research code is
R5/R11/R12/R14, and check `rgs-briefs/` (glob the last ~20 files by date, resolving each
topic-slug to its **latest version only** — an older version of a topic already re-grounded must
not be double-counted as a second use of its thinker) for a recency flag — deprioritize (don't
exclude) a thinker used in the last ~5 briefs; flag an exact concept×code repeat within the last
~15.

This step is cheap — map + front-matter + brief filenames only, no deep source reading yet.

```markdown
## Pairing Slate: [topic]

1. **[Thinker] × [Research code]** — [one-line mechanism link, from the map's "Why it links"]
   - Archetype: [A1 / A2 / A3 — see references/brand-voice-and-tone.md]
   - Quotability: [quote-ok / paraphrase-caution]
   - Safety flag: [none / R5 / R11 / R12 / R14 — note the extra handling this triggers]
   - Recency flag: [none / "[Thinker] used in the [date] brief"]
2. ...
3. ...

Pick one to proceed to a fully-verified Grounding Brief, or ask for a different topic framing.
```

Present this to the human and wait for a pick. **Non-interactive fallback** (no human available
to pick mid-invocation): proceed with the top-ranked row, and include an "Alternates
considered" appendix (below) in the final brief instead of stopping.

### 3. Verify the chosen pairing against source

Follow `references/thinker-corpus-protocol.md` and `references/research-corpus-protocol.md` in
full — open both the thinker's cleaned text and the research file's actual body. This step is
mandatory and does not get skipped for speed; see "Red flags" below.

### 4. Write the Grounding Brief

## Output contract

```markdown
---
date: [YYYY-MM-DD]
kind: grounding
slug: [topic-slug]
stage: 00-grounding
topic: "[topic]"
thinker: "[Name]"
concept: "[concept]"
research_codes: [[code]]
archetype: [A1/A2/A3]
version: [from `resolve_brief_version.py --next`, below]
supersedes: [previous version's path, from resolve_brief_version.py's plain (non-"--next") call, below -- omit this line entirely if version is 1]
status: candidate
---

# Grounding Brief: [topic]

## Pairing
- **Thinker:** [Name], *[Work]* — [concept] [THINKER: Name, Work, quotability]
- **Research:** [Author Year, code] — [finding] [RESEARCH: Author Year, quality rating]
- **Why this pairing:** [the mechanism-link sentence from the map row]

## Hook
[citation(s) for the hook beat; quotability restated here]

## Turn
[citation(s) for the turn beat; quotability restated here]

## Payoff
[citation(s) for the payoff beat — prefer the research file's own Content Hooks section over
re-deriving a number; quotability restated here]

## Reframe
[citation(s) for the reframe beat; quotability restated here]

## Safety handling
[Only if R5/R11/R12/R14 is touched — the specific constraints applied, per
references/safety-sensitive-handling.md. Omit this section entirely otherwise.]

## Verification record
- Thinker source opened: [file path + passage/lines confirmed]
- Research source opened: [file path + finding/citation/quality rating confirmed]

## Gap-fill flag
[Only if this pairing came from live-glob rather than the map — see
references/thinker-corpus-protocol.md Path 2 for the exact required heading/text]

## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above, mapped per `references/scripting-beat-mapping.md`),
shorts-styleboard (thinker/source and motif → the world lock's `register_b_*` keys and `motif`),
and visual-prompts (motif cue for shot composition only: [from the map row]).

**Per-brief mapping judgment** (see `references/scripting-beat-mapping.md` — state both, don't
restate the fixed mapping itself):
- Turn content lands in: [Setup / early-Build, ~[N]s]
- Payoff content (research finding) serves as: [the Build's proof beat / the script's own Payoff beat]

Constraints that survive to publish (omit this line entirely if none apply): [e.g.
"paraphrase-caution — never render as an on-screen quote/direct-attribution card" / "R5 —
mandatory 988 Suicide & Crisis Lifeline line required in final captions/copy"]

## Alternates considered
[Non-interactive fallback only: the other slate rows not chosen, one line each]
```

### 5. Save it

**Artifact vocabulary — one table, copied unchanged into every skill.** The resolver matches
filenames literally, so a `--kind` guessed from a stage id or a skill name returns `NONE` and
exit 1 — which this section documents as the benign "upstream hasn't run yet" case. Copy the
literal string from this table; never infer it.

| Stage id (`pipeline.yaml`) | `--kind` | `stage:` frontmatter | Owning skill |
|---|---|---|---|
| `grounding` | `grounding` | `00-grounding` | `rgs-grounding` |
| `ideation` | `concept-brief` | `01-ideation` | `shorts-ideation` |
| `scripting` | `script` | `02-scripting` | `shorts-scripting` |
| `styleboard` | `styleboard` | `02b-styleboard` | `shorts-styleboard` |
| `voiceover` | `voiceover-brief` | `03-voiceover` | `voiceover-brief` |
| `visual` | `visual-prompts` | `03-visual` | `visual-prompts` |
| `music` | `music` | `03-music` | `music-brief` |
| `assembly` | `assembly` | `04-assembly` | `shorts-assembly` |
| `repurpose` | `social-repurpose` | `05-repurpose` | `social-repurpose` |
| — (specialist) | `audio-spec` | `03-voiceover` | `elevenlabs-audio` |
| — (specialist) | `music-spec` | `03-music` | `elevenlabs-music` |
| — (specialist) | *none — transcript-only* | — | `midjourney-prompting` |

First, run `python scripts/resolve_brief_version.py --slug <topic-slug> --kind grounding` from
the repo root. If it prints a path (not `NONE`), that's the current version being superseded —
remember its printed path verbatim for the `supersedes:` field below; it's already
`rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.

Then run
`python scripts/resolve_brief_version.py --slug <topic-slug> --kind grounding --next --date <YYYY-MM-DD>`
to get the exact filename and version number to write (first-ever brief for this topic-slug:
version 1, no `-v` suffix; a regrounding of an existing topic: the next version — this prints a
bare filename, not a path, so `rgs-briefs/<that filename>` below is correct as written). Set the
template's `version:` field to the printed version number, and — only when it's greater than 1 —
add `supersedes: <the path the first resolve_brief_version.py call above printed>`. Write the
brief to `rgs-briefs/<that filename>` (see `rgs-briefs/README.md` for the schema). Never edit an
existing file in this directory — a `PreToolUse` hook blocks it. Confirm the file was written
before ending the turn.

**Briefs written before 2026-08-08 carry no `--kind` suffix.** If `--kind grounding` prints
`NONE` but a bare `<date>-<slug>.md` exists, that is the prior version — the kindless lookup
cannot see it, so **do not trust the resolver's proposed version number in this case**. Read the
bare file's own `version:` frontmatter field, set the new brief's `version:` to one higher than
that, add a `-v<N>` suffix to the filename matching it (the resolver's auto-generated filename
omits the suffix for what it thinks is version 1 — override it by hand), and set `supersedes:`
to the old bare file's path. Do not rename the old file.

## Red flags — stop and re-verify

- About to write a `[THINKER:` or `[RESEARCH:` citation without having opened that exact file
  in this invocation → stop, open it first.
- "The map already verified this row, I don't need to re-check it" → the map records that a
  human verified the source once; the citation you're about to write still needs the passage
  confirmed present, every time.
- "This is taking too long, I'll paraphrase from what I remember about [thinker]" → this is the
  exact failure this skill exists to prevent. Open the file.
- About to produce 3 full verified briefs instead of a slate + one brief → don't; verification
  depth is the expensive, quality-critical step — spend it once, on the human's actual pick.

## Citation index

- `references/pairing-map.md` — the curated matches, built per
  `docs/superpowers/plans/2026-07-25-raisinggoodsports-grounding-skills.md` Task 2 (~18–24 rows
  across the brand's 7 signature thinkers).
- `references/thinker-corpus-protocol.md` — map-first/live-glob-fallback resolution procedure.
- `references/research-corpus-protocol.md` — research-code resolution + verify-policy rules.
- `references/safety-sensitive-handling.md` — R5/R11/R12/R14 protocol.
- `references/brand-voice-and-tone.md` — voice, lexicon, archetypes, spine, quotability rule.
- `references/scripting-beat-mapping.md` — the fixed Hook/Turn/Payoff/Reframe →
  Hook/Setup/Build/Payoff/Loop-CTA mapping rule, stated once; every brief's Handoff states only
  the per-brief judgment this mapping leaves open.
- `references/worked-example.md` — one full topic-to-brief run.

## Handoff contract (machine-checked)

```handoff
produces.kind: grounding
produces.stage: 00-grounding
produces.section: Handoff
produces.section: Constraints that survive to publish
produces.section: Alternates considered
```
