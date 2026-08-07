"""Render spec models, frame quantization, and validation.

JSON uses `in`/`out`; Python exposes `start`/`end` because `in` is a keyword.
Quantization applies to absolute boundaries only — durations are derived by
differencing, so rounding error cannot accumulate across shots (spec §3).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SUPPORTED_SPEC_VERSIONS = {"1.0"}
V1_TRANSITIONS = {"cut", "whip"}
V1_CANVAS = (1080, 1920)


class _Base(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class Canvas(_Base):
    width: int
    height: int
    fps: int


class SafeZone(_Base):
    x: int
    y: int
    width: int
    height: int


class Style(_Base):
    font_file: str
    size_px: int
    body: str
    accent: str
    ground: str | None = None
    ground_opacity: float = 1.0
    padding_px: tuple[int, int] = (0, 0)
    line_spacing: float = 1.0
    align: Literal["left", "center", "right"] = "center"
    max_width_px: int
    max_lines: int
    stroke_px: int = 0
    stroke_color: str = "#000000"


class Motion(_Base):
    kind: Literal["push_in", "pull_out", "scale_up", "none"] = "none"
    # A negative zoom amount makes the animated `scale` shrink BELOW the fixed
    # `crop` that follows it, so the crop reads outside its input. Probed
    # against the installed 9.0 binary with stage A's real filter chain
    # (amount_pct=-20, supersample 4, a moving anchor): ffmpeg segfaults, exit
    # 139. There is no meaningful negative zoom to express -- pull_out is how
    # a shrink is authored -- so the floor is zero.
    amount_pct: float = Field(0.0, ge=0)
    anchor_start: tuple[float, float] = (0.5, 0.5)
    anchor_end: tuple[float, float] = (0.5, 0.5)
    hold_s: float = 0.0
    ease: Literal["linear", "ease_in", "ease_out", "ease_in_out"] = "linear"


class Transition(_Base):
    kind: str = "cut"
    direction: Literal["left", "right", "up", "down"] | None = None
    frames: int = 4


class Shot(_Base):
    n: int
    id: str
    beat: str
    start: float = Field(alias="in")
    end: float = Field(alias="out")
    source: str
    kind: Literal["still", "clip"]
    source_in: float | None = None
    source_out: float | None = None
    motion: Motion = Motion()
    transition_in: Transition = Transition()


class Overlay(_Base):
    id: str
    style: str
    start: float = Field(alias="in")
    end: float = Field(alias="out")
    anchor: Literal["center", "upper_third", "lower_third"] = "center"
    offset_px: tuple[int, int] = (0, 0)
    text: str


class Caption(_Base):
    start: float = Field(alias="in")
    end: float = Field(alias="out")
    text: str


class Stem(_Base):
    id: str
    file: str
    at: float
    gain_db: float = 0.0
    duration_s: float | None = None


class BedWindow(_Base):
    start: float = Field(alias="in")
    end: float = Field(alias="out")
    mode: Literal["out", "ducked", "full"]
    level_db: float | None = None


class Fade(_Base):
    at: float
    kind: Literal["in", "out"]
    ms: int


class Bed(_Base):
    file: str
    gain_db: float
    duck_db: float
    duck_attack_ms: int = 120
    duck_release_ms: int = 400
    windows: list[BedWindow] = []
    fades: list[Fade] = []


class Sfx(_Base):
    file: str
    at: float
    gain_db: float = 0.0


class Loudness(_Base):
    integrated_lufs: float
    true_peak_dbtp: float


class Audio(_Base):
    stems: list[Stem]
    bed: Bed | None = None
    sfx: list[Sfx] = []
    loudness: Loudness


class Cover(_Base):
    source: str
    overlays: list[str] = []


class Delivery(_Base):
    codec: str = "libx264"
    crf: int = 18
    preset: str = "slow"
    profile: str = "high"
    pix_fmt: str = "yuv420p"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_rate: int = 48000


class RenderSpec(_Base):
    spec_version: str
    slug: str
    canvas: Canvas
    safe_zone: SafeZone
    styles: dict[str, Style]
    shots: list[Shot]
    overlays: list[Overlay] = []
    captions: list[Caption] = []
    captions_style: str
    audio: Audio
    cover: Cover | None = None
    delivery: Delivery = Delivery()


# --- frame maths ---------------------------------------------------------


def quantize(seconds: float, fps: int) -> int:
    """Absolute time in seconds -> frame index, rounded to nearest."""
    return int(round(seconds * fps))


def frame_residual(seconds: float, fps: int) -> float:
    """How far this time sits from a frame boundary, in frames."""
    exact = seconds * fps
    return abs(exact - round(exact))


def runtime_seconds(spec: RenderSpec) -> float:
    return spec.shots[-1].end if spec.shots else 0.0


def shot_frame_bounds(spec: RenderSpec) -> list[tuple[int, int]]:
    """Quantize each boundary once; derive durations by differencing."""
    fps = spec.canvas.fps
    boundaries = [quantize(spec.shots[0].start, fps)] if spec.shots else []
    for shot in spec.shots:
        boundaries.append(quantize(shot.end, fps))
    return [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]


# --- loading -------------------------------------------------------------


def _collect_times(payload: dict) -> list[tuple[str, float]]:
    times: list[tuple[str, float]] = []
    for shot in payload.get("shots", []):
        times.append((f"shots[{shot.get('n')}].in", shot["in"]))
        times.append((f"shots[{shot.get('n')}].out", shot["out"]))
    for overlay in payload.get("overlays", []):
        times.append((f"overlays[{overlay.get('id')}].in", overlay["in"]))
        times.append((f"overlays[{overlay.get('id')}].out", overlay["out"]))
    for stem in payload.get("audio", {}).get("stems", []):
        times.append((f"audio.stems[{stem.get('id')}].at", stem["at"]))
    return times


def load_spec(path: Path) -> tuple[RenderSpec, list[str]]:
    """Parse and frame-check a spec. Raises ValueError on unusable input."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))

    version = payload.get("spec_version")
    if version not in SUPPORTED_SPEC_VERSIONS:
        raise ValueError(f"unsupported spec_version {version!r}")

    for shot in payload.get("shots", []):
        kind = shot.get("transition_in", {}).get("kind", "cut")
        if kind not in V1_TRANSITIONS:
            raise ValueError(
                f"transition_in.kind {kind!r} is not implemented in v1 "
                f"(shot {shot.get('id')}); only {sorted(V1_TRANSITIONS)} are supported"
            )

    try:
        spec = RenderSpec.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"spec failed schema validation:\n{exc}") from exc

    fps = spec.canvas.fps
    warnings = [
        f"{label} = {value}s is not frame-aligned at {fps}fps "
        f"({value * fps:.2f} frames); it will render at frame {quantize(value, fps)}"
        for label, value in _collect_times(payload)
        if frame_residual(value, fps) > 1e-9
    ]
    return spec, warnings


