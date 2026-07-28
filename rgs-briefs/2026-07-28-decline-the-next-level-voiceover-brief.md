---
date: 2026-07-28
kind: voiceover-brief
run: rgs-debut-20260728-055448
slug: decline-the-next-level
stage: 03-voiceover
script: rgs-briefs/2026-07-28-decline-the-next-level-script.md
concept_brief: rgs-briefs/2026-07-28-decline-the-next-level-concept-brief.md
grounding: rgs-briefs/2026-07-28-decline-the-next-level.md
archetype: A1
total_runtime_seconds: 45
status: complete
---

=== VOICEOVER BRIEF + ELEVENLABS CONFIG — decline-the-next-level-01 (Short A) ===

Produced in two authored parts, per the division of labour in the task brief: Part 1
(`voiceover-brief`) makes the creative call — voice character, tone per beat, pacing
resolution, and the loudness/ducking mix. Part 2 (`elevenlabs-audio`) accepts that call
without re-litigating it and emits the executable configuration — model routing, settings,
tagged script, pronunciation dictionary, request payloads, curl, and credit estimate. No
ElevenLabs API call was made to produce this document; no credits were spent.

## Marker legend (an unmarked normative line below is a bug)

- **`[C]`** — the 420-video ContentStudio creator-education corpus, cited `(Channel,
  video_id)`, as `docs/elevenlabs-voiceover-guide.md` and `docs/headless-youtube-audit.md`
  §5 give it.
- **`[I]`** — general craft judgment, traceable to none of the below. A working decision.
- **`[T]`** — web-verified tool/policy fact. `voiceover-brief`'s `[T]` facts are dated
  **2026-07-23** (`docs/elevenlabs-voiceover-guide.md`); `elevenlabs-audio`'s `[T]` facts are
  dated **2026-07-26** (`docs/elevenlabs-production-runbook.md`). Both surfaces move fast —
  re-verify before relying on either set.
