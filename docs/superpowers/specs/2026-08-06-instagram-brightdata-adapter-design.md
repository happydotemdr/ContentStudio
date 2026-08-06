# Instagram Discovery Adapter via Bright Data

**Status:** Design (approved, ready for implementation planning)
**Date:** 2026-08-06
**Follows from:** [`2026-08-06-paid-aggregator-cost-comparison-design.md`](2026-08-06-paid-aggregator-cost-comparison-design.md),
which recommended Bright Data over Apify for paid scraping, and
[`2026-08-06-social-platform-data-access-survey.md`](2026-08-06-social-platform-data-access-survey.md),
which scoped Instagram to "Reels/posts" and rated it medium-high risk /
~$1-2 per 1,000 items via a paid aggregator.

## Purpose

Add Instagram as a third discovery-pipeline platform, alongside the existing
YouTube and Bluesky adapters, using Bright Data's Instagram Posts Scraper API
as the data source. This is a design for implementation — a subsequent
implementation plan will break it into tasks.

## Scope

- **In scope:** one new platform adapter (`discovery_instagram.py`) satisfying
  the existing `PlatformAdapter` protocol, wired into the existing
  `ADAPTERS` registry and handle-registration UI. Captures both posts and
  Reels for each tracked Instagram handle.
- **Out of scope:** which specific Instagram handles to track (added later
  via the existing add-handle UI, same as any platform); video/image
  download; transcript generation (Bright Data does not provide one for
  Instagram — captions/metadata only, a real gap vs. YouTube's
  transcript-centric corpus, accepted here rather than solved).

## Architecture

`pipeline_app/discovery_instagram.py` mirrors the shape of
`discovery_bluesky.py`, the simplest existing adapter: no yt-dlp subprocess,
no multi-tab enumeration, a single external API as the whole data source.
It implements the same four functions the `PlatformAdapter` Protocol in
`discovery_engine.py` requires:

- `on_disk_ids(repo_root, handle) -> set[str]`
- `enumerate_newest_first(handle, keyword_filter) -> list[dict]`
- `peek_upload_date(item_id) -> str | None`
- `download_item(repo_root, handle, item_id, title, content_type=None) -> dict`

`discovery_engine.py` itself needs no changes — `process_handle`,
`process_handle_backfill`, and `process_handle_validate` are already
platform-agnostic and drive any adapter satisfying the Protocol.

Two wiring points, both additive, matching how Bluesky was added:

1. `run_discovery_cron.py`'s adapter-registry function gains
   `"instagram": discovery_instagram` alongside the existing `"youtube"` and
   `"bluesky"` entries.
2. `pipeline_app/templates/discovery_handles.html` gains
   `<option value="instagram">Instagram</option>` in the platform `<select>`.

## Credentials

Same lookup pattern as `discovery_youtube_api.api_key()` and
`discovery_notify.api_key()`: an env var first, then a gitignored file, so
the scheduled task (which inherits the User environment) and local manual
runs both work with no code difference.

- `BRIGHTDATA_API_KEY` env var, else `brightdata_api_key.txt` (gitignored,
  sibling to the existing `youtube_api_key.txt` / `resend_api_key.txt`) —
  the Bright Data account's API token.
- A dataset ID for the Instagram Posts Scraper API product — not a secret,
  a one-time value obtained from the Bright Data dashboard when the product
  is provisioned. Stored as a module constant in `discovery_instagram.py`
  with a comment pointing to where to find/regenerate it.

`.gitignore` gains `brightdata_api_key.txt`, matching the existing entries
for `youtube_api_key.txt`, `resend_api_key.txt`, and `cookies.txt`.

## Bright Data call shape

Bright Data's Instagram Posts Scraper API is asynchronous — unlike
YouTube's Data API or Bluesky's AppView, which answer a request directly, it
is trigger → poll → fetch:

1. **Trigger:** POST the handle's profile URL to start a collection job.
   Returns a snapshot/job ID.
2. **Poll:** GET the job's status on an interval until it reports `ready`
   (or `failed`).
3. **Fetch:** GET the finished job's result batch — posts and Reels
   together, each row already carrying id, caption, publish date, type
   (post/reel), and engagement counts. No further per-item network call is
   needed to get full content, unlike YouTube's enumerate-then-fetch split.

This shape does not map cleanly onto the adapter Protocol's implicit
assumption (visible in `discovery_bluesky.py`) that `enumerate_newest_first`
is cheap/free to call and `download_item` can re-fetch per item. Because
Bright Data bills per job/record, calling the API once during enumerate and
again per item during download would double-pay for the same posts. Instead:

- `enumerate_newest_first(handle, keyword_filter)` runs the full
  trigger-poll-fetch cycle **once** for the handle, parses the result batch
  into the `{id, title, published, content_type}` shape the engine expects,
  and stores the full parsed rows in a **module-level cache dict keyed by
  handle**, scoped to the current process (i.e., the current run).
- `download_item(repo_root, handle, item_id, title, content_type)` reads the
  matching row from that cache — no additional Bright Data call — and
  writes the `.md` file. If the cache has no entry for `handle` (e.g.
  `download_item` were somehow called without a prior `enumerate_newest_first`
  in the same process), it is a programming error, not a runtime condition to
  handle gracefully — matching how `discovery_bluesky.py`'s cache-free
  re-fetch already assumes `enumerate_newest_first` succeeded.
- `peek_upload_date(item_id)` returns `None` unconditionally. Every item
  from `enumerate_newest_first` already carries a `published` date (unlike
  YouTube's flat-playlist listing, which doesn't), so `process_handle`'s
  `item.get("published") or adapter.peek_upload_date(item_id)` never falls
  through to it — same dead-code-by-design as `discovery_bluesky.peek_upload_date`.

## Per-run cap and cost behavior

`enumerate_newest_first` requests only the newest `MAX_ITEMS_PER_RUN` items
per handle (a module constant, default 25, tunable) from Bright Data's
collection job — bounding both the job's payload size and worst-case cost
per handle per run, independent of how many Instagram handles get added
later.

**Cost caveat to design around, not solve:** Bright Data bills per
job/record returned, not per genuinely-new item. Local dedup via
`on_disk_ids` still prevents re-downloading or re-writing files for posts
already on disk, but it happens *after* the paid collection job has already
returned those posts — every daily run re-pays to re-collect the same top-N
posts even on a day with zero new content. The per-run cap is what bounds
this cost, not incremental fetching; there is no cheaper "only fetch what
changed" mode in Bright Data's API. This should be watched against actual
billing once live, and `MAX_ITEMS_PER_RUN` is the lever to pull if usage
runs hotter than the cost doc's 1,000/month-per-platform assumption.

## Timeout and error handling

The poll step runs for a bounded window (constant, e.g. 5 minutes) rather
than indefinitely. If the job hasn't reached `ready` by then,
`enumerate_newest_first` logs a warning to stderr (matching the existing
`discovery_youtube.py` / `discovery_bluesky.py` style) and returns an empty
list — which `process_handle` and `process_handle_validate` already treat as
"enumeration returned nothing," surfacing as `handle_not_found` /
`error` for that run via the existing per-handle error path in
`discovery_engine.py`. No new error-handling branch is needed there; the
handle is simply retried on the next scheduled run, same as any other
transient enumeration failure today.

A job that reports `failed` (Bright Data-side error, e.g. invalid/private
profile) is treated identically to a timeout: empty list, logged warning,
existing error path.

## File format

One `.md` file per post/Reel, written into
`output/brand-intel/instagram/<slugified-handle>/` (via the existing
`discovery_paths.handle_dir`, unchanged), named `<post_id>.md`. Frontmatter
plus body, matching `discovery_bluesky.py`'s structure rather than
`discovery_youtube.py`'s (no transcript section, since there is no
transcript):

```
---
post_id: <string>
url: <string>
handle: <string>
content_type: post | reel
published: <YYYY-MM-DD>
like_count: <int | null>
comment_count: <int | null>
fetched_at: <ISO 8601 UTC>
---

<caption text, or "(empty)">
```

Write-temp-then-rename on save, same as every other adapter, for the same
reason: an interrupted write must never leave a truncated file at a path
`on_disk_ids()` would treat as already-captured.

## Testing

Following `test_discovery_bluesky.py`'s pattern: unit tests against a fake
HTTP layer (no real Bright Data calls), covering — job trigger/poll/fetch
happy path, poll timeout returns empty list, job-failed returns empty list,
`download_item` reads from the enumerate cache without an extra network
call, `on_disk_ids` dedup, and the `MAX_ITEMS_PER_RUN` cap actually bounding
the request. Credential lookup (env var vs. file, matching
`test_discovery_youtube_api.py`'s coverage of the same pattern in
`discovery_youtube_api.py`).

## Non-goals

This does not implement Instagram Story capture (Stories aren't part of
Bright Data's Posts Scraper API and expire, making them a poor fit for an
archival pipeline anyway), does not add a generic multi-platform scraping
abstraction (the prior survey doc already recommended against that), and
does not verify which currently-tracked creators are actually active on
Instagram — that remains a prerequisite for actually registering any
Instagram handles once this ships.
