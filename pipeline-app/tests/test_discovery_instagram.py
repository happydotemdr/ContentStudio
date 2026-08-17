from pathlib import Path

from pipeline_app import brightdata_job
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


def test_preflight_reports_a_missing_key_once_without_calling_bright_data(monkeypatch, tmp_path):
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", tmp_path / "absent.txt")

    def _fail_if_called(*a, **k):
        raise AssertionError("preflight must not touch the network")

    monkeypatch.setattr(ig.requests, "post", _fail_if_called)
    message = ig.preflight()
    assert message is not None
    assert ig.KEY_ENV_VAR in message
    assert "instagram" in message


def test_preflight_returns_none_when_the_key_is_configured(monkeypatch, tmp_path):
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("k", encoding="utf-8")
    monkeypatch.delenv(ig.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(ig, "KEY_FILE", key_file)
    assert ig.preflight() is None


import pytest


def _fake_key(monkeypatch, value="test-key"):
    monkeypatch.setattr(ig, "api_key", lambda: value)


def test_run_collection_job_returns_results_on_ready(monkeypatch):
    _fake_key(monkeypatch)
    monkeypatch.setattr(ig, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id, key: [{"post_id": "p1"}])
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    assert ig._run_collection_job("somehandle") == [{"post_id": "p1"}]


def test_run_collection_job_raises_on_failed_status(monkeypatch):
    _fake_key(monkeypatch)
    monkeypatch.setattr(ig, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id, key: "failed")
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    with pytest.raises(ig.BrightDataJobFailed):
        ig._run_collection_job("somehandle")


def test_run_collection_job_raises_on_timeout(monkeypatch):
    _fake_key(monkeypatch)
    monkeypatch.setattr(ig, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id, key: "running")  # never ready
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    # Force the deadline to have already passed on the very first check.
    monkeypatch.setattr(ig.time, "monotonic", lambda: 10_000.0)
    monkeypatch.setattr(ig, "POLL_TIMEOUT_S", 0)
    with pytest.raises(ig.BrightDataJobTimeout):
        ig._run_collection_job("somehandle")


def test_run_collection_job_polls_until_ready(monkeypatch):
    _fake_key(monkeypatch)
    statuses = iter(["running", "running", "ready"])
    monkeypatch.setattr(ig, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id, key: next(statuses))
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id, key: [{"post_id": "p1"}])
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    assert ig._run_collection_job("somehandle") == [{"post_id": "p1"}]


def test_run_collection_job_raises_clear_error_when_key_missing(monkeypatch):
    monkeypatch.setattr(ig, "api_key", lambda: None)

    def _fail_if_called(handle, key):
        raise AssertionError("_trigger_job must not be called when the API key is missing")

    monkeypatch.setattr(ig, "_trigger_job", _fail_if_called)
    with pytest.raises(RuntimeError, match="Bright Data API key not configured"):
        ig._run_collection_job("somehandle")


def test_run_collection_job_prefers_a_pending_snapshot_over_a_new_billed_job(monkeypatch, tmp_path):
    """Bright Data bills per record. If the previous run paid for a snapshot
    and timed out before collecting it, this run must take that data rather
    than pay again."""
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    brightdata_job.record_pending("instagram/somehandle", "snap-abc")
    _fake_key(monkeypatch)

    def _fail_if_called(handle, key):
        raise AssertionError("must not trigger a new job while a snapshot is pending")

    monkeypatch.setattr(ig, "_trigger_job", _fail_if_called)
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id, key: [{"post_id": "p1"}])
    assert ig._run_collection_job("somehandle") == [{"post_id": "p1"}]


