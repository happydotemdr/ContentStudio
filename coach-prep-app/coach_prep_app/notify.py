# coach-prep-app/coach_prep_app/notify.py
"""Emails a coach-prep notification. Own copy of discovery_notify.py's
Resend HTTP pattern -- coach-prep-app does not depend on pipeline-app."""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import requests

RESEND_API_URL = "https://api.resend.com/emails"
KEY_ENV_VAR = "RESEND_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "resend_api_key.txt"
RECIPIENT = "brian@happydotemdr.com"  # see plan Task 25: confirm whether Ryan should receive these directly
SENDER = os.environ.get("RESEND_FROM_ADDRESS", "onboarding@resend.dev")
REQUEST_TIMEOUT_S = 15


def api_key() -> str | None:
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


def send_email(subject: str, text: str, recipient: str = RECIPIENT) -> bool:
    key = api_key()
    if not key:
        print("notify: no RESEND_API_KEY configured, skipping send", file=sys.stderr)
        return False
    payload = {"from": SENDER, "to": [recipient], "subject": subject, "text": text}
    try:
        response = requests.post(
            RESEND_API_URL, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        print(f"notify: send_email failed: {exc}", file=sys.stderr)
        return False


def render_review_email(client_display_name: str, meeting_date: dt.date, drive_file_id: str) -> tuple[str, str]:
    subject = f"Review: prep doc for {client_display_name} — meeting {meeting_date.isoformat()}"
    link = f"https://docs.google.com/document/d/{drive_file_id}/edit"
    text = (
        f"Draft coach-prep doc for {client_display_name}'s upcoming session "
        f"({meeting_date.isoformat()}) is ready for review:\n\n{link}\n\n"
        f"Review it, then move it into {client_display_name}'s own Drive folder yourself when ready."
    )
    return subject, text
