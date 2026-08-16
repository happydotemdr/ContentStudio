import json
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
# The thread that opened the boundary currently registered on a connection.
# Written wherever _TXN_DEPTH goes from absent to present and popped wherever
# _TXN_DEPTH is popped, so "there is a depth entry" and "we know whose it is"
# are never out of step. Any OTHER thread reaching commit_unless_in_transaction
# on that connection is a bystander whose write this boundary is about to
# swallow (T13b).
_TXN_OWNER: dict[int, int] = {}
# How many leaf commits a boundary has no-op'd for a NON-owning thread. A count,
# not a flag: an operator needs to know whether one write went missing or forty.
# Incremented under the lock by commit_unless_in_transaction, which reports
# nothing itself; transaction() drains and reports it on exit.
_TXN_SUPPRESSED: dict[int, int] = {}
_TXN_LOCK = threading.Lock()


def commit_unless_in_transaction(conn: sqlite3.Connection) -> None:
    """What every leaf helper in this module calls instead of `conn.commit()`.

    Outside a `transaction()` block it commits immediately, byte-for-byte the
    behaviour every existing caller already depends on. Inside one it is a
    no-op, so the boundary owns the commit and a multi-row invariant is atomic
    for the first time (A-70).

    It also **counts** the no-ops it performs for a thread that does not own the
    boundary. The boundary is keyed by connection and this app shares one
    connection across Starlette's threadpool and the event loop, so a leaf helper
    on a thread that is in no boundary at all still stops committing while another
    thread holds one -- and its write is discarded outright if that boundary rolls
    back (T13b). Counting here and *reporting* from `transaction()`'s exit is
    deliberate, not squeamishness: `obs.record_event` calls this function, so
    reporting from here would recurse through it forever, and one event naming N
    suppressed writes is more use to an operator than N events. A re-entrancy flag
    would break the recursion by making the second report silent, which is the
    defect class this whole mechanism exists to expose."""
    key = id(conn)
    with _TXN_LOCK:
        in_txn = _TXN_DEPTH.get(key, 0) > 0
        if in_txn and _TXN_OWNER.get(key) != threading.get_ident():
            _TXN_SUPPRESSED[key] = _TXN_SUPPRESSED.get(key, 0) + 1
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

    **Known hazard, detected rather than prevented (T13b).** The boundary is a
    property of the *connection*, and this app shares one connection across threads
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
      committing, and a fault path discards them outright.
    - `discovery_engine._open_heartbeat_connection`, which returns `None` on
      any `sqlite3.Error` and falls back to the shared connection; under a
      rolled-back boundary the heartbeat write vanishes, `heartbeat_at`
      freezes, and another process reclaims a run that is still alive. Making
      that fallback loud belongs to the discovery package; do not fix it here.

    The operator chose accept-and-detect over the three prevention designs
    (connection-per-boundary / serialize against the turn lock / process-wide
    write lock), each of which buys prevention at a cost this project should not
    pay yet. So the loss still happens -- what changed is that it is no longer
    silent: `commit_unless_in_transaction` counts every commit it swallows for a
    non-owning thread, and this block emits one `db.cross_thread_commit_suppressed`
    event on exit naming the count and the owning thread. `error` when the boundary
    rolled back (the writes are gone), `warning` when it committed (they were only
    held). Before that event existed, the `db.transaction_rolled_back` row
    attributed nothing to the collateral write, so a lost turn write and a turn
    that never wrote were the same record.

    Do not widen the boundary to be thread-local to address any of this -- that
    would break the single-connection design this app depends on."""
    key = id(conn)
    with _TXN_LOCK:
        depth = _TXN_DEPTH.get(key, 0)
        _TXN_DEPTH[key] = depth + 1
        # setdefault, so a nested block entered from a different thread cannot take
        # ownership away from the outermost one that actually holds the boundary.
        _TXN_OWNER.setdefault(key, threading.get_ident())
    outermost = depth == 0
    rolled_back = False
    try:
        yield conn
    except BaseException as exc:
        with _TXN_LOCK:
            _TXN_POISON.setdefault(key, exc)
        if outermost:
            _rollback_and_report(conn, exc)
            rolled_back = True
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
            rolled_back = True
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
                rolled_back = True
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
                # Drained with its siblings, never left behind. A count that outlives
                # its boundary makes the NEXT boundary on this connection report
                # suppressed writes that never happened -- a fabricated report, which
                # is worse than no report at all because it sends an operator hunting
                # data loss that did not occur.
                owner = _TXN_OWNER.pop(key, None)
                suppressed = _TXN_SUPPRESSED.pop(key, 0)
            else:
                _TXN_DEPTH[key] = remaining
                # An inner block is not the boundary and has nothing to report; the
                # outermost one still holds the keys and will drain them.
                owner, suppressed = None, 0
        if lost:
            # Never silently. Reaching here means the bookkeeping was already gone
            # when an inner block exited -- the anomaly above, caught rather than
            # absorbed. Inside the `finally` so it fires while an exception is
            # propagating too, but OUTSIDE the lock: obs.log() touches the
            # filesystem, and it never raises, so it cannot mask the original.
            from pipeline_app import obs

            obs.log("db.transaction_bookkeeping_lost", level="warning",
                    note="an inner transaction exited after its outer block unwound")
        if suppressed:
            _report_suppressed_commits(conn, suppressed, owner=owner,
                                       rolled_back=rolled_back)


def _report_suppressed_commits(conn: sqlite3.Connection, count: int, *,
                               owner: int | None, rolled_back: bool) -> None:
    """One event for the N leaf writes this boundary stopped another thread committing.

    Call site is the whole design (T13b). It is in `transaction()`'s `finally`,
    **after** the `_TXN_DEPTH` pop and **outside** `_TXN_LOCK`, and on the rollback
    path it runs after the rollback has already completed. Each of those is
    load-bearing:

    * After the pop, because this goes through `obs.record_event`, which calls
      `commit_unless_in_transaction`. With the depth key still present that commit
      is a no-op, so the row is never committed -- and on the rollback path it is
      rolled back along with the very loss it reports. The task would then report
      nothing at all, while a test that read the row back on the writing connection
      still passed.
    * Outside the lock, because `record_event`'s fallback path writes to the
      filesystem, and nothing that touches a disk should hold a lock every leaf
      helper in this module takes.
    * Not from `commit_unless_in_transaction`, which only counts: reporting from
      there recurses through `record_event` forever, and the obvious fix -- a
      re-entrancy flag -- makes the second, suppressed report silent, which is the
      defect class this event exists to expose.

    `rolled_back` picks the severity, and the difference is not cosmetic: on the
    rollback path those writes are GONE, on the success path they were merely held
    until this boundary committed and are still there. Reporting the two the same
    way would be a fresh instance of the same defect one level up."""
    from pipeline_app import obs

    if rolled_back:
        severity, outcome = "error", "discarded"
        message = (
            f"this boundary rolled back and discarded {count} write(s) made on the "
            f"same connection from other threads; those writes are gone"
        )
    else:
        severity, outcome = "warning", "delayed"
        message = (
            f"this boundary delayed {count} write(s) made on the same connection from "
            f"other threads until it committed; those writes survived"
        )
    obs.record_event(
        conn, kind="db.cross_thread_commit_suppressed", severity=severity,
        source="db.transaction", message=message,
        detail={"suppressed_writes": count, "owner_thread": owner, "outcome": outcome},
    )


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

# The platforms the discovery engine can actually serve. This is a THIRD copy of
# a vocabulary whose authority is `run_discovery_cron.build_adapters()` -- the
# other two being schema.sql's CHECK and _MIGRATION_1_HANDLES_STEPS' -- and it
# exists only because a migration body cannot import run_discovery_cron without
# dragging every adapter into the boot path.
#
# `test_known_platforms_is_the_hub_of_the_three_platform_vocabularies` is the pin,
# and it is THIS constant that is pinned, in both directions, to both of the
# others: registry == constant, and the CHECK SQLite is actually enforcing ==
# constant. The two round-trip tests C1 added compare the CHECK to the registry
# and never read this name at all, so they cannot see it drift -- which is what
# the first version of this comment wrongly claimed they did.
#
# Drift here is not cosmetic. `_quarantine_unknown_platforms` filters on this
# tuple while the rebuild's CHECK enforces its own list, so a constant NARROWER
# than the CHECK quarantines handles that were fine, and one WIDER lets a row the
# CHECK rejects reach the copy step and abort the boot (B-73).
KNOWN_PLATFORMS = ("youtube", "bluesky", "instagram", "linkedin-profile",
                   "linkedin-company", "facebook", "x")

# discovery_engine writes validating/validated/invalid (:243, :248, :255, :279);
# schema.sql's DEFAULT writes pending; 'failing' is B-82's, unwritten today.
# Pinned to the CHECK by test_handle_statuses_is_the_hub_the_check_and_the_
# coercion_filter_share, for the same reason and with the same two drift
# directions as KNOWN_PLATFORMS above -- `_coerce_unknown_handle_statuses`
# filters on this tuple and the rebuild enforces the CHECK.
HANDLE_STATUSES = ("pending", "validating", "validated", "invalid", "failing")


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    `INSERT ... SELECT` aborts on it. No third value passes the new CHECK, so
    coercion has to land on one of the five, and 'orphaned' is the honest choice:
    preflight.reconcile_orphaned_turns already uses it for a turn whose process
    died without reporting, which is the closest existing category to "we do not
    know what actually happened to this turn."

    This is an accepted trade, not a semantic identity. Coercing here makes a
    genuinely-orphaned turn and a ghost-status turn share one value in `turns` --
    one representation standing in for two different states, the same shape this
    package exists to remove elsewhere. What compensates is the
    `schema.turn_status_coerced` event row recorded below: it is the durable,
    queryable record that keeps "coerced from an unknown status" distinguishable
    from "actually orphaned by reconcile_orphaned_turns", so the collapse lands
    only in `turns` and not also in the record of what happened. The stage-side
    coercion to 'no_artifact' in `_coerce_unknown_stage_statuses` makes the
    identical trade for the identical reason.

    Record one event per row. No commit here, deliberately -- same reasoning as
    the stage coercion: the UPDATEs and their events belong to
    apply_migrations' transaction."""
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
    # A-71's single-running index. schema.sql deliberately does not carry a copy
    # (see the note there): it runs as one executescript() before any migration,
    # where the index cannot be built over a legacy database's duplicate
    # 'running' turns and the failure would abandon the rest of the schema. So
    # this rebuild owns the migrated database's copy, created after the
    # orphaning pass above has removed the duplicates, and init_db issues the
    # fresh database's copy after apply_migrations returns.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_turns_single_running "
    "ON turns(status) WHERE status = 'running'",
)


