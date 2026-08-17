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

MAX_ITEMS_PER_RUN = 10           # the default; override with the env var below
MAX_ITEMS_ENV_VAR = "BRIGHTDATA_MAX_ITEMS_X"
# 600, NOT the 300 Instagram and LinkedIn use. Measured latency was 243s at
# limit_per_input=10 -- the production setting -- so 300 would leave under a
# minute of margin and turn ordinary slowness into a BrightDataJobTimeout on
# a job that was already billed. Do not "make the constants consistent".
POLL_TIMEOUT_S = 600
POLL_INTERVAL_S = 5

TITLE_MAX_CHARS = 60


def max_items() -> int:
    return brightdata_job.config_int(MAX_ITEMS_ENV_VAR, MAX_ITEMS_PER_RUN)


def poll_timeout_s() -> float:
    return brightdata_job.config_int("BRIGHTDATA_POLL_TIMEOUT_X", POLL_TIMEOUT_S)


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

# Re-exported so `pytest.raises(discovery_x.BrightDataJobFailed)` works and
# callers need not know where the exceptions live.
BrightDataJobTimeout = brightdata_job.BrightDataJobTimeout
BrightDataJobFailed = brightdata_job.BrightDataJobFailed
BrightDataResponseError = brightdata_job.BrightDataResponseError
BrightDataConfigError = brightdata_job.BrightDataConfigError


def key_file_for(repo_root: Path | None) -> Path:
    """The credential file, resolved against the same root everything else
    uses. F-69: KEY_FILE was anchored to the real repo, so a test passing
    repo_root=tmp_path was still one env var away from a live token."""
    if repo_root is None:
        return KEY_FILE
    return Path(repo_root) / "pipeline-app" / KEY_FILE.name


def api_key(repo_root: Path | None = None) -> str | None:
    """The Bright Data API token, or None if not configured. Reads this
    module's KEY_ENV_VAR and the repo_root-resolved key file at call time so
    tests can patch them."""
    return brightdata_job.read_key(KEY_ENV_VAR, key_file_for(repo_root))


def preflight(repo_root: Path | None = None) -> str | None:
    """None if this platform can run; one operator-facing message if it cannot.

    B-21: the per-job guard in _run_collection_job stays as a backstop, but it
    fires once per handle, so one unset token used to produce twenty identical
    error rows and a run that finished 'completed_with_errors' rather than
    refusing to start. run_discovery_cron calls this once before the handle
    loop (P8).
    """
    if api_key(repo_root=repo_root) is None:
        return (f"x: Bright Data API key not configured "
                f"(set {KEY_ENV_VAR} or {KEY_FILE.name}) -- every x "
                f"handle in this run will fail")
    return None


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
            "limit_per_input": max_items(),
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
    pending_key = f"{PLATFORM}/{handle}"
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
    # The three lambdas resolve _trigger_job/_poll_job_status/
    # _fetch_job_results through module globals when they run, which is what
    # lets the tests monkeypatch them by name.
    return brightdata_job.await_results(
        trigger_fn=lambda: _trigger_job(handle, key),
        poll_fn=lambda job_id: _poll_job_status(job_id, key),
        fetch_fn=lambda job_id: _fetch_job_results(job_id, key),
        label=f"for {PLATFORM}/{handle}",
        poll_timeout_s=poll_timeout_s(),
        poll_interval_s=POLL_INTERVAL_S,
        pending_key=pending_key,
    )


# handle -> item_id -> normalized row. Populated by enumerate_newest_first,
# read by download_item. Calling Bright Data again per item would double-pay
# for posts already collected.
_ENUMERATE_CACHE: dict[str, dict[str, dict]] = {}


def reset_caches() -> None:
    """Clear this module's per-process enumerate cache.

    F-67: the cache is a process global that no fixture cleared, so the suite
    passed only because each test file happened to use distinct handle names.
    The repo-wide conftest fixture calls this before every test.
    """
    _ENUMERATE_CACHE.clear()


def cached_ids(handle: str) -> set[str]:
    """The item ids this handle's last enumerate retained. A read-only view so
    tests never reach into _ENUMERATE_CACHE directly."""
    return set(_ENUMERATE_CACHE.get(handle, {}))


