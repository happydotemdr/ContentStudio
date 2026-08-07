# stitcher/tests/test_motion.py
import math
import re

import pytest

from stitcher import motion as mo
from stitcher.spec import Canvas, Motion

CANVAS = Canvas(width=1080, height=1920, fps=30)


def test_eased_endpoints_are_fixed_for_every_curve():
    for ease in ("linear", "ease_in", "ease_out", "ease_in_out"):
        assert mo.eased(0.0, ease) == pytest.approx(0.0)
        assert mo.eased(1.0, ease) == pytest.approx(1.0)


def test_ease_out_starts_faster_than_linear():
    assert mo.eased(0.25, "ease_out") > 0.25


def test_ease_in_starts_slower_than_linear():
    assert mo.eased(0.25, "ease_in") < 0.25


def test_progress_is_zero_during_the_hold():
    assert mo.progress_at(0, 90, 30, "linear") == pytest.approx(0.0)
    assert mo.progress_at(29, 90, 30, "linear") == pytest.approx(0.0)
    assert mo.progress_at(30, 90, 30, "linear") == pytest.approx(0.0)


def test_progress_reaches_one_on_the_last_frame():
    assert mo.progress_at(89, 90, 30, "linear") == pytest.approx(1.0)


def test_progress_is_safe_on_a_single_frame_shot():
    assert mo.progress_at(0, 1, 0, "linear") == pytest.approx(0.0)


def test_zoom_runs_from_one_upward_for_push_in():
    motion = Motion(kind="push_in", amount_pct=15)
    assert mo.zoom_at(0.0, motion) == pytest.approx(1.0)
    assert mo.zoom_at(1.0, motion) == pytest.approx(1.15)


def test_zoom_runs_downward_for_pull_out():
    motion = Motion(kind="pull_out", amount_pct=15)
    assert mo.zoom_at(0.0, motion) == pytest.approx(1.15)
    assert mo.zoom_at(1.0, motion) == pytest.approx(1.0)


def test_zoom_is_flat_for_kind_none():
    motion = Motion(kind="none", amount_pct=15)
    assert mo.zoom_at(0.0, motion) == pytest.approx(1.0)
    assert mo.zoom_at(1.0, motion) == pytest.approx(1.0)


def test_equal_anchors_give_a_pure_centred_push():
    motion = Motion(kind="push_in", amount_pct=20,
                    anchor_start=(0.5, 0.5), anchor_end=(0.5, 0.5))
    _, _, x_start, y_start = mo.crop_rect_at(0, 60, motion, CANVAS, 4)
    scaled_w, scaled_h, x_end, y_end = mo.crop_rect_at(59, 60, motion, CANVAS, 4)
    crop_w, crop_h = mo.crop_size(CANVAS, 4)
    assert (x_start, y_start) == (0, 0)
    assert x_end == round(0.5 * (scaled_w - crop_w))
    assert y_end == round(0.5 * (scaled_h - crop_h))


def test_anchor_zero_pins_the_left_edge():
    motion = Motion(kind="push_in", amount_pct=20,
                    anchor_start=(0.0, 0.0), anchor_end=(0.0, 0.0))
    _, _, x_end, y_end = mo.crop_rect_at(59, 60, motion, CANVAS, 4)
    assert (x_end, y_end) == (0, 0)


def test_anchor_one_pins_the_right_edge():
    motion = Motion(kind="push_in", amount_pct=20,
                    anchor_start=(1.0, 1.0), anchor_end=(1.0, 1.0))
    scaled_w, scaled_h, x_end, y_end = mo.crop_rect_at(59, 60, motion, CANVAS, 4)
    crop_w, crop_h = mo.crop_size(CANVAS, 4)
    assert x_end == scaled_w - crop_w
    assert y_end == scaled_h - crop_h


