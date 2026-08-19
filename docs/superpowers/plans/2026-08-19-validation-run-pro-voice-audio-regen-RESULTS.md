# Validation Run Results — Pro-Voice Audio Regen

Executed against the plan at `2026-08-19-validation-run-pro-voice-audio-regen.md`. All decisions in
that plan's §2 were approved as-defaulted by the user before execution. This file records what actually
happened — the plan's `assets/provoice-2026-08-19/` outputs are git-ignored local files (per repo
convention) and are not part of this commit; this report is.

## Outcome: the mechanism works

All **11 of 11** `elevenlabs_tooling send` calls succeeded on the first attempt — `EXIT_PASS`,
`status_code: 200`, `content_type: audio/mpeg` every time. Zero retries, zero failures, zero wasted
spend. `use_pvc_as_ivc: false` against the new PVC voice (`eDwT8Vhp2yxJzAMmuuPA`) validated clean
(E7 fired correctly during pre-flight `validate` and required the explicit field, exactly as designed)
and sent clean.

| Call | Payload | Result |
|---|---|---|
| VO1 (Hook) + take 2 | text-to-speech | ✅ both, 200 |
| VO2 (Setup) | text-to-speech | ✅ 200 |
| VO3 (Build-mechanism) | text-to-speech | ✅ 200 |
| VO4 (Re-hook) | text-to-speech | ✅ 200 |
| VO5 (Build-proof) | text-to-speech | ✅ 200 |
| VO6 (Payoff) | text-to-speech | ✅ 200 |
| VO7 (Loop/CTA) + take 2 | text-to-speech | ✅ both, 200 |
| Bed A | music/compose | ✅ 200, 20.01s (target ~19.9s) |
| Bed B | music/compose | ✅ 200, 41.33s (target ~41.2s) |

## The predicted timing drift was real, and larger than expected

| Beat | Old (IVC) duration | New (PVC) duration, take 1 | Delta |
|---|---:|---:|---:|
| VO1 Hook | 5.642s | 5.200s | -7.8% |
| VO2 Setup | 6.426s | 5.600s | -12.9% |
| VO3 Mechanism | 7.549s | 5.440s | **-27.9%** |
| VO4 Re-hook | 5.956s | 6.320s | +6.1% |
| VO5 Proof | 15.073s | 13.280s | -11.9% |
| VO6 Payoff | 14.028s | 10.640s | **-24.2%** |
| VO7 Loop/CTA | 6.191s | 5.440s | -12.1% |
| **Total** | **60.865s** | **51.920s** | **-14.7%** |

The new PVC voice reads noticeably faster than the retired IVC across most beats (VO3 and VO6 especially)
— this is the single most important finding of this run. **`render-spec.json`'s shot cuts, overlay
timestamps, and captions were built by measuring the old voice; none of them are valid against this new
audio without a re-cut.** That re-cut is explicitly out of scope for this run (plan §8) — this is a
finding to act on, not a problem this run tried to fix.

## An assembly bug found and fixed during reconciliation (free, no re-spend)

The plan's Bed B composition plan was sized generously (~41.2s) against the *old* 60.865s timeline's
worst-case pause placement. On the new, ~9s-shorter 51.92s timeline, only ~31.7s of runway remained for
the "post-pause" bed region — straightforwardly using the first 31.7s of the generated Bed B track would
have covered the riser-out-of-silence opening but **cut off before Bed B's own loop-close fade**, breaking
the seamless-loop design the music brief calls for. Caught by listening to the structure (`ffmpeg
silencedetect` on the raw generated file), fixed with a 1-second crossfade splice that keeps both the
opening riser (first ~26.7s) and the closing fade (last ~6s), dropping only some of the middle "relief"
section. Zero additional API cost — this is exactly the kind of free, local, repeatable fix the plan's
non-destructive design was built to allow.

## Deliverables (local, git-ignored, under `assets/provoice-2026-08-19/`)

- 9 raw VO takes (`VO1_provoice.mp3` … `VO7_provoice.mp3`, plus `_take2` re-rolls for Hook and CTA) +
  their `_prepped.wav` conversions
- `BedA_provoice.mp3`, `BedB_provoice.mp3` (raw generations) and `BedB_provoice_spliced.wav` (the
  loop-close-preserving fix)
- `Bed Full_provoice.wav` — the complete new bed, hold-outs baked in, sized to the new 51.92s timeline
- `VO_assembled_provoice.wav` — all 7 new VO clips concatenated back-to-back (take 1 for Hook/CTA)
- `Final_Mix_Preview_provoice.mp3` — the full mixed preview: normalized VO + gain-conformed, ducked-style
  bed, 2-pass loudnorm'd to -14.3 LUFS integrated (target -14.0) — sent to the user for a listen
- `payloads/` — the exact 11 JSON payloads sent, plus `_manifest.json`

## Explicitly not done (per plan §8, unchanged)

- `render-spec.json` shot timings, `audio.stems[].at` offsets, captions, and overlays are untouched.
- No new `.mp4` was rendered.
- No pick has been made yet between VO1/VO7 take 1 vs. take 2 — both are delivered; that's a listening
  call for the user.
- Nothing was copied over the original `assets/` files — this run is fully additive and reversible.

## Recommended next step

Listen to `Final_Mix_Preview_provoice.mp3` and the two CTA/Hook takes. If the voice and beds are approved,
the next decision is whether to invest in a full re-cut (new `render-spec.json` shot timings + captions +
overlays sized to the new 51.92s timeline) — a separate, free, non-API-spending piece of work this report
sets up but does not start.
