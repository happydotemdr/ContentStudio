# Loudness & mix

Provenance markers as in `pacing-and-editing.md`. Primary source: `docs/headless-shorts-production-playbook.md` §5; cross-checked against `docs/headless-youtube-audit.md` §5 (Voiceover & audio).

## The chain

**Script → TTS voice → pacing → music bed + ducking → mix/loudness.**

## Ducking (the single most important mix rule)

- **Duck the music under the voice to about −22 dB** (or one-click auto-ducking) so it never overpowers the VO `[C] (Roberto Blake, iaTavrWIGDM)`.
- Audit corroborates with a slightly wider band: **keep background music around −21 to −22 dB, ducked under vocals** — loud music is one of the most common, most underestimated AVD killers `[C] (Romayroh, Wox4Jt_2t6w)`. In Premiere, the Essential Sound panel gives one-click auto-ducking around −22 dB; match music length with the Remix tool, not rate-stretch (rate-stretch alters pitch) `[C] (Roberto Blake, iaTavrWIGDM)`.
- **Never use music whose emotional tone contradicts the words** — no music beats wrong music `[C] (Kallaway, i7upRL4H1FM)`.
- **Give on-screen visuals matching sounds; use risers, hits, and drones to convey emotion**; pausing the music before the key line changes the whole feel `[C] (vidIQ, DiZnbihU4NM)`.

## Loudness targets `[I]`

- **Voice peaks around −3 to −6 dB; overall loudness target ≈ −14 LUFS** (YouTube normalizes toward this).
- **Music bed sits ~15–20 dB below the voice** — this is the same instruction as the −22 dB duck above, restated as a relative level.
- **SFX** (whoosh on cuts, subtle hits on text-card reveals) at a level that punctuates without startling.
- **Check the final mix on phone speakers, not headphones** — that's how it will actually be watched `[I]`.

## Voice pacing (feeds from the voiceover brief, re-stated for the edit)

- **150–170 wpm** natural narration; up to ~180 for high-energy niches, slower for teaching content. **Match editing pace to the audience** — fast for younger viewers, slower for older/learning viewers `[C] (Nick Nimmin, LAzYEKltBwA)`.
- Insert short pauses after the hook and before the payoff for comprehension; trim dead air ruthlessly — **constant forward motion, no dead air** `[C] (Jenny Hoyos, oVKBAMEqsPI)`.
- **Prioritize audio over video** — viewers tolerate weak footage but not bad, echoey audio; this is one of the biggest YouTube turn-offs `[C] (Dan the creator, 9JE8-wM8zKc)`. `[I]` Applying this to an all-AI-asset pipeline (the corpus's finding is about mic quality, not budget allocation): don't let visual polish absorb the time budget at the expense of a clean mix.

## Rights note carried into the mix

Music rights are cleared upstream (voiceover-brief / asset stage), but the assembly stage is the last checkpoint before the track is baked into the final export: **use YouTube's free Creator Music library, a royalty-free source, or a license service (e.g. Lickd) for a recognizable track — Creator Music can mean revenue-share/no-monetization, unlike a direct license** `[C] (Roberto Blake, SJsGBKGy4Do)`. Confirm this is settled before the final render, not after.
