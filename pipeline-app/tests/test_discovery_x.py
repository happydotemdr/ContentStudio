import pytest

from pipeline_app import discovery_x as x


def test_parse_published_accepts_the_verified_iso_format():
    """Live X rows carry real ISO 8601 UTC -- 2026-08-08T01:11:45.000Z
    (verified 2026-08-08, snapshot sd_mskd8iv12ivrnbejlz). This matches
    LinkedIn and differs from the Instagram product's US-format local
    timestamp; three Bright Data datasets, two date formats, so none may be
    assumed from another."""
    assert x._parse_published("2026-08-08T01:11:45.000Z") == "2026-08-08"
    assert x._parse_published("2026-08-08") == "2026-08-08"


def test_parse_published_rejects_unusable_values():
    assert x._parse_published("") is None
    assert x._parse_published(None) is None
    assert x._parse_published("not a date") is None
    # A US-format date is NOT silently reinterpreted -- guessing between
    # MM/DD and DD/MM produces wrong dates, which is worse than a dropped
    # row, and dropped rows are counted and logged.
    assert x._parse_published("08/08/2026 01:11:45") is None


def _raw_row(**overrides):
    """A row shaped like the live payload from snapshot sd_mskd8iv12ivrnbejlz."""
    row = {
        "id": "2085896713185714235",
        "date_posted": "2026-08-08T01:11:45.000Z",
        "user_posted": "CNN",
        "name": "CNN",
        "user_id": "759251",
        "description": "A daring mission to rescue one of NASA's observatories.",
        "url": "https://twitter.com/759251/status/2085896713185714235",
        "is_repost": False,
        "likes": 310,
        "replies": 85,
        "reposts": 64,
        "views": 214564,
        "bookmarks": 16,
        "quotes": 6,
        "hashtags": None,
        "photos": ["https://pbs.twimg.com/media/HPKX_XjXUAAxkvS.jpg"],
        "videos": None,
        "external_url": "https://cnn.it/45aXVbJ",
    }
    row.update(overrides)
    return row


def test_normalize_row_maps_every_verified_field():
    n = x._normalize_row(_raw_row())
    assert n["id"] == "2085896713185714235"
    assert n["published"] == "2026-08-08"
    assert n["author"] == "CNN"
    assert n["body"].startswith("A daring mission")
    assert n["like_count"] == 310
    assert n["comment_count"] == 85       # from `replies`
    assert n["repost_count"] == 64
    assert n["view_count"] == 214564
    assert n["bookmark_count"] == 16
    assert n["quote_count"] == 6
    assert n["photos"] == ["https://pbs.twimg.com/media/HPKX_XjXUAAxkvS.jpg"]
    assert n["external_url"] == "https://cnn.it/45aXVbJ"


def test_normalize_row_keeps_media_only_posts_with_an_empty_body():
    """3 of 10 live elonmusk rows had description: null -- media-only posts
    (snapshot sd_mskdghugb6u3685n6). These are KEPT, not dropped: the row
    still carries a date, six engagement counts and the media URLs, and
    dropping them would pay for rows it discards on a video-heavy account."""
    n = x._normalize_row(_raw_row(description=None, photos=None,
                                  videos=[{"video_url": "https://video.twimg.com/a.mp4",
                                           "duration": 6041}]))
    assert n is not None
    assert n["body"] == ""
    assert n["videos"] == ["https://video.twimg.com/a.mp4"]


def test_normalize_row_flattens_the_videos_struct_list_to_urls():
    """videos is a list of structs carrying video_url and duration (verified
    live). Storing the raw structs would put duration integers in the
    frontmatter; only the URL is wanted."""
    n = x._normalize_row(_raw_row(videos=[
        {"video_url": "https://video.twimg.com/a.mp4", "duration": 6041},
        {"video_url": "https://video.twimg.com/b.mp4", "duration": 3761157},
    ]))
    assert n["videos"] == ["https://video.twimg.com/a.mp4",
                           "https://video.twimg.com/b.mp4"]


