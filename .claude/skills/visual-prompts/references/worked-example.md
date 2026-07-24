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

## Step 4 — optional video note (only where motion earns its cost)

The Build beat's bloom sequence is a reasonable candidate for a single low-motion clip instead of 4
stills, if the assembly stage wants continuous motion there: take Build still 2 (mid-bloom) as the
start frame and prompt an image→video pass — `--motion low` (per the parameter table) — something like:

```
start with a close-up of coffee grounds blooming, bubbles breaking the surface;
the bloom slowly rises and settles; slow, no cuts; no subtitles and no music.
```

This is a note for `shorts-assembly` to decide on, not a directive — MJ's video model is D-tier
`[C] (Tao Prompts, uCsc0ORcJDo)`, so a still-only Build beat (per the "AI slideshow" format,
`references/faceless-pacing-rules.md`) is an equally valid, often cheaper choice.
