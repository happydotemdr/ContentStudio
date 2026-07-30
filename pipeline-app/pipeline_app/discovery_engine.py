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
