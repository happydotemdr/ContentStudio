import json
from pathlib import Path

import pytest

from pipeline_app import discovery_bluesky as bsky


def _post(rkey: str, day: str, text: str = "hello") -> dict:
    return {"post": {"uri": f"at://did/app.bsky.feed.post/{rkey}",
                     "record": {"text": text, "createdAt": f"{day}T10:00:00Z"}}}


@pytest.fixture
def logged(monkeypatch):
    """Captures every bsky.obs.log() call this test makes, as a list of dicts.

    Each record is {"event": ..., "level": ..., **fields} -- the same shape
    obs.log() takes, minus the timestamp obs.log() would otherwise stamp.
    """
    records: list[dict] = []

    def fake_log(event, *, level="info", **fields):
        records.append({"event": event, "level": level, **fields})

    monkeypatch.setattr(bsky.obs, "log", fake_log)
    return records


def test_on_disk_ids_matches_bare_rkey_filename(tmp_path: Path):
    # Matches Task 6's slugify behavior: dots are stripped, not hyphenated.
    handle_dir = tmp_path / "output" / "brand-intel" / "bluesky" / "adamgrantbskysocial"
    handle_dir.mkdir(parents=True)
    (handle_dir / "3abc123.md").write_text("x", encoding="utf-8")
    assert bsky.on_disk_ids(tmp_path, "adamgrant.bsky.social") == {"3abc123"}


def test_enumerate_newest_first_paginates_and_populates_published(monkeypatch):
    pages = [
        {
            "feed": [
                {"post": {"uri": "at://did/app.bsky.feed.post/rkey1",
                          "record": {"text": "first post", "createdAt": "2026-07-29T10:00:00Z"}}},
            ],
            "cursor": "page2",
        },
        {
            "feed": [
                {"post": {"uri": "at://did/app.bsky.feed.post/rkey2",
                          "record": {"text": "second post", "createdAt": "2026-07-20T10:00:00Z"}}},
            ],
        },
    ]
    call_count = {"n": 0}

    def fake_http_get(url):
        page = pages[call_count["n"]]
        call_count["n"] += 1
        return json.dumps(page).encode("utf-8")

    monkeypatch.setattr(bsky, "_http_get", fake_http_get)
    items = bsky.enumerate_newest_first("adamgrant.bsky.social", keyword_filter=None)
    assert [i["id"] for i in items] == ["rkey1", "rkey2"]
    assert items[0]["published"] == "2026-07-29"
    assert items[1]["published"] == "2026-07-20"


def test_enumerate_newest_first_skips_reposts(monkeypatch):
    page = {"feed": [
        {"reason": {"$type": "app.bsky.feed.defs#reasonRepost"},
         "post": {"uri": "at://did/app.bsky.feed.post/repost1", "record": {"text": "x", "createdAt": "2026-07-29T10:00:00Z"}}},
        {"post": {"uri": "at://did/app.bsky.feed.post/real1", "record": {"text": "y", "createdAt": "2026-07-28T10:00:00Z"}}},
    ]}
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(page).encode("utf-8"))
    items = bsky.enumerate_newest_first("adamgrant.bsky.social", keyword_filter=None)
    assert [i["id"] for i in items] == ["real1"]


def test_enumerate_newest_first_raises_on_fetch_failure(monkeypatch):
    """Inverts the test that used to live here.

    brightdata_job.py:6-10 states the invariant for every adapter: a failed
    fetch MUST raise, never return []. The old test asserted the opposite and
    froze B-05 and B-06 in place -- B-06 permanently disables a valid handle
    after one momentary outage.
    """
    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(bsky, "_http_get", raise_error)
    with pytest.raises(bsky.BlueskyFetchError) as exc:
        bsky.enumerate_newest_first("dead.bsky.social", keyword_filter=None)
    assert "dead.bsky.social" in str(exc.value)


def test_a_fetch_failure_is_distinguishable_from_an_empty_feed(monkeypatch):
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps({"feed": []}).encode("utf-8"))
    assert bsky.enumerate_newest_first("quiet.bsky.social", keyword_filter=None) == []

    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(bsky, "_http_get", raise_error)
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("quiet.bsky.social", keyword_filter=None)


