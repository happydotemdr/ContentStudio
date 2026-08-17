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

    def download_item(self, repo_root, handle, item_id, title, content_type=None):
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


def test_new_handle_stops_after_undated_stop_grace_when_peek_always_none():
    # peek_upload_date returning None for every item (yt-dlp unavailable,
    # etc.) must not walk the entire channel back-catalogue -- it should stop
    # after NEW_HANDLE_UNDATED_STOP_GRACE consecutive undated items.
    from pipeline_app.discovery_engine import NEW_HANDLE_UNDATED_STOP_GRACE

    enumerated = [{"id": f"v{i}", "title": f"video {i}", "published": None} for i in range(50)]
    adapter = FakeAdapter(enumerated, on_disk=set(), dates={})  # peek always returns None
    results = process_handle(adapter, None, FakeHandleRow(handle="@new", keyword_filter=None), now=NOW)
    assert results == []
    assert len(adapter.peek_calls) == NEW_HANDLE_UNDATED_STOP_GRACE


def test_new_handle_undated_streak_resets_on_a_dated_item():
    enumerated = [
        {"id": "v1", "title": "undated", "published": None},
        {"id": "v2", "title": "undated", "published": None},
        {"id": "v3", "title": "undated", "published": None},
        {"id": "v4", "title": "undated", "published": None},
        {"id": "v5", "title": "dated", "published": None},  # resets the streak (peek returns a date)
        {"id": "v6", "title": "undated", "published": None},
    ]
    adapter = FakeAdapter(enumerated, on_disk=set(), dates={"v5": "2026-07-20"})
    results = process_handle(adapter, None, FakeHandleRow(handle="@new", keyword_filter=None), now=NOW)
    assert [r["id"] for r in results] == ["v5"]
    # all 6 items get peeked: the streak reset at v5 lets v6 be attempted too
    assert adapter.peek_calls == ["v1", "v2", "v3", "v4", "v5", "v6"]


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


import json
import os
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from pipeline_app import db
from pipeline_app.discovery_engine import (
    _claim_run_ownership,
    _finish_run_guarded,
    _process_is_alive,
    make_run_id,
    now_iso,
    run_discovery,
)
from pipeline_app.discovery_paths import run_owner_path


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

    def download_item(self, repo_root, handle, item_id, title, content_type=None):
        return {"id": item_id, "ok": True, "published": "2026-07-29"}


def test_now_iso_and_make_run_id_are_stable_format():
    now = __import__("datetime").datetime(2026, 7, 30, 6, 0, 0, tzinfo=__import__("datetime").timezone.utc)
    assert now_iso(now) == "2026-07-30T06:00:00+00:00"
    run_id = make_run_id(now)
    assert run_id.startswith("2026-07-30T06-00-00")


def test_process_is_alive_reports_true_for_this_process_and_false_for_a_dead_pid():
    """NOT os.kill(pid, 0): on Windows os.kill calls TerminateProcess for any
    signal other than CTRL_C_EVENT/CTRL_BREAK_EVENT, so the POSIX idiom would
    kill the very run being checked on."""
    assert _process_is_alive(os.getpid()) is True
    assert _process_is_alive(0x7FFFFFFE) is False


def test_a_run_writes_an_owner_file_and_removes_it_when_it_finishes(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@a": []})},
                           trigger="manual", mode="incremental")
    assert not run_owner_path(tmp_path, result["run_row_id"]).exists()


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


def test_run_discovery_warns_when_two_handles_share_one_directory(engine_conn, tmp_path, capsys):
    """The registration guard cannot see collisions registered before it landed,
    so a run names them. Without this the second handle is billed and then
    reports the healthy 'no_new_content' after reading the first's files."""
    db.create_handle(engine_conn, "youtube", "john.doe.5", "A", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "johndoe5", "B", "guru", None, now_iso())
    adapter = SingleFakeAdapter({
        "john.doe.5": [{"id": "v1", "title": "x", "published": None}],
        "johndoe5": [{"id": "v2", "title": "y", "published": None}],
    })

    run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")

    err = capsys.readouterr().err
    assert "john.doe.5" in err
    assert "johndoe5" in err
    assert "johndoe5" in err  # the shared directory component


def test_run_discovery_does_not_warn_when_every_handle_has_its_own_directory(
        engine_conn, tmp_path, capsys):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "@b", "B", "guru", None, now_iso())
    adapter = SingleFakeAdapter({
        "@a": [{"id": "v1", "title": "x", "published": None}],
        "@b": [{"id": "v2", "title": "y", "published": None}],
    })

    run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")

    assert "share" not in capsys.readouterr().err


