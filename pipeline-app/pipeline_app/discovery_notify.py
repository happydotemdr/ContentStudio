"""Post-run email notification for the discovery pipeline. Deliberately has
no dependency on discovery_engine.py -- it reads only what a finished run
already persisted (DB rows via db.py, files via discovery_paths.py /
artifacts.py) and is invoked by run_discovery_cron.py after run_discovery()
returns. See docs/superpowers/specs/2026-08-01-discovery-email-summary-design.md.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

RESEND_API_URL = "https://api.resend.com/emails"
KEY_ENV_VAR = "RESEND_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "resend_api_key.txt"

RECIPIENT = "brian@happydotemdr.com"
# Resend's shared sandbox sender -- works with no domain verification. Once a
# real sending domain is verified in the Resend dashboard, set
# RESEND_FROM_ADDRESS in the environment to switch senders with no code change.
SENDER = os.environ.get("RESEND_FROM_ADDRESS", "onboarding@resend.dev")

REQUEST_TIMEOUT_S = 15


def api_key() -> str | None:
    """The Resend API key, or None if not configured. Same lookup order as
    discovery_youtube_api.api_key(): env var first, then a gitignored file."""
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


def send_email(subject: str, text: str) -> bool:
    """POST one email via Resend's HTTP API. Never raises -- returns False on
    any failure (no key configured, network error, non-2xx response) so a
    caller can log and move on rather than letting a notification failure
    propagate as an exception."""
    key = api_key()
    if not key:
        print("discovery_notify: no RESEND_API_KEY configured, skipping send", file=sys.stderr)
        return False
    try:
        response = requests.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"from": SENDER, "to": [RECIPIENT], "subject": subject, "text": text},
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        print(f"discovery_notify: send_email failed: {exc}", file=sys.stderr)
        return False