def test_a_fetch_failure_is_surfaced_as_a_structured_error_event(monkeypatch, logged):
    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(bsky, "_http_get", raise_error)
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("dead.bsky.social", keyword_filter=None)
    (record,) = [r for r in logged if r["event"] == "adapter.enumerate_failed"]
    assert record["level"] == "error" and record["platform"] == "bluesky"
    assert record["handle"] == "dead.bsky.social" and record["error"] == "OSError"


def test_malformed_json_raises_rather_than_reporting_an_empty_feed(monkeypatch):
    monkeypatch.setattr(bsky, "_http_get", lambda url: b"{not json")
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("x.bsky.social", keyword_filter=None)


@pytest.mark.parametrize("payload", [None, []])
def test_valid_json_with_wrong_top_level_shape_raises_rather_than_an_attributeerror(monkeypatch, payload):
    # Syntactically valid JSON (json.loads succeeds) but not the expected
    # {"feed": [...]} object shape -- e.g. the API returning `null` or a bare
    # list. Without validating the shape, `data.get("feed")` raises a raw,
    # undocumented AttributeError instead of the documented BlueskyFetchError.
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(payload).encode("utf-8"))
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("x.bsky.social", keyword_filter=None)


def test_download_item_writes_full_text_not_truncated_title(tmp_path, monkeypatch):
    # enumerate_newest_first truncates "title" to 60 chars for filtering/display,
    # but download_item must write the FULL post text to the .md body.
    long_text = "This is a much longer bluesky post body than sixty characters, well past the truncation point. " * 2
    assert len(long_text) > 60
    page = {
        "feed": [
            {"post": {"uri": "at://did/app.bsky.feed.post/target_rkey",
                      "record": {"text": long_text, "createdAt": "2026-07-29T10:00:00Z"}}},
        ]
    }
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(page).encode("utf-8"))

    result = bsky.download_item(tmp_path, "adamgrant.bsky.social", "target_rkey", long_text[:60])

    assert result["ok"] is True
    out_dir = tmp_path / "output" / "brand-intel" / "bluesky" / "adamgrantbskysocial"
    body = (out_dir / "target_rkey.md").read_text(encoding="utf-8")
    assert long_text.strip() in body
    assert long_text.strip() != long_text[:60]


def test_download_item_returns_ok_false_when_refetch_finds_no_match(tmp_path, monkeypatch):
    # When re-fetch returns a feed that doesn't contain the target rkey
    # (aged out of page_limit=5, network error swallowed by enumerate, etc.),
    # download_item must NOT write a degraded .md file and must return ok=False.
    from pipeline_app.discovery_paths import handle_dir

    bsky.clear_feed_cache()
    page = {
        "feed": [
            {"post": {"uri": "at://did/app.bsky.feed.post/other_rkey1",
                      "record": {"text": "some other post", "createdAt": "2026-07-29T10:00:00Z"}}},
            {"post": {"uri": "at://did/app.bsky.feed.post/other_rkey2",
                      "record": {"text": "another post", "createdAt": "2026-07-28T10:00:00Z"}}},
        ]
    }
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(page).encode("utf-8"))

    result = bsky.download_item(tmp_path, "adamgrant.bsky.social", "target_rkey", "some title")

    # Expect failure
    assert result == {"id": "target_rkey", "ok": False, "published": None,
                       "reason": "not-found-in-feed"}

    # Verify no .md file was written
    out_dir = handle_dir(tmp_path, "bluesky", "adamgrant.bsky.social")
    assert not (out_dir / "target_rkey.md").exists()
    # Also check no temp file lingering
    assert not (out_dir / "target_rkey.md.tmp").exists()


def test_download_item_reuses_the_enumerate_walk(monkeypatch, tmp_path):
    """Downloading N posts cost up to 5(N+1) requests against a public
    unauthenticated endpoint -- 55 round-trips for 10 posts (B-07)."""
    bsky.clear_feed_cache()
    calls = {"n": 0}
    feed = {"feed": [_post(f"rkey{i}", "2026-07-29") for i in range(3)]}

    def counting(url):
        calls["n"] += 1
        return json.dumps(feed).encode("utf-8")

    monkeypatch.setattr(bsky, "_http_get", counting)
    bsky.enumerate_newest_first("x.bsky.social", None)
    before = calls["n"]
    for i in range(3):
        bsky.download_item(tmp_path, "x.bsky.social", f"rkey{i}", "t")
    assert calls["n"] == before, "download_item must not re-walk the feed"


