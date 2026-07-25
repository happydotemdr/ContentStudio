# RaisingGoodSports → Generic Pipeline Handoff — Design

**Status:** Approved, pending final user sign-off on this written spec.
**Date:** 2026-07-25

## Context

`rgs-grounding` (topic → verified Grounding Brief, see
`docs/superpowers/specs/2026-07-25-raisinggoodsports-grounding-skills-design.md`) is built and
committed. Its own docs and every saved brief in `rgs-briefs/` claim a handoff — "feeds
`shorts-ideation`... travels forward... to `shorts-scripting`... and `visual-prompts`" — but none
of those three generic skills have any awareness of a Grounding Brief. This was a deliberate,
documented scope deferral in the original plan ("Follow-on work," not a bug), and this design is
that follow-on.

Two wrinkles surfaced during review:

1. **Beat-spine mismatch.** The Grounding Brief's spine is brand-bound — Hook → Turn → Payoff →
   Reframe, per RGS's `brand-definition.md`. `shorts-scripting`'s spine is generic — Hook → Setup
   → Build/Value (w/ re-hook) → Payoff → Loop/CTA, 5 beats. These don't map 1:1.
2. **A separate, approved-but-unimplemented spec**
   (`docs/superpowers/specs/2026-07-25-eval-and-io-boundaries-design.md`) will eventually
   formalize artifact I/O between all six generic stages via a `runs/<run_id>/NN-<stage>/
   artifact.vN.md` layout. Decided: build this handoff now, against the current plain-file,
   hand-chained convention (the same one `rgs-grounding` already uses), rather than wait on
   unscheduled work. The editorial logic here is expected to port cleanly into that system later.

This design also incorporates a fable-model review pass (see commit history) that caught three
real defects in the original sketch, folded in below rather than listed separately.

## Goals

1. Let `shorts-ideation`, `shorts-scripting`, and `visual-prompts` actually accept and correctly
   use a Grounding Brief when a human hands them one.
2. Keep the six generic skills genuinely brand-agnostic — reusable by a hypothetical second
   future brand, not just "no literal RGS string in the file."
3. Carry quotability and safety-sensitive constraints all the way to publish (`shorts-assembly`'s
   captions, `social-repurpose`'s post copy) — not just to the first skill that touches them.
4. Resolve the beat-spine mismatch with one real, once-stated mapping rule, not per-brief
   mechanical relabeling.
5. Preserve the anti-generic guarantee's marker discipline — no unmarked normative rule enters a
   generic skill.

## Non-goals

- Not redesigning around, or waiting for, the `runs/` artifact I/O spec (decided above).
- Not modifying `rgs-pairing-review`.
- Not building the Visual Kit skill (palette/typography/thumbnail rules) — still out of scope,
  per the original RGS design's own non-goals.
- Not changing `shorts-assembly`'s or `social-repurpose`'s corpus-grounded content — only adding a
  pass-through instruction for a constraint line when one is present.

## Design

### 1. A generic companion-artifact contract, not a named "RGS Grounding Brief" integration

The original sketch hardcoded "RGS Grounding Brief" into three generic skills by name — that
makes the generic skills brand-*aware*, not artifact-*aware*: the next brand would need its own
named subsection per skill. Instead, each affected generic skill gains one small, brand-neutral
contract for an **optional companion grounding artifact**, covering:

- Per-beat citation content, keyed to *the generic skill's own beat names* (e.g.
  `shorts-scripting`'s Hook/Setup/Build/Payoff/Loop-CTA) — never the brand's own beat names. The
  brand skill is responsible for producing content already in this shape (see §2).
- An archetype/angle hint for `shorts-ideation` (a plain-language label + one-line rationale —
  not RGS's specific A1/A2/A3 vocabulary).
- A visual motif cue for `visual-prompts`.
- A **"constraints that survive to publish"** line — e.g. "never render as an on-screen
  quote/direct-attribution card" or "must carry a named help-resource line in final copy" — that
  `shorts-scripting` copies verbatim into its own output so `shorts-assembly` and (through it)
  `social-repurpose` inherit it without ever needing brand-specific knowledge. They just honor a
  flagged constraint if one is present.

`rgs-grounding` is the first, and so far only, skill that conforms to this contract.

**Marker discipline:** this contract's rule text is an interface convention, not a corpus claim —
mark it `[I]` in each generic skill's new subsection. `shorts-ideation` currently states "No `[I]`
or `[T]` markers appear in this skill" (`SKILL.md:160`) — that line gets updated to reflect the
one newly-marked interface rule.

### 2. `rgs-grounding` side: one shared beat-mapping rule, not per-brief duplication

Reviewed and rejected: a per-brief "Beat mapping for shorts-scripting" block that duplicates
citation text under new beat labels. That duplicates content that would drift, while encoding
zero per-brief judgment (the mapping rule itself is constant across every brief) — and a naive
Reframe→Loop/CTA relabel doesn't actually work: Loop/CTA is 5–12 words and mirrors the Hook
(`shorts-scripting/SKILL.md:107`), while a brief's Reframe is a full argumentative move (see the
worked example, `rgs-briefs/2026-07-25-why-parents-overspend-on-travel-teams.md`, "Reframe"
section) — mechanically relabeling it produces an unwritable Loop beat.

Instead, add **one** new mapping-guidance section to `rgs-grounding`'s references, stated once:

- **Hook → Hook** (direct).
- **Turn → Setup + early-Build** — author's call exactly where in the ~20s Build the citation
  lands.
- **Payoff → the Build's required proof beat, or Payoff itself** — author's call, driven by
  whether the research finding *is* the proof beat this Short needs.
- **Reframe → split**: the argumentative body lands in late-Payoff; only its kicker line (the
  one-sentence takeaway) gets echoed in the Loop/CTA mirror — never the full Reframe text.

Each individual brief's Handoff section then states only genuine per-brief judgment (e.g. "this
pairing's research finding is the Build's proof beat, land it ~20s in") instead of repeating the
mechanism. This also shrinks the retrofit of the three existing `rgs-briefs/*.md` files to a
one-line addition each, not a duplicated block.

### 3. `shorts-ideation`

- New "Optional input: a companion grounding artifact" subsection (contract-shaped, `[I]`-marked).
- **Archetype-mismatch decision rule:** if no angle consistent with the artifact's archetype hint
  passes the skill's existing validation gate (net-information-gain / demonetization screen), the
  skill does not stretch a citation to fit. It either picks from the brief's own "Alternates
  considered" appendix (already produced by `rgs-grounding` for exactly this situation) or reports
  back that a new pairing is needed — never forces an unsupported angle.
- **Demonetization-screen resolution** (the one point that needed a product decision, now
  settled): the screen at `SKILL.md:76-77` flags "sensitive medical/financial framing" — a
  companion artifact's safety-sensitive citation (RGS's R5/R11/R12/R14 or any future brand's
  equivalent) **passes** this screen when it already follows a named-source, non-sensational
  protocol (as `rgs-grounding`'s `safety-sensitive-handling.md` requires, and as
  `brand-voice-and-tone.md`'s binding monetization rule already demands — the narrator must never
  present as a health authority, every claim needs its named source). The screen's actual intent
  is to catch content presenting *as* a health authority; a properly-sourced citation is the
  opposite of that failure mode. Only an unsourced or sensationalized safety-sensitive claim fails
  the screen.