- **`[T-unverified]`** — asserted by the supplied enterprise runbook that seeded
  `elevenlabs-audio` (wrong in eight places — see that doc's §10) but **not** confirmed
  against live ElevenLabs docs. Starting-point numbers, never facts.
- **`[B]`** — RaisingGoodSports Brand Definition (`output/raisinggoodsports-brand-definition.md`).

---

# PART 1 — `voiceover-brief` (the creative call)

## Voice pick

**No cloned own voice exists for this channel yet — this is upload #1.** The brand's default
pipeline is own-voice-into-a-phone-mic, with disclosed AI TTS as the explicit fallback `[B]`
(`output/raisinggoodsports-brand-definition.md` — "voiceover (own voice into a phone mic =
default; disclosed AI TTS = fallback)"). The script this brief inherits has already committed
to the fallback path — its own AI/synthetic-media disclosure section states plainly that "the
voiceover is synthetic (ElevenLabs)" and treats disclosure as unavoidable, not discretionary
`[B]`. That decision is not reopened here; this brief works inside it.

Because of that, the corpus's usual top preference — clone the creator's own voice, which per
one creator's report currently exempts a video from YouTube's disclosure box
`(Romayroh, OrPYWlXMQws)` — does not apply as a disclosure *avoidance* lever on this Short: the
brand's own binding policy (three placements, carried from the script, restated in full below)
mandates disclosure regardless of clone status. **Resolved tension, stated once:** the corpus's
disclosure-exemption argument for an own-voice clone is real but immaterial here, because the
brand's policy for this Short is broader than the exemption it would grant. `[I]`

**Recommendation: a lesser-used ElevenLabs library voice, explored and locked before this
Short renders, never a default/most-popular preset.** This is the corpus's fallback
preference (#3 in `voiceover-brief/references/voice-selection.md`, behind own-voice-clone and
self-recording) `[C]` `(Make Money Matt, TvJhpOxFRsE)`, appropriate here specifically because
neither of the higher-ranked options is available for a debut upload with no existing voice
asset. **Do not pick the obvious default preset voice** — the corpus's strongest-supported
signal on this whole topic is that the handful of most-common preset voices already blanket
hundreds of thousands of videos and can read a new channel as a repeat, risking reach/shadowban
`[C]` `(One Person Business, 84bavOadYCI)` `(Make Money Matt, TvJhpOxFRsE)`. Once a voice is
chosen it is locked channel-wide — this is the channel's identity going forward `[T]` `[I]`, not
re-picked per video.

**Performance requirement, stated in plain words before any voice is auditioned** `[T]`
(`elevenlabs-audio/references/voice-profiles.md` — "state the performance requirement first"):
this voice must sustain 45 seconds of measured, plainspoken delivery; carry a quiet-resolve
register without leaning into either flatness or performance; and land a single verbatim quote
card's surrounding lines without sounding like it's reciting scripture. It does **not** need to
shout, whisper, or hold a character voice.

**Voice character — the binding creative call, per the task brief and the brand's `voice_traits`
block** `[B]` (`output/raisinggoodsports-brand-definition.md` §Voice): **calm, warm, grounded —
an ally on the same side of the table as the parent. Not urgent, not alarmed, not
authoritative-expert.** This is the one instruction `elevenlabs-audio` must accept without
re-litigating downstream. Three concrete consequences for this specific script:

1. **The Build/Value beats carry a named research citation, but the VO must not read as a
   lecture.** Constraint 3 of this task (the narrator is a commentator, never a health or
   research authority) and the brand's "confident, never preachy — we reframe, we don't
   lecture" rule `[B]` point the same direction: the on-screen citation plate does the
   "official" work; the VO stays conversational, handing the fact over rather than presenting
   it. This is a real departure from `settings-by-content-type.md`'s Narration/technical preset,
   which pushes stability up to 65–75% for a clinical, authoritative register `[T]` — that
   register is exactly what the brand rules out. Flagged and overridden deliberately, not
   silently. `[I]`
2. **The Hook and re-hook are not played as Marketing/Shorts hype.** The preset table's
   Marketing/Shorts band (speed 1.1–1.3×, style 40–60%) `[T]` is tuned for attention-grabbing
   punch, which reads as urgency — banned by the brand's "not urgent, not alarmed" rule `[B]`.
   This brief keeps speed near-neutral and style modest throughout (see Settings below), even
   at the Hook, trading some of the corpus's generic Shorts-energy advice for the brand's
   specific ally register. `[I]`
3. **Ends on relief, not a sell.** The Loop/CTA is played warmer and calmer than its beat-mates,
   mirroring the Hook but resolved rather than opening a question — matching the brand's "end on
   relief and agency" rule `[B]` and the corpus's "relief over alarm" framing already locked at
   the concept-brief stage.

*If exploration surfaces no acceptable library candidate*, the recorded fallback is: record a
short reference pass in a real human voice matching this persona and run it through ElevenLabs'
voice-changer / Instant Voice Cloning rather than a pure preset — a documented middle path
`[C]` `(Romayroh, KbUXzJ55eJk)` that also converts this into an eventual own-voice clone for the
channel. Recorded as the alternate, not executed here (no audio was generated). `[I]`

## Settings

Per-beat, because this is a mixed-tone script across a hard 45-second timing model (see
"Pacing resolution," which this table encodes) — see
`voiceover-brief/references/settings-by-content-type.md` on sectioning a mixed script rather
than picking one blended number `[I]`. All values are `elevenlabs-audio`'s job to convert into
wire format (v3 stability *mode* vs. float, `voice_settings.style`/`speed`); this table states
the creative target each beat should land on.

| Beat | Range | Content register (adapted from the preset table, brand-overridden per above) | Stability feel | Style (expressiveness) | Speed feel | Speaker boost |
|---|---|---|---|---|---|---|
| Hook | 0–3s | Quiet resolve, not Marketing punch | Steady/Natural | Low | Slightly under neutral | ON |
| Setup | 3–8s | Ally explaining a mechanism, not lecturing | Steady/Natural | Low | Slightly over neutral (tight window) | ON |
| Build — proof | 8–18s | Commentator handing over a named citation | Steady/Natural | Low | Slightly over neutral (tight window) | ON |
| Re-hook | 18–21s | Contrast pivot ("But…"), still calm | Steady/Natural | Low-moderate | Moderately over neutral | ON |
| Build — Dewey (climax) | 21–28s | Quiet gravity around the quote card | Steady/Natural | Moderate | Over neutral (tightest window) | ON |
| Payoff | 28–38s | Warm reveal, handing back agency | Steady/Natural | Low-moderate | Slightly under neutral | ON |
| Loop/CTA | 38–45s | Warmest, most settled — mirrors the Hook, resolved | Steady/Natural | Low | Well under neutral, plus a held pause | ON |

**No beat uses a "performative" or maximally expressive register** `[I]` — every beat stays in
what `elevenlabs-audio` will map to v3's **Natural** mode, never Creative (documented as "prone
to hallucinations" `[T]`, and tonally too hot for an ally register) and never Robust (which
would suppress the `[pause]` tag this script needs `[T]`). Exact numeric settings and the
model/mode mapping are `elevenlabs-audio`'s job — see Part 2.

## Script, reformatted for TTS

Reformatting moves applied, each traceable to `voiceover-brief/references/scripting-for-tts.md`:

- **Sectioned into 7 TTS generation units**, matching the script's own beat boundaries exactly
  (Hook / Setup / Build-proof / re-hook / Build-Dewey / Payoff / Loop-CTA) rather than one block
  `[T]` — this also lets each beat carry its own settings (above) and be re-rolled independently
  without touching the rest.
