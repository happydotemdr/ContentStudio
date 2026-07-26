import hashlib
import re
from pathlib import Path

import yaml

_DELIM = "---"
_VERSION_RE = re.compile(r"artifact\.v(\d+)\.md$")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != _DELIM:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            yaml_text = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1:])
            meta = yaml.safe_load(yaml_text) or {}
            return meta, body.lstrip("\n")
    return {}, text


def render_frontmatter(meta: dict, body: str) -> str:
    yaml_text = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False).strip()
    return f"{_DELIM}\n{yaml_text}\n{_DELIM}\n\n{body.strip()}\n"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _versions_in(stage_dir: Path) -> list[tuple[int, Path]]:
    versions = []
    for p in stage_dir.glob("artifact.v*.md"):
        m = _VERSION_RE.match(p.name)
        if m:
            versions.append((int(m.group(1)), p))
    return versions


def next_version_number(stage_dir: Path) -> int:
    versions = _versions_in(stage_dir)
    return (max(v for v, _ in versions) if versions else 0) + 1


def latest_artifact_path(stage_dir: Path) -> Path | None:
    versions = _versions_in(stage_dir)
    if not versions:
        return None
    return max(versions, key=lambda t: t[0])[1]


def write_artifact(stage_dir: Path, version: int, meta: dict, body: str) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    path = stage_dir / f"artifact.v{version}.md"
    path.write_text(render_frontmatter(meta, body), encoding="utf-8")
    return path


def stamp_final(path: Path, finalized_at: str) -> None:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    meta["status"] = "final"
    meta["finalized_at"] = finalized_at
    path.write_text(render_frontmatter(meta, body), encoding="utf-8")
