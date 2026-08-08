"""Drafts three short comments on one social post, for the daily email's
spotlight section, by running a single tool-less `claude -p` turn.

Never raises. Every failure path returns [] and the email still sends with the
spotlight rendered minus its drafts.

WHAT IS GUARANTEED AND WHAT IS NOT. The no-dash rule and the length cap are
enforced HERE, in code, after generation -- a prompt instruction is a request,
and the user specified the dash rule as absolute. The "positive, nothing
negative or derogatory" constraint is prompt-enforced ONLY: it cannot be
verified programmatically, and a keyword blocklist would miss real negativity
while false-positiving on ordinary words. The email labels these as drafts for
review; the reader is the check on tone.

See docs/superpowers/specs/2026-08-08-morning-email-social-expansion-design.md.
"""
from __future__ import annotations

import re

DRAFT_COUNT = 3
MAX_DRAFT_CHARS = 300
# Below this a truncated draft is not worth showing; drop it and fail the batch.
MIN_DRAFT_CHARS = 40

# U+2014 em dash, U+2013 en dash, and any run of two or more hyphens.
_DASH_RE = re.compile(r"[—–]|-{2,}")


def strip_dashes(text: str) -> str:
    """Every em dash, en dash, and double-hyphen replaced with a comma.

    Runs unconditionally on every draft, so the rule cannot leak regardless of
    what the model returns. A SINGLE hyphen is preserved: "well-known" is not
    a dash.
    """
    out = _DASH_RE.sub(", ", text)
    out = re.sub(r"\s+", " ", out)
    # ", ." -> "." and ", ," -> "," : the substitution above can land a comma
    # immediately before existing punctuation.
    out = re.sub(r",\s*(?=[.,!?])", "", out)
    out = re.sub(r"\s+([.,!?])", r"\1", out)
    return out.strip().strip(",").strip()


def cap_length(text: str) -> str | None:
    """The draft at or under MAX_DRAFT_CHARS, or None if unusable."""
    stripped = text.strip()
    if len(stripped) <= MAX_DRAFT_CHARS:
        return stripped if len(stripped) >= MIN_DRAFT_CHARS else None
    cut = stripped[:MAX_DRAFT_CHARS]
    boundary = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    if boundary + 1 < MIN_DRAFT_CHARS:
        return None
    return cut[:boundary + 1].strip()


def sanitize_drafts(raw: list) -> list[str]:
    """Exactly DRAFT_COUNT clean drafts, or [].

    Three or nothing: a spotlight showing two drafts where three were promised
    reads as a bug, and partial output is not worth the ambiguity.
    """
    if not isinstance(raw, list) or len(raw) != DRAFT_COUNT:
        return []
    cleaned: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            return []
        capped = cap_length(strip_dashes(entry))
        if capped is None:
            return []
        cleaned.append(capped)
    return cleaned
