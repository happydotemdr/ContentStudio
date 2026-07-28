=== VISUAL PROMPT SHEET — NFL Stat Kills the 'Specialize Early' Advice ===

WHOLE-SHORT SETUP
  Aspect ratio:     --ar 9:16
  Style/params:     --style raw --s 160 --c 5 while drafting variants; drop to --c 0 once a
                     winning grid image is picked per beat.
  Consistency:      No recurring named host or figure across this Short → generate Hook still
                     #1 first with no --sref, then extract its style code and apply --sref CODE
                     to every later prompt below (bootstrap step, per
                     `references/midjourney-craft.md`'s consistency decision).
  Notes:            Every prompt ends "No Text." — the diverging-path fork, the empty gear peg,
                     and every other visual cue are plain physical objects, never legible words;
                     spoken stats/claims (Setup's date, the re-hook's medical-consensus line,
                     Payoff's athlete count) are shorts-assembly on-screen motion-text overlays,
                     composited after generation, not baked into any MJ prompt.

COVER / THUMBNAIL
  Dedicated MJ prompt, per the concept brief's packaging direction (distinct from any per-beat
  still — the thumbnail needs the "human cost" image the script itself never shows):
  "Photorealistic action shot, a kid mid-cannonball jump into a backyard pool on an ordinary
  weekday afternoon, one piece of sports practice gear — a cleat and a shin guard — resting
  abandoned on the pool deck in the foreground, water splashing up around the jump, bright
  natural daylight, warm sunlit color palette, one dominant mood of joyful freedom with a touch
  of wistfulness. Photorealistic, DSLR, muted colors, shot on 35mm film. No Text." --ar 9:16
  --style raw --s 160 --sref CODE

PER-BEAT PROMPTS
| Beat | Dur | Still # | Midjourney prompt | Params | Motion |
|---|---|---|---|---|---|
| Hook | 0–3s | 1 | Photorealistic split composition, one side showing a child's uniform and gear from three different sports layered and overlapping in sharp focus, the other side showing a single uniform lit brightly with everything else in soft blur, close-to-medium shot, clean lighting with one side warmer and fuller than the other, muted neutral color palette, contemplative mood. No Text. | --ar 9:16 --style raw --s 160 (no --sref — this is the bootstrap still) | --motion low (slow ~5% push-in, signals "something's coming") |
| Setup | 3–8s | 2 | Photorealistic wide shot, a young child playing freely and unstructured in a backyard with no equipment or coach in view, running through a sprinkler, golden late-afternoon light, warm nostalgic color palette, joyful unguarded mood. No Text. | --ar 9:16 --style raw --s 160 --sref CODE | still |
| Build/Value | 8–15s | 3 | Photorealistic medium shot, a garage mudroom wall with pegs holding gear from three different sports, one central peg now empty with its equipment packed into a cardboard box on the floor beside it, soft overhead light, muted cool color palette, quiet decisive mood. No Text. | --ar 9:16 --style raw --s 160 --sref CODE | still |
| Re-hook @ ~15s | 15–22s | 4 | Photorealistic medium shot, an athletic trainer's hands taping a young athlete's ankle on an exam table in a plain clinical room, no visible signage or logos, soft even overhead light, muted cool-gray color palette, calm clinical mood. No Text. | --ar 9:16 --style raw --s 140 --sref CODE | still |
| Re-hook (cont.) | 22–28s | 5 | Photorealistic medium shot, a young athlete sitting alone on a bench at the edge of a field, head down, gear beside them unused, soft overcast light, muted desaturated color palette, quiet exhausted mood. No Text. | --ar 9:16 --style raw --s 140 --sref CODE | still |
| Payoff | 28–33s | 6 | Photorealistic wide shot, two dirt trails diverging in an open field, one trail well-worn and busy-looking, the other narrower and quieter, a single weathered wooden signpost at the fork with no readable text, warm late-morning light, muted natural color palette, contemplative mood. No Text. | --ar 9:16 --style raw --s 150 --sref CODE | still |
| Payoff (cont.) | 33–38s | 7 | Photorealistic close-up, the same weathered wooden signpost at the fork in the trail, grain and texture visible, soft directional light, muted natural color palette, quiet mood. No Text. | --ar 9:16 --style raw --s 150 --sref CODE | still |
| Loop/CTA | 38–45s | 1 (reused) | Reuse Hook still #1 — same split-composition shot. shorts-assembly composites the single-uniform side as now visibly smaller/more isolated relative to the layered three-sport side, closing the visual loop against the mirrored VO line. | — | still (composited, no new generation needed) |

I2V PROMPTS
None needed for this Short. Every beat is either a static tableau (Setup, Build, re-hook,
Payoff) or a single hero-still breathing via `--motion low` (Hook only) — no beat's VO
describes continuous action, a camera move, or a transformation a static image can't sell, so
no beat clears the third tier in `references/image-to-video.md`'s decision table. Stating this
explicitly per the workflow's requirement not to leave the video-tier decision implicit.

Notes on text-bearing beats (flagged per the no-text rule, not baked into any MJ prompt above):
- Setup's "over 260 years ago, Rousseau" detail is a spoken date/name — a simple on-screen
  date-stamp graphic over Still #2 for shorts-assembly to add, paraphrase text only, no quote
  card, per Rousseau's paraphrase-caution flag carried from the script's Delivery notes.
- The re-hook's medical-consensus line ("no evidence early specializing is needed for elite
  success — just extra injury and burnout risk") is a spoken claim — render as on-screen motion
  text over Stills #4–5, per the pacing rule that spoken stats/claims need on-screen graphic
  treatment, not just narration.
- Payoff's "six thousand athletes... junior vs senior" finding is a spoken statistic — flagged
  for on-screen motion-text/graphic treatment over Stills #6–7 (e.g. a simple diverging-line
  graphic labeled "junior" / "world-class senior" overlaid on the fork-in-the-trail image), not
  a separate MJ generation.
