# RGS Grounding Brief → Generic Pipeline Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the gap between `rgs-grounding` (produces a verified Grounding Brief) and the
three generic skills it claims to feed — `shorts-ideation`, `shorts-scripting`, `visual-prompts`
— by giving each a small, brand-neutral "companion grounding artifact" contract, resolving the
Hook/Turn/Payoff/Reframe vs. Hook/Setup/Build/Payoff/Loop-CTA beat-spine mismatch with one
shared, stated-once mapping rule, and carrying quotability/safety constraints all the way through
`shorts-assembly` and `social-repurpose` to publish.

**Architecture:** Five generic skills each gain a small "Optional input: a companion grounding
artifact" section (`[I]`-marked, brand-neutral — never hardcoded to RGS by name as an operative
condition). `rgs-grounding` gains one new reference file stating the beat-mapping rule once, plus
a per-brief "judgment" addition to its Grounding Brief template and its three already-produced
briefs. No new skills, no orchestrator, no code — this is Markdown/YAML editing only, following
the same house pattern the original `rgs-grounding`/`rgs-pairing-review` plan used.

**Tech Stack:** Markdown, YAML front-matter, Claude Code skills. File operations only
(Read/Write/Edit/Glob/Grep) — no build step, no tests in the pytest sense; verification is
grep-based structural checks plus subagent dry runs, matching this repo's existing
skill-authoring convention.

## Global Constraints

- The six generic skills stay hand-chained by a human — no orchestrator is introduced.
- Every new normative line added to a generic skill carries a marker. All new sections in this
  plan are `[I]` (interface convention, not a corpus claim) — never left unmarked.
- Generic skills stay brand-agnostic: RGS/`rgs-grounding` may be named only as an illustrative
  example inside prose, never as the operative trigger condition for a rule. The contract is
  "a companion grounding artifact," not "an RGS Grounding Brief."
- Citation markers (e.g. `[THINKER: ...]`, `[RESEARCH: ...]`) are preserved verbatim wherever
  carried forward — never stripped or paraphrased away.
- Quotability (quote-ok vs. paraphrase-caution) is never violated: no skill in this pipeline
  renders a paraphrase-caution citation as an on-screen quote/direct-attribution card.
- A safety-sensitive "constraints that survive to publish" line, once stated by a companion
  artifact, must reach `shorts-assembly`'s captions and `social-repurpose`'s post copy — not stop
  at the first skill that touches it.
- No task in this plan modifies `rgs-pairing-review`, `pairing-map.md`'s row schema/content, any
  file under `output/`, or builds the Visual Kit (palette/typography/thumbnail-rules) skill —
  all explicitly out of scope per the design spec's non-goals.
- No task in this plan changes `shorts-assembly`'s or `social-repurpose`'s own corpus-grounded
  content — only adds a pass-through instruction for a constraint line when one is present.

---

## File Structure

```
.claude/skills/rgs-grounding/
  SKILL.md                                              # Modify — Task 1
  references/
    scripting-beat-mapping.md                           # Create — Task 1

rgs-briefs/
  README.md                                              # Modify — Task 2
  2026-07-25-why-parents-overspend-on-travel-teams.md    # Modify — Task 2
  2026-07-25-why-travel-sport-kids-quit-at-13.md         # Modify — Task 2
  2026-07-25-8000-a-year-club-soccer-parent.md           # Modify — Task 2

.claude/skills/shorts-ideation/SKILL.md                  # Modify — Task 3
.claude/skills/shorts-scripting/SKILL.md                 # Modify — Task 4
.claude/skills/visual-prompts/SKILL.md                   # Modify — Task 5
.claude/skills/shorts-assembly/SKILL.md                  # Modify — Task 6
.claude/skills/social-repurpose/SKILL.md                 # Modify — Task 6

docs/superpowers/specs/2026-07-25-raisinggoodsports-grounding-skills-design.md   # Modify — Task 7
```

Reference files stay split by concern, matching the existing six-skill and `rgs-grounding`
pattern: the beat-mapping rule is its own file, not folded into an existing reference, since it's
a distinct concern (translation between two spines) from citation resolution, safety handling, or
voice/tone.

---

### Task 1: Add the shared beat-mapping rule to `rgs-grounding`

**Files:**
- Create: `.claude/skills/rgs-grounding/references/scripting-beat-mapping.md`
- Modify: `.claude/skills/rgs-grounding/SKILL.md:20` (Pipeline position, Downstream cell)
- Modify: `.claude/skills/rgs-grounding/SKILL.md:125-127` (Grounding Brief template, Handoff
  section)
- Modify: `.claude/skills/rgs-grounding/SKILL.md:150-158` (Citation index)

**Interfaces:**
- Consumes: `shorts-scripting/SKILL.md`'s existing beat-timing table (Hook/Setup/Build/Payoff/
  Loop-CTA, `shorts-scripting/SKILL.md:99-116`) as the translation target.
