"""Bluesky platform adapter for the discovery engine. Isolates the public
AppView HTTP call so discovery_engine's core algorithm (Task 9) can be
unit-tested with no network access. Download logic ported from
download_brandintel.py's do_bluesky (that script stays unmodified)."""
from __future__ import annotations

import datetime as _dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from pipeline_app import artifacts, obs
from pipeline_app.discovery_paths import handle_dir

BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
USER_AGENT = "ContentStudio-discovery-engine/1.0 (personal archival; local inspection)"


class BlueskyFetchError(RuntimeError):
    """A getAuthorFeed page could not be fetched or parsed.

    The bare `except Exception: break` this replaces made DNS failure,
    connection reset, HTTP error, timeout and malformed JSON produce the same
    [] a genuinely quiet account produces -- which discovery_engine records as
    the healthy 'no_new_content', and which process_handle_validate turns into
    a permanent status='invalid', included=False for a perfectly good handle
    (B-05, B-06). brightdata_job.py:6-10 states the invariant this restores.
    """


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# Normalized rows from the last enumerate, keyed by handle then rkey. Matches
# the pattern all four Bright Data adapters already use: enumerate pays for
# the walk once and download_item reads from it, instead of re-walking the
# whole 5-page feed per item (B-07). Populated BEFORE keyword filtering so a
# filtered enumerate can still serve any row it saw.
_FEED_CACHE: dict[str, dict[str, dict]] = {}


def clear_feed_cache(handle: str | None = None) -> None:
    _FEED_CACHE.clear() if handle is None else _FEED_CACHE.pop(handle, None)


def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    directory = handle_dir(repo_root, "bluesky", handle)
    if not directory.exists():
        return set()
    return {p.stem for p in directory.glob("*.md")}


def enumerate_newest_first(handle: str, keyword_filter: str | None, page_limit: int = 5) -> list[dict]:
    items: list[dict] = []
    cursor = None
    undated = 0
    for page_index in range(page_limit):
        params = {"actor": handle, "limit": "100"}
        if cursor:
            params["cursor"] = cursor
        try:
            raw = _http_get(f"{BLUESKY_API}?{urllib.parse.urlencode(params)}")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError(f"expected a JSON object, got {type(data).__name__}")
            feed = data.get("feed") or []
        except Exception as exc:  # noqa: BLE001 - re-raised as a typed error, not swallowed
            obs.log("adapter.enumerate_failed", level="error", platform="bluesky",
                    handle=handle, page=page_index, pages_walked=page_index,
                    error=type(exc).__name__)
            print(f"  !! bluesky enumerate failed for {handle} on page {page_index + 1}: "
                  f"{type(exc).__name__}", file=sys.stderr)
            raise BlueskyFetchError(
                f"{handle}: page {page_index + 1} of {page_limit} failed "
                f"({type(exc).__name__})") from exc
        if not feed:
            break
        for entry in feed:
            if entry.get("reason"):  # skip reposts
                continue
            post = entry.get("post") or {}
            record = post.get("record") or {}
            uri = post.get("uri") or ""
            rkey = uri.rsplit("/", 1)[-1] if uri else ""
            if not rkey:
                continue
            text = (record.get("text") or "").strip()
            created = record.get("createdAt") or post.get("indexedAt") or ""
            if len(created) < 10:
                undated += 1
                continue
            items.append({"id": rkey, "title": text[:60], "text": text,
                          "published": created[:10]})
        cursor = data.get("cursor")
        if not cursor:
            break
    if undated:
        obs.log("adapter.undated_rows_dropped", level="warning", platform="bluesky",
                handle=handle, count=undated)
    _FEED_CACHE[handle] = {i["id"]: i for i in items}
    if keyword_filter:
        # Filter the full text, not the 60-char display title -- Instagram
        # filters `caption` and LinkedIn/Facebook/X filter `body` (B-08).
        needle = keyword_filter.lower()
        items = [i for i in items if needle in (i.get("text") or "").lower()]
    return items


def peek_upload_date(item_id: str) -> str | None:
    # Genuinely dead code as of B-09: enumerate_newest_first drops any row it
    # cannot date, so every item it yields carries 'published'. Kept because
    # the PlatformAdapter contract requires the method.
    return None


def download_item(repo_root: Path, handle: str, rkey: str, title: str,
                  content_type: str | None = None) -> dict:
    # content_type is part of the PlatformAdapter contract (YouTube uses it to
    # distinguish Shorts from long-form). Bluesky posts have no such split, so
    # it is accepted and ignored rather than omitted -- an adapter that cannot
    # be called with the full signature breaks the engine at runtime.
    out_dir = handle_dir(repo_root, "bluesky", handle)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Serve from the last enumerate_newest_first walk instead of re-walking
    # the whole 5-page feed per item (B-07). On a cache miss, fall back to
    # exactly one bounded re-fetch before giving up -- a transport failure in
    # that re-fetch must raise (B-05), not be reported as "not found."
    match = _FEED_CACHE.get(handle, {}).get(rkey)
    if match is None:
        items = enumerate_newest_first(handle, keyword_filter=None, page_limit=5)
        match = _FEED_CACHE.get(handle, {}).get(rkey)
        if match is None:
            # Covers callers that monkeypatch enumerate_newest_first itself
            # (bypassing the cache-population side effect) as well as the
            # normal path.
            match = next((i for i in items if i["id"] == rkey), None)

    # If the item still can't be found (network error, swallowed by enumerate,
    # or aged out of page_limit=5), report failure rather than writing a
    # degraded file. on_disk_ids() treats any existing {rkey}.md as "already
    # captured," so a silent write-with-blank-created would permanently hide
    # the error.
    if match is None:
        obs.log("adapter.item_not_found", level="warning", platform="bluesky",
                handle=handle, item_id=rkey)
        return {"id": rkey, "ok": False, "published": None, "reason": "not-found-in-feed"}

    published = match["published"]
    full_text = match.get("text") or title
    purl = f"https://bsky.app/profile/{handle}/post/{rkey}"
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    dest = out_dir / f"{rkey}.md"
    meta = {
        "post_id": rkey,
        "url": purl,
        "handle": handle,
        # Bluesky's getAuthorFeed is scoped to one author, so author == handle
        # by construction. Recorded anyway to match every other adapter's
        # frontmatter shape, which is what discovery_digest reads generically.
        "author": handle,
        "published": published,
        "fetched_at": fetched_at,
    }
    # No like/comment counts: getAuthorFeed does not surface them, so Bluesky
    # items always score 0 in the spotlight ranking. Deliberate, not an omission.
    body = full_text or "(empty)"
    # Write-temp-then-rename, same as discovery_youtube.download_item (Task 7)
    # -- see that task's comment for why.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")
    tmp_dest.replace(dest)
    return {"id": rkey, "ok": True, "published": published}
