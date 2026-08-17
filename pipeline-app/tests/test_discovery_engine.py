import ast
import datetime as _dt
import inspect
from pathlib import Path as _Path

from pipeline_app import discovery_engine
from pipeline_app.discovery_engine import PlatformAdapter, process_handle


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
    HandleNotFound,
    _claim_run_ownership,
    _finish_run_guarded,
    _process_is_alive,
    make_run_id,
    now_iso,
    run_discovery,
)
from pipeline_app.discovery_paths import run_owner_path
from pipeline_app.discovery_scheduling import decode_watermark


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


def test_a_collision_introduced_by_the_migration_path_is_reported_durably(engine_conn, tmp_path):
    """The migration bypasses the route entirely, so the runtime detector is the
    compensating control -- and it printed to stderr, into the void of B-42."""
    db.upsert_handle_from_migration(
        engine_conn, "youtube", "john.doe.5", "A", "guru", None, "validated", True, now_iso(),
    )
    db.upsert_handle_from_migration(
        engine_conn, "youtube", "johndoe5", "B", "guru", None, "validated", True, now_iso(),
    )
    run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                  trigger="manual", mode="incremental")
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.slug_collision'").fetchone()
    assert row is not None and row["severity"] == "warning"


def test_brightdata_diagnostics_are_drained_into_event_rows(engine_conn, tmp_path, monkeypatch):
    """P7's B-01: the diagnostics sink is written on every Bright Data call and
    read by nobody, so a job that retried three times and truncated its results
    leaves no durable trace."""
    # drain_diagnostics() returns list[dict] (per its real docstring); the mock
    # models "one batch on the first drain, empty after" as a list of batches
    # so the fake keeps that same shape rather than handing back a bare dict.
    batches = [[{"kind": "brightdata.truncated", "severity": "warning",
                 "source": "discovery_instagram",
                 "message": "instagram/@nasa returned exactly limit_per_input=10 items",
                 "detail": {"platform": "instagram", "records": 10}}]]
    monkeypatch.setattr(discovery_engine.brightdata_job, "drain_diagnostics",
                        lambda: batches.pop(0) if batches else [])
    db.create_handle(engine_conn, "instagram", "@nasa", "N", "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"instagram": SingleFakeAdapter({"@nasa": []})},
                  trigger="manual", mode="incremental")
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'brightdata.truncated'").fetchone()
    assert row is not None and row["severity"] == "warning"
    assert json.loads(row["detail"])["records"] == 10


def test_the_sink_is_drained_even_when_the_handle_errored(engine_conn, tmp_path, monkeypatch):
    """The truncation/retry evidence matters MOST on the failing handle, so the
    drain lives in a finally, not on the success path."""
    batches = [[{"kind": "brightdata.retry", "severity": "warning",
                 "source": "discovery_instagram",
                 "message": "instagram/@bad retried after a transient error",
                 "detail": {"platform": "instagram", "attempts": 2}}]]
    monkeypatch.setattr(discovery_engine.brightdata_job, "drain_diagnostics",
                        lambda: batches.pop(0) if batches else [])
    db.create_handle(engine_conn, "instagram", "@bad", "N", "guru", None, now_iso())
    adapter = SingleFakeAdapter({}, fail_handles={"@bad"})
    result = run_discovery(engine_conn, tmp_path, {"instagram": adapter},
                           trigger="manual", mode="incremental")
    assert result["status"] == "completed_with_errors"
    results = db.list_run_handle_results(engine_conn, result["run_row_id"])
    assert results[0]["status"] == "error"
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'brightdata.retry'").fetchone()
    assert row is not None and row["severity"] == "warning"
    assert json.loads(row["detail"])["attempts"] == 2


def test_a_diagnostics_drain_failure_never_aborts_the_run(engine_conn, tmp_path, monkeypatch):
    monkeypatch.setattr(discovery_engine.brightdata_job, "drain_diagnostics",
                        lambda: (_ for _ in ()).throw(RuntimeError("sink is broken")))
    db.create_handle(engine_conn, "instagram", "@nasa", "N", "guru", None, now_iso())
    result = run_discovery(engine_conn, tmp_path, {"instagram": SingleFakeAdapter({"@nasa": []})},
                           trigger="manual", mode="incremental")
    assert result["status"] in ("completed", "completed_with_errors")
    results = db.list_run_handle_results(engine_conn, result["run_row_id"])
    assert results[0]["status"] == "no_new_content"


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


