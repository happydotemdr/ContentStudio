"""Facebook platform adapter for the discovery engine, backed by Bright
Data's Facebook Pages Posts dataset.

Despite the product name, this dataset serves BOTH Pages and personal
profiles -- verified live 2026-08-08, where facebook.com/zuck returned rows
with is_page=False. It also returns Reels, tagged post_type='Reel'. Bright
Data's dedicated Reels dataset was evaluated and dropped: every reel it
returned was already returned here, and it reported 'dead_page' for an
account whose reels this dataset was serving in the same minute.

Field names below are from five live jobs on 2026-08-08, not from the
published field list. See docs/superpowers/specs/2026-08-08-facebook-
brightdata-adapter-design.md.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

PLATFORM = "facebook"

# Not a secret -- read off Bright Data's published endpoint index for the
# Facebook Pages Posts product (2026-08-08). This product has no discovery
# mode, so no type/discover_by query params are sent.
DATASET_ID = "gd_lkaxegm826bjpoo9m5"

KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

MAX_ITEMS_PER_RUN = 10
POLL_TIMEOUT_S = 300
POLL_INTERVAL_S = 5

TITLE_MAX_CHARS = 60


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or None.

    This dataset returns genuine ISO 8601 UTC -- '2026-07-06T19:01:04.000Z'
    (verified 2026-08-08) -- so a 10-character prefix is correct. That is NOT
    true of Bright Data's Instagram product, which returns a US-format local
    timestamp; the datasets disagree, so no format may be inferred from a
    sibling product.

    The MM-DD-YYYY format that appears in Bright Data's Facebook snippets is
    an INPUT format for start_date/end_date and does not describe output.

    US-format input is deliberately NOT accepted. Guessing between MM-DD and
    DD-MM would yield silently wrong dates, which is worse than a dropped row
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


def _normalize_row(row: dict) -> dict | None:
    """One raw Bright Data row -> this adapter's internal shape, or None if
    the row is unusable. The single place to update if the schema changes.

    Three returned fields are deliberately NOT read, each a live trap:
    - `timestamp` is SCRAPE time, not post time (2026-08-08 on a July post).
    - `shortcode` is not a stable identity: for one post the Reels product
      returned '1157962813213302' and this one returned '1479086397353733'.
    - `page_likes` returned 0 on an account reporting 1.4M page_followers.
    """
    post_id = row.get("post_id")
    if not post_id:
        return None
    published = _parse_published(row.get("date_posted"))
    if published is None:
        return None

    body = (row.get("content") or "").strip()
    first_line = body.split("\n", 1)[0].strip()
    title = first_line or str(post_id)

    raw_date_posted = (row.get("date_posted") or "").strip()

    return {
        "id": str(post_id),
        "title": title[:TITLE_MAX_CHARS],
        "published": published,
        # Full ISO 8601 timestamp, used only as the sort key -- 'published'
        # truncates to the date, so same-day rows would otherwise sort in
        # Bright Data's arrival order. Lexicographic comparison is correct
        # for this dataset's real ISO 8601 strings (verified 2026-08-08).
        # raw_date_posted is guaranteed non-empty here (the published check
        # above already required it), but the "or" fallback keeps this key
        # total rather than crashing if that ever stops being true.
        "published_ts": raw_date_posted or f"{published}T00:00:00",
        # Observed values: 'Post', 'Reel' -- display-cased, so lowercase.
        "content_type": (row.get("post_type") or "post").strip().lower(),
        # Recorded, never filtered on: a numeric handle returns the VANITY
        # profile_handle ('NASA'), so comparing it to the tracked handle
        # would discard every row. It is what makes a future regression
        # (this dataset starting to return other accounts) detectable.
        "author": (row.get("profile_handle") or "").strip(),
        "profile_id": row.get("profile_id") or "",
        "is_page": row.get("is_page"),
        "body": body,
        "url": row.get("url") or "",
        # `likes` is the reaction TOTAL. `num_likes_type` is a dict holding
        # only the 'Like' subtotal -- a different, smaller number.
        "like_count": row.get("likes"),
        "comment_count": row.get("num_comments"),
        "share_count": row.get("num_shares"),
        "view_count": row.get("video_view_count"),
        # Absent on Pages Posts rows, null on Reels rows -- both are real.
        "hashtags": row.get("hashtags") or [],
    }


def _error_codes(raw_rows: list[dict]) -> list[str]:
    """Vendor error codes from an include_errors=true batch.

    With include_errors=true a failure arrives as a ROW carrying `error` and
    `error_code` rather than as an absence, so the adapter can log Bright
    Data's own reason ('dead_page') instead of a bare drop count.
    """
    return [r.get("error_code") or "unknown" for r in raw_rows if r.get("error")]


BRIGHTDATA_API_BASE = brightdata_job.BRIGHTDATA_API_BASE

# Re-exported so `pytest.raises(discovery_facebook.BrightDataJobFailed)` works
# and callers need not know where the exceptions live.
BrightDataJobTimeout = brightdata_job.BrightDataJobTimeout
BrightDataJobFailed = brightdata_job.BrightDataJobFailed


def api_key() -> str | None:
    """The Bright Data API token, or None if not configured. Reads this
    module's KEY_ENV_VAR/KEY_FILE at call time so tests can patch them."""
    return brightdata_job.read_key(KEY_ENV_VAR, KEY_FILE)


