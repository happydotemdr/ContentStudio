# pipeline_app/browse_service.py
"""Read-only folder/file access scoped under repo_root/output, for the
Browse page. Pure logic only -- no FastAPI or Jinja imports here."""

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath

import markdown

from pipeline_app import artifacts, grounding_service
from pipeline_app import db as db_mod

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


_RUN_ID_TIMESTAMP_RE = re.compile(r"-(\d{8}-\d{6})$")


def _parse_created_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_run_id_timestamp(name: str) -> datetime | None:
    m = _RUN_ID_TIMESTAMP_RE.search(name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        # Shape-valid (8 digits, 6 digits) but calendar-invalid (e.g. Feb
        # 31st, hour 25) -- treat the same as "no parseable timestamp"
        # rather than letting this crash the whole /browse page.
        return None


def list_pipeline_projects(conn, repo_root: Path) -> list["Entry"]:
    runs_dir = runs_root(repo_root)
    if not runs_dir.is_dir():
        return []

    brand_and_created: dict[str, tuple[str, str]] = {
        row["run_id"]: (row["brand"], row["created_at"]) for row in db_mod.list_projects(conn)
    }

    candidates: list[tuple[str, str | None, str | None]] = []
    try:
        with os.scandir(runs_dir) as it:
            for entry in it:
                if entry.is_symlink() or not entry.is_dir():
                    continue
                brand, created_at = brand_and_created.get(entry.name, (None, None))
                candidates.append((entry.name, brand, created_at))
    except OSError as exc:
        raise FolderReadError(str(exc)) from exc

    _EPOCH = datetime.min.replace(tzinfo=timezone.utc)

    def sort_tuple(item: tuple[str, str | None, str | None]):
        # DB created_at is ISO 8601 ("2026-07-28T12:00:00+00:00"); an
        # orphan folder's fallback key is parsed from its run_id suffix
        # ("20260728-120000"). These two string formats do NOT compare
        # correctly against each other lexically (e.g. "2026-...": the
        # "-" at index 4 sorts below the "0" a compact-format string has
        # at the same index) -- both are parsed to real datetimes here so
        # comparison is always by actual chronological value, never by
        # incidental string shape.
        name, _brand, created_at = item
        when = _parse_created_at(created_at) if created_at else _parse_run_id_timestamp(name)
        return (when is not None, when or _EPOCH, name.lower())

    candidates.sort(key=sort_tuple, reverse=True)
    return [
        Entry(
            name=f"{name} ({brand})" if brand else name,
            rel_path=name,
            is_dir=True,
        )
        for name, brand, _created_at in candidates
    ]


def resolve_grounding_pointer(pointer_dir: Path, repo_root: Path) -> Path | None:
    """Resolve a grounding stage's pointer.yaml to the real rgs-briefs/ file
    it references. pointer.yaml's content is read from disk, not derived
    from the request/tree structure, so its target path is a new trust
    boundary here and gets an explicit containment check against the real
    rgs-briefs/ folder rather than being trusted outright."""
    try:
        target_rel = grounding_service.read_pointer(pointer_dir)
    except grounding_service.InvalidPointerError:
        # Malformed or non-mapping pointer.yaml content (hand-edited or
        # truncated) -- treat the same as "no valid pointer here" rather
        # than crashing tree expansion for the whole project.
        return None
    if not target_rel:
        return None
    rgs_briefs_root = (repo_root / "rgs-briefs").resolve()
    target = (repo_root / target_rel).resolve()
    if not target.is_relative_to(rgs_briefs_root):
        return None
    if not target.exists():
        return None
    return target


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
    unreadable: bool = False
    broken_reason: str | None = None


def _is_md_name(name: str) -> bool:
    return name.lower().endswith(".md")


def _md_below_state(folder: Path, repo_root: Path) -> str:
    """One of "content", "empty", "unreadable".

    The tri-state is the whole point. The old boolean (_has_md_below)
    returned False for both "nothing to show here" and "I could not look",
    and list_children used it as the include test -- so a permission-denied
    folder was not rendered as unreadable, it vanished from its parent's
    listing and the operator saw a shorter tree with no error anywhere
    (E-14a)."""
    try:
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_symlink():
                    continue
                if entry.is_file() and entry.name == "raw_output.md":
                    # Must agree with list_children's exclusion below.
                    continue
                if entry.is_file() and _is_md_name(entry.name):
                    return "content"
                if entry.is_file() and entry.name == "pointer.yaml":
                    try:
                        target_rel = grounding_service.read_pointer(folder)
                    except grounding_service.InvalidPointerError:
                        target_rel = None
                    if target_rel:
                        # A pointer with valid syntax is content even when
                        # its target file is missing on disk: the operator
                        # must be able to click through and read why
                        # (E-14b) -- it must not be silently treated as
                        # empty.
                        return "content"
                if entry.is_dir():
                    below = _md_below_state(Path(entry.path), repo_root)
                    if below in ("content", "unreadable"):
                        return below
    except OSError:
        return "unreadable"
    return "empty"


_ARTIFACT_VERSION_RE = re.compile(r"artifact\.v(\d+)\.md$", re.IGNORECASE)


def _file_sort_key(entry: "Entry") -> tuple:
    m = _ARTIFACT_VERSION_RE.match(entry.name)
    if m:
        return (0, int(m.group(1)), entry.name.lower())
    return (1, 0, entry.name.lower())


def list_children(folder: Path, root: Path, repo_root: Path) -> list["Entry"]:
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
                    state = _md_below_state(path, repo_root)
                    if state == "content":
                        dirs.append(Entry(name=entry.name, rel_path=rel_path, is_dir=True))
                    elif state == "unreadable":
                        dirs.append(Entry(
                            name=entry.name, rel_path=rel_path, is_dir=True,
                            unreadable=True,
                            broken_reason="this folder could not be read (permission denied, or it changed during the scan)",
                        ))
                elif entry.is_file():
                    if entry.name == "raw_output.md":
                        # Pre-versioning scratch state, already captured in
                        # the corresponding artifact.vN.md body -- showing
                        # both is redundant clutter, not useful history.
                        continue
                    if _is_md_name(entry.name):
                        files.append(Entry(name=entry.name, rel_path=rel_path, is_dir=False))
                    elif entry.name == "pointer.yaml":
                        target = resolve_grounding_pointer(folder, repo_root)
                        if target is not None:
                            files.append(Entry(
                                name=f"current-brief.md ({target.name})",
                                rel_path=rel_path,
                                is_dir=False,
                            ))
    except OSError as exc:
        # Unlike an empty folder, this must surface as an error rather than
        # silently returning [] -- to the caller those would look identical.
        raise FolderReadError(str(exc)) from exc
    dirs.sort(key=lambda e: e.name.lower())
    files.sort(key=_file_sort_key)
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
    except artifacts.MalformedArtifactError as exc:
        if "not valid YAML" in exc.reason:
            return {"error": "Frontmatter is not valid YAML."}
        return {"error": "Frontmatter is not a key/value mapping."}

    return {
        "frontmatter": meta,
        "body_html": markdown.markdown(body, extensions=["tables"]),
    }
