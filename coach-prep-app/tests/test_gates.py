# coach-prep-app/tests/test_gates.py
from __future__ import annotations

import pytest

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


# --- allowed_labels ---------------------------------------------------------

_BUNDLE = {
    "recent_emails": [
        {"source_label": "last-meeting-email"}, {"source_label": "sent-email-2"},
    ],
    "meeting_notes": [
        {"source_label": "meeting-note-aug"}, {"source_label": "meeting-note-jul"},
    ],
    "program_sources": [{"source_label": "program-structure"}],
    "book_list": {"source_label": "f2bu-coaching-book-recommendations"},
    "selected_frameworks": [{"source_label": "examining-fear"}],
}


def test_allowed_labels_covers_every_source_in_the_bundle():
    """A label missing here fails the citation gate and stops the run. The
    bundle grew from one email and one note to several of each plus a book
    list and the selected activities -- a caller assembling this set by hand
    would silently stop allowing whatever it had not been taught about."""
    assert gates.allowed_labels(_BUNDLE) == {
        "last-meeting-email", "sent-email-2", "meeting-note-aug", "meeting-note-jul",
        "program-structure", "f2bu-coaching-book-recommendations", "examining-fear",
    }


def test_allowed_labels_handles_a_bundle_with_no_book_list():
    labels = gates.allowed_labels({**_BUNDLE, "book_list": None})
    assert "f2bu-coaching-book-recommendations" not in labels
    assert "last-meeting-email" in labels


def test_allowed_labels_of_an_empty_bundle_is_empty():
    """A run that found nothing must yield an empty allowlist, so any tag at
    all in the draft fails the gate -- a draft citing sources that were never
    supplied is precisely what the gate exists to stop."""
    assert gates.allowed_labels({}) == set()


def test_a_draft_citing_the_new_source_kinds_passes_the_gate():
    draft = (
        "- Checked in on the reading [f2bu-coaching-book-recommendations]\n"
        "- Ran the fear exercise [examining-fear]\n"
        "- Referenced the July session [meeting-note-jul]\n"
    )
    assert gates.citation_gate(draft, gates.allowed_labels(_BUNDLE)) == []


def test_a_draft_citing_an_unsupplied_framework_still_fails():
    """The selected activities are the ONE part of the prompt the model helped
    choose. A draft citing an activity that was never embedded is the model
    working from its own knowledge of coaching tools instead of the corpus."""
    draft = "- Try the Johari Window [johari-window]\n"
    assert gates.citation_gate(draft, gates.allowed_labels(_BUNDLE)) == ["johari-window"]


# --- round-trip safety ------------------------------------------------------

def test_a_clean_prep_doc_passes():
    draft = (
        "## Summary\n\nHe has not made the call.\n\n"
        "### Why this direction\n\nBecause it is the fourth session.\n\n---\n\n"
        "## Part 1 — Check-in (~10 min)\n\n"
        "- What came up in the journalling? [last-meeting-email]\n\n"
        "### How to run it live\n\n1. Ask it plainly.\n2. Say **nothing** for a beat.\n\n"
        "| Book | Author |\n| --- | --- |\n| Dare to Lead | Brene Brown |\n"
    )
    assert gates.roundtrip_safe_markdown(draft) == []


@pytest.mark.parametrize("draft,hazard", [
    ("## Part 1\n\n<br>a line break", "raw_html"),
    ("## Part 1\n\n<div>a block</div>", "raw_html"),
    ("## Part 1\n\nA claim[^1]\n\n[^1]: the note", "footnote"),
    ("## Part 1\n\n#### Too deep\n\ntext", "heading_deeper_than_h3"),
    ("## Part 1\n\nSee [the guide][guide]\n\n[guide]: https://example.com", "reference_style_link"),
    ("## Part 1\n\n* * *\n\ntext", "asterisk_thematic_break"),
])
def test_roundtrip_gate_catches_each_hazard(draft, hazard):
    assert hazard in gates.roundtrip_safe_markdown(draft)


def test_roundtrip_gate_reports_every_hazard_it_finds():
    """One regeneration should fix all of them, not surface them one per run."""
    draft = "## Part 1\n\n<br>\n\n#### Deep\n\nA claim[^1]\n\n[^1]: note"
    found = gates.roundtrip_safe_markdown(draft)
    assert set(found) >= {"raw_html", "heading_deeper_than_h3", "footnote"}


def test_roundtrip_gate_allows_the_markdown_the_prep_doc_actually_uses():
    """The template asks for H2/H3, bold, bullets, numbered steps, `---`
    rules and a table. None of that may trip the gate, or every run fails."""
    from coach_prep_app import manifest
    footer = manifest.render([
        ("gmail_thread", "last-meeting-email", "thread-1", None),
        ("selected_framework", "fear", "Frameworks/Fear.pdf.md", "2"),
    ])
    assert gates.roundtrip_safe_markdown(footer) == []


def test_roundtrip_gate_does_not_flag_an_em_dash_or_a_time_box():
    assert gates.roundtrip_safe_markdown("## Part 1 — Check-in (~10 min)\n\ntext") == []
