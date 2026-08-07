"""Thin, logged wrapper around the ffmpeg and ffprobe binaries.

Every command is appended to the run log *before* it executes, so a failure
hands you a pasteable command rather than a traceback wrapping a subprocess
error (spec §6). shell=True is never used.

Every invocation is also bounded by a wall-clock timeout, so a non-terminating
filtergraph fails loudly instead of hanging the CLI forever -- see the
`*_TIMEOUT_S` constants below for the reasoning and the override.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

STDERR_TAIL_LINES = 40

# --- wall-clock bounds on every child process ------------------------------
#
# WHY THIS EXISTS. `subprocess.run` without `timeout=` waits forever. That is
# not hypothetical here: a bare `apad` bounded only by a downstream `atrim`
# was observed spinning at 100% CPU for 13+ minutes with the output file
# frozen at 1 MB, and it was *unrecoverable* precisely because nothing bounded
# it -- a hang never fails a test, it stalls one, with no diagnostic naming
# which of the ~19 invocations in a render was the one that stopped making
# progress. A timeout converts that into a named, pasteable command.
#
# HOW THE DEFAULTS WERE CHOSEN. The rule is: the default must never fire on a
# legitimate render, because a false timeout on a slow machine is a worse
# failure than the hang it guards against. Spec §1 allows a Short up to 3
# minutes at 1080x1920 through libx264, i.e. ~5,400 frames of 2.07 Mpx at the
# `slow` preset in a single stage-D encode. A modest laptop encodes that at
# roughly 8-20 fps (~5-11 minutes); a machine four times slower still lands
# under 45 minutes. FFMPEG_TIMEOUT_S is therefore set to a full hour -- well
# past any legitimate encode, while still bounding the failure. The value's
# job is to turn an unrecoverable hang into a diagnosable error, not to be a
# performance budget, so it is deliberately loose rather than tight.
#
# The metadata calls (`ffprobe -show_streams`, `ffmpeg -version`,
# `ffmpeg -encoders`) do no work proportional to any input: they are
# sub-second in practice and get their own, much tighter bound. 120 s is
# still ~2 orders of magnitude of headroom, covering a cold binary on a
# network share or a first-run Windows Defender scan of the ffmpeg image.
FFMPEG_TIMEOUT_S = 3600.0
FFPROBE_TIMEOUT_S = 120.0

# Both are overridable for a machine slower (or a workflow more impatient)
# than the defaults assume. Set to a positive number of seconds.
FFMPEG_TIMEOUT_ENV = "STITCHER_FFMPEG_TIMEOUT_S"
FFPROBE_TIMEOUT_ENV = "STITCHER_FFPROBE_TIMEOUT_S"


class FFmpegError(RuntimeError):
    """A non-zero exit from ffmpeg or ffprobe."""


class FFmpegTimeout(FFmpegError):
    """A child process exceeded its wall-clock bound and was killed.

    A subclass of FFmpegError so every existing handler (cmd_render's, the
    tests') keeps catching it, while a caller that wants to tell "ffmpeg said
    no" from "ffmpeg stopped making progress" still can.
    """


def _timeout(env_name: str, default: float) -> float:
    """The effective bound: the env override if it is usable, else `default`.

    An unusable override warns on stderr and falls back rather than raising.
    A typo in an environment variable must not be able to abort a render --
    but it must not be swallowed either, because a silently-ignored override
    is exactly how someone concludes the timeout "doesn't work".
    """
    raw = os.environ.get(env_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if value <= 0:
        print(
            f"warning: {env_name}={raw!r} is not a positive number of seconds; "
            f"using the default of {default:g}s",
            file=sys.stderr,
        )
        return default
    return value


@dataclass(frozen=True)
class ProbeResult:
    duration: float
    width: int | None
    height: int | None
    fps: float | None
    pix_fmt: str | None
    video_codec: str | None
    audio_codec: str | None
    sample_rate: int | None
    colorspace: str | None
    # Last, with a default, so existing positional constructions stay valid.
    profile: str | None = None
    # colour_tagging (verify.py) gates on colorspace/primaries/transfer
    # together (spec §4 stage F line 503), not colorspace alone. These
    # default to None, not "bt709": a ProbeResult that never had these
    # fields supplied has not been measured for them, and defaulting to the
    # passing value would let colour_tagging report PASS on data nobody
    # provided -- the exact failure mode this field pair exists to prevent
    # (task-13 review round 1). probe() always passes an explicit value
    # (including an explicit None when a real file genuinely lacks the
    # tag), so a genuinely probed file's result never depends on this
    # default either way.
    color_primaries: str | None = None
    color_transfer: str | None = None

    @property
    def has_video(self) -> bool:
        return self.video_codec is not None

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None


def _quote_for_log(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


def run(args: list[str], log_path: Path) -> str:
    """Execute a command, returning stderr. Logs before running.

    Bounded by FFMPEG_TIMEOUT_S (see the constant for the reasoning and the
    STITCHER_FFMPEG_TIMEOUT_S override). On expiry `subprocess.run` kills the
    child, the bound is appended to the same log the command was written to,
    and FFmpegTimeout names the limit, the log and the whole command line --
    the three things an operator needs to tell a hang from a slow encode.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = " ".join(_quote_for_log(a) for a in args)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {line}\n")

    limit = _timeout(FFMPEG_TIMEOUT_ENV, FFMPEG_TIMEOUT_S)
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=limit
        )
    except subprocess.TimeoutExpired as exc:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"# TIMED OUT after {limit:g}s; the process was killed\n")
        raise FFmpegTimeout(
            f"command exceeded its {limit:g}s timeout and was killed:\n{line}\n\n"
            f"log: {log_path}\n"
            f"Raise {FFMPEG_TIMEOUT_ENV} if this render legitimately needs longer; "
            "otherwise this invocation stopped making progress."
        ) from exc

    if completed.stderr:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(completed.stderr)
            handle.write("\n")

    if completed.returncode != 0:
        tail = "\n".join((completed.stderr or "").splitlines()[-STDERR_TAIL_LINES:])
        raise FFmpegError(f"command failed (exit {completed.returncode}):\n{line}\n\n{tail}")

    return completed.stderr or ""


