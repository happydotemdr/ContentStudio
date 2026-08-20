# Design — Native Single-Generation Render Mode

## Problem

The single-take VO pipeline (`docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-implementation.md`,
validated in `...-RESULTS.md`) replaced per-beat ElevenLabs generation with one continuous take, but still
splits that take into per-beat stems (`vo_split.py`) so each stem can be independently loudness-conditioned
(`precondition.condition_clip`) and so `stitcher`'s ducking envelope (`envelope.py`) has real gaps to detect
and ride. In production use, the delivered mix from that pipeline had two audible problems, root-caused this
session:

- **Bed level:** the ducking envelope's `gain_db`/`duck_db` constants (`-22`/`-29`, inherited from an era
  before the ducking math actually worked) left the bed at roughly -42 LUFS integrated for ~94% of the
  runtime — effectively inaudible, since the single-take architecture's near-continuous narration leaves very
  little real gap time for the bed to rise into.
- **Perceived "stutter":** most likely the audible signature of the bed surfacing briefly (~1s) out of
  near-silence and vanishing again at each of the 7 real inter-beat gaps — a symptom of the same root cause,
  not a separate defect (confirmed: no digital clipping, no literal duplicated audio, no glitch in the
  envelope math itself).

Both problems trace back to the same architectural choice: **automatic, math-derived mixing** (measure the
voice, derive a bed gain relative to it, ride an auto-detected envelope) applied to a single continuous take
that doesn't have many/wide gaps to ride. Three rounds of level-tuning (the A/B candidates already generated
this session) can paper over the symptom, but the underlying question is whether split-condition-envelope
machinery is worth keeping at all, given ElevenLabs' own output is already properly balanced and
production-ready, and its `/with-timestamps` alignment already gives exact timing for free.

## Goals

Design a **new, additive** stitcher render mode — the existing stitched/ducked pipeline is untouched and
remains available — that:

1. Uses the single continuous ElevenLabs take as the final voice track, unmodified, with no per-beat split
   and no per-beat loudness conditioning.
2. Uses the take's own `/with-timestamps` alignment as the single source of timing truth for captions, shot
   cuts, and music composition — eliminating hand-authored timing wherever the data already provides it.
3. Builds the music bed as one Eleven Music generation whose *arrangement* (not post-hoc volume automation)
   supplies the loud/quiet dynamic — sparse under narration, full in real pauses — so no auto-detected
   ducking envelope is needed for this mode.
4. Keeps the four creative-decision skills (`voiceover-brief`, `music-brief`, `visual-prompts`,
   `shorts-assembly`) completely unchanged. This is a tooling-layer project only.
5. Caps iteration on a real API generation at 2 attempts per track (VO, music — independent budgets), gated
   by a required proof that attempt 2 changed the measured output in the direction the settings change
   predicted.

## Non-goals

- Replacing or deprecating the existing stitched/ducked pipeline.
- Changing the validated `RenderSpec`/`Shot`/`Caption`/`Bed`/`Loudness` schema in `stitcher/stitcher/spec.py`.
- Changing `audio.py`, `envelope.py`, `assemble.py`, `shots.py`, `motion.py`, or any creative-decision skill.
- Sub-beat cut timing (multiple shots inside one beat) — out of scope per the "one visual per beat" decision
  below; a future project could add it without touching this one.
- Automatic correction of flagged loudness/peak outliers — flagging is read-only telemetry, never a fix.

## Decisions

These were made collaboratively during brainstorming; recorded here so the plan phase doesn't re-litigate
them.

- **VO processing: none.** The raw ElevenLabs take is the final voice track. No `precondition.condition_clip`
  call for VO in this mode. Its LUFS is still *measured* (not modified) to compute the bed's relative gain
  and for the flagging check — measurement is not processing.
- **Music dynamics: baked into the Eleven Music generation**, via a composition plan whose chunk boundaries
  and per-chunk style prompts are derived from real segment/gap timing and the music-brief's bed arc. No
  manually-authored volume windows, no auto-detected envelope, for this mode.
