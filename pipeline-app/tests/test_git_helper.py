import subprocess
from pathlib import Path

import pytest

from pipeline_app.git_helper import commit_skill_edit

pytestmark = pytest.mark.allow_subprocess


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-b", "skill-edits"], cwd=tmp_path, check=True,
                   capture_output=True, encoding="utf-8", errors="replace")
    for key, value in (("user.email", "test@example.com"), ("user.name", "Test User")):
        subprocess.run(["git", "config", key, value], cwd=tmp_path, check=True,
                       capture_output=True, encoding="utf-8", errors="replace")
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=tmp_path, check=True,
                   capture_output=True, encoding="utf-8", errors="replace")
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
    assert len(log) == 2  # the second call created no new commit (init + 1 skill edit)


def test_commit_is_scoped_to_the_file_and_leaves_unrelated_staged_work_alone(repo: Path):
    """A-53/D-49: `git commit -m msg` carried no pathspec, so an operator's
    unrelated staged work was swept into a "skill edit" commit."""
    unrelated = repo / "unrelated.txt"
    unrelated.write_text("operator work in progress\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True, capture_output=True)

    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited content\n", encoding="utf-8")

    result = commit_skill_edit(repo, skill_file, "shorts-ideation", now="2026-07-25")

    assert result.status == "committed"
    files = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", "HEAD"], cwd=repo,
        check=True, capture_output=True, encoding="utf-8", errors="replace",
    ).stdout.split()
    assert files == [".claude/skills/shorts-ideation/SKILL.md"]
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=repo,
        check=True, capture_output=True, encoding="utf-8", errors="replace",
    ).stdout.split()
    assert staged == ["unrelated.txt"]      # still the operator's, uncommitted


def test_unchanged_content_is_a_no_op_even_with_unrelated_staged_work(repo: Path):
    """The index-wide `git diff --cached --quiet` reported work to commit
    because of the operator's staging, producing a "skill edit" commit
    containing no skill edit (A-53)."""
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("same content\n", encoding="utf-8")
    assert commit_skill_edit(repo, skill_file, "shorts-ideation").status == "committed"

    (repo / "unrelated.txt").write_text("wip\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=repo, check=True, capture_output=True)

    second = commit_skill_edit(repo, skill_file, "shorts-ideation")

    assert second.status == "no_change"          # distinguishable from "committed"
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, check=True,
                         capture_output=True, encoding="utf-8", errors="replace").stdout
    assert log.count("skill edit") == 1


def test_every_git_call_carries_a_timeout(repo: Path, monkeypatch):
    """All three subprocess.run calls used capture_output with no timeout, so
    a git that prompts (GPG passphrase, an interactive hook) blocked forever
    with its prompt swallowed and wedged the request thread (D-50)."""
    seen = []
    real = subprocess.run

    def spy(args, **kwargs):
        if args and args[0] == "git":
            seen.append(kwargs.get("timeout"))
        return real(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited\n", encoding="utf-8")

    commit_skill_edit(repo, skill_file, "shorts-ideation")

    assert seen and all(t is not None and t > 0 for t in seen)


def test_a_hanging_git_reports_failure_rather_than_hanging(repo: Path, monkeypatch):
    def boom(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(subprocess, "run", boom)
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited\n", encoding="utf-8")

    result = commit_skill_edit(repo, skill_file, "shorts-ideation")

    assert result.status == "failed"
    assert "timed out" in result.detail
    assert result.ok is False              # distinguishable from no_change, which is also
                                           # "no commit was made" but is NOT a failure


def test_git_missing_from_path_reports_failure_rather_than_raising(repo: Path, monkeypatch):
    def boom(args, **kwargs):
        raise FileNotFoundError(2, "The system cannot find the file specified", "git")

    monkeypatch.setattr(subprocess, "run", boom)
    skill_file = repo / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("edited\n", encoding="utf-8")

    assert commit_skill_edit(repo, skill_file, "shorts-ideation").status == "failed"
