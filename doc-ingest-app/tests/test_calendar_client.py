# doc-ingest-app/tests/test_calendar_client.py
from __future__ import annotations

from doc_ingest import calendar_client


class _FakeExecute:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _FakeEvents:
    def __init__(self, result):
        self._result = result

    def get(self, calendarId, eventId):
        assert calendarId == "admin@freedom2beu.com"
        assert eventId == "287r283hliqvt8duvga7k87srs_20260811T140000Z"
        return _FakeExecute(self._result)


class _FakeService:
    def __init__(self, result):
        self._result = result

    def events(self):
        return _FakeEvents(self._result)


def test_get_event_attendees_extracts_emails():
    service = _FakeService({
        "attendees": [
            {"email": "sean.carl.tinsley@gmail.com"},
            {"email": "admin@freedom2beu.com"},
            {"displayName": "no email here"},
        ]
    })
    attendees = calendar_client.get_event_attendees(
        service, "287r283hliqvt8duvga7k87srs_20260811T140000Z", "admin@freedom2beu.com"
    )
    assert attendees == ["sean.carl.tinsley@gmail.com", "admin@freedom2beu.com"]


def test_get_event_attendees_handles_no_attendees_key():
    service = _FakeService({})
    attendees = calendar_client.get_event_attendees(
        service, "287r283hliqvt8duvga7k87srs_20260811T140000Z", "admin@freedom2beu.com"
    )
    assert attendees == []


def test_build_default_service_raises_clearly_with_no_cached_token(monkeypatch, tmp_path):
    from doc_ingest import calendar_client as cc
    # build_default_service resolves app_root from the module's own __file__
    # (parents[1]); redirecting __file__ at an empty tmp dir with no
    # calendar_token.json is what actually exercises the "not set up yet"
    # path, rather than mocking the function under test to throw the exact
    # thing being asserted.
    monkeypatch.setattr(cc, "__file__", str(tmp_path / "doc_ingest" / "calendar_client.py"))
    import pytest
    with pytest.raises(RuntimeError, match="Calendar token"):
        cc.build_default_service()
