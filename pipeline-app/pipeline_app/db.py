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

    **Does not cover DDL.** This context manager, like `commit_unless_in_transaction`,
    relies entirely on Python's sqlite3 implicit transaction control -- and that
    control only ever opens an implicit transaction ahead of DML
    (INSERT/UPDATE/DELETE). A `CREATE TABLE` or `ALTER TABLE` executed inside a
    `transaction()` block lands on disk the instant it runs, commits or no commits,
    and a rollback after it does not undo it (A-72). Schema migrations therefore do
    not use this: `db.apply_migrations` issues its own explicit
    `conn.execute("BEGIN IMMEDIATE")` around each migration instead, which does make
    DDL atomic. Reach for `transaction()` for row-level invariants only.

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
    # Read back rather than assumed: every FK constraint in schema.sql is inert
    # without this, and nothing else in the app ever checks. A fresh connection is
    # never inside a transaction, so the write should always take -- the same
    # reasoning behind every other verified pragma in this file (_set_foreign_keys,
    # _restore_foreign_keys). The impossible branch is logged, not asserted, because
    # this runs on the startup path and must not crash the app over a defensive check.
    conn.execute("PRAGMA foreign_keys = ON")
    if not bool(conn.execute("PRAGMA foreign_keys").fetchone()[0]):
        from pipeline_app import obs
        obs.log("db.foreign_keys_not_enabled", level="critical",
                note="PRAGMA foreign_keys = ON did not take on a fresh connection; "
                     "every FK constraint in schema.sql is inert without it")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


SCHEMA_VERSION = 1


class SchemaVersionError(RuntimeError):
    """The database was written by a build newer than this code understands."""


class StrandedPoisonError(RuntimeError):
    """The connection carries a transaction poison that predates this call.

    Distinct from NestedMigrationError: this is neither a transaction nor a
    boundary, so telling the caller to close its boundary would name something that
    does not exist. _exit_migration_boundary's own comment explains how a poison
    entry can survive onto a REUSED connection id."""


class NestedMigrationError(RuntimeError):
    """apply_migrations was called on a connection already inside a transaction.

    A dedicated type, not a bare RuntimeError: the migration tests raise
    RuntimeError from their own migration bodies, so a bare one here would let a
    precondition failure masquerade as the migration failure under test."""


class MigrationIntegrityError(RuntimeError):
    """A migration introduced foreign key violations that did not exist before it.

    Distinct from a plain sqlite3.IntegrityError, which SQLite raises per statement
    while enforcement is on. apply_migrations turns enforcement OFF around its
    transaction -- SQLite's own documented procedure for a table rebuild, and the
    only way DROP TABLE can run at all -- so this is what replaces it: a
    whole-database check whose failure is this code's fault, not the data's."""


STAGE_STATUSES = ("locked", "ready", "running", "awaiting_review", "approved",
                  "stale", "no_artifact")

# turn_service writes running/aborted/complete/failed; preflight writes orphaned.
# Verified against the call sites, not assumed: turn_service.py:129 (running),
# :210 (aborted), :216 (complete/failed), preflight.py:16 (orphaned) (A-75).
TURN_STATUSES = ("running", "complete", "failed", "aborted", "orphaned")


def _coerce_unknown_stage_statuses(conn: sqlite3.Connection) -> None:
    """A legacy row can already hold the typo the new CHECK exists to prevent, and
    the rebuild's `INSERT ... SELECT` aborts on it (verified: IntegrityError "CHECK
    constraint failed") -- bricking the boot on the very defect being fixed. Coerce
    to 'no_artifact', which is loud in the UI and destroys nothing, and record one
    event per row.

    No commit here, deliberately: the UPDATEs and their events belong to
    apply_migrations' transaction, so a migration that fails later takes its
    coercion records down with the coercions themselves. record_event's own commit
    no-ops inside the migration boundary, which is what makes that hold."""
    from pipeline_app import obs

    placeholders = ",".join("?" * len(STAGE_STATUSES))
    rows = conn.execute(
        f"SELECT id, project_id, stage_id, status FROM stages "
        f"WHERE status NOT IN ({placeholders})", STAGE_STATUSES
    ).fetchall()
    # Unpacked positionally rather than by column name: apply_migrations is public
    # and a caller's connection need not carry a Row factory.
    for row_id, project_id, stage_id, was in rows:
        conn.execute("UPDATE stages SET status = 'no_artifact' WHERE id = ?", (row_id,))
        coerced_id = obs.record_event(
            conn, kind="schema.stage_status_coerced", severity="warning",
            source="db.migration_1",
            message=f"stage {stage_id} held unknown status {was!r}; "
                    f"coerced to 'no_artifact'",
            detail={"stage_row_id": row_id, "project_id": project_id, "was": was},
        )
        if coerced_id == -1:
            obs.log("db.stage_status_coercion_unrecorded", level="error",
                    stage_row_id=row_id, was=was)


