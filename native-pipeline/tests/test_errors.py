from native_pipeline.errors import (
    BedDurationMismatchError,
    ChunkDurationTooShortError,
    IterationBudgetExceededError,
    ShotSegmentMismatchError,
)


def test_shot_segment_mismatch_error_is_a_value_error():
    assert issubclass(ShotSegmentMismatchError, ValueError)


def test_chunk_duration_too_short_error_is_a_value_error():
    assert issubclass(ChunkDurationTooShortError, ValueError)


def test_bed_duration_mismatch_error_is_a_runtime_error():
    assert issubclass(BedDurationMismatchError, RuntimeError)


def test_iteration_budget_exceeded_error_is_a_runtime_error():
    assert issubclass(IterationBudgetExceededError, RuntimeError)