def test_enumerate_newest_first_ready_with_empty_results_returns_empty_list(monkeypatch):
    _fake_key(monkeypatch)
    monkeypatch.setattr(ig, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(ig, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(ig, "_fetch_job_results", lambda job_id, key: [])
    monkeypatch.setattr(ig.time, "sleep", lambda s: None)
    assert ig.enumerate_newest_first("somehandle", keyword_filter=None) == []


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_trigger_job_posts_expected_request_and_returns_snapshot_id(monkeypatch):
    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"snapshot_id": "snap123"})

    monkeypatch.setattr(ig.requests, "post", fake_post)
    result = ig._trigger_job("somehandle", "the-key")

    assert result == "snap123"
    assert captured["url"] == f"{ig.BRIGHTDATA_API_BASE}/trigger"
    assert captured["params"]["dataset_id"] == ig.DATASET_ID
    assert captured["headers"]["Authorization"] == "Bearer the-key"
    assert captured["json"][0]["url"] == "https://www.instagram.com/somehandle/"
    assert captured["json"][0]["num_of_posts"] == ig.MAX_ITEMS_PER_RUN


def test_trigger_job_requests_a_discovery_job_not_a_single_page_collect(monkeypatch):
    """Without type=discover_new + discover_by=url, Bright Data reads the
    profile URL as one post page to scrape -- a paid job returning the wrong
    thing. These params are what make it 'newest N posts by this profile'."""
    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured.update(params)
        return _FakeResponse({"snapshot_id": "snap123"})

    monkeypatch.setattr(ig.requests, "post", fake_post)
    ig._trigger_job("somehandle", "the-key")

    assert captured["type"] == "discover_new"
    assert captured["discover_by"] == "url"
    # Server-side cost cap, independent of the num_of_posts input field.
    assert captured["limit_per_input"] == ig.MAX_ITEMS_PER_RUN