def test_unequal_anchors_produce_drift():
    drifting = Motion(kind="push_in", amount_pct=15,
                      anchor_start=(0.5, 0.5), anchor_end=(0.5, 0.2))
    steady = Motion(kind="push_in", amount_pct=15,
                    anchor_start=(0.5, 0.5), anchor_end=(0.5, 0.5))
    _, _, _, drift_y = mo.crop_rect_at(59, 60, drifting, CANVAS, 4)
    _, _, _, steady_y = mo.crop_rect_at(59, 60, steady, CANVAS, 4)
    assert drift_y < steady_y


def test_crop_size_is_the_canvas_times_the_supersample():
    assert mo.crop_size(CANVAS, 4) == (4320, 7680)
    assert mo.crop_size(CANVAS, 1) == (1080, 1920)


def test_crop_never_escapes_the_scaled_source():
    motion = Motion(kind="push_in", amount_pct=30, anchor_end=(1.0, 1.0))
    crop_w, crop_h = mo.crop_size(CANVAS, 4)
    for frame in range(60):
        scaled_w, scaled_h, x, y = mo.crop_rect_at(frame, 60, motion, CANVAS, 4)
        assert 0 <= x <= scaled_w - crop_w
        assert 0 <= y <= scaled_h - crop_h


def test_expressions_reference_the_frame_variable_and_are_emitted_unquoted():
    w_expr, h_expr = mo.scale_exprs(Motion(kind="push_in", amount_pct=15), CANVAS, 4, 60, 0)
    x_expr, y_expr = mo.crop_exprs(Motion(kind="push_in", amount_pct=15), CANVAS, 4, 60, 0)
    for expr in (w_expr, h_expr, x_expr, y_expr):
        assert "n" in expr
        assert "'" not in expr


def test_a_static_motion_emits_constant_expressions():
    w_expr, h_expr = mo.scale_exprs(Motion(kind="none"), CANVAS, 4, 60, 0)
    x_expr, y_expr = mo.crop_exprs(Motion(kind="none"), CANVAS, 4, 60, 0)
    assert w_expr == "4320"
    assert h_expr == "7680"
    assert x_expr == "0"
    assert y_expr == "0"


def test_hold_frames_delay_the_move_in_both_forms():
    motion = Motion(kind="push_in", amount_pct=20, hold_s=1.0)
    _, _, x_at_hold, _ = mo.crop_rect_at(29, 90, motion, CANVAS, 4, hold_frames=30)
    _, _, x_after, _ = mo.crop_rect_at(89, 90, motion, CANVAS, 4, hold_frames=30)
    assert x_at_hold == 0
    assert x_after > 0
    assert "30" in mo.progress_expr(90, 30, "linear")


# --- Cross-check: the Python form and the FFmpeg-expression form must agree ---
#
# None of the tests above evaluate the emitted expression strings numerically --
# they only check syntactic properties (references "n", has no quotes) or the
# fully-static degenerate case. A silent divergence between crop_rect_at and
# scale_exprs/crop_exprs would produce a render that is wrong in a way no test
# above would catch (task-6 brief, "Things to watch" #1). This section evaluates
# the expressions and compares them against crop_rect_at directly.
#
# The evaluator below is a faithful re-implementation of FFmpeg eval semantics
# for the specific function set this module emits (round, pow, min, max, if,
# lt). Its round() was verified against the real installed ffmpeg 9.0 binary
# before writing this file:
#
#   ffmpeg -f lavfi -i "color=c=black:s=16x16:d=0.1" -update 1 \
#     -vf "scale=w='round(2.5)':h='round(4.5)'" -frames:v 1 out.png
#   -> output is 3x5
#
# i.e. FFmpeg's round() rounds half away from zero (round(2.5) == 3,
# round(4.5) == 5), NOT Python's builtin round() (round(2.5) == 2, banker's
# rounding). motion.py's _round_half_up matches the ffmpeg behavior; this
# evaluator's round() must match it too or the cross-check would be comparing
# two things that already agree by construction.


