# Automated Asset Stitcher — Design

**Status:** Approved in brainstorm, pending final user sign-off on this written spec.
**Date:** 2026-08-06
**Revision:** incorporates a Fable 5 review pass (see "Review notes" at the bottom). Six technical
calls in the original design were wrong or incomplete — the design below is the corrected version,
not the original. Where the review was rejected, that is recorded too.

## Context

ContentStudio's six-skill pipeline currently ends at *plans*. `shorts-assembly` produces an
exhaustive human-readable edit plan (see `rgs-briefs/2026-07-28-nobody-asked-the-kid-assembly.md`)
covering shot-by-shot cut points, per-still motion, card schedules with exact hex colors, ducking
figures, and an asset-filename tree. `visual-prompts` produces a Gate-C-linted prompt sheet. What
does not exist is anything that takes the rendered assets those plans describe and produces a file
you can upload.

This spec defines that module: a **standalone** Python + FFmpeg asset stitcher that combines visual
assets, audio stems, and text overlays into publication-ready 9:16 Shorts deliverables.

**Standalone means standalone.** The module imports nothing from `pipeline_app`, reads no skill,
and never opens the corpus. Its entire world is one render spec and one folder of assets. Wiring it
into the pipeline is deliberately deferred to a later, separate adapter (see "Deferred work").

### Research basis (verified 2026-08-05, re-verify before relying on it)

- **FFmpeg 8.x** is current (8.0 "Huffman" → 8.0.1 → 8.1). `-vsync` is deprecated in favor of
  `-fps_mode`. A native `whisper` filter now exists; this module does not use it.
- **YouTube Shorts 2026 delivery:** 1080×1920, 9:16, up to **3 minutes**, H.264 + AAC-LC @ 48 kHz,
  8–12 Mbps. This resolves the gap `shorts-assembly` repeatedly flags as unverifiable — a 50-second
  runtime is comfortably legal.
- **Loudness:** two-pass `loudnorm` in linear mode; −14 LUFS integrated for YouTube; true peak
  −1.0 to −1.5 dBTP. Single-pass `loudnorm` pumps and is not acceptable for VOD.
- **Ken Burns:** both `zoompan` and `crop` quantize position to integer pixels. Smoothness comes
  from supersampling and downscaling, not from filter choice.

## Goals

1. Turn one validated render spec plus a folder of assets into a master MP4 that meets YouTube
   Shorts delivery spec, with measured (not asserted) loudness and safe-zone compliance.
2. Produce a complete asset *set* per run: master MP4, cover image, caption sidecars, QA report.
3. Be fully deterministic — same spec plus same assets plus same ffmpeg build yields the same
   output. No ML, no model weights, no network, no GPU.
4. Preserve every intermediate on disk under a naming convention that makes any artifact traceable
   to its upstream prompt-sheet row without a lookup.
5. Fail loudly and completely before rendering anything, rather than producing a subtly wrong video.
6. Let a user preview pacing and card legibility *before* spending Midjourney or ElevenLabs credits.

## Non-goals

- **No parsing of `assembly.md` or any prose artifact.** The stitcher's only input is
  `render-spec.json`.
- **No speech recognition or forced alignment.** All overlay copy, caption text, and timing are
  pre-authored in the spec.
- **No asset generation.** The module never calls Midjourney, Kling, or ElevenLabs.
- **No upload, scheduling, or metadata publishing.** It produces files; a human uploads them.
- **No editing decisions.** The module renders what the spec says. It does not re-time, re-cut, or
  re-order.
- **No pipeline integration in v1** (see "Deferred work").

---

## 1. Module boundary and layout

A standalone Python package at repo root, sibling to `pipeline-app/`, mirroring its shape.

```
stitcher/
  stitcher/
    __init__.py
    cli.py         # python -m stitcher render|validate|verify|clean
    naming.py      # single source of truth for every path and filename
    spec.py        # load, validate, frame-quantize render-spec.json
    preflight.py   # probe every asset, reconcile against the spec
    cache.py       # content hashing + work/<mode>/manifest.json
    ffmpeg.py      # subprocess wrapper: build, log, run, parse
    shots.py       # stage A
    overlays.py    # stage B
    audio.py       # stage C
    assemble.py    # stage D
    derive.py      # stage E
    verify.py      # stage F
  tests/
    fixtures/
  requirements.txt
  README.md
```

Eleven modules, one responsibility each. `naming.py` existing separately is deliberate: filename
conventions become testable assertions rather than string formatting scattered across six stages.

### Dependencies

`pydantic>=2.9`, `Pillow>=11.0`. FFmpeg and ffprobe 8.x are external binaries located on `PATH`.
No other runtime dependencies. `pytest` for tests.

### CLI

```bash
python -m stitcher validate <path-to-spec>      # schema + internal consistency only, no assets needed
python -m stitcher render <slug> --mode final   # strict; default
python -m stitcher render <slug> --mode draft   # placeholders permitted, fast encode
python -m stitcher render <slug> --force        # mint a new version even on a total cache hit
python -m stitcher verify <slug> [--version NN] # re-run stage F against an existing output
python -m stitcher clean <slug> [--mode MODE]   # delete work/, keep out/ and logs/
```

