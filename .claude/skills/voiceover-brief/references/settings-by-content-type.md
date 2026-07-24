# The four settings, by content type

Distilled from `docs/elevenlabs-voiceover-guide.md` §3 and §8 (cheat-sheet). All `[T]`
web-verified, dated 2026-07-23 — re-verify against elevenlabs.io/docs before relying on exact
numbers, since ElevenLabs tunes these ranges over time.

## What each slider controls `[T]`

| Setting | What it controls | Best-practice range | Notes |
|---|---|---|---|
| **Stability** | Consistency vs. natural variation | Default ~50% | Technical/corporate 65–75% (clarity, avoid robotic flatness); storytelling/character 40–55% (emotional arcs). Too low = unstable; too high = monotone. |
| **Similarity / Clarity boost** | How closely output tracks the source voice | 75–90% (~75 default) | **Never push to 100%** — produces over-enunciated "news anchor" artifacts. |
| **Style exaggeration** | Expressiveness / drama | Narration 10–50% (0 default) | Higher = more drama but **slower generation**. |
| **Speed** | Pace | Natural 0.9–1.1× | Marketing/energetic 1.1–1.3×; slow down for complex topics. |
| **Speaker boost** | Tightens similarity to the source voice | ON for most VO | Leave on unless it introduces artifacts. |

## Preset table by content type `[T]`

Classify the script's dominant mode first (a single Short can mix modes across beats — see
"Mixed scripts" below), then apply:

| Content type | Stability | Similarity/Clarity | Style | Speed | Speaker boost |
|---|---|---|---|---|---|
| **Narration / technical** | 65–75% | 75–90% | 10–30% | 0.9–1.0× | ON |
| **Storytelling / character** | 40–55% | 75–90% | 30–50% | 0.95–1.1× | ON |
| **Marketing / Shorts** | 50–70% | 75–90% | 40–60% | 1.1–1.3× | ON |

**Reading the table:** technical content wants stability high, style low, speed slightly under
1× — clear and unhurried. Storytelling drops stability so the voice can rise and fall with the
arc. Shorts push speed and style up because the hook is competing for attention in the first
second and pacing is a weapon.

**Default assumption for this skill `[I]`:** most faceless-Shorts scripts (hook → value → CTA)
sit closest to the **Marketing/Shorts** preset, since even an educational Short is fighting for
a scroll-stop in the first second. Downshift toward Narration/technical for a dense,
information-heavy explainer beat, or toward Storytelling for an emotional/narrative arc. This
is this skill's inference from the preset table, not a corpus- or guide-stated default.

## Mixed scripts (hook vs. body vs. CTA)

The corpus and the settings guide don't give a single "blend" number for a script that shifts
mode mid-Short — this is a gap, not a rule, so say so rather than inventing a blended value
`[I]`. The defensible move, extrapolating directly from the preset table `[T]`: treat the hook
and CTA as Marketing/Shorts-preset beats (speed up, style up — they're doing the attention and
conversion work) and the body as whichever of Narration or Storytelling matches its content,
generating each beat as its own section (see `scripting-for-tts.md`) so each can carry its own
settings and be re-rolled independently.

## Quick-reference (push up / push down) `[T]`

| Lever | Safe default | Push up when… | Push down when… |
|---|---|---|---|
| Stability | 50% | Technical/clarity (→75%) | Emotional storytelling (→40%) |
| Similarity/Clarity | 75% | Voice drifts from source (→90%) | Over-enunciated (never >90%) |
| Style | 10–20% | Shorts/marketing energy (→60%) | Clean narration (→0–10%) |
| Speed | 1.0× | Shorts/energy (→1.3×) | Complex topics (→0.9×) |
| Speaker boost | ON | — | Only if it adds artifacts |

## Artifacts to watch for `[T]`

Keep clarity/similarity at or below ~90%, don't over-crank style, and listen for the
"news-anchor" over-enunciation and metallic edges that come from maxed sliders. If a setting
combination produces artifacts, back it off rather than pushing further — there's no reward for
the extreme end of any of these ranges.
