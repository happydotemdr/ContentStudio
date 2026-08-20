"""Turn a single-take VO's derived Segment boundaries into absolute timing
for the objects whose spans must never drift from the measured audio.

Two uses:
  - Caption spans map 1:1 onto segments (one caption per beat) -- exact,
    no further decision needed.
  - Shot/overlay cut timing is still shots.py's/visual-prompts' own cadence
    decision (how many cuts within a beat, and roughly where) -- but that
    decision can be expressed as fractions of a beat's OWN duration and
    mapped onto the beat's real, measured window here, instead of being
    authored against an estimated duration that can silently drift out of
    sync with the actual audio (docs/superpowers/plans/
    2026-08-19-vo-architecture-test-plan.md: the live render-spec.json was
    found 8.945s out of sync with its actual audio for exactly this reason).
"""

from __future__ import annotations

from .spec import Caption
from .vo_alignment import Segment


def derive_captions(segments: list[Segment], beat_texts: list[str]) -> list[Caption]:
    """One Caption per segment, spanning it exactly."""
    if len(segments) != len(beat_texts):
        raise ValueError(
            f"segments ({len(segments)}) and beat_texts ({len(beat_texts)}) "
            "must be the same length"
        )
    return [
        Caption(start=segment.at, end=segment.at + segment.duration, text=text)
        for segment, text in zip(segments, beat_texts)
    ]


def rescale_relative_spans(
    spans: list[tuple[float, float]], segment: Segment
) -> list[tuple[float, float]]:
    """Map beat-relative (start_fraction, end_fraction) pairs -- each in
    [0, 1], expressing where within ONE beat's own duration a shot or
    overlay begins/ends -- onto absolute render-timeline seconds, anchored
    to that beat's measured Segment.
    """
    for start_frac, end_frac in spans:
        if not (0.0 <= start_frac <= end_frac <= 1.0):
            raise ValueError(
                f"span ({start_frac}, {end_frac}) must satisfy "
                "0 <= start <= end <= 1"
            )
    return [
        (segment.at + start_frac * segment.duration, segment.at + end_frac * segment.duration)
        for start_frac, end_frac in spans
    ]
