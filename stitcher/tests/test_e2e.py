import json
import shutil
import subprocess
from pathlib import Path

import pytest

from stitcher import cli
from stitcher.naming import Workspace
from tests.fixtures import make_fixture

pytestmark = pytest.mark.e2e

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not on PATH",
)
needs_font = pytest.mark.skipif(
    make_fixture.find_font() is None, reason="no usable font for the fixture"
)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    root = tmp_path_factory.mktemp("renders")
    make_fixture.build(root)
    code = cli.cmd_render("e2e", root, "final", force=False)
    return root, code


@needs_ffmpeg
@needs_font
def test_the_render_exits_clean(rendered):
    _, code = rendered
    assert code == cli.EXIT_OK


@needs_ffmpeg
@needs_font
def test_every_deliverable_is_written(rendered):
    root, _ = rendered
    ws = Workspace(root=root, slug="e2e", mode="final")
    for path in (ws.out_master(1), ws.out_cover(1), ws.out_srt(1), ws.out_ass(1),
                 ws.out_qa_json(1), ws.out_qa_md(1)):
        assert path.is_file(), f"missing deliverable: {path.name}"


@needs_ffmpeg
@needs_font
def test_the_qa_report_is_the_assertion_surface(rendered):
    root, _ = rendered
    ws = Workspace(root=root, slug="e2e", mode="final")
    payload = json.loads(ws.out_qa_json(1).read_text(encoding="utf-8"))
    assert payload["status"] == "pass", json.dumps(payload["checks"], indent=2)
    names = {check["name"] for check in payload["checks"]}
    assert {"container", "colour_tagging", "integrated_loudness", "true_peak",
            "loudnorm_linearity", "duck_depth", "safe_zone",
            "timeline_integrity", "placeholders"} <= names


@needs_ffmpeg
@needs_font
def test_the_master_is_a_conforming_short(rendered):
    from stitcher import ffmpeg
    root, _ = rendered
    ws = Workspace(root=root, slug="e2e", mode="final")
    probed = ffmpeg.probe(ws.out_master(1))
    assert (probed.width, probed.height) == (1080, 1920)
    assert probed.pix_fmt == "yuv420p"
    assert probed.colorspace == "bt709"
    assert probed.audio_codec == "aac"
    assert probed.sample_rate == 48000
    assert abs(probed.duration - 6.0) <= 1 / 30


@needs_ffmpeg
@needs_font
def test_a_second_identical_render_is_a_no_op(rendered):
    root, _ = rendered
    ws = Workspace(root=root, slug="e2e", mode="final")
    assert cli.cmd_render("e2e", root, "final", force=False) == cli.EXIT_OK
    assert not ws.out_master(2).exists()


# --- a bed window laid over the voice, measured against the real binary -----


@pytest.fixture(scope="module")
def rendered_windowed_bed(tmp_path_factory):
    """The main fixture's bed has `windows: []`, so the whole
    window-over-the-duck path had only ever been exercised against mocks."""
    root = tmp_path_factory.mktemp("windowed")
    base = make_fixture.build(root)
    spec = json.loads((base / "render-spec.json").read_text(encoding="utf-8"))
    spec["audio"]["bed"]["windows"] = [
        {"in": 0.0, "out": 6.0, "mode": "ducked", "level_db": -30.0}
    ]
    (base / "render-spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return root, cli.cmd_render("e2e", root, "final", force=False)


@needs_ffmpeg
@needs_font
def test_a_bed_window_over_the_voice_verifies_against_the_window_level(
    rendered_windowed_bed,
):
    """Design spec §3: an explicit window governs its span outright, over the
    duck. Measured on the real binary before the fix, this correct render
    reported `expected -14.0 dB, worst measured -22.0 dB` -- an 8 dB error
    against a 1.5 dB tolerance, so duck_depth FAILed, exit 3, and the master
    was never promoted."""
    root, code = rendered_windowed_bed
    ws = Workspace(root=root, slug="e2e", mode="final")
    assert code == cli.EXIT_OK
    payload = json.loads(ws.out_qa_json(1).read_text(encoding="utf-8"))
    duck = next(c for c in payload["checks"] if c["name"] == "duck_depth")
    assert duck["status"] == "pass", duck["detail"]
    assert "expected -22.0 dB" in duck["detail"]


# --- the second fixture: a real clip source, no bed, a short voice ----------


@pytest.fixture(scope="module")
def rendered_clip(tmp_path_factory):
    root = tmp_path_factory.mktemp("clip")
    make_fixture.build_clip(root)
    code = cli.cmd_render(make_fixture.CLIP_SLUG, root, "final", force=False)
    return root, code


def count_frames(path: Path) -> int:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return int(completed.stdout.strip().rstrip(","))


@needs_ffmpeg
@needs_font
def test_a_clip_shot_renders_and_passes_qa(rendered_clip):
    root, code = rendered_clip
    ws = Workspace(root=root, slug=make_fixture.CLIP_SLUG, mode="final")
    payload = (
        json.loads(ws.out_qa_json(1).read_text(encoding="utf-8"))
        if ws.out_qa_json(1).is_file() else {"checks": "no QA report written"}
    )
    assert code == cli.EXIT_OK, json.dumps(payload, indent=2)
    assert payload["status"] == "pass", json.dumps(payload["checks"], indent=2)


@needs_ffmpeg
@needs_font
def test_a_clip_shot_emits_exactly_its_timeline_slot_of_frames(rendered_clip):
    """`trim=start=0.5` on a 25fps source snaps to the source's frame grid and
    lands short; `-frames:v` cannot invent the missing frame. Measured against
    the real binary before the clone pad: 44 frames where the 0.0-1.5s slot at
    30fps asks for 45. Every later shot would then start one frame early
    against authored overlay/caption/audio times."""
    root, _ = rendered_clip
    ws = Workspace(root=root, slug=make_fixture.CLIP_SLUG, mode="final")
    clip = ws.shot_clip(1, "C-01", "Hook")
    assert clip.is_file(), f"stage A wrote no clip at {clip}"
    assert count_frames(clip) == 45


@needs_ffmpeg
@needs_font
def test_a_bedless_spec_with_a_short_voice_is_not_truncated(rendered_clip):
    """`atrim=0:runtime` trims but never pads, so a 2.0s voice in a 3.0s
    bed-less spec left the mix 2.0s long and stage D's `-shortest` then cut the
    master down to it."""
    from stitcher import ffmpeg
    root, _ = rendered_clip
    ws = Workspace(root=root, slug=make_fixture.CLIP_SLUG, mode="final")
    assert abs(ffmpeg.probe(ws.audio_step("06", "mix_final")).duration
               - make_fixture.CLIP_RUNTIME) <= 0.01
    probed = ffmpeg.probe(ws.out_master(1))
    assert abs(probed.duration - make_fixture.CLIP_RUNTIME) <= 1 / 30


@needs_ffmpeg
@needs_font
def test_draft_mode_renders_with_a_placeholder_for_a_missing_still(tmp_path):
    root = tmp_path / "renders"
    base = make_fixture.build(root)
    (base / "assets" / "s2.png").unlink()
    ws = Workspace(root=root, slug="e2e", mode="draft")
    assert cli.cmd_render("e2e", root, "draft", force=False) in (cli.EXIT_OK,)
    assert ws.out_master(None).is_file()
    payload = json.loads(ws.out_qa_json(None).read_text(encoding="utf-8"))
    placeholders = next(c for c in payload["checks"] if c["name"] == "placeholders")
    assert "s2" in placeholders["detail"] or "E-02" in placeholders["detail"]
