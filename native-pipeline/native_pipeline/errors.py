"""Exception types for the native single-generation render pipeline.

One narrow exception per failure mode, each subclassing a built-in --
matching stitcher's own pattern (FFmpegError(RuntimeError),
LoudnormNotLinearError(RuntimeError), etc.) rather than a shared base class.
"""

from __future__ import annotations


class ShotSegmentMismatchError(ValueError):
    """A segment/asset-manifest beat-name mismatch, or a build_shots()
    invariant violated (non-contiguous, doesn't start at 0, doesn't end at
    the take's runtime)."""


class ChunkDurationTooShortError(ValueError):
    """A composition-plan chunk violates one of Eleven Music's music_v2
    constraints: a chunk under the 3,000ms floor, a chunk over the
    120,000ms ceiling, more than 30 chunks total, or the plan's total
    duration not matching the take's runtime."""


class BedDurationMismatchError(RuntimeError):
    """The generated music bed's measured duration doesn't match the VO
    take's runtime within tolerance."""


class IterationBudgetExceededError(RuntimeError):
    """A generation attempt was requested for a track (VO or music) after
    its 2-attempt iteration cap was already spent."""


class VoModeMismatchError(ValueError):
    """run_vo_stage's vo_mode is unrecognized, or is 'v3_tags' without the
    beat_texts derive_segments_v3 needs (there is no <break> marker to
    split on, unlike the 'break' mode)."""
