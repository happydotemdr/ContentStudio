import pytest

from stitcher.vo_alignment import Segment

from native_pipeline.errors import ShotSegmentMismatchError
from native_pipeline.shots import build_shots

MOTION = {
    "kind": "push_in", "amount_pct": 15.0, "anchor_start": [0.5, 0.5],
    "anchor_end": [0.5, 0.5], "hold_s": 0.0, "ease": "linear",
}


def _manifest_entry(beat: str) -> dict:
    return {"beat": beat, "kind": "still", "source": f"{beat}.png",
            "source_in_s": None, "source_out_s": None, "motion": MOTION}


def test_build_shots_absorbs_gap_into_previous_shots_end():
    segments = [
        Segment(name="beat1", at=0.0, duration=5.0),
        Segment(name="beat2", at=6.0, duration=6.0),
    ]
    asset_manifest = [_manifest_entry("beat1"), _manifest_entry("beat2")]

    shots = build_shots(segments, asset_manifest)

    assert shots[0].start == 0.0
    assert shots[0].end == 6.0   # absorbs the 1.0s gap between beat1 and beat2
    assert shots[1].start == 6.0
    assert shots[1].end == 12.0  # 6.0 + 6.0 duration == runtime


def test_build_shots_first_shot_starts_at_zero_and_last_ends_at_runtime():
    segments = [
        Segment(name="beat1", at=0.0, duration=5.074),
        Segment(name="beat2", at=6.037, duration=6.339),
    ]
    asset_manifest = [_manifest_entry("beat1"), _manifest_entry("beat2")]

    shots = build_shots(segments, asset_manifest)

    assert shots[0].start == 0.0
    assert shots[-1].end == 6.037 + 6.339


def test_build_shots_raises_on_beat_name_mismatch():
    segments = [Segment(name="beat1", at=0.0, duration=5.0)]
    asset_manifest = [_manifest_entry("wrong_beat_name")]

    with pytest.raises(ShotSegmentMismatchError):
        build_shots(segments, asset_manifest)


def test_build_shots_sets_shot_fields_from_manifest():
    segments = [Segment(name="beat1", at=0.0, duration=5.0)]
    asset_manifest = [_manifest_entry("beat1")]

    shots = build_shots(segments, asset_manifest)

    assert shots[0].id == "beat1"
    assert shots[0].beat == "beat1"
    assert shots[0].source == "beat1.png"
    assert shots[0].kind == "still"
    assert shots[0].motion.kind == "push_in"
    assert shots[0].motion.amount_pct == 15.0
