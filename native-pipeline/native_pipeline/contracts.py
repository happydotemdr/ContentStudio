"""Loaders and structural validators for the two small data contracts this
pipeline needs: asset_manifest (per-beat visual direction, translating
visual-prompts' prose output) and bed_arc (per-movement music direction,
translating music-brief's prose bed arc). Both are plain operator-authored
JSON -- no skill emits them directly. Raises bare ValueError on structural
problems, matching stitcher's own validate-at-load-time convention
(spec.py, vo_alignment.py, vo_timing.py all do the same)."""

from __future__ import annotations

import json
from pathlib import Path

VALID_KINDS = {"still", "clip"}
VALID_DENSITIES = {"sparse", "medium", "full"}


def load_asset_manifest(path: Path) -> list[dict]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    for entry in entries:
        beat = entry.get("beat")
        kind = entry.get("kind")
        if kind not in VALID_KINDS:
            raise ValueError(f"asset_manifest entry {beat!r}: kind must be one of {VALID_KINDS}, got {kind!r}")
        if kind == "still" and not entry.get("motion"):
            raise ValueError(f"asset_manifest entry {beat!r}: kind='still' requires a motion dict")
        if kind == "clip" and (entry.get("source_in_s") is None or entry.get("source_out_s") is None):
            raise ValueError(
                f"asset_manifest entry {beat!r}: kind='clip' requires source_in_s and source_out_s"
            )
    return entries


def load_bed_arc(path: Path) -> list[dict]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    for entry in entries:
        label = entry.get("label")
        density = entry.get("density")
        if density not in VALID_DENSITIES:
            raise ValueError(f"bed_arc entry {label!r}: density must be one of {VALID_DENSITIES}, got {density!r}")
        if entry.get("end_s", 0) <= entry.get("start_s", 0):
            raise ValueError(
                f"bed_arc entry {label!r}: end_s ({entry.get('end_s')}) must be after start_s ({entry.get('start_s')})"
            )
    return entries
