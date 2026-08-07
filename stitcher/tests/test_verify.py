import json
import math
import shutil
from pathlib import Path

import pytest

from stitcher import envelope, verify as vf
from stitcher.ffmpeg import ProbeResult
from stitcher.naming import Workspace
from stitcher.spec import load_spec, runtime_seconds
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


# --- bed windows and fades (design spec §3 "precedence is window > duck") ---
#
# The fixture below simulates a CORRECT render: the ducked file is exactly the
# conformed file with stage C's own shifted envelope applied. Any spec whose
# envelope is not a flat duck_db plateau therefore proves whether verify
# derives its expectation from the same envelope stage C rendered, or from the
# constant duck_db - gain_db (which is only right when no window or fade
# covers the voice).


def correct_render(monkeypatch, spec, base_db=-30.0):
    """measure_window that reports the levels a correct stage C would produce.

    The ducked reading is the ENERGY AVERAGE of the envelope across whatever
    window verify asks for, which is what ebur128 would report for a
    constant-level bed modulated by that envelope -- not the envelope's value
    at a single instant. That distinction is the whole point: a check that
    measures one window spanning two envelope levels cannot compare it to
    either level, so this fixture only reports a clean number when verify
    asks about a window the envelope actually holds flat.
    """
    bed = spec.audio.bed
    spans = envelope.stem_spans(
        spec.audio.stems, {stem.file: 6.0 for stem in spec.audio.stems}
    )
    points = envelope.build_breakpoints(bed, spans, runtime_seconds(spec))
    shifted = [envelope.Breakpoint(p.t, p.db - bed.gain_db) for p in points]

    def fake_window(path, start, duration, log_path):
        if "04b" not in str(path):
            return base_db
        steps = 400
        energy = sum(
            10 ** (envelope.level_at(shifted, start + duration * (i + 0.5) / steps) / 10)
            for i in range(steps)
        )
        return base_db + 10 * math.log10(energy / steps)

    monkeypatch.setattr(vf, "measure_window", fake_window)


def with_window(**window) -> dict:
    payload = json.loads(json.dumps(MINIMAL))
    payload["audio"]["bed"]["windows"] = [window]
    return payload


def test_a_bed_window_over_a_voice_span_is_expected_at_the_window_level(
    ready, tmp_path, monkeypatch
):
    """A `level_db` window sitting over the voice makes the envelope -30 dB
    (voice-relative) there, not duck_db. Verify must expect the window's level;
    against the old constant expectation this is an 8 dB error and a false FAIL
    on a correct render."""
    ws, master = ready
    spec, _ = load_spec(
        write(tmp_path, with_window(**{"in": 0.0, "out": 3.0, "mode": "ducked",
                                       "level_db": -30.0}))
    )
    wire(monkeypatch)
    correct_render(monkeypatch, spec)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "duck_depth") == vf.PASS


def test_a_mode_out_window_over_a_voice_span_measures_the_rest_of_the_span(
    ready, tmp_path, monkeypatch
):
    """The design spec's own canonical case: "bed held out entirely for 0-3s
    while the child speaks". The held-out region cannot be measured (ebur128
    floors at -70), so it is skipped rather than compared -- but the ducked
    remainder of the same span still is."""
    ws, master = ready
    spec, _ = load_spec(
        write(tmp_path, with_window(**{"in": 0.0, "out": 3.0, "mode": "out",
                                       "level_db": None}))
    )
    wire(monkeypatch)
    correct_render(monkeypatch, spec)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    duck = next(c for c in checks if c.name == "duck_depth")
    assert duck.status == vf.PASS, duck.detail
    assert "-14.0" in duck.detail


def test_a_window_that_silences_the_whole_span_is_unavailable_not_a_pass(
    ready, tmp_path, monkeypatch
):
    """Nothing measurable is left, so the check must say so rather than assert
    a depth it never measured."""
    ws, master = ready
    spec, _ = load_spec(
        write(tmp_path, with_window(**{"in": 0.0, "out": 6.0, "mode": "out",
                                       "level_db": None}))
    )
    wire(monkeypatch)
    correct_render(monkeypatch, spec)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "duck_depth") == vf.UNAVAILABLE


def test_a_windowed_bed_that_is_actually_wrong_still_fails(ready, tmp_path, monkeypatch):
    """The envelope-derived expectation must not be vacuous: a ducked file that
    ignored the window (it applied plain duck_db throughout) is a real defect
    and must still FAIL."""
    ws, master = ready
    spec, _ = load_spec(
        write(tmp_path, with_window(**{"in": 0.0, "out": 3.0, "mode": "ducked",
                                       "level_db": -30.0}))
    )
    wire(monkeypatch, duck_delta=-14.0)  # plain duck_db everywhere, window ignored
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "duck_depth") == vf.FAIL


def test_a_fade_across_the_voice_span_is_not_compared_against_a_flat_level(
    ready, tmp_path, monkeypatch
):
    """A fade makes the envelope a ramp; an integrated measurement over a ramp
    cannot be compared to any single expected value, so the ramp is excluded
    the way the attack/release ramps already are."""
    ws, master = ready
    payload = json.loads(json.dumps(MINIMAL))
    payload["audio"]["bed"]["fades"] = [{"at": 0.0, "kind": "in", "ms": 4000}]
    spec, _ = load_spec(write(tmp_path, payload))
    wire(monkeypatch)
    correct_render(monkeypatch, spec)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    duck = next(c for c in checks if c.name == "duck_depth")
    assert duck.status in (vf.PASS, vf.UNAVAILABLE), duck.detail


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
    # work/ itself survives here, so this one genuinely did look and find
    # nothing -- unlike the cleaned-workspace case below.
    assert status_of(checks, "placeholders") == vf.PASS
    assert vf.overall_status(checks) == "incomplete"


def test_a_cleaned_work_directory_makes_placeholder_detection_unavailable(
    ready, tmp_path, monkeypatch
):
    """Design spec line 536 names placeholder detection among the checks that
    must report `unavailable` when their artifacts are gone. An empty glob on
    a workspace with no work/ at all is not evidence that no placeholder was
    used, and reporting PASS there asserts something nothing measured."""
    ws, master = ready
    spec, _ = load_spec(write(tmp_path, MINIMAL))
    wire(monkeypatch)
    shutil.rmtree(ws.work_dir)
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "placeholders") == vf.UNAVAILABLE
    assert vf.overall_status(checks) == "incomplete"


def test_timeline_integrity_measures_the_span_of_the_shot_bounds(
    ready, tmp_path, monkeypatch
):
    """The rendered master is the concat of the shot clips, so its expected
    length is the SPAN of the frame bounds, not the last shot's absolute end
    frame. Reading the end frame made a non-zero-start timeline fail after a
    full render with a message that pointed nowhere near the cause."""
    ws, master = ready
    payload = json.loads(json.dumps(MINIMAL))
    payload["shots"][0]["in"] = 2.0
    payload["shots"][0]["out"] = 5.0
    payload["shots"][1]["in"] = 5.0
    payload["shots"][1]["out"] = 8.0
    spec, _ = load_spec(write(tmp_path, payload))
    wire(monkeypatch, duration=6.0)   # 180 - 60 = 120 frames = 6.0s of clips
    checks = vf.verify(spec, ws, master, ws.log_path("t"))
    assert status_of(checks, "timeline_integrity") == vf.PASS


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