def _coerce_unknown_turn_statuses(conn: sqlite3.Connection) -> None:
    """Same ruling as `_coerce_unknown_stage_statuses`, one table over: a legacy
    row can already hold a status the new CHECK rejects, and the rebuild's
    `INSERT ... SELECT` aborts on it. A turn whose status cannot be interpreted
    *is* an orphan (preflight.reconcile_orphaned_turns already uses that status
    for turns whose process died without reporting), so that is where it goes.
    Record one event per row.

    No commit here, deliberately -- same reasoning as the stage coercion: the
    UPDATEs and their events belong to apply_migrations' transaction."""
    from pipeline_app import obs

    placeholders = ",".join("?" * len(TURN_STATUSES))
    rows = conn.execute(
        f"SELECT id, stage_row_id, status FROM turns "
        f"WHERE status NOT IN ({placeholders})", TURN_STATUSES
    ).fetchall()
    for row_id, stage_row_id, was in rows:
        conn.execute("UPDATE turns SET status = 'orphaned' WHERE id = ?", (row_id,))
        coerced_id = obs.record_event(
            conn, kind="schema.turn_status_coerced", severity="warning",
            source="db.migration_1",
            message=f"turn {row_id} on stage_row {stage_row_id} held unknown status "
                    f"{was!r}; coerced to 'orphaned'",
            detail={"turn_id": row_id, "stage_row_id": stage_row_id, "was": was},
        )
        if coerced_id == -1:
            obs.log("db.turn_status_coercion_unrecorded", level="error",
                    turn_id=row_id, was=was)


# One statement per execute(), never executescript(): executescript issues an
# implicit COMMIT before it runs, which would end apply_migrations' transaction and
# make this rebuild non-atomic. create-copy-drop-rename is exactly where that
# mistake is easiest to make, which is why the _MIGRATIONS contract names it.
# Verified: all four run inside BEGIN IMMEDIATE and commit together, and
# `turns.stage_row_id REFERENCES stages(id)` still resolves afterwards -- no
# PRAGMA legacy_alter_table needed, because nothing references `stages_new`.
_MIGRATION_1_STAGES_STEPS = (
    """CREATE TABLE stages_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        stage_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN
            ('locked','ready','running','awaiting_review','approved','stale','no_artifact')),
        claude_session_id TEXT,
        approved_at TEXT,
        UNIQUE(project_id, stage_id)
    )""",
    """INSERT INTO stages_new (id, project_id, stage_id, status, claude_session_id, approved_at)
        SELECT id, project_id, stage_id, status, claude_session_id, approved_at FROM stages""",
    "DROP TABLE stages",
    "ALTER TABLE stages_new RENAME TO stages",
)


# Same create-copy-drop-rename recipe as _MIGRATION_1_STAGES_STEPS, one statement
# per execute() for the same reason. The CREATE INDEX is appended to this tuple,
# not left to schema.sql: schema.sql's own `CREATE INDEX IF NOT EXISTS
# idx_turns_stage_row` runs BEFORE the migration (init_db's ordering) and so lands
# on the OLD `turns` table -- this rebuild's `DROP TABLE turns` then takes that
# index down with the table it was on, and a migrated database would silently come
# back unindexed while a fresh one would not (A-75).
_MIGRATION_1_TURNS_STEPS = (
    """CREATE TABLE turns_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stage_row_id INTEGER NOT NULL REFERENCES stages(id) ON DELETE CASCADE,
        status TEXT NOT NULL CHECK (status IN
            ('running','complete','failed','aborted','orphaned')),
        created_at TEXT NOT NULL,
        finished_at TEXT,
        events_path TEXT NOT NULL,
        cost_usd REAL
    )""",
    """INSERT INTO turns_new (id, stage_row_id, status, created_at, finished_at, events_path, cost_usd)
        SELECT id, stage_row_id, status, created_at, finished_at, events_path, cost_usd FROM turns""",
    "DROP TABLE turns",
    "ALTER TABLE turns_new RENAME TO turns",
    "CREATE INDEX IF NOT EXISTS idx_turns_stage_row ON turns(stage_row_id)",
)


