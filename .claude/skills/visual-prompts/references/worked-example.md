# Worked example: a scripted Short → a Midjourney prompt sheet

Input beat table below is the shot-list shape used elsewhere in the ContentStudio corpus (the
production playbook's Template 2, Short S042, "it's not the beans" coffee video) — a reasonable stand-in
for what `shorts-scripting` hands off, since beats + duration + VO line is the common shape either way.
The playbook's own template renders the hook still in Ideogram (a text-capable model) because its hook
card ("IT'S NOT THE BEANS") is baked into the image. This skill routes the same beat through
**Midjourney instead, with the text pulled out** — that's the concrete difference this skill makes: MJ
generates the plate, `shorts-assembly` composites the on-screen text.

## Input (from the script)

| # | Beat | Dur | VO line | On-screen text (handled downstream, not in the MJ prompt) |
|---|---|---|---|---|
| 1 | Hook | 3s | "Your drip coffee tastes flat..." | "IT'S NOT THE BEANS" |
| 2 | Setup | 5s | "Cafes do one thing you skip..." | "$2 FIX" |
| 3 | Build | 14s | "Bloom the grounds first..." | "BLOOM 30s" |
| 4 | Re-hook | 4s | "But there's a second mistake almost everyone makes..." | "2ND MISTAKE ->" |
| 5 | Payoff | 10s | "Water off the boil, 90s after..." | "SMOOTH" |
| 6 | Loop/CTA | 8s | "So it was never the beans..." | (none — visual mirrors beat 1) |

## Step 1 — stills-per-beat, applying the ~3s cadence rule

- Beat 1 (Hook, 3s): 1 still — already at the cadence limit.
- Beat 2 (Setup, 5s): 1 still is acceptable (borderline; could split into 2 if the VO has a clear
  midpoint beat).
- Beat 3 (Build, 14s): 14s ÷ ~3-4s ≈ **4 stills**, one per escalating step of the bloom process.
- Beat 4 (Re-hook, 4s): 1 still.
- Beat 5 (Payoff, 10s): **2-3 stills** (pour → wait → taste-reaction cue).
- Beat 6 (Loop/CTA, 8s): reuse beat 1's still (the script's own "mirror the opening" instruction) —
  **0 new generations needed**, which is itself the corpus-grounded loop technique
  `[C] (Jenny Hoyos, mhVDcqnxxaY)`, not a gap.

## Step 2 — whole-Short setup

