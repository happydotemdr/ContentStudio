"""Regression test for the same-day sort-order bug found in the final
whole-branch review (fix-wave finding 1).

`discovery_instagram.py` normalizes Bright Data's date_posted down to a
date-only `published` (YYYY-MM-DD) and, previously, sorted on that truncated
string. Python's sort is stable and Bright Data returns rows unsorted, so
three same-day posts came back in Bright Data's arbitrary arrival order
rather than newest-first. That can put a genuinely newer post behind posts
already captured on disk and trip discovery_engine's early-stop dedup,
silently dropping the newer post forever.

This file is separate from test_discovery_instagram.py, which is pinned
byte-for-byte by the fix-wave brief and must not be edited.
"""
from pipeline_app import discovery_instagram as ig


def _raw_row(post_id, date_posted, caption="hello", content_type="post"):
    return {
        "post_id": post_id,
        "description": caption,
        "date_posted": date_posted,
        "content_type": content_type,
        "url": f"https://instagram.com/p/{post_id}",
        "likes": 1,
        "num_comments": 1,
    }


def test_enumerate_newest_first_sorts_same_day_rows_by_time_not_arrival_order(monkeypatch):
    """date_posted is a US-format LOCAL timestamp ('07/23/2026 16:00:22'),
    not just a date. Feed three same-day rows out of BOTH arrival order and
    time order: a date-only (or absent) sort is stable and would leave them
    in input order, which does not match the expected newest-first-by-time
    order asserted below -- so this test only passes if the sort key is the
    full timestamp."""
    raw = [
        _raw_row("mid", "07/23/2026 14:00:00"),
        _raw_row("early", "07/23/2026 08:00:00"),
        _raw_row("late", "07/23/2026 20:00:00"),
    ]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)

    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)

    assert [i["id"] for i in items] == ["late", "mid", "early"]
    # 'published' stays the engine-facing date-only contract regardless of
    # how the sort key is derived.
    assert {i["published"] for i in items} == {"2026-07-23"}
