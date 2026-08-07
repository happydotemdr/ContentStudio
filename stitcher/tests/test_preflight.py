import json
from pathlib import Path

import pytest
from PIL import Image

from stitcher import preflight as pf
from stitcher.ffmpeg import ProbeResult
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_spec import MINIMAL, write

# Real, loadable fonts for the font-load check (design spec line 571: "every
# referenced font file loads" -- existence alone is not enough, see
# _check_fonts). No font fixture is checked into this repo yet, so we fall
# back to system fonts the same way the plan's Task 15 e2e fixture does
# (docs/superpowers/plans/2026-08-06-automated-asset-stitcher.md, find_font).
# Tests that need a real, working font are skipped if none is found; tests
# that only need a font path to exist-but-be-corrupt do not depend on this.
_FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]


def _find_font() -> Path | None:
    return next((p for p in _FONT_CANDIDATES if p.is_file()), None)


REAL_FONT = _find_font()

requires_font = pytest.mark.skipif(
    REAL_FONT is None, reason="no usable system font found (tried arialbd.ttf, arial.ttf)"
)


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
    for name in ("a.png", "b.png", "vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    # A real image, unlike the placeholder bytes above: stage E opens the
    # cover with Pillow, so preflight performs that same load (_check_cover)
    # and a stub would fail it for the right reason at the wrong time.
    Image.new("RGB", (8, 8), (10, 20, 30)).save(ws.asset("cover.png"))
    (tmp_path / "fonts").mkdir(exist_ok=True)
    return ws


def load(tmp_path: Path, payload: dict):
    spec, _ = load_spec(write(tmp_path / "spec", payload))
    return spec


@pytest.fixture
def spec_and_font(tmp_path: Path, ready):
    if REAL_FONT is None:
        pytest.skip("no usable system font found (tried arialbd.ttf, arial.ttf)")
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(REAL_FONT)
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


@requires_font
def test_draft_mode_allows_a_missing_stem_that_declares_duration_s(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(REAL_FONT)
    payload["audio"]["stems"][0]["duration_s"] = 2.875
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    ready.asset("vo.wav").unlink()
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "draft")
    assert "vo.wav" in report.missing_audio
    assert report.errors == []


@requires_font
def test_source_trim_outside_the_real_duration_is_a_preflight_error(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(REAL_FONT)
    payload["shots"][0].update(
        {"kind": "clip", "source": "a.mp4", "source_in": 0.0, "source_out": 9.0}
    )
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    ready.asset("a.mp4").write_bytes(b"x")
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: clip(5.0))
    report = pf.run_preflight(spec, ready, "final")
    assert any("source_out" in e and "5.0" in e for e in report.errors)


@requires_font
def test_an_unprobeable_clip_source_is_reported_not_raised(tmp_path, ready, monkeypatch):
    """Important-1 fix (task-5 review): a present-but-corrupt clip source used
    to reach an unguarded second ffmpeg.probe() call in _check_visual_assets,
    letting FFmpegError propagate straight out of run_preflight instead of
    being recorded -- defeating the "report every problem, never crash"
    contract this module exists for. run_preflight must return a report
    containing the error, not raise.
    """
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(REAL_FONT)
    payload["shots"][0].update(
        {"kind": "clip", "source": "a.mp4", "source_in": 0.0, "source_out": 9.0}
    )
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    ready.asset("a.mp4").write_bytes(b"x")

    def probe_corrupt(path):
        if Path(path).name == "a.mp4":
            raise pf.ffmpeg.FFmpegError(f"ffprobe failed on {path}: corrupt container")
        return still()

    monkeypatch.setattr(pf.ffmpeg, "probe", probe_corrupt)
    report = pf.run_preflight(spec, ready, "final")  # must not raise
    assert any("a.mp4" in e for e in report.errors)


def test_a_missing_font_file_is_an_error(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(tmp_path / "absent.ttf")
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "final")
    assert any("absent.ttf" in e for e in report.errors)


def test_a_corrupt_font_file_is_an_error(tmp_path, ready, monkeypatch):
    """Important-2 fix (task-5 review): a font file that exists but fails to
    load must be reported as an error -- existence alone is not "loads"
    (design spec line 571). Uses garbage bytes rather than a real font, so
    this test needs no @requires_font guard: Pillow rejects the four-byte
    payload on any platform.
    """
    payload = json.loads(json.dumps(MINIMAL))
    garbage = tmp_path / "corrupt.ttf"
    garbage.write_bytes(b"not a real font")
    payload["styles"]["card"]["font_file"] = str(garbage)
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "final")
    assert any("corrupt.ttf" in e for e in report.errors)


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