# discovery_run_handles gets no new CHECK (schema.sql never declared a status
# vocabulary for it, and A-75 does not ask for one) -- only ON DELETE CASCADE on
# both its foreign keys and the two covering indices, appended after the RENAME
# for the same reason the turns indices are: schema.sql's copies would land on the
# table this DROP TABLE is about to remove.
_MIGRATION_1_DISCOVERY_RUN_HANDLES_STEPS = (
    """CREATE TABLE discovery_run_handles_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
        handle_id INTEGER NOT NULL REFERENCES handles(id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        items_downloaded INTEGER NOT NULL DEFAULT 0,
        error_message TEXT
    )""",
    """INSERT INTO discovery_run_handles_new
        (id, run_id, handle_id, status, items_downloaded, error_message)
        SELECT id, run_id, handle_id, status, items_downloaded, error_message
        FROM discovery_run_handles""",
    "DROP TABLE discovery_run_handles",
    "ALTER TABLE discovery_run_handles_new RENAME TO discovery_run_handles",
    "CREATE INDEX IF NOT EXISTS idx_drh_run ON discovery_run_handles(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_drh_handle ON discovery_run_handles(handle_id)",
)


def _migration_1_constrain_core_tables(conn: sqlite3.Connection) -> None:
    """A-47 / A-75: give `stages.status`, `turns.status` and the discovery_run_handles
    foreign keys the constraints schema.sql can never deliver to an existing table.

    Every statement in schema.sql is `CREATE TABLE IF NOT EXISTS`, so no constraint
    added there reaches a database that already has the table. This is the only path
    that applies them, and it is why schema_version exists.

    Rebuild order: stages, then turns, then discovery_run_handles. `turns` is
    stages' FK child, so it is rebuilt immediately after its parent to keep the
    coerce-then-rebuild pairs for one FK relationship adjacent and readable;
    `discovery_run_handles` is independent of both (no FK to or from turns) and is
    placed last because its own two parents -- discovery_runs and handles -- are
    not rebuilt by this migration at all yet. This ordering is not load-bearing
    for correctness today: apply_migrations disables FK enforcement for the whole
    duration of this function, so DROP TABLE never trips a child row regardless of
    sequence, and a RENAME only needs fixing up by SQLite when something still
    references the table's *temporary* `_new` name, which nothing here ever does.
    It matters for readability and for whoever adds T9's `creators` and T10's
    `handles` rebuilds to this same function: `discovery_run_handles` (the child)
    must stay positioned before `handles`' own rebuild step when that lands, i.e.
    append T10's block after this one rather than inserting it above.

    Later tasks in this package extend this same migration further (handles,
    creators). It stays version 1 until it has shipped."""
    _coerce_unknown_stage_statuses(conn)
    for statement in _MIGRATION_1_STAGES_STEPS:
        conn.execute(statement)
    _coerce_unknown_turn_statuses(conn)
    for statement in _MIGRATION_1_TURNS_STEPS:
        conn.execute(statement)
    for statement in _MIGRATION_1_DISCOVERY_RUN_HANDLES_STEPS:
        conn.execute(statement)


_MIGRATIONS: list[tuple[int, "Callable[[sqlite3.Connection], None]"]] = [
    (1, _migration_1_constrain_core_tables),
    #
    # A migration body must not call conn.commit(), conn.rollback(), or any db.py
    # leaf helper that would. apply_migrations registers its boundary in
    # _TXN_DEPTH so the helpers no-op, but a raw commit still ends the
    # transaction and un-does the atomicity guarantee.
    #
    # It must not open a db.transaction() either. That boundary cannot help --
    # it does not cover DDL -- and inside a migration it is non-outermost, so it
    # leaves a _TXN_POISON entry behind on the connection's id.
    #
    # And it must not call conn.executescript(): that issues an implicit COMMIT
    # before running, which destroys apply_migrations' boundary silently. It is
    # the natural idiom for SQLite's create-copy-drop-rename recipe and is
    # already used elsewhere in this module, so this is the easiest of these
    # three mistakes to make. Use separate conn.execute() calls.
]