def test_normalize_row_title_is_the_first_line_then_falls_back_to_id():
    n = x._normalize_row(_raw_row(description="First line.\nSecond line."))
    assert n["title"] == "First line."
    media_only = x._normalize_row(_raw_row(description=None))
    assert media_only["title"] == "2085896713185714235"


def test_normalize_row_truncates_title_to_60_chars():
    n = x._normalize_row(_raw_row(description="y" * 100))
    assert n["title"] == "y" * 60


def test_normalize_row_drops_rows_with_no_id_or_unusable_date():
    assert x._normalize_row(_raw_row(id=None)) is None
    assert x._normalize_row(_raw_row(id="")) is None
    assert x._normalize_row(_raw_row(date_posted="nonsense")) is None
    assert x._normalize_row(_raw_row(date_posted=None)) is None


def test_normalize_row_drops_the_include_errors_error_row():
    """include_errors=true yields rows carrying error/error_code with every
    content field null (verified live, snapshot sd_mskdls3f26klcqyxk9:
    error_code 'dead_page'). They have no id, so the id guard discards them
    with no special-casing -- pin that, so a future 'helpful' fallback that
    invents an id from the url does not resurrect them."""
    error_row = {"error": "No public posts were found in the profile for the "
                          "specified period.",
                 "error_code": "dead_page",
                 "timestamp": "2026-08-08T12:56:25.349Z"}
    assert x._normalize_row(error_row) is None


def test_normalize_row_keeps_the_full_timestamp_as_a_separate_sort_key():
    """'published' truncates to the date, so same-day rows need the time of
    day to sort correctly. Rows arrive unsorted (verified live)."""
    n = x._normalize_row(_raw_row())
    assert n["published_ts"] == "2026-08-08T01:11:45.000Z"


def test_normalize_row_coerces_missing_list_fields_to_empty_lists():
    """hashtags/photos/videos come back as null, not [], on most rows.
    yaml.safe_dump renders None as 'null'; an empty list is the honest shape."""
    n = x._normalize_row(_raw_row(hashtags=None, photos=None, videos=None))
    assert n["hashtags"] == []
    assert n["photos"] == []
    assert n["videos"] == []


def test_api_key_prefers_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(x.KEY_ENV_VAR, "env-key")
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    monkeypatch.setattr(x, "KEY_FILE", key_file)
    assert x.api_key() == "env-key"


def test_api_key_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.delenv(x.KEY_ENV_VAR, raising=False)
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("  file-key\n", encoding="utf-8")
    monkeypatch.setattr(x, "KEY_FILE", key_file)
    assert x.api_key() == "file-key"


def test_api_key_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv(x.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(x, "KEY_FILE", tmp_path / "absent.txt")
    assert x.api_key() is None


def test_profile_url_strips_the_at_sign():
    assert x.profile_url("@CNN") == "https://x.com/CNN"
    assert x.profile_url("elonmusk") == "https://x.com/elonmusk"


def _fake_key(monkeypatch, value="test-key"):
    monkeypatch.setattr(x, "api_key", lambda: value)


def test_trigger_job_requests_a_discovery_job_not_a_single_page_collect(monkeypatch):
    """Without type=discover_new/discover_by=profile_url, Bright Data reads
    the input url as a single page to collect -- the wrong product mode
    entirely, and a silently useless one."""
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"snapshot_id": "snap1"}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(x.requests, "post", fake_post)
    assert x._trigger_job("CNN", "test-key") == "snap1"

    assert captured["url"].endswith("/trigger")
    assert captured["params"]["dataset_id"] == "gd_lwxkxvnf1cynvib9co"
    assert captured["params"]["type"] == "discover_new"
    assert captured["params"]["discover_by"] == "profile_url"
    assert captured["params"]["limit_per_input"] == x.MAX_ITEMS_PER_RUN
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    # A bare array, not {"input": [...]} -- the dashboard's object form
    # belongs to the synchronous /scrape endpoint, which no adapter uses.
    assert captured["json"] == [{"url": "https://x.com/CNN"}]


