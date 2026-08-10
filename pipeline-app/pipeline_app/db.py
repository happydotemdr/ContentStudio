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
# Maps a poisoned connection to the FIRST exception that poisoned it -- a set
# would record only that something failed, never what, which is the difference
# between an events row a human can act on and one that just says "a thing broke".
_TXN_POISON: dict[int, BaseException] = {}
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
    per-project backfill in this (T4b does exactly that). Nests: an inner block
    joins the outer one rather than committing early.

    **Known hazard, deliberately not solved here.** The boundary is a property of
    the *connection*, and this app shares one connection across threads
    (`get_connection`'s `check_same_thread=False`). So a leaf helper called from a
    thread that is in no boundary at all still stops committing while *another*
    thread holds one, and its write is discarded outright if that boundary rolls
    back. Two known sharers, the in-process one first:

    - `approve_stage_route` and `create_project_route` (routes/stages.py,
      routes/projects.py) are sync `def` routes, so Starlette runs them in the
      threadpool, and T4b has both open a boundary on `request.app.state.conn`
      -- the SAME connection the turn route's `async def stage_chat` writes to
      from the event-loop thread for the whole life of a streaming turn.
      `turn_service.any_turn_running` only gates the run-turn route itself, so
      approving stage Y while a turn streams on stage X is a supported path.
      Inside the approval/creation boundary, that concurrent turn's writes stop
      committing, and a fault path discards them outright -- with the resulting
      `db.transaction_rolled_back` event attributing nothing to the collateral
      write, so a lost turn write is indistinguishable from a turn that never
      wrote. Filed as T13b; needs an operator decision among several candidate
      designs (connection-per-boundary / serialize against the turn lock /
      process-wide write lock / accept-and-detect) -- do not fix it here.
    - `discovery_engine._open_heartbeat_connection`, which returns `None` on
      any `sqlite3.Error` and falls back to the shared connection; under a
      rolled-back boundary the heartbeat write vanishes, `heartbeat_at`
      freezes, and another process reclaims a run that is still alive. Making
      that fallback loud belongs to the discovery package; do not fix it here.

    Do not widen the boundary to be thread-local to address either -- that
    would break the single-connection design this app depends on."""
    key = id(conn)
    with _TXN_LOCK:
        depth = _TXN_DEPTH.get(key, 0)
        _TXN_DEPTH[key] = depth + 1
    outermost = depth == 0
    try:
        yield conn
    except BaseException as exc:
        with _TXN_LOCK:
            _TXN_POISON.setdefault(key, exc)
        if outermost:
            _rollback_and_report(conn, exc)
        raise
    else:
        with _TXN_LOCK:
            original = _TXN_POISON.get(key)
        if outermost and original is not None:
            exc = TransactionPoisonedError(
                "an inner transaction failed and its exception was swallowed: "
                f"{type(original).__name__}: {original}"
            )
            # The inner block was not outermost, so _rollback_and_report never ran
            # for it, and the caller swallowed the exception by definition of this
            # path. Without chaining, the ONLY record of what actually failed --
            # which statement in the cascade, and why -- exists nowhere: not in
            # `events`, not in the log, not in a traceback.
            exc.__cause__ = original
            _rollback_and_report(conn, exc, original=original)
            raise exc
        if outermost:
            try:
                conn.commit()
            except BaseException as commit_exc:
                # Without this the block's statements stay pending in an open
                # transaction with no rollback and no event, the finally pops the
                # depth, and the NEXT unrelated leaf helper commits this failed
                # block's work. The caller was told the operation failed and the
                # data landed anyway -- A-70 with extra steps.
                _rollback_and_report(conn, commit_exc)
                raise
    finally:
        with _TXN_LOCK:
            remaining = _TXN_DEPTH.get(key, 1) - 1
            # Decrement, never restore the entry depth. Restoring an absolute value
            # RE-CREATES the key if the outermost block already popped it -- which
            # happens whenever two threads hold boundaries on this shared connection
            # and unwind out of order, or a suspended generator's inner block is
            # closed by GC after the outer one finished. The phantom key is
            # permanent and totally silent: every later commit_unless_in_transaction
            # sees depth > 0 and does nothing, so that connection stops committing
            # forever, with no exception, no log line and no events row.
            lost = not outermost and key not in _TXN_DEPTH
            if outermost or remaining <= 0:
                _TXN_DEPTH.pop(key, None)
                _TXN_POISON.pop(key, None)
            else:
                _TXN_DEPTH[key] = remaining
        if lost:
            # Never silently. Reaching here means the bookkeeping was already gone
            # when an inner block exited -- the anomaly above, caught rather than
            # absorbed. Inside the `finally` so it fires while an exception is
            # propagating too, but OUTSIDE the lock: obs.log() touches the
            # filesystem, and it never raises, so it cannot mask the original.
            from pipeline_app import obs

            obs.log("db.transaction_bookkeeping_lost", level="warning",
                    note="an inner transaction exited after its outer block unwound")


def _rollback_and_report(conn: sqlite3.Connection, exc: BaseException,
                         *, original: BaseException | None = None) -> None:
    """`original` is the underlying failure when `exc` is a synthetic wrapper.

    On the poison path `exc` is a TransactionPoisonedError this module just
    built, so recording only `exc` would produce an events row that says a
    transaction was poisoned and nothing whatsoever about the fault -- the one
    thing an operator actually needs."""
    from pipeline_app import obs

    try:
        conn.rollback()
    except Exception as rollback_exc:  # noqa: BLE001 -- report it, never mask the original
        obs.log("db.rollback_failed", level="critical",
                error=f"{type(rollback_exc).__name__}: {rollback_exc}")
    detail = {"exception": type(exc).__name__}
    if original is not None:
        detail["original_exception"] = type(original).__name__
        detail["original_message"] = str(original)
    obs.record_event(
        conn, kind="db.transaction_rolled_back", severity="error", source="db.transaction",
        message=f"rolled back after {type(exc).__name__}: {exc}",
        detail=detail,
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


SCHEMA_VERSION = 1


class SchemaVersionError(RuntimeError):
    """The database was written by a build newer than this code understands."""


_MIGRATIONS: list[tuple[int, "Callable[[sqlite3.Connection], None]"]] = [
    # (1, _migration_1_constrain_core_tables) -- registered in T6.
]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def init_db(db_path: Path, schema_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        # A database that already has `projects` predates versioning, so it is
        # stamped 0 and every migration runs. A database that does not is being
        # created right now by schema.sql at the target shape, so it is stamped
        # at the current version and every migration is correctly skipped.
        pre_existing = _table_exists(conn, "projects")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)",
            (0 if pre_existing else SCHEMA_VERSION,),
        )
        conn.commit()
        apply_migrations(conn)
    finally:
        conn.close()


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Run every registered migration the database has not seen, in order.

    Returns the versions applied. Raises SchemaVersionError rather than booting
    against a database a newer build has already upgraded -- silently running
    old code over a new schema is how data gets destroyed."""
    from pipeline_app import obs

    current = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    if current > SCHEMA_VERSION:
        obs.record_event(
            conn, kind="schema.version_ahead_of_code", severity="critical", source="db.init_db",
            message=f"database is at schema version {current}, this build understands "
                    f"{SCHEMA_VERSION}",
            detail={"db_version": current, "code_version": SCHEMA_VERSION},
        )
        raise SchemaVersionError(
            f"database schema version {current} is newer than this build's {SCHEMA_VERSION}; "
            f"upgrade the app or restore an older database"
        )
    applied: list[int] = []
    for version, migrate in _MIGRATIONS:
        if version <= current:
            continue
        migrate(conn)
        conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (version,))
        conn.commit()
        applied.append(version)
        obs.record_event(
            conn, kind="schema.migration_applied", severity="info", source="db.apply_migrations",
            message=f"applied schema migration {version}", detail={"version": version},
        )
    return applied


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
