"""Per-clip loudness/true-peak conditioning.

Removes beat-to-beat level inconsistency and dynamic-range collapse (spec
docs/superpowers/specs/2026-08-19-audio-preconditioning-design.md §1) by
conditioning each raw VO take and bed segment individually, before it ever
reaches build_audio()'s own two-pass linear loudnorm. build_audio() itself is
unmodified -- this module only makes its inputs safe for that gate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg

# Pinned explicitly so a future ffmpeg default change can't silently move
# these -- verified against the installed ffmpeg 9.0 build's
# `-h filter=alimiter` (spec §4.1).
CONDITION_ATTACK_MS = 5
CONDITION_RELEASE_MS = 50

# How far a measured true peak may land over target before triggering a
# tighter-ceiling retry (spec §4.1).
TP_TOLERANCE_DB = 0.1

# How far a conditioned clip's integrated loudness may drift from target
# before triggering a makeup-gain retry. Deliberately 0.35, not 0.3: a
# boundary of exactly 0.3 sits on a floating-point knife edge against
# ebur128's 0.1 LU output granularity (spec §4.1: a real measured
# `-14.3` vs. target `-14.0` case evaluates `abs(-14.3 - -14.0) <= 0.3` as
# False due to `0.30000000000000071...`).
LUFS_TOLERANCE = 0.35

MAX_ATTEMPTS = 4


class PreconditionError(Exception):
    """Raised when, after MAX_ATTEMPTS, the output still fails the peak or
    loudness target. Never silently returned -- a hard stop, matching
    stitcher's existing LoudnormNotLinearError/SilentVoiceError philosophy."""


@dataclass(frozen=True)
class ConditionResult:
    source: Path
    output: Path
    # {input_i, input_tp, input_lra} -- the exact 3 keys
    # ffmpeg.measure_loudness returns (ffmpeg.py:344-348).
    input_measurement: dict
    output_measurement: dict
    # True if peak_reduction_db > 0.05 -- distinguishes "the limiter did
    # something" from "gain alone would have landed here anyway".
    limited: bool
    # (input_measurement['input_tp'] + applied_gain) - output_measurement['input_tp'],
    # using the ACCEPTED attempt's final applied_gain (which the
    # loudness-retry branch, Task 3, may have revised from its initial
    # value). The gap between "what the peak would have been with gain
    # alone" and "what it actually is".
    peak_reduction_db: float


# alimiter's `limit` parameter is only valid in [0.0625, 1] (~-24.08..0
# dBFS) -- verified against the installed ffmpeg 9.0 build's
# `-h filter=alimiter`. A ceiling that would push `limit` below this floor
# is a PreconditionError, not an invalid ffmpeg argument.
_ALIMITER_MIN_DBTP = 20 * math.log10(0.0625)  # ~-24.08


def condition_clip(
    source: Path,
    target_lufs: float,
    target_tp_dbtp: float,
    out_path: Path,
    log_path: Path,
) -> ConditionResult:
    """Condition one clip so it is safe for build_audio()'s linear-loudnorm
    gate, without collapsing dynamics to get there (spec §4.1)."""
    input_measurement = ffmpeg.measure_loudness(source, log_path)
    if ffmpeg.is_digital_silence(input_measurement):
        # Matches stitcher's existing SilentVoiceError philosophy (audio.py):
        # a silent source has no loudness to solve against, so failing loudly
        # here beats a doomed 4-attempt encode loop ending in a confusing
        # "-inf" peak_reduction_db.
        raise PreconditionError(
            f"{source}: input is digital silence (integrated "
            f"{input_measurement['input_i']} LUFS, true peak "
            f"{input_measurement['input_tp']} dBFS) -- there is no loudness "
            "to condition against"
        )
    applied_gain = target_lufs - input_measurement["input_i"]
    ceiling_dbtp = target_tp_dbtp

    temp = out_path.with_suffix(".tmp" + out_path.suffix)
    output_measurement: dict = {}

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if ceiling_dbtp < _ALIMITER_MIN_DBTP:
                raise PreconditionError(
                    f"{source}: peak-retry tightened the ceiling to "
                    f"{ceiling_dbtp:.2f} dBTP, below alimiter's valid range "
                    f"(>= {_ALIMITER_MIN_DBTP:.2f} dBTP); the source's true "
                    "peak is too extreme for this target to be reachable by "
                    "limiting alone"
                )
            limit = 10 ** (ceiling_dbtp / 20)
            chain = (
                f"aresample=48000,volume={applied_gain:.2f}dB,"
                f"alimiter=limit={limit:.6f}:attack={CONDITION_ATTACK_MS}:"
                f"release={CONDITION_RELEASE_MS}:level=0:latency=1"
            )
            ffmpeg.run(
                ["ffmpeg", "-hide_banner", "-y", "-i", str(source),
                 "-af", chain,
                 "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(temp)],
                log_path,
            )
            output_measurement = ffmpeg.measure_loudness(temp, log_path)

            tp_ok = output_measurement["input_tp"] <= target_tp_dbtp + TP_TOLERANCE_DB
            lufs_ok = abs(output_measurement["input_i"] - target_lufs) <= LUFS_TOLERANCE

            if tp_ok and lufs_ok:
                temp.replace(out_path)
                peak_reduction_db = (
                    (input_measurement["input_tp"] + applied_gain)
                    - output_measurement["input_tp"]
                )
                limited = peak_reduction_db > 0.05
                _log_result(
                    log_path, source, out_path, input_measurement, output_measurement,
                    applied_gain, ceiling_dbtp, attempt, peak_reduction_db,
                )
                return ConditionResult(
                    source, out_path, input_measurement, output_measurement,
                    limited, peak_reduction_db,
                )

            if not tp_ok:
                # Peak still too high -- tighten the ceiling, keep gain fixed.
                ceiling_dbtp -= (output_measurement["input_tp"] - target_tp_dbtp) + 0.2
            else:
                # tp_ok held but lufs_ok didn't: the limiter pulled loudness
                # away from target. Re-solve gain rather than accept the
                # drift -- this is the fix for the defect the second Opus
                # review round found (spec §4.1: a retry that only
                # re-checked peak silently let integrated loudness drift up
                # to 0.4 LU on real material).
                applied_gain += target_lufs - output_measurement["input_i"]

        raise PreconditionError(
            f"{source}: failed to reach target_lufs={target_lufs} / "
            f"target_tp_dbtp={target_tp_dbtp} within {MAX_ATTEMPTS} attempts; "
            f"last measurement: {output_measurement}"
        )
    finally:
        temp.unlink(missing_ok=True)


def _log_result(
    log_path: Path,
    source: Path,
    out_path: Path,
    input_measurement: dict,
    output_measurement: dict,
    applied_gain: float,
    ceiling_dbtp: float,
    attempts: int,
    peak_reduction_db: float,
) -> None:
    """A dynamics-losing fix must be visible in the QA trail, not another
    undocumented silent step (spec §4.1 step 6)."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"# condition_clip {source.name} -> {out_path.name}: "
            f"attempts={attempts} applied_gain={applied_gain:.2f}dB "
            f"ceiling={ceiling_dbtp:.2f}dBTP "
            f"input(I={input_measurement['input_i']:.2f} "
            f"TP={input_measurement['input_tp']:.2f} "
            f"LRA={input_measurement['input_lra']:.2f}) "
            f"output(I={output_measurement['input_i']:.2f} "
            f"TP={output_measurement['input_tp']:.2f} "
            f"LRA={output_measurement['input_lra']:.2f}) "
            f"peak_reduction_db={peak_reduction_db:.2f}\n"
        )
