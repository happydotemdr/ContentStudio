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


def _seed_run(conn):
    conn.execute(
        "INSERT INTO generation_runs (client_slug, calendar_event_instance_id, meeting_start_at, "
        "status, created_at, updated_at) VALUES ('sean', 'evt1', 'n', 'assembling', 'n', 'n')"
    )
    conn.commit()


# --- two weeks of sent email ------------------------------------------------
#
# The bundle carried exactly one sent email. Part 1 of the prep doc restates
# what Ryan asked the client to work on, and that lives across the post-call
# email AND whatever he sent mid-week -- a nudge, a reading, a reschedule.
# One message could only ever cover part of it.

class _FakeMessagesMulti:
    """list() returns several ids; get() returns whichever message matches."""

    def __init__(self, messages_by_id):
        self._by_id = messages_by_id
        self.last_query = None
        self.last_max_results = None

    def list(self, userId, q, maxResults):
        assert userId == "me"
        self.last_query = q
        self.last_max_results = maxResults
        return _Exec({"messages": [{"id": mid} for mid in self._by_id]})

    def get(self, userId, id, format):
        return _Exec(self._by_id[id])


class _FakeGmailMulti:
    def __init__(self, messages_by_id):
        self.messages_client = _FakeMessagesMulti(messages_by_id)
        self._users = _FakeUsers(self.messages_client)

    def users(self):
        return self._users


def _message(message_id, sent_at, body, subject="Session follow-up", to="sean@example.com"):
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": str(int(sent_at.timestamp() * 1000)),
        "payload": {
            "headers": [
                {"name": "To", "value": to},
                {"name": "Subject", "value": subject},
            ],
            "mimeType": "text/plain",
            "body": {"data": _b64(body)},
        },
    }


def test_find_recent_emails_returns_every_message_in_the_window():
    messages = {
        "m1": _message("m1", NOW - dt.timedelta(days=2), "the post-call email"),
        "m2": _message("m2", NOW - dt.timedelta(days=6), "a mid-week nudge"),
        "m3": _message("m3", NOW - dt.timedelta(days=11), "an earlier follow-up"),
    }
    service = _FakeGmailMulti(messages)
    found = bundle.find_recent_emails(service, "sean@example.com", NOW, days=14)
    assert [e["text"] for e in found] == [
        "the post-call email", "a mid-week nudge", "an earlier follow-up"
    ]


def test_find_recent_emails_orders_newest_first():
    """Part 1 restates the MOST RECENT post-call email's asks. It has to be
    identifiable as the first item, whatever order Gmail returns."""
    messages = {
        "old": _message("old", NOW - dt.timedelta(days=10), "older"),
        "new": _message("new", NOW - dt.timedelta(days=1), "newer"),
    }
    found = bundle.find_recent_emails(_FakeGmailMulti(messages), "sean@example.com", NOW, days=14)
    assert [e["text"] for e in found] == ["newer", "older"]


def test_find_recent_emails_bounds_the_query_at_both_ends():
    """`after:` scopes the window; `before:` keeps a future-dated or
    clock-skewed message from being trusted as the latest -- the same guard
    the single-email version carried."""
    service = _FakeGmailMulti({"m1": _message("m1", NOW - dt.timedelta(days=1), "body")})
    bundle.find_recent_emails(service, "sean@example.com", NOW, days=14)
    query = service.messages_client.last_query
    assert "in:sent" in query
    assert "to:sean@example.com" in query
    assert "after:2026/08/05" in query
    assert "before:2026/08/20" in query


def test_find_recent_emails_rejects_a_match_not_actually_addressed_to_the_client():
    """Gmail's `to:` matches the address anywhere it appears, including inside
    a quoted reply body. Re-checking the resolved To/Cc headers is what stops
    another client's email entering this client's bundle."""
    messages = {
        "real": _message("real", NOW - dt.timedelta(days=1), "genuinely to sean"),
        "quoted": _message("quoted", NOW - dt.timedelta(days=2), "quotes sean's address",
                           to="someone-else@example.com"),
    }
    found = bundle.find_recent_emails(_FakeGmailMulti(messages), "sean@example.com", NOW, days=14)
    assert [e["text"] for e in found] == ["genuinely to sean"]


def test_find_recent_emails_caps_how_many_it_returns():
    """A chatty fortnight must not push the framework material out of the
    drafting prompt."""
    messages = {
        f"m{i}": _message(f"m{i}", NOW - dt.timedelta(days=i), f"body {i}")
        for i in range(1, 12)
    }
    found = bundle.find_recent_emails(
        _FakeGmailMulti(messages), "sean@example.com", NOW, days=14, max_messages=5
    )
    assert len(found) == 5
    assert found[0]["text"] == "body 1"


