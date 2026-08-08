"""Post-run email notification for the discovery pipeline. Deliberately has
no dependency on discovery_engine.py -- it reads only what a finished run
already persisted (DB rows via db.py, files via discovery_digest.py) and is
invoked by run_discovery_cron.py after run_discovery() returns.

This module does NOT catch. tests/test_discovery_notify.py documents that
contract: the cron call site (run_discovery_cron.py:100) is the single catch
point, and notify() adding its own would be a second, redundant failure
boundary. The collaborators carry the burden instead -- comment_draft never
raises, and per-item parse failures are contained inside collect_new_items.

See docs/superpowers/specs/2026-08-08-morning-email-social-expansion-design.md.
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from pipeline_app import comment_draft
from pipeline_app import db as db_mod
from pipeline_app import discovery_digest
from pipeline_app import email_render

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


def send_email(subject: str, text: str, html: str | None = None) -> bool:
    """POST one email via Resend's HTTP API. Never raises -- returns False on
    any failure (no key configured, network error, non-2xx response) so a
    caller can log and move on rather than letting a notification failure
    propagate as an exception."""
    key = api_key()
    if not key:
        print("discovery_notify: no RESEND_API_KEY configured, skipping send", file=sys.stderr)
        return False
    payload = {"from": SENDER, "to": [RECIPIENT], "subject": subject, "text": text}
    if html:
        payload["html"] = html
    try:
        response = requests.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as exc:
        print(f"discovery_notify: send_email failed: {exc}", file=sys.stderr)
        return False


def build_summary(conn, repo_root: Path, run_row_id: int) -> dict:
    """The run's new items, flat, plus its status and errored handles.

    EVERY handle in the run is scanned, regardless of its recorded status or
    items_downloaded. Both gates this function used to apply are deliberately
    gone: discovery_engine.py:347 records error/0 for a handle whose
    process_handle raised AFTER some downloads succeeded, which is precisely
    the case the fetched_at watermark exists to self-correct. Keeping the gates
    and keeping the watermark's rationale are mutually exclusive.

    An errored handle with partial downloads therefore appears BOTH in `items`
    and in `errored`. That is intended: "this handle broke, and here are the
    three posts it got before it broke" beats either half alone.

    `items` is flat rather than pre-grouped -- select_spotlight needs the flat
    list, and email_render owns grouping so that adding a platform never
    requires a second place to be taught about it.
    """
    run_row = db_mod.get_run(conn, run_row_id)
    handle_results = db_mod.list_run_handle_results(conn, run_row_id)
    started_at = run_row["started_at"]

    items: list[dict] = []
    errored: list[str] = []
    for result in handle_results:
        handle_row = db_mod.get_handle(conn, result["handle_id"])
        label = handle_row["display_name"] or handle_row["handle"]

        if result["status"] == "error":
            errored.append(label)

        found = discovery_digest.collect_new_items(repo_root, handle_row, started_at)
        if len(found) != result["items_downloaded"]:
            print(f"discovery_notify: item count mismatch for {label}: "
                  f"db says {result['items_downloaded']}, found {len(found)} on disk",
                  file=sys.stderr)
        items.extend(found)

    has_issues = run_row["status"] != "completed" or bool(errored)
    return {
        "run_status": run_row["status"],
        "has_issues": has_issues,
        "items": items,
        "errored": errored,
    }


def notify(conn, repo_root: Path, run_row_id: int) -> bool:
    summary = build_summary(conn, repo_root, run_row_id)

    spotlight = discovery_digest.select_spotlight(summary["items"])
    # draft_comments never raises and returns [] on every failure path, so a
    # drafting problem costs three drafts, never the day's inventory.
    summary["spotlight"] = spotlight
    summary["drafts"] = comment_draft.draft_comments(spotlight) if spotlight else []

    run_row = db_mod.get_run(conn, run_row_id)
    timezone_name = db_mod.get_settings(conn)["timezone"]
    started_at = _dt.datetime.fromisoformat(run_row["started_at"])
    run_date = started_at.astimezone(ZoneInfo(timezone_name)).date().isoformat()

    rendered = email_render.render_email(summary, run_date)
    return send_email(rendered["subject"], rendered["text"], rendered["html"])
