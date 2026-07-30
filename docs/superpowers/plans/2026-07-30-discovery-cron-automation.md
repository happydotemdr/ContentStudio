# Discovery Cron Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate discovery/download of new content from ContentStudio's YouTube/Bluesky
brand-intel handles into a daily local cron job with a management UI in `pipeline-app`, replacing
the manual all-or-nothing `download_brandintel.py` script for that purpose.

**Architecture:** Four new SQLite tables in `pipeline-app`'s existing db (`handles`,
`discovery_runs`, `discovery_run_handles`, `discovery_settings`). A pure-logic dedup/early-stop
algorithm (`discovery_engine.process_handle`) driven by small per-platform adapters
(`discovery_youtube.py`, `discovery_bluesky.py`) that isolate all `yt-dlp`/HTTP calls behind a
common interface, so the core algorithm is unit-testable without any network access. A standalone
CLI (`run_discovery_cron.py`) is the single execution path for every trigger (Windows Task
Scheduler, the UI's "Run Now"/backfill buttons, and handle validation) — spawned as a subprocess,
never sharing `pipeline-app`'s long-lived web request connection. New FastAPI routes
(`routes/discovery.py`) add a handle roster page and a run history page to the existing app.

**Tech Stack:** Python 3.10+, FastAPI + Jinja2 (existing `pipeline-app` stack), stdlib `sqlite3`,
`yt-dlp` (subprocess), `youtube-transcript-api` (fallback), stdlib `urllib` for the Bluesky public
API, pytest + `fastapi.testclient.TestClient` (existing `pipeline-app` test conventions).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-30-discovery-cron-automation-design.md` — read it before
  starting; every task below implements a specific section of it.
- Cohort values are free text with no DB `CHECK` constraint: `guru`, `shorts-specialist`,
  `midjourney-source`, `general-interest` are UI suggestions only.
- Default schedule: daily, `06:00`, `America/Chicago`.
- New-handle lookback: 3 months (90 days) — a handle with nothing on disk yet.
- Existing-handle early-stop grace: 3 consecutive enumerated IDs already on disk.
- Heartbeat interval: 30 seconds. Stale-run reclaim threshold: 600 seconds (10 minutes).
- Windows Task Scheduler: one per-user task (`ContentStudio-Discovery`), fixed 15-minute trigger,
  registered once by a setup script — never re-registered from an HTTP request handler.
- Paired run record path: `output/discovery-runs/<run_id>.md`.
- Never delete, move, or truncate persisted content under `output/brand-intel/` (the existing
  `output/brand-intel/youtube/_tmp/` scratch directory is exempt — it's transient working files,
  not corpus content). The discovery engine never reads or writes `output/brand-intel/_manifest.csv`.
- `download_brandintel.py` and `manifests/brand_sources.json` (both at the repo root, outside
  `pipeline-app/`) are **not modified** by this plan — they stay available for manual/ad hoc use
  exactly as they are today.
- All new `pipeline-app` code follows the existing style in `pipeline_app/db.py` /
  `pipeline_app/project_service.py`: plain functions taking `conn: sqlite3.Connection` as the
  first argument, `conn.commit()` inline in the function that writes, `sqlite3.Row` return values,
  modern `X | None` type hints, no classes where a function suffices.
- Tests follow existing `pipeline-app/tests/` conventions: `tmp_path` + a fresh SQLite db per test
  (see `tests/test_db.py`'s `conn` fixture and `tests/test_routes_projects.py`'s `client` fixture),
  **no real network calls** — every `yt-dlp` subprocess call and every Bluesky HTTP call is
  monkeypatched/faked in tests.

---

## Task 1: Schema — four new tables + `busy_timeout`

**Files:**
- Modify: `pipeline-app/pipeline_app/schema.sql`
- Modify: `pipeline-app/pipeline_app/db.py:5-19` (the `get_connection` function)
- Test: `pipeline-app/tests/test_db.py`

**Interfaces:**
- Produces: the four tables (`handles`, `discovery_runs`, `discovery_run_handles`,
  `discovery_settings`) and index (`ux_discovery_single_running`) that every later task's `db.py`
  functions read/write. `discovery_settings` always has exactly one row, `id = 1`, seeded with
  defaults by the schema itself.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_db.py`:

```python
def test_schema_init_is_idempotent_with_new_discovery_tables(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    db.init_db(db_path, schema_path)  # second init must not raise
    conn = db.get_connection(db_path)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert {"handles", "discovery_runs", "discovery_run_handles", "discovery_settings"} <= tables
    settings = conn.execute("SELECT * FROM discovery_settings WHERE id = 1").fetchone()
    assert settings["frequency"] == "daily"
    assert settings["time_of_day"] == "06:00"
    assert settings["timezone"] == "America/Chicago"
    conn.close()


def test_two_running_discovery_runs_violate_unique_index(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at) "
        "VALUES ('run-1', 'manual', 'incremental', 'running', '2026-07-30T06:00:00Z')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at) "
            "VALUES ('run-2', 'manual', 'incremental', 'running', '2026-07-30T06:01:00Z')"
        )
    conn.close()
```

Add `import sqlite3` to the top of `tests/test_db.py` (it currently only imports `Path` and
`pytest`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k "discovery_tables or unique_index" -v`
Expected: FAIL — `handles`/`discovery_runs`/etc. don't exist yet.

- [ ] **Step 3: Write the schema changes**

Append to `pipeline-app/pipeline_app/schema.sql` (after the existing `turns` table):

```sql
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
```

In `pipeline-app/pipeline_app/db.py`, add `conn.execute("PRAGMA busy_timeout = 5000")` to
`get_connection`, right after the existing `conn.execute("PRAGMA journal_mode = WAL")` line:

```python
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -v`
Expected: PASS (all existing tests plus the two new ones)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/schema.sql pipeline-app/pipeline_app/db.py pipeline-app/tests/test_db.py
git commit -m "feat(discovery): add handles/discovery_runs/discovery_run_handles/discovery_settings schema"
```

---

## Task 2: `db.py` — `handles` table CRUD

**Files:**
- Modify: `pipeline-app/pipeline_app/db.py` (append functions)
- Test: `pipeline-app/tests/test_db.py`

**Interfaces:**
- Consumes: the `handles` table from Task 1.
- Produces:
  - `create_handle(conn, platform: str, handle: str, display_name: str | None, cohort: str, keyword_filter: str | None, added_at: str) -> int`
  - `get_handle(conn, handle_id: int) -> sqlite3.Row | None`
  - `get_handle_by_platform_and_handle(conn, platform: str, handle: str) -> sqlite3.Row | None`
  - `list_handles(conn, included_only: bool = False) -> list[sqlite3.Row]`
  - `set_handle_status(conn, handle_id: int, status: str, validated_at: str | None = None) -> None`
  - `set_handle_included(conn, handle_id: int, included: bool) -> None`
  - `set_handle_last_seen(conn, handle_id: int, last_seen_published_at: str) -> None`
  - `upsert_handle_from_migration(conn, platform: str, handle: str, display_name: str | None, cohort: str, keyword_filter: str | None, status: str, included: bool, added_at: str) -> int` — `INSERT OR IGNORE`, so re-running the migration never overwrites a manually-edited row; returns the row's id either way.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_db.py`:

```python
def test_create_and_get_handle(conn):
    handle_id = db.create_handle(conn, "youtube", "@Romayroh", "Romayroh", "guru", None, "2026-07-30T00:00:00Z")
    row = db.get_handle(conn, handle_id)
    assert row["handle"] == "@Romayroh"
    assert row["platform"] == "youtube"
    assert row["cohort"] == "guru"
    assert row["included"] == 1
    assert row["status"] == "pending"


def test_get_handle_by_platform_and_handle(conn):
    db.create_handle(conn, "youtube", "@Romayroh", "Romayroh", "guru", None, "2026-07-30T00:00:00Z")
    row = db.get_handle_by_platform_and_handle(conn, "youtube", "@Romayroh")
    assert row is not None
    assert db.get_handle_by_platform_and_handle(conn, "bluesky", "@Romayroh") is None


def test_list_handles_filters_included(conn):
    a = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-07-30T00:00:00Z")
    db.create_handle(conn, "youtube", "@b", None, "guru", None, "2026-07-30T00:00:00Z")
    db.set_handle_included(conn, a, False)
    assert len(db.list_handles(conn)) == 2
    included_only = db.list_handles(conn, included_only=True)
    assert len(included_only) == 1
    assert included_only[0]["handle"] == "@b"


def test_set_handle_status_and_validated_at(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-07-30T00:00:00Z")
    db.set_handle_status(conn, handle_id, "validated", validated_at="2026-07-30T01:00:00Z")
    row = db.get_handle(conn, handle_id)
    assert row["status"] == "validated"
    assert row["validated_at"] == "2026-07-30T01:00:00Z"


def test_set_handle_last_seen(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-07-30T00:00:00Z")
    db.set_handle_last_seen(conn, handle_id, "2026-07-28")
    assert db.get_handle(conn, handle_id)["last_seen_published_at"] == "2026-07-28"


def test_upsert_handle_from_migration_is_idempotent(conn):
    first_id = db.upsert_handle_from_migration(
        conn, "youtube", "@a", "A Channel", "guru", None, "validated", True, "2026-07-30T00:00:00Z"
    )
    db.set_handle_status(conn, first_id, "invalid")  # simulate a manual edit after migration
    second_id = db.upsert_handle_from_migration(
        conn, "youtube", "@a", "A Channel", "guru", None, "validated", True, "2026-07-30T00:00:00Z"
    )
    assert second_id == first_id
    assert db.get_handle(conn, first_id)["status"] == "invalid"  # not clobbered by re-running
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k handle -v`
Expected: FAIL — `AttributeError: module 'pipeline_app.db' has no attribute 'create_handle'`

- [ ] **Step 3: Implement the functions**

Append to `pipeline-app/pipeline_app/db.py`:

```python
def create_handle(
    conn: sqlite3.Connection, platform: str, handle: str, display_name: str | None,
    cohort: str, keyword_filter: str | None, added_at: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO handles (platform, handle, display_name, cohort, keyword_filter, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (platform, handle, display_name, cohort, keyword_filter, added_at),
    )
    conn.commit()
    return cur.lastrowid


def get_handle(conn: sqlite3.Connection, handle_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM handles WHERE id = ?", (handle_id,)).fetchone()


def get_handle_by_platform_and_handle(conn: sqlite3.Connection, platform: str, handle: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM handles WHERE platform = ? AND handle = ?", (platform, handle)
    ).fetchone()


def list_handles(conn: sqlite3.Connection, included_only: bool = False) -> list[sqlite3.Row]:
    if included_only:
        return conn.execute("SELECT * FROM handles WHERE included = 1 ORDER BY cohort, handle").fetchall()
    return conn.execute("SELECT * FROM handles ORDER BY cohort, handle").fetchall()


def set_handle_status(conn: sqlite3.Connection, handle_id: int, status: str, validated_at: str | None = None) -> None:
    if validated_at is not None:
        conn.execute(
            "UPDATE handles SET status = ?, validated_at = ? WHERE id = ?",
            (status, validated_at, handle_id),
        )
    else:
        conn.execute("UPDATE handles SET status = ? WHERE id = ?", (status, handle_id))
    conn.commit()


def set_handle_included(conn: sqlite3.Connection, handle_id: int, included: bool) -> None:
    conn.execute("UPDATE handles SET included = ? WHERE id = ?", (1 if included else 0, handle_id))
    conn.commit()


def set_handle_last_seen(conn: sqlite3.Connection, handle_id: int, last_seen_published_at: str) -> None:
    conn.execute(
        "UPDATE handles SET last_seen_published_at = ? WHERE id = ?",
        (last_seen_published_at, handle_id),
    )
    conn.commit()


def upsert_handle_from_migration(
    conn: sqlite3.Connection, platform: str, handle: str, display_name: str | None,
    cohort: str, keyword_filter: str | None, status: str, included: bool, added_at: str,
) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO handles "
        "(platform, handle, display_name, cohort, keyword_filter, status, included, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (platform, handle, display_name, cohort, keyword_filter, status, 1 if included else 0, added_at),
    )
    conn.commit()
    return get_handle_by_platform_and_handle(conn, platform, handle)["id"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k handle -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/db.py pipeline-app/tests/test_db.py
git commit -m "feat(discovery): add handles table CRUD to db.py"
```

---

## Task 3: `db.py` — `discovery_runs` + `discovery_run_handles` CRUD (locking, heartbeat, reclaim)

**Files:**
- Modify: `pipeline-app/pipeline_app/db.py` (append functions)
- Test: `pipeline-app/tests/test_db.py`

**Interfaces:**
- Consumes: `discovery_runs`/`discovery_run_handles` tables + `ux_discovery_single_running` index
  from Task 1.
- Produces:
  - `insert_running_run(conn, run_id, trigger, mode, started_at, backfill_start=None, backfill_end=None) -> int` — raises `sqlite3.IntegrityError` if another row already has `status='running'`.
  - `insert_locked_run(conn, run_id, trigger, mode, started_at, finished_at) -> int`
  - `insert_terminal_run(conn, run_id, trigger, mode, status, started_at, finished_at) -> int` — used by `validate_handle` (no `running` phase; see Task 9).
  - `get_running_run(conn) -> sqlite3.Row | None`
  - `update_run_heartbeat(conn, run_row_id: int, heartbeat_at: str) -> None`
  - `reclaim_stale_runs(conn, now_iso: str, staleness_seconds: int) -> list[int]` — flips any `running` row whose `heartbeat_at` (or `started_at` if never heartbeated) is older than `staleness_seconds` to `abandoned`; returns the list of reclaimed row ids.
  - `finish_run(conn, run_row_id: int, status: str, finished_at: str, md_path: str) -> None`
  - `get_run(conn, run_row_id: int) -> sqlite3.Row | None`
  - `list_runs(conn) -> list[sqlite3.Row]` — newest first.
  - `record_handle_result(conn, run_row_id: int, handle_id: int, status: str, items_downloaded: int, error_message: str | None = None) -> int`
  - `list_run_handle_results(conn, run_row_id: int) -> list[sqlite3.Row]`

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_db.py`:

```python
def test_insert_running_run_then_second_raises(conn):
    db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_running_run(conn, "run-2", "manual", "incremental", "2026-07-30T06:01:00Z")


def test_insert_locked_run_after_conflict(conn):
    db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    locked_id = db.insert_locked_run(
        conn, "run-2", "manual", "incremental", "2026-07-30T06:01:00Z", "2026-07-30T06:01:00Z"
    )
    row = db.get_run(conn, locked_id)
    assert row["status"] == "locked"


def test_insert_terminal_run_has_no_running_phase(conn):
    run_id = db.insert_terminal_run(
        conn, "validate-1", "manual", "validate_handle", "completed",
        "2026-07-30T06:00:00Z", "2026-07-30T06:00:30Z",
    )
    assert db.get_running_run(conn) is None
    assert db.get_run(conn, run_id)["status"] == "completed"


def test_get_running_run_returns_the_running_row(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    row = db.get_running_run(conn)
    assert row["id"] == run_id


def test_update_run_heartbeat(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    db.update_run_heartbeat(conn, run_id, "2026-07-30T06:00:30Z")
    assert db.get_run(conn, run_id)["heartbeat_at"] == "2026-07-30T06:00:30Z"


def test_reclaim_stale_runs_flips_to_abandoned(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    db.update_run_heartbeat(conn, run_id, "2026-07-30T06:00:30Z")
    reclaimed = db.reclaim_stale_runs(conn, "2026-07-30T06:20:00Z", staleness_seconds=600)
    assert reclaimed == [run_id]
    assert db.get_run(conn, run_id)["status"] == "abandoned"
    assert db.get_running_run(conn) is None


def test_reclaim_stale_runs_leaves_fresh_runs_alone(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    db.update_run_heartbeat(conn, run_id, "2026-07-30T06:09:30Z")
    reclaimed = db.reclaim_stale_runs(conn, "2026-07-30T06:10:00Z", staleness_seconds=600)
    assert reclaimed == []
    assert db.get_run(conn, run_id)["status"] == "running"


def test_finish_run(conn):
    run_id = db.insert_running_run(conn, "run-1", "manual", "incremental", "2026-07-30T06:00:00Z")
    db.finish_run(conn, run_id, "completed", "2026-07-30T06:04:00Z", "output/discovery-runs/run-1.md")
    row = db.get_run(conn, run_id)
    assert row["status"] == "completed"
    assert row["finished_at"] == "2026-07-30T06:04:00Z"
    assert row["md_path"] == "output/discovery-runs/run-1.md"


def test_list_runs_newest_first(conn):
    db.insert_terminal_run(conn, "r1", "manual", "incremental", "completed", "2026-07-30T06:00:00Z", "2026-07-30T06:01:00Z")
    db.insert_terminal_run(conn, "r2", "manual", "incremental", "completed", "2026-07-30T07:00:00Z", "2026-07-30T07:01:00Z")
    rows = db.list_runs(conn)
    assert [r["run_id"] for r in rows] == ["r2", "r1"]


def test_record_and_list_run_handle_results(conn):
    run_id = db.insert_terminal_run(conn, "r1", "manual", "incremental", "completed", "2026-07-30T06:00:00Z", "2026-07-30T06:01:00Z")
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-07-30T00:00:00Z")
    db.record_handle_result(conn, run_id, handle_id, "ok", items_downloaded=2)
    results = db.list_run_handle_results(conn, run_id)
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["items_downloaded"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k "run" -v`
Expected: FAIL — the new functions don't exist yet.

- [ ] **Step 3: Implement the functions**

Append to `pipeline-app/pipeline_app/db.py`:

```python
def insert_running_run(
    conn: sqlite3.Connection, run_id: str, trigger: str, mode: str, started_at: str,
    backfill_start: str | None = None, backfill_end: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, backfill_start, backfill_end, status, started_at) "
        "VALUES (?, ?, ?, ?, ?, 'running', ?)",
        (run_id, trigger, mode, backfill_start, backfill_end, started_at),
    )
    conn.commit()
    return cur.lastrowid


def insert_locked_run(conn: sqlite3.Connection, run_id: str, trigger: str, mode: str, started_at: str, finished_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at, finished_at) "
        "VALUES (?, ?, ?, 'locked', ?, ?)",
        (run_id, trigger, mode, started_at, finished_at),
    )
    conn.commit()
    return cur.lastrowid


def insert_terminal_run(conn: sqlite3.Connection, run_id: str, trigger: str, mode: str, status: str, started_at: str, finished_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, trigger, mode, status, started_at, finished_at),
    )
    conn.commit()
    return cur.lastrowid


def get_running_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM discovery_runs WHERE status = 'running'").fetchone()


def update_run_heartbeat(conn: sqlite3.Connection, run_row_id: int, heartbeat_at: str) -> None:
    conn.execute("UPDATE discovery_runs SET heartbeat_at = ? WHERE id = ?", (heartbeat_at, run_row_id))
    conn.commit()


def reclaim_stale_runs(conn: sqlite3.Connection, now_iso: str, staleness_seconds: int) -> list[int]:
    import datetime as _dt

    now = _dt.datetime.fromisoformat(now_iso)
    stale_ids: list[int] = []
    for row in conn.execute("SELECT * FROM discovery_runs WHERE status = 'running'").fetchall():
        last_seen = row["heartbeat_at"] or row["started_at"]
        age = (now - _dt.datetime.fromisoformat(last_seen)).total_seconds()
        if age >= staleness_seconds:
            stale_ids.append(row["id"])
    for run_row_id in stale_ids:
        conn.execute("UPDATE discovery_runs SET status = 'abandoned' WHERE id = ?", (run_row_id,))
    if stale_ids:
        conn.commit()
    return stale_ids


def finish_run(conn: sqlite3.Connection, run_row_id: int, status: str, finished_at: str, md_path: str) -> None:
    conn.execute(
        "UPDATE discovery_runs SET status = ?, finished_at = ?, md_path = ? WHERE id = ?",
        (status, finished_at, md_path, run_row_id),
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_row_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM discovery_runs WHERE id = ?", (run_row_id,)).fetchone()


def list_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM discovery_runs ORDER BY started_at DESC").fetchall()


def record_handle_result(
    conn: sqlite3.Connection, run_row_id: int, handle_id: int, status: str,
    items_downloaded: int, error_message: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO discovery_run_handles (run_id, handle_id, status, items_downloaded, error_message) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_row_id, handle_id, status, items_downloaded, error_message),
    )
    conn.commit()
    return cur.lastrowid


def list_run_handle_results(conn: sqlite3.Connection, run_row_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM discovery_run_handles WHERE run_id = ?", (run_row_id,)
    ).fetchall()
```

Note: `reclaim_stale_runs` compares ISO timestamps directly with `datetime.fromisoformat`, which
requires every timestamp written by this feature to be a real ISO 8601 string (all of `started_at`,
`heartbeat_at`, `now_iso` are produced by `datetime.isoformat()` elsewhere in this plan — see Task
11's `now_iso()` helper).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -v`
Expected: PASS (full file, including Task 1/2's tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/db.py pipeline-app/tests/test_db.py
git commit -m "feat(discovery): add discovery_runs/discovery_run_handles CRUD, locking, heartbeat, reclaim"
```

---

## Task 4: `db.py` — `discovery_settings` CRUD

**Files:**
- Modify: `pipeline-app/pipeline_app/db.py` (append functions)
- Test: `pipeline-app/tests/test_db.py`

**Interfaces:**
- Consumes: `discovery_settings` singleton row from Task 1.
- Produces:
  - `get_settings(conn) -> sqlite3.Row`
  - `update_settings(conn, frequency: str, time_of_day: str, timezone: str) -> None`
  - `set_last_scheduled_run_date(conn, date_iso: str) -> None`

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_db.py`:

```python
def test_get_settings_returns_defaults(conn):
    row = db.get_settings(conn)
    assert row["frequency"] == "daily"
    assert row["time_of_day"] == "06:00"
    assert row["timezone"] == "America/Chicago"
    assert row["last_scheduled_run_date"] is None


def test_update_settings(conn):
    db.update_settings(conn, "daily", "07:30", "America/New_York")
    row = db.get_settings(conn)
    assert row["time_of_day"] == "07:30"
    assert row["timezone"] == "America/New_York"


def test_set_last_scheduled_run_date(conn):
    db.set_last_scheduled_run_date(conn, "2026-07-30")
    assert db.get_settings(conn)["last_scheduled_run_date"] == "2026-07-30"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k settings -v`
Expected: FAIL

- [ ] **Step 3: Implement the functions**

Append to `pipeline-app/pipeline_app/db.py`:

```python
def get_settings(conn: sqlite3.Connection) -> sqlite3.Row:
    return conn.execute("SELECT * FROM discovery_settings WHERE id = 1").fetchone()


def update_settings(conn: sqlite3.Connection, frequency: str, time_of_day: str, timezone: str) -> None:
    conn.execute(
        "UPDATE discovery_settings SET frequency = ?, time_of_day = ?, timezone = ? WHERE id = 1",
        (frequency, time_of_day, timezone),
    )
    conn.commit()


def set_last_scheduled_run_date(conn: sqlite3.Connection, date_iso: str) -> None:
    conn.execute("UPDATE discovery_settings SET last_scheduled_run_date = ? WHERE id = 1", (date_iso,))
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/db.py pipeline-app/tests/test_db.py
git commit -m "feat(discovery): add discovery_settings CRUD to db.py"
```

---

## Task 5: Migration script — seed `handles` from `manifests/brand_sources.json`

**Files:**
- Create: `pipeline-app/scripts/migrate_handles_from_manifest.py`
- Test: `pipeline-app/tests/test_migrate_handles.py`

**Interfaces:**
- Consumes: `db.upsert_handle_from_migration` (Task 2), the repo-root
  `manifests/brand_sources.json` file (read-only, never modified).
- Produces: `derive_cohort(note: str, handle: str) -> str` and
  `migrate(conn: sqlite3.Connection, manifest_path: Path, now: str) -> int` (returns count of rows
  upserted), importable by tests and runnable as `python scripts/migrate_handles_from_manifest.py`.

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_migrate_handles.py`:

```python
import json
from pathlib import Path

import pytest

from pipeline_app import db
from scripts.migrate_handles_from_manifest import derive_cohort, migrate


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


@pytest.mark.parametrize("note,handle,expected", [
    ("guru channel (manual-seed)", "@Romayroh", "guru"),
    ("shorts specialist (exemplar shorts); added 2026-07-23", "@JennyHoyos", "shorts-specialist"),
    ("Midjourney prompting/features/styles (image+video); added 2026-07-23", "@FutureTechPilot", "midjourney-source"),
    ("shorts/algorithm teaching; added 2026-07-23", "@vidIQ", "guru"),
    ("small-channel tactics + packaging teaching; added 2026-07-23", "@nicknimmin", "guru"),
    ("monetization + packaging teaching; added 2026-07-23", "@robertoblake", "guru"),
    ("app-seeded; Big Think channel filtered to Adam Grant videos", "@bigthink", "general-interest"),
    ("app-seeded", "adamgrant.bsky.social", "general-interest"),
])
def test_derive_cohort(note, handle, expected):
    assert derive_cohort(note, handle) == expected


def test_migrate_seeds_all_16_handles_as_validated(conn, tmp_path):
    manifest_path = tmp_path / "brand_sources.json"
    manifest_path.write_text(json.dumps({
        "youtube": [
            {"handle": "@Romayroh", "display_name": "Romayroh", "keyword_filter": None, "note": "guru channel"},
            {"handle": "@JennyHoyos", "display_name": "Jenny Hoyos", "keyword_filter": None, "note": "shorts specialist"},
        ],
        "bluesky": [
            {"handle": "adamgrant.bsky.social", "display_name": "Adam Grant", "note": "app-seeded"},
        ],
        "rss": [],
    }), encoding="utf-8")
    count = migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")
    assert count == 3
    rows = db.list_handles(conn)
    assert len(rows) == 3
    romayroh = db.get_handle_by_platform_and_handle(conn, "youtube", "@Romayroh")
    assert romayroh["status"] == "validated"
    assert romayroh["included"] == 1
    assert romayroh["cohort"] == "guru"
    bluesky_row = db.get_handle_by_platform_and_handle(conn, "bluesky", "adamgrant.bsky.social")
    assert bluesky_row["cohort"] == "general-interest"


def test_migrate_is_idempotent(conn, tmp_path):
    manifest_path = tmp_path / "brand_sources.json"
    manifest_path.write_text(json.dumps({
        "youtube": [{"handle": "@a", "display_name": "A", "keyword_filter": None, "note": "guru channel"}],
        "bluesky": [], "rss": [],
    }), encoding="utf-8")
    migrate(conn, manifest_path, now="2026-07-30T00:00:00Z")
    handle_row = db.get_handle_by_platform_and_handle(conn, "youtube", "@a")
    db.set_handle_status(conn, handle_row["id"], "invalid")  # simulate manual edit
    count = migrate(conn, manifest_path, now="2026-07-30T01:00:00Z")
    assert count == 1
    assert db.get_handle_by_platform_and_handle(conn, "youtube", "@a")["status"] == "invalid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_migrate_handles.py -v`
Expected: FAIL — `scripts.migrate_handles_from_manifest` doesn't exist yet.

- [ ] **Step 3: Write the migration script**

Create `pipeline-app/scripts/__init__.py` (empty file, makes `scripts` importable in tests).

Create `pipeline-app/scripts/migrate_handles_from_manifest.py`:

```python
"""One-off: seed pipeline-app's `handles` table from the repo-root
manifests/brand_sources.json. Read-only against the JSON file and against
output/brand-intel/ -- writes only new `handles` rows. Safe to re-run: uses
INSERT OR IGNORE (see db.upsert_handle_from_migration), so a manual edit made
in the UI after the first run is never overwritten.

Usage: python scripts/migrate_handles_from_manifest.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_app import db  # noqa: E402


def derive_cohort(note: str, handle: str) -> str:
    note_lower = (note or "").lower()
    if "shorts specialist" in note_lower:
        return "shorts-specialist"
    if "midjourney" in note_lower:
        return "midjourney-source"
    if "guru channel" in note_lower:
        return "guru"
    # vidIQ / nicknimmin / robertoblake: algorithm/packaging/monetization
    # teaching notes with no "guru channel" phrase, but the same
    # creator-education shape as the guru entries -- not a shorts exemplar,
    # not a Midjourney source.
    if any(kw in note_lower for kw in ("teaching", "tactics", "monetization")):
        return "guru"
    return "general-interest"


def migrate(conn, manifest_path: Path, now: str) -> int:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    count = 0
    for entry in data.get("youtube", []):
        handle = entry.get("handle")
        if not handle:
            continue
        note = entry.get("note", "")
        db.upsert_handle_from_migration(
            conn, "youtube", handle, entry.get("display_name"),
            derive_cohort(note, handle), entry.get("keyword_filter"),
            status="validated", included=True, added_at=now,
        )
        count += 1
    for entry in data.get("bluesky", []):
        handle = entry.get("handle")
        if not handle:
            continue
        note = entry.get("note", "")
        db.upsert_handle_from_migration(
            conn, "bluesky", handle, entry.get("display_name"),
            derive_cohort(note, handle), None,
            status="validated", included=True, added_at=now,
        )
        count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=None, help="path to brand_sources.json (default: repo-root manifests/)")
    ap.add_argument("--db-path", default=None, help="path to pipeline.db (default: pipeline-app/pipeline.db)")
    args = ap.parse_args()

    pipeline_app_root = Path(__file__).resolve().parents[1]
    repo_root = pipeline_app_root.parent
    manifest_path = Path(args.manifest) if args.manifest else repo_root / "manifests" / "brand_sources.json"
    db_path = Path(args.db_path) if args.db_path else pipeline_app_root / "pipeline.db"

    schema_path = pipeline_app_root / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    count = migrate(conn, manifest_path, now)
    conn.close()
    print(f"migrated {count} handles from {manifest_path} into {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_migrate_handles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/scripts/__init__.py pipeline-app/scripts/migrate_handles_from_manifest.py pipeline-app/tests/test_migrate_handles.py
git commit -m "feat(discovery): add one-off migration script from brand_sources.json to handles table"
```

---

## Task 6: `discovery_paths.py` — slugify + on-disk path helpers

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_paths.py`
- Test: `pipeline-app/tests/test_discovery_paths.py`

**Interfaces:**
- Produces:
  - `slugify(value: str, maxlen: int = 80) -> str` (ported verbatim from `download_brandintel.py:52-56`)
  - `handle_dir(repo_root: Path, platform: str, handle: str) -> Path` — e.g.
    `output/brand-intel/youtube/romayroh/`
  - `run_record_path(repo_root: Path, run_id: str) -> Path` — `output/discovery-runs/<run_id>.md`
- Consumed by: Tasks 7, 8, 9, 11.

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_discovery_paths.py`:

```python
from pathlib import Path

from pipeline_app.discovery_paths import handle_dir, run_record_path, slugify


def test_slugify_basic():
    assert slugify("Romayroh") == "romayroh"
    assert slugify("@FutureTechPilot") == "futuretechpilot"
    assert slugify("Some Title: With Punctuation!") == "some-title-with-punctuation"


def test_handle_dir_youtube(tmp_path: Path):
    result = handle_dir(tmp_path, "youtube", "@Romayroh")
    assert result == tmp_path / "output" / "brand-intel" / "youtube" / "romayroh"


def test_handle_dir_bluesky(tmp_path: Path):
    result = handle_dir(tmp_path, "bluesky", "adamgrant.bsky.social")
    # slugify strips '.' entirely (not in \w, not whitespace, not '-') rather
    # than replacing it with a hyphen -- "adamgrant.bsky.social" collapses to
    # one run-on word. Verified against the actual regex, not assumed.
    assert result == tmp_path / "output" / "brand-intel" / "bluesky" / "adamgrantbskysocial"


def test_run_record_path(tmp_path: Path):
    result = run_record_path(tmp_path, "2026-07-30T06-00-00-0500")
    assert result == tmp_path / "output" / "discovery-runs" / "2026-07-30T06-00-00-0500.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_paths.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

Create `pipeline-app/pipeline_app/discovery_paths.py`:

```python
"""Shared filesystem-path helpers for the discovery engine (Tasks 6-13).
Ported from download_brandintel.py's slugify (that script is left unmodified
-- see the design spec's "Relationship to the existing manual script")."""
from __future__ import annotations

import html
import re
from pathlib import Path


def slugify(value: str, maxlen: int = 80) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    value = re.sub(r"[\s_-]+", "-", value)
    return (value[:maxlen].rstrip("-")) or "untitled"


def handle_dir(repo_root: Path, platform: str, handle: str) -> Path:
    return repo_root / "output" / "brand-intel" / platform / slugify(handle.lstrip("@"))


def run_record_path(repo_root: Path, run_id: str) -> Path:
    return repo_root / "output" / "discovery-runs" / f"{run_id}.md"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_paths.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_paths.py pipeline-app/tests/test_discovery_paths.py
git commit -m "feat(discovery): add slugify/path helpers shared by both platform adapters"
```

---

## Task 7: `discovery_youtube.py` — YouTube platform adapter

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_youtube.py`
- Modify: `pipeline-app/requirements.txt` (add `yt-dlp`, `youtube-transcript-api`)
- Test: `pipeline-app/tests/test_discovery_youtube.py`

**Interfaces:**
- Consumes: `discovery_paths.slugify`/`handle_dir` (Task 6).
- Produces (the YouTube half of the `PlatformAdapter` contract used by Task 9):
  - `on_disk_ids(repo_root: Path, handle: str) -> set[str]`
  - `enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]` — each item
    `{"id": str, "title": str, "published": None}` (YouTube's flat-playlist enumeration never
    carries a date — see spec's Extraction Engine section).
  - `peek_upload_date(video_id: str) -> str | None` — cheap metadata-only fetch (no subtitles), `YYYY-MM-DD` or `None`.
  - `download_item(repo_root: Path, handle: str, video_id: str, title: str) -> dict` — writes the
    `.md` file, returns `{"id": video_id, "ok": bool, "published": "YYYY-MM-DD" | None}`.

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_discovery_youtube.py`:

```python
import json
from pathlib import Path

from pipeline_app import discovery_youtube as yt


def test_on_disk_ids_matches_id_prefix_before_double_underscore(tmp_path: Path):
    handle_dir = tmp_path / "output" / "brand-intel" / "youtube" / "romayroh"
    handle_dir.mkdir(parents=True)
    (handle_dir / "abc123__original-title.md").write_text("x", encoding="utf-8")
    (handle_dir / "def456__retitled-now.md").write_text("x", encoding="utf-8")
    assert yt.on_disk_ids(tmp_path, "@Romayroh") == {"abc123", "def456"}


def test_on_disk_ids_empty_for_new_handle(tmp_path: Path):
    assert yt.on_disk_ids(tmp_path, "@BrandNew") == set()


def test_enumerate_newest_first_applies_keyword_filter(monkeypatch):
    fake_output = json.dumps({"entries": [
        {"id": "v1", "title": "Adam Grant on focus"},
        {"id": "v2", "title": "Unrelated video"},
        {"id": "v3", "title": "adam grant interview"},
    ]})

    class FakeProc:
        returncode = 0
        stdout = fake_output
        stderr = ""

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    items = yt.enumerate_newest_first("@bigthink", keyword_filter="Adam Grant")
    assert [i["id"] for i in items] == ["v1", "v3"]
    assert all(i["published"] is None for i in items)


def test_enumerate_newest_first_no_filter_returns_all(monkeypatch):
    fake_output = json.dumps({"entries": [{"id": "v1", "title": "A"}, {"id": "v2", "title": "B"}]})

    class FakeProc:
        returncode = 0
        stdout = fake_output
        stderr = ""

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    items = yt.enumerate_newest_first("@a", keyword_filter=None)
    assert [i["id"] for i in items] == ["v1", "v2"]


def test_enumerate_newest_first_returns_empty_on_failure(monkeypatch):
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "channel not found"

    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    assert yt.enumerate_newest_first("@dead-handle", keyword_filter=None) == []


def test_peek_upload_date_reads_info_json(monkeypatch, tmp_path):
    def fake_run(cmd, capture_output, text):
        # simulate yt-dlp writing the info.json next to -o's stem
        out_flag_index = cmd.index("-o")
        stem = Path(cmd[out_flag_index + 1].replace(".%(ext)s", ""))
        stem.with_suffix(".info.json").write_text(
            json.dumps({"upload_date": "20260415"}), encoding="utf-8"
        )
        class FakeProc:
            returncode = 0
            stdout = ""
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(yt.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)
    assert yt.peek_upload_date("v1") == "2026-04-15"


def test_peek_upload_date_returns_none_when_no_info_json(monkeypatch, tmp_path):
    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "error"
    monkeypatch.setattr(yt.subprocess, "run", lambda *a, **k: FakeProc())
    monkeypatch.chdir(tmp_path)
    assert yt.peek_upload_date("v1") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_youtube.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Add dependencies and implement**

Add to `pipeline-app/requirements.txt` (after the existing `httpx==0.27.*` line):

```
requests==2.31.*
yt-dlp>=2025.1.1
youtube-transcript-api>=1.0
```

Create `pipeline-app/pipeline_app/discovery_youtube.py`:

```python
"""YouTube platform adapter for the discovery engine. All yt-dlp/network
calls are isolated here so discovery_engine's core algorithm (Task 9) can be
unit-tested against a fake adapter with no network access. Download logic
(vtt parsing, transcript fallback, .md formatting) is ported from
download_brandintel.py's process_youtube_video (that script stays unmodified
-- see the design spec)."""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import datetime as _dt
from pathlib import Path

from pipeline_app.discovery_paths import handle_dir, slugify

USER_AGENT = "ContentStudio-discovery-engine/1.0 (personal archival; local inspection)"


def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    directory = handle_dir(repo_root, "youtube", handle)
    if not directory.exists():
        return set()
    return {p.name.split("__", 1)[0] for p in directory.glob("*__*.md")}


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    url = f"https://www.youtube.com/{handle}/videos"
    cmd = ["yt-dlp", "-J", "--flat-playlist", "--ignore-errors", url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"  ! yt-dlp enumerate failed for {handle}: {proc.stderr.strip()[:200]}", file=sys.stderr)
        return []
    data = json.loads(proc.stdout)
    entries = data.get("entries") or []
    items = [
        {"id": e["id"], "title": e.get("title") or e["id"], "published": None}
        for e in entries if e and e.get("id")
    ]
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["title"].lower()]
    return items


def peek_upload_date(video_id: str) -> str | None:
    tmp_stem = Path(f"_peek_{video_id}")
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp", "--skip-download", "--write-info-json", "--no-warnings",
        "--ignore-errors", "-o", str(tmp_stem) + ".%(ext)s", url,
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    info_path = tmp_stem.with_suffix(".info.json")
    if not info_path.exists():
        return None
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    finally:
        info_path.unlink(missing_ok=True)
    upload_date = info.get("upload_date")
    if not upload_date or len(upload_date) != 8:
        return None
    return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"


def _vtt_to_text(vtt: str) -> str:
    lines_out: list[str] = []
    prev = None
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or line.startswith(("NOTE", "Kind:", "Language:")):
            continue
        if "-->" in line or re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()
        if not line or line == prev:
            continue
        lines_out.append(line)
        prev = line
    return "\n".join(lines_out)


def _fetch_transcript_fallback(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        parts = [getattr(s, "text", "") for s in fetched]
        text = "\n".join(t for t in (p.strip() for p in parts) if t)
        return text or None
    except Exception:
        return None


def download_item(repo_root: Path, handle: str, video_id: str, title: str) -> dict:
    out_dir = handle_dir(repo_root, "youtube", handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = repo_root / "output" / "brand-intel" / "youtube" / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    stem = tmp_dir / video_id
    cmd = [
        "yt-dlp", "--skip-download", "--write-info-json",
        "--write-auto-subs", "--write-subs", "--sub-langs", "en.*",
        "--sub-format", "vtt", "--ignore-errors", "--no-warnings",
        "--retries", "5", "--sleep-requests", "2",
        "-o", str(stem) + ".%(ext)s", url,
    ]
    subprocess.run(cmd, capture_output=True, text=True)

    info = {}
    info_path = stem.with_suffix(".info.json")
    if info_path.exists():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            info = {}

    transcript, source = "", "none"
    vtts = sorted(tmp_dir.glob(f"{video_id}*.vtt"))
    if vtts:
        transcript = _vtt_to_text(vtts[0].read_text(encoding="utf-8", errors="replace"))
        source = "yt-dlp"
    if not transcript:
        fb = _fetch_transcript_fallback(video_id)
        if fb:
            transcript, source = fb, "youtube-transcript-api"

    description = info.get("description") or ""
    upload_date = info.get("upload_date") or ""
    if upload_date and len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    dest = out_dir / f"{video_id}__{slugify(title)}.md"
    md = [
        f"# {title}", "", "## metadata",
        f"- url: {url}", f"- video_id: {video_id}",
        f"- channel: {info.get('uploader') or handle}",
        f"- upload_date: {upload_date}",
        f"- duration_s: {info.get('duration') or ''}",
        f"- transcript_source: {source}", f"- fetched_at: {fetched_at}", "",
        "## description", "", description.strip() or "(none)", "",
        "## transcript", "", transcript.strip() or "(no transcript available)", "",
    ]
    # Write to a temp path and rename into place (atomic on both POSIX and
    # Windows via Path.replace) rather than writing dest directly -- an
    # interrupted write (process killed mid-download) must never leave a
    # truncated file at a path the next run's on_disk_ids() would treat as
    # already-captured.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text("\n".join(md), encoding="utf-8")
    tmp_dest.replace(dest)

    for p in tmp_dir.glob(f"{video_id}*"):
        p.unlink(missing_ok=True)

    return {"id": video_id, "ok": True, "published": upload_date or None}
```

Note: `peek_upload_date` writes its temp `_peek_<id>.info.json` in the process's current working
directory, cleaned up immediately after reading — `run_discovery_cron.py` (Task 14) always runs
with `cwd` set to the repo root, so this never collides with `output/brand-intel/`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_youtube.py -v`
Expected: PASS

Run: `cd pipeline-app && pip install -r requirements.txt` (installs the three new dependencies before any later task that actually invokes real `yt-dlp`).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_youtube.py pipeline-app/requirements.txt pipeline-app/tests/test_discovery_youtube.py
git commit -m "feat(discovery): add YouTube platform adapter (enumerate/peek-date/download)"
```

---

## Task 8: `discovery_bluesky.py` — Bluesky platform adapter

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_bluesky.py`
- Test: `pipeline-app/tests/test_discovery_bluesky.py`

**Interfaces:**
- Consumes: `discovery_paths.handle_dir` (Task 6).
- Produces (the Bluesky half of the `PlatformAdapter` contract used by Task 9):
  - `on_disk_ids(repo_root: Path, handle: str) -> set[str]`
  - `enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]` — each item
    `{"id": rkey, "title": text[:60], "published": "YYYY-MM-DD" | None}` — unlike YouTube, Bluesky's
    `getAuthorFeed` already carries a date per item, so `published` is populated directly
    (`peek_upload_date` is a no-op passthrough for this adapter — see Task 9's use of `item.get("published")`).
  - `peek_upload_date(item_id: str) -> str | None` — always returns `None`. Deliberately given the
    *same single-argument signature* `discovery_engine.process_handle` actually calls
    (`adapter.peek_upload_date(item_id)`, see Task 9) rather than a Bluesky-flavored
    `(handle, item_id, title)` signature — `enumerate_newest_first` already populates `published`
    for every item with a `createdAt`/`indexedAt`, so this is normally dead code, but matching the
    real call site's arity means a Bluesky item that's somehow missing both timestamps degrades to
    "treated as undated, skipped" instead of raising `TypeError` from an arity mismatch.
  - `download_item(repo_root: Path, handle: str, rkey: str, title: str) -> dict`

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_discovery_bluesky.py`:

```python
import json
from pathlib import Path

from pipeline_app import discovery_bluesky as bsky


def test_on_disk_ids_matches_bare_rkey_filename(tmp_path: Path):
    # Matches Task 6's slugify behavior: dots are stripped, not hyphenated.
    handle_dir = tmp_path / "output" / "brand-intel" / "bluesky" / "adamgrantbskysocial"
    handle_dir.mkdir(parents=True)
    (handle_dir / "3abc123.md").write_text("x", encoding="utf-8")
    assert bsky.on_disk_ids(tmp_path, "adamgrant.bsky.social") == {"3abc123"}


def test_enumerate_newest_first_paginates_and_populates_published(monkeypatch):
    pages = [
        {
            "feed": [
                {"post": {"uri": "at://did/app.bsky.feed.post/rkey1",
                          "record": {"text": "first post", "createdAt": "2026-07-29T10:00:00Z"}}},
            ],
            "cursor": "page2",
        },
        {
            "feed": [
                {"post": {"uri": "at://did/app.bsky.feed.post/rkey2",
                          "record": {"text": "second post", "createdAt": "2026-07-20T10:00:00Z"}}},
            ],
        },
    ]
    call_count = {"n": 0}

    def fake_http_get(url):
        page = pages[call_count["n"]]
        call_count["n"] += 1
        return json.dumps(page).encode("utf-8")

    monkeypatch.setattr(bsky, "_http_get", fake_http_get)
    items = bsky.enumerate_newest_first("adamgrant.bsky.social", keyword_filter=None)
    assert [i["id"] for i in items] == ["rkey1", "rkey2"]
    assert items[0]["published"] == "2026-07-29"
    assert items[1]["published"] == "2026-07-20"


def test_enumerate_newest_first_skips_reposts(monkeypatch):
    page = {"feed": [
        {"reason": {"$type": "app.bsky.feed.defs#reasonRepost"},
         "post": {"uri": "at://did/app.bsky.feed.post/repost1", "record": {"text": "x", "createdAt": "2026-07-29T10:00:00Z"}}},
        {"post": {"uri": "at://did/app.bsky.feed.post/real1", "record": {"text": "y", "createdAt": "2026-07-28T10:00:00Z"}}},
    ]}
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(page).encode("utf-8"))
    items = bsky.enumerate_newest_first("adamgrant.bsky.social", keyword_filter=None)
    assert [i["id"] for i in items] == ["real1"]


def test_enumerate_newest_first_returns_empty_on_fetch_failure(monkeypatch):
    def raise_error(url):
        raise OSError("network down")
    monkeypatch.setattr(bsky, "_http_get", raise_error)
    assert bsky.enumerate_newest_first("dead.bsky.social", keyword_filter=None) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_bluesky.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

Create `pipeline-app/pipeline_app/discovery_bluesky.py`:

```python
"""Bluesky platform adapter for the discovery engine. Isolates the public
AppView HTTP call so discovery_engine's core algorithm (Task 9) can be
unit-tested with no network access. Download logic ported from
download_brandintel.py's do_bluesky (that script stays unmodified)."""
from __future__ import annotations

import datetime as _dt
import json
import urllib.parse
import urllib.request
from pathlib import Path

from pipeline_app.discovery_paths import handle_dir

BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
USER_AGENT = "ContentStudio-discovery-engine/1.0 (personal archival; local inspection)"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    directory = handle_dir(repo_root, "bluesky", handle)
    if not directory.exists():
        return set()
    return {p.stem for p in directory.glob("*.md")}


def enumerate_newest_first(handle: str, keyword_filter: str | None, page_limit: int = 5) -> list[dict]:
    items: list[dict] = []
    cursor = None
    for _ in range(page_limit):
        params = {"actor": handle, "limit": "100"}
        if cursor:
            params["cursor"] = cursor
        try:
            data = json.loads(_http_get(f"{BLUESKY_API}?{urllib.parse.urlencode(params)}"))
        except Exception:
            break
        feed = data.get("feed") or []
        if not feed:
            break
        for entry in feed:
            if entry.get("reason"):  # skip reposts
                continue
            post = entry.get("post") or {}
            record = post.get("record") or {}
            uri = post.get("uri") or ""
            rkey = uri.rsplit("/", 1)[-1] if uri else ""
            if not rkey:
                continue
            text = (record.get("text") or "").strip()
            created = record.get("createdAt") or post.get("indexedAt") or ""
            published = created[:10] if len(created) >= 10 else None
            items.append({"id": rkey, "title": text[:60], "published": published})
        cursor = data.get("cursor")
        if not cursor:
            break
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["title"].lower()]
    return items


def peek_upload_date(item_id: str) -> str | None:
    return None  # normally dead code: enumerate_newest_first always populates 'published'


def download_item(repo_root: Path, handle: str, rkey: str, title: str) -> dict:
    out_dir = handle_dir(repo_root, "bluesky", handle)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Re-fetch this single item's full record for the post text and exact
    # created-at (enumerate_newest_first only carries a truncated title).
    items = enumerate_newest_first(handle, keyword_filter=None, page_limit=5)
    match = next((i for i in items if i["id"] == rkey), None)
    published = match["published"] if match else None
    purl = f"https://bsky.app/profile/{handle}/post/{rkey}"
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    dest = out_dir / f"{rkey}.md"
    md = [
        f"# bluesky post {rkey}", "",
        f"- url: {purl}", f"- author: {handle}",
        f"- created: {published or ''}", f"- fetched_at: {fetched_at}", "",
        title or "(empty)", "",
    ]
    # Write-temp-then-rename, same as discovery_youtube.download_item (Task 7)
    # -- see that task's comment for why.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text("\n".join(md), encoding="utf-8")
    tmp_dest.replace(dest)
    return {"id": rkey, "ok": True, "published": published}
```

Note: `download_item`'s single-item re-fetch (rather than passing the full post text through from
`enumerate_newest_first`) is a deliberate simplification — Bluesky posts are short (a few hundred
characters max), so re-enumerating is cheap, and it keeps the `PlatformAdapter.download_item`
signature identical across both platforms (`handle, item_id, title -> dict`) rather than requiring
the engine to thread extra per-item state through.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_bluesky.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_bluesky.py pipeline-app/tests/test_discovery_bluesky.py
git commit -m "feat(discovery): add Bluesky platform adapter"
```

---

## Task 9: `discovery_engine.py` — `process_handle` (core early-stop algorithm)

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_engine.py`
- Test: `pipeline-app/tests/test_discovery_engine.py`

**Interfaces:**
- Consumes: nothing concrete — this task defines `PlatformAdapter` as a `Protocol` and tests
  exclusively against a hand-written `FakeAdapter`, so it has zero dependency on Tasks 7/8's real
  adapters (those are wired in at Task 11).
- Produces:
  - `PlatformAdapter` (a `typing.Protocol` with `on_disk_ids`, `enumerate_newest_first`,
    `peek_upload_date`, `download_item` matching Tasks 7/8's signatures)
  - `process_handle(adapter: PlatformAdapter, repo_root: Path, handle_row: sqlite3.Row, now: datetime) -> list[dict]` — returns the list of `download_item` results for everything downloaded this call. Implements the newest-first early-stop walk from the spec (3 consecutive on-disk hits for existing handles; 3-month-old cutoff for brand-new handles).

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_discovery_engine.py`:

```python
import datetime as _dt

from pipeline_app.discovery_engine import process_handle


class FakeHandleRow(dict):
    """Stands in for a sqlite3.Row for handle_row['handle'] / ['keyword_filter'] access."""
    def __getitem__(self, key):
        return dict.get(self, key)


class FakeAdapter:
    def __init__(self, enumerated, on_disk, dates=None):
        self._enumerated = enumerated  # list of {"id","title","published"}
        self._on_disk = set(on_disk)
        self._dates = dates or {}      # id -> "YYYY-MM-DD", used by peek_upload_date
        self.downloaded_ids = []
        self.peek_calls = []

    def on_disk_ids(self, repo_root, handle):
        return self._on_disk

    def enumerate_newest_first(self, handle, keyword_filter):
        items = self._enumerated
        if keyword_filter:
            items = [i for i in items if keyword_filter.lower() in i["title"].lower()]
        return items

    def peek_upload_date(self, video_id):
        self.peek_calls.append(video_id)
        return self._dates.get(video_id)

    def download_item(self, repo_root, handle, item_id, title):
        self.downloaded_ids.append(item_id)
        return {"id": item_id, "ok": True, "published": self._dates.get(item_id)}


NOW = _dt.datetime(2026, 7, 30, tzinfo=_dt.timezone.utc)


def test_existing_handle_downloads_new_items_and_stops_after_3_consecutive_on_disk():
    enumerated = [
        {"id": "n3", "title": "new 3", "published": None},
        {"id": "n2", "title": "new 2", "published": None},
        {"id": "n1", "title": "new 1", "published": None},
        {"id": "old3", "title": "old 3", "published": None},
        {"id": "old2", "title": "old 2", "published": None},
        {"id": "old1", "title": "old 1", "published": None},
        {"id": "never_reached", "title": "should not be seen", "published": None},
    ]
    adapter = FakeAdapter(enumerated, on_disk={"old1", "old2", "old3"})
    results = process_handle(adapter, None, FakeHandleRow(handle="@a", keyword_filter=None), now=NOW)
    assert [r["id"] for r in results] == ["n3", "n2", "n1"]
    assert "never_reached" not in adapter.downloaded_ids


def test_existing_handle_tolerates_one_out_of_order_hit():
    enumerated = [
        {"id": "n1", "title": "new", "published": None},
        {"id": "old1", "title": "old, out of order", "published": None},  # single stray hit
        {"id": "n2", "title": "new after the gap", "published": None},
        {"id": "old2", "title": "old", "published": None},
        {"id": "old3", "title": "old", "published": None},
        {"id": "old4", "title": "old", "published": None},
    ]
    adapter = FakeAdapter(enumerated, on_disk={"old1", "old2", "old3", "old4"})
    results = process_handle(adapter, None, FakeHandleRow(handle="@a", keyword_filter=None), now=NOW)
    assert [r["id"] for r in results] == ["n1", "n2"]


def test_existing_handle_with_no_new_content_stops_immediately():
    enumerated = [
        {"id": "old1", "title": "old", "published": None},
        {"id": "old2", "title": "old", "published": None},
        {"id": "old3", "title": "old", "published": None},
        {"id": "never_reached", "title": "x", "published": None},
    ]
    adapter = FakeAdapter(enumerated, on_disk={"old1", "old2", "old3"})
    results = process_handle(adapter, None, FakeHandleRow(handle="@a", keyword_filter=None), now=NOW)
    assert results == []


def test_new_handle_downloads_until_3_months_old_using_peek(): 
    enumerated = [
        {"id": "v1", "title": "recent", "published": None},
        {"id": "v2", "title": "just inside window", "published": None},
        {"id": "v3", "title": "just outside window", "published": None},
        {"id": "v4", "title": "very old, never reached", "published": None},
    ]
    dates = {
        "v1": "2026-07-25",
        "v2": "2026-05-05",   # within 90 days of 2026-07-30
        "v3": "2026-04-01",   # older than 90 days
    }
    adapter = FakeAdapter(enumerated, on_disk=set(), dates=dates)
    results = process_handle(adapter, None, FakeHandleRow(handle="@new", keyword_filter=None), now=NOW)
    assert [r["id"] for r in results] == ["v1", "v2"]
    assert "v4" not in adapter.peek_calls


def test_new_handle_uses_prepopulated_published_date_without_peeking():
    enumerated = [
        {"id": "v1", "title": "recent bluesky post", "published": "2026-07-25"},
        {"id": "v2", "title": "old bluesky post", "published": "2026-01-01"},
    ]
    adapter = FakeAdapter(enumerated, on_disk=set())
    results = process_handle(adapter, None, FakeHandleRow(handle="@new", keyword_filter=None), now=NOW)
    assert [r["id"] for r in results] == ["v1"]
    assert adapter.peek_calls == []  # published was already present; peek never called


def test_new_handle_skips_item_when_peek_returns_none():
    enumerated = [
        {"id": "v1", "title": "undated", "published": None},
        {"id": "v2", "title": "dated", "published": None},
    ]
    adapter = FakeAdapter(enumerated, on_disk=set(), dates={"v2": "2026-07-20"})
    results = process_handle(adapter, None, FakeHandleRow(handle="@new", keyword_filter=None), now=NOW)
    assert [r["id"] for r in results] == ["v2"]


def test_keyword_filter_applied_before_the_walk():
    enumerated = [
        {"id": "v1", "title": "Adam Grant on focus", "published": None},
        {"id": "v2", "title": "unrelated", "published": None},
    ]
    adapter = FakeAdapter(enumerated, on_disk=set(), dates={"v1": "2026-07-25"})
    results = process_handle(
        adapter, None, FakeHandleRow(handle="@bigthink", keyword_filter="Adam Grant"), now=NOW
    )
    assert [r["id"] for r in results] == ["v1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_engine.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

Create `pipeline-app/pipeline_app/discovery_engine.py`:

```python
"""Core discovery orchestration: the platform-agnostic early-stop dedup walk
(process_handle), backfill/validate variants (Task 10), and the run
orchestrator (Task 11). process_handle takes no repo_root-typed dependency
on a real adapter -- it is tested entirely against a FakeAdapter with no
network access; discovery_youtube/discovery_bluesky (Tasks 7-8) are wired in
at Task 11 via the ADAPTERS registry."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Protocol

NEW_HANDLE_LOOKBACK_DAYS = 90
EXISTING_HANDLE_STOP_GRACE = 3


class PlatformAdapter(Protocol):
    def on_disk_ids(self, repo_root: Path, handle: str) -> set[str]: ...
    def enumerate_newest_first(self, handle: str, keyword_filter: str | None) -> list[dict]: ...
    def peek_upload_date(self, *args) -> str | None: ...
    def download_item(self, repo_root: Path, handle: str, item_id: str, title: str) -> dict: ...


def process_handle(adapter: PlatformAdapter, repo_root: Path, handle_row, now: _dt.datetime) -> list[dict]:
    handle = handle_row["handle"]
    keyword_filter = handle_row["keyword_filter"]
    on_disk = adapter.on_disk_ids(repo_root, handle)
    is_new = len(on_disk) == 0
    cutoff = now - _dt.timedelta(days=NEW_HANDLE_LOOKBACK_DAYS) if is_new else None

    enumerated = adapter.enumerate_newest_first(handle, keyword_filter)
    downloaded: list[dict] = []
    consecutive_on_disk = 0

    for item in enumerated:
        item_id = item["id"]
        if item_id in on_disk:
            consecutive_on_disk += 1
            if not is_new and consecutive_on_disk >= EXISTING_HANDLE_STOP_GRACE:
                break
            continue
        consecutive_on_disk = 0

        if is_new:
            published = item.get("published") or adapter.peek_upload_date(item_id)
            if published is None:
                continue
            if _dt.datetime.strptime(published, "%Y-%m-%d").replace(tzinfo=_dt.timezone.utc) < cutoff:
                break

        result = adapter.download_item(repo_root, handle, item_id, item["title"])
        if result.get("ok"):
            downloaded.append(result)

    return downloaded
```

Note: `FakeAdapter.peek_upload_date` in the tests above takes only `video_id`/`item_id`, matching
both real adapters' actual signatures — Task 7's YouTube `peek_upload_date(video_id)` and Task 8's
Bluesky `peek_upload_date(item_id)` are single-argument by design specifically so `process_handle`'s
`adapter.peek_upload_date(item_id)` call works identically against either real adapter (Task 8's is
normally unreachable since Bluesky always populates `published` at enumeration time, but matching
arity means it degrades gracefully — "treated as undated" — rather than raising `TypeError` in the
rare case it is reached).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_engine.py pipeline-app/tests/test_discovery_engine.py
git commit -m "feat(discovery): add process_handle newest-first early-stop dedup algorithm"
```

---

## Task 10: `discovery_engine.py` — `process_handle_backfill` and `process_handle_validate`

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_engine.py` (append functions)
- Test: `pipeline-app/tests/test_discovery_engine.py` (append tests, reusing `FakeAdapter`/`FakeHandleRow`)

**Interfaces:**
- Consumes: `PlatformAdapter`, `FakeAdapter`/`FakeHandleRow` test doubles from Task 9.
- Produces:
  - `process_handle_backfill(adapter, repo_root, handle_row, start_date: _dt.date, end_date: _dt.date) -> list[dict]`
  - `process_handle_validate(adapter, repo_root, handle_row) -> dict` — `{"ok": bool, "item": dict | None}`; `ok=False` means enumeration returned nothing (handle not found).

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_discovery_engine.py`:

```python
import datetime as _dt

from pipeline_app.discovery_engine import process_handle_backfill, process_handle_validate


def test_backfill_downloads_only_items_in_range_and_not_on_disk():
    enumerated = [
        {"id": "v1", "title": "too new", "published": "2026-07-29"},
        {"id": "v2", "title": "in range", "published": "2026-06-15"},
        {"id": "v3", "title": "already on disk, in range", "published": "2026-06-10"},
        {"id": "v4", "title": "too old", "published": "2026-01-01"},
    ]
    adapter = FakeAdapter(enumerated, on_disk={"v3"})
    results = process_handle_backfill(
        adapter, None, FakeHandleRow(handle="@a", keyword_filter=None),
        start_date=_dt.date(2026, 6, 1), end_date=_dt.date(2026, 6, 30),
    )
    assert [r["id"] for r in results] == ["v2"]


def test_backfill_uses_peek_when_published_missing():
    enumerated = [{"id": "v1", "title": "x", "published": None}]
    adapter = FakeAdapter(enumerated, on_disk=set(), dates={"v1": "2026-06-15"})
    results = process_handle_backfill(
        adapter, None, FakeHandleRow(handle="@a", keyword_filter=None),
        start_date=_dt.date(2026, 6, 1), end_date=_dt.date(2026, 6, 30),
    )
    assert [r["id"] for r in results] == ["v1"]


def test_validate_downloads_single_most_recent_item():
    enumerated = [{"id": "v1", "title": "newest", "published": "2026-07-29"}]
    adapter = FakeAdapter(enumerated, on_disk=set())
    result = process_handle_validate(adapter, None, FakeHandleRow(handle="@new", keyword_filter=None))
    assert result["ok"] is True
    assert result["item"]["id"] == "v1"
    assert adapter.downloaded_ids == ["v1"]


def test_validate_reports_not_ok_when_enumeration_empty():
    adapter = FakeAdapter(enumerated=[], on_disk=set())
    result = process_handle_validate(adapter, None, FakeHandleRow(handle="@dead", keyword_filter=None))
    assert result["ok"] is False
    assert result["item"] is None
    assert adapter.downloaded_ids == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_engine.py -k "backfill or validate" -v`
Expected: FAIL — functions don't exist yet.

- [ ] **Step 3: Implement**

Append to `pipeline-app/pipeline_app/discovery_engine.py`:

```python
def process_handle_backfill(adapter: PlatformAdapter, repo_root: Path, handle_row, start_date, end_date) -> list[dict]:
    handle = handle_row["handle"]
    keyword_filter = handle_row["keyword_filter"]
    on_disk = adapter.on_disk_ids(repo_root, handle)
    enumerated = adapter.enumerate_newest_first(handle, keyword_filter)
    downloaded: list[dict] = []

    for item in enumerated:
        item_id = item["id"]
        if item_id in on_disk:
            continue
        published = item.get("published") or adapter.peek_upload_date(item_id)
        if published is None:
            continue
        pub_date = _dt.datetime.strptime(published, "%Y-%m-%d").date()
        if pub_date < start_date or pub_date > end_date:
            continue
        result = adapter.download_item(repo_root, handle, item_id, item["title"])
        if result.get("ok"):
            downloaded.append(result)

    return downloaded


def process_handle_validate(adapter: PlatformAdapter, repo_root: Path, handle_row) -> dict:
    handle = handle_row["handle"]
    keyword_filter = handle_row["keyword_filter"]
    enumerated = adapter.enumerate_newest_first(handle, keyword_filter)
    if not enumerated:
        return {"ok": False, "item": None}
    newest = enumerated[0]
    result = adapter.download_item(repo_root, handle, newest["id"], newest["title"])
    return {"ok": bool(result.get("ok")), "item": result if result.get("ok") else None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_engine.py pipeline-app/tests/test_discovery_engine.py
git commit -m "feat(discovery): add backfill and validate_handle process functions"
```

---

## Task 11: `discovery_records.py` — paired Markdown run record writer

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_records.py`
- Test: `pipeline-app/tests/test_discovery_records.py`

**Interfaces:**
- Consumes: `discovery_paths.run_record_path` (Task 6).
- Produces: `write_run_record(repo_root: Path, run_row: dict, handle_results: list[dict]) -> Path` —
  `run_row` has keys `run_id, trigger, mode, status, started_at, finished_at, backfill_start, backfill_end`;
  each `handle_results` entry has keys `handle, platform, cohort, status, items_downloaded, last_seen_published_at, error_message`.
  Writes the file and returns its path.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_discovery_records.py`:

```python
from pathlib import Path

import yaml

from pipeline_app.discovery_records import write_run_record


def test_write_run_record_creates_file_with_frontmatter_and_summary(tmp_path: Path):
    run_row = {
        "run_id": "2026-07-30T06-00-00-0500", "trigger": "scheduled", "mode": "incremental",
        "status": "completed_with_errors", "started_at": "2026-07-30T06:00:00-05:00",
        "finished_at": "2026-07-30T06:04:12-05:00", "backfill_start": None, "backfill_end": None,
    }
    handle_results = [
        {"handle": "@Romayroh", "platform": "youtube", "cohort": "guru", "status": "ok",
         "items_downloaded": 2, "last_seen_published_at": "2026-07-28", "error_message": None},
        {"handle": "@ThatNateBlack", "platform": "youtube", "cohort": "shorts-specialist",
         "status": "no_new_content", "items_downloaded": 0, "last_seen_published_at": None, "error_message": None},
        {"handle": "@dead-handle", "platform": "youtube", "cohort": "guru", "status": "handle_not_found",
         "items_downloaded": 0, "last_seen_published_at": None,
         "error_message": "yt-dlp enumerate returned empty"},
    ]
    path = write_run_record(tmp_path, run_row, handle_results)
    assert path == tmp_path / "output" / "discovery-runs" / "2026-07-30T06-00-00-0500.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter_text = text.split("---\n")[1]
    frontmatter = yaml.safe_load(frontmatter_text)
    assert frontmatter["handles_processed"] == 3
    assert frontmatter["items_downloaded"] == 2
    assert frontmatter["handles_ok"] == 1
    assert frontmatter["handles_no_new_content"] == 1
    assert frontmatter["handles_not_found"] == 1
    assert frontmatter["handles_errored"] == 0
    assert "@Romayroh" in text
    assert "yt-dlp enumerate returned empty" in text
    # never includes actual transcript/description content:
    assert "no transcript available" not in text


def test_write_run_record_creates_parent_directory(tmp_path: Path):
    run_row = {
        "run_id": "r1", "trigger": "manual", "mode": "backfill", "status": "completed",
        "started_at": "2026-07-30T06:00:00Z", "finished_at": "2026-07-30T06:01:00Z",
        "backfill_start": "2026-06-01", "backfill_end": "2026-06-30",
    }
    path = write_run_record(tmp_path, run_row, [])
    assert path.exists()
    frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---\n")[1])
    assert frontmatter["backfill_range"] == {"start": "2026-06-01", "end": "2026-06-30"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_records.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

Create `pipeline-app/pipeline_app/discovery_records.py`:

```python
"""Writes the paired output/discovery-runs/<run_id>.md record for a
finished discovery run. Never includes extracted transcript/description
text -- only counts, statuses, and handle identifiers."""
from __future__ import annotations

from pathlib import Path

import yaml

from pipeline_app.discovery_paths import run_record_path


def write_run_record(repo_root: Path, run_row: dict, handle_results: list[dict]) -> Path:
    status_counts = {"ok": 0, "no_new_content": 0, "handle_not_found": 0, "error": 0}
    items_downloaded = 0
    for r in handle_results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        items_downloaded += r["items_downloaded"]

    backfill_range = None
    if run_row.get("backfill_start"):
        backfill_range = {"start": run_row["backfill_start"], "end": run_row["backfill_end"]}

    frontmatter = {
        "run_id": run_row["run_id"],
        "trigger": run_row["trigger"],
        "mode": run_row["mode"],
        "status": run_row["status"],
        "started_at": run_row["started_at"],
        "finished_at": run_row["finished_at"],
        "backfill_range": backfill_range,
        "handles_processed": len(handle_results),
        "items_downloaded": items_downloaded,
        "handles_ok": status_counts["ok"],
        "handles_no_new_content": status_counts["no_new_content"],
        "handles_not_found": status_counts["handle_not_found"],
        "handles_errored": status_counts["error"],
    }

    lines = ["---", yaml.safe_dump(frontmatter, sort_keys=False).rstrip("\n"), "---", "",
              "## Summary", "",
              f"Pulled {items_downloaded} new items across {status_counts['ok']} handles with "
              f"new content. {status_counts['handle_not_found']} handle(s) not found, "
              f"{status_counts['error']} errored.", "",
              "## Per-handle results", ""]
    for r in handle_results:
        detail = f"{r['items_downloaded']} new items" if r["status"] == "ok" else r["status"]
        if r.get("last_seen_published_at"):
            detail += f", last_seen now {r['last_seen_published_at']}"
        if r.get("error_message"):
            detail += f": {r['error_message']}"
        lines.append(f"- {r['handle']} ({r['platform']}, {r['cohort']}) — {detail}")

    dest = run_record_path(repo_root, run_row["run_id"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_records.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_records.py pipeline-app/tests/test_discovery_records.py
git commit -m "feat(discovery): add paired markdown run-record writer"
```

---

## Task 12: `discovery_engine.py` — `run_discovery` orchestrator (lock, resiliency, heartbeat)

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_engine.py` (append)
- Test: `pipeline-app/tests/test_discovery_engine.py` (append)

**Interfaces:**
- Consumes: `db.py` functions from Tasks 2-4, `process_handle`/`process_handle_backfill`/`process_handle_validate`
  (Tasks 9-10), `discovery_records.write_run_record` (Task 11), `PlatformAdapter` (Task 9).
- Produces:
  - `now_iso(now: _dt.datetime | None = None) -> str` — small helper used throughout (`datetime.isoformat(timespec="seconds")`).
  - `make_run_id(now: _dt.datetime) -> str` — e.g. `2026-07-30T06-00-00+0000`.
  - `run_discovery(conn, repo_root: Path, adapters: dict[str, PlatformAdapter], trigger: str, mode: str, backfill_start: str | None = None, backfill_end: str | None = None, handle_id: int | None = None, now: _dt.datetime | None = None, heartbeat_interval_s: float = 30.0, stale_after_s: int = 600) -> dict` —
    the single entry point every trigger (Task 14's CLI) calls. Returns `{"run_row_id": int, "status": str}`.
    - `mode='validate_handle'` requires `handle_id`; bypasses the lock entirely (no `running` row —
      see Task 10/spec's "Concurrency" section) and processes exactly that one handle synchronously.
    - `mode in ('incremental', 'backfill')` reclaims stale runs, then attempts the lock; on
      `IntegrityError` records a `locked` run and returns immediately without processing any handles.
    - On success, spawns a background heartbeat thread, iterates `db.list_handles(conn, included_only=True)`
      (or, for backfill, the same list with backfill dates), wraps each handle in try/except, records
      a `discovery_run_handles` row per handle, updates `handles.last_seen_published_at` on success,
      computes final run status (`completed`/`completed_with_errors`), stops the heartbeat thread,
      writes the paired record via `discovery_records.write_run_record`, and calls `db.finish_run`.

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_discovery_engine.py`:

```python
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from pipeline_app import db
from pipeline_app.discovery_engine import make_run_id, now_iso, run_discovery


@pytest.fixture
def engine_conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


class SingleFakeAdapter:
    """One FakeAdapter reused for every handle in a run_discovery test."""
    def __init__(self, enumerated_by_handle, on_disk_by_handle=None, fail_handles=None):
        self._enumerated = enumerated_by_handle
        self._on_disk = on_disk_by_handle or {}
        self._fail = set(fail_handles or [])

    def on_disk_ids(self, repo_root, handle):
        return self._on_disk.get(handle, set())

    def enumerate_newest_first(self, handle, keyword_filter):
        if handle in self._fail:
            raise RuntimeError(f"simulated enumerate failure for {handle}")
        return self._enumerated.get(handle, [])

    def peek_upload_date(self, item_id):
        # Every test handle in this fixture is "brand new" (empty on_disk_ids
        # by default), so process_handle's new-handle branch always needs a
        # date to pass the 3-month cutoff check before it will call
        # download_item at all -- return a fixed recent date rather than None,
        # or every item gets silently skipped and no test here would ever
        # observe a download. (Tests that care about the exact date-cutoff
        # boundary use Task 9's own FakeAdapter with an explicit `dates` dict.)
        return "2026-07-29"

    def download_item(self, repo_root, handle, item_id, title):
        return {"id": item_id, "ok": True, "published": "2026-07-29"}


def test_now_iso_and_make_run_id_are_stable_format():
    now = __import__("datetime").datetime(2026, 7, 30, 6, 0, 0, tzinfo=__import__("datetime").timezone.utc)
    assert now_iso(now) == "2026-07-30T06:00:00+00:00"
    run_id = make_run_id(now)
    assert run_id.startswith("2026-07-30T06-00-00")


def test_run_discovery_completes_and_writes_record(engine_conn, tmp_path):
    handle_id = db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]})
    now = __import__("datetime").datetime(2026, 7, 30, 6, 0, 0, tzinfo=__import__("datetime").timezone.utc)

    result = run_discovery(
        engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental", now=now,
    )
    assert result["status"] == "completed"
    run_row = db.get_run(engine_conn, result["run_row_id"])
    assert run_row["status"] == "completed"
    assert run_row["md_path"] is not None
    assert Path(run_row["md_path"]).exists() or (tmp_path / run_row["md_path"]).exists()
    results = db.list_run_handle_results(engine_conn, result["run_row_id"])
    assert len(results) == 1
    assert results[0]["status"] == "ok"
    assert results[0]["items_downloaded"] == 1
    assert db.get_handle(engine_conn, handle_id)["last_seen_published_at"] == "2026-07-29"


def test_run_discovery_excludes_handles_with_included_false(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    excluded_id = db.create_handle(engine_conn, "youtube", "@b", "B", "guru", None, now_iso())
    db.set_handle_included(engine_conn, excluded_id, False)
    adapter = SingleFakeAdapter({
        "@a": [{"id": "v1", "title": "x", "published": None}],
        "@b": [{"id": "v2", "title": "y", "published": None}],
    })
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")
    results = db.list_run_handle_results(engine_conn, result["run_row_id"])
    assert len(results) == 1  # only @a


def test_run_discovery_one_bad_handle_does_not_abort_the_run(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@good", "Good", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "@bad", "Bad", "guru", None, now_iso())
    adapter = SingleFakeAdapter(
        {"@good": [{"id": "v1", "title": "x", "published": None}]},
        fail_handles={"@bad"},
    )
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")
    assert result["status"] == "completed_with_errors"
    results = {r["handle_id"]: r["status"] for r in db.list_run_handle_results(engine_conn, result["run_row_id"])}
    assert list(results.values()).count("ok") == 1
    assert list(results.values()).count("error") == 1


def test_run_discovery_no_new_content_records_that_status(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": []})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")
    results = db.list_run_handle_results(engine_conn, result["run_row_id"])
    assert results[0]["status"] == "no_new_content"
    assert result["status"] == "completed"


def test_run_discovery_second_concurrent_call_is_locked(engine_conn, tmp_path):
    # Simulate a run already in progress by inserting a running row directly.
    db.insert_running_run(engine_conn, "already-running", "manual", "incremental", now_iso())
    adapter = SingleFakeAdapter({})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")
    assert result["status"] == "locked"
    assert db.list_run_handle_results(engine_conn, result["run_row_id"]) == []
    locked_row = db.get_run(engine_conn, result["run_row_id"])
    assert locked_row["md_path"] is not None  # locked runs still get a paired record


def test_run_discovery_reclaims_stale_run_and_writes_abandoned_record(engine_conn, tmp_path):
    stale_started = "2026-07-30T05:00:00+00:00"
    stale_id = db.insert_running_run(engine_conn, "stale-run", "manual", "incremental", stale_started)
    db.update_run_heartbeat(engine_conn, stale_id, "2026-07-30T05:01:00+00:00")
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]})
    now = __import__("datetime").datetime(2026, 7, 30, 6, 0, 0, tzinfo=__import__("datetime").timezone.utc)

    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental", now=now)
    assert result["status"] == "completed"  # the new run itself succeeds
    stale_row = db.get_run(engine_conn, stale_id)
    assert stale_row["status"] == "abandoned"
    assert stale_row["md_path"] is not None


def test_run_discovery_validate_handle_bypasses_lock_while_a_run_is_active(engine_conn, tmp_path):
    db.insert_running_run(engine_conn, "already-running", "manual", "incremental", now_iso())
    handle_id = db.create_handle(engine_conn, "youtube", "@new", "New", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@new": [{"id": "v1", "title": "x", "published": "2026-07-29"}]})
    result = run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    assert result["status"] in ("completed",)
    assert db.get_handle(engine_conn, handle_id)["status"] == "validated"
    # the still-running incremental run's lock row is untouched
    assert db.get_running_run(engine_conn)["run_id"] == "already-running"


def test_run_discovery_validate_handle_sets_invalid_and_excludes_on_empty_enumeration(engine_conn, tmp_path):
    handle_id = db.create_handle(engine_conn, "youtube", "@dead", "Dead", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@dead": []})
    run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    row = db.get_handle(engine_conn, handle_id)
    assert row["status"] == "invalid"
    assert row["included"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_engine.py -k run_discovery -v`
Expected: FAIL — `run_discovery`/`now_iso`/`make_run_id` don't exist yet.

- [ ] **Step 3: Implement**

Append to `pipeline-app/pipeline_app/discovery_engine.py`:

```python
import sqlite3
import threading

from pipeline_app import db as db_mod
from pipeline_app.discovery_records import write_run_record


def now_iso(now: _dt.datetime | None = None) -> str:
    return (now or _dt.datetime.now(_dt.timezone.utc)).isoformat(timespec="seconds")


def make_run_id(now: _dt.datetime) -> str:
    # Microsecond resolution, not just seconds: two processes can legitimately
    # start in the same second (a manual "Run Now" fired moments after the
    # scheduled trigger, or a validate_handle spawned alongside an
    # incremental run), and run_id is UNIQUE -- a second-resolution id would
    # raise an uncaught IntegrityError completely unrelated to the intended
    # single-flight lock on status='running'.
    return now.strftime("%Y-%m-%dT%H-%M-%S-%f%z")


def _write_abandoned_records_for_reclaimed_runs(conn: sqlite3.Connection, repo_root: Path, reclaimed_ids: list[int], now: _dt.datetime) -> None:
    for reclaimed_id in reclaimed_ids:
        reclaimed_row = db_mod.get_run(conn, reclaimed_id)
        finished_at = now_iso(now)
        md_path = write_run_record(repo_root, {
            "run_id": reclaimed_row["run_id"], "trigger": reclaimed_row["trigger"], "mode": reclaimed_row["mode"],
            "status": "abandoned", "started_at": reclaimed_row["started_at"], "finished_at": finished_at,
            "backfill_start": reclaimed_row["backfill_start"], "backfill_end": reclaimed_row["backfill_end"],
        }, [])  # no handle_results: we don't know how far the dead process got
        db_mod.finish_run(conn, reclaimed_id, "abandoned", finished_at, str(md_path))


def _run_heartbeat_loop(conn: sqlite3.Connection, run_row_id: int, interval_s: float, stop_event: threading.Event) -> None:
    while not stop_event.wait(interval_s):
        db_mod.update_run_heartbeat(conn, run_row_id, now_iso())


def _process_one_handle(adapters: dict, repo_root, handle_row, mode, backfill_start, backfill_end, now):
    adapter = adapters[handle_row["platform"]]
    if mode == "backfill":
        return process_handle_backfill(
            adapter, repo_root, handle_row,
            start_date=_dt.datetime.strptime(backfill_start, "%Y-%m-%d").date(),
            end_date=_dt.datetime.strptime(backfill_end, "%Y-%m-%d").date(),
        )
    return process_handle(adapter, repo_root, handle_row, now=now)


def run_discovery(
    conn: sqlite3.Connection, repo_root: Path, adapters: dict[str, PlatformAdapter],
    trigger: str, mode: str, backfill_start: str | None = None, backfill_end: str | None = None,
    handle_id: int | None = None, now: _dt.datetime | None = None,
    heartbeat_interval_s: float = 30.0, stale_after_s: int = 600,
) -> dict:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    started_at = now_iso(now)
    run_id = make_run_id(now)

    if mode == "validate_handle":
        handle_row = db_mod.get_handle(conn, handle_id)
        adapter = adapters[handle_row["platform"]]
        db_mod.set_handle_status(conn, handle_id, "validating")
        outcome = process_handle_validate(adapter, repo_root, handle_row)
        finished_at = now_iso()
        if outcome["ok"]:
            db_mod.set_handle_status(conn, handle_id, "validated", validated_at=finished_at)
            db_mod.set_handle_last_seen(conn, handle_id, outcome["item"]["published"])
            status = "completed"
            handle_result = {"handle": handle_row["handle"], "platform": handle_row["platform"],
                              "cohort": handle_row["cohort"], "status": "ok", "items_downloaded": 1,
                              "last_seen_published_at": outcome["item"]["published"], "error_message": None}
        else:
            db_mod.set_handle_status(conn, handle_id, "invalid")
            db_mod.set_handle_included(conn, handle_id, False)
            status = "completed_with_errors"
            handle_result = {"handle": handle_row["handle"], "platform": handle_row["platform"],
                              "cohort": handle_row["cohort"], "status": "handle_not_found",
                              "items_downloaded": 0, "last_seen_published_at": None,
                              "error_message": "enumerate returned no results"}
        run_row_id = db_mod.insert_terminal_run(conn, run_id, trigger, mode, status, started_at, finished_at)
        db_mod.record_handle_result(conn, run_row_id, handle_id, handle_result["status"],
                                     handle_result["items_downloaded"], handle_result["error_message"])
        db_mod.finish_run(conn, run_row_id, status, finished_at,
                           str(write_run_record(repo_root, {
                               "run_id": run_id, "trigger": trigger, "mode": mode, "status": status,
                               "started_at": started_at, "finished_at": finished_at,
                               "backfill_start": None, "backfill_end": None,
                           }, [handle_result])))
        return {"run_row_id": run_row_id, "status": status}

    # incremental / backfill: single-flight lock applies.
    reclaimed_ids = db_mod.reclaim_stale_runs(conn, now_iso(now), stale_after_s)
    _write_abandoned_records_for_reclaimed_runs(conn, repo_root, reclaimed_ids, now)
    try:
        run_row_id = db_mod.insert_running_run(conn, run_id, trigger, mode, started_at, backfill_start, backfill_end)
    except sqlite3.IntegrityError:
        # A fresh run_id for the locked row -- reusing `run_id` here would
        # collide with the very row that just won the lock (both share the
        # same run_id UNIQUE constraint), raising a second, unrelated
        # IntegrityError instead of cleanly recording "locked".
        finished_at = now_iso()
        locked_run_id = make_run_id(_dt.datetime.now(_dt.timezone.utc))
        locked_id = db_mod.insert_locked_run(conn, locked_run_id, trigger, mode, started_at, finished_at)
        md_path = write_run_record(repo_root, {
            "run_id": locked_run_id, "trigger": trigger, "mode": mode, "status": "locked",
            "started_at": started_at, "finished_at": finished_at,
            "backfill_start": backfill_start, "backfill_end": backfill_end,
        }, [])
        db_mod.finish_run(conn, locked_id, "locked", finished_at, str(md_path))
        return {"run_row_id": locked_id, "status": "locked"}

    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_run_heartbeat_loop, args=(conn, run_row_id, heartbeat_interval_s, stop_event), daemon=True,
    )
    heartbeat_thread.start()

    handle_results = []
    any_error = False
    outer_crash: Exception | None = None
    try:
        handles = db_mod.list_handles(conn, included_only=True)
        for handle_row in handles:
            try:
                downloaded = _process_one_handle(adapters, repo_root, handle_row, mode, backfill_start, backfill_end, now)
                # Not every downloaded item is guaranteed to carry a date (a
                # YouTube item whose info.json write failed reports
                # published=None) -- guard max() against an empty sequence
                # rather than letting a fully-successful download raise
                # ValueError and get mislabeled as a per-handle "error".
                published_dates = [d["published"] for d in downloaded if d.get("published")]
                if published_dates:
                    db_mod.set_handle_last_seen(conn, handle_row["id"], max(published_dates))
                status = "ok" if downloaded else "no_new_content"
                db_mod.record_handle_result(conn, run_row_id, handle_row["id"], status, len(downloaded))
                handle_results.append({
                    "handle": handle_row["handle"], "platform": handle_row["platform"],
                    "cohort": handle_row["cohort"], "status": status, "items_downloaded": len(downloaded),
                    "last_seen_published_at": db_mod.get_handle(conn, handle_row["id"])["last_seen_published_at"],
                    "error_message": None,
                })
            except Exception as exc:  # noqa: BLE001 - per-handle isolation is the whole point
                any_error = True
                db_mod.record_handle_result(conn, run_row_id, handle_row["id"], "error", 0, str(exc))
                handle_results.append({
                    "handle": handle_row["handle"], "platform": handle_row["platform"],
                    "cohort": handle_row["cohort"], "status": "error", "items_downloaded": 0,
                    "last_seen_published_at": None, "error_message": str(exc),
                })
    except Exception as exc:  # noqa: BLE001 - a crash OUTSIDE the per-handle loop
        # (e.g. db_mod.list_handles itself raising) -- distinct from any
        # individual handle's error above. The run still gets a terminal
        # status and a paired record with whatever partial handle_results
        # were collected before the crash, per the spec's error-handling
        # requirement, rather than leaving the row stuck at 'running' forever
        # (that's what reclaim_stale_runs is for on a hard process kill; this
        # branch is for a crash the process itself survives long enough to
        # report).
        outer_crash = exc
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=5)

    if outer_crash is not None:
        final_status = "failed"
    else:
        final_status = "completed_with_errors" if any_error else "completed"
    finished_at = now_iso()
    md_path = write_run_record(repo_root, {
        "run_id": run_id, "trigger": trigger, "mode": mode, "status": final_status,
        "started_at": started_at, "finished_at": finished_at,
        "backfill_start": backfill_start, "backfill_end": backfill_end,
    }, handle_results)
    db_mod.finish_run(conn, run_row_id, final_status, finished_at, str(md_path))
    if trigger == "scheduled" and final_status != "failed":
        db_mod.set_last_scheduled_run_date(conn, now.date().isoformat())
    return {"run_row_id": run_row_id, "status": final_status}
```

Note on `handle_not_found` vs `error`: `_process_one_handle` currently raises for any adapter
failure and the `except Exception` branch always records `"error"`, not `"handle_not_found"`. This
is intentional simplification for incremental/backfill runs — the spec's distinct
`handle_not_found` status is fully implemented for `validate_handle` (Task 10 already returns
`ok=False` distinctly from an exception), where it matters most (auto-exclude on first add). For an
already-`validated` handle that later goes empty on enumeration, `discovery_youtube.enumerate_newest_first`
and `discovery_bluesky.enumerate_newest_first` already return `[]` rather than raising (see Tasks 7-8),
which `process_handle` treats as `no_new_content`, not `error` — so a truly dead handle (yt-dlp
returns a non-zero exit and empty output) still surfaces as `no_new_content` every run rather than
a directly-actionable `handle_not_found`. Flagging this as a known limitation rather than adding
adapter-level "not found" detection here, which would require distinguishing "yt-dlp succeeded with
zero results" from "yt-dlp failed to resolve the channel" — out of scope for this plan; the run
history's `error_message`/status still makes a silently-broken handle visible over time via
repeated `no_new_content` runs, just not as crisply as `handle_not_found` would.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_engine.py -v`
Expected: PASS (full file)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_engine.py pipeline-app/tests/test_discovery_engine.py
git commit -m "feat(discovery): add run_discovery orchestrator with locking, heartbeat, resiliency"
```

---

## Task 13: `discovery_scheduling.py` — due-check with catch-up semantics

**Files:**
- Create: `pipeline-app/pipeline_app/discovery_scheduling.py`
- Test: `pipeline-app/tests/test_discovery_scheduling.py`

**Interfaces:**
- Consumes: nothing (pure function over plain values, no DB access — the caller in Task 14 reads
  `db.get_settings` and passes its fields in).
- Produces: `is_due(now: _dt.datetime, timezone_name: str, time_of_day: str, last_scheduled_run_date: str | None) -> bool`

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_discovery_scheduling.py`:

```python
import datetime as _dt

from pipeline_app.discovery_scheduling import is_due


def test_not_due_before_time_of_day():
    now = _dt.datetime(2026, 7, 30, 5, 45, tzinfo=_dt.timezone.utc)  # 00:45 America/Chicago (CDT, UTC-5)
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date=None) is False


def test_due_at_or_after_time_of_day_when_not_yet_run_today():
    now = _dt.datetime(2026, 7, 30, 11, 0, tzinfo=_dt.timezone.utc)  # 06:00 America/Chicago
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date=None) is True


def test_not_due_again_same_day_after_already_run():
    now = _dt.datetime(2026, 7, 30, 12, 0, tzinfo=_dt.timezone.utc)  # 07:00 America/Chicago
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date="2026-07-30") is False


def test_catch_up_fires_once_after_multiple_missed_days():
    now = _dt.datetime(2026, 8, 2, 19, 0, tzinfo=_dt.timezone.utc)  # afternoon, several days later
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date="2026-07-28") is True


def test_due_again_next_day_after_time_of_day():
    now = _dt.datetime(2026, 7, 31, 11, 30, tzinfo=_dt.timezone.utc)  # 06:30 America/Chicago
    assert is_due(now, "America/Chicago", "06:00", last_scheduled_run_date="2026-07-30") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_scheduling.py -v`
Expected: FAIL — module doesn't exist. (`America/Chicago` is UTC-5 during the tests' July/August
dates because CDT is in effect; verify with `python -c "import zoneinfo,datetime; print(datetime.datetime(2026,7,30,tzinfo=zoneinfo.ZoneInfo('America/Chicago')))"` if the offset in a test comment ever looks wrong.)

**Before Step 3**, add `tzdata` to `pipeline-app/requirements.txt` (append after the `youtube-transcript-api>=1.0`
line added in Task 7):

```
tzdata>=2024.1
```

Windows does not ship the IANA timezone database the way Linux/macOS do — stdlib `zoneinfo` has no
data to load on a bare Windows Python install, and `ZoneInfo("America/Chicago")` raises
`ZoneInfoNotFoundError` without this package. Install it now: `cd pipeline-app && pip install -r requirements.txt`.

- [ ] **Step 3: Implement**

Create `pipeline-app/pipeline_app/discovery_scheduling.py`:

```python
"""Pure due-check for the discovery cron -- see the design spec's
'Scheduling' section for the catch-up semantics this implements. No DB or
network access: run_discovery_cron.py (Task 14) reads discovery_settings and
passes its fields in."""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo


def is_due(now: _dt.datetime, timezone_name: str, time_of_day: str, last_scheduled_run_date: str | None) -> bool:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    today = local_now.date().isoformat()
    if last_scheduled_run_date == today:
        return False
    hour, minute = (int(part) for part in time_of_day.split(":"))
    return local_now.time() >= _dt.time(hour, minute)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_scheduling.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_scheduling.py pipeline-app/tests/test_discovery_scheduling.py
git commit -m "feat(discovery): add scheduler due-check with once-per-day catch-up semantics"
```

---

## Task 14: `run_discovery_cron.py` — CLI entry point

**Files:**
- Create: `pipeline-app/run_discovery_cron.py`
- Test: `pipeline-app/tests/test_run_discovery_cron.py`

**Interfaces:**
- Consumes: `db.get_settings`/`db.init_db`/`db.get_connection` (Tasks 1-4), `discovery_scheduling.is_due`
  (Task 13), `discovery_engine.run_discovery` (Task 12), `discovery_youtube`/`discovery_bluesky`
  (Tasks 7-8, wired into an `ADAPTERS` dict).
- Produces: `build_adapters() -> dict[str, PlatformAdapter]` and `main(argv: list[str] | None = None) -> int`,
  importable for tests and runnable as `python run_discovery_cron.py [args]`. This is the exact
  script both Windows Task Scheduler (Task 17) and every UI-triggered action (Tasks 15-16) invoke
  as a subprocess — see spec's "Concurrency and execution model".

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_run_discovery_cron.py`:

```python
from pathlib import Path

import pytest

from pipeline_app import db
import run_discovery_cron as cron


@pytest.fixture
def repo_root(tmp_path: Path):
    db_path = tmp_path / "pipeline-app" / "pipeline.db"
    db_path.parent.mkdir(parents=True)
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    return tmp_path


def test_scheduled_mode_skips_when_not_due(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: False)
    called = {"n": 0}
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert exit_code == 0
    assert called["n"] == 0


def test_scheduled_mode_runs_when_due(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert exit_code == 0
    assert calls[0]["trigger"] == "scheduled"
    assert calls[0]["mode"] == "incremental"


def test_incremental_mode_always_runs(monkeypatch, repo_root):
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main(["--mode", "incremental", "--repo-root", str(repo_root)])
    assert exit_code == 0
    assert calls[0]["trigger"] == "manual"
    assert calls[0]["mode"] == "incremental"


def test_backfill_mode_requires_start_and_end(repo_root):
    with pytest.raises(SystemExit):
        cron.main(["--mode", "backfill", "--repo-root", str(repo_root)])


def test_backfill_mode_passes_dates_through(monkeypatch, repo_root):
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main([
        "--mode", "backfill", "--backfill-start", "2026-06-01", "--backfill-end", "2026-06-30",
        "--repo-root", str(repo_root),
    ])
    assert exit_code == 0
    assert calls[0]["mode"] == "backfill"
    assert calls[0]["backfill_start"] == "2026-06-01"
    assert calls[0]["backfill_end"] == "2026-06-30"


def test_validate_handle_mode_requires_handle_id(repo_root):
    with pytest.raises(SystemExit):
        cron.main(["--mode", "validate_handle", "--repo-root", str(repo_root)])


def test_validate_handle_mode_passes_handle_id_through(monkeypatch, repo_root):
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main(["--mode", "validate_handle", "--handle-id", "42", "--repo-root", str(repo_root)])
    assert exit_code == 0
    assert calls[0]["handle_id"] == 42
    assert calls[0]["mode"] == "validate_handle"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_run_discovery_cron.py -v`
Expected: FAIL — `run_discovery_cron` module doesn't exist yet.

- [ ] **Step 3: Implement**

Create `pipeline-app/run_discovery_cron.py`:

```python
"""Standalone CLI entry point for the discovery engine. This is the single
execution path for every trigger -- Windows Task Scheduler's 15-minute
wake (--mode scheduled), the UI's Run Now (--mode incremental), Run Now
(backfill) (--mode backfill), and handle validation (--mode validate_handle)
-- always invoked as a subprocess, never imported into the running
pipeline-app web process (see the design spec's "Concurrency and execution
model"). Run from anywhere; --repo-root defaults to this file's grandparent.

Usage:
  python run_discovery_cron.py --mode scheduled
  python run_discovery_cron.py --mode incremental
  python run_discovery_cron.py --mode backfill --backfill-start 2026-06-01 --backfill-end 2026-06-30
  python run_discovery_cron.py --mode validate_handle --handle-id 42
"""
from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

from pipeline_app import db
from pipeline_app import discovery_bluesky, discovery_youtube
from pipeline_app.discovery_engine import run_discovery
from pipeline_app.discovery_scheduling import is_due

HERE = Path(__file__).resolve().parent


def build_adapters():
    return {"youtube": discovery_youtube, "bluesky": discovery_bluesky}


def _is_due_now(conn) -> bool:
    settings = db.get_settings(conn)
    return is_due(
        _dt.datetime.now(_dt.timezone.utc), settings["timezone"],
        settings["time_of_day"], settings["last_scheduled_run_date"],
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", required=True,
                     choices=["scheduled", "incremental", "backfill", "validate_handle"])
    ap.add_argument("--backfill-start")
    ap.add_argument("--backfill-end")
    ap.add_argument("--handle-id", type=int)
    ap.add_argument("--repo-root", default=str(HERE.parent))
    args = ap.parse_args(argv)

    repo_root = Path(args.repo_root)
    if args.mode == "backfill" and not (args.backfill_start and args.backfill_end):
        ap.error("--mode backfill requires --backfill-start and --backfill-end")
    if args.mode == "validate_handle" and args.handle_id is None:
        ap.error("--mode validate_handle requires --handle-id")

    # Schema init happens BEFORE any due-check or run attempt -- on the very
    # first-ever scheduled wake (no pipeline.db yet), sqlite3.connect silently
    # creates an empty file, and db.get_settings against a table-less DB
    # raises OperationalError. init_db is idempotent (Task 1's IF NOT EXISTS
    # everywhere), so running it on every invocation, scheduled or not, is
    # always safe.
    db_path = repo_root / "pipeline-app" / "pipeline.db"
    schema_path = HERE / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    try:
        if args.mode == "scheduled":
            if not _is_due_now(conn):
                return 0
            trigger, mode = "scheduled", "incremental"
        elif args.mode == "incremental":
            trigger, mode = "manual", "incremental"
        elif args.mode == "backfill":
            trigger, mode = "manual", "backfill"
        else:
            trigger, mode = "manual", "validate_handle"

        result = run_discovery(
            conn, repo_root, build_adapters(), trigger=trigger, mode=mode,
            backfill_start=args.backfill_start, backfill_end=args.backfill_end,
            handle_id=args.handle_id,
        )
        print(f"run {result['run_row_id']}: {result['status']}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_run_discovery_cron.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/run_discovery_cron.py pipeline-app/tests/test_run_discovery_cron.py
git commit -m "feat(discovery): add run_discovery_cron.py CLI entry point"
```

---

## Task 15: `routes/discovery.py` + templates — handle roster page

**Files:**
- Create: `pipeline-app/pipeline_app/routes/discovery.py`
- Create: `pipeline-app/pipeline_app/templates/discovery_handles.html`
- Modify: `pipeline-app/pipeline_app/templates/partials/header.html` (add nav links)
- Modify: `pipeline-app/pipeline_app/main.py` (register router)
- Test: `pipeline-app/tests/test_routes_discovery.py`

**Interfaces:**
- Consumes: `db.py` handle functions (Task 2), spawns `run_discovery_cron.py` (Task 14) as a
  subprocess for handle validation.
- Produces routes:
  - `GET /discovery/handles` — roster table.
  - `POST /discovery/handles` — add a handle (form: `platform`, `handle`, `display_name`, `cohort`,
    `keyword_filter`), inserts as `pending`, spawns `python run_discovery_cron.py --mode validate_handle --handle-id <id>` non-blocking, redirects back to the roster page.
  - `POST /discovery/handles/{handle_id}/toggle` — flips `included`, redirects back.
  - `GET /discovery/handles/{handle_id}/status` — JSON `{"status": "..."}`, polled by the roster
    page while a row is `pending`/`validating`.

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_routes_discovery.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app)


def test_get_handles_page_lists_no_handles_initially(client: TestClient):
    response = client.get("/discovery/handles")
    assert response.status_code == 200
    assert "No handles yet" in response.text


def test_add_handle_creates_pending_row_and_spawns_validation(client: TestClient, monkeypatch):
    spawned = {}

    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        class FakeProc:
            pid = 999
        return FakeProc()

    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", fake_popen)
    response = client.post("/discovery/handles", data={
        "platform": "youtube", "handle": "@NewChannel", "display_name": "New Channel",
        "cohort": "guru", "keyword_filter": "",
    })
    assert response.status_code in (200, 303, 307)
    listing = client.get("/discovery/handles")
    assert "@NewChannel" in listing.text
    assert "pending" in listing.text.lower() or "validating" in listing.text.lower()
    assert "--mode" in spawned["cmd"]
    assert "validate_handle" in spawned["cmd"]


def test_toggle_include_flips_and_persists(client: TestClient, monkeypatch):
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", lambda *a, **k: type("P", (), {"pid": 1})())
    client.post("/discovery/handles", data={
        "platform": "youtube", "handle": "@a", "display_name": "A", "cohort": "guru", "keyword_filter": "",
    })
    listing = client.get("/discovery/handles")
    import re
    match = re.search(r'/discovery/handles/(\d+)/toggle', listing.text)
    assert match is not None
    handle_id = match.group(1)
    response = client.post(f"/discovery/handles/{handle_id}/toggle")
    assert response.status_code in (200, 303, 307)


def test_handle_status_endpoint_returns_json(client: TestClient, monkeypatch):
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", lambda *a, **k: type("P", (), {"pid": 1})())
    client.post("/discovery/handles", data={
        "platform": "youtube", "handle": "@a", "display_name": "A", "cohort": "guru", "keyword_filter": "",
    })
    listing = client.get("/discovery/handles")
    import re
    handle_id = re.search(r'/discovery/handles/(\d+)/toggle', listing.text).group(1)
    response = client.get(f"/discovery/handles/{handle_id}/status")
    assert response.status_code == 200
    assert response.json()["status"] in ("pending", "validating", "validated", "invalid")


def test_add_duplicate_handle_returns_400_not_500(client: TestClient, monkeypatch):
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", lambda *a, **k: type("P", (), {"pid": 1})())
    data = {"platform": "youtube", "handle": "@a", "display_name": "A", "cohort": "guru", "keyword_filter": ""}
    first = client.post("/discovery/handles", data=data)
    assert first.status_code in (200, 303, 307)
    second = client.post("/discovery/handles", data=data)
    assert second.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_routes_discovery.py -v`
Expected: FAIL — `pipeline_app.routes.discovery` doesn't exist and isn't registered.

- [ ] **Step 3: Implement**

Create `pipeline-app/pipeline_app/routes/discovery.py`:

```python
import datetime
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

from pipeline_app import db as db_mod

router = APIRouter()

COHORT_SUGGESTIONS = ["guru", "shorts-specialist", "midjourney-source", "general-interest"]


def _spawn_cron(repo_root: Path, args: list[str]) -> None:
    cron_script = repo_root / "pipeline-app" / "run_discovery_cron.py"
    subprocess.Popen(
        [sys.executable, str(cron_script), *args, "--repo-root", str(repo_root)],
        cwd=str(repo_root),
    )


@router.get("/discovery/handles")
def discovery_handles_page(request: Request):
    conn = request.app.state.conn
    handles = db_mod.list_handles(conn)
    return request.app.state.templates.TemplateResponse(
        request, "discovery_handles.html",
        {
            "handles": handles, "cohort_suggestions": COHORT_SUGGESTIONS,
            "active_nav": "discovery_handles", "cli_available": request.app.state.cli_available,
        },
    )


@router.post("/discovery/handles")
def add_handle(
    request: Request, platform: str = Form(...), handle: str = Form(...),
    display_name: str = Form(""), cohort: str = Form(...), keyword_filter: str = Form(""),
):
    conn = request.app.state.conn
    repo_root = request.app.state.repo_root
    if db_mod.get_handle_by_platform_and_handle(conn, platform, handle) is not None:
        return PlainTextResponse(f"handle already exists: {platform}/{handle}", status_code=400)
    added_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    handle_id = db_mod.create_handle(
        conn, platform, handle, display_name or None, cohort, keyword_filter or None, added_at,
    )
    _spawn_cron(repo_root, ["--mode", "validate_handle", "--handle-id", str(handle_id)])
    return RedirectResponse(url="/discovery/handles", status_code=303)


@router.post("/discovery/handles/{handle_id}/toggle")
def toggle_handle_included(request: Request, handle_id: int):
    conn = request.app.state.conn
    row = db_mod.get_handle(conn, handle_id)
    if row is not None:
        db_mod.set_handle_included(conn, handle_id, not bool(row["included"]))
    return RedirectResponse(url="/discovery/handles", status_code=303)


@router.get("/discovery/handles/{handle_id}/status")
def handle_status(request: Request, handle_id: int):
    conn = request.app.state.conn
    row = db_mod.get_handle(conn, handle_id)
    if row is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"status": row["status"]})
```

Create `pipeline-app/pipeline_app/templates/discovery_handles.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Discovery: Handles</h1>
{% if handles %}
<table>
  <thead>
    <tr><th>Platform</th><th>Handle</th><th>Display name</th><th>Cohort</th><th>Status</th><th>Included</th><th>Last seen</th></tr>
  </thead>
  <tbody>
    {% for h in handles %}
    <tr>
      <td>{{ h.platform }}</td>
      <td>{{ h.handle }}</td>
      <td>{{ h.display_name or "" }}</td>
      <td>{{ h.cohort }}</td>
      <td><span class="status" data-handle-status="{{ h.id }}">{{ h.status }}</span></td>
      <td>
        <form method="post" action="/discovery/handles/{{ h.id }}/toggle">
          <button type="submit">{{ "Exclude" if h.included else "Include" }}</button>
        </form>
      </td>
      <td>{{ h.last_seen_published_at or "" }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<p>No handles yet.</p>
{% endif %}

<h2>Add handle</h2>
<form method="post" action="/discovery/handles">
  <select name="platform">
    <option value="youtube">YouTube</option>
    <option value="bluesky">Bluesky</option>
  </select>
  <input name="handle" placeholder="@handle or actor.bsky.social" required>
  <input name="display_name" placeholder="Display name">
  <input name="cohort" placeholder="cohort" list="cohort-suggestions" required>
  <datalist id="cohort-suggestions">
    {% for c in cohort_suggestions %}<option value="{{ c }}">{% endfor %}
  </datalist>
  <input name="keyword_filter" placeholder="keyword filter (optional)">
  <button type="submit">Add handle</button>
</form>

<script>
  document.querySelectorAll("[data-handle-status]").forEach((el) => {
    const status = el.textContent.trim();
    if (status !== "pending" && status !== "validating") return;
    const handleId = el.dataset.handleStatus;
    const poll = setInterval(async () => {
      const res = await fetch(`/discovery/handles/${handleId}/status`);
      const data = await res.json();
      if (data.status !== "pending" && data.status !== "validating") {
        clearInterval(poll);
        window.location.reload();
      }
    }, 3000);
  });
</script>
{% endblock %}
```

Modify `pipeline-app/pipeline_app/templates/partials/header.html`: add two links inside `<nav class="top-nav">`, after the existing `Projects` link:

```html
    <a href="/discovery/handles" class="{{ 'active' if active_nav == 'discovery_handles' }}">Discovery</a>
    <a href="/discovery/runs" class="{{ 'active' if active_nav == 'discovery_runs' }}">Discovery Runs</a>
```

Modify `pipeline-app/pipeline_app/main.py`: add the import and registration alongside the existing routers.

```python
from pipeline_app.routes import browse, discovery, doctor, inspector, projects, skills, stages
```

```python
    app.include_router(discovery.router)
```
(add this line next to the existing `app.include_router(projects.router)` etc.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_discovery.py -v`
Expected: PASS

Run the full suite once to confirm nothing else broke: `cd pipeline-app && python -m pytest -v`

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/discovery.py pipeline-app/pipeline_app/templates/discovery_handles.html pipeline-app/pipeline_app/templates/partials/header.html pipeline-app/pipeline_app/main.py pipeline-app/tests/test_routes_discovery.py
git commit -m "feat(discovery): add handle roster page with add/validate/include-toggle"
```

---

## Task 16: `routes/discovery.py` — Run Now / Run Now (backfill) / schedule settings

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/discovery.py` (append routes)
- Modify: `pipeline-app/pipeline_app/templates/discovery_handles.html` (add Run Now + schedule controls)
- Test: `pipeline-app/tests/test_routes_discovery.py` (append)

**Interfaces:**
- Consumes: `_spawn_cron` (Task 15), `db.get_settings`/`db.update_settings` (Task 4).
- Produces routes:
  - `POST /discovery/run-now` — spawns `--mode incremental`, redirects to `/discovery/runs`.
  - `POST /discovery/run-now-backfill` — form fields `start`, `end` (`YYYY-MM-DD`); spawns
    `--mode backfill --backfill-start <start> --backfill-end <end>`, redirects to `/discovery/runs`.
  - `POST /discovery/settings` — form fields `time_of_day` (`HH:MM`), `timezone`; writes to
    `discovery_settings` via `db.update_settings` (frequency is fixed at `"daily"` for now — see
    the spec's Non-goals — so the form only exposes time and timezone), redirects back to
    `/discovery/handles`. This is the spec's "UI schedule form" (Goal 4 / "Scheduling" section) —
    it does **not** touch Windows Task Scheduler at all (see Task 18's `setup_discovery_task.py`
    and Task 14's `run_discovery_cron.py --mode scheduled`, which is what actually reads this row).

- [ ] **Step 1: Write the failing tests**

Append to `pipeline-app/tests/test_routes_discovery.py`:

```python
def test_run_now_spawns_incremental_mode(client: TestClient, monkeypatch):
    spawned = {}
    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        return type("P", (), {"pid": 1})()
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", fake_popen)
    response = client.post("/discovery/run-now")
    assert response.status_code in (200, 303, 307)
    assert "incremental" in spawned["cmd"]


def test_run_now_backfill_spawns_backfill_mode_with_dates(client: TestClient, monkeypatch):
    spawned = {}
    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        return type("P", (), {"pid": 1})()
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", fake_popen)
    response = client.post("/discovery/run-now-backfill", data={"start": "2026-06-01", "end": "2026-06-30"})
    assert response.status_code in (200, 303, 307)
    assert "backfill" in spawned["cmd"]
    assert "2026-06-01" in spawned["cmd"]
    assert "2026-06-30" in spawned["cmd"]


def test_update_settings_persists_time_and_timezone(client: TestClient):
    response = client.post("/discovery/settings", data={"time_of_day": "07:30", "timezone": "America/New_York"})
    assert response.status_code in (200, 303, 307)
    from pipeline_app import db as db_mod
    row = db_mod.get_settings(client.app.state.conn)
    assert row["time_of_day"] == "07:30"
    assert row["timezone"] == "America/New_York"


def test_handles_page_shows_current_schedule(client: TestClient):
    client.post("/discovery/settings", data={"time_of_day": "07:30", "timezone": "America/New_York"})
    listing = client.get("/discovery/handles")
    assert "07:30" in listing.text
    assert "America/New_York" in listing.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_routes_discovery.py -k "run_now or settings" -v`
Expected: FAIL — routes don't exist yet.

- [ ] **Step 3: Implement**

Append to `pipeline-app/pipeline_app/routes/discovery.py`:

```python
@router.post("/discovery/run-now")
def run_now(request: Request):
    _spawn_cron(request.app.state.repo_root, ["--mode", "incremental"])
    return RedirectResponse(url="/discovery/runs", status_code=303)


@router.post("/discovery/run-now-backfill")
def run_now_backfill(request: Request, start: str = Form(...), end: str = Form(...)):
    _spawn_cron(request.app.state.repo_root, [
        "--mode", "backfill", "--backfill-start", start, "--backfill-end", end,
    ])
    return RedirectResponse(url="/discovery/runs", status_code=303)


@router.post("/discovery/settings")
def update_settings(request: Request, time_of_day: str = Form(...), timezone: str = Form(...)):
    conn = request.app.state.conn
    db_mod.update_settings(conn, "daily", time_of_day, timezone)
    return RedirectResponse(url="/discovery/handles", status_code=303)
```

Modify `discovery_handles_page` (Task 15) to also pass the current schedule into the template context:

```python
@router.get("/discovery/handles")
def discovery_handles_page(request: Request):
    conn = request.app.state.conn
    handles = db_mod.list_handles(conn)
    settings = db_mod.get_settings(conn)
    return request.app.state.templates.TemplateResponse(
        request, "discovery_handles.html",
        {
            "handles": handles, "cohort_suggestions": COHORT_SUGGESTIONS, "settings": settings,
            "active_nav": "discovery_handles", "cli_available": request.app.state.cli_available,
        },
    )
```

Add to `pipeline-app/pipeline_app/templates/discovery_handles.html`, before `{% endblock %}`:

```html
<h2>Run now</h2>
<form method="post" action="/discovery/run-now">
  <button type="submit">Run Now (incremental)</button>
</form>
<form method="post" action="/discovery/run-now-backfill">
  <input type="date" name="start" required>
  <input type="date" name="end" required>
  <button type="submit">Run Now (backfill)</button>
</form>

<h2>Schedule</h2>
<p>Daily at {{ settings.time_of_day }} ({{ settings.timezone }})</p>
<form method="post" action="/discovery/settings">
  <input type="time" name="time_of_day" value="{{ settings.time_of_day }}" required>
  <input name="timezone" value="{{ settings.timezone }}" required placeholder="e.g. America/Chicago">
  <button type="submit">Update schedule</button>
</form>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_discovery.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/discovery.py pipeline-app/pipeline_app/templates/discovery_handles.html pipeline-app/tests/test_routes_discovery.py
git commit -m "feat(discovery): add Run Now, Run Now (backfill), and schedule settings UI"
```

---

## Task 17: `routes/discovery.py` + template — job history page

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/discovery.py` (append route)
- Create: `pipeline-app/pipeline_app/templates/discovery_runs.html`
- Test: `pipeline-app/tests/test_routes_discovery.py` (append)

**Interfaces:**
- Consumes: `db.list_runs`, `db.list_run_handle_results` (Task 3).
- Produces: `GET /discovery/runs` — lists all runs newest-first with a per-handle drill-down.

- [ ] **Step 1: Write the failing test**

Append to `pipeline-app/tests/test_routes_discovery.py`:

```python
def test_discovery_runs_page_lists_runs_newest_first(client: TestClient):
    from pipeline_app import db as db_mod
    conn = client.app.state.conn
    handle_id = db_mod.create_handle(conn, "youtube", "@a", "A", "guru", None, "2026-07-30T00:00:00Z")
    r1 = db_mod.insert_terminal_run(conn, "r1", "manual", "incremental", "completed", "2026-07-30T06:00:00Z", "2026-07-30T06:01:00Z")
    db_mod.record_handle_result(conn, r1, handle_id, "ok", 2)
    r2 = db_mod.insert_terminal_run(conn, "r2", "scheduled", "incremental", "completed_with_errors", "2026-07-30T07:00:00Z", "2026-07-30T07:01:00Z")
    response = client.get("/discovery/runs")
    assert response.status_code == 200
    first_pos = response.text.index("r2")
    second_pos = response.text.index("r1")
    assert first_pos < second_pos  # r2 (newer) rendered before r1
    assert "completed_with_errors" in response.text


def test_discovery_runs_page_empty_state(client: TestClient):
    response = client.get("/discovery/runs")
    assert response.status_code == 200
    assert "No discovery runs yet" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_routes_discovery.py -k discovery_runs_page -v`
Expected: FAIL — route/template don't exist yet.

- [ ] **Step 3: Implement**

Append to `pipeline-app/pipeline_app/routes/discovery.py`:

```python
@router.get("/discovery/runs")
def discovery_runs_page(request: Request):
    conn = request.app.state.conn
    runs = db_mod.list_runs(conn)
    runs_with_results = [
        {"run": run, "handle_results": db_mod.list_run_handle_results(conn, run["id"])}
        for run in runs
    ]
    return request.app.state.templates.TemplateResponse(
        request, "discovery_runs.html",
        {
            "runs_with_results": runs_with_results, "active_nav": "discovery_runs",
            "cli_available": request.app.state.cli_available,
        },
    )
```

Create `pipeline-app/pipeline_app/templates/discovery_runs.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Discovery: Run History</h1>
{% if runs_with_results %}
<ul>
  {% for entry in runs_with_results %}
  <li>
    <strong>{{ entry.run.run_id }}</strong>
    — <span class="status status-{{ entry.run.status }}">{{ entry.run.status }}</span>
    — trigger: {{ entry.run.trigger }}, mode: {{ entry.run.mode }}
    — started: {{ entry.run.started_at }}, finished: {{ entry.run.finished_at or "—" }}
    <ul>
      {% for hr in entry.handle_results %}
      <li>handle #{{ hr.handle_id }}: {{ hr.status }} ({{ hr.items_downloaded }} items){% if hr.error_message %} — {{ hr.error_message }}{% endif %}</li>
      {% endfor %}
    </ul>
  </li>
  {% endfor %}
</ul>
{% else %}
<p>No discovery runs yet.</p>
{% endif %}
<p><a href="/discovery/runs">Refresh</a></p>
{% endblock %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_discovery.py -v`
Expected: PASS

Run the full suite: `cd pipeline-app && python -m pytest -v`
Expected: PASS (everything, including the pre-existing test suite)

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/routes/discovery.py pipeline-app/pipeline_app/templates/discovery_runs.html pipeline-app/tests/test_routes_discovery.py
git commit -m "feat(discovery): add job history page with per-handle drill-down"
```

---

## Task 18: `scripts/setup_discovery_task.py` — one-time Windows Task Scheduler registration

**Files:**
- Create: `pipeline-app/scripts/setup_discovery_task.py`
- Test: `pipeline-app/tests/test_setup_discovery_task.py`

**Interfaces:**
- Consumes: nothing from earlier tasks except the path convention (`run_discovery_cron.py` at
  `pipeline-app/run_discovery_cron.py`, established in Task 14).
- Produces: `build_schtasks_command(python_exe: Path, cron_script: Path) -> list[str]` and
  `main(argv: list[str] | None = None) -> int` — run manually once, **never called from an HTTP
  route** (see spec's "Scheduling" section). Default is a dry run that prints the command; `--apply`
  actually executes it.

- [ ] **Step 1: Write the failing tests**

Create `pipeline-app/tests/test_setup_discovery_task.py`:

```python
from pathlib import Path

from scripts.setup_discovery_task import build_schtasks_command, main


def test_build_schtasks_command_shape():
    cmd = build_schtasks_command(Path("C:/venv/Scripts/python.exe"), Path("C:/repo/pipeline-app/run_discovery_cron.py"))
    assert cmd[0] == "schtasks"
    assert "/Create" in cmd
    assert "ContentStudio-Discovery" in cmd
    assert "/SC" in cmd
    assert "MINUTE" in cmd
    assert "/MO" in cmd
    mo_index = cmd.index("/MO")
    assert cmd[mo_index + 1] == "15"
    tr_index = cmd.index("/TR")
    assert "python.exe" in cmd[tr_index + 1]
    assert "run_discovery_cron.py" in cmd[tr_index + 1]
    assert "--mode" in cmd[tr_index + 1]
    assert "scheduled" in cmd[tr_index + 1]


def test_main_dry_run_does_not_execute(monkeypatch, capsys):
    called = {"n": 0}
    monkeypatch.setattr("scripts.setup_discovery_task.subprocess.run", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    exit_code = main([])
    assert exit_code == 0
    assert called["n"] == 0
    captured = capsys.readouterr()
    assert "schtasks" in captured.out
    assert "--apply" in captured.out


def test_main_apply_executes_schtasks(monkeypatch):
    calls = []
    class FakeResult:
        returncode = 0
        stdout = "SUCCESS"
        stderr = ""
    monkeypatch.setattr("scripts.setup_discovery_task.subprocess.run", lambda cmd, **k: (calls.append(cmd), FakeResult())[1])
    exit_code = main(["--apply"])
    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0][0] == "schtasks"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_setup_discovery_task.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

Create `pipeline-app/scripts/setup_discovery_task.py`:

```python
"""One-time registration of the ContentStudio-Discovery Windows Task
Scheduler task. Registers a SINGLE fixed 15-minute trigger; run_discovery_cron.py
itself decides on each wake whether a scheduled run is actually due (see
discovery_scheduling.is_due and the design spec's "Scheduling" section).
This script is never invoked from the running web app -- run it by hand,
once, after cloning/setting up the repo.

Usage:
  python scripts/setup_discovery_task.py            # dry run: prints the command
  python scripts/setup_discovery_task.py --apply     # actually registers the task
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ContentStudio-Discovery"


def build_schtasks_command(python_exe: Path, cron_script: Path) -> list[str]:
    task_command = f'"{python_exe}" "{cron_script}" --mode scheduled'
    return [
        "schtasks", "/Create", "/TN", TASK_NAME,
        "/TR", task_command, "/SC", "MINUTE", "/MO", "15", "/F",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually register the task (default: dry run / print only)")
    args = ap.parse_args(argv)

    pipeline_app_root = Path(__file__).resolve().parents[1]
    python_exe = Path(sys.executable)
    cron_script = pipeline_app_root / "run_discovery_cron.py"
    cmd = build_schtasks_command(python_exe, cron_script)

    if not args.apply:
        print("Dry run -- this is the command that would register the scheduled task:")
        print(" ".join(cmd))
        print("\nRe-run with --apply to actually register it.")
        return 0

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    print(f"Registered task '{TASK_NAME}': fires every 15 minutes, "
          f"run_discovery_cron.py decides per-wake whether a scheduled run is due.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_setup_discovery_task.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/scripts/setup_discovery_task.py pipeline-app/tests/test_setup_discovery_task.py
git commit -m "feat(discovery): add one-time Windows Task Scheduler setup script"
```

---

## Task 19: End-to-end verification and migration run

**Files:**
- None created/modified — this task runs the full suite and the one-off migration against the
  real repo, then verifies manually via the browser per this project's UI-change convention.

- [ ] **Step 1: Run the full pipeline-app test suite**

Run: `cd pipeline-app && python -m pytest -v`
Expected: PASS — every test from Tasks 1-18 plus the pre-existing suite (projects/stages/skills/
doctor/inspector/browse) all green.

- [ ] **Step 2: Run the one-off migration against the real repo**

```bash
cd pipeline-app
python scripts/migrate_handles_from_manifest.py
```

Expected output: `migrated 16 handles from .../manifests/brand_sources.json into .../pipeline.db`

- [ ] **Step 3: Start the app and verify the roster page in a browser**

```bash
cd pipeline-app
uvicorn pipeline_app.main:create_default_app --factory --reload
```

Open `http://127.0.0.1:8000/discovery/handles` — verify all 16 migrated handles appear, grouped
sensibly by cohort, all `status=validated`, `included` toggle present per row. Add one test handle
(a real, findable `@handle`) through the form, confirm it shows `pending`/`validating` then flips
to `validated` within ~90 seconds without a page reload (the polling script from Task 15), and
confirm a new `.md` file landed under `output/brand-intel/youtube/<slug>/`.

- [ ] **Step 4: Verify Run Now and the history page**

Click "Run Now (incremental)" on the roster page. Navigate to `http://127.0.0.1:8000/discovery/runs`,
confirm the run appears (may already show `completed` since incremental runs are typically fast
once most handles have nothing new), with correct per-handle status breakdown. Confirm
`output/discovery-runs/<run_id>.md` was written and contains no transcript/description text.

- [ ] **Step 5: Verify the never-delete invariant and commit any final fixes**

```bash
cd pipeline-app
git status  # confirm no files under output/brand-intel/ were modified/deleted by the above steps
python -m pytest -v  # final full green run
git add -A
git commit -m "chore(discovery): verify end-to-end after implementation (migration + manual UI check)"
```

(Only commit if Step 5's `git status` shows changes — e.g. if a manual fix was needed during
verification. If everything already passed cleanly in Tasks 1-18, this step may have nothing to commit.)

---

## Self-Review Notes

**Spec coverage:** every section of `docs/superpowers/specs/2026-07-30-discovery-cron-automation-design.md`
maps to a task — Data model → Tasks 1-4, Migration → Task 5, Roster page → Task 15, Validation →
Tasks 10/12/15, Extraction engine → Tasks 6-9, Run Now/backfill → Tasks 10/16, Concurrency → Task 12,
Scheduling → Tasks 13-14/16/18 (the UI schedule-settings form, originally missing from the first
draft of this plan, is now in Task 16), History page → Task 17, Paired record → Task 11
(including the `abandoned`/`locked` terminal-status record paths, and a `failed` outer-crash path,
all originally missing from the first draft and now in Task 12), Error handling → Task 12 (with the
`handle_not_found`-vs-`error` limitation for incremental/backfill runs explicitly flagged as a known
gap, not silently dropped) plus the write-temp-then-rename invariant in Tasks 7-8, Testing → woven
into every task.

**Deviation from the spec, and why:** the spec's Handle Validation section says a new handle's
"3-month-old" video is "discarded, not saved" after a full download — Task 9 instead peeks the
publish date *before* downloading (via `peek_upload_date`), so nothing is ever written and deleted.
This avoids a direct conflict with the spec's own "never delete persisted content" invariant
(Error Handling section) and is strictly cheaper (skips the full transcript fetch for
out-of-window videos entirely). This is an implementation-level refinement, not a scope or
requirement change.

**Type/interface consistency check:** `PlatformAdapter.peek_upload_date` is declared as `(*args) -> str | None`
in Task 9's `Protocol`, but both real adapters (Tasks 7 and 8) deliberately implement it as the
same single-argument `(item_id) -> str | None`, matching exactly how `process_handle`/
`process_handle_backfill` call it (`adapter.peek_upload_date(item_id)`) — the earlier draft of this
plan gave Bluesky's version a 3-argument signature that would have raised `TypeError` if ever
reached; fixed to match arity exactly instead of relying on "unreachable in practice."

**Accepted, documented gaps** (raised by a second-pass review, judged not worth the added complexity
for this iteration; revisit if they cause real friction after Task 19's manual verification):
- The roster page (Task 15) sorts `ORDER BY cohort, handle` rather than rendering explicit
  collapsible cohort sections — visually grouped, not interactively filterable. Fine for ~16-20
  handles; revisit if the roster grows much larger.
- Backfill mode's "Bluesky pagination depth limit reached, coverage may be partial" reporting
  (spec's Run Now/backfill section) isn't implemented — a backfill against a very old date range on
  a high-volume Bluesky account may silently under-report rather than flagging partial coverage.
  Low risk given this toolkit's actual Bluesky roster is a single handle today.
- No dedicated test asserts "no discovery code path calls unlink/rmtree/move outside `_tmp/`" or
  "`_manifest.csv` is never written by the discovery engine" as standalone invariants — the
  invariants hold by construction in the code as written (verified by inspection: Tasks 7-8's only
  `unlink` calls are the YouTube `_tmp` cleanup and the `peek_upload_date` temp-file cleanup; no
  task's code ever opens `_manifest.csv`), but nothing would catch a future edit that breaks them.
