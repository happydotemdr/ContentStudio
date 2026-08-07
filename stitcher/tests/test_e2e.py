import json
import shutil
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