Exit codes, shared by `render` and `verify`: **0** success, **1** preflight or validation failure,
**2** render failure, **3** QA failure (the file exists in `work/` but does not meet spec), **4**
verification incomplete (`verify` could not run every check because `work/` was cleaned — §4 stage
F). `validate` exits 0 or 1.

---

## 2. Workspace layout and naming

One directory per Short, under a git-ignored `renders/` root.

```
renders/
  nobody-asked-the-kid/
    render-spec.json
    assets/                                 # INPUTS — supplied by upstream, never modified
      B-01_hook_i2v.mp4
      B-02_setup-1.png
      ...
      vo_child_00_hook.wav
      vo_nar_01_setup.wav
      room_tone.wav
      music_bed.mp3
      B-16_cover.png
    work/
      final/                                # or draft/ — never shared between modes
        shots/
          001_B-01_hook.mkv
          002_B-02_setup-1.mkv
        overlays/
          001_hook_best-part-was-the-mud.png
          001_hook_best-part-was-the-mud.json     # ink bounding box
        audio/
          01_vo-child.wav
          02_vo-nar-01.wav
          03_vo_assembled.wav
          04a_bed_conformed.wav             # baseline gain, no envelope — stage F reference
          04b_bed_ducked.wav
          05_mix_pre-loudnorm.wav
          06_mix_final.wav
          loudnorm_pass1.json
        master.mp4                          # stage D output, promoted to out/ only on QA pass
        concat.txt
        graph_assemble.txt                  # the -filter_complex_script file, kept
        manifest.json                       # stage -> input hash -> artifact
    out/
      nobody-asked-the-kid_v03_1080x1920.mp4
      nobody-asked-the-kid_v03_cover_1080x1920.png
      nobody-asked-the-kid_v03.srt
      nobody-asked-the-kid_v03.ass
      nobody-asked-the-kid_v03_qa.json
      nobody-asked-the-kid_v03_qa.md
      nobody-asked-the-kid_v03_contact-sheet.png
    logs/
      2026-08-06T14-22-03Z_final.log
```

### Naming rules (enforced in `naming.py`, asserted in tests)

1. **`assets/` adopts the convention the assembly plans already specify** — `B-01_hook_i2v.mp4`,
   `vo_nar_01_setup.wav`. The module conforms to the repo, not the reverse. Asset filenames are
   referenced by the spec and are otherwise opaque to the module.
2. **Every visual intermediate is `<ordinal>_<upstream-id>_<slug>`.** The ordinal is timeline
   position zero-padded to three digits, so `ls` sorts into playback order. The upstream id is the
   prompt sheet's own `B-NN`, so any intermediate traces to a prompt-sheet row and an assembly-table
   row without a lookup. Audio intermediates use chain-order ordinals (`01`–`06`) so the mix reads as
   a sequence.
3. **`work/` is content-addressed but readably named.** Hashes live in `manifest.json`, not in
   filenames; a stale artifact is overwritten in place. Variants do not need to coexist in `work/`
   because `out/` is where versions live.
4. **`work/` is partitioned by run mode.** `work/draft/` and `work/final/` never share artifacts or
   a manifest. A cached draft placeholder must never be able to satisfy a final-mode cache lookup.
5. **`out/` is version-stamped and never overwritten, and a version is allocated only on QA pass.**
   Stage D always renders to `work/<mode>/master.mp4`; stage F verifies it; only on a clean pass is
   it promoted into `out/` as `_vNN_`, with `NN` one above the highest already there. A QA-failed
   render leaves the file in `work/` and writes its report to `logs/`, so failures never consume a
   version number and `out/` contains only outputs that actually met spec. **Draft outputs are not
   versioned** — they write `<slug>_draft_1080x1920.mp4` and are overwritten every draft run, because
   a draft is a disposable look, not a reviewable artifact.
6. **`work/` and `logs/` are safe to delete at any time**; `assets/`, `render-spec.json`, and `out/`
   are not.

### Windows path length

`preflight` computes the longest path the run will produce and fails if it exceeds 255 characters,
naming the offending path and suggesting a shorter slug. Long-path support is not assumed.

---

## 3. The render spec

Pydantic v2 models are the source of truth; `stitcher/schema/render-spec.schema.json` is generated
from them so external tools can validate without importing Python.

### Top level

| Field | Type | Notes |
|---|---|---|
| `spec_version` | `"1.0"` | Rejected if unknown. |
| `slug` | string | Must match the containing directory name. |
| `canvas` | object | `width`, `height`, `fps`. v1 requires 1080×1920. |
| `safe_zone` | object | `x`, `y`, `width`, `height` in pixels. No default — must be stated. |
| `styles` | map | Named overlay styles. |
| `shots` | array | Timeline, ordered. |
| `overlays` | array | Burned-in text. |
| `captions` | array | Spoken lines for the sidecars. |
| `captions_style` | string | Name of the style in `styles` used for the `.ass` sidecar. |
| `audio` | object | Stems, bed, sfx, loudness targets. |
| `cover` | object | Supplied cover asset plus its overlays. |
| `delivery` | object | Encoder settings. |

### `styles.<name>`