def test_run_discovery_does_not_warn_across_platforms(engine_conn, tmp_path, capsys):
    """Directories are namespaced by platform, so youtube/nasa and bluesky/nasa
    are distinct and must not be reported."""
    db.create_handle(engine_conn, "youtube", "nasa", "A", "guru", None, now_iso())
    db.create_handle(engine_conn, "bluesky", "NASA", "B", "guru", None, now_iso())
    adapter = SingleFakeAdapter({})

    run_discovery(engine_conn, tmp_path, {"youtube": adapter, "bluesky": adapter},
                  trigger="manual", mode="incremental")

    assert "share" not in capsys.readouterr().err


def test_run_discovery_still_processes_both_colliding_handles(engine_conn, tmp_path):
    """The warning is a diagnostic, not a gate: silently skipping a handle would
    stop capturing content the operator asked for. Flag it, then proceed."""
    db.create_handle(engine_conn, "youtube", "john.doe.5", "A", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "johndoe5", "B", "guru", None, now_iso())
    adapter = SingleFakeAdapter({
        "john.doe.5": [{"id": "v1", "title": "x", "published": None}],
        "johndoe5": [{"id": "v2", "title": "y", "published": None}],
    })

    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                           trigger="manual", mode="incremental")

    assert len(db.list_run_handle_results(engine_conn, result["run_row_id"])) == 2


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


def test_run_discovery_validate_handle_sets_invalid_and_excludes_on_crash(engine_conn, tmp_path):
    handle_id = db.create_handle(engine_conn, "youtube", "@crashy", "Crashy", "guru", None, now_iso())
    adapter = SingleFakeAdapter({}, fail_handles={"@crashy"})
    result = run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    assert result["status"] == "failed"
    row = db.get_handle(engine_conn, handle_id)
    assert row["status"] == "invalid"
    assert row["included"] == 0


def test_reclaim_cascade_leaves_nothing_behind_when_it_fails_partway(engine_conn, tmp_path, monkeypatch):
    """FAULT (A-70). The staleness cascade first marks reclaimed runs 'abandoned'
    (db.reclaim_stale_runs), then writes each one's abandoned-run record and sets
    finished_at/md_path (_write_abandoned_records_for_reclaimed_runs). Without a
    transaction boundary the 'abandoned' status commits immediately, so an
    interruption in the second step leaves a run stuck at status='abandoned' with
    finished_at=NULL and md_path=NULL forever -- nothing else in the app ever
    revisits an already-abandoned run. Force the failure on the second step and
    assert the first step's write (the status flip) did not survive either."""
    import pipeline_app.discovery_engine as de_mod

    stale_started = "2026-07-30T05:00:00+00:00"
    stale_id = db.insert_running_run(engine_conn, "stale-run", "manual", "incremental", stale_started)
    db.update_run_heartbeat(engine_conn, stale_id, "2026-07-30T05:01:00+00:00")
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]})
    now = __import__("datetime").datetime(2026, 7, 30, 6, 0, 0, tzinfo=__import__("datetime").timezone.utc)

    def raise_write_run_record(*args, **kwargs):
        raise RuntimeError("boom mid-way through the abandoned-run record")

    monkeypatch.setattr(de_mod, "write_run_record", raise_write_run_record)

    with pytest.raises(RuntimeError):
        run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental", now=now)

    stale_row = db.get_run(engine_conn, stale_id)
    assert stale_row["status"] == "running"
    assert stale_row["finished_at"] is None
    assert stale_row["md_path"] is None


class SlowFakeAdapter(SingleFakeAdapter):
    """Sleeps during download_item so the heartbeat loop gets a chance to tick
    at least once during a run, without depending on exact wall-clock timing."""
    def __init__(self, *args, sleep_s=0.2, **kwargs):
        super().__init__(*args, **kwargs)
        self._sleep_s = sleep_s

    def download_item(self, repo_root, handle, item_id, title, content_type=None):
        time.sleep(self._sleep_s)
        return super().download_item(repo_root, handle, item_id, title)


def test_run_discovery_heartbeat_ticks_at_least_once_during_a_run(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SlowFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]}, sleep_s=0.2)

    result = run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="incremental", heartbeat_interval_s=0.05,
    )

    assert result["status"] == "completed"
    run_row = db.get_run(engine_conn, result["run_row_id"])
    # The heartbeat is cleared/overwritten by finish_run's own bookkeeping in
    # some schemas, so the strongest signal available post-hoc is simply that
    # a heartbeat was recorded at all -- confirming the loop body executed at
    # least once during the (deliberately slow) handle processing.
    assert run_row["heartbeat_at"] is not None


