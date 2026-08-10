-- Schema versioning exists because everything below is `IF NOT EXISTS`: on a
-- database that already has a table, a newly added column, CHECK or UNIQUE is
-- silently skipped and the first query touching it fails at runtime with
-- `no such column` in whatever route happens to hit it first (A-72). This file
-- is the create-from-scratch path; db._MIGRATIONS is the upgrade path, and
-- test_fresh_schema_matches_migrated_schema keeps the two identical.
CREATE TABLE IF NOT EXISTS schema_version (
    id      INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL,
    brand TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    stage_id TEXT NOT NULL,
    status TEXT NOT NULL,
    claude_session_id TEXT,
    approved_at TEXT,
    UNIQUE(project_id, stage_id)
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_row_id INTEGER NOT NULL REFERENCES stages(id),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    events_path TEXT NOT NULL,
    cost_usd REAL
);

CREATE TABLE IF NOT EXISTS handles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    display_name TEXT,
    cohort TEXT NOT NULL,
    keyword_filter TEXT,
    included INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    added_at TEXT NOT NULL,
    validated_at TEXT,
    last_seen_published_at TEXT,
    UNIQUE(platform, handle)
);

CREATE TABLE IF NOT EXISTS discovery_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    trigger TEXT NOT NULL,
    mode TEXT NOT NULL,
    backfill_start TEXT,
    backfill_end TEXT,
    status TEXT NOT NULL,
    heartbeat_at TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    md_path TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_discovery_single_running
    ON discovery_runs(status) WHERE status = 'running';

CREATE TABLE IF NOT EXISTS discovery_run_handles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES discovery_runs(id),
    handle_id INTEGER NOT NULL REFERENCES handles(id),
    status TEXT NOT NULL,
    items_downloaded INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS discovery_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    frequency TEXT NOT NULL DEFAULT 'daily',
    time_of_day TEXT NOT NULL DEFAULT '06:00',
    timezone TEXT NOT NULL DEFAULT 'America/Chicago',
    last_scheduled_run_date TEXT
);
INSERT OR IGNORE INTO discovery_settings (id) VALUES (1);

-- The place a failure goes. Before this table the codebase caught errors
-- carefully and told nobody: 35 stderr diagnostics on the scheduled path wrote
-- to a console Windows Task Scheduler destroys.
CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at  TEXT    NOT NULL,
  kind         TEXT    NOT NULL,
  severity     TEXT    NOT NULL CHECK (severity IN ('info','warning','error','critical')),
  source       TEXT    NOT NULL,
  message      TEXT    NOT NULL,
  detail       TEXT,
  run_id       INTEGER,
  acknowledged INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity, occurred_at DESC);
