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


def log(event: str, *, level: str = "info", **fields) -> None:
    """Structured line to stderr AND to pipeline-app/logs/app-YYYY-MM-DD.log.

    `event` is a dotted kind, e.g. "adapter.fetch_failed". Never raises."""
    now = _utcnow()
    try:
        line = json.dumps(
            {"ts": now.isoformat(timespec="seconds"), "level": level, "event": event, **fields},
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