def test_run_discovery_crash_outside_handle_loop_is_recorded_as_failed(engine_conn, tmp_path, monkeypatch):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]})

    def _boom(conn, included_only=False):
        raise RuntimeError("simulated list_handles crash")

    monkeypatch.setattr(db, "list_handles", _boom)

    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")

    assert result["status"] == "failed"
    run_row = db.get_run(engine_conn, result["run_row_id"])
    assert run_row["status"] == "failed"
    assert run_row["md_path"] is not None


def test_run_discovery_scheduled_trigger_updates_last_scheduled_run_date(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]})
    now = __import__("datetime").datetime(2026, 7, 30, 6, 0, 0, tzinfo=__import__("datetime").timezone.utc)

    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="scheduled", mode="incremental", now=now)

    assert result["status"] == "completed"
    assert db.get_settings(engine_conn)["last_scheduled_run_date"] == "2026-07-30"


def test_run_discovery_scheduled_trigger_stores_local_date_not_utc_date(engine_conn, tmp_path):
    # now is 2026-07-31T02:00:00 UTC, which is 2026-07-30T21:00:00-05:00 in
    # America/Chicago -- a full calendar day earlier locally. The stored
    # last_scheduled_run_date must match the LOCAL date (2026-07-30), since
    # that's what discovery_scheduling.is_due compares against.
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]})
    now = __import__("datetime").datetime(2026, 7, 31, 2, 0, 0, tzinfo=__import__("datetime").timezone.utc)

    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="scheduled", mode="incremental", now=now)

    assert result["status"] == "completed"
    assert db.get_settings(engine_conn)["last_scheduled_run_date"] == "2026-07-30"


def test_run_discovery_manual_trigger_does_not_update_last_scheduled_run_date(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]})
    now = __import__("datetime").datetime(2026, 7, 30, 6, 0, 0, tzinfo=__import__("datetime").timezone.utc)

    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental", now=now)

    assert result["status"] == "completed"
    assert db.get_settings(engine_conn)["last_scheduled_run_date"] is None


def test_backfill_skips_unsupported_platform_without_calling_adapter(engine_conn, tmp_path):
    db.create_handle(engine_conn, "instagram", "@ig_handle", "IG", "guru", None, now_iso())

    class ExplodingAdapter:
        def on_disk_ids(self, repo_root, handle):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def enumerate_newest_first(self, handle, keyword_filter):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def peek_upload_date(self, item_id):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def download_item(self, repo_root, handle, item_id, title, content_type=None):
            raise AssertionError("must not be called for a backfill-unsupported platform")

    result = run_discovery(
        engine_conn, tmp_path, {"instagram": ExplodingAdapter()},
        trigger="manual", mode="backfill",
        backfill_start="2026-06-01", backfill_end="2026-06-30",
    )
    assert result["status"] == "completed"
    results = db.list_run_handle_results(engine_conn, result["run_row_id"])
    assert len(results) == 1
    assert results[0]["status"] == "skipped"
    assert results[0]["items_downloaded"] == 0


def test_run_discovery_result_carries_per_status_counts(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "@good", "G", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "@bad", "B", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@good": [{"id": "v1", "title": "x", "published": None}]},
                                fail_handles={"@bad"})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                           trigger="manual", mode="incremental")
    assert result["counts"]["total"] == 2
    assert result["counts"]["attempted"] == 2
    assert result["counts"]["failed"] == 1
    assert result["counts"]["skipped"] == 0


def test_a_heartbeat_write_failure_leaves_an_event_not_only_a_print(engine_conn, tmp_path, monkeypatch):
    """D-02: this print is the sole detector of the condition that lets B-50's
    double-run happen, and on the scheduled path it goes nowhere."""
    monkeypatch.setattr(db, "update_run_heartbeat",
                        lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SlowFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": None}]}, sleep_s=0.2)
    run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual",
                  mode="incremental", heartbeat_interval_s=0.05)
    rows = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.heartbeat_failed'").fetchall()
    assert rows and rows[0]["severity"] == "error"


