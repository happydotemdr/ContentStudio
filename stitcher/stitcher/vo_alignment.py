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
