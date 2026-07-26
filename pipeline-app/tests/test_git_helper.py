import subprocess
from pathlib import Path

import pytest

from pipeline_app.git_helper import commit_skill_edit


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    return tmp_path


def test_commit_skill_edit_creates_a_commit(repo: Path):
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited content", encoding="utf-8")

    commit_skill_edit(repo, skill_file, "shorts-ideation", now="2026-07-25")

    log = subprocess.run(
        ["git", "log", "--oneline", "-1"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
    assert "shorts-ideation" in log
    assert "2026-07-25" in log


def test_commit_skill_edit_is_a_no_op_when_content_is_unchanged(repo: Path):
    """Re-saving byte-identical content from the editor (no textarea change,
    just hitting Save again) must not crash — `git commit` with nothing
    staged exits nonzero, and a naive check=True would raise CalledProcessError
    and 500 the skill-editor route."""
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("same content", encoding="utf-8")
    commit_skill_edit(repo, skill_file, "shorts-ideation", now="2026-07-25")

    commit_skill_edit(repo, skill_file, "shorts-ideation", now="2026-07-25")  # no-op, must not raise

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert len(log) == 1  # the second call created no new commit
