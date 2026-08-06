import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lint_script_language import (  # noqa: E402
    VOLine,
    Finding,
    parse_script,
    word_count,
    check_punctuation,
    check_vocabulary,
    check_pace,
    beat_wpm,
    WPM_CEILING,
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


def test_d1_flags_em_dash_in_vo_line():
    lines, _ = parse_script(
        'HOOK (0–3s | 9 words): "An activity done for a result — constrained labor."\n'
    )
    findings = check_punctuation(lines)
    assert [f.check for f in findings] == ["D1"]


def test_d1_flags_en_dash_in_vo_line():
    lines, _ = parse_script('HOOK (0–3s | 5 words): "It won\'t – set him back."\n')
    assert [f.check for f in check_punctuation(lines)] == ["D1"]


def test_d1_ignores_the_en_dash_in_the_beat_heading():
    lines, _ = parse_script('HOOK (0–3s | 5 words): "It won\'t set him back."\n')
    assert check_punctuation(lines) == []


def test_d1_allows_hyphens():
    lines, _ = parse_script('HOOK (0–3s | 6 words): "Multi-sport players had longer careers."\n')
    assert check_punctuation(lines) == []


def test_d2_flags_semicolons_and_brackets():
    lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "He signed; then he quit (again)."\n'
    )
    checks = sorted(f.check for f in check_punctuation(lines))
    assert checks == ["D2", "D2"]


def test_d1_counts_on_shipped_fixtures():
    expected = {
        "script_let_kids_play_act.md": 4,
        "script_specialization.md": 1,
        "script_decline.md": 2,
        "script_nobody_asked.md": 0,
    }
    for name, count in expected.items():
        lines, _ = parse_script(_read(name))
        d1 = [f for f in check_punctuation(lines) if f.check == "D1"]
        assert len(d1) == count, f"{name}: got {len(d1)}"


def test_d2_is_clean_on_every_shipped_fixture():
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        lines, _ = parse_script(_read(name))
        assert [f for f in check_punctuation(lines) if f.check == "D2"] == [], name


def test_scope_containment_prose_and_notes_never_fire_d1():
    """The check most likely to regress into noise.

    A shipped script's prose, Delivery notes, quote cards, and on-screen plates
    are written English and legitimately full of em-dashes. Only the quoted
    spoken text is in scope. script_nobody_asked.md has dozens of em-dashes in
    its prose and exactly zero in its voiceover lines -- if D1 ever fires on it,
    the parser has leaked out of the VO lines."""
    text = _read("script_nobody_asked.md")
    assert text.count("—") > 20, "fixture no longer exercises the containment case"
    lines, _ = parse_script(text)
    assert [f for f in check_punctuation(lines) if f.check == "D1"] == []


def test_a_verbatim_quote_card_in_prose_never_fires_d1():
    text = (
        "### The one quote card, verbatim\n\n"
        "> \"it becomes constrained labor when the consequences are outside\"\n"
        "> — John Dewey, *Democracy and Education*, 1916\n\n"
        'HOOK (0–3s | 5 words): "It will not set him back."\n'
    )
    lines, _ = parse_script(text)
    assert check_punctuation(lines) == []


def test_d2_flags_unbalanced_open_paren():
    lines, _ = parse_script('HOOK (0–3s | 4 words): "He signed (again"\n')
    checks = [f.check for f in check_punctuation(lines)]
    assert checks == ["D2"]


def test_d2_flags_stray_closing_bracket():
    lines, _ = parse_script('HOOK (0–3s | 3 words): "stray ] here"\n')
    checks = [f.check for f in check_punctuation(lines)]
    assert checks == ["D2"]


def test_d2_flags_nested_parens_as_one_outer_span():
    lines, _ = parse_script('HOOK (0–3s | 4 words): "nested (a (b) c)"\n')
    findings = check_punctuation(lines)
    assert [f.check for f in findings] == ["D2"]
    assert "(a (b) c)" in findings[0].message


def test_d2_reports_semicolon_and_parenthetical_separately_when_nested():
    """A semicolon nested inside a parenthetical, e.g. "(guilty; wow)",
    violates two distinct clauses of the D2 rule at once -- "no semicolons"
    and "no parentheticals" -- and an author fixing the line has to remove
    both constructs. This is deliberate: semicolons and bracket spans are
    scanned independently, so overlapping/nested text is reported once per
    clause it violates rather than deduplicated into a single finding. This
    pins that behavior against silent drift (e.g. an editor "optimizing" the
    scan into one combined pass that only flags the outer span)."""
    lines, _ = parse_script('HOOK (0–3s | 3 words): "settled (guilty; wow)"\n')
    findings = check_punctuation(lines)
    assert findings == [
        Finding(
            "D2",
            "HOOK",
            "line 1: ';' is written-register punctuation in a spoken line",
        ),
        Finding(
            "D2",
            "HOOK",
            "line 1: '(guilty; wow)' is written-register punctuation in a spoken line",
        ),
    ]


