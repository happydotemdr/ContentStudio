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
             "color_space": "bt709"},
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
    assert result.has_video and result.has_audio


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
