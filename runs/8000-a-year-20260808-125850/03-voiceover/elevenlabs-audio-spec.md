=== AUDIO PRODUCTION SPEC — 8000-a-year-club-soccer — DRAFT ===

Specialist output of `elevenlabs-audio`, pipeline mode. Creative call taken from the approved
`03-voiceover/artifact.v1.md` and NOT re-litigated. Markers: `[T]` web-verified 2026-07-26 ·
`[T-unverified]` asserted but unconfirmed · `[I]` general practice · `[C]` corpus-cited ·
`[P]` project/operator decision.

**Regenerated 2026-08-21 — supersedes the prior spec.** Two facts changed since the first pass:
the old voice_id `5kVvcrJnhhULT5LdbshJ` was deleted from ElevenLabs, and the operator pinned its
replacement plus a model-routing decision. See
`.claude/skills/voiceover-brief/references/channel-voice.md` for the record. Nothing about the
creative call (voice character, tone per beat, content type, −14 LUFS target) changed — only the
executable configuration below.

## CONTROL SURFACE

```
phase:          draft        (two-phase protocol is a hard default; master is gated on your
                              confirmation + Gate 3)
use_case:       shorts-vo    (inferred from the pipeline stage)
expressiveness: per-beat     (the brief supplies a per-beat table; not a single 1-5 dial)
voice:          eDwT8Vhp2yxJzAMmuuPA   (pinned channel voice, supplied -- Stage A skipped)
language:       en           (assumed)
length:         648 chars master / 383 chars draft
privacy:        standard     (assumed)
determinism:    on           (seed fixed on BOTH phases so draft iterations isolate the
                              parameter change rather than sampling variance [T])
```

**Assumed defaults, stated so you can correct them:** `language: en`, `privacy: standard`,
`use_case: shorts-vo`. Everything else came from the brief, the pinned-voice record, or you.

## VOICE PROFILE

```
voice_id:  eDwT8Vhp2yxJzAMmuuPA
type:      PVC — Professional Voice Clone of the operator's own voice [P]
persona:   channel owner's own voice (voiceover-brief's ranked-first choice)
```

**Both prior caveats are now resolved by an explicit operator decision** `[P]`
(`.claude/skills/voiceover-brief/references/channel-voice.md`, 2026-08-21):

1. ~~If this is a PVC, it is "not fully optimized for Eleven v3."~~ **Resolved: this voice never
   routes to `eleven_v3`.** It always routes to `eleven_multilingual_v2` for full PVC fidelity —
   not `use_pvc_as_ivc`, not v3-with-degraded-fidelity. This is a deliberate fidelity-over-tags
   trade the operator made explicitly, not a default.
2. ~~Tag effectiveness is bounded by the voice's training data; unproven against this voice.~~
   **Moot.** `eleven_multilingual_v2` does not render audio tags at all `[T]`, so there is nothing
   to probe. No v3 tag-probe phase in this run (contrast the prior spec, which had one).

**One caveat carried forward, still open** (`channel-voice.md` Open action 2): reference-audio
condition for this PVC hasn't been recorded. Noise in the reference is exactly what a high
`similarity_boost` reproduces faithfully `[T]` — if the render sounds noisy, that's the thing to
fix, not the setting.

## MODEL ROUTING

| Phase | `model_id` | Why |
|---|---|---|
| draft | `eleven_flash_v2_5` | 50% cheaper, 40k cap `[T]`; validates text/pacing/voice fit — hard default regardless of the master model `[I]` |
| master | `eleven_multilingual_v2` | **`[P]` operator decision**: full PVC fidelity over v3's tag repertoire. 10,000-char cap `[T]` |

Feature check: no audio tags in this script (routing precludes them), no inline IPA (not
supported on `eleven_multilingual_v2` `[T]` — see PRONUNCIATION), no `<phoneme>` (multilingual_v2
is alias-only `[T]`), single speaker, 648 chars ≪ 10,000 cap. Two `<break time="Xs" />` SSML tags
are used instead — these **are** supported on both `eleven_multilingual_v2` and
`eleven_flash_v2_5` `[T]` (unlike bracketed audio tags, which work only on `eleven_v3` and are
absent here by construction).

## VOICE SETTINGS

