# stitcher/stitcher/motion.py
"""Ken Burns geometry, as both Python functions and FFmpeg expressions.

Both forms implement the same closed-form maths, so the Python version can be
unit-tested directly and the expression version locked by a filtergraph golden.

`crop`'s w/h are evaluated once at init and cannot animate, which is why the
zoom must live in `scale=eval=frame` and never in the crop (spec §4 stage A).

Rounding: every value rounded in this module (scaled dimensions, crop
offsets) is non-negative by construction (zoom >= 1.0 always, anchors in
[0, 1]). FFmpeg's eval `round()` rounds half away from zero (verified against
the installed 9.0 binary: `round(2.5)` -> 3, `round(4.5)` -> 5), while
Python's builtin `round()` uses banker's rounding (`round(2.5)` -> 2). Using
the builtin here would make the Python form and the FFmpeg-expression form
silently disagree at exact `.5` ties -- a bug no test in this file would
catch unless it evaluated the emitted expression numerically. `_round_half_up`
below is used everywhere the plan's code used the builtin, so both forms
round identically.
"""

from __future__ import annotations

import math

from .spec import Canvas, Motion

ZOOMING_KINDS = {"push_in", "pull_out", "scale_up"}


def _round_half_up(x: float) -> int:
    """Round half away from zero, matching FFmpeg eval's `round()`.

    Every caller in this module only ever rounds a non-negative value, so
    round-half-away-from-zero and round-half-up coincide; the two-branch
    general form is not needed.
    """
    return math.floor(x + 0.5)


def crop_size(canvas: Canvas, supersample: int) -> tuple[int, int]:
    return canvas.width * supersample, canvas.height * supersample


# --- Python form ---------------------------------------------------------


def eased(p: float, ease: str) -> float:
    p = min(1.0, max(0.0, p))
    if ease == "ease_in":
        return p * p
    if ease == "ease_out":
        return 1.0 - (1.0 - p) ** 2
    if ease == "ease_in_out":
        return 2 * p * p if p < 0.5 else 1.0 - 2 * (1.0 - p) ** 2
    return p


def progress_at(frame: int, total_frames: int, hold_frames: int, ease: str) -> float:
    span = max(1, total_frames - hold_frames - 1)
    return eased((frame - hold_frames) / span, ease)


def zoom_at(p: float, motion: Motion) -> float:
    if motion.kind not in ZOOMING_KINDS or motion.amount_pct == 0:
        return 1.0
    amount = motion.amount_pct / 100.0
    if motion.kind == "pull_out":
        return 1.0 + amount * (1.0 - p)
    return 1.0 + amount * p


def anchor_at(p: float, motion: Motion) -> tuple[float, float]:
    start_x, start_y = motion.anchor_start
    end_x, end_y = motion.anchor_end
    return (start_x + (end_x - start_x) * p, start_y + (end_y - start_y) * p)


def crop_rect_at(
    frame: int,
    total_frames: int,
    motion: Motion,
    canvas: Canvas,
    supersample: int,
    hold_frames: int = 0,
) -> tuple[int, int, int, int]:
    """Returns (scaled_w, scaled_h, crop_x, crop_y) for one frame."""
    p = progress_at(frame, total_frames, hold_frames, motion.ease)
    zoom = zoom_at(p, motion)
    crop_w, crop_h = crop_size(canvas, supersample)
    scaled_w = _round_half_up(canvas.width * supersample * zoom)
    scaled_h = _round_half_up(canvas.height * supersample * zoom)
    anchor_x, anchor_y = anchor_at(p, motion)
    return (
        scaled_w,
        scaled_h,
        _round_half_up(anchor_x * (scaled_w - crop_w)),
        _round_half_up(anchor_y * (scaled_h - crop_h)),
    )


# --- FFmpeg expression form ----------------------------------------------
# Emitted UNQUOTED. shots.py wraps each in single quotes inside the
# filtergraph, and that quoting is what protects the commas from the parser.


def _raw_progress_expr(total_frames: int, hold_frames: int) -> str:
    span = max(1, total_frames - hold_frames - 1)
    return f"max(0,min(1,(n-{hold_frames})/{span}))"


def progress_expr(total_frames: int, hold_frames: int, ease: str) -> str:
    raw = _raw_progress_expr(total_frames, hold_frames)
    if ease == "ease_in":
        return f"pow({raw},2)"
    if ease == "ease_out":
        return f"(1-pow(1-{raw},2))"
    if ease == "ease_in_out":
        return f"if(lt({raw},0.5),2*pow({raw},2),1-2*pow(1-{raw},2))"
    return raw


def _zoom_expr(motion: Motion, progress: str) -> str:
    if motion.kind not in ZOOMING_KINDS or motion.amount_pct == 0:
        return "1"
    amount = motion.amount_pct / 100.0
    if motion.kind == "pull_out":
        return f"(1+{amount}*(1-{progress}))"
    return f"(1+{amount}*{progress})"


def _anchor_expr(start: float, end: float, progress: str) -> str:
    return str(start) if start == end else f"({start}+{end - start}*{progress})"


def scale_exprs(
    motion: Motion, canvas: Canvas, supersample: int, total_frames: int, hold_frames: int
) -> tuple[str, str]:
    base_w = canvas.width * supersample
    base_h = canvas.height * supersample
    if motion.kind not in ZOOMING_KINDS or motion.amount_pct == 0:
        return str(base_w), str(base_h)
    zoom = _zoom_expr(motion, progress_expr(total_frames, hold_frames, motion.ease))
    return f"round({base_w}*{zoom})", f"round({base_h}*{zoom})"


def crop_exprs(
    motion: Motion, canvas: Canvas, supersample: int, total_frames: int, hold_frames: int
) -> tuple[str, str]:
    crop_w, crop_h = crop_size(canvas, supersample)
    static_anchor = motion.anchor_start == motion.anchor_end
    no_zoom = motion.kind not in ZOOMING_KINDS or motion.amount_pct == 0
    if no_zoom and static_anchor:
        return "0", "0"

    progress = progress_expr(total_frames, hold_frames, motion.ease)
    scale_w, scale_h = scale_exprs(motion, canvas, supersample, total_frames, hold_frames)
    anchor_x = _anchor_expr(motion.anchor_start[0], motion.anchor_end[0], progress)
    anchor_y = _anchor_expr(motion.anchor_start[1], motion.anchor_end[1], progress)
    return (
        f"round({anchor_x}*({scale_w}-{crop_w}))",
        f"round({anchor_y}*({scale_h}-{crop_h}))",
    )
