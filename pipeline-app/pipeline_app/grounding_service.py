from pathlib import Path

import yaml


def snapshot_rgs_briefs(rgs_briefs_dir: Path) -> set[str]:
    if not rgs_briefs_dir.exists():
        return set()
    return {p.name for p in rgs_briefs_dir.glob("*.md")}


def identify_new_brief(before: set[str], after: set[str]) -> str | None:
    new_files = after - before
    if len(new_files) != 1:
        return None
    return next(iter(new_files))


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
    if previous_path.exists():
        previous_path.unlink()
