"""Error surfacing for the pipeline app.

Two sinks, deliberately independent:

* `log()` writes a structured line to stderr AND to a dated file under
  `pipeline-app/logs/`. stderr is what a human sees interactively; the file is
  what survives Windows Task Scheduler destroying the console window, which is
  where all 35 of the scheduled path's diagnostics went before this module
  existed.
* `record_event()` appends a row to `events`, which is what makes a failure
  *findable* later: /doctor renders unacknowledged error/critical events from
  the last seven days.

Neither function ever raises. A failure to report must never mask the thing
being reported.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# pipeline-app/logs/ -- a sibling of pipeline_app/, not inside it.
LOG_DIR = Path(__file__).resolve().parents[1] / "logs"

VALID_SEVERITIES = ("info", "warning", "error", "critical")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _merge(reserved: dict, fields: dict) -> dict:
    """Reserved keys always win; a colliding caller field is preserved, never dropped.

    `ts` is the one field that makes two log lines comparable, so a caller must
    never be able to replace it. But silently *discarding* the caller's value
    would be the same bug wearing a different hat: a mistaken call would look
    exactly like a correct one. A collision is therefore re-keyed to
    `field_<name>`, which keeps the record self-describing.

    Only `ts` can actually collide today -- `level` and `event` are named
    parameters, so passing either twice is a TypeError at the call site. All
    three are guarded anyway, so a later signature change cannot open the hole.
    """
    merged = dict(reserved)
    for key, value in fields.items():
        merged[f"field_{key}" if key in reserved else key] = value
    return merged


def log(event: str, *, level: str = "info", **fields) -> None:
    """Structured line to stderr AND to pipeline-app/logs/app-YYYY-MM-DD.log.

    `event` is a dotted kind, e.g. "adapter.fetch_failed". Never raises."""
    now = _utcnow()
    try:
        line = json.dumps(
            _merge(
                {"ts": now.isoformat(timespec="seconds"), "level": level, "event": event},
                fields,
            ),
            default=repr,
            ensure_ascii=False,
        )
    except Exception:  # noqa: BLE001 -- a field we cannot serialize must not kill the caller
        line = json.dumps({"ts": now.isoformat(timespec="seconds"), "level": level,
                           "event": event, "fields": "<unserializable>"})
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001 -- a detached/closed stderr must not kill the caller
        pass
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / f"app-{now.strftime('%Y-%m-%d')}.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 -- a read-only disk must not kill the caller
        pass


def record_event(conn, *, kind: str, severity: str, source: str,
                 message: str, detail: dict | None = None,
                 run_id: int | None = None) -> int:
    """Append one row to the `events` table and return its id.

    severity in {"info","warning","error","critical"}. Never raises -- a
    failure to record must not mask the thing being recorded; it falls back to
    log() and returns -1."""
    try:
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"unknown severity {severity!r}")
        detail_json = (
            json.dumps(detail, default=repr, ensure_ascii=False) if detail is not None else None
        )
        cur = conn.execute(
            "INSERT INTO events (occurred_at, kind, severity, source, message, detail, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_utcnow().isoformat(timespec="seconds"), kind, severity, source, message,
             detail_json, run_id),
        )
        from pipeline_app.db import commit_unless_in_transaction

        commit_unless_in_transaction(conn)
        event_id = int(cur.lastrowid)
    except Exception as exc:  # noqa: BLE001 -- recording must never mask the recorded
        log("obs.record_event_failed", level="error", kind=kind, severity=severity,
            source=source, message=message, error=f"{type(exc).__name__}: {exc}")
        return -1
    log(kind, level=severity, source=source, message=message, event_id=event_id, run_id=run_id)
    return event_id
