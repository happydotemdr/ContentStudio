# Audio Preconditioning for `stitcher` — Design Spec

**Status:** Draft v3 — revised after two rounds of Opus technical review, both empirically verified
against the installed ffmpeg 9.0 binary, not just documentation. v1's core premise (§4.4) was found
empirically false; v2's fix was directionally right but its retry loop silently let integrated loudness
drift (reintroducing the beat-to-beat defect this spec exists to remove) and its peak-conditioning
target was more aggressive than the actual required margin justified. Both are fixed in this version.
**Scope:** Fix the leveling/clipping defect diagnosed in the pro-voice audio validation run. Audio-only.
Does not touch shot timing, captions, overlays, or produce a video render.

---

## 0. Source material (this spec is self-contained; these are pointers, not requirements to read)

The prior validation-run and vocal-leakage-fix results docs that motivated this spec live in a
*different* worktree (`C:\Projects\ContentStudio\.claude\worktrees\elevenlabs-tooling-impl\docs\superpowers\plans\2026-08-19-*.md`)
— not this one. All numbers this spec actually depends on (durations, offsets, measured loudness
figures) are inlined below; nothing here requires cross-referencing those files.

The render being fixed lives outside any git worktree, as local git-ignored files:
`C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711\`.
There is **no `render-spec.json` committed anywhere in this repo** — only the schema,
`stitcher/schema/render-spec.schema.json`. References below to "the current render-spec.json" mean that
live, local, gitignored file at the path above, observed directly, not a repo artifact.

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

`stitcher` — this repo's actual tested render tool — already has a gate designed to catch exactly this:
`audio.py`'s two-pass `loudnorm` with `linear=true`, raising `LoudnormNotLinearError`
(`audio.py:532-538`) if pass 2 can't stay in linear mode. Running `stitcher`'s conform/duck/mix math by
hand, outside the CLI, bypassed that gate. Replaying `stitcher`'s real two-pass loudnorm against the raw
new voiceover produces `"normalization_type": "dynamic"` — the exact condition the gate exists to
refuse. The new voice's peak-to-loudness ratio (PLR) is ~21 dB; reaching −14 LUFS integrated with a
sane true-peak ceiling by static gain alone requires PLR low enough that gain alone can do it. Gain
cannot supply peak reduction — only actual limiting can.

## 2. Goals

- Produce a corrected audio mix (voiceover + music bed) for the already-generated new-voice assets that
  a human can listen to and confirm the leveling/clipping is gone.
- Add a real, tested capability to `stitcher` — not another ad hoc script — so the same fix applies
  automatically to every future render, including the next voice swap.
- Preserve narration dynamics (LRA) rather than collapsing them.
- Route the actual render-time mixing math through `stitcher`'s existing, gated `build_audio()` — don't
  reimplement it a second time.

## 3. Non-goals

- Re-cutting `render-spec.json`'s shot timings, captions, or overlays. Separate, still-open decision.
- Producing a new `.mp4`. This is an audio-only validation.
- Re-generating or re-spending on any ElevenLabs call. The 9 voiceover takes and the 2 corrected
  (prompt-mode, `force_instrumental`) music beds from the prior runs are the inputs.
- A general redesign of `stitcher`'s render pipeline.

## 4. Architecture

### 4.1 New module: `stitcher/stitcher/precondition.py`

One function: take a raw clip and a **per-clip conditioning target** (deliberately *not* the render's
own delivery target — see §4.4 for why that distinction is load-bearing) and return a clip that is safe
for `stitcher`'s downstream linear-loudnorm gate to accept, without collapsing dynamics to get there.

```python
@dataclass(frozen=True)
class ConditionResult:
    source: Path
    output: Path
    input_measurement: dict   # {input_i, input_tp, input_lra} -- the exact 3 keys ffmpeg.measure_loudness
                               # returns (ffmpeg.py:344-348); it does NOT return input_thresh, which
                               # belongs to loudnorm's own pass-1 JSON, a different mechanism.
    output_measurement: dict  # same 3-key shape, measured on the written output file
    limited: bool              # True if peak_reduction_db > 0.05 (an arbitrary-but-stated threshold
                                # above measurement noise -- distinguishes "the limiter did something"
                                # from "gain alone would have landed here anyway")
    peak_reduction_db: float   # 0.0 if the accepted attempt applied no limiting; otherwise
                                # (input_measurement['input_tp'] + applied_gain) - output_measurement['input_tp']
                                # using the ACCEPTED attempt's final `applied_gain` value (§4.1 step 3
                                # may have revised it from its initial value via the loudness-retry
                                # branch) -- the gap between "what the peak would have been with gain
                                # alone" and "what it actually is" -- a quantity directly derivable from
                                # the two measurements plus the known applied gain, unlike a true
                                # instantaneous per-sample maximum, which nothing in this chain measures.