def test_three_consecutive_failing_runs_downgrade_the_handle(engine_conn, tmp_path):
    """P1's B-82: set_handle_status was called only from the one-shot validate
    branch, so a handle that validated at registration and later died kept
    status='validated', included=1 forever while raising an error row on every
    single run. A permanently broken source was indistinguishable from a healthy
    one on the roster."""
    handle_id = db.create_handle(engine_conn, "youtube", "@dead", "D", "guru", None, now_iso())
    db.set_handle_status(engine_conn, handle_id, "validated")
    adapter = SingleFakeAdapter({}, fail_handles={"@dead"})
    for _ in range(3):
        run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")
    row = db.get_handle(engine_conn, handle_id)
    assert row["consecutive_failures"] == 3
    assert row["status"] == "failing"


def test_a_handle_timeout_also_counts_as_a_failure(engine_conn, tmp_path, monkeypatch):
    """A timeout is a real failure mode, not a shrug -- it must feed the same
    consecutive-failure counter as the generic exception branch."""
    handle_id = db.create_handle(engine_conn, "youtube", "@slow", "S", "guru", None, now_iso())
    db.set_handle_status(engine_conn, handle_id, "validated")

    import concurrent.futures

    def _raise_timeout(self, timeout=None):
        raise concurrent.futures.TimeoutError()

    monkeypatch.setattr(concurrent.futures.Future, "result", _raise_timeout)
    adapter = SingleFakeAdapter({"@slow": [{"id": "v1", "title": "x", "published": None}]})
    run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")
    row = db.get_handle(engine_conn, handle_id)
    assert row["consecutive_failures"] == 1


def test_one_successful_run_clears_the_failure_counter(engine_conn, tmp_path):
    """The counter must be CONSECUTIVE, or a handle that fails once a month for
    a year is eventually condemned for being popular."""
    handle_id = db.create_handle(engine_conn, "youtube", "@flaky", "F", "guru", None, now_iso())
    db.set_handle_status(engine_conn, handle_id, "validated")
    failing_adapter = SingleFakeAdapter({}, fail_handles={"@flaky"})
    run_discovery(engine_conn, tmp_path, {"youtube": failing_adapter}, trigger="manual", mode="incremental")
    assert db.get_handle(engine_conn, handle_id)["consecutive_failures"] == 1

    healthy_adapter = SingleFakeAdapter({"@flaky": []})
    run_discovery(engine_conn, tmp_path, {"youtube": healthy_adapter}, trigger="manual", mode="incremental")
    assert db.get_handle(engine_conn, handle_id)["consecutive_failures"] == 0
    assert db.get_handle(engine_conn, handle_id)["status"] == "validated"


def test_a_failing_handle_is_still_included_in_the_run(engine_conn, tmp_path):
    """'failing' is a signal, not an exclusion -- B-57's lesson. Only a
    definitive not-found removes a handle from the roster."""
    handle_id = db.create_handle(engine_conn, "youtube", "@dead", "D", "guru", None, now_iso())
    db.set_handle_status(engine_conn, handle_id, "validated")
    adapter = SingleFakeAdapter({}, fail_handles={"@dead"})
    for _ in range(3):
        run_discovery(engine_conn, tmp_path, {"youtube": adapter}, trigger="manual", mode="incremental")
    assert db.get_handle(engine_conn, handle_id)["status"] == "failing"
    assert db.get_handle(engine_conn, handle_id)["included"] == 1


def test_a_skipped_handle_does_not_count_as_a_failure(engine_conn, tmp_path):
    """A backfill skip is 'this platform has no backfill path', not 'this handle
    is broken'. Counting it would condemn every Bright Data handle after three
    backfills."""
    handle_id = db.create_handle(engine_conn, "instagram", "@nasa", "N", "guru", None, now_iso())
    db.set_handle_status(engine_conn, handle_id, "validated")
    adapter = SingleFakeAdapter({"@nasa": []})
    for _ in range(3):
        run_discovery(engine_conn, tmp_path, {"instagram": adapter}, trigger="manual", mode="backfill")
    row = db.get_handle(engine_conn, handle_id)
    assert row["consecutive_failures"] == 0
    assert row["status"] == "validated"


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


def test_a_handle_that_raises_after_two_downloads_records_two_not_zero(engine_conn, tmp_path):
    """B-54: process_handle accumulated `downloaded` in a local destroyed on
    raise, so the except branch hardcoded items_downloaded=0 -- the DB row, the
    markdown record and last_seen_published_at all under-reported real work
    that is on disk, permanently."""
    class FailsOnThird(SingleFakeAdapter):
        def download_item(self, repo_root, handle, item_id, title, content_type=None):
            if item_id == "v3":
                raise RuntimeError("rate limited")
            return {"id": item_id, "ok": True, "published": "2026-07-29"}
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = FailsOnThird({"@a": [{"id": f"v{i}", "title": "x", "published": "2026-07-29"}
                                    for i in (1, 2, 3)]})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                           trigger="manual", mode="incremental")
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert row["status"] == "error"
    assert row["items_downloaded"] == 2


