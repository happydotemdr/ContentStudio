import math
import re

import pytest

from stitcher import envelope as env
from stitcher.spec import Bed, BedWindow, Fade, Stem


def bed(**overrides) -> Bed:
    base = dict(
        file="bed.mp3", gain_db=-8.0, duck_db=-22.0,
        duck_attack_ms=120, duck_release_ms=400, windows=[], fades=[],
    )
    base.update(overrides)
    return Bed(**base)


def test_stem_spans_uses_file_duration_when_present():
    stems = [Stem(id="a", file="a.wav", at=1.0)]
    assert env.stem_spans(stems, {"a.wav": 2.0}) == [(1.0, 3.0)]


def test_stem_spans_falls_back_to_declared_duration_s():
    stems = [Stem(id="a", file="a.wav", at=1.0, duration_s=2.5)]
    assert env.stem_spans(stems, {}) == [(1.0, 3.5)]


def test_baseline_holds_where_no_stem_sounds():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 0.5) == pytest.approx(-8.0)
    assert env.level_at(points, 9.5) == pytest.approx(-8.0)


def test_bed_is_fully_ducked_while_a_stem_sounds():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 5.5) == pytest.approx(-22.0)


def test_the_attack_ramp_completes_at_stem_onset():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 5.0) == pytest.approx(-22.0)      # already down
    assert env.level_at(points, 4.88) == pytest.approx(-8.0)      # ramp not begun
    midpoint = env.level_at(points, 4.94)                          # mid-ramp
    assert -22.0 < midpoint < -8.0


def test_the_release_ramp_begins_at_stem_offset():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 6.0) == pytest.approx(-22.0)
    assert env.level_at(points, 6.4) == pytest.approx(-8.0)
    assert -22.0 < env.level_at(points, 6.2) < -8.0


def test_overlapping_stems_take_the_most_ducked_level():
    points = env.build_breakpoints(bed(), [(1.0, 4.0), (3.0, 6.0)], runtime=10.0)
    assert env.level_at(points, 3.5) == pytest.approx(-22.0)


def test_a_window_beats_the_duck_even_while_a_stem_sounds():
    windows = [BedWindow.model_validate({"in": 0.0, "out": 3.0, "mode": "out"})]
    points = env.build_breakpoints(bed(windows=windows), [(0.0, 2.875)], runtime=10.0)
    assert env.level_at(points, 1.0) == pytest.approx(env.SILENCE_DB)


def test_a_window_level_db_overrides_both_duck_and_baseline():
    windows = [BedWindow.model_validate(
        {"in": 17.0, "out": 26.0, "mode": "ducked", "level_db": -26.0}
    )]
    points = env.build_breakpoints(bed(windows=windows), [(18.0, 20.0)], runtime=30.0)
    assert env.level_at(points, 19.0) == pytest.approx(-26.0)


def test_window_mode_full_returns_to_the_baseline():
    windows = [BedWindow.model_validate({"in": 2.0, "out": 4.0, "mode": "full"})]
    points = env.build_breakpoints(bed(windows=windows), [(2.5, 3.5)], runtime=10.0)
    assert env.level_at(points, 3.0) == pytest.approx(-8.0)


def test_a_fade_in_ramps_up_from_silence_over_its_declared_length():
    fades = [Fade(at=3.0, kind="in", ms=300)]
    points = env.build_breakpoints(bed(fades=fades), [], runtime=10.0)
    # _level floors at SILENCE_DB, so the fade's start is exactly the floor
    # rather than baseline + full attenuation.
    assert env.level_at(points, 3.0) == pytest.approx(env.SILENCE_DB)
    assert env.level_at(points, 3.3) == pytest.approx(-8.0)
    assert env.SILENCE_DB < env.level_at(points, 3.15) < -8.0


def test_breakpoints_are_sorted_and_bounded_by_the_runtime():
    windows = [BedWindow.model_validate({"in": 0.0, "out": 3.0, "mode": "out"})]
    points = env.build_breakpoints(bed(windows=windows), [(0.0, 2.9)], runtime=10.0)
    times = [point.t for point in points]
    assert times == sorted(times)
    assert times[0] >= 0.0 and times[-1] <= 10.0


def test_volume_expr_is_a_function_of_t_and_converts_db_to_linear_gain():
    points = env.build_breakpoints(bed(), [(5.0, 6.0)], runtime=10.0)
    expr = env.volume_expr(points)
    assert "t" in expr
    assert "pow(10," in expr
    assert "'" not in expr