class PreconditionError(Exception):
    """Raised when, after MAX_ATTEMPTS, the output still fails the peak or loudness target."""

CONDITION_ATTACK_MS = 5      # equals alimiter's own current ffmpeg default; pinned explicitly so a
CONDITION_RELEASE_MS = 50    # future ffmpeg default change can't silently move these (verified against
                              # the installed ffmpeg 9.0 build's `-h filter=alimiter`)
TP_TOLERANCE_DB = 0.1        # how far over target_tp_dbtp a measured true peak may land before
                              # triggering a tighter-ceiling retry
LUFS_TOLERANCE = 0.35        # how far the *conditioned* clip's integrated loudness may drift from
                              # target_lufs before triggering a makeup-gain retry (LU). Deliberately
                              # 0.35, not 0.3: a boundary of exactly 0.3 sits on a floating-point knife
                              # edge against ebur128's 0.1 LU output granularity -- a real measured case
                              # (`-14.3` vs. target `-14.0`) evaluates `abs(-14.3 - -14.0) <= 0.3` as
                              # **False** (`0.30000000000000071...`) and would trigger an unnecessary
                              # retry on a result that's already correct to the tool's own precision.
MAX_ATTEMPTS = 4

def condition_clip(
    source: Path,
    target_lufs: float,
    target_tp_dbtp: float,
    out_path: Path,
    log_path: Path,
) -> ConditionResult:
    ...