# --- validation ----------------------------------------------------------


def validate_spec(spec: RenderSpec) -> list[str]:
    """Internal-consistency errors. Never touches assets (spec §3)."""
    errors: list[str] = []

    if (spec.canvas.width, spec.canvas.height) != V1_CANVAS:
        errors.append(
            f"canvas {spec.canvas.width}x{spec.canvas.height} is not supported in v1; "
            "only 1080x1920 is implemented"
        )

    if not spec.shots:
        errors.append("shots must not be empty")
        return errors

    # Every downstream stage assumes the rendered timeline starts at 0: stage
    # D concatenates the shot clips head to tail (so the first frame of the
    # first shot IS t=0), while every overlay `enable=` expression and every
    # `adelay` is authored in ABSOLUTE spec seconds against that concat. A
    # spec whose first shot starts at 2.0 renders 60 fewer frames than
    # runtime_seconds implies and puts every overlay and stem 2 seconds late,
    # with nothing but timeline_integrity to notice afterwards -- and only
    # after a full render.
    if spec.shots[0].start != 0:
        errors.append(
            f"the timeline must start at 0s; shot {spec.shots[0].id} starts at "
            f"{spec.shots[0].start}s. Overlay, caption and audio times are absolute "
            "spec seconds against a concat timeline that begins at the first shot, "
            "so a non-zero start silently offsets all of them"
        )

    for previous, shot in zip(spec.shots, spec.shots[1:]):
        if shot.start != previous.end:
            errors.append(
                f"shots are not contiguous: shot {previous.id} ends at {previous.end}s "
                f"but shot {shot.id} starts at {shot.start}s"
            )

    for shot in spec.shots:
        if shot.end <= shot.start:
            errors.append(f"shot {shot.id} has non-positive duration")
        if shot.kind == "clip" and (shot.source_in is None or shot.source_out is None):
            errors.append(
                f"shot {shot.id} is kind 'clip' and must declare source_in and source_out"
            )
        elif shot.kind == "clip":
            # Stage A trims a clip's source window but never re-times it (spec
            # line 405; "no re-timing" is an explicit non-goal), so the source
            # window duration must equal the shot's timeline slot duration
            # exactly. If it doesn't, ffmpeg emits fewer/more frames than the
            # timeline slot requests with no error, silently truncating the
            # clip and misaligning the tail whip's frame-count gate and stage
            # D's concat timing.
            source_duration = shot.source_out - shot.source_in
            slot_duration = shot.end - shot.start
            if abs(source_duration - slot_duration) > 1e-6:
                errors.append(
                    f"shot {shot.id}: source window is {source_duration}s "
                    f"(source_in={shot.source_in}, source_out={shot.source_out}) but "
                    f"its timeline slot is {slot_duration}s ({shot.start}-{shot.end}s); "
                    "stage A trims without re-timing, so these must match exactly"
                )
        if shot.kind == "clip" and shot.motion.kind != "none":
            # shots.clip_filters never reads shot.motion at all -- the Ken
            # Burns scale/crop pair is built only by still_filters -- so a
            # clip authoring push_in rendered motionless with no error, no
            # warning and no QA signal. That is precisely the "subtly wrong
            # video" goal 5 exists to prevent, and §3 already rejects
            # unimplemented values ("not implemented in v1") rather than
            # dropping them, so this is rejected the same way.
            errors.append(
                f"shot {shot.id}: motion.kind {shot.motion.kind!r} on a kind 'clip' "
                "shot is not implemented in v1; stage A's clip path applies no "
                "motion, so it would render motionless. Set motion.kind to 'none', "
                "or use kind 'still'"
            )
        if shot.motion.amount_pct < 0:
            # Unreachable through load_spec, which rejects it at the field
            # (Motion.amount_pct has ge=0). Kept as a second gate for any spec
            # built by a path that skips field validation, because what it
            # prevents is an ffmpeg SEGFAULT rather than a bad-looking render.
            errors.append(
                f"shot {shot.id}: motion.amount_pct is {shot.motion.amount_pct} and must "
                "not be negative; a negative zoom shrinks the animated scale below the "
                "fixed crop and ffmpeg segfaults. Use motion.kind 'pull_out' to shrink"
            )
        if shot.transition_in.kind == "whip" and shot.transition_in.direction is None:
            errors.append(
                f"shot {shot.id} has a whip transition without a direction; "
                "direction is required and has no default"
            )

    runtime = runtime_seconds(spec)

    for overlay in spec.overlays:
        if overlay.style not in spec.styles:
            errors.append(f"overlay {overlay.id} references unknown style {overlay.style!r}")
        if overlay.end > runtime or overlay.start < 0:
            errors.append(
                f"overlay {overlay.id} spans {overlay.start}-{overlay.end}s, "
                f"outside the runtime 0-{runtime}s"
            )

    if spec.captions_style not in spec.styles:
        errors.append(f"captions_style {spec.captions_style!r} is not defined in styles")

    for previous, caption in zip(spec.captions, spec.captions[1:]):
        if caption.start < previous.end:
            errors.append(
                f"captions overlap: one ends at {previous.end}s, the next starts at {caption.start}s"
            )
    for caption in spec.captions:
        if caption.end > runtime or caption.start < 0:
            errors.append(f"caption at {caption.start}s falls outside the runtime 0-{runtime}s")

    if not spec.audio.stems:
        errors.append(
            "the spec declares no audio stems; at least one voice stem is "
            "required -- stage C's entire dB model (bed gain_db/duck_db) is "
            "relative to the measured voice track, so there is no reference "
            "level to be relative to without one"
        )

    if spec.audio.bed:
        windows = sorted(spec.audio.bed.windows, key=lambda w: w.start)
        for previous, window in zip(windows, windows[1:]):
            if window.start < previous.end:
                errors.append(
                    f"bed windows overlap at {window.start}s; overlapping windows are rejected "
                    "so precedence among them never arises"
                )

    if spec.cover and spec.cover.overlays:
        known = {overlay.id for overlay in spec.overlays}
        for name in spec.cover.overlays:
            if name not in known:
                errors.append(f"cover references unknown overlay id {name!r}")

    return errors
