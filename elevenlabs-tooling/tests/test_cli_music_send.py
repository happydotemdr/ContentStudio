import json
from pathlib import Path

import pytest

from elevenlabs_tooling.cli import EXIT_NO_API_KEY, EXIT_PASS, EXIT_SEND_FAILED, EXIT_USAGE, main


@pytest.fixture
def payload_path(tmp_path: Path) -> Path:
    path = tmp_path / "composition_plan.json"
    path.write_text(json.dumps({"model_id": "music_v2", "composition_plan": {"chunks": []}}), encoding="utf-8")
    return path


def test_music_send_writes_response_body_on_success(tmp_path, payload_path, monkeypatch):
    output_path = tmp_path / "bed.wav"

    class FakeResult:
        ok = True
        status_code = 200
        content_type = "audio/wav"
        body = b"fake-bed-bytes"
        error_message = None

    monkeypatch.setattr("elevenlabs_tooling.cli.client_send", lambda *a, **k: FakeResult())
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    exit_code = main([
        "music", "send",
        "--payload", str(payload_path),
        "--url", "https://api.elevenlabs.io/v1/music/compose",
        "--output", str(output_path),
    ])

    assert exit_code == EXIT_PASS
    assert output_path.read_bytes() == b"fake-bed-bytes"


def test_music_send_does_not_call_the_tts_validator(tmp_path, payload_path, monkeypatch):
    """A composition-plan payload has no voice_id/text/model_id-for-TTS shape --
    cmd_music_send must never call validate(), which would reject it."""
    output_path = tmp_path / "bed.wav"

    def fail_if_called(*args, **kwargs):
        raise AssertionError("validate() must not be called by cmd_music_send")

    monkeypatch.setattr("elevenlabs_tooling.cli.validate", fail_if_called)

    class FakeResult:
        ok = True
        status_code = 200
        content_type = "audio/wav"
        body = b"fake-bed-bytes"
        error_message = None

    monkeypatch.setattr("elevenlabs_tooling.cli.client_send", lambda *a, **k: FakeResult())
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    exit_code = main([
        "music", "send",
        "--payload", str(payload_path),
        "--url", "https://api.elevenlabs.io/v1/music/compose",
        "--output", str(output_path),
    ])
    assert exit_code == EXIT_PASS


def test_music_send_returns_no_api_key_exit_code_when_unset(tmp_path, payload_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    exit_code = main([
        "music", "send",
        "--payload", str(payload_path),
        "--url", "https://api.elevenlabs.io/v1/music/compose",
        "--output", str(tmp_path / "bed.wav"),
    ])
    assert exit_code == EXIT_NO_API_KEY


def test_music_send_refuses_to_overwrite_without_force(tmp_path, payload_path, monkeypatch):
    output_path = tmp_path / "bed.wav"
    output_path.write_bytes(b"existing")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    exit_code = main([
        "music", "send",
        "--payload", str(payload_path),
        "--url", "https://api.elevenlabs.io/v1/music/compose",
        "--output", str(output_path),
    ])
    assert exit_code == EXIT_USAGE
    assert output_path.read_bytes() == b"existing"
