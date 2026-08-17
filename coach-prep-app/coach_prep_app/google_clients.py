"""coach-prep-app's own OAuth client and token -- entirely separate from
doc-ingest-app's credentials (both the Drive/Docs/Sheets pair and the
calendar-only pair added in doc-ingest-app Task 6). One consent grants all
three scopes below in a single token, since a Google OAuth token carries a
scope SET, not one scope per API. Mirrors doc_ingest/drive_client.py's
cron-safe shape: never falls through to the interactive flow when no cached
token exists."""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
]


def _app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_credentials(token_path: Path, client_secret_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _build_service(service_name: str, version: str):
    from googleapiclient.discovery import build

    app_root = _app_root()
    token_path = app_root / "token.json"
    if not token_path.exists():
        raise RuntimeError(
            "coach-prep-app has no cached Google token -- run the one-time "
            "interactive consent documented in SETUP.md before the cron can run"
        )
    creds = get_credentials(token_path, app_root / "client_secret.json")
    return build(service_name, version, credentials=creds)


def build_calendar_service(cfg=None):
    return _build_service("calendar", "v3")


def build_gmail_service(cfg=None):
    return _build_service("gmail", "v1")


def build_drive_service(cfg=None):
    return _build_service("drive", "v3")
