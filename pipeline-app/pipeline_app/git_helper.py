import datetime
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline_app import obs

GIT_TIMEOUT_SECONDS = 15
PROTECTED_BRANCHES = frozenset({"main", "master"})
APP_COMMITTER_NAME = "pipeline-app"
APP_COMMITTER_EMAIL = "noreply@localhost"


@dataclass(frozen=True)
class CommitResult:
    """Why the route needs this: the save already wrote the file by the time
    git runs, so "did the commit happen" is a separate outcome from "did the
    save happen" and must be reported separately (A-54)."""
    status: str          # committed | no_change | refused_protected_branch | failed
    branch: str | None = None
    commit_sha: str | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in ("committed", "no_change")


def _git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True,
        encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT_SECONDS,
    )


def current_branch(repo_root: Path) -> str | None:
    # symbolic-ref, not rev-parse --abbrev-ref: it also answers correctly on
    # an unborn branch (a freshly-init'd repo), where rev-parse errors.
    proc = _git(repo_root, ["symbolic-ref", "--quiet", "--short", "HEAD"])
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def commit_skill_edit(repo_root: Path, file_path: Path, skill_name: str,
                      now: str | None = None) -> CommitResult:
    now = now or datetime.date.today().isoformat()
    rel_path = file_path.relative_to(repo_root).as_posix()

    try:
        branch = current_branch(repo_root)
        if branch in PROTECTED_BRANCHES:
            detail = (f"refusing to commit to protected branch {branch!r}; the file was saved "
                      f"but is uncommitted")
            obs.log("git.commit_refused_protected_branch", level="warning",
                    branch=branch, path=rel_path)
            return CommitResult(status="refused_protected_branch", branch=branch, detail=detail)

        message = f"skill edit: {skill_name} via pipeline-app, {now}"
        add = _git(repo_root, ["add", "--", rel_path])
        if add.returncode != 0:
            return CommitResult(status="failed", detail=(add.stderr or add.stdout).strip())
        # `-- rel_path` on BOTH commands, so the emptiness check and the commit
        # describe the same single file (A-53/D-49).
        diff = _git(repo_root, ["diff", "--cached", "--quiet", "--", rel_path])
        if diff.returncode == 0:
            return CommitResult(status="no_change", branch=branch)
        commit = _git(repo_root, [
            "-c", f"user.name={APP_COMMITTER_NAME}",
            "-c", f"user.email={APP_COMMITTER_EMAIL}",
            "commit", "-m", message, "--", rel_path,
        ])
        if commit.returncode != 0:
            detail = (commit.stderr or commit.stdout).strip()
            obs.log("git.commit_failed", level="error", path=rel_path, detail=detail)
            return CommitResult(status="failed", branch=branch, detail=detail)
        sha = _git(repo_root, ["rev-parse", "HEAD"]).stdout.strip() or None
        return CommitResult(status="committed", branch=branch, commit_sha=sha)
    except subprocess.TimeoutExpired:
        detail = f"git timed out after {GIT_TIMEOUT_SECONDS}s"
        obs.log("git.timeout", level="error", path=rel_path, detail=detail)
        return CommitResult(status="failed", detail=detail)
    except OSError as exc:                  # git absent from PATH, or unreadable cwd
        obs.log("git.unavailable", level="error", path=rel_path, detail=str(exc))
        return CommitResult(status="failed", detail=str(exc))
