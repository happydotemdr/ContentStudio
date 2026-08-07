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
from dataclasses import dataclass
from pathlib import Path

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
SEMICOLON_RE = re.compile(r";")


def _bracket_spans(text: str, open_char: str, close_char: str) -> list[str]:
    """One entry per top-level well-formed span, plus one per stray delimiter.

    A balanced top-level span -- e.g. "(again)", or the whole outer span of
    "(a (b) c)" -- yields ONE entry covering the full span; nested spans of
    the same bracket type are absorbed into their enclosing span rather than
    counted again. Any delimiter that never finds its match -- a stray close
    with nothing open, or an open that is never closed -- yields its own
    one-character entry. This is what keeps malformed input from silently
    producing zero findings: a naive regex over a matched-pair pattern simply
    fails to match "He signed (again" or "stray ] here" at all, so those
    unconsumed characters must be swept up explicitly."""
    entries: list[tuple[int, str]] = []
    stack: list[int] = []
    for i, ch in enumerate(text):
        if ch == open_char:
            stack.append(i)
        elif ch == close_char:
            if stack:
                start = stack.pop()
                if not stack:  # this close completed the outermost span
                    entries.append((start, text[start : i + 1]))
            else:
                entries.append((i, ch))  # stray close, nothing open
    entries.extend((i, open_char) for i in stack)  # opens never closed
    entries.sort(key=lambda entry: entry[0])
    return [snippet for _, snippet in entries]


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
        # Semicolons and bracket spans are scanned independently, by design.
        # D2's rule is "no semicolons, parentheticals, or bracketed asides" --
        # three distinct clauses. A semicolon that happens to sit inside a
        # parenthetical, e.g. "(guilty; wow)", violates two of them at once,
        # and fixing the line means removing both constructs -- so it is
        # deliberately reported as two findings, not deduplicated into one.
        snippets = [m.group(0) for m in SEMICOLON_RE.finditer(vo.text)]
        snippets += _bracket_spans(vo.text, "(", ")")
        snippets += _bracket_spans(vo.text, "[", "]")
        for snippet in snippets:
            findings.append(
                Finding(
                    "D2",
                    vo.beat,
                    f"line {vo.line_number}: {snippet!r} is written-register "
                    "punctuation in a spoken line",
                )
            )
    return findings


# Carried forward verbatim from the corpus's own no-list
# [C] (Romayroh, ErCV5czVK1g) via
# .claude/skills/shorts-scripting/references/script-intelligence-and-delivery.md
FINGERPRINT_PHRASES = (
    "it's important to note",
    "it is important to note",
    "some may argue",
)
BUZZWORDS = (
    "delve", "delves", "delving",
    "leverage", "leverages", "leveraged", "leveraging",
    "comprehensive", "comprehensively",
    "robust", "robustly",
    "holistic", "holistically",
)
BUZZWORD_RE = re.compile(r"\b(" + "|".join(BUZZWORDS) + r")\b", re.IGNORECASE)

# Tokens a text-to-speech voice cannot render as speech. These belong on an
# on-screen citation plate, never in a voiceover line.
UNSPEAKABLE = (
    (re.compile(r"&"), "ampersand"),
    (re.compile(r"§"), "section sign"),
    (re.compile(r"\b\w+\s*=\s*\d"), "an inline statistic like n=142"),
    (re.compile(r"\d+\(\d+\):\d+"), "a journal citation string"),
)


def check_vocabulary(vo_lines: list[VOLine]) -> list[Finding]:
    """D3-D4: the corpus buzzword no-list, and tokens TTS cannot speak."""
    findings: list[Finding] = []
    for vo in vo_lines:
        lowered = vo.text.lower()
        for phrase in FINGERPRINT_PHRASES:
            if phrase in lowered:
                findings.append(
                    Finding("D3", vo.beat, f"line {vo.line_number}: AI-fingerprint phrase {phrase!r}")
                )
        for match in BUZZWORD_RE.finditer(vo.text):
            findings.append(
                Finding("D3", vo.beat, f"line {vo.line_number}: buzzword {match.group(0)!r}")
            )
        for pattern, label in UNSPEAKABLE:
            if pattern.search(vo.text):
                findings.append(
                    Finding(
                        "D4",
                        vo.beat,
                        f"line {vo.line_number}: {label} in a spoken line -- "
                        "belongs on an on-screen plate",
                    )
                )
    return findings


