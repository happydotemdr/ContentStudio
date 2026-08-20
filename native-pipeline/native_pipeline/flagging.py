"""flag_outliers -- a read-only measurement pass over the raw VO take (per
beat) or the generated music bed (per chunk). Flags, never corrects: this
mode trusts ElevenLabs/Eleven Music output completely, and this is the one
piece of visibility into whether that trust was warranted for a specific
render. Never calls stitcher.precondition.condition_clip or anything else
that would modify the audio."""

from __future__ import annotations

import statistics
from pathlib import Path

from stitcher.verify import MIN_DUCK_WINDOW_S, measure_window


def flag_outliers(
    path: Path,
    spans: list[tuple[str, float, float]],
    log_path: Path,
    threshold_lu: float = 3.0,
) -> list[dict]:
    """spans: list of (label, start_s, duration_s). A span shorter than
    MIN_DUCK_WINDOW_S is skipped -- an ebur128 integrated reading over a
    very short window is not a meaningful measurement (stitcher.verify
    applies the same floor for its own ducking checks)."""
    measurements = []
    for label, start, duration in spans:
        if duration < MIN_DUCK_WINDOW_S:
            continue
        lufs = measure_window(path, start, duration, log_path)
        measurements.append((label, lufs))

    if len(measurements) < 2:
        return []

    median = statistics.median(lufs for _, lufs in measurements)

    flags = []
    for label, lufs in measurements:
        deviation = abs(lufs - median)
        if deviation > threshold_lu:
            flags.append({"label": label, "lufs": lufs, "median_lufs": median, "deviation_lu": deviation})
    return flags