def test_trigger_job_does_not_send_date_filters(monkeypatch):
    """start_date/end_date are PROVEN broken on this dataset -- a two-day
    window against an account posting hundreds of times a day returned a
    single error row, error_code 'dead_page' (snapshot sd_mskdls3f26klcqyxk9).
    Sending empty strings would be harmless but misleading; sending real ones
    would break collection. Pin that neither key is present."""
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"snapshot_id": "snap1"}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(x.requests, "post", fake_post)
    x._trigger_job("CNN", "test-key")
    assert "start_date" not in captured["json"][0]
    assert "end_date" not in captured["json"][0]


def test_run_collection_job_returns_results_on_ready(monkeypatch):
    _fake_key(monkeypatch)
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(x, "_fetch_job_results", lambda job_id, key: [{"id": "p1"}])
    monkeypatch.setattr(x.time, "sleep", lambda s: None)
    assert x._run_collection_job("CNN") == [{"id": "p1"}]


def test_run_collection_job_polls_until_ready(monkeypatch):
    _fake_key(monkeypatch)
    statuses = iter(["running", "running", "ready"])
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: next(statuses))
    monkeypatch.setattr(x, "_fetch_job_results", lambda job_id, key: [{"id": "p1"}])
    monkeypatch.setattr(x.time, "sleep", lambda s: None)
    assert x._run_collection_job("CNN") == [{"id": "p1"}]


def test_run_collection_job_raises_on_failed_status(monkeypatch):
    """A failed job must NEVER return [] -- the engine would record the
    healthy status 'no_new_content' for a job that was billed and failed."""
    _fake_key(monkeypatch)
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "failed")
    monkeypatch.setattr(x.time, "sleep", lambda s: None)
    with pytest.raises(x.BrightDataJobFailed):
        x._run_collection_job("CNN")


def test_run_collection_job_raises_on_timeout(monkeypatch):
    _fake_key(monkeypatch)
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "running")
    monkeypatch.setattr(x.time, "sleep", lambda s: None)
    monkeypatch.setattr(x, "POLL_TIMEOUT_S", 0)
    with pytest.raises(x.BrightDataJobTimeout):
        x._run_collection_job("CNN")


def test_run_collection_job_raises_clear_error_when_key_missing(monkeypatch):
    monkeypatch.setattr(x, "api_key", lambda: None)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("must not trigger a paid job with no key")

    monkeypatch.setattr(x, "_trigger_job", _fail_if_called)
    with pytest.raises(RuntimeError, match="Bright Data API key not configured"):
        x._run_collection_job("CNN")


def test_poll_timeout_is_600_not_the_inherited_300():
    """Deliberate divergence from Instagram and LinkedIn. Measured latency
    was 243s at limit_per_input=10, the production setting, so 300s leaves
    under a minute of margin. This test exists to fail a well-meaning 'make
    the constants consistent' edit."""
    assert x.POLL_TIMEOUT_S == 600


def _enumerate_with(monkeypatch, rows):
    _fake_key(monkeypatch)
    monkeypatch.setattr(x, "_trigger_job", lambda handle, key: "job1")
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(x, "_fetch_job_results", lambda job_id, key: rows)
    monkeypatch.setattr(x.time, "sleep", lambda s: None)