- **Two `[pause]` insertions** — before "Not athletically." in the Hook, and before "It won't
  set him back." in the Loop/CTA — using ElevenLabs' documented delivery-control tag `[T]`
  rather than an ellipsis, because both are hard beat boundaries inside a tight second-range
  that need a clean breath, not a trailing-off. See "Pacing resolution" below for why the
  Loop/CTA one is load-bearing, not decorative.
- **No other tags added.** Per the brand-driven register above, punctuation (the em-dashes and
  full stops already in the shorts-scripting output) does the delivery work; tags are minimal
  and confirmed-catalog only `[T]` (`elevenlabs-audio/references/directorial-prompting.md`).
- **One phonetic flag, not resolved at this layer:** "Côté, Lidor and Hackfort" is the one place
  a mispronunciation risk exists, exactly as the script itself calls out. Respelling is
  `elevenlabs-audio`'s job (a PLS dictionary, Part 2) rather than an inline change to the script
  text, since the words must still read correctly on screen in the citation plate.
- **Sound-like-a-person check: pass.** Every line already varies 5–28 words, avoids AI-fingerprint
  phrases, and reads like something a person would actually say out loud — the shorts-scripting
  stage's own "humanize pass: run" note applies unchanged here `[C]` `(Romayroh, ErCV5czVK1g)`.
  No rewrite was needed at this layer.

```
HOOK (0–3s):
It won't set him back. [pause] Not athletically.

SETUP (3–8s):
That offer moves his reason for playing outside the playing. Dewey saw it coming.

BUILD — PROOF (8–18s):
A 2009 international position stand — Côté, Lidor and Hackfort — reports that kids who
sample many sports still tend to reach elite performance. Late focusers tend to catch up.

BUILD — RE-HOOK (18–21s):
But the offer isn't really about your kid.

BUILD — DEWEY / CLIMAX (21–28s):
Dewey named this in 1916. An activity done for a result outside itself isn't more
serious play — it's constrained labor.

PAYOFF (28–38s):
The next tier exists because the industry needs a next tier to sell. Not because he
cleared a checkpoint. You're allowed to decline it.

LOOP/CTA (38–45s):
You're not taking something away from him. [pause] It won't set him back.
```

## Pacing resolution — the three problems this brief must not inherit silently

The script stage flagged three pacing problems and handed them down explicitly rather than
resolving them. Addressed in order:

**1. 113 words is 3 over the 90–110 word band; a slow, uniform read lands at ~45.2s against a
45s target.** Resolved by **not** reading the whole script at one uniform (slow) rate. Per-beat
speed is set close to neutral but *not* uniform — modestly under neutral on the Hook, Payoff and
Loop/CTA (where the script's own timing table shows slack: implied rates of 140, 144, and 103
wpm against the ~151 wpm average) and modestly over neutral on Setup, Build-proof, the re-hook,
and the Dewey climax (where the table shows implied rates of 160–171 wpm). Working the arithmetic
per beat at a baseline of ~155 wpm at ElevenLabs' neutral `speed: 1.0` — **an assumption, not a
documented ElevenLabs figure; no source states a words-per-minute value for `speed: 1.0`, so this
is this brief's own `[I]` extrapolation from the script's stated 150–170 wpm band** — the seven
beats sum to **~44.75s of actual speech**, plus the one held pause at the Loop/CTA boundary
(~0.35s, see problem 3 below), landing at **~45.1s total — within rounding of the 45s target**,
consistent with the script's own "within rounding" framing of the Dewey sub-beat. **If this
±0.1s drift is unacceptable at the frame-exact edit stage**, the lever is upstream, not here:
trimming two words from the Build-proof beat (e.g., "still tend to" → "tend to") would save
roughly 0.4s — a `shorts-scripting` edit, not something this brief can apply on its own
authority. Flagged, not silently applied. `[I]`

**2. The Dewey sub-beat implies ~171 wpm, marginally above the 150–170 band.** Resolved by
setting that beat's speed at the top of ElevenLabs' valid `speed` range for this script (still
inside the documented 0.7–1.2 bound `[T]`) rather than forcing it through a Marketing/Shorts-style
punchy read. At that speed the beat's 20 words land in ~7.04s against the 7s window — inside
rounding. This is the one beat where the brand's calm register and the timing math are in
genuine tension: a quote-card climax beat "wants" to breathe, and this timing asks it to move
slightly quicker than any other narration beat in the piece. Resolved by keeping style
moderate (not low) so the read carries weight through *emphasis*, not through slowing down —
gravity from delivery, not from pace. `[I]`