- **Shot granularity: one visual per beat**, held for the beat's full measured duration. No sub-division of
  long beats. Leans on stitcher's existing Ken Burns motion to keep long holds visually alive.
- **Skill scope: tooling-only.** No `SKILL.md` changes. The four creative-decision skills keep producing
  exactly the outputs they produce today; this project only changes how those outputs get turned into API
  calls and a `render-spec.json`.
- **Iteration cap: 2 attempts each, independently, for VO and for music.** Not a shared budget, not a
  per-issue budget.
- **Safety net: read-only outlier flagging**, for both VO (per-beat) and music (per-chunk), against each
  track's own median. Flags are logged, never acted on automatically.

## Architecture

A new module, `stitcher/stitcher/native_pipeline.py`, orchestrates this mode. It imports the existing
`vo_alignment`, `vo_timing`, `spec`, and `ffmpeg` modules and calls the existing, unmodified render entry
point at the end. It does **not** import `vo_split` or `precondition` — those modules remain used only by the
existing stitched mode.

```
ElevenLabs /with-timestamps  →  vo_alignment.derive_segments()          [reused, unmodified]
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
        native_pipeline.build_shots   vo_timing.derive_captions   native_pipeline.build_music_plan
        (NEW — one Shot per segment)  (reused, unmodified)        (NEW — Eleven Music CompositionPlan)
                    │                     │                     │
                    │                     │           elevenlabs-music tooling call [existing, unmodified]
                    │                     │                     │
                    └─────────────────────┴─────────────────────┘
                                          ▼
                    native_pipeline.assemble_spec()  (NEW — builds RenderSpec)
                    - Stem(file=raw_take, at=0.0, duration_s=runtime)   ← whole take, unsplit
                    - Bed(file=generated_bed, gain_db=X, duck_db=X)     ← flat, envelope is a no-op
                                          ▼
                    stitcher's existing render entry point              [reused, unmodified]
```

### `build_shots(segments, asset_manifest) -> list[Shot]`

Pure function. For each segment (from `derive_segments`), emits one `Shot` with `start`/`end` set exactly to
the segment's `at`/`at + duration`, and `kind`/`source`/`source_in`/`source_out`/`motion` taken from a small
per-beat asset manifest — a plain mapping of beat name to the image or I2V file the operator (via
`visual-prompts`) already chose for that beat, plus a Ken Burns motion direction for `still` shots. This
function does no image/video generation itself; it only positions already-chosen assets on the real timeline.
Invariants asserted (mirroring what `RenderSpec` itself validates): shot count equals segment count, shots are
contiguous, first shot starts at 0.

### `build_music_plan(segments, bed_arc) -> CompositionPlan`

Pure function. Builds an Eleven Music `music_v2` `CompositionPlan.chunks[]`:

- One chunk per real segment (narration span) and one chunk per real inter-beat gap, in timeline order.
  `duration_ms` is the segment's/gap's measured width in milliseconds.
