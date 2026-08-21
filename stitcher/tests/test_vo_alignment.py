import json
from pathlib import Path

import pytest

from stitcher.vo_alignment import Segment, derive_segments, derive_segments_v3


def _build_case(beat_texts, break_seconds):
    """Build (text, alignment) for beats joined by <break> tags, with a
    synthetic alignment that mirrors ElevenLabs' real observed structure
    (docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md §6c):
    the entire pause duration lands on the space character immediately
    before the <break> tag; the tag's own markup characters (and the space
    after it) are zero-width at the instant the pause ends; the next real
    character begins at that exact instant."""
    CHAR_DUR = 0.1
    chars, starts, ends = [], [], []
    clock = 0.0

    def emit_real(s):
        nonlocal clock
        for ch in s:
            chars.append(ch)
            starts.append(round(clock, 4))
            clock = round(clock + CHAR_DUR, 4)
            ends.append(clock)

    def emit_gap_char(ch, gap):
        nonlocal clock
        chars.append(ch)
        starts.append(round(clock, 4))
        clock = round(clock + gap, 4)
        ends.append(clock)

    def emit_zero_width(s):
        for ch in s:
            chars.append(ch)
            starts.append(clock)
            ends.append(clock)

    text_parts = [beat_texts[0]]
    emit_real(beat_texts[0])
    for beat, seconds in zip(beat_texts[1:], break_seconds):
        tag = f'<break time="{seconds:.1f}s" />'
        emit_gap_char(" ", seconds)
        emit_zero_width(tag)
        emit_zero_width(" ")
        emit_real(beat)
        text_parts.append(f' {tag} ')
        text_parts.append(beat)

    text = "".join(text_parts)
    alignment = {
        "characters": chars,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": ends,
    }
    assert len(chars) == len(text)
    return text, alignment


def test_two_beats_one_break_recovers_correct_segment_boundaries():
    beat1, beat2 = "Hi there.", "Bye now."
    text, alignment = _build_case([beat1, beat2], [0.5])

    segments = derive_segments(text, alignment)

    assert len(segments) == 2
    assert segments[0].name == "beat1"
    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat1) * 0.1)
    assert segments[1].name == "beat2"
    assert segments[1].at == pytest.approx(len(beat1) * 0.1 + 0.5)
    assert segments[1].duration == pytest.approx(len(beat2) * 0.1)


def test_three_beats_two_breaks_recovers_all_boundaries():
    beat1, beat2, beat3 = "First one.", "Second one.", "Third one."
    text, alignment = _build_case([beat1, beat2, beat3], [0.5, 0.3])

    segments = derive_segments(text, alignment)

    assert [s.name for s in segments] == ["beat1", "beat2", "beat3"]
    b1_end = len(beat1) * 0.1
    b2_at = b1_end + 0.5
    b2_end = b2_at + len(beat2) * 0.1
    b3_at = b2_end + 0.3
    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat1) * 0.1)
    assert segments[1].at == pytest.approx(b2_at)
    assert segments[1].duration == pytest.approx(len(beat2) * 0.1)
    assert segments[2].at == pytest.approx(b3_at)
    assert segments[2].duration == pytest.approx(len(beat3) * 0.1)


def test_custom_names_are_used_in_order():
    text, alignment = _build_case(["A beat.", "Another beat."], [0.4])
    segments = derive_segments(text, alignment, names=["hook", "cta"])
    assert [s.name for s in segments] == ["hook", "cta"]


def test_single_beat_no_breaks_returns_one_segment_spanning_the_whole_text():
    beat = "Just one beat here."
    text, alignment = _build_case([beat], [])
    segments = derive_segments(text, alignment)
    assert len(segments) == 1
    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat) * 0.1)


def test_mismatched_names_length_raises():
    text, alignment = _build_case(["A.", "B."], [0.5])
    with pytest.raises(ValueError, match="2 segments"):
        derive_segments(text, alignment, names=["only_one"])


def test_alignment_length_mismatch_raises():
    text, alignment = _build_case(["A.", "B."], [0.5])
    alignment["characters"] = alignment["characters"][:-1]
    with pytest.raises(ValueError, match="mismatched lengths"):
        derive_segments(text, alignment)


def test_alignment_text_mismatch_raises():
    text, alignment = _build_case(["A.", "B."], [0.5])
    with pytest.raises(ValueError, match="do not reconstruct"):
        derive_segments("Completely different text.", alignment)


def test_break_tag_at_text_start_raises():
    """A <break> tag at position 0 (before any real text) is structurally
    invalid and must raise a clear error, not silently corrupt segment
    boundaries via negative indexing into the ends array."""
    # Build alignment for a break tag followed by actual text
    CHAR_DUR = 0.1
    chars, starts, ends = [], [], []
    clock = 0.0

    # Emit zero-width break tag characters
    tag = '<break time="0.5s" />'
    for ch in tag:
        chars.append(ch)
        starts.append(clock)
        ends.append(clock)

    # Emit the space after the tag (also zero-width since break ends at time 0)
    chars.append(" ")
    starts.append(clock)
    ends.append(clock)

    # Emit actual spoken text
    beat = "Now speaking."
    for ch in beat:
        chars.append(ch)
        starts.append(round(clock, 4))
        clock = round(clock + CHAR_DUR, 4)
        ends.append(clock)

    text = tag + " " + beat
    alignment = {
        "characters": chars,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": ends,
    }

    with pytest.raises(ValueError, match="cannot appear at the very start"):
        derive_segments(text, alignment)


