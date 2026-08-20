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
   by a recorded settings diff and a measured-output delta directionally consistent with what that change
   predicted (not a rigorous causal proof — see the Iteration/proof harness section).

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
  **Accepted risk:** an unusually hot take (high LUFS combined with a high true peak — the validated pipeline
  measured raw beats as hot as -4.4 dBTP) can require enough gain during the existing final-mix `loudnorm`
  pass to overshoot the -1 dBTP delivery ceiling, which the pipeline's existing linear-mode gate treats as a
  hard error rather than silently falling back to a dynamic-range-compressing mode. This mode accepts that
  failure mode deliberately: a render fails loud with a clear error on a hot take rather than either silently
  processing the VO (which the mode exists to avoid) or silently accepting a degraded fallback normalization.
  A failed render here is expected to be handled per-render — retry the take (within the iteration cap below)
  or fall back to the existing stitched pipeline for that script — not treated as a design defect.
- **Music dynamics: baked into the Eleven Music generation**, via a composition plan whose chunk boundaries
  and per-chunk style prompts are derived from real segment/gap timing and the music-brief's bed arc. No
  manually-authored volume windows, no auto-detected envelope, for this mode.
- **Shot granularity: one visual per beat**, held for the beat's full measured duration. No sub-division of
  long beats. Leans on stitcher's existing Ken Burns motion to keep long holds visually alive.
  **Acknowledged trade-off:** the existing `shorts-assembly` pacing guidance calls for a visual change roughly
  every ~3s; the two longest beats in the validated take (14.5s and 11.3s) hold a single image for far longer
  than that. This is a deliberate, informed trade-off — eliminating manual sub-beat cut authoring — not an
  oversight. If long single-image holds read as visually static in practice, that's the signal to revisit this
  decision (e.g. via the "let a human author extra cut points" alternative considered and set aside during
  brainstorming), not something this design resolves in advance.
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
        (NEW — one Shot per segment,  (reused, unmodified)        (NEW — one chunk per bed-arc
        gap-absorbing end times)                                  movement, not per segment/gap)
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

Pure function. For each segment (from `derive_segments`), emits one `Shot` whose `kind`/`source`/
`source_in`/`source_out`/`motion` come from a small per-beat asset manifest (see Data contracts below), and
whose `start`/`end` are **not** simply the segment's own `at`/`at + duration` — segments have real gaps
between them (the whole point of this take's pacing), and `RenderSpec` validation requires exact shot
contiguity with the first shot starting at 0 (`spec.py:293-306`). Instead, each shot's `start` is its
segment's `at`, and its `end` is the **next** segment's `at` (the final shot's `end` is the take's total
runtime) — the image simply holds through its trailing gap rather than cutting away at the moment speech
stops. This satisfies contiguity trivially, by construction, with no separate gap-filler shots. This function
does no image/video generation itself; it only positions already-chosen assets on the real timeline.
Invariants asserted: shot count equals segment count, shots are contiguous, first shot starts at 0, last shot
ends at the take's total runtime.

### `build_music_plan(segments, bed_arc) -> CompositionPlan`

**Revised during Opus review:** the original design of one chunk per real segment/gap is invalid — Eleven
Music's `music_v2` bounds every chunk's `duration_ms` to 3,000–120,000 ms (`docs/elevenlabs-music-runbook.md`
§2), and real inter-beat gaps run 0.848–1.428s and one segment (`beat4a`) runs 1.196s — all below the floor.
Micro-per-gap chunking cannot be built as an Eleven Music composition plan at all.

Chunks are built at **bed-arc movement boundaries** instead — the same macro sections `music-brief` already
describes (e.g. "rising urgency 4.0-20.0s"), which are multi-second by construction and comfortably clear the
3,000ms floor. Fine-grained response to a specific pause or emphasis *within* a movement is expressed as a
prompt/style instruction on that movement's chunk (e.g. "arrangement thins briefly in the middle of this
section, around the beat's key line, then returns to full") rather than as a hard chunk boundary — this is
closer to how a real composer would score a live narration anyway, and avoids needing sub-3s chunks entirely:

- One chunk per bed-arc movement, `duration_ms` set to that movement's real span (already expressed in real
  seconds by `music-brief` today) in milliseconds.
- Each chunk's `positive_styles`/`negative_styles` come from the movement's density call in the bed arc
  (sparse/full/medium — see Data contracts) plus any specific in-movement dynamic instruction the bed arc
  calls out (a real pause or hook inside that movement described in prose, translated into a style note).
- `force_instrumental: true` throughout — vocal leakage via negative-style suppression alone is a documented,
  confirmed-insufficient approach (`docs/elevenlabs-music-runbook.md` §7).
