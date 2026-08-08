"""X.com platform adapter for the discovery engine, backed by Bright Data's
X Posts dataset (discover_by=profile_url).

Field names below come from six live jobs on 2026-08-08, not from the
published field list. See docs/superpowers/specs/2026-08-08-x-brightdata-
adapter-design.md, which also records why two modes Bright Data advertises
are NOT implemented:

  - The X Profiles dataset (gd_lwxmeb2u1cniijd7t4) returns one billed record
    with an embedded posts array, which looked ~20x cheaper. Its depth and
    recency are wildly inconsistent -- CNN returned 20 posts from the last
    two days, elonmusk returned 99 spanning 2018-2025 whose newest was
    eleven months stale, unsorted, with no author field to filter on.
  - start_date/end_date backfill returns an error row (error_code
    'dead_page'), verified. There is no backfill path here.
"""
from __future__ import annotations

import datetime as _dt
import sys
import time  # noqa: F401 -- kept so tests can monkeypatch x.time.sleep/monotonic
from pathlib import Path

import requests  # noqa: F401 -- kept so tests can monkeypatch x.requests.post/get

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

# Not a secret -- read off the Bright Data dashboard's generated API snippet
# for the X Posts product (2026-08-08). The type/discover_by query params
# select the mode; this is the Posts dataset, NOT the Profiles dataset.
DATASET_ID = "gd_lwxkxvnf1cynvib9co"

KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

PLATFORM = "x"

MAX_ITEMS_PER_RUN = 10
# 600, NOT the 300 Instagram and LinkedIn use. Measured latency was 243s at
# limit_per_input=10 -- the production setting -- so 300 would leave under a
# minute of margin and turn ordinary slowness into a BrightDataJobTimeout on
# a job that was already billed. Do not "make the constants consistent".
POLL_TIMEOUT_S = 600
POLL_INTERVAL_S = 5

TITLE_MAX_CHARS = 60


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or None.

    This dataset returns genuine ISO 8601 UTC -- '2026-08-08T01:11:45.000Z'
    (verified 2026-08-08) -- so a 10-character prefix is correct. That is NOT
    true of Bright Data's Instagram product, which returns a US-format local
    timestamp; the datasets disagree, so no format may be inferred from
    another.

    US-format input is deliberately NOT accepted. Guessing between MM/DD and
    DD/MM would yield silently wrong dates, which is worse than a dropped row
    -- and drops are counted and logged by enumerate_newest_first.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    candidate = raw[:10]
    try:
        _dt.datetime.strptime(candidate, "%Y-%m-%d")
        return candidate
    except ValueError:
        return None


def _video_urls(raw) -> list[str]:
    """The `videos` field is a list of structs -- [{'video_url': ...,
    'duration': ...}] -- verified live. Flatten to URLs; duration is not
    stored. Bare strings are tolerated in case the shape ever simplifies."""
    if not raw:
        return []
    urls = []
    for entry in raw:
        if isinstance(entry, dict):
            url = (entry.get("video_url") or "").strip()
            if url:
                urls.append(url)
        elif isinstance(entry, str) and entry.strip():
            urls.append(entry.strip())
    return urls


