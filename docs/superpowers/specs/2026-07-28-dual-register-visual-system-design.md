# Dual-Register Visual System — Design

**Date:** 2026-07-28
**Status:** approved
**Affects:** `.claude/skills/visual-prompts/`, `.claude/skills/midjourney-prompting/`, `scripts/`, `tests/`

## Problem

The visual stage is the weakest link in the pipeline. Evidence: the emitted sheet at
`runs/letkidsplay-20260727-005326/03-visual/artifact.v1.md`, generated from a script whose spine is a
1st-century Plutarch pairing.

Five distinct failures, in order of severity:

1. **The thinker era is absent.** The script says "someone warned us 2,000 years ago" and carries
   `[THINKER: Plutarch]` markers on two beats. The sheet contains zero Plutarch visuals. The single
   most distinctive property of the content — an ancient voice against a modern problem — has no
   visual expression.
2. **Six of nine stills are the same photograph.** Hook, Setup #2, Build 1/2/3 and Payoff #1 all read:
   *eight-year-old from behind · blank-tagged gear · empty gym out of focus · low rear angle · 35mm
   f2.8 · dim overcast · muted desaturated.* The only variable across 45 seconds is how much gear is
   on the child.
3. **No sport is specified anywhere.** `"empty youth gym softly out of focus"` carries no sport
   signal — no hoop, goal, mat, or baseline. Confirmed absent upstream too: neither the grounding
   brief, the ideation artifact ("sports parent", "$5,000-a-year sports"), nor the script names a sport.
4. **Optics are copy-pasted.** `35mm f2.8` on seven of eleven prompts. No establishing wide, no long
   lens, one macro, no deep focus.
5. **Prompts are thin and uncopyable.** Each is one ~45-word sentence living inside a markdown table
   cell, with parameters in a *separate column* — so no prompt can be copied into Midjourney in one
   action, and most of the 9 prompt layers are absent or implied.

### Root cause

Failures 2 and 4 are *caused by the skill*, not by bad luck. The emitted sheet states its own
mechanism at line 67: *"Shared style vocabulary (repeated in every prompt, doing the consistency work
alongside the --sref code)."* That instruction is taught by
`visual-prompts/references/worked-example.md:38-40`. Achieving consistency by cloning the prompt body
guarantees near-identical images.

Compounding it: `visual-prompts/SKILL.md` proceeds beat → shot count → prompt, one beat at a time,
and **has no step that examines the sheet as a sequence.** Step 4's "beat-to-beat coherence" note asks
only whether shots look *related* — never whether they are *different*.

## Solution overview

Three mechanisms, none of which exist today:

1. **Two visual registers** with disjoint vocabularies, so "now" and "then" are legible in half a second.
2. **An arc-first workflow** — the whole sheet is planned as a sequence before any prompt is written.
3. **Gate C, a deterministic shot-variety lint** that runs on the arc and on the emitted sheet, and
   blocks emission on failure.

Plus two output-quality requirements: comprehensive 9-layer prompts, and a copy-paste-ready sheet format.

## Decisions taken

| Decision | Choice | Rationale |
|---|---|---|
| Where the register system lives | Generic dual-register inside `visual-prompts` | Keeps one storyboarding skill. Registers are named generically (`present` / `source-era`); RGS supplies the concrete case. Preserves CLAUDE.md's generic-vs-brand boundary. |
| Register assignment | Quota + intercut floor | Marker-driven alone yields 2 thinker shots at 5s and 40s with a 20s all-modern Build. Quota guarantees rhythm. |
| Register B content | Mixed: FIGURE + WORLD + ARTIFACT | A single repeated archetype figure would recreate the sameness failure inside the new register. |
| Sport lock owner | `visual-prompts`, stating rationale | Nothing upstream names a sport; it is a visual decision; self-contained, touches no other skill. |
| Register B art style | Fixed channel signature, era-varied content | Viewers learn "painted = the old wisdom" as channel grammar; the `--sref` code is harvested once and stored as a repo asset rather than re-derived per Short. |

## The two register contracts

The core mechanism is **vocabulary disjunction**: the registers share no medium, no optics language,
no palette family, and no parameter band. That separation is what makes the contrast readable.

### Register A — PRESENT

- **Medium:** `documentary sports photography`
- **World lock:** one sport per Short, named in *every* A prompt, plus at least one **sport-signature
  object** in frame (hoop + backboard + painted key; goal net + corner flag + touchline; spring floor
  + balance beam + chalk). The string `empty gym` and its variants are **banned** — that phrasing is
  what produced beige rooms.
- **Parameters:** `--raw`, `--s 80–120` — the documented photographic band
  (`midjourney-prompting/references/prompt-architecture.md`) `[T]`.
- **Consistency:** one `--sref` code, harvested per Short.
- **Shot classes, which must rotate:**
  - `ESTABLISHING` — wide; the venue reads instantly
  - `ACTION-ADJACENT` — mid; bodies and equipment in use
  - `DETAIL` — macro; the object carrying the claim
  - `HUMAN-COST` — the emotional frame

  The failing sheet is `HUMAN-COST` eleven times and the other three zero times.

### Register B — SOURCE ERA

- **Medium:** one fixed painterly signature, channel-wide.
- **Parameters:** **no `--raw`**, `--s 400–700` — the documented fine-art/illustrative band `[T]`.
  This is what makes it read as not-a-photograph.
- **Consistency:** one `--sref` code harvested **once** and stored in the repo as a channel-level
  asset, reused by every future Short.
- **Banned vocabulary:** `DSLR`, focal lengths (`mm`), f-stops (`f/`), `shot on 35mm film`,
  `documentary`. Register B speaks in ground, glaze, brushwork, and light quality. Sharing optics
  language with A collapses the two registers back into one look.
