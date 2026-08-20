import pytest

from native_pipeline.errors import IterationBudgetExceededError
from native_pipeline.iteration import IterationRecord


def test_record_raises_iteration_budget_exceeded_on_third_attempt():
    record = IterationRecord(track="vo")
    record.record({"stability": 0.4}, {"lufs": -22.0})
    record.record({"stability": 0.6}, {"lufs": -18.0})

    with pytest.raises(IterationBudgetExceededError, match="vo"):
        record.record({"stability": 0.8}, {"lufs": -15.0})


def test_compare_reports_directionally_consistent_delta():
    record = IterationRecord(track="vo")
    record.record({"stability": 0.4}, {"lufs": -22.0})
    record.record({"stability": 0.6}, {"lufs": -18.0})

    result = record.compare("lufs", expected_direction="up")

    assert result["directionally_consistent"] is True
    assert result["delta"] == pytest.approx(4.0)
    assert result["settings_diff"] == {"stability": (0.4, 0.6)}


def test_compare_reports_contradicted_direction_without_raising():
    record = IterationRecord(track="vo")
    record.record({"stability": 0.4}, {"lufs": -22.0})
    record.record({"stability": 0.6}, {"lufs": -25.0})  # moved the wrong way

    result = record.compare("lufs", expected_direction="up")

    assert result["directionally_consistent"] is False


def test_compare_raises_value_error_with_fewer_than_two_attempts():
    record = IterationRecord(track="vo")
    record.record({"stability": 0.4}, {"lufs": -22.0})

    with pytest.raises(ValueError, match="need 2 attempts"):
        record.compare("lufs", expected_direction="up")
