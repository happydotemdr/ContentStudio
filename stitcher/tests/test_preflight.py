import json
from pathlib import Path

import pytest

from stitcher import preflight as pf
from stitcher.ffmpeg import ProbeResult
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_spec import MINIMAL, write


def still(duration: float = 0.0) -> ProbeResult:
    return ProbeResult(duration, 1080, 1920, None, "rgba", "png", None, None, None)


def clip(duration: float) -> ProbeResult:
    return ProbeResult(duration, 1080, 1920, 24.0, "yuv420p", "h264", None, None, "bt709")


def wav(duration: float) -> ProbeResult:
    return ProbeResult(duration, None, None, None, None, None, "pcm_s16le", 48000, None)


@pytest.fixture
def ready(tmp_path: Path, monkeypatch):
    """A workspace whose spec is valid and whose tools are present."""
    monkeypatch.setattr(pf.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 8.0.1")
    monkeypatch.setattr(pf.ffmpeg, "has_encoder", lambda name: name == "libx264")
    ws = Workspace(root=tmp_path, slug="demo", mode="final")
    ws.ensure_dirs()
    for name in ("a.png", "b.png", "cover.png", "vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    (tmp_path / "fonts").mkdir(exist_ok=True)
    return ws


def load(tmp_path: Path, payload: dict):
    spec, _ = load_spec(write(tmp_path / "spec", payload))
    return spec


@pytest.fixture
def spec_and_font(tmp_path: Path, ready):
    payload = json.loads(json.dumps(MINIMAL))
    font = tmp_path / "Inter-Bold.ttf"
    font.write_bytes(b"font")
    payload["styles"]["card"]["font_file"] = str(font)
    (tmp_path / "spec").mkdir(exist_ok=True)
    return load(tmp_path, payload), ready


def test_preflight_passes_when_everything_is_present(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert report.errors == []
    assert report.ok is True


def test_preflight_reports_every_problem_not_just_the_first(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    ws.asset("a.png").unlink()
    ws.asset("b.png").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert len(report.errors) >= 2


def test_final_mode_treats_a_missing_visual_asset_as_an_error(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    ws.asset("a.png").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert any("a.png" in e for e in report.errors)


def test_draft_mode_records_a_missing_visual_as_a_placeholder(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    ws.asset("a.png").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "draft")
    assert "a.png" in report.missing_visual
    assert not any("a.png" in e for e in report.errors)


def test_draft_mode_aborts_on_a_missing_stem_without_duration_s(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    ws.asset("vo.wav").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "draft")
    assert any("duration_s" in e for e in report.errors)


def test_draft_mode_allows_a_missing_stem_that_declares_duration_s(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    font = tmp_path / "Inter-Bold.ttf"
    font.write_bytes(b"font")
    payload["styles"]["card"]["font_file"] = str(font)
    payload["audio"]["stems"][0]["duration_s"] = 2.875
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    ready.asset("vo.wav").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "draft")
    assert "vo.wav" in report.missing_audio
    assert report.errors == []


def test_source_trim_outside_the_real_duration_is_a_preflight_error(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    font = tmp_path / "Inter-Bold.ttf"
    font.write_bytes(b"font")
    payload["styles"]["card"]["font_file"] = str(font)
    payload["shots"][0].update(
        {"kind": "clip", "source": "a.mp4", "source_in": 0.0, "source_out": 9.0}
    )
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    ready.asset("a.mp4").write_bytes(b"x")
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: clip(5.0))
    report = pf.run_preflight(spec, ready, "final")
    assert any("source_out" in e and "5.0" in e for e in report.errors)


def test_a_missing_font_file_is_an_error(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(tmp_path / "absent.ttf")
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "final")
    assert any("absent.ttf" in e for e in report.errors)


def test_missing_libx264_is_an_error(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "has_encoder", lambda name: False)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert any("libx264" in e for e in report.errors)


def test_libass_is_never_required(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "has_encoder", lambda name: name == "libx264")
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert not any("libass" in e.lower() for e in report.errors)


def test_an_over_long_path_is_an_error(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    monkeypatch.setattr(pf, "MAX_PATH_LEN", 10)
    report = pf.run_preflight(spec, ws, "final")
    assert any("path" in e.lower() for e in report.errors)


def test_a_pre_8x_ffmpeg_is_an_error(spec_and_font, monkeypatch):
    spec, ws = spec_and_font
    monkeypatch.setattr(pf.ffmpeg, "ffmpeg_version", lambda: "ffmpeg version 7.1")
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert any("8" in e for e in report.errors)


def test_slug_not_matching_the_workspace_directory_is_an_error(tmp_path, ready, monkeypatch):
    """Controller-directed addition (rulings.md, not in the brief): design spec §3/§6
    require the spec's slug to match the containing directory name. Task 2's
    validate_spec(spec) is pure and has no directory to check against, so the check
    lives here, where both spec.slug and ws.slug are available."""
    payload = json.loads(json.dumps(MINIMAL))
    font = tmp_path / "Inter-Bold.ttf"
    font.write_bytes(b"font")
    payload["styles"]["card"]["font_file"] = str(font)
    payload["slug"] = "not-demo"
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "final")
    assert any("not-demo" in e and "demo" in e for e in report.errors)