def test_a_partly_downloaded_handle_still_advances_last_seen(engine_conn, tmp_path):
    """B-54: last_seen_published_at must advance from the items actually
    downloaded before the failure, not stay stuck at None."""
    handle_id = db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())

    class FailsOnThird(SingleFakeAdapter):
        def download_item(self, repo_root, handle, item_id, title, content_type=None):
            if item_id == "v3":
                raise RuntimeError("rate limited")
            return {"id": item_id, "ok": True, "published": "2026-07-29"}
    adapter = FailsOnThird({"@a": [{"id": f"v{i}", "title": "x", "published": "2026-07-29"}
                                    for i in (1, 2, 3)]})
    run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                  trigger="manual", mode="incremental")
    assert db.get_handle(engine_conn, handle_id)["last_seen_published_at"] == "2026-07-29"


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
    assert locked_row["md_path"] is None  # B-49: a no-op lock loss gets no paired record
    assert list((tmp_path / "output" / "discovery-runs").glob("*.md")) == []


def test_a_lock_loss_retries_once_instead_of_re_raising(engine_conn, tmp_path, monkeypatch):
    """B-59's TOCTOU: if the winner finished between the loser's IntegrityError
    and its get_running_run() is None check, the loser RE-RAISED -- legitimate
    lock contention surfaced as an unhandled IntegrityError, a dead subprocess,
    and no run row at all."""
    calls = {"n": 0}
    real_insert = db.insert_running_run
    def flaky(conn, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.IntegrityError("UNIQUE constraint failed")
        return real_insert(conn, *a, **k)
    monkeypatch.setattr(db, "insert_running_run", flaky)
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                           trigger="manual", mode="incremental")
    assert result["status"] == "completed"     # not an escaped IntegrityError
    assert calls["n"] == 2


def test_a_second_collision_within_the_retry_window_still_re_raises(engine_conn, tmp_path, monkeypatch):
    """The retry exists for the TOCTOU race, not to paper over a genuine
    double collision -- if the retry ALSO raises IntegrityError, that's real
    and must propagate, not be silently swallowed a second time."""
    def always_raises(conn, *a, **k):
        raise sqlite3.IntegrityError("UNIQUE constraint failed")
    monkeypatch.setattr(db, "insert_running_run", always_raises)
    with pytest.raises(sqlite3.IntegrityError):
        run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                      trigger="manual", mode="incremental")


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


def test_an_abandoned_record_reports_the_work_its_db_rows_prove(engine_conn, tmp_path):
    """B-51: _write_abandoned_records_for_reclaimed_runs passed [] by design, so
    the markdown record -- the durable artifact a future reader trusts -- said
    'Pulled 0 new items across 0 handles' while discovery_run_handles held a row
    per completed handle. On a hard reboot mid-run it is the only post-mortem."""
    handle_id = db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    dead_id = db.insert_running_run(engine_conn, "dead", "manual", "incremental",
                                    "2026-07-30T05:00:00+00:00")
    db.record_handle_result(engine_conn, dead_id, handle_id, "ok", 4)
    now = _dt.datetime(2026, 7, 30, 6, 0, tzinfo=_dt.timezone.utc)
    run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                  trigger="manual", mode="incremental", now=now)
    record = Path(db.get_run(engine_conn, dead_id)["md_path"]).read_text(encoding="utf-8")
    assert "items_downloaded: 4" in record
    assert "partial" in record.lower()


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