def profile_url(handle: str) -> str:
    """The Facebook URL for a tracked handle.

    Two shapes, both verified live 2026-08-08. An all-digit handle is an
    account id and goes through profile.php?id=, which is the form that was
    tested; the bare facebook.com/<numeric-id> form was NOT tested and is
    deliberately not used.
    """
    slug = handle.lstrip("@").strip()
    if slug.isdigit():
        return f"https://www.facebook.com/profile.php?id={slug}"
    return f"https://www.facebook.com/{slug}"


def _trigger_job(handle: str, key: str) -> str:
    return brightdata_job.trigger(
        BRIGHTDATA_API_BASE,
        DATASET_ID,
        {
            # No type/discover_by: this product has no discovery mode. The
            # input URL is the account and the collector walks it.
            "include_errors": "true",
            "notify": "false",
        },
        [{
            # Server-side per-input record cap: the primary cost control.
            # Verified honored exactly -- 3 returned 3, 2 returned 2.
            "url": profile_url(handle),
            "num_of_posts": MAX_ITEMS_PER_RUN,
        }],
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
    return brightdata_job.await_results(
        trigger_fn=lambda: _trigger_job(handle, key),
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
        label=f"for {PLATFORM}/{handle}",
        poll_timeout_s=POLL_TIMEOUT_S,
        poll_interval_s=POLL_INTERVAL_S,
    )


# handle -> item_id -> normalized row. Populated by enumerate_newest_first,
# read by download_item. Calling Bright Data again per item would double-pay
# for posts already collected. Per-process: run_discovery_cron is always
# invoked as a subprocess, so no entry outlives a single run.
_ENUMERATE_CACHE: dict[str, dict[str, dict]] = {}


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    # Raises BrightDataJobTimeout/BrightDataJobFailed -- never swallowed here.
    # An empty return must mean "the job completed and there was nothing",
    # nothing else.
    raw_rows = _run_collection_job(handle)

    normalized = [_normalize_row(r) for r in raw_rows]
    unusable = sum(1 for n in normalized if n is None)
    kept = [n for n in normalized if n is not None]
    codes = _error_codes(raw_rows)

    if unusable:
        detail = f" ({', '.join(sorted(set(codes)))})" if codes else ""
        print(f"  ! {PLATFORM}/{handle}: dropped {unusable} unusable row(s){detail}",
              file=sys.stderr)

    if raw_rows and not kept:
        # This run was billed and produced nothing, but process_handle will
        # record the healthy status 'no_new_content' -- indistinguishable
        # from a quiet day unless it is loud here.
        detail = f" Bright Data reported: {', '.join(sorted(set(codes)))}." if codes else ""
        print(f"  !! {PLATFORM}/{handle}: Bright Data returned {len(raw_rows)} "
              f"row(s) but none survived filtering. This run was billed and "
              f"captured nothing -- check whether this handle is still valid."
              f"{detail}", file=sys.stderr)

    # Sort on the full timestamp, not the date-truncated 'published': Python's
    # sort is stable, so same-day rows sorted on 'published' alone would keep
    # Bright Data's arrival order, which can put a genuinely newer post behind
    # ones already on disk and trip the early-stop dedup before reaching it.
    # Cap AFTER sorting so it bounds retained items.
    kept.sort(key=lambda n: n["published_ts"], reverse=True)
    kept = kept[:MAX_ITEMS_PER_RUN]

    # Overwrite, not merge: a fresh successful enumerate replaces whatever
    # this handle held, so download_item never reads a stale id. Cached
    # BEFORE keyword_filter -- the filter narrows what the engine walks, not
    # what was collected and paid for.
    _ENUMERATE_CACHE[handle] = {n["id"]: n for n in kept}

    items = kept
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["body"].lower()]
    return [
        {"id": i["id"], "title": i["title"], "published": i["published"],
         "content_type": i["content_type"]}
        for i in items
    ]
