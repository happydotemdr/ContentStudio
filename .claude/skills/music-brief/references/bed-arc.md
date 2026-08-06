# Bed arc design

The `[C]` findings behind this skill, translated into arc-design rules. This file owns the bed's
**emotional shape over time** — which movement plays under which beat range, when the bed holds
out or drops out, and where a pause is a deliberate device. It does **not** own duck depth or the
loudness target — those already live in
`.claude/skills/voiceover-brief/references/production-and-loudness.md` and are not restated here.

## Match tone, never contradict

**No music beats the wrong music** — don't add a bed just to fill silence if nothing matches the
beat's tone `[C] (Kallaway, i7upRL4H1FM)`. This is the single strongest finding behind this skill,
and it is the reason the `music` stage is **not** a hard dependency of `assembly` — a no-bed Short
is a legitimate outcome of this skill, not a failure to produce one.

## Low-energy bed; emotion comes from events, not from the bed's own volume

Keep the bed itself low-energy and let discrete events carry the emotional lift: risers into a
reveal, a hit on the release, a low drone under a mysterious beat `[C] (vidIQ, DiZnbihU4NM)`. The
arc's job is to set a floor of feeling, not to compete with the voiceover or the visuals for
attention.

## Pausing the music before the big line

Pausing the music before the big line changes how the moment lands `[C] (vidIQ, DiZnbihU4NM)`.
Treat this as a first-class arc device with an explicit timestamp in the bed arc table — not an
afterthought or a generic "duck a bit more here" note.

## Why the arc must stay low-energy (rationale only — the number stays with voiceover-brief)

Loud music is the most-underestimated AVD (average view duration) killer
`[C] (Romayroh, Wox4Jt_2t6w)` `[C] (Roberto Blake, iaTavrWIGDM)`. That finding is cited here
**only** as the reason the arc must stay low-energy throughout — it is not this skill's decision
to make about depth. **The duck depth number itself (−21 to −22 dB) and the −14 LUFS mix target
belong to `voiceover-brief`; do not restate them here.**

## Length-matching is moot for a generated bed

`[I]` The corpus's rule for a licensed or library track is to length-match it with a Remix-style
tool and **never rate-stretch, which alters pitch** `[C] (Roberto Blake, iaTavrWIGDM)`. That rule
is inherited into this skill's territory but does not bind it: a bed composed to the script's own
beat durations from the start has nothing to remix and nothing to stretch — there is no
pre-existing track being fitted to a timeline. State this explicitly as the reason the rule is
acknowledged but does not apply, rather than silently dropping it.

## The three-movement worked precedent

`[I]` — from `rgs-briefs/2026-07-28-nobody-asked-the-kid-assembly.md` §9, the shape a new arc is
built against:

- **0–3s: bed out entirely.** `[I]` The hook's differentiator line carries alone, nothing
  competing for it.
- **~3.0s: fade in over ~300ms.** `[I]` Warm and light.
- **Narrowing to quiet gravity** `[I]` under the re-hook and the 17–26s quote card.
- **Opening to relief from 38s** `[I]` through the Loop/CTA.

Note that source brief's own rule that the bed tracks the **emotional** arc, not the visual
register — a bed scored to visual cuts (register changes, shot changes) turns a narrative device
into a cutaway segment `[C] (Kallaway, i7upRL4H1FM)`. Movement boundaries are set by where the
*feeling* changes, not by where the picture changes.

## Gaps to flag honestly

`[I]` The corpus has **zero findings on AI music generation**, and no finding at all on BPM, key,
genre, or instrumentation for a Shorts bed. Where a user asks for any of these, say the gap exists
and hand the question to `elevenlabs-music`, which is vendor-grounded — do not invent a
confident-sounding tempo, key, or genre to fill the silence.