`font_file` (path, **never a family name**), `size_px`, `body` (hex), `accent` (hex), `ground` (hex
or null), `ground_opacity`, `padding_px` `[x, y]`, `line_spacing`, `align`, `max_width_px`,
`max_lines`, `stroke_px`, `stroke_color`.

A font family name renders differently on another machine and silently substitutes when missing. A
path fails loudly. `max_width_px` and `max_lines` are required because Pillow cannot wrap without
them; exceeding `max_lines` after wrapping is a preflight failure, not a silent overflow.

### `shots[]`

```jsonc
{ "n": 2, "id": "B-02", "beat": "Setup",
  "in": 3.0, "out": 5.5,
  "source": "B-02_setup-1.png", "kind": "still",
  "source_in": null, "source_out": null,
  "motion": { "kind": "push_in", "amount_pct": 15,
              "anchor_start": [0.5, 0.5], "anchor_end": [0.5, 0.5],
              "hold_s": 0.0, "ease": "linear" },
  "transition_in": "cut" }
```

- `in`/`out` are timeline seconds. `source_in`/`source_out` are seconds *within the source file*,
  required for `kind: "clip"` where the delivered asset is longer than the beat (Kling delivers
  fixed 5 s/10 s clips; `B-01` needs 3.0 s and `B-07` needs 4.5 s out of them).
- `motion.kind` ∈ `push_in` | `pull_out` | `scale_up` | `none`. `amount_pct` is total scale change
  across the shot.
- **`anchor_start` and `anchor_end` are the normalized point that stays fixed** at the start and end
  of the move. Equal values give a pure push toward that point; unequal values give a drift.
  `[0.5,0.5]` is centered; `[0.5,0.35]` biases toward the upper third; `[0.8,0.5]` toward the right
  margin. This expresses every move in the reference assembly plan.
- `hold_s` delays the move's start, for "static-to-slow push".
- `ease` ∈ `linear` | `ease_in` | `ease_out` | `ease_in_out`.
- `transition_in` ∈ `cut` | `whip`. A `whip` is specified as
  `{ "kind": "whip", "direction": "left"|"right"|"up"|"down", "frames": 4 }`, where `frames` is the
  count **per side** — the outgoing shot's tail carries `frames` of the gesture and the incoming
  shot's head carries `frames` of the matching one, so the whole thing spans `2 × frames`.
  `direction` is required and has no default; without it the two halves cannot be guaranteed to
  match.

  **The whip is a directional blur, with no translate.** A slide would drag un-rendered content in
  at the trailing edge, and FFmpeg offers no edge-clamping pad; the workarounds — scaling the whole
  shot up to manufacture margin, or splitting and re-concatenating the whip frames — either degrade
  the entire shot or add a filter graph out of proportion to a four-frame gesture. The blur is
  applied at a fixed radius gated to the whip's frames rather than ramped, because the filter that
  can blur directionally cannot ramp per-frame (see the amendment note at the end of this document).

### `overlays[]`

```jsonc
{ "id": "hook-1", "style": "card", "in": 0.0, "out": 2.0,
  "anchor": "center", "offset_px": [0, 0],
  "text": "BEST PART WAS THE [[MUD]]" }
```

- `[[…]]` marks the accent span. Inline markup rather than a separate field, so multi-word accents
  and repeated words are unambiguous.
- `\n` in `text` is a hard line break; everything else wraps at `style.max_width_px`.
- `anchor` ∈ `center` | `upper_third` | `lower_third`, adjusted by `offset_px`.
- Overlays may freely span shot cuts; this requires no special handling (see §4, stage D).

### `captions[]`

```jsonc
{ "in": 0.0, "out": 2.9, "text": "The best part was the mud, and it's not on here." }
```

The spoken narration, authored upstream alongside the VO stems. This exists because overlay cards
are *designed copy*, not a transcript — generating an `.srt` from card text would produce a caption
track that does not match the narration. `captions[]` is the honest source for the sidecars. It is
validated for monotonic non-overlapping times but is otherwise not cross-checked against audio.

### `audio`

```jsonc
{
  "stems": [ { "id": "vo-child", "file": "vo_child_00_hook.wav",
               "at": 0.0, "gain_db": 0.0, "duration_s": 2.875 } ],
  "bed": {
    "file": "music_bed.mp3", "gain_db": -8.0, "duck_db": -22.0,
    "duck_attack_ms": 120, "duck_release_ms": 400,
    "windows": [ { "in": 0.0,  "out": 3.0,  "mode": "out",    "level_db": null },
                 { "in": 17.0, "out": 26.0, "mode": "ducked", "level_db": -26.0 } ],
    "fades": [ { "at": 3.0, "kind": "in", "ms": 300 } ]
  },
  "sfx": [ { "file": "hit.wav", "at": 0.2, "gain_db": -12.0 } ],
  "loudness": { "integrated_lufs": -14.0, "true_peak_dbtp": -1.5 }
}
```

- `stems[].gain_db` is what makes the ±1 LU speaker-handoff match expressible. Without it the
  hardest audio move in the reference plan has nowhere to live.
- `stems[].duration_s` is **optional and used only in draft mode**, to synthesize silence for a stem
  whose file does not exist yet. It is ignored when the file is present (the file's real duration
  wins) and is never required in final mode.