def test_poll_job_status_gets_expected_request_and_returns_status(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse({"status": "ready"})

    monkeypatch.setattr(ig.requests, "get", fake_get)
    result = ig._poll_job_status("job1", "the-key")

    assert result == "ready"
    assert captured["url"] == f"{ig.BRIGHTDATA_API_BASE}/progress/job1"
    assert captured["headers"]["Authorization"] == "Bearer the-key"


def test_fetch_job_results_gets_expected_request_and_returns_payload(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _FakeResponse([{"post_id": "p1"}])

    monkeypatch.setattr(ig.requests, "get", fake_get)
    result = ig._fetch_job_results("job1", "the-key")

    assert result == [{"post_id": "p1"}]
    assert captured["url"] == f"{ig.BRIGHTDATA_API_BASE}/snapshot/job1"
    assert captured["params"] == {"format": "json"}
    assert captured["headers"]["Authorization"] == "Bearer the-key"


def test_normalize_row_truncates_date_to_yyyy_mm_dd():
    row = {
        "post_id": "p1", "description": "hello world", "date_posted": "2026-08-01T12:34:56.000Z",
        "content_type": "post", "url": "https://instagram.com/p/p1", "likes": 10, "num_comments": 2,
    }
    normalized = ig._normalize_row(row)
    assert normalized["id"] == "p1"
    assert normalized["published"] == "2026-08-01"
    assert normalized["content_type"] == "post"
    assert normalized["caption"] == "hello world"
    assert normalized["like_count"] == 10
    assert normalized["comment_count"] == 2


def test_normalize_row_parses_us_format_date_posted():
    """The live dataset returns '07/23/2026 16:00:22', not ISO 8601 (verified
    2026-08-06 against instagram.com/nike). Slicing raw[:10] and parsing it as
    %Y-%m-%d rejected every such row, which surfaced as a healthy
    'no_new_content' for an already-paid-for batch. Pin the real format."""
    row = {"post_id": "3947698118484087161", "description": "Beat the heat.",
           "date_posted": "07/23/2026 16:00:22", "content_type": "Reel",
           "url": "https://www.instagram.com/reel/DbJCoXguNF5/",
           "likes": 17227, "num_comments": 366}
    normalized = ig._normalize_row(row)
    assert normalized is not None, "a real Bright Data row must not be dropped"
    assert normalized["published"] == "2026-07-23"
    assert normalized["content_type"] == "reel"
    assert normalized["like_count"] == 17227


def test_parse_published_accepts_both_observed_and_iso_formats():
    assert ig._parse_published("07/23/2026 16:00:22") == "2026-07-23"
    assert ig._parse_published("07/23/2026") == "2026-07-23"
    assert ig._parse_published("2026-07-23T16:00:22.000Z") == "2026-07-23"
    assert ig._parse_published("") is None
    assert ig._parse_published(None) is None
    assert ig._parse_published("not a date at all") is None
    # Month/day must not silently swap: 13 is not a month, so US parsing fails
    # and the ISO fallback rejects it too, rather than yielding a wrong date.
    assert ig._parse_published("13/45/2026 00:00:00") is None


def test_normalize_row_handles_carousel_content_type():
    """Live data returns Carousel alongside Post and Reel -- the design doc
    only anticipated post|reel."""
    row = {"post_id": "p1", "description": "x", "date_posted": "07/30/2026 16:00:32",
           "content_type": "Carousel"}
    assert ig._normalize_row(row)["content_type"] == "carousel"


def test_normalize_row_reads_caption_text_from_description_field():
    """Bright Data's Instagram Posts schema has no 'caption' field -- the text
    is in 'description'. Reading the wrong key wouldn't drop the row (post_id
    and date_posted are still there), it would silently write '(empty)' bodies
    for posts already paid for, so pin the field name."""
    row = {"post_id": "p1", "caption": "wrong field", "date_posted": "2026-08-01T00:00:00Z"}
    assert ig._normalize_row(row)["caption"] == ""


def test_normalize_row_lowercases_display_cased_content_type():
    row = {"post_id": "p1", "description": "x", "date_posted": "2026-08-01T00:00:00Z",
           "content_type": "Reel"}
    assert ig._normalize_row(row)["content_type"] == "reel"


def test_normalize_row_title_is_truncated_caption():
    long_caption = "x" * 100
    row = {"post_id": "p1", "description": long_caption, "date_posted": "2026-08-01T00:00:00Z", "content_type": "reel"}
    normalized = ig._normalize_row(row)
    assert normalized["title"] == long_caption[:60]
    assert normalized["content_type"] == "reel"


def test_normalize_row_returns_none_without_id():
    row = {"description": "x", "date_posted": "2026-08-01T00:00:00Z", "content_type": "post"}
    assert ig._normalize_row(row) is None


def test_normalize_row_returns_none_without_usable_date():
    row = {"post_id": "p1", "description": "x", "date_posted": "", "content_type": "post"}
    assert ig._normalize_row(row) is None


def test_normalize_row_returns_none_with_malformed_date():
    """A date_posted value that is >= 10 chars but not valid YYYY-MM-DD should return None."""
    row = {"post_id": "p1", "description": "x", "date_posted": "01/08/2026 xx", "content_type": "post"}
    assert ig._normalize_row(row) is None


def test_normalize_row_empty_caption_still_normalizes():
    row = {"post_id": "p1", "description": None, "date_posted": "2026-08-01T00:00:00Z", "content_type": "post"}
    normalized = ig._normalize_row(row)
    assert normalized["caption"] == ""
    assert normalized["title"] == "p1"  # falls back to id when caption is empty


def _raw_row(post_id, date, caption="hello", content_type="post"):
    return {"post_id": post_id, "description": caption, "date_posted": f"{date}T00:00:00Z",
            "content_type": content_type, "url": f"https://instagram.com/p/{post_id}",
            "likes": 1, "num_comments": 1}


def test_enumerate_newest_first_sorts_newest_first(monkeypatch):
    raw = [_raw_row("old", "2026-07-01"), _raw_row("new", "2026-08-01"), _raw_row("mid", "2026-07-15")]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert [i["id"] for i in items] == ["new", "mid", "old"]


def test_full_cap_batch_records_a_saturation_error(monkeypatch):
    """Fault test. Ten of ten means posts were dropped that no later run can
    fetch -- the handle still reports 'ok', so this must be reported here."""
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(10)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    brightdata_job.drain_diagnostics()
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    saturation = [d for d in brightdata_job.drain_diagnostics()
                  if d["kind"] == "adapter.batch_saturated"]
    assert len(saturation) == 1
    assert saturation[0]["severity"] == "error"


def test_a_short_batch_records_no_saturation_diagnostic(monkeypatch):
    """Distinguishability. Nine of ten is a quiet account; ten of ten is
    truncation. The two must be observably different."""
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(9)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    brightdata_job.drain_diagnostics()
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert [d for d in brightdata_job.drain_diagnostics()
            if d["kind"] == "adapter.batch_saturated"] == []


def test_saturation_diagnostic_names_the_cap_the_override_and_the_lost_window(monkeypatch):
    """Surfacing. The record must be actionable on its own: an operator
    reading it in the log or the events table must know what to change."""
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(10)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    brightdata_job.drain_diagnostics()
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.batch_saturated"][0]
    assert record["detail"]["cap"] == 10
    assert record["detail"]["handle"] == "somehandle"
    assert record["detail"]["platform"] == "instagram"
    assert ig.MAX_ITEMS_ENV_VAR in record["message"]
    assert "no backfill" in record["message"]


def test_enumerate_newest_first_caps_retained_items(monkeypatch):
    """Consequence of truncation: the returned list itself is bounded to the
    cap, independent of whether the diagnostic above also fires."""
    raw = [_raw_row(f"p{i}", "2026-08-01") for i in range(25)]
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: raw)
    items = ig.enumerate_newest_first("somehandle", keyword_filter=None)
    assert len(items) == ig.MAX_ITEMS_PER_RUN


def test_enumerate_newest_first_drops_undated_and_idless_rows(monkeypatch):
    raw = [_raw_row("good", "2026-08-01"), {"description": "no id"},
           {"post_id": "no_date", "description": "x", "date_posted": ""}]
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


def test_on_disk_ids_empty_when_directory_missing(tmp_path):
    assert ig.on_disk_ids(tmp_path, "somehandle") == set()


def test_on_disk_ids_reads_stems_of_md_files(tmp_path):
    out_dir = tmp_path / "output" / "brand-intel" / "instagram" / "somehandle"
    out_dir.mkdir(parents=True)
    (out_dir / "p1.md").write_text("x", encoding="utf-8")
    (out_dir / "p2.md").write_text("x", encoding="utf-8")
    assert ig.on_disk_ids(tmp_path, "somehandle") == {"p1", "p2"}


def test_peek_upload_date_always_none():
    assert ig.peek_upload_date("anything") is None


def test_download_item_writes_frontmatter_and_caption_from_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("p1", "2026-08-01", caption="the caption")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)

    result = ig.download_item(tmp_path, "somehandle", "p1", "the caption", content_type="post")

    assert result == {"id": "p1", "ok": True, "published": "2026-08-01"}
    out_path = tmp_path / "output" / "brand-intel" / "instagram" / "somehandle" / "p1.md"
    text = out_path.read_text(encoding="utf-8")
    assert "post_id: p1" in text
    assert "content_type: post" in text
    # yaml.safe_dump (used by artifacts.render_frontmatter) quotes date-like
    # strings -- this is NOT "published: 2026-08-01", it's single-quoted.
    assert "published: '2026-08-01'" in text
    assert "the caption" in text
    assert not out_path.with_name("p1.md.tmp").exists()


