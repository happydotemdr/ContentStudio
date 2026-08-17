# coach-prep-app/tests/test_notify.py
from __future__ import annotations

import datetime as dt

import pytest

from coach_prep_app import notify


def test_api_key_reads_env_var_first(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "from-env")
    assert notify.api_key() == "from-env"


def test_api_key_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr(notify, "KEY_FILE", notify.Path("/nonexistent/resend_api_key.txt"))
    assert notify.api_key() is None


def test_send_email_returns_false_with_no_key_configured(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr(notify, "KEY_FILE", notify.Path("/nonexistent/resend_api_key.txt"))
    assert notify.send_email("subject", "body") is False


@pytest.mark.allow_network  # this test intentionally exercises the real requests.post call path, mocked below
def test_send_email_posts_to_resend_with_the_configured_key(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def _fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(notify.requests, "post", _fake_post)
    result = notify.send_email("Test subject", "Test body")
    assert result is True
    assert captured["url"] == notify.RESEND_API_URL
    assert captured["json"]["subject"] == "Test subject"
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_render_review_email_includes_the_drive_link_and_client_name():
    subject, text = notify.render_review_email("Sean", dt.date(2026, 8, 20), "drive-file-123")
    assert "Sean" in subject
    assert "2026-08-20" in subject
    assert "drive-file-123" in text
    assert "review" in text.lower()
