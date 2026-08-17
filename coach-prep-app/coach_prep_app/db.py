"""coach-prep-app's own schema, connection factory, and transaction
boundary. Same connection-per-caller model as doc_ingest/db.py, reimplemented
rather than shared (each app owns its own database, matching that module's
own stated rationale)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS watermarks (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_slug                 TEXT NOT NULL,
    calendar_event_instance_id  TEXT NOT NULL,
    done_at                     TEXT NOT NULL,
    UNIQUE(client_slug, calendar_event_instance_id)
);

CREATE TABLE IF NOT EXISTS generation_runs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_slug                 TEXT NOT NULL,
    calendar_event_instance_id  TEXT NOT NULL,
    meeting_start_at            TEXT NOT NULL,
    status                      TEXT NOT NULL CHECK (status IN
        ('assembling','generated','gates_failed','published','notified','failed')),
    failure_reason              TEXT,
    draft_drive_file_id         TEXT,
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generation_runs_client ON generation_runs(client_slug);

CREATE TABLE IF NOT EXISTS generation_inputs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES generation_runs(id) ON DELETE CASCADE,
    source_label    TEXT NOT NULL,
    source_kind     TEXT NOT NULL CHECK (source_kind IN ('gmail_thread','converted_file','program_source')),
    reference       TEXT NOT NULL,
    version_or_hash TEXT,
    captured_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_generation_inputs_run ON generation_inputs(run_id);
"""

SCHEMA_VERSION = 1
_TXN_DEPTH: dict[int, int] = {}
_MIGRATIONS: list[tuple[int, str]] = []


@contextmanager
def transaction(conn: sqlite3.Connection):
    key = id(conn)
    depth = _TXN_DEPTH.get(key, 0)
    if depth == 0:
        conn.execute("BEGIN")
    _TXN_DEPTH[key] = depth + 1
    try:
        yield conn
    except BaseException:
        _TXN_DEPTH[key] = depth
        if depth == 0:
            conn.execute("ROLLBACK")
            del _TXN_DEPTH[key]
        raise
    else:
        _TXN_DEPTH[key] = depth
        if depth == 0:
            conn.execute("COMMIT")
            del _TXN_DEPTH[key]


def apply_migrations(conn: sqlite3.Connection) -> None:
    # executescript runs its own implicit COMMIT before executing, so it
    # cannot be wrapped in a BEGIN/COMMIT pair -- it establishes its own
    # transaction boundary per statement under isolation_level=None. Mirrors
    # doc_ingest/db.py's apply_migrations exactly (see that module for the
    # full rationale and the accepted single-operator-tool gap this leaves:
    # a crash between the DDL and the schema_version UPDATE is tolerated by
    # this function's own idempotence on the next run).
    current = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    for target_version, ddl in _MIGRATIONS:
        if target_version <= current:
            continue
        conn.executescript(ddl)
        conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (target_version,))


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(_SCHEMA)
    conn.execute("INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)", (SCHEMA_VERSION,))
    apply_migrations(conn)
    return conn
