import json
import subprocess
from pathlib import Path

import pytest

from stitcher import ffmpeg as ff


def test_run_writes_the_command_to_the_log_before_executing(tmp_path: Path, monkeypatch):
    log = tmp_path / "run.log"
    seen: dict[str, bool] = {}

    def fake_run(args, capture_output, text, check, cwd=None):
        # The log must already exist and name the command by the time we execute.
        seen["logged"] = log.exists() and "-version" in log.read_text(encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ff.run(["ffmpeg", "-version"], log)
    assert seen["logged"] is True


def test_run_raises_with_the_command_and_stderr_tail(tmp_path: Path, monkeypatch):
    def fake_run(args, capture_output, text, check, cwd=None):
        return subprocess.CompletedProcess(args, 1, "", "boom: invalid argument")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ff.FFmpegError) as exc:
        ff.run(["ffmpeg", "-nope"], tmp_path / "run.log")
    assert "-nope" in str(exc.value)
    assert "boom: invalid argument" in str(exc.value)


def test_run_never_uses_a_shell(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(args, capture_output, text, check, cwd=None):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ff.run(["ffmpeg", "-i", "C:/a b/c.png"], tmp_path / "run.log")
    assert isinstance(captured["args"], list)


def test_probe_parses_a_video_stream(tmp_path: Path, monkeypatch):
    payload = {
        "format": {"duration": "3.500000"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080,
             "height": 1920, "pix_fmt": "yuv420p", "r_frame_rate": "30000/1001",
             "color_space": "bt709", "color_primaries": "bt709",
             "color_transfer": "bt709"},
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000"},
        ],
    }
    monkeypatch.setattr(ff, "_probe_json", lambda path: payload)
    result = ff.probe(tmp_path / "x.mp4")
    assert result.duration == pytest.approx(3.5)
    assert result.width == 1080
    assert result.fps == pytest.approx(30000 / 1001)
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
    assert result.sample_rate == 48000
    assert result.colorspace == "bt709"
    assert result.color_primaries == "bt709"
    assert result.color_transfer == "bt709"
    assert result.has_video and result.has_audio


def test_probe_reports_an_explicit_none_for_untagged_colour_fields(tmp_path: Path, monkeypatch):
    # A real file that genuinely lacks colour tagging must probe as None, not
    # silently inherit ProbeResult's "bt709" constructor default -- that
    # default exists only to keep pre-existing hand-built ProbeResult test
    # fixtures elsewhere in the suite conformant; probe() itself must always
    # pass an explicit value so verify.py's colour_tagging check (which gates
    # on colorspace/primaries/transfer together) can tell "untagged" from
    # "tagged bt709" for a file actually measured.
    payload = {
        "format": {"duration": "1.0"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080,
             "height": 1920, "pix_fmt": "yuv420p", "r_frame_rate": "30/1"},
        ],
    }
    monkeypatch.setattr(ff, "_probe_json", lambda path: payload)
    result = ff.probe(tmp_path / "untagged.mp4")
    assert result.colorspace is None
    assert result.color_primaries is None
    assert result.color_transfer is None


def test_probe_handles_an_audio_only_file(tmp_path: Path, monkeypatch):
    payload = {
        "format": {"duration": "2.875000"},
        "streams": [{"codec_type": "audio", "codec_name": "pcm_s16le",
                     "sample_rate": "48000"}],
    }
    monkeypatch.setattr(ff, "_probe_json", lambda path: payload)
    result = ff.probe(tmp_path / "vo.wav")
    assert result.has_audio and not result.has_video
    assert result.width is None
    assert result.duration == pytest.approx(2.875)


def test_measure_loudness_parses_the_ebur128_summary(tmp_path: Path, monkeypatch):
    stderr = (
        "[Parsed_ebur128_0 @ 0000] Summary:\n"
        "  Integrated loudness:\n"
        "    I:         -14.3 LUFS\n"
        "    Threshold: -24.8 LUFS\n"
        "  Loudness range:\n"
        "    LRA:         6.2 LU\n"
        "  True peak:\n"
        "    Peak:       -1.7 dBFS\n"
    )
    monkeypatch.setattr(ff, "run", lambda args, log_path: stderr)
    result = ff.measure_loudness(tmp_path / "mix.wav", tmp_path / "run.log")
    assert result["input_i"] == pytest.approx(-14.3)
    assert result["input_tp"] == pytest.approx(-1.7)
    assert result["input_lra"] == pytest.approx(6.2)


# --- silence is a measurement, not a parse failure -------------------------
#
# Captured verbatim from the installed 9.0 binary:
#
#     ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 2 \
#            -filter_complex ebur128=peak=true -f null -
#
# The integrated loudness comes back as the finite gating floor while the true
# peak comes back as the literal token "-inf", which the old numeric-only
# pattern could not match -- so measure_loudness RAISED on a digitally silent
# track and the render died at exit 2 blaming unreadable ffmpeg output.
SILENT_SUMMARY = (
    "[Parsed_ebur128_0 @ 0000] Summary:\n"
    "  Integrated loudness:\n"
    "    I:         -70.0 LUFS\n"
    "    Threshold:   0.0 LUFS\n"
    "  Loudness range:\n"
    "    LRA:         0.0 LU\n"
    "  True peak:\n"
    "    Peak:       -inf dBFS\n"
)