- **`bed.gain_db` and `bed.duck_db` are levels relative to the assembled voice track**, not gains on
  the bed file and not absolute loudness values. `duck_db: -22` means *the bed sits 22 dB below the
  voice while any stem is sounding*; `gain_db: -8` means it sits 8 dB below the voice when no stem is
  sounding. Stage C establishes the reference by measuring `03_vo_assembled.wav`'s integrated
  loudness, then solves for the bed gain that lands each level.

  This is the only reading consistent with the reference corpus, which states the figure both ways
  and glosses them as equivalent: *"keep background music around −21 to −22 dB, ducked under
  vocals"* and *"music bed sits ~15–20 dB below the voice — this is the same instruction as the
  −22 dB duck above, restated as a relative level."* A gain applied to a bed file of unknown inherent
  loudness would make the number mean nothing; voice-relative makes it mean exactly what the corpus
  says.
- `bed.windows[].mode` ∈ `out` | `ducked` | `full`, with an optional `level_db` override (also
  voice-relative) so a multi-movement music arc is expressible rather than just duck-on/duck-off.
- **Precedence is window > duck > baseline.** An explicit window governs its span outright,
  regardless of whether a stem is sounding underneath it — which is what makes the reference plan's
  "bed held out entirely for 0–3s while the child speaks" expressible. Outside any window, the bed
  sits at `duck_db` while a stem sounds and `gain_db` otherwise. **Overlapping windows are rejected
  at validation**, so precedence among windows never arises.
- `duck_attack_ms` / `duck_release_ms` are **ramp durations, and the attack ramp completes at stem
  onset** — the bed is already down when the voice arrives, rather than ducking after the first
  syllable. Release begins at stem offset.
- `duck_db` is **intent**. The module computes a deterministic gain envelope to achieve it (§4 stage
  C), and stage F measures the achieved bed-vs-voice delta (§4 stage F).

### `cover` and `delivery`

`cover`: `{ "source": "B-16_cover.png", "overlays": ["thumb-line"] }`. The cover is a **supplied
standalone asset**, conformed and composited — never a frame extracted from the timeline.

`delivery`: `{ "codec": "libx264", "crf": 18, "preset": "slow", "profile": "high",
"pix_fmt": "yuv420p", "audio_codec": "aac", "audio_bitrate": "192k", "audio_rate": 48000 }`.

### Time handling

**Times are authored in seconds and quantized to frames on load.** Quantization applies to
**absolute boundaries**, never to durations — rounding each duration independently accumulates drift
against the audio timeline. Durations are derived by differencing quantized boundaries.

Every time that does not land on a frame boundary is **reported** by `spec.py` as a warning naming
the field and the residual (at 30 fps, `2.875 s` is 86.25 frames). Warnings do not block; silent
rounding is what blocks understanding.

### Validation rules

Rejected at `validate` time, before any asset is touched:

- Unknown `spec_version`; `slug` not matching the directory.
- `shots` not contiguous, overlapping, or not summing to a single runtime.
- Any `overlays`/`captions` time outside `[0, runtime]`.
- `captions` overlapping or non-monotonic.
- A `style`, `anchor`, `motion.kind`, `ease`, `transition_in`, or `bed.windows[].mode` value outside
  its enum — reported as *"not implemented in v1"* where the value is a known future feature, rather
  than silently substituting a default.
- Text that cannot fit `max_lines` at `max_width_px` in the declared font.
- `source_in`/`source_out` absent on any `kind: "clip"` shot. Whether they fall inside the source's
  real duration is a **preflight** check (§6), not a validation check — `validate` probes no assets,
  so it can only require the fields' presence.
- Overlapping `bed.windows` entries.
- A `whip` transition without a `direction`.
- `captions_style` naming a style that does not exist in `styles`.

---

## 4. The six stages

Each stage writes named artifacts and is independently cacheable. Exactly two encodes occur across
the whole run.

### Stage A — shots → `work/<mode>/shots/NNN_<id>_<slug>.mkv`

Conforms every source to one profile, because the concat demuxer requires identical codec,
`pix_fmt`, timebase, SAR, and frame rate: `canvas.fps` via `-fps_mode cfr`, SAR 1:1, BT.709 tagged.
Kling clips commonly arrive at 24 or 25 fps and must be conformed here.

**Stills** get their motion by **supersampling**. The source is first scaled so that the *narrowest
crop window the move will use* — i.e. the most zoomed-in frame — is at least 3.5 × 1080 px wide.
Sizing off the narrowest window floors the supersample factor at 3.5× for the entire move rather
than only at its start.

The move itself is `scale=eval=frame` feeding a **fixed-size** `crop`, in that order. This
combination is mandatory, not a preference: `crop`'s `w`/`h` are evaluated once at init and cannot
animate, so a zoom must come from animating the *scale* while the crop window stays a constant size
and only its `x`/`y` track the anchor. Attempting to animate `crop`'s dimensions silently produces a
static frame size.

Each frame is then downscaled to 1080×1920 with lanczos. Both `zoompan` and `crop` quantize position
to integer pixels; supersampling is what turns that quantization into sub-pixel motion at output
scale (at 3.5× the residual is ~0.29 output px, invisible under lanczos).