- Each chunk's `positive_styles`/`negative_styles` are derived from the bed arc's existing per-timestamp
  creative call (already expressed in real seconds by `music-brief` today): narration chunks get a sparser
  style description ("sparse pad, minimal percussion"), gap/hook chunks get a fuller one ("full arrangement,
  rhythmic emphasis"), matching whatever the bed arc specifies at that real timestamp.
- `force_instrumental: true` throughout — vocal leakage via negative-style suppression alone is a documented,
  confirmed-insufficient approach (`docs/elevenlabs-music-runbook.md` §7).
- Asserts total chunk count ≤ 30 (Eleven Music's hard limit) and total duration matches the take's runtime
  within rounding tolerance. If a future script's beat count approaches the ceiling, adjacent same-intensity
  chunks would need merging — noted as a documented limit, not built out now since the current 8-beat scripts
  sit at ~15 chunks.

### `assemble_spec(shots, captions, voice_take, music_bed, runtime) -> RenderSpec`

Builds the final `RenderSpec` using only existing `spec.py` classes — no schema changes. Notably:

- `Audio.stems = [Stem(file=voice_take, at=0.0, duration_s=runtime)]` — one stem, the whole unsplit take.
- `Audio.bed = Bed(file=music_bed, gain_db=X, duck_db=X, windows=[], fades=[])` — `gain_db` and `duck_db` set
  to the **same value**. This is the mechanism that makes `_build_bed()`'s existing ducking envelope
  mathematically flat without any change to `audio.py`/`envelope.py`: `stem_spans()`/`build_breakpoints()`
  still run, but every breakpoint resolves to the same level, so the "duck" is a no-op by construction. `X`
  itself is chosen the same way the existing code already does — relative to the take's *measured* (not
  processed) LUFS — since the music's own dynamics are already baked into its arrangement.
- Everything downstream (loudness normalization of the final mix, captions rendering, shot rendering, Ken
  Burns, transitions) is the existing, unmodified render entry point.

### Outlier flagging

A read-only check, run once after VO generation and once after music generation:

- Per-beat LUFS and true-peak of the raw take, measured at each segment's real boundaries via the existing
  `ffmpeg.measure_loudness` (measurement only — no `precondition.condition_clip` call).
- Per-chunk LUFS of the generated bed, measured the same way.
- Flags (logs, does not block or fix) any value deviating from its track's own median by more than a
  threshold (starting point: 3 LU / 3 dB, tunable once real output has been observed).

### Iteration/proof harness

Applies independently to a VO generation attempt and to a music generation attempt. Before a second attempt
is permitted:

- The exact settings/prompt diff between attempt 1 and attempt 2 must be recorded (e.g. a specific
  ElevenLabs voice-setting change, or a specific `positive_styles` change on a specific chunk).
- The same measured-metric battery used for flagging (per-beat/per-chunk LUFS and peak) must be captured for
  both attempts, and the delta must move in the direction the settings change predicts.
- If the measured delta contradicts the predicted direction, that is reported as a finding — not resolved
  with a third attempt. The cap is hard: 2 attempts, full stop, report to the operator.
- Both attempts' settings diff and metrics diff are written to the render's log directory alongside the two
  candidate files, so the choice between them is auditable later.

## Data flow summary

```
script + voiceover-brief + music-brief + visual-prompts   (all existing skill outputs, unchanged)
        │
        ▼
ONE ElevenLabs /with-timestamps call  →  single_take.{mp3,wav} + alignment.json
        │
        ▼
derive_segments (existing)  →  per-beat (name, at, duration)
        │
   ┌────┼────────────────────┬─────────────────────┐
   ▼    ▼                    ▼                     ▼
captions (existing)     shots (NEW)          music composition plan (NEW)
                                                    │
                                          ONE Eleven Music call → music_bed.wav
   │                    │                            │
   └────────────────────┴────────────────────────────┘
                         ▼
              assemble_spec (NEW) → render-spec.json (existing schema)
                         ▼
       existing, unmodified stitcher render entry point → final video
```

## Testing

- **Unit (no API calls):** `build_shots` and `build_music_plan` against synthetic segment lists — shot
  count/contiguity/start-at-0 invariants; chunk duration sum and 30-chunk ceiling; correct sparse/full style
  selection from a synthetic bed arc.
- **Integration (one real end-to-end run, mirrors the Task 11 harness style):** real take + timestamps →
  shots/captions/music-plan → real Eleven Music generation → assembled spec → existing render entry point.
  Asserts: no exceptions, `normalization_type == "linear"`, independent re-measurement of the final mix within
  tolerance, `bed.gain_db == bed.duck_db` (envelope verified flat via the same `envelope.level_at()` query
  technique used in the RESULTS doc), zero unexpected flags (or documented if one legitimately fires), music
  bed runtime matches VO runtime.
- **Explicitly not automatable:** whether the arrangement actually *sounds* sparse under narration and full in
  the pauses is a by-ear judgment, called out in the validation report rather than silently assumed.

## Open risk

"Zero processing, trust ElevenLabs" removes the one safety net the current pipeline has against an
occasional anomalous take (a clipped word, an oddly loud beat). The flagging step gives visibility, not
correction — if flags fire often in practice, that's a signal to revisit this decision, not something this
design resolves in advance.
