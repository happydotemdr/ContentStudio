from enum import Enum

from pipeline_app.pipeline_config import StageDef


class StageStatus(str, Enum):
    LOCKED = "locked"
    READY = "ready"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    STALE = "stale"
    NO_ARTIFACT = "no_artifact"


def compute_initial_status(depends_on: list[str]) -> StageStatus:
    return StageStatus.READY if not depends_on else StageStatus.LOCKED


def is_locked_or_running(status: str) -> bool:
    return status in (StageStatus.LOCKED.value, StageStatus.RUNNING.value)


def stages_to_unlock(all_stage_defs: list[StageDef], approved_stage_ids: set[str]) -> list[str]:
    unlocked = []
    for stage in all_stage_defs:
        if stage.id in approved_stage_ids:
            continue
        if stage.depends_on and all(dep in approved_stage_ids for dep in stage.depends_on):
            unlocked.append(stage.id)
    return unlocked


def stages_to_relock(all_stage_defs: list[StageDef], approved_stage_ids: set[str]) -> list[str]:
    """The inverse of stages_to_unlock: dependents whose dependencies are no
    longer all approved (A-45).

    An already-approved stage is never relocked -- it has an artifact of its
    own and the right treatment is staleness, not a lock that would hide it.
    """
    relock = []
    for stage in all_stage_defs:
        if stage.id in approved_stage_ids:
            continue
        if stage.depends_on and not all(dep in approved_stage_ids for dep in stage.depends_on):
            relock.append(stage.id)
    return relock


def is_stale(recorded_depends_on: list[dict], current_hashes: dict[str, str]) -> bool:
    for dep in recorded_depends_on:
        path = dep["path"]
        recorded_hash = dep["sha256"]
        if current_hashes.get(path) != recorded_hash:
            return True
    return False
