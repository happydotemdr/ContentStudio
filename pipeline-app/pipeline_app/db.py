import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class TransactionPoisonedError(RuntimeError):
    """An inner transaction failed and its exception was swallowed.

    Committing the outer block would persist half a cascade -- exactly the
    defect `transaction()` exists to prevent -- so the boundary rolls back and
    raises this instead of silently succeeding."""


# Keyed by connection identity, deliberately NOT by thread: the app shares one
# connection between the threadpool routes and the event-loop chat route
# (get_connection's check_same_thread=False), so a transaction is a property of
# the connection, not of whoever happens to be running. The key is only present
# while `transaction()` holds a strong reference to the connection, so id reuse
# cannot collide.
_TXN_DEPTH: dict[int, int] = {}
_TXN_POISON: set[int] = set()
_TXN_LOCK = threading.Lock()


def commit_unless_in_transaction(conn: sqlite3.Connection) -> None:
    """What every leaf helper in this module calls instead of `conn.commit()`.

    Outside a `transaction()` block it commits immediately, byte-for-byte the
    behaviour every existing caller already depends on. Inside one it is a
    no-op, so the boundary owns the commit and a multi-row invariant is atomic
    for the first time (A-70)."""
    with _TXN_LOCK:
        in_txn = _TXN_DEPTH.get(id(conn), 0) > 0
    if not in_txn:
        conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection):
    """One explicit boundary around a multi-row invariant.

    Wrap project creation, approval + unlock, the staleness cascade and each
    per-project backfill in this. Nests: an inner block joins the outer one
    rather than committing early."""
    key = id(conn)
    with _TXN_LOCK:
        depth = _TXN_DEPTH.get(key, 0)
        _TXN_DEPTH[key] = depth + 1
    outermost = depth == 0
    try:
        yield conn
    except BaseException as exc:
        with _TXN_LOCK:
            _TXN_POISON.add(key)
        if outermost:
            _rollback_and_report(conn, exc)
        raise
    else:
        with _TXN_LOCK:
            poisoned = key in _TXN_POISON
        if outermost and poisoned:
            exc = TransactionPoisonedError(
                "an inner transaction failed and its exception was swallowed"
            )
            _rollback_and_report(conn, exc)
            raise exc
        if outermost:
            conn.commit()
    finally:
        with _TXN_LOCK:
            if outermost:
                _TXN_DEPTH.pop(key, None)
                _TXN_POISON.discard(key)
            else:
                _TXN_DEPTH[key] = depth


def _rollback_and_report(conn: sqlite3.Connection, exc: BaseException) -> None:
    from pipeline_app import obs

    try:
        conn.rollback()
    except Exception as rollback_exc:  # noqa: BLE001 -- report it, never mask the original
        obs.log("db.rollback_failed", level="critical",
                error=f"{type(rollback_exc).__name__}: {rollback_exc}")
    obs.record_event(
        conn, kind="db.transaction_rolled_back", severity="error", source="db.transaction",
        message=f"rolled back after {type(exc).__name__}: {exc}",
        detail={"exception": type(exc).__name__},
    )
    # Commit the event row explicitly. We are still nominally inside this
    # transaction -- `transaction()`'s finally has not popped the depth key yet --
    # so `record_event`'s `commit_unless_in_transaction` is a no-op here. The
    # rollback above already discarded the caller's work, so this row is the only
    # statement pending; committing it cannot resurrect anything.
    #
    # Without this the sole durable trace of the rollback dies with the
    # connection: verified empirically on sqlite3 with the default
    # isolation_level -- the row is visible on THIS connection, invisible to any
    # other, and gone entirely after close(). A surfacing mechanism that only the
    # failing process can see is the exact defect this package exists to remove.
    try:
        conn.commit()
    except Exception as commit_exc:  # noqa: BLE001 -- a lost event must not mask the original
        obs.log("db.rollback_event_commit_failed", level="critical",
                error=f"{type(commit_exc).__name__}: {commit_exc}")


