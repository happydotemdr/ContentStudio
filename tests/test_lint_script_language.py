import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lint_script_language import (  # noqa: E402
    VOLine,
    Finding,
    parse_script,
    word_count,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


SCRIPT = """\
=== SHORT SCRIPT — demo ===

HOOK        (0–3s  | 7 words): "It won't set him back. Not athletically."
SETUP       (3–8s  | 8 words) — *narrator enters*: "Kids do that, every single time."
BUILD/VALUE (8–28s | 20 words):
  (8–18s | 12 words): "A position stand reports that samplers still reach elite level."
  [re-hook beat @ ~18s] (18–21s | 8 words): "But the offer isn't really about your kid."
[re-hook beat @ ~15s]: "His proof: a trader who bought every oil press in town."
LOOP/CTA    (38–45s | 5 words, mirrors hook): "It won't set him back."
Comment-bait question: "What tier were you offered?"
"""


def test_parses_every_vo_line_form():
    lines, _ = parse_script(SCRIPT)
    assert [vo.text for vo in lines] == [
        "It won't set him back. Not athletically.",
        "Kids do that, every single time.",
        "A position stand reports that samplers still reach elite level.",
        "But the offer isn't really about your kid.",
        "His proof: a trader who bought every oil press in town.",
        "It won't set him back.",
    ]


def test_comment_bait_is_not_a_vo_line():
    lines, _ = parse_script(SCRIPT)
    assert all("What tier" not in vo.text for vo in lines)


def test_reads_beat_ranges():
    lines, _ = parse_script(SCRIPT)
    assert (lines[0].beat, lines[0].start_s, lines[0].end_s) == ("HOOK", 0, 3)
    assert (lines[3].beat, lines[3].start_s, lines[3].end_s) == ("re-hook", 18, 21)


def test_old_format_rehook_has_no_range():
    lines, _ = parse_script(SCRIPT)
    old = lines[4]
    assert old.beat == "re-hook"
    assert old.start_s is None and old.end_s is None


def test_word_count_ignores_standalone_dashes():
    # NOTE: the task-1 brief asserts `== 8` here, but that is an off-by-one
    # error in the brief itself. The string tokenizes to 8 whitespace-
    # separated tokens, one of which is a standalone em dash ("—") with no
    # alphanumeric character -- per this project's own word-counting rule
    # (see CLAUDE.md / the task-1 brief's "GLOBAL CONSTRAINTS": "a 'word' is
    # a whitespace-separated token containing at least one alphanumeric
    # character. This excludes a standalone —"), that token must not count.
    # 8 tokens - 1 excluded dash = 7. Verified by hand-tracing the brief's
    # own `word_count` implementation against this exact string.
    assert word_count("isn't more serious play — it's constrained labor") == 7


def test_shipped_fixtures_parse_to_expected_counts():
    expected = {
        "script_let_kids_play_act.md": 6,
        "script_specialization.md": 6,
        "script_decline.md": 7,
        "script_nobody_asked.md": 8,
    }
    for name, count in expected.items():
        lines, _ = parse_script(_read(name))
        assert len(lines) == count, f"{name}: got {len(lines)}"


def test_zero_vo_lines_yields_no_lines():
    lines, findings = parse_script("just prose, no beats at all\n")
    assert lines == []
    assert findings == []


def test_beat_heading_with_no_quoted_line_anywhere_is_partial_parse():
    text = 'HOOK        (0–3s  | 7 words):\nSETUP (3–8s | 4 words): "A real spoken line."\n'
    _, findings = parse_script(text)
    assert [f.kind for f in findings] == ["partial-parse"]
    assert findings[0].beat == "HOOK"
