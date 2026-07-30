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
