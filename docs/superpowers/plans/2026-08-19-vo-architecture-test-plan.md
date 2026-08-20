# Single-Take VO Architecture — Review & Bounded Test Plan

**Status:** Plan only — not executed. No API calls made, no code changed.
**Author of the technical review:** Opus (dispatched as a subagent), reviewing a proposal from the
project owner. This doc is the orchestrator's synthesis of that review into an actionable plan.

## 0. What was proposed

Replace the current 7-clip-VO + 2-segment-bed hand-stitched architecture with:
1. One continuous ElevenLabs TTS call for the whole script, using `<break time="Xs"/>` tags
   (Multilingual v2, the model the operator's Pro voice is enabled for) to bake pauses into the
   generation.
2. A spectrogram/measurement pass to confirm where those pauses actually landed.
3. Shot/caption/overlay timing derived from that measurement, instead of hand-authored.
4. One Eleven Music bed generation instead of two spliced segments.
5. Mix through `stitcher`.

Motivation: this session's three real bugs (beat-to-beat loudness spread, a dynamic-range-collapsing
double-loudnorm, and a duck_db miscalibration found this session) all trace back to hand-assembling
multiple audio pieces. The operator's hypothesis: fewer pieces, less hand-assembly, fewer bugs.

## 1. Verdict

**Good diagnosis, wrong prescription.** Steps 2–4 (measure, derive, single bed) are correct and
worth doing. Step 1 (single continuous TTS call) should be rejected — it doesn't just fail to help,
it makes one of this session's bugs permanent and unfixable.

### The decisive finding

**The seven current VO clips already tile into one continuous file, exactly.** Each clip's measured
duration lands precisely on the next clip's `at` offset — zero gaps, zero overlap. Concatenating them
today produces the same single audio stream the proposal asks ElevenLabs to generate directly. There
is nothing to gain from generating it as one call, because it already functions as one file.

**And that zero-gap tiling is the literal cause of this session's duck_db bug.** `envelope.py`'s
`_duck_level` ducks the bed under every VO stem's time span; because the spans cover `[0, runtime]`
with no gaps, the bed sits at `duck_db` (the deep, "narration is happening" level) for 100% of the
runtime and never reaches `gain_db` (the shallower baseline level) at all. A single-file VO is one
span over the whole runtime — the identical pathology, now structural. No spec edit could ever fix
it, because the ducking logic has nothing but VO timing to go on, and a single file removes the only
information (gaps) it needs.

### What actually fixes the architecture

