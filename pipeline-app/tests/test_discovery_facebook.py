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


def test_parse_published_rejects_unusable_values():
    assert fb._parse_published("") is None
    assert fb._parse_published(None) is None
    assert fb._parse_published("garbage") is None
    # US-format input is NOT silently reinterpreted: guessing between MM/DD
    # and DD/MM yields silently wrong dates, which is worse than a dropped
    # row -- and drops are counted and logged.
    assert fb._parse_published("07-06-2026") is None


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