def test_download_item_empty_caption_writes_placeholder(tmp_path, monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("p1", "2026-08-01", caption="")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    ig.download_item(tmp_path, "somehandle", "p1", "p1")
    out_path = tmp_path / "output" / "brand-intel" / "instagram" / "somehandle" / "p1.md"
    assert "(empty)" in out_path.read_text(encoding="utf-8")


def test_download_item_raises_on_cache_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(ig, "_run_collection_job", lambda handle: [_raw_row("p1", "2026-08-01")])
    ig.enumerate_newest_first("somehandle", keyword_filter=None)
    with pytest.raises(KeyError):
        ig.download_item(tmp_path, "somehandle", "not_in_cache", "title")


def test_max_items_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_MAX_ITEMS_INSTAGRAM", "25")
    assert ig.max_items() == 25
    monkeypatch.delenv("BRIGHTDATA_MAX_ITEMS_INSTAGRAM")
    assert ig.max_items() == ig.MAX_ITEMS_PER_RUN == 10


def test_poll_timeout_s_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_POLL_TIMEOUT_INSTAGRAM", "45")
    assert ig.poll_timeout_s() == 45
    monkeypatch.delenv("BRIGHTDATA_POLL_TIMEOUT_INSTAGRAM")
    assert ig.poll_timeout_s() == ig.POLL_TIMEOUT_S == 300