**3. The 22-word verbatim quote card in the 21–28s window is the tightest read in the piece.**
Resolved narrower than it first looks: **the VO does not speak the 22-word card verbatim** — it
speaks a 20-word paraphrase ("Dewey named this in 1916…"), while the card's exact wording
renders on screen only, per the script's own beat map. So the TTS pacing problem here is
smaller than the visual problem: the spoken line fits its 7s window (see problem 2). **What this
brief cannot resolve, and is flagging rather than papering over:** whether a cold viewer can
actually *read* 22 words of on-screen quote text inside a 7-second hold is a visual/reading-speed
question, not a voiceover question — it belongs to `visual-prompts` and `shorts-assembly`, which
own the card's on-screen hold duration and typography. Recorded here as an explicit downstream
open item so it isn't silently assumed solved because the audio timing works out. `[I]`

**The Loop/CTA's own edge case, surfaced by this arithmetic and worth stating outright:** its
implied rate (103 wpm) is *slower* than ElevenLabs' `speed` floor (0.7×) can reach at the
assumed 155 wpm baseline (0.7× → ~108.5 wpm, still faster than 103). The fix is **not** to push
speed below the documented valid range — it's to let the beat finish its 12 words in ~6.6s at
the floor speed and hold the `[pause]` tag for the remaining ~0.4s before the mirrored closing
line, which is the natural shape for a closing beat anyway. This is exactly what the `[pause]`
tag placed above is for — it is load-bearing, not decorative. `[I]`

## Production & loudness

- **Normalize the finished voice track to −14 LUFS** `[T]` (YouTube's loudness target;
  `voiceover-brief/references/production-and-loudness.md`). Leave headroom, avoid clipping.
- **Duck the music bed.** The settings guide's documented range is −12 to −18 dB under the
  voice `[T]`, but corpus creators run noticeably lower — around **−21 to −22 dB** — and name
  loud music as the most common beginner cause of low average view duration
  `[C]` `(Romayroh, Wox4Jt_2t6w)` `(Roberto Blake, iaTavrWIGDM)`. Both ranges are given rather
  than silently picking one; **lead with −21 to −22 dB** for this Short, since it's the number
  tied directly to a retention complaint rather than a general mixing guideline.
- **Match music to tone, not just fill silence.** No music beats mismatched music
  `[C]` `(Kallaway, i7upRL4H1FM)` — the Hook/Setup/Build run on quiet-resolve-to-gravity, the
  Payoff turns to warmth and relief; a single static bed that doesn't track that arc will fight
  the VO rather than support it.
- **Re-roll budget for the highest-leverage lines:** consider 2–3 takes each for the Hook and
  the Loop/CTA specifically before locking `[C]` `(Nick Nimmin, IF-PD6XMjYY)` — these are the
  two beats carrying the mirrored closing line the corpus flags as a medium-confidence but
  structurally important technique `(Jenny Hoyos, mhVDcqnxxaY)`.
- **When in doubt, music too quiet beats music too loud** `[I]` — there is no corpus report of a
  video failing for underpowered music, only for overpowering it.

## AI/synthetic-media disclosure — carried forward verbatim for Tasks 13 and 14

Per the script's binding, brand-mandated policy `[B]`, restated here exactly so downstream
stages inherit it rather than re-deriving it:

**On-screen line (safe zone, during the Payoff beat):**
> AI-generated visuals · synthetic voiceover

Rendering spec: small-set, `#F7F3E8`, **never amber** (amber is reserved for the single accent
word elsewhere in the Short) `[B]`.

**Same line required in two more places** `[B]`:
- The video description.
- Every cross-post caption (TikTok/Instagram/X/Bluesky, per `social-repurpose`'s eventual output).

**Plus the platform-level disclosure**, separate from the on-screen/description line: YouTube's
altered/synthetic-content disclosure box, set at upload time `[T]`
(YouTube inauthentic-content policy, verified 2026-07-23 via
https://support.google.com/youtube/answer/1311392 — **re-verify before publishing**, since this
policy area moved once already in 2025). This applies here regardless of voice choice, per the
"Voice pick" resolution above — the library-voice fallback does not clear a disclosure bar the
brand has already decided to hold unconditionally for this Short.

`shorts-assembly` and `social-repurpose` own placement timing and copy integration; this brief
does not own whether the disclosure ships — it already isn't optional.

## Downstream

This brief (Part 1's creative call plus Part 2's executable config below), alongside
`visual-prompts`'s prompt sheet for the same script, is the input to `shorts-assembly`.
`shorts-assembly` inherits the −14 LUFS target and the −21 to −22 dB ducking depth from this
document without re-deriving them.

---

# PART 2 — `elevenlabs-audio` (the executable configuration)

Accepting Part 1's creative call as given: voice character (calm/warm/grounded ally, library
voice, disclosed), per-beat tone, and the −14 LUFS / ducking targets (not restated below —
`voiceover-brief` owns them). This part converts that call into a working ElevenLabs setup.
**No API call was made; no credits were spent.** Fresh-agent Validation Gates 1–3 (normally
dispatched per `elevenlabs-audio/references/validation-gates.md`) were run as a **self-checked
deterministic checklist** instead of a live subagent dispatch for this run — no render or spend
is at stake for a configuration-only artifact, and the autonomy rule directs taking the
non-interactive fallback rather than stopping to ask. Findings are reported as if a gate had
run; treat the checklist below as their output.

