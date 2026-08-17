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
from zoneinfo import ZoneInfo

NEW_HANDLE_LOOKBACK_DAYS = 90
EXISTING_HANDLE_STOP_GRACE = 3
# For a brand-new handle, if peek_upload_date keeps returning None (e.g.
# yt-dlp unavailable), there's no date-based cutoff to stop the walk -- left
# unbounded, it would call peek_upload_date once per item across the ENTIRE
# channel back-catalogue before giving up. Stop after this many consecutive
# undated is_new items instead.
NEW_HANDLE_UNDATED_STOP_GRACE = 5

# Platforms whose adapter can serve process_handle_backfill's date-ranged
# fetch. Instagram's adapter only ever fetches the newest MAX_ITEMS_PER_RUN
# items (see discovery_instagram.py / the design doc's "Backfill support"),
# so a backfill request for it would trigger a paid Bright Data job and
# silently return nothing for any window older than that cutoff -- rejected
# here before the adapter is ever called.
BACKFILL_SUPPORTED_PLATFORMS = {"youtube", "bluesky"}


class PlatformAdapter(Protocol):
    def on_disk_ids(self, repo_root: Path, handle: str) -> set[str]: ...
    def enumerate_newest_first(self, handle: str, keyword_filter: str | None) -> list[dict]: ...
    def peek_upload_date(self, *args) -> str | None: ...
    def download_item(self, repo_root: Path, handle: str, item_id: str, title: str,
                      content_type: str | None = None) -> dict: ...


class HandleFailure(Exception):
    """Carries the items already written to disk when a walk fails partway, so
    the run records real work instead of 0 (B-54). The engine's per-handle
    except branch reads .downloaded and .cause."""
    def __init__(self, cause: BaseException, downloaded: list[dict]):
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.cause, self.downloaded = cause, downloaded


def process_handle(adapter: PlatformAdapter, repo_root: Path, handle_row, now: _dt.datetime) -> list[dict]:
    handle = handle_row["handle"]
    keyword_filter = handle_row["keyword_filter"]
    on_disk = adapter.on_disk_ids(repo_root, handle)
    is_new = len(on_disk) == 0
    cutoff = now - _dt.timedelta(days=NEW_HANDLE_LOOKBACK_DAYS) if is_new else None

    downloaded: list[dict] = []
    try:
        enumerated = adapter.enumerate_newest_first(handle, keyword_filter)
        consecutive_on_disk = 0
        consecutive_undated = 0

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
                    consecutive_undated += 1
                    if consecutive_undated >= NEW_HANDLE_UNDATED_STOP_GRACE:
                        break
                    continue
                consecutive_undated = 0
                if _dt.datetime.strptime(published, "%Y-%m-%d").replace(tzinfo=_dt.timezone.utc) < cutoff:
                    break

            result = adapter.download_item(repo_root, handle, item_id, item["title"],
                                           item.get("content_type"))
            if result.get("ok"):
                downloaded.append(result)
    except HandleFailure:
        raise
    except Exception as exc:
        raise HandleFailure(exc, downloaded) from exc

    return downloaded


def process_handle_backfill(adapter: PlatformAdapter, repo_root: Path, handle_row, start_date: _dt.date, end_date: _dt.date) -> list[dict]:
    handle = handle_row["handle"]
    keyword_filter = handle_row["keyword_filter"]
    downloaded: list[dict] = []
    try:
        on_disk = adapter.on_disk_ids(repo_root, handle)
        enumerated = adapter.enumerate_newest_first(handle, keyword_filter)

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
            result = adapter.download_item(repo_root, handle, item_id, item["title"],
                                           item.get("content_type"))
            if result.get("ok"):
                downloaded.append(result)
    except HandleFailure:
        raise
    except Exception as exc:
        raise HandleFailure(exc, downloaded) from exc

    return downloaded