def test_an_empty_enumeration_is_not_treated_as_proof_of_non_existence(engine_conn, tmp_path):
    """Inverts test_run_discovery_validate_handle_sets_invalid_and_excludes_on_empty_enumeration.
    B-57: an empty result is D-03's ambiguity -- a dead handle and a failed
    fetch look alike -- so it must not permanently exclude a valid handle."""
    handle_id = db.create_handle(engine_conn, "youtube", "@dead", "Dead", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@dead": []})
    result = run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    assert result["status"] == "completed_with_errors"
    row = db.get_handle(engine_conn, handle_id)
    assert row["status"] == "pending"
    assert row["included"] == 1


def test_a_transient_validate_failure_leaves_the_handle_pending_and_included(engine_conn, tmp_path):
    """Inverts test_run_discovery_validate_handle_sets_invalid_and_excludes_on_crash.
    B-57: the blanket except set 'invalid' AND cleared 'included' with no
    distinction between 'this account does not exist' and 'the VPN was up' --
    quietly and permanently removing a valid handle from every future run."""
    handle_id = db.create_handle(engine_conn, "youtube", "@crashy", "Crashy", "guru", None, now_iso())
    adapter = SingleFakeAdapter({}, fail_handles={"@crashy"})
    result = run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    assert result["status"] == "failed"           # the run still reports the failure
    row = db.get_handle(engine_conn, handle_id)
    assert row["status"] == "pending"             # ...but the handle is retryable
    assert row["included"] == 1


def test_a_definitive_not_found_does_exclude_the_handle(engine_conn, tmp_path):
    """HandleNotFound is the one exception that still excludes -- a definitive
    404/"no such account", not merely an empty enumeration or a network blip."""
    class GoneAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            raise HandleNotFound("account does not exist")

    handle_id = db.create_handle(engine_conn, "youtube", "@gone", "Gone", "guru", None, now_iso())
    adapter = GoneAdapter({})
    result = run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    assert result["status"] == "failed"
    row = db.get_handle(engine_conn, handle_id)
    assert row["status"] == "invalid"
    assert row["included"] == 0


@pytest.mark.parametrize("error_name", [
    "BlueskyFetchError", "YouTubeEnumerationError", "TranscriptFetchBlocked", "YtDlpUnavailable",
])
def test_a_typed_adapter_fetch_error_never_marks_a_handle_invalid(engine_conn, tmp_path, error_name):
    """P6's B-06 (S1): a valid handle added while the VPN was up was quietly and
    permanently removed from every future run. P6 makes the failure raise; this
    asserts P8 does not then convert the raise into 'invalid' + included=0. The
    error types are constructed locally by name so this test does not depend on
    P6's merge landing first."""
    Boom = type(error_name, (RuntimeError,), {})

    class RaisingAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            raise Boom("transport failed")

    handle_id = db.create_handle(engine_conn, "bluesky", "adamgrant.bsky.social", "AG",
                                 "guru", None, now_iso())
    db.set_handle_status(engine_conn, handle_id, "validated")
    result = run_discovery(engine_conn, tmp_path, {"bluesky": RaisingAdapter({})},
                           trigger="manual", mode="validate_handle", handle_id=handle_id)
    row = db.get_handle(engine_conn, handle_id)
    assert result["status"] == "failed"        # the run reports the failure...
    assert row["status"] != "invalid"          # ...without condemning the handle
    assert row["included"] == 1


P6_ERROR_NAMES = ("BlueskyFetchError", "YouTubeEnumerationError",
                  "TranscriptFetchBlocked", "YtDlpUnavailable")


def test_the_local_stand_in_names_match_p6s_real_exported_errors():
    """The test above constructs P6's error types by NAME so P8 is not blocked
    on P6's merge order -- which means a rename on P6's side would leave this
    suite green against types that no longer exist, i.e. an except clause that
    silently never matches. Assert the names against the real modules the
    moment they are importable, so a rename is a failure rather than a
    disappearance."""
    from pipeline_app import discovery_bluesky, discovery_youtube
    exported = set(dir(discovery_bluesky)) | set(dir(discovery_youtube))
    missing = [name for name in P6_ERROR_NAMES if name not in exported]
    assert not missing, (
        f"P6 no longer exports {missing}; the parametrised stand-ins above are "
        f"testing types nothing raises. Update P6_ERROR_NAMES and EXCLUDING_ERRORS together."
    )
    for name in P6_ERROR_NAMES:
        error_type = getattr(discovery_bluesky, name, None) or getattr(discovery_youtube, name)
        assert issubclass(error_type, Exception)
        assert not issubclass(error_type, discovery_engine.EXCLUDING_ERRORS), (
            f"{name} is a transport failure, not proof the account is gone (B-06)")


def test_only_handle_not_found_survives_as_an_excluding_error(engine_conn, tmp_path):
    """The whitelist is the contract: if a future adapter error type is added and
    nobody updates this set, the default is 'retryable', never 'delete it from
    the roster'."""
    assert discovery_engine.EXCLUDING_ERRORS == (discovery_engine.HandleNotFound,)


def test_a_transient_validate_failure_names_the_error_type_in_its_event(engine_conn, tmp_path):
    """The event detail records the concrete adapter error type name, not a
    generic label -- so an operator scanning events can tell BlueskyFetchError
    apart from a socket timeout."""
    from pipeline_app import discovery_bluesky

    class RaisingAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            raise discovery_bluesky.BlueskyFetchError("transport failed")

    handle_id = db.create_handle(engine_conn, "bluesky", "adamgrant.bsky.social", "AG",
                                 "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"bluesky": RaisingAdapter({})},
                 trigger="manual", mode="validate_handle", handle_id=handle_id)
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.validate_transient_failure'").fetchone()
    assert row is not None
    detail = json.loads(row["detail"])
    assert detail["error_type"] == "BlueskyFetchError"


def test_validate_handle_with_no_matching_adapter_records_a_failed_run_not_a_crash(engine_conn, tmp_path):
    """B-58: a handle whose platform has no entry in the adapters dict used to
    raise KeyError OUTSIDE run_discovery's try -- the fire-and-forget child died
    with a traceback nobody saw, no run row was written, and the handle sat at
    'pending' forever with no explanation. adapters[handle_row["platform"]] must
    live inside the try so this produces a recorded 'failed' run instead."""
    handle_id = db.create_handle(engine_conn, "youtube", "@orphan", "Orphan", "guru", None, now_iso())
    result = run_discovery(
        engine_conn, tmp_path, {},  # no adapter registered for "youtube"
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    assert result["status"] == "failed"
    row = db.get_handle(engine_conn, handle_id)
    assert row["status"] == "pending"
    assert db.get_run(engine_conn, result["run_row_id"]) is not None


def test_validate_handle_with_a_nonexistent_handle_id_returns_failed_not_a_crash(engine_conn, tmp_path):
    """I-1 Part A: db_mod.get_handle(conn, handle_id) is inside the try, but a
    None handle_row does not itself raise -- the crash used to happen later,
    while building handle_result, when the except handler tried
    handle_row["handle"] against a None handle_row (AFTER already calling
    set_handle_status/recording a misleading 'validate_transient_failure'
    event for a handle that was never real). run_discovery must return a
    dict, not raise, with an honest 'not found' error message -- not the
    transient-failure framing, and no discovery_run_handles row (handles.id
    is a foreign key; that insert would raise its own IntegrityError for an
    id that was never real)."""
    nonexistent_handle_id = 999999
    result = run_discovery(
        engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
        trigger="manual", mode="validate_handle", handle_id=nonexistent_handle_id,
    )
    assert isinstance(result, dict)
    assert result["status"] == "failed"
    run_row = db.get_run(engine_conn, result["run_row_id"])
    assert run_row is not None
    assert run_row["status"] == "failed"

    # No misleading "transient failure" event -- the handle never existed.
    events = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.validate_transient_failure'").fetchall()
    assert events == []
    assert db.list_run_handle_results(engine_conn, result["run_row_id"]) == []


def test_a_transient_validate_failure_leaves_a_warning_event(engine_conn, tmp_path):
    handle_id = db.create_handle(engine_conn, "youtube", "@crashy", "Crashy", "guru", None, now_iso())
    adapter = SingleFakeAdapter({}, fail_handles={"@crashy"})
    run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.validate_transient_failure'").fetchone()
    assert row is not None
    assert row["severity"] == "warning"


def test_an_empty_enumeration_leaves_a_warning_event(engine_conn, tmp_path):
    handle_id = db.create_handle(engine_conn, "youtube", "@dead", "Dead", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@dead": []})
    run_discovery(
        engine_conn, tmp_path, {"youtube": adapter},
        trigger="manual", mode="validate_handle", handle_id=handle_id,
    )
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.validate_transient_failure'").fetchone()
    assert row is not None
    assert row["severity"] == "warning"


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
    stored = db.get_settings(engine_conn)["last_scheduled_run_date"]
    assert decode_watermark(stored)[0] == "2026-07-30"


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
    stored = db.get_settings(engine_conn)["last_scheduled_run_date"]
    assert decode_watermark(stored)[0] == "2026-07-30"


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


def test_an_unknown_platform_error_message_names_the_exception_type(engine_conn, tmp_path):
    """B-55: str(KeyError('youtube')) stores the literal 'youtube'; str(IndexError())
    stores an empty string. With no log file that string is the entire
    post-mortem, and it is rendered verbatim in the UI and the record.

    `handles.platform` is CHECK-constrained to known platform values, so a
    truly-unknown platform can't be persisted -- the KeyError is instead
    forced by handing run_discovery an adapters dict missing the "youtube"
    key that _process_one_handle looks up by handle_row["platform"]."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    result = run_discovery(engine_conn, tmp_path, {},
                           trigger="manual", mode="incremental")
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert row["error_message"].startswith("KeyError:")


def test_an_empty_str_exception_is_still_identifiable(engine_conn, tmp_path):
    """IndexError() -> "IndexError: " -- never the empty string that str(exc) gives."""
    class RaisesIndexError(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            raise IndexError()

    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = RaisesIndexError({})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                           trigger="manual", mode="incremental")
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert row["error_message"] != ""
    assert row["error_message"] == "IndexError: "


def test_the_full_traceback_reaches_the_event_detail(engine_conn, tmp_path):
    """The bare error_message string is the whole post-mortem with no log
    file -- the full traceback must land in the discovery.handle_failed
    event's detail so the actual failure site is recoverable."""
    class RaisesIndexError(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            raise IndexError()

    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = RaisesIndexError({})
    run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                  trigger="manual", mode="incremental")
    row = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.handle_failed'").fetchone()
    assert row is not None
    assert row["severity"] == "error"
    detail = json.loads(row["detail"])
    assert "Traceback (most recent call last)" in detail["traceback"]


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


def test_a_handle_that_never_returns_is_recorded_as_an_error_and_the_run_finishes(engine_conn, tmp_path):
    """B-53: nothing bounded a run's duration, so one blocking network call held
    the status='running' row -- and the single-flight lock -- forever, while the
    run history showed a run that looked healthy and in progress."""
    class HangingAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            time.sleep(30)
    db.create_handle(engine_conn, "youtube", "@hang", "H", "guru", None, now_iso())
    started = time.monotonic()
    result = run_discovery(engine_conn, tmp_path, {"youtube": HangingAdapter({})},
                           trigger="manual", mode="incremental", per_handle_deadline_s=0.2)
    elapsed = time.monotonic() - started
    assert elapsed < 10  # bounded by the 0.2s deadline, not the adapter's 30s sleep
    assert result["status"] == "completed_with_errors"
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert "TimeoutError" in row["error_message"]
    assert db.get_running_run(engine_conn) is None          # the lock was released


def test_a_run_that_blows_its_overall_deadline_ends_failed_not_running(engine_conn, tmp_path):
    """B-53: the per-run cap. Even if every handle returns promptly, a run
    that has already been going longer than run_deadline_s must stop
    processing the remaining handles and end 'failed', not silently keep
    the 'running' row alive to the end of the handle list."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "@b", "B", "guru", None, now_iso())
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@a": [], "@b": []})},
                           trigger="manual", mode="incremental", run_deadline_s=0.0)
    assert result["status"] == "failed"
    assert db.get_running_run(engine_conn) is None
    row = engine_conn.execute(
        "SELECT kind, severity FROM events WHERE kind = 'discovery.run_deadline_exceeded'").fetchone()
    assert row is not None
    assert row["severity"] == "error"


def test_a_deadline_exceeded_scheduled_run_still_advances_the_watermark_instant(engine_conn, tmp_path):
    """I-4: a RunDeadlineExceeded-caused 'failed' run correctly skips the
    normal success watermark write (final_status == 'failed'), but that means
    is_due() sees no recent instant at all and fires again at the very next
    15-minute wake, with no backoff -- a hung run just keeps re-attempting for
    the rest of the day, burning up to run_deadline_s of billable adapter
    calls each time. A deadline-exceeded run must still stamp the watermark's
    instant so MIN_RUN_INTERVAL_H's instant-based check in is_due blocks a
    same-day re-fire, giving the operator time to notice and intervene."""
    from pipeline_app.discovery_scheduling import is_due

    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    now = _dt.datetime(2026, 7, 30, 6, 0, 0, tzinfo=_dt.timezone.utc)
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@a": []})},
                           trigger="scheduled", mode="incremental", run_deadline_s=0.0, now=now)
    assert result["status"] == "failed"

    settings = db.get_settings(engine_conn)
    last_date, last_instant = decode_watermark(settings["last_scheduled_run_date"])
    assert last_instant is not None      # the instant WAS stamped despite the failure

    # A same-day recheck shortly after the deadline-exceeded run must not be due
    # again -- MIN_RUN_INTERVAL_H's backoff blocks the immediate re-fire.
    recheck = now + _dt.timedelta(minutes=15)
    assert is_due(recheck, settings["timezone"], settings["time_of_day"],
                  settings["last_scheduled_run_date"]) is False


def test_a_non_deadline_crash_does_not_advance_the_watermark(engine_conn, tmp_path, monkeypatch):
    """I-4's carve-out: only a RunDeadlineExceeded warrants the backoff write.
    A startup crash or any other outer exception must still leave tomorrow's
    normal schedule untouched -- writing the watermark here would be exactly
    the B-50 desync this branch must not reintroduce for an ordinary crash."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())

    def _boom(*a, **k):
        raise RuntimeError("list_handles blew up")

    monkeypatch.setattr(db, "list_handles", _boom)
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({"@a": []})},
                           trigger="scheduled", mode="incremental")
    assert result["status"] == "failed"

    settings = db.get_settings(engine_conn)
    last_date, last_instant = decode_watermark(settings["last_scheduled_run_date"])
    assert last_instant is None


def test_the_engine_module_has_no_mid_file_imports():
    """B-64(1): import sqlite3/sys/threading and the pipeline_app imports sat at
    line 117, so importing the pure walk functions dragged in the DB layer."""
    tree = ast.parse(_Path(discovery_engine.__file__).read_text(encoding="utf-8"))
    import_lines = [n.lineno for n in ast.walk(tree)
                    if isinstance(n, (ast.Import, ast.ImportFrom)) and n.col_offset == 0]
    first_def = min(n.lineno for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)))
    assert max(import_lines) < first_def


