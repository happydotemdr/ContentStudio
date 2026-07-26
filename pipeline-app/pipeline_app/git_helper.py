import datetime
import subprocess
from pathlib import Path


def commit_skill_edit(repo_root: Path, file_path: Path, skill_name: str, now: str | None = None) -> None:
    now = now or datetime.date.today().isoformat()
    rel_path = file_path.relative_to(repo_root)
    message = f"skill edit: {skill_name} via pipeline-app, {now}"
    subprocess.run(["git", "add", str(rel_path)], cwd=repo_root, check=True, capture_output=True)
    # `git commit` exits nonzero when there's nothing staged (re-saving
    # byte-identical content) — that must be a silent no-op, not a crash, so
    # this checks for staged changes first rather than blindly using
    # check=True on the commit itself.
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=repo_root, capture_output=True
    )
    if diff.returncode == 0:
        return  # nothing staged — content was unchanged
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True, capture_output=True)
