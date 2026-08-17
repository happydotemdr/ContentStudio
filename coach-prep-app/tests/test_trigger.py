# coach-prep-app/tests/test_trigger.py
from __future__ import annotations

import datetime as dt

from coach_prep_app import trigger

TZ = "America/Chicago"


def _utc(y, m, d, h, minute=0):
    return dt.datetime(y, m, d, h, minute, tzinfo=dt.timezone.utc)


def test_not_due_before_seven_am_the_day_before(conn):
    meeting_start = _utc(2026, 8, 20, 15, 0)  # Aug 20, 10am Chicago
    now = _utc(2026, 8, 19, 11, 0)  # Aug 19, 6am Chicago -- before 7am
    assert trigger.is_due(conn, "sean", "evt1", meeting_start, now, TZ, 7) is False


def test_due_at_or_after_seven_am_the_day_before(conn):
    meeting_start = _utc(2026, 8, 20, 15, 0)
    now = _utc(2026, 8, 19, 12, 30)  # Aug 19, 7:30am Chicago
    assert trigger.is_due(conn, "sean", "evt1", meeting_start, now, TZ, 7) is True


def test_not_due_after_watermark_already_set(conn):
    meeting_start = _utc(2026, 8, 20, 15, 0)
    now = _utc(2026, 8, 19, 12, 30)
    trigger.mark_done(conn, "sean", "evt1", now.isoformat())
    assert trigger.is_due(conn, "sean", "evt1", meeting_start, now, TZ, 7) is False


def test_a_different_event_instance_is_independently_due(conn):
    now = _utc(2026, 8, 19, 12, 30)
    trigger.mark_done(conn, "sean", "evt1", now.isoformat())
    # Same day-before/ready-hour window as evt1's meeting (Aug 20) -- this
    # test is about watermark independence between instance ids, not about
    # a second due-window computation, so it must land inside the window
    # (brief had this at Aug 27, 8 days outside the window relative to
    # `now`; corrected here -- see task-14-report.md for the discrepancy).
    meeting_start_2 = _utc(2026, 8, 20, 15, 0)
    assert trigger.is_due(conn, "sean", "evt2", meeting_start_2, now, TZ, 7) is True


def test_recurring_events_instance_ids_are_independent_watermarks(conn):
    """A recurring weekly booking has a distinct instance ID per occurrence
    even though it shares a recurringEventId -- the watermark must be keyed
    on the instance ID (what this function receives), never the series ID,
    or every occurrence after the first would be silently suppressed."""
    now = _utc(2026, 8, 19, 12, 30)
    trigger.mark_done(conn, "sean", "series1_20260820T150000Z", now.isoformat())
    now_next_week = _utc(2026, 8, 26, 12, 30)
    meeting_next_week = _utc(2026, 8, 27, 15, 0)
    assert trigger.is_due(
        conn, "sean", "series1_20260827T150000Z", meeting_next_week, now_next_week, TZ, 7
    ) is True


def test_day_before_computation_across_dst_fallback_resolves_to_correct_wall_clock_seven_am(conn):
    """2026-11-01 (Sunday) is the US DST fall-back date for America/Chicago:
    clocks move from CDT (UTC-5) to CST (UTC-6) at 2am local. A meeting on
    the Monday after it (2026-11-02) has its "day before" ready time land
    on the transition date itself -- confirm is_due still resolves to
    07:00 wall-clock Chicago time (13:00 UTC, CST) rather than drifting an
    hour off from a naively-applied fixed UTC offset."""
    meeting_start = _utc(2026, 11, 2, 21, 0)  # Nov 2, 3pm Chicago (CST, UTC-6)
    not_yet = _utc(2026, 11, 1, 12, 59)  # Nov 1, 6:59am CST -- one minute before ready
    ready = _utc(2026, 11, 1, 13, 0)  # Nov 1, 7:00am CST -- exactly ready
    assert trigger.is_due(conn, "sean", "evt-dst", meeting_start, not_yet, TZ, 7) is False
    assert trigger.is_due(conn, "sean", "evt-dst", meeting_start, ready, TZ, 7) is True
