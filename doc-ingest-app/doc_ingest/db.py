"""doc-ingest-app's own schema, connection factory, and transaction boundary.
Reimplemented rather than imported from pipeline_app/db.py, deliberately: the
two apps share no database and no code (spec §3), and this app's concurrency
model -- one SQLite connection per worker, never shared across threads -- is
simpler than pipeline_app's shared-connection design and does not need its
cross-thread commit-suppression machinery. See db.transaction (Task 3) for
the one-paragraph version of that reasoning."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source_files (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_path            TEXT NOT NULL UNIQUE,
    extension           TEXT NOT NULL,
    sniffed_signature   TEXT,
    classification      TEXT NOT NULL CHECK (classification IN
        ('convertible','catalog_only','excluded_media','gdoc_pointer','blocked_unknown','missing')),
    size_bytes          INTEGER,
    mtime               TEXT,
    content_hash        TEXT,
    doc_id              TEXT,
    resource_key        TEXT,
    drive_modified_time TEXT,
    drive_mime_type     TEXT,
    first_seen_at       TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_files_classification ON source_files(classification);

CREATE TABLE IF NOT EXISTS conversion_jobs (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id                  INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    status                          TEXT NOT NULL CHECK (status IN
        ('pending','claimed','converting','placing','complete','failed')),
    worker_id                       TEXT,
    claimed_at                      TEXT,
    heartbeat_at                    TEXT,
    finished_at                     TEXT,
    failure_reason                  TEXT,
    tmp_dir                         TEXT,
    source_hash_at_attempt          TEXT,
    drive_modified_time_at_attempt  TEXT,
    created_at                      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_status ON conversion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_conversion_jobs_source_file ON conversion_jobs(source_file_id);

CREATE TABLE IF NOT EXISTS conversions (
    id                                 INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id                     INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    job_id                             INTEGER REFERENCES conversion_jobs(id) ON DELETE SET NULL,
    version_number                     INTEGER NOT NULL,
    output_path                        TEXT NOT NULL,
    status                             TEXT NOT NULL CHECK (status IN ('current','superseded')),
    source_type                        TEXT NOT NULL CHECK (source_type IN
        ('pdf','docx','xlsx','gdoc','gsheet','txt','md','ppt')),
    source_hash_at_conversion          TEXT,
    drive_modified_time_at_conversion  TEXT,
    conversion_tool                    TEXT NOT NULL CHECK (conversion_tool IN
        ('firecrawl-parse','google-docs-export','google-docs-export-docx-fallback',
         'google-sheets-export','passthrough')),
    converted_at                       TEXT NOT NULL,
    gauntlet_passed_at                 TEXT,
    locked_confirmed_at                TEXT,
    page_count                         INTEGER,
    word_count                         INTEGER,
    sheet_count                        INTEGER,
    row_count_total                    INTEGER,
    UNIQUE(source_file_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_conversions_status ON conversions(status);
CREATE INDEX IF NOT EXISTS idx_conversions_converted_at ON conversions(converted_at);
CREATE INDEX IF NOT EXISTS idx_conversions_source_type ON conversions(source_type);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    source_file_id  INTEGER REFERENCES source_files(id) ON DELETE SET NULL,
    conversion_id   INTEGER REFERENCES conversions(id) ON DELETE SET NULL,
    details_json    TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS conversions_fts USING fts5(
    conversion_id UNINDEXED,
    source_rel_path,
    output_path UNINDEXED,
    body
);
"""

SCHEMA_VERSION = 1

_TXN_DEPTH: dict[int, int] = {}

_MIGRATIONS: list[tuple[int, str]] = []  # (target_version, DDL/DML) -- empty until schema changes


@contextmanager
def transaction(conn: sqlite3.Connection):
    """One explicit boundary around a multi-row invariant. Nests: an inner
    block joins the outer one rather than committing early.

    Unlike pipeline_app.db.transaction, this does not need cross-thread
    commit-suppression tracking, because each connection here has exactly one
    owning worker for its whole life (spec §5) -- there is no other thread
    that could observe a boundary it doesn't own.

    Note: _TXN_DEPTH is keyed by id(conn) and entries are explicitly deleted
    when depth returns to 0. This prevents a hazard where a stale depth entry
    could be reused if CPython recycles an id() for a new connection object.
    sqlite3.Connection objects are not weak-referenceable in CPython, so
    WeakKeyDictionary is not an option here."""
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
    """Runs any migration whose target version is above the DB's current
    schema_version, in order, each in its own BEGIN IMMEDIATE (DDL commits
    immediately regardless, same caveat as pipeline_app.db.apply_migrations).
    Empty today -- Task 2's schema is version 1 and this app has shipped
    nothing yet to migrate away from. Add entries here, never edit _SCHEMA's
    already-shipped shape in place."""
    current = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    for target_version, ddl in _MIGRATIONS:
        if target_version <= current:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.executescript(ddl)
            conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (target_version,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def get_connection(db_path: Path) -> sqlite3.Connection:
    """One connection per caller, never shared across threads (spec §5) --
    check_same_thread stays at its default (True) on purpose, so an accidental
    cross-thread use raises immediately instead of silently corrupting a
    boundary the way a shared connection would."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)",
        (SCHEMA_VERSION,),
    )
    apply_migrations(conn)
    return conn