def _orphan_all_but_newest_running_turn(conn: sqlite3.Connection) -> list[dict]:
    """A-71's data-repair half. A legacy database can already hold two (or
    more) 'running' turns -- exactly the race `ux_turns_single_running` exists
    to prevent -- and a unique index cannot be created over duplicates that
    already violate it.

    Keeps the turn with the latest `created_at` (ties broken by `id`, both
    DESC) and orphans every other running turn. For each loser this has a
    SECOND job, not just the status flip: `preflight.reconcile_orphaned_turns`
    unwedges a stage by iterating *running* turns (preflight.py:14-18), so a
    turn this function has already set to 'orphaned' is invisible to it -- its
    stage would sit at 'running' forever, `is_locked_or_running` would answer
    True, and no operator action could free it. So a loser's stage, if still
    'running', is reset to 'ready' here -- the same no-artifact branch
    `_unwedge_stage` takes, and it destroys nothing (where an artifact does
    exist the stage merely needs re-approving, which the returned detail
    says). Not resolved by reaching into the filesystem to choose
    'awaiting_review' instead: this has no business making that call, and
    neither does a migration body.

    Its one caller is `_migration_1_constrain_core_tables`, as a precondition
    for that migration's own `turns` rebuild -- `_MIGRATION_1_TURNS_STEPS`
    appends `ux_turns_single_running` as the last step of the rebuild, and a
    UNIQUE index cannot be built over duplicates that already violate it. Every
    route to the repair goes through that migration: `init_db` reaches it via
    `apply_migrations`, and so does a caller that runs `apply_migrations`
    directly (several tests in this suite do, bypassing `init_db` entirely).

    Returns one dict per turn orphaned (`turn_id`, `stage_row_id`,
    `stage_status_was`) rather than recording the events itself, and imports no
    `obs`, so that the data repair stays testable and callable with no regard to
    whether an `events` table is present. `_record_duplicate_running_turns_orphaned`
    is the recording half; `_migration_1_constrain_core_tables` pairs the two.

    Ordered after the turn-status coercion pass, not because a coerced ghost
    status could ever read 'running' here (it becomes 'orphaned', so it is
    already excluded from the SELECT below) but to keep a fixed, readable order
    as more coercion passes are added ahead of it.

    Touches only columns that exist in both the legacy and the rebuilt shape
    of `turns` and of `stages`, so it is safe to run before either table has
    been rebuilt by this migration.

    No commit, no pragma, no executescript, no `obs` import -- callable from
    either context without regard to which one it is."""
    running = conn.execute(
        "SELECT id, stage_row_id FROM turns WHERE status = 'running' "
        "ORDER BY created_at DESC, id DESC"
    ).fetchall()
    orphaned: list[dict] = []
    for turn_id, stage_row_id in running[1:]:
        conn.execute("UPDATE turns SET status = 'orphaned' WHERE id = ?", (turn_id,))
        stage_row = conn.execute(
            "SELECT status FROM stages WHERE id = ?", (stage_row_id,)
        ).fetchone()
        stage_status_was = stage_row[0] if stage_row is not None else None
        if stage_status_was == "running":
            conn.execute("UPDATE stages SET status = 'ready' WHERE id = ?", (stage_row_id,))
        orphaned.append({"turn_id": turn_id, "stage_row_id": stage_row_id,
                          "stage_status_was": stage_status_was})
    return orphaned