def test_a_directory_collision_leaves_an_event_naming_both_handles(engine_conn, tmp_path):
    db.create_handle(engine_conn, "youtube", "john.doe.5", "A", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "johndoe5", "B", "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                  trigger="manual", mode="incremental")
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.slug_collision'").fetchone()
    assert row is not None
    assert "john.doe.5" in row["message"] and "johndoe5" in row["message"]


def test_a_backfill_skip_leaves_an_event(engine_conn, tmp_path):
    db.create_handle(engine_conn, "instagram", "@ig_handle", "IG", "guru", None, now_iso())

    class ExplodingAdapter:
        def on_disk_ids(self, repo_root, handle):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def enumerate_newest_first(self, handle, keyword_filter):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def peek_upload_date(self, item_id):
            raise AssertionError("must not be called for a backfill-unsupported platform")

        def download_item(self, repo_root, handle, item_id, title, content_type=None):
            raise AssertionError("must not be called for a backfill-unsupported platform")

    run_discovery(
        engine_conn, tmp_path, {"instagram": ExplodingAdapter()},
        trigger="manual", mode="backfill",
        backfill_start="2026-06-01", backfill_end="2026-06-30",
    )
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.backfill_unsupported'").fetchone()
    assert row is not None
    assert row["severity"] == "warning"


def test_a_stale_heartbeat_does_not_reclaim_a_run_whose_owner_is_still_alive(engine_conn, tmp_path):
    """B-50 (S1): a laptop lid-close freezes the heartbeat thread while the run
    survives; on resume the next wake reclaimed the LIVE run, freeing the
    single-flight index and starting a second, concurrently-billing run."""
    stale_id = db.insert_running_run(engine_conn, "live-run", "manual", "incremental",
                                     "2026-07-30T05:00:00+00:00")
    _claim_run_ownership(tmp_path, stale_id, "2026-07-30T05:00:00+00:00")  # this process: alive
    now = _dt.datetime(2026, 7, 30, 6, 0, 0, tzinfo=_dt.timezone.utc)
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                           trigger="manual", mode="incremental", now=now)
    assert db.get_run(engine_conn, stale_id)["status"] == "running"   # not stolen
    assert result["status"] == "locked"                                # and we backed off


def test_a_stale_run_whose_owner_is_gone_is_still_reclaimed(engine_conn, tmp_path):
    stale_id = db.insert_running_run(engine_conn, "dead-run", "manual", "incremental",
                                     "2026-07-30T05:00:00+00:00")
    _claim_run_ownership(tmp_path, stale_id, "2026-07-30T05:00:00+00:00")
    run_owner_path(tmp_path, stale_id).write_text(json.dumps({"pid": 0x7FFFFFFE, "started_at": "x"}),
                                                  encoding="utf-8")
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    now = _dt.datetime(2026, 7, 30, 6, 0, 0, tzinfo=_dt.timezone.utc)

    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@a": []})},
                           trigger="manual", mode="incremental", now=now)

    assert result["status"] == "completed"  # the new run itself succeeds
    assert db.get_run(engine_conn, stale_id)["status"] == "abandoned"


def test_a_refused_reclaim_leaves_a_warning_event(engine_conn, tmp_path):
    stale_id = db.insert_running_run(engine_conn, "live-run", "manual", "incremental",
                                     "2026-07-30T05:00:00+00:00")
    _claim_run_ownership(tmp_path, stale_id, "2026-07-30T05:00:00+00:00")
    now = _dt.datetime(2026, 7, 30, 6, 0, 0, tzinfo=_dt.timezone.utc)

    run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                  trigger="manual", mode="incremental", now=now)

    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.reclaim_refused'").fetchone()
    assert row is not None
    assert row["severity"] == "warning"


def test_a_malformed_but_parseable_owner_file_does_not_crash_the_sweep_and_is_reclaimed(engine_conn, tmp_path):
    """`_read_run_owner` only guards the JSON parse step, not the parsed
    dict's shape. A sidecar that is valid JSON but is missing (or has a
    non-integer) "pid" is exactly the kind of truncated/corrupted write this
    sidecar exists to survive (crash/sleep). Treat it like a missing owner:
    don't crash, don't protect the row -- reclaim proceeds as normal."""
    stale_id = db.insert_running_run(engine_conn, "stale-run", "manual", "incremental",
                                     "2026-07-30T05:00:00+00:00")
    run_owner_path(tmp_path, stale_id).parent.mkdir(parents=True, exist_ok=True)
    run_owner_path(tmp_path, stale_id).write_text(json.dumps({"started_at": "x"}),  # no "pid" key
                                                  encoding="utf-8")
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    now = _dt.datetime(2026, 7, 30, 6, 0, 0, tzinfo=_dt.timezone.utc)

    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@a": []})},
                           trigger="manual", mode="incremental", now=now)

    assert result["status"] == "completed"  # the sweep did not crash the run
    assert db.get_run(engine_conn, stale_id)["status"] == "abandoned"


