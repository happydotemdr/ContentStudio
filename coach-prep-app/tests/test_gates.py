# coach-prep-app/tests/test_gates.py
from __future__ import annotations

from coach_prep_app import gates

OTHER_CLIENTS = [
    {"slug": "josh", "display_name": "Josh", "primary_email": "josh@example.com", "alias_emails": []},
    {
        "slug": "joanne", "display_name": "Joanne", "primary_email": "jnnbryant77@gmail.com",
        "alias_emails": ["joanne.bryant@schwab.com"],
    },
]


def test_citation_gate_passes_when_every_label_is_allowed():
    text = "- Reflect on X [last-meeting-email]\n- Discuss Y [program-structure-v3]"
    assert gates.citation_gate(text, {"last-meeting-email", "program-structure-v3"}) == []


def test_citation_gate_flags_an_invented_label():
    text = "- Reflect on X [made-up-source]"
    assert gates.citation_gate(text, {"last-meeting-email"}) == ["made-up-source"]


def test_leakage_scan_passes_clean_text():
    text = "- Sean should reflect on morality [last-meeting-email]"
    assert gates.leakage_scan(text, OTHER_CLIENTS) == []


def test_leakage_scan_catches_another_clients_full_name():
    text = "- Like we discussed with Josh, try the same exercise [last-meeting-email]"
    assert gates.leakage_scan(text, OTHER_CLIENTS) == ["josh"]


def test_leakage_scan_catches_another_clients_alias_email():
    text = "- Follow up per joanne.bryant@schwab.com's note [last-meeting-email]"
    assert gates.leakage_scan(text, OTHER_CLIENTS) == ["joanne"]


def test_leakage_scan_catches_another_clients_first_name():
    text = "- Joanne mentioned this exact struggle too [last-meeting-email]"
    assert gates.leakage_scan(text, OTHER_CLIENTS) == ["joanne"]


def test_citation_gate_does_not_flag_a_markdown_link():
    text = "- See more [here](https://example.com) for context"
    assert gates.citation_gate(text, set()) == []


def test_citation_gate_still_flags_a_bogus_label_with_no_paren_after():
    text = "- Reflect on X [made-up-source]"
    assert gates.citation_gate(text, {"last-meeting-email"}) == ["made-up-source"]


def test_leakage_scan_ignores_lowercase_common_word_matching_first_name():
    clients = [
        {
            "slug": "grace", "display_name": "Grace Wilson", "primary_email": "gracewilson@example.com",
            "alias_emails": [],
        },
    ]
    text = "- Approach this with grace and patience, one step at a time"
    assert gates.leakage_scan(text, clients) == []


def test_leakage_scan_still_catches_capitalized_first_name():
    clients = [
        {
            "slug": "grace", "display_name": "Grace Wilson", "primary_email": "gracewilson@example.com",
            "alias_emails": [],
        },
    ]
    text = "- Grace mentioned this exact struggle too [last-meeting-email]"
    assert gates.leakage_scan(text, clients) == ["grace"]
