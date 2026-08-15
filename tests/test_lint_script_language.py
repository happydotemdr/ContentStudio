import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lint_script_language import (  # noqa: E402
    VOLine,
    Finding,
    parse_script,
    word_count,
    check_punctuation,
    check_vocabulary,
    check_pace,
    check_beat_set,
    beat_wpm,
    WPM_CEILING,
    check_gate_e_reported,
    lint,
    main,
    is_blocking,
    NON_BLOCKING_KINDS,
    BUZZWORD_LEMMAS,
    BUZZWORDS,
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


def test_a_bolded_beat_label_is_a_blocking_parse_finding():
    """C-88 fault test. `**HOOK**` is a heading to every human who reads the
    script and to nobody in the parser. It used to delete the beat and every
    check over it, silently. It must now block."""
    text = (
        '**HOOK**   (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP      (3–8s | 6 words): "Kids do that every single time."\n'
    )
    lines, findings = parse_script(text)
    assert [vo.beat for vo in lines] == ["SETUP"]
    assert [(f.check, f.beat, f.kind) for f in findings] == [("PARSE", "HOOK", "fail")]
    assert "not a parseable beat heading" in findings[0].message


def test_a_disguised_heading_is_distinguishable_from_a_script_that_omits_it():
    """C-88 distinguishability test. A script that never had a HOOK and a script
    whose HOOK the parser refused must not produce the same finding set."""
    disguised = '## HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
    absent = 'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
    _, disguised_findings = parse_script(disguised)
    _, absent_findings = parse_script(absent)
    assert disguised_findings != absent_findings
    assert [f.beat for f in disguised_findings] == ["HOOK"]
    assert absent_findings == []


def test_prose_that_merely_mentions_a_beat_label_is_not_a_disguised_heading():
    """The heuristic's guard rail: a notes line reading `- LOOP/CTA mirrors the
    hook` carries no range and no colon, so it is prose, not a refused heading."""
    text = (
        'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        "- LOOP/CTA mirrors the hook by design\n"
    )
    _, findings = parse_script(text)
    assert findings == []


def test_a_label_first_sub_beat_is_a_blocking_parse_finding():
    """C-88b fault test. `mechanism (18-28s | 19 words)` is a label-first
    sub-beat: SUBRANGE_RE requires the range to start the line, so this line
    falls through `_beat_name` unrecognised -- and unlike T1's disguised
    top-level headings, it names no BEAT_LABEL either, so `_disguised_beat_label`
    does not catch it. It carries its own `| N words` budget group, the
    author's own assertion that this is a beat line -- so refusing it must be
    a loud finding, not a silent deletion."""
    text = (
        "BUILD/VALUE (8–28s | 20 words):\n"
        '  (8–18s | 20 words): "A position stand reports that kids who sample many sports '
        'still tend to reach the elite level in the end."\n'
        '  mechanism (18–28s | 19 words): "Kids hand over control and something shifts fast today for them."\n'
    )
    _, findings = parse_script(text)
    assert [(f.check, f.beat, f.kind) for f in findings] == [("PARSE", "BUILD/VALUE", "fail")]
    assert "line 3" in findings[0].message


def test_a_refused_sub_beat_is_distinguishable_from_a_beat_that_has_none():
    """C-88b distinguishability test. Both scripts have a heading already
    covered by a sibling sub-beat whose own declared/counted words match
    exactly, so neither the coverage check nor the dropped-text check fires
    either way -- isolating the one real difference: one script's second
    sub-beat is label-first and silently refused ('the parser ate what the
    author wrote'), the other simply has no second sub-beat at all ('the
    author wrote nothing'). Those must not collapse into the same empty
    finding list -- that collapse is the defect itself."""
    with_refused = (
        "BUILD/VALUE (8–28s | 20 words):\n"
        '  (8–18s | 20 words): "A position stand reports that kids who sample many sports '
        'still tend to reach the elite level in the end."\n'
        '  mechanism (18–28s | 19 words): "Kids hand over control and something shifts fast today for them."\n'
    )
    with_none = (
        "BUILD/VALUE (8–28s | 20 words):\n"
        '  (8–18s | 20 words): "A position stand reports that kids who sample many sports '
        'still tend to reach the elite level in the end."\n'
    )
    _, refused_findings = parse_script(with_refused)
    _, none_findings = parse_script(with_none)
    assert refused_findings != none_findings
    assert none_findings == []


def test_a_refused_sub_beat_reaches_the_shell_as_exit_1(tmp_path):
    """C-88b surfacing test. The parent heading's own `| N words` is stripped
    so the group-level dropped-text check (declared vs counted) has nothing to
    fire on, and a sibling sub-beat already covers the heading so the
    no-voiceover-line coverage check has nothing to fire on either -- the exit
    code must still be 1, proving the new sub-beat detector fired, not some
    other check riding along."""
    text = (
        'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
        "BUILD/VALUE (8–28s):\n"
        '  (11–18s | 8 words): "Kids hand over control and something shifts fast."\n'
        '  mechanism (18–24s | 6 words): "Extra words that never surfaced today somehow."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n"
    )
    path = tmp_path / "refused_subbeat.md"
    path.write_text(text, encoding="utf-8")
    assert main([str(path)]) == 1


def test_a_visual_note_line_carrying_a_time_range_is_not_a_refused_sub_beat():
    """Calibration: `tests/fixtures/script_decline.md:189`'s visual note line
    carries a time range but no `| N words` budget group -- the signal that
    separates a refused sub-beat from ordinary shot-list prose describing a
    beat's visuals. Taken verbatim from the shipped fixture."""
    text = (
        'BUILD/VALUE (8–28s | 8 words): "Kids hand over control and something shifts fast."\n'
        "  Hook (0–3s): The club registration form already mid-slide back across a table, adult hand and\n"
    )
    _, findings = parse_script(text)
    assert findings == []


def test_the_shipped_fixtures_produce_no_refused_sub_beat_finding():
    """Calibration: 0 hits across the 4 shipped fixtures, honouring §1's
    'fixtures stay byte-identical' guarantee -- the new detector must not
    retroactively invalidate any real artifact."""
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        _, findings = parse_script(_read(name))
        hits = [f for f in findings if "parseable sub-beat line" in f.message]
        assert hits == [], f"{name}: {hits}"


def test_beat_heading_with_no_quoted_line_anywhere_is_partial_parse():
    text = 'HOOK        (0–3s  | 7 words):\nSETUP (3–8s | 4 words): "A real spoken line."\n'
    _, findings = parse_script(text)
    assert [f.kind for f in findings] == ["partial-parse"]
    assert findings[0].beat == "HOOK"


def test_a_curly_quoted_sub_beat_under_a_covered_heading_is_not_dropped():
    """Finding 1a. Coverage is tracked per TOP-LEVEL beat, so a sub-beat sitting
    under a heading that a SIBLING sub-beat already satisfied produces no
    coverage finding of its own. If its quotes are curly rather than straight
    and the extractor only knows straight quotes, the whole sub-beat vanishes
    silently -- its dashes never reach D1 and its words never reach D5. Both
    sub-beats must parse."""
    text = (
        "BUILD/VALUE (8–28s | 16 words):\n"
        '  (8–18s | 8 words): "A position stand reports that samplers reach elite level."\n'
        "  (18–28s | 8 words): “But the offer isn’t really — about your kid.”\n"
    )
    lines, findings = parse_script(text)
    assert [vo.line_number for vo in lines] == [2, 3]
    assert "But the offer" in lines[1].text
    assert findings == []
    assert [f.check for f in check_punctuation(lines)] == ["D1"]


def test_an_apostrophe_is_not_treated_as_a_quote_delimiter():
    """The curly-quote support must not swallow contractions: `isn’t` and
    `won't` carry apostrophes, not span boundaries."""
    lines, _ = parse_script(
        'HOOK (0–3s | 7 words): "It won\'t set him back. It isn’t serious."\n'
    )
    assert [vo.text for vo in lines] == ["It won't set him back. It isn’t serious."]


def test_two_quoted_spans_on_one_beat_line_are_both_linted():
    """Finding 1b. `.search()` returned only the first span, so a second one --
    and any em-dash inside it -- escaped every check. Both spans are extracted
    and joined into the single VOLine the beat line declares, so the VO-line
    count the calibration fixtures pin is unchanged while the linted surface
    grows."""
    lines, _ = parse_script(
        'HOOK (0–3s | 10 words): "The first half is clean" and then "the second half — is not"\n'
    )
    assert len(lines) == 1
    assert "the second half" in lines[0].text
    assert [f.check for f in check_punctuation(lines)] == ["D1"]


def test_a_nested_quote_does_not_truncate_the_line_and_is_reported():
    """Finding 1c. `"He said "quit" and walked away — done."` used to extract
    only `He said `: the em-dash escaped D1 and the collapsed word count made
    D5 under-fire. The tail is now extracted (so D1 fires), and because the
    nested `"quit"` is still unrecoverable the declared-vs-counted shortfall is
    reported as a partial parse rather than passing quietly."""
    text = 'HOOK (0–3s | 9 words): "He said "quit" and walked away — done."\n'
    lines, findings = parse_script(text)
    assert "walked away" in lines[0].text
    assert [f.check for f in check_punctuation(lines)] == ["D1"]
    assert [f.kind for f in findings] == ["partial-parse"]
    assert "declares 9 words but only 6" in findings[0].message


def test_a_sub_beat_whose_text_is_unreadable_is_a_partial_parse():
    """The dropped-text detector proper: a sub-beat that declares 20 words and
    yields none is reported both on its own line and in its heading's group
    total, even though a sibling sub-beat already covered the heading."""
    text = (
        "BUILD/VALUE (8–28s | 40 words):\n"
        '  (8–18s | 20 words): "A position stand reports that kids who sample many sports '
        'still tend to reach the elite level in the end."\n'
        "  (18–28s | 20 words): unquoted prose the parser cannot see at all\n"
    )
    _, findings = parse_script(text)
    assert [f.kind for f in findings] == ["partial-parse", "partial-parse"]
    assert "line 3 declares 20 words but only 0" in findings[0].message
    assert "declares 40 words" in findings[1].message


def test_an_over_count_is_not_a_dropped_text_finding():
    """A heading claiming fewer words than the line actually speaks is a stale
    number, not evidence the parser missed something. Only a shortfall fires."""
    text = 'HOOK (0–8s | 3 words): "This spoken line is very much longer than its heading claims."\n'
    _, findings = parse_script(text)
    assert findings == []


def test_a_top_level_heading_with_no_word_budget_blocks():
    """C-89 fault test. The dropped-text detector's only witness is the
    heading's own declaration. A heading that omits it disables the detector
    for that beat, so the omission itself must block."""
    text = 'HOOK (0–3s): "Best part was the mud today, honestly."\n'
    _, findings = parse_script(text)
    assert [(f.check, f.beat, f.kind) for f in findings] == [("PARSE", "HOOK", "fail")]
    assert "| N words" in findings[0].message


def test_a_sub_beat_with_a_range_but_no_budget_blocks():
    """The same hole one level down: a sub-beat carrying a time range is
    new-format and must declare its budget."""
    text = (
        "BUILD/VALUE (8–28s | 16 words):\n"
        '  (8–18s): "A position stand reports that samplers reach elite level."\n'
    )
    _, findings = parse_script(text)
    assert any(f.kind == "fail" and "| N words" in f.message for f in findings)


def test_the_old_format_rehook_without_a_range_is_still_exempt():
    """Calibration. `script_let_kids_play_act.md:14` is an old-format re-hook
    with neither a range nor a budget; it is a known, shipped shape and must not
    be broken by this rule. The rule is: a beat line that declares a TIME RANGE
    must also declare a WORD BUDGET."""
    text = (
        'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
    )
    _, findings = parse_script(text)
    assert findings == []


def test_a_declared_zero_budget_is_distinguishable_from_no_declaration():
    """C-89 distinguishability test. `| 0 words` is an author saying "this beat
    speaks nothing"; omitting the annotation is the detector being switched off.
    They are different states and must produce different results."""
    declared = 'HOOK (0–3s | 0 words): "Mud."\n'
    omitted = 'HOOK (0–3s): "Mud."\n'
    assert parse_script(declared)[1] != parse_script(omitted)[1]
    assert parse_script(declared)[1] == []


def test_authorial_rounding_on_the_shipped_fixtures_never_fires_the_detector():
    """The threshold's calibration case. The four shipped scripts declare word
    counts that differ from their extracted text by up to 2 words absolute and
    9.1% relative -- authors rounding, not dropped text. The detector must be
    silent on all four."""
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        _, findings = parse_script(_read(name))
        assert findings == [], f"{name}: {findings}"


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
    assert sorted(f.check for f in check_vocabulary(lines) if is_blocking(f)) == ["D3", "D3"]


def test_d3_flags_buzzwords_and_their_inflections():
    lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "We leveraged a comprehensive and robust approach."\n'
    )
    assert len([f for f in check_vocabulary(lines) if f.check == "D3"]) == 3


