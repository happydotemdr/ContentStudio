"""Calendar API access for doc-ingest-app's meeting-note classifier. Uses its
OWN credential pair (calendar_client_secret.json / calendar_token.json),
scoped to calendar.readonly only -- deliberately separate from
client_secret.json/token.json (Drive/Docs/Sheets), so adding this can never
invalidate the credential the running ingest cron already depends on.
Mirrors drive_client.py's shape; see that module and SETUP.md for the
one-time interactive consent this cron-unfriendly flow requires."""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


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


def build_default_service(cfg=None):
    from googleapiclient.discovery import build

    app_root = Path(__file__).resolve().parents[1]
    token_path = app_root / "calendar_token.json"
    if not token_path.exists():
        raise RuntimeError(
            "doc-ingest-app has no cached Calendar token -- run the one-time "
            "interactive consent documented in SETUP.md's Calendar section "
            "before the classifier can resolve meeting-note attendees"
        )
    creds = get_credentials(token_path, app_root / "calendar_client_secret.json")
    return build("calendar", "v3", credentials=creds)


def get_event_attendees(service, event_id: str, calendar_id: str) -> list[str]:
    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    return [a["email"] for a in event.get("attendees", []) if "email" in a]
