from __future__ import annotations

from doc_ingest import client_matching

SEAN = {"slug": "sean", "primary_email": "sean.carl.tinsley@gmail.com", "alias_emails": []}
JOANNE = {
    "slug": "joanne", "primary_email": "jnnbryant77@gmail.com",
    "alias_emails": ["joanne.bryant@schwab.com"],
}
CLIENTS = [SEAN, JOANNE]
COACH_EMAIL = "admin@freedom2beu.com"


def test_matches_a_single_registered_client():
    result = client_matching.match_attendees_to_client(
        ["sean.carl.tinsley@gmail.com", "admin@freedom2beu.com"], CLIENTS, COACH_EMAIL
    )
    assert result == "sean"


def test_matches_via_an_alias_email():
    result = client_matching.match_attendees_to_client(
        ["joanne.bryant@schwab.com", "admin@freedom2beu.com"], CLIENTS, COACH_EMAIL
    )
    assert result == "joanne"


def test_costa_rica_case_no_registered_client_is_unmatched():
    result = client_matching.match_attendees_to_client(
        ["jake.m.lockwood@gmail.com", "admin@freedom2beu.com"], CLIENTS, COACH_EMAIL
    )
    assert result == client_matching.UNMATCHED


def test_chris_griswold_case_no_registered_client_is_unmatched():
    result = client_matching.match_attendees_to_client(
        ["cgris68@gmail.com", "admin@freedom2beu.com"], CLIENTS, COACH_EMAIL
    )
    assert result == client_matching.UNMATCHED


def test_investor_meeting_case_empty_attendee_list_is_unmatched():
    result = client_matching.match_attendees_to_client([], CLIENTS, COACH_EMAIL)
    assert result == client_matching.UNMATCHED


def test_two_distinct_clients_on_one_event_is_unmatched():
    result = client_matching.match_attendees_to_client(
        ["sean.carl.tinsley@gmail.com", "jnnbryant77@gmail.com"], CLIENTS, COACH_EMAIL
    )
    assert result == client_matching.UNMATCHED


def test_coach_own_address_alone_is_unmatched_never_a_client():
    result = client_matching.match_attendees_to_client(["admin@freedom2beu.com"], CLIENTS, COACH_EMAIL)
    assert result == client_matching.UNMATCHED


def test_matching_is_case_insensitive():
    result = client_matching.match_attendees_to_client(
        ["Sean.Carl.Tinsley@GMAIL.com"], CLIENTS, COACH_EMAIL
    )
    assert result == "sean"
