import json
from pathlib import Path

from pipeline_app import discovery_bluesky as bsky


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


def test_enumerate_newest_first_returns_empty_on_fetch_failure(monkeypatch):
    def raise_error(url):
        raise OSError("network down")
    monkeypatch.setattr(bsky, "_http_get", raise_error)
    assert bsky.enumerate_newest_first("dead.bsky.social", keyword_filter=None) == []


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
