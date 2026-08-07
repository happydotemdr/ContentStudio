import json
from pathlib import Path

import pytest

from stitcher import verify as vf
from stitcher.ffmpeg import ProbeResult
from stitcher.naming import Workspace
from stitcher.spec import load_spec
from tests.test_spec import MINIMAL, write


def good_probe(duration: float = 6.0) -> ProbeResult:
    # color_primaries/color_transfer supplied explicitly (not left to
    # ProbeResult's default): colour_tagging gates on all three fields
    # together, and a "conforming render" fixture must actually measure
    # bt709 on all three rather than benefit from a passing default (review
    # round 1 finding on task-13).
    return ProbeResult(duration, 1080, 1920, 30.0, "yuv420p", "h264",
                       "aac", 48000, "bt709", "High", "bt709", "bt709")


@pytest.fixture
def ready(tmp_path: Path):
    ws = Workspace(root=tmp_path / "r", slug="demo", mode="final")
    ws.ensure_dirs()
    master = ws.master_path
    master.write_bytes(b"mp4")
    # _check_duck probes the stem files to learn their durations.
    for name in ("vo.wav", "bed.mp3"):
        ws.asset(name).write_bytes(b"x")
    ws.audio_step("06", "mix_final").write_bytes(b"wav")
    ws.audio_step("04a", "bed_conformed").write_bytes(b"wav")
    ws.audio_step("04b", "bed_ducked").write_bytes(b"wav")
    (ws.audio_dir / "loudnorm_pass1.json").write_text("{}", encoding="utf-8")
    (ws.work_dir / "loudnorm_pass2.json").write_text(
        json.dumps({"normalization_type": "linear"}), encoding="utf-8"
    )
    png = ws.overlay_png(1, "hook-1", "hello")
    png.write_bytes(b"png")
    png.with_suffix(".json").write_text(json.dumps({"bbox": [200, 500, 800, 700]}), "utf-8")
    return ws, master


def wire(monkeypatch, *, duration=6.0, integrated=-14.0, true_peak=-1.6,
         duck_delta=-14.0):
    monkeypatch.setattr(vf.ffmpeg, "probe", lambda path: good_probe(duration))

    def fake_measure(path, log_path):
        if "mix_final" in str(path):
            return {"input_i": integrated, "input_tp": true_peak, "input_lra": 6.0}
        return {"input_i": integrated, "input_tp": true_peak, "input_lra": 6.0}

    monkeypatch.setattr(vf.ffmpeg, "measure_loudness", fake_measure)

    def fake_window(path, start, dur, log_path):
        return -30.0 + duck_delta if "04b" in str(path) else -30.0

    monkeypatch.setattr(vf, "measure_window", fake_window)
    monkeypatch.setattr(vf.ffmpeg, "run", lambda args, log_path: "")


def status_of(checks, name):
    return next(c.status for c in checks if c.name == name)


def test_a_conforming_render_passes_every_check(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert vf.overall_status(checks) == "pass"


def test_a_wrong_h264_profile_fails_container_conformance(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    monkeypatch.setattr(
        vf.ffmpeg, "probe",
        lambda path: ProbeResult(6.0, 1080, 1920, 30.0, "yuv420p", "h264",
                                 "aac", 48000, "bt709", "Baseline"),
    )
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "container") == vf.FAIL


def test_wrong_resolution_fails_container_conformance(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    monkeypatch.setattr(
        vf.ffmpeg, "probe",
        lambda path: ProbeResult(6.0, 720, 1280, 30.0, "yuv420p", "h264", "aac", 48000, "bt709"),
    )
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "container") == vf.FAIL


def test_missing_bt709_tagging_fails_the_colour_check(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    monkeypatch.setattr(
        vf.ffmpeg, "probe",
        lambda path: ProbeResult(6.0, 1080, 1920, 30.0, "yuv420p", "h264", "aac", 48000, "bt601"),
    )
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "colour_tagging") == vf.FAIL


def test_unmeasured_colour_primaries_or_transfer_is_not_silently_a_pass(ready, tmp_path, monkeypatch):
    # A ProbeResult constructed without the two new colour fields (as every
    # ProbeResult built before this task existed necessarily was) must not
    # report colour_tagging = pass -- that would mean two of three required
    # fields passed without anything having measured them (review round 1
    # finding on task-13). This is FAIL, not UNAVAILABLE: verify() only ever
    # reaches this check after successfully probing the master file, so
    # "colour_primaries/color_transfer read back None" is not "we could not
    # measure it" -- it is a genuine, actionable measurement: the file was
    # probed and the tags are absent, exactly as a real render encoded with
    # output-level colour flags instead of a frame-tagging filter measures
    # (see task-13-report.md's empirical finding). UNAVAILABLE is reserved
    # for checks whose data source (a separate, deletable work/ artifact)
    # is missing outright, which is not the case here.
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    monkeypatch.setattr(
        vf.ffmpeg, "probe",
        lambda path: ProbeResult(6.0, 1080, 1920, 30.0, "yuv420p", "h264", "aac", 48000, "bt709"),
    )
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "colour_tagging") == vf.FAIL