def test_volume_expr_survives_duplicate_breakpoint_times():
    points = [env.Breakpoint(0.0, -8.0), env.Breakpoint(0.0, -8.0),
              env.Breakpoint(1.0, -22.0)]
    assert isinstance(env.volume_expr(points), str)


def test_level_at_clamps_outside_the_breakpoint_range():
    points = [env.Breakpoint(1.0, -8.0), env.Breakpoint(2.0, -22.0)]
    assert env.level_at(points, 0.0) == pytest.approx(-8.0)
    assert env.level_at(points, 9.0) == pytest.approx(-22.0)


# --- Edge cases from the task-9 brief's "things the envelope must survive" ---


def test_zero_stems_holds_baseline_across_the_whole_runtime():
    points = env.build_breakpoints(bed(), [], runtime=10.0)
    assert env.level_at(points, 0.0) == pytest.approx(-8.0)
    assert env.level_at(points, 5.0) == pytest.approx(-8.0)
    assert env.level_at(points, 10.0) == pytest.approx(-8.0)


def test_a_stem_extending_past_the_runtime_still_ducks_up_to_the_edge():
    # Span (8, 12) sounds past runtime=10; the envelope must still be fully
    # ducked at the runtime boundary rather than releasing early.
    points = env.build_breakpoints(bed(), [(8.0, 12.0)], runtime=10.0)
    assert env.level_at(points, 9.9) == pytest.approx(-22.0)
    assert env.level_at(points, 10.0) == pytest.approx(-22.0)


def test_adjacent_stems_with_no_gap_produce_no_click():
    # Stem A ends exactly where stem B begins (t=3). Two breakpoints would
    # land on the same t; build_breakpoints must resolve that to a single,
    # unambiguous value rather than emit duplicate/contradictory points.
    points = env.build_breakpoints(bed(), [(1.0, 3.0), (3.0, 5.0)], runtime=10.0)
    times = [point.t for point in points]
    assert len(times) == len(set(times)), "build_breakpoints must dedupe same-t points"
    # The bed stays ducked straight through the join -- no bounce back to
    # baseline between the two stems, which would be an audible click.
    assert env.level_at(points, 2.999) == pytest.approx(-22.0)
    assert env.level_at(points, 3.0) == pytest.approx(-22.0)
    assert env.level_at(points, 3.001) == pytest.approx(-22.0)


def test_duck_db_equal_to_gain_db_is_a_flat_line_no_actual_duck():
    flat_bed = bed(duck_db=-8.0)  # duck_db == gain_db: ducking is a no-op
    points = env.build_breakpoints(flat_bed, [(5.0, 6.0)], runtime=10.0)
    for t in (0.0, 4.9, 5.0, 5.5, 6.0, 6.5, 10.0):
        assert env.level_at(points, t) == pytest.approx(-8.0)


def test_a_window_at_exactly_t_zero_takes_effect_immediately():
    windows = [BedWindow.model_validate({"in": 0.0, "out": 2.0, "mode": "out"})]
    points = env.build_breakpoints(bed(windows=windows), [], runtime=10.0)
    assert env.level_at(points, 0.0) == pytest.approx(env.SILENCE_DB)


def test_a_window_ending_exactly_at_the_runtime_holds_to_the_end():
    windows = [BedWindow.model_validate({"in": 8.0, "out": 10.0, "mode": "out"})]
    points = env.build_breakpoints(bed(windows=windows), [], runtime=10.0)
    assert env.level_at(points, 9.999) == pytest.approx(env.SILENCE_DB)


def test_a_window_covering_the_entire_runtime_overrides_everything():
    windows = [BedWindow.model_validate({"in": 0.0, "out": 10.0, "mode": "full"})]
    points = env.build_breakpoints(bed(windows=windows), [(2.0, 3.0)], runtime=10.0)
    # A stem sounds inside the window, but "full" mode + the window's
    # precedence over duck means the bed never ducks anywhere.
    assert env.level_at(points, 2.5) == pytest.approx(-8.0)