def test_find_recent_emails_returns_empty_when_nothing_was_sent():
    service = _FakeGmailService({"messages": []}, {})
    assert bundle.find_recent_emails(service, "sean@example.com", NOW, days=14) == []


def test_recent_emails_get_distinct_source_labels():
    """Every email is separately citable in Part 1, and the citation gate
    validates each tag against the allowlist."""
    messages = {
        "m1": _message("m1", NOW - dt.timedelta(days=1), "one"),
        "m2": _message("m2", NOW - dt.timedelta(days=5), "two"),
    }
    labels = [e["source_label"] for e in
              bundle.find_recent_emails(_FakeGmailMulti(messages), "sean@example.com", NOW, days=14)]
    assert labels == ["last-meeting-email", "sent-email-2"]
    assert all(label.replace("-", "").isalnum() for label in labels)


def test_the_newest_email_keeps_the_last_meeting_email_label():
    """Part 1's whole job is checking in on what the post-call email asked
    for. That email must be identifiable by a stable label the prompt can
    name, not by position alone."""
    messages = {"m1": _message("m1", NOW - dt.timedelta(days=1), "the post-call email")}
    found = bundle.find_recent_emails(_FakeGmailMulti(messages), "sean@example.com", NOW, days=14)
    assert found[0]["source_label"] == "last-meeting-email"


def test_recent_emails_carry_subject_and_date_for_the_prep_doc():
    messages = {"m1": _message("m1", NOW - dt.timedelta(days=3), "body",
                               subject="Your week: the PQ reps")}
    found, = bundle.find_recent_emails(_FakeGmailMulti(messages), "sean@example.com", NOW, days=14)
    assert found["subject"] == "Your week: the PQ reps"
    assert found["sent_date"] == "2026-08-16"
    assert found["thread_id"] == "thread-m1"


# --- the assembled bundle ---------------------------------------------------

def _fake_reader(notes, program_sources, book_list=None):
    class _Reader:
        @staticmethod
        def get_recent_meeting_notes(conn, cfg, slug, limit=2):
            return notes[:limit]

        @staticmethod
        def get_program_sources(cfg):
            return program_sources

    return _Reader


_PROGRAM = [
    {"source_label": "freedom2beu-program-structure-v3", "rel_path": "p/structure.md",
     "version": None, "text": "the program"},
    {"source_label": "f2bu-coaching-book-recommendations", "rel_path":
     "Frameworks to consider/Books and research/Coaching Book Recommendations/"
     "F2BU Coaching Book Recommendations.gsheet.md", "version": None,
     "text": "| Book Title | Author |\n| --- | --- |\n| Dare to Lead | Brene Brown |"},
]

_NOTES = [
    {"source_label": "meeting-note-aug", "rel_path": "n/aug.md", "version": 1,
     "meeting_date": "2026-08-04", "text": "the August session"},
    {"source_label": "meeting-note-jul", "rel_path": "n/jul.md", "version": 1,
     "meeting_date": "2026-07-22", "text": "the July session"},
]


def _build(gmail_service=None, notes=None, program=None, selected=None):
    from coach_prep_app.config import Config
    service = gmail_service or _FakeGmailMulti(
        {"m1": _message("m1", NOW - dt.timedelta(days=2), "the post-call email")}
    )
    return bundle.build_bundle(
        service, _fake_reader(notes if notes is not None else _NOTES,
                              program if program is not None else _PROGRAM),
        None, Config(),
        {"slug": "sean", "display_name": "Sean", "primary_email": "sean@example.com"},
        NOW, selected_frameworks=selected or [],
    )


def test_build_bundle_carries_recent_emails_and_two_notes():
    built = _build()
    assert [e["source_label"] for e in built["recent_emails"]] == ["last-meeting-email"]
    assert [n["meeting_date"] for n in built["meeting_notes"]] == ["2026-08-04", "2026-07-22"]


def test_build_bundle_splits_the_book_list_out_of_the_program_sources():
    """The book list is a reading catalog, not program structure. The prompt
    uses it for one job -- recommending a reading -- so it is passed under its
    own key rather than buried among the eight framework documents."""
    built = _build()
    assert built["book_list"] is not None
    assert "Dare to Lead" in built["book_list"]["text"]
    assert "f2bu-coaching-book-recommendations" not in [
        s["source_label"] for s in built["program_sources"]
    ]