- Produces: `references/scripting-beat-mapping.md` and its "Per-brief judgment" two-line format
  (which beat the Turn content lands in; whether the Payoff content is the Build's proof beat or
  the script's own Payoff beat) — consumed by Task 2 (brief retrofits) and Task 4
  (`shorts-scripting`'s new optional-input section).

- [ ] **Step 1: Write `references/scripting-beat-mapping.md`**

```markdown
# Scripting Beat Mapping

How a Grounding Brief's brand-bound Hook → Turn → Payoff → Reframe spine maps onto
`shorts-scripting`'s generic Hook → Setup → Build/Value → Payoff → Loop/CTA spine. This mapping
is stated once, here — a Grounding Brief's own Handoff section states only the per-brief
judgment call this mapping still leaves open (see below), never a repeated restatement of the
mapping itself.

## The fixed mapping

- **Hook → Hook.** Direct — use the brief's Hook content as-is for the script's Hook beat.
- **Turn → Setup + early-Build.** The brief's Turn beat names the mechanism plainly (e.g. "this
  isn't about X, it's the same instinct [thinker] named"). Exactly where inside
  `shorts-scripting`'s Setup (3–8s) and early Build/Value (8–~15s) this lands is a per-brief
  judgment call — state it explicitly in the brief's Handoff section (see "Per-brief judgment"
  below), don't leave it to `shorts-scripting` to guess.
- **Payoff → the Build's required proof beat, or Payoff itself.** `shorts-scripting` requires at
  least one concrete proof beat inside Build/Value (its `[I]`-marked proof-beat rule,
  `shorts-scripting/SKILL.md:40-47`). A Grounding Brief's Payoff content — a research finding,
  ideally the source file's own Content Hook — is frequently *exactly* that proof beat. Whether
  it lands in Build/Value as the proof beat or later in the script's own Payoff beat is a
  per-brief call, driven by whether the finding is best used to build the case (Build/Value) or
  resolve the Hook's question (Payoff) — state which one the brief intends.
- **Reframe → split.** The brief's Reframe is a full argumentative move (typically 2–3
  sentences). It does not become the Loop/CTA beat wholesale — `shorts-scripting`'s Loop/CTA is
  5–12 words and must mirror the Hook's phrasing (`shorts-scripting/SKILL.md:107`). Instead:
  - The Reframe's argumentative body lands in the script's own **Payoff** beat (after or combined
    with the research finding, if the finding didn't already fill Payoff above).
  - Only the Reframe's **kicker line** — the one-sentence takeaway ("it was never about your
    kid's talent — that's the good news," in the worked examples) — gets echoed in the
    **Loop/CTA** beat, reworked to mirror the Hook's own phrasing per `shorts-scripting`'s rule,
    never restated in full.

## Per-brief judgment

Every Grounding Brief's Handoff section states, in one or two lines, the two calls this mapping
leaves open for that specific brief:

1. Where the Turn content lands (Setup vs. early-Build) and roughly when.
2. Whether the Payoff content (the research finding) is the Build's proof beat or the script's
   own Payoff beat.

This is genuine per-brief editorial judgment — it depends on how substantial the research finding
is and how much setup the thinker's mechanism needs — not a restatement of the fixed mapping
above, which never changes brief-to-brief.

## Marker and constraint carry-through

The citation text handed to `shorts-scripting` keeps its `[THINKER: ...]` / `[RESEARCH: ...]`
markers intact — `shorts-scripting` preserves them in the script output rather than stripping
them, and restates quotability (quote-ok / paraphrase-caution) at every beat that uses a
citation. Any citation carrying a publish-time constraint (e.g. a mandatory safety-resource line)
is stated as a **"constraints that survive to publish"** line in the brief's Handoff section —
`shorts-scripting` copies this line verbatim into its own Delivery notes field so it reaches
`shorts-assembly` and `social-repurpose` without either skill needing brand-specific knowledge.
```

- [ ] **Step 2: Update `SKILL.md`'s Pipeline position Downstream cell**

Locate (`SKILL.md:20`):

```
| **Downstream** | Feeds `shorts-ideation` (angle/archetype pick); the same brief also feeds `shorts-scripting` (citation text per beat) and `visual-prompts` (motif cues) — hand it forward at each stage, don't regenerate it |
```

Replace with:

```
| **Downstream** | Feeds `shorts-ideation` (angle/archetype pick, via the concept brief's Grounding reference line); the same brief also feeds `shorts-scripting` (citation text per beat, mapped per `references/scripting-beat-mapping.md`) and `visual-prompts` (motif cues) — hand it forward at each stage, don't regenerate it |
```

- [ ] **Step 3: Update the Grounding Brief template's Handoff section**

Locate (`SKILL.md:125-127`):

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above) and visual-prompts (visual motif cue: [from the map row]).
```

Replace with:

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above, mapped per `references/scripting-beat-mapping.md`) and
visual-prompts (visual motif cue: [from the map row]).

**Per-brief mapping judgment** (see `references/scripting-beat-mapping.md` — state both, don't
restate the fixed mapping itself):
- Turn content lands in: [Setup / early-Build, ~[N]s]
- Payoff content (research finding) serves as: [the Build's proof beat / the script's own Payoff beat]

**Constraints that survive to publish** (omit this line entirely if none apply): [e.g.
"paraphrase-caution — never render as an on-screen quote/direct-attribution card" / "R5 —
mandatory 988 Suicide & Crisis Lifeline line required in final captions/copy"]
```

- [ ] **Step 4: Update the Citation index**

Locate (`SKILL.md:150-158`):

```markdown
- `references/pairing-map.md` — the curated matches (Task 2 of the implementation plan; ~18–24
  rows across the brand's 7 signature thinkers).
- `references/thinker-corpus-protocol.md` — map-first/live-glob-fallback resolution procedure.
- `references/research-corpus-protocol.md` — research-code resolution + verify-policy rules.
- `references/safety-sensitive-handling.md` — R5/R11/R12/R14 protocol.
- `references/brand-voice-and-tone.md` — voice, lexicon, archetypes, spine, quotability rule.
- `references/worked-example.md` — one full topic-to-brief run.
```

Replace with:

```markdown
- `references/pairing-map.md` — the curated matches (Task 2 of the implementation plan; ~18–24
  rows across the brand's 7 signature thinkers).
- `references/thinker-corpus-protocol.md` — map-first/live-glob-fallback resolution procedure.
- `references/research-corpus-protocol.md` — research-code resolution + verify-policy rules.
- `references/safety-sensitive-handling.md` — R5/R11/R12/R14 protocol.
- `references/brand-voice-and-tone.md` — voice, lexicon, archetypes, spine, quotability rule.
- `references/scripting-beat-mapping.md` — the fixed Hook/Turn/Payoff/Reframe →
  Hook/Setup/Build/Payoff/Loop-CTA mapping rule, stated once; every brief's Handoff states only
  the per-brief judgment this mapping leaves open.
- `references/worked-example.md` — one full topic-to-brief run.
```

- [ ] **Step 5: Verify**

Run: read `.claude/skills/rgs-grounding/references/scripting-beat-mapping.md` and
`.claude/skills/rgs-grounding/SKILL.md` back in full.
Expected: the new reference file has all four sections (The fixed mapping, Per-brief judgment,
Marker and constraint carry-through, plus its header); `SKILL.md`'s Downstream cell, template
Handoff section, and Citation index all reference `scripting-beat-mapping.md` by exact filename.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/rgs-grounding/references/scripting-beat-mapping.md .claude/skills/rgs-grounding/SKILL.md
git commit -m "feat: add shared scripting beat-mapping rule to rgs-grounding"
```

---

### Task 2: Retrofit `rgs-briefs/` with per-brief mapping judgment and clarify `status`

**Files:**
- Modify: `rgs-briefs/2026-07-25-why-parents-overspend-on-travel-teams.md:71-75`
- Modify: `rgs-briefs/2026-07-25-why-travel-sport-kids-quit-at-13.md:86-89`
- Modify: `rgs-briefs/2026-07-25-8000-a-year-club-soccer-parent.md:116-120`
- Modify: `rgs-briefs/README.md:29-31`

**Interfaces:**
- Consumes: Task 1's `references/scripting-beat-mapping.md` per-brief judgment format.
- Produces: three real, consumable companion-artifact briefs for Task 8's dry run — in
  particular `2026-07-25-why-parents-overspend-on-travel-teams.md`, which Task 8 uses directly.

- [ ] **Step 1: Retrofit `2026-07-25-why-parents-overspend-on-travel-teams.md`**

Locate (lines 71-75):

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above) and visual-prompts (visual motif cue: a sideline where parents'
gear, setup, or effort visibly outcompetes their neighbors' — the comparison itself as the
shot, not any one family singled out).
```

Replace with:

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above, mapped per
`.claude/skills/rgs-grounding/references/scripting-beat-mapping.md`) and visual-prompts (visual
motif cue: a sideline where parents' gear, setup, or effort visibly outcompetes their neighbors'
— the comparison itself as the shot, not any one family singled out).

