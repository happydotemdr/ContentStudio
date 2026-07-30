# pipeline_app/browse_service.py
"""Read-only folder/file access scoped under repo_root/output, for the
Browse page. Pure logic only -- no FastAPI or Jinja imports here."""

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

import markdown
import yaml

from pipeline_app import artifacts

MAX_FILE_BYTES = 5 * 1024 * 1024


class PathSafetyError(Exception):
    """Raised when a requested path would resolve outside output/."""


def output_root(repo_root: Path) -> Path:
    return (repo_root / "output").resolve()


def resolve_under_output(root: Path, rel_path: str) -> Path:
    rel_path = (rel_path or "").strip()
    if rel_path in ("", ".", "/"):
        return root

    normalized = rel_path.replace("\\", "/")

    # A colon anywhere (not just a leading drive letter) also catches
    # Windows drive-relative forms like "C:foo", which pathlib's
    # is_absolute() does NOT flag as absolute.
    if ":" in normalized:
        raise PathSafetyError("':' is not allowed in path")
    if PureWindowsPath(normalized).is_absolute() or PurePosixPath(normalized).is_absolute():
        raise PathSafetyError("absolute paths are not allowed")

    segments = [seg for seg in normalized.split("/") if seg]
    if any(seg == ".." for seg in segments):
        raise PathSafetyError("'..' is not allowed in path")

    candidate = (root / "/".join(segments)).resolve()
    if not candidate.is_relative_to(root):
        raise PathSafetyError("path escapes output/")
    return candidate
