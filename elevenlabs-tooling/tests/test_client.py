from unittest.mock import MagicMock, patch
import base64
import json

import requests

from elevenlabs_tooling.client import DEFAULT_TIMEOUT_S, SendResult, send, TimestampsResult, send_with_timestamps


def _mock_response(status_code=200, content_type="audio/mpeg", content=b"FAKE_MP3_BYTES", raise_exc=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"Content-Type": content_type}
    response.content = content
    response.text = content.decode("utf-8", errors="replace")
    if raise_exc:
        response.raise_for_status.side_effect = raise_exc
    else:
        response.raise_for_status.return_value = None
    return response


@patch("elevenlabs_tooling.client.requests.post")
def test_send_success_returns_ok_with_body(mock_post):
    mock_post.return_value = _mock_response()
    result = send("https://api.elevenlabs.io/v1/music", b'{"prompt": "x"}', "fake-key")
    assert result.ok is True
    assert result.status_code == 200
    assert result.content_type == "audio/mpeg"
    assert result.body == b"FAKE_MP3_BYTES"
    assert result.error_message is None


@patch("elevenlabs_tooling.client.requests.post")
def test_send_sends_correct_headers_and_raw_body(mock_post):
    mock_post.return_value = _mock_response()
    payload_bytes = b'{"prompt": "exact bytes"}'
    send("https://api.elevenlabs.io/v1/music", payload_bytes, "my-secret-key", timeout=45.0)
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["xi-api-key"] == "my-secret-key"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["data"] == payload_bytes
    assert kwargs["timeout"] == 45.0


@patch("elevenlabs_tooling.client.requests.post")
def test_send_unexpected_content_type_returns_not_ok_but_keeps_body(mock_post):
    mock_post.return_value = _mock_response(content_type="application/json", content=b'{"weird": true}')
    result = send("https://api.elevenlabs.io/v1/music", b"{}", "fake-key")
    assert result.ok is False
    assert result.body == b'{"weird": true}'
    assert "audio/*" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_non_2xx_returns_not_ok_with_no_body(mock_post):
    error_response = _mock_response(status_code=422, content_type="application/json")
    error_response.text = '{"detail": "invalid voice_id"}'
    http_error = requests.exceptions.HTTPError("422 Client Error")
    http_error.response = error_response
    mock_post.return_value = _mock_response(status_code=422, raise_exc=http_error)
    result = send("https://api.elevenlabs.io/v1/music", b"{}", "fake-key")
    assert result.ok is False
    assert result.status_code == 422
    assert result.body is None
    assert "invalid voice_id" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_network_error_returns_not_ok_with_no_status(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("connection refused")
    result = send("https://api.elevenlabs.io/v1/music", b"{}", "fake-key")
    assert result.ok is False
    assert result.status_code is None
    assert result.body is None
    assert "connection refused" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_timeout_returns_not_ok(mock_post):
    mock_post.side_effect = requests.exceptions.Timeout("timed out")
    result = send("https://api.elevenlabs.io/v1/music", b"{}", "fake-key")
    assert result.ok is False
    assert "timed out" in result.error_message


def test_default_timeout_is_300_seconds():
    assert DEFAULT_TIMEOUT_S == 300.0


def _mock_json_response(status_code=200, content_type="application/json", payload=None, raise_exc=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"Content-Type": content_type}
    response.json.return_value = payload if payload is not None else {}
    response.text = json.dumps(payload if payload is not None else {})
    response.content = response.text.encode("utf-8")
    if raise_exc:
        response.raise_for_status.side_effect = raise_exc
    else:
        response.raise_for_status.return_value = None
    return response


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_success_decodes_audio_and_alignment(mock_post):
    fake_alignment = {
        "characters": ["H", "i"],
        "character_start_times_seconds": [0.0, 0.1],
        "character_end_times_seconds": [0.1, 0.2],
    }
    mock_post.return_value = _mock_json_response(payload={
        "audio_base64": base64.b64encode(b"FAKE_AUDIO_BYTES").decode("ascii"),
        "alignment": fake_alignment,
        "normalized_alignment": fake_alignment,
    })
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b'{"text": "Hi"}', "fake-key",
    )
    assert result.ok is True
    assert result.status_code == 200
    assert result.audio_bytes == b"FAKE_AUDIO_BYTES"
    assert result.alignment == fake_alignment
    assert result.error_message is None


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_sends_correct_headers_and_raw_body(mock_post):
    mock_post.return_value = _mock_json_response(payload={
        "audio_base64": base64.b64encode(b"X").decode("ascii"),
        "alignment": {"characters": []},
    })
    payload_bytes = b'{"text": "exact bytes"}'
    send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        payload_bytes, "my-secret-key", timeout=45.0,
    )
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["xi-api-key"] == "my-secret-key"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["data"] == payload_bytes
    assert kwargs["timeout"] == 45.0


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_missing_alignment_field_returns_not_ok(mock_post):
    mock_post.return_value = _mock_json_response(payload={
        "audio_base64": base64.b64encode(b"X").decode("ascii"),
    })
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert "alignment" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_wrong_content_type_returns_not_ok(mock_post):
    mock_post.return_value = _mock_json_response(content_type="audio/mpeg")
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert "application/json" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_non_2xx_returns_not_ok(mock_post):
    error_response = _mock_json_response(status_code=422)
    error_response.text = '{"detail": "invalid voice_id"}'
    http_error = requests.exceptions.HTTPError("422 Client Error")
    http_error.response = error_response
    mock_post.return_value = _mock_json_response(status_code=422, raise_exc=http_error)
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert result.status_code == 422
    assert "invalid voice_id" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_network_error_returns_not_ok(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("connection refused")
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert result.status_code is None
    assert "connection refused" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_malformed_json_body_returns_not_ok(mock_post):
    response = _mock_json_response()
    response.json.side_effect = ValueError("Expecting value: line 1 column 1")
    mock_post.return_value = response
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert result.audio_bytes is None
    assert "did not parse" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_non_dict_json_body_returns_not_ok(mock_post):
    mock_post.return_value = _mock_json_response(payload=["unexpected", "array"])
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert "must be an object" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_invalid_base64_returns_not_ok(mock_post):
    mock_post.return_value = _mock_json_response(payload={
        "audio_base64": "not valid base64!!!",
        "alignment": {"characters": []},
    })
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert "did not decode as base64" in result.error_message


@patch("elevenlabs_tooling.client.requests.post")
def test_send_with_timestamps_failure_preserves_raw_body_for_quarantine(mock_post):
    mock_post.return_value = _mock_json_response(payload={"unexpected": "shape"})
    result = send_with_timestamps(
        "https://api.elevenlabs.io/v1/text-to-speech/VOICE/with-timestamps",
        b"{}", "fake-key",
    )
    assert result.ok is False
    assert result.raw_body == b'{"unexpected": "shape"}'
