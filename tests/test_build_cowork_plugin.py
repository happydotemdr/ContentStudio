import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build-cowork-plugin.sh"
EXCLUDED = {"rgs-grounding", "rgs-pairing-review"}


def _skill_dirs() -> set[str]:
    return {p.name for p in (REPO / ".claude" / "skills").iterdir() if p.is_dir()}


# Final-review finding #5. The build script's `HERE` resolves from the
# SCRIPT's own on-disk location (`$(dirname "${BASH_SOURCE[0]}")/..`), not
# from `cwd` -- so copying the whole relevant subtree (`.claude/skills/` and
# `scripts/`, including the build script and cowork_plugin_lock.py
# themselves) into an isolated `tmp_path` and invoking the COPIED script
# works correctly without any `cwd` trick, and never touches the real repo's
# git-tracked scripts/cowork-plugin.lock.json -- the file
# test_the_lock_file_matches_the_current_skills_tree exists to guard.
#
# The build script also shells out to `git rev-list --count HEAD` and
# `git rev-parse --short HEAD` to derive the plugin version; `tmp_path` is
# not a git repo, so a stub `git` shim (prepended onto PATH for the
# subprocess only) answers those two calls without needing a real repo.
_FAKE_GIT_SH = """#!/usr/bin/env bash
case "$1" in
  rev-list) echo 42 ;;
  rev-parse) echo abc1234 ;;
  *) exit 1 ;;
esac
"""


