import pytest

from stitcher.vo_alignment import Segment
from stitcher.vo_assemble import build_audio_config


def test_builds_one_stem_per_segment_at_its_measured_offset():
    segments = [
        Segment(name="beat1", at=0.0, duration=5.5),
        Segment(name="beat2", at=6.2, duration=4.0),
    ]
    audio = build_audio_config(
        segments,
        stem_files=["beat1_conditioned.wav", "beat2_conditioned.wav"],
        bed_file="BedFull_conditioned.wav",
        bed_gain_db=-22.0,
        bed_duck_db=-29.0,
        delivery_lufs=-14.0,
        delivery_tp_dbtp=-1.0,
    )

    assert len(audio.stems) == 2
    assert audio.stems[0].id == "beat1"
    assert audio.stems[0].file == "beat1_conditioned.wav"
    assert audio.stems[0].at == 0.0
    assert audio.stems[0].gain_db == 0.0
    assert audio.stems[1].id == "beat2"
    assert audio.stems[1].at == 6.2


def test_bed_config_carries_through_with_no_windows_or_fades():
    segments = [Segment(name="only", at=0.0, duration=2.0)]
    audio = build_audio_config(
        segments, ["only.wav"], "bed.wav", bed_gain_db=-13.0, bed_duck_db=-18.0,
        delivery_lufs=-14.0, delivery_tp_dbtp=-1.0,
    )

    assert audio.bed.file == "bed.wav"
    assert audio.bed.gain_db == -13.0
    assert audio.bed.duck_db == -18.0
    assert audio.bed.windows == []
    assert audio.bed.fades == []


def test_loudness_carries_through():
    segments = [Segment(name="only", at=0.0, duration=1.0)]
    audio = build_audio_config(
        segments, ["only.wav"], "bed.wav", -22.0, -29.0,
        delivery_lufs=-14.0, delivery_tp_dbtp=-1.0,
    )
    assert audio.loudness.integrated_lufs == -14.0
    assert audio.loudness.true_peak_dbtp == -1.0


def test_mismatched_segments_and_stem_files_length_raises():
    segments = [Segment(name="a", at=0.0, duration=1.0), Segment(name="b", at=1.0, duration=1.0)]
    with pytest.raises(ValueError, match="must be the same length"):
        build_audio_config(segments, ["only_one.wav"], "bed.wav", -22.0, -29.0, -14.0, -1.0)
