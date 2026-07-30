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


@dataclass(frozen=True)
class Entry:
    name: str
    rel_path: str
    is_dir: bool


def _is_md_name(name: str) -> bool:
    return name.lower().endswith(".md")


def _has_md_below(folder: Path) -> bool:
    with os.scandir(folder) as it:
        for entry in it:
            if entry.is_symlink():
                continue
            if entry.is_file() and _is_md_name(entry.name):
                return True
            if entry.is_dir() and _has_md_below(Path(entry.path)):
                return True
    return False


def list_children(folder: Path, root: Path) -> list["Entry"]:
    dirs: list[Entry] = []
    files: list[Entry] = []
    with os.scandir(folder) as it:
        for entry in it:
            if entry.is_symlink():
                continue
            path = Path(entry.path)
            rel_path = path.relative_to(root).as_posix()
            if entry.is_dir():
                if _has_md_below(path):
                    dirs.append(Entry(name=entry.name, rel_path=rel_path, is_dir=True))
            elif entry.is_file() and _is_md_name(entry.name):
                files.append(Entry(name=entry.name, rel_path=rel_path, is_dir=False))
    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=lambda e: e.name.lower())
    return dirs + files
