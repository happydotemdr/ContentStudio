import json
from pathlib import Path

from native_pipeline.cli import EXIT_USAGE, main


def test_render_command_calls_all_four_stages_in_order(tmp_path, monkeypatch):
    calls = []

    def fake_run_vo_stage(ws, payload_path, url, log_path, vo_mode="break", beat_texts=None):
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
    asset_manifest_path = tmp_path / "manifest.json"
    asset_manifest_path.write_text(json.dumps([]), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(asset_manifest_path),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
        "--vo-mode", "break",
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

    def fake_run_vo_stage(ws, payload_path, url, log_path, vo_mode="break", beat_texts=None):
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
    (tmp_path / "manifest.json").write_text(json.dumps([]), encoding="utf-8")

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
        "--vo-mode", "break",
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


def test_render_command_rejects_malformed_styles_before_any_billed_call(tmp_path, monkeypatch):
    """cmd_render must validate --styles (and --beat-texts and --asset-manifest)
    before it ever calls run_vo_stage/run_music_stage -- those two are real,
    billed ElevenLabs/Eleven Music API calls. A malformed --styles file should
    never let a billed generation happen first. This is the concrete proof the
    hoist actually saves the calls, not just that validation happens to run
    earlier in the source.
    """
    calls = []

    def fake_run_vo_stage(ws, payload_path, url, log_path):
        calls.append("vo")
        raise AssertionError("run_vo_stage must not be called when --styles is malformed")

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        calls.append("music")
        raise AssertionError("run_music_stage must not be called when --styles is malformed")

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    # Missing required Style fields (e.g. font_file) -- pydantic raises
    # ValidationError (a ValueError subclass) constructing Style(**fields).
    styles_path.write_text(json.dumps({"default": {"size_px": 64}}), encoding="utf-8")
    asset_manifest_path = tmp_path / "manifest.json"
    asset_manifest_path.write_text(json.dumps([]), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(asset_manifest_path),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
    ])

    assert exit_code == EXIT_USAGE
    assert calls == [], f"a billed stage was invoked despite malformed --styles: {calls}"


def test_render_command_rejects_invalid_asset_manifest_before_any_billed_call(tmp_path, monkeypatch):
    """Same guarantee as the --styles case above, for --asset-manifest: an
    entry with an invalid `kind` must fail contracts.load_asset_manifest's
    structural check before either billed stage runs.
    """
    calls = []

    def fake_run_vo_stage(ws, payload_path, url, log_path):
        calls.append("vo")
        raise AssertionError("run_vo_stage must not be called when --asset-manifest is invalid")

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        calls.append("music")
        raise AssertionError("run_music_stage must not be called when --asset-manifest is invalid")

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    styles_path.write_text(json.dumps({
        "default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF", "accent": "#FFD700",
                    "max_width_px": 900, "max_lines": 3},
    }), encoding="utf-8")
    asset_manifest_path = tmp_path / "manifest.json"
    asset_manifest_path.write_text(json.dumps([
        {"beat": "beat1", "kind": "not-a-real-kind"},
    ]), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(asset_manifest_path),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
    ])

    assert exit_code == EXIT_USAGE
    assert calls == [], f"a billed stage was invoked despite an invalid --asset-manifest: {calls}"


def test_render_command_rejects_v3_tags_mode_without_vo_beat_texts_before_any_billed_call(tmp_path, monkeypatch, capsys):
    """--vo-mode v3_tags requires --vo-beat-texts (run_vo_stage's
    VoModeMismatchError has no way to recover boundaries otherwise). This
    must be caught here, before run_vo_stage/run_music_stage -- real,
    billed API calls -- ever run.
    """
    calls = []

    def fake_run_vo_stage(ws, payload_path, url, log_path, vo_mode="break", beat_texts=None):
        calls.append("vo")
        raise AssertionError("run_vo_stage must not be called when --vo-beat-texts is missing")

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        calls.append("music")
        raise AssertionError("run_music_stage must not be called when --vo-beat-texts is missing")

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    styles_path.write_text(json.dumps({
        "default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF", "accent": "#FFD700",
                    "max_width_px": 900, "max_lines": 3},
    }), encoding="utf-8")
    asset_manifest_path = tmp_path / "manifest.json"
    asset_manifest_path.write_text(json.dumps([]), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(asset_manifest_path),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
        "--vo-mode", "v3_tags",
    ])

    assert exit_code == EXIT_USAGE
    assert calls == [], f"a billed stage was invoked despite missing --vo-beat-texts: {calls}"
    assert "--vo-beat-texts is required" in capsys.readouterr().err


def test_render_command_rejects_beat_texts_length_mismatch_before_any_billed_call(tmp_path, monkeypatch, capsys):
    """--beat-texts and --vo-beat-texts must correspond 1:1 (same beats). A
    mismatch must be caught here, before run_vo_stage/run_music_stage --
    real, billed API calls -- ever run.
    """
    calls = []

    def fake_run_vo_stage(ws, payload_path, url, log_path, vo_mode="break", beat_texts=None):
        calls.append("vo")
        raise AssertionError("run_vo_stage must not be called when beat-texts lengths mismatch")

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        calls.append("music")
        raise AssertionError("run_music_stage must not be called when beat-texts lengths mismatch")

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    vo_beat_texts_path = tmp_path / "vo_beat_texts.json"
    vo_beat_texts_path.write_text(json.dumps(["hello", "there"]), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    styles_path.write_text(json.dumps({
        "default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF", "accent": "#FFD700",
                    "max_width_px": 900, "max_lines": 3},
    }), encoding="utf-8")
    asset_manifest_path = tmp_path / "manifest.json"
    asset_manifest_path.write_text(json.dumps([]), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(asset_manifest_path),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
        "--vo-mode", "v3_tags",
        "--vo-beat-texts", str(vo_beat_texts_path),
    ])

    assert exit_code == EXIT_USAGE
    assert calls == [], f"a billed stage was invoked despite a beat-texts length mismatch: {calls}"
    assert "must correspond 1:1" in capsys.readouterr().err


