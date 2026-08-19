# Audio Preconditioning for `stitcher` — Design Spec

**Status:** Draft, pending user review.
**Scope:** Fix the leveling/clipping defect diagnosed in the pro-voice audio validation run (see
`docs/superpowers/plans/2026-08-19-validation-run-pro-voice-audio-regen.md` and the Opus review that
followed it). Audio-only. Does not touch shot timing, captions, overlays, or produce a video render.

---

## 1. Problem statement

Two independent, root-caused defects were found in the ad hoc local reconciliation pipeline used to
regenerate this Short's audio with a new narrator voice:

1. **Beat-to-beat level inconsistency.** The *original* (pre-session) asset-prep step silently applied
   ~5 dB of per-clip loudness conforming, landing every old VO beat within 0.26 LU of a consistent
   target. That step was never documented in the repo. The new run's "prep" (documented as
   format-conversion-only) did not reproduce it, producing a 4.1 LU spread in level between beats.
2. **Dynamic-range collapse from cascaded `loudnorm` passes.** The ad hoc pipeline ran `ffmpeg loudnorm`
   twice (once "normalizing" the assembled VO, once on the final mix). `loudnorm`'s dynamic mode is an
   adaptive gain rider, not a static normalizer — measured gain swung from +0.46 dB to +9.41 dB across
   one take. Loudness range (LRA) collapsed from 6.10 LU (raw) to 3.00 LU to 2.50 LU (final). This is
   the audible "leveling and clipping."