def get_connection(db_path: Path) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI/Starlette runs sync `def` routes in a
    # worker-thread pool while async `def` routes (the chat/SSE endpoint) run
    # on the event-loop thread. A single shared connection is used across all
    # of them (one local user, effectively serialized by the app's own global
    # single-flight turn lock), so the default check_same_thread=True would
    # raise "SQLite objects created in a thread can only be used in that same
    # thread" the first time a sync route and the async route are hit from
    # different threads. WAL mode keeps reads from blocking on the rare
    # concurrent write.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(db_path: Path, schema_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def create_project(conn: sqlite3.Connection, run_id: str, slug: str, brand: str, created_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO projects (run_id, slug, brand, created_at) VALUES (?, ?, ?, ?)",
        (run_id, slug, brand, created_at),
    )
    commit_unless_in_transaction(conn)
    return cur.lastrowid


def get_project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def list_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()


def create_stage_row(conn: sqlite3.Connection, project_id: int, stage_id: str, status: str) -> int:
    cur = conn.execute(
        "INSERT INTO stages (project_id, stage_id, status) VALUES (?, ?, ?)",
        (project_id, stage_id, status),
    )
    commit_unless_in_transaction(conn)
    return cur.lastrowid


def get_stage(conn: sqlite3.Connection, project_id: int, stage_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM stages WHERE project_id = ? AND stage_id = ?",
        (project_id, stage_id),
    ).fetchone()


