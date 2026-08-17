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

WATERMARK_SEP = "|"
MIN_RUN_INTERVAL_H = 20     # < 24 so a schedule time change still fires; > 12 so no
                            # timezone edit, DST shift or clock skew can double-fire


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


def encode_watermark(local_date: str, timezone_name: str, run_instant_utc: str) -> str:
    return WATERMARK_SEP.join([local_date, timezone_name, run_instant_utc])


def decode_watermark(raw: str | None) -> tuple[str | None, _dt.datetime | None]:
    """Returns (local_date, run_instant). Accepts the legacy bare 'YYYY-MM-DD'
    form so an existing install does not re-fire on the first upgraded wake."""
    if not raw:
        return None, None
    parts = raw.split(WATERMARK_SEP)
    if len(parts) != 3:
        return parts[0], None
    try:
        return parts[0], _dt.datetime.fromisoformat(parts[2])
    except ValueError:
        return parts[0], None


def is_due(now: _dt.datetime, timezone_name: str, time_of_day: str, last_scheduled_run_date: str | None) -> bool:
    last_date, last_instant = decode_watermark(last_scheduled_run_date)
    if last_instant is not None and (now - last_instant) < _dt.timedelta(hours=MIN_RUN_INTERVAL_H):
        return False
    local_now = now.astimezone(resolve_timezone(timezone_name))
    today = local_now.date().isoformat()
    if last_date == today:
        return False
    target_time = parse_time_of_day(time_of_day)
    return local_now.time() >= target_time