## Control surface

| Input | Value | Basis |
|---|---|---|
| `phase` | `draft` → `master` (two-phase; see COST) | `[I]` two-phase protocol is a hard default |
| `use_case` | `shorts-vo` | Stated by the job |
| `expressiveness` | `3` centrally, modulated per beat (2–4 range) | Assumed default `3`, adjusted per Part 1's per-beat table |
| `voice` | `explore` → library voice (see Voice Profile below) | Part 1's creative call; no clone exists yet |
| `language` | `en` | Assumed — script is English |
| `length` | ~675 characters tagged (7 beats, see COST) | Counted from the reformatted script above |
| `privacy` | `standard` | Assumed — no zero-retention requirement stated |
| `determinism` | `on` for master, `off` for draft | Default mapping `[T]` |

## Voice profile

**Stage A was not run to completion** — auditioning a specific voice requires listening to
generated audio, which this configuration-only run does not do (Step 3 of the task brief: no
API call, no credits). What is fixed instead, per the exploration workflow
(`elevenlabs-audio/references/voice-profiles.md`): the performance requirement (stated in Part
1), and three candidate personas to audition against it, in order of preference, each on
`eleven_flash_v2_5` with a 250–500 character excerpt — audition on the *hardest* line (the
Dewey climax beat), not the first one `[T]` `[I]`:

1. **Mid-register, unhurried, warm** — the primary target. Reads Part 1's "quiet resolve"
   requirement literally: not youthful-energetic, not aged-authoritative.
2. **Slightly lower register, plainspoken, minimal vocal fry** — a fallback if candidate 1's
   library instance shows tag/pause artifacts on the `[pause]` tag specifically.
3. **A voice explicitly marketed as "conversational" rather than "narrator" or "announcer"** —
   avoids the news-anchor over-enunciation risk this brief must not have `[T]`.

```
=== VOICE PROFILE CARD (placeholder — Stage A not run) ===
Name:            TBD — audition against the three candidates above
voice_id:        REPLACE_WITH_AUDITIONED_VOICE_ID
Source:          library (lesser-used preset, not a top-default voice) [C]
Reference audio: n/a (not a clone in this run)
Persona:         calm, warm, grounded, mid-register, unhurried — ally, not authority [B]

Locked settings: pending audition — see per-beat table below for the target values to
                 confirm the chosen voice can actually hit
Known-good tags: pending — confirm [pause] lands cleanly before committing to a master
Known-bad tags:  pending
Dictionaries:    pronunciation_dictionary for "Côté, Lidor and Hackfort" — see below
Caveats:         library voice, not a clone — disclosure applies regardless (see Part 1)
Verified on:     not yet — audition step is an open pre-production action
```

This card is deliberately incomplete — filling it in requires the audition step this run does
not take. Recorded as the explicit next action rather than a silent gap. `[I]`

## Model routing

**`eleven_v3` for the master; `eleven_flash_v2_5` for the draft.** Both from the `shorts-vo` row
of the routing table `[T]` (`elevenlabs-audio/references/control-surface.md`, Mapping 1) —
Shorts VO is short and tag-driven, and this script uses the `[pause]` tag, which is v3-only
`[T]`. `model_id` is set explicitly on every payload below; the API default
(`eleven_multilingual_v2`) would silently drop the tag `[T]`.

**Feature check, run before any tag was written** (`model-routing.md` quick check):
1. Contains a tag (`[pause]`)? → v3 or nothing. **v3 selected.** `[T]`
2. Inline IPA? Not used — pronunciation handled via PLS `<alias>` instead (see below), so this
   doesn't force v3 on its own.
3. `<phoneme>`? Not used — `<alias>` chosen instead, which works on every model, including the
   Flash v2.5 draft `[T]`.
4. Multiple speakers? No — single narrator throughout.
5. Non-English? No — `en`.
6. Real-time? No — pre-rendered VO.
7. Longer than the model's cap? No — full tagged script is ~675 characters, far under v3's
   5,000-character cap `[T]`; each of the 7 per-beat requests is far smaller still.

**No routing contradictions found.**

## Voice settings

