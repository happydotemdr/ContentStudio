# Implementation Results — Single-Take VO Pipeline, Real End-to-End Validation

Executed against `2026-08-19-single-take-vo-pipeline-implementation.md` Task 11: **one real,
billed ElevenLabs API call** (`eleven_multilingual_v2`, 956-character break-tagged payload, the
pinned channel narrator voice `eDwT8Vhp2yxJzAMmuuPA`, `/with-timestamps`), followed by a fully
local run of the new single-take VO pipeline — `elevenlabs_tooling.breaks.compose_break_tagged_text`
(Task 1), `stitcher.vo_alignment.derive_segments` (Task 4), `stitcher.vo_split.split_segments`
(Task 5), `stitcher.vo_timing.derive_captions` (Task 6), `stitcher.vo_assemble.build_audio_config`
(Task 7), and the existing, unmodified `stitcher.precondition.condition_clip` /
`stitcher.audio.build_audio`. No other network calls, no additional spend.

Run with two throwaway scripts, neither committed:
- `elevenlabs-tooling/compose_payload.py` — composed the payload, imports only
  `elevenlabs_tooling`. Deleted after Step 2 ran; never staged.
- `stitcher/renders/stop-over-specialization-in-youth-sports-20260811-004711/validate_single_take_pipeline.py`
  — the harness, imports only `stitcher`. Lives under `stitcher/renders/`, excluded wholesale by
  `.gitignore:43`, never staged.

The API call: exit code 0, HTTP 200, 1,468,334 audio bytes written to `single_take.mp3` (19,608-byte
`alignment.json` alongside it), both landing at the exact absolute `RENDER_DIR` paths Step 1 wrote
`payload.json` to.

## Outcome

All 5 success criteria passed on the first harness run, in order, with no `AssertionError` and no
exception of any kind.

| Criterion | Result |
|---|---|
| 1–2: `build_audio()` raises no exception; `loudnorm.normalization_type == "linear"` | PASS |
| 3: independent re-measurement of the written mix within tolerance | PASS |
| 4: mean per-clip LRA loss ≤ 1.2 LU | PASS — **0.77 LU** |
| 5: ducking envelope reaches true baseline in every real inter-beat gap | PASS — all 7 gaps at exactly **+7.00 dB** delta (expected `BED_GAIN_DB - BED_DUCK_DB` = -22.0 − (−29.0) = +7.0) |

## Derived segments (from real alignment data, Task 4)

```
beat1:  at=0.000  duration=5.074
beat2:  at=6.037  duration=6.339
beat3:  at=13.224 duration=6.362
beat4a: at=20.573 duration=1.196
beat4b: at=23.197 duration=3.994
beat5:  at=28.201 duration=14.512
beat6:  at=43.700 duration=11.273
beat7:  at=56.041 duration=5.073
```

Total runtime: **61.114s**.

## Per-clip conditioning measurements (real ffmpeg loudnorm, captured verbatim from stdout)

| Clip | Input (I / TP / LRA) | Output (I / TP / LRA) | Limited | Peak reduction (dB) |
|---|---|---|---|---|
| beat1 | -24.5 / -9.2 / 1.9 | -14.1 / -2.4 / 1.9 | True | 4.30 |
| beat2 | -22.1 / -4.4 / 2.5 | -14.3 / -2.5 / 2.0 | True | 7.30 |
| beat3 | -22.6 / -6.6 / 2.0 | -14.3 / -2.5 / 1.5 | True | 5.30 |
| beat4a | -25.0 / -9.0 / 0.0 | -14.0 / -2.5 / 0.0 | True | 4.90 |
| beat4b | -22.4 / -5.9 / 1.4 | -14.1 / -2.4 / 1.1 | True | 6.50 |
| beat5 | -22.4 / -4.7 / 5.3 | -14.2 / -2.4 / 2.5 | True | 7.90 |
| beat6 | -23.7 / -5.6 / 4.2 | -14.1 / -2.5 / 2.4 | True | 8.30 |
| beat7 | -25.2 / -8.2 / 2.3 | -14.2 / -2.5 / 2.0 | True | 6.20 |

All 8 segments (7 sentence beats plus the split beat4a/beat4b) required limiting.

Bed source reused from this session's earlier preconditioning work (no new conditioning spend):
`_precondition_validation_duckfix/run/assets/BedFull_provoice_conditioned.wav`.

## Per-clip LRA loss (criterion 4 detail)

```
beat1: 0.0    beat2: 0.5    beat3: 0.5    beat4a: 0.0
beat4b: 0.3   beat5: 2.8    beat6: 1.8    beat7: 0.3
```

Mean: **0.77 LU** (gate ≤ 1.2 LU). beat5 (2.8) and beat6 (1.8) show the largest individual losses —
both are the longest segments (14.512s and 11.273s respectively), consistent with loudnorm's LRA
estimate being more volatile over longer single-pass windows; the mean still clears the gate
comfortably.

## Independent re-measurement of the delivered mix (criterion 3)

