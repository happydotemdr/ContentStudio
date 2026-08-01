from pathlib import Path

import pytest

from pipeline_app import discovery_notify


@pytest.fixture(autouse=True)
def _clean_credential_env(monkeypatch):
    # Every test starts with no ambient credential, matching the "tests never
    # depend on the developer's real environment" constraint.
    monkeypatch.delenv(discovery_notify.KEY_ENV_VAR, raising=False)


def test_api_key_reads_env_var_first(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "env-key-123")
    assert discovery_notify.api_key() == "env-key-123"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    key_file = tmp_path / "resend_api_key.txt"
    key_file.write_text("file-key-456\n", encoding="utf-8")
    monkeypatch.setattr(discovery_notify, "KEY_FILE", key_file)
    assert discovery_notify.api_key() == "file-key-456"


def test_api_key_returns_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.setattr(discovery_notify, "KEY_FILE", tmp_path / "missing.txt")
    assert discovery_notify.api_key() is None


def test_send_email_returns_false_without_key(monkeypatch, tmp_path):
    monkeypatch.setattr(discovery_notify, "KEY_FILE", tmp_path / "missing.txt")
    calls = []
    monkeypatch.setattr(discovery_notify.requests, "post", lambda *a, **k: calls.append((a, k)))
    assert discovery_notify.send_email("subject", "body") is False
    assert calls == []  # no request attempted at all


def test_send_email_posts_expected_payload(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")
    captured = {}

    class FakeResponse:
        status_code = 200
        def raise_for_status(self):
            pass

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(discovery_notify.requests, "post", fake_post)
    result = discovery_notify.send_email("Test Subject", "Test body text")

    assert result is True
    assert captured["url"] == discovery_notify.RESEND_API_URL
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["to"] == [discovery_notify.RECIPIENT]
    assert captured["json"]["from"] == discovery_notify.SENDER
    assert captured["json"]["subject"] == "Test Subject"
    assert captured["json"]["text"] == "Test body text"
    assert captured["timeout"] == 15


def test_send_email_catches_request_exception(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")

    def raising_post(*a, **k):
        raise discovery_notify.requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(discovery_notify.requests, "post", raising_post)
    assert discovery_notify.send_email("subject", "body") is False


def test_send_email_catches_timeout(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")

    def timing_out_post(*a, **k):
        raise discovery_notify.requests.exceptions.Timeout("too slow")

    monkeypatch.setattr(discovery_notify.requests, "post", timing_out_post)
    assert discovery_notify.send_email("subject", "body") is False


def test_send_email_catches_non_2xx_response(monkeypatch):
    monkeypatch.setenv(discovery_notify.KEY_ENV_VAR, "test-key")

    class FailingResponse:
        status_code = 403
        def raise_for_status(self):
            raise discovery_notify.requests.exceptions.HTTPError("403 forbidden")

    monkeypatch.setattr(discovery_notify.requests, "post", lambda *a, **k: FailingResponse())
    assert discovery_notify.send_email("subject", "body") is False