def test_download_item_reports_a_reason_when_the_item_is_not_found(monkeypatch, tmp_path, logged):
    bsky.clear_feed_cache()
    monkeypatch.setattr(bsky, "_http_get",
                        lambda url: json.dumps({"feed": [_post("other", "2026-07-29")]}).encode("utf-8"))
    bsky.enumerate_newest_first("x.bsky.social", None)
    result = bsky.download_item(tmp_path, "x.bsky.social", "target", "t")
    assert result["ok"] is False
    assert result["reason"] == "not-found-in-feed"
    assert [r for r in logged if r["event"] == "adapter.item_not_found"]


def test_download_item_propagates_a_transport_failure_rather_than_reporting_not_found(
        monkeypatch, tmp_path):
    """A cache miss falls back to one re-fetch. If THAT fails, it is a failure,
    not an aged-out item."""
    bsky.clear_feed_cache()

    def raise_error(url):
        raise OSError("network down")

    monkeypatch.setattr(bsky, "_http_get", raise_error)
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.download_item(tmp_path, "x.bsky.social", "target", "t")


def test_the_cache_holds_unfiltered_rows(monkeypatch, tmp_path):
    """A keyword-filtered enumerate must still be able to serve a download of
    any row it saw, or the filter silently breaks the download path."""
    bsky.clear_feed_cache()
    feed = {"feed": [_post("a", "2026-07-29", "permaculture"), _post("b", "2026-07-28", "other")]}
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(feed).encode("utf-8"))
    bsky.enumerate_newest_first("x.bsky.social", keyword_filter="permaculture")
    assert bsky._FEED_CACHE["x.bsky.social"].keys() == {"a", "b"}


def test_download_item_writes_parseable_frontmatter(tmp_path, monkeypatch):
    from pipeline_app import artifacts, discovery_bluesky
    from pipeline_app.discovery_paths import handle_dir

    monkeypatch.setattr(
        discovery_bluesky, "enumerate_newest_first",
        lambda handle, keyword_filter=None, page_limit=5: [
            {"id": "abc123", "title": "Hello there", "text": "Hello there, full post text.",
             "published": "2026-08-01"}
        ],
    )

    result = discovery_bluesky.download_item(tmp_path, "someone.bsky.social", "abc123", "Hello there")

    assert result["ok"] is True
    dest = handle_dir(tmp_path, "bluesky", "someone.bsky.social") / "abc123.md"
    meta, body = artifacts.parse_frontmatter(dest.read_text(encoding="utf-8"))
    assert meta["post_id"] == "abc123"
    assert meta["url"] == "https://bsky.app/profile/someone.bsky.social/post/abc123"
    assert meta["handle"] == "someone.bsky.social"
    assert meta["author"] == "someone.bsky.social"
    assert meta["published"] == "2026-08-01"
    assert isinstance(meta["fetched_at"], str)
    assert meta["fetched_at"].endswith("+00:00")
    assert body.strip() == "Hello there, full post text."


def test_a_failure_mid_pagination_raises_rather_than_truncating_the_walk(monkeypatch):
    """A failure on page 3 of 5 used to return pages 1-2 as if the walk had
    completed, silently shortening a new handle's 90-day lookback."""
    pages = [
        {"feed": [_post("rkey1", "2026-07-29")], "cursor": "p2"},
        {"feed": [_post("rkey2", "2026-07-28")], "cursor": "p3"},
    ]
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        if calls["n"] > len(pages):
            raise TimeoutError("appview timeout")
        return json.dumps(pages[calls["n"] - 1]).encode("utf-8")

    monkeypatch.setattr(bsky, "_http_get", flaky)
    with pytest.raises(bsky.BlueskyFetchError) as exc:
        bsky.enumerate_newest_first("x.bsky.social", keyword_filter=None)
    assert "page 3" in str(exc.value)


def test_a_complete_short_walk_is_not_a_failure(monkeypatch):
    """Distinguishability: a feed that runs out of cursor before page_limit is
    a completed walk, and must still return normally."""
    pages = [{"feed": [_post("rkey1", "2026-07-29")]}]
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(pages[0]).encode("utf-8"))
    assert [i["id"] for i in bsky.enumerate_newest_first("x.bsky.social", None)] == ["rkey1"]


