import pytest

from pipeline_app import brightdata_job
from pipeline_app import discovery_linkedin as li


@pytest.fixture(autouse=True)
def _isolate_linkedin_state(monkeypatch, tmp_path):
    """F-67 + F-69, belt and braces with the repo-wide conftest guard (P0).
    Unlike the module adapters, LinkedInAdapter's enumerate cache is
    per-instance (self._cache) and profile_adapter()/company_adapter() hand
    back a fresh instance every call, so there is no module-global cache
    here to clear -- only the shared credential lookup and the diagnostics
    buffer/pending store that brightdata_job owns on every adapter's
    behalf. Points the pending store at tmp_path and makes sure no test can
    see the real BRIGHTDATA_API_KEY that is set in this machine's
    environment."""
    monkeypatch.delenv(li.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(li, "KEY_FILE", tmp_path / "no-brightdata_api_key.txt")
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    brightdata_job.reset_state()
    yield
    brightdata_job.reset_state()


def test_parse_published_accepts_the_verified_iso_format():
    """Live LinkedIn rows carry real ISO 8601 UTC -- 2026-07-08T14:00:09.491Z
    (verified 2026-08-07). Note this DIFFERS from the Instagram product, which
    returns a US-format local timestamp; the two Bright Data datasets do not
    agree, which is why neither may be assumed from the other."""
    assert li._parse_published("2026-07-08T14:00:09.491Z") == "2026-07-08"
    assert li._parse_published("2026-07-08") == "2026-07-08"


def test_parse_published_rejects_unusable_values():
    assert li._parse_published("") is None
    assert li._parse_published(None) is None
    assert li._parse_published("not a date") is None
    # A US-format date is NOT silently reinterpreted -- guessing between
    # MM/DD and DD/MM would produce wrong dates, which is worse than a
    # dropped row, and dropped rows are logged.
    assert li._parse_published("07/08/2026 14:00:09") is None


def test_preflight_reports_a_missing_key_once_without_calling_bright_data(monkeypatch, tmp_path):
    monkeypatch.delenv(li.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(li, "KEY_FILE", tmp_path / "absent.txt")

    def _fail_if_called(*a, **k):
        raise AssertionError("preflight must not touch the network")

    # discovery_linkedin has no module-level `requests` import -- its HTTP
    # calls all go through brightdata_job, so that is what must not be hit.
    monkeypatch.setattr(brightdata_job.requests, "post", _fail_if_called)
    for adapter in (li.profile_adapter(), li.company_adapter()):
        message = adapter.preflight()
        assert message is not None
        assert li.KEY_ENV_VAR in message
        assert adapter.platform in message


def test_preflight_returns_none_when_the_key_is_configured(monkeypatch, tmp_path):
    key_file = tmp_path / "brightdata_api_key.txt"
    key_file.write_text("k", encoding="utf-8")
    monkeypatch.delenv(li.KEY_ENV_VAR, raising=False)
    monkeypatch.setattr(li, "KEY_FILE", key_file)
    assert li.profile_adapter().preflight() is None
    assert li.company_adapter().preflight() is None


def test_run_collection_job_prefers_a_pending_snapshot_over_a_new_billed_job(monkeypatch, tmp_path):
    """Bright Data bills per record. If the previous run paid for a snapshot
    and timed out before collecting it, this run must take that data rather
    than pay again."""
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    brightdata_job.record_pending("linkedin-profile/somehandle", "snap-abc")
    person = li.profile_adapter()
    monkeypatch.setattr(person, "api_key", lambda: "test-key")

    def _fail_if_called(handle, key):
        raise AssertionError("must not trigger a new job while a snapshot is pending")

    monkeypatch.setattr(person, "_trigger_job", _fail_if_called)
    monkeypatch.setattr(person, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(person, "_fetch_job_results", lambda job_id, key: [{"id": "p1"}])
    assert person._run_collection_job("somehandle") == [{"id": "p1"}]


def test_profile_and_company_pending_snapshots_never_collide(monkeypatch, tmp_path):
    """A person and a company can share a slug. One pending entry must not
    serve the other mode -- the same reason the two adapters keep separate
    caches."""
    monkeypatch.setattr(brightdata_job, "PENDING_STORE_PATH", tmp_path / "pending.json")
    brightdata_job.record_pending("linkedin-profile/acme", "snap-person")
    person, company = li.profile_adapter(), li.company_adapter()
    monkeypatch.setattr(person, "api_key", lambda: "k")
    monkeypatch.setattr(company, "api_key", lambda: "k")
    monkeypatch.setattr(person, "_poll_job_status", lambda job_id, key: "ready")
    monkeypatch.setattr(person, "_fetch_job_results", lambda job_id, key: [{"id": "c1"}])

    def _fail_if_called(*a, **k):
        raise AssertionError("company mode must not see the profile snapshot")

    monkeypatch.setattr(company, "_poll_job_status", _fail_if_called)
    monkeypatch.setattr(company, "_trigger_job", lambda handle, key: "fresh")
    monkeypatch.setattr(company, "_fetch_job_results", lambda job_id, key: [])
    assert person._run_collection_job("acme") == [{"id": "c1"}]


def _raw_row(**overrides):
    """A row shaped like the live payload from snapshot sd_msizuwoz1sxczzt49."""
    row = {
        "id": "7480621754537701376",
        "date_posted": "2026-07-08T14:00:09.491Z",
        "post_type": "post",
        "account_type": "Person",
        "user_id": "bettywliu",
        "user_name": "Betty Liu",
        "headline": "Your personal brand isn't your resume.",
        "title": "#personalbrand #leadership #careeradvice | Betty Liu",
        "post_text": "Your personal brand isn't your resume.\n\nIt's what people say.",
        "original_post_text": "Your personal brand isn&apos;t your resume.",
        "post_text_html": "<a class=\"link\">markup</a>",
        "url": "https://www.linkedin.com/posts/bettywliu_personalbrand-activity-748",
        "num_likes": 74,
        "num_comments": 9,
        "hashtags": ["#personalbrand", "#leadership"],
    }
    row.update(overrides)
    return row


def test_normalize_row_maps_every_verified_field():
    n = li._normalize_row(_raw_row())
    assert n["id"] == "7480621754537701376"
    assert n["published"] == "2026-07-08"
    assert n["content_type"] == "post"
    assert n["account_type"] == "person"
    assert n["author"] == "bettywliu"
    assert n["like_count"] == 74
    assert n["comment_count"] == 9
    assert n["hashtags"] == ["#personalbrand", "#leadership"]


def test_normalize_row_body_comes_from_post_text_not_the_markup_fields():
    """post_text is the clean body -- entities decoded, links flattened.
    original_post_text and post_text_html are LONGER but carry &apos; and
    <a class="link"> markup. Reading the longer field would quietly fill the
    corpus with HTML for posts already paid for."""
    n = li._normalize_row(_raw_row())
    assert n["body"].startswith("Your personal brand isn't your resume.")
    assert "&apos;" not in n["body"]
    assert "<a" not in n["body"]


def test_normalize_row_title_prefers_headline_over_the_seo_title_field():
    """The `title` field is SEO text with hashtags and the author appended.
    `headline` is the post's own first line."""
    n = li._normalize_row(_raw_row())
    assert n["title"] == "Your personal brand isn't your resume."
    assert "#personalbrand" not in n["title"]


def test_normalize_row_title_falls_back_to_first_line_then_id():
    no_headline = li._normalize_row(_raw_row(headline="", post_text="First line.\nSecond line."))
    assert no_headline["title"] == "First line."
    nothing = li._normalize_row(_raw_row(headline="", post_text=""))
    assert nothing["title"] == "7480621754537701376"


def test_normalize_row_truncates_title_to_60_chars():
    n = li._normalize_row(_raw_row(headline="x" * 100))
    assert n["title"] == "x" * 60


def test_normalize_row_preserves_repost_as_a_content_type():
    """post_type='repost' was observed live alongside 'post'. It is a real
    value, not an error -- do not coerce it to 'post'."""
    assert li._normalize_row(_raw_row(post_type="repost"))["content_type"] == "repost"


def test_normalize_row_lowercases_content_type_and_account_type():
    n = li._normalize_row(_raw_row(post_type="Post", account_type="Organization"))
    assert n["content_type"] == "post"
    assert n["account_type"] == "organization"


def test_normalize_row_returns_none_without_id():
    assert li._normalize_row(_raw_row(id="")) is None


def test_normalize_row_returns_none_with_unusable_date():
    assert li._normalize_row(_raw_row(date_posted="")) is None
    assert li._normalize_row(_raw_row(date_posted="garbage")) is None


def test_normalize_row_tolerates_missing_optional_fields():
    n = li._normalize_row({"id": "1", "date_posted": "2026-07-08T00:00:00.000Z"})
    assert n["body"] == ""
    assert n["author"] == ""
    assert n["hashtags"] == []
    assert n["like_count"] is None
    assert n["content_type"] == "post"


import pytest

from pipeline_app import brightdata_job


def _profile():
    return li.profile_adapter()


def _company():
    return li.company_adapter()


def _row(post_id, date, author="bettywliu", text="hello", post_type="post"):
    return _raw_row(id=post_id, date_posted=f"{date}T00:00:00.000Z",
                    user_id=author, post_text=text, headline=text,
                    post_type=post_type)


def _stub_job(adapter, rows, monkeypatch):
    monkeypatch.setattr(adapter, "_run_collection_job", lambda handle: rows)


def test_profile_and_company_adapters_report_their_platform():
    assert _profile().platform == "linkedin-profile"
    assert _company().platform == "linkedin-company"


def test_profile_url_templates_differ_per_mode():
    assert _profile().profile_url("bettywliu") == "https://www.linkedin.com/in/bettywliu"
    assert _company().profile_url("lanieri") == "https://www.linkedin.com/company/lanieri"
    # A pasted @-prefixed handle still resolves.
    assert _profile().profile_url("@bettywliu") == "https://www.linkedin.com/in/bettywliu"


def test_trigger_job_sends_the_mode_specific_discovery_params(monkeypatch):
    captured = {}

    def fake_trigger(api_base, dataset_id, params, body, key):
        captured.update(api_base=api_base, dataset_id=dataset_id, params=params,
                        body=body, key=key)
        return "snap1"

    monkeypatch.setattr(brightdata_job, "trigger", fake_trigger)
    assert _profile()._trigger_job("bettywliu", "the-key") == "snap1"

    assert captured["dataset_id"] == li.DATASET_ID
    assert captured["params"]["type"] == "discover_new"
    assert captured["params"]["discover_by"] == "profile_url"
    # Server-side per-input record cap -- the primary cost control.
    assert captured["params"]["limit_per_input"] == li.MAX_ITEMS_PER_RUN
    assert captured["body"] == [{"url": "https://www.linkedin.com/in/bettywliu"}]


def test_trigger_job_uses_company_url_discovery_for_the_company_mode(monkeypatch):
    captured = {}

    def fake_trigger(api_base, dataset_id, params, body, key):
        captured.update(params=params, body=body)
        return "snap1"

    monkeypatch.setattr(brightdata_job, "trigger", fake_trigger)
    _company()._trigger_job("lanieri", "the-key")
    assert captured["params"]["discover_by"] == "company_url"
    assert captured["body"] == [{"url": "https://www.linkedin.com/company/lanieri"}]


def test_run_collection_job_raises_clear_error_when_key_missing(monkeypatch):
    adapter = _profile()
    monkeypatch.setattr(adapter, "api_key", lambda: None)
    with pytest.raises(RuntimeError, match="Bright Data API key not configured"):
        adapter._run_collection_job("bettywliu")


def test_run_collection_job_drives_full_trigger_poll_fetch_cycle(monkeypatch):
    """Nothing else exercises _run_collection_job's wiring of
    brightdata_job.trigger/poll_status/fetch_results into
    brightdata_job.await_results -- every other adapter test stubs
    _run_collection_job wholesale. A transposed callable or a wrong constant
    here would survive the whole suite and fail on the first live run, after
    paying for a job. Stub the shared brightdata_job boundary, never the
    network, and assert the snapshot id trigger() returns is what gets
    threaded through to poll_status() and fetch_results() -- the specific
    transposition this test exists to catch."""
    adapter = _profile()
    monkeypatch.setattr(adapter, "api_key", lambda: "the-key")

    poll_calls = []
    fetch_calls = []
    statuses = iter(["running", "ready"])

    def fake_trigger(api_base, dataset_id, params, body, key):
        return "snap-789"

    def fake_poll_status(api_base, job_id, key):
        poll_calls.append(job_id)
        return next(statuses)

    def fake_fetch_results(api_base, job_id, key):
        fetch_calls.append(job_id)
        return [{"id": "p1", "date_posted": "2026-07-08T00:00:00.000Z"}]

    monkeypatch.setattr(brightdata_job, "trigger", fake_trigger)
    monkeypatch.setattr(brightdata_job, "poll_status", fake_poll_status)
    monkeypatch.setattr(brightdata_job, "fetch_results", fake_fetch_results)
    monkeypatch.setattr(brightdata_job.time, "sleep", lambda s: None)

    result = adapter._run_collection_job("bettywliu")

    assert result == [{"id": "p1", "date_posted": "2026-07-08T00:00:00.000Z"}]
    assert poll_calls == ["snap-789", "snap-789"]
    assert fetch_calls == ["snap-789"]


def test_enumerate_propagates_job_timeout(monkeypatch):
    adapter = _profile()

    def raise_timeout(handle):
        raise brightdata_job.BrightDataJobTimeout("timed out")

    monkeypatch.setattr(adapter, "_run_collection_job", raise_timeout)
    with pytest.raises(brightdata_job.BrightDataJobTimeout):
        adapter.enumerate_newest_first("bettywliu", keyword_filter=None)


def test_profile_mode_drops_posts_written_by_other_people(monkeypatch, capsys):
    """VERIFIED LIVE: discover_by=profile_url returns the person's profile
    ACTIVITY, including posts authored by others. Querying /in/bettywliu
    returned a row authored by mattwilkerson. Without this filter those land
    in her folder and any downstream reader misattributes them."""
    adapter = _profile()
    _stub_job(adapter, [
        _row("own1", "2026-07-08", author="bettywliu"),
        _row("foreign", "2026-07-14", author="mattwilkerson"),
        _row("own2", "2026-07-03", author="bettywliu"),
    ], monkeypatch)

    items = adapter.enumerate_newest_first("bettywliu", keyword_filter=None)

    assert [i["id"] for i in items] == ["own1", "own2"]
    assert "other author" in capsys.readouterr().err


def test_profile_mode_author_match_is_case_insensitive_and_ignores_at_prefix(monkeypatch):
    adapter = _profile()
    _stub_job(adapter, [_row("p1", "2026-07-08", author="BettyWLiu")], monkeypatch)
    items = adapter.enumerate_newest_first("@bettywliu", keyword_filter=None)
    assert [i["id"] for i in items] == ["p1"]


def test_company_mode_does_not_filter_by_author(monkeypatch):
    """Company results were clean in live testing -- every row was authored by
    the queried org -- and a company's user_id need not equal its URL slug, so
    filtering here would risk discarding legitimate rows."""
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-04-01", author="lanieri-official")], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert [i["id"] for i in items] == ["c1"]


def test_enumerate_sorts_newest_first(monkeypatch):
    """VERIFIED LIVE: rows arrive unsorted (Jul 8, Jul 14, Jul 3). The engine's
    early-stop dedup assumes newest-first order."""
    adapter = _company()
    _stub_job(adapter, [
        _row("mid", "2026-07-08"), _row("new", "2026-07-14"), _row("old", "2026-07-03"),
    ], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert [i["id"] for i in items] == ["new", "mid", "old"]


def test_enumerate_sorts_same_day_rows_by_full_timestamp_not_arrival_order(monkeypatch):
    """date_posted is a full ISO 8601 timestamp, not just a date --
    'published' truncates to the date, so three same-day rows would come
    back in Bright Data's arbitrary arrival order under a date-only sort.
    Feed them out of BOTH arrival order and time order so a date-only (or
    absent) sort would fail this test."""
    adapter = _company()
    _stub_job(adapter, [
        _raw_row(id="mid", date_posted="2026-07-08T14:00:00.000Z"),
        _raw_row(id="early", date_posted="2026-07-08T08:00:00.000Z"),
        _raw_row(id="late", date_posted="2026-07-08T20:00:00.000Z"),
    ], monkeypatch)

    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)

    assert [i["id"] for i in items] == ["late", "mid", "early"]
    assert {i["published"] for i in items} == {"2026-07-08"}


def test_enumerate_caps_at_max_items_per_run(monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row(f"p{i}", "2026-07-08") for i in range(25)], monkeypatch)
    monkeypatch.setattr(li, "MAX_ITEMS_PER_RUN", 10)
    assert len(adapter.enumerate_newest_first("lanieri", keyword_filter=None)) == 10


def test_full_cap_batch_records_a_saturation_error(monkeypatch):
    """Fault test. Ten of ten means posts were dropped that no later run can
    fetch -- the handle still reports 'ok', so this must be reported here."""
    adapter = _company()
    _stub_job(adapter, [_row(f"p{i}", "2026-07-08") for i in range(10)], monkeypatch)
    brightdata_job.drain_diagnostics()
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    saturation = [d for d in brightdata_job.drain_diagnostics()
                  if d["kind"] == "adapter.batch_saturated"]
    assert len(saturation) == 1
    assert saturation[0]["severity"] == "error"


def test_a_short_batch_records_no_saturation_diagnostic(monkeypatch):
    """Distinguishability. Nine of ten is a quiet account; ten of ten is
    truncation. The two must be observably different."""
    adapter = _company()
    _stub_job(adapter, [_row(f"p{i}", "2026-07-08") for i in range(9)], monkeypatch)
    brightdata_job.drain_diagnostics()
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert [d for d in brightdata_job.drain_diagnostics()
            if d["kind"] == "adapter.batch_saturated"] == []


def test_saturation_diagnostic_names_the_cap_the_override_and_the_lost_window(monkeypatch):
    """Surfacing. The record must be actionable on its own: an operator
    reading it in the log or the events table must know what to change. Uses
    the profile adapter -- self.platform, not a shared PLATFORM constant, is
    what LinkedIn must report, since linkedin-profile and linkedin-company
    share this same module."""
    adapter = _profile()
    _stub_job(adapter, [_row(f"p{i}", "2026-07-08") for i in range(10)], monkeypatch)
    brightdata_job.drain_diagnostics()
    adapter.enumerate_newest_first("bettywliu", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.batch_saturated"][0]
    assert record["detail"]["cap"] == 10
    assert record["detail"]["handle"] == "bettywliu"
    assert record["detail"]["platform"] == "linkedin-profile"
    assert record["detail"]["raw_count"] == 10
    assert li.MAX_ITEMS_ENV_VAR in record["message"]
    assert "no backfill" in record["message"]


def test_dropped_rows_reach_a_durable_surface_not_only_stderr(monkeypatch, capsys):
    """Fault test. The Scheduled Task command has no redirection, so a stderr
    warning on the production path has no destination at all (B-01)."""
    adapter = _company()
    _stub_job(adapter, [_row("good", "2026-07-08"), {"post_text": "no id"}], monkeypatch)
    brightdata_job.drain_diagnostics()
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.rows_dropped"][0]
    assert record["severity"] == "warning"
    assert record["detail"]["dropped"] == 1
    assert record["source"] == "discovery_linkedin"
    assert "dropped 1 unusable row(s)" in capsys.readouterr().err   # the print stays


def test_foreign_author_rows_reach_a_durable_surface_not_only_stderr(monkeypatch, capsys):
    """Fault test, the foreign-author case: profile mode filters posts
    written by other people and today only unusable rows reach a durable
    surface -- this must be true for the foreign-author drop too."""
    adapter = _profile()
    _stub_job(adapter, [
        _row("own1", "2026-07-08", author="bettywliu"),
        _row("foreign", "2026-07-14", author="mattwilkerson"),
    ], monkeypatch)
    brightdata_job.drain_diagnostics()
    adapter.enumerate_newest_first("bettywliu", keyword_filter=None)
    record = [d for d in brightdata_job.drain_diagnostics()
              if d["kind"] == "adapter.foreign_rows_dropped"][0]
    assert record["severity"] == "warning"
    assert record["detail"]["dropped"] == 1
    assert record["source"] == "discovery_linkedin"
    assert "dropped 1 row(s) by another author" in capsys.readouterr().err


def test_a_clean_batch_produces_no_diagnostics_at_all(monkeypatch):
    """Distinguishability. A degraded run must be observably different from a
    healthy one -- 'no diagnostics' is the healthy signal."""
    adapter = _company()
    _stub_job(adapter, [_row("good", "2026-07-08")], monkeypatch)
    brightdata_job.drain_diagnostics()
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert brightdata_job.drain_diagnostics() == []


def test_diagnostics_carry_everything_obs_record_event_requires(monkeypatch):
    """Surfacing. P8 writes these straight into the events table; a record
    missing a column is a record that never becomes a row."""
    adapter = _profile()
    _stub_job(adapter, [
        _row("own1", "2026-07-08", author="bettywliu"),
        {"post_text": "no id"},
        _row("foreign", "2026-07-14", author="mattwilkerson"),
    ], monkeypatch)
    brightdata_job.drain_diagnostics()
    adapter.enumerate_newest_first("bettywliu", keyword_filter=None)
    records = brightdata_job.drain_diagnostics()
    assert records
    for record in records:
        assert set(record) == {"kind", "severity", "source", "message", "detail"}
        assert record["severity"] in {"info", "warning", "error", "critical"}
        assert record["message"]


def test_enumerate_drops_unusable_rows_and_logs(monkeypatch, capsys):
    adapter = _company()
    _stub_job(adapter, [
        _row("good", "2026-07-08"),
        {"post_text": "no id"},
        {"id": "no_date", "post_text": "x", "date_posted": ""},
    ], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert [i["id"] for i in items] == ["good"]
    assert "unusable" in capsys.readouterr().err


def test_enumerate_drop_log_reports_both_counts_when_both_are_nonzero(monkeypatch, capsys):
    """When a batch has both unusable rows and foreign-author rows, the
    combined wording from before this fix wave must still appear -- only the
    zero-count case changes."""
    adapter = _profile()
    _stub_job(adapter, [
        _row("own", "2026-07-08", author="bettywliu"),
        _row("foreign", "2026-07-08", author="someone-else"),
        {"post_text": "no id"},
    ], monkeypatch)
    adapter.enumerate_newest_first("bettywliu", keyword_filter=None)
    err = capsys.readouterr().err
    assert "unusable" in err
    assert "other author" in err


def test_enumerate_all_filtered_warning_points_at_handle_when_rows_were_unusable(monkeypatch, capsys):
    """Regression for the fix-wave finding: with include_errors=true, a dead
    or renamed slug returns error rows with no id, which normalize to None.
    Before this fix, the all-filtered warning always said 'check whether
    this account posts its own content' even when every drop was unusable
    (not foreign-authored), pointing the operator at the wrong cause."""
    adapter = _company()
    _stub_job(adapter, [
        {"post_text": "no id"},
        {"id": "no_date", "post_text": "x", "date_posted": ""},
    ], monkeypatch)
    assert adapter.enumerate_newest_first("lanieri", keyword_filter=None) == []
    err = capsys.readouterr().err
    assert "none survived" in err
    assert "billed" in err
    assert "posts its own content" not in err
    assert "handle" in err


def test_enumerate_warns_loudly_when_rows_returned_but_none_survive(monkeypatch, capsys):
    """The silent-failure door the author filter opens: a billed job returns
    rows, the filter drops them all, enumerate returns [], and process_handle
    records the HEALTHY status 'no_new_content'. Returning [] is correct --
    it can happen legitimately -- but it must be loud in the log."""
    adapter = _profile()
    _stub_job(adapter, [
        _row("f1", "2026-07-08", author="someone-else"),
        _row("f2", "2026-07-09", author="another-person"),
    ], monkeypatch)

    assert adapter.enumerate_newest_first("bettywliu", keyword_filter=None) == []
    err = capsys.readouterr().err
    assert "none survived" in err
    assert "billed" in err


def test_enumerate_does_not_warn_when_the_job_genuinely_returned_nothing(monkeypatch, capsys):
    adapter = _company()
    _stub_job(adapter, [], monkeypatch)
    assert adapter.enumerate_newest_first("lanieri", keyword_filter=None) == []
    assert "none survived" not in capsys.readouterr().err


def test_enumerate_applies_keyword_filter_to_post_text(monkeypatch):
    adapter = _company()
    _stub_job(adapter, [
        _row("a", "2026-07-08", text="talks about gardens"),
        _row("b", "2026-07-08", text="talks about cars"),
    ], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter="GARDEN")
    assert [i["id"] for i in items] == ["a"]


def test_enumerate_returns_only_the_engine_facing_keys(monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08")], monkeypatch)
    items = adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert set(items[0]) == {"id", "title", "published", "content_type"}


def test_enumerate_populates_the_cache_before_the_keyword_filter(monkeypatch):
    """download_item reads the cache, and process_handle only ever asks for
    ids enumerate returned -- but caching the pre-filter batch matches the
    Instagram adapter and costs nothing."""
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08", text="full body text")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter="nomatch")
    assert adapter.cached_row("lanieri", "c1")["body"] == "full body text"


def test_enumerate_overwrites_a_previous_cache_entry(monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row("old_batch", "2026-07-01")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    _stub_job(adapter, [_row("new_batch", "2026-08-01")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    assert adapter.cached_ids("lanieri") == {"new_batch"}


def test_two_adapters_sharing_a_handle_slug_do_not_share_cache(monkeypatch):
    """A person and a company can have the same slug. A module-level cache
    keyed by handle alone would let one mode's batch serve the other's
    download_item."""
    person, company = _profile(), _company()
    _stub_job(person, [_row("person_post", "2026-07-08", author="acme")], monkeypatch)
    _stub_job(company, [_row("company_post", "2026-07-08", author="acme")], monkeypatch)

    person.enumerate_newest_first("acme", keyword_filter=None)
    company.enumerate_newest_first("acme", keyword_filter=None)

    assert person.cached_ids("acme") == {"person_post"}
    assert company.cached_ids("acme") == {"company_post"}


def test_on_disk_ids_empty_when_directory_missing(tmp_path):
    assert _profile().on_disk_ids(tmp_path, "bettywliu") == set()


def test_on_disk_ids_reads_stems_of_md_files(tmp_path):
    out_dir = tmp_path / "output" / "brand-intel" / "linkedin-profile" / "bettywliu"
    out_dir.mkdir(parents=True)
    (out_dir / "p1.md").write_text("x", encoding="utf-8")
    (out_dir / "p2.md").write_text("x", encoding="utf-8")
    assert _profile().on_disk_ids(tmp_path, "bettywliu") == {"p1", "p2"}


def test_on_disk_ids_is_scoped_per_platform(tmp_path):
    """A person and a company sharing a slug must not see each other's files."""
    person_dir = tmp_path / "output" / "brand-intel" / "linkedin-profile" / "acme"
    person_dir.mkdir(parents=True)
    (person_dir / "person_post.md").write_text("x", encoding="utf-8")
    assert _profile().on_disk_ids(tmp_path, "acme") == {"person_post"}
    assert _company().on_disk_ids(tmp_path, "acme") == set()


def test_peek_upload_date_always_none():
    assert _profile().peek_upload_date("anything") is None


def test_download_item_writes_frontmatter_and_body_from_cache(tmp_path, monkeypatch):
    adapter = _profile()
    _stub_job(adapter, [_row("p1", "2026-07-08", author="bettywliu",
                             text="the body text")], monkeypatch)
    adapter.enumerate_newest_first("bettywliu", keyword_filter=None)

    result = adapter.download_item(tmp_path, "bettywliu", "p1", "the body text",
                                   content_type="post")

    assert result == {"id": "p1", "ok": True, "published": "2026-07-08"}
    out_path = (tmp_path / "output" / "brand-intel" / "linkedin-profile"
                / "bettywliu" / "p1.md")
    text = out_path.read_text(encoding="utf-8")
    assert "post_id: p1" in text
    assert "author: bettywliu" in text
    assert "account_type: person" in text
    assert "content_type: post" in text
    # yaml.safe_dump quotes date-like strings -- this is NOT bare 2026-07-08.
    assert "published: '2026-07-08'" in text
    assert "the body text" in text
    # write-temp-then-rename must leave no partial file behind
    assert not out_path.with_name("p1.md.tmp").exists()


def test_download_item_records_engagement_and_hashtags(tmp_path, monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_raw_row(id="c1", date_posted="2026-04-01T00:00:00.000Z",
                                 num_likes=18, num_comments=0,
                                 hashtags=["#wool", "#tailoring"])], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    adapter.download_item(tmp_path, "lanieri", "c1", "t")

    text = (tmp_path / "output" / "brand-intel" / "linkedin-company" / "lanieri"
            / "c1.md").read_text(encoding="utf-8")
    assert "like_count: 18" in text
    assert "comment_count: 0" in text
    assert "- '#wool'" in text


def test_download_item_empty_body_writes_placeholder(tmp_path, monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08", text="")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    adapter.download_item(tmp_path, "lanieri", "c1", "c1")
    out = tmp_path / "output" / "brand-intel" / "linkedin-company" / "lanieri" / "c1.md"
    assert "(empty)" in out.read_text(encoding="utf-8")


def test_download_item_raises_on_cache_miss(tmp_path, monkeypatch):
    """A missing id is a programming error, not a degraded write. KeyError
    propagates to run_discovery's per-handle handler and is recorded as a
    normal 'error' -- safe-fail rather than an empty file that on_disk_ids
    would then treat as captured."""
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)
    with pytest.raises(KeyError):
        adapter.download_item(tmp_path, "lanieri", "not_in_cache", "title")


def test_download_item_makes_no_network_call(tmp_path, monkeypatch):
    adapter = _company()
    _stub_job(adapter, [_row("c1", "2026-07-08")], monkeypatch)
    adapter.enumerate_newest_first("lanieri", keyword_filter=None)

    def _fail(*args, **kwargs):
        raise AssertionError("download_item must read the cache, not re-collect")

    monkeypatch.setattr(adapter, "_run_collection_job", _fail)
    monkeypatch.setattr(brightdata_job, "trigger", _fail)
    assert adapter.download_item(tmp_path, "lanieri", "c1", "t")["ok"] is True


def test_max_items_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_MAX_ITEMS_LINKEDIN", "25")
    assert li.max_items() == 25
    monkeypatch.delenv("BRIGHTDATA_MAX_ITEMS_LINKEDIN")
    assert li.max_items() == li.MAX_ITEMS_PER_RUN == 10


def test_poll_timeout_s_honours_the_per_platform_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_POLL_TIMEOUT_LINKEDIN", "45")
    assert li.poll_timeout_s() == 45
    monkeypatch.delenv("BRIGHTDATA_POLL_TIMEOUT_LINKEDIN")
    assert li.poll_timeout_s() == li.POLL_TIMEOUT_S == 300
