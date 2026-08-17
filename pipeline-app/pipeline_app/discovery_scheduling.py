"""Pure due-check for the discovery cron -- see the design spec's
'Scheduling' section for the catch-up semantics this implements. No DB or
network access: run_discovery_cron.py (Task 14) reads discovery_settings and
passes its fields in."""
from __future__ import annotations

import datetime as _dt
import re
from zoneinfo import ZoneInfo


class ScheduleConfigError(ValueError):
    """The stored schedule settings cannot be evaluated. Raised in place of
    ZoneInfoNotFoundError / ValueError so the caller can report a wedged
    scheduler as its own terminal state (B-47) instead of dying with a
    traceback into a console Task Scheduler discards (B-42)."""


_HHMM = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def parse_time_of_day(time_of_day: str) -> _dt.time:
    match = _HHMM.fullmatch(time_of_day or "")
    if match is None:
        raise ScheduleConfigError(f"time_of_day must be HH:MM (24-hour), got {time_of_day!r}")
    return _dt.time(int(match.group(1)), int(match.group(2)))


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception as exc:  # ZoneInfoNotFoundError, ValueError, TypeError
        raise ScheduleConfigError(f"unknown timezone {timezone_name!r}") from exc


def is_due(now: _dt.datetime, timezone_name: str, time_of_day: str, last_scheduled_run_date: str | None) -> bool:
    local_now = now.astimezone(resolve_timezone(timezone_name))
    today = local_now.date().isoformat()
    if last_scheduled_run_date == today:
        return False
    target_time = parse_time_of_day(time_of_day)
    return local_now.time() >= target_time