def test_peek_upload_date_has_a_real_signature():
    """B-64(2): (self, *args) type-checks nothing -- adapters can and do
    disagree on arity with no signal."""
    sig = inspect.signature(PlatformAdapter.peek_upload_date)
    assert list(sig.parameters) == ["self", "item_id"]


def test_run_discovery_normalizes_a_naive_now_to_aware_utc(engine_conn, tmp_path):
    """B-64(4): a naive `now` made make_run_id's %z render empty and made
    reclaim_stale_runs subtract a naive from an aware datetime -- an uncaught
    TypeError. No production caller passes it; the parameter is public."""
    naive = _dt.datetime(2026, 7, 30, 6, 0, 0)
    result = run_discovery(engine_conn, tmp_path, {"youtube": SingleFakeAdapter({})},
                           trigger="manual", mode="incremental", now=naive)
    assert result["status"] == "completed"


def test_preflight_runs_once_per_run_not_once_per_handle(engine_conn, tmp_path):
    """P7's B-21: a missing credential failed N times, once per handle, with N
    identical unhelpful errors. One check, before the loop, one message."""
    calls = {"n": 0}

    class PreflightAdapter(SingleFakeAdapter):
        def preflight(self, repo_root=None):
            calls["n"] += 1
            return None

    for handle in ("@a", "@b", "@c"):
        db.create_handle(engine_conn, "instagram", handle, handle, "guru", None, now_iso())
    run_discovery(engine_conn, tmp_path, {"instagram": PreflightAdapter({})},
                  trigger="manual", mode="incremental")
    assert calls["n"] == 1


