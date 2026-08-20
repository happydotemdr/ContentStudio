import json
import sys
from pathlib import Path

import pytest

from stitcher.naming import Workspace
from stitcher.vo_alignment import Segment

from native_pipeline import orchestrate


class FakeCompletedProcess:
    def __init__(self):
        self.returncode = 0


def test_run_vo_stage_calls_generate_vo_and_derives_segments(tmp_path, monkeypatch):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({"text": "beat one. beat two."}), encoding="utf-8")

    ws = Workspace(root=tmp_path / "renders", slug="test-slug", mode="final")
    ws.ensure_dirs()

    captured_cmd = {}

    def fake_run(cmd, check, cwd=None):
        captured_cmd["cmd"] = cmd
        captured_cmd["cwd"] = cwd
        # Simulate generate-vo writing its two output files.
        alignment_output = Path(cmd[cmd.index("--alignment-output") + 1])
        alignment_output.write_text(json.dumps({"characters": [], "character_start_times_seconds": [],
                                                  "character_end_times_seconds": []}), encoding="utf-8")
        audio_output = Path(cmd[cmd.index("--audio-output") + 1])
        audio_output.write_bytes(b"fake-audio")
        return FakeCompletedProcess()

    monkeypatch.setattr("native_pipeline.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(
        "native_pipeline.orchestrate.derive_segments",
        lambda text, alignment, names=None: [Segment(name="beat1", at=0.0, duration=5.0)],
    )
    monkeypatch.setattr("native_pipeline.orchestrate.flag_outliers", lambda *a, **k: [])

    log_path = tmp_path / "log.txt"
    audio_output, segments = orchestrate.run_vo_stage(ws, payload_path, "https://fake-url", log_path)

    assert captured_cmd["cmd"][:4] == [sys.executable, "-m", "elevenlabs_tooling", "generate-vo"]
    assert "--force" in captured_cmd["cmd"]
    assert captured_cmd["cwd"] == orchestrate._ELEVENLABS_TOOLING_DIR
    assert audio_output.read_bytes() == b"fake-audio"
    assert segments[0].name == "beat1"


def test_run_vo_stage_appends_flag_lines_to_log_when_flagging_finds_something(tmp_path, monkeypatch):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps({"text": "beat one."}), encoding="utf-8")
    ws = Workspace(root=tmp_path / "renders", slug="test-slug", mode="final")
    ws.ensure_dirs()

    def fake_run(cmd, check, cwd=None):
        Path(cmd[cmd.index("--alignment-output") + 1]).write_text(json.dumps({
            "characters": [], "character_start_times_seconds": [], "character_end_times_seconds": []}),
            encoding="utf-8")
        Path(cmd[cmd.index("--audio-output") + 1]).write_bytes(b"fake-audio")
        return FakeCompletedProcess()

    monkeypatch.setattr("native_pipeline.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr(
        "native_pipeline.orchestrate.derive_segments",
        lambda text, alignment, names=None: [Segment(name="beat1", at=0.0, duration=5.0)],
    )
    monkeypatch.setattr(
        "native_pipeline.orchestrate.flag_outliers",
        lambda path, spans, log_path: [{"label": "beat1", "lufs": -25.0, "median_lufs": -14.0, "deviation_lu": 11.0}],
    )

    log_path = tmp_path / "log.txt"
    log_path.write_text("", encoding="utf-8")
    orchestrate.run_vo_stage(ws, payload_path, "https://fake-url", log_path)

    assert "FLAG:" in log_path.read_text(encoding="utf-8")
    assert "beat1" in log_path.read_text(encoding="utf-8")


def test_run_music_stage_writes_plan_and_calls_music_send(tmp_path, monkeypatch):
    ws = Workspace(root=tmp_path / "renders", slug="test-slug", mode="final")
    ws.ensure_dirs()
    bed_arc_path = tmp_path / "bed_arc.json"
    bed_arc_path.write_text(json.dumps([
        {"label": "hook", "start_s": 0.0, "end_s": 5.0, "density": "full", "style_notes": ""},
    ]), encoding="utf-8")
    segments = [Segment(name="beat1", at=0.0, duration=5.0)]

    captured_cmd = {}

    def fake_run(cmd, check, cwd=None):
        captured_cmd["cmd"] = cmd
        captured_cmd["cwd"] = cwd
        output = Path(cmd[cmd.index("--output") + 1])
        output.write_bytes(b"fake-bed")
        return FakeCompletedProcess()

    monkeypatch.setattr("native_pipeline.orchestrate.subprocess.run", fake_run)
    monkeypatch.setattr("native_pipeline.orchestrate.flag_outliers", lambda *a, **k: [])

    log_path = tmp_path / "log.txt"
    log_path.write_text("", encoding="utf-8")
    bed_path = orchestrate.run_music_stage(segments, bed_arc_path, ws, "https://fake-music-url", log_path)

    assert captured_cmd["cmd"][:4] == [sys.executable, "-m", "elevenlabs_tooling", "music"]
    assert captured_cmd["cmd"][4] == "send"
    assert captured_cmd["cwd"] == orchestrate._ELEVENLABS_TOOLING_DIR
    assert bed_path.read_bytes() == b"fake-bed"


def test_run_render_stage_invokes_stitcher_render(tmp_path, monkeypatch):
    captured_cmd = {}

    def fake_run(cmd, check, cwd=None):
        captured_cmd["cmd"] = cmd
        captured_cmd["cwd"] = cwd
        return FakeCompletedProcess()

    monkeypatch.setattr("native_pipeline.orchestrate.subprocess.run", fake_run)

    orchestrate.run_render_stage("test-slug", tmp_path)

    assert captured_cmd["cmd"] == [
        sys.executable, "-m", "stitcher", "render", "test-slug",
        "--root", str(tmp_path), "--mode", "final", "--force",
    ]
    assert captured_cmd["cwd"] == orchestrate._STITCHER_DIR
