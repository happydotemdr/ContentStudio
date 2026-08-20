import json

import pytest

from native_pipeline.contracts import load_asset_manifest, load_bed_arc


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_asset_manifest_returns_parsed_entries(tmp_path):
    path = _write(tmp_path, "manifest.json", [
        {"beat": "beat1", "kind": "still", "source": "a.png", "source_in_s": None, "source_out_s": None,
         "motion": {"kind": "push_in", "amount_pct": 15.0, "anchor_start": [0.5, 0.5],
                    "anchor_end": [0.5, 0.5], "hold_s": 0.0, "ease": "linear"}},
    ])
    entries = load_asset_manifest(path)
    assert entries[0]["beat"] == "beat1"
    assert entries[0]["motion"]["kind"] == "push_in"


def test_load_asset_manifest_raises_on_still_without_motion(tmp_path):
    path = _write(tmp_path, "manifest.json", [
        {"beat": "beat1", "kind": "still", "source": "a.png", "source_in_s": None, "source_out_s": None,
         "motion": None},
    ])
    with pytest.raises(ValueError, match="beat1.*motion"):
        load_asset_manifest(path)


def test_load_asset_manifest_raises_on_clip_without_source_in_out(tmp_path):
    path = _write(tmp_path, "manifest.json", [
        {"beat": "beat1", "kind": "clip", "source": "a.mp4", "source_in_s": None, "source_out_s": None,
         "motion": None},
    ])
    with pytest.raises(ValueError, match="beat1.*source_in_s"):
        load_asset_manifest(path)


def test_load_asset_manifest_raises_on_bad_kind(tmp_path):
    path = _write(tmp_path, "manifest.json", [
        {"beat": "beat1", "kind": "video", "source": "a.mp4", "source_in_s": 0.0, "source_out_s": 1.0,
         "motion": None},
    ])
    with pytest.raises(ValueError, match="beat1.*kind"):
        load_asset_manifest(path)


def test_load_bed_arc_returns_parsed_entries(tmp_path):
    path = _write(tmp_path, "bed_arc.json", [
        {"label": "rising urgency", "start_s": 4.0, "end_s": 20.0, "density": "full", "style_notes": ""},
    ])
    entries = load_bed_arc(path)
    assert entries[0]["label"] == "rising urgency"
    assert entries[0]["density"] == "full"


def test_load_bed_arc_raises_on_bad_density(tmp_path):
    path = _write(tmp_path, "bed_arc.json", [
        {"label": "x", "start_s": 0.0, "end_s": 5.0, "density": "loud", "style_notes": ""},
    ])
    with pytest.raises(ValueError, match="x.*density"):
        load_bed_arc(path)


def test_load_bed_arc_raises_when_end_before_start(tmp_path):
    path = _write(tmp_path, "bed_arc.json", [
        {"label": "x", "start_s": 5.0, "end_s": 5.0, "density": "full", "style_notes": ""},
    ])
    with pytest.raises(ValueError, match="x.*end_s"):
        load_bed_arc(path)
