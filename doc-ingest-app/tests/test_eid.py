from __future__ import annotations

import pytest

from doc_ingest import eid as eid_mod

REAL_EID = (
    "Mjg3cjI4M2hsaXF2dDhkdXZnYTdrODdzcnNfMjAyNjA4MTFUMTQwMDAwWiBhZG1pbkBmcmVlZG9tMmJldS5jb20"
)
REAL_EVENT_ID = "287r283hliqvt8duvga7k87srs_20260811T140000Z"
REAL_CALENDAR_ID = "admin@freedom2beu.com"

BODY_WITH_EID = (
    "Attachments [Sean and Ryan Coaching Session]"
    f"(https://calendar.google.com/calendar/event?eid={REAL_EID}) "
    "[Notes by Gemini](https://docs.google.com/document/d/abc/edit)"
)

BODY_WITHOUT_EID = "# Notes\n\nInvestor Operator Meeting\n\nNo attachments line here."


def test_extract_eid_finds_the_real_corpus_eid():
    assert eid_mod.extract_eid(BODY_WITH_EID) == REAL_EID


def test_extract_eid_returns_none_when_absent():
    assert eid_mod.extract_eid(BODY_WITHOUT_EID) is None


def test_decode_eid_matches_the_verified_real_value():
    event_id, calendar_id = eid_mod.decode_eid(REAL_EID)
    assert event_id == REAL_EVENT_ID
    assert calendar_id == REAL_CALENDAR_ID


def test_decode_eid_rejects_garbage():
    with pytest.raises(ValueError):
        eid_mod.decode_eid("not-valid-base64-at-all-!!!")