**The brief's per-beat stability floats now apply directly** — no mode conversion needed.
`eleven_multilingual_v2` takes stability as the native 0–1 float `[T]`, so the brief's 45–70%
per-beat range (previously discarded because v3 takes discrete modes instead) is restored,
mapped to a representative value per beat.

Two beats — Hook and Payoff — are each split into **two** chunks. The brief marked one moment in
each with a tag (`[whispers]` on "Why?", `[sighs]` before "Because…") that no longer exists on
this routing. Since tags are gone, the only lever left that can isolate *just that phrase* is a
separate request with its own settings — punctuation and a `<break>` carry the pause, and a lower
`style`/`speed` on that one chunk carries the hushed/released quality the tag used to carry `[I]`.

| Beat | `stability` | `similarity_boost` | `style` | `speed` | `use_speaker_boost` |
|---|---|---|---|---|---|
| Hook-A | 0.60 | 0.80 | 0.52 | 1.15 | true |
| Hook-B ("Why?" hold — replaces `[whispers]`) | 0.50 | 0.80 | 0.32 | 0.90 | true |
| Setup | 0.60 | 0.80 | 0.42 | 1.05 | true |
| Turn | 0.50 | 0.80 | 0.42 | 1.00 | true |
| Re-hook | 0.60 | 0.80 | 0.48 | 1.10 | true |
| Proof | 0.68 | 0.80 | 0.22 | 0.98 | true |
| Payoff-A | 0.50 | 0.80 | 0.45 | 0.94 | true |
| Payoff-B (release — replaces `[sighs]`) | 0.45 | 0.80 | 0.38 | 0.90 | true |
| Loop/CTA | 0.60 | 0.80 | 0.52 | 1.15 | true |

`similarity_boost` stays **fixed at 0.80 across every chunk** — it tracks the voice, not the
performance, and shouldn't move when expressiveness moves `[I]`.

**Seam-smoothing note.** Gate 2 flagged the Hook-A→Hook-B seam as the sharpest setting jump in
the job, and mid-beat rather than at a beat boundary — riskier than the Payoff-A→Payoff-B split,
which lands much smoother (stability Δ0.05, style Δ0.07, speed Δ0.04). Hook-B's values above are
already the moderated version (originally stability 0.45 / style 0.28 / speed 0.85); pulled
closer to Hook-A to reduce the audible-shift risk while still keeping the hold distinct.

## DIRECTORIAL SCRIPT

Nine sections across seven beats — per-beat settings *require* separate requests `[T]`, and the
two tag-replacement splits (Hook, Payoff) follow the same logic: an isolated bad take re-rolls one
short chunk, not the beat around it.

```
§1a HOOK-A      stability 0.60 · style 0.52 · speed 1.15
Eight grand a year on club soccer.

§1b HOOK-B      stability 0.50 · style 0.32 · speed 0.90
<break time="0.5s" /> Why?

§2 SETUP        stability 0.60 · style 0.42 · speed 1.05
Ask any club-soccer parent… and the real answer never comes out.

§3 TURN         stability 0.50 · style 0.42 · speed 1.00
Here's the psychologist Alfred add-ler, writing in nineteen twenty-seven. Nobody calls it
vanity. They call it ambition. Investing in her future.

§4 RE-HOOK      stability 0.60 · style 0.48 · speed 1.10
But here's what that story quietly costs.

§5 PROOF        stability 0.68 · style 0.22 · speed 0.98
In a twenty-nineteen study, Post and colleagues tracked the real bill. Thousands a year…
chasing a scholarship most kids never get.

§6a PAYOFF-A    stability 0.50 · style 0.45 · speed 0.94
So why can't you say why?

§6b PAYOFF-B    stability 0.45 · style 0.38 · speed 0.90
<break time="0.4s" /> Because that's what vanity sounds like from the inside. It was never
dishonesty. And naming it… makes it optional again.

§7 LOOP/CTA     stability 0.60 · style 0.52 · speed 1.15
Eight grand a year. Now you can say why.
```

**No bracketed audio tags anywhere** — `eleven_multilingual_v2` doesn't render them `[T]`, and the
draft/master use the same model family, so there's no version of this script where a tag would
survive. The two acoustic moments the brief flagged are instead carried by:
- Layer-1 punctuation and a `<break>` (structural pause) `[T]`, plus
- A dedicated low-`style`/sub-1.0-`speed` chunk for just that phrase `[I]`.