def test_enumerate_drops_posts_written_by_someone_else(monkeypatch):
    """discover_by=profile_url returns the tracked account's TIMELINE, not
    only its authorship. Live job sd_mskdghugb6u3685n6 asked for elonmusk's
    10 newest and returned one authored by arctotherium42. Without this
    filter, output/brand-intel/x/<handle>/ stops meaning 'what this account
    wrote'."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", user_posted="elonmusk", date_posted="2026-08-08T04:00:00.000Z"),
        _raw_row(id="2", user_posted="arctotherium42", date_posted="2026-08-07T12:06:57.000Z"),
    ])
    items = x.enumerate_newest_first("elonmusk", None)
    assert [i["id"] for i in items] == ["1"]


def test_enumerate_author_filter_is_case_insensitive(monkeypatch):
    """The handle as registered and user_posted as returned need not agree on
    case -- the live CNN rows carry user_posted 'CNN' while the profile URL
    resolves to x.com/cnn."""
    _enumerate_with(monkeypatch, [_raw_row(id="1", user_posted="CNN")])
    assert [i["id"] for i in x.enumerate_newest_first("cnn", None)] == ["1"]


def test_enumerate_does_not_use_is_repost_as_the_filter(monkeypatch):
    """is_repost was False on the foreign arctotherium42 row, and False on
    all 16 post records observed. It is the field a maintainer will reach for
    and it does not work. This test fails if the filter is 'simplified' to
    is_repost: the foreign row below is explicitly is_repost=False, so an
    is_repost-based filter would keep it."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", user_posted="elonmusk", is_repost=False),
        _raw_row(id="2", user_posted="someone_else", is_repost=False),
    ])
    items = x.enumerate_newest_first("elonmusk", None)
    assert [i["id"] for i in items] == ["1"]


def test_enumerate_returns_newest_first_from_unsorted_input(monkeypatch):
    """Rows arrive badly unsorted -- live job 4 returned Aug 6, 8, 7, 6, 7,
    8, 3, 1, 4, 8. The engine's early-stop dedup assumes newest-first."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="old", date_posted="2026-08-01T00:46:44.000Z"),
        _raw_row(id="new", date_posted="2026-08-08T03:54:50.000Z"),
        _raw_row(id="mid", date_posted="2026-08-04T20:57:23.000Z"),
    ])
    items = x.enumerate_newest_first("CNN", None)
    assert [i["id"] for i in items] == ["new", "mid", "old"]


def test_enumerate_sorts_same_day_rows_by_time_of_day(monkeypatch):
    """'published' truncates to the date. Python's sort is stable, so
    same-day rows sorted on the date alone would keep Bright Data's arbitrary
    arrival order -- which can put a genuinely newer post behind ones already
    on disk and trip the early-stop dedup before reaching it."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="early", date_posted="2026-08-08T01:11:45.000Z"),
        _raw_row(id="late", date_posted="2026-08-08T08:54:49.000Z"),
    ])
    items = x.enumerate_newest_first("CNN", None)
    assert [i["id"] for i in items] == ["late", "early"]


def test_enumerate_caps_after_filtering_so_the_cap_bounds_retained_items(monkeypatch):
    """The cap must bound RETAINED items, not raw rows. Cap-then-filter would
    keep the 10 newest raw rows (ids 15..6 from 15 total), drop the five
    foreign authors, and return only 5 items. Filter-then-cap (correct) keeps
    all 10 CNN rows and returns all 10 newest-first. This test fails if the
    cap is applied before the author filter."""
    rows = []
    # Ids 1-10: authored by CNN (will pass author filter)
    for n in range(1, 11):
        rows.append(_raw_row(id=str(n), user_posted="CNN",
                             date_posted=f"2026-08-{n:02d}T00:00:00.000Z"))
    # Ids 11-15: authored by stranger (will be filtered out)
    for n in range(11, 16):
        rows.append(_raw_row(id=str(n), user_posted="stranger",
                             date_posted=f"2026-08-{n:02d}T00:00:00.000Z"))
    _enumerate_with(monkeypatch, rows)
    items = x.enumerate_newest_first("CNN", None)
    # If cap is applied after filter (correct): 10 CNN rows remain, all returned
    # newest-first as ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1"].
    # If cap is applied before filter (bug): 10 newest raw rows (ids 15..6) are
    # kept, then five foreign rows are dropped, leaving only 5 items.
    assert len(items) == x.MAX_ITEMS_PER_RUN
    assert [i["id"] for i in items] == ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1"]


def test_enumerate_keeps_media_only_posts(monkeypatch):
    """A media-only post (description: null) is a normal X post, not an
    unusable row. 3 of 10 live rows for one account were media-only."""
    _enumerate_with(monkeypatch, [_raw_row(id="1", description=None)])
    items = x.enumerate_newest_first("CNN", None)
    assert [i["id"] for i in items] == ["1"]
    assert items[0]["title"] == "1"


