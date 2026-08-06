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
python -m stitcher verify <slug> [--version NN] # re-run stage F against an existing output
python -m stitcher clean <slug> [--mode MODE]   # delete work/, keep out/ and logs/
```

`render` exits 0 on success, 1 on preflight failure, 2 on render failure, 3 on QA failure (the
output file exists but does not meet spec). `validate` exits 0 or 1.

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
          04_bed_ducked.wav
          05_mix_pre-loudnorm.wav
          06_mix_final.wav
          loudnorm_pass1.json
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
5. **`out/` is version-stamped and never overwritten.** `_vNN_` bumps on every successful final
   render, so a re-render after a fix cannot silently clobber a reviewed output. The version is
   determined by scanning existing `out/` filenames and incrementing the maximum. **Draft outputs are
   not versioned** — they write `<slug>_draft_1080x1920.mp4` and are overwritten on every draft run,
   because a draft is a disposable look, not a reviewable artifact.
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
- `transition_in` ∈ `cut` | `whip`. `whip` is a 4-frame directional blur-and-slide into the incoming
  shot; the outgoing shot's tail carries the matching blur.

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
  "stems": [ { "id": "vo-child", "file": "vo_child_00_hook.wav", "at": 0.0, "gain_db": 0.0 } ],
  "bed": {
    "file": "music_bed.mp3", "gain_db": -18.0, "duck_db": -22.0,
    "duck_attack_ms": 120, "duck_release_ms": 400,
    "windows": [ { "in": 0.0, "out": 3.0, "mode": "out", "level_db": null },
                 { "in": 17.0, "out": 26.0, "mode": "ducked", "level_db": -26.0 } ],
    "fades": [ { "at": 3.0, "kind": "in", "ms": 300 } ]
  },
  "sfx": [ { "file": "hit.wav", "at": 0.2, "gain_db": -12.0 } ],
  "loudness": { "integrated_lufs": -14.0, "true_peak_dbtp": -1.5 }
}
```

- `stems[].gain_db` is what makes the ±1 LU speaker-handoff match expressible. Without it the
  hardest audio move in the reference plan has nowhere to live.
- `bed.windows[].mode` ∈ `out` | `ducked` | `full`, with an optional `level_db` override so a
  multi-movement music arc is expressible rather than just duck-on/duck-off.
- **`gain_db` and `duck_db` are both absolute bed levels, not deltas.** `gain_db` is the bed's level
  when no stem is sounding; `duck_db` is its level while a stem is sounding. In the example above the
  bed sits at −18 dB and drops to −22 dB under voice. `windows[].level_db`, where present, overrides
  both for that window.
- `duck_db` is **intent**. The module computes a deterministic gain envelope from the stem spans to
  achieve it (see §4, stage C). Stage F measures the achieved delta.

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
- `source_in`/`source_out` absent on a `kind: "clip"` shot whose source is longer than the beat.

---

## 4. The six stages

Each stage writes named artifacts and is independently cacheable. Exactly two encodes occur across
the whole run.

### Stage A — shots → `work/<mode>/shots/NNN_<id>_<slug>.mkv`

Conforms every source to one profile, because the concat demuxer requires identical codec,
`pix_fmt`, timebase, SAR, and frame rate: `canvas.fps` via `-fps_mode cfr`, SAR 1:1, BT.709 tagged.
Kling clips commonly arrive at 24 or 25 fps and must be conformed here.

**Stills** get their motion by **supersampling**: the source is scaled so the *narrowest crop window
the move will use* is at least 3.5 × 1080 px wide, the crop is animated across frames at that
working resolution, and each frame is downscaled to 1080×1920 with lanczos. Both `zoompan` and
`crop` quantize position to integer pixels; supersampling is what turns that quantization into
sub-pixel motion at output scale, and it is the operative fix regardless of which filter performs
the move.

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
3. The bed is trimmed/looped to runtime, then a **computed gain envelope** is applied →
   `04_bed_ducked.wav`. The envelope is derived from the stem spans: baseline `gain_db`, `duck_db`
   during any span where a stem is sounding, per-window `mode`/`level_db` overrides, and `fades`,
   with `duck_attack_ms`/`duck_release_ms` shaping the transitions.
4. SFX are placed and summed with the above → `05_mix_pre-loudnorm.wav`.
5. `loudnorm` pass 1 (analysis) → `loudnorm_pass1.json`.
6. `loudnorm` pass 2 with measured values, `linear=true`, followed by an explicit
   `aresample=48000` → `06_mix_final.wav`.

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

### Stage D — assemble → `out/<slug>_vNN_1080x1920.mp4`

One ffmpeg invocation: concat demuxer over the stage-A clips → overlay chain → mux
`06_mix_final.wav` → final encode.

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
- **Captions:** render `captions[]` to `.srt` and to `.ass` (styled from `styles.card`).

### Stage F — verify → `out/<slug>_vNN_qa.{json,md}`

| Check | Method | Hard failure when |
|---|---|---|
| Container/stream conformance | `ffprobe` | duration, fps, resolution, SAR, `pix_fmt`, codec, or profile ≠ spec |
| Color tagging | `ffprobe` | colorspace/primaries/trc ≠ bt709 |
| Audio conformance | `ffprobe` | codec ≠ AAC-LC or rate ≠ 48000 |
| Integrated loudness | `ebur128` on the master | > 1.0 LU from `integrated_lufs` |
| True peak | `ebur128` on the master | exceeds `true_peak_dbtp` |
| Loudnorm linearity | parse `loudnorm` pass 2 output | `normalization_type != "linear"` |
| Duck depth | `ebur128` windowed on `04_bed_ducked.wav`, inside vs. outside voice spans | achieved level > 1.5 dB from `duck_db` (measurement tolerance; the envelope itself is exact) |
| Safe zone | overlay bbox JSON from stage B ⊆ `safe_zone` | any overlay's ink escapes the safe zone |
| Timeline integrity | Σ shot frames vs. audio frames vs. container duration | any mismatch |
| Placeholders | manifest | any placeholder present in **final** mode |
| Contact sheet | one frame from each shot's midpoint | never fails; informational |

Duck depth is measured on `04_bed_ducked.wav` rather than the master because once voice and bed are
summed they cannot be separated. That intermediate is retained specifically for this check.

**Frame checksums are deliberately not used.** libx264 output varies by build and thread count, so a
checksum would produce false failures rather than evidence. Probe, loudness, and bounds checks are
the verification surface.

`qa.json` is the machine-readable record; `qa.md` is the human summary. Stage F exits non-zero on
any hard failure — the output file still exists, but the run is not reported as successful.

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

---

## 6. Failure handling

**`preflight` runs to completion before a single frame renders, and reports every problem at once**
rather than the first:

- Spec schema and internal-consistency validation (§3).
- Every referenced asset exists and probes cleanly.
- `source_in`/`source_out` fall inside the source's real duration.
- Every referenced font file loads.
- ffmpeg and ffprobe are present, are 8.x, and have libx264 and libass.
- The longest path the run will generate is ≤ 255 characters.

In **final** mode any preflight failure aborts and nothing renders. In **draft** mode a missing
*asset* becomes a placeholder; every *spec* error still aborts.

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
PNG within tolerance. Catches font, padding, and accent-parsing regressions.

**Filtergraph snapshot tests:** build the graph string for a fixture spec and diff against a
committed golden. Catches accidental changes without rendering anything.

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

**Reversed on review:** the whip transition, originally cut from v1. The review's framing — that v1
would otherwise be unable to render its own canonical upstream artifact, which specifies a whip-out
at 45 s — is correct, and the implementation is small. It is in v1.