def test_a_failed_preflight_skips_that_platform_and_reports_once(engine_conn, tmp_path):
    class Unconfigured(SingleFakeAdapter):
        def preflight(self, repo_root=None):
            return "BRIGHTDATA_API_KEY is not set; instagram cannot run"

        def enumerate_newest_first(self, handle, keyword_filter):
            raise AssertionError("must not be reached when preflight failed")

    for handle in ("@a", "@b", "@c"):
        db.create_handle(engine_conn, "instagram", handle, handle, "guru", None, now_iso())
    result = run_discovery(engine_conn, tmp_path, {"instagram": Unconfigured({})},
                           trigger="manual", mode="incremental")
    results = db.list_run_handle_results(engine_conn, result["run_row_id"])
    assert len(results) == 3
    for row in results:
        assert row["status"] == "error"
        assert "BRIGHTDATA_API_KEY" in row["error_message"]
    events = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.preflight_failed'").fetchall()
    assert len(events) == 1
    assert events[0]["severity"] == "error"


def test_three_consecutive_failing_preflights_downgrade_every_handle_on_that_platform(engine_conn, tmp_path):
    """I-6 / P1's B-82: _apply_preflight's per-platform failure branch recorded
    an 'error' handle_result for every handle on a platform whose preflight
    failed, but never called record_handle_failure -- so a permanently
    unconfigured platform (e.g. no BRIGHTDATA_API_KEY) raised an identical
    error on every run forever without ever downgrading its handles to
    'failing', unlike the main per-handle loop's TimeoutError/generic-
    exception branches (Task 39). Same shape as
    test_three_consecutive_failing_runs_downgrade_the_handle, but via the
    preflight path instead of a per-handle adapter exception."""
    class Unconfigured(SingleFakeAdapter):
        def preflight(self, repo_root=None):
            return "BRIGHTDATA_API_KEY is not set; instagram cannot run"

        def enumerate_newest_first(self, handle, keyword_filter):
            raise AssertionError("must not be reached when preflight failed")

    handle_ids = []
    for handle in ("@a", "@b", "@c"):
        handle_id = db.create_handle(engine_conn, "instagram", handle, handle, "guru", None, now_iso())
        db.set_handle_status(engine_conn, handle_id, "validated")
        handle_ids.append(handle_id)

    for _ in range(3):
        run_discovery(engine_conn, tmp_path, {"instagram": Unconfigured({})},
                      trigger="manual", mode="incremental")

    for handle_id in handle_ids:
        row = db.get_handle(engine_conn, handle_id)
        assert row["consecutive_failures"] == 3
        assert row["status"] == "failing"


