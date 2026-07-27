import hashlib
from pathlib import Path

import yaml


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


def write_pointer(stage_dir: Path, rgs_brief_relpath: str) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = stage_dir / "pointer.yaml"
    pointer_path.write_text(
        yaml.safe_dump({"rgs_brief_path": rgs_brief_relpath}, sort_keys=False),
        encoding="utf-8",
    )
    return pointer_path


def read_pointer(stage_dir: Path) -> str | None:
    pointer_path = stage_dir / "pointer.yaml"
    if not pointer_path.exists():
        return None
    data = yaml.safe_load(pointer_path.read_text(encoding="utf-8")) or {}
    return data.get("rgs_brief_path")


def supersede_previous_brief(repo_root: Path, stage_dir: Path) -> None:
    previous = read_pointer(stage_dir)
    if not previous:
        return
    previous_path = repo_root / previous
    if not previous_path.exists():
        return
    archive_dir = previous_path.parent / ".superseded"
    archive_dir.mkdir(parents=True, exist_ok=True)
    previous_path.rename(archive_dir / previous_path.name)
