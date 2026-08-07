"""Instagram platform adapter for the discovery engine, backed by Bright
Data's Instagram Posts Scraper API. Isolates the Bright Data HTTP calls so
discovery_engine's core algorithm can be unit-tested with no network access,
the same isolation discovery_bluesky.py and discovery_youtube.py use.

Bright Data's API is asynchronous (trigger -> poll -> fetch) and bills per
record, unlike YouTube's Data API or Bluesky's AppView which answer
synchronously. See docs/superpowers/specs/2026-08-06-instagram-brightdata-
adapter-design.md for the full design, including why enumerate_newest_first
runs the whole job cycle once per handle per run and caches results for
download_item to read from -- calling Bright Data once per item would
double-pay for the same posts.
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
import time
from pathlib import Path

import requests

from pipeline_app import artifacts
from pipeline_app.discovery_paths import handle_dir

BRIGHTDATA_API_BASE = "https://api.brightdata.com/datasets/v3"

# Key lookup order: env var first (works for the scheduled task, which
# inherits the User environment), then a gitignored file for convenience --
# same pattern as discovery_youtube_api.api_key() / discovery_notify.api_key().
KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

# Bright Data dataset id for the Instagram Posts Scraper API product. Not a
# secret -- a one-time value read off the Bright Data dashboard's generated
# API snippet for "Instagram post - discover by URL" (2026-08-06). The same
# dataset id serves both the discover-by-profile and collect-by-post-URL
# modes; the type/discover_by query params below are what select between them.
DATASET_ID = "gd_lk5ns7kz21pck8jpis"

REQUEST_TIMEOUT_S = 30


def api_key() -> str | None:
    """The Bright Data API token, or None if not configured."""
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


MAX_ITEMS_PER_RUN = 10
POLL_TIMEOUT_S = 300
POLL_INTERVAL_S = 5


class BrightDataJobTimeout(Exception):
    """A Bright Data collection job did not reach 'ready' within POLL_TIMEOUT_S."""


class BrightDataJobFailed(Exception):
    """A Bright Data collection job reported status 'failed'."""


def _trigger_job(handle: str, key: str) -> str:
    if DATASET_ID.startswith("gd_REPLACE"):
        raise RuntimeError(
            "Instagram adapter DATASET_ID is still a placeholder -- provision the "
            "Bright Data Instagram Posts Scraper API product and set the real "
            "dataset id in discovery_instagram.py"
        )
    profile_url = f"https://www.instagram.com/{handle.lstrip('@')}/"
    response = requests.post(
        f"{BRIGHTDATA_API_BASE}/trigger",
        params={
            "dataset_id": DATASET_ID,
            # This is a *discovery* job -- "find this profile's newest posts".
            # Without type/discover_by, Bright Data reads the input url as a
            # single post page to collect, which is the wrong product mode for
            # a profile URL. Values from the dashboard's generated snippet.
            "type": "discover_new",
            "discover_by": "url",
            # Server-side per-input record cap: the primary cost control, and
            # the one that binds even if the dataset ignores num_of_posts.
            "limit_per_input": MAX_ITEMS_PER_RUN,
            "include_errors": "true",
            "notify": "false",
        },
        headers={"Authorization": f"Bearer {key}"},
        # Bare-array body is /trigger's documented shape. The dashboard's
        # {"input": [...], "limit_per_input": null} object form belongs to the
        # synchronous /scrape endpoint, which this adapter deliberately does
        # not use -- a discovery job takes minutes and would hang an HTTP call.
        # Empty start_date/end_date/post_type mirror the dashboard's "no
        # filter" example rows: unfiltered returns posts and Reels together,
        # which is what this pipeline wants.
        json=[{
            "url": profile_url,
            "num_of_posts": MAX_ITEMS_PER_RUN,
            "start_date": "",
            "end_date": "",
            "post_type": "",
        }],
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()["snapshot_id"]


def _poll_job_status(job_id: str, key: str) -> str:
    response = requests.get(
        f"{BRIGHTDATA_API_BASE}/progress/{job_id}",
        headers={"Authorization": f"Bearer {key}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()["status"]


def _fetch_job_results(job_id: str, key: str) -> list[dict]:
    response = requests.get(
        f"{BRIGHTDATA_API_BASE}/snapshot/{job_id}",
        params={"format": "json"},
        headers={"Authorization": f"Bearer {key}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


def _run_collection_job(handle: str) -> list[dict]:
    key = api_key()
    if key is None:
        raise RuntimeError(
            "Bright Data API key not configured "
            f"(set {KEY_ENV_VAR} or {KEY_FILE.name})"
        )
    job_id = _trigger_job(handle, key)
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while True:
        status = _poll_job_status(job_id, key)
        if status == "ready":
            return _fetch_job_results(job_id, key)
        if status == "failed":
            raise BrightDataJobFailed(f"Bright Data job {job_id} for {handle} failed")
        if time.monotonic() >= deadline:
            raise BrightDataJobTimeout(
                f"Bright Data job {job_id} for {handle} timed out after {POLL_TIMEOUT_S}s"
            )
        time.sleep(POLL_INTERVAL_S)


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or None.

    This dataset returns a US-format local timestamp -- '07/23/2026 16:00:22'
    -- NOT ISO 8601 (verified 2026-08-06 against a live snapshot of
    instagram.com/nike). The original ISO-prefix-slicing implementation
    rejected every row of that shape, which made enumerate_newest_first return
    [] and the engine report a healthy 'no_new_content' for a batch that had
    already been paid for. The ISO branch is kept as a cheap fallback in case
    the dataset's format changes or another Bright Data product is pointed at
    this adapter.

    No timezone is supplied with the timestamp; since the engine only ever
    compares dates, an off-by-one at a midnight boundary is the worst case.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return _dt.datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    candidate = raw[:10]
    try:
        _dt.datetime.strptime(candidate, "%Y-%m-%d")
        return candidate
    except ValueError:
        return None


def _normalize_row(row: dict) -> dict | None:
    """Maps one raw Bright Data Instagram row into the shape this adapter
    works with internally. Field names are taken from the published
    Instagram-Posts dataset schema (post_id, description, date_posted,
    content_type, url, likes, num_comments) -- note the caption text lives in
    'description', NOT 'caption'; there is no 'caption' field, and reading one
    would silently write empty bodies for a batch that was already paid for.
    This is the single place to update if the real schema differs.
    """
    post_id = row.get("post_id")
    if not post_id:
        return None
    published = _parse_published(row.get("date_posted"))
    if published is None:
        return None
    caption = (row.get("description") or "").strip()
    # Bright Data returns display-cased values ("Post", "Reel"); the file
    # format documented in the design doc is lowercase.
    return {
        "id": post_id,
        "title": caption[:60] if caption else post_id,
        "published": published,
        "content_type": (row.get("content_type") or "post").lower(),
        "caption": caption,
        "url": row.get("url") or "",
        "like_count": row.get("likes"),
        "comment_count": row.get("num_comments"),
    }


# handle -> item_id -> normalized row. Populated by enumerate_newest_first,
# read by download_item. Per-process, per-run cache -- see the design doc's
# "Cache concurrency" section for the documented, accepted race with
# validate_handle mode.
_ENUMERATE_CACHE: dict[str, dict[str, dict]] = {}


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    raw_rows = _run_collection_job(handle)  # raises BrightDataJobTimeout/Failed -- never swallowed here
    normalized = [_normalize_row(r) for r in raw_rows]
    dropped = sum(1 for n in normalized if n is None)
    if dropped:
        print(f"  ! {dropped} Bright Data row(s) for {handle} dropped (missing id or unusable date)",
              file=sys.stderr)
    normalized = [n for n in normalized if n is not None]
    normalized.sort(key=lambda n: n["published"], reverse=True)
    # Client-side backstop cap, independent of whether Bright Data's trigger
    # actually honors num_of_posts (see Task 2's comment) -- bounds cost
    # regardless of that unverified assumption.
    normalized = normalized[:MAX_ITEMS_PER_RUN]

    # Overwrite, not merge: a fresh successful enumerate replaces whatever
    # this handle's cache held before, so download_item never reads a stale
    # id from a previous run in the same process.
    _ENUMERATE_CACHE[handle] = {n["id"]: n for n in normalized}

    items = normalized
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["caption"].lower()]
    return [
        {"id": i["id"], "title": i["title"], "published": i["published"], "content_type": i["content_type"]}
        for i in items
    ]


def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    directory = handle_dir(repo_root, "instagram", handle)
    if not directory.exists():
        return set()
    return {p.stem for p in directory.glob("*.md")}


def peek_upload_date(item_id: str) -> str | None:
    # Dead code by design: enumerate_newest_first only ever returns items
    # with a normalized 'published' date (Task 3/4), so process_handle's
    # `item.get("published") or adapter.peek_upload_date(item_id)` never
    # falls through to this -- same as discovery_bluesky.peek_upload_date.
    return None


def download_item(repo_root: Path, handle: str, item_id: str, title: str,
                  content_type: str | None = None) -> dict:
    # A missing handle or item_id here is a programming error (every engine
    # call path calls enumerate_newest_first for this handle in this process
    # before calling download_item) -- KeyError propagates to the per-handle
    # error path in discovery_engine.py rather than being caught here, so it
    # surfaces as a normal 'error' result instead of failing silently.
    cached = _ENUMERATE_CACHE[handle][item_id]

    out_dir = handle_dir(repo_root, "instagram", handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    meta = {
        "post_id": cached["id"],
        "url": cached["url"],
        "handle": handle,
        "content_type": cached["content_type"],
        "published": cached["published"],
        "like_count": cached["like_count"],
        "comment_count": cached["comment_count"],
        "fetched_at": fetched_at,
    }
    body = cached["caption"] or "(empty)"

    dest = out_dir / f"{item_id}.md"
    # Write-temp-then-rename, same as discovery_youtube.download_item and
    # discovery_bluesky.download_item: an interrupted write must never leave
    # a truncated file at a path on_disk_ids() would treat as already-captured.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")
    tmp_dest.replace(dest)
    return {"id": item_id, "ok": True, "published": cached["published"]}
