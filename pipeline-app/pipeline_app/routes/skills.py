from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from pipeline_app import git_helper

router = APIRouter()

STAGE_ID_BY_SKILL = {
    "rgs-grounding": "grounding",
    "shorts-ideation": "ideation",
    "shorts-scripting": "scripting",
    "voiceover-brief": "voiceover",
    "visual-prompts": "visual",
    "music-brief": "music",
    "shorts-assembly": "assembly",
    "social-repurpose": "repurpose",
    "rgs-pairing-review": None,
}


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

    stage_id = STAGE_ID_BY_SKILL.get(skill_name)
    kickoff_template_content = ""
    if stage_id:
        template_path = repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"
        if template_path.exists():
            kickoff_template_content = template_path.read_text(encoding="utf-8")

    return request.app.state.templates.TemplateResponse(
        request, "skill_editor.html",
        {
            "skill_name": skill_name,
            "skill_md_content": skill_md_content,
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
        stage_id = STAGE_ID_BY_SKILL.get(skill_name)
        path = repo_root / "pipeline-app" / "stage_templates" / f"{stage_id}.md"
        path.write_text(content, encoding="utf-8")
    return RedirectResponse(url=f"/skills/{skill_name}", status_code=303)
