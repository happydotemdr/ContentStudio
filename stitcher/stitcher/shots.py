# stitcher/stitcher/shots.py
"""Stage A: render one conformed, near-lossless clip per shot.

Every clip leaves this stage with identical codec, pix_fmt, timebase, SAR and
frame rate, because the concat demuxer in stage D refuses anything else.

Whip transitions are applied HERE, not in stage D: a shot renders its own head
whip when its own transition_in is a whip, and its own tail whip when the NEXT
shot's transition_in is a whip. That is why a shot's cache key includes its
successor's transition (spec §4 stage A).
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg, motion
from .cache import Manifest, file_digest, payload_digest
from .naming import SUPERSAMPLE_DRAFT, SUPERSAMPLE_FINAL, Workspace
from .overlays import render_placeholder
from .spec import Canvas, Motion, RenderSpec, Shot, Transition, shot_frame_bounds

WHIP_BLUR_PX = 40

INTERMEDIATE_PIX_FMT = "yuv444p"
INTERMEDIATE_CRF_FINAL = 12
INTERMEDIATE_CRF_DRAFT = 28
INTERMEDIATE_PRESET_FINAL = "veryfast"
INTERMEDIATE_PRESET_DRAFT = "ultrafast"

# Verified against the installed ffmpeg 9.0 binary with the h264 `trace_headers`
# bitstream filter: the generic top-level `-colorspace`/`-color_primaries`/
# `-color_trc` output options do NOT reliably reach libx264's VUI on this
# build. `-colorspace bt709` alone lands (matrix_coefficients=1 in the
# decoded SPS), but `-color_primaries bt709 -color_trc bt709` do not --
# colour_primaries and transfer_characteristics come back `2` (Unspecified)
# regardless of what is requested generically, confirmed by decoding the
# muxed output with `ffmpeg -i out.mkv -c copy -bsf:v trace_headers -f null -`.
# Routing colorprim/transfer/colormatrix through `-x264-params` does set them.
# This is a real divergence from the plan, which specified the generic flags.
#
# `range=tv` inside the same -x264-params string does NOT work on this
# libx264 core (r3223): it logs "Error parsing option 'range = tv'." and is
# silently dropped, confirmed with the isolated key-by-key test above. It is
# also unnecessary: the scale filter's `out_range=tv` (see _colour_scale)
# already tags the AVFrame's color_range, and libx264 reads that frame field
# automatically to set video_full_range_flag=0 -- verified correct via
# trace_headers with no explicit range option at all. So range is omitted
# here rather than passed as a parameter that errors on every render.
_X264_PARAMS_BT709 = "colorprim=bt709:transfer=bt709:colormatrix=bt709"


def conform_size(canvas: Canvas, shot_motion: Motion) -> tuple[int, int]:
    """Cover size that leaves headroom for the maximum zoom.

    Conforming to canvas * z_max means the animated scale is a pure supersample
    at full zoom rather than an upscale of already-discarded detail.
    """
    if shot_motion.kind in motion.ZOOMING_KINDS and shot_motion.amount_pct:
        z_max = 1.0 + shot_motion.amount_pct / 100.0
    else:
        z_max = 1.0
    return round(canvas.width * z_max), round(canvas.height * z_max)


def _colour_scale(canvas: Canvas) -> str:
    return (
        f"scale={canvas.width}:{canvas.height}:flags=lanczos"
        ":out_color_matrix=bt709:out_range=tv"
    )


def whip_filters(
    direction: str, frames: int, total_frames: int, at_head: bool, canvas: Canvas
) -> list[str]:
    """A directional blur gated to the whip's frames.

    `avgblur` rather than `boxblur`, for two reasons: it takes separate
    sizeX/sizeY so the blur is actually directional, and boxblur's radii are
    evaluated once at init with expressions that cannot reference n or t, so a
    per-frame ramp is not expressible there at all. Verified against the
    installed 9.0 binary (`ffmpeg -h filter=avgblur`): it takes distinct
    sizeX/sizeY options and reports timeline (`enable=`) support.

    The effect is gated with `enable=` at a fixed radius rather than ramped.
    Over four frames a constant directional blur is indistinguishable from a
    ramped one, and it needs no per-frame expression support.

    No slide: a translate would drag un-rendered content in at the trailing
    edge, and FFmpeg has no edge-clamping pad. See this task's preamble.
    """
    if at_head:
        window = f"lt(n,{frames})"
    else:
        window = f"gte(n,{max(0, total_frames - frames)})"

    horizontal = direction in ("left", "right")
    size_x = WHIP_BLUR_PX if horizontal else 1
    size_y = 1 if horizontal else WHIP_BLUR_PX
    return [f"avgblur=sizeX={size_x}:sizeY={size_y}:enable='{window}'"]


def still_filters(
    shot: Shot,
    canvas: Canvas,
    supersample: int,
    total_frames: int,
    hold_frames: int,
    whip_in: Transition | None,
    whip_out: Transition | None,
) -> list[str]:
    conform_w, conform_h = conform_size(canvas, shot.motion)
    crop_w, crop_h = motion.crop_size(canvas, supersample)
    scale_w, scale_h = motion.scale_exprs(
        shot.motion, canvas, supersample, total_frames, hold_frames
    )
    crop_x, crop_y = motion.crop_exprs(
        shot.motion, canvas, supersample, total_frames, hold_frames
    )

    # No `fps` filter here: render_shot sets -framerate on the input, so the
    # still already arrives at canvas.fps. An `fps` filter placed AFTER the
    # n-based scale/crop would rewrite frame numbering underneath them and the
    # move would silently never complete.
    filters = [
        f"scale={conform_w}:{conform_h}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={conform_w}:{conform_h}",
        f"scale=w='{scale_w}':h='{scale_h}':eval=frame:flags=lanczos",
        f"crop=w={crop_w}:h={crop_h}:x='{crop_x}':y='{crop_y}'",
        _colour_scale(canvas),
        # Immediately after the tagged conversion, so nothing downstream can
        # leave the frame in RGB and trigger a default BT.601 conversion later.
        f"format={INTERMEDIATE_PIX_FMT}",
    ]
    filters.extend(_whip_stack(whip_in, whip_out, total_frames, canvas))
    filters.append("setsar=1")
    return filters


def clip_filters(
    shot: Shot, canvas: Canvas, whip_in: Transition | None, whip_out: Transition | None
) -> list[str]:
    # `fps` must precede the whip, whose enable window counts frames.
    filters = [
        f"trim=start={shot.source_in}:end={shot.source_out}",
        "setpts=PTS-STARTPTS",
        f"scale={canvas.width}:{canvas.height}"
        ":force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={canvas.width}:{canvas.height}",
        f"fps={canvas.fps}",
        _colour_scale(canvas),
        f"format={INTERMEDIATE_PIX_FMT}",
    ]
    total_frames = round((shot.source_out - shot.source_in) * canvas.fps)
    filters.extend(_whip_stack(whip_in, whip_out, total_frames, canvas))
    filters.append("setsar=1")
    return filters


def _whip_stack(
    whip_in: Transition | None,
    whip_out: Transition | None,
    total_frames: int,
    canvas: Canvas,
) -> list[str]:
    stack: list[str] = []
    if whip_in and whip_in.kind == "whip":
        stack.extend(
            whip_filters(whip_in.direction, whip_in.frames, total_frames, True, canvas)
        )
    if whip_out and whip_out.kind == "whip":
        stack.extend(
            whip_filters(whip_out.direction, whip_out.frames, total_frames, False, canvas)
        )
    return stack


def shot_cache_key(
    shot: Shot,
    next_transition: Transition | None,
    source_digest: str,
    ffmpeg_build: str,
    supersample: int,
    mode: str,
) -> str:
    return payload_digest(
        shot.model_dump(by_alias=True),
        next_transition.model_dump() if next_transition else None,
        source_digest,
        ffmpeg_build,
        supersample,
        mode,
    )


def render_shot(
    spec: RenderSpec,
    ws: Workspace,
    index: int,
    shot: Shot,
    next_transition: Transition | None,
    supersample: int,
    mode: str,
    manifest: Manifest,
    log_path: Path,
    is_placeholder: bool,
) -> Path:
    canvas = spec.canvas
    bounds = shot_frame_bounds(spec)[index - 1]
    total_frames = bounds[1] - bounds[0]
    hold_frames = round(shot.motion.hold_s * canvas.fps)

    if is_placeholder:
        source = ws.work_dir / "placeholders" / f"{shot.id}.png"
        render_placeholder(f"{shot.id} - {shot.source} MISSING", canvas, source)
    else:
        source = ws.asset(shot.source)

    target = ws.shot_clip(index, shot.id, shot.beat)
    key = f"shots/{index:03d}"
    digest = shot_cache_key(
        shot, next_transition, file_digest(source), ffmpeg.ffmpeg_version(),
        supersample, mode,
    )
    if manifest.is_fresh(key, digest, target):
        return target

    whip_in = shot.transition_in if shot.transition_in.kind == "whip" else None
    whip_out = (
        next_transition
        if next_transition and next_transition.kind == "whip"
        else None
    )

    if shot.kind == "still" or is_placeholder:
        filters = still_filters(
            shot, canvas, supersample, total_frames, hold_frames, whip_in, whip_out
        )
        # -framerate is mandatory: -loop 1 otherwise defaults the input to
        # 25fps, so the n-based motion expressions (built against total_frames
        # at canvas.fps) would only ever reach ~83% of the move before -t cut
        # the input. Nothing downstream would catch it.
        inputs = [
            "-loop", "1", "-framerate", str(canvas.fps),
            "-t", f"{total_frames / canvas.fps:.6f}", "-i", str(source),
        ]
    else:
        filters = clip_filters(shot, canvas, whip_in, whip_out)
        inputs = ["-i", str(source)]

    crf = INTERMEDIATE_CRF_DRAFT if mode == "draft" else INTERMEDIATE_CRF_FINAL
    preset = INTERMEDIATE_PRESET_DRAFT if mode == "draft" else INTERMEDIATE_PRESET_FINAL

    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run(
        [
            "ffmpeg", "-hide_banner", "-y", *inputs,
            "-vf", ",".join(filters),
            "-frames:v", str(total_frames),
            "-fps_mode", "cfr", "-r", str(canvas.fps),
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", INTERMEDIATE_PIX_FMT,
            "-x264-params", _X264_PARAMS_BT709,
            "-an", str(target),
        ],
        log_path,
    )
    manifest.set(key, digest)
    return target


def render_all(
    spec: RenderSpec,
    ws: Workspace,
    mode: str,
    manifest: Manifest,
    log_path: Path,
    missing_visual: list[str],
) -> list[Path]:
    supersample = SUPERSAMPLE_DRAFT if mode == "draft" else SUPERSAMPLE_FINAL
    clips: list[Path] = []
    for index, shot in enumerate(spec.shots, start=1):
        successor = spec.shots[index].transition_in if index < len(spec.shots) else None
        clips.append(
            render_shot(
                spec, ws, index, shot, successor, supersample, mode, manifest,
                log_path, shot.source in missing_visual,
            )
        )
    manifest.save()
    return clips
