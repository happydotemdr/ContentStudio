import datetime as _dt

import pytest

from pipeline_app.discovery_scheduling import ScheduleConfigError, encode_watermark, is_due


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


def test_a_timezone_change_cannot_fire_a_second_run_the_same_day():
    """B-48: last_scheduled_run_date was a bare local date computed under the
    timezone configured at WRITE time and compared under the one configured at
    READ time. Changing the setting made today's date differ from the stored
    string while the same day was still in progress -- a full second run, a
    duplicate billable Bright Data pass for every handle."""
    ran_at = _dt.datetime(2026, 7, 30, 12, 0, tzinfo=_dt.timezone.utc)   # 07:00 Chicago
    watermark = encode_watermark("2026-07-30", "America/Chicago", ran_at.isoformat(timespec="seconds"))
    two_hours_later = _dt.datetime(2026, 7, 30, 14, 0, tzinfo=_dt.timezone.utc)
    assert is_due(two_hours_later, "Pacific/Auckland", "06:00", watermark) is False


def test_a_legacy_bare_date_watermark_still_works():
    now = _dt.datetime(2026, 7, 30, 12, 0, tzinfo=_dt.timezone.utc)
    assert is_due(now, "America/Chicago", "06:00", "2026-07-30") is False


def test_the_next_day_still_fires_after_the_minimum_interval():
    ran_at = _dt.datetime(2026, 7, 30, 11, 0, tzinfo=_dt.timezone.utc)
    watermark = encode_watermark("2026-07-30", "America/Chicago", ran_at.isoformat(timespec="seconds"))
    tomorrow = _dt.datetime(2026, 7, 31, 11, 30, tzinfo=_dt.timezone.utc)
    assert is_due(tomorrow, "America/Chicago", "06:00", watermark) is True
