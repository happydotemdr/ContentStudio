# coach-prep-app/coach_prep_app/bundle.py
"""Assembles the single-client input bundle for one generation run, and
persists it to generation_inputs BEFORE generation happens -- this row
exists regardless of what generation/gates/publish do afterward."""
from __future__ import annotations

import base64
import datetime as dt
import email.utils

from coach_prep_app import db


def find_last_meeting_email(gmail_service, client_email: str, now_utc: dt.datetime, staleness_days: int) -> dict:
    # Upper-bound the search relative to now_utc -- an unbounded `in:sent
    # to:` query has no defense against a future-dated or clock-skewed
    # message being trusted as "the last meeting email". `before:` is
    # exclusive, so add a day to include anything sent earlier today.
    before = (now_utc + dt.timedelta(days=1)).strftime("%Y/%m/%d")
    query = f"in:sent to:{client_email} before:{before}"
    resp = gmail_service.users().messages().list(userId="me", q=query, maxResults=1).execute()
    messages = resp.get("messages", [])
    if not messages:
        return {
            "source_label": "last-meeting-email", "thread_id": None,
            "text": "No follow-up email found for this client.",
        }
    message_id = messages[0]["id"]
    full = gmail_service.users().messages().get(userId="me", id=message_id, format="full").execute()

    # Gmail's `to:` search operator matches substrings anywhere the address
    # appears (including a quoted reply body), not just the actual
    # recipient list -- re-check the resolved To/Cc headers before trusting
    # the match.
    if client_email.strip().lower() not in _extract_recipients(full):
        return {
            "source_label": "last-meeting-email", "thread_id": None,
            "text": "No follow-up email found for this client.",
        }

    internal_date = dt.datetime.fromtimestamp(int(full["internalDate"]) / 1000, tz=dt.timezone.utc)
    text = _extract_plain_text(full)
    if (now_utc - internal_date).days > staleness_days:
        text = f"[No recent follow-up found -- most recent is from {internal_date.date().isoformat()}]\n\n{text}"
    return {"source_label": "last-meeting-email", "thread_id": full.get("threadId"), "text": text}


def _extract_recipients(message: dict) -> set[str]:
    headers = message.get("payload", {}).get("headers", [])
    recipients: set[str] = set()
    for header in headers:
        if header.get("name", "").lower() in ("to", "cc"):
            for raw_addr in header.get("value", "").split(","):
                _, addr = email.utils.parseaddr(raw_addr)
                if addr:
                    recipients.add(addr.strip().lower())
    return recipients


def _extract_plain_text(message: dict) -> str:
    payload = message.get("payload", {})
    parts = payload.get("parts") or [payload]
    for part in parts:
        if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    return message.get("snippet", "")


def build_bundle(gmail_service, doc_ingest_reader_mod, doc_ingest_conn, cfg, client: dict, now_utc: dt.datetime) -> dict:
    last_email = find_last_meeting_email(
        gmail_service, client["primary_email"], now_utc, cfg.last_meeting_email_staleness_days
    )
    last_note = doc_ingest_reader_mod.get_latest_tagged_meeting_note(doc_ingest_conn, cfg, client["slug"])
    program_sources = doc_ingest_reader_mod.get_program_sources(cfg)
    return {
        "client_display_name": client["display_name"],
        "client_slug": client["slug"],
        "last_meeting_email": last_email,
        "last_meeting_note": last_note,
        "program_sources": program_sources,
    }


def persist_inputs(conn, run_id: int, the_bundle: dict, now_iso: str) -> None:
    rows = [
        (the_bundle["last_meeting_email"]["source_label"], "gmail_thread",
         the_bundle["last_meeting_email"]["thread_id"] or "none", None),
        (the_bundle["last_meeting_note"]["source_label"], "converted_file",
         the_bundle["last_meeting_note"]["rel_path"] or "none", the_bundle["last_meeting_note"].get("version")),
    ] + [
        (item["source_label"], "program_source", item["rel_path"], item.get("version"))
        for item in the_bundle["program_sources"]
    ]
    with db.transaction(conn):
        for source_label, source_kind, reference, version in rows:
            conn.execute(
                "INSERT INTO generation_inputs "
                "(run_id, source_label, source_kind, reference, version_or_hash, captured_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, source_label, source_kind, reference, str(version) if version else None, now_iso),
            )
