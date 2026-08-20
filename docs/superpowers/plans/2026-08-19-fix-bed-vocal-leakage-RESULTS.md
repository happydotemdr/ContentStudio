# Fix Results — Vocal Leakage in the Regenerated Music Beds

Executed against `2026-08-19-fix-bed-vocal-leakage.md`. Both new calls succeeded on the first attempt.

## Outcome

| Call | Mode | Result |
|---|---|---|
| Bed A v2 | `prompt` + `force_instrumental: true`, `music_v1` | ✅ 200, 15.073s (target ≥14.314s) |
| Bed B v2 | `prompt` + `force_instrumental: true`, `music_v1` | ✅ 200, 33.019s (target ≥31.697s) |

2 calls, both clean. The 9 voiceover calls from the prior run were untouched, per plan.

## Trim was simpler than the v1 fix required

Both `prompt`-mode generations happened to fade naturally right where the required cut point fell:
Bed A's fade-to-silence spans 12.257–15.073s (cut at 14.314s lands inside it); Bed B's spans
28.044–33.019s (cut at 31.697s lands inside it), and Bed B also opened with 2.15s of natural silence
before its riser — meaning a **plain front-trim** (`ffmpeg -t <target>`) was sufficient for both; the
crossfade splice the v1 fix needed wasn't necessary this time. `Bed Full_provoice_v2.wav` reassembled
to exactly 51.920000s.

## Delivered

- `BedA_provoice_v2.mp3`, `BedB_provoice_v2.mp3` — raw generations, sent to the user standalone for a
  clean listen isolated from the mix
- `Bed Full_provoice_v2.wav` — reassembled bed, same hold-out/pause structure as before
- `Final_Mix_Preview_provoice_v2.mp3` — full corrected mix, -14.3 LUFS integrated (target -14.0)

## Status: pending user listen-confirmation

Sent to the user for a direct listen — this is the one check that matters most given the prior
failure. Not marked resolved until confirmed clean.
