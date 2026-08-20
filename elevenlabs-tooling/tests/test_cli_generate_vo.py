import json
from unittest.mock import patch

import elevenlabs_tooling.log as log_module
from elevenlabs_tooling.cli import (
    EXIT_FINDINGS,
    EXIT_NO_API_KEY,
    EXIT_PASS,
    EXIT_SEND_FAILED,
    EXIT_USAGE,
    main,
)
from elevenlabs_tooling.client import TimestampsResult

TTS_URL = (
    "https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA/with-timestamps"
    "?output_format=mp3_44100_192"
)

FAKE_ALIGNMENT = {
    "characters": ["H", "i"],
    "character_start_times_seconds": [0.0, 0.1],
    "character_end_times_seconds": [0.1, 0.2],
}


def _write_payload(tmp_path, data):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _valid_payload_path(tmp_path):
    return _write_payload(tmp_path, {"text": "Hello world.", "model_id": "eleven_multilingual_v2"})


def _logged_events():
    files = list(log_module.LOG_DIR.glob("tooling-*.log"))
    assert files, "expected at least one log file to be written"
    return [
        json.loads(line)["event"]
        for line in files[0].read_text(encoding="utf-8").strip().splitlines()
    ]


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_success_writes_audio_and_alignment(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=True, status_code=200, audio_bytes=b"FAKE_AUDIO", alignment=FAKE_ALIGNMENT,
        error_message=None,
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_PASS
    assert audio_output.read_bytes() == b"FAKE_AUDIO"
    assert json.loads(alignment_output.read_text(encoding="utf-8")) == FAKE_ALIGNMENT
    mock_send.assert_called_once()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_success_writes_attempt_and_success_log_entries(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=True, status_code=200, audio_bytes=b"X", alignment=FAKE_ALIGNMENT, error_message=None,
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    events = _logged_events()
    assert "generate_vo.attempt" in events
    assert "generate_vo.success" in events


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_blocked_by_validation_never_calls_client(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _write_payload(tmp_path, {"text": "Hi"})  # missing model_id -> E4
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_FINDINGS
    mock_send.assert_not_called()
    assert not audio_output.exists()
    assert not alignment_output.exists()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_missing_api_key_returns_no_api_key(mock_send, tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_NO_API_KEY
    assert not audio_output.exists()
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_refuses_to_overwrite_audio_output_without_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    audio_output.write_bytes(b"EXISTING")
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_USAGE
    assert audio_output.read_bytes() == b"EXISTING"
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_refuses_to_overwrite_alignment_output_without_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"
    alignment_output.write_text('{"existing": true}', encoding="utf-8")

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_USAGE
    assert alignment_output.read_text(encoding="utf-8") == '{"existing": true}'
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_overwrites_both_outputs_with_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=True, status_code=200, audio_bytes=b"NEW_AUDIO", alignment=FAKE_ALIGNMENT,
        error_message=None,
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    audio_output.write_bytes(b"OLD_AUDIO")
    alignment_output = tmp_path / "vo_alignment.json"
    alignment_output.write_text('{"old": true}', encoding="utf-8")

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
        "--force",
    ])

    assert code == EXIT_PASS
    assert audio_output.read_bytes() == b"NEW_AUDIO"
    assert json.loads(alignment_output.read_text(encoding="utf-8")) == FAKE_ALIGNMENT


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_send_failure_writes_nothing(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=False, status_code=422, audio_bytes=None, alignment=None,
        error_message="invalid voice_id",
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_SEND_FAILED
    assert not audio_output.exists()
    assert not alignment_output.exists()


@patch("elevenlabs_tooling.cli.client_send_with_timestamps")
def test_generate_vo_failure_with_a_body_quarantines_it(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = TimestampsResult(
        ok=False, status_code=200, audio_bytes=None, alignment=None,
        error_message="response JSON is missing 'audio_base64' or 'alignment'",
        raw_body=b'{"unexpected": true}',
    )
    payload_path = _valid_payload_path(tmp_path)
    audio_output = tmp_path / "vo.mp3"
    alignment_output = tmp_path / "vo_alignment.json"

    code = main([
        "generate-vo", "--payload", str(payload_path), "--url", TTS_URL,
        "--audio-output", str(audio_output), "--alignment-output", str(alignment_output),
    ])

    assert code == EXIT_SEND_FAILED
    assert not audio_output.exists()
    quarantine_path = tmp_path / "vo.mp3.unexpected"
    assert quarantine_path.read_bytes() == b'{"unexpected": true}'