def _normalize_row(row: dict) -> dict | None:
    """One raw Bright Data row -> this adapter's internal shape, or None if
    the row is unusable. The single place to update if the schema changes.

    Load-bearing and verified:
    - The body is `description`, and it is NULLABLE -- 3 of 10 live rows for
      one account were media-only posts. A null body is kept, not dropped.
    - Authorship is `user_posted` (the handle), NOT `user_id` (a numeric
      profile id) and NOT `is_repost`, which was False even on a row the
      tracked account did not write.
    - There is no usable content_type field; see enumerate_newest_first.
    """
    post_id = row.get("id")
    if not post_id:
        return None
    published = _parse_published(row.get("date_posted"))
    if published is None:
        return None

    body = (row.get("description") or "").strip()
    first_line = body.split("\n", 1)[0].strip()
    title = first_line or str(post_id)

    raw_date_posted = (row.get("date_posted") or "").strip()

    return {
        "id": str(post_id),
        "title": title[:TITLE_MAX_CHARS],
        "published": published,
        # Full ISO 8601 timestamp, used only as the sort key -- 'published'
        # truncates to the date, so same-day rows would otherwise sort in
        # Bright Data's arbitrary arrival order (verified live: rows are NOT
        # returned newest-first). Lexicographic comparison is correct for
        # this dataset's real ISO 8601 strings.
        "published_ts": raw_date_posted or f"{published}T00:00:00",
        "author": (row.get("user_posted") or "").strip(),
        "body": body,
        # Informational only. The domain varies by account --
        # twitter.com/<numeric_id>/status/<id> for CNN,
        # x.com/<handle>/status/<id> for elonmusk -- so identity is never
        # keyed on it.
        "url": row.get("url") or "",
        "like_count": row.get("likes"),
        "comment_count": row.get("replies"),
        "repost_count": row.get("reposts"),
        "view_count": row.get("views"),
        "bookmark_count": row.get("bookmarks"),
        "quote_count": row.get("quotes"),
        # These come back as null rather than [] on most rows; yaml.safe_dump
        # would render that as 'null', and an empty list is the honest shape.
        "hashtags": row.get("hashtags") or [],
        "photos": row.get("photos") or [],
        "videos": _video_urls(row.get("videos")),
        "external_url": row.get("external_url"),
    }


BRIGHTDATA_API_BASE = brightdata_job.BRIGHTDATA_API_BASE
REQUEST_TIMEOUT_S = brightdata_job.REQUEST_TIMEOUT_S

# Re-exported so `pytest.raises(discovery_x.BrightDataJobFailed)` works and
# callers need not know where the exceptions live.
BrightDataJobTimeout = brightdata_job.BrightDataJobTimeout
BrightDataJobFailed = brightdata_job.BrightDataJobFailed


def api_key() -> str | None:
    """The Bright Data API token, or None if not configured. Reads this
    module's KEY_ENV_VAR/KEY_FILE at call time so tests can patch them."""
    return brightdata_job.read_key(KEY_ENV_VAR, KEY_FILE)


def profile_url(handle: str) -> str:
    return f"https://x.com/{handle.lstrip('@').strip()}"


def _trigger_job(handle: str, key: str) -> str:
    return brightdata_job.trigger(
        BRIGHTDATA_API_BASE,
        DATASET_ID,
        {
            # A *discovery* job -- "find this account's newest posts".
            # Without type/discover_by, Bright Data reads the input url as a
            # single page to collect, the wrong product mode entirely.
            "type": "discover_new",
            "discover_by": "profile_url",
            # Server-side per-input record cap: the primary cost control.
            "limit_per_input": MAX_ITEMS_PER_RUN,
            "include_errors": "true",
            "notify": "false",
        },
        # No start_date/end_date. Bright Data's snippet accepts them and this
        # dataset does not honor them: a two-day window against an account
        # posting hundreds of times a day returned one error row, error_code
        # 'dead_page' (verified 2026-08-08). There is no backfill path here.
        [{"url": profile_url(handle)}],
        key,
    )


def _poll_job_status(job_id: str, key: str) -> str:
    return brightdata_job.poll_status(BRIGHTDATA_API_BASE, job_id, key)


def _fetch_job_results(job_id: str, key: str) -> list[dict]:
    return brightdata_job.fetch_results(BRIGHTDATA_API_BASE, job_id, key)


def _run_collection_job(handle: str) -> list[dict]:
    key = api_key()
    if key is None:
        raise RuntimeError(
            "Bright Data API key not configured "
            f"(set {KEY_ENV_VAR} or {KEY_FILE.name})"
        )
    # The three lambdas resolve _trigger_job/_poll_job_status/
    # _fetch_job_results through module globals when they run, which is what
    # lets the tests monkeypatch them by name.
    return brightdata_job.await_results(
        trigger_fn=lambda: _trigger_job(handle, key),
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
        label=f"for {PLATFORM}/{handle}",
        poll_timeout_s=POLL_TIMEOUT_S,
        poll_interval_s=POLL_INTERVAL_S,
    )
