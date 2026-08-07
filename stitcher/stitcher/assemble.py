# stitcher/stitcher/assemble.py
"""Stage D: concat the shot clips, composite the overlays, encode the master.

The result stays in work/ until stage F passes it; only then is it promoted
into out/ with a version number (spec §2 rule 5).
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg
from .naming import Workspace
from .spec import RenderSpec

DRAFT_CRF = 30
DRAFT_PRESET = "ultrafast"

# The filtergraph is written to work/<mode>/graph_assemble.txt and read from
# there rather than embedded inline, per spec §4 stage D.
#
# The plan called this "-filter_complex_script <file>". That flag does not
# exist on the installed ffmpeg 9.0 binary (gyan.dev full_build):
# `ffmpeg -filter_complex_script anything` fails with "Unrecognized option
# 'filter_complex_script'" (exit 8), and the string `filter_complex_script`
# is entirely absent from the binary -- confirmed both by running the flag
# directly and by grepping the compiled executable. This is not a fluke of
# this build: upstream ffmpeg deprecated `-filter_complex_script` in favour
# of `-/filter_complex <file>` in January 2024
# (fftools/ffmpeg: deprecate -filter_complex_script,
# https://patchwork.ffmpeg.org/project/ffmpeg/patch/20240117092233.8503-5-anton@khirnov.net/,
# commit message: "It is equivalent to -/filter_complex."), gated behind
# `#if FFMPEG_OPT_FILTER_SCRIPT` -- this 9.0 build was compiled with that
# compatibility shim off, so only the replacement spelling is available.
#
# `-/filter_complex <file>` is ffmpeg's generic "read this option's value
# from a file" convention (the leading `/` attaches to the option name, not
# the value) -- NOT the `@file` convention, which does not apply to
# -filter_complex on this binary (verified: `-filter_complex "@file.txt"`
# fails with "No such filter: ''", i.e. no indirection happens at all).
#
# Verified end-to-end against the real 9.0 binary with synthetic bt709-tagged
# clips, a single-frame RGBA overlay PNG, and a 48kHz wav mix: `-/filter_complex
# graph_assemble.txt` parses a written multi-line graph file -- including the
# `enable='gte(t,IN)*lt(t,OUT)'` expressions' internal commas and a two-overlay
# chain through an intermediate `[v0]` label -- exactly like the equivalent
# inline `-filter_complex "<same text>"` would.
_FILTER_COMPLEX_FROM_FILE = "-/filter_complex"


def write_concat(clips: list[Path], path: Path) -> Path:
    """Concat demuxer list. Forward slashes and quoting, read with -safe 0.

    Verified against the real binary: `Path.as_posix()`'s forward-slash form
    of a Windows path (e.g. `C:/Users/.../001_clip.mkv`, drive letter and
    colon intact) is read correctly by `-f concat -safe 0`. The MSYS-style
    `/c/Users/...` form a bash shell would produce is a different, unrelated
    thing and does NOT work here -- ffmpeg.exe is a native Windows binary and
    has no notion of that mount-point syntax. Nothing in this codebase
    produces that form; `pathlib.Path.as_posix()` on a `WindowsPath` never
    does either.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"file '{clip.as_posix()}'" for clip in clips]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def overlay_enable(start: float, end: float) -> str:
    """Half-open gating.

    `between(t,a,b)` is inclusive at BOTH ends, so a card ending at 2.0 and the
    next starting at 2.0 would both render for one frame (spec §4 stage D).
    """
    return f"gte(t,{start})*lt(t,{end})"


def build_graph(overlay_count: int, enables: list[str]) -> str:
    """Chain one overlay filter per PNG input, ending at [vout].

    Every overlay PNG is a single-frame input. Verified against the real
    binary that ffmpeg's `overlay` filter default `eof_action=repeat` keeps a
    single-frame input available for the entire output timeline rather than
    vanishing after frame 1: sampled frames across a gated window (t=0.1,
    1.0, 1.95) all showed the overlay composited in, and frames just past its
    `out` boundary (t=2.05, 2.9) did not -- so the `enable=` expression alone
    is sufficient to control visibility, exactly as the brief assumed. No
    `loop`/`tpad` workaround is needed.
    """
    if overlay_count == 0:
        return "[0:v]null[vout]"

    steps = []
    current = "0:v"
    for index in range(overlay_count):
        label = "vout" if index == overlay_count - 1 else f"v{index}"
        steps.append(
            f"[{current}][{index + 1}:v]overlay=0:0:enable='{enables[index]}'[{label}]"
        )
        current = label
    return ";".join(steps)


def normalize_graph(graph: str, replacements: dict[str, str]) -> str:
    """Tokenize absolute paths so filtergraph goldens are machine-independent."""
    normalized = graph
    for literal, token in replacements.items():
        normalized = normalized.replace(literal, token)
    return normalized


