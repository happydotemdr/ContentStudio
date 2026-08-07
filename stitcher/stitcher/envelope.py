"""The ducking envelope: a deterministic gain schedule, not a compressor.

Every dB value here is RELATIVE TO THE VOICE REFERENCE. audio.py measures the
assembled voice track once and adds the single constant offset that turns
these into absolute gains (spec §3, §4 stage C).

Precedence is window > duck > baseline. The attack ramp COMPLETES at stem
onset, so the bed is already down when the voice arrives rather than ducking
after the first syllable; the release ramp BEGINS at stem offset.

Two faces, one math: `level_at` (Python) and `volume_expr` (FFmpeg `eval`
expression) must agree exactly. `volume_expr` achieves this not by computing
a linear gain in Python and formatting it (which risks tiny SILENCE_DB
values printing in scientific notation FFmpeg's expression parser can choke
on), but by interpolating the same dB breakpoints `level_at` interpolates
and only converting dB -> linear gain symbolically, via `pow(10, db/20)`,
inside the emitted expression itself. Both forms therefore do the identical
piecewise-linear-in-dB interpolation; only the point of evaluation (Python
vs. ffmpeg `eval`) differs. See test_envelope.py's cross-check section for
the numeric proof against the real ffmpeg binary.
"""

from __future__ import annotations

from dataclasses import dataclass

from .spec import Bed, Stem

SILENCE_DB = -100.0
_STEP = 0.001  # 1ms, so a window edge is a fast ramp rather than a discontinuity


@dataclass(frozen=True)
class Breakpoint:
    t: float
    db: float


def stem_spans(
    stems: list[Stem], durations: dict[str, float]
) -> list[tuple[float, float]]:
    """(start, end) for each stem. Real file duration wins over duration_s."""
    spans: list[tuple[float, float]] = []
    for stem in stems:
        length = durations.get(stem.file, stem.duration_s)
        if length is None:
            raise ValueError(
                f"stem {stem.id!r} has neither a probed duration nor duration_s"
            )
        spans.append((stem.at, stem.at + length))
    return spans


def _duck_level(
    t: float, spans: list[tuple[float, float]], bed: Bed
) -> float:
    """Baseline, ducked, or mid-ramp — taking the most ducked of all spans."""
    attack = bed.duck_attack_ms / 1000.0
    release = bed.duck_release_ms / 1000.0
    level = bed.gain_db
    for start, end in spans:
        if start - attack <= t < start and attack > 0:
            progress = (t - (start - attack)) / attack
            candidate = bed.gain_db + (bed.duck_db - bed.gain_db) * progress
        elif start <= t <= end:
            candidate = bed.duck_db
        elif end < t <= end + release and release > 0:
            progress = (t - end) / release
            candidate = bed.duck_db + (bed.gain_db - bed.duck_db) * progress
        else:
            continue
        level = min(level, candidate)
    return level


def _window_level(t: float, bed: Bed) -> float | None:
    """The active window's level at `t`, or None if no window covers it.

    Windows are validated non-overlapping at spec load (spec.py
    validate_spec), so precedence among windows never arises here — at
    most one window can match any given `t`.
    """
    for window in bed.windows:
        if window.start <= t < window.end:
            if window.level_db is not None:
                return window.level_db
            if window.mode == "out":
                return SILENCE_DB
            if window.mode == "ducked":
                return bed.duck_db
            return bed.gain_db
    return None


def _fade_attenuation(t: float, bed: Bed) -> float:
    """Additive dB attenuation from any fade covering t. Zero elsewhere."""
    attenuation = 0.0
    for fade in bed.fades:
        length = fade.ms / 1000.0
        if length <= 0:
            continue
        if fade.kind == "in" and fade.at <= t < fade.at + length:
            progress = (t - fade.at) / length
            attenuation = min(attenuation, SILENCE_DB * (1.0 - progress))
        elif fade.kind == "out" and fade.at - length < t <= fade.at:
            progress = (t - (fade.at - length)) / length
            attenuation = min(attenuation, SILENCE_DB * progress)
    return attenuation


def _level(t: float, bed: Bed, spans: list[tuple[float, float]]) -> float:
    """Precedence: an active window governs outright; otherwise duck/baseline."""
    base = _window_level(t, bed)
    if base is None:
        base = _duck_level(t, spans, bed)
    return max(SILENCE_DB, base + _fade_attenuation(t, bed))


def build_breakpoints(
    bed: Bed, spans: list[tuple[float, float]], runtime: float
) -> list[Breakpoint]:
    """Sample the envelope at every time where its slope can change."""
    attack = bed.duck_attack_ms / 1000.0
    release = bed.duck_release_ms / 1000.0

    times: set[float] = {0.0, runtime}
    for start, end in spans:
        times.update({start - attack, start, end, end + release})
    for window in bed.windows:
        # Both edges need a point just inside and just outside the window so
        # the window's level holds FLAT across its span and only transitions
        # fast (over _STEP) at the boundary -- not a slow ramp smeared across
        # the whole window. window.end is exclusive in _window_level, so
        # window.end itself already reads as "outside"; without end - _STEP
        # there is no breakpoint left that still carries the window's value,
        # and the interpolation from window.start's value to window.end's
        # post-window value would bleed across the entire window (a real bug
        # the plan's original code had, caught by
        # test_a_window_ending_exactly_at_the_runtime_holds_to_the_end).
        times.update({
            window.start - _STEP, window.start,
            window.end - _STEP, window.end, window.end + _STEP,
        })
    for fade in bed.fades:
        length = fade.ms / 1000.0
        if fade.kind == "in":
            times.update({fade.at, fade.at + length})
        else:
            times.update({fade.at - length, fade.at})

    ordered = sorted({round(t, 6) for t in times if 0.0 <= t <= runtime})
    return [Breakpoint(t, _level(t, bed, spans)) for t in ordered]


def level_at(breakpoints: list[Breakpoint], t: float) -> float:
    """Linear interpolation between breakpoints; clamped at both ends."""
    if not breakpoints:
        return 0.0
    if t <= breakpoints[0].t:
        return breakpoints[0].db
    if t >= breakpoints[-1].t:
        return breakpoints[-1].db
    for left, right in zip(breakpoints, breakpoints[1:]):
        if left.t <= t <= right.t:
            if right.t == left.t:
                return right.db
            progress = (t - left.t) / (right.t - left.t)
            return left.db + (right.db - left.db) * progress
    return breakpoints[-1].db


def volume_expr(breakpoints: list[Breakpoint]) -> str:
    """Nested-if FFmpeg expression over t, emitted UNQUOTED.

    audio.py wraps it in single quotes inside the filtergraph, and that
    quoting is what protects the commas from the filter parser -- this
    function itself must never emit a `'` (see test), and doesn't: every
    token it emits is a digit, operator, or one of a fixed set of function
    names.
    """
    unique: list[Breakpoint] = []
    for point in breakpoints:
        if not unique or point.t != unique[-1].t:
            unique.append(point)
    if not unique:
        return "1"
    if len(unique) == 1:
        return f"pow(10,{unique[0].db}/20)"

    def segment(left: Breakpoint, right: Breakpoint) -> str:
        slope = (right.db - left.db) / (right.t - left.t)
        return f"pow(10,({left.db}+{slope}*(t-{left.t}))/20)"

    expr = segment(unique[-2], unique[-1])
    for index in range(len(unique) - 2, 0, -1):
        left, right = unique[index - 1], unique[index]
        expr = f"if(lt(t,{right.t}),{segment(left, right)},{expr})"
    return expr
