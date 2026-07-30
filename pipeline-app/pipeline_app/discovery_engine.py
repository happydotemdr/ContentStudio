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


def process_handle_backfill(adapter: PlatformAdapter, repo_root: Path, handle_row, start_date: _dt.date, end_date: _dt.date) -> list[dict]:
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