def get_stage_by_row_id(conn: sqlite3.Connection, stage_row_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM stages WHERE id = ?", (stage_row_id,)).fetchone()


def list_stages(conn: sqlite3.Connection, project_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM stages WHERE project_id = ?", (project_id,)).fetchall()


def update_stage_status(conn: sqlite3.Connection, stage_row_id: int, status: str, approved_at: str | None = None) -> None:
    if approved_at is not None:
        conn.execute(
            "UPDATE stages SET status = ?, approved_at = ? WHERE id = ?",
            (status, approved_at, stage_row_id),
        )
    else:
        conn.execute("UPDATE stages SET status = ? WHERE id = ?", (status, stage_row_id))
    commit_unless_in_transaction(conn)


def update_stage_session(conn: sqlite3.Connection, stage_row_id: int, session_id: str) -> None:
    conn.execute("UPDATE stages SET claude_session_id = ? WHERE id = ?", (session_id, stage_row_id))
    commit_unless_in_transaction(conn)


def create_turn(conn: sqlite3.Connection, stage_row_id: int, status: str, created_at: str, events_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO turns (stage_row_id, status, created_at, events_path) VALUES (?, ?, ?, ?)",
        (stage_row_id, status, created_at, events_path),
    )
    commit_unless_in_transaction(conn)
    return cur.lastrowid


def update_turn(conn: sqlite3.Connection, turn_id: int, status: str, finished_at: str | None = None, cost_usd: float | None = None) -> None:
    conn.execute(
        "UPDATE turns SET status = ?, finished_at = COALESCE(?, finished_at), cost_usd = COALESCE(?, cost_usd) WHERE id = ?",
        (status, finished_at, cost_usd, turn_id),
    )
    commit_unless_in_transaction(conn)


def list_turns(conn: sqlite3.Connection, stage_row_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM turns WHERE stage_row_id = ? ORDER BY created_at", (stage_row_id,)
    ).fetchall()


def list_running_turns(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM turns WHERE status = 'running'").fetchall()


def create_handle(
    conn: sqlite3.Connection, platform: str, handle: str, display_name: str | None,
    cohort: str, keyword_filter: str | None, added_at: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO handles (platform, handle, display_name, cohort, keyword_filter, added_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (platform, handle, display_name, cohort, keyword_filter, added_at),
    )
    commit_unless_in_transaction(conn)
    return cur.lastrowid


def get_handle(conn: sqlite3.Connection, handle_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM handles WHERE id = ?", (handle_id,)).fetchone()


def get_handle_by_platform_and_handle(conn: sqlite3.Connection, platform: str, handle: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM handles WHERE platform = ? AND handle = ?", (platform, handle)
    ).fetchone()


def list_platform_handles(conn: sqlite3.Connection, platform: str) -> list[sqlite3.Row]:
    """Every handle registered for one platform, included or not.

    Excluded handles still own their output directory, so a collision check has
    to see them too -- re-including one later must not silently start sharing
    files with a handle registered in the meantime.
    """
    return conn.execute(
        "SELECT * FROM handles WHERE platform = ? ORDER BY handle", (platform,)
    ).fetchall()


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
    commit_unless_in_transaction(conn)


def set_handle_included(conn: sqlite3.Connection, handle_id: int, included: bool) -> None:
    conn.execute("UPDATE handles SET included = ? WHERE id = ?", (1 if included else 0, handle_id))
    commit_unless_in_transaction(conn)


def set_handle_last_seen(conn: sqlite3.Connection, handle_id: int, last_seen_published_at: str) -> None:
    conn.execute(
        "UPDATE handles SET last_seen_published_at = ? WHERE id = ?",
        (last_seen_published_at, handle_id),
    )
    commit_unless_in_transaction(conn)


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
    commit_unless_in_transaction(conn)
    return get_handle_by_platform_and_handle(conn, platform, handle)["id"]


def insert_running_run(
    conn: sqlite3.Connection, run_id: str, trigger: str, mode: str, started_at: str,
    backfill_start: str | None = None, backfill_end: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, backfill_start, backfill_end, status, started_at) "
        "VALUES (?, ?, ?, ?, ?, 'running', ?)",
        (run_id, trigger, mode, backfill_start, backfill_end, started_at),
    )
    commit_unless_in_transaction(conn)
    return cur.lastrowid


def insert_locked_run(conn: sqlite3.Connection, run_id: str, trigger: str, mode: str, started_at: str, finished_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at, finished_at) "
        "VALUES (?, ?, ?, 'locked', ?, ?)",
        (run_id, trigger, mode, started_at, finished_at),
    )
    commit_unless_in_transaction(conn)
    return cur.lastrowid


def insert_terminal_run(conn: sqlite3.Connection, run_id: str, trigger: str, mode: str, status: str, started_at: str, finished_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at, finished_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, trigger, mode, status, started_at, finished_at),
    )
    commit_unless_in_transaction(conn)
    return cur.lastrowid


def get_running_run(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM discovery_runs WHERE status = 'running'").fetchone()


def update_run_heartbeat(conn: sqlite3.Connection, run_row_id: int, heartbeat_at: str) -> None:
    conn.execute("UPDATE discovery_runs SET heartbeat_at = ? WHERE id = ?", (heartbeat_at, run_row_id))
    commit_unless_in_transaction(conn)


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
        commit_unless_in_transaction(conn)
    return stale_ids


def finish_run(conn: sqlite3.Connection, run_row_id: int, status: str, finished_at: str, md_path: str) -> None:
    conn.execute(
        "UPDATE discovery_runs SET status = ?, finished_at = ?, md_path = ? WHERE id = ?",
        (status, finished_at, md_path, run_row_id),
    )
    commit_unless_in_transaction(conn)


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
    commit_unless_in_transaction(conn)
    return cur.lastrowid


def list_run_handle_results(conn: sqlite3.Connection, run_row_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM discovery_run_handles WHERE run_id = ?", (run_row_id,)
    ).fetchall()


def get_settings(conn: sqlite3.Connection) -> sqlite3.Row:
    return conn.execute("SELECT * FROM discovery_settings WHERE id = 1").fetchone()


def update_settings(conn: sqlite3.Connection, frequency: str, time_of_day: str, timezone: str) -> None:
    conn.execute(
        "UPDATE discovery_settings SET frequency = ?, time_of_day = ?, timezone = ? WHERE id = 1",
        (frequency, time_of_day, timezone),
    )
    commit_unless_in_transaction(conn)


def set_last_scheduled_run_date(conn: sqlite3.Connection, date_iso: str) -> None:
    conn.execute("UPDATE discovery_settings SET last_scheduled_run_date = ? WHERE id = 1", (date_iso,))
    commit_unless_in_transaction(conn)