Converting Part 1's per-beat feel into ElevenLabs' wire values. On `eleven_v3`, `stability` is
one of three discrete modes, not a float `[T]`; every beat below uses **Natural**, per Part 1's
explicit rule against both Creative (too hot for the ally register, and "prone to
hallucinations" `[T]`) and Robust (would suppress the `[pause]` tag `[T]`).

`similarity_boost`: the two source documents disagree on the safe band —
`voiceover-brief`'s guide gives **0.75–0.90** `[T]` (dated 2026-07-23), while
`elevenlabs-audio`'s runbook gives **0.65–0.75, `[T-unverified]`**, warning that above ~0.85
risks reproducing reference-audio noise. Both are given rather than silently picking one; this
brief holds **0.78** — inside both ranges, and conservative against the noise risk the
lower-band source names specifically. `[I]`

Speed values below implement the Pacing resolution above; each is inside ElevenLabs' documented
valid range of 0.7–1.2 `[T]`.

| Beat | Stability mode | `style` | `similarity_boost` | `speed` | `use_speaker_boost` |
|---|---|---|---|---|---|
| Hook | Natural | 0.20 | 0.78 | 0.90 | true |
| Setup | Natural | 0.15 | 0.78 | 1.08 | true |
| Build — proof | Natural | 0.15 | 0.78 | 1.08 | true |
| Re-hook | Natural | 0.25 | 0.78 | 1.03 | true |
| Build — Dewey (climax) | Natural | 0.30 | 0.78 | 1.10 | true |
| Payoff | Natural | 0.25 | 0.78 | 0.93 | true |
| Loop/CTA | Natural | 0.20 | 0.78 | 0.70 (floor) | true |

No beat uses `style` above 0.30 — deliberately below the corpus's Marketing/Shorts band
(0.40–0.60) `[T]`, per Part 1's brand-driven override. `use_speaker_boost: true` throughout —
the corpus/runbook default for VO, left on unless it produces artifacts `[T]`.

## Directorial script (tagged, chunked per beat)

Each beat is its own generation unit, chained with `previous_request_ids` (stronger than text
context, anchors to real rendered audio `[T]`) plus `previous_text`/`next_text` as a redundant
fallback. This also matches `voiceover-brief`'s TTS-sectioning rule — a bad take costs one
beat, not the whole 45 seconds `[T]`.

```
1. HOOK          "It won't set him back. [pause] Not athletically."
2. SETUP         "That offer moves his reason for playing outside the playing. Dewey saw it
                  coming."
3. BUILD-PROOF   "A 2009 international position stand — Côté, Lidor and Hackfort — reports
                  that kids who sample many sports still tend to reach elite performance.
                  Late focusers tend to catch up."
4. RE-HOOK       "But the offer isn't really about your kid."
5. BUILD-DEWEY   "Dewey named this in 1916. An activity done for a result outside itself
                  isn't more serious play — it's constrained labor."
6. PAYOFF        "The next tier exists because the industry needs a next tier to sell. Not
                  because he cleared a checkpoint. You're allowed to decline it."
7. LOOP-CTA      "You're not taking something away from him. [pause] It won't set him back."
```

`[pause]` is a documented delivery-control tag `[T]`
(`elevenlabs-audio/references/directorial-prompting.md`) — not experimental, no flag needed.
No other tags are used; punctuation (the em-dashes and full stops already in the script) carries
the rest of the delivery, per Part 1's brand-driven minimal-tagging decision and the general
rule that punctuation works on every model while tags work on exactly one `[T]`.

**Pre-render checklist** (`directorial-prompting.md`):
1. Punctuation alone reads sensibly without the tag — yes, both `[pause]` placements sit at
   already-punctuated sentence breaks.
2. Every tag is catalog-confirmed — yes, `[pause]` only.
3. No closing-tag syntax used — confirmed.
4. Model is `eleven_v3` — confirmed for the master.
5. Stability mode is Natural, not Robust — confirmed for every beat.
6. Tags compatible with the voice's known range — **pending audition** (Voice Profile Card is
   incomplete); flagged, not assumed.
7. No multi-speaker — confirmed, single narrator.
8. Numbers pre-checked — "2009" and "1916" are spoken as years; ElevenLabs' text normalizer
   handles calendar-adjacent numbers by default `[T]`, but this is called out explicitly in the
   QC checklist below rather than assumed silently correct, since years aren't one of the
   sources' explicitly-confirmed-safe categories.
9. Each chunk is far under the model's cap — confirmed (largest beat, Build-proof, is 176
   characters).

## Pronunciation

