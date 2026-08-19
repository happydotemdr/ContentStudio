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
from elevenlabs_tooling.client import SendResult

MUSIC_URL = "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192"


def _write_payload(tmp_path, data):
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _valid_payload_path(tmp_path):
    return _write_payload(tmp_path, {"prompt": "a calm ambient bed", "model_id": "music_v1"})


def _logged_events():
    files = list(log_module.LOG_DIR.glob("tooling-*.log"))
    assert files, "expected at least one log file to be written"
    return [
        json.loads(line)["event"]
        for line in files[0].read_text(encoding="utf-8").strip().splitlines()
    ]


@patch("elevenlabs_tooling.cli.client_send")
def test_send_success_writes_output_and_returns_pass(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"FAKE_AUDIO", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_PASS
    assert output_path.read_bytes() == b"FAKE_AUDIO"
    mock_send.assert_called_once()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_success_writes_attempt_and_success_log_entries(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"FAKE_AUDIO", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path)])

    events = _logged_events()
    assert "send.attempt" in events
    assert "send.success" in events


@patch("elevenlabs_tooling.cli.client_send")
def test_send_blocked_by_validation_never_calls_client(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _write_payload(tmp_path, {"prompt": "x"})  # missing model_id -> E4
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_FINDINGS
    mock_send.assert_not_called()
    assert not output_path.exists()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_missing_api_key_returns_no_api_key(mock_send, tmp_path, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_NO_API_KEY
    assert not output_path.exists()
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_missing_api_key_reported_after_validation_findings(mock_send, tmp_path, monkeypatch, capsys):
    # A payload with BOTH a validation problem and no API key must report
    # the validation problem (EXIT_FINDINGS), not hide it behind the key
    # check -- and must not touch the network either way.
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    payload_path = _write_payload(tmp_path, {"prompt": "x"})  # missing model_id -> E4
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_FINDINGS
    mock_send.assert_not_called()
    captured = capsys.readouterr()
    assert "E4: model_id must be present and non-empty" in captured.err


@patch("elevenlabs_tooling.cli.client_send")
def test_send_refuses_to_overwrite_existing_output_without_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"
    output_path.write_bytes(b"EXISTING")

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_USAGE
    assert output_path.read_bytes() == b"EXISTING"
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_overwrites_existing_output_with_force(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"NEW_AUDIO", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"
    output_path.write_bytes(b"OLD_AUDIO")

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
        "--force",
    ])

    assert code == EXIT_PASS
    assert output_path.read_bytes() == b"NEW_AUDIO"


@patch("elevenlabs_tooling.cli.client_send")
def test_send_output_parent_directory_missing(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "does_not_exist" / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_USAGE
    mock_send.assert_not_called()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_bare_filename_output_with_no_directory_component_works(mock_send, tmp_path, monkeypatch):
    # --output out.mp3 (no directory) must resolve its parent to the cwd,
    # not crash on an empty parent.
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.chdir(tmp_path)
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)

    code = main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", "out.mp3"])

    assert code == EXIT_PASS
    assert (tmp_path / "out.mp3").read_bytes() == b"X"


@patch("elevenlabs_tooling.cli.client_send")
def test_send_non_2xx_failure_writes_nothing(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=False, status_code=422, content_type=None, body=None, error_message="invalid voice_id"
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_SEND_FAILED
    assert not output_path.exists()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_failure_writes_send_failed_log_entry(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=False, status_code=422, content_type=None, body=None, error_message="invalid voice_id"
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path)])

    assert "send.failed" in _logged_events()


@patch("elevenlabs_tooling.cli.client_send")
def test_send_unexpected_content_type_quarantines_body(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=False,
        status_code=200,
        content_type="application/json",
        body=b'{"unexpected": true}',
        error_message="expected an audio/* response, got Content-Type 'application/json'",
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    code = main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
    ])

    assert code == EXIT_SEND_FAILED
    assert not output_path.exists()
    quarantine_path = tmp_path / "out.mp3.unexpected"
    assert quarantine_path.read_bytes() == b'{"unexpected": true}'


@patch("elevenlabs_tooling.cli.client_send")
def test_send_passes_cli_timeout_to_client(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
        "--timeout", "12.5",
    ])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 12.5


@patch("elevenlabs_tooling.cli.client_send")
def test_send_uses_env_timeout_when_no_cli_flag(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ELEVENLABS_TOOLING_TIMEOUT_S", "77")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path)])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 77.0


@patch("elevenlabs_tooling.cli.client_send")
def test_send_falls_back_to_default_on_invalid_env_timeout(mock_send, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ELEVENLABS_TOOLING_TIMEOUT_S", "not-a-number")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main(["send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path)])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 300.0
    captured = capsys.readouterr()
    assert "ELEVENLABS_TOOLING_TIMEOUT_S" in captured.err
    assert "300" in captured.err  # Ensure the timeout value is rendered correctly


@patch("elevenlabs_tooling.cli.client_send")
def test_send_falls_back_to_default_on_non_positive_cli_timeout(mock_send, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
        "--timeout", "-5",
    ])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 300.0
    captured = capsys.readouterr()
    assert "--timeout" in captured.err
    assert "300" in captured.err  # Ensure the timeout value is rendered correctly


@patch("elevenlabs_tooling.cli.client_send")
def test_send_cli_timeout_overrides_env_timeout(mock_send, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ELEVENLABS_TOOLING_TIMEOUT_S", "77")
    mock_send.return_value = SendResult(
        ok=True, status_code=200, content_type="audio/mpeg", body=b"X", error_message=None
    )
    payload_path = _valid_payload_path(tmp_path)
    output_path = tmp_path / "out.mp3"

    main([
        "send", "--payload", str(payload_path), "--url", MUSIC_URL, "--output", str(output_path),
        "--timeout", "12.5",
    ])

    _, kwargs = mock_send.call_args
    assert kwargs["timeout"] == 12.5