Keep per-beat generation (cheap re-rolls, matches this repo's own corpus guidance — see §2 below),
but stop hand-computing offsets. Instead:

1. **Measure** each take's real speech extent (trim leading/trailing silence).
2. **Derive** `at` offsets as the cumulative sum of trimmed durations plus small, deliberate,
   authored inter-beat gaps.
3. Real gaps between stems means ducking finally has something to duck around — the bed lifts to
   baseline in the pauses and drops under speech, as designed, for the first time.
4. Add `previous_request_ids` chaining across the 7 beats (documented in this repo's own
   `elevenlabs-audio` skill, apparently not currently used) for cross-beat prosodic continuity —
   this is likely what the single-file idea was really chasing.
5. One Eleven Music composition-plan call (2 sections) replaces the two-segment hand splice.

This requires **zero changes to `stitcher/stitcher/{audio,spec,envelope}.py`** — the existing
`Stem`/`Bed` model and `_build_bed`/`_place_stems` already support it.

## 2. Corpus grounding (this project's non-negotiable discipline)

`docs/elevenlabs-voiceover-guide.md:96` `[T]`, citing `(Nick Nimmin, IF-PD6XMjYY)`:
> "Generate section-by-section. Don't render one giant block. Section-level generation lets you
> control pacing and re-roll a bad read cheaply — the same logic human narrators use when they
> record each line 2–3 times to have options in the edit."

`docs/headless-shorts-production-playbook.md:207`: generate 2–3 takes of the hook line and pick the
best read. This session actually exercised that: `VO1_provoice_take2.mp3` and
`VO7_provoice_take2.mp3` exist on disk — re-rolls of exactly the hook and the CTA, the two lines the
corpus singles out. A single-call architecture would have turned both of those into full-script
regenerations.

Also relevant: `docs/headless-shorts-production-playbook.md:213` already sanctions pause tags
(`<break>`) *or* "trim silences in the edit" as alternatives — the recommended architecture takes
the second, corpus-sanctioned option.

## 3. A live, separate bug this review surfaced (fix independent of any architecture decision)

The current live `render-spec.json` is **8.945 seconds out of sync** with the actual new-voice audio
— it still carries offsets computed for the *previous* narrator voice's clip durations. By beat 7,
shots/captions/overlays are 8.2s ahead of where the narration actually is, and the spec still
references the old voice's asset files, not `assets/provoice-2026-08-19/`. This is a real shipping
defect, discovered as a side effect of this review, and it needs no decision — it should be
re-derived from the actual new-voice clip durations regardless of which architecture direction is
chosen.

## 4. Risks, ranked by how likely they are to bite

| # | Risk | Likelihood | Notes |
|---|---|---|---|
| 1 | Ducking collapse becomes permanent | Near-certain if step 1 is kept | Dealbreaker for the literal proposal |
| 2 | Loss of per-beat re-roll granularity | Certain, expensive | A flub anywhere forces a full-script regeneration; non-deterministic TTS means the other beats change too, invalidating derived timing |
| 3 | `<break>` tag timing isn't guaranteed exact | Likely, but manageable | ElevenLabs documents no ms guarantee and warns excessive breaks can cause speed-up/artifacts. Under the recommended architecture this risk mostly disappears — gaps come from measured take boundaries, not requested tag durations |
| 4 | Silence-detection may not cleanly recover beat boundaries from one blended file | Moderate — the single biggest unknown, and free to test | Under the recommended per-beat architecture this is much easier: detecting speech extent *within one known take*, not unknown boundaries inside a blended file |
| 5 | Commits the channel to Multilingual v2/Flash, forecloses v3 | Moderate, strategic | `<break>` doesn't work on v3; the measured/trim approach is model-agnostic |
| 6 | Existing duck-depth QA check may be silently measuring nothing | Low, but worth checking | It differences two bed intermediates; with a flat envelope there's no un-ducked region to compare — it didn't catch the 100%-duck bug |

## 5. Opportunities confirmed

- **Deriving timing from measurement, not hand-authoring, kills the drift bug at its source** and
  makes every future voice swap mechanical instead of error-prone.
- **One Eleven Music composition-plan call replaces the two-segment splice** — the strongest single
  element of the original proposal. `stitcher`'s `_build_bed` already loops/trims/conforms a bed to
  the render's runtime (`-stream_loop -1 -t runtime`), so the bed never needed hand-sizing at all —
  more redundant work than previously realized.
- Eleven Music has no documented loudness/volume API control, but this turns out **not to matter**:
  `stitcher`'s bed conforming is already voice-relative and solves for absolute level regardless of
  what the API returns (`audio.py:313-314`). The only bed property that actually matters is its
  internal dynamic range (LRA) — which is exactly what the newly-built `precondition.py` exists to
  tame, independent of this architecture question.

## 6. Bounded test plan (≤ 3 real ElevenLabs API calls)

### Test 0 — zero cost, run first

Everything needed already exists on disk (`VO{1..7}_provoice_prepped.wav` with known exact
boundaries; `VO_assembled_provoice.wav`, 51.920s continuous).

- Run `ffmpeg -af silencedetect=n=-40dB:d=0.25` (sweep threshold −35/−40/−45dB, duration
  0.20/0.25/0.35s) against the continuous file; compare recovered boundaries to the 6 known ones.
- Separately measure each take's own leading/trailing padding — this directly produces the trim
  values the recommended architecture needs, for free.
- **Pass:** some parameter pair recovers exactly 6 boundaries, each within ±120ms of truth.
- **Fail:** confirms per-beat measurement (not blended-file boundary recovery) is the only viable
  path — which is what's recommended anyway.

### Call 1 — full-script single take with `<break>` tags (upside test, not a gate)

TTS call using the pinned channel voice, Multilingual v2, all 7 caption lines joined with
`<break time="0.7s"/>` at beat boundaries and a longer break at the re-hook. ~850 characters, ≈$0.09.

- **Measure:** `silencedetect` for pause position/duration accuracy; `ebur128` for LRA (artifact
  check); speech-only duration vs. baseline (speed-drift check).
- **Pass (all):** median break-timing error ≤100ms (max ≤250ms); LRA within 1.5 LU of the
  per-beat baseline; no runaway silence; speech rate within 5% of baseline.
- **Fail →** confirms the recommendation (per-beat + measured gaps) as the only path — costs $0.09
  to learn this either way.

### Call 2 — Eleven Music, single composition-plan bed

2-section composition plan mirroring the existing bed arc (~14s + ~32s), via the `elevenlabs-music`
skill's payload construction. No loudness/volume parameter attempted (none exists; none needed).

- **Measure:** duration accuracy vs. request; `ebur128` LRA (predicts ducking stability — target
  ≲9 LU); audible coherence of the section transition vs. the current spliced baseline.
- **Pass:** duration within ±2%, audible section change near the requested boundary, no clicks.

### Call 3 — held in reserve, spend after 1–2 are analyzed

Either: (a) validate the recommended architecture's continuity claim by re-rolling one beat (beat 5)
with `previous_request_ids` chained to its neighbors and checking for an audible seam; or (b), if
Call 1's break timing was borderline, re-run it verbatim to measure run-to-run variance.

### Comparison baseline

`Final_Mix_Preconditioned_DuckFix.wav` is a reasonable reference but was produced by the ad hoc
hand-mixing path (the thing bug #2 came from) — for a fair comparison, render a comparison mix
through `stitcher`'s real, gated `build_audio()` instead, and difference the two bed intermediates
(`04a_bed_conformed` vs. `04b_bed_ducked`) to directly see whether ducking is finally working (bed at
baseline in gaps, at duck level under speech) instead of flat.

### Tooling

No new ElevenLabs client code needed — `elevenlabs-tooling/elevenlabs_tooling/client.py`'s
`send(url, payload_bytes, api_key)` already does a generic authenticated POST and returns raw audio
bytes or a structured error. The only genuinely new code is a `silencedetect` output parser (there's
currently no helper for it in `stitcher/stitcher/ffmpeg.py`, only `measure_loudness`) — worth writing
carefully since the recommended architecture depends on it permanently.

## 6a. Test 0 — actual result (run against real files, zero API cost)

**Outcome: FAIL, decisively — confirms §1's recommendation.**

Ran `ffmpeg silencedetect` against `VO_assembled_provoice.wav` (51.920s, the current continuous
concatenation) sweeping threshold ∈ {−35, −40, −45 dBFS} × min-duration ∈ {0.20, 0.25, 0.35s}, and
compared every detected silence interval, across every setting, to the 6 known clip-tiling
boundaries (5.200 / 10.800 / 16.240 / 22.560 / 35.840 / 46.480):

| Known boundary | Nearest detected silence edge (best across all settings) | Delta | Within ±120ms? |
|---|---|---|---|
| 5.200 | 5.168 (silence 4.786–5.168, at −35dB) | 32ms | ✅ |
| 10.800 | *none detected within several seconds* | — | ❌ |
| 16.240 | 16.201 (silence 15.944–16.201, at −35dB) | 39ms | ✅ |
| 22.560 | 22.558 (silence 21.716–22.558, at −35dB) | 2ms | ✅ |
| 35.840 | *none detected within several seconds* | — | ❌ |
| 46.480 | *none detected within several seconds* | — | ❌ |

**3 of 6 recovered, 3 of 6 have no detectable silence at any tested setting** — plus every sweep also
produced 8–16 *spurious* silence detections (natural mid-sentence breaths within individual takes)
that don't correspond to any real boundary. This fails the plan's stated pass bar (exactly 6, no
spurious) outright — not a close call.

**Why:** at three of the six clip-to-clip seams (vo2→vo3, vo5→vo6, vo7→end), the narrator simply
didn't pause when each beat was originally recorded as a separate take — there's no acoustic gap
there to find, at any threshold. Per-clip padding measurements (run on the 7 individual
`VO{1..7}_provoice_prepped.wav` files) confirm this directly: VO2, VO5, and VO7 all show **zero**
detected trailing silence — real speech content runs to within a few ms of the file's own end. VO1
also opens with **zero** leading silence. Where clips do have padding, it's small and asymmetric
(VO3 ≈106ms leading / 68ms trailing tail after last silence block; VO4 ≈71ms leading and a
substantial ~780ms trailing silence block; VO6 ≈222ms trailing).

**One reassuring side-finding:** the one deliberate, actually-recorded pause in this render — the
narrator's natural mid-sentence pause inside vo4, at the design spec's declared "re-hook pause"
window (19.514–20.223) — *was* cleanly detected (19.606–20.223, well within tolerance) at −35dB.
`silencedetect` works fine on **real** pauses. It specifically cannot recover **seams** where no
pause was ever recorded, which is the situation at half of the 6 clip boundaries.

**Conclusion, directly actionable:** boundary recovery from a blended/single file is not reliable
here — confirming §1's rejection of "generate as one call, then detect boundaries after the fact."
It does **not** invalidate the recommended architecture, which never depends on discovering
boundaries after the fact — it works forward from known, separate takes and **authors** small
deliberate gaps at assembly time rather than hunting for pauses that may not exist. The per-take
padding numbers above are usable as-is for that trimming step.

## 6b. Call 1 — actual result (1 real, billed ElevenLabs API call made)

**Spent:** 1 of the plan's 3-call budget. `eleven_multilingual_v2`, voice `eDwT8Vhp2yxJzAMmuuPA` (the
pinned channel PVC), 956 characters (script + break markup), `mp3_44100_192`, HTTP 200, 1.38MB
audio. Settings used (none were locked on the voice's card, so these were assumed and stated
explicitly per this repo's `elevenlabs-audio` skill discipline): `stability=0.55,
similarity_boost=0.80, style=0.30, speed=1.0, speaker_boost=true` — a blended Marketing/Shorts ×
Storytelling preset per `settings-by-content-type.md`, picked because a single call can't carry
per-beat settings the way the current per-beat pipeline does.

**Script:** the live spec's 7 caption cues, verbatim (deliberately *not* hand-converting
"2,300"/"2,556"/"2026" to spelled-out words, so text-normalization wasn't a second variable), joined
with `<break time="Xs"/>` tags: 0.5 / 0.4 / 0.5s at the three ordinary beat boundaries, 1.0s at the
script's own natural "re-hook" turn inside beat 4 ("Here's the strange part. ⟨break⟩ Jump forward
2,300 years..."), then 0.5 / 0.4 / 0.6s at the remaining three beat boundaries. 7 breaks total,
3.9s of requested pause time.

### What worked

- **No artifacts, no destabilization at 7 breaks in ~950 characters.** Speech rate (chars ÷
  speech-only seconds, matched `silencedetect` settings both files): **16.34 chars/s** on the new
  take vs. **16.53 chars/s** on the current per-beat baseline — a **1.1% difference**, well inside
  the plan's 5% "no speed-up artifact" bar. The documented ElevenLabs caveat ("excessive breaks...
  speech might speed up") did not materialize at this break count.
- **LRA held:** 5.2 LU (new) vs. 6.4 LU (baseline) — **1.2 LU delta**, inside the plan's ≤1.5 LU bar.
  No dynamic-range collapse.
- **The most distinctive break — the 1.0s re-hook pause — landed almost exactly on target and was
  unambiguous to find:** measured **1.110s**, a clean, isolated silence with nothing else nearby to
  confuse it with. **+110ms over the request**, inside the plan's ≤250ms max-error bar.
- All 7 requested breaks are present in the file *somewhere*, each in the right rough position and
  each measuring within roughly 50–200ms of its requested duration, every one running slightly
  **longer** than requested (a consistent, one-directional bias, not random noise).
- Total duration: **57.446s** vs. the baseline's 51.920s (+5.526s) — larger than the 3.9s of
  requested break time alone, because (see below) the model also inserted pauses I never asked for.

### What didn't work — and it's the same failure mode Test 0 already found, in a new form

**Confidently attributing each of the other 6 detected pauses to a specific requested break, vs. a
natural sentence-final pause the model chose on its own, is not reliable from amplitude-threshold
`silencedetect` alone.** Two of beat 5's own internal sentence boundaries ("...2026 study." /
"...fewer injuries." / "...an extra season." — 4 sentences in one beat) produced silences
(0.72s and 0.75s) **the same size as the requested inter-beat breaks** — nothing in the waveform
distinguishes "a break I asked for" from "a period the model paused at anyway." Cumulative-timing
estimation (character count × measured speech rate) narrows the search but doesn't resolve it
cleanly past the third break, because per-beat speaking rate isn't actually constant across an
~800-character script.

**This is not a new problem — it's Test 0's finding again, inside one generated file instead of the
current blended assembly.** The correct tool for exact ground truth exists and wasn't used here:
ElevenLabs' `/v1/text-to-speech/{voice_id}/with-timestamps` endpoint returns character-level
alignment directly, no post-hoc inference needed. That would fully resolve this ambiguity in one
more call, if it's worth spending on.

### Reading on the verdict in §1

This **does not overturn** the recommendation in §1. If anything it reinforces the same underlying
point from a second angle: generation-time markup (`<break>` tags) is a plausible, artifact-free way
to *request* pauses (the primary question this call was testing, and it passed cleanly) — but
**recovering exact pause locations after the fact, from audio alone, is unreliable whether the file
is one continuous take or the current blended assembly.** The recommended architecture
(§1: per-beat generation + `previous_request_ids` chaining + measured trim + authored gaps) sidesteps
this entirely because it never needs to *recover* a boundary — every boundary is already known, by
construction, from the moment each take is generated.

## 6c. Operator listened to Call 1 and prefers it — re-opening the question

The operator listened to `single_take_break_test.mp3` and judged it clearly better than the current
per-beat-stitched mix. That's a real signal this plan can't get from measurement alone, and it
reopens §1's rejection of the single-take idea — not because the technical analysis in §1–§6b was
wrong, but because a strong subjective preference changes which trade-offs are worth accepting.

### Investigation: `/with-timestamps` and Forced Alignment (2 more real API calls)

**Forced Alignment (`POST /v1/forced-alignment`) — blocked, not usable right now.** Attempted to
retroactively align the already-generated Call 1 audio against its plain transcript (zero new TTS
spend). Failed with HTTP 401: **the current API key is missing the `forced_alignment` permission
scope** — a dashboard-level key setting, not something more calls fixes. If retroactive alignment of
already-recorded audio is ever needed, that scope has to be enabled on the key first.

**`/with-timestamps` (`POST /v1/text-to-speech/{voice_id}/with-timestamps`) — works, and resolves
the entire measurement problem.** Same endpoint family as regular TTS, same per-character pricing,
just returns `alignment.characters[]` with an exact start/end second for every character —
**including the literal `<break time="Xs"/>` markup**, which collapses to a single zero-duration
instant at the moment the break begins. The real pause length is exactly
`(next real spoken character's start time) − (last real spoken character's end time before the tag)`
— exact ground truth, no acoustic inference, no ambiguity with natural sentence-internal pauses.

**Call 2** (identical text/voice/settings to Call 1, `seed=42` for reproducibility, routed through
`/with-timestamps`) gave exact, unambiguous results for all 7 breaks:

| # | requested | measured (exact) | delta |
|---|---|---|---|
| 1 | 0.50s | 0.604s | +104ms |
| 2 | 0.40s | 0.453s | +53ms |
| 3 | 0.50s | 0.569s | +69ms |
| 4 (re-hook) | 1.00s | 1.207s | +207ms |
| 5 | 0.50s | 0.558s | +58ms |
| 6 | 0.40s | 0.453s | +53ms |
| 7 | 0.60s | 0.697s | +97ms |

**Median delta 69ms, max 207ms** — inside the plan's ≤100ms / ≤250ms bars (Call 1's silencedetect
estimate had put the median right at the edge of failing; the real number clears it comfortably).
Every break runs long by a small, bounded, one-directional amount — consistent and apparently
predictable, not random jitter.

### Why this changes the recommendation

§1 rejected single-take generation specifically because a single VO stem is one unbroken span, and
`stitcher`'s ducking (`envelope.py`'s `_duck_level`) ducks the bed for the full extent of every VO
stem's span — so a single file can never let the bed breathe. That objection assumed the pause
locations would have to be *discovered* after the fact, unreliably.

**They don't, anymore.** With exact character-level timestamps, the single continuous take can be
**split into multiple stem files at the exact measured break boundaries** — trivial `ffmpeg -ss/-t`
trims, zero regeneration, zero new API spend — and fed into `stitcher`'s existing `Stem`/`Bed` model
completely unchanged. Real gaps between stems is exactly what `_duck_level` needs to lift the bed to
baseline between beats. This gets **both** things at once: the single-generation prosody the operator
heard and preferred, and working ducking — without writing a single line of new `stitcher` code.

**What this does *not* resolve:** re-roll granularity (§4, risk 2) is unchanged. A flub anywhere in
a ~950-character single generation still means regenerating the whole take, and the other 6 beats'
audio will come out slightly different every time (non-deterministic TTS, `seed` only being
"best-effort"). That trade-off is real and worth the operator deciding on explicitly (§7.2) — it
doesn't go away just because timing can now be measured exactly.

### Free follow-up, actually run — the ducking fix confirmed at the mechanism level

Split Call 2's audio at its 7 exact measured break boundaries into 8 stem files (beat 1, 2, 3, 4a,
4b, 5, 6, 7), conditioned each with `precondition.py` (Tasks 1–4's module), reused the
already-conditioned bed from earlier this session, and ran a real `RenderSpec` — original,
unmodified `gain_db=-22.0` / `duck_db=-29.0`, **no bed windows declared** — through `stitcher`'s
actual `build_audio()`. Zero new API spend; local `ffmpeg`/`stitcher` only.

**Result: linear-mode gate passed, mix re-measured at −14.0 LUFS / −1.9 dBTP.** All 8 stems
conditioned cleanly (7–9 dB peak reduction each, consistent with Task 5's earlier real numbers).

**The ducking question itself needed a second pass to answer correctly.** A first check — sampling
audio RMS in the real gap between beat 3 and beat 4a vs. under continuous speech — came back
essentially flat (−0.75 dB delta), which looked like the fix hadn't worked. It hadn't been measured
right: that gap is only **569ms** wide, and `Bed`'s default ramps
(`spec.py:139-140`, `duck_attack_ms=120`, `duck_release_ms=400`) consume **520ms** of it — the
next stem's 120ms attack-anticipation starts *before* its own `at`, so the envelope only reaches a
true flat baseline for roughly a **20–30ms window**, sandwiched between the release ramp finishing
and the next attack ramp starting. A crude 270ms sample window mostly captured ramp, not baseline.

**Querying `envelope.level_at()` directly — the exact function `_build_bed` itself uses, no audio
measurement involved — gives the real, unambiguous answer:**

```
t=18.360 → 18.459s:  -29.00 dB  (still ducked, beat3 still speaking / release not yet started)
t=18.478 → 18.853s:  ramping up (release, 400ms)
t=18.873 → 18.892s:  -22.00 dB  ← exact baseline, gain_db, reached
t=18.912 → 19.011s:  ramping down (attack, 120ms, anticipating beat4a's `at`)
t=19.030 → 19.129s:  -29.00 dB  (ducked again, beat4a now speaking)
```

**Peak in the gap: exactly −22.00 dB (`gain_db`). Mid-speech (beat 5's midpoint): exactly −29.00 dB
(`duck_db`). Delta: +7.00 dB — precisely `gain_db − duck_db`, the exact designed value.** The
envelope alternates correctly, for the first time this session, with zero new `stitcher` code —
confirming §6a/§6c's core hypothesis at the code level, not just in principle.

**One real, actionable refinement this surfaces:** at ~570ms, these gaps are only *just* wide enough
to touch true baseline for ~20–30ms before ducking back down — the mechanism works, but the audible
"breathe" moment is a brief flicker, not a sustained lift. If the goal is a *perceptible* bed lift
between beats (not just a mathematically-correct one), the inter-beat `<break>` durations tested in
Call 2 (0.4–0.6s requested, 0.45–0.7s actual) should likely be pushed longer — roughly ≥0.8–1.0s —
to give the release ramp room to finish and hold before the next attack ramp begins. This is now a
precisely tunable question, not a guess: `envelope.level_at()` against any candidate gap width
gives an exact answer with zero API spend.

A corrected comparison mix (`Final_Mix_SingleTake.wav`/`.mp3`) — single-take prosody, real per-beat
conditioning, and now-working ducking, unmodified original `gain_db`/`duck_db` — was produced and
delivered for a listen.

## 7. Decisions for the operator before any execution

1. **Fix the live 8.945s spec drift now** — independent of everything else above, not a decision,
   just needs doing.
2. **Give up per-beat re-roll?** Recommendation: no. You used it twice this session already (the hook
   and CTA takes) — exactly what the corpus says to re-roll. If you want it anyway, that's a
   legitimate `[P]` operator call, but should be recorded as one, overriding the corpus's stated
   position.
3. **Pause authored (via `<break>`) or measured (via trim)?** Recommendation: measured — more
   robust, model-agnostic, and what the recommended architecture is built on.
4. **Keep the door open to `eleven_v3`?** `<break>` tags only work on Multilingual v2/Flash;
   building the pipeline around them is a bet against ever moving to v3's audio-tag model.
5. **Adopt `previous_request_ids` chaining regardless of everything else?** Recommendation: yes,
   independent of all other decisions — cheap, already documented in this repo's own
   `elevenlabs-audio` skill, and likely explains the seam problem that motivated this whole proposal.
6. **Small housekeeping:** `.claude/skills/elevenlabs-audio/` currently documents only v3's
   bracketed `[pause]` tag, not the `<break time="Xs"/>` SSML tag that actually works on the model
   this channel uses. Worth a follow-up fix, dated `[T]`, with the model-support matrix.

## 8. Recommended next step

Run **Test 0 now** (zero cost, uses files already on disk) to settle the biggest open unknown
(silence-detection reliability) before spending anything. Then decide, based on its result and the
decisions in §7, whether to spend Calls 1–3 at all, or move straight to implementing the recommended
per-beat-plus-measurement architecture (which needs no new experiments to validate — it's provably
compatible with `stitcher` as-is, per §1).
