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


def test_render_shot_encodes_with_libx264_and_tags_colour_via_the_filter_not_the_encoder(
    tmp_path: Path, monkeypatch
):
    # Colour tagging is carried entirely by the setparams filter (see
    # still_filters/clip_filters); this locks the encode-time argv so a later
    # refactor can't silently reintroduce the generic -colorspace/
    # -color_primaries/-color_trc flags (which don't reach ffprobe's report
    # on the installed 9.0 build) or the -x264-params route (whose
    # range=tv errors on this libx264 core).
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

    assert args[args.index("-c:v") + 1] == "libx264"
    assert "-crf" in args
    assert "-preset" in args
    for flag in ("-x264-params", "-colorspace", "-color_primaries", "-color_trc"):
        assert flag not in args


def test_still_filters_quote_every_animated_expression():
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    animated = next(f for f in filters if "eval=frame" in f)
    assert "w='" in animated and "h='" in animated


def test_still_filters_force_and_tag_bt709():
    joined = ";".join(sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None))
    assert "out_color_matrix=bt709" in joined
    assert "out_range=tv" in joined


def test_still_filters_and_clip_filters_stamp_frame_colour_with_setparams():
    # ffprobe -- what the project's own QA gates on (Task 13/15) -- reads
    # container-level colour fields, which `-x264-params` alone does not
    # populate on the installed 9.0 build even though the encoded bitstream
    # is correct; `setparams` on the frame is what makes both agree.
    still_joined = ";".join(sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None))
    assert "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709" in still_joined

    clip = shot(kind="clip", source="a.mp4", source_in=1.0, source_out=4.0)
    clip_joined = ";".join(sh.clip_filters(clip, CANVAS, 90, None, None))
    assert "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709" in clip_joined


def test_still_filters_use_a_fixed_size_crop():
    filters = sh.still_filters(shot(), CANVAS, 4, 90, 0, None, None)
    animated_crop = next(f for f in filters if f.startswith("crop=") and "x='" in f)
    assert "w=4320" in animated_crop and "h=7680" in animated_crop


def test_clip_filters_trim_to_the_source_window_and_conform_fps():
    clip = shot(kind="clip", source="a.mp4", source_in=1.0, source_out=4.0)
    joined = ";".join(sh.clip_filters(clip, CANVAS, 90, None, None))
    assert "trim=start=1.0:end=4.0" in joined
    assert "setpts=PTS-STARTPTS" in joined
    assert "fps=30" in joined


def test_clip_filters_pad_to_the_exact_frame_count_after_conforming_fps():
    """`trim=start=X` snaps to the SOURCE's frame grid, so a source_in off that
    grid yields a short span and `-frames:v` cannot invent the missing frame --
    ffmpeg writes fewer frames and exits 0, shifting every later shot one frame
    early. The clone pad is what makes the frame count exact; it has to sit
    after `fps` (so it pads at canvas.fps) and before the whip (so the tail
    whip's frame gate counts against the final length)."""
    clip = shot(kind="clip", source="a.mp4", source_in=0.5, source_out=3.5)
    filters = sh.clip_filters(
        clip, CANVAS, 90, None, Transition(kind="whip", direction="left", frames=4)
    )
    assert sh.CLIP_PAD in filters
    assert filters.index("fps=30") < filters.index(sh.CLIP_PAD)
    whip_index = next(i for i, f in enumerate(filters) if "avgblur" in f)
    assert filters.index(sh.CLIP_PAD) < whip_index


def test_the_clip_tail_whip_gates_against_the_timeline_slot_not_the_source_window():
    """The tail whip's window is gte(n, total_frames - frames) and total_frames
    is now the shot's own slot, so the gate lands on the last four frames the
    clip actually emits."""
    clip = shot(kind="clip", source="a.mp4", source_in=0.5, source_out=3.5)
    joined = ";".join(
        sh.clip_filters(
            clip, CANVAS, 90, None, Transition(kind="whip", direction="left", frames=4)
        )
    )
    assert "enable='gte(n,86)'" in joined


def test_render_shot_passes_the_slot_frame_count_to_a_clip(tmp_path: Path, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][0]["kind"] = "clip"
    payload["shots"][0]["source"] = "a.mp4"
    payload["shots"][0]["source_in"] = 0.5
    payload["shots"][0]["source_out"] = 3.5
    spec, _ = load_spec(write(tmp_path, payload))
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    ws.asset("a.mp4").write_bytes(b"mp4")
    captured: list[list[str]] = []
    monkeypatch.setattr(sh.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    monkeypatch.setattr(sh.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 9.0")
    sh.render_shot(spec, ws, 1, spec.shots[0], None, 4, "final",
                   Manifest(ws.manifest_path), ws.log_path("t"), False)
    args = captured[0]
    assert args[args.index("-frames:v") + 1] == "90"
    assert sh.CLIP_PAD in args[args.index("-vf") + 1]


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
    cut = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 4, "final", 30)
    whip = sh.shot_cache_key(
        shot(), Transition(kind="whip", direction="left"), "src", "ff8", 4, "final", 30
    )
    assert cut != whip


def test_cache_key_changes_with_the_ffmpeg_build():
    a = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8.0", 4, "final", 30)
    b = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8.1", 4, "final", 30)
    assert a != b


def test_cache_key_changes_between_run_modes():
    final = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 4, "final", 30)
    draft = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 1, "draft", 30)
    assert final != draft


def test_cache_key_changes_when_fps_changes():
    # Canvas width/height cannot vary in v1, but fps can, and an fps edit
    # changes total_frames/hold_frames/every n-based motion expression/the
    # whip windows without touching shot, next_transition, source_digest,
    # ffmpeg_build, supersample, or mode -- so fps must be its own input to
    # the key or a re-render after an fps edit would falsely cache-hit.
    at_30 = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 4, "final", 30)
    at_60 = sh.shot_cache_key(shot(), Transition(kind="cut"), "src", "ff8", 4, "final", 60)
    assert at_30 != at_60


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