**Per-brief mapping judgment:**
- Turn content lands in: Setup, ~5s (short, direct naming of the mechanism — no separate Build
  placement needed).
- Payoff content (research finding) serves as: the script's own Payoff beat — F4's Content Hook
  directly resolves the Hook's implicit question ("why do parents overspend").

**Constraints that survive to publish:** paraphrase-caution (Veblen) — never render as an
on-screen quote/direct-attribution card.
```

- [ ] **Step 2: Retrofit `2026-07-25-why-travel-sport-kids-quit-at-13.md`**

Locate (lines 86-89):

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above) and visual-prompts (visual motif cue: a young child joyfully
kicking a ball alone, cut against a teenager sitting on a bench, disengaged, during a drill).
```

Replace with:

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting
(citation text per beat above, mapped per
`.claude/skills/rgs-grounding/references/scripting-beat-mapping.md`) and visual-prompts (visual
motif cue: a young child joyfully kicking a ball alone, cut against a teenager sitting on a
bench, disengaged, during a drill).

**Per-brief mapping judgment:**
- Turn content lands in: Setup, ~5s (short, direct naming of the mechanism).
- Payoff content (research finding) serves as: the script's own Payoff beat — R8's Content Hook
  directly resolves the Hook's implicit question ("why do kids quit").

**Constraints that survive to publish:** paraphrase-caution (Ellen Key) — never render as an
on-screen quote/direct-attribution card.
```

- [ ] **Step 3: Retrofit `2026-07-25-8000-a-year-club-soccer-parent.md`**

Locate (lines 116-120):

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting (citation
text per beat above) and visual-prompts (visual motif cue: a stack of travel-team gear,
showcase-tournament wristbands, and private-training receipts — the paper trail of "ambition" as
a visual pile).
```

Replace with:

```markdown
## Handoff
Feeds shorts-ideation next. Travels forward as a companion artifact to shorts-scripting (citation
text per beat above, mapped per
`.claude/skills/rgs-grounding/references/scripting-beat-mapping.md`) and visual-prompts (visual
motif cue: a stack of travel-team gear, showcase-tournament wristbands, and private-training
receipts — the paper trail of "ambition" as a visual pile).

**Per-brief mapping judgment:**
- Turn content lands in: Setup + early-Build, ~4–10s (longer than a single naming line — two
  moves: the "ambition"-as-cloak claim, then landing it on the club-soccer parent specifically).
- Payoff content (research finding) serves as: the Build's required proof beat — S5's numbers
  are supporting evidence for the premise the Hook already stated, not a fresh resolution. The
  script's own Payoff beat instead carries the Reframe's argumentative body below ("it was never
  dishonesty..."), with only its kicker line echoed in Loop/CTA.

**Constraints that survive to publish:** paraphrase-caution (Adler) — never render as an
on-screen quote/direct-attribution card.
```

- [ ] **Step 4: Clarify `status` for downstream consumers in `rgs-briefs/README.md`**

Locate (lines 29-31):

```markdown
- `status` is `candidate` until the Short is actually produced, then hand-edit to `produced` or
  delete the file if the topic was abandoned. `rgs-grounding`'s recency rules apply to files
  regardless of `status` — even an abandoned candidate reflects a recent pairing choice.
```

Replace with:

```markdown
- `status` is `candidate` until the Short is actually produced, then hand-edit to `produced` or
  delete the file if the topic was abandoned. `rgs-grounding`'s recency rules apply to files
  regardless of `status` — even an abandoned candidate reflects a recent pairing choice.
- **For downstream consumers** (`shorts-ideation`, `shorts-scripting`, `visual-prompts`): a brief
  with `status: candidate` or `status: produced` is safe to hand forward as a companion grounding
  artifact. A brief hand-edited to any other value, or whose `date` predates the most recent
  refresh of the research/thinker corpora it cites, should be flagged before use rather than
  consumed silently — see each generic skill's "Optional input" section for the exact rule.
```

- [ ] **Step 5: Verify**

Run:
```bash
grep -c "Per-brief mapping judgment" rgs-briefs/2026-07-25-why-parents-overspend-on-travel-teams.md rgs-briefs/2026-07-25-why-travel-sport-kids-quit-at-13.md rgs-briefs/2026-07-25-8000-a-year-club-soccer-parent.md
grep -c "For downstream consumers" rgs-briefs/README.md
```
Expected: `1` for each of the four files.

- [ ] **Step 6: Commit**

```bash
git add rgs-briefs/
git commit -m "docs: retrofit rgs-briefs with per-brief scripting mapping judgment"
```

---

### Task 3: `shorts-ideation` accepts an optional companion grounding artifact

**Files:**
- Modify: `.claude/skills/shorts-ideation/SKILL.md:18` (Pipeline position, Upstream cell)
- Modify: `.claude/skills/shorts-ideation/SKILL.md:23-25` (insert new section)
- Modify: `.claude/skills/shorts-ideation/SKILL.md:134-136` (concept brief template, insert
  Grounding section)
- Modify: `.claude/skills/shorts-ideation/SKILL.md:160-162` (marker-discipline closing note)

**Interfaces:**
- Consumes: a companion grounding artifact's archetype/angle hint, citations, and (optionally)
  "alternates considered" list — shape defined by `rgs-grounding`'s Grounding Brief template
  (`.claude/skills/rgs-grounding/SKILL.md`), but this skill never names `rgs-grounding` as the
  operative trigger.
- Produces: the concept brief template's new "Grounding" section (thinker/concept/archetype/file
  path reference) — consumed by Task 4's `shorts-scripting` optional-input section as the pointer
  back to the full artifact.

- [ ] **Step 1: Update the Pipeline position Upstream cell**

Locate (`SKILL.md:18`):

```
| **Upstream** | None — the input is a raw human idea or topic, however rough |
```

Replace with:

```
| **Upstream** | None by default — the input is a raw human idea or topic, however rough. Optionally, a companion grounding artifact from a brand-specific skill (see "Optional input" below) |
```

- [ ] **Step 2: Insert the "Optional input" section**

Locate (`SKILL.md:22-25`):

```markdown
Hand the finished concept brief to `shorts-scripting` next. Don't write the script yourself
here — see "Scope boundary" below.

## Scope boundary (read before drafting anything)
```

Replace with:

```markdown
Hand the finished concept brief to `shorts-scripting` next. Don't write the script yourself
here — see "Scope boundary" below.

## Optional input: a companion grounding artifact `[I]`

Some brands run a brand-specific skill upstream of this one that produces a **companion
grounding artifact** — a small, brand-neutral packet naming an archetype/angle hint (a
plain-language label + one-line rationale), one or more citations, and (optionally) a
"constraints that survive to publish" line. RaisingGoodSports's `rgs-grounding` is the first
skill that produces one — see its `SKILL.md` — but this skill doesn't hardcode RGS by name; any
brand-specific skill producing the same shape of artifact works the same way here. This is an
interface convention, not a corpus claim — that's why it's marked `[I]`.

When a companion artifact is provided:

- **Prefer an angle consistent with its archetype/angle hint.** Don't invent an angle the
  artifact's citations can't support.
- **If no archetype-consistent angle passes this skill's own validation gate** (step 5 below —
  net information gain, home-feed click test, packaging-compellingness, demonetization screen):
  do not stretch a citation to force a fit. Instead, pick from the artifact's own "alternates
  considered" list if it has one, or report back that the upstream brand skill needs to produce a
  different pairing. Never ship a brief built on an unsupported angle.
- **Demonetization screen and safety-sensitive citations:** step 2's screen (below) flags
  "sensitive medical/financial framing." A companion artifact's safety-sensitive citation passes
  this screen when it already carries a named source and non-sensational framing (the upstream
  brand skill's own protocol should guarantee this) — the screen's intent is to catch content
  presenting *as* a health/financial authority, and a properly-sourced citation is the opposite
  of that failure mode. Only an unsourced or sensationalized safety-sensitive claim fails the
  screen.
- **Staleness check:** if the artifact's stated date predates the most recent refresh of
  whatever corpus it cites, or its status field indicates it isn't in an active/consumable
  state, flag this before use rather than proceeding silently.
- **Carry it forward, don't re-derive it.** The concept brief's "Grounding" section (see the
  template below) points at the artifact rather than re-typing its citation text — the artifact
  remains the single source of truth for citation content.

## Scope boundary (read before drafting anything)
```

- [ ] **Step 3: Insert the Grounding section into the concept brief template**

Locate (`SKILL.md:130-138`):

```markdown
## Validation
- Net information gain: [the specific new angle/fact vs. the top 5 existing videos]
- Home-feed click test: [pass/fail + why]
- Packaging-compellingness: [pass/fail + why]
- Demonetization/policy screen: [clear / flagged — note]

## Handoff
This brief feeds `shorts-scripting` next. Scripting owns the opening lines, retention loop
structure, and pacing — not this brief.
```

Replace with:

```markdown
## Validation
- Net information gain: [the specific new angle/fact vs. the top 5 existing videos]
- Home-feed click test: [pass/fail + why]
- Packaging-compellingness: [pass/fail + why]
- Demonetization/policy screen: [clear / flagged — note]

## Grounding (omit this section entirely if no companion artifact was provided)
- Source: [companion artifact file path]
- Archetype/angle hint honored: [archetype label]
- Citations carried forward: [thinker/source names — full citation text lives in the artifact,
  not repeated here]

## Handoff
This brief feeds `shorts-scripting` next. Scripting owns the opening lines, retention loop
structure, and pacing — not this brief.
```

- [ ] **Step 4: Update the marker-discipline closing note**

Locate (`SKILL.md:160-162`):

```markdown
No `[I]` or `[T]` markers appear in this skill — every normative rule traces to a specific
corpus finding. If a future edit needs an industry-practice or tool/policy claim, mark it
`[I]`/`[T]` explicitly rather than leaving it bare.
```

Replace with:

```markdown
This skill's content carries `[C]` markers exclusively, with one exception: the "Optional
input: a companion grounding artifact" section above, marked `[I]` — an interface convention,
not a corpus claim. If a future edit needs another industry-practice or tool/policy claim, mark
it `[I]`/`[T]` explicitly rather than leaving it bare.
```

- [ ] **Step 5: Verify**

Run:
```bash
grep -n "^## Optional input" .claude/skills/shorts-ideation/SKILL.md
grep -n "^## Grounding (omit" .claude/skills/shorts-ideation/SKILL.md
grep -n "No \`\[I\]\` or \`\[T\]\` markers appear in this skill" .claude/skills/shorts-ideation/SKILL.md
```
Expected: first two greps each return one match; third grep returns no match (confirms the old
absolute claim was replaced, not duplicated).

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/shorts-ideation/SKILL.md
git commit -m "feat: shorts-ideation accepts an optional companion grounding artifact"
```

---

### Task 4: `shorts-scripting` accepts an optional companion grounding artifact

**Files:**
- Modify: `.claude/skills/shorts-scripting/SKILL.md:17-20` (Pipeline position, upstream-input
  bullet)
- Modify: `.claude/skills/shorts-scripting/SKILL.md:40-47` (`[I]` enumeration)
- Modify: `.claude/skills/shorts-scripting/SKILL.md:53-55` (insert new section)
- Modify: `.claude/skills/shorts-scripting/SKILL.md:150-151` (output contract, Delivery notes
  field)

**Interfaces:**
- Consumes: Task 3's concept-brief "Grounding" section (file path pointer) and/or a companion
  artifact handed directly; Task 1's `references/scripting-beat-mapping.md` mapping rule and
  per-brief judgment format.
- Produces: a script whose Delivery notes field may carry a verbatim "constraints that survive to
  publish" line — consumed by Task 6's `shorts-assembly` and `social-repurpose` additions.

- [ ] **Step 1: Update the Pipeline position upstream-input bullet**

Locate (`SKILL.md:17-20`):

```markdown
- **Upstream input:** the `shorts-ideation` skill's concept brief — angle, hook
  concept, packaging direction (title frame, cover text), target avatar. If you
  don't have this, ask for it rather than inventing a concept from scratch;
  this skill scripts a concept, it doesn't originate one.
```

Replace with:

```markdown
- **Upstream input:** the `shorts-ideation` skill's concept brief — angle, hook
  concept, packaging direction (title frame, cover text), target avatar. If you
  don't have this, ask for it rather than inventing a concept from scratch;
  this skill scripts a concept, it doesn't originate one. **Optionally**, a companion grounding
  artifact may also be handed to this skill directly, or reached via the concept brief's
  "Grounding" section — see "Optional input" below.