def _record_duplicate_running_turns_orphaned(
    conn: sqlite3.Connection, orphaned: list[dict], *, source: str,
) -> None:
    """The event-recording half of `_orphan_all_but_newest_running_turn`, split
    out so the repair itself stays pure and `obs`-free (see that function's
    docstring). `source` is a parameter rather than a literal so the row names
    the call site that produced it -- there is one today, `db.migration_1`, and
    the split is what keeps adding a second honest. `record_event` never
    raises -- the same never-mask-the-thing-being-recorded contract as
    everywhere else it is used."""
    from pipeline_app import obs

    for detail in orphaned:
        orphaned_id = obs.record_event(
            conn, kind="schema.duplicate_running_turn_orphaned", severity="warning",
            source=source,
            message=f"turn {detail['turn_id']} on stage_row {detail['stage_row_id']} lost "
                    f"the race for the single-running-turn invariant "
                    f"(ux_turns_single_running); orphaned",
            detail=detail,
        )
        if orphaned_id == -1:
            obs.log("db.duplicate_running_turn_orphan_unrecorded", level="error", **detail)


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


# B-72's migrated half. `creators` itself needs no migration step -- it is a new
# table, so schema.sql's `CREATE TABLE IF NOT EXISTS creators` creates it on
# every database shape -- but `handles.creator_id` does: schema.sql's `handles`
# DDL is IF NOT EXISTS and is skipped outright on a pre-existing database, so
# the column declared there never reaches one. Hence the ALTER.
#
# No create-copy-drop-rename here, unlike every other block above. Probed on
# sqlite 3.50.4 rather than reasoned about: `ALTER TABLE ... ADD COLUMN ...
# REFERENCES creators(id) ON DELETE SET NULL` is accepted, is accepted inside
# apply_migrations' `BEGIN IMMEDIATE` with `foreign_keys = OFF`, and the
# ON DELETE SET NULL clause is genuinely enforced afterwards -- deleting a
# creator sets its handles' creator_id to NULL rather than deleting them. A
# rebuild would buy nothing and would destroy this index on its way past.
#
# The index is appended here for the same reason the turns indices are: a copy
# in schema.sql cannot work, because schema.sql runs before this migration and
# the column does not exist yet on the shape that needs it (see the note in
# schema.sql where the index would otherwise go). db.init_db issues the fresh
# database's copy after apply_migrations returns.
_MIGRATION_1_HANDLES_CREATOR_STEPS = (
    "ALTER TABLE handles ADD COLUMN creator_id INTEGER "
    "REFERENCES creators(id) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS idx_handles_creator ON handles(creator_id)",
)


