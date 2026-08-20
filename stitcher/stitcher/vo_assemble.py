"""Build a stitcher.spec.Audio object from a single-take VO's derived
segments (stitcher.vo_alignment.Segment) plus their conditioned stem files
and a bed configuration. Pure assembly -- no ffmpeg, no I/O beyond what the
caller already did (conditioning each segment via precondition.condition_clip
happens before this module runs, not inside it)."""

from __future__ import annotations

from .spec import Audio, Bed, Loudness, Stem
from .vo_alignment import Segment


def build_audio_config(
    segments: list[Segment],
    stem_files: list[str],
    bed_file: str,
    bed_gain_db: float,
    bed_duck_db: float,
    delivery_lufs: float,
    delivery_tp_dbtp: float,
) -> Audio:
    """segments and stem_files must be the same length and in the same
    order -- stem_files[i] is the conditioned audio file for segments[i]."""
    if len(segments) != len(stem_files):
        raise ValueError(
            f"segments ({len(segments)}) and stem_files ({len(stem_files)}) "
            "must be the same length"
        )
    stems = [
        Stem(id=segment.name, file=stem_file, at=segment.at, gain_db=0.0)
        for segment, stem_file in zip(segments, stem_files)
    ]
    bed = Bed(
        file=bed_file,
        gain_db=bed_gain_db,
        duck_db=bed_duck_db,
        windows=[],
        fades=[],
    )
    return Audio(
        stems=stems,
        bed=bed,
        sfx=[],
        loudness=Loudness(integrated_lufs=delivery_lufs, true_peak_dbtp=delivery_tp_dbtp),
    )
