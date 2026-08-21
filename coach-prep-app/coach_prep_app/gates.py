# coach-prep-app/coach_prep_app/gates.py
"""Mechanical, non-LLM gates run on generated text before publish. Defense
in depth -- NOT the sole safety mechanism. The draft always lands in the
shared Pending Review folder (Task 19), never directly in a client's real
folder, regardless of what these gates find."""
from __future__ import annotations

import re

_CITATION_RE = re.compile(r"\[([a-z0-9\-]+)\](?!\()")


def citation_gate(generated_text: str, allowed_labels: set[str]) -> list[str]:
    found = set(_CITATION_RE.findall(generated_text))
    return sorted(found - allowed_labels)


def leakage_scan(generated_text: str, other_clients: list[dict]) -> list[str]:
    lowered = generated_text.lower()
    hits = []
    for client in other_clients:
        needles = [client["display_name"], client["primary_email"], *client["alias_emails"]]
        first_name = client["display_name"].split()[0] if client["display_name"] else ""
        matched = any(needle and needle.lower() in lowered for needle in needles)
        if not matched and first_name:
            matched = bool(re.search(rf"\b{re.escape(first_name)}\b", generated_text))
        if matched:
            hits.append(client["slug"])
    return hits


def allowed_labels(the_bundle: dict) -> set[str]:
    """Every source label this bundle legitimately carries -- the allowlist the
    citation gate validates the draft's inline tags against.

    Derived from the bundle rather than assembled by each caller: the bundle
    grew from one email and one note to several of each plus a book list and
    the selected framework activities, and a caller that built this set by
    hand would silently stop allowing whatever it had not been taught about.
    A label missing from here fails the gate and stops the run."""
    labels = {
        item["source_label"]
        for key in ("recent_emails", "meeting_notes", "program_sources", "selected_frameworks")
        for item in the_bundle.get(key) or []
    }
    if the_bundle.get("book_list"):
        labels.add(the_bundle["book_list"]["source_label"])
    return labels


# Markdown constructs Google's Docs importer drops, mangles, or renders as
# literal text. The published draft is picked up by the ingest cron and
# converted back to markdown, so anything that does not survive the trip out
# also does not survive the trip back -- and the recovered file becomes the
# corpus's record of what Ryan was given.
_ROUNDTRIP_HAZARDS = (
    (re.compile(r"<[a-zA-Z/!][^>]*>"), "raw_html"),
    (re.compile(r"\[\^[^\]]+\]"), "footnote"),
    (re.compile(r"^#{4,}\s", re.MULTILINE), "heading_deeper_than_h3"),
    (re.compile(r"^\s*\[[^\]]+\]:\s+\S+", re.MULTILINE), "reference_style_link"),
    (re.compile(r"^\s{0,3}(\*\s*){3,}$", re.MULTILINE), "asterisk_thematic_break"),
)
# Not checked: nested tables. Markdown has no syntax for them, so there is
# nothing to detect -- a first attempt at a pattern for it matched every
# ordinary header-plus-separator table, including the prep doc's own book
# list, and would have failed every run.


def roundtrip_safe_markdown(generated_text: str) -> list[str]:
    """Names of markdown constructs in the draft that will not survive the
    Google Docs round trip. Empty means clean.

    Runs alongside the citation and leakage gates for the same reason they
    do: a defect found here costs a regenerated draft, whereas one found
    later costs Ryan a doc he cannot read mid-call and leaves the corpus
    holding a garbled record of it."""
    return sorted({name for pattern, name in _ROUNDTRIP_HAZARDS if pattern.search(generated_text)})
