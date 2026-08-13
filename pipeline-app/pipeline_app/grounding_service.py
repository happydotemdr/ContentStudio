import datetime
import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml

from pipeline_app.artifacts import _atomic_write_text
from pipeline_app import obs

_POINTER_ROOT = "rgs-briefs"


class InvalidPointerError(Exception):
    """pointer.yaml exists but is not a usable pointer."""


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_rgs_briefs(rgs_briefs_dir: Path) -> dict[str, str]:
    """Relative posix path -> sha256 for every brief, RECURSIVELY (A-81)."""
    if not rgs_briefs_dir.exists():
        return {}
    return {
        p.relative_to(rgs_briefs_dir).as_posix(): _hash_file(p)
        for p in sorted(rgs_briefs_dir.rglob("*.md"))
        if p.is_file()
    }


@dataclass(frozen=True)
class BriefChange:
    brief: str | None
    added: list[str]
    modified: list[str]
    reason: str


def classify_brief_change(before: dict[str, str], after: dict[str, str]) -> BriefChange:
    """Which brief a grounding turn produced, and why the answer is what it is.

    Replaces identify_new_brief, which returned a bare str | None and collapsed
    every non-unit outcome into None (A-81). Renamed rather than re-typed so an
    unmigrated caller fails loudly instead of formatting a dataclass repr into
    a pointer path.
    """
    added = sorted(n for n in after if n not in before)
    modified = sorted(n for n in after if n in before and before[n] != after[n])
    if len(added) == 1:
        extra = f"; {len(modified)} other file(s) also modified" if modified else ""
        return BriefChange(added[0], added, modified, f"one brief added{extra}")
    if not added and len(modified) == 1:
        # A same-day rerun on the same topic overwrites the brief in place --
        # same filename, new content.
        return BriefChange(modified[0], added, modified, "one brief modified in place")
    if not added and not modified:
        return BriefChange(None, [], [], "no brief was written")
    return BriefChange(
        None, added, modified,
        f"expected exactly 1 new brief, found {len(added)} added and "
        f"{len(modified)} modified: " + ", ".join(added + modified),
    )


@dataclass(frozen=True)
class PointerStatus:
    """no_pointer | unpinned | missing_target | hash_mismatch | ok"""
    state: str
    path: str | None = None
    recorded_sha256: str | None = None
    actual_sha256: str | None = None


def write_pointer(stage_dir: Path, rgs_brief_relpath: str, repo_root: Path) -> Path:
    """Point a grounding stage at the brief it produced, pinned to that brief's
    exact bytes.

    A-80: the pointer stored only rgs_brief_path, so the brief under an
    approved grounding stage could be rewritten with no staleness signal at
    all. The hashing machinery already existed -- snapshot_rgs_briefs computes
    a sha256 for every brief -- and was thrown away. `repo_root` is required,
    not optional, so an unmigrated caller fails loudly instead of silently
    writing an unpinned pointer.
    """
    target = repo_root / rgs_brief_relpath
    stage_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = stage_dir / "pointer.yaml"
    _atomic_write_text(
        pointer_path,
        yaml.safe_dump(
            {
                "rgs_brief_path": rgs_brief_relpath,
                "sha256": _hash_file(target),
                "size": target.stat().st_size,
                "written_at": datetime.datetime.now(datetime.timezone.utc)
                .isoformat(timespec="seconds"),
            },
            sort_keys=False,
        ),
    )
    return pointer_path


def read_pointer(stage_dir: Path) -> str | None:
    """The brief path a grounding stage points at, or None if there is no
    pointer at all. A pointer that EXISTS but is unusable raises -- returning
    None for both would put a hand-broken pointer and an un-run stage in the
    same bucket (A-82)."""
    pointer_path = stage_dir / "pointer.yaml"
    if not pointer_path.exists():
        return None
    try:
        data = yaml.safe_load(pointer_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise InvalidPointerError(f"{pointer_path}: not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidPointerError(
            f"{pointer_path}: parsed to "
            f"{'nothing' if data is None else type(data).__name__}, not a mapping"
        )
    value = data.get("rgs_brief_path")
    if not isinstance(value, str) or not value.strip():
        raise InvalidPointerError(f"{pointer_path}: rgs_brief_path is missing or not a string")
    normalised = value.replace("\\", "/")
    parts = PureWindowsPath(normalised).parts
    if (
        PureWindowsPath(normalised).is_absolute()
        or PurePosixPath(normalised).is_absolute()
        or ".." in parts
        or parts[:1] != (_POINTER_ROOT,)
    ):
        raise InvalidPointerError(
            f"{pointer_path}: rgs_brief_path {value!r} must be a relative path under "
            f"{_POINTER_ROOT}/ -- refusing to read outside the brief directory"
        )
    return value


def verify_pointer(stage_dir: Path, repo_root: Path) -> PointerStatus:
    """Whether a grounding stage's pinned brief is still the brief it approved."""
    pointer_path = stage_dir / "pointer.yaml"
    if not pointer_path.exists():
        return PointerStatus("no_pointer")
    relpath = read_pointer(stage_dir)
    data = yaml.safe_load(pointer_path.read_text(encoding="utf-8")) or {}
    recorded = data.get("sha256")
    target = repo_root / relpath
    if not target.exists():
        return PointerStatus("missing_target", relpath, recorded, None)
    actual = _hash_file(target)
    if not isinstance(recorded, str) or len(recorded) != 64:
        obs.log("grounding.pointer_unpinned", level="warning", pointer=str(pointer_path))
        return PointerStatus("unpinned", relpath, None, actual)
    if recorded != actual:
        return PointerStatus("hash_mismatch", relpath, recorded, actual)
    return PointerStatus("ok", relpath, recorded, actual)