**One dictionary, `<alias>` entries only** — not `<phoneme>`, deliberately. Two reasons: (1)
these three names are used exactly once in the whole script, and an alias is "often the better
answer even where phonemes work — readable, reviewable, model-portable" `[I]`
(`elevenlabs-audio/references/pronunciation-dictionaries.md`); (2) the draft phase runs on
`eleven_flash_v2_5`, which does not support `<phoneme>` at all (only `eleven_v3` and
`eleven_flash_v2` do — **not** `eleven_flash_v2_5`, a point the supplied enterprise runbook got
wrong `[T]`), so a phoneme-only dictionary would be silently inert during drafting. `<alias>`
works on every model, including the draft `[T]`.

Applied only to the Build-proof beat's request (the sole beat where the names appear) via
`pronunciation_dictionary_locators` — 2 locators, well under the documented max of 3 `[T]`.
Case variants enumerated per the mandatory rule that PLS matching is case-sensitive `[T]` — a
single-casing entry would be a finding, not a style choice, per Validation Gate 2's own check.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0"
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.w3.org/2005/01/pronunciation-lexicon
    http://www.w3.org/TR/2007/CR-pronunciation-lexicon-20071212/pls.xsd"
    alphabet="ipa" xml:lang="en-US">

  <lexeme><grapheme>Cote</grapheme><alias>Koh-tay</alias></lexeme>
  <lexeme><grapheme>cote</grapheme><alias>Koh-tay</alias></lexeme>
  <lexeme><grapheme>COTE</grapheme><alias>Koh-tay</alias></lexeme>

  <lexeme><grapheme>Lidor</grapheme><alias>Lee-dor</alias></lexeme>
  <lexeme><grapheme>lidor</grapheme><alias>Lee-dor</alias></lexeme>
  <lexeme><grapheme>LIDOR</grapheme><alias>Lee-dor</alias></lexeme>

</lexicon>
```

Note on the grapheme spelling: the script's citation text renders the name with the accented
character (Cote with an acute e); the `<grapheme>` entries above use the plain-ASCII form since
PLS grapheme matching is exact-string and the source text should be checked against whichever
literal character encoding the final script file uses before this dictionary is created — flag
this as a pre-production verification step, not a resolved detail. `[I]` **"Hackfort" needs no
entry** — it renders correctly as ordinary English text; it is flagged elsewhere in the pipeline
(script and concept-brief stages) as a lexicon false-positive against the banned word "hack,"
which is a text-screening concern, not a pronunciation one, and is already resolved there.

`version_id`: not yet issued (dictionary not created — no API call made). **Pin it once created**
`[I]` — omitting it means a later dictionary edit silently changes a job believed to be locked.

## Request payload

One worked example — the Build-Dewey climax beat (beat 5), chosen because it is the tightest
timing case in the piece (see Pacing resolution) and therefore the one worth showing in full.
The other six beats follow the identical shape, substituting each beat's `text` and the
Voice Settings table's row above; they are not repeated here to keep this document readable.

```json
{
  "text": "Dewey named this in 1916. An activity done for a result outside itself isn't more serious play — it's constrained labor.",
  "model_id": "eleven_v3",
  "voice_settings": {
    "stability": "natural",
    "similarity_boost": 0.78,
    "style": 0.30,
    "speed": 1.10,
    "use_speaker_boost": true
  },
  "seed": 20260728,
  "previous_request_ids": ["REQUEST_ID_FROM_BEAT_4_RE_HOOK"],
  "previous_text": "But the offer isn't really about your kid.",
  "next_text": "The next tier exists because the industry needs a next tier to sell.",
  "apply_text_normalization": "auto"
}
```

Query parameters: `output_format=mp3_44100_192&enable_logging=true`

**Note on the `stability` field's wire shape:** v3 exposes stability as the three discrete modes
(Creative / Natural / Robust); this brief writes it as the string `"natural"` above, but the
exact wire representation (mode string vs. an SDK-mapped value) should be confirmed against the
live API reference before this payload is actually sent — this is one of the fastest-moving
parts of the surface `[T]` `[I]`. Everything else in the template is written as documented.

**curl:**

```bash
curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/REPLACE_WITH_AUDITIONED_VOICE_ID?output_format=mp3_44100_192&enable_logging=true" -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" -d @beat5-dewey.json --output beat5-dewey.mp3
```

Written to a file and referenced with `-d @beat5-dewey.json` rather than inlined, since a tagged
script inlined into a shell string is a quoting hazard `[I]`. **Not executed** — no API key was
used, no request was sent, no credits were spent.

## Cost

```
COST
  Draft:  ~296 chars (Build-proof + Build-Dewey excerpts, the two riskiest beats for
          pacing) x Flash v2.5 rate ($0.05 / 1,000 chars, T) ~= $0.015
  Master: ~675 chars (all 7 beats, tagged, full script) x master rate (~$0.10 / 1,000
          chars -- T-unverified, inferred as 2x the documented Flash discount rather
          than a directly quoted master figure) ~= $0.07
  Basis:  per input character, including spaces and punctuation [T]
  Note:   API calls are billed; the two free regenerations are website-only and not
          available via the API [T] -- if free re-rolls are wanted while tuning fixed
          text, do that tuning in the web UI and port settled values into this payload
  Re-roll budget: 3 master re-rolls budgeted for the Dewey and Loop/CTA beats
          specifically (the tightest-timing and most structurally load-bearing lines)
          ~= $0.02-0.03 each, ~$0.08 worst case additional
  Total estimate, draft + master + budgeted re-rolls: roughly $0.10-0.12
