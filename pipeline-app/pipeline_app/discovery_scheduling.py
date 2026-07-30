"""Pure due-check for the discovery cron -- see the design spec's
'Scheduling' section for the catch-up semantics this implements. No DB or
network access: run_discovery_cron.py (Task 14) reads discovery_settings and
passes its fields in."""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo


def is_due(now: _dt.datetime, timezone_name: str, time_of_day: str, last_scheduled_run_date: str | None) -> bool:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    today = local_now.date().isoformat()
    if last_scheduled_run_date == today:
        return False
    hour, minute = (int(part) for part in time_of_day.split(":"))
    return local_now.time() >= _dt.time(hour, minute)
