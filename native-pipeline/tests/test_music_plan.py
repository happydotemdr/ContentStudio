import pytest

from native_pipeline.errors import ChunkDurationTooShortError
from native_pipeline.music_plan import build_music_plan


def _movement(label, start_s, end_s, density, style_notes=""):
    return {"label": label, "start_s": start_s, "end_s": end_s, "density": density, "style_notes": style_notes}


def test_build_music_plan_sets_duration_ms_from_movement_span():
    bed_arc = [_movement("hook", 0.0, 4.0, "full"), _movement("rising urgency", 4.0, 20.0, "full")]
    plan = build_music_plan(bed_arc, runtime=20.0)

    chunks = plan["composition_plan"]["chunks"]
    assert chunks[0]["duration_ms"] == 4000
    assert chunks[1]["duration_ms"] == 16000


def test_build_music_plan_uses_sparse_style_for_sparse_density():
    bed_arc = [_movement("verse", 0.0, 10.0, "sparse")]
    plan = build_music_plan(bed_arc, runtime=10.0)

    chunk = plan["composition_plan"]["chunks"][0]
    assert any("sparse" in style for style in chunk["positive_styles"])


def test_build_music_plan_folds_style_notes_into_positive_styles():
    bed_arc = [_movement("hook", 0.0, 5.0, "full", style_notes="brass hit on the key line")]
    plan = build_music_plan(bed_arc, runtime=5.0)

    chunk = plan["composition_plan"]["chunks"][0]
    assert "brass hit on the key line" in chunk["positive_styles"]


def test_build_music_plan_sets_force_instrumental():
    bed_arc = [_movement("hook", 0.0, 5.0, "full")]
    plan = build_music_plan(bed_arc, runtime=5.0)
    assert plan["force_instrumental"] is True


def test_build_music_plan_raises_on_movement_under_3000ms_floor():
    bed_arc = [_movement("gap", 0.0, 1.2, "full")]
    with pytest.raises(ChunkDurationTooShortError, match="gap"):
        build_music_plan(bed_arc, runtime=1.2)


def test_build_music_plan_raises_on_total_duration_mismatch():
    bed_arc = [_movement("hook", 0.0, 4.0, "full")]
    with pytest.raises(ChunkDurationTooShortError, match="runtime"):
        build_music_plan(bed_arc, runtime=61.114)


def test_build_music_plan_raises_when_over_30_chunks():
    bed_arc = [_movement(f"m{i}", i * 3.0, (i + 1) * 3.0, "full") for i in range(31)]
    with pytest.raises(ChunkDurationTooShortError, match="30"):
        build_music_plan(bed_arc, runtime=93.0)
