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
import sys
import time  # noqa: F401 -- kept so tests can monkeypatch ig.time.sleep/monotonic
from pathlib import Path

import requests  # noqa: F401 -- kept so tests can monkeypatch ig.requests.post/get

from pipeline_app import artifacts, brightdata_job
from pipeline_app.discovery_paths import handle_dir

BRIGHTDATA_API_BASE = brightdata_job.BRIGHTDATA_API_BASE
REQUEST_TIMEOUT_S = brightdata_job.REQUEST_TIMEOUT_S

# Re-exported so `pytest.raises(discovery_instagram.BrightDataJobFailed)` keeps
# working and callers need not know the exceptions moved.
BrightDataJobTimeout = brightdata_job.BrightDataJobTimeout
BrightDataJobFailed = brightdata_job.BrightDataJobFailed
BrightDataResponseError = brightdata_job.BrightDataResponseError
BrightDataConfigError = brightdata_job.BrightDataConfigError

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

# UNVERIFIED FIELD NAMES. Facebook's `profile_handle` and X's `user_posted`
# were both confirmed against live snapshots on 2026-08-08; this dataset's
# owner field was not. Read the candidates in order and report loudly when
# none is present rather than inventing a name -- B-23 asks for the field to
# be RECORDED (Facebook's rationale: it is what makes "this dataset started
# returning other accounts" detectable after the fact), not filtered on.
# Filtering waits for a live sample.
AUTHOR_FIELD_CANDIDATES = ("user_posted", "profile_name", "owner_username",
                           "user_username_raw", "username")


def _first_present(row: dict, candidates: tuple[str, ...]):
    for name in candidates:
        value = row.get(name)
        if value not in (None, ""):
            return name, value
    return None, None


def api_key() -> str | None:
    """The Bright Data API token, or None if not configured. Reads this
    module's KEY_ENV_VAR/KEY_FILE at call time so tests can patch them."""
    return brightdata_job.read_key(KEY_ENV_VAR, KEY_FILE)


def preflight() -> str | None:
    """None if this platform can run; one operator-facing message if it cannot.

    B-21: the per-job guard in _run_collection_job stays as a backstop, but it
    fires once per handle, so one unset token used to produce twenty identical
    error rows and a run that finished 'completed_with_errors' rather than
    refusing to start. run_discovery_cron calls this once before the handle
    loop (P8).
    """
    if api_key() is None:
        return (f"instagram: Bright Data API key not configured "
                f"(set {KEY_ENV_VAR} or {KEY_FILE.name}) -- every instagram "
                f"handle in this run will fail")
    return None


MAX_ITEMS_PER_RUN = 10           # the default; override with the env var below
MAX_ITEMS_ENV_VAR = "BRIGHTDATA_MAX_ITEMS_INSTAGRAM"
POLL_TIMEOUT_S = 300
POLL_INTERVAL_S = 5


def max_items() -> int:
    return brightdata_job.config_int(MAX_ITEMS_ENV_VAR, MAX_ITEMS_PER_RUN)


def poll_timeout_s() -> float:
    return brightdata_job.config_int("BRIGHTDATA_POLL_TIMEOUT_INSTAGRAM", POLL_TIMEOUT_S)