# Tests for derive_segments_v3 (bracket-tagged, paragraph-split style)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "v3_tags_alignment_sample.json"


def _build_v3_case(beat_texts):
    """Build (text, alignment) for beats joined by a blank line ("\\n\\n"),
    mirroring the REAL structure captured in v3_tags_alignment_sample.json
    (Task 1): plain real text advances the clock by CHAR_DUR per character;
    no bracket tag appears in this helper's own cases (see
    test_bracket_tag_is_excluded_from_segment_timing for that shape)."""
    CHAR_DUR = 0.1
    chars, starts, ends = [], [], []
    clock = 0.0

    def emit_real(s):
        nonlocal clock
        for ch in s:
            chars.append(ch)
            starts.append(round(clock, 4))
            clock = round(clock + CHAR_DUR, 4)
            ends.append(clock)

    for i, beat in enumerate(beat_texts):
        if i > 0:
            emit_real("\n\n")
        emit_real(beat)

    text = "\n\n".join(beat_texts)
    alignment = {
        "characters": chars,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": ends,
    }
    assert len(chars) == len(text)
    return text, alignment


def test_two_beats_no_tags_recovers_correct_segment_boundaries():
    beat1, beat2 = "Hi there.", "Bye now."
    text, alignment = _build_v3_case([beat1, beat2])

    segments = derive_segments_v3(text, alignment, [beat1, beat2])

    assert len(segments) == 2
    assert segments[0].name == "beat1"
    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat1) * 0.1)
    assert segments[1].name == "beat2"
    gap_start = (len(beat1) + 2) * 0.1  # beat1 + the 2-char "\n\n" separator
    assert segments[1].at == pytest.approx(gap_start)
    assert segments[1].duration == pytest.approx(len(beat2) * 0.1)


def test_bracket_tag_is_excluded_from_segment_timing():
    """A tag's characters collapse to a single zero-duration instant (the
    real collapse pattern Task 1 confirmed against a live /with-timestamps
    response) -- the segment's `at` must be the first REAL character's
    start time, not the tag's."""
    CHAR_DUR = 0.1
    chars, starts, ends = [], [], []
    clock = 0.0
    for ch in "[excited] ":  # tag + its trailing space, all zero-width
        chars.append(ch)
        starts.append(clock)
        ends.append(clock)
    beat = "Real words start here."
    for ch in beat:
        chars.append(ch)
        starts.append(round(clock, 4))
        clock = round(clock + CHAR_DUR, 4)
        ends.append(clock)
    text = "[excited] " + beat
    alignment = {"characters": chars, "character_start_times_seconds": starts,
                 "character_end_times_seconds": ends}

    segments = derive_segments_v3(text, alignment, [text])

    assert segments[0].at == 0.0
    assert segments[0].duration == pytest.approx(len(beat) * 0.1)


def test_paragraph_count_mismatch_raises():
    text, alignment = _build_v3_case(["A.", "B."])
    with pytest.raises(ValueError, match="2 paragraph"):
        derive_segments_v3(text, alignment, ["A.", "B.", "C."])


def test_beat_text_mismatch_raises():
    text, alignment = _build_v3_case(["A.", "B."])
    with pytest.raises(ValueError, match="expected beat text"):
        derive_segments_v3(text, alignment, ["A.", "Different."])


def test_custom_names_are_used_in_order_v3():
    text, alignment = _build_v3_case(["A beat.", "Another beat."])
    segments = derive_segments_v3(text, alignment, ["A beat.", "Another beat."],
                                   names=["hook", "cta"])
    assert [s.name for s in segments] == ["hook", "cta"]


def test_all_tag_no_real_text_raises():
    text = "[pause]"
    alignment = {
        "characters": list(text),
        "character_start_times_seconds": [0.0] * len(text),
        "character_end_times_seconds": [0.0] * len(text),
    }
    with pytest.raises(ValueError, match="no real spoken text"):
        derive_segments_v3(text, alignment, [text])


@pytest.mark.skipif(
    not FIXTURE_PATH.is_file(),
    reason="run native-pipeline's e2e test (-m e2e) first to capture "
    "v3_tags_alignment_sample.json (Task 1)",
)
def test_real_captured_v3_alignment_recovers_two_segments():
    """Grounds this function against a REAL ElevenLabs /with-timestamps
    response. Beat texts here must stay byte-identical to
    native-pipeline/tests/test_e2e.py's V3_TAG_BEAT_TEXTS constant (Task 1)."""
    recorded = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    beat_texts = [
        "[excited] This is the first beat of a real v3 tags test.",
        "So here's the second beat, after a real pause.",
    ]
    segments = derive_segments_v3(recorded["text"], recorded["alignment"], beat_texts)
    assert len(segments) == 2
    assert segments[0].at == pytest.approx(0.0, abs=0.2)
    assert segments[1].at > segments[0].at + segments[0].duration
