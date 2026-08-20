import pytest

from elevenlabs_tooling.breaks import compose_break_tagged_text


def test_composes_two_beats_with_one_break():
    result = compose_break_tagged_text(["Hello there.", "Goodbye now."], [0.9])
    assert result == 'Hello there. <break time="0.9s" /> Goodbye now.'


def test_composes_three_beats_with_two_breaks_of_different_durations():
    result = compose_break_tagged_text(
        ["First beat.", "Second beat.", "Third beat."], [0.5, 1.2]
    )
    assert result == (
        'First beat. <break time="0.5s" /> Second beat. '
        '<break time="1.2s" /> Third beat.'
    )


def test_single_beat_needs_no_breaks():
    assert compose_break_tagged_text(["Only one beat."], []) == "Only one beat."


def test_wrong_break_count_raises():
    with pytest.raises(ValueError, match="exactly 2 entries"):
        compose_break_tagged_text(["A", "B", "C"], [0.5])


def test_break_duration_zero_raises():
    with pytest.raises(ValueError, match="0-3s range"):
        compose_break_tagged_text(["A", "B"], [0.0])


def test_break_duration_over_three_seconds_raises():
    with pytest.raises(ValueError, match="0-3s range"):
        compose_break_tagged_text(["A", "B"], [3.5])


def test_empty_beats_list_raises():
    with pytest.raises(ValueError, match="at least one beat"):
        compose_break_tagged_text([], [])