def test_loudness_outside_one_lu_fails(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, integrated=-11.5)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "integrated_loudness") == vf.FAIL


def test_true_peak_is_measured_pre_aac_on_the_mix(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    seen: list[str] = []

    def fake_measure(path, log_path):
        seen.append(str(path))
        return {"input_i": -14.0, "input_tp": -1.6, "input_lra": 6.0}

    wire(monkeypatch)
    monkeypatch.setattr(vf.ffmpeg, "measure_loudness", fake_measure)
    vf.verify(spec, ws, master, ws.log_path("t"))
    assert any("06_mix_final.wav" in path for path in seen)


def test_true_peak_over_the_target_fails(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, true_peak=-0.4)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "true_peak") == vf.FAIL


def test_a_dynamic_loudnorm_record_fails_the_linearity_check(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    (ws.work_dir / "loudnorm_pass2.json").write_text(
        json.dumps({"normalization_type": "dynamic"}), encoding="utf-8"
    )
    wire(monkeypatch)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "loudnorm_linearity") == vf.FAIL


def test_duck_depth_compares_the_two_bed_intermediates(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    probed: list[str] = []

    def fake_window(path, start, dur, log_path):
        probed.append(Path(path).name)
        return -44.0 if "04b" in str(path) else -30.0

    wire(monkeypatch)
    monkeypatch.setattr(vf, "measure_window", fake_window)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert "04a_bed_conformed.wav" in probed
    assert "04b_bed_ducked.wav" in probed
    assert status_of(checks, "duck_depth") == vf.PASS


def test_duck_depth_outside_tolerance_fails(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, duck_delta=-6.0)   # expected -14 dB, measured -6 dB
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "duck_depth") == vf.FAIL


def test_an_overlay_escaping_the_safe_zone_fails(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    png = ws.overlay_png(1, "hook-1", "hello")
    png.with_suffix(".json").write_text(json.dumps({"bbox": [0, 0, 1080, 1900]}), "utf-8")
    wire(monkeypatch)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "safe_zone") == vf.FAIL


def test_timeline_integrity_allows_one_frame_of_aac_padding(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, duration=6.03)     # one frame at 30fps
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "timeline_integrity") == vf.PASS


def test_timeline_integrity_fails_beyond_one_frame(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch, duration=6.5)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "timeline_integrity") == vf.FAIL


def test_missing_work_artifacts_report_unavailable_never_pass(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    ws.audio_step("04a", "bed_conformed").unlink()
    ws.audio_step("04b", "bed_ducked").unlink()
    (ws.work_dir / "loudnorm_pass2.json").unlink()
    for sidecar in ws.overlays_dir.glob("*.json"):
        sidecar.unlink()
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "duck_depth") == vf.UNAVAILABLE
    assert status_of(checks, "safe_zone") == vf.UNAVAILABLE
    assert status_of(checks, "loudnorm_linearity") == vf.UNAVAILABLE
    assert vf.overall_status(checks) == "incomplete"


def test_a_placeholder_in_final_mode_is_a_failure(ready, tmp_path, monkeypatch):
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    (ws.work_dir / "placeholders").mkdir(exist_ok=True)
    (ws.work_dir / "placeholders" / "B-01.png").write_bytes(b"png")
    wire(monkeypatch)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "placeholders") == vf.FAIL


def test_write_reports_emits_both_json_and_markdown(tmp_path: Path):
    checks = [vf.Check("container", vf.PASS, "1080x1920 @ 30fps"),
              vf.Check("true_peak", vf.FAIL, "-0.4 dBTP exceeds -1.5")]
    json_path, md_path = tmp_path / "qa.json", tmp_path / "qa.md"
    vf.write_reports(checks, json_path, md_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert len(payload["checks"]) == 2
    assert "true_peak" in md_path.read_text(encoding="utf-8")