def process_handle_validate(adapter: PlatformAdapter, repo_root: Path, handle_row) -> dict:
    handle = handle_row["handle"]
    keyword_filter = handle_row["keyword_filter"]
    enumerated = adapter.enumerate_newest_first(handle, keyword_filter)
    if not enumerated:
        return {"ok": False, "item": None}
    newest = enumerated[0]
    result = adapter.download_item(repo_root, handle, newest["id"], newest["title"],
                                   newest.get("content_type"))
    return {"ok": bool(result.get("ok")), "item": result if result.get("ok") else None}


import concurrent.futures
import json
import os
import platform
import sqlite3
import sys
import threading
import traceback

from pipeline_app import db as db_mod
from pipeline_app import obs
from pipeline_app.discovery_paths import group_slug_collisions, run_owner_path
from pipeline_app.discovery_records import write_run_record
from pipeline_app.discovery_scheduling import encode_watermark


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


def _summarize(handle_results: list[dict]) -> dict:
    """Counts the exit-code contract is computed from. `attempted` excludes
    'skipped' handles: a backfill that skipped every handle made zero adapter
    calls, which is a different outcome from a run in which everything failed."""
    by_status: dict[str, int] = {}
    for r in handle_results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    skipped = by_status.get("skipped", 0)
    failed = by_status.get("error", 0) + by_status.get("handle_not_found", 0)
    return {
        "total": len(handle_results),
        "attempted": len(handle_results) - skipped,
        "skipped": skipped,
        "failed": failed,
        "by_status": by_status,
    }


TERMINAL_RUN_STATUSES = frozenset({"completed", "completed_with_errors", "failed",
                                   "abandoned", "locked"})


def _finish_run_guarded(conn, run_row_id: int, status: str, finished_at: str, md_path: str) -> bool:
    """Status precondition db.finish_run lacks. Read-then-write, not atomic:
    the durable fix is a `WHERE status = 'running'` inside db.finish_run, which
    belongs to P1. This closes the realistic case (minutes apart, not
    microseconds) and reports the refusal instead of silently overwriting."""
    current = db_mod.get_run(conn, run_row_id)
    if current is not None and current["status"] in TERMINAL_RUN_STATUSES and current["status"] != status:
        obs.record_event(conn, kind="discovery.finish_run_refused", severity="error",
                         source="discovery_engine",
                         message=(f"run {run_row_id} is already {current['status']}; refusing to "
                                  f"overwrite it with {status} -- it was reclaimed while still live"),
                         run_id=run_row_id)
        return False
    db_mod.finish_run(conn, run_row_id, status, finished_at, md_path)
    return True


def _write_abandoned_records_for_reclaimed_runs(conn: sqlite3.Connection, repo_root: Path, reclaimed_ids: list[int], now: _dt.datetime) -> None:
    for reclaimed_id in reclaimed_ids:
        reclaimed_row = db_mod.get_run(conn, reclaimed_id)
        finished_at = now_iso(now)
        md_path = write_run_record(repo_root, {
            "run_id": reclaimed_row["run_id"], "trigger": reclaimed_row["trigger"], "mode": reclaimed_row["mode"],
            "status": "abandoned", "started_at": reclaimed_row["started_at"], "finished_at": finished_at,
            "backfill_start": reclaimed_row["backfill_start"], "backfill_end": reclaimed_row["backfill_end"],
        }, [])  # no handle_results: we don't know how far the dead process got
        _finish_run_guarded(conn, reclaimed_id, "abandoned", finished_at, str(md_path))