**Layer-1 check** `[I]`: the ellipses (§2, §5, §7's source line, §6b) are held beats independent of
the tag question. §6b's ellipsis before "makes it optional again" is the pause-before-the-big-line
the music brief pairs its bed `out` window to — unchanged by this regeneration.

**Respelling unchanged from the prior spec.** `add-ler` (lowercase, hard short A, stress on the
first syllable) — capitals were ruled out as a mispronunciation risk (read as acronym/volume
spike) `[T]`; `ahd-ler` was ruled out because it encodes the wrong vowel. Same text on draft and
master, so the draft still validates the respelling.

## PRONUNCIATION

**No dictionary needed; the escalation path changed.** "Adler" is handled by the in-text
respelling, which renders identically on Flash and Multilingual v2 (it's plain text, not a
phoneme mechanism, so it's model-agnostic `[I]`).

**If `add-ler` doesn't land, the prior spec's escalation — inline IPA `/ˈædlər/` — is no longer
available.** Inline IPA is `eleven_v3`-only `[T]`, and this voice never routes to v3. The
escalation on `eleven_multilingual_v2` is a PLS `<alias>` pronunciation dictionary entry instead
`[T]` (`<phoneme>` is also unavailable on this model — alias is the only pronunciation-control
mechanism it supports). Not needed yet; noted so the next person doesn't reach for IPA and hit a
dead end.

## REQUEST PAYLOAD — DRAFT (run this one)

383 chars covering the four beats actually in question: the Hook (both its punchy lead-in and the
"Why?" hold), the respelling, the flagged Proof line, and the Loop mirror. Both `<break>` tags are
**kept in the draft**, not stripped — unlike bracketed audio tags, SSML `<break>` is supported on
`eleven_flash_v2_5` too `[T]`, so the draft can validate the hold timing before any master spend,
not just text/pacing/voice fit.

One representative settings block is used for this single-request draft (per-beat precision isn't
the draft's job); `stability 0.55` / `style 0.40` / `speed 1.05` sit near the middle of the
per-beat table above.

Query: `?output_format=mp3_22050_32&enable_logging=true`

```json
{
  "text": "Eight grand a year on club soccer. <break time=\"0.5s\" /> Why?\n\nHere's the psychologist Alfred add-ler, writing in nineteen twenty-seven. Nobody calls it vanity. They call it ambition. Investing in her future.\n\nIn a twenty-nineteen study, Post and colleagues tracked the real bill. Thousands a year… chasing a scholarship most kids never get.\n\nEight grand a year. Now you can say why.",
  "model_id": "eleven_flash_v2_5",
  "voice_settings": {
    "stability": 0.55,
    "similarity_boost": 0.80,
    "style": 0.40,
    "speed": 1.05,
    "use_speaker_boost": true
  },
  "seed": 20260821,
  "apply_text_normalization": "auto"
}
```

```bash
curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA?output_format=mp3_22050_32&enable_logging=true" -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" -d @draft.json --output draft.mp3
```

## REQUEST PAYLOAD — MASTER (NOT YET AUTHORIZED — Gate 3 BLOCKED pending your draft confirmation)

Nine chunked requests, settings per the table above, stitched with `previous_text`/`next_text` on
every seam. This is the **first** master run for this voice_id, so there are no prior
`previous_request_ids` to anchor to yet; once each chunk actually renders, capture its
`request_id` and a second pass could re-stitch on `previous_request_ids` for stronger continuity
if a re-render is ever needed `[T]`.

Query (all 9 chunks): `?output_format=mp3_44100_192&enable_logging=true`

> **Tier gate, unresolved — flagged by Gate 2** `[T]`: `mp3_44100_192` requires **Creator tier or
> above**. This spec doesn't know your account tier. If it's below Creator, use `mp3_44100_128`
> (the ungated API default) for all 9 chunks instead. PCM/WAV at 44.1 kHz would need Pro+. Confirm
> your tier before running any master chunk.

```json
[
  {
    "text": "Eight grand a year on club soccer.",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.60, "similarity_boost": 0.80, "style": 0.52, "speed": 1.15, "use_speaker_boost": true},
    "seed": 20260821,
    "next_text": "Why?",
    "apply_text_normalization": "auto"
  },
  {
    "text": "<break time=\"0.5s\" /> Why?",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.32, "speed": 0.90, "use_speaker_boost": true},
    "seed": 20260821,
    "previous_text": "Eight grand a year on club soccer.",
    "next_text": "Ask any club-soccer parent",
    "apply_text_normalization": "auto"
  },
  {
    "text": "Ask any club-soccer parent… and the real answer never comes out.",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.60, "similarity_boost": 0.80, "style": 0.42, "speed": 1.05, "use_speaker_boost": true},
    "seed": 20260821,
    "previous_text": "Why?",
    "next_text": "Here's the psychologist Alfred add-ler",
    "apply_text_normalization": "auto"
  },
  {
    "text": "Here's the psychologist Alfred add-ler, writing in nineteen twenty-seven. Nobody calls it vanity. They call it ambition. Investing in her future.",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.42, "speed": 1.00, "use_speaker_boost": true},
    "seed": 20260821,
    "previous_text": "Ask any club-soccer parent… and the real answer never comes out.",
    "next_text": "But here's what that story quietly costs.",
    "apply_text_normalization": "auto"
  },
  {
    "text": "But here's what that story quietly costs.",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.60, "similarity_boost": 0.80, "style": 0.48, "speed": 1.10, "use_speaker_boost": true},
    "seed": 20260821,
    "previous_text": "Investing in her future.",
    "next_text": "In a twenty-nineteen study, Post and colleagues",
    "apply_text_normalization": "auto"
  },
  {
    "text": "In a twenty-nineteen study, Post and colleagues tracked the real bill. Thousands a year… chasing a scholarship most kids never get.",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.68, "similarity_boost": 0.80, "style": 0.22, "speed": 0.98, "use_speaker_boost": true},
    "seed": 20260821,
    "previous_text": "But here's what that story quietly costs.",
    "next_text": "So why can't you say why?",
    "apply_text_normalization": "auto"
  },
  {
    "text": "So why can't you say why?",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.45, "speed": 0.94, "use_speaker_boost": true},
    "seed": 20260821,
    "previous_text": "chasing a scholarship most kids never get.",
    "next_text": "Because that's what vanity sounds like from the inside.",
    "apply_text_normalization": "auto"
  },
  {
    "text": "<break time=\"0.4s\" /> Because that's what vanity sounds like from the inside. It was never dishonesty. And naming it… makes it optional again.",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.45, "similarity_boost": 0.80, "style": 0.38, "speed": 0.90, "use_speaker_boost": true},
    "seed": 20260821,
    "previous_text": "So why can't you say why?",
    "next_text": "Eight grand a year. Now you can say why.",
    "apply_text_normalization": "auto"
  },
  {
    "text": "Eight grand a year. Now you can say why.",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.60, "similarity_boost": 0.80, "style": 0.52, "speed": 1.15, "use_speaker_boost": true},
    "seed": 20260821,
    "previous_text": "And naming it… makes it optional again.",
    "apply_text_normalization": "auto"
  }
]
```

```bash
# Run once per chunk, in order, each with its own JSON body (chunk-1.json … chunk-9.json)
curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA?output_format=mp3_44100_192&enable_logging=true" -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" -d @chunk-1.json --output chunk-1.mp3
```

## COST

```
Draft:  383 chars x Flash rate (50% discount)   ~ $0.019
Master: 648 chars x standard rate               ~ $0.065
                                                  ────────
Full path, one master, no re-rolls              ~ $0.084

Basis:  per input character, incl. spaces & punctuation, and SSML <break> tags count as
        text characters [T]
        ~$0.05 / 1,000 chars on Flash; standard is 2x that [T]
Note:   every API call is billed -- the two free regenerations are WEBSITE ONLY and
        explicitly unavailable via the API [T]
Re-roll budget: 3 chunk re-rolls (~$0.02). Nothing here uses v3 Creative mode, so the
        "prone to hallucinations" re-roll requirement doesn't apply [T]. The brief asks for
        2-3 takes of the Hook and Loop specifically -- those four chunks (1a/1b/7) are 100
        chars combined, so three extra takes is ~$0.015.
```

This run is **cheaper than the prior voice's spec** (~$0.084 vs. ~$0.101) despite splitting into
9 chunks instead of 7 — the removed v3 tag-probe phase (~$0.021) more than covers the two extra
chunk seams.

**Free re-rolls, if you want them:** tune sliders in the **web UI**, where the two free
regenerations survive voice-settings changes `[T]`, then port the settled values into these
payloads.

## STEM CONDITIONING — required before the stitcher will render

Unchanged by the voice/model switch — this is a renderer-side requirement, not an ElevenLabs one.
The stitcher requires loudnorm to resolve **linearly**, which needs the mix's peak-to-loudness
ratio inside `target_i - target_tp` = **12.5 dB** at −14 LUFS / −1.5 dBTP. Raw ElevenLabs stems on
the previous Short measured **18.2 dB** and the render was refused (exit 2). There is **no
compressor or limiter stage in the render spec**
(`docs/superpowers/specs/2026-08-07-stitcher-capability-boundary.md` §1), so this happens to the
files before they arrive.

Two things that do **not** work, both measured rather than assumed:

- **Lowering the true-peak target.** It shrinks the budget. loudnorm just applies less gain and
  PLR is unchanged — 12.9 dB whether the ceiling was −3 or −6 dBTP.
- **A limiter alone.** `alimiter` caps *sample* peak while loudnorm measures *true* peak
  (~1.2 dB inter-sample overshoot here), and every 1 dB of ceiling costs ~0.55 dB of integrated
  loudness — ~0.45 dB of real headroom per dB.

Compression is what actually lowers PLR. Per stem, in order:

```
1. acompressor=threshold=-20dB:ratio=3:attack=5:release=120
2. volume=<gain>dB          # solved AFTER compression, to -14 LUFS integrated
3. alimiter=limit=0.5623:attack=5:release=50:level=disabled     # -5 dBFS ceiling
```

Measured result on the previous Short: PLR 18.2 → **~10.5 dB**, and stage C resolved linear on
the first attempt. Script: `scratchpad/prep_vo.py` — hand me the stems and I will run it.

## QC CHECKLIST

| Listen for | Likely cause | Fix |
|---|---|---|
| "add-ler" read as letters or shouted | caps/acronym artifact returning | escalate to a PLS `<alias>` dictionary entry — inline IPA is **not** an option on this routing `[T]` |
| "Post" heard as a common noun | bare surname in a noun slot | see Gate 1 finding 2 (below) — decision pending, same open item as before |
| Hook-B / Payoff-B don't read as a held pause or release | `<break>` duration too short, or the seam settings snapped back too hard | try `0.6–0.8s`; re-check the Hook-A→Hook-B seam settings gap first (Gate 2 flagged it as the sharpest in the job) |
| Slurring, vocal fry, wild swings | `stability` too low | raise it |
| Flat, monotone | `stability` too high | lower it; raise `style` |
| Metallic / hissy edge | `similarity_boost` too high, over-fitting reference noise | lower toward 0.75; fix the reference audio `[T-unverified]` — still unrecorded, see VOICE PROFILE |
| Cadence drop at a section seam | missing stitching context | every chunk above already carries `previous_text`/`next_text` |
| Numbers read oddly in the draft | **Flash artifact, not a script defect** `[T]` | re-check on `eleven_multilingual_v2` before changing the script |
| `<break>` duration feels off vs. what was requested | ElevenLabs breaks run long by ~50–210ms in practice, undocumented guarantee `[T]` | confirm actual timing via `/with-timestamps` if this pause needs to hit a specific frame for the stitcher's `out` window |

Check the two free things first `[I]`: is the model right, and is the text the problem? Both
are free; a settings change costs a render.

## VALIDATION GATES

```
Gate 1 (script & tag): PASS — 0 findings across all 13 items (fresh-agent dispatch, 2026-08-21).
  One non-checklist observation: the "add-ler" respelling's correctness isn't covered by any
  checklist item — noted, not a finding.
Gate 2 (payload):      1 FINDING, 1 addressed:
  · Item 10 — mp3_44100_192 tier requirement unflagged in the spec — RESOLVED: tier-gate note
    added above the master payload (mp3_44100_128 fallback named).
  · Item 18 (advisory, not a strict finding) — Hook-A→Hook-B seam was the sharpest setting jump
    in the job, landing mid-beat — ADDRESSED: Hook-B settings moderated (stability 0.45→0.50,
    style 0.28→0.32, speed 0.85→0.90) to narrow the gap while keeping the hold distinct.
Gate 3 (spend):        BLOCKED — no draft has been run or confirmed yet; fires again once you
                        confirm the draft direction.
```

**Gate 1 item 12 from the prior spec, still open, unchanged by this regeneration.** "In a
twenty-nineteen study, Post and colleagues tracked the real bill." reads as a written citation;
"Post" is a bare surname in a noun slot. The gate's proposed rewrite would drop the surname, but
naming the source is a survives-to-publish constraint from the grounding brief — rewriting it here
would re-litigate `shorts-scripting`'s already-gated output. Same three options as before, still
yours to pick:

1. **Accept as-is, mitigated by design.** Overlay O8 (`Post, Rosenthal & Rauh 2019 · Sports
   7(12):247`) is on screen at ~19–28s, exactly under this line. **Recommended.**
2. **Add a first name** — needs verification of the author's given name first.
3. **Send it back to `shorts-scripting`** for a v2 script, which re-runs its own gates.

## NEXT

**SUPERSEDED 2026-08-21.** Everything below this line described the chunked-master path
(9 separately-generated `eleven_multilingual_v2` beats, individually conditioned to −14 LUFS,
then concatenated into `vo_full.wav`) as the shipped voiceover. It is kept as dated history —
none of those files (`draft.mp3`, `draft2.mp3`, `chunk-1.mp3` … `chunk-9.mp3`,
`chunk-N-conditioned.wav`, `vo_full.wav`/`vo_full.mp3`, `condition_log.txt`) are deleted — but
none of them is the run's VO stem any longer. Two later same-day experiments
(`v3single/full.mp3`, `v3single/full_pause.mp3` and the `v3tags/`, `speedtest-*` comparison
renders) tested `eleven_v3` + bracket-tag alternatives ad hoc, outside the real pipeline tooling;
those are also kept as history and also superseded.

**This run's voiceover is now a single continuous `eleven_v3` take with bracket audio tags,**
generated for real through `elevenlabs_tooling generate-vo` (Task 6 of
`docs/superpowers/plans/2026-08-21-v3-tags-native-pipeline-adoption.md`) — the `full_pause`
script variant (3 emotional tags plus `[pause]` at 4 structural breaks), split into 7 paragraphs
rather than the original 9-beat breakdown (several original beats merge into continuous prose
with no blank-line break between them in the approved script).

**Deliverables, superseding everything above:**

- `native/payload.json` — the exact request body sent (`model_id: eleven_v3`, `seed: 20260821`,
  `use_pvc_as_ivc: false` — see the payload for the full `voice_settings` block).
- `native/vo_beat_texts.json` — the 7 per-paragraph strings `derive_segments_v3` used to recover
  segment boundaries (no `<break>` marker exists on v3 to split on instead).
- `native/single_take.mp3` — the shipped VO stem. HTTP 200, 794,584 bytes.
- `native/alignment.json` — the `/with-timestamps` character-level alignment the take's own
  segment timing is derived from.
- `vo_segments.json` — the run's new source-of-truth timing artifact: 7 segments
  (`hook`/`setup`/`turn`/`cost`/`proof`/`payoff`/`loopcta`), `at`/`duration` in seconds, derived
  from `alignment.json` via `stitcher.vo_alignment.derive_segments_v3`. This is what
  `shorts-assembly` and `music-brief` should read for this run going forward.

**Per-beat conditioning is deliberately NOT applied to `single_take.mp3`.** The native
single-generation render mode (see `native-pipeline/README.md` and this plan's Global
Constraints) does no VO processing at all — no `precondition.condition_clip()`, no per-beat
split, no loudnorm pass. The raw take is final as delivered by the API. Its loudness was
*measured*, not modified: `stitcher.ffmpeg.measure_loudness` reports **−22.3 LUFS integrated /
−1.1 dBTP true peak / 8.0 LU loudness range** on the raw file — well under the −14 LUFS target
by design, since no normalization has been applied. Bringing it to target is `shorts-assembly`'s
stage to run (its own `build_audio()` two-pass loudnorm), same division of responsibility as
before; this spec only reports the raw, unmodified number so that stage isn't guessing.

**Real generation spend: ~$0.065–0.08** (677-character `eleven_v3` take with bracket tags,
`/with-timestamps`; the API response itself does not report a per-call credit/cost figure, so
this is the same character-count-based estimate the operator confirmed before authorizing the
run — consistent with this session's two earlier same-length `v3single/` test renders).