def cached_row(handle: str, item_id: str) -> dict:
    """One retained row. KeyError if absent -- same contract download_item has."""
    return _ENUMERATE_CACHE[handle][item_id]


def enumerate_newest_first(handle: str, keyword_filter: str | None) -> list[dict]:
    # Raises BrightDataJobTimeout/BrightDataJobFailed -- never swallowed here.
    # An empty return must mean "the job completed and there was nothing".
    raw_rows = _run_collection_job(handle)

    normalized = [_normalize_row(r) for r in raw_rows]
    unusable = sum(1 for n in normalized if n is None)
    kept = [n for n in normalized if n is not None]

    # Authorship filter. discover_by=profile_url returns the account's
    # timeline, including other people's posts (verified live). NOT is_repost,
    # which was False even on the foreign row.
    wanted = handle.lstrip("@").strip().lower()
    before = len(kept)
    kept = [n for n in kept if n["author"].lower() == wanted]
    foreign = before - len(kept)

    if unusable and foreign:
        print(f"  ! {PLATFORM}/{handle}: dropped {unusable} unusable row(s), "
              f"{foreign} row(s) by another author", file=sys.stderr)
    elif unusable:
        print(f"  ! {PLATFORM}/{handle}: dropped {unusable} unusable row(s)",
              file=sys.stderr)
    elif foreign:
        print(f"  ! {PLATFORM}/{handle}: dropped {foreign} row(s) by another author",
              file=sys.stderr)

    if unusable:
        brightdata_job.record_diagnostic(
            kind="adapter.rows_dropped", severity="warning",
            source="discovery_x",
            message=f"{PLATFORM}/{handle}: dropped {unusable} unusable row(s)",
            detail={"platform": PLATFORM, "handle": handle, "dropped": unusable})
    if foreign:
        brightdata_job.record_diagnostic(
            kind="adapter.foreign_rows_dropped", severity="warning",
            source="discovery_x",
            message=f"{PLATFORM}/{handle}: dropped {foreign} row(s) by another author",
            detail={"platform": PLATFORM, "handle": handle, "dropped": foreign})

    if raw_rows and not kept:
        # This run was billed and produced nothing, but process_handle will
        # record the healthy status 'no_new_content' -- indistinguishable from
        # a quiet day unless it is loud here. The advice depends on *why*
        # nothing survived: an all-unusable batch (error rows carrying no id,
        # with include_errors=true) points at a dead or renamed handle, not at
        # authorship.
        if unusable and not foreign:
            advice = "check whether this handle is still valid"
        elif foreign and not unusable:
            advice = "check whether this account posts its own content"
        else:
            advice = "check whether this handle is valid and posts its own content"
        print(f"  !! {PLATFORM}/{handle}: Bright Data returned {len(raw_rows)} "
              f"row(s) but none survived filtering. This run was billed and "
              f"captured nothing -- {advice}.", file=sys.stderr)

    # Rows arrive unsorted (verified live); the engine's early-stop dedup
    # assumes newest-first. Sort on the full timestamp, not the date-truncated
    # 'published': Python's sort is stable, so same-day rows sorted on
    # 'published' alone would keep Bright Data's arbitrary arrival order, which
    # can put a genuinely newer post behind ones already on disk and trip the
    # early-stop dedup before reaching it. Cap AFTER filtering so it bounds
    # retained items.
    kept.sort(key=lambda n: n["published_ts"], reverse=True)

    # B-02 (S1): saturation must be computed on the PRE-cap count, right here
    # before the client-side slice below discards everything past the cap --
    # once that slice runs, how many rows Bright Data actually returned is
    # gone. None of the four Bright Data platforms support backfill, so a
    # batch that filled the cap is a data-loss event this run made, not a
    # quiet-account day, and process_handle would otherwise report it as the
    # healthy status 'ok'.
    cap = max_items()
    # Measured against raw_rows, NOT kept: kept has already dropped unusable
    # and foreign-author rows -- X filters both -- so a batch that filled the
    # cap but included one such row would otherwise show len(kept) == cap - 1
    # and never trip the alarm, even though the same cap-truncation data loss
    # occurred (plan correction, T17 task review, 2026-08-16).
    if brightdata_job.is_saturated(len(raw_rows), cap=cap):
        oldest = min((n["published_ts"] for n in kept), default=None)
        brightdata_job.record_diagnostic(
            kind="adapter.batch_saturated", severity="error",
            source="discovery_x",
            message=(f"{PLATFORM}/{handle}: the batch filled the cap of {cap}. Posts "
                     f"older than {oldest} in this interval were dropped and there is "
                     f"no backfill path for this platform. Raise "
                     f"{MAX_ITEMS_ENV_VAR} (this increases Bright Data spend per run) "
                     f"or shorten the run interval."),
            detail={"platform": PLATFORM, "handle": handle, "cap": cap,
                    "collected": len(kept), "raw_count": len(raw_rows),
                    "oldest_kept": oldest})
        print(f"  !! {PLATFORM}/{handle}: batch filled the cap of {cap}; older posts "
              f"in this interval are unrecoverable", file=sys.stderr)

    kept = kept[:cap]

    # Overwrite, not merge: a fresh successful enumerate replaces whatever this
    # handle held, so download_item never reads a stale id.
    _ENUMERATE_CACHE[handle] = {n["id"]: n for n in kept}

    items = kept
    if keyword_filter:
        items = [i for i in items if keyword_filter.lower() in i["body"].lower()]
    return [
        # content_type is a constant. X's only type-like field is is_repost,
        # which was False even on a post the account did not write; a field
        # that is always False would be worse than absent, so it is neither
        # reported nor written to disk.
        {"id": i["id"], "title": i["title"], "published": i["published"],
         "content_type": "post"}
        for i in items
    ]