**Clips** are trimmed to `source_in`/`source_out` and conformed identically.

**Whip transitions are applied here, not in stage D.** A shot renders its own head blur when its
`transition_in` is `whip`, and its own tail blur when the *next* shot's `transition_in` is `whip`.
Stage A therefore reads each shot's successor, and a shot's cache key includes its successor's
`transition_in` — otherwise changing shot N+1 to a whip would leave shot N's cached tail stale. This
keeps stage D a pure concat-and-composite pass.

**Color:** PNG sources are RGB. swscale's default RGB→YUV conversion is BT.601, while players assume
BT.709 for HD — a visible palette shift landing on exactly the colors the reference plan makes
binding. Conversion forces `out_color_matrix=bt709:out_range=tv`, and the stream is tagged
`-colorspace bt709 -color_primaries bt709 -color_trc bt709`.

**Intermediate codec:** `libx264 -crf 12 -pix_fmt yuv444p -preset veryfast`. Visually lossless,
roughly 10× smaller than FFV1, and staying 4:4:4 means chroma is subsampled exactly once — at the
final encode. In draft mode: `-crf 28 -preset ultrafast`.

**Placeholders (draft only):** a missing asset renders as a magenta slate carrying the shot id,
beat, and duration, generated through the same Pillow path as overlays. Every placeholder is
recorded in the manifest and listed in the QA report.

### Stage B — overlays → `work/<mode>/overlays/NNN_<id>_<slug>.png` + `.json`

Each overlay renders as a **full-canvas 1080×1920 RGBA PNG** with position already baked in. Two
consequences: stage D always composites at `0:0` with no coordinate arithmetic, and Pillow knows the
exact ink bounding box, which it writes to a sidecar JSON. The safe-zone check in stage F is then a
measurement rather than an estimate.

Rendering: parse `[[…]]` accent spans, wrap at `max_width_px`, apply `line_spacing`, draw the
`ground` plate at `ground_opacity` behind the text block with `padding_px`, draw body text in `body`
and accent spans in `accent`, apply `stroke_px`/`stroke_color`.

### Stage C — audio → `work/<mode>/audio/`

1. Each stem is gain-adjusted by `gain_db` → `01_…`, `02_…`.
2. Stems are placed at absolute times (`adelay`) and summed (`amix`) → `03_vo_assembled.wav`.
   Its integrated loudness is then measured with `ebur128` — this is the **voice reference** every
   bed level is expressed against.
3. The bed is trimmed or looped to runtime and gain-shifted so its integrated loudness sits
   `gain_db` below the voice reference → `04a_bed_conformed.wav`. **No envelope yet.**
4. The **computed gain envelope** is applied → `04b_bed_ducked.wav`. The envelope is a piecewise
   function over the runtime: explicit `windows` first, then `duck_db` across any span where a stem
   is sounding, then `gain_db` everywhere else (precedence per §3), with `duck_attack_ms` /
   `duck_release_ms` ramps and `fades` shaping the transitions. Because every stem's placement and
   duration are known before rendering, this envelope is fully determined ahead of time.
5. SFX are placed, gain-adjusted, and summed with the above → `05_mix_pre-loudnorm.wav`.
6. `loudnorm` pass 1 (analysis) → `loudnorm_pass1.json`, retained in `work/` so `verify` can
   re-check linearity later.
7. `loudnorm` pass 2 with measured values, `linear=true`, followed by an explicit
   `aresample=48000` → `06_mix_final.wav`.

`04a_bed_conformed.wav` exists solely so stage F can measure the envelope in isolation — see stage
F's duck-depth check for why comparing ducked-vs-unducked is the only sound method.

Two things this stage must assert rather than assume:

- **`loudnorm` internally resamples to 192 kHz.** Without the explicit `aresample=48000`, the mix
  silently comes out at 192 kHz.
- **`linear=true` silently falls back to dynamic mode** when true-peak limiting is required. Stage C
  parses pass 2's reported `normalization_type` and fails the run if it is not `linear`. Otherwise
  the determinism claim is void.

**Why a computed envelope rather than `sidechaincompress`:** compressor duck depth is
program-dependent, so `duck_db: -22` could never be honored exactly and its measurement would be
flaky. Because every stem's placement is pre-authored, the exact ducking schedule is known ahead of
time. An envelope is smaller, deterministic, and verifiable.

### Stage D — assemble → `work/<mode>/master.mp4`

One ffmpeg invocation: concat demuxer over the stage-A clips → overlay chain → mux
`06_mix_final.wav` → final encode. The result stays in `work/` until stage F passes it (§2 rule 5).

- Overlay gating is `enable='gte(t,IN)*lt(t,OUT)'`. **`between(t,a,b)` is inclusive at both ends**,
  which would render adjacent cards (one ending at 2.0, the next starting at 2.0) simultaneously for
  one frame.
- Because compositing happens over the already-concatenated video, an overlay spanning a shot cut
  needs no special handling.