def test_d3_inflections_are_complete_for_every_corpus_lemma():
    """Finding 5. `delves`/`delving` were listed but not `delved`; `robust` but
    not `robustness` -- so "We delved into robustness levers." produced zero D3
    findings. The five lemmas are the corpus's own and are not extended here;
    only their inflections are completed."""
    lines, _ = parse_script('HOOK (0–8s | 5 words): "We delved into robustness levers."\n')
    found = sorted(
        f.message.rsplit(" ", 1)[-1] for f in check_vocabulary(lines) if is_blocking(f)
    )
    assert found == ["'delved'", "'robustness'"]


def test_d3_flags_the_remaining_new_inflections():
    lines, _ = parse_script(
        'HOOK (0–20s | 12 words): "A comprehensiveness nobody wanted, delved over and over."\n'
    )
    assert len([f for f in check_vocabulary(lines) if f.check == "D3"]) == 2


def test_d3_does_not_flag_a_word_that_merely_contains_a_lemma():
    """`levers` and `lever` are not `leverage`; the word boundaries hold."""
    lines, _ = parse_script('HOOK (0–8s | 6 words): "He pulled the levers, every lever."\n')
    assert [f for f in check_vocabulary(lines) if is_blocking(f)] == []


def test_d3_does_not_flag_hackfort_the_surname():
    lines, _ = parse_script('HOOK (0–3s | 5 words): "Côté, Lidor and Hackfort reported."\n')
    assert [f for f in check_vocabulary(lines) if is_blocking(f)] == []