- Validates: every chunk's `duration_ms` is ≥3,000ms (fails loud if a movement is shorter — merge with an
  adjacent movement rather than submit an invalid plan), total chunk count ≤30, total duration matches the
  take's runtime within rounding tolerance.

### Data contracts (added during Opus review)

`build_shots` and `build_music_plan` both presuppose structured inputs — `asset_manifest` and `bed_arc` — that
neither skill emits today, and the original design left undefined. Consistent with "tooling-only, skills
unchanged": the skills keep producing prose exactly as they do today; the operator does one small, bounded
transcription step per render, translating that prose into these two lightweight structures. This is a data
contract at the tooling boundary, not a skill change.

- **`asset_manifest`** — one entry per beat name, translating `visual-prompts`' per-beat direction:
  `{beat: str, kind: "still" | "clip", source: str, source_in_s/source_out_s (clip only),
  motion: {kind, amount_pct, anchor_start, anchor_end, hold_s, ease} (still only)}`.
- **`bed_arc_structured`** — one entry per bed-arc movement, translating `music-brief`'s prose bed arc:
  `{label: str, start_s: float, end_s: float, density: "sparse" | "medium" | "full", style_notes: str}`,
  where `style_notes` carries any in-movement dynamic instruction (a real pause or emphasis inside that
  movement) as prose to fold into that chunk's style prompt.

Both are plain data (JSON/dict), no new schema files, validated only by the pure functions that consume them
(missing beat, unparseable density value, etc. raise clearly rather than silently defaulting).

### `assemble_spec(shots, captions, voice_take, music_bed, runtime) -> RenderSpec`

Builds the final `RenderSpec` using only existing `spec.py` classes — no schema changes. Notably:

- `Audio.stems = [Stem(file=voice_take, at=0.0, duration_s=runtime)]` — one stem, the whole unsplit take.
- `Audio.bed = Bed(file=music_bed, gain_db=X, duck_db=X, windows=[], fades=[])` — `gain_db` and `duck_db` set
  to the **same value**. This is the mechanism that makes `_build_bed()`'s existing ducking envelope
  mathematically flat without any change to `audio.py`/`envelope.py`: `stem_spans()`/`build_breakpoints()`
  still run, but every breakpoint resolves to the same level, so the "duck" is a no-op by construction
  (verified against the real `_build_bed()`/`envelope.py` logic during Opus review).
  **`X`'s derivation (revised during Opus review — the original wording, "chosen the same way the existing
  code already does," pointed at the very -22/-29 constants this project exists to replace):**
  `X = voice_lufs_measured + BED_RELATIVE_OFFSET_DB`, where `BED_RELATIVE_OFFSET_DB` is a single explicit
  starting constant — not auto-derived — taken from the corpus-cited mixing guidance already in this repo
  (`.claude/skills/shorts-assembly/references/loudness-and-mix.md`: bed sits "~15-20dB below the voice").
  A concrete starting value (e.g. -17dB, the midpoint) is set once as the mode's default and tuned after
  hearing real output — there is no ducking to compensate for a level that's off, so getting this single
  constant right matters more here than it did in the enveloped pipeline.
- **Bed-duration fail-loud check (added during Opus review):** before handing the spec to the render entry
  point, `assemble_spec` independently measures the generated bed's duration and asserts it matches the
  take's runtime within a tight tolerance (e.g. 50ms). This mode does not rely on `audio.py`'s existing
  `-stream_loop -1 -t runtime` bed-conforming step to mask a mismatch — a bed even slightly short would
  otherwise have its intro silently restart under the outro, and a bed too long would be silently truncated
  mid-arrangement, defeating the entire point of composing dynamics into the arrangement. A mismatch fails the
  render loudly here, before reaching the shared render entry point, rather than degrading silently downstream.
- Everything downstream (loudness normalization of the final mix, captions rendering, shot rendering, Ken
  Burns, transitions) is the existing, unmodified render entry point.

### Outlier flagging

A read-only check, run once after VO generation and once after music generation.

**Corrected during Opus review:** `ffmpeg.measure_loudness(path, log_path)` measures a whole file, not a
window — it cannot measure "at each segment's real boundaries" as originally (incorrectly) written. The
windowed measurement this needs already exists as `verify.measure_window` (`stitcher/stitcher/verify.py`),
which this module imports for this purpose (measurement only — never `precondition.condition_clip`, and
never used to modify the audio).

- Per-beat LUFS and true-peak of the raw take, measured over each segment's real span via
  `verify.measure_window`.
- Per-chunk LUFS of the generated bed, measured the same way over each chunk's real span.
- **Short-window guard:** `verify.py` already treats sub-`MIN_DUCK_WINDOW_S` (0.4s) windows and readings below
  a -70dB floor as unreliable for its own ducking checks; this flagging step applies the same floor. A beat or
  chunk shorter than that minimum is skipped for flagging rather than measured — ebur128 integrated loudness
  over a very short window is not a meaningful reading, and a "flag" built on it would be noise, not signal.