def _quarantine_unknown_platforms(conn: sqlite3.Connection) -> None:
    """Move B-73's ghost rows aside so the rebuild's `INSERT ... SELECT` is not
    aborted by the very defect the CHECK exists to prevent. Each row is copied
    verbatim and reported -- deleting it silently would destroy the operator's
    only record of the typo, which is the same class of failure. Same ruling as
    `_coerce_unknown_stage_statuses`, one table over: do not brick, do not discard.

    Coercion is not available here the way it was for the two status columns.
    There is no honest platform to coerce `'instgram'` to -- picking one would
    invent a claim about which adapter should have run -- so the row leaves
    `handles` entirely and `handles_quarantine` is what keeps it readable.

    **The ghost's `discovery_run_handles` children go with it, and that is not
    incidental.** `adapters[handle_row["platform"]]` raises inside
    discovery_engine's per-handle isolation, which records an 'error' result --
    so the real operator's ghost has children, one per daily run. `apply_migrations`
    runs with FK enforcement OFF (SQLite's own rebuild procedure) and replaces it
    with a whole-database `foreign_key_check`, so `ON DELETE CASCADE` does not
    fire here and orphaned children would be counted as violations THIS migration
    introduced: MigrationIntegrityError, out of init_db, boot dead. Deleting them
    explicitly is the cascade the schema already declares, executed by hand
    because enforcement is off -- and the count goes into the event so the
    removal is stated rather than silent.

    Columns are named rather than `SELECT *`, and unpacked positionally:
    `apply_migrations` is public and a caller's connection need not carry a Row
    factory (the same reason `_coerce_unknown_stage_statuses` does it), and by
    this point in the migration `SELECT *` would also pick up `creator_id`, which
    `handles_quarantine` has no column for.

    No commit here, deliberately -- same reasoning as the two coercion passes:
    the INSERTs, the DELETEs and their events belong to `apply_migrations`'
    transaction, so a migration that fails later takes the quarantine records
    down with the quarantining itself. A raw `conn.commit()` would end that
    transaction outright (the `_MIGRATIONS` contract names this as the easiest
    mistake to make in a create-copy-drop-rename)."""
    from pipeline_app import obs

    placeholders = ",".join("?" * len(KNOWN_PLATFORMS))
    rows = conn.execute(
        f"SELECT id, platform, handle, display_name, cohort, keyword_filter, included, "
        f"status, added_at, validated_at, last_seen_published_at FROM handles "
        f"WHERE platform NOT IN ({placeholders})", KNOWN_PLATFORMS
    ).fetchall()
    if not rows:
        return
    now = _utcnow_iso()
    for (row_id, platform, handle, display_name, cohort, keyword_filter, included,
            status, added_at, validated_at, last_seen_published_at) in rows:
        conn.execute(
            "INSERT INTO handles_quarantine (quarantined_at, reason, platform, handle, "
            "display_name, cohort, keyword_filter, included, status, added_at, validated_at, "
            "last_seen_published_at) VALUES (?, 'unknown platform', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now, platform, handle, display_name, cohort, keyword_filter, included,
             status, added_at, validated_at, last_seen_published_at),
        )
        run_results_removed = conn.execute(
            "DELETE FROM discovery_run_handles WHERE handle_id = ?", (row_id,)
        ).rowcount
        conn.execute("DELETE FROM handles WHERE id = ?", (row_id,))
        quarantined_id = obs.record_event(
            conn, kind="schema.handle_quarantined", severity="warning",
            source="db.migration_1",
            message=f"handle {handle} names unknown platform {platform!r}; moved to "
                    f"handles_quarantine with {run_results_removed} recorded run "
                    f"result(s)",
            detail={"platform": platform, "handle": handle,
                    "run_results_removed": run_results_removed,
                    "known_platforms": list(KNOWN_PLATFORMS)},
        )
        if quarantined_id == -1:
            obs.log("db.handle_quarantine_unrecorded", level="error",
                    platform=platform, handle=handle,
                    run_results_removed=run_results_removed)


def _coerce_unknown_handle_statuses(conn: sqlite3.Connection) -> None:
    """The other half of the repair `_quarantine_unknown_platforms` does, for the
    other column the same rebuild narrows. Legacy `handles.status` is free text;
    the rebuilt table constrains it to five values, so a legacy row holding
    anything else aborts the copy step out of `init_db` -- the identical
    boot-brick `_coerce_unknown_stage_statuses` and `_coerce_unknown_turn_statuses`
    exist to prevent, one table over.

    **Coerced, not quarantined**, and that asymmetry with the platform pass is the
    point: an unknown *platform* means no adapter can ever serve the row, so it is
    unusable and has to be set aside; an unknown *status* is one corrupted field
    on an otherwise valid handle that the next discovery run can resolve. Do not
    brick, do not discard.

    **Coerced to 'pending', not 'invalid'.** 'invalid' is the verdict
    discovery_engine writes when a handle was actually looked up and not found
    (:255, :279); writing it here would claim a validation nobody performed.
    'pending' claims nothing, and it is the state a freshly added handle is in --
    the next run picks the row up and produces a real verdict.

    The accepted trade, stated rather than glossed -- the same one the turn
    coercion makes: afterwards a coerced handle and a genuinely-pending one share
    one value in `handles`, which is the collapse this package exists to remove
    elsewhere. What compensates is the `schema.handle_status_coerced` row recorded
    below: the durable, queryable record that keeps "we could not read what this
    said" distinguishable from "nobody has validated it yet". The collapse lands
    in `handles` only, never in the record of what happened.

    Record one event per row. No commit here, deliberately -- same reasoning as
    every other pass in this migration: the UPDATEs and their events belong to
    `apply_migrations`' transaction."""
    from pipeline_app import obs

    placeholders = ",".join("?" * len(HANDLE_STATUSES))
    rows = conn.execute(
        f"SELECT id, platform, handle, status FROM handles "
        f"WHERE status NOT IN ({placeholders})", HANDLE_STATUSES
    ).fetchall()
    # Unpacked positionally rather than by column name, for the same reason
    # _coerce_unknown_stage_statuses does it: apply_migrations is public and a
    # caller's connection need not carry a Row factory.
    for row_id, platform, handle, was in rows:
        conn.execute("UPDATE handles SET status = 'pending' WHERE id = ?", (row_id,))
        coerced_id = obs.record_event(
            conn, kind="schema.handle_status_coerced", severity="warning",
            source="db.migration_1",
            message=f"handle {handle} on {platform} held unknown status {was!r}; "
                    f"coerced to 'pending'",
            detail={"handle_id": row_id, "platform": platform, "handle": handle,
                    "was": was},
        )
        if coerced_id == -1:
            obs.log("db.handle_status_coercion_unrecorded", level="error",
                    handle_id=row_id, was=was)