```

- [ ] **Step 2: Update the `[I]` enumeration**

Locate (`SKILL.md:40-47`):

```markdown
- **`[I]`** industry practice — used for three things in this skill: the
  150–170 wpm narration-pace assumption, the re-hook's specific ~15s
  placement (the underlying re-hook *cadence* is `[C]`; the exact timestamp is
  this skill's own synthesis — see `references/beat-timing-model.md`), and
  the requirement of at least one concrete proof beat inside Build/Value (the
  corpus's proof-density cadence is stated for long-form; compressing it into
  a single Shorts-scale beat is this skill's adaptation — see
  `references/retention-loops-and-structure.md`).
```

Replace with:

```markdown
- **`[I]`** industry practice — used for four things in this skill: the
  150–170 wpm narration-pace assumption, the re-hook's specific ~15s
  placement (the underlying re-hook *cadence* is `[C]`; the exact timestamp is
  this skill's own synthesis — see `references/beat-timing-model.md`), the
  requirement of at least one concrete proof beat inside Build/Value (the
  corpus's proof-density cadence is stated for long-form; compressing it into
  a single Shorts-scale beat is this skill's adaptation — see
  `references/retention-loops-and-structure.md`), and the "Optional input: a
  companion grounding artifact" section below (an interface convention, not a
  corpus claim).
```

- [ ] **Step 3: Insert the "Optional input" section**

Locate (`SKILL.md:51-55`):

```markdown
If a concept brief needs something the corpus doesn't cover (e.g. genre-specific
hook phrasing, a topic this corpus never touches), say so explicitly in the
script's notes rather than inventing generic advice to fill the gap.

## Process
```

Replace with:

```markdown
If a concept brief needs something the corpus doesn't cover (e.g. genre-specific
hook phrasing, a topic this corpus never touches), say so explicitly in the
script's notes rather than inventing generic advice to fill the gap.

## Optional input: a companion grounding artifact `[I]`

If a companion grounding artifact is handed to this skill (directly, or via the concept brief's
"Grounding" section), weave its per-beat citation content into this script's native beats rather
than inventing your own framing for that material:

- Follow the artifact's own stated per-brief mapping judgment (where its Turn-equivalent content
  lands, whether its Payoff-equivalent content is the Build's proof beat or this script's own
  Payoff beat) — the fixed translation rule behind that judgment, if you need the full reasoning,
  is whatever reference file the artifact's producing skill documents (e.g. `rgs-grounding`'s
  `references/scripting-beat-mapping.md`).
- Preserve any citation markers in the artifact's text verbatim (e.g. `[THINKER: ...]`,
  `[RESEARCH: ...]`) in this script's output — don't strip or paraphrase them away.
- Restate any quotability constraint (e.g. quote-ok vs. paraphrase-caution) at every beat that
  uses the citation, not just once.
- If the artifact states a "constraints that survive to publish" line, copy it **verbatim** into
  this script's own Delivery notes field (see the output contract below) so it reaches
  `shorts-assembly` and, through it, `social-repurpose` — those skills honor a flagged
  constraint without needing to know what produced it.

If no companion artifact is provided, this section doesn't apply — script normally.

## Process
```

- [ ] **Step 4: Update the output contract's Delivery notes field**

Locate (`SKILL.md:150-151`):

```
Delivery notes: <muted-friendly check, medium-confidence flags used (if any),
  humanize-pass confirmation>
```

Replace with:

```
Delivery notes: <muted-friendly check, medium-confidence flags used (if any),
  humanize-pass confirmation, and — only if a companion grounding artifact supplied one — its
  "constraints that survive to publish" line, copied verbatim>
```

- [ ] **Step 5: Verify**

Run:
```bash
grep -n "used for four things in this skill" .claude/skills/shorts-scripting/SKILL.md
grep -n "^## Optional input" .claude/skills/shorts-scripting/SKILL.md
grep -n "constraints that survive to publish" .claude/skills/shorts-scripting/SKILL.md
```
Expected: each returns at least one match (the third returns two — once in the new section, once
in the Delivery notes field description).

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/shorts-scripting/SKILL.md
git commit -m "feat: shorts-scripting accepts an optional companion grounding artifact"
```

---

### Task 5: `visual-prompts` accepts an optional companion grounding artifact

**Files:**
- Modify: `.claude/skills/visual-prompts/SKILL.md:10-12` (Pipeline position, upstream-input
  bullet)
- Modify: `.claude/skills/visual-prompts/SKILL.md:41-43` (insert new section)

**Interfaces:**
- Consumes: a companion artifact's visual motif cue (plain-language shot description).
- Produces: nothing consumed by a later task — this skill never renders on-screen text, so no
  quote-card/quotability gate is added here (that responsibility stays in Task 4's
  `shorts-scripting` Delivery-notes carry-forward, per the corrected design).

- [ ] **Step 1: Update the Pipeline position upstream-input bullet**

Locate (`SKILL.md:10-12`):

```markdown
- **Upstream input:** the shot-ready, timed script from `shorts-scripting` — a beat-by-beat breakdown
  (Hook / Setup / Build / Re-hook / Payoff / Loop-CTA, or whatever beats that skill emits) with a
  duration and VO line per beat.
```

