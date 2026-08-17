import pytest

from pipeline_app import brightdata_job
from pipeline_app import discovery_x as x


def test_parse_published_accepts_the_verified_iso_format():
    """Live X rows carry real ISO 8601 UTC -- 2026-08-08T01:11:45.000Z
    (verified 2026-08-08, snapshot sd_mskd8iv12ivrnbejlz). This matches
    LinkedIn and differs from the Instagram product's US-format local
    timestamp; three Bright Data datasets, two date formats, so none may be
    assumed from another."""
    assert x._parse_published("2026-08-08T01:11:45.000Z") == "2026-08-08"
    assert x._parse_published("2026-08-08") == "2026-08-08"


def test_preflight_reports_a_missing_key_once_without_calling_bright_data(monkeypatch, tmp_path):
    monkeypatch.delenv(x.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(x, "KEY_FILE", tmp_path / "absent.txt")

    def _fail_if_called(*a, **k):
        raise AssertionError("preflight must not touch the network")

    monkeypatch.setattr(x.requests, "post", _fail_if_called)
    message = x.preflight()
    assert message is not None
    assert x.KEY_ENV_VAR in message
    assert "x" in message


def test_preflight_returns_none_when_the_key_is_configured(monkeypatch, tmp_path):
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("k", encoding="utf-8")
    monkeypatch.delenv(x.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(x, "KEY_FILE", key_file)
    assert x.preflight() is None


def test_parse_published_rejects_unusable_values():
    assert x._parse_published("") is None
    assert x._parse_published(None) is None
    assert x._parse_published("not a date") is None
    # A US-format date is NOT silently reinterpreted -- guessing between
    # MM/DD and DD/MM produces wrong dates, which is worse than a dropped
    # row, and dropped rows are counted and logged.
    assert x._parse_published("08/08/2026 01:11:45") is None


def test_run_collection_job_prefers_a_pending_snapshot_over_a_new_billed_job(monkeypatch, tmp_path):
    """Bright Data bills per record. If the previous run paid for a snapshot
    and timed out before collecting it, this run must take that data rather
    than pay again."""
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    brightdata_job.record_pending("x/somehandle", "snap-abc")
    monkeypatch.setattr(x, "api_key", lambda: "test-key")

    def _fail_if_called(handle, key):
        raise AssertionError("must not trigger a new job while a snapshot is pending")

    monkeypatch.setattr(x, "_trigger_job", _fail_if_called)
    monkeypatch.setattr(x, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(x, "_fetch_job_results", lambda job_id, key: [{"id": "p1"}])
    assert x._run_collection_job("somehandle") == [{"id": "p1"}]


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
    would break collection. Pin that neither key is present in EITHER channel
    Bright Data reads them from: the JSON body (brightdata_job.trigger's
    `body` arg) and the query params (its `params` arg, which is what
    /trigger's `params={"dataset_id": dataset_id, **params}` sends) -- a date
    filter added to either would slip past a body-only check."""
    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"snapshot_id": "snap1"}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured["json"] = json
        captured["params"] = params
        return _Resp()

    monkeypatch.setattr(x.requests, "post", fake_post)
    x._trigger_job("CNN", "test-key")
    assert "start_date" not in captured["json"][0]
    assert "end_date" not in captured["json"][0]
    assert "start_date" not in captured["params"]
    assert "end_date" not in captured["params"]


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
    cap is applied before the author filter.

    The foreign (stranger) rows are appended to the fixture BEFORE the CNN
    rows -- deliberate, not incidental. With CNN rows first (as this fixture
    used to be ordered), a cap applied to raw INSERTION order (before any
    sort or author filter) would coincidentally select exactly the 10 CNN
    rows and pass this test for the wrong reason. With strangers first, that
    same insertion-order-cap bug instead keeps the 5 strangers plus the 5
    oldest CNN rows, then filters down to 5 -- failing both assertions below,
    same as the sort-order and filter-order bugs this test already catches."""
    rows = []
    # Ids 11-15: authored by stranger (will be filtered out). Appended first.
    for n in range(11, 16):
        rows.append(_raw_row(id=str(n), user_posted="stranger",
                             date_posted=f"2026-08-{n:02d}T00:00:00.000Z"))
    # Ids 1-10: authored by CNN (will pass author filter). Appended after.
    for n in range(1, 11):
        rows.append(_raw_row(id=str(n), user_posted="CNN",
                             date_posted=f"2026-08-{n:02d}T00:00:00.000Z"))
    _enumerate_with(monkeypatch, rows)
    items = x.enumerate_newest_first("CNN", None)
    # If cap is applied after filter (correct): 10 CNN rows remain, all returned
    # newest-first as ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1"].
    # If cap is applied before filter (bug): 10 newest raw rows (ids 15..6) are
    # kept, then five foreign rows are dropped, leaving only 5 items.
    assert len(items) == x.MAX_ITEMS_PER_RUN
    assert [i["id"] for i in items] == ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1"]


def test_full_cap_batch_records_a_saturation_error(monkeypatch):
    """Fault test. Ten of ten means posts were dropped that no later run can
    fetch -- the handle still reports 'ok', so this must be reported here."""
    _enumerate_with(monkeypatch, [
        _raw_row(id=str(i), user_posted="CNN", date_posted=f"2026-08-{i:02d}T00:00:00.000Z")
        for i in range(1, 11)
    ])
    brightdata_job.drain_diagnostics()
    x.enumerate_newest_first("CNN", None)
    saturation = [d for d in brightdata_job.drain_diagnostics()
                  if d["kind"] == "adapter.batch_saturated"]
    assert len(saturation) == 1
    assert saturation[0]["severity"] == "error"


def test_a_short_batch_records_no_saturation_diagnostic(monkeypatch):
    """Distinguishability. Nine of ten is a quiet account; ten of ten is
    truncation. The two must be observably different."""
    _enumerate_with(monkeypatch, [
        _raw_row(id=str(i), user_posted="CNN", date_posted=f"2026-08-{i:02d}T00:00:00.000Z")
        for i in range(1, 10)
    ])
    brightdata_job.drain_diagnostics()
    x.enumerate_newest_first("CNN", None)
    assert [d for d in brightdata_job.drain_diagnostics()
            if d["kind"] == "adapter.batch_saturated"] == []


def test_saturation_diagnostic_names_the_cap_the_override_and_the_lost_window(monkeypatch):
    """Surfacing. The record must be actionable on its own: an operator
    reading it in the log or the events table must know what to change."""
    _enumerate_with(monkeypatch, [
        _raw_row(id=str(i), user_posted="CNN", date_posted=f"2026-08-{i:02d}T00:00:00.000Z")
        for i in range(1, 11)
    ])
    brightdata_job.drain_diagnostics()
    x.enumerate_newest_first("CNN", None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.batch_saturated"][0]
    assert record["detail"]["cap"] == 10
    assert record["detail"]["handle"] == "CNN"
    assert record["detail"]["platform"] == "x"
    assert record["detail"]["raw_count"] == 10
    assert x.MAX_ITEMS_ENV_VAR in record["message"]
    assert "no backfill" in record["message"]


def test_dropped_rows_reach_a_durable_surface_not_only_stderr(monkeypatch, capsys):
    """Fault test. The Scheduled Task command has no redirection, so a stderr
    warning on the production path has no destination at all (B-01)."""
    _enumerate_with(monkeypatch, [_raw_row(id="1", user_posted="CNN"), {"no": "id"}])
    brightdata_job.drain_diagnostics()
    x.enumerate_newest_first("CNN", None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.rows_dropped"][0]
    assert record["severity"] == "warning"
    assert record["detail"]["dropped"] == 1
    assert record["source"] == "discovery_x"
    assert "dropped 1 unusable row(s)" in capsys.readouterr().err   # the print stays


def test_foreign_author_rows_reach_a_durable_surface_not_only_stderr(monkeypatch, capsys):
    """Fault test, the foreign-author case: X filters both unusable and
    foreign-author rows and today only unusable rows reach a durable
    surface -- this must be true for the foreign-author drop too."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", user_posted="CNN"),
        _raw_row(id="2", user_posted="someone_else"),
    ])
    brightdata_job.drain_diagnostics()
    x.enumerate_newest_first("CNN", None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.foreign_rows_dropped"][0]
    assert record["severity"] == "warning"
    assert record["detail"]["dropped"] == 1
    assert record["source"] == "discovery_x"
    assert "dropped 1 row(s) by another author" in capsys.readouterr().err


def test_a_clean_batch_produces_no_diagnostics_at_all(monkeypatch):
    """Distinguishability. A degraded run must be observably different from a
    healthy one -- 'no diagnostics' is the healthy signal."""
    _enumerate_with(monkeypatch, [_raw_row(id="1", user_posted="CNN")])
    brightdata_job.drain_diagnostics()
    x.enumerate_newest_first("CNN", None)
    assert brightdata_job.drain_diagnostics() == []


def test_diagnostics_carry_everything_obs_record_event_requires(monkeypatch):
    """Surfacing. P8 writes these straight into the events table; a record
    missing a column is a record that never becomes a row."""
    _enumerate_with(monkeypatch, [
        _raw_row(id="1", user_posted="CNN"),
        {"no": "id"},
        _raw_row(id="2", user_posted="someone_else"),
    ])
    brightdata_job.drain_diagnostics()
    x.enumerate_newest_first("CNN", None)
    records = brightdata_job.drain_diagnostics()
    assert records
    for record in records:
        assert set(record) == {"kind", "severity", "source", "message", "detail"}
        assert record["severity"] in {"info", "warning", "error", "critical"}
        assert record["message"]


def test_saturation_fires_even_when_a_filtered_row_drops_kept_below_the_cap(monkeypatch):
    """Plan correction (T17 task review, 2026-08-16): saturation must be
    measured on the RAW Bright Data count, not the post-filter 'kept' count.
    Ten raw rows at cap=10, but one is by a foreign author -- kept drops to
    9. The cap still truncated the batch (Bright Data returned exactly 10,
    its per-input limit), so the alarm must still fire even though
    len(kept) < cap. X is the most exposed adapter: it filters both unusable
    rows and foreign-author rows."""
    _enumerate_with(monkeypatch, [
        _raw_row(id=str(i), user_posted="CNN", date_posted=f"2026-08-{i:02d}T00:00:00.000Z")
        for i in range(1, 10)
    ] + [_raw_row(id="10", user_posted="someone_else", date_posted="2026-08-10T00:00:00.000Z")])
    brightdata_job.drain_diagnostics()
    items = x.enumerate_newest_first("CNN", None)
    assert len(items) == 9  # kept < cap after the foreign-author row is dropped
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.batch_saturated"][0]
    assert record["detail"]["raw_count"] == 10
    assert record["detail"]["collected"] == 9


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


def test_on_disk_ids_reads_filename_stems(tmp_path):
    """The ids Bright Data returns are JSON strings, and on_disk_ids compares
    against filename stems. A numeric id would never match, so every run
    would re-download and re-pay in silence."""
    directory = tmp_path / "output" / "brand-intel" / "x" / "cnn"
    directory.mkdir(parents=True)
    (directory / "2085896713185714235.md").write_text("x", encoding="utf-8")
    (directory / "notes.txt").write_text("x", encoding="utf-8")
    assert x.on_disk_ids(tmp_path, "CNN") == {"2085896713185714235"}


def test_on_disk_ids_empty_when_directory_absent(tmp_path):
    assert x.on_disk_ids(tmp_path, "CNN") == set()


def test_peek_upload_date_is_none():
    """Dead code by design: enumerate_newest_first only ever returns items
    carrying a normalized 'published', so process_handle never falls through
    to this -- same as discovery_bluesky/instagram/linkedin."""
    assert x.peek_upload_date("1") is None


def test_download_item_writes_frontmatter_and_body(monkeypatch, tmp_path):
    _enumerate_with(monkeypatch, [_raw_row()])
    x.enumerate_newest_first("CNN", None)
    result = x.download_item(tmp_path, "CNN", "2085896713185714235", "title")

    assert result == {"id": "2085896713185714235", "ok": True,
                      "published": "2026-08-08"}
    dest = tmp_path / "output" / "brand-intel" / "x" / "cnn" / "2085896713185714235.md"
    text = dest.read_text(encoding="utf-8")
    assert "post_id: '2085896713185714235'" in text
    assert "author: CNN" in text
    assert "published: '2026-08-08'" in text
    assert "like_count: 310" in text
    assert "comment_count: 85" in text
    assert "repost_count: 64" in text
    assert "view_count: 214564" in text
    assert "bookmark_count: 16" in text
    assert "quote_count: 6" in text
    assert "external_url: https://cnn.it/45aXVbJ" in text
    assert "https://pbs.twimg.com/media/HPKX_XjXUAAxkvS.jpg" in text
    assert "A daring mission" in text


def test_download_item_writes_empty_marker_for_media_only_posts(monkeypatch, tmp_path):
    """A media-only post is kept with the '(empty)' body Instagram and
    LinkedIn already use -- the media URLs and engagement counts are what
    make the file worth having."""
    _enumerate_with(monkeypatch, [_raw_row(
        id="1", description=None, photos=None,
        videos=[{"video_url": "https://video.twimg.com/a.mp4", "duration": 6041}])])
    x.enumerate_newest_first("CNN", None)
    x.download_item(tmp_path, "CNN", "1", "title")

    text = (tmp_path / "output" / "brand-intel" / "x" / "cnn" / "1.md").read_text(
        encoding="utf-8")
    assert "(empty)" in text
    assert "https://video.twimg.com/a.mp4" in text


def test_download_item_does_not_write_content_type(monkeypatch, tmp_path):
    """is_repost is unreliable, so no content_type is recorded. A key that
    always said 'post' would assert that the account never reposts."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)
    x.download_item(tmp_path, "CNN", "1", "title", content_type="post")
    text = (tmp_path / "output" / "brand-intel" / "x" / "cnn" / "1.md").read_text(
        encoding="utf-8")
    assert "content_type" not in text


def test_download_item_makes_no_second_network_call(monkeypatch, tmp_path):
    """Calling Bright Data once per item would double-pay for posts already
    collected by enumerate_newest_first."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("download_item must read the cache, not the API")

    monkeypatch.setattr(x, "_run_collection_job", _fail_if_called)
    monkeypatch.setattr(x, "_trigger_job", _fail_if_called)
    assert x.download_item(tmp_path, "CNN", "1", "title")["ok"] is True


def test_download_item_raises_on_cache_miss(monkeypatch, tmp_path):
    """A missing handle or id is a programming error. KeyError propagates to
    run_discovery's per-handle error path, surfacing as a normal 'error'
    rather than failing silently."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)
    with pytest.raises(KeyError):
        x.download_item(tmp_path, "CNN", "absent", "title")


def test_download_item_leaves_no_tmp_file(monkeypatch, tmp_path):
    """Write-temp-then-rename: an interrupted write must never leave a
    truncated file at a path on_disk_ids() would treat as captured."""
    _enumerate_with(monkeypatch, [_raw_row(id="1")])
    x.enumerate_newest_first("CNN", None)
    x.download_item(tmp_path, "CNN", "1", "title")
    directory = tmp_path / "output" / "brand-intel" / "x" / "cnn"
    assert [p.name for p in directory.iterdir()] == ["1.md"]


def test_max_items_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_MAX_ITEMS_X", "25")
    assert x.max_items() == 25
    monkeypatch.delenv("BRIGHTDATA_MAX_ITEMS_X")
    assert x.max_items() == x.MAX_ITEMS_PER_RUN == 10


def test_instagram_override_does_not_change_x(monkeypatch):
    """One knob per platform: raising Instagram's cap must not silently raise
    the spend on an account posting hundreds of times a day."""
    monkeypatch.setenv("BRIGHTDATA_MAX_ITEMS_INSTAGRAM", "50")
    assert x.max_items() == 10


def test_poll_timeout_s_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_POLL_TIMEOUT_X", "45")
    assert x.poll_timeout_s() == 45
    monkeypatch.delenv("BRIGHTDATA_POLL_TIMEOUT_X")
    assert x.poll_timeout_s() == x.POLL_TIMEOUT_S == 600
