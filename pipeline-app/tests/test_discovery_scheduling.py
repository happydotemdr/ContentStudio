import datetime as _dt

import pytest

from pipeline_app.discovery_scheduling import ScheduleConfigError, is_due


def test_not_due_before_time_of_day():
    now = _dt.datetime(2026, 7, 30, 5, 45, tzinfo=_dt.timezone.utc)  # 00:45 America/Chicago (CDT, UTC-5)
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date=None) is False


def test_due_at_or_after_time_of_day_when_not_yet_run_today():
    now = _dt.datetime(2026, 7, 30, 11, 0, tzinfo=_dt.timezone.utc)  # 06:00 America/Chicago
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date=None) is True


def test_not_due_again_same_day_after_already_run():
    now = _dt.datetime(2026, 7, 30, 12, 0, tzinfo=_dt.timezone.utc)  # 07:00 America/Chicago
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date="2026-07-30") is False


def test_catch_up_fires_once_after_multiple_missed_days():
    now = _dt.datetime(2026, 8, 2, 19, 0, tzinfo=_dt.timezone.utc)  # afternoon, several days later
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date="2026-07-28") is True


def test_due_again_next_day_after_time_of_day():
    now = _dt.datetime(2026, 7, 31, 11, 30, tzinfo=_dt.timezone.utc)  # 06:30 America/Chicago
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date="2026-07-30") is True


def test_is_due_rejects_an_unknown_timezone_as_a_schedule_config_error():
    now = _dt.datetime(2026, 7, 30, 11, 0, tzinfo=_dt.timezone.utc)
    with pytest.raises(ScheduleConfigError):
        is_due(now, "America/Chicgo", "06:00", last_scheduled_run_date=None)


def test_is_due_rejects_a_non_hhmm_time_of_day():
    now = _dt.datetime(2026, 7, 30, 11, 0, tzinfo=_dt.timezone.utc)
    with pytest.raises(ScheduleConfigError):
        is_due(now, "America/Chicago", "6am", last_scheduled_run_date=None)
