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
