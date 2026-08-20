# Worked example

> **`[T]` facts in this file were web-verified 2026-07-23** against live ElevenLabs documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

> This example illustrates rules already marked in this skill's other reference files and carries no independent normative weight. Where a line here restates a rule, the marker lives
> on the rule, not on the illustration — do not copy an unmarked line out of this file into a
> real brief as if it were sourced `[I]`.

## Input: shot-ready script excerpt (from `shorts-scripting`)

```
TOPIC: Why you procrastinate (45s Short)

[00:00–00:03] HOOK — on-screen text: "You're not lazy."
VO: You're not lazy. You're scared of failing in front of people who don't even care.

[00:03–00:08] SHOT 2 — talking-head style overlay
VO: Procrastination isn't a time problem. It's an emotion problem.

[00:08–00:20] SHOT 3 — b-roll montage, clock/desk
VO: Every time you delay a task, your brain is avoiding a feeling — boredom, doubt,
overwhelm. Not the task itself.

[00:20–00:35] SHOT 4 — on-screen text callouts
VO: So instead of forcing focus, ask what feeling you're actually avoiding. Name it. That
alone cuts the urge to scroll.

[00:35–00:45] CTA
VO: Try it on your next task. Comment the feeling you found below.
```

## Output: voiceover production brief

### Voice pick

**Cloned own voice** (Instant Voice Cloning, Starter tier or above) `[C]` `[T]`. This is the corpus's
top-preference fix for the strongest signal in the topic: default/popular library voices risk
reach or shadowban because they already blanket hundreds of thousands of videos
`(One Person Business, 84bavOadYCI)` `(Make Money Matt, TvJhpOxFRsE)`. A cloned own-voice is
100% unique, and it also matters for disclosure: ElevenLabs' SynthID watermark means any
library voice or non-own clone needs YouTube's altered-content disclosure, but cloning your
OWN voice is the current exception that needs none `[C] (Romayroh, G9LfE3k-IEI;
Romayroh, OrPYWlXMQws)` — see `production-and-loudness.md`'s AI disclosure note. This script
uses an own-voice clone, so no disclosure is needed here. Lock this voice channel-wide going
forward — don't re-pick per video `[T]`.

*If a clone isn't set up yet:* fall back to a lesser-used library voice, never a default preset
`(Make Money Matt, TvJhpOxFRsE)`.

### Tone per beat

| Beat | Timestamp range (s) | Tone | Delivery intent |
|---|---|---|---|
| Hook | 0–3 | Excited, confrontational | Land "you're not lazy" as a corrective jolt — the viewer braces for the usual guilt-trip opener and gets the opposite in the first clause; low stability/high style so the reversal actually lands with energy `[I]`. |
| Shot 2 | 3–8 | Even, matter-of-fact | State "it's an emotion problem" as settled fact, not a hot take — high stability, low style keeps the reframe sounding assured rather than argued `[I]`. |
| Shot 3 | 8–20 | Reflective, narrative | Walk the boredom/doubt/overwhelm list at an unhurried pace so it reads as recognition, not a lecture — storytelling preset, a little more style than Shot 2 to carry the small emotional beat `[I]`. |
| Shot 4 | 20–35 | Instructive, calm | Guide the "ask what feeling you're avoiding, name it" technique like a doable next step, not another task on the pile — narration preset again, slightly slower speed to let the instruction breathe `[I]`. |
| CTA | 35–45 | Sincere, warm | Close on a genuine invitation to comment, not a hard sell — Marketing/Shorts preset for a touch of lift, but the `[sincere]` tag (used below) is the load-bearing cue, not the settings `[I]`. |

Tone assignments track the Settings table below one-for-one: low stability/high style rows (Hook,
CTA) get the more excited/warm tones, high-stability/low-style rows (Shot 2, Shot 4) get the
even/instructive tones — consistent with the model/settings choices, not an independent call.

### Model

**Eleven v3** `[T]` — the hook and CTA both benefit from the audio-tag emotion system, and this
is a short, single-take-per-section Short rather than a long consistency-first narration.

### Settings — per section (mixed script; see `settings-by-content-type.md`)

| Section | Content type | Stability | Similarity | Style | Speed | Speaker boost |
|---|---|---|---|---|---|---|
| Hook (00:00–00:03) | Marketing/Shorts | 55% | 80% | 55% | 1.15× | ON |
| Shot 2 (00:03–00:08) | Narration | 70% | 80% | 20% | 1.0× | ON |
| Shot 3 (00:08–00:20) | Storytelling | 50% | 80% | 35% | 1.0× | ON |
| Shot 4 (00:20–00:35) | Narration | 70% | 80% | 20% | 0.95× | ON |
| CTA (00:35–00:45) | Marketing/Shorts | 55% | 80% | 50% | 1.1× | ON |

All values pulled from the content-type preset table `[T]`; the hook/CTA-as-Marketing-preset
split is this skill's extrapolation for mixed scripts, not a corpus-stated blend rule — see the
"Mixed scripts" note in `settings-by-content-type.md` `[I]`.

### Script, reformatted for TTS

```
[excited] You're not lazy. You're scared of failing… in front of people who don't even care.

Procrastination isn't a time problem. It's an emotion problem.

Every time you delay a task, your brain is avoiding a feeling — boredom, doubt, overwhelm.
Not the task itself.

So instead of forcing focus: ask what feeling you're actually avoiding. Name it. That alone
cuts the urge to scroll.

[sincere] Try it on your next task. Comment the feeling you found below.
```

Notes on the changes made, each traceable to a rule above:
- Split "You're scared of failing in front of people who don't even care" with an ellipsis to
  place a breath before the twist, and tagged `[excited]` on the hook per the v3 emotion-tag
  rule `[T]` — flag `[sincere]` as unverified against the current tag vocabulary; confirm it
  exists before relying on it, since only `[excited]/[whispers]/[sighs]/[laughs]/[sarcastic]`
  are corpus/guide-confirmed.
- Added a colon before "ask what feeling…" as a pacing beat, not a grammar fix `[T]`.
- No phonetic respellings needed — no brand names/acronyms in this script.
- Each bracketed block above is one TTS generation unit (5 sections) so a bad take on the CTA
  can be re-rolled without regenerating the hook `[T]`.

### Production & loudness

- Normalize the final voice track to **−14 LUFS** `[T]`.
- Duck the music bed to **−21 to −22 dB under the voice** (corpus practitioner number, leads
  over the −12 to −18 dB docs range for this Shorts context — see
  `production-and-loudness.md`) `(Romayroh, Wox4Jt_2t6w)`.
- Match music tone to the "you're not lazy, you're scared" reveal in the hook — an anxious-to-
  resolving cue works better here than a purely upbeat bed; no music beats mismatched music
  `(Kallaway, i7upRL4H1FM)`.
- Consider 2–3 takes of the hook and CTA specifically before locking `(Nick Nimmin, IF-PD6XMjYY)`.

### Downstream

This brief, plus `visual-prompts`'s prompt sheet for the same script, is the input to
`shorts-assembly`.