def test_a_failed_preflight_does_not_block_other_platforms(engine_conn, tmp_path):
    class Unconfigured(SingleFakeAdapter):
        def preflight(self, repo_root=None):
            return "BRIGHTDATA_API_KEY is not set; instagram cannot run"

        def enumerate_newest_first(self, handle, keyword_filter):
            raise AssertionError("must not be reached when preflight failed")

    db.create_handle(engine_conn, "instagram", "@bad", "Bad", "guru", None, now_iso())
    db.create_handle(engine_conn, "youtube", "@good", "Good", "guru", None, now_iso())
    good_adapter = SingleFakeAdapter({"@good": [{"id": "v1", "title": "x", "published": "2026-07-29"}]})
    result = run_discovery(engine_conn, tmp_path,
                           {"instagram": Unconfigured({}), "youtube": good_adapter},
                           trigger="manual", mode="incremental")
    results = {r["handle_id"]: r["status"] for r in db.list_run_handle_results(engine_conn, result["run_row_id"])}
    assert list(results.values()).count("error") == 1
    assert list(results.values()).count("ok") == 1


def test_an_adapter_without_preflight_is_not_an_error(engine_conn, tmp_path):
    """preflight() is optional -- the native adapters have no credentials to
    check. getattr, not hasattr-then-call."""
    assert getattr(SingleFakeAdapter, "preflight", None) is None
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    adapter = SingleFakeAdapter({"@a": [{"id": "v1", "title": "x", "published": "2026-07-29"}]})
    result = run_discovery(engine_conn, tmp_path, {"youtube": adapter},
                           trigger="manual", mode="incremental")
    assert result["status"] == "completed"
    events = engine_conn.execute(
        "SELECT * FROM events WHERE kind = 'discovery.preflight_failed'").fetchall()
    assert events == []