# B-73's migrated half, and the same create-copy-drop-rename recipe as every
# rebuild above, one statement per execute() for the same reason.
#
# `creator_id` is declared here and named in the copy, not left to the ALTER that
# ran a step earlier: this DROP TABLE removes the table that ALTER just modified,
# so a rebuild that forgot the column would take B-72 back out again -- and
# `idx_handles_creator` is re-created after the RENAME because the DROP takes the
# index down with the table it was on (T7-F2's exact shape: a fresh database
# keeps its index, a migrated one silently loses it, and every fresh-database
# test passes either way). init_db's own copy of that CREATE INDEX is guarded
# `if not pre_existing:` precisely so it cannot paper over an omission here.
#
# The `status` CHECK and `consecutive_failures` belong to B-82, not B-73. They
# are added by this rebuild anyway because widening a CHECK needs another
# create-copy-drop-rename, and a second rebuild of one table inside one unshipped
# migration is waste.
_MIGRATION_1_HANDLES_STEPS = (
    """CREATE TABLE handles_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creator_id INTEGER REFERENCES creators(id) ON DELETE SET NULL,
        platform TEXT NOT NULL CHECK (platform IN
            ('youtube','bluesky','instagram','linkedin-profile','linkedin-company',
             'facebook','x')),
        handle TEXT NOT NULL,
        display_name TEXT,
        cohort TEXT NOT NULL,
        keyword_filter TEXT,
        included INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
            ('pending','validating','validated','invalid','failing')),
        consecutive_failures INTEGER NOT NULL DEFAULT 0,
        added_at TEXT NOT NULL,
        validated_at TEXT,
        last_seen_published_at TEXT,
        UNIQUE(platform, handle)
    )""",
    """INSERT INTO handles_new (id, creator_id, platform, handle, display_name, cohort,
        keyword_filter, included, status, added_at, validated_at, last_seen_published_at)
        SELECT id, creator_id, platform, handle, display_name, cohort,
        keyword_filter, included, status, added_at, validated_at, last_seen_published_at
        FROM handles""",
    "DROP TABLE handles",
    "ALTER TABLE handles_new RENAME TO handles",
    "CREATE INDEX IF NOT EXISTS idx_handles_creator ON handles(creator_id)",
)


