from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pathlib import Path
from urllib.parse import quote
import yaml

from pipeline_app import git_helper, obs
from pipeline_app.pipeline_config import stage_id_by_skill, stage_template_path

router = APIRouter()


def _reject(request: Request, skill_name: str, reason: str, **detail) -> HTTPException:
    """Record a rejection event and return an HTTPException."""
    obs.record_event(
        request.app.state.conn, kind="skill_editor.save_rejected", severity="warning",
        source="routes.skills", message=f"{skill_name}: {reason}",
        detail={"skill": skill_name, **detail},
    )
    return HTTPException(status_code=400, detail=reason)


def _discovered_skill_names(repo_root) -> set[str]:
    skills_dir = repo_root / ".claude" / "skills"
    if not skills_dir.exists():
        return set()
    return {
        p.name for p in skills_dir.iterdir()
        # is_dir() follows symlinks, so without the is_symlink() exclusion a
        # link placed in .claude/skills/ becomes a legitimate member of the
        # discovered set and the save route writes through it to wherever it
        # points, outside the repo included (A-56). The set-membership check
        # is otherwise the right defence and stays exactly as it is.
        if p.is_dir() and not p.is_symlink()
    }


VALID_TARGETS = ("SKILL.md", "kickoff_template")


def _normalized(content: str) -> str:
    """HTML form submission normalizes a <textarea> to CRLF; combined with
    write_text's newline=None translation that becomes \\r\\r\\n on Windows and
    every save is a whole-file diff (A-55)."""
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _validate_content(target: str, content: str) -> str | None:
    """Return an operator-facing rejection reason, or None if the body is
    safe to write. A blank textarea used to write a zero-byte file and 303 as
    a success, destroying the skill (A-51)."""
    if not content.strip():
        return "Refusing to write an empty file — the editor body was blank."

    if target != "SKILL.md":
        return None
    if not content.lstrip().startswith("---"):
        return "A SKILL.md must begin with a YAML frontmatter block (`---`)."
    parts = content.lstrip().split("---", 2)
    if len(parts) < 3:
        return "The SKILL.md frontmatter block is not closed with a second `---`."
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        return f"The SKILL.md frontmatter is not valid YAML: {exc}"
    if not isinstance(meta, dict):
        return "The SKILL.md frontmatter must be a YAML mapping."
    missing = [k for k in ("name", "description") if not str(meta.get(k) or "").strip()]
    if missing:
        return (f"The SKILL.md frontmatter is missing required key(s): "
                f"{', '.join(missing)} — the skill loader would reject this file.")
    return None


def _resolve_write_path(request: Request, skill_name: str, target: str) -> Path:
    repo_root = request.app.state.repo_root
    if target == "SKILL.md":
        root = repo_root / ".claude" / "skills"
        path = root / skill_name / "SKILL.md"
    elif target == "kickoff_template":
        stage_id = stage_id_by_skill(request.app.state.stage_defs).get(skill_name)
        if stage_id is None:
            raise _reject(
                request, skill_name,
                (f"Skill {skill_name!r} is not bound to a pipeline stage, so it has "
                 f"no kickoff template to save."),
            )
        path = stage_template_path(repo_root, stage_id)
        root = path.parent
    else:
        raise _reject(
            request, skill_name,
            f"Unrecognized save target {target!r}; expected one of {VALID_TARGETS}.",
        )
    if not path.resolve().is_relative_to(root.resolve()):
        raise _reject(request, skill_name, "Refusing to write outside the skill tree.")
    return path


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
def skill_detail(request: Request, skill_name: str, warning: str | None = None):
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
    skill_md_exists = skill_md_path.is_file()
    skill_md_content = skill_md_path.read_text(encoding="utf-8") if skill_md_exists else ""
    if not skill_md_exists:
        obs.log("skill_editor.skill_md_missing", level="warning",
                skill=skill_name, path=str(skill_md_path))

    stage_id = stage_id_by_skill(request.app.state.stage_defs).get(skill_name)
    template_path = stage_template_path(repo_root, stage_id) if stage_id else None
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
            "skill_md_missing": not skill_md_exists,
            "stage_id": stage_id,
            "kickoff_template_applies": stage_id is not None,
            "kickoff_template_missing": kickoff_template_missing,
            "kickoff_template_content": kickoff_template_content,
            "active_nav": "skills",
            "cli_available": request.app.state.cli_available,
            "warning": warning,
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

    # Resolve and validate the target path first; raises 400 if invalid or out of bounds.
    path = _resolve_write_path(request, skill_name, target)

    # Normalize line endings: HTML form submission uses CRLF; write_text(newline=None)
    # translates every \n to os.linesep, producing \r\r\n on Windows (A-55).
    normalized = _normalized(content)

    # Validate content before writing; raises 400 if blank.
    problem = _validate_content(target, normalized)
    if problem is not None:
        raise _reject(request, skill_name, problem)

    # Write the file.
    path.write_text(normalized, encoding="utf-8", newline="")

    # Commit both SKILL.md and kickoff_template saves (A-52).
    stage_id = None
    if target == "kickoff_template":
        stage_id = stage_id_by_skill(request.app.state.stage_defs).get(skill_name)
    label = skill_name if target == "SKILL.md" else f"{skill_name} kickoff ({stage_id})"
    result = git_helper.commit_skill_edit(repo_root, path, label)

    # Record the save event (file write succeeded regardless of commit outcome)
    obs.record_event(
        request.app.state.conn, kind="skill_editor.saved", severity="info",
        source="routes.skills", message=f"{skill_name}: saved",
        detail={
            "skill": skill_name,
            "target": target,
            "path": path.relative_to(repo_root).as_posix(),
            "result_status": result.status,
            "result_branch": result.branch,
            "result_commit_sha": result.commit_sha,
        },
    )

    if result.ok:
        return RedirectResponse(url=f"/skills/{skill_name}", status_code=303)

    # Record the commit failure -- unless it was a deliberate policy refusal
    # (protected-branch guard), which is a warning, not an error (Finding 5).
    if result.status == "refused_protected_branch":
        obs.record_event(
            request.app.state.conn, kind="skill_editor.commit_refused", severity="warning",
            source="routes.skills", message=f"{skill_name}: {result.detail}",
            detail={"skill": skill_name, "target": target, "result_status": result.status},
        )
    else:
        obs.record_event(
            request.app.state.conn, kind="skill_editor.commit_failed", severity="error",
            source="routes.skills", message=f"{skill_name}: {result.detail}",
            detail={"skill": skill_name, "target": target, "result_status": result.status},
        )

    warning = f"Saved, but not committed: {result.detail}"
    return RedirectResponse(
        url=f"/skills/{skill_name}?warning={quote(warning)}", status_code=303,
    )
