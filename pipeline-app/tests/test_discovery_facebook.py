from pipeline_app import brightdata_job
from pipeline_app import discovery_facebook as fb


def _raw_row(**overrides):
    """A row shaped like the live payload from snapshot sd_mskdsc8e27l3f2p9yn.

    Note there is NO 'hashtags' key: the live Pages Posts rows omit it
    entirely, while the Reels product returns it as null. Both must
    normalize to [].
    """
    row = {
        "post_id": "1479086397353733",
        "date_posted": "2026-07-06T19:01:04.000Z",
        "timestamp": "2026-08-08T13:00:43.704Z",
        "post_type": "Reel",
        "profile_handle": "MrBeast6000",
        "user_username_raw": "MrBeast Gaming",
        "profile_id": "100057571594903",
        "is_page": True,
        "content": "$10,000 Every Boss You Beat",
        "url": "https://www.facebook.com/reel/1157962813213302/",
        "shortcode": "1479086397353733",
        "likes": 2836,
        "num_likes_type": {"type": "Like", "num": 2429},
        "num_comments": 149,
        "num_shares": 70,
        "video_view_count": 88381,
    }
    row.update(overrides)
    return row


def _error_row(url="https://www.facebook.com/NASA", code="dead_page"):
    """With include_errors=true, a failure arrives as a ROW, not an absence."""
    return {
        "timestamp": "2026-08-08T13:00:27.576Z",
        "input": {"url": url, "num_of_posts": 3},
        "error": "Seems page have not reels",
        "error_code": code,
    }


def test_parse_published_accepts_the_verified_iso_format():
    """Live Facebook rows carry real ISO 8601 UTC -- 2026-07-06T19:01:04.000Z
    (verified 2026-08-08), same as LinkedIn and UNLIKE Instagram, which
    returns a US-format local timestamp. The MM-DD-YYYY format in Bright
    Data's snippets is input-only and does not describe output."""
    assert fb._parse_published("2026-07-06T19:01:04.000Z") == "2026-07-06"
    assert fb._parse_published("2026-07-06") == "2026-07-06"