def test_measure_loudness_reads_an_infinite_true_peak(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ff, "run", lambda args, log_path: SILENT_SUMMARY)
    result = ff.measure_loudness(tmp_path / "silence.wav", tmp_path / "run.log")
    assert result["input_tp"] == float("-inf")
    assert result["input_i"] == pytest.approx(-70.0)
    assert result["input_lra"] == pytest.approx(0.0)


def test_a_positive_infinity_parses_too(tmp_path: Path, monkeypatch):
    """The pattern admits `inf` as well as `-inf`; neither is a parse error."""
    monkeypatch.setattr(
        ff, "run",
        lambda args, log_path: SILENT_SUMMARY.replace("-inf dBFS", "inf dBFS"),
    )
    result = ff.measure_loudness(tmp_path / "x.wav", tmp_path / "run.log")
    assert result["input_tp"] == float("inf")


def test_measure_loudness_still_raises_on_genuinely_absent_output(
    tmp_path: Path, monkeypatch
):
    """Admitting -inf must not turn a real parse failure into a silent one."""
    monkeypatch.setattr(ff, "run", lambda args, log_path: "ffmpeg wrote nothing useful")
    with pytest.raises(ff.FFmpegError):
        ff.measure_loudness(tmp_path / "x.wav", tmp_path / "run.log")


def test_digital_silence_is_detected_from_either_signal():
    assert ff.is_digital_silence({"input_i": -70.0, "input_tp": float("-inf")})
    # A stray non-zero sample lifts the peak off -inf, but ebur128 still
    # declined to measure the programme -- which is the operative condition.
    assert ff.is_digital_silence({"input_i": -70.0, "input_tp": -91.2})
    # Exact digital zero with a floor reading that somehow parsed higher.
    assert ff.is_digital_silence({"input_i": -60.0, "input_tp": float("-inf")})


def test_a_real_measurement_is_not_mistaken_for_silence():
    assert not ff.is_digital_silence({"input_i": -18.0, "input_tp": -3.0})
    assert not ff.is_digital_silence({"input_i": -69.9, "input_tp": -80.0})


# --- argv construction coverage -------------------------------------------
#
# The tests above monkeypatch this module's own helpers (`_probe_json`,
# `ff.run`), so none of them ever exercise the real argv these four
# functions hand to subprocess.run. These tests patch subprocess.run itself
# instead and assert the exact constructed command line, which is this
# module's actual unit responsibility -- six downstream stages depend on it.


def test_probe_json_builds_the_expected_ffprobe_argv(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    payload = {"format": {"duration": "1.0"}, "streams": []}

    def fake_run(args, capture_output, text, check, cwd=None):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    target = tmp_path / "clip.mp4"
    ff._probe_json(target)
    assert captured["args"] == [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(target),
    ]


def test_ffmpeg_version_argv_is_just_dash_version(monkeypatch):
    captured: dict[str, object] = {}
    banner = (
        "ffmpeg version 9.0-full_build-www.gyan.dev Copyright (c) 2000-2026 "
        "the FFmpeg developers\n"
    )

    def fake_run(args, capture_output, text, check, cwd=None):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, banner, "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    version = ff.ffmpeg_version()
    assert captured["args"] == ["ffmpeg", "-version"]
    assert version == banner.splitlines()[0].strip()


def test_has_encoder_argv_and_exact_token_match(monkeypatch):
    captured: dict[str, object] = {}
    # Modeled on real `ffmpeg -hide_banner -encoders` output: legend/rule
    # rows plus two encoders whose names both contain "h264" as a substring
    # (libx264, h264_nvenc) but neither of which IS "h264".
    stdout = (
        "Encoders:\n"
        " V..... = Video\n"
        " A..... = Audio\n"
        " ------\n"
        " V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)\n"
        " V....D h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)\n"
        " A....D aac                  AAC (Advanced Audio Coding)\n"
    )

    def fake_run(args, capture_output, text, check, cwd=None):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert ff.has_encoder("libx264") is True
    assert ff.has_encoder("aac") is True
    # "h264" is never a real encoder name here -- only libx264/h264_nvenc
    # are. A substring check would wrongly return True and risk selecting
    # NVENC, which is the constraint this function has to hold the line on.
    assert ff.has_encoder("h264") is False
    assert captured["args"] == ["ffmpeg", "-hide_banner", "-encoders"]


def test_measure_loudness_builds_the_expected_ebur128_argv(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    stderr = (
        "[Parsed_ebur128_0 @ 0000] Summary:\n"
        "  Integrated loudness:\n"
        "    I:         -16.0 LUFS\n"
        "  Loudness range:\n"
        "    LRA:         3.0 LU\n"
        "  True peak:\n"
        "    Peak:       -2.0 dBFS\n"
    )

    def fake_run(args, capture_output, text, check, cwd=None):
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, "", stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    target = tmp_path / "mix.wav"
    result = ff.measure_loudness(target, tmp_path / "run.log")
    assert captured["args"] == [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(target),
        "-filter_complex", "ebur128=peak=true", "-f", "null", "-",
    ]
    assert result["input_i"] == pytest.approx(-16.0)
