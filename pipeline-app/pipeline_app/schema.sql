-- Schema versioning exists because everything below is `IF NOT EXISTS`: on a
-- database that already has a table, a newly added column, CHECK or UNIQUE is
-- silently skipped and the first query touching it fails at runtime with
-- `no such column` in whatever route happens to hit it first (A-72). This file
-- is the create-from-scratch path; db._MIGRATIONS is the upgrade path. They are
-- two hand-maintained definitions of one schema, and nothing enforces that they
-- agree until T12 adds test_a_migrated_database_has_the_same_schema_as_a_fresh_one.
-- Until then, a change here needs a matching migration by hand.
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
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stage_id TEXT NOT NULL,
    -- Mirrors state_machine.StageStatus. Without it a typo'd literal (three
    -- call sites already pass bare strings) persists a status no guard
    -- recognizes: is_locked_or_running returns False for it, so the stage stays
    -- chattable, editable and approvable regardless of intent (A-47).
    status TEXT NOT NULL CHECK (status IN
        ('locked','ready','running','awaiting_review','approved','stale','no_artifact')),
    claude_session_id TEXT,
    approved_at TEXT,
    UNIQUE(project_id, stage_id)
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_row_id INTEGER NOT NULL REFERENCES stages(id) ON DELETE CASCADE,
    -- turn_service writes running/aborted/complete/failed; preflight writes
    -- orphaned. Verified against the call sites, not assumed: turn_service.py:129
    -- (running), :210 (aborted), :216 (complete/failed), preflight.py:16
    -- (orphaned). Anything else is a typo that every status comparison in the app
    -- would silently answer False to (A-47's defect, same shape) (A-75).
    status TEXT NOT NULL CHECK (status IN
        ('running','complete','failed','aborted','orphaned')),
    created_at TEXT NOT NULL,
    finished_at TEXT,
    events_path TEXT NOT NULL,
    cost_usd REAL
);
CREATE INDEX IF NOT EXISTS idx_turns_stage_row ON turns(stage_row_id);
-- `ux_turns_single_running` (the pipeline's single-running invariant, A-71) is
-- deliberately NOT here. This file runs as one executescript() before any
-- migration, and a pre-existing database can already hold two 'running' turns:
-- a UNIQUE index built over that violation raises, executescript abandons every
-- statement after it -- `events` among them, it is created near the end of this
-- file -- and the boot dies with a half-built schema and nowhere to record it.
-- db.init_db issues the index after apply_migrations instead, at a point where
-- migration 1 has already repaired any duplicates. See db._MIGRATION_1_TURNS_STEPS
-- and db.init_db.

-- Cross-platform creator identity. Without it @jane on YouTube and @jane on X
-- are unrelated rows: per-creator reporting is impossible, one creator's
-- cross-post is counted three times in the daily inventory, and "did we miss
-- this creator's new platform" is unanswerable (B-72). P10 populates this from
-- the manifests; this package only creates it.
CREATE TABLE IF NOT EXISTS creators (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  slug         TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS handles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id INTEGER REFERENCES creators(id) ON DELETE SET NULL,
    -- The adapter registry's vocabulary (run_discovery_cron.build_adapters).
    -- Unconstrained, a mistyped or hand-posted value is stored happily and then
    -- raises KeyError in a detached validate subprocess, leaving the row
    -- 'pending'/included=1 forever: a ghost the handles page polls for a status
    -- that never arrives (B-73).
    platform TEXT NOT NULL CHECK (platform IN
        ('youtube','bluesky','instagram','linkedin-profile','linkedin-company',
         'facebook','x')),
    handle TEXT NOT NULL,
    display_name TEXT,
    cohort TEXT NOT NULL,
    keyword_filter TEXT,
    included INTEGER NOT NULL DEFAULT 1,
    -- discovery_engine writes validating/validated/invalid; this DEFAULT writes
    -- pending; 'failing' is written by the per-handle failure counter that owns
    -- consecutive_failures below (B-82). Both are declared here rather than
    -- later because a CHECK cannot be widened without a second rebuild of this
    -- same table inside the same unshipped migration 1.
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
        ('pending','validating','validated','invalid','failing')),
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    validated_at TEXT,
    last_seen_published_at TEXT,
    UNIQUE(platform, handle)
);
-- `idx_handles_creator` is deliberately NOT here, for the same reason
-- `ux_turns_single_running` is not: this file runs as one executescript()
-- before any migration, and on a pre-existing database the `CREATE TABLE IF NOT
-- EXISTS handles` above is skipped -- so `handles` still has no `creator_id`
-- column at this point and `CREATE INDEX ... ON handles(creator_id)` raises
-- `no such column: creator_id` right here (probed on sqlite 3.50.4, not
-- reasoned about). executescript then abandons every statement after it --
-- `events` among them, it is created near the end of this file -- and the boot
-- dies with a half-built schema and nowhere to record it. The column and the
-- index are added to a pre-existing database by
-- db._MIGRATION_1_HANDLES_CREATOR_STEPS, and to a fresh one by db.init_db after
-- apply_migrations returns. See both.

-- Rows migration 1 could not carry across the platform CHECK above. Kept, not
-- dropped: this is the only record of what the operator actually typed, and it
-- deliberately carries no CHECK of its own -- constraining the record of a bad
-- value the same way as the value would make it unstorable here too. Written
-- only by db._quarantine_unknown_platforms; nothing reads it automatically.
CREATE TABLE IF NOT EXISTS handles_quarantine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quarantined_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    display_name TEXT,
    cohort TEXT,
    keyword_filter TEXT,
    included INTEGER,
    status TEXT,
    added_at TEXT,
    validated_at TEXT,
    last_seen_published_at TEXT
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
    run_id INTEGER NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
    handle_id INTEGER NOT NULL REFERENCES handles(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    items_downloaded INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_drh_run ON discovery_run_handles(run_id);
CREATE INDEX IF NOT EXISTS idx_drh_handle ON discovery_run_handles(handle_id);

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