def _validate_migration_order(migrations) -> None:
    """Fail at import rather than wedge a database at runtime.

    apply_migrations walks this list as written and skips anything already
    applied, so an out-of-order entry runs late and stamps the version BACKWARDS:
    with [(2, m2), (1, m1)] on a v0 database, m2 runs and stamps 2, then m1 runs
    and stamps 1. Migration 2 has run but the database claims it has not, so the
    next boot re-runs it, hits `duplicate column name`, and is stuck at a version
    that is neither true nor recoverable. A duplicate version does the same."""
    versions = [version for version, _ in migrations]
    if versions != sorted(set(versions)):
        raise RuntimeError(
            f"_MIGRATIONS must be strictly increasing with no duplicates, got {versions}"
        )


_validate_migration_order(_MIGRATIONS)


def _enter_migration_boundary(conn: sqlite3.Connection) -> None:
    """Make db.py's own leaf helpers no-op inside a migration.

    `apply_migrations` opens its boundary with a raw `BEGIN IMMEDIATE`, because
    `transaction()` relies on implicit transaction control and so cannot cover DDL.
    But `commit_unless_in_transaction` decides "am I inside a boundary?" by
    consulting `_TXN_DEPTH`, which only `transaction()` populates -- so without this
    registration a migration body calling ANY db.py helper commits mid-migration,
    the later rollback rolls back nothing, and half-applied is indistinguishable
    from never-ran again. Not hypothetical: SQLite's only recipe for adding a CHECK
    is create-copy-drop-rename, and the copy step is exactly the data movement an
    author would route through an existing helper.

    apply_migrations refuses a connection that already carries poison, and
    _exit_migration_boundary pops it whenever the depth reaches zero. A body that
    leaks a depth increment defeats both, and with several migrations registered the
    next one would then be refused for its predecessor's swallowed failure -- which
    is loud and wrong rather than silent and wrong, but still worth knowing."""
    with _TXN_LOCK:
        _TXN_DEPTH[id(conn)] = _TXN_DEPTH.get(id(conn), 0) + 1


def _exit_migration_boundary(conn: sqlite3.Connection) -> None:
    """Release the boundary. Cleanup only -- the poison check happens in
    `apply_migrations` before the stamp and the commit, which is the last moment
    refusing is still possible."""
    key = id(conn)
    with _TXN_LOCK:
        # A missing key is NOT a normal exit. `.get(key, 1) - 1` yields 0 either way,
        # so without this flag "healthy decrement from 1" and "my boundary was
        # clobbered" are the same silent return -- and the second means every leaf
        # helper in the migration body committed with no boundary at all, which is
        # exactly the defect this registration exists to prevent. transaction()
        # fixed this class once and kept its detector; copying its arithmetic
        # without its detector re-introduced it.
        lost = key not in _TXN_DEPTH
        remaining = _TXN_DEPTH.get(key, 1) - 1
        if remaining <= 0:
            _TXN_DEPTH.pop(key, None)
            # Pop the poison too, or it outlives this connection. A db.transaction()
            # opened inside a migration body is non-outermost (this boundary already
            # holds depth 1), so its finally takes the nested branch and leaves
            # _TXN_POISON[key] behind. init_db then closes its connection and the app
            # allocates a new one immediately after -- CPython reuses the freed
            # address readily -- so the first SUCCESSFUL outermost transaction() on
            # the app's real connection would roll back correct work and raise
            # TransactionPoisonedError citing a boot-time migration failure.
            _TXN_POISON.pop(key, None)
        else:
            _TXN_DEPTH[key] = remaining
    if lost:
        # Logged outside the lock: obs.log() touches the filesystem, and it never
        # raises, so it cannot mask whatever else is going wrong.
        from pipeline_app import obs

        obs.log("db.migration_bookkeeping_lost", level="error",
                note="the migration boundary was gone before the migration finished")


