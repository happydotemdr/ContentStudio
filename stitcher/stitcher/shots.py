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

# Clones the last frame indefinitely so `-frames:v total_frames` always has a
# frame to take. See clip_filters' docstring for the measurement that made
# this necessary and for why the pad is unbounded.
CLIP_PAD = "tpad=stop=-1:stop_mode=clone"

INTERMEDIATE_PIX_FMT = "yuv444p"
INTERMEDIATE_CRF_FINAL = 12
INTERMEDIATE_CRF_DRAFT = 28
INTERMEDIATE_PRESET_FINAL = "veryfast"
INTERMEDIATE_PRESET_DRAFT = "ultrafast"

# Tags the frame's colour metadata (primaries/transfer/matrix) before encode.
#
# Superseded a first attempt that used `-x264-params colorprim=:transfer=:
# colormatrix=` as an encode-time flag instead of this filter. That attempt
# was verified against the h264 `trace_headers` bitstream filter, which
# showed the SPS VUI correctly carrying colour_primaries=1/transfer_
# characteristics=1/matrix_coefficients=1 -- but `ffprobe -show_streams` on
# the very same file reported color_primaries=unknown and color_transfer=
# unknown (only color_space landed). That is decisive: ffprobe is what this
# project's own QA gates on (design spec line 503; Task 13's colour_tagging
# check and Task 15's e2e assertion both read ffmpeg.probe(), built on
# ffprobe), so a tag only visible via a manual bitstream decode does not
# satisfy the spec's own observable, and stage A's clips would fail the QA
# gate for a defect this task's own report had wrongly marked closed.
#
# `setparams` fixes this at the frame-metadata level instead of the encoder
# level: verified with `ffprobe -show_streams` on the resulting file --
# color_space=bt709, color_primaries=bt709, color_transfer=bt709 all land,
# and independently reconfirmed with trace_headers that the encoded SPS still
# carries the correct VUI values. `-x264-params` is no longer used at all:
# once setparams tags the frame before libx264 sees it, the encoder's own
# automatic VUI generation (already responsible for out_range=tv on
# _colour_scale landing correctly, see below) picks up colorspace, primaries
# and transfer the same way -- there is nothing left for an encoder-side flag
# to add, and dropping it also removes the `range=tv` parse error a prior
# version of this constant carried (`-x264-params` rejects "range=tv" on this
# libx264 core; `setparams` has no such key at all, so the question does not
# arise here -- range remains solely the scale filter's `out_range=tv`).
_SETPARAMS_BT709 = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"


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
        # Stamps colour_primaries/color_trc/colorspace onto the frame itself
        # so they survive into both the encoded bitstream and ffprobe's
        # container-level report (see _SETPARAMS_BT709's docstring above).
        _SETPARAMS_BT709,
    ]
    filters.extend(_whip_stack(whip_in, whip_out, total_frames, canvas))
    filters.append("setsar=1")
    return filters


def clip_filters(
    shot: Shot,
    canvas: Canvas,
    total_frames: int,
    whip_in: Transition | None,
    whip_out: Transition | None,
) -> list[str]:
    """Trim a clip's source window and conform it to exactly total_frames.

    `total_frames` is the shot's own timeline slot (shot_frame_bounds), not
    the source window re-measured: those are equal by validation (spec.py
    requires source_out - source_in == out - in exactly), and the slot is the
    one that stage D's concat timeline, the overlay `enable=` expressions and
    the audio `adelay`s are all authored against.

    CLIP_PAD is why they stay equal in the output. `trim=start=X` snaps to the
    SOURCE's frame grid, so a source_in that does not land on a source frame
    boundary yields a span shorter than requested -- and `-frames:v` cannot
    invent the missing frame, so ffmpeg writes fewer and exits 0. Reproduced
    against the installed 9.0 binary on a 25fps source, requesting 45 frames
    at 30fps:

        source_in=0.0   source_out=1.5    -> 45 frames
        source_in=0.5   source_out=2.0    -> 44 frames   <-- one short
        source_in=0.04  source_out=1.54   -> 45 frames

    Every subsequent shot then starts one frame early against authored
    overlay/caption/audio times, and the drift accumulates until
    timeline_integrity's slack fires -- below which it ships misaligned.

    Padding was chosen over frame-aligning the trim window at preflight. The
    alignment route would have to reject a spec whose source_in is off the
    source's own frame grid, which is a property of the asset the author
    generally does not know (and cannot express for a variable-frame-rate
    source at all); the worst case here is instead one cloned tail frame,
    which is what the concat timeline needs anyway. The pad is INFINITE and
    bounded by `-frames:v total_frames` rather than being sized to a computed
    shortfall: an exact frame count is the guarantee this fix exists to make,
    and computing the shortfall would mean re-deriving the source's own frame
    grid -- the very thing that is unreliable here. Verified on the same
    binary that all three cases above then emit exactly 45 frames and that
    the command still terminates.
    """
    # `fps` must precede the pad and the whip, both of which count frames at
    # canvas.fps; the pad must precede the whip so the whip's tail window
    # (gte(n, total_frames - frames)) gates against the final, exact length.
    filters = [
        f"trim=start={shot.source_in}:end={shot.source_out}",
        "setpts=PTS-STARTPTS",
        f"scale={canvas.width}:{canvas.height}"
        ":force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={canvas.width}:{canvas.height}",
        f"fps={canvas.fps}",
        CLIP_PAD,
        _colour_scale(canvas),
        f"format={INTERMEDIATE_PIX_FMT}",
        _SETPARAMS_BT709,
    ]
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
    fps: int,
) -> str:
    # v1's canvas width/height cannot vary (ruling: only 1080x1920 is
    # implemented), so fps is the one live piece of `Canvas` that changes the
    # render without changing anything else already in this key: editing
    # spec.canvas.fps changes total_frames/hold_frames/the whip windows and
    # every n-based motion expression, but none of shot/next_transition/
    # source_digest/ffmpeg_build/supersample/mode would differ. Without fps
    # here, re-rendering after an fps edit would report a false cache hit and
    # silently keep serving a clip rendered at the old frame rate.
    return payload_digest(
        shot.model_dump(by_alias=True),
        next_transition.model_dump() if next_transition else None,
        source_digest,
        ffmpeg_build,
        supersample,
        mode,
        fps,
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
        supersample, mode, canvas.fps,
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
        filters = clip_filters(shot, canvas, total_frames, whip_in, whip_out)
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