def test_d3_d4_coverage_scope_is_reported_as_a_non_blocking_finding():
    """C-92. A clean D3/D4 means "none of these eight things", not "no AI
    tells". The gate now says which eight, in a finding both callers render."""
    lines, _ = parse_script('HOOK (0–3s | 6 words): "Best part was the mud today."\n')
    scope = [f for f in check_vocabulary(lines) if f.kind == "info"]
    assert len(scope) == 1
    assert scope[0].check == "D3/D4"
    assert "3 fingerprint phrases" in scope[0].message
    assert "5 corpus lemmas" in scope[0].message
    assert "4 unspeakable token classes" in scope[0].message
    assert not is_blocking(scope[0])


def test_the_non_blocking_kinds_are_a_closed_declared_set():
    """The contract pipeline_app/gates.py binds to. A new kind must be a
    deliberate edit here, not an accident downstream."""
    assert NON_BLOCKING_KINDS == frozenset({"skipped", "info"})
    assert is_blocking(Finding("D1", "HOOK", "x")) is True
    assert is_blocking(Finding("D5", "HOOK", "x", kind="skipped")) is False
    assert is_blocking(Finding("PARSE", "HOOK", "x", kind="partial-parse")) is True


def test_buzzword_inflections_are_derived_from_the_five_corpus_lemmas():
    """The lemma count in the scope message must be the real one, not a literal
    typed beside it -- anti-tautology rule: assert on effect, not on echo."""
    assert len(BUZZWORD_LEMMAS) == 5
    assert set(BUZZWORDS) == {form for forms in BUZZWORD_LEMMAS.values() for form in forms}


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
        assert [f for f in check_vocabulary(lines) if is_blocking(f)] == [], name


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
    # Two ratable beats (HOOK, SETUP) sit alongside the old-format re-hook on
    # purpose: 2 of 3 beats ratable clears the 50% floor (see
    # test_d5_blocks_when_most_beats_are_unratable for the case where it
    # doesn't), so the only finding here is the per-beat `skipped` semantics
    # on the one still-unratable line, which are unchanged.
    lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
    )
    findings = check_pace(lines)
    assert [f.kind for f in findings] == ["skipped"]
    assert findings[0].check == "D5"


