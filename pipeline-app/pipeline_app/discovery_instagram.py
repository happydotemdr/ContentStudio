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
# secret -- a one-time value from the Bright Data dashboard when the product
# is provisioned. Placeholder until that provisioning step happens; replace
# before the first real run.
DATASET_ID = "gd_REPLACE_WITH_REAL_DATASET_ID"

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


def _trigger_job(handle: str) -> str:
    profile_url = f"https://www.instagram.com/{handle.lstrip('@')}/"
    response = requests.post(
        f"{BRIGHTDATA_API_BASE}/trigger",
        params={"dataset_id": DATASET_ID, "include_errors": "true"},
        headers={"Authorization": f"Bearer {api_key()}"},
        # num_of_posts as a request-time limit is this design's best-available
        # assumption about Bright Data's trigger API -- UNVERIFIED, see the
        # design doc's "Verification needed before implementation". If the API
        # doesn't honor it, enumerate_newest_first's post-fetch slice (Task 4)
        # still bounds cost on this side.
        json=[{"url": profile_url, "num_of_posts": MAX_ITEMS_PER_RUN}],
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()["snapshot_id"]


def _poll_job_status(job_id: str) -> str:
    response = requests.get(
        f"{BRIGHTDATA_API_BASE}/progress/{job_id}",
        headers={"Authorization": f"Bearer {api_key()}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()["status"]


def _fetch_job_results(job_id: str) -> list[dict]:
    response = requests.get(
        f"{BRIGHTDATA_API_BASE}/snapshot/{job_id}",
        params={"format": "json"},
        headers={"Authorization": f"Bearer {api_key()}"},
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


def _run_collection_job(handle: str) -> list[dict]:
    job_id = _trigger_job(handle)
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while True:
        status = _poll_job_status(job_id)
        if status == "ready":
            return _fetch_job_results(job_id)
        if status == "failed":
            raise BrightDataJobFailed(f"Bright Data job {job_id} for {handle} failed")
        if time.monotonic() >= deadline:
            raise BrightDataJobTimeout(
                f"Bright Data job {job_id} for {handle} timed out after {POLL_TIMEOUT_S}s"
            )
        time.sleep(POLL_INTERVAL_S)


def _normalize_row(row: dict) -> dict | None:
    """Maps one raw Bright Data Instagram row into the shape this adapter
    works with internally. Field names (post_id, caption, date_posted,
    content_type, url, likes, num_comments) are this design's best-available
    assumption about Bright Data's response schema -- UNVERIFIED, see the
    design doc's "Verification needed before implementation". This is the
    single place to update if the real schema differs.
    """
    post_id = row.get("post_id")
    if not post_id:
        return None
    published_raw = row.get("date_posted") or ""
    published_candidate = published_raw[:10] if len(published_raw) >= 10 else None
    published = None
    if published_candidate is not None:
        try:
            _dt.datetime.strptime(published_candidate, "%Y-%m-%d")
            published = published_candidate
        except ValueError:
            published = None
    if published is None:
        return None
    caption = (row.get("caption") or "").strip()
    return {
        "id": post_id,
        "title": caption[:60] if caption else post_id,
        "published": published,
        "content_type": row.get("content_type") or "post",
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