WPM_CEILING = 170
WPM_TOLERANCE = 2


def beat_wpm(vo: VOLine) -> float | None:
    """Words per minute implied by this beat, or None if it carries no range."""
    if vo.start_s is None or vo.end_s is None:
        return None
    duration = vo.end_s - vo.start_s
    if duration <= 0:
        return None
    return word_count(vo.text) / duration * 60


def check_pace(vo_lines: list[VOLine]) -> list[Finding]:
    """D5: a ceiling, not a band.

    Under-running is a legitimate authorial choice -- the corpus asks for
    breathing room so a key word lands [C] (Kallaway, ZM3elcBE48I), and shipped
    scripts run a Loop/CTA at ~103 wpm on purpose. Over-running is a production
    failure: the line cannot be spoken in its seconds, and the bad timing
    propagates into voiceover-brief and shorts-assembly unchallenged."""
    limit = WPM_CEILING + WPM_TOLERANCE
    findings: list[Finding] = []
    for vo in vo_lines:
        wpm = beat_wpm(vo)
        if wpm is None:
            # Same `skipped` kind either way -- only the message text
            # distinguishes a range that was never parsed (old-format
            # re-hook line) from one that parsed but is malformed (start >=
            # end), so a reader isn't told "missing" when the beat actually
            # carries a nonsensical range.
            if vo.start_s is not None and vo.end_s is not None and vo.end_s <= vo.start_s:
                reason = (
                    f"malformed time range ({vo.start_s}–{vo.end_s}s, start >= end); "
                    "pace unchecked"
                )
            else:
                reason = "no computable time range; pace unchecked"
            findings.append(
                Finding(
                    "D5",
                    vo.beat,
                    f"line {vo.line_number}: {reason}",
                    kind="skipped",
                )
            )
            continue
        if wpm > limit:
            findings.append(
                Finding(
                    "D5",
                    vo.beat,
                    f"line {vo.line_number}: {wpm:.0f} wpm exceeds the {WPM_CEILING} ceiling "
                    f"(+{WPM_TOLERANCE} tolerance) -- more words than fit in the beat",
                )
            )
    return findings


GATE_E_RE = re.compile(r"^\s*Gate E\b[^:]*:\s*(\S.*)$", re.MULTILINE)


def check_gate_e_reported(text: str) -> list[Finding]:
    """D6 -- the honesty lock.

    This cannot prove Gate E ran; a skill that skipped it can still write
    `Gate E: pass`. It raises the cost of the omission from silent to
    deliberate, and no further. See the spec's "Known limits"."""
    if GATE_E_RE.search(text):
        return []
    return [
        Finding(
            "D6",
            None,
            "no well-formed `Gate E: <result>` line in the artifact -- "
            "a gate that was not reported is a gate that was not run",
        )
    ]


def lint(vo_lines: list[VOLine], text: str, parse_findings: list[Finding] | None = None) -> list[Finding]:
    """Run every Gate D check, in check order."""
    return [
        *(parse_findings or []),
        *check_punctuation(vo_lines),
        *check_vocabulary(vo_lines),
        *check_pace(vo_lines),
        *check_gate_e_reported(text),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_script_language",
        description="Gate D -- read-aloud lint for ContentStudio Short scripts.",
    )
    parser.add_argument("script", type=Path, help="path to an emitted Short script (.md)")
    args = parser.parse_args(argv)

    text = args.script.read_text(encoding="utf-8")
    vo_lines, parse_findings = parse_script(text)
    if not vo_lines:
        print(f"Gate D: no voiceover lines parsed from {args.script}. Check the script format.")
        return 2

    findings = lint(vo_lines, text, parse_findings)
    blocking = [f for f in findings if f.kind != "skipped"]
    skipped = [f for f in findings if f.kind == "skipped"]

    for finding in skipped:
        print(f"  [skipped] {finding.beat or 'script'}: {finding.message}")

    if not blocking:
        print(f"Gate D: PASS -- {len(vo_lines)} voiceover lines, 0 findings.")
        return 0

    print(f"Gate D: FAIL -- {len(vo_lines)} voiceover lines, {len(blocking)} finding(s).")
    for finding in blocking:
        print(f"  [{finding.check}] {finding.beat or 'script'}: {finding.message}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
