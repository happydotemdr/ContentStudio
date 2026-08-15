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

BEAT_LABELS = ("HOOK", "SETUP", "BUILD/VALUE", "PAYOFF", "LOOP/CTA")
BEAT_LABEL_RE = re.compile(r"^(HOOK|SETUP|BUILD/VALUE|PAYOFF|LOOP/CTA)\b")
# Leading markdown furniture a heading can hide behind: blockquote, ATX heading,
# list bullet, bold/italic/underscore emphasis, inline code.
_MARKDOWN_LEAD_RE = re.compile(r"^[\s>#*_+`~-]+")
# After the furniture is stripped, a genuine heading still carries its range or
# its colon. Requiring one of those is what keeps a prose line that merely names
# a beat ("- LOOP/CTA mirrors the hook") from false-failing.
_SUSPECT_HEADING_RE = re.compile(
    r"^(HOOK|SETUP|BUILD/VALUE|PAYOFF|LOOP/CTA)\b[^\n]*[(:]"
)
REHOOK_RE = re.compile(r"^\[re-hook\b")
SUBRANGE_RE = re.compile(r"^\(\d+")
RANGE_RE = re.compile(r"\((\d+)\s*[–—-]\s*(\d+)s")
# Straight AND curly quote pairs. A lone apostrophe (' or ’) is deliberately
# NOT a delimiter: it is a letter's neighbour in "won't" / "kid’s", not a span
# boundary, and treating it as one would shred every contraction in the corpus.
QUOTED_RE = re.compile(r'"([^"]+)"|“([^”]+)”')
# Every beat heading states its own budget as `| N words`. That declaration is
# the only independent witness to how much spoken text the line is supposed to
# contain, and it is what the dropped-text detector below measures against.
DECLARED_WORDS_RE = re.compile(r"\|\s*(\d+)\s*words")
# A refused sub-beat's tell: a `(start-end)` range that does not start the
# line -- e.g. `mechanism (11-18s | 19 words):` -- fails SUBRANGE_RE (which
# requires the range to open the line) and names no BEAT_LABEL either, so it
# falls through both `_beat_name` and `_disguised_beat_label` unrecognised.
# The anchor here is the budget group, not the range: measured identical
# precision against the 4 shipped fixtures (2/2 true positives, 0 false
# positives) to a `RANGE_RE and DECLARED_WORDS_RE` anchor, and it additionally
# catches `mechanism (11-18 sec | 19 words):`, whose non-standard range suffix
# a RANGE_RE anchor misses outright.
BUDGET_GROUP_RE = re.compile(r"\([^)\n]*\|\s*\d+\s*words[^)\n]*\)")


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


def _disguised_beat_label(stripped: str) -> str | None:
    """The beat a line NAMES if it is a heading the parser refused, else None.

    This is the fail-closed half of the parser. `_beat_name` answers "is this a
    beat?"; this answers "did something that looks exactly like a beat just fall
    through?". A heading the parser cannot read must be a finding, never a
    deletion -- a deleted beat takes every D-check over it with it, and the
    coverage machinery below can only fire for headings it already recognised.

    Known limit, stated rather than papered over: a disguised heading carrying
    neither a `(` nor a `:` is not detected here. The five-label cross-check in
    `check_beat_set` is the independent second detector for that case."""
    unstyled = _MARKDOWN_LEAD_RE.sub("", stripped).replace("**", "").replace("__", "").lstrip()
    match = _SUSPECT_HEADING_RE.match(unstyled)
    return match.group(1) if match else None


# The dropped-text threshold. Calibrated against the declared-vs-counted spread
# measured over all 27 VO lines in tests/fixtures/script_*.md: the worst
# under-count there is 2 words absolute (let-kids-play-act's BUILD/VALUE group,
# 51 declared vs 49 extracted) and 9.1% relative (its LOOP/CTA, 11 vs 10).
# Those gaps are the authors' own rounding, not dropped text.
#
# Both conditions must hold, and each guards the other's blind spot: the
# absolute floor stops a 1-word rounding gap on a 4-word beat from firing, and
# the fraction stops a 3-word gap on a 60-word beat from firing. Real dropped
# text is not subtle -- a swallowed sub-beat or an unclosed quoted span loses a
# third to a half of the beat, several times the widest gap any shipped script
# produces. An OVER-count never fires: more words than declared is a stale
# heading number, not evidence the parser missed something.
DROPPED_TEXT_MIN_WORDS = 3
DROPPED_TEXT_MIN_FRACTION = 0.25


def _is_dropped_text(declared: int, counted: int) -> bool:
    shortfall = declared - counted
    return (
        shortfall >= DROPPED_TEXT_MIN_WORDS
        and shortfall >= DROPPED_TEXT_MIN_FRACTION * declared
    )


