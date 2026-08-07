"""Thin, logged wrapper around the ffmpeg and ffprobe binaries.

Every command is appended to the run log *before* it executes, so a failure
hands you a pasteable command rather than a traceback wrapping a subprocess
error (spec §6). shell=True is never used.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

STDERR_TAIL_LINES = 40


class FFmpegError(RuntimeError):
    """A non-zero exit from ffmpeg or ffprobe."""


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
    """Execute a command, returning stderr. Logs before running."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = " ".join(_quote_for_log(a) for a in args)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {line}\n")

    completed = subprocess.run(args, capture_output=True, text=True, check=False)

    if completed.stderr:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(completed.stderr)
            handle.write("\n")

    if completed.returncode != 0:
        tail = "\n".join((completed.stderr or "").splitlines()[-STDERR_TAIL_LINES:])
        raise FFmpegError(f"command failed (exit {completed.returncode}):\n{line}\n\n{tail}")

    return completed.stderr or ""


def _probe_json(path: Path) -> dict:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=False,
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
    completed = subprocess.run(
        ["ffmpeg", "-version"], capture_output=True, text=True, check=False
    )
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
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        return False
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == name:
            return True
    return False


_I = re.compile(r"^\s*I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", re.MULTILINE)
_TP = re.compile(r"^\s*Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", re.MULTILINE)
_LRA = re.compile(r"^\s*LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", re.MULTILINE)


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
