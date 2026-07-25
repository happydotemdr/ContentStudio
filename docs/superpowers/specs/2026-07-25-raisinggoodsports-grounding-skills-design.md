# RaisingGoodSports Grounding Skills — Design

**Status:** Approved, pending final user sign-off on this written spec.
**Date:** 2026-07-25

## Context

ContentStudio's six existing skills (`shorts-ideation` → `shorts-scripting` → `voiceover-brief` +
`visual-prompts` → `shorts-assembly` → `social-repurpose`) are brand-agnostic pipeline stages,
each grounded in the headless-YouTube corpus (`docs/`, `output/brand-intel/`) with `[C]`/`[I]`/`[T]`
provenance markers. They say nothing about any specific channel's brand identity.

RaisingGoodSports (RGS) is a specific brand this toolkit produces content for — a youth-sports
parenting channel whose entire differentiator is grounding every Short in two equal-weight
sources most creators in the niche don't have:

- **Pillar A — historical thinkers.** `manifests/thinkers.json` catalogs 53 public-domain works
  across ~50 authors (Project Gutenberg etc.), each tagged with `pillars` and a `quotability`
  flag (`quote-ok` vs. `paraphrase-caution` + `cautionNote`). Full cleaned text lives at
  `output/thinkers/anchorandwave/<thinker>/<slug>.cleaned.md`. ~12 works carry the `parenting`
  pillar tag.
- **Pillar B — youth-sports research.** `output/youth-sports/raisinggoodsports/rgs-*.md` — 31
  themed research files (front-matter: `slug`, `code`, `section`, `pillars`, `quotability`,
  `edition`), governed by `rgs-meta-verify-policy.md`'s citation discipline (paraphrase not
  quote, lead with association not causation, name the exact construct/population/data-year).
  Four files are safety-sensitive: r5 (suicide risk), r11 (eating disorders/RED-S), r12
  (safeguarding/abuse), r14 (male eating disorders). `master-edition-v2.md` is provenance-only,
  never citable.

