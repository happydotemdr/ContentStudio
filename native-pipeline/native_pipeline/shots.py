"""build_shots -- turns real per-beat alignment segments plus an operator-
authored asset manifest into stitcher Shot objects, one per beat, with the
image/clip holding through its trailing gap (RenderSpec requires exact shot
contiguity -- see spec.py's validate_spec -- and real inter-beat gaps mean a
naive at/at+duration mapping is NOT contiguous)."""

from __future__ import annotations

from stitcher.spec import Motion, Shot
from stitcher.vo_alignment import Segment

from native_pipeline.errors import ShotSegmentMismatchError


def build_shots(segments: list[Segment], asset_manifest: list[dict]) -> list[Shot]:
    manifest_by_beat = {entry["beat"]: entry for entry in asset_manifest}

    segment_names = [segment.name for segment in segments]
    manifest_names = set(manifest_by_beat)
    if set(segment_names) != manifest_names:
        missing = sorted(set(segment_names) - manifest_names)
        extra = sorted(manifest_names - set(segment_names))
        raise ShotSegmentMismatchError(
            f"asset_manifest beat names don't match segments: missing={missing} extra={extra}"
        )

    runtime = segments[-1].at + segments[-1].duration
    shots: list[Shot] = []
    for ordinal, segment in enumerate(segments, start=1):
        entry = manifest_by_beat[segment.name]
        end = segments[ordinal].at if ordinal < len(segments) else runtime
        motion = Motion(**entry["motion"]) if entry.get("motion") else Motion()
        shots.append(
            Shot(
                n=ordinal,
                id=segment.name,
                beat=segment.name,
                start=segment.at,
                end=end,
                source=entry["source"],
                kind=entry["kind"],
                source_in=entry.get("source_in_s"),
                source_out=entry.get("source_out_s"),
                motion=motion,
            )
        )

    if shots[0].start != 0.0:
        raise ShotSegmentMismatchError(f"first shot must start at 0.0, got {shots[0].start}")
    for prev, cur in zip(shots, shots[1:]):
        if prev.end != cur.start:
            raise ShotSegmentMismatchError(
                f"shots not contiguous: {prev.id!r} ends at {prev.end}, {cur.id!r} starts at {cur.start}"
            )
    if shots[-1].end != runtime:
        raise ShotSegmentMismatchError(f"last shot must end at runtime {runtime}, got {shots[-1].end}")

    return shots