@requires_font
def test_text_that_cannot_fit_max_lines_is_a_preflight_error(tmp_path, ready, monkeypatch):
    """Design spec line 227 ("exceeding max_lines after wrapping is a preflight
    failure") and line 369 (listed under "rejected before any asset is
    touched"). Living only inside stage B, this surfaced as a render failure
    AFTER stage A had already burned an encode per shot."""
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(REAL_FONT)
    payload["styles"]["card"]["max_width_px"] = 300
    payload["styles"]["card"]["max_lines"] = 1
    payload["overlays"][0]["text"] = "one two three four five six seven eight nine ten"
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "final")
    assert any("hook-1" in e and "max_lines" in e for e in report.errors)


@requires_font
def test_a_single_overlong_token_is_a_preflight_error(tmp_path, ready, monkeypatch):
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(REAL_FONT)
    payload["styles"]["card"]["max_width_px"] = 50
    payload["overlays"][0]["text"] = "SUPERCALIFRAGILISTICEXPIALIDOCIOUS"
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "final")
    assert any("hook-1" in e and "max_width_px" in e for e in report.errors)


@requires_font
def test_a_cover_ffprobe_reads_but_pillow_cannot_open_is_an_error(spec_and_font, monkeypatch):
    """Stage E opens the cover with Pillow while preflight probed it with
    ffprobe, so a file only one of them accepts used to surface as an uncaught
    traceback -- after the master had already been promoted into out/."""
    spec, ws = spec_and_font
    ws.asset("cover.png").write_bytes(b"not a png at all")
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ws, "final")
    assert any("cover.png" in e and "image" in e for e in report.errors)


@requires_font
def test_draft_mode_warns_that_a_non_high_profile_cannot_be_honoured(
    tmp_path, ready, monkeypatch
):
    """Accepted limitation, surfaced before the render rather than after it:
    -preset ultrafast emits Constrained Baseline and the High-only 8x8dct
    override cannot generalize, so verify's container check will fail. A
    warning, not an error -- the behaviour is deliberate."""
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(REAL_FONT)
    payload["delivery"]["profile"] = "main"
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())

    draft = pf.run_preflight(spec, ready, "draft")
    assert draft.ok is True
    assert any("main" in w and "--mode final" in w for w in draft.warnings)

    final = pf.run_preflight(spec, ready, "final")
    assert not any("--mode final" in w for w in final.warnings)


def test_the_path_gate_samples_the_longest_deliverable(ready):
    """out_contact_sheet's suffix is 10 characters longer than out_qa_json's,
    so sampling the latter let a workspace pass this gate and then fail while
    writing the contact sheet -- which happens after promotion."""
    assert len(str(ready.out_contact_sheet(99))) > len(str(ready.out_qa_json(99)))


@requires_font
def test_slug_not_matching_the_workspace_directory_is_an_error(tmp_path, ready, monkeypatch):
    """Controller-directed addition (rulings.md, not in the brief): design spec §3/§6
    require the spec's slug to match the containing directory name. Task 2's
    validate_spec(spec) is pure and has no directory to check against, so the check
    lives here, where both spec.slug and ws.slug are available."""
    payload = json.loads(json.dumps(MINIMAL))
    payload["styles"]["card"]["font_file"] = str(REAL_FONT)
    payload["slug"] = "not-demo"
    (tmp_path / "spec").mkdir(exist_ok=True)
    spec = load(tmp_path, payload)
    monkeypatch.setattr(pf.ffmpeg, "probe", lambda path: still())
    report = pf.run_preflight(spec, ready, "final")
    assert any("not-demo" in e and "demo" in e for e in report.errors)