def _quoted_spans(stripped: str) -> list[str]:
    """Every quoted span on the line, straight or curly, in order.

    `.search()` would return only the first, which is the silent
    under-extraction this parser exists to avoid: a beat line carrying two
    quoted spans, or a nested quote like `"He said "quit" and walked away —
    done."`, would have its tail dropped -- taking the tail's em-dashes out of
    D1's reach and collapsing D5's word count so an over-stuffed beat reads as
    comfortable."""
    return [
        m.group(1) if m.group(1) is not None else m.group(2)
        for m in QUOTED_RE.finditer(stripped)
    ]


def parse_script(text: str) -> tuple[list[VOLine], list[Finding]]:
    """Return (VO lines in script order, coverage findings).

    A beat heading may legitimately carry no quoted text of its own -- BUILD and
    PAYOFF often delegate to indented sub-ranges beneath them. So coverage is
    tracked per top-level beat: a heading is satisfied by its own quoted span or
    by any beat line before the next top-level heading. A heading satisfied by
    neither means the parser is not seeing text that is there, which must fail
    loudly rather than silently shrink the linted surface.

    Coverage alone is too coarse, though: a sub-beat swallowed whole leaves its
    heading covered by a *sibling* sub-beat and produces no finding at all. So
    every declared `| N words` budget is also measured against the words
    actually extracted under it -- per top-level group for a heading (whose
    budget is the sum across its sub-beats), and per line for a sub-beat that
    declares its own. A material shortfall is a `partial-parse` finding: the
    parser saying out loud that it is linting less text than the script
    contains.

    A sub-beat line SUBRANGE_RE refuses (its range does not start the line,
    e.g. a label-first `mechanism (11-18s | 19 words):`) is also refused loud
    rather than deleted silent, on the same principle as a disguised top-level
    heading -- but only when it carries its own `| N words` budget group,
    the author's own assertion that the line is a beat line. Known limit,
    stated rather than papered over: a refused sub-beat line carrying no
    budget group is not detected here. The dropped-text check above is the
    independent second detector for that case, when the sub-beat's own
    budget or its parent group's budget survives on a nearby line."""
    vo_lines: list[VOLine] = []
    findings: list[Finding] = []

    current_label: str | None = None
    current_label_line = 0
    label_covered = True
    group_declared: int | None = None
    group_counted = 0

    def close_label() -> None:
        if current_label is None:
            return
        if not label_covered:
            findings.append(
                Finding(
                    "PARSE",
                    current_label,
                    f"beat heading at line {current_label_line} yielded no voiceover line",
                    kind="partial-parse",
                )
            )
            return
        if group_declared is not None and _is_dropped_text(group_declared, group_counted):
            findings.append(
                Finding(
                    "PARSE",
                    current_label,
                    f"beat heading at line {current_label_line} declares {group_declared} "
                    f"words but only {group_counted} were extracted from it and its "
                    "sub-beats -- the parser is not seeing spoken text that is there",
                    kind="partial-parse",
                )
            )

    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        beat = _beat_name(stripped)
        if beat is None:
            disguised = _disguised_beat_label(stripped)
            if disguised is not None:
                findings.append(
                    Finding(
                        "PARSE",
                        disguised,
                        f"line {number}: {stripped[:70]!r} names beat {disguised} but is "
                        "not a parseable beat heading -- strip the markdown styling so the "
                        "line begins with the bare label",
                        kind="fail",
                    )
                )
            elif current_label is not None and BUDGET_GROUP_RE.search(stripped):
                findings.append(
                    Finding(
                        "PARSE",
                        current_label,
                        f"line {number}: {stripped[:70]!r} carries a word budget but is not "
                        "a parseable sub-beat line -- SUBRANGE_RE requires the range to "
                        "start the line; move the label after the colon or drop it",
                        kind="fail",
                    )
                )
            continue

        declared_match = DECLARED_WORDS_RE.search(stripped)
        declared = int(declared_match.group(1)) if declared_match else None

        is_top_level = BEAT_LABEL_RE.match(stripped) is not None
        if is_top_level:
            close_label()
            current_label = beat
            current_label_line = number
            label_covered = False
            group_declared = declared
            group_counted = 0

        spans = _quoted_spans(stripped)
        counted = sum(word_count(span) for span in spans)
        group_counted += counted

        # A top-level heading's budget covers its whole group (BUILD/VALUE
        # declares the sum of its sub-ranges), so it is settled in close_label
        # once the group is complete -- checking it here would fire on every
        # heading that delegates to sub-beats.
        if not is_top_level and declared is not None and _is_dropped_text(declared, counted):
            findings.append(
                Finding(
                    "PARSE",
                    current_label or beat,
                    f"line {number} declares {declared} words but only {counted} were "
                    "extracted from its quoted span(s) -- the parser is not seeing "
                    "spoken text that is there",
                    kind="partial-parse",
                )
            )

        if not spans:
            continue

        label_covered = True
        span = RANGE_RE.search(stripped)
        # Multiple spans on one beat line are joined into ONE VOLine rather
        # than split into several. The beat line is the unit the script
        # declares (`| N words`) and the unit D5 rates against a single time
        # range; splitting would fragment one range across several lines and
        # inflate the VO-line count that the baseline inventory and the
        # calibration fixtures are pinned to.
        vo_lines.append(
            VOLine(
                beat=current_label if beat == "sub-beat" and current_label else beat,
                line_number=number,
                text=" ".join(spans),
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
# The five lemmas are the corpus's, verbatim: delve, leverage, comprehensive,
# robust, holistic. Only their inflections are enumerated here -- adding a sixth
# lemma would be inventing corpus content, which this project's central rule
# forbids. Each lemma is carried to its full set: verb forms for delve and
# leverage, adverb and nominalization for the adjectives. "holistic" has no
# nominalization on its own stem ("holism" is a different word, so it is not
# listed rather than smuggled in as an inflection).
#
# Longest-first ordering is deliberate: `\b(robust|robustness)\b` still matches
# "robustness" via backtracking, but ordering the alternation by descending
# length makes the intended match obvious instead of load-bearing on regex
# engine behaviour.
BUZZWORDS = (
    "delving", "delved", "delves", "delve",
    "leveraging", "leveraged", "leverages", "leverage",
    "comprehensiveness", "comprehensively", "comprehensive",
    "robustness", "robustly", "robust",
    "holistically", "holistic",
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


def check_beat_set(vo_lines: list[VOLine]) -> list[Finding]:
    """Every one of the five top-level beats must have produced a spoken line.

    Independent of `_disguised_beat_label`, deliberately: two detectors with
    different failure modes means an evasion has to beat both. All four shipped
    scripts carry all five labels, so this is calibrated on real artifacts, not
    invented."""
    seen = {vo.beat for vo in vo_lines}
    missing = [label for label in BEAT_LABELS if label not in seen]
    if not missing:
        return []
    return [
        Finding(
            "PARSE",
            None,
            f"no voiceover line parsed for beat(s) {', '.join(missing)} -- either the "
            "script is missing them or their headings did not parse; a gate that never "
            "saw a beat did not check it",
            kind="fail",
        )
    ]


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
    propagates into voiceover-brief and shorts-assembly unchallenged.

    One unratable beat is a known unknown -- reported `skipped`, non-blocking.
    A script where NOTHING is ratable is not a known unknown, it is a format
    failure: D5 checked nothing at all, and a gate that checked nothing must
    not be reported as a gate that passed."""
    limit = WPM_CEILING + WPM_TOLERANCE
    findings: list[Finding] = []
    rated = 0
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
        rated += 1
        if wpm > limit:
            findings.append(
                Finding(
                    "D5",
                    vo.beat,
                    f"line {vo.line_number}: {wpm:.0f} wpm exceeds the {WPM_CEILING} ceiling "
                    f"(+{WPM_TOLERANCE} tolerance) -- more words than fit in the beat",
                )
            )
    if vo_lines and rated == 0:
        findings.append(
            Finding(
                "D5",
                None,
                f"not one of the {len(vo_lines)} voiceover lines carries a readable time "
                "range, so the wpm ceiling was never checked on this script -- every beat "
                "heading needs a `(<start>–<end>s | N words)` range, e.g. "
                "`(0–3s | 8 words)`. A gate that rated nothing is not a gate that passed",
            )
        )
    return findings


GATE_E_RE = re.compile(r"^\s*Gate E\b[^:]*:\s*(\S.*)$", re.MULTILINE)
# A value still wrapped in <…> or […] is the output contract's own slot, not a
# result. So is one that still carries the template's `|` alternation bars --
# no genuine result ("pass", "3 findings", "2 findings, 1 defended",
# "overridden: <why>") contains one.
PLACEHOLDER_WRAPPED_RE = re.compile(r"^<.*>$|^\[.*\]$", re.DOTALL)


def _is_unfilled_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_WRAPPED_RE.match(value)) or "|" in value


def check_gate_e_reported(text: str) -> list[Finding]:
    """D6 -- the honesty lock.

    This cannot prove Gate E ran; a skill that skipped it can still write
    `Gate E: pass`. It raises the cost of the omission from silent to
    deliberate, and no further. See the spec's "Known limits".

    What it CAN refuse is the zero-cost defeat: pasting the output contract's
    own placeholder unchanged. `<pass | N findings | N defended | overridden:
    reason>` is a slot, not a result, and accepting it would let a skill
    satisfy the lock without deciding anything at all -- weaker even than
    "silent to deliberate"."""
    values = [m.group(1).strip() for m in GATE_E_RE.finditer(text)]
    if any(not _is_unfilled_placeholder(value) for value in values):
        return []
    if values:
        return [
            Finding(
                "D6",
                None,
                f"the `Gate E:` line still holds the unfilled output-contract "
                f"placeholder ({values[0]!r}) -- pasting the template is not reporting "
                "a result; write what the critic actually returned",
            )
        ]
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
        *check_beat_set(vo_lines),
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
