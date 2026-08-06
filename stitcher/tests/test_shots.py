# stitcher/tests/test_shots.py
import json
from pathlib import Path

import pytest

from stitcher import shots as sh
from stitcher.cache import Manifest
from stitcher.naming import Workspace
from stitcher.spec import Canvas, Motion, Shot, Transition, load_spec
from tests.test_spec import MINIMAL, write

CANVAS = Canvas(width=1080, height=1920, fps=30)


def shot(**overrides) -> Shot:
    base = dict(
        n=1, id="B-01", beat="Hook", **{"in": 0.0, "out": 3.0},
        source="a.png", kind="still",
        motion=Motion(kind="push_in", amount_pct=15),
        transition_in=Transition(kind="cut"),
    )
    base.update(overrides)
    return Shot.model_validate(base)


def test_conform_size_reserves_headroom_for_the_maximum_zoom():
    assert sh.conform_size(CANVAS, Motion(kind="push_in", amount_pct=15)) == (1242, 2208)
    assert sh.conform_size(CANVAS, Motion(kind="none")) == (1080, 1920)


def test_still_filters_conform_then_animate_then_downscale():
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    conform_index = next(i for i, f in enumerate(filters) if "force_original_aspect_ratio" in f)
    animate_index = next(i for i, f in enumerate(filters) if "eval=frame" in f)
    colour_index = next(i for i, f in enumerate(filters) if "out_color_matrix" in f)
    format_index = next(i for i, f in enumerate(filters) if f.startswith("format="))
    assert conform_index < animate_index < colour_index
    assert format_index == colour_index + 1
    assert "1080:1920" in ";".join(filters)


def test_still_filters_carry_no_fps_filter_after_the_animated_stage():
    # -framerate on the input already sets the rate; an fps filter here would
    # rewrite frame numbering underneath the n-based expressions.
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    assert not any(f.startswith("fps=") for f in filters)


def test_render_shot_sets_framerate_on_a_still_input(tmp_path: Path, monkeypatch):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    ws.asset("a.png").write_bytes(b"png")
    captured: list[list[str]] = []
    monkeypatch.setattr(sh.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")
    sh.render_shot(spec, ws, 1, spec.shots[0], None, 4, "final",
                   Manifest(ws.manifest_path), ws.log_path("t"), False)
    args = captured[0]
    assert "-framerate" in args
    assert args[args.index("-framerate") + 1] == "30"
    assert args.index("-framerate") < args.index("-i")


def test_still_filters_quote_every_animated_expression():
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    animated = next(f for f in filters if "eval=frame" in f)
    assert "w='" in animated and "h='" in animated


def test_still_filters_force_and_tag_bt709():
    joined = ";".join(sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None))
    assert "out_color_matrix=bt709" in joined
    assert "out_range=tv" in joined


def test_still_filters_use_a_fixed_size_crop():
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    animated_crop = next(f for f in filters if f.startswith("crop=") and "x='" in f)
    assert "w=4320" in animated_crop and "h=7680" in animated_crop


def test_clip_filters_trim_to_the_source_window_and_conform_fps():
    clip = shot(kind="clip", source="a.mp4", source_in=1.0, source_out=4.0)
    joined = ";".join(sh.clip_filters(clip, CANVAS, None, None))
    assert "trim=start=1.0:end=4.0" in joined
    assert "setpts=PTS-STARTPTS" in joined
    assert "fps=30" in joined


def test_whip_at_the_head_is_gated_to_the_opening_frames():
    joined = ";".join(sh.whip_filters("left", 4, 90, at_head=True, canvas=CANVAS))
    assert "avgblur" in joined
    assert "enable='lt(n,4)'" in joined


def test_whip_at_the_tail_is_gated_to_the_closing_frames():
    joined = ";".join(sh.whip_filters("left", 4, 90, at_head=False, canvas=CANVAS))
    assert "enable='gte(n,86)'" in joined


def test_a_horizontal_whip_blurs_on_x_not_y():
    joined = ";".join(sh.whip_filters("left", 4, 90, at_head=True, canvas=CANVAS))
    assert f"sizeX={sh.WHIP_BLUR_PX}" in joined
    assert "sizeY=1" in joined


def test_a_vertical_whip_blurs_on_y_not_x():
    joined = ";".join(sh.whip_filters("up", 4, 90, at_head=True, canvas=CANVAS))
    assert f"sizeY={sh.WHIP_BLUR_PX}" in joined
    assert "sizeX=1" in joined


def test_the_whip_never_pads_with_black():
    for direction in ("left", "right", "up", "down"):
        joined = ";".join(sh.whip_filters(direction, 4, 90, True, CANVAS))
        assert "pad=" not in joined
        assert "color=black" not in joined


def test_cache_key_changes_when_the_successor_becomes_a_whip():
    cut = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 4, "final")
    whip = sh.shot_cache_key(
        shot(), Transition(kind="whip", direction="left"), "src", "ff8", 4, "final"
    )
    assert cut != whip


def test_cache_key_changes_with_the_ffmpeg_build():
    a = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8.0", 4, "final")
    b = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8.1", 4, "final")
    assert a != b


def test_cache_key_changes_between_run_modes():
    final = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 4, "final")
    draft = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 1, "draft")
    assert final != draft


def test_render_shot_skips_the_encode_on_a_cache_hit(tmp_path: Path, monkeypatch):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    ws.asset("a.png").write_bytes(b"png")

    calls: list[list[str]] = []
    monkeypatch.setattr(sh.ffmpeg, "run", lambda args, log_path: calls.append(args) or "")
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")

    manifest = Manifest(ws.manifest_path)
    target = ws.shot_clip(1, "B-01", "Hook")

    sh.render_shot(spec, ws, 1, spec.shots[0], spec.shots[1].transition_in,
                   4, "final", manifest, ws.log_path("t"), False)
    assert len(calls) == 1

    target.write_bytes(b"clip")  # the fake ffmpeg never wrote one
    sh.render_shot(spec, ws, 1, spec.shots[0], spec.shots[1].transition_in,
                   4, "final", manifest, ws.log_path("t"), False)
    assert len(calls) == 1  # second call was a cache hit


def test_render_all_returns_one_clip_per_shot_in_timeline_order(tmp_path: Path, monkeypatch):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    for name in ("a.png", "b.png"):
        ws.asset(name).write_bytes(b"png")

    def fake_run(args, log_path):
        Path(args[-1]).write_bytes(b"clip")
        return ""

    monkeypatch.setattr(sh.ffmpeg, "run", fake_run)
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")

    clips = sh.render_all(spec, ws, "final", Manifest(ws.manifest_path),
                          ws.log_path("t"), missing_visual=[])
    assert [clip.name for clip in clips] == ["001_B-01_hook.mkv", "002_B-02_setup.mkv"]


def test_render_all_uses_a_placeholder_for_a_missing_asset_in_draft(tmp_path: Path, monkeypatch):
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="draft")
    ws.ensure_dirs()
    ws.asset("b.png").write_bytes(b"png")

    def fake_run(args, log_path):
        Path(args[-1]).write_bytes(b"clip")
        return ""

    monkeypatch.setattr(sh.ffmpeg, "run", fake_run)
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")

    sh.render_all(spec, ws, "draft", Manifest(ws.manifest_path),
                  ws.log_path("t"), missing_visual=["a.png"])
    placeholders = list(ws.work_dir.glob("placeholders/*.png"))
    assert len(placeholders) == 1
