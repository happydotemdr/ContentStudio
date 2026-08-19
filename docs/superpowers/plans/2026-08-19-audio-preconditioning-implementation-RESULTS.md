# Implementation Results — Audio Preconditioning, Real End-to-End Validation

Executed against `2026-08-19-audio-preconditioning-implementation.md` Task 5: a real, unmocked run
of `stitcher.precondition.condition_clip` against the 9 raw source files for
`stop-over-specialization-in-youth-sports-20260811-004711`, feeding the result into the real,
unmodified `stitcher.audio.build_audio()`. No network calls, no ElevenLabs spend, no modification
to `audio.py`/`spec.py`/`envelope.py`/`naming.py`/`ffmpeg.py`.

Run with the throwaway harness `validate_precondition.py` (not committed — lives under
`stitcher/renders/...`, excluded wholesale by `.gitignore:43`). One deviation from the plan's
literal script text: the `sys.path.insert` target was corrected from a stale path
(`...\contentstudio-stitcher-first-short-33bc3c\stitcher`, a different, unrelated worktree without
`precondition.py`) to this worktree's own `stitcher` package
(`C:\Projects\ContentStudio\.claude\worktrees\elevenlabs-tooling-impl\stitcher`). No other code in
the harness was changed.

## Outcome

All 5 success criteria (spec §5) passed on the first run, in order, with no `AssertionError` and no
`PreconditionError`/`LoudnormNotLinearError` raised.

| Criterion | Result |
|---|---|
| 1–2: `build_audio()` raises no exception; `loudnorm.normalization_type == "linear"` | PASS |
| 3: independent re-measurement of the written mix within tolerance | PASS |
| 4: mean per-clip LRA loss ≤ 1.2 LU | PASS — **0.93 LU** |
| 5: every clip's conditioned integrated loudness within `LUFS_TOLERANCE` (0.35 LU) of -14.0 | PASS |

## Per-clip conditioning measurements (real ffmpeg loudnorm, captured verbatim from stdout)

| Clip | Input (I / TP / LRA) | Output (I / TP / LRA) | Limited | Peak reduction (dB) |
|---|---|---|---|---|
| vo1 | -23.5 / -3.2 / 3.8 | -14.3 / -2.5 / 2.6 | True | 9.90 |
| vo2 | -22.9 / -1.7 / 4.3 | -14.2 / -2.5 / 1.6 | True | 11.50 |
| vo3 | -19.9 / -1.2 / 0.7 | -14.3 / -2.4 / 0.9 | True | 7.90 |
| vo4 | -23.8 / -1.5 / 3.7 | -14.3 / -2.5 / 2.5 | True | 12.10 |
| vo5 | -21.8 / -0.6 / 5.5 | -14.2 / -2.5 / 3.0 | True | 11.70 |
| vo6 | -23.8 / -3.2 / 2.0 | -14.3 / -2.5 / 1.1 | True | 10.10 |
| vo7 | -25.3 / -6.0 / 1.4 | -14.1 / -2.5 / 1.5 | True | 8.20 |
| BedA | -15.6 / -1.3 / 23.3 | -14.2 / -2.5 / 23.1 | — | — |
| BedB | -12.1 / -2.9 / 14.2 | -14.0 / -4.8 / 14.2 | — | — |

All 7 VO clips required limiting (true peak above -2.5 dBTP pre-conditioning); both beds did not
(the harness's `condition_clip` call reports `limited`/`peak_reduction_db` only for VO stems in this
harness's print statements — beds print input/output measurement only).

`BedFull_provoice_conditioned.wav` assembled to **53.241750s** against a runtime of 51.92s (silence
prepend + BedA trimmed to 15.022948s + BedB in full — no crossfade engineering, per spec §4.5).

## Per-clip LRA loss (criterion 4 detail)

```
vo1: 1.20    vo2: 2.70    vo3: -0.20    vo4: 1.20    vo5: 2.50
vo6: 0.90    vo7: -0.10   BedA: 0.20    BedB: 0.00
```

Mean: **0.93 LU** (gate ≤ 1.2 LU). vo3 and vo7 show small *negative* loss (LRA increased slightly
after conditioning) — not a concern, within measurement noise of ffmpeg's `loudnorm` single-pass
LRA estimate.

**Note on divergence from the design spec's prose:** the design spec (§5, an earlier exploratory
pass) reports a max per-clip LRA loss of ~2.5–2.7 LU attributed to **vo5**. This run's actual max
loss (2.70 LU) belongs to **vo2**, not vo5 (vo5 came in at 2.50 LU, the second-highest). The mean
(0.93 LU) is close to but not identical to the spec's quoted 0.89/0.94 LU range. Reporting this
plainly per the brief's Step 5 instruction rather than reconciling it — it does not affect the
pass/fail outcome (mean is still well under the 1.2 LU gate either way).

## Independent re-measurement of the delivered mix (criterion 3)

```
{'input_i': -13.9, 'input_tp': -2.0, 'input_lra': 2.5}
```

Target: -14.0 LUFS integrated (within 0.5 LU — actual delta 0.1), ≤ -1.0 dBTP true peak (actual
-2.0, well under). Both within tolerance.

## Deliverables

- `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\assets\provoice-2026-08-19\Final_Mix_Preconditioned.wav` — 9,968,718 bytes
- `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\assets\provoice-2026-08-19\Final_Mix_Preconditioned.mp3` — 1,247,660 bytes

Both written by the harness itself (WAV copied from `build_audio()`'s output mix; MP3 encoded from
it at `libmp3lame -b:a 192k`), not hand-assembled.

## Status: pending user listen-confirmation

The pipeline ran clean end-to-end and every automated gate in spec §5 passed, but nobody has
listened to `Final_Mix_Preconditioned.mp3`/`.wav` yet. Per spec §5 Step 4 (leveling/pumping,
clipping/harshness, the masked re-hook pause at 19.514331s–20.222948s, BedB's riser emerging from
the fade at 20.222948s), that ear-check is the determination that actually matters and is not this
report's to make. Not marked resolved until the user confirms by ear.