- Concept-brief output adds a one-line **Grounding** reference (thinker/concept/archetype/file
  path) pointing at the artifact — never re-typing its citation text, so there is one source of
  truth.

### 4. `shorts-scripting`

- New "Optional input" subsection (`[I]`-marked): when handed a companion artifact, weave its
  per-beat citation content into the matching native beat — using §2's shared mapping rule plus
  the artifact's own per-brief judgment note — preserving `[THINKER:]`/`[RESEARCH:]`-style
  markers and restating quotability at every beat that uses one.
- Copies the artifact's "constraints that survive to publish" line into its own **Delivery
  notes** field (`SKILL.md:150`, already flows downstream) verbatim, so `shorts-assembly` and,
  through it, `social-repurpose` inherit the constraint without needing brand-specific awareness.

### 5. `visual-prompts`

- New "Optional input" subsection (`[I]`-marked): use the artifact's visual motif cue as a
  shot-composition input for the relevant beat(s).
- **Correction from the original sketch:** the quote-card quotability gate does *not* belong here.
  `visual-prompts` never renders on-screen text — it explicitly routes all caption/overlay copy to
  `shorts-assembly` (`SKILL.md:26`, `:87-90`, the "No Text" rule). That gate is now carried by
  §4's Delivery-notes constraint line instead, reaching the skill that actually decides
  quote-card treatment.

### 6. `shorts-assembly` and `social-repurpose` — small, additive, brand-blind

- One new line each: "if the script's Delivery notes carry a constraints line (e.g. a quotability
  restriction or a required safety element), honor it in captions/overlay copy (`shorts-assembly`)
  or post copy (`social-repurpose`)." No brand-specific knowledge added — just "read and obey a
  flagged constraint if one is present," which is how they already treat everything else that
  arrives from upstream.

### 7. Staleness and status handling

- `shorts-ideation`'s optional-input subsection adds: "if the companion artifact's date predates
  the most recent relevant corpus refresh, or its `status` field isn't in an active/consumable
  state, flag before use rather than proceeding silently."
- `rgs-briefs/README.md`'s front-matter schema doc gets a clarifying line on what `status:
  candidate` means for downstream consumption (currently only defined for `rgs-grounding`'s own
  recency heuristics, not for a downstream consumer).

### 8. Documentation

- `docs/superpowers/specs/2026-07-25-raisinggoodsports-grounding-skills-design.md`'s "Follow-on
  work" section gets a short pointer to this spec once implemented.

## Open questions

None blocking. The demonetization-screen conflict (§3) is resolved by the named-source-passes
rule above.
