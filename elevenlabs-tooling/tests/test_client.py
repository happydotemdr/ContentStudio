from unittest.mock import MagicMock, patch

import requests

from elevenlabs_tooling.client import DEFAULT_TIMEOUT_S, SendResult, send


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