def _eval_ffmpeg_expr(expr: str, n: int) -> float:
    """Evaluate one of this module's emitted expression strings for frame n."""
    # "if" and "lt" are Python keywords/builtins that cannot be called as
    # bare identifiers the way FFmpeg's eval functions can; rename them.
    safe = re.sub(r"\bif\(", "_ff_if(", expr)
    safe = re.sub(r"\blt\(", "_ff_lt(", safe)
    namespace = {
        "n": n,
        "round": lambda x: math.floor(x + 0.5),  # matches ffmpeg eval round(), verified above
        "pow": pow,
        "min": min,
        "max": max,
        "_ff_if": lambda cond, a, b: a if cond else b,
        "_ff_lt": lambda a, b: 1 if a < b else 0,
    }
    return eval(safe, {"__builtins__": {}}, namespace)  # noqa: S307 - fixed internal expression, not user input


CROSS_CHECK_CASES = [
    # label, motion, total_frames, hold_frames, supersample
    ("push_in_linear_centered", Motion(kind="push_in", amount_pct=15), 60, 0, 4),
    ("push_in_ease_in_drift", Motion(
        kind="push_in", amount_pct=20, ease="ease_in",
        anchor_start=(0.5, 0.5), anchor_end=(0.5, 0.2)), 60, 0, 4),
    ("pull_out_ease_out_drift", Motion(
        kind="pull_out", amount_pct=25, ease="ease_out",
        anchor_start=(0.2, 0.8), anchor_end=(0.8, 0.2)), 90, 0, 4),
    ("push_in_ease_in_out_with_hold", Motion(
        kind="push_in", amount_pct=10, ease="ease_in_out"), 90, 15, 4),
    ("scale_up_anchor_pinned_zero", Motion(
        kind="scale_up", amount_pct=30,
        anchor_start=(0.0, 0.0), anchor_end=(0.0, 0.0)), 60, 0, 4),
    ("scale_up_anchor_pinned_one", Motion(
        kind="scale_up", amount_pct=30,
        anchor_start=(1.0, 1.0), anchor_end=(1.0, 1.0)), 60, 0, 4),
    ("kind_none_zoom_exactly_one", Motion(kind="none"), 60, 0, 4),
    ("zero_amount_pct_zoom_exactly_one", Motion(kind="push_in", amount_pct=0), 60, 0, 4),
    ("hold_frames_equals_total_frames", Motion(kind="push_in", amount_pct=20), 30, 30, 4),
    ("single_frame_shot", Motion(kind="push_in", amount_pct=20), 1, 0, 4),
    ("supersample_one_no_oversampling", Motion(
        kind="push_in", amount_pct=15, anchor_end=(1.0, 1.0)), 60, 0, 1),
]


@pytest.mark.parametrize(
    "label,motion,total_frames,hold_frames,supersample", CROSS_CHECK_CASES
)
def test_ffmpeg_expressions_agree_exactly_with_the_python_form(
    label, motion, total_frames, hold_frames, supersample
):
    w_expr, h_expr = mo.scale_exprs(motion, CANVAS, supersample, total_frames, hold_frames)
    x_expr, y_expr = mo.crop_exprs(motion, CANVAS, supersample, total_frames, hold_frames)

    candidate_frames = (
        0, 1, hold_frames - 1, hold_frames, hold_frames + 1,
        total_frames // 2, total_frames - 2, total_frames - 1,
    )
    frames = sorted({f for f in candidate_frames if 0 <= f < total_frames}) or [0]

    for frame in frames:
        expected = mo.crop_rect_at(frame, total_frames, motion, CANVAS, supersample, hold_frames)
        actual = (
            _eval_ffmpeg_expr(w_expr, frame),
            _eval_ffmpeg_expr(h_expr, frame),
            _eval_ffmpeg_expr(x_expr, frame),
            _eval_ffmpeg_expr(y_expr, frame),
        )
        assert actual == expected, (
            f"{label} frame {frame}: python form {expected} != "
            f"ffmpeg-expression form {actual}\n"
            f"  scale: w={w_expr!r} h={h_expr!r}\n"
            f"  crop:  x={x_expr!r} y={y_expr!r}"
        )
