"""YouTube Data API v3 client for video metadata.

Exists because YouTube's per-video InnerTube endpoints (what yt-dlp scrapes)
bot-block by IP, which took out peek_upload_date and download_item's metadata
half while leaving channel enumeration working. The Data API is key-
authenticated and quota'd rather than bot-gated, so it is unaffected by that
block.

Scope: metadata ONLY. The API cannot return caption *text* for videos the key's
owner does not own (captions.download requires OAuth as the video owner), so
transcripts still come from yt-dlp / youtube-transcript-api.

It also exposes contentDetails.caption, surfaced here as `manual_captions`.
Do NOT read that as "a transcript is obtainable": measured against this repo's
own corpus on 2026-07-30, 388 of the 411 videos we demonstrably hold a
transcript for report caption == "false". The field tracks only
manually-uploaded caption tracks; auto-generated (ASR) captions -- which is
what yt-dlp actually pulled for nearly the whole corpus -- report false. So
manual_captions=True is a strong positive signal and manual_captions=False
says almost nothing.

Quota: videos.list costs 1 unit per call and accepts up to 50 ids per call,
against a default 10,000 units/day. The whole 420-video corpus is ~9 units.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pipeline_app import obs

API_URL = "https://www.googleapis.com/youtube/v3/videos"

# Key lookup order: env var first (works for the scheduled task, which inherits
# the User environment), then a gitignored file for convenience.
KEY_ENV_VAR = "YOUTUBE_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "youtube_api_key.txt"

MAX_IDS_PER_CALL = 50

_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)

# One fact about the environment, not a per-video event: fetch_one() calls
# fetch_metadata() once per video from both download_item and
# peek_upload_date, so an unguarded warning emits hundreds of identical lines
# and drowns the escalations that matter (B-15). Mirrors
# discovery_youtube._TRANSCRIPT_API_MISSING_WARNED.
_NO_KEY_WARNED = False


def _warn_no_key(caller: str) -> None:
    global _NO_KEY_WARNED
    obs.log("adapter.api_key_missing", level="warning", platform="youtube",
            caller=caller, env_var=KEY_ENV_VAR)
    if _NO_KEY_WARNED:
        return
    _NO_KEY_WARNED = True
    print(f"  ! no YouTube Data API key ({KEY_ENV_VAR} env var or {KEY_FILE.name}) "
          f"-- falling back to yt-dlp for metadata", file=sys.stderr)


def api_key() -> str | None:
    """The Data API key, or None if not configured."""
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


def parse_duration(iso: str | None) -> int | None:
    """ISO-8601 duration (PT4M13S) -> whole seconds. None if unparseable.

    Live/upcoming videos report P0D, which correctly yields 0.
    """
    if not iso:
        return None
    match = _DURATION_RE.match(iso.strip())
    if not match:
        return None
    parts = {k: int(v) for k, v in match.groupdict(default="0").items()}
    return (parts["days"] * 86400 + parts["hours"] * 3600
            + parts["minutes"] * 60 + parts["seconds"])


def _to_int(value: str | None) -> int | None:
    # statistics fields are strings, and are omitted entirely when the uploader
    # hides them (likes) or they do not apply -- absent is not zero.
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _http_get_json(url: str, key: str | None = None) -> dict | None:
    """Isolated for monkeypatching in tests.

    The key goes in X-goog-api-key, never in the query string: the two except
    clauses below are careful not to print the URL, but any exception outside
    them escapes with the full URL -- and therefore the live key -- in a
    traceback the discovery cron writes to its log (D-52). Bright Data and
    Resend are already header-borne; this was the one that was not.
    """
    headers = {"X-goog-api-key": key} if key else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001 - error body is best-effort only
            pass
        if exc.code == 403:
            print(f"  ! YouTube Data API refused the request (403): {detail or 'quota exceeded or key restricted'}",
                  file=sys.stderr)
        elif exc.code == 400:
            print(f"  ! YouTube Data API rejected the request (400): {detail or 'bad API key'}",
                  file=sys.stderr)
        else:
            print(f"  ! YouTube Data API HTTP {exc.code}: {detail}", file=sys.stderr)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"  ! YouTube Data API request failed: {type(exc).__name__}", file=sys.stderr)
        return None


def _normalize(item: dict) -> dict:
    snippet = item.get("snippet") or {}
    content = item.get("contentDetails") or {}
    stats = item.get("statistics") or {}

    published_at = snippet.get("publishedAt") or ""
    upload_date = published_at[:10] if len(published_at) >= 10 else None

    # contentDetails.caption is a STRING "true"/"false", not a bool.
    caption_raw = content.get("caption")
    manual_captions = {"true": True, "false": False}.get(caption_raw)

    return {
        "title": snippet.get("title"),
        "channel": snippet.get("channelTitle"),
        "description": snippet.get("description") or "",
        "upload_date": upload_date,
        "duration_s": parse_duration(content.get("duration")),
        "view_count": _to_int(stats.get("viewCount")),
        "like_count": _to_int(stats.get("likeCount")),
        "comment_count": _to_int(stats.get("commentCount")),
        "manual_captions": manual_captions,
        "tags": snippet.get("tags") or [],
    }


def fetch_metadata(video_ids: list[str], key: str | None = None) -> dict[str, dict]:
    """Fetch metadata for video_ids. Returns {video_id: normalized_record}.

    Batches into MAX_IDS_PER_CALL-sized requests. Ids that the API does not
    return (deleted, private, or region-blocked videos) are simply absent from
    the result -- callers must treat a missing key as "no metadata", not as an
    error, since a partial batch is still useful.
    """
    key = key or api_key()
    if not key:
        _warn_no_key("fetch_metadata")
        return {}

    unique_ids = list(dict.fromkeys(v for v in video_ids if v))
    out: dict[str, dict] = {}

    for start in range(0, len(unique_ids), MAX_IDS_PER_CALL):
        batch = unique_ids[start:start + MAX_IDS_PER_CALL]
        query = urllib.parse.urlencode({
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(batch),
            "maxResults": MAX_IDS_PER_CALL,
        })
        payload = _http_get_json(f"{API_URL}?{query}", key)
        if payload is None:
            continue
        for item in payload.get("items") or []:
            video_id = item.get("id")
            if video_id:
                out[video_id] = _normalize(item)

    return out


def fetch_one(video_id: str, key: str | None = None) -> dict | None:
    """Single-video convenience wrapper. None if unavailable."""
    return fetch_metadata([video_id], key=key).get(video_id)


def fetch_upload_dates(video_ids: list[str], key: str | None = None) -> dict[str, str]:
    """{video_id: 'YYYY-MM-DD'} for the ids the API returns.

    Lighter than fetch_metadata (part=snippet only) but the same 1 unit per 50
    ids. Exists so enumerate_newest_first can establish a single global
    ordering across the /videos and /shorts tabs, which are each newest-first
    on their own but carry no dates in a --flat-playlist listing.
    """
    key = key or api_key()
    if not key:
        _warn_no_key("fetch_upload_dates")
        return {}

    unique_ids = list(dict.fromkeys(v for v in video_ids if v))
    out: dict[str, str] = {}

    for start in range(0, len(unique_ids), MAX_IDS_PER_CALL):
        batch = unique_ids[start:start + MAX_IDS_PER_CALL]
        query = urllib.parse.urlencode({
            "part": "snippet",
            "id": ",".join(batch),
            "maxResults": MAX_IDS_PER_CALL,
        })
        payload = _http_get_json(f"{API_URL}?{query}", key)
        if payload is None:
            continue
        for item in payload.get("items") or []:
            video_id = item.get("id")
            published_at = ((item.get("snippet") or {}).get("publishedAt") or "")
            if video_id and len(published_at) >= 10:
                out[video_id] = published_at[:10]

    return out