def test_render_command_defaults_vo_mode_to_v3_tags():
    from native_pipeline.cli import build_parser
    parser = build_parser()
    args = parser.parse_args([
        "render", "test-slug",
        "--root", "renders", "--vo-payload", "p.json", "--vo-url", "https://x",
        "--bed-arc", "b.json", "--music-url", "https://x", "--asset-manifest", "m.json",
        "--beat-texts", "bt.json", "--styles", "s.json", "--captions-style", "default",
    ])
    assert args.vo_mode == "v3_tags"


def test_render_command_v3_tags_happy_path_parses_beat_texts(tmp_path, monkeypatch):
    """A valid --vo-beat-texts file (matching --beat-texts length) should
    reach run_vo_stage as its beat_texts kwarg, with vo_mode="v3_tags".
    """
    received = {}

    def fake_run_vo_stage(ws, payload_path, url, log_path, vo_mode="break", beat_texts=None):
        received["vo_mode"] = vo_mode
        received["beat_texts"] = beat_texts
        from stitcher.vo_alignment import Segment
        return tmp_path / "take.mp3", [Segment(name="beat1", at=0.0, duration=5.0)]

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        return tmp_path / "bed.wav"

    def fake_run_assemble_stage(ws, segments, asset_manifest_path, beat_texts, voice_take, music_bed,
                                 styles, captions_style, log_path):
        return tmp_path / "render-spec.json"

    def fake_run_render_stage(slug, root):
        pass

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_assemble_stage", fake_run_assemble_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_render_stage", fake_run_render_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    vo_beat_texts_path = tmp_path / "vo_beat_texts.json"
    vo_beat_texts_path.write_text(json.dumps(["[excited] hello"]), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    styles_path.write_text(json.dumps({
        "default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF", "accent": "#FFD700",
                    "max_width_px": 900, "max_lines": 3},
    }), encoding="utf-8")
    asset_manifest_path = tmp_path / "manifest.json"
    asset_manifest_path.write_text(json.dumps([]), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(asset_manifest_path),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
        "--vo-mode", "v3_tags",
        "--vo-beat-texts", str(vo_beat_texts_path),
    ])

    assert exit_code == 0
    assert received["vo_mode"] == "v3_tags"
    assert received["beat_texts"] == ["[excited] hello"]


def test_render_command_rejects_malformed_vo_beat_texts_file_before_any_billed_call(tmp_path, monkeypatch, capsys):
    """A --vo-beat-texts file that isn't a JSON list of strings must be
    rejected before run_vo_stage/run_music_stage -- real, billed API calls
    -- ever run.
    """
    calls = []

    def fake_run_vo_stage(ws, payload_path, url, log_path, vo_mode="break", beat_texts=None):
        calls.append("vo")
        raise AssertionError("run_vo_stage must not be called when --vo-beat-texts is malformed")

    def fake_run_music_stage(segments, bed_arc_path, ws, url, log_path):
        calls.append("music")
        raise AssertionError("run_music_stage must not be called when --vo-beat-texts is malformed")

    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_vo_stage", fake_run_vo_stage)
    monkeypatch.setattr("native_pipeline.cli.orchestrate.run_music_stage", fake_run_music_stage)

    beat_texts_path = tmp_path / "beat_texts.json"
    beat_texts_path.write_text(json.dumps(["hello"]), encoding="utf-8")
    vo_beat_texts_path = tmp_path / "vo_beat_texts.json"
    vo_beat_texts_path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    styles_path = tmp_path / "styles.json"
    styles_path.write_text(json.dumps({
        "default": {"font_file": "Inter-Bold.ttf", "size_px": 64, "body": "#FFFFFF", "accent": "#FFD700",
                    "max_width_px": 900, "max_lines": 3},
    }), encoding="utf-8")
    asset_manifest_path = tmp_path / "manifest.json"
    asset_manifest_path.write_text(json.dumps([]), encoding="utf-8")

    exit_code = main([
        "render", "test-slug",
        "--root", str(tmp_path / "renders"),
        "--vo-payload", str(tmp_path / "payload.json"),
        "--vo-url", "https://fake-vo-url",
        "--bed-arc", str(tmp_path / "bed_arc.json"),
        "--music-url", "https://fake-music-url",
        "--asset-manifest", str(asset_manifest_path),
        "--beat-texts", str(beat_texts_path),
        "--styles", str(styles_path),
        "--captions-style", "default",
        "--vo-mode", "v3_tags",
        "--vo-beat-texts", str(vo_beat_texts_path),
    ])

    assert exit_code == EXIT_USAGE
    assert calls == [], f"a billed stage was invoked despite a malformed --vo-beat-texts file: {calls}"
