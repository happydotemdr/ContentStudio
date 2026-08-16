import datetime
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pipeline_app import obs

GIT_TIMEOUT_SECONDS = 15


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


def commit_skill_edit(repo_root: Path, file_path: Path, skill_name: str,
                      now: str | None = None) -> CommitResult:
    now = now or datetime.date.today().isoformat()
    rel_path = file_path.relative_to(repo_root).as_posix()
    message = f"skill edit: {skill_name} via pipeline-app, {now}"

    try:
        add = _git(repo_root, ["add", "--", rel_path])
        if add.returncode != 0:
            return CommitResult(status="failed", detail=(add.stderr or add.stdout).strip())
        # `-- rel_path` on BOTH commands, so the emptiness check and the commit
        # describe the same single file (A-53/D-49).
        diff = _git(repo_root, ["diff", "--cached", "--quiet", "--", rel_path])
        if diff.returncode == 0:
            return CommitResult(status="no_change")
        commit = _git(repo_root, ["commit", "-m", message, "--", rel_path])
        if commit.returncode != 0:
            detail = (commit.stderr or commit.stdout).strip()
            obs.log("git.commit_failed", level="error", path=rel_path, detail=detail)
            return CommitResult(status="failed", detail=detail)
        sha = _git(repo_root, ["rev-parse", "HEAD"]).stdout.strip() or None
        return CommitResult(status="committed", commit_sha=sha)
    except subprocess.TimeoutExpired:
        detail = f"git timed out after {GIT_TIMEOUT_SECONDS}s"
        obs.log("git.timeout", level="error", path=rel_path, detail=detail)
        return CommitResult(status="failed", detail=detail)
    except OSError as exc:                  # git absent from PATH, or unreadable cwd
        obs.log("git.unavailable", level="error", path=rel_path, detail=str(exc))
        return CommitResult(status="failed", detail=str(exc))
