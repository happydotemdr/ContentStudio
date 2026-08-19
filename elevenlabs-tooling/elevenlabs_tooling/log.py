"""Structured, dual-sink logging that never raises.

Mirrors pipeline_app/obs.py's log() shape without importing pipeline_app:
every event is a JSON line written to stderr AND appended to a dated file
under elevenlabs-tooling/logs/. A failure to log must never mask or
interrupt the thing being logged -- every I/O boundary below is wrapped.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


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
    """Structured line to stderr AND to LOG_DIR/tooling-YYYY-MM-DD.log.

    Never raises.
    """
    now = _utcnow()
    record = _merge(
        {"ts": now.isoformat(timespec="seconds"), "level": level, "event": event},
        fields,
    )

    try:
        line = json.dumps(record, default=repr, ensure_ascii=False)
    except Exception:  # noqa: BLE001 -- an unserializable field must not kill the caller
        line = json.dumps({
            "ts": now.isoformat(timespec="seconds"),
            "level": level,
            "event": event,
            "fields": "<unserializable>",
        })

    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001 -- a detached/closed stderr must not kill the caller
        pass

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"tooling-{now.strftime('%Y-%m-%d')}.log"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001 -- a read-only disk must not kill the caller
        pass