def assemble(
    spec: RenderSpec,
    ws: Workspace,
    mode: str,
    clips: list[Path],
    overlay_pngs: dict[str, Path],
    mix: Path,
    log_path: Path,
) -> Path:
    """Concat -> overlay chain -> mux mix -> final encode, in one ffmpeg call.

    Verified against the real 9.0 binary (see module docstrings above for
    each piece): the concat demuxer accepts stage A's bt709-tagged, yuv444p
    intermediates; the graph-from-file mechanism parses correctly; and the
    explicit `-colorspace/-color_primaries/-color_trc bt709` output flags
    below are, on their own, sufficient to make `ffprobe -show_streams`
    report `color_space=color_primaries=color_transfer=bt709` on the *final*
    encode -- confirmed on a real concat+overlay+encode run, with no
    `setparams` re-stamp filter needed in this graph. That differs from stage
    A's finding (`-x264-params` did not reach ffprobe there): this is a
    different mechanism (generic AVCodecContext colour fields the libx264
    encoder wrapper reads directly, not a private x264 option string) and it
    does work. Final container duration also matched the exact sum of the
    input clip durations in that test (3.000000s for two 1.5s clips) -- AAC's
    encoder priming is signalled through the mp4 container's own delay
    accounting rather than skewing the reported duration.
    """
    concat = write_concat(clips, ws.concat_path)

    ordered = [o for o in spec.overlays if o.id in overlay_pngs]
    enables = [overlay_enable(o.start, o.end) for o in ordered]
    graph = build_graph(len(ordered), enables)
    ws.graph_path.write_text(graph, encoding="utf-8")

    inputs = ["-f", "concat", "-safe", "0", "-i", str(concat)]
    for overlay in ordered:
        inputs += ["-i", str(overlay_pngs[overlay.id])]
    audio_index = 1 + len(ordered)
    inputs += ["-i", str(mix)]

    delivery = spec.delivery
    crf = DRAFT_CRF if mode == "draft" else delivery.crf
    preset = DRAFT_PRESET if mode == "draft" else delivery.preset

    # Draft-mode profile fix (surfaced only by the e2e run against the real
    # binary -- no unit test exercises a real encode). `-preset ultrafast`
    # sets cabac=0/8x8dct=0/bframes=0, and libx264's `-profile:v <name>` can
    # only ever CONSTRAIN the actual feature set down to that profile, never
    # force weaker preset defaults back up to it: with `-preset ultrafast
    # -profile:v high` alone, the muxed SPS still reported "Constrained
    # Baseline" (verified on the installed 9.0 binary), because
    # cabac=0/8x8dct=0/bframes=0 already satisfy Baseline and x264 signals
    # whatever profile the *actual* encode needs, not the name that was
    # requested. Design §4 stage D says draft mode overrides only
    # `delivery.crf`/`delivery.preset` and "every other delivery setting is
    # honored so a draft still exercises the real conformance path" -- which
    # includes `delivery.profile`. Re-enabling cabac and the 8x8 transform
    # via `-x264-params` restores that: confirmed on the same binary that
    # adding only this flag to the same ultrafast command makes ffprobe
    # report `profile=High`.
    #
    # CORRECTION (task-15 review): an earlier version of this comment claimed
    # this was "safe for any configured profile" because `-profile:v` is
    # parsed after `-x264-params` and `x264_param_apply_profile` would
    # constrain the features back down for "main"/"baseline". That claim was
    # never actually verified and is false: `8x8dct` is itself a High-only
    # feature, so forcing it on drags the signalled profile UP to High
    # regardless of what `-profile:v` requested -- reproduced directly with
    # this exact argv (`-preset ultrafast -profile:v main -x264-params
    # cabac=1:8x8dct=1` -> `profile=High`, not Main) and end-to-end through
    # `cmd_render` with `delivery.profile` set to "main" (QA failed, "FAIL
    # container: profile High"). So this fix is gated to specs that actually
    # request "high" -- the only profile it's known to restore correctly.
    # A spec requesting "main" or "baseline" gets no override here and keeps
    # whatever `-preset ultrafast` naturally produces; verify.py's container
    # check will correctly fail that combination until a per-profile
    # feature mapping is added, which no current spec (including this
    # module's default) needs.
    profile_args = (
        ["-x264-params", "cabac=1:8x8dct=1"]
        if mode == "draft" and delivery.profile.lower() == "high"
        else []
    )

    ffmpeg.run(
        [
            "ffmpeg", "-hide_banner", "-y", *inputs,
            _FILTER_COMPLEX_FROM_FILE, str(ws.graph_path),
            "-map", "[vout]", "-map", f"{audio_index}:a",
            "-c:v", delivery.codec, "-crf", str(crf), "-preset", preset,
            "-profile:v", delivery.profile, "-pix_fmt", delivery.pix_fmt,
            *profile_args,
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-fps_mode", "cfr", "-r", str(spec.canvas.fps),
            "-c:a", delivery.audio_codec, "-b:a", delivery.audio_bitrate,
            "-ar", str(delivery.audio_rate),
            "-movflags", "+faststart",
            "-shortest", str(ws.master_path),
        ],
        log_path,
    )
    return ws.master_path
