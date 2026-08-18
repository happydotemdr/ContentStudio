"""Per-(client, calendar event instance) due-check: fires once, at or after
a configured local hour on the day before the meeting, gated by a persisted
watermark keyed on the event INSTANCE id (never a recurring series id)."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from coach_prep_app import db


def is_due(
    conn,
    client_slug: str,
    event_instance_id: str,
    meeting_start_utc: dt.datetime,
    now_utc: dt.datetime,
    timezone_name: str,
    ready_hour_local: int,
) -> bool:
    already_done = conn.execute(
        "SELECT 1 FROM watermarks WHERE client_slug = ? AND calendar_event_instance_id = ?",
        (client_slug, event_instance_id),
    ).fetchone()
    if already_done is not None:
        return False

    tz = ZoneInfo(timezone_name)
    meeting_local = meeting_start_utc.astimezone(tz)
    ready_at_local = (meeting_local - dt.timedelta(days=1)).replace(
        hour=ready_hour_local, minute=0, second=0, microsecond=0
    )
    return now_utc.astimezone(tz) >= ready_at_local


def mark_done(conn, client_slug: str, event_instance_id: str, now_iso: str) -> None:
    with db.transaction(conn):
        conn.execute(
            "INSERT OR IGNORE INTO watermarks (client_slug, calendar_event_instance_id, done_at) "
            "VALUES (?, ?, ?)",
            (client_slug, event_instance_id, now_iso),
        )
