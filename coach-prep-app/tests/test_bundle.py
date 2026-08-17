# coach-prep-app/tests/test_bundle.py
from __future__ import annotations

import base64
import datetime as dt

from coach_prep_app import bundle

NOW = dt.datetime(2026, 8, 19, 12, 0, tzinfo=dt.timezone.utc)


class _FakeMessages:
    def __init__(self, list_response, get_response):
        self._list_response = list_response
        self._get_response = get_response
        self.last_query = None

    def list(self, userId, q, maxResults):
        assert userId == "me"
        self.last_query = q
        return _Exec(self._list_response)

    def get(self, userId, id, format):
        return _Exec(self._get_response)


class _Exec:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeUsers:
    def __init__(self, messages_client):
        self._messages = messages_client

    def messages(self):
        return self._messages


class _FakeGmailService:
    def __init__(self, list_response, get_response):
        self.messages_client = _FakeMessages(list_response, get_response)
        self._users = _FakeUsers(self.messages_client)

    def users(self):
        return self._users


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


def _headers_to(*addresses: str) -> list[dict]:
    return [{"name": "To", "value": ", ".join(addresses)}]


def test_find_last_meeting_email_returns_recent_message_verbatim():
    internal_date_ms = int(dt.datetime(2026, 8, 12, 0, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    service = _FakeGmailService(
        list_response={"messages": [{"id": "msg1"}]},
        get_response={
            "threadId": "thread1",
            "internalDate": str(internal_date_ms),
            "payload": {
                "headers": _headers_to("sean@example.com"),
                "parts": [{"mimeType": "text/plain", "body": {"data": _b64("Do the 5-minute exercise.")}}],
            },
        },
    )
    result = bundle.find_last_meeting_email(service, "sean@example.com", NOW, staleness_days=30)
    assert result["thread_id"] == "thread1"
    assert "Do the 5-minute exercise." in result["text"]
    assert "No recent follow-up" not in result["text"]
    # NOW is 2026-08-19 -- the search must carry an upper date bound so it
    # never trusts a message dated after "now" (clock skew, replay, a
    # future-dated draft).
    assert "before:2026/08/20" in service.messages_client.last_query


def test_find_last_meeting_email_flags_a_stale_match():
    internal_date_ms = int(dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    service = _FakeGmailService(
        list_response={"messages": [{"id": "msg1"}]},
        get_response={
            "threadId": "thread1",
            "internalDate": str(internal_date_ms),
            "payload": {
                "headers": _headers_to("sean@example.com"),
                "parts": [{"mimeType": "text/plain", "body": {"data": _b64("Old content.")}}],
            },
        },
    )
    result = bundle.find_last_meeting_email(service, "sean@example.com", NOW, staleness_days=30)
    assert "No recent follow-up" in result["text"]
    assert "Old content." in result["text"]


def test_find_last_meeting_email_handles_no_messages_found():
    service = _FakeGmailService(list_response={}, get_response={})
    result = bundle.find_last_meeting_email(service, "sean@example.com", NOW, staleness_days=30)
    assert result["thread_id"] is None
    assert "No follow-up email found" in result["text"]


def test_find_last_meeting_email_rejects_a_match_not_actually_addressed_to_the_client():
    """The Gmail search `in:sent to:<address>` can surface a message where
    the address only appears in a quoted reply body rather than the actual
    recipient list -- confirm the resolved To/Cc headers really contain the
    target client before trusting the match."""
    internal_date_ms = int(dt.datetime(2026, 8, 12, 0, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    service = _FakeGmailService(
        list_response={"messages": [{"id": "msg1"}]},
        get_response={
            "threadId": "thread1",
            "internalDate": str(internal_date_ms),
            "payload": {
                "headers": _headers_to("someone.else@example.com"),
                "parts": [{"mimeType": "text/plain", "body": {"data": _b64("Not actually to Sean.")}}],
            },
        },
    )
    result = bundle.find_last_meeting_email(service, "sean@example.com", NOW, staleness_days=30)
    assert result["thread_id"] is None
    assert "No follow-up email found" in result["text"]


def test_persist_inputs_writes_one_row_per_source(conn):
    _seed_run(conn)
    the_bundle = {
        "last_meeting_email": {"source_label": "last-meeting-email", "thread_id": "t1", "text": "x"},
        "last_meeting_note": {"source_label": "last-meeting-note", "rel_path": "a/b.md", "version": 1, "text": "y"},
        "program_sources": [
            {"source_label": "vision", "rel_path": "c/d.md", "version": None, "text": "z"},
        ],
    }
    bundle.persist_inputs(conn, 1, the_bundle, "2026-08-19T12:00:00+00:00")
    rows = conn.execute("SELECT source_label, source_kind, reference FROM generation_inputs ORDER BY id").fetchall()
    assert rows == [
        ("last-meeting-email", "gmail_thread", "t1"),
        ("last-meeting-note", "converted_file", "a/b.md"),
        ("vision", "program_source", "c/d.md"),
    ]


def _seed_run(conn):
    conn.execute(
        "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, meeting_start_at, "
        "status, created_at, updated_at) VALUES ('sean', 'evt1', 'n', 'assembling', 'n', 'n')"
    )
    conn.commit()