def test_d3_flags_fingerprint_phrases():
    lines, _ = parse_script(
        'HOOK (0–3s | 9 words): "It\'s important to note that some may argue otherwise."\n'
    )
    assert sorted(f.check for f in check_vocabulary(lines)) == ["D3", "D3"]


def test_d3_flags_buzzwords_and_their_inflections():
    lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "We leveraged a comprehensive and robust approach."\n'
    )
    assert len([f for f in check_vocabulary(lines) if f.check == "D3"]) == 3


def test_d3_does_not_flag_hackfort_the_surname():
    lines, _ = parse_script('HOOK (0–3s | 5 words): "Côté, Lidor and Hackfort reported."\n')
    assert check_vocabulary(lines) == []


def test_d4_flags_unspeakable_tokens():
    lines, _ = parse_script(
        'HOOK (0–3s | 7 words): "The study had n=142 kids & 37 coaches."\n'
    )
    assert len([f for f in check_vocabulary(lines) if f.check == "D4"]) == 2


def test_d4_flags_a_journal_citation_string():
    lines, _ = parse_script('HOOK (0–3s | 4 words): "See 12(3):424–433 for details."\n')
    assert [f.check for f in check_vocabulary(lines) if f.check == "D4"] == ["D4"]


def test_d3_and_d4_are_clean_on_every_shipped_fixture():
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        lines, _ = parse_script(_read(name))
        assert check_vocabulary(lines) == [], name


def test_d5_flags_an_over_stuffed_beat():
    lines, _ = parse_script(
        'HOOK (0–3s | 13 words): "Why would a federal proposal count your kid registration app '
        'as youth sports?"\n'
    )
    findings = [f for f in check_pace(lines) if f.kind == "fail"]
    assert [f.check for f in findings] == ["D5"]
    assert "260" in findings[0].message


def test_d5_does_not_flag_an_under_running_beat():
    lines, _ = parse_script('LOOP/CTA (38–45s | 12 words): "You are not taking something away."\n')
    assert [f for f in check_pace(lines) if f.kind == "fail"] == []


def test_d5_tolerance_passes_a_beat_at_171_wpm():
    # 20 words in 7s = 171.4 wpm -- the Dewey sub-beat, "within rounding".
    #
    # NOTE: the task-4 brief's own quoted spoken text for this beat is only
    # 16 words ("Dewey named this in 1916 an activity done for a result
    # outside itself is constrained labor.") despite its heading claiming
    # "20 words" -- 16/7*60 ~= 137 wpm, which would make the very assertion
    # below (`beat_wpm(lines[0]) > 170`) fail. word_count() counts the real
    # quoted text, not the heading's claim (see word_count's docstring and
    # test_word_count_ignores_standalone_dashes above for the same
    # heading-vs-body discipline). Per the task-4 brief's own instructions
    # for this exact contradiction, the spoken text below has been lengthened
    # to genuinely contain 20 words so the heading and the body agree, and so
    # the beat genuinely computes to ~171.4 wpm -- just over the 170 ceiling
    # and inside the +/-2 tolerance. The assertions, the beat range (21-28s),
    # the ceiling, and the tolerance are all unchanged from the brief.
    text = (
        'BUILD/VALUE (21–28s | 20 words): "Dewey named this back in 1916 as an activity done for a '
        'result that is outside itself and constrained labor."\n'
    )
    lines, _ = parse_script(text)
    assert beat_wpm(lines[0]) > 170
    assert [f for f in check_pace(lines) if f.kind == "fail"] == []


def test_d5_skips_a_beat_with_no_range_and_says_so():
    lines, _ = parse_script('[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n')
    findings = check_pace(lines)
    assert [f.kind for f in findings] == ["skipped"]
    assert findings[0].check == "D5"


def test_d5_counts_on_shipped_fixtures():
    expected = {
        "script_let_kids_play_act.md": 1,
        "script_specialization.md": 2,
        "script_decline.md": 0,
        "script_nobody_asked.md": 0,
    }
    for name, count in expected.items():
        lines, _ = parse_script(_read(name))
        fails = [f for f in check_pace(lines) if f.kind == "fail"]
        assert len(fails) == count, f"{name}: got {len(fails)}"