def test_enumerate_applies_keyword_filter_against_the_body(monkeypatch):
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", description="A daring NASA mission."),
        _raw_row(id="2", description="Senate confirms attorney general."),
    ])
    assert [i["id"] for i in x.enumerate_newest_first("CNN", "nasa")] == ["1"]


def test_enumerate_returns_empty_list_when_the_job_had_nothing(monkeypatch):
    """The one case that honestly means 'nothing to report'."""
    _enumerate_with(monkeypatch, [])
    assert x.enumerate_newest_first("CNN", None) == []


def test_enumerate_warns_when_rows_returned_but_all_filtered(monkeypatch, capsys):
    """A paid batch that yields nothing is recorded by process_handle as the
    healthy status 'no_new_content'. It must be loud here or it is invisible."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", user_posted="stranger"),
        _raw_row(id="2", user_posted="another_stranger"),
    ])
    assert x.enumerate_newest_first("CNN", None) == []
    err = capsys.readouterr().err
    assert "none survived filtering" in err
    assert "posts its own content" in err


def test_enumerate_warns_differently_when_all_rows_were_unusable(monkeypatch, capsys):
    """An all-error batch (the include_errors 'dead_page' shape) points at a
    dead or renamed handle, not at authorship. Pointing the operator at the
    wrong cause wastes their time."""
    _enumerate_with(monkeypatch, [
        {"error": "No public posts were found.", "error_code": "dead_page"},
    ])
    assert x.enumerate_newest_first("CNN", None) == []
    err = capsys.readouterr().err
    assert "none survived filtering" in err
    assert "still valid" in err
    assert "posts its own content" not in err


def test_enumerate_caches_rows_for_download_item(monkeypatch):
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)
    assert x._ENUMERATE_CACHE["CNN"]["1"]["author"] == "CNN"


def test_enumerate_overwrites_rather_than_merges_the_cache(monkeypatch):
    """A fresh successful enumerate replaces whatever the handle held, so
    download_item never reads a stale id from an earlier run in-process."""
    _enumerate_with(monkeypatch, [_raw_row(id="old")])
    x.enumerate_newest_first("CNN", None)
    _enumerate_with(monkeypatch, [_raw_row(id="fresh")])
    x.enumerate_newest_first("CNN", None)
    assert set(x._ENUMERATE_CACHE["CNN"]) == {"fresh"}


def test_enumerate_warns_about_both_causes_when_they_are_mixed(monkeypatch, capsys):
    """A batch that is part error rows and part other people's posts must not
    point the operator at only one cause."""
    _enumerate_with(monkeypatch, [
        {"error": "No public posts were found.", "error_code": "dead_page"},
        _raw_row(id="2", user_posted="stranger"),
    ])
    assert x.enumerate_newest_first("CNN", None) == []
    err = capsys.readouterr().err
    assert "none survived filtering" in err
    assert "valid and posts its own content" in err


def test_enumerate_keys_identity_on_id_not_url(monkeypatch):
    """The dataset returns two different URL shapes -- legacy
    twitter.com/<numeric_profile_id>/status/<id> for CNN and
    x.com/<handle>/status/<id> for elonmusk (both verified live). Anything
    that derived identity from the URL would treat the same account's posts
    as two populations."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", url="https://twitter.com/759251/status/1",
                 date_posted="2026-08-08T01:00:00.000Z"),
        _raw_row(id="2", url="https://x.com/CNN/status/2",
                 date_posted="2026-08-08T02:00:00.000Z"),
    ])
    items = x.enumerate_newest_first("CNN", None)
    assert [i["id"] for i in items] == ["2", "1"]
    assert set(x._ENUMERATE_CACHE["CNN"]) == {"1", "2"}


def test_enumerate_returns_a_constant_content_type(monkeypatch):
    """The engine's item shape wants content_type. X's only type-like field
    is is_repost, which is unreliable, so the adapter reports the constant
    'post' and does not write it to disk."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    assert x.enumerate_newest_first("CNN", None)[0]["content_type"] == "post"