def test_d5_blocks_when_most_beats_are_unratable():
    """Finding 1 (the floor). Deleting the ranges from most-but-not-all beats
    used to leave a minority rated and no pace check on the majority, with the
    all-unratable backstop staying silent because it wasn't literally zero.
    1 of 3 ratable must now block, and the message must name both counts."""
    lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP (0:03–0:08 | 6 words): "Kids do that every single time."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
    )
    findings = [f for f in check_pace(lines) if f.kind == "fail"]
    assert len(findings) == 1
    assert findings[0].check == "D5"
    assert "1 of 3" in findings[0].message


def test_d5_treats_a_malformed_range_as_blocking_not_skipped():
    """Finding 2's other half. A malformed range (start >= end) is a defect,
    not a known unknown -- it must not be reported inside a non-blocking
    `skipped` finding, distinguishable from a merely-absent range only by
    message text."""
    lines, _ = parse_script(
        'HOOK (8–3s | 8 words): "Best part was the mud today, honestly."\n'
    )
    findings = check_pace(lines)
    fails = [f for f in findings if f.kind == "fail"]
    assert any("start >= end" in f.message for f in fails)
    assert all(f.kind != "skipped" for f in findings if "start >= end" in f.message)


def test_d5_distinguishes_mostly_unratable_from_fully_rated():
    """The two states this task tells apart must actually differ: a script
    where every beat is ratable produces no blocking finding at all, unlike
    the mostly-unratable case above."""
    unratable_lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP (0:03–0:08 | 6 words): "Kids do that every single time."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
    )
    rated_lines, _ = parse_script(
        'HOOK (0–3s | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP (3–8s | 6 words): "Kids do that every single time."\n'
    )
    assert [f for f in check_pace(unratable_lines) if f.kind == "fail"] != []
    assert [f for f in check_pace(rated_lines) if f.kind == "fail"] == []


