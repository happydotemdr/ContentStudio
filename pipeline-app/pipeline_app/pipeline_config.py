from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StageDef:
    id: str
    skill: str
    dir_prefix: str
    depends_on: list[str] = field(default_factory=list)
    brand_scope: str | None = None
    specialist: str | None = None


def load_topology(path: Path) -> list[StageDef]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        StageDef(
            id=s["id"],
            skill=s["skill"],
            dir_prefix=s["dir_prefix"],
            depends_on=list(s.get("depends_on", [])),
            brand_scope=s.get("brand_scope"),
            specialist=s.get("specialist"),
        )
        for s in data["stages"]
    ]


def stage_dir_name(stage: StageDef) -> str:
    return f"{stage.dir_prefix}-{stage.id}"