The brand's own definition, `output/raisinggoodsports-brand-definition.md`, is a static,
read-only reference copy (pulled verbatim from a separate system this project has zero
connection to — edits happen upstream, never here; see CLAUDE.md's FamilyBrain firewall and
its "Origin" section for the identical precedent already established for the corpus itself).
It names RGS's signature differentiator as **"what a 100-year-old thinker saw coming"**, gives
a curated table of 7 signature thinkers (Veblen, Adler, Dewey, Charlotte Mason, William James,
Ellen Key, Rousseau) with their theme-power and quotability, three content archetypes (A1 "the
thinker who saw it coming," A2 "the number they don't tell you," A3 "what the kid hears"), a
binding **hook → turn → payoff → reframe** production spine, and a binding monetization-policy
rule: the narrator must never present as a health authority, so every health/injury claim needs
its named source on-screen/in voiceover — which is exactly what Pillar B's citation discipline
already produces.

CLAUDE.md and README.md both currently state the thinkers corpus is "inert leftover toolkit
capability... not read by any ContentStudio skill." This design deliberately overturns that,
for RaisingGoodSports specifically — an intentional, named scope expansion, not a violation of
the anti-generic guarantee (every claim still traces to real corpus text; the guarantee is about
sourcing discipline, not which corpora exist).

## Goals

1. Ground every RGS Short in both pillars, not vibes — every foundational asset carries at
   least one real thinker citation and one real research citation, verified against source text
   at the moment of use (not from model memory of what a thinker "probably said").
2. Let that grounding actually shape hook, turn, payoff, reframe, and visual motif — not just
   seed the initial idea.
3. Stay current as both corpora grow, without silently degrading match quality and without
   requiring a skill edit every time a thinker or research theme is added.
4. Avoid the channel's content converging on the same 2–3 thinkers and the same 2–3 stats.
5. Never invent a pairing the corpus doesn't actually support; say so explicitly when a pillar
   is thin for a given topic.

## Non-goals

- No multi-brand generalization, brand-pack pattern, or "could point at other brands" hooks —
  this is RaisingGoodSports-only, by explicit instruction.
- No modification of the six existing generic skills' files in this work. Needed downstream
  changes are documented as a follow-on (see "Follow-on work," below), not implemented here.
- No cron/scheduled automation. `rgs-pairing-review` is human-triggered.
- No database, no app server. Everything is flat Markdown/YAML-front-matter files, consistent
  with the rest of this toolkit.
- No Visual Kit / packaging-brand-style skill. `brand-definition.md` also contains a palette,
  typography, and thumbnail-rules block — a third, separate kind of brand grounding, unrelated
  to the two research/wisdom pillars this design covers. Explicitly out of scope; flagged as a
  candidate for a future, separate design.
- No live sync back to the system `brand-definition.md` was copied from. It is read-only here.

## Design

Two new atomic skills, both under the `rgs-` naming prefix (distinguishes them at a glance from
the six generic pipeline skills; matches the corpus's own `rgs-*.md` slug convention):

- **`rgs-grounding`** — the production skill. Raw RGS topic → a verified, corpus-grounded
  **Grounding Brief**.
- **`rgs-pairing-review`** — the maintenance skill. Detects corpus growth since the last
  review and proposes curated additions to `rgs-grounding`'s pairing map, for human approval.

Neither skill orchestrates the other five, or each other. Both are hand-chained by a human,
matching the existing house pattern.

### Why not live-glob-and-guess matching

The original draft of this design had `rgs-grounding` live-query both corpora at invocation
time and rely on model judgment to pick a fitting thinker/research pairing. Rejected: proving a
work *exists* in a manifest is not the same as grounding what the skill *says about it*. If the
model matches "parental pressure" to Adler because it already knows Adler's ideas from training
data, the resulting citation is generic knowledge with a citation stapled on after the fact —
the exact provenance-theater failure the anti-generic guarantee exists to prevent, landing on
the one asset the brand calls its moat. A curated, source-verified map is required instead (see
below); live-glob is retained only as a gap-fill path for topics the map doesn't yet cover.

### `rgs-grounding`

**Pipeline position**

| | |
|---|---|
| Upstream | A raw RGS topic/pain point, or a specific thinker passage / research stat the user already has in mind |
| This skill | Topic → one verified **Grounding Brief**, saved to `rgs-briefs/` |
| Downstream | Feeds `shorts-ideation` (angle/archetype pick); the same brief travels forward as a companion artifact into `shorts-scripting` (citation text per beat) and `visual-prompts` (motif cues) |

**Files:**
- `.claude/skills/rgs-grounding/SKILL.md` — two-phase workflow (below) + embedded Grounding
  Brief and Pairing Slate templates
- `.claude/skills/rgs-grounding/references/pairing-map.md` — the curated pairing map (schema
  below); the single source of trusted thinker↔research matches
- `.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md` — how to resolve a
  pairing-map row to its full text (`output/thinkers/anchorandwave/...`), and the gap-fill
  protocol: live-glob `manifests/thinkers.json` filtered to the `parenting` pillar only when
  the map has no row for the topic, always flagged `candidate for brand-book review`
- `.claude/skills/rgs-grounding/references/research-corpus-protocol.md` — how to resolve a
  pairing-map row's research code to its full `rgs-*.md` file, the verify-policy rules
  (association not causation; name construct/population/data-year; S5 and R8 arrive pre-hedged
  per verify-policy rule 3), and the reminder that `master-edition-v2.md` is never citable
- `.claude/skills/rgs-grounding/references/safety-sensitive-handling.md` — the r5/r11/r12/r14
  protocol: help-resource pairing for suicide content (988 Suicide & Crisis Lifeline), non-
  sensational framing, naming the specific construct/population behind any number, never
  naming/implying individuals for r12, and the note that r5 content carries a real production-
  time cost (mandatory help-resource line) worth surfacing before commitment, not after
- `.claude/skills/rgs-grounding/references/brand-voice-and-tone.md` — voice traits, the
  preferred/banned lexicon, Do/Don't production rules, the three archetypes, and the quote-ok /
  paraphrase-caution handling rule, distilled from `brand-definition.md` at authoring time with
  a "last synced" date noted in the file
- `.claude/skills/rgs-grounding/references/worked-example.md` — one full raw-topic-to-brief run

**Citation markers:** `[THINKER: Name, Work, quotability]` and `[RESEARCH: Author Year, quality
rating]` — new markers, not a reuse of `[C]`/`[I]`/`[T]`, since those specifically denote
corpus-cited to the 14-channel headless-YouTube corpus; reusing them for a thinker's public-
domain text or a peer-reviewed study would misrepresent the source.

**`pairing-map.md` schema.** Unit of pairing is **thinker-concept × research-code**, not
thinker × topic — the brand's own 7-thinker table already operates at this granularity
("invidious comparison," "the pressured/pampered child," "play vs. work"). Front-matter is a
review ledger (also the input `rgs-pairing-review` diffs against — see below):

```yaml
---
last_review: 2026-07-25
thinker_slugs_reviewed: [aurelius-meditations, epictetus-enchiridion, ...]  # every slug considered, mapped or not
research_codes_reviewed: {R1: v2-2026-07-18, R2: v2-2026-07-18, ...}        # code -> edition considered
---
```

Body is one section per thinker, one subsection per concept:

```markdown
## Veblen

### Concept: Invidious comparison (status by display)
- **Work / anchor:** *Theory of the Leisure Class*, ch. on conspicuous consumption —
  `output/thinkers/anchorandwave/thorstein-veblen/veblen-theory-of-the-leisure-class.cleaned.md`
- **Quotability:** paraphrase-caution (satire — never place on a quote card as a direct claim)
- **Pairs with:** F4 (sport-parent burnout), S5 (professionalization), S1 (pay-to-play), R7 (parental pressure)
- **Why it links:** Veblen's mechanism is esteem-by-display among status-peers; F4's
  sport-parent-burnout construct is chronic status-investment without recovery — same
  mechanism, different vocabulary, 120 years apart.
- **Visual motif cue:** a sideline where parents' gear/setup visibly outcompetes each other
```

Roughly 20–25 rows total, covering the brand's 7 signature thinkers. **Authoring this initial
map is in scope for the implementation plan** — it requires reading each signature thinker's
actual cleaned text and cross-referencing it against the 31 research theme files; it cannot be
mechanically generated.

**Two-phase workflow, one invocation:**

*Phase 1 — Pairing Slate (cheap, map + front-matter only, no deep source reading):*

```markdown
## Pairing Slate: [topic]

1. **[Thinker] × [Research code]** — [one-line mechanism link, from the map's "why it links"]
   - Archetype: [A1 / A2 / A3]
   - Quotability: [quote-ok / paraphrase-caution]
   - Safety flag: [none / r5 / r11 / r12 / r14 — note the extra handling this triggers]
   - Recency flag: [none / "Veblen used in the 2026-07-18 brief"]
2. ...
3. ...

Pick one to proceed to a fully-verified Grounding Brief, or ask for a different topic framing.
```

Safety flags surface **here**, before commitment — r5 in particular carries a real cost (a
mandatory help-resource line) worth knowing about before the human picks that pairing for a
sub-60-second Short.

*Phase 2 — the human picks one row; the skill then produces exactly one fully-verified brief*
(never 3 full briefs — verification is the expensive step, and producing 3 in parallel invites
shallow verification under time pressure, which is the failure this design exists to prevent).
**Mandatory before the brief is written:** open the resolved `rgs-*.md` file (not just its
front-matter) and pull the actual finding, full citation, Quality rating, and cautionNote; open
the thinker's cleaned text at the map's anchor and confirm the actual passage. If either source
doesn't actually support the map's claim (drift, edition change), stop and flag it rather than
writing the brief.

```markdown
---
date: 2026-07-25
topic: "..."
thinker: "Thorstein Veblen"
concept: "Invidious comparison"
research_codes: [F4]
archetype: A1
status: candidate
---

# Grounding Brief: [topic]

## Pairing
- **Thinker:** Veblen, *Theory of the Leisure Class* — invidious comparison
  [THINKER: Thorstein Veblen, Theory of the Leisure Class, paraphrase-caution]
- **Research:** [Author Year, F4] — [finding]
  [RESEARCH: Author Year, quality rating]
- **Why this pairing:** [mechanism-link sentence, from the map]

## Hook
[citation(s) fit for the hook beat; quotability restated here, not just once at the top,
so shorts-scripting inherits it without re-checking]

## Turn
[...]

## Payoff
[...] — prefer the research file's own pre-verified **Content Hooks** section where one exists,
over re-deriving a number from raw findings

## Reframe
[...]

## Safety handling
[If r5/r11/r12/r14 touched: the specific verify-policy constraints applied; help-resource line
if r5. Omit this section entirely if not applicable — don't force it in.]

## Verification record
- Thinker source opened: [file path + passage confirmed]
- Research source opened: [file path + finding/citation/quality rating confirmed]

## Gap-fill flag (only if applicable)
[If this pairing came from live-glob gap-fill rather than the map: "candidate for brand-book
review" — this is what rgs-pairing-review greps for]

## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above) and visual-prompts (visual motif cue: [...]).

## Alternates considered
[Non-interactive fallback only: the other slate rows not chosen, one-line reasons each]
```

**Save path:** `rgs-briefs/YYYY-MM-DD-<topic-slug>.md` (top-level, git-tracked — this is
original editorial output, not downloaded/regenerable corpus data, so it does not belong under
the git-ignored `output/`).

**The saved briefs are the ledger — no separate log file.** `rgs-grounding` live-globs
`rgs-briefs/*.md` front-matter (bounded to roughly the last 20 briefs by filename date is
sufficient; no need to scan an unbounded archive) and applies **soft** variety rules at the
Pairing Slate stage: deprioritize (don't exclude) a thinker used in the last ~5 briefs, flag an
exact concept×code repeat within the last ~15, note A1/A2/A3 archetype distribution. These are
starting heuristics, not hard limits — surfaced as a visible flag the human can override, since
with 7 signature thinkers at a 5-Shorts/week cadence, some recurrence is mathematically
unavoidable; real variety comes from the pairing map's concept-level granularity (Veblen×F4,
Veblen×S1, Veblen×R7 are three different Shorts), not from blocking a thinker outright.

**Non-interactive fallback:** if the invocation can't pause for a human pick between phases,
produce one full verified brief for the top-ranked slate row, plus the "Alternates considered"
appendix (the rejected rows, one line each), so a re-roll is cheap and informed.

### `rgs-pairing-review`

A thin, separate skill — disjoint trigger ("I refreshed the corpus, review the map") and
disjoint output (a proposal doc, not a Grounding Brief) from `rgs-grounding`. It has no
`references/` of its own; it reads `rgs-grounding/references/pairing-map.md` as its format and
quality-bar contract, so the quality criteria live in exactly one place.

**File:** `.claude/skills/rgs-pairing-review/SKILL.md`

**Workflow:**

1. Read `pairing-map.md`'s front-matter ledger (`last_review`, `thinker_slugs_reviewed`,
   `research_codes_reviewed`).
2. Diff against current state, three checks:
   - **New thinker works:** slugs in `manifests/thinkers.json` absent from
     `thinker_slugs_reviewed`.
   - **New research:** codes in `output/youth-sports/raisinggoodsports/rgs-*.md` front-matter
     absent from `research_codes_reviewed`.
   - **Changed research:** a code present in `research_codes_reviewed` whose current file
     `edition` no longer matches the recorded value — flag every existing map row that
     references this code for re-verification, not just new-row consideration.
3. **Secondary signal:** grep `rgs-briefs/*.md` for the "Gap-fill flag" section (`candidate for
   brand-book review`), so pairings `rgs-grounding` organically discovered via its live-glob
   gap-fill path enter this same review pass.
4. For each new/changed item, run the identical source-open verification `rgs-grounding` uses
   before drafting a candidate row — never propose a pairing that hasn't actually been checked
   against source text; an unverified proposal makes the human's approval step a rubber stamp
   on an unearned pairing. Where no strong pairing exists, record "considered, no pairing found"
   with a one-line reason — this is an explicitly valid outcome, not a failure.
5. Write a dated proposal to `output/pairing-proposals/YYYY-MM-DD-proposal.md` (git-ignored,
   ephemeral — this directory lives under `output/` deliberately, since a proposal is disposable
   working material, unlike the briefs ledger): proposed rows in the exact `pairing-map.md`
   row format, the considered-and-rejected list, and re-verification verdicts for any
   edition-changed codes.
6. Present the proposal to the human in-conversation. On approval (whole or partial — the human
   may accept some rows and reject others), edit the approved rows plus the updated ledger
   front-matter (`last_review` date, newly-considered slugs/codes added to the reviewed lists)
   directly into `pairing-map.md`. **Never write directly to `pairing-map.md` before this
   approval step.** The resulting `git diff` on `pairing-map.md` is the approval surface the
   human reviews before committing — mirroring the research corpus's own existing refresh
   workflow ("re-split the changed themes, get owner approval on the per-theme git diffs, then
   run the ingest").

**Trigger:** event-driven, not scheduled. Primary: one added line in `README.md`'s existing
corpus-refresh workflow ("...run `npm run research:ingest` on the Pi and the laptop enrichment
loop" → append "...then run `rgs-pairing-review`"). No cron; this is a local, stateless,
no-server toolkit, and the diff is only non-empty right after a corpus refresh anyway.

## Follow-on work (spec'd, not implemented in this plan)

The six existing generic skills are not modified here. When implementation of this design is
complete, each of the following becomes its own small follow-on change:

- `shorts-ideation`: accept an optional Grounding Brief as additional input; prefer angle
  candidates the brief's archetype/citations support.
- `shorts-scripting`: accept an optional Grounding Brief; weave its `[THINKER]`/`[RESEARCH]`
  citations into the hook/turn/payoff/reframe beats, respecting the per-beat quotability
  restated in the brief.
- `visual-prompts`: accept an optional Grounding Brief; use its visual motif cue(s) for shot
  composition, alongside `brand-definition.md`'s separate Visual Kit block (out of scope here —
  see "Non-goals").

**Addressed:** see `docs/superpowers/specs/2026-07-25-rgs-pipeline-handoff-design.md` for the
follow-on design covering all three, plus `shorts-assembly`/`social-repurpose` constraint
pass-through and the beat-spine reconciliation this list didn't anticipate.

## Scope-note updates (in scope for this plan)

- `CLAUDE.md`: revise the "Out of scope, kept for structural completeness" note — the thinkers
  corpus now feeds `rgs-grounding` and `rgs-pairing-review` for the RaisingGoodSports brand
  specifically. The youth-sports corpus and the general-interest roster entry remain otherwise
  unaffected by this note's accuracy (youth-sports was never claimed out of scope the same way;
  confirm during implementation and word precisely).
- `README.md`: same correction to the "Thinkers... kept over because this toolkit downloads
  three corpora as a unit; they are not read by any ContentStudio skill" scope note, plus the
  one-line addition to the refresh workflow described above.

## Open questions

None blocking. The two soft-rule thresholds (deprioritize-last-5, flag-repeat-within-15) and
the bounded-briefs-scan window (~20) are starting heuristics — expected to be tuned after real
production use, not fixed constants.