def test_d5_blocks_when_no_beat_at_all_is_ratable():
    """Finding 2. A script whose every beat uses colon timestamps yields
    ALL-skipped pace findings, and `skipped` is non-blocking -- so the gate
    recorded `pass` on a script whose timing D5 never read a single character
    of, indistinguishable at the approval boundary from a verified one. One
    unratable re-hook is a known unknown; every beat unratable is a format
    failure, and the spec is explicit that a beat whose timing cannot be
    checked is not a pass."""
    lines, _ = parse_script(
        'HOOK (0:00–0:03 | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP (0:03–0:08 | 6 words): "Kids do that every single time."\n'
    )
    findings = check_pace(lines)
    assert [f.kind for f in findings] == ["skipped", "skipped", "fail"]
    assert findings[-1].check == "D5"
    assert "(<start>–<end>s | N words)" in findings[-1].message


def test_d5_does_not_block_when_one_beat_among_several_is_unratable():
    """The companion guard. `script_let_kids_play_act` and
    `script_specialization` each carry one old-format re-hook with no range
    alongside computable beats; neither may trip the all-unratable finding."""
    for name in ("script_let_kids_play_act.md", "script_specialization.md"):
        lines, _ = parse_script(_read(name))
        findings = check_pace(lines)
        assert any(f.kind == "skipped" for f in findings), name
        assert [f for f in findings if f.beat is None] == [], name


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


def test_a_missing_top_level_beat_blocks_the_lint():
    """C-88 surfacing test. The second, independent detector: whatever styling
    trick hid the heading, the label is absent from the parsed set and that is
    reported at the gate boundary."""
    text = (
        'HOOK        (0–3s  | 8 words): "Best part was the mud today, honestly."\n'
        'SETUP       (3–8s  | 6 words): "Kids do that every single time."\n'
        'BUILD/VALUE (8–20s | 9 words): "They hand over the whole account without a question."\n'
        'PAYOFF      (20–30s| 9 words): "Ask about the mud and you get him back."\n'
    )
    lines, _ = parse_script(text)
    findings = check_beat_set(lines)
    assert [(f.check, f.kind) for f in findings] == [("PARSE", "fail")]
    assert "LOOP/CTA" in findings[0].message


def test_the_shipped_fixtures_all_carry_the_five_beats():
    """Calibration: the check is pinned to what real scripts actually do."""
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        lines, _ = parse_script(_read(name))
        assert check_beat_set(lines) == [], name


