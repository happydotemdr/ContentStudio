from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StageDef:
    id: str
    skill: str
    dir_prefix: str
    depends_on: list[str] = field(default_factory=list)
    # An edge that supplies an input but does NOT gate unlocking. state_machine.
    # stages_to_unlock reads `depends_on` only, so an optional upstream never
    # locks its dependent -- which is exactly what shorts-assembly/SKILL.md:26-29
    # asks for ("genuinely optional and its absence is never a blocker") and why
    # modelling music as a hard edge would have been wrong (A-02).
    optional_depends_on: list[str] = field(default_factory=list)
    brand_scope: str | None = None
    specialist: str | None = None
    specialist_mode: str | None = None

    @property
    def all_depends_on(self) -> list[str]:
        return [*self.depends_on, *self.optional_depends_on]


# Explicit, not inferred from the projects table: a brand_scope typo has to be
# rejectable at load time, before any project exists to compare against (A-12).
KNOWN_BRAND_SCOPES = frozenset({"raisinggoodsports"})


def load_topology(path: Path, repo_root: Path | None = None) -> list[StageDef]:
    """repo_root is where `.claude/skills/` and `pipeline-app/stage_templates/`
    resolve from. It defaults to the YAML file's parent, which is correct only
    because pipeline.yaml happens to live at the repo root (A-17) -- so
    _validate_topology verifies the derived root really is a ContentStudio
    checkout instead of validating against the wrong tree in silence."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    stages = [
        StageDef(
            id=s["id"],
            skill=s["skill"],
            dir_prefix=s["dir_prefix"],
            depends_on=list(s.get("depends_on", [])),
            optional_depends_on=list(s.get("optional_depends_on", [])),
            brand_scope=s.get("brand_scope"),
            specialist=s.get("specialist"),
            specialist_mode=s.get("specialist_mode"),
        )
        for s in data["stages"]
    ]
    _validate_topology(stages, repo_root if repo_root is not None else path.parent)
    return stages


def stage_template_path(repo_root: Path, stage_id: str) -> Path:
    """The one place the kickoff-template location is spelled. _validate_topology,
    prompt_builder's loader and the skill editor must all agree on it."""
    return repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"


def stage_id_by_skill(stage_defs: list[StageDef]) -> dict[str, str]:
    """Derived, never stored. Safe to build as a plain dict only because
    _validate_topology rejects a duplicate `skill:` -- otherwise last-wins would
    bind a skill to the wrong stage's template."""
    return {s.skill: s.id for s in stage_defs}


def _validate_topology(stages: list[StageDef], repo_root: Path) -> None:
    seen: set[str] = set()
    for stage in stages:
        if stage.id in seen:
            raise ValueError(f"pipeline.yaml: duplicate stage id '{stage.id}'")
        seen.add(stage.id)
    by_skill: dict[str, list[str]] = {}
    for stage in stages:
        by_skill.setdefault(stage.skill, []).append(stage.id)
    for skill, stage_ids in by_skill.items():
        if len(stage_ids) > 1:
            raise ValueError(
                f"pipeline.yaml: skill '{skill}' is declared by {len(stage_ids)} stages "
                f"({', '.join(sorted(stage_ids))}); stage_id_by_skill would silently keep one"
            )
    for stage in stages:
        for dep in stage.all_depends_on:
            if dep not in seen:
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' depends_on unknown stage '{dep}'"
                )
    _check_no_cycles(stages)

    skills_dir = repo_root / ".claude" / "skills"
    templates_dir = repo_root / "pipeline-app" / "stage_templates"
    # An empty topology has nothing to validate against a checkout, so it
    # needs no scaffolding at all -- only guard the ones that declare stages.
    if stages and (not skills_dir.is_dir() or not templates_dir.is_dir()):
        raise ValueError(
            f"pipeline.yaml: {repo_root} is not a ContentStudio checkout — expected "
            f"{skills_dir} and {templates_dir} to exist. Pass repo_root explicitly."
        )
    scope_by_id = {s.id: s.brand_scope for s in stages}
    for stage in stages:
        # `skill` gets exactly the check `specialist` already had. It is the
        # mandatory field, and the one every template renders as /{{ skill }}.
        for field_name in ("skill", "specialist"):
            name = getattr(stage, field_name)
            if name is None:
                continue
            skill_md = skills_dir / name / "SKILL.md"
            if not skill_md.exists():
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' {field_name} '{name}' has no skill "
                    f"at {skill_md}"
                )
        template = stage_template_path(repo_root, stage.id)
        if not template.exists():
            raise ValueError(
                f"pipeline.yaml: stage '{stage.id}' has no kickoff template at {template}"
            )
        if stage.brand_scope is not None and stage.brand_scope not in KNOWN_BRAND_SCOPES:
            raise ValueError(
                f"pipeline.yaml: stage '{stage.id}' brand_scope '{stage.brand_scope}' is not "
                f"one of {sorted(KNOWN_BRAND_SCOPES)}"
            )
        for dep in stage.all_depends_on:
            dep_scope = scope_by_id[dep]
            if dep_scope is not None and stage.brand_scope != dep_scope:
                raise ValueError(
                    f"pipeline.yaml: stage '{stage.id}' (brand_scope {stage.brand_scope!r}) "
                    f"depends on '{dep}' (brand_scope {dep_scope!r}), which has no row on every "
                    f"project '{stage.id}' does — '{stage.id}' would sit locked forever."
                )
        # sidebar.html renders specialist_mode == "manual" as "(manual
        # hand-off)" and treats anything else -- including a missing
        # value or a typo like "Manual" -- as "(auto-delegated)", the
        # stronger/wrong claim. A stage with a specialist must declare an
        # unambiguous mode rather than silently defaulting to that claim.
        if stage.specialist is not None and stage.specialist_mode not in ("auto", "manual"):
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
