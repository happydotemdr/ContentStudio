# Voice selection & cloning

Distilled from `docs/elevenlabs-voiceover-guide.md` §2 and `docs/headless-youtube-audit.md` §5.
Markers: `[C]` corpus-cited `(Channel, video_id)` · `[I]` industry practice · `[T]` web-verified
tool/policy fact, dated 2026-07-23 — re-verify before relying on it.

## The one rule

**Pick ONE voice and keep it consistent across every video on the channel.** That voice *is*
the channel's identity `[T]` `[I]`. Switching voices between uploads reads as a different
creator and breaks the consistency the algorithm and audience both reward.

## Do NOT use a default/popular library voice

This is the strongest, most corpus-supported signal on the whole topic — call it out plainly
in every brief. ElevenLabs ships **10,000+ library voices** `[T]`, but the handful of
most-common preset voices already appear on hundreds of thousands of videos. Creators report
YouTube can detect the repeat and treat a new channel as **another copy of the same voice —
risking limited reach or shadowban** `(One Person Business, 84bavOadYCI)` `(Make Money Matt, TvJhpOxFRsE)`.

Fixes, in the corpus's rough order of preference:

1. **Clone your own voice.** 100% unique, and — per one creator — a cloned-*own* voice
   currently does not trigger YouTube's altered-content/AI disclosure `(Romayroh, OrPYWlXMQws)`.
   Requires the Starter tier or above for Instant Voice Cloning `[T]` (the source guide's
   own pricing table names Starter, ~$6/mo, as the tier that unlocks it; a separate line in
   the same guide says "Creator+" — flagged here as a source inconsistency, not resolved by
   this skill; re-verify at elevenlabs.io/pricing before relying on either).
2. **Record your own voice** instead of TTS entirely. Even a cheap mic and an accent reads as
   *original* against a sea of polished AI voices, and it's free `(One Person Business, 6s2T2NlWDhQ)`.
   Audio quality matters more than video quality for retention, so a sub-$50 mic is the
   highest-leverage purchase in the whole stack `(Dan the creator, 9JE8-wM8zKc)`.
3. **If you must use a library voice, pick a lesser-used one** — avoid the obvious defaults
   `(Make Money Matt, TvJhpOxFRsE)`. One creator argues higher-tier "pro" (double-credit) voices
   are less likely to be flagged — framed explicitly as a **low-confidence theory, not confirmed
   policy** `(Romayroh, e5AvJAbxWW8)`.

## The voice-changer middle path

You don't have to choose pure TTS *or* pure human recording. ElevenLabs' **voice-changer**
lets you read the script yourself and convert the read — keeping your human pauses, breaths,
and cadence while cleaning up the sound `(Romayroh, KbUXzJ55eJk)`. A cloned voice is also good
for **patching narration errors over B-roll** without a re-record: type the corrected line and
generate it — short lines work well, long blocks less so, and speed is adjustable to match the
surrounding cadence `(Nick Nimmin, usll4p9ziRw)`.

## Cloning paths (reference) `[T]`

| Path | What it is | When to use |
|---|---|---|
| Library voice | Pick a pre-made voice | Fastest start — but see the warning above |
| Instant Voice Cloning | Clone from a short sample (Starter tier or above — see the source-inconsistency note above) | Your own voice, no big recording session |
| Professional Voice Cloning | Clone from a long, high-quality dataset | Highest fidelity; channel voice as a long-term asset |
| Voice Design | Generate a voice from a text description | A distinctive voice no one else has |

## Model choice by script type `[T]`

| Model | Strengths | Best for |
|---|---|---|
| **Eleven v3** | Most expressive; audio-tag system (`[excited]`, `[whispers]`, `[sighs]`); Text-to-Dialogue (multi-speaker) | Narrative/emotional VO; Shorts hooks that need punch |
| **Multilingual v2** | Stable, consistent across long runs | Long-form narration where consistency beats drama |
| **Flash / Turbo v2.5** | Low-latency, cheapest (~$0.05/1k chars) | High-volume batch generation, draft passes before a final v3 render |

Default recommendation for a Shorts voiceover brief: **Eleven v3**, since Shorts hooks and
punchy delivery are exactly where the audio-tag system earns its keep — drop to Flash/Turbo
only for draft/cost-constrained passes. `[I]` (this is this skill's extrapolation from the
model table above, not a corpus- or guide-stated rule).

## Budget alternatives, if ElevenLabs cost is a blocker `[T]`

Murf (~$0.01/min via the Falcon API), Fish Audio (long-form), and the open-source/local
Chatterbox model (free, reportedly beat ElevenLabs in a blind test) are corpus-noted
alternatives. This skill's settings guidance is ElevenLabs-specific; treat these as a fallback
note, not a replacement workflow.

## Cost framing `[T]` `[C]`

ElevenLabs voiceover runs roughly **$1–2 per video** versus **~$25 for a human voice artist**
`(Make Money Matt, TvJhpOxFRsE)`. The Creator tier (~$22/mo, ~100k characters, commercial
license required for monetized YouTube) is the tier almost every faceless creator needs —
Instant Voice Cloning itself may unlock a tier lower (Starter, ~$6/mo) per the source guide's
pricing table, though a separate line in that guide says "Creator+" (unresolved source
inconsistency, see above). Verify current pricing at elevenlabs.io/pricing before relying on
either, since plans and character allotments change.