def test_build_bundle_tolerates_a_missing_book_list():
    """The sheet only converts because of the gsheet gauntlet fix. If it ever
    drops out of the corpus again, the run must degrade to a prep doc with no
    reading recommendation -- not fail."""
    built = _build(program=[_PROGRAM[0]])
    assert built["book_list"] is None
    assert built["program_sources"]


def test_build_bundle_carries_the_selected_framework_activities():
    selected = [{"source_label": "examining-fear", "rel_path": "f/fear.md", "version": 1,
                 "id": "jscc-a3-2-examining-fear", "title": "Examining Fear",
                 "why": "his avoidance pattern", "text": "the exercise"}]
    built = _build(selected=selected)
    assert built["selected_frameworks"] == selected


def test_persist_inputs_records_every_source_including_the_new_kinds(conn):
    _seed_run(conn)
    the_bundle = {
        "recent_emails": [
            {"source_label": "last-meeting-email", "thread_id": "t1", "text": "x"},
            {"source_label": "sent-email-2", "thread_id": "t2", "text": "x"},
        ],
        "meeting_notes": [
            {"source_label": "meeting-note-aug", "rel_path": "n/aug.md", "version": 1, "text": "y"},
        ],
        "program_sources": [
            {"source_label": "vision", "rel_path": "c/d.md", "version": None, "text": "z"},
        ],
        "book_list": {"source_label": "books", "rel_path": "b/books.md", "version": 2, "text": "b"},
        "selected_frameworks": [
            {"source_label": "fear", "rel_path": "f/fear.md", "version": 1, "text": "f"},
        ],
    }
    bundle.persist_inputs(conn, 1, the_bundle, "2026-08-19T12:00:00+00:00")
    rows = conn.execute(
        "SELECT source_label, source_kind, reference FROM generation_inputs ORDER BY id"
    ).fetchall()
    assert rows == [
        ("last-meeting-email", "gmail_thread", "t1"),
        ("sent-email-2", "gmail_thread", "t2"),
        ("meeting-note-aug", "converted_file", "n/aug.md"),
        ("vision", "program_source", "c/d.md"),
        ("books", "book_list", "b/books.md"),
        ("fear", "selected_framework", "f/fear.md"),
    ]


def test_persist_inputs_records_a_run_that_found_nothing(conn):
    """The manifest at the foot of the prep doc is rendered from these rows.
    A run with no email and no notes must still leave a truthful record --
    an empty manifest is information, a crash is not."""
    _seed_run(conn)
    bundle.persist_inputs(
        conn, 1,
        {"recent_emails": [], "meeting_notes": [], "program_sources": [],
         "book_list": None, "selected_frameworks": []},
        "2026-08-19T12:00:00+00:00",
    )
    assert conn.execute("SELECT COUNT(*) FROM generation_inputs").fetchone()[0] == 0


def test_persist_inputs_happens_before_generation_can_fail(conn):
    """persist_inputs is called with the bundle, never with the draft. The row
    has to exist regardless of what generation, the gates, or publish do
    afterwards -- that is the whole audit trail."""
    import inspect
    source = inspect.getsource(bundle.persist_inputs)
    assert "generate" not in source
    assert "draft" not in source


def test_build_bundle_falls_back_to_the_last_email_when_the_window_is_empty():
    """A client Ryan has not emailed in three weeks would otherwise get an
    empty Part 1 with no explanation on the page. The fallback carries the
    stale email AND its staleness note, so he can see why it is thin."""
    old_message = _message("old", NOW - dt.timedelta(days=40), "an old ask")
    service = _FakeGmailMulti({"old": old_message})

    # The windowed query finds nothing; the unbounded fallback finds this one.
    class _WindowAware(_FakeMessagesMulti):
        def list(self, userId, q, maxResults):
            self.last_query = q
            if "after:" in q:
                return _Exec({"messages": []})
            return _Exec({"messages": [{"id": "old"}]})

    service.messages_client.__class__ = _WindowAware
    built = _build(gmail_service=service)

    assert len(built["recent_emails"]) == 1
    assert "an old ask" in built["recent_emails"][0]["text"]
    assert "No recent follow-up found" in built["recent_emails"][0]["text"]


def test_build_bundle_leaves_recent_emails_empty_when_there_are_none_at_all():
    service = _FakeGmailMulti({})
    assert _build(gmail_service=service)["recent_emails"] == []