def test_d6_passes_a_well_formed_gate_e_line():
    text = "GATES\n  Gate E (fresh Opus critic):               pass\n"
    assert check_gate_e_reported(text) == []


def test_d6_fails_a_missing_gate_e_line():
    findings = check_gate_e_reported("GATES\n  Gate D (linter): pass\n")
    assert [f.check for f in findings] == ["D6"]


def test_d6_fails_an_empty_gate_e_value():
    assert [f.check for f in check_gate_e_reported("  Gate E (critic):   \n")] == ["D6"]


SKILL_MD = (
    Path(__file__).resolve().parents[1]
    / ".claude" / "skills" / "shorts-scripting" / "SKILL.md"
)


def test_d6_rejects_the_unfilled_output_contract_placeholder():
    """Finding 4. D6 accepted the output contract's own placeholder verbatim,
    so a skill that pasted the contract without dispatching anything satisfied
    the honesty lock at zero cost -- weaker than even the "raises the omission
    from silent to deliberate" bar the lock claims, because pasting a template
    is not a decision at all. An unfilled slot is not a result.

    This does NOT make D6 a proof that Gate E ran; nothing here can be. A skill
    that skipped the critic can still type `pass`. What changed is only that it
    now has to type something."""
    line = "  Gate E (fresh Opus critic):               <pass | N findings | N defended | overridden: reason>"
    findings = check_gate_e_reported(f"GATES\n{line}\n")
    assert [f.check for f in findings] == ["D6"]
    assert "placeholder" in findings[0].message