def _migration_1_constrain_core_tables(conn: sqlite3.Connection) -> None:
    """A-47 / A-75: give `stages.status`, `turns.status` and the discovery_run_handles
    foreign keys the constraints schema.sql can never deliver to an existing table.
    Also A-71's migration-side precondition: a legacy `turns` table can already
    hold more than one 'running' row, which the `ux_turns_single_running`
    unique index appended to the turns rebuild cannot be created over.

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
    B-72's `handles.creator_id` step is appended after `discovery_run_handles`,
    following that same readability convention -- not a correctness requirement,
    per the paragraph above -- and B-73's `handles` rebuild goes after it rather
    than above it, so `discovery_run_handles` (the child) stays positioned
    before `handles`' own rebuild step. That one IS load-bearing: the rebuild's
    copy step names `creator_id`, so the ALTER that adds it must already have run.

    It stays version 1 until it has shipped."""
    _coerce_unknown_stage_statuses(conn)
    for statement in _MIGRATION_1_STAGES_STEPS:
        conn.execute(statement)
    _coerce_unknown_turn_statuses(conn)
    # Before the rebuild, deliberately: a legacy database can already hold two
    # or more 'running' turns, and ux_turns_single_running (appended to
    # _MIGRATION_1_TURNS_STEPS below) cannot be created over duplicates that
    # already violate it (A-71). This is the only place the repair happens, on
    # every route into it -- init_db's and a direct apply_migrations caller's
    # alike -- and `events` always exists by migration time, so the recording is
    # immediate and inside this migration's transaction, where it belongs.
    _record_duplicate_running_turns_orphaned(
        conn, _orphan_all_but_newest_running_turn(conn), source="db.migration_1"
    )
    for statement in _MIGRATION_1_TURNS_STEPS:
        conn.execute(statement)
    for statement in _MIGRATION_1_DISCOVERY_RUN_HANDLES_STEPS:
        conn.execute(statement)
    # Before the `handles` rebuild below, and that order is load-bearing: the
    # rebuild's create-copy-drop-rename carries `creator_id REFERENCES
    # creators(id) ON DELETE SET NULL` forward and re-creates
    # idx_handles_creator (its DROP TABLE takes the index down with the table --
    # the T7-F2 shape), and its INSERT ... SELECT can only name the column once
    # this ALTER has added it.
    for statement in _MIGRATION_1_HANDLES_CREATOR_STEPS:
        conn.execute(statement)
    # Before the rebuild, deliberately, and for the same reason the two status
    # coercions run before theirs: a legacy database can already hold a platform
    # the new CHECK rejects, and the rebuild's INSERT ... SELECT aborts on it
    # (CHECK constraint failed) -- bricking the boot on the very defect being
    # fixed (B-73).
    _quarantine_unknown_platforms(conn)
    # After the quarantine, not before it, and the order is load-bearing in one
    # direction: a ghost-platform row can hold a ghost status too, and coercing
    # first would write 'pending' into the copy `handles_quarantine` keeps --
    # destroying part of the very record the quarantine exists to preserve, and
    # emitting a coercion event for a row that is about to leave the table. Both
    # narrowed columns are repaired before the rebuild's copy step either way.
    _coerce_unknown_handle_statuses(conn)
    for statement in _MIGRATION_1_HANDLES_STEPS:
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
    is loud and wrong rather than silent and wrong, but still worth knowing.

    The owner registration is not decoration either: `commit_unless_in_transaction`
    counts a suppressed commit whenever the depth entry's owner is not the calling
    thread, so a depth entry with no owner would make every ordinary leaf call in a
    migration body look like a cross-thread loss (T13b)."""
    with _TXN_LOCK:
        _TXN_DEPTH[id(conn)] = _TXN_DEPTH.get(id(conn), 0) + 1
        _TXN_OWNER.setdefault(id(conn), threading.get_ident())


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
            # Same reasoning, same reused id, one rung further along: a leaked owner
            # entry names a thread that is dead by then, so the first real boundary on
            # the app's connection would count every leaf commit as a cross-thread
            # loss and report writes that were never suppressed. A migration never
            # reports a count of its own (it runs on init_db's private connection,
            # which no other thread has), so draining here loses nothing (T13b).
            _TXN_OWNER.pop(key, None)
            _TXN_SUPPRESSED.pop(key, None)
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
        # A-71's fresh-database copy of the single-running index, issued here
        # rather than in schema.sql because schema.sql runs as one
        # executescript() before any migration: on a pre-existing database
        # already holding two 'running' turns the index cannot be built, the
        # script abandons every later statement (`events` included, it is near
        # the end of the file), and the boot dies with a half-built schema and
        # nowhere to record it. Worse, anything schema.sql-adjacent that mutated
        # rows to make the index buildable would have committed that mutation
        # with no `events` table to record it in.
        #
        # It cannot raise HERE, and that is the property to preserve. Four
        # cases -- the fourth was missing from this comment until T9, which is
        # why it is spelled out rather than trimmed:
        #   * brand-new database -- schema.sql just created an empty `turns`,
        #     so there is nothing to violate;
        #   * pre-existing and stamped 0 -- apply_migrations has just run
        #     migration 1, which orphans duplicate running turns before
        #     rebuilding `turns` and creates this same index as the last step of
        #     that rebuild, so this is an IF NOT EXISTS no-op;
        #   * pre-existing and already stamped 1 by a SHIPPED build -- migration
        #     1 is skipped, but apply_migrations wraps each migration in BEGIN
        #     IMMEDIATE, under which SQLite's DDL is transactional, so the stamp
        #     landed only if the whole of migration 1 did. Again a no-op;
        #   * pre-existing and stamped 1 by an INTERMEDIATE build of this
        #     package -- migration 1 is still under construction and grows a
        #     step per task, so such a database carries the stamp without the
        #     steps added after it was written, and skips them permanently.
        #     Dev-only (version 1 is unshipped) and loud rather than silent, but
        #     it is real: do not reason from an exhaustiveness claim here.
        # A later migration that reintroduces duplicate running turns, or that
        # rebuilds `turns` without recreating the index, breaks that reasoning
        # and this statement is where the boot will fail. That is the intended
        # tripwire -- fix the migration, do not move this line.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_turns_single_running "
            "ON turns(status) WHERE status = 'running'"
        )
        # B-72's fresh-database copy of idx_handles_creator, here for the same
        # reason as the statement above: schema.sql cannot carry it. On a
        # pre-existing database `CREATE TABLE IF NOT EXISTS handles` is skipped,
        # so the column does not exist yet when schema.sql runs and the index
        # raises `no such column: creator_id` inside executescript -- before
        # `events` is created, so the boot dies with a half-built schema and
        # nowhere to record it (probed on sqlite 3.50.4, not reasoned about).
        # Migration 1 owns the pre-existing database's copy
        # (_MIGRATION_1_HANDLES_CREATOR_STEPS); this owns the fresh one.
        #
        # Guarded by `not pre_existing`, unlike the unconditional statement
        # above, and the guard is load-bearing rather than an optimisation.
        # `pre_existing` is False exactly when schema.sql has just built the
        # whole schema at the target shape and no migration will run over it --
        # which is the one case with a column but no index. Issuing it
        # unconditionally would instead create the index on a MIGRATED database
        # too, and that silently repairs the migration's own omission: T10
        # rebuilds `handles` in this same migration 1, its DROP TABLE takes
        # idx_handles_creator down with the table, and a rebuild that forgot to
        # re-create it would be papered over here -- with
        # test_every_foreign_key_column_is_still_indexed_after_the_migration
        # going green over the defect, since it boots through init_db. A
        # migration must leave the schema complete on its own; a direct
        # apply_migrations caller (several tests are) never reaches this line at
        # all.
        #
        # The cost of the guard, stated rather than glossed: on the fourth case
        # above -- pre-existing, stamped 1 by an intermediate build, so
        # migration 1's ALTER never ran -- this is skipped, and neither the
        # column nor the index appears. That is dev-only and identical to what
        # every other step of the unshipped migration 1 does on that shape.
        if not pre_existing:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_handles_creator ON handles(creator_id)"
            )
        conn.commit()
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
    from pipeline_app import obs

    try:
        cur = conn.execute(
            "INSERT INTO turns (stage_row_id, status, created_at, events_path) "
            "VALUES (?, ?, ?, ?)",
            (stage_row_id, status, created_at, events_path),
        )
    except sqlite3.IntegrityError as exc:
        # Four constraints on `turns` raise IntegrityError and only ONE of them
        # is the race: the ux_turns_single_running UNIQUE index, the `status`
        # CHECK, the `stage_row_id` FOREIGN KEY, and NOT NULL on
        # `events_path` -- all four confirmed by probe, not assumed. Reporting
        # all four as a concurrent start puts a confident wrong diagnosis in the
        # one place the operator is told to look, and makes two distinct faults
        # share one representation.
        #
        # Discriminated on `exc.sqlite_errorname` (sqlite3.Error, Python 3.11+),
        # never on the message: the errorname is a stable API contract, the
        # message is prose. The raw errorname goes into `detail` on BOTH
        # branches, so what the operator reads is the constraint class SQLite
        # reported rather than this function's interpretation of it.
        if exc.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE":
            # ux_turns_single_running fired: another turn is already running. The
            # application-level checks (route pre-check and run_stage_turn) both
            # read zero -- this is the race they cannot see (A-71).
            kind = "turn.concurrent_start_rejected"
            message = f"refused a second running turn for stage_row_id={stage_row_id}"
        else:
            kind = "turn.insert_rejected"
            message = (f"refused a turn for stage_row_id={stage_row_id}: "
                       f"{exc.sqlite_errorname}. This is NOT a concurrency race")
        event_id = obs.record_event(
            conn, kind=kind, severity="error", source="db.create_turn",
            message=message,
            detail={"stage_row_id": stage_row_id, "status": status,
                    "sqlite_errorname": exc.sqlite_errorname, "error": str(exc)},
        )
        # Outside a db.transaction() the event commits and outlives the raise
        # (verified: the failed INSERT leaves in_transaction True, and the events
        # row still survives a reconnect). INSIDE one it does not -- the caller's
        # boundary rolls back on this very exception and takes the only record of
        # the fault with it. No caller wraps create_turn today, but it is a public
        # helper, and "the record died with the thing it was recording" is the
        # defect this package exists to remove. Both branches equally: a
        # misdiagnosed insert is no less worth keeping than a race.
        if event_id != -1 and _TXN_DEPTH.get(id(conn), 0) > 0:
            obs.log(kind, level="error", stage_row_id=stage_row_id,
                    sqlite_errorname=exc.sqlite_errorname, error=str(exc),
                    note="inside a caller transaction: the events row will be rolled "
                         "back with it, so this log line is the durable record")
        raise
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


def set_handle_brands(conn: sqlite3.Connection, handle_id: int, brands: list[str]) -> None:
    """Replace handle_id's brand tags with exactly `brands` (order-insensitive,
    duplicates collapsed). Delete-then-insert rather than a diff: with at most
    a handful of tags per handle the atomicity is worth more than the extra
    writes, and the caller never needs to know which tags were already there.

    Wrapped in transaction(conn), not a bare commit_unless_in_transaction after
    both statements: this connection is shared across Starlette's threadpool,
    and an uncommitted DELETE sitting on it between the two execute() calls
    would be flushed early by an unrelated leaf helper's commit on the same
    connection if the INSERT ever raised in between -- silently clearing the
    handle's tags with no INSERT to replace them.
    """
    with transaction(conn):
        conn.execute("DELETE FROM handle_brands WHERE handle_id = ?", (handle_id,))
        conn.executemany(
            "INSERT INTO handle_brands (handle_id, brand) VALUES (?, ?)",
            [(handle_id, b) for b in dict.fromkeys(brands)],
        )


def get_handle_brands(conn: sqlite3.Connection, handle_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT brand FROM handle_brands WHERE handle_id = ? ORDER BY brand", (handle_id,)
    ).fetchall()
    return [r["brand"] for r in rows]


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


HANDLE_FAILURE_THRESHOLD = 3


def record_handle_failure(conn: sqlite3.Connection, handle_id: int, *, now_iso: str,
                          threshold: int = HANDLE_FAILURE_THRESHOLD) -> str:
    """Count one consecutive per-handle failure; return the handle's status.

    B-82: set_handle_status was only ever called from the one-shot validate
    branch, so a handle that validated at registration and later died kept
    status='validated', included=1 forever while raising an error row into
    discovery_run_handles on every single run. On the roster a permanently
    broken source was indistinguishable from a healthy one.

    At `threshold` consecutive failures the handle is downgraded to 'failing'.
    The counter is the evidence; the status is the signal. P8 calls this from
    the per-handle error branch of discovery_engine.

    Uses `transaction()`, not `commit_unless_in_transaction` (C3) -- do not
    "fix" this to match T9's C6 on `upsert_creator`. `upsert_creator` was a
    single already-atomic INSERT ... ON CONFLICT; this is THREE writes -- the
    counter increment, the status downgrade, and the event -- that must land
    together or not at all, so the boundary stays. The known cross-thread
    suppression hazard documented on `transaction()` itself applies here too
    and is not this function's to solve (T13b tracks it).

    Raises LookupError naming `handle_id` when no such row exists (C1). An
    earlier draft returned the string "unknown" here instead -- the same
    defect T9 fixed on `link_handle_to_creator`, one task later: "unknown"
    travels back in the SAME channel as a real status, so a caller looping
    over handles (P8) cannot tell "this handle is now failing" from "there is
    no such handle" without special-casing a magic string, and it is also a
    fourth value outside HANDLE_STATUSES, which the CHECK constraint will
    never accept. The check runs BEFORE `transaction()` opens, deliberately:
    doing it after an UPDATE that matched nothing would leave a transaction
    boundary open around a no-op write for what is actually a caller error,
    triggering `transaction()`'s rollback-and-report machinery (a spurious
    `db.transaction_rolled_back` event) for something that never wrote
    anything and needs no rollback at all."""
    from pipeline_app import obs

    if get_handle(conn, handle_id) is None:
        raise LookupError(f"no handle with id {handle_id}")

    with transaction(conn):
        conn.execute(
            "UPDATE handles SET consecutive_failures = consecutive_failures + 1 WHERE id = ?",
            (handle_id,),
        )
        row = conn.execute(
            "SELECT handle, platform, status, consecutive_failures FROM handles WHERE id = ?",
            (handle_id,),
        ).fetchone()
        status = row["status"]
        if row["consecutive_failures"] >= threshold and status in ("validated", "pending"):
            status = "failing"
            conn.execute("UPDATE handles SET status = 'failing' WHERE id = ?", (handle_id,))
            obs.record_event(
                conn, kind="handle.marked_failing", severity="error",
                source="db.record_handle_failure",
                message=f"{row['platform']} handle {row['handle']} failed "
                        f"{row['consecutive_failures']} consecutive runs; marked failing",
                detail={"handle_id": handle_id, "platform": row["platform"],
                        "handle": row["handle"],
                        "consecutive_failures": row["consecutive_failures"],
                        # C4: this is when the THIRD failure landed, not when the
                        # handle started failing (the first failure's timestamp
                        # was never recorded) -- "since" would claim a
                        # measurement this code never took.
                        "marked_failing_at": now_iso},
            )
    return status


def clear_handle_failures(conn: sqlite3.Connection, handle_id: int) -> None:
    """A successful fetch resets the counter and lifts a 'failing' handle back to
    'validated'. 'invalid' is deliberately untouched: that is a registration-time
    verdict, not a failure counter.

    Raises LookupError naming `handle_id` when no such row exists (C2),
    identical to T9's F1 on `link_handle_to_creator`: without the check the
    UPDATE matches zero rows and this returns None -- the success value -- so
    "the handle recovered" and "there is no such handle" would share one
    representation."""
    cur = conn.execute(
        "UPDATE handles SET consecutive_failures = 0, "
        "status = CASE WHEN status = 'failing' THEN 'validated' ELSE status END WHERE id = ?",
        (handle_id,),
    )
    if cur.rowcount == 0:
        # Before commit_unless_in_transaction, not after: a call that changed
        # nothing must not commit as though it had.
        raise LookupError(f"no handle with id {handle_id}")
    commit_unless_in_transaction(conn)


def upsert_creator(conn: sqlite3.Connection, *, slug: str, display_name: str) -> int:
    """One creator, keyed by a stable slug. P10 calls this from the manifests.

    `commit_unless_in_transaction` rather than a `transaction()` block, like
    every other leaf helper here: a single INSERT ... ON CONFLICT is already
    atomic, and a boundary opened in a leaf helper is the cross-thread
    suppression hazard documented on `transaction()` itself."""
    conn.execute(
        "INSERT INTO creators (slug, display_name) VALUES (?, ?) "
        "ON CONFLICT(slug) DO UPDATE SET display_name = excluded.display_name",
        (slug, display_name),
    )
    commit_unless_in_transaction(conn)
    return conn.execute("SELECT id FROM creators WHERE slug = ?", (slug,)).fetchone()["id"]


def get_creator_by_slug(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM creators WHERE slug = ?", (slug,)).fetchone()


def link_handle_to_creator(conn: sqlite3.Connection, handle_id: int, creator_id: int) -> None:
    """Raises LookupError when `handle_id` names no row.

    Without the check the UPDATE matches nothing and this returns None --
    exactly what it returns on success -- so "there was no such handle" and "the
    link was established" share one representation, and P10 populating
    `creators` from the manifests would report success having linked nothing.

    The silence was also asymmetric: a `creator_id` that names no row was
    already loud, because the foreign key raises. Only `handle_id` could be
    wrong for free.

    `rowcount` is an exact signal here rather than an inference. This is a
    single-row UPDATE by primary key, so it is 1 or 0 -- and 1 covers relinking
    a handle to the creator it already has, because SQLite counts the rows the
    WHERE clause matched, not the values it changed (probed, not assumed).

    Two things deliberately absent. No `events` row: the raise is itself the
    human-reachable signal and it propagates, so a row here would record a
    caller's bad argument twice. And no rollback: the failed UPDATE changed
    nothing, while this helper is callable inside a `db.transaction()` boundary
    where a rollback would silently discard the caller's work -- the boundary
    owns that decision, and it already makes it on this exception."""
    cur = conn.execute("UPDATE handles SET creator_id = ? WHERE id = ?", (creator_id, handle_id))
    if cur.rowcount == 0:
        # Before commit_unless_in_transaction, not after: a call that changed
        # nothing must not commit as though it had.
        raise LookupError(
            f"no handle with id {handle_id}; nothing was linked to creator {creator_id}"
        )
    commit_unless_in_transaction(conn)


def list_handles_for_creator(conn: sqlite3.Connection, creator_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM handles WHERE creator_id = ? ORDER BY platform, handle", (creator_id,)
    ).fetchall()


def list_unlinked_handles(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Handles with no creator. After P10's migration this is the coverage gap
    list: every row here is a creator the roster cannot report on."""
    return conn.execute(
        "SELECT * FROM handles WHERE creator_id IS NULL ORDER BY platform, handle"
    ).fetchall()


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


