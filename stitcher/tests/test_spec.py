import json
from pathlib import Path

import pytest

from stitcher.spec import (
    RenderSpec,
    frame_residual,
    load_spec,
    quantize,
    runtime_seconds,
    shot_frame_bounds,
    validate_spec,
)

MINIMAL = {
    "spec_version": "1.0",
    "slug": "demo",
    "canvas": {"width": 1080, "height": 1920, "fps": 30},
    "safe_zone": {"x": 90, "y": 380, "width": 900, "height": 1160},
    "styles": {
        "card": {
            "font_file": "fonts/Inter-Bold.ttf",
            "size_px": 72,
            "body": "#F7F3E8",
            "accent": "#F2A541",
            "ground": "#0E3B43",
            "ground_opacity": 0.85,
            "padding_px": [32, 40],
            "line_spacing": 1.15,
            "align": "center",
            "max_width_px": 820,
            "max_lines": 4,
            "stroke_px": 0,
            "stroke_color": "#000000",
        }
    },
    "shots": [
        {
            "n": 1,
            "id": "B-01",
            "beat": "Hook",
            "in": 0.0,
            "out": 3.0,
            "source": "a.png",
            "kind": "still",
            "motion": {"kind": "push_in", "amount_pct": 15},
            "transition_in": {"kind": "cut"},
        },
        {
            "n": 2,
            "id": "B-02",
            "beat": "Setup",
            "in": 3.0,
            "out": 6.0,
            "source": "b.png",
            "kind": "still",
            "motion": {"kind": "none"},
            "transition_in": {"kind": "cut"},
        },
    ],
    "overlays": [
        {"id": "hook-1", "style": "card", "in": 0.0, "out": 2.0,
         "anchor": "center", "offset_px": [0, 0], "text": "HELLO [[WORLD]]"}
    ],
    "captions": [{"in": 0.0, "out": 2.9, "text": "Hello world."}],
    "captions_style": "card",
    "audio": {
        "stems": [{"id": "vo", "file": "vo.wav", "at": 0.0, "gain_db": 0.0}],
        "bed": {
            "file": "bed.mp3", "gain_db": -8.0, "duck_db": -22.0,
            "duck_attack_ms": 120, "duck_release_ms": 400,
            "windows": [], "fades": [],
        },
        "sfx": [],
        "loudness": {"integrated_lufs": -14.0, "true_peak_dbtp": -1.5},
    },
    "cover": {"source": "cover.png", "overlays": []},
    "delivery": {
        "codec": "libx264", "crf": 18, "preset": "slow", "profile": "high",
        "pix_fmt": "yuv420p", "audio_codec": "aac",
        "audio_bitrate": "192k", "audio_rate": 48000,
    },
}


def write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "render-spec.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_quantize_rounds_to_nearest_frame():
    assert quantize(2.0, 30) == 60
    assert quantize(2.875, 30) == 86
    assert quantize(21.5, 30) == 645


def test_frame_residual_reports_non_frame_aligned_times():
    assert frame_residual(21.5, 30) == pytest.approx(0.0)
    assert frame_residual(2.875, 30) == pytest.approx(0.25)


def test_load_spec_warns_about_non_frame_aligned_times(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][0]["out"] = 2.875
    payload["shots"][1]["in"] = 2.875
    spec, warnings = load_spec(write(tmp_path, payload))
    assert any("2.875" in w and "86.25" in w for w in warnings)


def test_load_spec_exposes_in_out_as_start_end(tmp_path: Path):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    assert spec.shots[0].start == 0.0
    assert spec.shots[0].end == 3.0


def test_shot_frame_bounds_are_derived_by_differencing_boundaries(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][0]["out"] = 2.875
    payload["shots"][1]["in"] = 2.875
    spec, _ = load_spec(write(tmp_path, payload))
    bounds = shot_frame_bounds(spec)
    # Boundary 2.875s quantizes to frame 86 once, shared by both shots.
    assert bounds == [(0, 86), (86, 180)]
    assert bounds[-1][1] == quantize(runtime_seconds(spec), spec.canvas.fps)


def test_validate_accepts_the_minimal_spec(tmp_path: Path):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    assert validate_spec(spec) == []


def test_validate_rejects_non_contiguous_shots(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][1]["in"] = 3.5
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("contiguous" in e for e in validate_spec(spec))


def test_validate_rejects_non_1080x1920_canvas(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["canvas"]["width"] = 720
    payload["canvas"]["height"] = 1280
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("1080" in e for e in validate_spec(spec))


def test_validate_rejects_clip_without_source_trim(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][0]["kind"] = "clip"
    payload["shots"][0]["source"] = "a.mp4"
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("source_in" in e for e in validate_spec(spec))


def test_validate_rejects_whip_without_direction(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][1]["transition_in"] = {"kind": "whip", "frames": 4}
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("direction" in e for e in validate_spec(spec))


def test_validate_rejects_overlapping_bed_windows(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["audio"]["bed"]["windows"] = [
        {"in": 0.0, "out": 3.0, "mode": "out", "level_db": None},
        {"in": 2.0, "out": 5.0, "mode": "ducked", "level_db": None},
    ]
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("overlap" in e for e in validate_spec(spec))


def test_validate_rejects_unknown_captions_style(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["captions_style"] = "nope"
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("captions_style" in e for e in validate_spec(spec))


def test_validate_rejects_overlapping_captions(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["captions"] = [
        {"in": 0.0, "out": 2.0, "text": "one"},
        {"in": 1.5, "out": 3.0, "text": "two"},
    ]
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("caption" in e.lower() for e in validate_spec(spec))


def test_validate_rejects_overlay_past_runtime(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["overlays"][0]["out"] = 99.0
    spec, _ = load_spec(write(tmp_path, payload))
    assert any("runtime" in e for e in validate_spec(spec))


def test_unknown_spec_version_is_rejected(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["spec_version"] = "9.9"
    with pytest.raises(ValueError):
        load_spec(write(tmp_path, payload))


def test_unsupported_transition_names_v1(tmp_path: Path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][1]["transition_in"] = {"kind": "dissolve"}
    with pytest.raises(ValueError, match="not implemented in v1"):
        load_spec(write(tmp_path, payload))
