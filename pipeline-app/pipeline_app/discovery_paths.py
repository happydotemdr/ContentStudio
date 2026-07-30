"""Shared filesystem-path helpers for the discovery engine (Tasks 6-13).
Ported from download_brandintel.py's slugify (that script is left unmodified
-- see the design spec's "Relationship to the existing manual script")."""
from __future__ import annotations

import html
import re
from pathlib import Path


def slugify(value: str, maxlen: int = 80) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    value = re.sub(r"[\s_-]+", "-", value)
    return (value[:maxlen].rstrip("-")) or "untitled"


def handle_dir(repo_root: Path, platform: str, handle: str) -> Path:
    return repo_root / "output" / "brand-intel" / platform / slugify(handle.lstrip("@"))


def run_record_path(repo_root: Path, run_id: str) -> Path:
    return repo_root / "output" / "discovery-runs" / f"{run_id}.md"
