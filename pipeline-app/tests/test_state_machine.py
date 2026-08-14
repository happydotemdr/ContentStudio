from pipeline_app.pipeline_config import StageDef
from pipeline_app.state_machine import (
    StageStatus,
    compute_initial_status,
    is_stale,
    stages_to_relock,
    stages_to_unlock,
)


def test_stage_with_no_dependencies_starts_ready():
    assert compute_initial_status([]) == StageStatus.READY


def test_stage_with_dependencies_starts_locked():
    assert compute_initial_status(["ideation"]) == StageStatus.LOCKED


def test_stages_to_unlock_finds_stage_whose_deps_are_all_approved():
    stages = [
        StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01"),
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=["ideation"]),
    ]
    unlocked = stages_to_unlock(stages, approved_stage_ids={"ideation"})
    assert unlocked == ["scripting"]


def test_stages_to_unlock_respects_parallel_pair_needing_both_deps():
    stages = [
        StageDef(id="voiceover", skill="voiceover-brief", dir_prefix="03", depends_on=["scripting"]),
        StageDef(id="visual", skill="visual-prompts", dir_prefix="03", depends_on=["scripting"]),
        StageDef(id="assembly", skill="shorts-assembly", dir_prefix="04", depends_on=["voiceover", "visual"]),
    ]
    unlocked = stages_to_unlock(stages, approved_stage_ids={"scripting", "voiceover"})
    assert "assembly" not in unlocked  # visual not yet approved
    unlocked_both = stages_to_unlock(stages, approved_stage_ids={"scripting", "voiceover", "visual"})
    assert "assembly" in unlocked_both


def test_is_stale_when_hash_no_longer_matches():
    recorded = [{"path": "../01-ideation/artifact.v1.md", "sha256": "abc123"}]
    current_hashes = {"../01-ideation/artifact.v1.md": "different-hash"}
    assert is_stale(recorded, current_hashes) is True


def test_is_stale_false_when_hash_matches():
    recorded = [{"path": "../01-ideation/artifact.v1.md", "sha256": "abc123"}]
    current_hashes = {"../01-ideation/artifact.v1.md": "abc123"}
    assert is_stale(recorded, current_hashes) is False


def test_is_stale_false_for_empty_dependencies():
    assert is_stale([], {}) is False


def test_is_stale_true_when_dependency_missing_from_current_hashes():
    recorded = [{"path": "missing.md", "sha256": "abc123"}]
    assert is_stale(recorded, {}) is True


def test_stages_to_relock_finds_a_dependent_whose_dependency_left_approved():
    """A-45: stages_to_unlock is a one-way ratchet and LOCKED is never passed to
    update_stage_status anywhere in the app. Approve scripting (unlocking
    styleboard and voiceover), then hand-edit scripting -- the dependents stay
    ready, runnable and approvable on a dependency that is no longer approved."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
    ]
    assert stages_to_relock(stages, approved_stage_ids=set()) == ["styleboard"]
    assert stages_to_relock(stages, approved_stage_ids={"scripting"}) == []


def test_stages_to_relock_is_the_exact_inverse_of_stages_to_unlock():
    """The DAG invariant must hold in both directions or `locked` records a
    high-water mark rather than the current topology."""
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="voiceover", skill="voiceover-brief", dir_prefix="03",
                 depends_on=["scripting"]),
        StageDef(id="visual", skill="visual-prompts", dir_prefix="03",
                 depends_on=["scripting"]),
        StageDef(id="assembly", skill="shorts-assembly", dir_prefix="04",
                 depends_on=["voiceover", "visual"]),
    ]
    for approved in ({"scripting"}, {"scripting", "voiceover"}, set()):
        unlockable = set(stages_to_unlock(stages, approved))
        relockable = set(stages_to_relock(stages, approved))
        assert not (unlockable & relockable)


def test_stages_to_relock_never_relocks_an_approved_stage():
    stages = [
        StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02"),
        StageDef(id="styleboard", skill="shorts-styleboard", dir_prefix="02b",
                 depends_on=["scripting"]),
    ]
    assert stages_to_relock(stages, approved_stage_ids={"styleboard"}) == []
