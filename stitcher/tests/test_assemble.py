# stitcher/tests/test_assemble.py
import copy
import json
from pathlib import Path

import pytest

from stitcher import assemble as asm
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_spec import MINIMAL, write


def test_write_concat_uses_forward_slashes_and_quotes(tmp_path: Path):
    clips = [tmp_path / "a b" / "001.mkv", tmp_path / "a b" / "002.mkv"]
    target = asm.write_concat(clips, tmp_path / "concat.txt")
    body = target.read_text(encoding="utf-8")
    assert "\\" not in body
    assert body.count("file '") == 2


def test_write_concat_absolutizes_a_relative_clip_path(tmp_path: Path, monkeypatch):
    """The concat demuxer resolves a relative entry against the CONCAT FILE's
    directory, not the process CWD. `--root` defaults to a relative
    `Path("renders")`, so every clip path reaching this function was relative
    and every entry resolved to
    `<root>/<slug>/work/<mode>/renders/<slug>/work/<mode>/shots/...` -- a
    doubled path that does not exist. Absolute entries are what the demuxer
    needs and what this function's own docstring already assumes."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "renders" / "work").mkdir(parents=True)
    clips = [Path("renders") / "work" / "001.mkv"]
    target = asm.write_concat(clips, tmp_path / "renders" / "work" / "concat.txt")

    entry = target.read_text(encoding="utf-8").strip()
    assert entry == f"file '{(tmp_path / 'renders' / 'work' / '001.mkv').as_posix()}'"
    assert Path(entry[len("file '"):-1]).is_absolute()


def test_overlay_enable_is_half_open_not_between():
    enable = asm.overlay_enable(0.0, 2.0)
    assert "gte(t,0.0)" in enable
    assert "lt(t,2.0)" in enable
    assert "between" not in enable


def test_adjacent_overlays_never_both_enable_on_the_same_frame():
    first = asm.overlay_enable(0.0, 2.0)
    second = asm.overlay_enable(2.0, 3.0)
    # At t == 2.0 exactly: first is lt(t,2.0) -> false, second is gte(t,2.0) -> true.
    assert "lt(t,2.0)" in first and "gte(t,2.0)" in second


def test_build_graph_chains_one_overlay_per_input_and_ends_at_vout():
    graph = asm.build_graph(2, [asm.overlay_enable(0, 1), asm.overlay_enable(1, 2)])
    assert graph.count("overlay=0:0") == 2
    assert graph.strip().endswith("[vout]")
    assert "[0:v]" in graph


def test_build_graph_with_no_overlays_still_produces_vout():
    graph = asm.build_graph(0, [])
    assert graph.strip().endswith("[vout]")
    assert "overlay" not in graph


def test_normalize_graph_tokenizes_absolute_paths_for_golden_diffs():
    graph = "movie=C:/Users/BKing/renders/demo/work/final/x.png"
    normalized = asm.normalize_graph(graph, {"C:/Users/BKing/renders/demo/work/final": "<WORK>"})
    assert normalized == "movie=<WORK>/x.png"
    assert "BKing" not in normalized


@pytest.fixture
def ready(tmp_path: Path):
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    clips = []
    for index in (1, 2):
        clip = ws.shot_clip(index, f"B-0{index}", "beat")
        clip.write_bytes(b"clip")
        clips.append(clip)
    mix = ws.audio_step("06", "mix_final")
    mix.write_bytes(b"wav")
    return ws, clips, mix


def test_assemble_writes_the_graph_to_a_script_file(tmp_path, ready, monkeypatch):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    png = ws.overlay_png(1, "hook-1", "hello")
    png.write_bytes(b"png")

    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: "")
    asm.assemble(spec, ws, "final", clips, {"hook-1": png}, mix, ws.log_path("t"))
    assert ws.graph_path.is_file()
    assert "[vout]" in ws.graph_path.read_text(encoding="utf-8")


def test_assemble_passes_the_graph_by_script_never_inline(tmp_path, ready, monkeypatch):
    # Deviation from the brief (recorded in task-11-report.md): the brief's
    # code used "-filter_complex_script <file>". That flag does not exist on
    # the installed ffmpeg 9.0 binary -- confirmed with a direct run
    # ("Unrecognized option 'filter_complex_script'", exit 8) and by
    # grepping the compiled binary for the string, which is absent. Upstream
    # ffmpeg deprecated -filter_complex_script in January 2024 in favour of
    # "-/filter_complex <file>" (same file-reading behaviour, different
    # spelling), and this build has already dropped the old spelling
    # entirely. "-/filter_complex <file>" was verified end-to-end against
    # the real binary (real concat + overlay + encode, correct output) and
    # is what assemble() actually emits.
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    png = ws.overlay_png(1, "hook-1", "hello")
    png.write_bytes(b"png")

    captured: list[list[str]] = []
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    asm.assemble(spec, ws, "final", clips, {"hook-1": png}, mix, ws.log_path("t"))
    args = captured[0]
    assert "-/filter_complex" in args
    assert str(ws.graph_path) in args
    assert "-filter_complex" not in args
    assert "-filter_complex_script" not in args


def test_assemble_targets_work_not_out(tmp_path, ready, monkeypatch):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: "")
    result = asm.assemble(spec, ws, "final", clips, {}, mix, ws.log_path("t"))
    assert result == ws.master_path
    assert result.parent == ws.work_dir


def test_final_encode_tags_bt709_and_faststart(tmp_path, ready, monkeypatch):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    captured: list[list[str]] = []
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    asm.assemble(spec, ws, "final", clips, {}, mix, ws.log_path("t"))
    joined = " ".join(captured[0])
    assert "-colorspace bt709" in joined
    assert "-color_primaries bt709" in joined
    assert "-color_trc bt709" in joined
    assert "+faststart" in joined
    assert "-crf 18" in joined


def test_draft_mode_overrides_crf_and_preset_but_keeps_delivery_conformance(
    tmp_path, ready, monkeypatch
):
    ws, clips, mix = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    draft_ws = Workspace(root=ws.root, slug="demo", mode="draft")
    draft_ws.ensure_dirs()
    captured: list[list[str]] = []
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    asm.assemble(spec, draft_ws, "draft", clips, {}, mix, draft_ws.log_path("t"))
    joined = " ".join(captured[0])
    assert f"-crf {asm.DRAFT_CRF}" in joined
    assert f"-preset {asm.DRAFT_PRESET}" in joined
    assert "-pix_fmt yuv420p" in joined      # delivery conformance still exercised
    assert "-c:a aac" in joined
    # MINIMAL's delivery.profile is "high": ultrafast alone can't reach it
    # (verified against the real binary -- see assemble.py's comment), so
    # the cabac/8x8dct override must be present.
    assert "-x264-params cabac=1:8x8dct=1" in joined


def test_draft_mode_does_not_force_x264_params_for_a_non_high_profile(
    tmp_path, ready, monkeypatch
):
    # Regression test for a task-15 review finding: an earlier version of
    # this fix applied "-x264-params cabac=1:8x8dct=1" unconditionally in
    # draft mode, on the false claim that "-profile:v" would constrain the
    # signalled profile back down for "main"/"baseline". It doesn't --
    # 8x8dct is itself a High-only feature, so forcing it on drags a "main"
    # request up to a High-profile bitstream regardless (reproduced against
    # the real binary and end-to-end through cmd_render). The fix must only
    # apply when the spec actually asks for "high".
    ws, clips, mix = ready
    non_high = copy.deepcopy(MINIMAL)
    non_high["delivery"]["profile"] = "main"
    spec, _ = load_spec(write(tmp_path, non_high))
    draft_ws = Workspace(root=ws.root, slug="demo", mode="draft")
    draft_ws.ensure_dirs()
    captured: list[list[str]] = []
    monkeypatch.setattr(asm.ffmpeg, "run", lambda args, log_path: captured.append(args) or "")
    asm.assemble(spec, draft_ws, "draft", clips, {}, mix, draft_ws.log_path("t"))
    joined = " ".join(captured[0])
    assert "-profile:v main" in joined
    assert "-x264-params" not in joined
