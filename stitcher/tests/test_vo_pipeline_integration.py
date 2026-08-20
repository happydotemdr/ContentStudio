"""Integration test locking in the vo_alignment -> vo_assemble -> envelope
composition: a single continuous VO take, split into per-beat stems at
measured boundaries, must actually reproduce stitcher's automatic ducking
behavior (the entire reason this branch exists) -- the bed sits at
`duck_db` under speech and returns to `gain_db` baseline in every gap
between segments.

Nothing else in the committed suite exercises all three modules together:
test_vo_alignment.py covers `derive_segments` alone, test_envelope.py covers
the envelope math against hand-built `Stem`/`Bed` fixtures, and
test_vo_assemble equivalents cover `build_audio_config` alone. Task 11's
real-run harness proved the full composition once by hand
(docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md, a
+7.00dB swing between gain_db and duck_db) but was gitignored and deleted per
the plan's own design -- this test makes that proof permanent, fast, and
committed.

No ffmpeg, no network, no real audio files: `stem_spans`, `build_breakpoints`,
and `level_at` are pure functions over the `Audio`/`Stem`/`Bed` objects and a
`durations` dict supplied directly -- they never touch disk.
"""

import pytest

from stitcher import envelope
from stitcher.vo_alignment import derive_segments
from stitcher.vo_assemble import build_audio_config

from .test_vo_alignment import _build_case

# The real render values this plan validated against
# (2026-08-19-single-take-vo-pipeline-RESULTS.md): a +7.00dB duck swing.
GAIN_DB = -22.0
DUCK_DB = -29.0


def test_derived_segments_duck_correctly_through_the_full_pipeline():
    beat1, beat2, beat3 = "First beat here.", "Second beat now.", "Third and final."
    gap = 1.5  # seconds -- well clear of the default 120ms attack / 400ms release
    text, alignment = _build_case([beat1, beat2, beat3], [gap, gap])

    # Step 1: real Segment objects from the real derive_segments boundary math.
    segments = derive_segments(text, alignment)
    assert len(segments) == 3

    # Step 2: a real Audio config from the real assembly function.
    stem_files = [f"{segment.name}.wav" for segment in segments]
    audio = build_audio_config(
        segments=segments,
        stem_files=stem_files,
        bed_file="bed.mp3",
        bed_gain_db=GAIN_DB,
        bed_duck_db=DUCK_DB,
        delivery_lufs=-14.0,
        delivery_tp_dbtp=-1.0,
    )

    assert audio.bed is not None
    assert [stem.id for stem in audio.stems] == [s.name for s in segments]

    # Step 3: the real ducking envelope, queried at points that prove the
    # mechanism -- no real audio files needed, just the durations envelope.py
    # asks for.
    durations = {
        stem_file: segment.duration
        for segment, stem_file in zip(segments, stem_files)
    }
    spans = envelope.stem_spans(audio.stems, durations)
    runtime = spans[-1][1] + 2.0
    breakpoints = envelope.build_breakpoints(audio.bed, spans, runtime=runtime)

    # (a) mid-speech, well inside the first segment: fully ducked.
    mid_speech = spans[0][0] + (spans[0][1] - spans[0][0]) / 2
    assert envelope.level_at(breakpoints, mid_speech) == pytest.approx(DUCK_DB)

    # (b) mid-gap between segment 1 and segment 2, clear of both the release
    # ramp (400ms after segment 1 ends) and the attack ramp (120ms before
    # segment 2 begins): back at the bed's baseline gain.
    gap1_start, gap1_end = spans[0][1], spans[1][0]
    assert gap1_end - gap1_start == pytest.approx(gap)
    mid_gap1 = gap1_start + (gap1_end - gap1_start) / 2
    assert envelope.level_at(breakpoints, mid_gap1) == pytest.approx(GAIN_DB)

    # (c) same check on the second gap, for good measure.
    gap2_start, gap2_end = spans[1][1], spans[2][0]
    assert gap2_end - gap2_start == pytest.approx(gap)
    mid_gap2 = gap2_start + (gap2_end - gap2_start) / 2
    assert envelope.level_at(breakpoints, mid_gap2) == pytest.approx(GAIN_DB)

    # (d) and mid-speech in the final segment too, so the assertion isn't
    # coincidentally true only for the first stem.
    mid_speech_3 = spans[2][0] + (spans[2][1] - spans[2][0]) / 2
    assert envelope.level_at(breakpoints, mid_speech_3) == pytest.approx(DUCK_DB)