def test_preflight_reports_a_missing_key_once_without_calling_bright_data(monkeypatch, tmp_path):
    monkeypatch.delenv(fb.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(fb, "KEY_FILE", tmp_path / "absent.txt")

    def _fail_if_called(*a, **k):
        raise AssertionError("preflight must not touch the network")

    # discovery_facebook has no module-level `requests` import -- its HTTP
    # calls all go through brightdata_job, so that is what must not be hit.
    monkeypatch.setattr(brightdata_job.requests, "post", _fail_if_called)
    message = fb.preflight()
    assert message is not None
    assert fb.KEY_ENV_VAR in message
    assert "facebook" in message


def test_preflight_returns_none_when_the_key_is_configured(monkeypatch, tmp_path):
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("k", encoding="utf-8")
    monkeypatch.delenv(fb.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(fb, "KEY_FILE", key_file)
    assert fb.preflight() is None


def test_parse_published_rejects_unusable_values():
    assert fb._parse_published("") is None
    assert fb._parse_published(None) is None
    assert fb._parse_published("garbage") is None
    # US-format input is NOT silently reinterpreted: guessing between MM/DD
    # and DD/MM yields silently wrong dates, which is worse than a dropped
    # row -- and drops are counted and logged.
    assert fb._parse_published("07-06-2026") is None


def test_run_collection_job_prefers_a_pending_snapshot_over_a_new_billed_job(monkeypatch, tmp_path):
    """Bright Data bills per record. If the previous run paid for a snapshot
    and timed out before collecting it, this run must take that data rather
    than pay again."""
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    brightdata_job.record_pending("facebook/somehandle", "snap-abc")
    monkeypatch.setattr(fb, "api_key", lambda: "test-key")

    def _fail_if_called(handle, key):
        raise AssertionError("must not trigger a new job while a snapshot is pending")

    monkeypatch.setattr(fb, "_trigger_job", _fail_if_called)
    monkeypatch.setattr(fb, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(fb, "_fetch_job_results", lambda job_id, key: [{"post_id": "p1"}])
    assert fb._run_collection_job("somehandle") == [{"post_id": "p1"}]


def test_normalize_row_maps_every_verified_field():
    n = fb._normalize_row(_raw_row())
    assert n["id"] == "1479086397353733"
    assert n["published"] == "2026-07-06"
    assert n["content_type"] == "reel"
    assert n["author"] == "MrBeast6000"
    assert n["profile_id"] == "100057571594903"
    assert n["is_page"] is True
    assert n["body"] == "$10,000 Every Boss You Beat"
    assert n["url"] == "https://www.facebook.com/reel/1157962813213302/"
    assert n["comment_count"] == 149
    assert n["share_count"] == 70
    assert n["view_count"] == 88381


def test_like_count_comes_from_likes_not_num_likes_type():
    """`likes` is the reaction TOTAL (2836). `num_likes_type` is a dict
    holding only the 'Like' subtotal (2429) -- a different, smaller number.
    Reading it would understate engagement on every row."""
    n = fb._normalize_row(_raw_row())
    assert n["like_count"] == 2836


def test_timestamp_is_never_used_as_the_post_date():
    """`timestamp` is SCRAPE time, not post time -- 2026-08-08 on a post
    dated 2026-07-06. It reads as a plausible date field and is wrong by
    however long ago the post was made."""
    n = fb._normalize_row(_raw_row())
    assert n["published"] == "2026-07-06"
    assert not n["published_ts"].startswith("2026-08-08")


def test_published_ts_keeps_the_full_timestamp_for_sorting():
    n = fb._normalize_row(_raw_row())
    assert n["published_ts"] == "2026-07-06T19:01:04.000Z"


def test_hashtags_normalize_to_a_list_whether_absent_or_null():
    """VERIFIED LIVE: the key is ABSENT from Pages Posts rows and present-
    but-null on Reels rows. Both shapes are real."""
    assert fb._normalize_row(_raw_row())["hashtags"] == []
    assert fb._normalize_row(_raw_row(hashtags=None))["hashtags"] == []
    assert fb._normalize_row(_raw_row(hashtags=["#a"]))["hashtags"] == ["#a"]


def test_content_type_is_lowercased():
    """Bright Data returns display-cased values: 'Post', 'Reel'."""
    assert fb._normalize_row(_raw_row(post_type="Post"))["content_type"] == "post"
    assert fb._normalize_row(_raw_row(post_type="Reel"))["content_type"] == "reel"


def test_reel_is_preserved_as_a_real_content_type():
    """Reels are captured through this dataset rather than the dedicated
    Reels product; 'reel' is a valid value, not an error to coerce away."""
    assert fb._normalize_row(_raw_row(post_type="Reel"))["content_type"] == "reel"


def test_title_is_the_first_line_of_content():
    n = fb._normalize_row(_raw_row(content="First line.\nSecond line."))
    assert n["title"] == "First line."


def test_title_truncates_to_60_chars():
    n = fb._normalize_row(_raw_row(content="x" * 100))
    assert n["title"] == "x" * 60


def test_title_falls_back_to_post_id_when_content_is_empty():
    """Image-only posts genuinely have empty content -- a real case."""
    n = fb._normalize_row(_raw_row(content=""))
    assert n["title"] == "1479086397353733"


def test_normalize_row_returns_none_without_post_id():
    assert fb._normalize_row(_raw_row(post_id="")) is None


def test_normalize_row_returns_none_with_unusable_date():
    assert fb._normalize_row(_raw_row(date_posted="")) is None
    assert fb._normalize_row(_raw_row(date_posted="garbage")) is None


def test_normalize_row_drops_an_include_errors_error_row():
    """Error rows carry no post_id, so the id check already rejects them."""
    assert fb._normalize_row(_error_row()) is None


def test_normalize_row_tolerates_missing_optional_fields():
    n = fb._normalize_row({"post_id": "1", "date_posted": "2026-07-06T00:00:00.000Z"})
    assert n["body"] == ""
    assert n["author"] == ""
    assert n["hashtags"] == []
    assert n["like_count"] is None
    assert n["view_count"] is None
    assert n["content_type"] == "post"


def test_error_codes_collects_vendor_reasons():
    codes = fb._error_codes([_raw_row(), _error_row(code="dead_page"),
                             _error_row(code="not_found")])
    assert codes == ["dead_page", "not_found"]


def test_error_codes_is_empty_for_a_clean_batch():
    assert fb._error_codes([_raw_row()]) == []


import pytest

from pipeline_app import brightdata_job


def test_profile_url_uses_the_vanity_slug_form_for_named_handles():
    assert fb.profile_url("NASA") == "https://www.facebook.com/NASA"
    assert fb.profile_url("MrBeast6000") == "https://www.facebook.com/MrBeast6000"
    # A pasted @-prefixed handle still resolves.
    assert fb.profile_url("@zuck") == "https://www.facebook.com/zuck"


def test_profile_url_uses_profile_php_for_all_numeric_handles():
    """VERIFIED LIVE: profile.php?id=100044561550831 resolved to NASA. The
    bare facebook.com/<numeric-id> form was NOT tested, so it is not used --
    there is no reason to guess when a verified form exists."""
    assert fb.profile_url("100044561550831") == \
        "https://www.facebook.com/profile.php?id=100044561550831"


def test_trigger_job_sends_the_verified_request_shape(monkeypatch):
    captured = {}

    def fake_trigger(api_base, dataset_id, params, body, key):
        captured.update(api_base=api_base, dataset_id=dataset_id, params=params,
                        body=body, key=key)
        return "snap1"

    monkeypatch.setattr(brightdata_job, "trigger", fake_trigger)
    assert fb._trigger_job("NASA", "the-key") == "snap1"

    assert captured["dataset_id"] == fb.DATASET_ID
    assert captured["key"] == "the-key"
    assert captured["params"]["include_errors"] == "true"
    assert captured["params"]["notify"] == "false"
    # Bare array, not {"input": [...]} -- the object form belongs to the
    # synchronous /scrape endpoint. Verified HTTP 200 with the bare array.
    assert captured["body"] == [{
        "url": "https://www.facebook.com/NASA",
        "num_of_posts": fb.MAX_ITEMS_PER_RUN,
    }]


def test_trigger_job_sends_no_discovery_params(monkeypatch):
    """Unlike the Instagram and LinkedIn datasets, this product has no
    discovery mode. Sending type/discover_by would select a mode that does
    not exist here."""
    captured = {}
    monkeypatch.setattr(brightdata_job, "trigger",
                        lambda a, d, params, b, k: captured.update(params=params) or "s")
    fb._trigger_job("NASA", "the-key")
    assert "type" not in captured["params"]
    assert "discover_by" not in captured["params"]


def test_trigger_job_never_sends_exclusion_or_date_window_keys(monkeypatch):
    """All three of posts_to_not_include / start_date / end_date verified
    WORKING against the vendor and all three are deliberately unused.

    posts_to_not_include is the dangerous one. Excluding on-disk ids
    server-side removes them from the response, which disables BOTH of
    process_handle's termination conditions -- the early-stop counter needs
    on-disk ids to APPEAR (discovery_engine.py:54-57), and the lookback
    cutoff only applies while is_new (:44-45, :61-70). Every later run would
    then download MAX_ITEMS_PER_RUN progressively OLDER posts, daily, until
    the account's whole back-catalogue landed -- in the mode whose only job
    is new content. See the spec's "Rejected on analysis".
    """
    captured = {}
    monkeypatch.setattr(brightdata_job, "trigger",
                        lambda a, d, p, body, k: captured.update(body=body) or "s")
    fb._trigger_job("NASA", "the-key")

    for forbidden in ("posts_to_not_include", "start_date", "end_date"):
        assert forbidden not in captured["body"][0]


def test_run_collection_job_raises_clear_error_when_key_missing(monkeypatch):
    monkeypatch.setattr(fb, "api_key", lambda: None)
    with pytest.raises(RuntimeError, match="Bright Data API key not configured"):
        fb._run_collection_job("NASA")


def test_run_collection_job_drives_full_trigger_poll_fetch_cycle(monkeypatch):
    """Nothing else exercises this wiring -- every other adapter test stubs
    _run_collection_job wholesale. A transposed callable here would survive
    the whole suite and fail on the first live run, after paying for a job.
    Assert the snapshot id trigger() returns is threaded through to
    poll_status() and fetch_results()."""
    monkeypatch.setattr(fb, "api_key", lambda: "the-key")

    poll_calls = []
    fetch_calls = []
    statuses = iter(["running", "ready"])

    monkeypatch.setattr(brightdata_job, "trigger",
                        lambda a, d, p, b, k: "snap-789")
    monkeypatch.setattr(brightdata_job, "poll_status",
                        lambda a, job_id, k: (poll_calls.append(job_id), next(statuses))[1])
    monkeypatch.setattr(brightdata_job, "fetch_results",
                        lambda a, job_id, k: (fetch_calls.append(job_id), [_raw_row()])[1])
    monkeypatch.setattr(brightdata_job.time, "sleep", lambda s: None)

    result = fb._run_collection_job("NASA")

    assert result == [_raw_row()]
    assert poll_calls == ["snap-789", "snap-789"]
    assert fetch_calls == ["snap-789"]


def test_api_key_prefers_env_var_then_file(monkeypatch, tmp_path):
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("from-file", encoding="utf-8")
    monkeypatch.setattr(fb, "KEY_FILE", key_file)

    monkeypatch.setenv(fb.KEY_ENV_VAR, "from-env")
    assert fb.api_key() == "from-env"

    monkeypatch.delenv(fb.KEY_ENV_VAR, raising=False)
    assert fb.api_key() == "from-file"


def _row(post_id, date, content="hello", post_type="Post"):
    return _raw_row(post_id=post_id, date_posted=f"{date}T00:00:00.000Z",
                    content=content, post_type=post_type)


def _stub_job(monkeypatch, rows):
    monkeypatch.setattr(fb, "_run_collection_job", lambda handle: rows)


def test_enumerate_returns_engine_shaped_items(monkeypatch):
    _stub_job(monkeypatch, [_row("p1", "2026-07-06")])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert items == [{"id": "p1", "title": "hello", "published": "2026-07-06",
                      "content_type": "post"}]


def test_enumerate_sorts_newest_first(monkeypatch):
    _stub_job(monkeypatch, [
        _row("older", "2025-08-08"),
        _row("newest", "2026-07-06"),
        _row("middle", "2026-05-28"),
    ])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert [i["id"] for i in items] == ["newest", "middle", "older"]


def test_enumerate_sorts_same_day_rows_by_time_not_just_date(monkeypatch):
    """The sort MUST key on the full timestamp. Python's sort is stable, so
    a date-truncated key leaves same-day rows in Bright Data's arrival
    order, which can put a genuinely newer post behind ones already on disk
    and trip discovery_engine's early-stop dedup before reaching it. Both
    sibling adapters carry a published_ts for exactly this reason."""
    _stub_job(monkeypatch, [
        _raw_row(post_id="morning", date_posted="2026-07-06T08:00:00.000Z"),
        _raw_row(post_id="evening", date_posted="2026-07-06T20:00:00.000Z"),
    ])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert [i["id"] for i in items] == ["evening", "morning"]


def test_enumerate_caps_retained_items(monkeypatch):
    _stub_job(monkeypatch, [_row(f"p{i}", f"2026-07-{i:02d}") for i in range(1, 21)])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert len(items) == fb.MAX_ITEMS_PER_RUN


def test_full_cap_batch_records_a_saturation_error(monkeypatch):
    """Fault test. Ten of ten means posts were dropped that no later run can
    fetch -- the handle still reports 'ok', so this must be reported here."""
    _stub_job(monkeypatch, [_row(f"p{i}", f"2026-07-{i:02d}") for i in range(1, 11)])
    brightdata_job.drain_diagnostics()
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    saturation = [d for d in brightdata_job.drain_diagnostics()
                  if d["kind"] == "adapter.batch_saturated"]
    assert len(saturation) == 1
    assert saturation[0]["severity"] == "error"


def test_a_short_batch_records_no_saturation_diagnostic(monkeypatch):
    """Distinguishability. Nine of ten is a quiet account; ten of ten is
    truncation. The two must be observably different."""
    _stub_job(monkeypatch, [_row(f"p{i}", f"2026-07-{i:02d}") for i in range(1, 10)])
    brightdata_job.drain_diagnostics()
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert [d for d in brightdata_job.drain_diagnostics()
            if d["kind"] == "adapter.batch_saturated"] == []


def test_saturation_diagnostic_names_the_cap_the_override_and_the_lost_window(monkeypatch):
    """Surfacing. The record must be actionable on its own: an operator
    reading it in the log or the events table must know what to change."""
    _stub_job(monkeypatch, [_row(f"p{i}", f"2026-07-{i:02d}") for i in range(1, 11)])
    brightdata_job.drain_diagnostics()
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.batch_saturated"][0]
    assert record["detail"]["cap"] == 10
    assert record["detail"]["handle"] == "NASA"
    assert record["detail"]["platform"] == "facebook"
    assert record["detail"]["raw_count"] == 10
    assert fb.MAX_ITEMS_ENV_VAR in record["message"]
    assert "no backfill" in record["message"]


def test_enumerate_applies_keyword_filter_against_content(monkeypatch):
    _stub_job(monkeypatch, [
        _row("hit", "2026-07-06", content="Artemis launch today"),
        _row("miss", "2026-07-05", content="Something else"),
    ])
    items = fb.enumerate_newest_first("NASA", keyword_filter="artemis")
    assert [i["id"] for i in items] == ["hit"]


def test_enumerate_drops_unusable_rows_and_logs_the_count(monkeypatch, capsys):
    _stub_job(monkeypatch, [_row("good", "2026-07-06"), _raw_row(post_id="")])
    items = fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert [i["id"] for i in items] == ["good"]
    assert "dropped 1" in capsys.readouterr().err


def test_enumerate_logs_the_vendor_error_code_not_just_a_count(monkeypatch, capsys):
    """With include_errors=true Bright Data tells us WHY. Logging
    'dead_page' instead of a bare drop count is the difference between a
    diagnosable dead slug and a mystery."""
    _stub_job(monkeypatch, [_row("good", "2026-07-06"), _error_row(code="dead_page")])
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert "dead_page" in capsys.readouterr().err


def test_enumerate_warns_loudly_when_rows_returned_but_none_survive(monkeypatch, capsys):
    """A billed job that captured nothing would otherwise be recorded by
    process_handle as the healthy status 'no_new_content' -- indistinguishable
    from a quiet day."""
    _stub_job(monkeypatch, [_error_row(code="dead_page")])
    assert fb.enumerate_newest_first("NASA", keyword_filter=None) == []
    err = capsys.readouterr().err
    assert "none survived" in err
    assert "dead_page" in err


def test_enumerate_returns_empty_without_warning_for_a_genuinely_empty_job(monkeypatch, capsys):
    _stub_job(monkeypatch, [])
    assert fb.enumerate_newest_first("NASA", keyword_filter=None) == []
    assert "none survived" not in capsys.readouterr().err


def test_enumerate_overwrites_rather_than_merges_the_cache(monkeypatch):
    """A fresh successful enumerate replaces whatever this handle held, so
    download_item never reads a stale id from an earlier run."""
    _stub_job(monkeypatch, [_row("old", "2026-07-01")])
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    _stub_job(monkeypatch, [_row("new", "2026-07-06")])
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    assert set(fb._ENUMERATE_CACHE["NASA"]) == {"new"}


def test_enumerate_caches_per_handle(monkeypatch):
    _stub_job(monkeypatch, [_row("a1", "2026-07-06")])
    fb.enumerate_newest_first("NASA", keyword_filter=None)
    _stub_job(monkeypatch, [_row("b1", "2026-07-06")])
    fb.enumerate_newest_first("zuck", keyword_filter=None)
    assert set(fb._ENUMERATE_CACHE["NASA"]) == {"a1"}
    assert set(fb._ENUMERATE_CACHE["zuck"]) == {"b1"}


def test_enumerate_caches_items_filtered_out_by_keyword(monkeypatch):
    """keyword_filter narrows what the ENGINE walks, not what was collected
    and paid for. The cache must hold the full retained batch."""
    _stub_job(monkeypatch, [
        _row("hit", "2026-07-06", content="Artemis launch"),
        _row("miss", "2026-07-05", content="Other"),
    ])
    fb.enumerate_newest_first("NASA", keyword_filter="artemis")
    assert set(fb._ENUMERATE_CACHE["NASA"]) == {"hit", "miss"}


def test_enumerate_does_not_filter_by_author(monkeypatch):
    """Unlike linkedin-profile, this adapter must NOT drop rows whose
    profile_handle differs from the tracked handle. Across 17 live records
    profile_handle always matched, and filtering would be actively wrong: a
    numeric handle returns the VANITY profile_handle ('NASA'), so the
    comparison would discard every row for handle '100044561550831'."""
    _stub_job(monkeypatch, [_raw_row(post_id="p1", profile_handle="NASA")])
    items = fb.enumerate_newest_first("100044561550831", keyword_filter=None)
    assert [i["id"] for i in items] == ["p1"]
    assert fb._ENUMERATE_CACHE["100044561550831"]["p1"]["author"] == "NASA"


def test_enumerate_propagates_job_timeout(monkeypatch):
    def raise_timeout(handle):
        raise brightdata_job.BrightDataJobTimeout("timed out")

    monkeypatch.setattr(fb, "_run_collection_job", raise_timeout)
    with pytest.raises(brightdata_job.BrightDataJobTimeout):
        fb.enumerate_newest_first("NASA", keyword_filter=None)


def test_enumerate_propagates_job_failure(monkeypatch):
    def raise_failed(handle):
        raise brightdata_job.BrightDataJobFailed("failed")

    monkeypatch.setattr(fb, "_run_collection_job", raise_failed)
    with pytest.raises(brightdata_job.BrightDataJobFailed):
        fb.enumerate_newest_first("NASA", keyword_filter=None)


from pipeline_app import artifacts
from pipeline_app.discovery_paths import handle_dir


def test_on_disk_ids_is_empty_for_a_missing_directory(tmp_path):
    assert fb.on_disk_ids(tmp_path, "NASA") == set()


def test_on_disk_ids_reads_md_stems(tmp_path):
    d = handle_dir(tmp_path, "facebook", "NASA")
    d.mkdir(parents=True)
    (d / "1596499905178713.md").write_text("x", encoding="utf-8")
    (d / "1596305355198168.md").write_text("x", encoding="utf-8")
    (d / "notes.txt").write_text("x", encoding="utf-8")
    assert fb.on_disk_ids(tmp_path, "NASA") == {"1596499905178713", "1596305355198168"}


def test_on_disk_ids_matches_the_string_post_id_exactly(tmp_path):
    """post_id is a JSON string and on_disk_ids compares filename stems. A
    numeric id would never match, and every run would re-download and re-pay
    in silence."""
    d = handle_dir(tmp_path, "facebook", "NASA")
    d.mkdir(parents=True)
    (d / "1596499905178713.md").write_text("x", encoding="utf-8")
    assert "1596499905178713" in fb.on_disk_ids(tmp_path, "NASA")


def test_peek_upload_date_is_dead_code_by_design():
    """enumerate_newest_first only ever returns items carrying a normalized
    'published', so process_handle never falls through to this."""
    assert fb.peek_upload_date("anything") is None


def test_download_item_writes_frontmatter_and_body(tmp_path, monkeypatch):
    _stub_job(monkeypatch, [_raw_row()])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)

    result = fb.download_item(tmp_path, "MrBeast6000", "1479086397353733", "ignored")
    assert result == {"id": "1479086397353733", "ok": True, "published": "2026-07-06"}

    dest = handle_dir(tmp_path, "facebook", "MrBeast6000") / "1479086397353733.md"
    meta, body = artifacts.parse_frontmatter(dest.read_text(encoding="utf-8"))

    assert meta["post_id"] == "1479086397353733"
    assert meta["handle"] == "MrBeast6000"
    assert meta["author"] == "MrBeast6000"
    assert meta["profile_id"] == "100057571594903"
    assert meta["is_page"] is True
    assert meta["content_type"] == "reel"
    assert meta["published"] == "2026-07-06"
    assert meta["like_count"] == 2836
    assert meta["comment_count"] == 149
    assert meta["share_count"] == 70
    assert meta["view_count"] == 88381
    assert meta["hashtags"] == []
    assert "fetched_at" in meta
    assert body.strip() == "$10,000 Every Boss You Beat"


def test_download_item_writes_empty_placeholder_for_image_only_posts(tmp_path, monkeypatch):
    """Image-only posts genuinely have empty content -- a real case."""
    _stub_job(monkeypatch, [_raw_row(content="")])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)
    fb.download_item(tmp_path, "MrBeast6000", "1479086397353733", "ignored")

    dest = handle_dir(tmp_path, "facebook", "MrBeast6000") / "1479086397353733.md"
    _, body = artifacts.parse_frontmatter(dest.read_text(encoding="utf-8"))
    assert body.strip() == "(empty)"


def test_download_item_leaves_no_tmp_file(tmp_path, monkeypatch):
    """Write-temp-then-rename: an interrupted write must never leave a
    truncated file at a path on_disk_ids() would treat as captured."""
    _stub_job(monkeypatch, [_raw_row()])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)
    fb.download_item(tmp_path, "MrBeast6000", "1479086397353733", "ignored")

    d = handle_dir(tmp_path, "facebook", "MrBeast6000")
    assert list(d.glob("*.tmp")) == []