- The filtergraph is written to `work/<mode>/graph_assemble.txt` and passed via
  `-filter_complex_script`, which eliminates the entire class of Windows `C:\` colon-escaping bugs.
- `concat.txt` uses forward slashes and is read with `-safe 0`.
- Final encode: `delivery` settings, BT.709 tagged, `-movflags +faststart`. **Draft mode overrides
  `delivery.crf` to 30 and `delivery.preset` to `ultrafast`**; every other delivery setting is
  honored so a draft still exercises the real conformance path.

### Stage E — derive → `out/`

- **Cover:** conform `cover.source` to 1080×1920, composite its named overlays, write PNG. One
  output, 9:16 only — a 16:9 thumbnail variant is deferred, because there is no unambiguous way to
  derive a 16:9 crop from a 9:16 composition without a crop rectangle the spec does not carry.
- **Captions:** render `captions[]` to `.srt` and to `.ass`, styled from the style named by
  `captions_style` (a top-level spec field). It is not hardcoded to `styles.card`, since nothing
  requires a spec to define a style by that name.

### Stage F — verify → `out/<slug>_vNN_qa.{json,md}`

| Check | Method | Hard failure when |
|---|---|---|
| Container/stream conformance | `ffprobe` | duration, fps, resolution, SAR, `pix_fmt`, codec, or profile ≠ spec |
| Color tagging | `ffprobe` | colorspace/primaries/trc ≠ bt709 |
| Audio conformance | `ffprobe` | codec ≠ AAC-LC or rate ≠ 48000 |
| Integrated loudness | `ebur128` on the master | > 1.0 LU from `integrated_lufs` |
| True peak | `ebur128` on **`06_mix_final.wav`**, not the master | exceeds `true_peak_dbtp` |
| Loudnorm linearity | parse `loudnorm` pass 2 output | `normalization_type != "linear"` |
| Duck depth | `ebur128` over identical windows on **`04b_bed_ducked.wav` vs. `04a_bed_conformed.wav`** | achieved gain > 1.5 dB from the intended envelope value |
| Safe zone | overlay bbox JSON from stage B ⊆ `safe_zone` | any overlay's ink escapes the safe zone |
| Timeline integrity | Σ shot frames vs. audio frames vs. container duration | mismatch exceeding the larger of one frame or 50 ms |
| Placeholders | manifest | any placeholder present in **final** mode |
| Contact sheet | one frame from each shot's midpoint | never fails; informational |

Three of these measurement choices are deliberate and load-bearing:

- **Duck depth compares the ducked bed against the *conformed* bed over identical windows**, not the
  ducked bed inside-voice against outside-voice. The naive comparison measures the envelope *plus
  the music's own dynamics*, which routinely swing more than 1.5 dB on real material and would
  false-fail a correct render. Differencing the two bed intermediates isolates exactly the gain the
  envelope applied. Attack and release ramp regions are excluded from the measurement windows.
- **True peak is measured on `06_mix_final.wav`, before AAC encoding.** AAC decode can overshoot the
  encoder's input by roughly 0.3–1 dB, so a mix correctly normalized to −1.5 dBTP would spuriously
  fail if measured on the master.
- **Timeline integrity allows the larger of one frame or 50 ms of slack.** AAC priming and padding
  shift container duration by roughly 20–45 ms — which at 30 fps exceeds a single 33 ms frame, so a
  one-frame tolerance would intermittently fail correct renders.

**Frame checksums are deliberately not used.** libx264 output varies by build and thread count, so a
checksum would produce false failures rather than evidence. Probe, loudness, and bounds checks are
the verification surface.

`qa.json` is the machine-readable record; `qa.md` is the human summary.

**`verify` on a workspace whose `work/` has been cleaned runs a degraded check set.** Duck depth,
safe zone, loudnorm linearity, and placeholder detection all depend on `work/` artifacts. When those
are absent, each is reported as `unavailable` — never as passed — and `verify` exits 4 to distinguish
"could not fully verify" from "verified and failed."

---

## 5. Caching

`work/<mode>/manifest.json` maps each artifact to the hash of everything that determines it. A stage
is skipped when its hash matches.

The hash **must** include: the relevant spec fragment, the content hash of every input asset, the
content hash of every referenced font file, the ffmpeg build string, and the run mode. A font swap
that did not invalidate every overlay PNG, or a draft artifact satisfying a final-mode lookup, are
the two worst failures this design could produce; both are prevented here, the latter reinforced by
the `work/draft` ÷ `work/final` split.

Practical effect: changing one card's copy re-runs stages B, D, E, F and leaves the 15 shot clips
untouched.

**A total cache hit does not mint a new version.** If every stage hits cache *and* an existing
`out/` version was produced from an identical manifest, `render` reports "no changes; `vNN` is
current" and exits 0 without re-encoding or allocating a version. `--force` overrides this and mints
a new version anyway. Without this rule, re-running `render` would quietly fill `out/` with
byte-identical files under climbing version numbers.

---

## 6. Failure handling

**`preflight` runs to completion before a single frame renders, and reports every problem at once**
rather than the first:

- Spec schema and internal-consistency validation (§3).
- Every referenced asset exists and probes cleanly.
- `source_in`/`source_out` fall inside the source's real duration.
- Every referenced font file loads.
- ffmpeg and ffprobe are present, are 8.x, and have libx264. **libass is not required** — ASS
  burn-in was rejected in favor of Pillow compositing, and the `.ass` sidecar is text written by
  Python, never rendered by the module.
- The longest path the run will generate is ≤ 255 characters.

In **final** mode any preflight failure aborts and nothing renders. In **draft** mode a missing
*asset* becomes a placeholder; every *spec* error still aborts.

**Draft placeholders cover visual assets and audio stems, but by different rules.** A missing image
or clip becomes a magenta slate of the shot's own duration, which the spec already knows. A missing
audio stem has no known duration — durations come from files — so it can be synthesized as silence
**only if that stem declares `duration_s`**; without it, the run aborts even in draft mode, naming
the stem and the missing field. A missing music bed or SFX file is simply omitted in draft, and
listed as omitted in the QA report.

Every ffmpeg command line is written to `logs/<timestamp>_<mode>.log` **before** it executes, so a
failure hands you a pasteable command rather than a traceback wrapping a subprocess error. Non-zero
ffmpeg exits raise with the command and the stderr tail attached. All subprocess calls pass argv
lists; `shell=True` is never used.

---

## 7. Testing

**Pure-function unit tests (no rendering):**

- `naming.py` — every path and filename form, including version increment and mode partitioning.
- `spec.py` — frame quantization on boundaries not durations; the non-frame-aligned warning
  (`2.875 s` → 86.25 frames at 30 fps); rejection of non-contiguous shots, overlapping captions,
  out-of-enum values, and unfittable text.
- Motion math — `anchor_start`/`anchor_end`/`hold_s`/`ease` → per-frame crop rect, including that
  equal anchors produce a pure push and unequal anchors produce a drift.
- Duck-envelope computation from stem spans, including window overrides and fades.
- Text layout — wrapping, hard breaks, accent-span parsing, `max_lines` overflow.

**Golden-image tests:** `overlays.py` renders each fixture card and is compared against a committed
PNG. Catches font, padding, and accent-parsing regressions. Three provisions keep these from
becoming brittle busywork, and all three are required rather than optional: `Pillow` and its bundled
freetype are **pinned to exact versions** in `requirements.txt` (glyph rasterization shifts between
builds); "within tolerance" means a **stated RMSE threshold**, not visual similarity; and these
tests are marked Windows-only, because font rasterization is not portable.

**Filtergraph snapshot tests:** build the graph string for a fixture spec and diff against a
committed golden. Catches accidental changes without rendering anything. **Absolute paths are
tokenized before diffing** (`<WORK>`, `<ASSETS>`, `<FONT>`) — an untokenized golden embeds one
machine's `C:\Users\…` paths and fails on every other machine, including the same machine under a
different workspace root.

**One end-to-end fixture:** a 6-second, 3-shot spec over tiny generated assets (solid-color PNGs,
sine WAVs) committed under `tests/fixtures/`. Fast enough to run on every change, and **its
assertions are the QA report itself** — which means stage F is exercised constantly rather than only
in anger.

---

## 8. Known v1 limitations, stated rather than hidden

- **Only `cut` and `whip` transitions.** Dissolves, film burns, and every other transition are
  rejected at validation with an explicit "not implemented in v1" message rather than silently
  substituting a cut.
- **No pan without scale.** `anchor_start`/`anchor_end` express drift during a scale; a pure
  translate at constant scale is not expressible.
- **`captions[]` is not cross-checked against the audio.** Nothing verifies that a caption's timing
  matches when the words are actually spoken; that would require the forced alignment this design
  deliberately excludes. The QA report states this explicitly rather than implying the sidecars are
  verified.
- **1080×1920 only.** Other aspect ratios are rejected at validation. Cross-platform variants
  (square, 4:5) are deferred.
- **No hardware encoding.** NVENC output varies by driver version, which would undermine
  reproducibility.

---

## 9. Deferred work (explicitly out of scope for v1)

1. **The `assembly.md` → `render-spec.json` adapter.** This is the pipeline connection, and it is a
   separate module with its own spec. Keeping it out of v1 is what lets the stitcher be tested
   entirely against hand-authored fixtures.
2. **Cross-platform output variants** (TikTok/Reels safe-zone differences, square/4:5 crops) and a
   16:9 thumbnail variant of the cover. All of these need a crop rectangle the spec does not
   currently carry.
3. **A `stitcher` skill or `pipeline-app` stage** exposing the module through the existing UI.
4. **Karaoke captions.** If a non-RGS brand ever needs word-level captions, that is an optional
   alignment stage feeding `overlays[]`, not a change to this design.

---

## Review notes

A Fable 5 review pass was run against the design before this document was written. It found six
technical errors that would have shipped, and several spec holes. All are corrected above.

**Accepted — technique:**

1. `scale`+`crop` does not fix Ken Burns judder on its own; `crop` output size is init-fixed and its
   x/y still snap to integer pixels. Supersampling is the operative fix. §4 stage A rewritten.
2. `sidechaincompress` cannot honor `duck_db` deterministically and would make its own QA check
   flaky. Replaced with a computed gain envelope — smaller *and* more verifiable. §4 stage C.
3. `between(t,in,out)` is inclusive at both ends; adjacent cards would double-render for one frame.
   Now `gte*lt`. §4 stage D.
4. `loudnorm` resamples internally to 192 kHz; explicit `aresample=48000` added. §4 stage C.
5. `loudnorm`'s `linear=true` silently falls back to dynamic mode; now asserted. §4 stage C, §4
   stage F.
6. swscale defaults RGB→YUV to BT.601 while players assume BT.709 for HD — a palette shift on
   exactly the colors the reference plan makes binding. Forced conversion and tagging added. §4
   stage A, verified in stage F.

**Accepted — spec holes:** `source_in`/`source_out`; per-stem `gain_db`; text wrap semantics
(`max_width_px`, `max_lines`, `\n`); per-window bed `level_db`; `hold_s` and
`anchor_start`/`anchor_end`; cover modeled as a conform rather than a frame extract; and the
`captions[]` block — the review's best catch, that sidecar captions had no honest data source.

**Accepted — architecture:** quantize boundaries not durations; partition the cache by run mode;
include the ffmpeg build and font bytes in cache keys; drop frame checksums; measure duck depth on
the retained bed intermediate; conform Kling's fps in stage A; use `-filter_complex_script` on
Windows.

**Rejected:** the recommendation to cut draft-mode placeholders (draft = fast preset only, with
missing assets aborting in both modes). That deletes the capability's whole purpose — previewing
pacing and card legibility before spending Midjourney and ElevenLabs credits — and the "subsystem"
is one function drawing a slate through the Pillow renderer that already exists. The real risk the
review identified was cache poisoning, which is addressed by the mode-partitioned cache instead.

### Third review pass (against the implementation plan)

A fresh Fable 5 reviewer read `docs/superpowers/plans/2026-08-06-automated-asset-stitcher.md`
against this spec and found nine issues that would have broken execution. Two required amending
this document rather than only the plan:

- **The whip lost its slide (§3).** The plan's first implementation used `boxblur` with per-frame
  radius expressions — which cannot work, since `boxblur`'s radii are evaluated once at filter init
  and their expressions cannot reference `n` or `t`. Rewriting it on `avgblur` (which takes separate
  `sizeX`/`sizeY`, so it is genuinely directional) gated by `enable=` fixed the blur. The translate
  was then dropped entirely: this spec had required edge-clamped fill, and FFmpeg has no
  edge-clamping pad. A blur-only whip is the honest v1.
- **Timeline slack was too tight (§4 stage F).** One frame is 33 ms at 30 fps, but this document's
  own text puts AAC priming/padding at 20–45 ms — so the stated tolerance was narrower than the
  error it exists to absorb, and would have flaked on correct renders.

The remaining seven were plan-only defects: a still's `-loop 1` input defaulting to 25 fps so the
Ken Burns move silently never completed; a missing `SUPERSAMPLE_*` import; and four tests that were
broken exactly as printed (an illegal walrus in an `assert`, a mock that never wrote the file its
test asserted on, a spec written into a directory that was never created, and a duck check that
raised `ValueError` on the fixture it shipped with). All are corrected in the plan.

**Reversed on review:** the whip transition, originally cut from v1. The review's framing — that v1
would otherwise be unable to render its own canonical upstream artifact, which specifies a whip-out
at 45 s — is correct, and the implementation is small. It is in v1.

### Second review pass

A second Fable 5 pass was run against this written document, checking both whether the first pass's
corrections had landed *correctly* and reviewing the roughly half of the spec it had never seen.
Every first-pass correction verified as landed except one, and that one was broken by an edit made
during the author's own self-review rather than by the original write-up:

- **Ducking semantics were incoherent and are now fixed (§3 audio, §4 stage C, §4 stage F).** The
  self-review had redefined `gain_db`/`duck_db` as "absolute bed levels," which is meaningless for a
  gain applied to a bed file of unknown inherent loudness — and the accompanying example (−18 → −22)
  implied a 4 dB duck where the corpus calls for the bed to sit 15–20 dB below the voice. Both are
  now defined as **levels relative to the measured voice track**, which is the only reading
  consistent with the corpus stating the figure both ways and glossing them as equivalent. The QA
  check reverted to measuring a bed-vs-voice relationship rather than an absolute level.
- **The Ken Burns mechanism was named (§4 stage A).** "The crop is animated across frames" is not
  implementable: `crop`'s `w`/`h` are evaluated once at init. The spec now mandates
  `scale=eval=frame` feeding a fixed-size `crop`, which is the only arrangement that produces a zoom.

Also corrected: the duck-depth check compared ducked-vs-unducked *voice spans*, which measures the
music's own dynamics and would false-fail real material — it now differences the two bed
intermediates; true peak moved off the master to pre-AAC, where it is not distorted by codec
overshoot; timeline integrity gained one frame of slack for AAC priming/padding; a leftover libass
preflight requirement was dropped (nothing uses it); version allocation moved to QA-pass-only,
resolving a contradiction between §2 rule 5 and stage D; `validate`'s `source_in` rule was split so
it no longer requires probing assets it is defined as not touching; the whip gained a required
`direction` and an explicit per-side frame count; the `.ass` sidecar style became a spec field
rather than a hardcoded `styles.card`; draft-mode audio placeholders were specified; total-cache-hit
behavior was specified; and the golden-image and filtergraph-snapshot tests gained the three
provisions (pinned Pillow/freetype, a numeric RMSE threshold, tokenized paths) without which they
would have been brittle busywork.
