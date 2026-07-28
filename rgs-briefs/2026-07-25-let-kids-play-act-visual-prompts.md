---
version: 1
---
=== VISUAL PROMPT SHEET — Aristotle Named This 2,300 Years Before Private Equity ===

WHOLE-SHORT SETUP
  Aspect ratio:     --ar 9:16
  Style/params:     --style raw --s 160 --c 5 while drafting variants; drop to --c 0 once a
                     winning grid image is picked per beat.
  Consistency:      No recurring named host across the whole Short → generate Hook still #1
                     first with no --sref, then extract its style code and apply --sref CODE to
                     every later prompt below (bootstrap step). Scoped exception: the "buyer"
                     figure recurs across the three Build/re-hook market stills only (not the
                     whole Short) — add a single fixed --seed on top of the shared --sref for
                     just those three stills, since that figure isn't a named hero needing a
                     full Omni Reference character sheet, just good-enough continuity for one
                     internal sequence.
  Notes:            Every prompt ends "No Text." — the app icon, any diagram, and the "SOLD"/
                     price-tag cue are all rendered as plain generic shapes/glyphs, never
                     legible words; actual on-screen text (date stamp, "SOLD," the Payoff
                     checklist) is shorts-assembly overlay copy, composited after generation.

COVER / THUMBNAIL
  Dedicated MJ prompt (distinct from the Hook still — the Hook still deliberately withholds the
  ownership-change cue to raise the question; the thumbnail needs it already visible to bait the
  click):
  "Photorealistic close-up product shot, a smartphone screen showing a plain unbranded youth-
  sports registration app glyph (a simple ball-and-calendar icon, no readable text), a small
  blank red price-tag shape overlapping one corner of the screen, held at a slight low angle in
  a parent's hand, shallow depth of field, soft indoor window light, muted desaturated color
  palette, one dominant mood of quiet alarm. Photorealistic, DSLR, muted colors, shot on 35mm
  film. No Text." --ar 9:16 --style raw --s 160 --sref CODE

PER-BEAT PROMPTS
| Beat | Dur | Still # | Midjourney prompt | Params | Motion |
|---|---|---|---|---|---|
| Hook | 0–3s | 1 | Photorealistic close-up, a smartphone screen displaying a plain unbranded youth-sports registration app glyph (simple ball-and-calendar icon, no readable text), held in a parent's hand, blurred indoor kitchen counter behind, slight top-down angle looking down at the phone, soft morning window light, muted neutral color palette, quiet contemplative mood. No Text. | --ar 9:16 --style raw --s 160 (no --sref — this is the bootstrap still) | --motion low (slow ~5% push-in, signals "something's coming") |
| Setup | 3–8s | 2 | Photorealistic wide shot, a weathered classical Greek stoa colonnade at golden hour, worn marble columns, an olive branch resting on a low stone ledge, empty of people, warm low sunlight, muted earthy color palette, still contemplative mood. No Text. | --ar 9:16 --style raw --s 160 --sref CODE | still |
| Build/Value | 8–15s | 3 | Photorealistic wide shot, a bustling ancient open-air marketplace at midday, several independent merchant stalls each run by a different trader exchanging goods and coins, hand-crafted pottery visible on one stall, warm sunlight, dusty earthy color palette, lively grounded mood. No Text. | --ar 9:16 --style raw --s 160 --sref CODE --seed [FIXED-A] | still |
| Build/Value | 8–15s | 4 | Photorealistic medium shot, a single potter's hands actively shaping clay on a wheel at a market stall, another stall blurred in the background, warm directional light, dusty earthy color palette, focused industrious mood. No Text. | --ar 9:16 --style raw --s 160 --sref CODE --seed [FIXED-A] | still |
| Re-hook @ ~15s | 15–28s | 5 (start frame) | Photorealistic wide shot, the same ancient open-air marketplace, five distinct oil-press stalls each run by a different merchant, market bustling, warm midday sunlight, dusty earthy color palette. No Text. | --ar 9:16 --style raw --s 160 --sref CODE --seed [FIXED-A] | see I2V block below |

I2V PROMPTS (only for beats marked "see I2V block" above)
| Beat | Source still | Target tool | I2V prompt | Start/end-frame notes |
|---|---|---|---|---|
| Re-hook (15–28s) | Still #5 — wide marketplace shot, five distinct oil-press stalls | Kling — A-tier, named as excelling specifically at start/end-frame transformations, which is exactly what this beat needs (a market of five independent stalls consolidating into one owner) | "Wide shot of an ancient marketplace with five separate oil-press stalls, each run by a different merchant. Slowly, one by one, a single trader in plain dark cloth quietly approaches each stall and takes it over — restate framing: keep the wide shot fixed, no camera cuts. By the end, that one trader stands centrally among all five presses, now the only merchant left. Continuous slow motion, in a single shot, no cuts. No subtitles and no music." | End frame: same wide angle as the start frame (restate the fixed camera position so the transformation reads as one continuous shot, not a new scene) — the five stalls now show only the one trader present at each, standing centrally at the end. Produced as a still edit of Still #5 in an external image editor (recolor/reposition figures) before generating, per the start/end-frame keyframing technique — confirm Kling's current max single-clip duration before rendering; if it's under this beat's ~13s, split into two chained i2v segments (the buy-up montage, then the final centralized-owner reveal) per the extend guidance rather than forcing one over-long clip. |

PER-BEAT PROMPTS (continued)
| Beat | Dur | Still # | Midjourney prompt | Params | Motion |
|---|---|---|---|---|---|
| Payoff | 28–38s | 6 | Photorealistic close-up, a neat stack of official-looking papers and folders on a plain desk, a pen resting on top, soft overhead light, muted cool-gray color palette, formal orderly mood. No Text. | --ar 9:16 --style raw --s 140 --sref CODE | still |
| Payoff | 28–38s | 7 | Photorealistic close-up, the same desk, a single folder now open with a rubber stamp resting beside it, soft overhead light, muted cool-gray color palette, formal orderly mood. No Text. | --ar 9:16 --style raw --s 140 --sref CODE | still |
| Loop/CTA | 38–45s | 1 (reused) | Reuse Hook still #1 — same phone/app-glyph shot. shorts-assembly composites the "SOLD"/price-tag graphic (a plain red tag shape, no legible text) fully visible over the app glyph to close the visual loop against the mirrored VO line. | — | still (composited, no new generation needed) |

Notes on text-bearing beats (flagged per the no-text rule, not baked into any MJ prompt above):
- Setup's "2,300 years ago" date stamp and the two-kinds-of-money split diagram are simple
  on-screen graphic/motion-text overlays for shorts-assembly to add over Still #2 — not a
  separate MJ generation.
- Payoff's spoken checklist ("apps & platforms count too" / "forced sellback" / "fee refunds")
  is on-screen motion text over Stills #6–7, per the script's own flag that this beat carries a
  spoken list.
- Loop/CTA's "SOLD"/price-tag reveal reuses Hook Still #1 with a graphic overlay, not a new
  generation, since the transformation is simple (a tag appearing) rather than continuous
  action.
