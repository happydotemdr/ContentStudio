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


def log(event: str, *, level: str = "info", **fields) -> None:
    """Structured line to stderr AND to LOG_DIR/tooling-YYYY-MM-DD.log.

    Never raises.
    """
    now = _utcnow()
    record = {"ts": now.isoformat(timespec="seconds"), "level": level, "event": event}
    record.update(fields)

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
