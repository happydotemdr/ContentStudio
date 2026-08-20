import json
from pathlib import Path

from native_pipeline.cli import main


def test_render_command_calls_all_four_stages_in_order(tmp_path, monkeypatch):
    calls = []

    def fake_run_vo_stage(ws, payload_path, url, log_path):
        calls.append("vo")
        from stitcher.vo_alignment import Segment
        return tmp_path / "take.mp3", [Segment(name="beat1", at=0.0, duration=5.0)]

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        calls.append("music")
        return tmp_path / "bed.wav"

    def fake_run_assemble_stage(ws, segments, asset_manifest_path, beat_texts, voice_take, music_bed,
                                 styles, captions_style, log_path):
        calls.append("assemble")
        return tmp_path / "render-spec.json"

    def fake_run_render_stage(slug, root):
        calls.append("render")

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_assemble_stage", fake_run_assemble_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_render_stage", fake_run_render_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    styles_path.write_text(json.dumps({
        "default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF", "accent": "#FFD700",
                    "max_width_px": 900, "max_lines": 3},
    }), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(tmp_path / "manifest.json"),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
    ])

    assert exit_code == 0
    assert calls == ["vo", "music", "assemble", "render"]


def test_render_command_resolves_relative_paths_to_absolute(tmp_path, monkeypatch):
    """Task 9's orchestrate.py shells out to sibling packages with
    cwd=<sibling-package-dir>, so every path-bearing CLI argument must be
    absolute before it reaches Workspace/orchestrate -- a relative path
    would resolve against the wrong directory. This passes a relative
    --root (and relative payload/manifest paths) from a chdir'd cwd and
    asserts the Workspace/paths the stages actually receive are absolute
    and anchored at that cwd, not left relative.
    """
    received = {}

    def fake_run_vo_stage(ws, payload_path, url, log_path):
        received["ws_root"] = ws.root
        received["payload_path"] = payload_path
        from stitcher.vo_alignment import Segment
        return tmp_path / "take.mp3", [Segment(name="beat1", at=0.0, duration=5.0)]

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        received["bed_arc_path"] = bed_arc_path
        return tmp_path / "bed.wav"

    def fake_run_assemble_stage(ws, segments, asset_manifest_path, beat_texts, voice_take, music_bed,
                                 styles, captions_style, log_path):
        received["asset_manifest_path"] = asset_manifest_path
        return tmp_path / "render-spec.json"

    def fake_run_render_stage(slug, root):
        received["render_root"] = root

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_assemble_stage", fake_run_assemble_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_render_stage", fake_run_render_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    styles_path.write_text(json.dumps({
        "default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF", "accent": "#FFD700",
                    "max_width_px": 900, "max_lines": 3},
    }), encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    exit_code = main([
        "render", "test-slug",
        "--root", "renders",
        "--vo-payload", "payload.json",
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", "bed_arc.json",
        "--music-url", "https://fake-music-url",
        "--asset-manifest", "manifest.json",
        "--beat-texts", "beat_texts.json",
        "--styles", "styles.json",
        "--captions-style", "default",
    ])

    assert exit_code == 0
    assert received["ws_root"].is_absolute()
    assert received["ws_root"] == tmp_path / "renders"
    assert received["payload_path"].is_absolute()
    assert received["payload_path"] == tmp_path / "payload.json"
    assert received["bed_arc_path"].is_absolute()
    assert received["bed_arc_path"] == tmp_path / "bed_arc.json"
    assert received["asset_manifest_path"].is_absolute()
    assert received["asset_manifest_path"] == tmp_path / "manifest.json"
    assert received["render_root"].is_absolute()
    assert received["render_root"] == tmp_path / "renders"