def _run_metadata(args: list[str]) -> subprocess.CompletedProcess:
    """Run one of the three metadata calls under FFPROBE_TIMEOUT_S.

    These three (`ffprobe -show_streams`, `ffmpeg -version`,
    `ffmpeg -encoders`) are not part of a render and have no run log to write
    to, so the timeout message says so rather than naming a log that does not
    exist. Everything else matches `run`: the bound, the command line, and the
    name of the variable that raises it.
    """
    limit = _timeout(FFPROBE_TIMEOUT_ENV, FFPROBE_TIMEOUT_S)
    line = " ".join(_quote_for_log(a) for a in args)
    try:
        return subprocess.run(
            args, capture_output=True, text=True, check=False, timeout=limit
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegTimeout(
            f"command exceeded its {limit:g}s timeout and was killed:\n{line}\n\n"
            "log: none (metadata call, made outside a render's log)\n"
            f"Raise {FFPROBE_TIMEOUT_ENV} if this machine legitimately needs longer."
        ) from exc


def _probe_json(path: Path) -> dict:
    completed = _run_metadata(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
    )
    if completed.returncode != 0:
        raise FFmpegError(f"ffprobe failed on {path}:\n{completed.stderr}")
    return json.loads(completed.stdout)


def _parse_rate(value: str | None) -> float | None:
    if not value or "/" not in value:
        return None
    numerator, denominator = value.split("/", 1)
    denom = float(denominator)
    return float(numerator) / denom if denom else None


def probe(path: Path) -> ProbeResult:
    payload = _probe_json(path)
    video = next((s for s in payload["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in payload["streams"] if s["codec_type"] == "audio"), None)
    return ProbeResult(
        duration=float(payload.get("format", {}).get("duration", 0.0)),
        width=video.get("width") if video else None,
        height=video.get("height") if video else None,
        fps=_parse_rate(video.get("r_frame_rate")) if video else None,
        pix_fmt=video.get("pix_fmt") if video else None,
        video_codec=video.get("codec_name") if video else None,
        audio_codec=audio.get("codec_name") if audio else None,
        sample_rate=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        colorspace=video.get("color_space") if video else None,
        profile=video.get("profile") if video else None,
        color_primaries=video.get("color_primaries") if video else None,
        color_transfer=video.get("color_transfer") if video else None,
    )


def ffmpeg_version() -> str:
    """First line of `ffmpeg -version`, e.g.

    'ffmpeg version 9.0-full_build-www.gyan.dev Copyright (c) 2000-2026 the
    FFmpeg developers'. Verified against the installed 9.0 binary: no
    reformatting is needed, the raw first line is returned as-is. Part of
    every cache key (spec §5).
    """
    completed = _run_metadata(["ffmpeg", "-version"])
    if completed.returncode != 0:
        raise FFmpegError("ffmpeg is not available on PATH")
    return completed.stdout.splitlines()[0].strip()


def has_encoder(name: str) -> bool:
    """True if ffmpeg was built with an encoder of exactly this name.

    Matches the encoder-name column exactly (second whitespace-separated
    token per data row of `ffmpeg -encoders`), not a substring of the whole
    listing. A naive `name in stdout` check gives false positives on this
    build: it has both `libx264` and `h264_nvenc` compiled in, so a
    substring check for e.g. "h264" would incorrectly report True from the
    NVENC encoder alone even if libx264 were absent. Verified against the
    real 9.0 `-encoders` output, including its header/legend lines, which
    tokenize to `parts[1] == "="` and never collide with a real name.
    """
    completed = _run_metadata(["ffmpeg", "-hide_banner", "-encoders"])
    if completed.returncode != 0:
        return False
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == name:
            return True
    return False


# ebur128 reports silence as a MEASUREMENT, not as an absence, and the two
# fields report it differently. Verified against the installed 9.0 binary on
# `anullsrc=r=48000:cl=stereo -t 2`:
#
#     I:         -70.0 LUFS      <- the gating floor, a finite number
#     LRA:         0.0 LU
#     Peak:       -inf dBFS      <- literally "-inf"
#
# The old numeric pattern could not match "-inf", so measure_loudness raised
# FFmpegError on a digitally silent track and the render died at exit 2 with a
# message about unreadable output -- a parse failure standing in for a
# perfectly good reading. Python's float() accepts "inf"/"-inf" directly, so
# the pattern just has to admit them; every caller then gets a real -inf and
# decides for itself what silence means (see is_digital_silence).
EBUR128_NUMBER = r"-?(?:inf|\d+(?:\.\d+)?)"

# The flat value ebur128 reports for anything at or below its gating floor.
# verify.EBUR128_FLOOR_DB is the same number, used there to reject a duck
# window whose reading is dominated by the floor; here it is the honest signal
# that a track has no measurable programme at all.
EBUR128_FLOOR_LUFS = -70.0

_I = re.compile(rf"^\s*I:\s*({EBUR128_NUMBER})\s*LUFS", re.MULTILINE)
_TP = re.compile(rf"^\s*Peak:\s*({EBUR128_NUMBER})\s*dBFS", re.MULTILINE)
_LRA = re.compile(rf"^\s*LRA:\s*({EBUR128_NUMBER})\s*LU", re.MULTILINE)


def is_digital_silence(measured: dict) -> bool:
    """True when an ebur128 measurement describes no programme at all.

    Detected FROM THE MEASUREMENT rather than guessed from the inputs: a
    stem synthesized as silence, a stem that is silent on disk, and a mix of
    both are the same fact about the audio, and only the measurement knows.

    Either signal is sufficient and each covers a case the other misses. A
    true peak of -inf is exact digital zero. An integrated loudness at or
    below the gating floor is a track ebur128 declined to measure -- which is
    the operative condition for anything expressed relative to it, whether or
    not a stray non-zero sample lifted the peak off -inf.
    """
    return (
        measured["input_tp"] == float("-inf")
        or measured["input_i"] <= EBUR128_FLOOR_LUFS
    )


def measure_loudness(path: Path, log_path: Path) -> dict:
    """Integrated LUFS, true peak, and LRA via the ebur128 filter.

    ebur128's per-second progress lines (e.g. "[Parsed_ebur128_0 @ ...] t:
    0.19  ... I: -70.0 LUFS ... LRA: 0.0 LU") also contain "I:"/"LRA:"
    tokens, but never at true line-start (they're prefixed by the frame
    tag and other fields on the same line), so the ^-anchored, MULTILINE
    regexes below only match the final "Summary:" block. Confirmed against
    real ffmpeg 9.0 ebur128 output. `matches[-1]` is an extra safety net so
    the last (summary) occurrence always wins even if that assumption ever
    breaks.
    """
    stderr = run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
        log_path,
    )

    def grab(pattern: re.Pattern[str], label: str) -> float:
        matches = pattern.findall(stderr)
        if not matches:
            raise FFmpegError(f"could not read {label} from ebur128 output for {path}")
        return float(matches[-1])

    return {
        "input_i": grab(_I, "integrated loudness"),
        "input_tp": grab(_TP, "true peak"),
        "input_lra": grab(_LRA, "loudness range"),
    }
