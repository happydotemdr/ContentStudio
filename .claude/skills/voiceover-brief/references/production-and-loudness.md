# Production, mixing & loudness

Distilled from `docs/elevenlabs-voiceover-guide.md` §5 and §8, cross-checked against
`docs/headless-youtube-audit.md` §5. `[T]` facts below (LUFS target, ducking-dB norms,
disclosure policy) are web-verified as of **2026-07-23** — re-verify against
elevenlabs.io/docs and YouTube's current policy pages before relying on them, since loudness
norms and disclosure rules can change. This is where the corpus is most emphatic: the mix is
where most faceless channels quietly lose retention, more than the script or the edit does
`(Romayroh, Wox4Jt_2t6w)` `(Dan the creator, 9JE8-wM8zKc)`.

## Loudness target

**Normalize the voice track to −14 LUFS `[T]`.** That is YouTube's loudness target — leave
headroom and avoid clipping. If the source audio came from a weak mic (relevant for the
voice-changer or B-roll-patching workflows in `voice-selection.md`), **normalize the detached
audio track first** to remove peaks and even out volume before final loudness normalization
`(Make Money Matt, LlIkMWX50aQ)`.

## Ducking the music bed

- **Docs/notes target −12 to −18 dB under the voice `[T]`.** The settings guide's cheat-sheet
  gives −16 dB as a safe default starting point.
- **Corpus creators run noticeably lower — around −21 to −22 dB** `[C]` — and call loud music the
  **most common cause of low average view duration (AVD)** that beginners underestimate
  `(Romayroh, Wox4Jt_2t6w)` `(Roberto Blake, iaTavrWIGDM)`.
- Where the notes and the corpus disagree on exact depth, give both in the brief rather than
  picking one silently — the corpus's practitioner number (−21 to −22 dB) is the one to lead
  with for a faceless-Shorts brief, since it's the number tied directly to an AVD complaint,
  not just a general audio-mixing guideline.
- Use one-click auto-ducking (e.g., Premiere's Essential Sound panel) so music restores
  automatically when no voice is present, rather than hand-riding the fader
  `(Roberto Blake, iaTavrWIGDM)`.
- **When in doubt, music too quiet beats music too loud `[I]`** — there is no corpus report of
  a video failing because the music was too quiet, only ones failing because it was too loud.
  This is this skill's inference from that asymmetry, not a directly corpus-stated rule.

## Matching music to the script

Music drives the emotional state that triggers shares; a track that clashes with the words
confuses the viewer. **No music beats the wrong music** — don't add a bed just to fill silence
if nothing matches the beat's tone `(Kallaway, i7upRL4H1FM)`.

## Consistency across videos

Lock **one voice + one settings preset + one loudness target**, and reuse them channel-wide
`[T]`. Consistency here is part of the brand, the same way a recurring voice is (see
`voice-selection.md`) — don't re-tune settings per video without a content-type reason.

## Re-rolling and takes

Section-level generation (see `scripting-for-tts.md`) makes re-rolling a bad read nearly free —
regenerate one line, not the whole track `[T]`. For the highest-leverage lines — the hook and
the CTA — consider generating 2–3 takes and picking the best, exactly as human narrators
record each line multiple times for edit-room options `(Nick Nimmin, IF-PD6XMjYY)`.

## Sound design (optional lift) `[I]`

Beyond the voice and music bed, small sound-design touches can lift an otherwise flat VO:
risers into a reveal, a hit on the release, a low drone under a mysterious beat, and small
whooshes/ticks matched to on-screen motion. Pausing the music right before the big line is
called out specifically as changing how the moment lands `(vidIQ, DiZnbihU4NM)`. This is
general production craft rather than an ElevenLabs-specific setting — flag it as an optional
polish pass, not a required step of the voiceover brief itself.

## AI disclosure note (scope boundary)

AI voiceover alone does not require YouTube's synthetic-content disclosure and is not
disqualifying for monetization `[T]`. **This is not a blanket exemption for ElevenLabs
specifically, though: ElevenLabs now embeds an unremovable SynthID watermark (since May
2026) — disclose AI voiceover via YouTube's altered-content box, or risk demonetization/YPP
rejection, for any library voice or any cloned voice that isn't your own**
`[C] (Romayroh, G9LfE3k-IEI)`. **Cloning your OWN voice is the current exception that needs no
disclosure** `(Romayroh, OrPYWlXMQws)` — see `voice-selection.md` for why an own-voice clone is
already this skill's top pick on separate reach/uniqueness grounds. Full disclosure/rights
compliance is otherwise out of scope for this skill — flag it in the brief as a pointer to the
launch game plan's rights gate rather than re-deriving it here.
