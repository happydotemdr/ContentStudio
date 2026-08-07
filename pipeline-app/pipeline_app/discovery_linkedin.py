"""LinkedIn platform adapters for the discovery engine, backed by Bright
Data's LinkedIn Posts dataset. Two platforms share this module:

  linkedin-profile  -- a person's own posts   (discover_by=profile_url)
  linkedin-company  -- an organization's posts (discover_by=company_url)

A third mode Bright Data advertises -- discover_by=url against
/today/author/<slug>, nominally "Pulse articles" -- is deliberately NOT
implemented. Live testing on 2026-08-07 against both authors in Bright Data's
own documentation snippet returned unrelated third-party posts and zero
articles, twice. See the design doc's "Broken -- Pulse articles" section.

Field names below are from four live jobs on 2026-08-07, not from the
published field list. See docs/superpowers/specs/2026-08-07-linkedin-
brightdata-adapter-design.md.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

# Not a secret -- read off the Bright Data dashboard's generated API snippet
# for the LinkedIn Posts product (2026-08-07). One dataset serves every mode;
# the type/discover_by query params select between them.
DATASET_ID = "gd_lyy3tktm25m4avu764"

KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

MAX_ITEMS_PER_RUN = 10
POLL_TIMEOUT_S = 300
POLL_INTERVAL_S = 5

TITLE_MAX_CHARS = 60


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or None.

    This dataset returns genuine ISO 8601 UTC -- '2026-07-08T14:00:09.491Z'
    (verified 2026-08-07) -- so a 10-character prefix is correct. That is NOT
    true of Bright Data's Instagram product, which returns a US-format local
    timestamp; the two datasets disagree, so neither format may be inferred
    from the other.

    US-format input is deliberately NOT accepted here. Guessing between MM/DD
    and DD/MM would yield silently wrong dates, which is worse than a dropped
    row -- and drops are counted and logged by enumerate_newest_first.
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

    Two field choices are load-bearing and verified:
    - The body is `post_text`. `original_post_text` and `post_text_html` are
      longer but carry HTML entities and anchor markup.
    - The title comes from `headline` (the post's first line), NOT the `title`
      field, which is SEO text with hashtags and the author name appended.
    """
    post_id = row.get("id")
    if not post_id:
        return None
    published = _parse_published(row.get("date_posted"))
    if published is None:
        return None

    body = (row.get("post_text") or "").strip()
    headline = (row.get("headline") or "").strip()
    first_line = body.split("\n", 1)[0].strip()
    title = headline or first_line or str(post_id)

    return {
        "id": str(post_id),
        "title": title[:TITLE_MAX_CHARS],
        "published": published,
        # Observed values: 'post', 'repost'. Lowercased defensively -- the
        # Instagram product returns display-cased values for the same concept.
        "content_type": (row.get("post_type") or "post").strip().lower(),
        "account_type": (row.get("account_type") or "").strip().lower(),
        "author": (row.get("user_id") or "").strip(),
        "body": body,
        "url": row.get("url") or "",
        "like_count": row.get("num_likes"),
        "comment_count": row.get("num_comments"),
        "hashtags": row.get("hashtags") or [],
    }
