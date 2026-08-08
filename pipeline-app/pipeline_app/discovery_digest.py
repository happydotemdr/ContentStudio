"""Reads a finished discovery run's on-disk output into normalized items for
the daily email, and picks the one item the email spotlights.

Filesystem only -- no network, no DB, no LLM. Deliberately has no dependency
on discovery_engine.py, same as discovery_notify.py.

THE PLATFORM CONTRACT. A discovery adapter's download_item must write YAML
frontmatter containing at minimum `url` and `fetched_at`, with the post's text
as the markdown body. An adapter that does this appears in the daily email --
inventory entry, link, title, and spotlight eligibility -- with no change to
any email-side module. `like_count`, `comment_count`, `view_count`, and
`published` are optional; each is omitted from the render when absent.
`fetched_at` must be an aware-UTC isoformat(timespec="seconds") STRING.

One known exception: download_brandintel.py, the manual toolkit script at repo
root, does not honor this contract and is deliberately left unmodified.
Nothing it writes falls inside a discovery run's watermark, so it never
reaches the email.

See docs/superpowers/specs/2026-08-08-morning-email-social-expansion-design.md.
"""
from __future__ import annotations

import re

# Written by the adapters when they have nothing. Treated as empty everywhere:
# an excerpt reading "(no transcript available)" is worse than no excerpt.
PLACEHOLDERS = frozenset({"(none)", "(empty)", "(no transcript available)"})

TITLE_MAX_CHARS = 90

# Preference order when a body is section-structured (YouTube's is: an H1, then
# "## description", then "## transcript" -- discovery_youtube.py:289-293).
_SECTION_PREFERENCE = ("## transcript", "## description")

_H1_PREFIX = "# "


def _clean(text: str) -> str:
    """Stripped text, or "" if it is one of the adapters' placeholder strings."""
    stripped = text.strip()
    return "" if stripped in PLACEHOLDERS else stripped


def _truncate_at_word(text: str, maxlen: int) -> str:
    if len(text) <= maxlen:
        return text
    cut = text[:maxlen]
    space = cut.rfind(" ")
    return (cut[:space] if space > 0 else cut).rstrip()


def derive_title(body: str, fallback: str) -> str:
    """The item's title: a leading markdown H1 if there is one, else the first
    non-empty line truncated.

    The H1 test requires "# " -- hash followed by a SPACE -- and that is
    load-bearing. Social posts routinely open with a hashtag ("#MondayMotivation
    ..."), and a bare startswith("#") would classify that as a heading, then
    strip the line as one and lose the post's first sentence.
    """
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(_H1_PREFIX):
            heading = stripped[len(_H1_PREFIX):].strip()
            return _truncate_at_word(heading, TITLE_MAX_CHARS) or fallback
        return _truncate_at_word(stripped, TITLE_MAX_CHARS)
    return fallback


def _section_text(lines: list[str], heading: str) -> str:
    """The text under `heading` up to the next "## " heading, or ""."""
    for i, line in enumerate(lines):
        if line.strip().lower() != heading:
            continue
        collected: list[str] = []
        for following in lines[i + 1:]:
            if following.strip().lower().startswith("## "):
                break
            collected.append(following)
        return _clean("\n".join(collected))
    return ""


def extract_primary_text(body: str) -> str:
    """The item's primary text -- what the excerpt and the comment drafter read.

    Structural rather than per-platform, so a future adapter writing the same
    sections inherits the behavior: prefer a transcript section, then a
    description section, then the whole remainder.
    """
    lines = body.splitlines()

    # Drop a leading H1 -- and only when it is a real "# " heading, i.e. exactly
    # when derive_title consumed it as the title.
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is not None and lines[first].strip().startswith(_H1_PREFIX):
        lines = lines[first + 1:]

    for heading in _SECTION_PREFERENCE:
        section = _section_text(lines, heading)
        if section:
            return section

    # A sectioned body whose sections were all placeholders has no primary text.
    # Falling through would return the section headers themselves as content.
    if any(line.strip().lower().startswith("## ") for line in lines):
        return ""

    return _clean("\n".join(lines))


def published_rank(published: str | None) -> tuple[int, int]:
    """Sort key giving newest-first under an ASCENDING sort, missing last.

    Returns (missing_flag, negated_yyyymmdd). Negating an int is what lets one
    ascending sorted() key mix descending dates with ascending tie-breaks.
    """
    if not isinstance(published, str):
        return (1, 0)
    digits = re.sub(r"\D", "", published)[:8]
    if len(digits) != 8:
        return (1, 0)
    return (0, -int(digits))
