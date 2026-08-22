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


def find_recent_emails(gmail_service, client_email: str, now_utc: dt.datetime,
                       days: int = 14, max_messages: int = 5) -> list[dict]:
    """Everything Ryan sent this client over the trailing window, newest first.

    Part 1 of the prep doc checks in on what he asked the client to work on,
    and that is spread across the post-call email AND whatever he sent
    mid-week -- a nudge, a reading, a reschedule. A single message could only
    ever cover part of it.

    The window is bounded at BOTH ends. `after:` scopes it; `before:` is the
    same guard the single-email version carried, so a future-dated or
    clock-skewed message cannot be trusted as the most recent. Gmail's `to:`
    also matches the address anywhere it appears, including inside a quoted
    reply body, so every hit is re-checked against its resolved To/Cc headers
    before it enters this client's bundle.

    max_messages caps the result: a chatty fortnight must not push the
    framework material out of the drafting prompt."""
    after = (now_utc - dt.timedelta(days=days)).strftime("%Y/%m/%d")
    before = (now_utc + dt.timedelta(days=1)).strftime("%Y/%m/%d")
    query = f"in:sent to:{client_email} after:{after} before:{before}"
    resp = gmail_service.users().messages().list(
        userId="me", q=query, maxResults=max_messages * 2
    ).execute()

    found = []
    for stub in resp.get("messages", []):
        full = gmail_service.users().messages().get(
            userId="me", id=stub["id"], format="full"
        ).execute()
        if client_email.strip().lower() not in _extract_recipients(full):
            continue
        sent_at = dt.datetime.fromtimestamp(int(full["internalDate"]) / 1000, tz=dt.timezone.utc)
        found.append({
            "thread_id": full.get("threadId"),
            "subject": _extract_header(full, "subject"),
            "sent_at": sent_at,
            "sent_date": sent_at.date().isoformat(),
            "text": _extract_plain_text(full),
        })

    found.sort(key=lambda m: m["sent_at"], reverse=True)
    found = found[:max_messages]
    for position, message in enumerate(found, start=1):
        # The newest keeps the label the prompt names by hand -- Part 1's job
        # is checking in on what THAT email asked for, so it has to be
        # identifiable by a stable label rather than by position alone.
        message["source_label"] = "last-meeting-email" if position == 1 else f"sent-email-{position}"
        del message["sent_at"]
    return found


def _extract_header(message: dict, name: str) -> str:
    for header in message.get("payload", {}).get("headers", []):
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


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


# The book list is a reading catalog, not program structure. It is listed in
# program_sources.yaml so doc-ingest version-tracks it like everything else,
# but the prompt uses it for exactly one job -- recommending a reading -- so
# the bundle pulls it out under its own key rather than leaving it buried
# among the framework documents.
BOOK_LIST_LABEL = "f2bu-coaching-book-recommendations"


def build_bundle(gmail_service, doc_ingest_reader_mod, doc_ingest_conn, cfg, client: dict,
                 now_utc: dt.datetime, selected_frameworks: list[dict] | None = None) -> dict:
    recent_emails = find_recent_emails(
        gmail_service, client["primary_email"], now_utc, days=cfg.email_window_days,
        max_messages=cfg.max_recent_emails,
    )
    if not recent_emails:
        # Nothing inside the window. Fall back to the single most recent email
        # ever sent, carrying its own staleness note -- Part 1 exists to check
        # in on what Ryan last asked for, and "here is that ask, and it is
        # three weeks old" is far more use to him than a silently empty
        # section he has to work out the reason for mid-call.
        fallback = find_last_meeting_email(
            gmail_service, client["primary_email"], now_utc, cfg.last_meeting_email_staleness_days
        )
        if fallback.get("thread_id"):
            recent_emails = [fallback]
    meeting_notes = doc_ingest_reader_mod.get_recent_meeting_notes(
        doc_ingest_conn, cfg, client["slug"], limit=cfg.meeting_notes_count
    )
    all_program = doc_ingest_reader_mod.get_program_sources(cfg)
    book_list = next((s for s in all_program if s["source_label"] == BOOK_LIST_LABEL), None)
    program_sources = [s for s in all_program if s["source_label"] != BOOK_LIST_LABEL]
    return {
        "client_display_name": client["display_name"],
        "client_slug": client["slug"],
        "recent_emails": recent_emails,
        "meeting_notes": meeting_notes,
        "program_sources": program_sources,
        "book_list": book_list,
        "selected_frameworks": list(selected_frameworks or []),
    }


def persist_inputs(conn, run_id: int, the_bundle: dict, now_iso: str) -> None:
    """Record every source this run drew on, BEFORE generation happens. These
    rows are the audit trail and the thing the prep doc's closing manifest is
    rendered from, so they must exist regardless of what generation, the gates,
    or publish do afterwards."""
    rows = [
        (email["source_label"], "gmail_thread", email.get("thread_id") or "none", None)
        for email in the_bundle["recent_emails"]
    ] + [
        (note["source_label"], "converted_file", note["rel_path"], note.get("version"))
        for note in the_bundle["meeting_notes"]
    ] + [
        (item["source_label"], "program_source", item["rel_path"], item.get("version"))
        for item in the_bundle["program_sources"]
    ]
    if the_bundle.get("book_list"):
        book = the_bundle["book_list"]
        rows.append((book["source_label"], "book_list", book["rel_path"], book.get("version")))
    rows += [
        (item["source_label"], "selected_framework", item["rel_path"], item.get("version"))
        for item in the_bundle.get("selected_frameworks", [])
    ]

    with db.transaction(conn):
        for source_label, source_kind, reference, version in rows:
            conn.execute(
                "INSERT INTO generation_inputs "
                "(run_id, source_label, source_kind, reference, version_or_hash, captured_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, source_label, source_kind, reference, str(version) if version else None, now_iso),
            )