def _isolated_repo_copy(tmp_path: Path) -> Path:
    """A tmp_path tree carrying only what build-cowork-plugin.sh reads:
    .claude/skills/ and scripts/ (script + lock helper). Running the build
    against this copy, with cwd=this copy, can never write to the real
    repo's tracked lock file."""
    root = tmp_path / "repo_copy"
    shutil.copytree(REPO / ".claude" / "skills", root / ".claude" / "skills")
    shutil.copytree(REPO / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    return root


def _fake_git_path(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    git_stub = bin_dir / "git"
    git_stub.write_text(_FAKE_GIT_SH, encoding="utf-8")
    git_stub.chmod(0o755)
    return bin_dir


def _run_isolated_build(tmp_path: Path) -> tuple[subprocess.CompletedProcess, Path]:
    bash_path = shutil.which("bash")
    assert bash_path is not None, "bash not found on PATH (expected on this project's target platform)"
    repo_copy = _isolated_repo_copy(tmp_path)
    fakebin = _fake_git_path(tmp_path)
    env = dict(os.environ)
    env["PATH"] = f"{fakebin}{os.pathsep}{env.get('PATH', '')}"
    result = subprocess.run(
        [bash_path, str(repo_copy / "scripts" / "build-cowork-plugin.sh")],
        cwd=repo_copy, capture_output=True, encoding="utf-8", errors="replace", env=env,
    )
    return result, repo_copy


def test_the_script_never_calls_the_pipeline_seven_skills():
    """C-101. Three strings said "Seven" while eleven skills shipped."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"\bseven\b", source, re.IGNORECASE), (
        "build-cowork-plugin.sh still says 'seven'; it ships eight pipeline skills "
        "plus three tool specialists"
    )


def test_the_bundled_readme_chain_names_shorts_styleboard():
    """shorts-styleboard produces the world lock Gate C reads. A chain that
    omits it documents a pipeline whose gate has no input."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "shorts-styleboard" in source


def test_the_expected_shipped_roster_is_exactly_the_tree_minus_the_rgs_skills():
    """Anti-tautology: derived from the real directory, not a literal count."""
    shipped = _skill_dirs() - EXCLUDED
    assert len(shipped) == 11
    assert "shorts-styleboard" in shipped
    assert EXCLUDED & shipped == set()


LOCK = REPO / "scripts" / "cowork-plugin.lock.json"


def test_the_lock_file_matches_the_current_skills_tree():
    """C-103 fault test. Editing a skill without rebuilding the plugin used to
    be undetectable. Now it fails here, with the one command that fixes it."""
    from scripts.cowork_plugin_lock import compute_stamp

    assert LOCK.exists(), "run: bash scripts/build-cowork-plugin.sh"
    recorded = json.loads(LOCK.read_text(encoding="utf-8"))
    assert recorded == compute_stamp(REPO), (
        "the shipped plugin is stale relative to .claude/skills/ -- "
        "run: bash scripts/build-cowork-plugin.sh"
    )


def test_a_changed_skill_changes_the_stamp(tmp_path):
    """C-103 distinguishability test. A stamp that did not move when a skill
    moved would be a stamp that certifies nothing."""
    from scripts.cowork_plugin_lock import compute_stamp

    fake = tmp_path / ".claude" / "skills" / "demo"
    fake.mkdir(parents=True)
    (fake / "SKILL.md").write_text("one\n", encoding="utf-8")
    before = compute_stamp(tmp_path)
    (fake / "SKILL.md").write_text("two\n", encoding="utf-8")
    assert compute_stamp(tmp_path) != before


def test_the_manifest_version_is_derived_not_pinned():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"version": "0.1.0"' not in source
    assert "git rev-list" in source or "date -u" in source


def test_the_build_asserts_the_copied_roster_before_packaging():
    """C-102 fault test, at the source level: the count must be COMPARED, not
    merely printed. A build that copied nine skills must fail, not congratulate
    itself."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "cowork_plugin_lock.py" in source
    assert "--check" in source or "--write" in source


def test_the_written_manifest_is_validated_as_json():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "json.load" in source or "json.tool" in source


@pytest.mark.allow_subprocess
def test_the_build_produces_a_valid_manifest_and_the_expected_roster(tmp_path):
    """C-102 surfacing test: run the actual script and inspect what it wrote.

    Runs against an isolated copy (see _run_isolated_build), not the real
    repo -- the build script's `cowork_plugin_lock.py --write` step rewrites
    scripts/cowork-plugin.lock.json as a side effect, and running it against
    the real repo would silently "heal" that git-tracked staleness stamp,
    defeating test_the_lock_file_matches_the_current_skills_tree."""
    result, repo_copy = _run_isolated_build(tmp_path)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(
        (repo_copy / "cowork-plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "content-studio"
    assert manifest["version"] != "0.1.0"
    shipped = {p.name for p in (repo_copy / "cowork-plugin" / "skills").iterdir() if p.is_dir()}
    assert shipped == _skill_dirs() - EXCLUDED


def test_junk_is_pruned_before_packaging_not_during():
    """C-104. Two branches with two different exclusion rules produce two
    different artifacts from one tree. Prune once, up front, and both branches
    archive the same thing."""
    source = SCRIPT.read_text(encoding="utf-8")
    prune_at = source.index("find") if "find" in source else -1
    zip_at = source.index("Compress-Archive")
    assert re.search(r'-name\s+["\']?\.DS_Store', source), (
        "no pre-packaging prune step; the two archive branches still disagree"
    )
    assert 0 < prune_at < zip_at
    assert '-x "*.DS_Store"' not in source, (
        "the zip branch still carries a branch-local exclusion -- the rule must "
        "live in one place, before either branch runs"
    )


@pytest.mark.allow_subprocess
def test_the_packaged_tree_contains_no_junk_files(tmp_path):
    """Runs against an isolated copy for the same reason as
    test_the_build_produces_a_valid_manifest_and_the_expected_roster above --
    see _run_isolated_build's docstring/comment."""
    result, repo_copy = _run_isolated_build(tmp_path)
    assert result.returncode == 0, result.stderr
    junk = [p for p in (repo_copy / "cowork-plugin").rglob("*")
            if p.name in (".DS_Store", "Thumbs.db") or p.suffix == ".pyc"]
    assert junk == []


def test_a_locally_built_artifact_is_not_older_than_the_skills_it_ships():
    """The mtime half, for the machine that actually has the artifact. dist/ is
    git-ignored, so this is a no-op in CI and a real check locally -- stated
    plainly rather than dressed up as universal coverage."""
    artifact = REPO / "dist" / "content-studio.plugin"
    if not artifact.exists():
        pytest.skip("no local build artifact; the lock-file check above is the CI gate")
    newest = max(
        p.stat().st_mtime for p in (REPO / ".claude" / "skills").rglob("*") if p.is_file()
    )
    assert artifact.stat().st_mtime >= newest, "run: bash scripts/build-cowork-plugin.sh"