def _schema_cookie(conn: sqlite3.Connection) -> "int | None":
    """SQLite's schema cookie: it bumps when a schema change COMMITS, and a rollback
    leaves it where it was.

    This exists because every *inferred* answer to "did the migration's changes
    survive?" has been wrong. Whether `rollback()` raised does not tell you (it is a
    silent no-op with no open transaction). Whether `conn.in_transaction` is False
    does not tell you (true both when the body committed and when it rolled itself
    back). A body can commit its boundary with `executescript()` and then open a
    fresh transaction, so the rollback succeeds while the DDL is already durable.

    It is NOT a verdict, and this function deliberately does not present it as one:
    it is blind to DML, and inside an uncommitted write transaction it already shows
    the bumped value. It goes into the failure event's `detail` as a raw reading for
    whoever investigates. Returns None when it cannot be read at all."""
    try:
        return conn.execute("PRAGMA schema_version").fetchone()[0]
    except Exception:  # noqa: BLE001 -- an unreadable cookie is its own reading
        return None


def _swallowed_failure(conn: sqlite3.Connection) -> "BaseException | None":
    """The inner failure a migration body caught and discarded, if there was one.

    Peeks without popping: `_exit_migration_boundary` still owns the cleanup. A
    `db.transaction()` opened inside a migration body is non-outermost, so its
    failure sets `_TXN_POISON` and skips `_rollback_and_report` entirely -- nothing
    reports it. Discarding that quietly would make a migration that swallowed a
    failure indistinguishable from one that ran cleanly, and it would be stamped and
    recorded as applied. `transaction()` refuses exactly this on its outermost exit;
    so does `apply_migrations`."""
    with _TXN_LOCK:
        return _TXN_POISON.get(id(conn))


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


