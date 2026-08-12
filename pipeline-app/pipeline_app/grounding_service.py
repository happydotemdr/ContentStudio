import datetime
import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from pipeline_app.artifacts import _atomic_write_text
from pipeline_app import obs


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_rgs_briefs(rgs_briefs_dir: Path) -> dict[str, str]:
    if not rgs_briefs_dir.exists():
        return {}
    return {p.name: _hash_file(p) for p in rgs_briefs_dir.glob("*.md")}


def identify_new_brief(before: dict[str, str], after: dict[str, str]) -> str | None:
    changed = [name for name, sha in after.items() if before.get(name) != sha]
    if len(changed) != 1:
        return None
    return changed[0]


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
    pointer_path = stage_dir / "pointer.yaml"
    if not pointer_path.exists():
        return None
    data = yaml.safe_load(pointer_path.read_text(encoding="utf-8")) or {}
    return data.get("rgs_brief_path")


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
