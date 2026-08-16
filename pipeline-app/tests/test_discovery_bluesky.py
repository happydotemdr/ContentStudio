import json
from pathlib import Path

import pytest

from pipeline_app import discovery_bluesky as bsky


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
    assert result == {"id": "target_rkey", "ok": False, "published": None}

    # Verify no .md file was written
    out_dir = tmp_path / "output" / "brand-intel" / "bluesky" / "adamgrant.bsky.social"
    assert not (out_dir / "target_rkey.md").exists()
    # Also check no temp file lingering
    assert not (out_dir / "target_rkey.md.tmp").exists()


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
