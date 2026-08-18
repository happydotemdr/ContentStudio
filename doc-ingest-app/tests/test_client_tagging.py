# doc-ingest-app/tests/test_client_tagging.py
from __future__ import annotations

from doc_ingest import client_matching, client_tagging, clients_db

SEAN_EID = (
    "Mjg3cjI4M2hsaXF2dDhkdXZnYTdrODdzcnNfMjAyNjA4MTFUMTQwMDAwWiBhZG1pbkBmcmVlZG9tMmJldS5jb20"
)


def _register_sean(conn):
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean.carl.tinsley@gmail.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder1",
    )


def test_session_outlines_folder_matches_by_folder_name(conn):
    _register_sean(conn)
    result = client_tagging.classify(
        conn, "Client Session Outlines/Sean/Some Doc.gdoc", "irrelevant body", lambda: None
    )
    assert result.frontmatter_extra == {"client": "sean"}
    assert result.event_type is None


def test_session_outlines_folder_with_no_registered_client_is_flagged(conn):
    result = client_tagging.classify(
        conn, "Client Session Outlines/Unknown Person/Doc.gdoc", "irrelevant body", lambda: None
    )
    assert result.frontmatter_extra == {"client": client_matching.UNMATCHED}
    assert result.event_type == "client_outline_folder_unregistered"


def test_meeting_note_resolves_via_eid_and_calendar_lookup(conn):
    _register_sean(conn)
    body = (
        f"Attachments [x](https://calendar.google.com/calendar/event?eid={SEAN_EID}) "
    )

    class FakeService:
        def events(self):
            class E:
                def get(self, calendarId, eventId):
                    class Exec:
                        def execute(self):
                            return {"attendees": [
                                {"email": "sean.carl.tinsley@gmail.com"},
                                {"email": "admin@freedom2beu.com"},
                            ]}
                    return Exec()
            return E()

    result = client_tagging.classify(conn, "Client Meet Recordings & Notes/Sean.gdoc", body, lambda: FakeService())
    assert result.frontmatter_extra == {"client": "sean"}
    assert result.event_type is None


def test_meeting_note_with_no_eid_is_unmatched(conn):
    result = client_tagging.classify(
        conn, "Client Meet Recordings & Notes/Investor Operator Meeting.gdoc",
        "# Notes\n\nno eid here", lambda: None,
    )
    assert result.frontmatter_extra == {"client": client_matching.UNMATCHED}
    assert result.event_type == "client_meeting_note_no_eid"


def test_meeting_note_whose_attendees_match_no_client_is_unmatched(conn):
    _register_sean(conn)
    body = f"Attachments [x](https://calendar.google.com/calendar/event?eid={SEAN_EID})"

    class FakeService:
        def events(self):
            class E:
                def get(self, calendarId, eventId):
                    class Exec:
                        def execute(self):
                            return {"attendees": [{"email": "jake.m.lockwood@gmail.com"}]}
                    return Exec()
            return E()

    result = client_tagging.classify(conn, "Client Meet Recordings & Notes/x.gdoc", body, lambda: FakeService())
    assert result.frontmatter_extra == {"client": client_matching.UNMATCHED}
    assert result.event_type == "client_meeting_note_unmatched"


def test_meeting_note_whose_calendar_lookup_fails_is_unmatched(conn):
    body = f"Attachments [x](https://calendar.google.com/calendar/event?eid={SEAN_EID})"

    def failing_factory():
        raise RuntimeError("no cached Calendar token")

    result = client_tagging.classify(conn, "Client Meet Recordings & Notes/x.gdoc", body, failing_factory)
    assert result.frontmatter_extra == {"client": client_matching.UNMATCHED}
    assert result.event_type == "client_meeting_note_lookup_failed"


def test_non_client_file_gets_no_tag_at_all(conn):
    result = client_tagging.classify(
        conn, "Offer & Coaching Framework/Current finalized documents/Vision.gdoc", "body", lambda: None
    )
    assert result.frontmatter_extra == {}
    assert result.event_type is None