def test_download_item_raises_on_cache_miss_rather_than_degrading(tmp_path, monkeypatch):
    """A missing entry is a programming error: every engine call path runs
    enumerate_newest_first for this handle first. KeyError propagates to
    run_discovery's per-handle error path instead of failing silently."""
    _stub_job(monkeypatch, [_raw_row()])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)
    with pytest.raises(KeyError):
        fb.download_item(tmp_path, "MrBeast6000", "nonexistent-id", "ignored")


def test_download_item_makes_no_network_call(tmp_path, monkeypatch):
    """download_item reads the cache. Calling Bright Data once per item
    would double-pay for posts already collected."""
    _stub_job(monkeypatch, [_raw_row()])
    fb.enumerate_newest_first("MrBeast6000", keyword_filter=None)

    def boom(*a, **k):
        raise AssertionError("download_item must not call Bright Data")

    monkeypatch.setattr(fb, "_run_collection_job", boom)
    monkeypatch.setattr(brightdata_job, "trigger", boom)
    assert fb.download_item(tmp_path, "MrBeast6000", "1479086397353733", "x")["ok"]


def test_max_items_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_MAX_ITEMS_FACEBOOK", "25")
    assert fb.max_items() == 25
    monkeypatch.delenv("BRIGHTDATA_MAX_ITEMS_FACEBOOK")
    assert fb.max_items() == fb.MAX_ITEMS_PER_RUN == 10


def test_poll_timeout_s_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_POLL_TIMEOUT_FACEBOOK", "45")
    assert fb.poll_timeout_s() == 45
    monkeypatch.delenv("BRIGHTDATA_POLL_TIMEOUT_FACEBOOK")
    assert fb.poll_timeout_s() == fb.POLL_TIMEOUT_S == 300
