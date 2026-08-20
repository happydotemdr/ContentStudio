"""Extract each Segment (stitcher.vo_alignment.Segment) from a single
continuous VO recording into its own audio file, via a plain ffmpeg trim --
no re-encoding decisions beyond the standard stitcher intermediate format
(pcm_s16le, 48kHz, stereo), matching precondition.py's own output
convention so condition_clip() can consume these files directly.
"""

from __future__ import annotations

from pathlib import Path

from . import ffmpeg
from .vo_alignment import Segment


def split_segments(
    source: Path,
    segments: list[Segment],
    out_dir: Path,
    log_path: Path,
) -> list[Path]:
    """Write one WAV file per segment to out_dir, named "<segment.name>.wav".
    Returns the output paths in the same order as `segments`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for segment in segments:
        out_path = out_dir / f"{segment.name}.wav"
        ffmpeg.run(
            [
                "ffmpeg", "-hide_banner", "-y",
                "-i", str(source),
                "-ss", f"{segment.at:.6f}",
                "-t", f"{segment.duration:.6f}",
                "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                str(out_path),
            ],
            log_path,
        )
        outputs.append(out_path)
    return outputs
