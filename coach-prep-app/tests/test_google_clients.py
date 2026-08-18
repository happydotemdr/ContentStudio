# coach-prep-app/tests/test_google_clients.py
from __future__ import annotations

import pytest

from coach_prep_app import config, google_clients


def test_build_calendar_service_raises_clearly_with_no_cached_token(tmp_path):
    cfg = config.Config()
    # google_clients resolves its own app_root from __file__, not from cfg --
    # simulate "no token" by pointing at an isolated app_root via monkeypatch
    # of the module-level app_root computation, exercised directly here:
    import coach_prep_app.google_clients as gc
    original = gc._app_root
    gc._app_root = lambda: tmp_path
    try:
        with pytest.raises(RuntimeError, match="no cached Google token"):
            gc.build_calendar_service(cfg)
    finally:
        gc._app_root = original


def test_scopes_include_calendar_gmail_and_drive_file():
    assert "https://www.googleapis.com/auth/calendar.readonly" in google_clients.SCOPES
    assert "https://www.googleapis.com/auth/gmail.readonly" in google_clients.SCOPES
    assert "https://www.googleapis.com/auth/drive.file" in google_clients.SCOPES
