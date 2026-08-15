import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "build-cowork-plugin.sh"
EXCLUDED = {"rgs-grounding", "rgs-pairing-review"}


def _skill_dirs() -> set[str]:
    return {p.name for p in (REPO / ".claude" / "skills").iterdir() if p.is_dir()}


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
    """C-102 surfacing test: run the actual script and inspect what it wrote."""
    result = subprocess.run(
        ["bash", str(SCRIPT)], cwd=REPO, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, result.stderr
    manifest = json.loads(
        (REPO / "cowork-plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "content-studio"
    assert manifest["version"] != "0.1.0"
    shipped = {p.name for p in (REPO / "cowork-plugin" / "skills").iterdir() if p.is_dir()}
    assert shipped == _skill_dirs() - EXCLUDED


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
