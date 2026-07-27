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


def build_stage_nav(stage_defs: list[StageDef], stage_rows) -> list[list[dict]]:
    """Merge the ordered/filtered stage topology with a project's DB stage
    rows into grouped nav steps, in stage_defs order (already dependency-
    correct — NOT re-sorted by dir_prefix). Stages sharing a dir_prefix (the
    voiceover/visual parallel pair) group into one step. A stage_def with no
    matching row (a brand-scoped stage this project doesn't have) is
    omitted, same as it already is everywhere else in the app."""
    rows_by_id = {row["stage_id"]: row for row in stage_rows}
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for stage_def in stage_defs:
        row = rows_by_id.get(stage_def.id)
        if row is None:
            continue
        entry = {"id": stage_def.id, "status": row["status"], "specialist": stage_def.specialist}
        if stage_def.dir_prefix not in groups:
            groups[stage_def.dir_prefix] = []
            order.append(stage_def.dir_prefix)
        groups[stage_def.dir_prefix].append(entry)
    return [groups[prefix] for prefix in order]