def test_an_adapter_that_declares_handle_row_receives_it(engine_conn, tmp_path):
    """C1 (operator-approved 2026-08-16, P7-brightdata.md Sec 6 / commit 55109b8):
    the true per-handle cap needs handle_row threaded into enumerate_newest_first.
    The adapters that would read it are P6/P7-owned files P8 cannot edit, so this
    only proves the engine offers the row to an adapter that opts in."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    received = {}

    class OptedInAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter, handle_row=None):
            received["handle_row"] = handle_row
            return []

    run_discovery(engine_conn, tmp_path, {"youtube": OptedInAdapter({})},
                  trigger="manual", mode="incremental")
    assert received["handle_row"] is not None
    assert received["handle_row"]["handle"] == "@a"


def test_an_adapter_that_has_not_opted_in_is_called_exactly_as_before(engine_conn, tmp_path):
    """Zero behavior change for discovery_bluesky/discovery_youtube/discovery_instagram
    until each is updated on its own package's side to declare the parameter."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    calls = []

    class LegacyAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter):
            calls.append((handle, keyword_filter))
            return []

    result = run_discovery(engine_conn, tmp_path, {"youtube": LegacyAdapter({})},
                           trigger="manual", mode="incremental")
    assert result["status"] == "completed"
    assert calls == [("@a", None)]


def test_the_seam_is_offered_at_every_enumerate_call_site(engine_conn, tmp_path):
    """process_handle, process_handle_backfill and process_handle_validate all
    call enumerate_newest_first -- the seam must not be wired into only one."""
    handle_id = db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())
    seen = []

    class OptedInAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter, handle_row=None):
            seen.append(handle_row["handle"] if handle_row else None)
            return []

    run_discovery(engine_conn, tmp_path, {"youtube": OptedInAdapter({})},
                  trigger="manual", mode="validate_handle", handle_id=handle_id)
    assert seen == ["@a"]


def test_a_real_typeerror_inside_an_opted_in_adapter_still_propagates(engine_conn, tmp_path):
    """Detection is by signature introspection, not by catching TypeError --
    a bug inside an adapter that HAS opted in must not be swallowed and
    misread as 'this adapter doesn't take handle_row'."""
    db.create_handle(engine_conn, "youtube", "@a", "A", "guru", None, now_iso())

    class BuggyOptedInAdapter(SingleFakeAdapter):
        def enumerate_newest_first(self, handle, keyword_filter, handle_row=None):
            raise TypeError("unrelated bug inside the adapter")

    result = run_discovery(engine_conn, tmp_path, {"youtube": BuggyOptedInAdapter({})},
                           trigger="manual", mode="incremental")
    row = db.list_run_handle_results(engine_conn, result["run_row_id"])[0]
    assert row["status"] == "error"
    assert "unrelated bug inside the adapter" in row["error_message"]
    assert db.get_run(engine_conn, result["run_row_id"])["run_id"].endswith("+0000")