Replace with:

```markdown
- **Upstream input:** the shot-ready, timed script from `shorts-scripting` — a beat-by-beat breakdown
  (Hook / Setup / Build / Re-hook / Payoff / Loop-CTA, or whatever beats that skill emits) with a
  duration and VO line per beat. **Optionally**, a companion grounding artifact may also be handed
  to this skill directly (or reached via the script's own upstream chain) — see "Optional input"
  below.
```

- [ ] **Step 2: Insert the "Optional input" section**

Locate (`SKILL.md:40-43`):

```markdown
find yourself about to write a rule with no `[C]`/`[I]`/`[T]` marker, stop — that's the signal you're
inventing instead of sourcing. Say the corpus doesn't cover it and move on.

## Workflow
```

Replace with:

```markdown
find yourself about to write a rule with no `[C]`/`[I]`/`[T]` marker, stop — that's the signal you're
inventing instead of sourcing. Say the corpus doesn't cover it and move on.

## Optional input: a companion grounding artifact `[I]`

If a companion grounding artifact is handed to this skill, use its visual motif cue as a
shot-composition input for the beat(s) carrying that citation — fold the cue into step 2's
still-count decision and step 4's prompt anatomy for that beat, the same way any other visual
note is used.

This section does **not** add a quotability/quote-card gate — this skill never renders
on-screen text (every prompt ends "No Text," step 4 below); on-screen text and caption
decisions, including whether a citation is safe to render as a quote card, belong entirely to
`shorts-scripting`'s Delivery notes and `shorts-assembly`'s caption treatment. If no companion
artifact is provided, this section doesn't apply — build the prompt sheet normally.

## Workflow
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -n "^## Optional input" .claude/skills/visual-prompts/SKILL.md
grep -n "does \*\*not\*\* add a quotability" .claude/skills/visual-prompts/SKILL.md
```
Expected: both return exactly one match — confirms the section exists and explicitly disclaims
the quote-card gate (the corrected placement from fable's review).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/visual-prompts/SKILL.md
git commit -m "feat: visual-prompts accepts an optional companion grounding artifact"
```

---

### Task 6: `shorts-assembly` and `social-repurpose` honor a constraints-that-survive-to-publish line

**Files:**
- Modify: `.claude/skills/shorts-assembly/SKILL.md:16-21` (Inputs required section)
- Modify: `.claude/skills/social-repurpose/SKILL.md:12-17` (Upstream input paragraph)

**Interfaces:**
- Consumes: Task 4's Delivery-notes "constraints that survive to publish" line, verbatim.
- Produces: nothing consumed by a later task — this is the terminal hop for a publish-time
  constraint (captions in `shorts-assembly`, post copy in `social-repurpose`).

- [ ] **Step 1: Update `shorts-assembly/SKILL.md`'s Inputs required section**

Locate (`SKILL.md:16-21`):

```markdown
**Inputs required to run this skill:**
1. The shot-ready script with beat timing (Hook/Setup/Build/Payoff/Loop, seconds + word counts).
2. The voiceover brief (voice pick, pacing wpm, take count) — or at minimum the VO's target wpm and total duration.
3. The visual prompt sheet keyed to script beats (which shot uses which asset, generated vs. stock).

If any of the three is missing, ask for it rather than inventing shot content — this skill assembles what upstream produced, it doesn't re-derive the script or the visuals.
```

Replace with:

```markdown
**Inputs required to run this skill:**
1. The shot-ready script with beat timing (Hook/Setup/Build/Payoff/Loop, seconds + word counts).
2. The voiceover brief (voice pick, pacing wpm, take count) — or at minimum the VO's target wpm and total duration.
3. The visual prompt sheet keyed to script beats (which shot uses which asset, generated vs. stock).

If any of the three is missing, ask for it rather than inventing shot content — this skill assembles what upstream produced, it doesn't re-derive the script or the visuals.

**Optional: constraints that survive to publish.** If the incoming script's Delivery notes field
carries a "constraints that survive to publish" line (e.g. a quotability restriction on a
citation, or a mandatory safety-resource line), honor it in the caption/overlay treatment below —
this skill doesn't need to know what produced the constraint, only that it's flagged and must be
respected.
```

- [ ] **Step 2: Update `social-repurpose/SKILL.md`'s Upstream input paragraph**

Locate (`SKILL.md:12-17`):

```markdown
**Upstream input** (from `shorts-assembly`): the finished Short's script, its packaging
direction (working title/angle decided at `shorts-ideation`), and the edit/assembly plan.
You need the script text (for AEO specifics and hook language) and whatever title/thumbnail
direction earlier stages already committed to — this skill does not re-derive thumbnail
design (that's `shorts-ideation`/`shorts-assembly` territory); it writes the **text** that
accompanies the finished video.
```

Replace with:

```markdown
**Upstream input** (from `shorts-assembly`): the finished Short's script, its packaging
direction (working title/angle decided at `shorts-ideation`), and the edit/assembly plan.
You need the script text (for AEO specifics and hook language) and whatever title/thumbnail
direction earlier stages already committed to — this skill does not re-derive thumbnail
design (that's `shorts-ideation`/`shorts-assembly` territory); it writes the **text** that
accompanies the finished video. **If the script or assembly plan carries a "constraints that
survive to publish" line** (e.g. a mandatory safety-resource mention), honor it in the post copy
you write — this skill doesn't need to know what produced the constraint, only that it's
flagged.
```

- [ ] **Step 3: Verify**

Run:
```bash
grep -n "constraints that survive to publish" .claude/skills/shorts-assembly/SKILL.md .claude/skills/social-repurpose/SKILL.md
```
Expected: one match in each file.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/shorts-assembly/SKILL.md .claude/skills/social-repurpose/SKILL.md
git commit -m "feat: shorts-assembly and social-repurpose honor a constraints-that-survive-to-publish line"
```

---

### Task 7: Point the original RGS design spec's "Follow-on work" at this plan

**Files:**
- Modify: `docs/superpowers/specs/2026-07-25-raisinggoodsports-grounding-skills-design.md:325-337`

**Interfaces:**
- Consumes: nothing new — this is a documentation pointer only.
- Produces: nothing consumed by another task.

- [ ] **Step 1: Add the pointer**

Locate:

```markdown
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
```

Replace with:

```markdown
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
```

- [ ] **Step 2: Verify**

Run: `grep -n "Addressed:" docs/superpowers/specs/2026-07-25-raisinggoodsports-grounding-skills-design.md`
Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-07-25-raisinggoodsports-grounding-skills-design.md
git commit -m "docs: point RGS design spec's follow-on work at the pipeline-handoff spec"
```

---

### Task 8: Final integration dry run

**Files:** none created or modified except a possible REFACTOR fix in Step 4.

**Interfaces:**
- Consumes: everything from Tasks 1–7.

- [ ] **Step 1: Brand-neutrality check**

Run:
```bash
grep -n "^## Optional input" .claude/skills/shorts-ideation/SKILL.md .claude/skills/shorts-scripting/SKILL.md .claude/skills/visual-prompts/SKILL.md
```
Expected: one match per file, each reading `## Optional input: a companion grounding artifact
` + backtick-I-backtick — confirms the contract section exists under a generic (not brand-named)
heading in all three skills.

Run:
```bash
grep -in "RGS Grounding Brief\|## RaisingGoodSports\|when producing RaisingGoodSports" .claude/skills/shorts-ideation/SKILL.md .claude/skills/shorts-scripting/SKILL.md .claude/skills/visual-prompts/SKILL.md .claude/skills/shorts-assembly/SKILL.md .claude/skills/social-repurpose/SKILL.md
```
Expected: no matches — confirms no section header or operative rule was hardcoded to RGS by
name (the pattern fable's review flagged and this plan rejected). A prose mention of
`rgs-grounding` as an *example* inside the "Optional input" section (Task 3, Step 2) is expected
and fine — this check targets brand-named *headers and rules*, not every string occurrence.

- [ ] **Step 2: Marker-consistency check**

Run:
```bash
grep -n "used for four things in this skill" .claude/skills/shorts-scripting/SKILL.md
grep -n "No \`\[I\]\` or \`\[T\]\` markers appear in this skill" .claude/skills/shorts-ideation/SKILL.md
```
Expected: first returns one match (confirms the enumeration was updated from "three" to "four");
second returns no match (confirms the old absolute claim in `shorts-ideation` was replaced, not
left alongside the new `[I]` line it would contradict).

- [ ] **Step 3: Functional dry run**

Dispatch a subagent, working directory `C:\Projects\ContentStudio`, prompt:

```
Two steps, in order:

1. Use the shorts-ideation skill for the topic "why families overspend on travel-team club
   sports," with this companion grounding artifact:
   rgs-briefs/2026-07-25-why-parents-overspend-on-travel-teams.md — read it in full and treat it
   as the companion artifact this skill's "Optional input" section describes. Produce the
   concept brief.

2. Use the shorts-scripting skill on the concept brief you just produced, still treating the
   same Grounding Brief as the companion artifact. Produce the full script.

Show both outputs in full.
```

Expected:
- The concept brief includes a non-empty "Grounding" section pointing at
  `rgs-briefs/2026-07-25-why-parents-overspend-on-travel-teams.md`, naming archetype A1.
- The script's Setup beat (or early Build) carries the Turn content (Veblen's mechanism,
  paraphrased, explicitly not on a quote card).
- The script's Payoff beat carries F4's Content Hook resolving the "why do parents overspend"
  question, per the retrofitted brief's stated per-brief judgment (Task 2, Step 1).
- `[THINKER: ...]` / `[RESEARCH: ...]`-style markers are preserved somewhere in the script or its
  notes, not silently dropped.
- The script's Delivery notes field contains, verbatim, "paraphrase-caution (Veblen) — never
  render as an on-screen quote/direct-attribution card."

- [ ] **Step 4: REFACTOR — only if Step 3 failed**

If any expected element from Step 3 is missing or wrong: identify which file's instructions the
subagent actually followed, edit that file to close the gap, and re-run Step 3 with a fresh
subagent. Repeat until it passes. If Step 3 passed on the first try, skip this step — don't edit
a passing skill speculatively.

- [ ] **Step 5: Commit (only if Step 4 made changes)**

```bash
git add .claude/skills/shorts-ideation/SKILL.md .claude/skills/shorts-scripting/SKILL.md
git commit -m "fix: address gaps found in RGS pipeline-handoff integration dry run"
```

If Step 4 was skipped, no commit is needed for this task — the working tree should already be
clean from Tasks 1–7's commits.
