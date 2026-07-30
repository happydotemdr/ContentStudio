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


class FolderReadError(Exception):
    """Raised when a folder cannot be scanned (permission error, folder
    removed between the route's existence check and the scan, etc.)."""


def output_root(repo_root: Path) -> Path:
    return (repo_root / "output").resolve()


def runs_root(repo_root: Path) -> Path:
    return (repo_root / "runs").resolve()


def root_path(repo_root: Path, root: str) -> Path:
    if root == "output":
        return output_root(repo_root)
    if root == "pipeline":
        return runs_root(repo_root)
    raise ValueError(f"unknown browse root: {root!r}")


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
    try:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_symlink():
                    continue
                if entry.is_file() and _is_md_name(entry.name):
                    return True
                if entry.is_dir() and _has_md_below(Path(entry.path)):
                    return True
    except OSError:
        # Can't even scan this folder (permission denied, removed mid-scan,
        # etc.) -- treat it as contributing no visible .md file to its
        # ancestor's listing. Defensive default, not a correctness claim.
        return False
    return False


def list_children(folder: Path, root: Path) -> list["Entry"]:
    dirs: list[Entry] = []
    files: list[Entry] = []
    try:
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
    except OSError as exc:
        # Unlike an empty folder, this must surface as an error rather than
        # silently returning [] -- to the caller those would look identical.
        raise FolderReadError(str(exc)) from exc
    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=lambda e: e.name.lower())
    return dirs + files


def render_md_file(path: Path) -> dict:
    try:
        size = path.stat().st_size
    except OSError as exc:
        # e.g. the file was deleted on disk between the route's existence
        # check and this call -- a real (if narrow) TOCTOU window given
        # this is a live filesystem browser, not a security boundary
        # concern here (single-user, read-only local app).
        return {"error": f"Could not read file: {exc}"}
    if size > MAX_FILE_BYTES:
        return {
            "oversize": True,
            "size_mb": size / (1024 * 1024),
            "cap_mb": MAX_FILE_BYTES / (1024 * 1024),
            "abs_path": str(path),
        }

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return {"error": f"Could not read file: {exc}"}

    try:
        meta, body = artifacts.parse_frontmatter(text)
    except yaml.YAMLError:
        return {"error": "Frontmatter is not valid YAML."}
    if not isinstance(meta, dict):
        return {"error": "Frontmatter is not a key/value mapping."}

    return {"frontmatter": meta, "body_html": markdown.markdown(body)}