def test_the_skill_md_output_contract_placeholder_fails_d6():
    """The contract shipped in SKILL.md is read straight off disk here rather
    than restated, so the assertion cannot drift away from the real template.
    An earlier task verified the opposite -- that the template SATISFIES D6 --
    which was the bug: a skill emitting the contract unfilled must fail the
    lock, not pass it."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "Gate E (fresh Opus critic)" in text, "output contract no longer names Gate E"
    assert [f.check for f in check_gate_e_reported(text)] == ["D6"]


def test_d6_accepts_every_genuinely_filled_shape():
    for value in (
        "pass",
        "3 findings",
        "2 findings, 1 defended",
        "overridden: dash is inside a verbatim 1886 quote",
        "deferred — app-run",
    ):
        assert check_gate_e_reported(f"  Gate E (critic): {value}\n") == [], value


def test_d6_rejects_a_bracketed_placeholder_too():
    """The design spec writes the same slot with square brackets."""
    text = "  Gate E (fresh Opus critic): [pass | N findings | N defended | overridden: <reason>]\n"
    assert [f.check for f in check_gate_e_reported(text)] == ["D6"]


def test_d6_accepts_a_filled_line_alongside_a_stray_placeholder():
    """A real result anywhere satisfies the lock; a leftover template line
    elsewhere in the document must not veto it."""
    text = (
        "  Gate E (fresh Opus critic): <pass | N findings>\n"
        "  Gate E (fresh Opus critic): 2 findings, 1 defended\n"
    )
    assert check_gate_e_reported(text) == []


def test_d6_fails_on_every_shipped_fixture_because_they_predate_the_gate():
    for name in (
        "script_let_kids_play_act.md",
        "script_specialization.md",
        "script_decline.md",
        "script_nobody_asked.md",
    ):
        assert [f.check for f in check_gate_e_reported(_read(name))] == ["D6"], name


def test_d6_accepts_a_pipe_separated_genuine_result():
    """C-91. A result written in the contract's own vocabulary, separated with a
    pipe, is a result. The old heuristic called it a template."""
    assert check_gate_e_reported("  Gate E (critic): 2 findings | 1 defended\n") == []


def test_d6_still_rejects_the_unwrapped_template_text():
    """The heuristic the pipe rule was standing in for: the actual template
    alternation, pasted without its angle brackets."""
    text = "  Gate E (critic): pass | N findings | N defended | overridden: reason\n"
    assert [f.check for f in check_gate_e_reported(text)] == ["D6"]


def test_d6_ignores_a_gate_e_line_inside_a_code_fence():
    """A script quoting the output contract in an example must not thereby
    satisfy the lock -- that is a zero-cost defeat, and the sibling linter
    already scopes its equivalent check to unfenced lines."""
    text = "```\nGate E (critic): pass\n```\n\nsome prose\n"
    assert [f.check for f in check_gate_e_reported(text)] == ["D6"]


def test_d6_accepts_a_real_line_outside_a_fence_alongside_a_fenced_example():
    text = "```\nGate E (critic): <pass | N findings>\n```\n  Gate E (critic): pass\n"
    assert check_gate_e_reported(text) == []


def test_decline_hook_loop_mirror_produces_no_gate_d_finding():
    """SKILL.md:108 requires the Loop/CTA to mirror the Hook, and the corpus
    cites it [C] (Jenny Hoyos, mhVDcqnxxaY). A gate that blocks a mandated
    mechanic is worse than no gate -- this is the regression guard for the
    repeated-template check that was removed from Gate D."""
    text = _read("script_decline.md")
    lines, parse_findings = parse_script(text)
    # NOTE: the task-5 brief's own test asserts an exact match against
    # "It won't set him back." but the fixture's actual Hook line is "It
    # won't set him back. Not athletically." and its Loop/CTA line is "You're
    # not taking something away from him. It won't set him back." -- an exact
    # match against either yields zero. The governing rule, per this test's
    # own docstring, is that the mandated Hook/Loop mirror mechanic (repeating
    # a phrase across Hook and Loop/CTA) must not itself trip a Gate D check;
    # the brief's exact-equality check was miscalibrated against the real
    # fixture text. Substring containment is what the docstring actually
    # requires, and both beats do contain the mirrored phrase.
    mirrored = [vo for vo in lines if "It won't set him back." in vo.text]
    assert len(mirrored) >= 2
    assert any(vo.beat == "HOOK" for vo in mirrored)
    assert any(vo.beat == "LOOP/CTA" for vo in mirrored)
    findings = lint(lines, text, parse_findings)
    assert [f for f in findings if f.check in ("D2", "D3", "D4")] == []


def test_main_returns_2_on_a_file_with_no_vo_lines(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("no beats here at all\n", encoding="utf-8")
    assert main([str(path)]) == 2


def test_main_returns_1_on_a_failing_fixture(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text(_read("script_decline.md"), encoding="utf-8")
    assert main([str(path)]) == 1


def test_main_returns_0_on_a_clean_five_beat_script(tmp_path):
    """Renamed from test_main_returns_0_on_a_clean_script (C-88 / T2): the
    fixture was a one-beat script, and check_beat_set now blocks any script
    missing a top-level label, so a "clean" script must carry all five. Not
    built on a shared CLEAN_SCRIPT constant -- that name belongs to T7, which
    lands its own module-level constant later in this package's task order;
    defining it here would collide with T7's addition."""
    path = tmp_path / "clean.md"
    path.write_text(
        'HOOK        (0–3s   | 6 words): "Best part was the mud today."\n'
        'SETUP       (3–8s   | 6 words): "Kids do that every single time."\n'
        'BUILD/VALUE (8–20s  | 9 words): "They hand over the whole account without a question."\n'
        'PAYOFF      (20–30s | 9 words): "Ask about the mud and you get him back."\n'
        'LOOP/CTA    (30–35s | 6 words): "Best part was the mud today."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n",
        encoding="utf-8",
    )
    assert main([str(path)]) == 0


def test_main_returns_0_when_only_finding_is_skipped(tmp_path):
    """Carried forward from Task 4's review: a kind="skipped" finding (e.g. D5
    on a beat with no computable time range) must never contribute to a
    non-zero exit. This script has a re-hook beat with no range (skipped D5)
    plus a well-formed Gate E line, so the only findings are non-blocking.

    Widened to all five top-level beats for the same reason as
    test_main_returns_0_on_a_clean_five_beat_script above: check_beat_set
    (C-88 / T2) now blocks a script missing a label, and this fixture was
    previously HOOK-only."""
    path = tmp_path / "skipped_only.md"
    path.write_text(
        'HOOK        (0–3s   | 6 words): "Best part was the mud today."\n'
        '[re-hook beat @ ~15s]: "His proof, a trader who bought the presses."\n'
        'SETUP       (3–8s   | 6 words): "Kids do that every single time."\n'
        'BUILD/VALUE (8–20s  | 9 words): "They hand over the whole account without a question."\n'
        'PAYOFF      (20–30s | 9 words): "Ask about the mud and you get him back."\n'
        'LOOP/CTA    (30–35s | 6 words): "Best part was the mud today."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n",
        encoding="utf-8",
    )
    assert main([str(path)]) == 0


