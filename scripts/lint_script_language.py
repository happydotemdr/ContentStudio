"""Gate D — deterministic read-aloud lint for ContentStudio Short scripts.

Parses the voiceover lines out of the script format emitted by the
`shorts-scripting` skill and enforces the rules that are wrong unconditionally,
whatever the author intended: unspeakable punctuation, unspeakable tokens, and
beats with more words than fit in their seconds.

Rhythm and template judgments are deliberately NOT here -- whether a fragment
run is deliberate cadence or the model's default needs the whole script in view,
so it belongs to Gate E. See
docs/superpowers/specs/2026-08-06-script-language-naturalness-design.md.

Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

BEAT_LABELS = ("HOOK", "SETUP", "BUILD/VALUE", "PAYOFF", "LOOP/CTA")
BEAT_LABEL_RE = re.compile(r"^(HOOK|SETUP|BUILD/VALUE|PAYOFF|LOOP/CTA)\b")
REHOOK_RE = re.compile(r"^\[re-hook\b")
SUBRANGE_RE = re.compile(r"^\(\d+")
RANGE_RE = re.compile(r"\((\d+)\s*[–—-]\s*(\d+)s")
QUOTED_RE = re.compile(r'"([^"]+)"')


@dataclass(frozen=True)
class VOLine:
    beat: str
    line_number: int
    text: str
    start_s: int | None
    end_s: int | None


@dataclass(frozen=True)
class Finding:
    check: str
    beat: str | None
    message: str
    kind: str = "fail"


def word_count(text: str) -> int:
    """Whitespace tokens carrying at least one alphanumeric character.

    Excludes a standalone em-dash, which is punctuation the narrator does not
    speak -- counting it would inflate every wpm figure on a dashed line."""
    return sum(1 for token in text.split() if any(c.isalnum() for c in token))


def _beat_name(stripped: str) -> str | None:
    """The beat this line belongs to, or None if it is not a beat line at all."""
    label = BEAT_LABEL_RE.match(stripped)
    if label:
        return label.group(1)
    if REHOOK_RE.match(stripped):
        return "re-hook"
    if SUBRANGE_RE.match(stripped):
        return "sub-beat"
    return None


def parse_script(text: str) -> tuple[list[VOLine], list[Finding]]:
    """Return (VO lines in script order, coverage findings).

    A beat heading may legitimately carry no quoted text of its own -- BUILD and
    PAYOFF often delegate to indented sub-ranges beneath them. So coverage is
    tracked per top-level beat: a heading is satisfied by its own quoted span or
    by any beat line before the next top-level heading. A heading satisfied by
    neither means the parser is not seeing text that is there, which must fail
    loudly rather than silently shrink the linted surface."""
    vo_lines: list[VOLine] = []
    findings: list[Finding] = []

    current_label: str | None = None
    current_label_line = 0
    label_covered = True

    def close_label() -> None:
        if current_label is not None and not label_covered:
            findings.append(
                Finding(
                    "PARSE",
                    current_label,
                    f"beat heading at line {current_label_line} yielded no voiceover line",
                    kind="partial-parse",
                )
            )

    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        beat = _beat_name(stripped)
        if beat is None:
            continue

        is_top_level = BEAT_LABEL_RE.match(stripped) is not None
        if is_top_level:
            close_label()
            current_label = beat
            current_label_line = number
            label_covered = False

        quoted = QUOTED_RE.search(stripped)
        if quoted is None:
            continue

        label_covered = True
        span = RANGE_RE.search(stripped)
        vo_lines.append(
            VOLine(
                beat=current_label if beat == "sub-beat" and current_label else beat,
                line_number=number,
                text=quoted.group(1),
                start_s=int(span.group(1)) if span else None,
                end_s=int(span.group(2)) if span else None,
            )
        )

    close_label()
    return vo_lines, findings


DASH_RE = re.compile(r"[–—]")
# A semicolon is one written-register hit on its own. A parenthetical or
# bracketed aside is flagged as a single unit -- "(again)" is one written
# insertion, not two ("(" and ")" separately), so the two bracket
# characters are matched together with their enclosed span rather than as
# a bare `[;()\[\]]` character class (which would double-count every pair).
WRITTEN_PUNCT_RE = re.compile(r"[;]|\([^()]*\)|\[[^\[\]]*\]")


def check_punctuation(vo_lines: list[VOLine]) -> list[Finding]:
    """D1-D2: punctuation that exists only in written English.

    Scoped to the quoted spoken text, never the heading -- every beat heading
    carries an en-dash inside its own `(0–3s | N words)` range, which is not
    something anyone speaks aloud and not something to flag."""
    findings: list[Finding] = []
    for vo in vo_lines:
        if DASH_RE.search(vo.text):
            findings.append(
                Finding(
                    "D1",
                    vo.beat,
                    f"line {vo.line_number}: em/en-dash in a spoken line -- "
                    "a written parenthetical with no spoken realization",
                )
            )
        for match in WRITTEN_PUNCT_RE.finditer(vo.text):
            findings.append(
                Finding(
                    "D2",
                    vo.beat,
                    f"line {vo.line_number}: {match.group(0)!r} is written-register "
                    "punctuation in a spoken line",
                )
            )
    return findings
