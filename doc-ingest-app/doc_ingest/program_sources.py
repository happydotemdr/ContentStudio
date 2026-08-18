"""Loads the human-maintained allowlist of exact converted-file paths Phase 2
generation may treat as current program/framework/PQ grounding. Deliberately
NOT derived from `status: current`, which duplicate/archived files in the
real corpus have already been shown to falsify (design spec, 'Freshness')."""
from __future__ import annotations

from pathlib import Path

import yaml

WATCHED_PREFIXES = (
    "Offer & Coaching Framework/Current finalized documents/",
    "Frameworks to consider/Sabatoures/",
)


def load_program_sources(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(raw.get("paths", []))


def check_drift(dest_rel_path: str, allowlist: list[str]) -> str | None:
    for prefix in WATCHED_PREFIXES:
        if dest_rel_path.startswith(prefix) and dest_rel_path not in allowlist:
            return f"{dest_rel_path} is under a watched folder but not in program_sources.yaml"
    return None