def test_a_non_integer_pid_owner_file_does_not_crash_the_sweep_and_is_reclaimed(engine_conn, tmp_path):
    stale_id = db.insert_running_run(engine_conn, "stale-run", "manual", "incremental",
                                     "2026-07-30T05:00:00+00:00")
    run_owner_path(tmp_path, stale_id).parent.mkdir(parents=True, exist_ok=True)
    run_owner_path(tmp_path, stale_id).write_text(json.dumps({"pid": "not-a-pid", "started_at": "x"}),
                                                  encoding="utf-8")
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    now = _dt.datetime(2026, 7, 30, 6, 0, 0, tzinfo=_dt.timezone.utc)

    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@a": []})},
                           trigger="manual", mode="incremental", now=now)

    assert result["status"] == "completed"  # the sweep did not crash the run
    assert db.get_run(engine_conn, stale_id)["status"] == "abandoned"


def test_finish_run_cannot_resurrect_an_abandoned_run(engine_conn, tmp_path):
    """B-50's evidence-erasing half: db.finish_run has no status precondition,
    so the original process overwrote its own 'abandoned' row back to
    'completed' and -- if scheduled -- wrote the watermark, erasing the only
    evidence that two runs had been live at once."""
    run_row_id = db.insert_running_run(engine_conn, "r", "scheduled", "incremental", now_iso())
    engine_conn.execute("UPDATE discovery_runs SET status = 'abandoned' WHERE id = ?", (run_row_id,))
    engine_conn.commit()

    assert _finish_run_guarded(engine_conn, run_row_id, "completed", now_iso(), "x.md") is False
    assert db.get_run(engine_conn, run_row_id)["status"] == "abandoned"


def test_a_refused_finish_leaves_an_error_event(engine_conn, tmp_path):
    run_row_id = db.insert_running_run(engine_conn, "r", "scheduled", "incremental", now_iso())
    engine_conn.execute("UPDATE discovery_runs SET status = 'abandoned' WHERE id = ?", (run_row_id,))
    engine_conn.commit()

    assert _finish_run_guarded(engine_conn, run_row_id, "completed", now_iso(), "x.md") is False

    events = engine_conn.execute(
        "SELECT kind, severity, run_id FROM events WHERE kind = 'discovery.finish_run_refused'"
    ).fetchall()
    assert len(events) == 1
    assert events[0]["severity"] == "error"
    assert events[0]["run_id"] == run_row_id


def test_finish_run_guarded_allows_a_normal_terminal_write(engine_conn, tmp_path):
    """A run finishing normally (still 'running' when finish is called) must
    not be refused -- the guard only blocks a *second* write to a row that
    already reached a terminal status under a different outcome."""
    run_row_id = db.insert_running_run(engine_conn, "r", "manual", "incremental", now_iso())

    assert _finish_run_guarded(engine_conn, run_row_id, "completed", now_iso(), "x.md") is True
    assert db.get_run(engine_conn, run_row_id)["status"] == "completed"


def test_a_reclaimed_run_does_not_write_a_stale_watermark(engine_conn, tmp_path):
    """The evidence-preserving half of the fix: when the main run's own
    completion write is refused because it was reclaimed out from under it
    (its row is already 'abandoned'), the scheduled-run watermark write must
    be skipped too -- otherwise a dead run's stale finished_at would desync
    discovery_scheduling.is_due from reality."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    now = _dt.datetime(2026, 7, 30, 6, 0, 0, tzinfo=_dt.timezone.utc)

    class ReclaimingAdapter(SingleFakeAdapter):
        """Simulates another process reclaiming this run mid-flight: by the
        time run_discovery reaches its own finish_run call, the row has
        already been marked 'abandoned' out from under it."""
        def enumerate_newest_first(self, handle, keyword_filter):
            rows = engine_conn.execute(
                "SELECT id FROM discovery_runs WHERE status = 'running' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if rows is not None:
                engine_conn.execute(
                    "UPDATE discovery_runs SET status = 'abandoned' WHERE id = ?", (rows["id"],)
                )
                engine_conn.commit()
            return super().enumerate_newest_first(handle, keyword_filter)

    before = db.get_settings(engine_conn)["last_scheduled_run_date"]

    result = run_discovery(engine_conn, tmp_path, {"youtube": ReclaimingAdapter({"@a": []})},
                           trigger="scheduled", mode="incremental", now=now)

    assert db.get_run(engine_conn, result["run_row_id"])["status"] == "abandoned"
    after = db.get_settings(engine_conn)["last_scheduled_run_date"]
    assert after == before  # watermark must not move for a reclaimed run
