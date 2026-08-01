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

from pipeline_app import db as db_mod
from pipeline_app import discovery_paths
from pipeline_app import artifacts

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


def _youtube_headlines_for_handle(repo_root, platform_handle: str, started_at: str) -> list[str]:
    directory = discovery_paths.handle_dir(repo_root, "youtube", platform_handle)
    if not directory.exists():
        return []
    headlines = []
    for path in sorted(directory.glob("*__*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = artifacts.parse_frontmatter(text)
        fetched_at = meta.get("fetched_at")
        if not fetched_at or fetched_at < started_at:
            continue
        first_line = next((line for line in body.splitlines() if line.strip()), "")
        title = first_line.lstrip("#").strip() if first_line.startswith("#") else None
        if title:
            headlines.append(title)
    return headlines


def build_summary(conn, repo_root: Path, run_row_id: int) -> dict:
    run_row = db_mod.get_run(conn, run_row_id)
    handle_results = db_mod.list_run_handle_results(conn, run_row_id)

    channels = []
    errored = []
    for result in handle_results:
        handle_row = db_mod.get_handle(conn, result["handle_id"])
        label = handle_row["display_name"] or handle_row["handle"]

        if result["status"] == "error":
            errored.append(label)
            continue

        if result["items_downloaded"] <= 0:
            continue

        if handle_row["platform"] == "youtube":
            headlines = _youtube_headlines_for_handle(repo_root, handle_row["handle"], run_row["started_at"])
            if len(headlines) != result["items_downloaded"]:
                print(
                    f"discovery_notify: headline count mismatch for {label}: "
                    f"db says {result['items_downloaded']}, found {len(headlines)} on disk",
                    file=sys.stderr,
                )
            channels.append({"name": label, "headlines": headlines, "count": len(headlines)})
        else:
            channels.append({"name": label, "headlines": [], "count": result["items_downloaded"]})

    has_issues = run_row["status"] != "completed" or bool(errored)
    return {
        "run_status": run_row["status"],
        "has_issues": has_issues,
        "channels": channels,
        "errored": errored,
    }