```
{'input_i': -13.9, 'input_tp': -2.0, 'input_lra': 3.6}
```

Target: -14.0 LUFS integrated (within 0.5 LU — actual delta 0.1), ≤ -1.0 dBTP true peak (actual
-2.0, well under). Both within tolerance.

## Ducking envelope check (criterion 5 detail — new for this plan)

Queried the real `envelope.level_at`/`build_breakpoints`/`stem_spans` math directly against every
real inter-beat gap (not just the widest), same method as the free follow-up test in
`docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md` §6c. Mid-speech reference level:
**-29.00 dB** (sampled at the middle of beat7).

```
gap 5.074–6.037s   (width 0.963s): peak -22.00 dB, delta +7.00 dB
gap 12.376–13.224s (width 0.848s): peak -22.00 dB, delta +7.00 dB
gap 19.586–20.573s (width 0.987s): peak -22.00 dB, delta +7.00 dB
gap 21.769–23.197s (width 1.428s): peak -22.00 dB, delta +7.00 dB
gap 27.191–28.201s (width 1.010s): peak -22.00 dB, delta +7.00 dB
gap 42.713–43.700s (width 0.987s): peak -22.00 dB, delta +7.00 dB
gap 54.973–56.041s (width 1.068s): peak -22.00 dB, delta +7.00 dB
```

Every one of the 7 real gaps — even the narrowest (12.376–13.224s, 0.848s wide) — reaches the exact
expected baseline delta of +7.00 dB (`BED_GAIN_DB - BED_DUCK_DB` = -22.0 − (−29.0)). This is the
refined break-duration fix (50–210ms overshoot + 520ms attack/release clearance built into the
0.8–1.3s `BREAK_SECONDS` used in Step 1) verified against real data, not simulated.

## Captions (exact, derived from measured segments — Task 6)

```
(0.000, 5.074,   "The oldest warning about pushi")
(6.037, 12.376,  "Aristotle watched the ancient ")
(13.224, 19.586, "He blamed the early training. ")
(20.573, 21.769, "Here's the strange part.")
(23.197, 27.191, "Jump forward 2,300 years — and")
(28.201, 42.713, "Chundi and colleagues followed")
(43.700, 54.973, "So the kid who plays everythin")
(56.041, 61.114, "That 2,300-year-old warning? T")
```

Every caption span exactly matches its segment's derived duration (asserted in the harness before
`build_audio()` ran at all) — this is the fix for the render-spec timing drift bug found earlier
this session.

## Deliverables

- `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\assets\provoice-2026-08-19\Final_Mix_SingleTakePipeline.wav` — 11,733,966 bytes (pcm_s16le, 48kHz, stereo, 61.114s)
- `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\assets\provoice-2026-08-19\Final_Mix_SingleTakePipeline.mp3` — 1,468,268 bytes (libmp3lame 192kbps, 48kHz, stereo, 61.114s)

Both written by the harness itself (WAV copied from `build_audio()`'s output mix; MP3 encoded from
it at `libmp3lame -b:a 192k`), not hand-assembled. Confirmed valid audio via `ffprobe` (format,
duration, sample rate, channel count all as expected).

## Step 4 — listening comparison: what could and could not be checked

The subagent that ran this validation cannot listen to audio, so no by-ear judgment is asserted
here. What was verified instead:

- Both deliverable files exist at the documented paths and are valid, playable audio (`ffprobe`
  confirms codec, duration, sample rate, channel count for both).
- `assets/provoice-2026-08-19/Final_Mix_Preconditioned_DuckFix.wav` (the per-beat baseline named in
  the brief) **is present** on disk — 9,968,718 bytes, pcm_s16le, 48kHz, stereo, 51.920s.
- `Final_Mix_SingleTake.mp3` (this session's earlier manually-assembled single-take proof-of-concept,
  also named in the brief as a comparison target) was searched for across the entire
  `stitcher/renders/` tree and **was not found anywhere** — it does not exist in this worktree.
  Only two files are actually available for the by-ear comparison the brief describes:
  `Final_Mix_SingleTakePipeline.mp3` (this run's output) and `Final_Mix_Preconditioned_DuckFix.wav`
  (the per-beat baseline).

The actual determination — single-take prosody retained, bed audibly breathing in the gaps (not
just mathematically, per the envelope-math check above), no clipping or leveling artifacts — is
deferred to the user's own listen.

## Status: pending user listen-confirmation

The pipeline ran clean end-to-end and every automated gate passed, including the new ducking
baseline check (criterion 5) that the prior preconditioning-only plan could not exercise without a
real single-take alignment. Nobody has listened to `Final_Mix_SingleTakePipeline.mp3`/`.wav` yet,
and `Final_Mix_SingleTake.mp3` (one of the two comparison files the brief named) is not present in
this worktree to compare against — only `Final_Mix_Preconditioned_DuckFix.wav` is. That ear-check
is the determination that actually matters and is not this report's to make. Not marked resolved
until the user confirms by ear.