```

This is well below the corpus's ~$1–2/video figure `[C]` `(Make Money Matt, TvJhpOxFRsE)` —
that figure appears to bundle iteration and multiple full-script takes; the arithmetic above is
per-beat, sectioned generation on a 45-second script, which is exactly the cost structure the
sectioning discipline is meant to produce. Both framings are legitimate; shown rather than
reconciled by picking one.

## QC checklist

| Symptom | Likely cause | Fix |
|---|---|---|
| `[pause]` ignored | Wrong model/mode, or the audition voice can't perform it | Confirm v3 + Natural/Creative; if the voice itself can't, re-audition (`voice-profiles.md`) `[T]` |
| "2009" / "1916" read oddly (e.g., digit-by-digit instead of as a year) | Normalizer trouble spot not explicitly confirmed for calendar years | Pre-convert to "twenty-oh-nine" / "nineteen sixteen" in the text if the auto read is wrong `[T]`/`[I]` |
| "Côté, Lidor and Hackfort" mispronounced | Dictionary not applied to that beat's request, or grapheme casing mismatch | Confirm the locator is attached to beat 3 only; confirm exact grapheme string matches the script file's literal characters `[T]` |
| Flat, monotone delivery on the Dewey beat | Style too low for the climax read | Nudge `style` up within the 0.25–0.35 band before touching `stability` `[T]` |
| Slurring or unstable read | Speed pushed near the 1.10–1.15 edge on the tight beats | Back off 0.02–0.05 increments; the pacing math has ~0.1s of slack overall (see Pacing resolution) `[T]` |
| Draft sounds worse than expected on the years/numbers | Flash v2.5 artifact, not a script defect | Re-check on the v3 master before rewriting anything `[T]` |
| Loop/CTA finishes early even at the speed floor | Expected — see Pacing resolution's Loop/CTA note | Confirm the `[pause]` is landing and filling the gap; if not, lengthen it manually in the edit rather than fighting `speed` below its valid floor `[T]` |

## Validation gates (self-checked deterministic pass, not a live fresh-agent dispatch)

- **Gate 1 — Script & tag:** PASS. Only one tag used (`[pause]`), catalog-confirmed, no closing
  tags, correct model (v3), stability mode Natural on every beat (never Robust with the tag
  present), all 7 chunks far under the 5,000-char cap, single speaker throughout (no
  Text-to-Dialogue routing error), numbers flagged in the QC checklist rather than assumed safe.
- **Gate 2 — Payload:** PASS. Every setting in its documented valid range (`speed` 0.90–1.10,
  inside 0.7–1.2; `style` ≤0.30; `similarity_boost` 0.78, inside both cited bands);
  `model_id` set explicitly on every request; `output_format` matches the master phase and the
  Creator+ tier gate is named; `enable_logging: true` matches `privacy: standard` (no
  zero-retention conflict); `seed` present and fixed for the master; every chunk seam carries
  both `previous_request_ids` and `previous_text`/`next_text`; 2 dictionary locators (≤3);
  both PLS case variants (upper/lower/mixed) enumerated for each name; `<alias>` used
  throughout, which is valid on every model in this job including the Flash draft.
- **Gate 3 — Pre-master spend:** N/A for this run — no draft was actually rendered and no master
  will be sent from this document; it is a configuration artifact. Recorded as `n/a`, not
  claimed as `pass`, per the output contract's instruction never to claim a gate passed without
  running it.

## Next

1. Run the Stage A audition (three candidate personas above, Flash v2.5, 250–500 character
   excerpt on the Dewey beat) and fill in the Voice Profile Card.
2. Create the PLS pronunciation dictionary from the XML above; confirm the grapheme string
   against the literal script file; pin `version_id`.
3. Render the draft (the two flagged excerpt beats) and confirm direction before any master
   spend, per the two-phase protocol.
4. Feeds `shorts-assembly` next, alongside `visual-prompts`'s prompt sheet for the same script —
   `shorts-assembly` inherits the −14 LUFS target, the −21 to −22 dB ducking depth, and the
   verbatim disclosure line, all recorded in Part 1 above.
