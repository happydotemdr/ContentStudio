import shutil
import sqlite3
from typing import Callable

from pipeline_app import db as db_mod
from pipeline_app.cli_runner import resolve_claude_binary


def reconcile_orphaned_turns(conn: sqlite3.Connection) -> int:
    running = db_mod.list_running_turns(conn)
    for turn in running:
        db_mod.update_turn(conn, turn["id"], "orphaned")
    return len(running)


def check_cli_available(which_fn: Callable[[str], str | None] = shutil.which) -> dict:
    try:
        path = resolve_claude_binary(which_fn)
        return {"available": True, "path": path, "error": None}
    except FileNotFoundError as exc:
        return {"available": False, "path": None, "error": str(exc)}