def _trigger_job(handle: str, key: str) -> str:
    profile_url = f"https://www.instagram.com/{handle.lstrip('@')}/"
    return brightdata_job.trigger(
        BRIGHTDATA_API_BASE,
        DATASET_ID,
        {
            # This is a *discovery* job -- "find this profile's newest posts".
            # Without type/discover_by, Bright Data reads the input url as a
            # single post page to collect, which is the wrong product mode for
            # a profile URL. Values from the dashboard's generated snippet.
            "type": "discover_new",
            "discover_by": "url",
            # Server-side per-input record cap: the primary cost control, and
            # the one that binds even if the dataset ignores num_of_posts.
            "limit_per_input": max_items(),
            "include_errors": "true",
            "notify": "false",
        },
        [{
            "url": profile_url,
            "num_of_posts": max_items(),
            "start_date": "",
            "end_date": "",
            "post_type": "",
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
    pending_key = f"instagram/{handle}"
    # Free recovery before any billed call: a snapshot an earlier run paid for
    # and abandoned on timeout (B-19). None means "nothing pending", which is
    # the ordinary case.
    resumed = brightdata_job.resume_pending(
        pending_key,
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
    )
    if resumed is not None:
        return resumed
    # The three lambdas resolve _trigger_job/_poll_job_status/_fetch_job_results
    # through module globals when they run, which is what keeps the existing
    # monkeypatch-based tests working after the extraction.
    return brightdata_job.await_results(
        trigger_fn=lambda: _trigger_job(handle, key),
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
        label=f"for {handle}",
        poll_timeout_s=poll_timeout_s(),
        poll_interval_s=POLL_INTERVAL_S,
        pending_key=pending_key,
    )


def _parse_datetime(raw: str | None) -> _dt.datetime | None:
    """Bright Data's date_posted -> a full datetime, or None if it matches
    none of this dataset's known formats.

    This dataset returns a US-format local timestamp -- '07/23/2026 16:00:22'
    -- NOT ISO 8601 (verified 2026-08-06 against a live snapshot of
    instagram.com/nike). The original ISO-prefix-slicing implementation
    rejected every row of that shape, which made enumerate_newest_first return
    [] and the engine report a healthy 'no_new_content' for a batch that had
    already been paid for. The ISO branch is kept as a cheap fallback in case
    the dataset's format changes or another Bright Data product is pointed at
    this adapter -- it only recovers the date, not the time of day.

    No timezone is supplied with the timestamp; since 'published' (see
    _parse_published) only ever compares dates, an off-by-one at a midnight
    boundary is the worst case there. The full time-of-day this function
    preserves is used only as enumerate_newest_first's sort key, to break
    ties between same-day posts -- see the sort call in enumerate_newest_first
    for why a date-only sort key is not good enough (Bright Data returns rows
    unsorted, and a date-only key sorts same-day rows in that arbitrary
    arrival order instead of newest-first).

    This is the single place the format list lives; _parse_published and
    enumerate_newest_first's sort key both build on it rather than
    reimplementing it.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return _dt.datetime.strptime(raw, fmt)
        except ValueError:
            pass
    candidate = raw[:10]
    try:
        return _dt.datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError:
        return None


def _parse_published(raw: str | None) -> str | None:
    """Bright Data's date_posted -> the engine's required YYYY-MM-DD, or
    None. Thin wrapper over _parse_datetime; see that function's docstring
    for the format list and why the US-format branch is tried first."""
    parsed = _parse_datetime(raw)
    return parsed.strftime("%Y-%m-%d") if parsed else None


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
    # Full parsed datetime, used only as enumerate_newest_first's sort key --
    # 'published' truncates to the date, so same-day rows need the time of
    # day to sort correctly. Reuses _parse_datetime rather than a second copy
    # of the format list. This second parse can't fail: _parse_published
    # above already required _parse_datetime to succeed on this same raw
    # value, but the "or" fallback keeps the key total (never crash, never
    # sort to the top) rather than relying on that invariant silently.
    parsed_dt = _parse_datetime(row.get("date_posted"))
    published_ts = parsed_dt.isoformat() if parsed_dt else f"{published}T00:00:00"
    # Bright Data returns display-cased values ("Post", "Reel"); the file
    # format documented in the design doc is lowercase.
    return {
        "id": post_id,
        "title": caption[:60] if caption else post_id,
        "published": published,
        "published_ts": published_ts,
        "content_type": (row.get("content_type") or "post").lower(),
        "caption": caption,
        "url": row.get("url") or "",
        "author": str(_first_present(row, AUTHOR_FIELD_CANDIDATES)[1] or "").strip(),
        "like_count": row.get("likes"),
        "comment_count": row.get("num_comments"),
    }


def _error_codes(raw_rows: list[dict]) -> list[str]:
    """Vendor error codes from an include_errors=true batch.

    With include_errors=true a failure arrives as a ROW carrying `error` and
    `error_code` rather than as an absence, so the adapter can log Bright
    Data's own reason ('dead_page') instead of a bare drop count.
    """
    return [r.get("error_code") or "unknown" for r in raw_rows if r.get("error")]


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

    if normalized and all(not n["author"] for n in normalized):
        # The candidate list (AUTHOR_FIELD_CANDIDATES) is a hypothesis, never
        # verified against a live snapshot the way Facebook's profile_handle
        # and X's user_posted were (2026-08-08). Every kept row resolving to
        # "" means every candidate missed -- report it loudly, with the real
        # keys this batch actually carried, so the next edit is informed
        # rather than another guess.
        brightdata_job.record_diagnostic(
            kind="adapter.author_field_unresolved", severity="warning",
            source="discovery_instagram",
            message=(f"instagram/{handle}: none of the candidate author fields "
                     f"{AUTHOR_FIELD_CANDIDATES} were present on any kept row -- "
                     f"the real field name is still unverified."),
            detail={"platform": "instagram", "handle": handle,
                    "candidates": list(AUTHOR_FIELD_CANDIDATES),
                    "observed_keys": sorted(raw_rows[0])})

    if raw_rows and not normalized:
        # This run was billed and produced nothing, but process_handle will
        # record the healthy status 'no_new_content' -- indistinguishable
        # from a quiet day unless it is loud here.
        codes = _error_codes(raw_rows)
        detail = f" Bright Data reported: {', '.join(sorted(set(codes)))}." if codes else ""
        print(f"  !! instagram/{handle}: Bright Data returned {len(raw_rows)} "
              f"row(s) but none survived filtering. This run was billed and "
              f"captured nothing -- check whether this handle is still valid."
              f"{detail}", file=sys.stderr)
        brightdata_job.record_diagnostic(
            kind="adapter.billed_captured_nothing", severity="error",
            source="discovery_instagram",
            message=(f"instagram/{handle}: Bright Data returned {len(raw_rows)} "
                     f"row(s) but none survived filtering. This run was billed "
                     f"and captured nothing.{detail}"),
            detail={"platform": "instagram", "handle": handle,
                    "raw_count": len(raw_rows), "error_codes": sorted(set(codes))})

    # Sort on the full timestamp, not the date-truncated 'published': Python's
    # sort is stable and Bright Data returns rows unsorted, so same-day rows
    # sorted on 'published' alone would keep Bright Data's arbitrary arrival
    # order, which can put a genuinely newer post behind ones already on disk
    # and trip discovery_engine's early-stop dedup before reaching it.
    normalized.sort(key=lambda n: n["published_ts"], reverse=True)

    # B-02 (S1): saturation must be computed on the PRE-cap count, right here
    # before the client-side slice below discards everything past the cap --
    # once that slice runs, how many rows Bright Data actually returned is
    # gone. None of the four Bright Data platforms support backfill, so a
    # batch that filled the cap is a data-loss event this run made, not a
    # quiet-account day, and process_handle would otherwise report it as the
    # healthy status 'ok'.
    cap = max_items()
    # Measured against raw_rows, NOT normalized: normalized has already
    # dropped unusable rows, so a batch that filled the cap but included one
    # id-less/undated row would otherwise show len(normalized) == cap - 1 and
    # never trip the alarm, even though the same cap-truncation data loss
    # occurred (plan correction, T17 task review, 2026-08-16).
    if brightdata_job.is_saturated(len(raw_rows), cap=cap):
        oldest = min((n["published_ts"] for n in normalized), default=None)
        brightdata_job.record_diagnostic(
            kind="adapter.batch_saturated", severity="error",
            source="discovery_instagram",
            message=(f"instagram/{handle}: the batch filled the cap of {cap}. Posts "
                     f"older than {oldest} in this interval were dropped and there is "
                     f"no backfill path for this platform. Raise "
                     f"{MAX_ITEMS_ENV_VAR} (this increases Bright Data spend per run) "
                     f"or shorten the run interval."),
            detail={"platform": "instagram", "handle": handle, "cap": cap,
                    "collected": len(normalized), "raw_count": len(raw_rows),
                    "oldest_kept": oldest})
        print(f"  !! instagram/{handle}: batch filled the cap of {cap}; older posts "
              f"in this interval are unrecoverable", file=sys.stderr)

    # Client-side backstop cap, independent of whether Bright Data's trigger
    # actually honors num_of_posts (see Task 2's comment) -- bounds cost
    # regardless of that unverified assumption.
    normalized = normalized[:cap]

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
        # Recorded although never filtered on (the field name itself is
        # unverified -- see AUTHOR_FIELD_CANDIDATES): it is what makes a
        # regression (this dataset starting to return other accounts)
        # detectable after the fact, same rationale as Facebook's `author`.
        "author": cached["author"],
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
