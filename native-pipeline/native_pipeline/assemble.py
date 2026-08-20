"""assemble_spec builds the final RenderSpec for this mode using only
existing stitcher.spec classes -- no schema changes. Bed.gain_db ==
Bed.duck_db always, which makes stitcher's existing ducking envelope
(_build_bed() in audio.py) mathematically flat by construction, since the
music's own dynamics are already baked into its Eleven Music arrangement.

check_bed_duration is a fail-loud guard: audio.py's existing bed-conforming
step uses `-stream_loop -1 -t runtime`, which would otherwise silently
restart a too-short bed's intro under the outro, or truncate a too-long
bed mid-arrangement -- defeating the entire point of composing dynamics
into the arrangement."""

from __future__ import annotations

import subprocess
from pathlib import Path

from stitcher.spec import Audio, Bed, Canvas, Caption, Loudness, RenderSpec, SafeZone, Shot, Stem, Style

from native_pipeline.errors import BedDurationMismatchError

BED_RELATIVE_OFFSET_DB = -17.0
BED_DURATION_TOLERANCE_S = 0.05
DELIVERY_LUFS = -14.0
DELIVERY_TP_DBTP = -1.0


def check_bed_duration(bed_path: Path, runtime: float, log_path: Path) -> None:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(bed_path)]
    probe = subprocess.run(cmd, capture_output=True, text=True, check=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"$ {' '.join(cmd)}\n{probe.stdout}{probe.stderr}\n")

    bed_duration = float(probe.stdout.strip())
    delta = abs(bed_duration - runtime)
    if delta > BED_DURATION_TOLERANCE_S:
        raise BedDurationMismatchError(
            f"generated bed is {bed_duration:.3f}s, take runtime is {runtime:.3f}s "
            f"(off by {delta:.3f}s, tolerance is {BED_DURATION_TOLERANCE_S}s)"
        )


def assemble_spec(
    slug: str,
    shots: list[Shot],
    captions: list[Caption],
    voice_take: str,
    music_bed: str,
    runtime: float,
    voice_lufs: float,
    styles: dict[str, Style],
    captions_style: str,
) -> RenderSpec:
    bed_gain = voice_lufs + BED_RELATIVE_OFFSET_DB
    return RenderSpec(
        spec_version="1.0",
        slug=slug,
        canvas=Canvas(width=1080, height=1920, fps=30),
        safe_zone=SafeZone(x=90, y=380, width=900, height=1160),
        styles=styles,
        shots=shots,
        captions=captions,
        captions_style=captions_style,
        audio=Audio(
            stems=[Stem(id="voice", file=voice_take, at=0.0, duration_s=runtime)],
            bed=Bed(file=music_bed, gain_db=bed_gain, duck_db=bed_gain, windows=[], fades=[]),
            sfx=[],
            loudness=Loudness(integrated_lufs=DELIVERY_LUFS, true_peak_dbtp=DELIVERY_TP_DBTP),
        ),
    )
