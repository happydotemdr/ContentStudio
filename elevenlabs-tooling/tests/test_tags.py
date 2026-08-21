import pytest

from elevenlabs_tooling.tags import compose_tagged_text


def test_composes_two_beats_one_tagged_one_not():
    result = compose_tagged_text(
        ["Eight grand a year.", "Why?"], ["[excited]", "[whispers]"]
    )
    assert result == "[excited] Eight grand a year.\n\n[whispers] Why?"


def test_beat_with_none_tag_gets_no_bracket_prefix():
    result = compose_tagged_text(["Plain beat.", "Tagged beat."], [None, "[curious]"])
    assert result == "Plain beat.\n\n[curious] Tagged beat."


def test_stacked_tags_pass_through_as_one_string():
    result = compose_tagged_text(["Why?"], ["[pause][whispers]"])
    assert result == "[pause][whispers] Why?"


def test_single_beat_no_tag():
    assert compose_tagged_text(["Only one beat."], [None]) == "Only one beat."


def test_wrong_tag_count_raises():
    with pytest.raises(ValueError, match="exactly 2 entries"):
        compose_tagged_text(["A", "B"], ["[x]"])


def test_empty_beats_list_raises():
    with pytest.raises(ValueError, match="at least one beat"):
        compose_tagged_text([], [])
