from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StageDef:
    id: str
    skill: str
    dir_prefix: str
    depends_on: list[str] = field(default_factory=list)
    optional_depends_on: list[str] = field(default_factory=list)
    brand_scope: str | None = None
    specialist: str | None = None
    specialist_mode: str | None = None


def load_topology(path: Path) -> list[StageDef]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    stages = [
        StageDef(
            id=s["id"],
            skill=s["skill"],
            dir_prefix=s["dir_prefix"],
            depends_on=list(s.get("depends_on", [])),
            brand_scope=s.get("brand_scope"),
            specialist=s.get("specialist"),
            specialist_mode=s.get("specialist_mode"),
        )
        for s in data["stages"]
    ]
    _validate_topology(stages, path.parent)
    return stages


def _validate_topology(stages: list[StageDef], repo_root: Path) -> None:
    seen: set[str] = set()
    for stage in stages:
        if stage.id in seen:
            raise ValueError(f"pipeline.yaml: duplicate stage id '{stage.id}'")
        seen.add(stage.id)
    for stage in stages:
        for dep in stage.depends_on:
            if dep not in seen:
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' depends_on unknown stage '{dep}'"
                )
    _check_no_cycles(stages)
    for stage in stages:
        if stage.specialist is not None:
            skill_md = repo_root / ".claude" / "skills" / stage.specialist / "SKILL.md"
            if not skill_md.exists():
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' specialist '{stage.specialist}' has no "
                    f"skill at {skill_md}"
                )
            # sidebar.html renders specialist_mode == "manual" as "(manual
            # hand-off)" and treats anything else -- including a missing
            # value or a typo like "Manual" -- as "(auto-delegated)", the
            # stronger/wrong claim. A stage with a specialist must declare an
            # unambiguous mode rather than silently defaulting to that claim.
            if stage.specialist_mode not in ("auto", "manual"):
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' specialist_mode must be 'auto' or "
                    f"'manual', got {stage.specialist_mode!r}"
                )


def _check_no_cycles(stages: list[StageDef]) -> None:
    by_id = {s.id: s for s in stages}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {s.id: WHITE for s in stages}

    def visit(stage_id: str, path: list[str]) -> None:
        color[stage_id] = GRAY
        for dep in by_id[stage_id].depends_on:
            if color[dep] == GRAY:
                cycle = " -> ".join(path + [dep])
                raise ValueError(f"pipeline.yaml: dependency cycle detected: {cycle}")
            if color[dep] == WHITE:
                visit(dep, path + [dep])
        color[stage_id] = BLACK

    for stage in stages:
        if color[stage.id] == WHITE:
            visit(stage.id, [stage.id])


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
        entry = {
            "id": stage_def.id, "status": row["status"],
            "specialist": stage_def.specialist, "specialist_mode": stage_def.specialist_mode,
        }
        if stage_def.dir_prefix not in groups:
            groups[stage_def.dir_prefix] = []
            order.append(stage_def.dir_prefix)
        groups[stage_def.dir_prefix].append(entry)
    return [groups[prefix] for prefix in order]