def list_unacknowledged_events(conn: sqlite3.Connection, *, since_iso: str,
                               limit: int = 50) -> list[dict]:
    """Unacknowledged error/critical events since `since_iso`, newest first.

    Returns plain dicts, not Rows: `detail` is parsed out of its JSON column so
    a template can iterate it, and the shape is the contract /doctor renders
    (see P1's published interface). A detail that will not parse becomes
    {"raw": <text>} -- losing the whole event over a formatting problem would be
    the same silence this table exists to end."""
    rows = conn.execute(
        "SELECT * FROM events WHERE acknowledged = 0 AND severity IN ('error','critical') "
        "AND occurred_at >= ? ORDER BY occurred_at DESC, id DESC LIMIT ?",
        (since_iso, limit),
    ).fetchall()
    out: list[dict] = []
    for row in rows:
        detail = None
        if row["detail"] is not None:
            try:
                parsed = json.loads(row["detail"])
                detail = parsed if isinstance(parsed, dict) else {"raw": row["detail"]}
            except (ValueError, TypeError):
                detail = {"raw": row["detail"]}
        out.append({
            "id": row["id"], "occurred_at": row["occurred_at"], "kind": row["kind"],
            "severity": row["severity"], "source": row["source"], "message": row["message"],
            "detail": detail, "run_id": row["run_id"],
            "acknowledged": bool(row["acknowledged"]),
        })
    return out


def acknowledge_event(conn: sqlite3.Connection, event_id: int) -> None:
    conn.execute("UPDATE events SET acknowledged = 1 WHERE id = ?", (event_id,))
    commit_unless_in_transaction(conn)


def count_unacknowledged_events(conn: sqlite3.Connection) -> int:
    """ALL-TIME count of unacknowledged error/critical events -- deliberately
    unbounded by `list_unacknowledged_events`'s window or limit. Read
    together, the two distinguish "nothing else to show" from "more exist,
    silently excluded by the window or the row cap" -- the recurring defect
    class, reappearing inside this task's own dashboard if left unpaired."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE acknowledged = 0 "
        "AND severity IN ('error','critical')"
    ).fetchone()
    return row["n"]
