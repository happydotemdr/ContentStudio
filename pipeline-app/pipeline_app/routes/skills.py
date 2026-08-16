from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pathlib import Path

from pipeline_app import git_helper, obs

router = APIRouter()


def _stage_id_by_skill(stage_defs) -> dict[str, str]:
    """Skill name -> stage id, derived from the loaded topology.

    Replaces a hand-maintained dict that had already drifted from
    pipeline.yaml (A-48). P4 owns the canonical version of this function --
    see the P4 contract in this package's plan; this private copy exists only
    so P5 is not blocked on P4, and T19 deletes it.
    """
    return {s.skill: s.id for s in stage_defs}


def _template_path(repo_root: Path, stage_id: str) -> Path:
    # Convention frozen with P4 -- see the P4 contract. T19 replaces this with
    # pipeline_config.stage_template_path().
    return repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"


def _discovered_skill_names(repo_root) -> set[str]:
    skills_dir = repo_root / ".claude" / "skills"
    if not skills_dir.exists():
        return set()
    return {p.name for p in skills_dir.iterdir() if p.is_dir()}


@router.get("/skills")
def skill_list(request: Request):
    repo_root = request.app.state.repo_root
    skill_names = sorted(_discovered_skill_names(repo_root))
    return request.app.state.templates.TemplateResponse(
        request, "skill_list.html",
        {
            "skill_names": skill_names,
            "active_nav": "skills",
            "cli_available": request.app.state.cli_available,
        },
    )


@router.get("/skills/{skill_name}")
def skill_detail(request: Request, skill_name: str):
    repo_root = request.app.state.repo_root

    # SECURITY: skill_name is an attacker/user-controlled URL path segment.
    # It must be validated against the actual discovered skill set BEFORE it
    # is used to build any filesystem path — a set-membership check (not a
    # string blocklist on ".." or "/") is robust against path traversal via
    # forward slashes, backslashes, or URL-encoded variants alike.
    discovered = _discovered_skill_names(repo_root)
    if skill_name not in discovered:
        raise HTTPException(status_code=404, detail="Unknown skill.")

    skill_md_path = repo_root / ".claude" / "skills" / skill_name / "SKILL.md"
    skill_md_content = skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""

    stage_id = _stage_id_by_skill(request.app.state.stage_defs).get(skill_name)
    template_path = _template_path(repo_root, stage_id) if stage_id else None
    kickoff_template_missing = bool(stage_id) and not template_path.is_file()
    kickoff_template_content = (
        template_path.read_text(encoding="utf-8")
        if template_path is not None and template_path.is_file() else ""
    )
    if kickoff_template_missing:
        obs.log("skill_editor.template_file_missing", level="warning",
                skill=skill_name, stage_id=stage_id, path=str(template_path))

    return request.app.state.templates.TemplateResponse(
        request, "skill_editor.html",
        {
            "skill_name": skill_name,
            "skill_md_content": skill_md_content,
            "stage_id": stage_id,
            "kickoff_template_applies": stage_id is not None,
            "kickoff_template_missing": kickoff_template_missing,
            "kickoff_template_content": kickoff_template_content,
            "active_nav": "skills",
            "cli_available": request.app.state.cli_available,
        },
    )


@router.post("/skills/{skill_name}/save")
def save_skill(request: Request, skill_name: str, target: str = Form(...), content: str = Form(...)):
    repo_root = request.app.state.repo_root

    # SECURITY: same discovered-set validation as skill_detail above, done
    # first and before any path construction or file I/O in this route.
    discovered = _discovered_skill_names(repo_root)
    if skill_name not in discovered:
        raise HTTPException(status_code=404, detail="Unknown skill.")

    if target == "SKILL.md":
        path = repo_root / ".claude" / "skills" / skill_name / "SKILL.md"
        path.write_text(content, encoding="utf-8")
        git_helper.commit_skill_edit(repo_root, path, skill_name)
    elif target == "kickoff_template":
        stage_id = _stage_id_by_skill(request.app.state.stage_defs).get(skill_name)
        path = repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"
        path.write_text(content, encoding="utf-8")
    return RedirectResponse(url=f"/skills/{skill_name}", status_code=303)