- **Figure treatment:** archetype only — unnamed, face averted or lost in shadow, dressed and posed to
  the role. Never a likeness attempt. This also means no subject-lock is needed, so the Short stays in
  V8.2 rather than dropping to V7 at 2× GPU `[T] (verified 2026-07-26)`.
- **Shot classes, which must rotate:** `FIGURE` · `WORLD` · `ARTIFACT`.

### The motif bridge

The grounding brief's motif is rendered in **both** registers. On the reference Short, the watering can
stops being a modern still-life on a wooden table and becomes a terracotta vessel over a seedling on a
sun-bleached Mediterranean terrace, *and* has a modern counterpart. A motif that crosses eras is what
welds the two registers into one story instead of two intercut slideshows.

### PLATE

Subject-free background plates for motion-graphic cards are neither register. They are exempt from the
world lock, the register vocabularies, and the parameter bands — but not from prompt density or the
copy-paste format.

## Workflow changes

### New step 2.5 — Lock the world (once per Short)

Emits a block every downstream prompt inherits:

```
WORLD LOCK
  register_a_sport:              [one sport]
  register_a_venue:              [venue type]
  register_a_signature_objects:  [2-3 objects that make the sport unmistakable]
  register_a_season_time:        [season / time of day]
  register_a_rationale:          [one line tying the sport to the claim's evidence]
  register_b_thinker:            [name]
  register_b_era_place:          [specific era and place]
  register_b_locations:          [2-3 named period locations]
  register_b_artifacts:          [2-3 period objects]
  register_b_figure_archetype:   [role and dress; never a likeness]
  motif:                         [the grounding brief's motif, rendered in BOTH registers]
```

### New step 3 — Build the visual arc (before any prompt exists)

Lay the whole Short out as a table first — `# | Beat | Register | Shot class | Scale | Camera height |
What changes vs. previous` — then run Gate C **on the table**. Fixing a repetitive arc means editing a
table row, not eleven prompt strings, and it happens before a single GPU minute is spent.

### Changed step 4 — delegation

The handoff block gains `register:` and `shot_class:`. `midjourney-prompting` maps register → parameter
band. **The shared-style-vocabulary pattern is deleted outright** from both `SKILL.md` and
`worked-example.md`; consistency comes from `--sref` alone, which is what it is for, leaving the prompt
body free to vary.

## Gate C — shot-variety lint

Deterministic, implemented as a runnable script so it cannot be skipped or fudged. Runs on the arc and
again on the emitted sheet. Any finding blocks emission.

| Check | Rule |
|---|---|
| C1 | No two consecutive shots share a shot class |
| C2 | No two consecutive shots share a scale |
| C3 | No run of more than 2 consecutive shots in the same register |
| C4 | ≥3 distinct scales across the sheet |
| C5 | ≥2 distinct camera heights across the sheet |
| C6 | ≥3 Register A shots and ≥2 Register B shots |
| C7 | The register sequence alternates at least twice |
| C8 | Every Register A prompt names the locked sport and ≥1 signature object |
| C9 | No Register A prompt contains a banned generic-venue string (`empty gym`, `empty youth gym`) |
| C10 | No Register B prompt contains photographic-optics vocabulary (`DSLR`, `mm`, `f/`, `shot on 35mm film`, `documentary`) |
| C11 | No two prompts share 6 or more identical clauses (anti-clone) |
| C12 | Every prompt body has ≥10 clauses and ≥60 words (density) |
| C13 | Every prompt is one contiguous string, `No Text.` before the flags, flags last, `--ar` present |
| C14 | Register A carries `--raw` and `--s` 80–120; Register B carries no `--raw` and `--s` 400–700 |

The failing reference sheet must be kept as a regression fixture and must fail C1, C2, C3, C8, C9, C11,
C12 and C13.

## Prompt density — resolving a conflict with the corpus

`prompt-architecture.md` carries **"Short usually beats long"** `[C] (Tokenized AI, vezJXJGQMoY)` and
"Nine layers does not mean nine clauses." Gate A's A4 requires only layers 1, 2 and 4 (plus 6 and 7 for
photographic). The new requirement is comprehensive prompts.

**Resolution `[I]`, with both lines kept visible per the repo's conflict rule:** the corpus finding
concerns *padding and abstract quality claims diluting which words get weighted* — not the number of
distinct visual attributes specified. A prompt that names its lens, its light direction, its palette
and its background separation is denser, not more diluted. The rule therefore becomes **density, not
length**: all 9 layers must be present with concrete renderable content in each; the buzzword ban and
the padding ban both still stand. Gate A gains a pipeline-mode check `A4b` requiring all 9 layers.

This is an `[I]` adaptation and must be labelled as one wherever it appears. It does not delete the
`[C]` line.

## Output format — copy-paste requirement

Prompts move out of table cells. One block per shot:

```
### Shot 4 — Build (8–15s) · Register A · ESTABLISHING · XWIDE · LOW
Changes vs. previous: register switch back to present; widest frame in the Short.

    ```text
    <entire prompt: 9-layer body, "No Text.", then every flag — one contiguous string>
    ```
```

The fenced block is the whole Midjourney input. Nothing needed from any other column. This also makes
the sheet machine-parseable, which is what lets Gate C run against emitted artifacts.

## Non-goals

- No new pipeline stage or skill. Six-stage pipeline is unchanged.
- No change to `shorts-assembly`'s ownership of on-screen text — every prompt still ends `No Text.`
- No change to the i2v decision tiers in `references/image-to-video.md`, beyond i2v prompts inheriting
  their source still's register.
- Not re-running the reference Short. It is a fixture, not a deliverable.