- Flags (logs, does not block or fix) any value deviating from its track's own median by more than a
  threshold (starting point: 3 LU / 3 dB, tunable once real output has been observed). A flag on a beat/chunk
  skipped by the short-window guard cannot occur by construction.

### Iteration/proof harness

Applies independently to a VO generation attempt and to a music generation attempt. Before a second attempt
is permitted:

- The exact settings/prompt diff between attempt 1 and attempt 2 must be recorded (e.g. a specific
  ElevenLabs voice-setting change, or a specific `positive_styles` change on a specific chunk).
- The same measured-metric battery used for flagging (per-beat/per-chunk LUFS and peak) must be captured for
  both attempts, and the delta must be **directionally consistent with** what the settings change predicts.
  **Caveat added during Opus review:** neither ElevenLabs nor Eleven Music generation is fully deterministic
  run-to-run, so a measured delta is evidence consistent with the settings change, not rigorous proof of
  causation — this harness cannot fully separate "the prompt change worked" from "generation noise happened
  to move the same direction." It is deliberately built to this lower, honestly-stated bar rather than
  claiming a certainty the underlying generation doesn't support.
- If the measured delta contradicts the predicted direction, that is reported as a finding (an inconclusive or
  contradicted result) — not resolved with a third attempt. The cap is hard: 2 attempts, full stop, report to
  the operator.
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
captions (existing)     shots (NEW,           music composition plan (NEW,
                         gap-absorbing)        one chunk per bed-arc movement)
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

- **Unit (no API calls):** `build_shots` against synthetic segment lists — shot count/contiguity/start-at-0/
  ends-at-runtime invariants (per the revised gap-absorbing rule above). `build_music_plan` against a
  synthetic `bed_arc_structured` — every chunk's `duration_ms` ≥3,000ms, total duration matches runtime,
  30-chunk ceiling, correct sparse/full style selection per movement.
- **Integration (one real end-to-end run, mirrors the Task 11 harness style):** real take + timestamps →
  shots/captions/music-plan → real Eleven Music generation → assembled spec → existing render entry point.
  Asserts, with concrete tolerances (clarified during Opus review):
  - No exceptions raised.
  - `normalization_type == "linear"` — a documented hard failure (see the accepted-risk note under VO
    processing) is an acceptable *test* outcome for an atypically hot take, not a bug in the test itself.
  - Independent re-measurement of the final mix within 0.5 LU of target (the same tolerance the original
    single-take validation used).
  - The bed envelope is genuinely flat in the *rendered* output — not merely that `Bed.gain_db == Bed.duck_db`
    on the input spec (a trivially-true check by construction) — verified by querying `envelope.level_at()` at
    several real sampled timestamps across the take and confirming they return the same value.
  - Bed duration matches take runtime within 50ms (the fail-loud check from `assemble_spec`, independently
    re-verified here).
  - No flags fire beyond any explicitly pre-documented expected case for that specific take (there are none
    expected for a normal take — any flag on a normal run is itself a finding to investigate, not an assertion
    failure to silence).
- **Explicitly not automatable:** whether the arrangement actually *sounds* sparse under narration and full in
  the pauses is a by-ear judgment, called out in the validation report rather than silently assumed.

## Open risks (updated after Opus review)

- **Zero VO processing removes the one safety net** the current pipeline has against an occasional anomalous
  take (a clipped word, an oddly loud beat) — including, in the worst case, an outright render failure on a
  take too hot for linear-mode normalization (see the accepted-risk note under VO processing). The flagging
  step gives visibility, not correction; a render failure gives an unambiguous stop signal. If either fires
  often in practice, that's a signal to revisit "zero processing," not something this design resolves in
  advance.
- **One visual per beat trades away the corpus's ~3s cut-cadence guidance** on long beats (two beats in the
  validated take run 11–14.5s on a single held image). Deliberately accepted per the brainstorming discussion;
  revisit if long holds read as visually static once actually watched.
- **Shot/chunk boundaries use raw (unrounded) alignment timestamps**, while stitcher's renderer frame-quantizes
  shot boundaries (`spec.py` warns and rounds). A cut can land up to roughly half a frame off the exact
  alignment timestamp — a real but low-severity effect, noted here rather than discovered during
  implementation.
- **The iteration/proof harness cannot fully prove causation** for either track, since neither ElevenLabs nor
  Eleven Music generation is deterministic run-to-run (see the caveat under Iteration/proof harness) — it
  proves directional consistency, not a controlled experiment.