```

**Algorithm** (v3 — revised again after a second review found v2's retry loop verified-in-practice to
let integrated loudness drift by up to 0.4 LU across differently-limited clips, because it only
re-checked true peak on retry, never re-solving gain. That drift is exactly defect §1.1 — beat-to-beat
level inconsistency — reintroduced by the fix meant to remove it. v3 makes every accepted result satisfy
*both* the peak ceiling and the loudness target, explicitly, every attempt.):

1. Measure the source with `ffmpeg.measure_loudness` (existing helper — the same ebur128 measurement
   `_build_bed` already uses for the bed's own conform, `audio.py:313`, and `build_audio` uses for the
   voice reference, `audio.py:375`). This is `input_measurement`, fixed for the whole call.
2. `applied_gain = target_lufs - input_measurement['input_i']`; `ceiling_dbtp = target_tp_dbtp` (the
   starting point for the loop below).
3. **Loop, up to `MAX_ATTEMPTS`:**
   - Build and run: `aresample=48000,volume={applied_gain:.2f}dB,alimiter=limit={10**(ceiling_dbtp/20):.6f}:attack=5:release=50:level=0:latency=1` → `-c:a pcm_s16le -ar 48000 -ac 2` → a temp file.
     - **Resample first**: avoids a *later* resample (as in v1) reintroducing overshoot after the
       limiter already ran. This does **not** guarantee the limiter's sample-peak ceiling exactly equals
       the eventual measured *true* peak — `alimiter` fundamentally limits sample peak, not true peak,
       and some gap between the two is intrinsic to any sample-peak limiter (verified directly: a chain
       whose sample peak landed exactly on a `-4.5` dBFS ceiling measured `-1.4` dBTP true peak on
       broadband material — a ~3 dB gap, not something reordering removes). That gap is *why* this
       loop's re-measurement-and-retry (below) is the actual mechanism that closes it, not the filter
       ordering by itself. (v2's spec text claimed the ordering alone closed the gap; that claim was
       wrong and is corrected here.)
     - **`level=0`**: disables `alimiter`'s own auto-leveling (verified: `level <boolean> auto level
       (default true)`), so `volume=` remains the sole loudness control the algorithm reasons about.
     - **`latency=1`**: without it, `alimiter` delays its output by its `attack` time — verified directly
       (identical input, first content at 517.12ms with `latency=0` vs. 512.15ms with `latency=1`, a
       ~5ms shift) — and **only on a pass that actually engages limiting**, an asymmetry that would
       otherwise place a limited clip's audible content a few milliseconds later than its declared `at`
       offset while an unlimited clip lands exactly on it. Total frame count/duration is unaffected
       either way (`latency` shifts *content within* the clip, it does not change how many frames the
       clip has) — this is a timing-alignment fix, not a duration fix.
   - Measure the temp file: `result = ffmpeg.measure_loudness(temp)`.
   - `tp_ok = result['input_tp'] <= target_tp_dbtp + TP_TOLERANCE_DB`
   - `lufs_ok = abs(result['input_i'] - target_lufs) <= LUFS_TOLERANCE`
   - **If both hold:** promote the temp file to `out_path`; done.
   - **If `tp_ok` is false:** peak still too high — tighten the ceiling:
     `ceiling_dbtp -= (result['input_tp'] - target_tp_dbtp) + 0.2`, keep `applied_gain` unchanged, retry.
   - **If `tp_ok` holds but `lufs_ok` is false:** the limiter pulled integrated loudness away from
     target (the v2 defect) — **re-solve gain, don't just accept the drift**:
     `applied_gain += (target_lufs - result['input_i'])`, keep `ceiling_dbtp` unchanged, retry.
     Confirmed by running this exact algorithm against all 9 real conditioned sources: `alimiter`
     reliably pins measured true peak at the ceiling from the first attempt (the peak-retry branch above
     essentially never fires on real material — measured true peak sat exactly on `-2.5` across every
     attempt on every clip), so in practice this loop is a **loudness-only contraction**: each gain
     correction reduces the remaining loudness error by roughly the same fraction rather than closing it
     in one step, because re-applying `alimiter` after a larger gain correction clips slightly more of
     the signal again (measured error sequence on one real clip: `1.1 → 0.3 → 0.1` LU). `MAX_ATTEMPTS =
     4` gives one attempt of margin over the ~3 the real material needed at `CONDITION_TP_DBTP = -2.5`
     — measured, not assumed; a materially tighter ceiling should re-confirm the attempt count against
     real files rather than relying on 4 by extrapolation.
4. If `MAX_ATTEMPTS` is exhausted without both conditions holding simultaneously, raise
   `PreconditionError` with the source path and the last measurement — never return a result that
   fails either target.
5. On acceptance: compute `limited` and `peak_reduction_db` from `input_measurement`, `applied_gain`
   (the value actually used on the accepted attempt), and `output_measurement`.
6. `log(...)` every call's before/after `I`/`TP`/`LRA`, `peak_reduction_db`, and the number of attempts
   taken — a dynamics-losing fix must be visible in the QA trail, not another undocumented silent step
   like the one that caused half of this bug originally. `peak_reduction_db` specifically answers "was
   this clip pushed hard enough that a human should listen for dulled plosives" without requiring that
   listen on every run.

Every conditioned clip, VO or bed, is written as explicit `-ac 2` (stereo) regardless of source channel
layout — verified necessary: a mono VO stem `amix`ed with a stereo bed through `build_audio`'s real
graph makes ffmpeg negotiate the **entire mix** down to mono. This is not optional per-clip; it applies
uniformly.

### 4.2 Where it plugs in

`condition_clip` runs once per raw asset, **before** that asset is referenced as a `render-spec.json`
stem or bed file:

- **Each of the 7 raw VO takes** is conditioned individually — target = §4.4's per-clip targets, *not*
  the render's delivery targets. Conditioning before concatenation is what removes the 4.1 LU
  beat-to-beat spread: each clip lands at the same reference loudness independently.
- **`BedA_provoice_v2.mp3` and `BedB_provoice_v2.mp3` are each conditioned individually**, same
  per-clip targets, same reasoning.
- Conditioned VO clips are placed as `Audio.stems[]` entries at their exact new back-to-back offsets
  (§4.3, already known exactly).
- Conditioned bed segments are assembled per §4.5 — concatenation only, no crossfade engineering; the
  one remaining hand-placed silence is the leading hold-out only (§4.5 explains why that one span stays
  a simple prepend rather than a declarative window).

`condition_clip` stays general-purpose (any source, any target envelope in, safe clip out); `stitcher`'s
own `build_audio()` stays completely unmodified.

### 4.3 VO stem placement (known exactly, no re-measurement needed)

Using **take 1** for VO1 (Hook) and VO7 (CTA) — the take used in both prior mix previews. Take-2
re-rolls remain available as a straightforward substitution, not part of this validation pass.

| Stem | File (post-conditioning) | `at` | Measured duration |
|---|---|---:|---:|
| vo1 | `VO1_provoice_conditioned.wav` | 0.000000 | 5.200000 |
| vo2 | `VO2_provoice_conditioned.wav` | 5.200000 | 5.600000 |
| vo3 | `VO3_provoice_conditioned.wav` | 10.800000 | 5.440000 |
| vo4 | `VO4_provoice_conditioned.wav` | 16.240000 | 6.320000 |
| vo5 | `VO5_provoice_conditioned.wav` | 22.560000 | 13.280000 |
| vo6 | `VO6_provoice_conditioned.wav` | 35.840000 | 10.640000 |
| vo7 | `VO7_provoice_conditioned.wav` | 46.480000 | 5.440000 |

Total runtime: **51.920000s**. `condition_clip`'s `latency=1` fix (§4.1) keeps each clip's duration
exactly equal to its measured input duration, so this table's durations hold after conditioning too. The
implementation asserts `at + duration <= runtime` for every stem (VO7: `46.480000 + 5.440000 =
51.920000`, exactly the runtime — the tightest case, asserted rather than assumed) — `_place_stems`'
downstream `atrim=0:{runtime}` (`audio.py:476`) would otherwise silently truncate an overrunning clip
with no error.

### 4.4 Loudness targets — two different envelopes, deliberately decoupled

**This is the section both review rounds focused on, and it went through two corrections.**

v1 conditioned every clip to the render's own delivery targets (`-14.0 LUFS / -1.0 dBTP`) directly,
reasoning that `build_audio()`'s own subsequent gain-conform would then need only a trivial residual
shift. That reasoning was wrong: a mix whose true peak sits *exactly* on the delivery ceiling still
fails `stitcher`'s linear-mode gate — verified (a mix at `input_i -14.15 / input_tp -0.94` came back
`"normalization_type": "dynamic"`, i.e. it would still raise `LoudnormNotLinearError`). Zero margin.

v2's fix decoupled the conditioning target from the delivery target, which was the right move, but
picked `-4.5 dBTP` — 3.5 dB of headroom — asserted rather than derived from what margin is actually
needed. That over-shot: `-4.5` demands ~11.5 dB of peak reduction from the source's ~21 dB PLR, and
measured directly, that much reduction cost up to **1.8 LU of per-clip loudness-range loss** — the
dynamics-collapse this whole spec exists to prevent, just moved into a new step instead of removed.

**v3 derives the margin from the actual linear-mode boundary, not an assumed number.** The empirically
measured condition for `stitcher`'s two-pass loudnorm to land in linear mode is
`input_tp + loudnorm's own reported target_offset <= target_TP`; `target_offset` can be either sign
(measured `-0.06` to `-0.3` dB on some test mixes, `+0.10` dB on the real conditioned mix) — a negative
value would *relax* the linear-mode condition, so the derivation below treats it as a cost (`+0.3`
worst-case magnitude) deliberately, to stay conservative regardless of which sign shows up on a given
mix, not because the sign is known in advance. Add the bed's own true-peak contribution once mixed with
the (now much louder, individually-conditioned) voice — confirmed against the real render-spec.json's
`gain_db: -22.0` / `duck_db: -29.0`: `20 · log10(1 + 10^(-22/20)) ≈ 0.66 dB` as a coherent-sum worst-case
estimate (the real measured contribution on the actual mix came back lower, `0.38 dB` — the estimate is
conservative in the safe direction, as intended). Minimum required margin ≈ `0.3 + 0.66 + a small noise
allowance ≈ 1.2 dB`. `-2.5` gives 1.5 dB of headroom — safely above the derived 1.2 dB minimum.