def test_validate_shaped_call_raises_on_a_transient_failure(monkeypatch):
    """process_handle_validate treats an empty enumerate as ok:False and
    run_discovery then sets status='invalid' AND included=False, permanently,
    with nothing ever retrying it. A blip must therefore never look empty."""
    def blip(url):
        raise ConnectionResetError("reset by peer")

    monkeypatch.setattr(bsky, "_http_get", blip)
    with pytest.raises(bsky.BlueskyFetchError):
        bsky.enumerate_newest_first("valid.bsky.social", keyword_filter=None, page_limit=1)


def test_a_genuinely_nonexistent_actor_still_returns_empty(monkeypatch):
    """The legitimate invalid-handle case the auto-exclude exists for: the
    AppView answers, with an empty feed. This must NOT raise, or a real typo
    would be recorded as an infrastructure error."""
    monkeypatch.setattr(bsky, "_http_get",
                        lambda url: json.dumps({"feed": []}).encode("utf-8"))
    assert bsky.enumerate_newest_first("typo.bsky.social", keyword_filter=None) == []


def test_the_two_validate_outcomes_have_different_types(monkeypatch):
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps({"feed": []}).encode("utf-8"))
    empty = bsky.enumerate_newest_first("typo.bsky.social", None)

    def blip(url):
        raise ConnectionResetError("reset by peer")

    monkeypatch.setattr(bsky, "_http_get", blip)
    with pytest.raises(bsky.BlueskyFetchError) as exc:
        bsky.enumerate_newest_first("valid.bsky.social", None)
    assert empty == [] and isinstance(exc.value, bsky.BlueskyFetchError)


def test_keyword_filter_matches_beyond_the_first_sixty_characters(monkeypatch):
    """`title` is text[:60] for display; every other text-bearing adapter
    filters the full body. A keyword past character 60 was silently
    non-matching, producing a quietly under-populated capture (B-08)."""
    long_text = ("x" * 90) + " permaculture"
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(
        {"feed": [_post("rkey1", "2026-07-29", long_text)]}).encode("utf-8"))
    items = bsky.enumerate_newest_first("x.bsky.social", keyword_filter="permaculture")
    assert [i["id"] for i in items] == ["rkey1"]


def test_keyword_filter_still_excludes_a_genuine_non_match(monkeypatch):
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(
        {"feed": [_post("rkey1", "2026-07-29", "nothing relevant here")]}).encode("utf-8"))
    assert bsky.enumerate_newest_first("x.bsky.social", keyword_filter="permaculture") == []


def test_a_row_with_no_usable_created_at_is_dropped(monkeypatch, logged):
    """peek_upload_date's comment claims enumerate always populates
    'published'. It did not: a short/absent createdAt yielded None, and for a
    new handle five of those in a row aborted the whole walk with a healthy
    status. The Bright Data adapters drop such rows in _normalize_row; match
    them, and report the drop (B-09)."""
    feed = {"feed": [
        _post("good", "2026-07-29"),
        {"post": {"uri": "at://did/app.bsky.feed.post/bad", "record": {"text": "t", "createdAt": "2026"}}},
        {"post": {"uri": "at://did/app.bsky.feed.post/none", "record": {"text": "t"}}},
    ]}
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(feed).encode("utf-8"))
    items = bsky.enumerate_newest_first("x.bsky.social", None)
    assert [i["id"] for i in items] == ["good"]
    assert all(i["published"] for i in items)
    (record,) = [r for r in logged if r["event"] == "adapter.undated_rows_dropped"]
    assert record["level"] == "warning" and record["count"] == 2


def test_indexed_at_is_accepted_when_created_at_is_absent(monkeypatch):
    feed = {"feed": [{"post": {"uri": "at://did/app.bsky.feed.post/i1",
                               "indexedAt": "2026-07-29T10:00:00Z",
                               "record": {"text": "t"}}}]}
    monkeypatch.setattr(bsky, "_http_get", lambda url: json.dumps(feed).encode("utf-8"))
    assert bsky.enumerate_newest_first("x.bsky.social", None)[0]["published"] == "2026-07-29"
