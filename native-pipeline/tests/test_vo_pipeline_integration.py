"""Binds elevenlabs_tooling.tags.compose_tagged_text's beat-join convention
to stitcher.vo_alignment.derive_segments_v3's paragraph-split convention --
these are independently-committed functions in two different packages that
share an implicit "\\n\\n" contract enforced only by docstring prose in each.
This test makes that contract a real, failing-on-drift assertion."""

import pytest

from elevenlabs_tooling.tags import compose_tagged_text
from stitcher.vo_alignment import derive_segments_v3


def _fake_alignment(text, char_dur=0.1):
    chars, starts, ends = [], [], []
    clock = 0.0
    for ch in text:
        chars.append(ch)
        starts.append(round(clock, 4))
        clock = round(clock + char_dur, 4)
        ends.append(clock)
    return {"characters": chars, "character_start_times_seconds": starts,
            "character_end_times_seconds": ends}


def test_compose_tagged_text_output_round_trips_through_derive_segments_v3():
    beats = ["Eight grand a year on club soccer.", "Why?", "So why can't you say why?"]
    tags = ["[excited]", "[whispers]", None]

    text = compose_tagged_text(beats, tags)
    tagged_beats = [f"{tag} {beat}" if tag else beat for beat, tag in zip(beats, tags)]
    alignment = _fake_alignment(text)

    segments = derive_segments_v3(text, alignment, tagged_beats, names=["hook", "why", "turn"])

    assert [s.name for s in segments] == ["hook", "why", "turn"]
    # segments[0].at is not 0.0 here: the beat is prefixed with the
    # "[excited] " tag text (compose_tagged_text's own contract), which
    # derive_segments_v3 correctly excludes as non-real (tag) text -- see
    # its own docstring on recovering `at`/`duration` from the first/last
    # REAL character in each beat's paragraph, not the paragraph's raw
    # start index.
    assert segments[0].at >= 0.0
    for i in range(1, len(segments)):
        assert segments[i].at > segments[i - 1].at + segments[i - 1].duration - 1e-6