CLEAN_SCRIPT = """\
=== SHORT SCRIPT — Gate D mutation base ===

HOOK        (0–4s  | 9 words): "Nobody asked him what the best part was."
SETUP       (4–10s | 12 words): "He came home muddy, and the whole story arrived without a question."
BUILD/VALUE (10–24s | 20 words):
  (10–24s | 20 words): "Kids hand over the account when nothing is riding on the answer, and that is the entire trick."
PAYOFF      (24–34s | 18 words): "Ask about the score and you get a score. Ask about the mud and you get him."
LOOP/CTA    (34–40s | 10 words, mirrors hook): "Ask what the best part was. Then believe it."

GATES
  Gate E (fresh Opus critic): 2 findings, 1 defended
"""


def _run(tmp_path, text, name="script.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return main([str(path)])


def test_the_mutation_base_passes_gate_d(tmp_path):
    """The control. If this ever fails, every row below is meaningless."""
    assert _run(tmp_path, CLEAN_SCRIPT) == 0


MUTATIONS = [
    # (id, target substring, replacement, the check that must fire)
    ("D1-em-dash", "arrived without a question.",
     "arrived — without a question.", "D1"),
    ("D2-parenthetical", "you get him.", "you get him (again).", "D2"),
    ("D3-buzzword", "Kids hand over", "Kids leveraged and hand over", "D3"),
    ("D4-inline-stat", "you get a score.", "you get n=142 back.", "D4"),
    ("D5-over-stuffed", "HOOK        (0–4s  | 9 words)",
     "HOOK        (0–1s  | 9 words)", "D5"),
    ("D5-malformed-range", "SETUP       (4–10s | 12 words)",
     "SETUP       (10–4s | 12 words)", "D5"),
    ("D6-deleted", "  Gate E (fresh Opus critic): 2 findings, 1 defended\n", "", "D6"),
    ("D6-fenced", "GATES\n", "GATES\n```\n", "D6"),
    ("C88-bolded-label", "HOOK        (0–4s", "**HOOK**    (0–4s", "PARSE"),
    ("C88-deleted-beat",
     'LOOP/CTA    (34–40s | 10 words, mirrors hook): "Ask what the best part was. Then believe it."\n',
     "", "PARSE"),
    ("C89-stripped-budget", "HOOK        (0–4s  | 9 words)", "HOOK        (0–4s)", "PARSE"),
    # C88b (T1b, already merged): CLEAN_SCRIPT's BUILD/VALUE sub-beat is
    # deliberately the BARE, parseable form (a parenthesis starting the
    # line) so the control stays clean. This mutation adds a "mechanism "
    # label prefix, which SUBRANGE_RE cannot match -- the exact refused-line
    # shape T1b's detector exists to catch instead of silently deleting.
    ("C88b-label-first-subbeat",
     '  (10–24s | 20 words): "Kids hand over the account when nothing is riding on the answer, and that is the entire trick."',
     '  mechanism (10–24s | 20 words): "Kids hand over the account when nothing is riding on the answer, and that is the entire trick."',
     "PARSE"),
]


@pytest.mark.parametrize("mutation_id,target,replacement,expected_check", MUTATIONS,
                         ids=[m[0] for m in MUTATIONS])
def test_each_single_edit_evasion_still_fails_the_gate(
    tmp_path, mutation_id, target, replacement, expected_check
):
    """The whole point of Gate D. Each row is ONE edit to a passing script, of
    the kind a model actually emits. Every one must block, and must block for
    the named reason -- a gate that fails for the wrong reason is a gate that
    will be 'fixed' into passing."""
    assert target in CLEAN_SCRIPT, mutation_id
    mutated = CLEAN_SCRIPT.replace(target, replacement, 1)
    assert mutated != CLEAN_SCRIPT, mutation_id

    lines, parse_findings = parse_script(mutated)
    findings = [f for f in lint(lines, mutated, parse_findings) if is_blocking(f)]
    assert findings, mutation_id
    assert expected_check in {f.check for f in findings}, (mutation_id, findings)
    assert _run(tmp_path, mutated) == 1, mutation_id
