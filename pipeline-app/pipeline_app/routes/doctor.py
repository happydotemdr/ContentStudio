from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/doctor")
def doctor_page(request: Request):
    repo_root = request.app.state.repo_root
    skills_dir = repo_root / ".claude" / "skills"
    skill_names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.exists() else []
    return request.app.state.templates.TemplateResponse(
        request, "doctor.html",
        {
            "repo_root": str(repo_root),
            "db_path": str(getattr(request.app.state, "db_path", "")),
            "cli": request.app.state.cli_probe.get(),
            "skill_names": skill_names,
            "orphaned_count": getattr(request.app.state, "orphaned_count", 0),
            "active_nav": "doctor",
            "cli_available": request.app.state.cli_available,
        },
    )
