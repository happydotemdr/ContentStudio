"""Everything that must be true before a single frame renders.

Runs to completion and reports every problem at once rather than the first
(spec §6). In final mode any failure aborts; in draft mode a missing visual
asset becomes a placeholder, and a missing stem is tolerated only when it
declares duration_s.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFont

from . import ffmpeg, overlays
from .naming import MAX_PATH_LEN, Workspace
from .spec import RenderSpec, runtime_seconds, validate_spec

_VERSION_RE = re.compile(r"ffmpeg version (\d+)")


@dataclass
class PreflightReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_visual: list[str] = field(default_factory=list)
    missing_audio: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _check_tools(report: PreflightReport) -> None:
    try:
        version = ffmpeg.ffmpeg_version()
    except ffmpeg.FFmpegError as exc:
        report.errors.append(str(exc))
        return

    match = _VERSION_RE.search(version)
    if not match or int(match.group(1)) < 8:
        report.errors.append(
            f"ffmpeg 8.x or newer is required (-fps_mode replaced -vsync); found: {version}"
        )

    # libass is deliberately NOT checked: ASS burn-in was rejected in favour of
    # Pillow compositing, and the .ass sidecar is text written by Python. This
    # build has libass compiled in, but its presence must never be relied on
    # (ruling R1) -- checking for it here would pass on this machine and fail
    # silently elsewhere.
    if not ffmpeg.has_encoder("libx264"):
        report.errors.append("ffmpeg has no libx264 encoder; it is required for all encodes")


def _check_slug(spec: RenderSpec, ws: Workspace, report: PreflightReport) -> None:
    """Design spec §3/§6: the spec's slug must match the containing directory name.

    validate_spec(spec) (Task 2) is pure and has no directory to compare against,
    so this check lives here where both spec.slug and the workspace's directory
    name are available. ws.base is root/ws.slug, so ws.base.name is exactly the
    directory the spec file lives in.
    """
    directory_name = ws.base.name
    if spec.slug != directory_name:
        report.errors.append(
            f"spec slug {spec.slug!r} does not match the containing directory "
            f"{directory_name!r}"
        )


def _check_paths(spec: RenderSpec, ws: Workspace, report: PreflightReport) -> None:
    candidates = [ws.manifest_path, ws.graph_path, ws.master_path]
    for index, shot in enumerate(spec.shots, start=1):
        candidates.append(ws.shot_clip(index, shot.id, shot.beat))
    for index, overlay in enumerate(spec.overlays, start=1):
        candidates.append(ws.overlay_png(index, overlay.id, overlay.text))
    # The LONGEST deliverable, not just any deliverable: out_contact_sheet's
    # suffix is 10 characters longer than out_qa_json's, so sampling the
    # latter let a workspace pass this gate and then fail while writing the
    # contact sheet -- which happens after promotion. Version 99 stands in for
    # the widest version number the naming scheme formats.
    candidates.append(ws.out_contact_sheet(99))

    longest = max(candidates, key=lambda p: len(str(p)))
    if len(str(longest)) > MAX_PATH_LEN:
        report.errors.append(
            f"path exceeds {MAX_PATH_LEN} characters ({len(str(longest))}): {longest}. "
            "Use a shorter slug or move the workspace closer to the drive root."
        )


def _check_fonts(spec: RenderSpec, report: PreflightReport) -> dict[str, ImageFont.FreeTypeFont]:
    """Design spec line 571: "Every referenced font file loads." Existence is
    not loading -- a truncated or corrupt font must be caught here, not during
    glyph rendering. PIL.ImageFont.truetype is the same call Task 7's renderer
    uses, so preflight and the renderer agree on what "loadable" means.

    Returns the loaded fonts by style name so _check_text_fit can wrap against
    the real metrics without loading each file a second time.
    """
    loaded: dict[str, ImageFont.FreeTypeFont] = {}
    for name, style in spec.styles.items():
        path = Path(style.font_file)
        if not path.is_file():
            report.errors.append(
                f"style {name!r} references a font file that does not exist: {style.font_file}"
            )
            continue
        try:
            loaded[name] = ImageFont.truetype(str(path), style.size_px)
        except Exception as exc:
            report.errors.append(
                f"style {name!r} references a font file that failed to load: "
                f"{style.font_file} ({exc})"
            )
    return loaded


def _check_text_fit(
    spec: RenderSpec,
    fonts: dict[str, ImageFont.FreeTypeFont],
    report: PreflightReport,
) -> None:
    """Design spec line 227: "exceeding `max_lines` after wrapping is a
    preflight failure, not a silent overflow" -- and line 369 lists it among
    the things rejected before any asset is touched.

    This cannot live in validate_spec: wrapping needs the real font metrics,
    and validate_spec is pure and probes nothing (spec §3). Preflight is the
    first point where both the text and the loaded font exist, which is the
    same reason §3 defers `source_in`/`source_out` bounds here. Left where it
    was -- inside stage B's renderer -- `render` only discovered it after
    stage A had already burned an encode per shot, and reported it as a render
    failure (exit 2) rather than a spec failure.
    """
    for overlay in spec.overlays:
        font = fonts.get(overlay.style)
        if font is None:
            # Unknown style (validate_spec) or unloadable font (_check_fonts);
            # both are already errors and neither can be wrapped against.
            continue
        problem = overlays.fit_error(overlay.text, spec.styles[overlay.style], font)
        if problem is not None:
            report.errors.append(
                f"overlay {overlay.id!r} does not fit style {overlay.style!r}: "
                f"{problem}: {overlay.text!r}"
            )


def _check_cover(spec: RenderSpec, ws: Workspace, mode: str, report: PreflightReport) -> None:
    """Stage E opens the cover with Pillow, so preflight must too.

    _check_visual_assets already probes it with ffprobe, but ffprobe and
    Pillow do not accept the same set of files. A cover that ffprobe reads and
    Pillow does not used to surface as an uncaught traceback in stage E --
    after the master had already been promoted into out/ with a version
    number. Validated here the way _check_fonts validates fonts: by performing
    the load the later stage will perform.
    """
    if not spec.cover:
        return
    path = ws.asset(spec.cover.source)
    if not path.is_file():
        # Absence is _check_visual_assets' report to make (and is tolerated in
        # draft mode, where the cover is skipped).
        return
    try:
        with Image.open(path) as image:
            image.load()
    except Exception as exc:
        report.errors.append(
            f"cover source {spec.cover.source} could not be opened as an image: {exc}"
        )


def _check_draft_profile(spec: RenderSpec, mode: str, report: PreflightReport) -> None:
    """An accepted limitation, surfaced before it costs a full render.

    Draft mode encodes with `-preset ultrafast`, which sets
    cabac=0/8x8dct=0/bframes=0 -- already Baseline-conforming, and x264
    signals the profile the encode actually needs rather than the one
    requested. Stage D restores High by forcing cabac/8x8dct back on, but
    `8x8dct` is itself High-only, so that override cannot generalize to
    "main" or "baseline" (see assemble.py). The combination therefore renders
    fully and then fails verify's container check with a message that points
    at the encoder rather than at the mode. It is knowable before a frame
    renders, so say so here -- as a WARNING, because the render is otherwise
    correct and the behaviour is deliberate.
    """
    if mode == "draft" and spec.delivery.profile.lower() != "high":
        report.warnings.append(
            f"draft mode cannot honour delivery.profile {spec.delivery.profile!r}: "
            "-preset ultrafast emits Constrained Baseline and the High-only 8x8dct "
            "override does not generalize, so the container check will fail. Use "
            "--mode final to verify the profile."
        )


def _check_visual_assets(
    spec: RenderSpec, ws: Workspace, mode: str, report: PreflightReport
) -> None:
    sources = {shot.source for shot in spec.shots}
    if spec.cover:
        sources.add(spec.cover.source)

    # Each present source is probed at most once. The clip-specific checks
    # below reuse this ProbeResult instead of probing the same file again --
    # a second, unguarded probe() call would let FFmpegError propagate out of
    # run_preflight for a present-but-corrupt clip, defeating the "report
    # every problem, never crash" contract this module exists for.
    probed: dict[str, ffmpeg.ProbeResult] = {}

    for source in sorted(sources):
        path = ws.asset(source)
        if not path.is_file():
            if mode == "draft":
                report.missing_visual.append(source)
            else:
                report.errors.append(f"asset not found: {path}")
            continue
        try:
            probed[source] = ffmpeg.probe(path)
        except ffmpeg.FFmpegError as exc:
            report.errors.append(f"asset {source} could not be probed: {exc}")

    for shot in spec.shots:
        if shot.kind != "clip" or shot.source in report.missing_visual:
            continue
        result = probed.get(shot.source)
        if result is None:
            # Either missing (handled above) or failed to probe (error
            # already recorded above); nothing further to check here.
            continue
        if shot.source_out is not None and shot.source_out > result.duration + 1e-6:
            report.errors.append(
                f"shot {shot.id}: source_out {shot.source_out}s exceeds the real duration "
                f"of {shot.source} ({result.duration}s)"
            )
        if shot.source_in is not None and shot.source_in < 0:
            report.errors.append(f"shot {shot.id}: source_in must not be negative")


def _check_audio_assets(
    spec: RenderSpec, ws: Workspace, mode: str, report: PreflightReport
) -> None:
    for stem in spec.audio.stems:
        path = ws.asset(stem.file)
        if path.is_file():
            continue
        if mode == "draft" and stem.duration_s is not None:
            report.missing_audio.append(stem.file)
        elif mode == "draft":
            report.errors.append(
                f"stem {stem.id!r} file {stem.file} is missing and declares no duration_s; "
                "draft mode can only synthesize silence for a stem of known length"
            )
        else:
            report.errors.append(f"stem file not found: {path}")

    optional = [spec.audio.bed.file] if spec.audio.bed else []
    optional += [item.file for item in spec.audio.sfx]
    for name in optional:
        path = ws.asset(name)
        if path.is_file():
            continue
        if mode == "draft":
            report.missing_audio.append(name)
            report.warnings.append(f"{name} is missing; it will be omitted from the draft mix")
        else:
            report.errors.append(f"audio file not found: {path}")


def run_preflight(spec: RenderSpec, ws: Workspace, mode: str) -> PreflightReport:
    report = PreflightReport()
    report.errors.extend(validate_spec(spec))

    if runtime_seconds(spec) <= 0:
        report.errors.append("spec has zero runtime")

    _check_slug(spec, ws, report)
    _check_tools(report)
    _check_paths(spec, ws, report)
    fonts = _check_fonts(spec, report)
    _check_text_fit(spec, fonts, report)
    _check_visual_assets(spec, ws, mode, report)
    _check_cover(spec, ws, mode, report)
    _check_audio_assets(spec, ws, mode, report)
    _check_draft_profile(spec, mode, report)
    return report
