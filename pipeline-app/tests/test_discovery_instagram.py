from pathlib import Path

from pipeline_app import discovery_instagram as ig


def test_api_key_prefers_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(ig.KEY_ENV_VAR, "env-key")
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.api_key() == "env-key"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("  file-key\n", encoding="utf-8")
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.api_key() == "file-key"


def test_api_key_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", tmp_path / "absent.txt")
    assert ig.api_key() is None


import pytest


def test_run_collection_job_returns_results_on_ready(monkeypatch):
    monkeypatch.setattr(ig, "_trigger_job", lambda handle: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id: "ready")
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id: [{"post_id": "p1"}])
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    assert ig._run_collection_job("somehandle") == [{"post_id": "p1"}]


def test_run_collection_job_raises_on_failed_status(monkeypatch):
    monkeypatch.setattr(ig, "_trigger_job", lambda handle: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id: "failed")
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    with pytest.raises(ig.BrightDataJobFailed):
        ig._run_collection_job("somehandle")


def test_run_collection_job_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(ig, "_trigger_job", lambda handle: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id: "running")  # never ready
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    # Force the deadline to have already passed on the very first check.
    monkeypatch.setattr(ig.time, "monotonic", lambda: 10_000.0)
    monkeypatch.setattr(ig, "POLL_TIMEOUT_S", 0)
    with pytest.raises(ig.BrightDataJobTimeout):
        ig._run_collection_job("somehandle")


def test_run_collection_job_polls_until_ready(monkeypatch):
    statuses = iter(["running", "running", "ready"])
    monkeypatch.setattr(ig, "_trigger_job", lambda handle: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id: next(statuses))
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id: [{"post_id": "p1"}])
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    assert ig._run_collection_job("somehandle") == [{"post_id": "p1"}]


def test_normalize_row_truncates_date_to_yyyy_mm_dd():
    row = {
        "post_id": "p1", "caption": "hello world", "date_posted": "2026-08-01T12:34:56.000Z",
        "content_type": "post", "url": "https://instagram.com/p/p1", "likes": 10, "num_comments": 2,
    }
    normalized = ig._normalize_row(row)
    assert normalized["id"] == "p1"
    assert normalized["published"] == "2026-08-01"
    assert normalized["content_type"] == "post"
    assert normalized["caption"] == "hello world"
    assert normalized["like_count"] == 10
    assert normalized["comment_count"] == 2


def test_normalize_row_title_is_truncated_caption():
    long_caption = "x" * 100
    row = {"post_id": "p1", "caption": long_caption, "date_posted": "2026-08-01T00:00:00Z", "content_type": "reel"}
    normalized = ig._normalize_row(row)
    assert normalized["title"] == long_caption[:60]
    assert normalized["content_type"] == "reel"


def test_normalize_row_returns_none_without_id():
    row = {"caption": "x", "date_posted": "2026-08-01T00:00:00Z", "content_type": "post"}
    assert ig._normalize_row(row) is None


def test_normalize_row_returns_none_without_usable_date():
    row = {"post_id": "p1", "caption": "x", "date_posted": "", "content_type": "post"}
    assert ig._normalize_row(row) is None


def test_normalize_row_returns_none_with_malformed_date():
    """A date_posted value that is >= 10 chars but not valid YYYY-MM-DD should return None."""
    row = {"post_id": "p1", "caption": "x", "date_posted": "01/08/2026 xx", "content_type": "post"}
    assert ig._normalize_row(row) is None


def test_normalize_row_empty_caption_still_normalizes():
    row = {"post_id": "p1", "caption": None, "date_posted": "2026-08-01T00:00:00Z", "content_type": "post"}
    normalized = ig._normalize_row(row)
    assert normalized["caption"] == ""
    assert normalized["title"] == "p1"  # falls back to id when caption is empty


def _raw_row(post_id, date, caption="hello", content_type="post"):
    return {"post_id": post_id, "caption": caption, "date_posted": f"{date}T00:00:00Z",
            "content_type": content_type, "url": f"https://instagram.com/p/{post_id}",
            "likes": 1, "num_comments": 1}


def test_enumerate_newest_first_sorts_newest_first(monkeypatch):
    raw = [_raw_row("old", "2026-07-01"), _raw_row("new", "2026-08-01"), _raw_row("mid", "2026-07-15")]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert [i["id"] for i in items] == ["new", "mid", "old"]


def test_enumerate_newest_first_caps_at_max_items_per_run(monkeypatch):
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(25)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    monkeypatch.setattr(ig, "MAX_ITEMS_PER_RUN", 10)
    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert len(items) == 10


def test_enumerate_newest_first_drops_undated_and_idless_rows(monkeypatch):
    raw = [_raw_row("good", "2026-08-01"), {"caption": "no id"}, {"post_id": "no_date", "caption": "x", "date_posted": ""}]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert [i["id"] for i in items] == ["good"]


def test_enumerate_newest_first_applies_keyword_filter_to_caption(monkeypatch):
    raw = [_raw_row("a", "2026-08-01", caption="talks about gardens"), _raw_row("b", "2026-08-01", caption="talks about cars")]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    items = ig.enumerate_newest_first("somehandle", keyword_filter="garden")
    assert [i["id"] for i in items] == ["a"]


def test_enumerate_newest_first_populates_cache_for_download_item(monkeypatch):
    raw = [_raw_row("p1", "2026-08-01", caption="full caption text")]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert ig._ENUMERATE_CACHE["somehandle"]["p1"]["caption"] == "full caption text"


def test_enumerate_newest_first_overwrites_previous_cache_entry(monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("old_batch", "2026-07-01")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("new_batch", "2026-08-01")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert "old_batch" not in ig._ENUMERATE_CACHE["somehandle"]
    assert "new_batch" in ig._ENUMERATE_CACHE["somehandle"]


def test_enumerate_newest_first_propagates_timeout(monkeypatch):
    def raise_timeout(handle):
        raise ig.BrightDataJobTimeout("timed out")
    monkeypatch.setattr(ig, "_run_collection_job", raise_timeout)
    with pytest.raises(ig.BrightDataJobTimeout):
        ig.enumerate_newest_first("somehandle", keyword_filter=None)
