"""Derive stem segment boundaries from ElevenLabs' /with-timestamps
character-level alignment, given the exact submitted text (including its
<break time="Xs" /> tags).

Verified against real ElevenLabs output (docs/superpowers/plans/
2026-08-19-vo-architecture-test-plan.md §6c): a <break> tag's own markup
characters all collapse to a single zero-duration instant at the moment the
break begins ("<", "b", "r", ... all report the same start==end timestamp).
The real, audible pause length is the gap between the last real spoken
character's end time before the tag and the first real spoken character's
start time after it -- not anything printed for the tag's own characters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BREAK_RE = re.compile(r'<break time="[\d.]+s" />')


@dataclass(frozen=True)
class Segment:
    name: str
    at: float
    duration: float


def derive_segments(text: str, alignment: dict, names: list[str] | None = None) -> list[Segment]:
    """Split `text` on its <break> tags and return one Segment per piece of
    real spoken text, with `at`/`duration` taken from `alignment`'s
    character-level timestamps.

    `alignment` is the `alignment` field of an ElevenLabs /with-timestamps
    response: {"characters": [...], "character_start_times_seconds": [...],
    "character_end_times_seconds": [...]}. All three lists must be the same
    length as `text`.
    """
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    if not (len(chars) == len(starts) == len(ends)):
        raise ValueError(
            f"alignment lists have mismatched lengths: "
            f"characters={len(chars)} starts={len(starts)} ends={len(ends)}"
        )
    aligned_text = "".join(chars)
    if aligned_text != text:
        raise ValueError(
            "alignment's characters do not reconstruct the submitted text -- "
            f"expected {len(text)} characters, alignment has {len(aligned_text)}"
        )

    total_duration = ends[-1] if ends else 0.0

    breaks = []
    for match in _BREAK_RE.finditer(text):
        i0, i1 = match.span()
        j = i0 - 1
        while j >= 0 and text[j] == " ":
            j -= 1
        if j < 0:
            raise ValueError(
                "a <break> tag cannot appear at the very start of the text — "
                "no preceding spoken character to end a segment"
            )
        pre_end = ends[j]
        k = i1
        while k < len(text) and text[k] == " ":
            k += 1
        post_start = starts[k] if k < len(text) else total_duration
        breaks.append((pre_end, post_start))

    bounds = []
    prev_end = 0.0
    for pre_end, post_start in breaks:
        bounds.append((prev_end, pre_end))
        prev_end = post_start
    bounds.append((prev_end, total_duration))

    if names is None:
        names = [f"beat{i + 1}" for i in range(len(bounds))]
    if len(names) != len(bounds):
        raise ValueError(
            f"names has {len(names)} entries but the text has {len(bounds)} "
            f"segments ({len(breaks)} break tags found)"
        )

    return [
        Segment(name=name, at=start, duration=end - start)
        for name, (start, end) in zip(names, bounds)
    ]


_TAG_RE = re.compile(r'\[[^\]]*\]')


def _is_real_text_index(text: str, i: int, tag_spans: list[tuple[int, int]]) -> bool:
    if text[i].isspace():
        return False
    return not any(start <= i < end for start, end in tag_spans)


def derive_segments_v3(
    text: str, alignment: dict, beat_texts: list[str], names: list[str] | None = None
) -> list[Segment]:
    """Split `text` on its "\\n\\n" paragraph breaks -- the composition
    convention elevenlabs_tooling.tags.compose_tagged_text uses for a
    single continuous eleven_v3 generation -- and return one Segment per
    beat, with `at`/`duration` taken from real (non-tag, non-whitespace)
    character timestamps in `alignment`.

    Unlike derive_segments (the <break>-tagged path for
    eleven_multilingual_v2/flash), eleven_v3 has no <break> mechanism --
    beats are separated by bracket audio tags like [excited]/[whispers] and
    plain paragraph structure instead. Verified against a real ElevenLabs
    /with-timestamps response (stitcher/tests/fixtures/
    v3_tags_alignment_sample.json, captured 2026-08-21): a bracket tag's own
    characters collapse to a near-zero-duration cluster at the instant the
    tag "fires," the same way a <break> tag's markup characters do -- so a
    beat's real `at`/end are the first/last REAL (non-tag, non-whitespace)
    character's timestamps within that beat's own paragraph, not the
    paragraph's raw start/end index.

    `alignment` is the `alignment` field of an ElevenLabs /with-timestamps
    response: {"characters": [...], "character_start_times_seconds": [...],
    "character_end_times_seconds": [...]}. All three lists must be the same
    length as `text`.
    """
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    if not (len(chars) == len(starts) == len(ends)):
        raise ValueError(
            f"alignment lists have mismatched lengths: "
            f"characters={len(chars)} starts={len(starts)} ends={len(ends)}"
        )
    aligned_text = "".join(chars)
    if aligned_text != text:
        raise ValueError(
            "alignment's characters do not reconstruct the submitted text -- "
            f"expected {len(text)} characters, alignment has {len(aligned_text)}"
        )

    pieces = text.split("\n\n")
    if len(pieces) != len(beat_texts):
        raise ValueError(
            f"text splits into {len(pieces)} paragraph(s) on a blank line but "
            f"{len(beat_texts)} beat_texts were supplied -- these must match"
        )
    for index, (piece, expected) in enumerate(zip(pieces, beat_texts)):
        if piece != expected:
            raise ValueError(
                f"paragraph {index} is {piece!r} but the expected beat text at "
                f"that position is {expected!r}"
            )

    if names is None:
        names = [f"beat{i + 1}" for i in range(len(pieces))]
    if len(names) != len(pieces):
        raise ValueError(
            f"names has {len(names)} entries but the text has {len(pieces)} paragraphs"
        )

    tag_spans = [match.span() for match in _TAG_RE.finditer(text)]

    segments = []
    offset = 0
    for name, piece in zip(names, pieces):
        real_indices = [
            i for i in range(offset, offset + len(piece))
            if _is_real_text_index(text, i, tag_spans)
        ]
        if not real_indices:
            raise ValueError(
                f"paragraph {piece!r} (segment {name!r}) has no real spoken "
                "text -- every character is a bracket tag or whitespace"
            )
        at = starts[real_indices[0]]
        end = ends[real_indices[-1]]
        segments.append(Segment(name=name, at=at, duration=end - at))
        offset += len(piece) + 2  # skip the "\n\n" separator

    return segments