**On the LRA cost of `-2.5` vs. tighter alternatives — measured by actually running §4.1's algorithm
against all 9 real conditioned sources, not estimated:** mean per-clip LRA loss came back **0.89 LU at
`-2.0`, 0.94 LU at `-2.5`, 1.20 LU at `-4.5`** — real numbers superseding an earlier, non-reproducing
estimate in an intermediate draft of this spec. Two things follow: `-2.0` and `-2.5` cost almost the
same (0.05 LU apart, not a meaningful tradeoff either way), so `-2.5` is chosen purely on margin —
sitting safely above the derived 1.2 dB minimum, where `-2.0`'s 1.0 dB does not — not because it's
cheaper. And `-4.5` (v2's original, rejected choice) costs noticeably more than either, confirming that
correction was worth making even though the earlier magnitude estimate for it wasn't precise. Individual
clips vary around this mean by real, content-dependent amounts (a content-dense clip with wide natural
dynamics, e.g. VO5's spoken-numbers proof segment, showed the largest measured single-clip loss, ~2.5
LU, at `-2.5`) — §5's success criterion (below) is set from this full measured distribution, not the
mean alone.

**Two separate constants, not one:**

```python
DELIVERY_LUFS = -14.0        # unchanged -- render-spec.json's audio.loudness.integrated_lufs
DELIVERY_TP_DBTP = -1.0      # relaxed from the original render's -0.15 (Opus's recommendation --
                              # a tight -0.15 ceiling on a lossy-delivered platform buys negligible
                              # benefit and consumes limiting headroom better spent on dynamics)

CONDITION_LUFS = -14.0       # per-clip conditioning target -- matches delivery loudness;
                              # `_place_stems`' non-overlapping stems (§4.3) mean the assembled VO's
                              # own integrated loudness tracks each clip's, confirmed against the real
                              # `amix` graph -- and §4.1's loop now actively re-solves gain on retry
                              # to hold every accepted clip to this target, not just aim for it once.
CONDITION_TP_DBTP = -2.5     # per-clip conditioning true-peak target -- NOT DELIVERY_TP_DBTP.
                              # 1.5 dB of headroom below the -1.0 delivery ceiling: above the derived
                              # ~1.2 dB minimum (target_offset + the bed's 0.66 dB true-peak
                              # contribution + noise), without the excess of v2's -4.5, which cost
                              # measurably more dynamics than the margin required.
```

Measured mean per-clip LRA loss at `-2.5`: **0.94 LU**; measured per-clip maximum: **2.7 LU** (VO5).
§5's success criterion is set from this real distribution — a single "~1.0 LU per clip" ceiling looks
reasonable until checked against real files, where it fails 4 of the 9 real clips; see §5 for the
criterion actually used.

One residual precision note, not a defect: `_build_bed` formats its own conform gain as
`{conform_gain:.1f}dB` (`audio.py:320`) — the bed's final level is quantized to 0.1 dB regardless of how
precisely `condition_clip` conditioned its inputs. This is `stitcher`'s existing behavior, unrelated to
and unaffected by this spec; noted so a future 0.1 dB discrepancy between a conditioning log and the
final bed level isn't mistaken for a bug in `precondition.py`.

`render-spec.json`'s `audio.loudness` is set to `{DELIVERY_LUFS, DELIVERY_TP_DBTP}` — this is what
`build_audio()`'s own final two-pass loudnorm targets, unchanged from v1's design and correct. What
changes is that `condition_clip`'s per-VO-clip and per-bed-segment calls use `CONDITION_LUFS` /
`CONDITION_TP_DBTP` instead — a *tighter*, independently-verified-safe envelope that gives
`build_audio()`'s own subsequent processing the margin it needs to land in linear mode at the *looser*
delivery envelope. The two envelopes are never conflated again anywhere in this design.

### 4.5 Bed assembly: mostly declarative, one deliberate exception

`stitcher/stitcher/spec.py`'s `Bed` model supports `windows: list[BedWindow] = []` and
`fades: list[Fade] = []` (`spec.py:135-142`; `BedWindow = {in, out, mode: "out"|"ducked"|"full",
level_db?}`, `spec.py:122-126`; `Fade = {at, kind, ms}`, `spec.py:129-132`), consumed by `envelope.py`'s
`_window_level`/`build_breakpoints`/`volume_expr` to shape the bed's gain envelope at mix time —
confirmed unused-but-fully-functional against the live render-spec.json (§0). A `mode: "out"` window
forces the bed to `SILENCE_DB` (`-100.0`) for its declared span, taking outright precedence over the
duck/baseline envelope — **except** `_build_bed` subtracts `bed.gain_db` from every breakpoint
(`audio.py:332-334`), so a `mode:"out"` window actually renders at `-100 - (-22) = -78` dB relative to
the conformed bed level, not literal digital silence. -78 dB is inaudible under narration in practice,
but "digital silence" is the wrong mental model for what's actually happening — worth stating plainly
rather than letting an implementation assume otherwise.

**The re-hook pause is declarative — the fragile part of v1's design:**

```json
"windows": [
  { "in": 19.514331, "out": 20.222948, "mode": "out" }
],
"fades": [
  { "at": 19.514331, "kind": "out", "ms": 150 },
  { "at": 20.222948, "kind": "in", "ms": 150 }
]
```

`envelope.py`'s edge transition is `_STEP = 0.001` (1 ms) with no fade declared — a window with no
adjacent `fades` entries renders as a ~1 ms mute/unmute on continuous music, i.e. an audible click. The
150ms fades above are declared on both edges of the pause window; `_fade_attenuation`
(`envelope.py:95-108`) composes correctly with the window regardless of which side it's on.

**The bed file's content is built so the one actual BedA→BedB splice sits at the pause window's END, not
its start — and the safety net is the declared fade at that point, not the window's silence** (an
earlier draft of this section claimed the splice fell at the window's start and was masked by the
window's silence; that was checked directly and is wrong — corrected here).

Two coordinate frames matter here, kept explicitly distinct: **BedA-relative time** (0 = the start of
`BedA_conditioned`'s own clip) and **`BedFull` position**, which equals **absolute render time** directly
— `_build_bed`'s envelope timeline starts at file-position 0 = render absolute 0 (§4.5's leading
paragraph), so `BedFull_provoice_conditioned.wav`'s own internal timeline needs no separate offset from
the render's absolute clock. Every position below states which frame it's in.

- `BedA_conditioned` measures **15.072625s** (its real, full conditioned duration — the raw generation
  was `BedA_provoice_v2.mp3` at that length; conditioning doesn't trim it). It is used **trimmed to
  15.022948s of BedA-relative time `[0, 15.022948]`** — *not* its full length; the extra 0.0497s beyond
  that point is discarded. This placement covers `BedFull` position `[5.200000, 20.222948]`.
  - The first 14.314331s of that (`BedFull` position `[5.200000, 19.514331]`) is `BedA`'s own
    intentional content — its fade-in, mechanism drone, and thinning arc, ending right where the
    pause window begins.
  - The remaining 0.708617s (`BedFull` position `[19.514331, 20.222948]`, = BedA-relative
    `[14.314331, 15.022948]`) is filler, covering the pause window's exact duration. Its content is
    `BedA`'s own trailing audio, immaterial because the window silences it regardless — reusing it
    avoids needing any new material or synthesized silence for this span. **The margin is thin but
    sufficient**: `BedA_conditioned` needs to supply at least 15.022948s and has exactly 15.072625s,
    a 0.0497s spare — worth stating explicitly rather than leaving as an unstated assumption an
    implementer could trip on with a slightly-shorter conditioned clip.
- `BedB_conditioned` begins immediately after, at **`BedFull` position 20.222948 — exactly the pause
  window's end**. **This is where the one real splice in the file sits**: `BedA`'s trimmed tail
  transitions directly to `BedB`'s own beginning, no crossfade. What makes this safe is not the window
  (which has already ended by this point) but the **declared 150ms fade-in at `at: 20.222948`** (the
  `fades` entry above) — the envelope is still ramping up from `-100 dB` at the exact instant the splice
  occurs, so the discontinuity is inaudible under the fade, not because it falls inside silenced
  territory. A future edit that removes or shortens that fade without noticing this dependency would
  reintroduce the click — this note exists so that dependency isn't invisible. `BedB_conditioned`'s own
  onset (the "riser out of silence" the music brief calls for) is therefore what's actually heard
  emerging as the fade opens, matching the intended creative effect.

**One deliberate exception — the leading hold-out stays a plain prepend, not a window:** the hook
hold-out `[0, 5.200000]` is realized as **5.2 seconds of genuine silence prepended to the bed file**,
*not* a `windows` entry. Reasoning: `_build_bed`'s envelope timeline starts at file-position 0 = render
absolute 0, so whatever audio sits at the very front of the bed file is what a `mode:"out"` window there
would be silencing. If `BedA_conditioned`'s own content started at file-position 0 instead of a prepend,
its own fade-in arc (explicitly designed to be heard starting at 5.2s) would only become audible
partway through its own generation, at whatever content happens to sit at the 5.2s mark — not its
actual beginning. A plain silence prepend is trivial, was never the fragile part of the prior design
(the fragile part was the *mid-track* splice requiring hand-computed crossfade timing, which this
design eliminates), and is the only construction that lets `BedA`'s own composed fade-in be heard
starting from its own true beginning.

`BedFull_provoice_conditioned.wav` total length: `5.200000 + 14.314331 + 0.708617 +
len(BedB_conditioned)` — comfortably exceeding the 51.920000s runtime given `BedB_conditioned`'s
expected ~33s length, satisfying `_build_bed`'s requirement that the source not be shorter than
`runtime` (a shorter source would loop-repeat rather than simply end, an audible seam this design avoids
by construction, asserted in the implementation rather than assumed).

## 5. Validation plan

`build_audio(spec, ws, mode, log_path, missing_audio, manifest=None) -> AudioResult` (`audio.py:347-354`)
is a plain module function, confirmed to read only `spec.audio` and `spec.shots[-1].end` (via
`runtime_seconds`, `spec.py:208-209`), never `overlays`/`captions`/`styles`/`delivery`, and to **not**
call `validate_spec` itself. The real, gated `stitcher` pipeline can be exercised directly, without a
full CLI render and without resolving the shot-timing re-cut question.

**Test harness (a script, not a `stitcher` feature — throwaway, unlike `precondition.py`):**

1. Construct a minimal `RenderSpec`. Required fields, confirmed against the model (`_Base` sets
   `extra="forbid"`, `spec.py:31`): `spec_version`, `slug`, `canvas`, `safe_zone`, `styles`, `shots`,
   `captions_style`, `audio`. One dummy `Shot` (fields `n`, `id`, `beat`, `in`, `out`, `source`, `kind`;
   `populate_by_name=True` allows `start=`/`end=` aliases) spanning `[0, 51.920000]`. `overlays`/
   `captions` default to `[]` and don't need to be supplied. **The script does not call
   `validate_spec`** — confirmed it requires more than an audio-focused minimal spec conveniently
   provides (an exact `1080x1920` canvas, `spec.py:275-279`, and a `captions_style` key that must
   actually resolve against a populated `styles` dict, `spec.py:373-374`) and there is no audio-only
   entrypoint into it; satisfying it fully would mean building a spec this validation doesn't otherwise
   need. Instead, the script directly asserts §4.5's two `windows` don't overlap (a two-line check —
   the same invariant `spec.py:393-400` enforces, just checked locally rather than through the full
   validator) before calling `build_audio()`, which doesn't require `validate_spec` to have run either.
2. Build a real `Workspace` (`root=<scratch dir>, slug="precondition-validation", mode="final"`),
   `ensure_dirs()`.
3. Run `condition_clip` (real ffmpeg, not mocked) on each of the 9 raw source files (7 VO + 2 bed
   segments) with `CONDITION_LUFS`/`CONDITION_TP_DBTP` (§4.4), writing into the workspace's asset
   directory.
4. Assemble `BedFull_provoice_conditioned.wav` per §4.5 (silence prepend + `BedA` + filler + `BedB`,
   concatenation only).
5. Call `build_audio(spec, ws, mode="final", log_path=..., missing_audio=[])` for real.

**Success criteria — checked in this order, before any listening:**

1. No exception raised (specifically: no `LoudnormNotLinearError`).
2. `AudioResult.loudnorm["normalization_type"] == "linear"` — **note the field is `.loudnorm`, not
   `.pass2`** (`audio.py:88`).
3. **Independent re-measurement of the written output file** — `ffmpeg.measure_loudness(result.mix,
   log_path)` — checking `input_i` within `±0.5` of `DELIVERY_LUFS` and `input_tp <=
   DELIVERY_TP_DBTP`. This is necessary because in linear mode, `loudnorm`'s own reported
   `output_i`/`output_tp`/`output_lra` are **arithmetic predictions from the pass-1 measurement, not
   independent measurements of the file actually written** — verified directly (a case with
   `input_tp -10.52` and `target_offset 0.21` reported `output_tp -10.31` by simple addition, and
   `output_lra` came back byte-identical to `input_lra`, and separately, a file whose reported `output_tp`
   was `-5.08` measured `-4.5 dBTP` on disk — a 0.58 dB gap between the report and reality). Asserting
   only on `loudnorm`'s own reported numbers proves nothing about the file on disk; a fresh, independent
   measurement does.
4. **Per-clip dynamics preservation, gated on the aggregate, reported per-clip.** For each of the 9
   `ConditionResult`s from step 3, compute `input_measurement['input_lra'] -
   output_measurement['input_lra']`. **Gate on the mean across all 9**: expect ≤ **1.2 LU** (measured
   real value at `CONDITION_TP_DBTP = -2.5` is 0.94 LU mean — 1.2 gives working margin above that without
   being loose enough to mask a real regression). **Do not gate per-clip against a single fixed number**
   — measured real per-clip values at `-2.5` range from −0.2 to 2.7 LU (content-dependent: a
   naturally-dynamic clip like VO5's spoken-numbers proof segment costs more than a flatter one; a
   uniform per-clip ceiling tight enough to be meaningful for the flat clips fails the dynamic ones for
   reasons that have nothing to do with the limiter misbehaving). Every clip's individual delta is still
   `log()`-ed (§4.1 step 6) and printed in the validation script's report for a human to scan — a single
   clip wildly out of line with its neighbors (not just "high," but discontinuously higher) is worth a
   look even though it isn't a hard gate. This — not the assembled program's overall LRA — is the correct
   test that the limiter didn't collapse dynamics. The assembled mix's own LRA is expected to *shrink*
   somewhat as a side effect of removing the 4.1 LU beat-to-beat spread (§4.2) — that's the fix working
   as intended, not a dynamics loss, so it is reported for the record but not gated on. Source LRA
   baseline this compares against: 6.10 LU, measured on the raw (pre-any-processing) assembled VO in the
   prior run.
5. **Per-clip loudness accuracy** — for each of the 9 `ConditionResult`s, confirm
   `output_measurement['input_i']` is within `LUFS_TOLERANCE` (0.3 LU) of `CONDITION_LUFS`. This is the
   check that directly catches the v2 defect (a retry that satisfied the peak target while silently
   drifting loudness) were it to recur — §4.1's algorithm is designed to prevent it, and this criterion
   is what proves the design held on the real files, not just in the abstract.

**Then, and only after all four pass:** produce the mixed output and deliver it for a listen — the same
closing step as the two prior rounds, now backed by an objective, independently-measured pass first.

## 6. Error handling

- `condition_clip` raising `PreconditionError` after exhausting `MAX_ATTEMPTS` (§4.1 step 4) is a hard
  stop, not something to silently work around — matching `stitcher`'s existing
  `LoudnormNotLinearError`/`SilentVoiceError` philosophy: fail loudly on a genuine audio-quality problem
  rather than ship a degraded result.
- `build_audio()`'s own `LoudnormNotLinearError` remains untouched and still fires if, despite
  preconditioning, the assembled mix still can't reach linear mode — the correct backstop, not a bug to
  route around a second time. If it fires here, that itself is a finding: it would mean
  `CONDITION_TP_DBTP`'s 1.5 dB headroom (§4.4) was insufficient for this specific mix (e.g. the bed's
  real true-peak contribution exceeded the 0.66 dB coherent-sum estimate), and the constant needs
  revisiting, not the gate.

## 7. Testing

`stitcher/tests/test_precondition.py`, following the existing `test_audio.py` pattern (`MINIMAL` spec
fixture at `tests/test_spec.py:16`, `wire()` monkeypatching `ffmpeg.run`/`probe`/`measure_loudness` at
`tests/test_audio.py:51-74` — confirmed as the real, existing precedent):

- **Clean path**: a source whose first attempt already satisfies both `tp_ok` and `lufs_ok` — confirms
  the `volume=` gain matches the computed value, exactly one `ffmpeg.run` call happens, and `limited`/
  `peak_reduction_db` reflect no meaningful limiting.
- **Peak-retry path**: mock the first re-measurement to fail `tp_ok` (true peak over target) and the
  second to satisfy both — confirms a second `ffmpeg.run` call happens with a tightened `ceiling_dbtp`
  and *unchanged* `applied_gain`, and that `volume=` precedes `alimiter=` in the emitted chain (ordering,
  not just presence — the exact defect the first review round caught in v1).
- **Loudness-retry path** (the case the second review round's finding required adding): mock the first
  re-measurement to pass `tp_ok` but fail `lufs_ok` (peak fine, loudness drifted from the limiter) —
  confirms a second `ffmpeg.run` call happens with `applied_gain` adjusted by the measured drift and
  `ceiling_dbtp` unchanged, and that the accepted `ConditionResult`'s `output_measurement['input_i']` is
  within `LUFS_TOLERANCE` of target. This is the test that would have caught the v2 defect.
- **Exhausted retries**: mock all `MAX_ATTEMPTS` measurements to keep failing one condition or the
  other — confirms `PreconditionError` is raised, not a silently-out-of-envelope result returned.
- **Timing alignment**: confirms `latency=1` is present in every constructed command. Framed correctly
  as an *alignment* property, not duration — verified directly that total frame count is identical with
  `latency=0` vs. `latency=1` (the flag shifts *where content starts within* the clip, it does not add
  or remove frames), so a test asserting only "output duration equals input duration" would pass on a
  build with the flag silently dropped; this test asserts flag presence in the command instead.
- **Output channel count**: confirms `-ac 2` is present in every constructed command regardless of
  source channel layout.

The validation script (§5) is throwaway — not committed as permanent `stitcher` code. It depends on
`precondition.py` and `build_audio()` and nothing else beyond the standard library.

## 8. Out of scope (explicit)

- The shot-timing re-cut (§3).
- Any change to `elevenlabs_tooling` — not touched by this spec at all.
- Wiring `precondition.py` into `cmd_render`/the standard CLI render path automatically. This spec adds
  the capability and proves it against this real render; wiring it into the standard path is a natural,
  small follow-up once this round's results are confirmed by ear, but is a separate, reviewable change.