Critically: `stitcher` — this repo's actual tested render tool — already has a gate designed to catch
exactly this failure (`audio.py`'s `linear=true` two-pass `loudnorm` check, raising
`LoudnormNotLinearError` if pass 2 can't stay in linear mode). Running `stitcher`'s conform/duck/mix math
by hand, outside the CLI, bypassed that gate. Verified directly: replaying `stitcher`'s real two-pass
loudnorm against the new raw voiceover produces `"normalization_type": "dynamic"` — the exact condition
the gate exists to refuse. The new voice's peak-to-loudness ratio (PLR) is measured at ~21 dB; reaching
−14 LUFS integrated with any sane true-peak ceiling by static gain alone requires PLR ≤ ~13 dB. Gain
cannot supply that — only actual peak reduction can.

## 2. Goals

- Produce a corrected audio mix (voiceover + music bed) for the already-generated new-voice assets that
  a human can listen to and confirm the leveling/clipping is gone.
- Do this by adding a real, tested capability to `stitcher` — not another ad hoc script — so the same
  fix applies automatically to every future render, including the next voice swap.
- Preserve narration dynamics (LRA) rather than collapsing them.
- Route the actual render-time mixing math through `stitcher`'s existing, gated `build_audio()` — don't
  reimplement it a second time.

## 3. Non-goals

- Re-cutting `render-spec.json`'s shot timings, captions, or overlays to match the new (shorter) voice
  durations. That's a separate, already-flagged, still-open decision.
- Producing a new `.mp4`. This is an audio-only validation.
- Changing anything about how VO or music is *generated* (ElevenLabs payloads, voice/model choice). The
  9 voiceover takes and the 2 corrected (prompt-mode, `force_instrumental`) music beds from the prior
  runs are the inputs; nothing gets re-generated or re-spent.
- A general redesign of `stitcher`'s render pipeline. This is one new, narrowly-scoped stage plus two
  small, targeted schema uses.

## 4. Architecture

### 4.1 New module: `stitcher/stitcher/precondition.py`

One function, one clear purpose: take a raw audio clip and a target loudness/peak envelope, and return a
clip that is *safe* for `stitcher`'s own downstream linear-loudnorm gate to accept — without collapsing
its dynamics to get there.

```python
@dataclass(frozen=True)
class ConditionResult:
    source: Path
    output: Path
    input_measurement: dict   # {input_i, input_tp, input_lra, input_thresh} from ffmpeg.measure_loudness
    output_measurement: dict  # same shape, measured after processing
    limited: bool             # True if peak limiting was applied, False if gain-only sufficed

class PreconditionError(Exception):
    """Raised when the output, re-measured, still fails to meet the target envelope."""

SAFETY_MARGIN_DB = 0.3  # headroom against filter/encode rounding

def condition_clip(
    source: Path,
    target_lufs: float,
    target_tp_dbtp: float,
    out_path: Path,
    log_path: Path,
) -> ConditionResult:
    ...
```

**Algorithm:**

1. Measure the source with `ffmpeg.measure_loudness` (already exists, reused — `audio.py`'s own
   pass-1 measurement helper).
2. Compute `naive_gain = target_lufs - input_i`, and `projected_peak = input_tp + naive_gain` — what
   the peak would be if we simply gain-shifted to the target loudness with no limiting.
3. **If `projected_peak <= target_tp_dbtp - SAFETY_MARGIN_DB`:** gain-only suffices. Apply
   `volume={naive_gain}dB,aresample=48000`. `limited=False`.
4. **Otherwise:** peak reduction is required before the gain stage. Compute the pre-gain ceiling
   `alimiter` must hold the signal under: `limiter_ceiling_dbtp = target_tp_dbtp - naive_gain -
   SAFETY_MARGIN_DB`, convert to linear amplitude (`10 ** (limiter_ceiling_dbtp / 20)`), and apply
   `alimiter=limit=<linear>:attack=5:release=50:level=0,volume={naive_gain}dB,aresample=48000` in one
   pass — `alimiter`'s own auto-leveling is explicitly disabled (`level=0`) so it only clips peaks; the
   subsequent `volume` stage remains the sole loudness control, keeping the operation deterministic and
   auditable. `limited=True`.

   `alimiter` is a brickwall peak limiter, not an adaptive normalizer: it only engages when the signal
   exceeds the ceiling, and does not ride gain on passages that never approach it. This is the direct,
   deliberate opposite of `loudnorm`'s dynamic mode, which is what produced the measured LRA collapse.
5. Re-measure the output. If `output_measurement['input_tp'] > target_tp_dbtp` (the safety margin didn't
   hold — a real possibility with filter/rounding behavior worth catching, not assuming away), raise
   `PreconditionError` with the measured values. Never silently ship an out-of-envelope result.
6. `log(...)` (via the existing `elevenlabs_tooling`-style / `stitcher` logging convention already used
   elsewhere in this repo) the before/after `I`/`TP`/`LRA` for every call — a dynamics-losing fix must be
   *visible* in the QA trail, not another undocumented silent step like the one that caused half of this
   bug in the first place.

**Exact `alimiter` attack/release values (5ms/50ms) and the 0.3 dB safety margin are stated explicitly,
not left as ffmpeg defaults** — this project's convention throughout is to record the value chosen
rather than let an implicit default stand in for a decision.

### 4.2 Where it plugs in

`condition_clip` runs once per raw asset, **before** that asset is referenced as a `render-spec.json`
stem or bed file — replacing the old undocumented-by-hand "prep" step:

- **Each of the 7 raw VO takes** (`VO#_provoice.mp3`, the ones actually used — take 1 for VO1/VO7 unless
  the take-2 re-roll is preferred) is conditioned individually, target = `spec.audio.loudness`'s values
  (§4.4). Conditioning *before* concatenation is what removes the 4.1 LU beat-to-beat spread — each
  clip lands at the same reference loudness independently, rather than being conformed as part of an
  already-uneven combined track.
- **`BedA_provoice_v2.mp3` and `BedB_provoice_v2.mp3` are each conditioned individually**, same targets,
  same reasoning (consistency between the two halves before they're joined).
- Conditioned VO clips are placed as `Audio.stems[]` entries at their exact new back-to-back offsets
  (already known exactly from the prior run's measurement — §4.3).
- Conditioned bed segments are **concatenated directly** (`BedA` then `BedB`, no gap, no crossfade, no
  hand-placed silence) into one bed file. The hold-out and pause silences are expressed declaratively
  instead (§4.5) — the concatenated file's own samples are just continuous music.

This keeps `condition_clip` a general-purpose, single-responsibility function (any source, target
envelope in, safe clip out) reusable for both VO and bed, and keeps `stitcher`'s own `build_audio()`
completely unmodified — it keeps doing exactly what it already does, gated exactly as it already gates,
just fed inputs that no longer force it into a corner.

### 4.3 VO stem placement (known exactly, no re-measurement needed)

From the prior run's results, using **take 1** for VO1 (Hook) and VO7 (CTA) — the same take used in
both prior mix previews, kept for consistency with what's already been evaluated. The take-2 re-rolls
remain available as an alternate; switching to one is a straightforward substitution (a different source
file into the same `condition_clip` call, same target `at` offset) that doesn't otherwise change this
design, and is not part of this validation pass.

| Stem | File (post-conditioning) | `at` |
|---|---|---:|
| vo1 | `VO1_provoice_conditioned.wav` | 0.000000 |
| vo2 | `VO2_provoice_conditioned.wav` | 5.200000 |
| vo3 | `VO3_provoice_conditioned.wav` | 10.800000 |
| vo4 | `VO4_provoice_conditioned.wav` | 16.240000 |
| vo5 | `VO5_provoice_conditioned.wav` | 22.560000 |
| vo6 | `VO6_provoice_conditioned.wav` | 35.840000 |
| vo7 | `VO7_provoice_conditioned.wav` | 46.480000 |

Total runtime: 51.920000s.

### 4.4 Loudness targets

`spec.audio.loudness`:
```json
{ "integrated_lufs": -14.0, "true_peak_dbtp": -1.0 }
```

`true_peak_dbtp` is relaxed from the original render's −0.15 to **−1.0** (Opus's recommendation): a
tight −0.15 dBTP ceiling on a lossy-delivered platform buys negligible practical benefit and consumes
limiting headroom that's better spent preserving dynamics. `condition_clip` is called with these same
two values for every VO and bed asset (§4.2) — pre-conditioning every input to (approximately) the
render's own final target means `build_audio()`'s own subsequent gain-conform step, measuring an
already-on-target mix, needs only a small residual shift, which stays linear trivially. This is *why*
the fix works, not an incidental detail.

### 4.5 Bed hold-outs via `Bed.windows`, not baked silence

`stitcher/stitcher/spec.py`'s `Bed` model already supports `windows: list[BedWindow]` and
`fades: list[Fade]` (`BedWindow = {in, out, mode: "out"|"ducked"|"full", level_db?}`), consumed by
`envelope.py`'s `_window_level`/`build_breakpoints`/`volume_expr` to shape the bed's gain envelope at
mix time — confirmed these are unused-but-fully-functional in the current render-spec.json.

```json
"bed": {
  "file": "BedFull_provoice_conditioned.wav",
  "gain_db": -22.0,
  "duck_db": -29.0,
  "duck_attack_ms": 120,
  "duck_release_ms": 400,
  "windows": [
    { "in": 0.0, "out": 5.200000, "mode": "out" },
    { "in": 19.514331, "out": 20.222948, "mode": "out" }
  ],
  "fades": [
    { "at": 5.200000, "kind": "in", "ms": 300 }
  ]
}
```

The hook hold-out and the re-hook pause (both timestamps already known exactly from the prior run's
`ffmpeg silencedetect` measurement against the new VO4) are declared as `mode: "out"` windows —
`envelope.py` forces the bed to `SILENCE_DB` for the declared span regardless of what audio is actually
underneath. `BedFull_provoice_conditioned.wav` itself is nothing more than the two conditioned bed
segments concatenated back-to-back — no silence-splicing, no crossfade engineering. This directly
replaces the fragile hand-built splice from the prior run (which required a corrective crossfade fix
once already, per its results doc) with the schema's own declarative mechanism.

## 5. Validation plan

`build_audio(spec, ws, mode, log_path, missing_audio, manifest=None) -> AudioResult` is a plain module
function — confirmed it reads only `spec.audio` and `spec.shots[-1].end` (via `runtime_seconds`), never
`overlays`/`captions`/`styles`/`delivery`, and does **not** call `validate_spec` itself. This means the
real, gated `stitcher` pipeline can be exercised directly, without a full CLI render and without
resolving the shot-timing re-cut question.

**Test harness (a script, not a `stitcher` feature — this part is throwaway, unlike `precondition.py`):**

1. Construct a minimal `RenderSpec`: one dummy `Shot` spanning `[0, 51.920000]` (satisfies
   `validate_spec`'s non-empty/contiguous requirement if ever invoked; irrelevant to `build_audio()`
   itself either way), the 7 VO stems from §4.3, the bed from §4.5, loudness from §4.4, empty
   `overlays`/`captions`.
2. Build a real `Workspace` (`root=<scratch dir>, slug="precondition-validation", mode="final"`),
   `ensure_dirs()`.
3. Run `condition_clip` (real ffmpeg, not mocked) on each of the 9 raw source files (7 VO + 2 bed
   segments), writing into the workspace's asset directory.
4. Concatenate the two conditioned bed segments into `BedFull_provoice_conditioned.wav`.
5. Call `build_audio(spec, ws, mode="final", log_path=..., missing_audio=[])` for real.

**Success criteria (objective, checked before any listening):**
- No exception raised (specifically: no `LoudnormNotLinearError`).
- Returned `AudioResult.pass2["normalization_type"] == "linear"`.
- LRA is preserved, not collapsed: compare `AudioResult.pass2`'s reported `input_lra`/`output_lra`
  against the raw (pre-conditioning) VO's measured LRA — the fix is confirmed only if the gap is small,
  not if LRA quietly dropped again by another route.

**Then, and only after the above passes:** produce the actual mixed output file and deliver it for a
listen — the same closing step as the two prior rounds, now backed by an objective pass first instead of
skipping straight to "does it sound okay."

## 6. Error handling

- `condition_clip` raising `PreconditionError` on a source that can't be brought into envelope even with
  limiting (e.g., true garbage input) is treated as a hard stop, not something to silently work around —
  matching `stitcher`'s existing `LoudnormNotLinearError`/`SilentVoiceError` philosophy of failing loudly
  on a genuine audio-quality problem rather than shipping a degraded result.
- `build_audio()`'s own `LoudnormNotLinearError` remains untouched and still fires if, despite
  preconditioning, the final assembled mix still can't reach linear mode — this is the correct backstop,
  not a bug to route around a second time.

## 7. Testing

`stitcher/stitcher/precondition.py` gets its own test file, `stitcher/tests/test_precondition.py`,
following the existing `test_audio.py` pattern (mocked `ffmpeg.run`/`probe`/`measure_loudness`, no real
binaries invoked in unit tests):

- Gain-only path: a source whose projected peak already fits the target — confirms no `alimiter` stage
  is applied and the exact `volume=` gain matches the computed value.
- Limiting-required path: a high-PLR source (mirroring the real ~21 dB PLR measurement) — confirms
  `alimiter` is applied with the correct computed `limit=`, `level=0` is present, and the subsequent
  `volume=` stage still runs.
- Post-condition verification failure: mock the re-measurement to still exceed the target — confirms
  `PreconditionError` is raised rather than the out-of-envelope file being returned silently.
- `SAFETY_MARGIN_DB` is honored: a source landing exactly at the ceiling before margin is still routed
  through the limiting path, not the gain-only path.

The validation script itself (§5) is a one-off, not committed as permanent `stitcher` code — it exists to
produce this round's proof, using `precondition.py` and `build_audio()` as its only two dependencies
beyond the standard library.

## 8. Out of scope (explicit)

- The shot-timing re-cut (§3).
- Any change to `elevenlabs_tooling` (payload construction, `validate`/`send`) — not touched by this
  spec at all.
- Extending `precondition.py` to run automatically as part of every `stitcher render` invocation (i.e.
  wiring it into `cmd_render`/the CLI) — this spec adds the capability and proves it against this real
  render; wiring it into the standard render path is a natural, small follow-up but is a separate,
  reviewable change once this one's results are confirmed by ear.