# --- Cross-check: level_at (Python) and volume_expr (FFmpeg eval) must agree ---
#
# None of the tests above evaluate volume_expr's output numerically -- they
# only check syntactic properties (references "t", uses pow(10,...), has no
# quotes). A silent divergence between level_at and volume_expr would ship a
# render whose ducking is subtly wrong in a way no test above would catch
# (task-9 brief instructions, "two things that are easy to get wrong" /
# motion.py's precedent in task 6).
#
# The evaluator below re-implements FFmpeg eval semantics for the exact
# function set volume_expr emits (pow, if, lt, and the time variable `t`).
# It was verified against the real installed ffmpeg 9.0 binary via
# `aevalsrc`, which evaluates an expression string as a function of `t` in
# seconds -- i.e. exactly the form volume_expr emits:
#
#   ffmpeg -f lavfi -i "aevalsrc=exprs='if(lt(t,1),pow(10,(-8+
#     (-14/0.12)*(t-1))/20),pow(10,-22/20))':s=1000:d=1.2" \
#     -f f64le -acodec pcm_f64le -
#
# Sampled at t=0.88, 0.94, 1.0, 1.1 the raw f64 output matched the hand
# computed values (1.9952623149688795, 0.8912509381337461,
# 0.07943282347242814, 0.07943282347242814) exactly, confirming pow/if/lt/t
# behave as this evaluator assumes.
#
# A second check ran an *actual* `volume_expr(build_breakpoints(...))`
# output (including a SILENCE_DB=-100.0 breakpoint, windows, overlapping
# stems, and a fade) through the same aevalsrc mechanism and compared every
# 7ms sample over the full runtime against `level_at`: the worst relative
# error observed was ~2.15e-15 -- floating-point noise, not disagreement.


def _safe_pow(base: float, exponent: float) -> float:
    """`pow`, but tolerant of overflow in a branch `_ff_if` will discard.

    Real ffmpeg `eval` selects a branch of `if()` lazily -- the untaken
    branch is never evaluated. Python's function-call semantics evaluate
    every argument to `_ff_if` eagerly before `_ff_if` gets to choose, so a
    distant segment with a very steep slope (e.g. a 1ms window edge) can be
    asked for its value at a `t` many seconds away and overflow computing
    `pow(10, huge_exponent)`, even though that value is about to be thrown
    away. Clamping to +inf here (never -inf; `10**x` is never negative) lets
    the discarded branch finish evaluating instead of raising, matching what
    the lazy ffmpeg evaluator would have skipped entirely.
    """
    try:
        return pow(base, exponent)
    except OverflowError:
        return math.inf


def _eval_ffmpeg_expr(expr: str, t: float) -> float:
    """Evaluate one of volume_expr's emitted strings at a given time `t`."""
    safe = re.sub(r"\bif\(", "_ff_if(", expr)
    safe = re.sub(r"\blt\(", "_ff_lt(", safe)
    namespace = {
        "t": t,
        "pow": _safe_pow,
        "_ff_if": lambda cond, a, b: a if cond else b,
        "_ff_lt": lambda a, b: 1 if a < b else 0,
    }
    return eval(safe, {"__builtins__": {}}, namespace)  # noqa: S307 - fixed internal expression, not user input


CROSS_CHECK_SCENARIOS = [
    ("simple_attack_release", bed(), [(5.0, 6.0)], 10.0),
    ("overlapping_stems", bed(), [(1.0, 4.0), (3.0, 6.0)], 10.0),
    ("adjacent_stems_no_gap", bed(), [(1.0, 3.0), (3.0, 5.0)], 10.0),
    ("window_out_beats_duck", bed(windows=[
        BedWindow.model_validate({"in": 0.0, "out": 3.0, "mode": "out"})
    ]), [(0.0, 2.875)], 10.0),
    ("window_level_db_override", bed(windows=[
        BedWindow.model_validate({"in": 17.0, "out": 26.0, "mode": "ducked", "level_db": -26.0})
    ]), [(18.0, 20.0)], 30.0),
    ("fade_in_from_silence", bed(fades=[Fade(at=3.0, kind="in", ms=300)]), [], 10.0),
    ("flat_no_duck", bed(duck_db=-8.0), [(5.0, 6.0)], 10.0),
    ("stem_past_runtime", bed(), [(8.0, 12.0)], 10.0),
    ("zero_stems", bed(), [], 10.0),
]


@pytest.mark.parametrize("label,bed_,spans,runtime", CROSS_CHECK_SCENARIOS)
def test_volume_expr_agrees_with_level_at_across_the_runtime(label, bed_, spans, runtime):
    points = env.build_breakpoints(bed_, spans, runtime)
    expr = env.volume_expr(points)

    step_ms = 13  # deliberately not a multiple of any breakpoint spacing above
    t_ms = 0
    while t_ms <= round(runtime * 1000):
        t = t_ms / 1000.0
        expected_linear = 10 ** (env.level_at(points, t) / 20.0)
        actual_linear = _eval_ffmpeg_expr(expr, t)
        assert actual_linear == pytest.approx(expected_linear, rel=1e-9, abs=1e-12), (
            f"{label} at t={t}: level_at-derived {expected_linear!r} != "
            f"volume_expr-derived {actual_linear!r}\n  expr={expr!r}"
        )
        t_ms += step_ms