No recurring character in this Short (it's product/process, not a host) → no Omni Reference needed.
Consistency here is really just "reads like one shoot": a single `--sref` isn't essential for a
tight product Short like this, so the setup relies on a **shared style vocabulary repeated in every
prompt** (photoreal, DSLR, warm morning light) rather than a locked sref code. If this were a
recurring-character or heavily-branded series, this section would instead specify an `--oref`/`--sref`.

```
WHOLE-SHORT SETUP
  Aspect ratio:     --ar 9:16
  Style/params:     --style raw --s 150
  Consistency:      none (product/process Short) — shared style vocabulary per prompt: photoreal, DSLR,
                    warm morning kitchen light, muted brown/cream palette
  Notes:            beat 6 reuses beat 1's still exactly (loop mirror) — no new generation

COVER / THUMBNAIL
  Cover = Hook beat still #1 + shorts-assembly's text overlay ("IT'S NOT THE BEANS"). The packaging
  direction (flat coffee, one dominant emotion — disappointment) is already fully delivered by the
  Hook still itself; nothing about it calls for a separately staged cover shot, so no dedicated cover
  prompt is generated. (Per the workflow's step 7: this decision is stated explicitly, not skipped.)
```

## Step 3 — per-beat prompts

| Beat | Still # | Midjourney prompt | Params |
|---|---|---|---|
| Hook | 1 | extreme close-up of a black cup of drip coffee, flat dull surface, faint steam rising, kitchen counter softly blurred behind, warm morning window light from the left, moody and a little disappointing, photoreal, warm brown and cream palette, shot on 35mm film. No Text. | `--ar 9:16 --style raw --s 150` |
| Setup | 1 | photo of a cafe counter, espresso portafilter mid-tamp, brushed steel surface, warm ambient light, shallow depth of field, photoreal, DSLR, warm brown and cream palette. No Text. | `--ar 9:16 --style raw --s 150` |
| Build | 1 | close-up of dry coffee grounds in a ceramic dripper, hot water just beginning to touch the surface, tiny cracks forming, overhead kitchen light, photoreal macro, DSLR. No Text. | `--ar 9:16 --style raw --s 150` |
| Build | 2 | close-up of coffee grounds blooming, small bubbles breaking the surface, gentle steam, overhead kitchen light, photoreal macro, DSLR. No Text. | `--ar 9:16 --style raw --s 150` |
| Build | 3 | close-up of a fully bloomed coffee bed, dome of foam rising, bubbles thickening, overhead kitchen light, photoreal macro, DSLR. No Text. | `--ar 9:16 --style raw --s 150` |
| Build | 4 | wide shot of a ceramic dripper on a wood counter, bloom settling, gentle wisps of steam catching the window light, photoreal, DSLR, warm brown and cream palette. No Text. | `--ar 9:16 --style raw --s 150` |
| Re-hook | 1 | close-up of a kettle spout, thin stream of steam, dark blurred kitchen background, dramatic side lighting, photoreal, DSLR. No Text. | `--ar 9:16 --style raw --s 150` |
| Payoff | 1 | coffee pouring from a dripper into a clear glass mug, warm brown liquid catching the light, steam rising, shallow depth of field, photoreal, DSLR, warm brown and cream palette. No Text. | `--ar 9:16 --style raw --s 150` |
| Payoff | 2 | close-up of a hand lifting a clear glass mug of coffee toward camera, soft warm light, shallow depth of field, photoreal, DSLR. No Text. | `--ar 9:16 --style raw --s 150` |
| Loop/CTA | — | reuse Hook still 1 exactly — no new prompt | — |

## Step 4 — per-beat motion decision (still vs. `--motion low` vs. a real i2v clip)

Running the decision table from `references/image-to-video.md` (see `SKILL.md` workflow step 6)
against each beat:

- **Hook, Setup, Re-hook:** single stills, no motion needed — each is already at or near the ~3s
  cadence limit (step 1).
- **Payoff:** the pour-to-taste sequence is visual variety over ~10s, already covered by the 2-3
  stills from step 1 — no motion needed.
- **Build:** this is the one beat where a static image genuinely under-sells the process — the VO
  ("bloom the grounds first...") describes **continuous transformation** (dry grounds → bubbling →
  full dome), which is exactly tier 3 of the decision table: a real i2v clip, not just `--motion low`
  on one still.

Rather than 4 separate Build stills, replace stills 1-3 with a single animated clip and keep still 4
(the settled wide shot) as a static cutaway:

```
I2V PROMPT — Build beat

Source still:        Build still 1 (dry coffee grounds in a ceramic dripper, hot water just touching
                      the surface)
Target tool:          Kling — start/end-frame keyframing suits this beat's single continuous
                      transformation better than Seedance's multi-shot strength, which isn't needed here
                      (per the model-landscape table in references/image-to-video.md)
Start frame:          Build still 1 (as generated)
End frame:            Build still 3's composition (fully bloomed dome, thick bubbles) — produced by
                      editing Build still 1 in an external image editor for the later-stage look, per
                      the start/end-frame keyframing section of references/image-to-video.md, rather
                      than generating an unrelated second image
I2V prompt text:      start with a close-up of dry coffee grounds just touching hot water; the grounds
                      slowly bloom, small bubbles breaking the surface, building to a thick dome of
                      foam; slow, continuous motion; in a single shot, no cuts; no subtitles and no
                      music.
```

Build still 2 (the mid-bloom stage) is dropped as a separate generation — its composition is now
covered by the clip's midpoint — and Build still 4 (wide, settled) remains a static cutaway still, so
this beat ends up as 2 stills + 1 clip instead of 4 stills.

MJ's own `--motion low` path was considered and rejected here: it's meant for a hero shot breathing in
place, not a multi-stage transformation, and MJ's video model is D-tier for anything beyond that
`[C] (Tao Prompts, uCsc0ORcJDo)`. A still-only Build beat (per the "AI slideshow" format,
`references/faceless-pacing-rules.md`) remains an equally valid, cheaper fallback if the animated clip
isn't worth its cost for this particular Short — that's a call for whoever is producing the Short to
make, but the prompt above is ready to use either way, not a placeholder.