def _foreign_key_violations(conn: sqlite3.Connection) -> set:
    """`PRAGMA foreign_key_check` as a comparable set of (child table, rowid, parent, fk index)."""
    return {tuple(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()}


def _set_foreign_keys(conn: sqlite3.Connection, enabled: bool) -> bool:
    """Set enforcement and return what it ACTUALLY reads back, not what was asked.

    `PRAGMA foreign_keys` is a documented no-op inside a transaction (verified on
    sqlite 3.50.4: issued inside BEGIN IMMEDIATE the value does not move). A caller
    that assumes the write took gets a connection running with no referential
    integrity and no indication -- "asked and never checked" is the exact shape this
    package exists to remove, so this returns the reading and every caller compares."""
    conn.execute(f"PRAGMA foreign_keys = {'ON' if enabled else 'OFF'}")
    return bool(conn.execute("PRAGMA foreign_keys").fetchone()[0])


def _restore_foreign_keys(conn: sqlite3.Connection, wanted: bool, version: int) -> None:
    """Put enforcement back, and never raise doing it.

    Called from a `finally:` and from the path where the transaction never opened.
    A raise from either would replace the migration's own exception with this one --
    and from the `finally:` it would also skip the failure-reporting block below,
    losing the only durable record that the migration failed at all. Reporting must
    never mask the thing being reported; `obs.record_event` holds the same contract
    for the same reason.

    `_set_foreign_keys` returns a reading rather than an intent, so "it did not take"
    and "it raised" are two different observations and both are said out loud."""
    from pipeline_app import obs

    try:
        if _set_foreign_keys(conn, wanted) == wanted:
            return
        reading = "unchanged"
    except Exception as exc:  # noqa: BLE001 -- restoring must not mask the failure
        reading = f"{type(exc).__name__}: {exc}"
    obs.log("db.foreign_keys_not_restored", level="critical", version=version,
            wanted=wanted, reading=reading,
            note="PRAGMA foreign_keys is a no-op inside a transaction; this connection "
                 "is running without referential integrity enforcement and must be "
                 "closed, not reused")


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Run every registered migration the database has not seen, in order.

    Returns the versions applied. Raises SchemaVersionError rather than booting
    against a database a newer build has already upgraded -- silently running
    old code over a new schema is how data gets destroyed.

    `conn` must not already be inside a transaction: this opens its own with a
    raw `BEGIN IMMEDIATE`, and sqlite3 rejects a nested one.

    **Caller contract on failure:** when this raises, the connection may still hold an
    open write transaction -- deliberately, because committing it would persist a
    partial migration. The caller must CLOSE the connection without committing.
    `init_db` does. A caller that catches and continues will have the partial
    migration committed by the next leaf helper that calls
    `commit_unless_in_transaction`."""
    from pipeline_app import obs

    # Enforced, not merely documented. If the caller's boundary has already done
    # DML, BEGIN IMMEDIATE raises and the failure is loud. If it has NOT, BEGIN
    # succeeds, the depth goes 1->2, and on the failure path it returns to 1 -- so
    # record_event's commit no-ops and the caller's rollback destroys the
    # schema.migration_failed row. The one durable record of the failure, lost,
    # with nothing to indicate it.
    if conn.in_transaction or _TXN_DEPTH.get(id(conn)):
        raise NestedMigrationError(
            "apply_migrations opens its own BEGIN IMMEDIATE and cannot run inside an "
            "existing transaction; commit or close the caller's boundary first"
        )
    with _TXN_LOCK:
        stranded = _TXN_POISON.get(id(conn))
    if stranded is not None:
        # Refusing here is also what lets the swallowed-failure check below be a plain
        # `is not None`: nothing can be inherited past this point, so identity
        # comparison against a pre-existing entry is unnecessary -- and it would have
        # been wrong anyway, since transaction() populates the map with setdefault, so
        # a later genuine failure never replaces an older object.
        raise StrandedPoisonError(
            f"connection carries a stranded transaction poison "
            f"({type(stranded).__name__}: {stranded}); it predates this call. Nothing "
            f"clears it in-process -- restart the app, and if it recurs the boundary "
            f"bookkeeping in db.py is leaking"
        )

    current = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
    if current > SCHEMA_VERSION:
        ahead_id = obs.record_event(
            conn, kind="schema.version_ahead_of_code", severity="critical",
            source="db.apply_migrations",
            message=f"database is at schema version {current}, this build understands "
                    f"{SCHEMA_VERSION}",
            detail={"db_version": current, "code_version": SCHEMA_VERSION},
        )
        if ahead_id == -1:
            obs.log("db.version_ahead_unrecorded", level="critical",
                    db_version=current, code_version=SCHEMA_VERSION,
                    message=f"database is at schema version {current}, this build "
                            f"understands {SCHEMA_VERSION}")
        raise SchemaVersionError(
            f"database schema version {current} is newer than this build's {SCHEMA_VERSION}; "
            f"upgrade the app or restore an older database"
        )
    applied: list[int] = []
    for version, migrate in _MIGRATIONS:
        if version <= current:
            continue
        # Explicit BEGIN IMMEDIATE, not db.transaction(). Python's sqlite3 opens an implicit
        # transaction only for DML, never for DDL -- so under the default
        # transaction control a migration's CREATE/ALTER lands on disk the instant
        # it executes and survives any rollback. Verified: without BEGIN,
        # `in_transaction` is False after a CREATE TABLE and rollback leaves the
        # table; with BEGIN it is True and the table is gone. db.transaction()
        # relies on that same implicit control, so it does NOT make DDL atomic and
        # is the wrong tool here.
        #
        # Without this, a migration that raises halfway leaves its DDL applied and
        # the version stamp untouched -- "partially applied" and "never ran" become
        # the same state. The next boot re-runs it, the already-applied ALTER fails
        # with "duplicate column name", and the database is wedged at that version
        # permanently, with every boot reporting the same error and no way to tell
        # which half already happened.
        #
        # IMMEDIATE rather than deferred: this boundary only ever writes, and on a
        # connection shared across threads under WAL a deferred transaction that
        # upgrades to a write can take SQLITE_BUSY_SNAPSHOT, which busy_timeout does
        # not resolve.
        cookie_before = _schema_cookie(conn)
        # SQLite's only recipe for adding a CHECK to an existing table is
        # create-copy-drop-rename, and `DROP TABLE stages` performs an implicit
        # DELETE that trips every child row referencing it (verified:
        # IntegrityError "FOREIGN KEY constraint failed", against the operator's
        # own turns table). SQLite's documented procedure disables enforcement
        # around the rebuild, and the pragma is a no-op inside a transaction -- so
        # here, before BEGIN, is the only moment it can be done.
        #
        # Enforcement is not traded for nothing. `foreign_key_check` below replaces
        # it and is strictly stronger: it checks the whole database rather than one
        # statement's rows.
        fk_was_enabled = bool(conn.execute("PRAGMA foreign_keys").fetchone()[0])
        # Everything between disabling enforcement and opening the transaction runs
        # inside this try. Below it, the `finally:` restores; above it, nothing has
        # changed yet. In between there is no other restorer -- and `BEGIN IMMEDIATE`
        # is precisely where a failure is expected, since SQLITE_BUSY is the whole
        # reason it is IMMEDIATE. Without this the caller gets its connection back
        # with referential integrity silently off: no exception about it, no log, no
        # event, and every later orphan accepted. Confirmed by probe, not argument.
        try:
            if _set_foreign_keys(conn, False):
                raise MigrationIntegrityError(
                    f"could not disable foreign key enforcement before migration "
                    f"{version}; the rebuild would fail on DROP TABLE, and refusing to "
                    f"start beats a half-applied schema"
                )
            violations_before = _foreign_key_violations(conn)
            conn.execute("BEGIN IMMEDIATE")
        except BaseException:
            _restore_foreign_keys(conn, fk_was_enabled, version)
            raise
        _enter_migration_boundary(conn)
        failure: BaseException | None = None
        rollback_failed = False
        pending_when_it_failed: bool | None = None
        try:
            migrate(conn)
            swallowed = _swallowed_failure(conn)
            if swallowed is not None:
                # Checked BEFORE the stamp and the commit, the last moment refusing is
                # still possible. The body caught an inner transaction()'s failure and
                # carried on; committing now would stamp a half-done migration as
                # applied while that inner failure went unreported by anyone, because
                # non-outermost blocks skip _rollback_and_report entirely.
                raise TransactionPoisonedError(
                    f"migration {version} swallowed an inner transaction failure: "
                    f"{type(swallowed).__name__}: {swallowed}"
                ) from swallowed
            new_violations = _foreign_key_violations(conn) - violations_before
            if new_violations:
                raise MigrationIntegrityError(
                    f"migration {version} introduced {len(new_violations)} foreign key "
                    f"violation(s), e.g. {sorted(new_violations)[:3]}"
                )
            if violations_before:
                # Pre-existing, so not this migration's fault and not grounds for
                # refusing to boot -- but carrying them silently through a rebuild
                # would be the discard this package exists to remove. Same ruling as
                # _coerce_unknown_stage_statuses: do not brick, do not discard.
                pre_id = obs.record_event(
                    conn, kind="schema.pre_existing_fk_violations", severity="warning",
                    source="db.apply_migrations",
                    message=f"{len(violations_before)} foreign key violation(s) predate "
                            f"migration {version} and were carried through the rebuild",
                    detail={"version": version, "count": len(violations_before),
                            "sample": [list(v) for v in sorted(violations_before)[:5]]},
                )
                if pre_id == -1:
                    obs.log("db.pre_existing_fk_violations_unrecorded", level="warning",
                            version=version, count=len(violations_before))
            conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (version,))
            conn.commit()
        except BaseException as exc:
            failure = exc
            # Captured HERE, before rollback() destroys it. It reports exactly one
            # thing: whether the body's work was still pending when it failed (True)
            # or the body had already ended the transaction itself (False). It is the
            # only observation on offer that flips when a body commits DML, which the
            # schema cookie cannot see.
            #
            # It does NOT distinguish a body that committed from one that rolled ITSELF
            # back -- both read False. Within the _MIGRATIONS contract that cannot
            # happen, since a body may not call conn.rollback(); outside it, this
            # reading is silent on the difference. Stated because the previous version
            # of this comment claimed more than the reading supports, which is the same
            # overclaiming that produced five wrong verdicts here.
            #
            # It was earlier rejected for making a bad VERDICT, which was a category
            # error: this is a raw reading, and the reader draws the conclusion.
            try:
                pending_when_it_failed = conn.in_transaction
            except Exception:  # noqa: BLE001 -- unreadable is its own reading
                pending_when_it_failed = None
            try:
                # Unconditional: rollback() with no open transaction is a harmless no-op.
                conn.rollback()
            except Exception as rollback_exc:  # noqa: BLE001 -- report, never mask
                rollback_failed = True
                obs.log("db.migration_rollback_failed", level="critical", version=version,
                        error=f"{type(rollback_exc).__name__}: {rollback_exc}")
        finally:
            # Leave the boundary BEFORE reporting. record_event commits through
            # commit_unless_in_transaction, which no-ops while the depth is held --
            # so reporting inside would leave the only durable record of the failure
            # uncommitted, and it would die with the process that needed to report it.
            _exit_migration_boundary(conn)
            # Restored here, before the failure report below, and VERIFIED. On the
            # normal failure path rollback() has already ended the transaction so this
            # takes; on the path where rollback itself failed a transaction is still
            # open and the pragma silently does nothing. That second case is precisely
            # a restore that did not restore, so it is read back and reported rather
            # than assumed. Via the helper, which cannot raise: this is a `finally:`,
            # and an exception here would replace the migration's own and skip the
            # reporting block below it.
            _restore_foreign_keys(conn, fk_was_enabled, version)
        if failure is not None:
            # Report OBSERVATIONS, not a verdict.
            #
            # Five attempts to state what survived have each been wrong in a different
            # way: whether rollback() raised (a no-op with no open transaction), whether
            # conn.in_transaction is False (true both when the body committed and when
            # it rolled itself back), whether the body returned normally, whether the
            # stamp advanced, and the schema cookie (blind to DML, and already bumped
            # inside an uncommitted transaction). Each new classifier was blind to a
            # migration shape the previous one handled.
            #
            # So this makes no claim it cannot support. The message says what is always
            # true -- the migration failed, a rollback was attempted, the database must
            # be checked -- and `detail` carries the raw readings for whoever looks. A
            # statement that cannot be false cannot conflate "nothing happened" with
            # "half of it is on disk", which is what every verdict here has done.
            cookie_after = _schema_cookie(conn)
            kind = "schema.migration_failed"
            message = (
                f"migration {version} failed and a rollback was "
                f"{'attempted and itself failed' if rollback_failed else 'attempted'}; "
                f"the database may contain partial changes -- verify before restarting: "
                f"{type(failure).__name__}: {failure}"
            )
            detail = {"version": version, "exception": type(failure).__name__,
                      "rollback_failed": rollback_failed,
                      "pending_when_it_failed": pending_when_it_failed,
                      "schema_cookie_before": cookie_before,
                      "schema_cookie_after": cookie_after,
                      "applied_before_failure": applied}
            # Recording COMMITS. If anything is still pending on this connection, that
            # commit would make a partial migration durable -- turning a state SQLite
            # discards on close into permanent corruption. So check first, and when it
            # is not safe, report to the log only. That is not a silent path: `failure`
            # is re-raised below, init_db's caller aborts the boot, and a process that
            # refuses to start is itself a surfacing signal.
            try:
                still_pending = conn.in_transaction
                pending_reading = still_pending
            except Exception:  # noqa: BLE001 -- unreadable means assume the worst
                still_pending = True
                pending_reading = "unreadable"
            if still_pending:
                # NOTE: nothing renders this. /doctor shows `events`, so the worst
                # reachable migration failure currently surfaces on no operator-facing
                # surface -- only in the log file and in the boot abort. Recording it
                # here is not an option: the commit would make the partial migration
                # durable. Raised as a known gap rather than pretended away.
                obs.log("db.migration_failed_unrecoverable", level="critical",
                        version=version, kind=kind, message=message, detail=detail,
                        in_transaction=pending_reading,
                        note="no events row written: a commit here would persist the "
                             "pending work")
            else:
                event_id = obs.record_event(
                    conn, kind=kind, severity="critical", source="db.apply_migrations",
                    message=message, detail=detail,
                )
                if event_id == -1:
                    # record_event never raises; it returns -1. Here the database is the
                    # component that just failed, so this is the likeliest place for the
                    # record itself to be lost -- and a missing record must not look
                    # like a migration that never failed.
                    obs.log("db.migration_failure_unrecorded", level="critical",
                            version=version, kind=kind, message=message)
            raise failure
        # Keep `current` honest inside the loop, so the skip guard above reflects
        # what has actually been applied rather than the state at entry.
        current = version
        applied.append(version)
        applied_id = obs.record_event(
            conn, kind="schema.migration_applied", severity="info", source="db.apply_migrations",
            message=f"applied schema migration {version}", detail={"version": version},
        )
        if applied_id == -1:
            # Without this, a migration that ran and a migration whose success was
            # never recorded look the same in `events` -- and `events` is what an
            # operator reads to reconstruct what a boot actually did.
            obs.log("db.migration_success_unrecorded", level="error", version=version)
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