def _read_run_owner(repo_root: Path, run_row_id: int) -> dict | None:
    """Read the sidecar written by `_claim_run_ownership`. Never raises: a
    missing, unreadable, or corrupt file must not block the reclaim sweep --
    it just means this run's ownership can't be confirmed and reclaim falls
    through to the plain heartbeat-age check."""
    path = run_owner_path(repo_root, run_row_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def reclaim_stale_runs_owned(conn: sqlite3.Connection, repo_root: Path, now: _dt.datetime, stale_after_s: int) -> list[int]:
    """db.reclaim_stale_runs decides purely on heartbeat age. A sleeping machine
    and a locked-DB heartbeat both freeze that clock while the run is very much
    alive, so ask the OS before stealing the lock (B-50)."""
    protected: list[int] = []
    for row in conn.execute("SELECT id FROM discovery_runs WHERE status = 'running'").fetchall():
        owner = _read_run_owner(repo_root, row["id"])
        # `_read_run_owner` only guards the JSON *parse* -- a sidecar can be
        # valid JSON with a missing/truncated/non-integer "pid" (plausible
        # exactly because this file exists to survive crash/sleep scenarios).
        # An unvalidated owner["pid"] would raise KeyError, or a non-int pid
        # would raise ctypes.ArgumentError inside _process_is_alive's Windows
        # branch, either of which would crash the whole reclaim sweep -- a
        # strictly worse failure mode than B-50 itself. Treat a malformed
        # owner file the same as a missing one: not protected, reclaim
        # proceeds normally for that row.
        if not (isinstance(owner, dict) and isinstance(owner.get("pid"), int)):
            continue
        if _process_is_alive(owner["pid"]):
            protected.append(row["id"])
            obs.record_event(conn, kind="discovery.reclaim_refused", severity="warning",
                             source="discovery_engine",
                             message=f"run {row['id']} looks stale but pid {owner['pid']} is alive",
                             detail=owner, run_id=row["id"])
    if protected:
        return []      # a live owner exists: back off entirely, do not reclaim
    return db_mod.reclaim_stale_runs(conn, now_iso(now), stale_after_s)


def sweep_stale_runs(conn: sqlite3.Connection, repo_root: Path, *, now: _dt.datetime | None = None,
                     stale_after_s: int = 600) -> list[int]:
    """The reclaim-and-abandon cascade (reclaim_stale_runs_owned +
    _write_abandoned_records_for_reclaimed_runs), exported so the cron entrypoint
    can run it without starting a run. run_discovery still runs this same cascade
    itself right before claiming the single-flight lock -- that stays in place as
    a safety net for direct incremental/backfill/validate_handle callers -- but
    the scheduled path returns before ever reaching run_discovery when today
    isn't due, so a Run Now that died hard after the day's scheduled run would
    otherwise sit 'running' until the next due day (B-52)."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    with db_mod.transaction(conn):
        reclaimed_ids = reclaim_stale_runs_owned(conn, repo_root, now, stale_after_s)
        _write_abandoned_records_for_reclaimed_runs(conn, repo_root, reclaimed_ids, now)
    return reclaimed_ids


def _open_heartbeat_connection(conn: sqlite3.Connection) -> sqlite3.Connection | None:
    """Best-effort: open a dedicated sqlite3.Connection to the same database
    file for the heartbeat thread, so it doesn't commit through the same
    Connection object the main per-handle loop writes through (both threads
    sharing one Connection is a latent risk if a future multi-statement
    transaction in the main loop gets partially committed by an unrelated
    heartbeat tick). run_discovery only receives an already-open `conn` --
    not a db_path -- so the file path is recovered via `PRAGMA database_list`
    rather than widening run_discovery's public signature (which existing
    callers/tests already depend on). Returns None for a connection with no
    on-disk file (e.g. ':memory:'), in which case the caller falls back to
    the pre-existing shared-connection behavior instead of crashing.
    """
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        db_file = row[2] if row is not None else None
    except sqlite3.Error:
        return None
    if not db_file:
        return None
    try:
        hb_conn = sqlite3.connect(db_file, check_same_thread=False)
        hb_conn.execute("PRAGMA busy_timeout = 5000")
        return hb_conn
    except sqlite3.Error:
        return None


def _process_is_alive(pid: int) -> bool:
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True     # exists, owned by someone else
        return True
    import ctypes
    SYNCHRONIZE, WAIT_TIMEOUT = 0x00100000, 0x00000102
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _claim_run_ownership(repo_root: Path, run_row_id: int, started_at: str) -> None:
    path = run_owner_path(repo_root, run_row_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": os.getpid(), "started_at": started_at,
                                "host": platform.node()}), encoding="utf-8")


def _release_run_ownership(repo_root: Path, run_row_id: int) -> None:
    run_owner_path(repo_root, run_row_id).unlink(missing_ok=True)


def _run_heartbeat_loop(conn: sqlite3.Connection, run_row_id: int, interval_s: float, stop_event: threading.Event) -> None:
    while not stop_event.wait(interval_s):
        try:
            db_mod.update_run_heartbeat(conn, run_row_id, now_iso())
        except Exception as exc:  # noqa: BLE001 - a transient failure (locked DB,
            # disk full, etc.) must not silently kill this thread: if
            # heartbeat_at freezes, another process can see the run as stale,
            # reclaim it, and start a concurrent run against the same
            # single-flight lock -- so log and keep ticking instead of letting
            # the exception propagate out of the thread target.
            print(f"heartbeat update failed: {exc}", file=sys.stderr)
            obs.record_event(conn, kind="discovery.heartbeat_failed", severity="error",
                             source="discovery_engine", message=f"heartbeat update failed: {exc}",
                             run_id=run_row_id)


def _process_one_handle(adapters: dict, repo_root, handle_row, mode, backfill_start, backfill_end, now):
    adapter = adapters[handle_row["platform"]]
    if mode == "backfill":
        return process_handle_backfill(
            adapter, repo_root, handle_row,
            start_date=_dt.datetime.strptime(backfill_start, "%Y-%m-%d").date(),
            end_date=_dt.datetime.strptime(backfill_end, "%Y-%m-%d").date(),
        )
    return process_handle(adapter, repo_root, handle_row, now=now)


def _warn_on_directory_collisions(conn: sqlite3.Connection, handle_rows) -> None:
    """Name any two handles in this run that write to one output directory.

    slugify() is lossy (it strips periods and lowercases), so two distinct
    handles can share a directory -- see discovery_paths.handle_slug for why
    that mapping is not being changed. The registration guard blocks new
    collisions but cannot see ones registered before it existed, so a run
    reports them: both handles are billed, and whichever runs second reads the
    other's captures via on_disk_ids() and records the healthy 'no_new_content'.

    Diagnostic only -- it never skips a handle. Silently dropping one would
    stop capturing content the operator asked for, which is the failure this
    is meant to surface, not cause.
    """
    by_platform: dict[str, list[str]] = {}
    for row in handle_rows:
        by_platform.setdefault(row["platform"], []).append(row["handle"])
    for platform, handles in sorted(by_platform.items()):
        for slug, colliding in sorted(group_slug_collisions(handles).items()):
            message = (f"  !! {platform}: handles {', '.join(colliding)} all share one "
                      f"output directory (output/brand-intel/{platform}/{slug}). Each is "
                      f"billed separately while writing to the same files, so all but "
                      f"one will report 'no_new_content' after reading the others' "
                      f"captures. Rename or remove all but one.")
            print(message, file=sys.stderr)
            obs.record_event(conn, kind="discovery.slug_collision", severity="warning",
                             source="discovery_engine", message=message,
                             detail={"platform": platform, "handles": colliding, "slug": slug})


class RunDeadlineExceeded(Exception):
    """Raised internally when a run has been going longer than run_deadline_s.

    Never escapes run_discovery -- it is caught by the same outer `except
    Exception` that handles any other crash outside the per-handle loop, so
    the run ends with status 'failed' through the existing path rather than a
    second, duplicate failure-handling branch."""


def run_discovery(
    conn: sqlite3.Connection, repo_root: Path, adapters: dict[str, PlatformAdapter],
    trigger: str, mode: str, backfill_start: str | None = None, backfill_end: str | None = None,
    handle_id: int | None = None, now: _dt.datetime | None = None,
    heartbeat_interval_s: float = 30.0, stale_after_s: int = 600,
    per_handle_deadline_s: float = 900.0, run_deadline_s: float = 5400.0,
) -> dict:
    """...

    B-53: `per_handle_deadline_s` bounds any single handle's adapter call (run
    through a one-worker ThreadPoolExecutor so `future.result(timeout=...)`
    can actually interrupt a blocking network call) and `run_deadline_s`
    bounds the whole run, checked between handles. Both exist so one hung
    adapter call can no longer hold the status='running' row -- and the
    single-flight lock -- forever.

    Honest caveat: `future.result(timeout=...)` abandons the worker thread,
    it does not kill it. That thread is NOT a daemon -- ThreadPoolExecutor
    workers are created non-daemon, and concurrent.futures.thread registers
    an atexit hook (_python_exit) that JOINS any still-running worker thread
    before the interpreter exits. So if the adapter call is truly wedged on a
    socket with no client-side timeout of its own, that thread doesn't just
    run quietly in the background -- it keeps running (connection still open)
    for as long as the underlying call takes to fail, AND it can block this
    process's own shutdown/exit until that happens. This unwedges the *run*
    (the DB row and the single-flight lock are released), not the thread and
    not necessarily the process. The durable fix is socket-level timeouts
    inside the adapters themselves (T4 / packages P6-P7) -- this deadline is
    a backstop, not a substitute for that.
    """
    now = now or _dt.datetime.now(_dt.timezone.utc)
    started_at = now_iso(now)
    run_id = make_run_id(now)

    if mode == "validate_handle":
        handle_row = db_mod.get_handle(conn, handle_id)
        adapter = adapters[handle_row["platform"]]
        db_mod.set_handle_status(conn, handle_id, "validating")
        try:
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
            _finish_run_guarded(conn, run_row_id, status, finished_at,
                               str(write_run_record(repo_root, {
                                   "run_id": run_id, "trigger": trigger, "mode": mode, "status": status,
                                   "started_at": started_at, "finished_at": finished_at,
                                   "backfill_start": None, "backfill_end": None,
                               }, [handle_result])))
            return {"run_row_id": run_row_id, "status": status, "counts": _summarize([handle_result])}
        except Exception as exc:  # noqa: BLE001 - an unguarded network/adapter
            # failure here must not leave the handle stuck forever in
            # status='validating' with no run row and no paired record --
            # match the existing "enumeration returned nothing" failure path
            # (set the handle back to 'invalid' AND excluded, per the spec's
            # auto-exclude-on-invalid behavior) and still produce a terminal
            # run row + markdown record documenting the error.
            db_mod.set_handle_status(conn, handle_id, "invalid")
            db_mod.set_handle_included(conn, handle_id, False)
            status = "failed"
            finished_at = now_iso()
            handle_result = {"handle": handle_row["handle"], "platform": handle_row["platform"],
                              "cohort": handle_row["cohort"], "status": "error",
                              "items_downloaded": 0, "last_seen_published_at": None,
                              "error_message": f"{type(exc).__name__}: {exc}"}
            run_row_id = db_mod.insert_terminal_run(conn, run_id, trigger, mode, status, started_at, finished_at)
            db_mod.record_handle_result(conn, run_row_id, handle_id, handle_result["status"],
                                         handle_result["items_downloaded"], handle_result["error_message"])
            _finish_run_guarded(conn, run_row_id, status, finished_at,
                               str(write_run_record(repo_root, {
                                   "run_id": run_id, "trigger": trigger, "mode": mode, "status": status,
                                   "started_at": started_at, "finished_at": finished_at,
                                   "backfill_start": None, "backfill_end": None,
                               }, [handle_result])))
            return {"run_row_id": run_row_id, "status": status, "counts": _summarize([handle_result])}

    # incremental / backfill: single-flight lock applies.
    with db_mod.transaction(conn):
        reclaimed_ids = reclaim_stale_runs_owned(conn, repo_root, now, stale_after_s)
        _write_abandoned_records_for_reclaimed_runs(conn, repo_root, reclaimed_ids, now)
    try:
        run_row_id = db_mod.insert_running_run(conn, run_id, trigger, mode, started_at, backfill_start, backfill_end)
    except sqlite3.IntegrityError:
        # discovery_runs.run_id also carries a plain UNIQUE constraint, so an
        # IntegrityError here isn't necessarily the intended single-flight
        # lock (ux_discovery_single_running) firing -- it could be a run_id
        # collision (unlikely in production given microsecond-resolution ids,
        # but real in tests that pass a fixed `now`). Confirm a running row
        # actually exists before treating this as "locked"; if it doesn't,
        # the IntegrityError was something else entirely and must not be
        # silently swallowed.
        if db_mod.get_running_run(conn) is None:
            raise
        # A fresh run_id for the locked row -- reusing `run_id` here would
        # collide with the very row that just won the lock (both share the
        # same run_id UNIQUE constraint), raising a second, unrelated
        # IntegrityError instead of cleanly recording "locked".
        # B-49: a lock loss is a no-op, not an event worth a paired markdown
        # file -- a 90-minute Bright Data run left five locked rows and five
        # junk files, one per 15-minute scheduled wake that found the lock
        # held. Keep the DB row (the honest record that a call was refused);
        # drop the file it would otherwise burn a write on.
        finished_at = now_iso()
        locked_run_id = make_run_id(_dt.datetime.now(_dt.timezone.utc))
        locked_id = db_mod.insert_locked_run(conn, locked_run_id, trigger, mode, started_at, finished_at)
        _finish_run_guarded(conn, locked_id, "locked", finished_at, None)
        return {"run_row_id": locked_id, "status": "locked", "counts": _summarize([])}

    _claim_run_ownership(repo_root, run_row_id, started_at)

    heartbeat_conn = _open_heartbeat_connection(conn)
    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_run_heartbeat_loop, args=(heartbeat_conn or conn, run_row_id, heartbeat_interval_s, stop_event), daemon=True,
    )
    heartbeat_thread.start()

    handle_results = []
    any_error = False
    outer_crash: Exception | None = None
    run_started = _dt.datetime.now(_dt.timezone.utc)
    try:
        handles = db_mod.list_handles(conn, included_only=True)
        _warn_on_directory_collisions(conn, handles)
        for handle_row in handles:
            elapsed_s = (_dt.datetime.now(_dt.timezone.utc) - run_started).total_seconds()
            if elapsed_s >= run_deadline_s:
                deadline_message = (f"  !! run exceeded its {run_deadline_s}s overall deadline "
                                    f"after {elapsed_s:.1f}s -- stopping before the remaining "
                                    f"handles, run will end 'failed'")
                print(deadline_message, file=sys.stderr)
                obs.record_event(conn, kind="discovery.run_deadline_exceeded", severity="error",
                                 source="discovery_engine", message=deadline_message,
                                 run_id=run_row_id,
                                 detail={"run_deadline_s": run_deadline_s, "elapsed_s": elapsed_s})
                raise RunDeadlineExceeded(
                    f"run exceeded its {run_deadline_s}s overall deadline after {elapsed_s:.1f}s")
            try:
                if mode == "backfill" and handle_row["platform"] not in BACKFILL_SUPPORTED_PLATFORMS:
                    skip_message = (f"  ! backfill not supported for platform "
                                    f"'{handle_row['platform']}' (handle {handle_row['handle']}) "
                                    f"-- skipping, no adapter call made")
                    print(skip_message, file=sys.stderr)
                    obs.record_event(conn, kind="discovery.backfill_unsupported", severity="warning",
                                     source="discovery_engine", message=skip_message,
                                     run_id=run_row_id,
                                     detail={"platform": handle_row["platform"],
                                             "handle": handle_row["handle"]})
                    status = "skipped"
                    db_mod.record_handle_result(conn, run_row_id, handle_row["id"], status, 0)
                    handle_results.append({
                        "handle": handle_row["handle"], "platform": handle_row["platform"],
                        "cohort": handle_row["cohort"], "status": status, "items_downloaded": 0,
                        "last_seen_published_at": None, "error_message": None,
                    })
                    continue
                # Not `with ThreadPoolExecutor(...) as pool:` -- __exit__ calls
                # shutdown(wait=True), which blocks until the worker thread
                # finishes, defeating the whole point of the timeout below. No
                # explicit shutdown() is called either: on a timeout the pool
                # (and its one worker thread) is simply abandoned. See the
                # docstring's caveat about what that means for that thread.
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = pool.submit(_process_one_handle, adapters, repo_root, handle_row,
                                     mode, backfill_start, backfill_end, now)
                downloaded = future.result(timeout=per_handle_deadline_s)
                pool.shutdown(wait=False)
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
            except concurrent.futures.TimeoutError:
                # Must come BEFORE the generic `except Exception` below --
                # concurrent.futures.TimeoutError IS an Exception subclass, so
                # Python matches except clauses top-to-bottom and this one
                # needs its own distinct error_message, not the generic
                # str(exc) from the catch-all.
                any_error = True
                timeout_message = f"TimeoutError: handle exceeded its {per_handle_deadline_s}s deadline"
                db_mod.record_handle_result(conn, run_row_id, handle_row["id"], "error", 0, timeout_message)
                handle_results.append({
                    "handle": handle_row["handle"], "platform": handle_row["platform"],
                    "cohort": handle_row["cohort"], "status": "error", "items_downloaded": 0,
                    "last_seen_published_at": None, "error_message": timeout_message,
                })
            except Exception as exc:  # noqa: BLE001 - per-handle isolation is the whole point
                any_error = True
                # B-54: a handle that fails partway through its walk still has
                # real items on disk -- HandleFailure (raised by process_handle
                # / process_handle_backfill) carries them via .downloaded so
                # this branch can record actual counts instead of hardcoding 0.
                partial = getattr(exc, "downloaded", [])
                partial_dates = [d["published"] for d in partial if d.get("published")]
                if partial_dates:
                    db_mod.set_handle_last_seen(conn, handle_row["id"], max(partial_dates))
                # B-55: str(exc) alone is the whole post-mortem when there's no
                # log file -- str(KeyError('youtube')) stores just "'youtube'"
                # with no hint it's even a KeyError, and str(IndexError()) is
                # the empty string. Name the exception type too, and stash the
                # full traceback on an event so the actual failure site is
                # still recoverable after the fact. HandleFailure already
                # carries the true underlying exception on .cause (it formats
                # its own str() the same way) -- use that when present so the
                # message names the real failure, not "HandleFailure".
                cause = getattr(exc, "cause", exc)
                error_message = f"{type(cause).__name__}: {cause}"
                obs.record_event(conn, kind="discovery.handle_failed", severity="error",
                                 source="discovery_engine", message=error_message,
                                 run_id=run_row_id,
                                 detail={"handle": handle_row["handle"], "platform": handle_row["platform"],
                                         "traceback": traceback.format_exc()})
                db_mod.record_handle_result(conn, run_row_id, handle_row["id"], "error", len(partial), error_message)
                handle_results.append({
                    "handle": handle_row["handle"], "platform": handle_row["platform"],
                    "cohort": handle_row["cohort"], "status": "error", "items_downloaded": len(partial),
                    "last_seen_published_at": db_mod.get_handle(conn, handle_row["id"])["last_seen_published_at"],
                    "error_message": error_message,
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
        if heartbeat_conn is not None:
            heartbeat_conn.close()
        _release_run_ownership(repo_root, run_row_id)

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
    finished_cleanly = _finish_run_guarded(conn, run_row_id, final_status, finished_at, str(md_path))
    if finished_cleanly and trigger == "scheduled" and final_status != "failed":
        # Store the LOCAL calendar date in the configured timezone, not the
        # UTC date -- discovery_scheduling.is_due compares this value against
        # local_now.date().isoformat(), so storing a UTC date here would
        # desync from that comparison for any schedule time where the UTC and
        # local calendar dates diverge, causing the scheduled run to re-fire
        # repeatedly. Skipped entirely when the guard refused the write: a
        # run reclaimed out from under itself (row already 'abandoned') must
        # not also stamp the watermark with its stale finished_at -- that
        # would desync is_due from reality on top of erasing the reclaim
        # evidence (B-50).
        timezone_name = db_mod.get_settings(conn)["timezone"]
        local_date = now.astimezone(ZoneInfo(timezone_name)).date().isoformat()
        db_mod.set_last_scheduled_run_date(conn, encode_watermark(local_date, timezone_name, now_iso(now)))
    return {"run_row_id": run_row_id, "status": final_status, "counts": _summarize(handle_results)}