def on_disk_ids(repo_root: Path, handle: str) -> set[str]:
    directory = handle_dir(repo_root, PLATFORM, handle)
    if not directory.exists():
        return set()
    return {p.stem for p in directory.glob("*.md")}


def peek_upload_date(item_id: str) -> str | None:
    # Dead code by design: enumerate_newest_first only ever returns items
    # carrying a normalized 'published' date, so process_handle's
    # `item.get("published") or adapter.peek_upload_date(...)` never falls
    # through -- same as discovery_bluesky/instagram/linkedin.
    return None


def download_item(repo_root: Path, handle: str, item_id: str, title: str,
                  content_type: str | None = None) -> dict:
    # A missing handle or item_id is a programming error: every engine call
    # path runs enumerate_newest_first for this handle first. KeyError
    # propagates to run_discovery's per-handle error path rather than being
    # caught here, so it surfaces as a normal 'error' instead of failing
    # silently. content_type is accepted to satisfy the protocol and ignored:
    # X has no reliable type field (see enumerate_newest_first).
    cached = _ENUMERATE_CACHE[handle][item_id]

    out_dir = handle_dir(repo_root, PLATFORM, handle)
    out_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    meta = {
        "post_id": cached["id"],
        "url": cached["url"],
        "handle": handle,
        # Recorded even though the filter guarantees it matches the handle:
        # it is what makes a filtering regression detectable after the fact.
        "author": cached["author"],
        "published": cached["published"],
        "like_count": cached["like_count"],
        "comment_count": cached["comment_count"],
        "repost_count": cached["repost_count"],
        "view_count": cached["view_count"],
        "bookmark_count": cached["bookmark_count"],
        "quote_count": cached["quote_count"],
        "hashtags": cached["hashtags"],
        # Pointers, not an archive -- pbs.twimg.com and video.twimg.com URLs
        # expire. No media is downloaded.
        "photos": cached["photos"],
        "videos": cached["videos"],
        "external_url": cached["external_url"],
        "fetched_at": fetched_at,
    }
    body = cached["body"] or "(empty)"

    dest = out_dir / f"{item_id}.md"
    # Write-temp-then-rename, same as every other adapter: an interrupted
    # write must never leave a truncated file at a path on_disk_ids() would
    # treat as already-captured.
    tmp_dest = dest.with_name(dest.name + ".tmp")
    tmp_dest.write_text(artifacts.render_frontmatter(meta, body), encoding="utf-8")
    tmp_dest.replace(dest)
    return {"id": item_id, "ok": True, "published": cached["published"]}
