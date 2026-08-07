# Instagram Discovery Adapter via Bright Data

**Status:** Design (revised after Fable 5 review — see "Review history" below;
ready for implementation planning)
**Date:** 2026-08-06 (revised 2026-08-06)
**Follows from:** [`2026-08-06-paid-aggregator-cost-comparison-design.md`](2026-08-06-paid-aggregator-cost-comparison-design.md),
which recommended Bright Data over Apify for paid scraping, and
[`2026-08-06-social-platform-data-access-survey.md`](2026-08-06-social-platform-data-access-survey.md),
which scoped Instagram to "Reels/posts" and rated it medium-high risk /
~$1-2 per 1,000 items via a paid aggregator.

## Review history

A Fable 5 review of the first version of this doc found six gaps, all closed
in this revision:

1. Timeout/job-failure handling was underspecified and, as originally
   written, would have been misread as healthy or caused permanent
   handle exclusion — see "Timeout and error handling."
2. The per-run item cap didn't reconcile against the cost-comparison doc's
   platform-wide monthly budget — see "Cost model."
3. Backfill mode was claimed to need "no engine changes" without checking
   whether it actually works against a capped, newest-N-only adapter — see
   "Backfill support."
4. Date normalization from Bright Data's timestamp format to the engine's
   expected `YYYY-MM-DD` was implied but never stated — see "Bright Data
   call shape."
5. Two load-bearing assumptions about Bright Data's billing and query
   capabilities were unverified and undated — see "Verification needed
   before implementation."
6. Minor gaps (`keyword_filter` handling, cache concurrency, validate-handle
   cost) — addressed inline below.

## Purpose

Add Instagram as a third discovery-pipeline platform, alongside the existing
YouTube and Bluesky adapters, using Bright Data's Instagram Posts Scraper API
as the data source. This is a design for implementation — a subsequent
implementation plan will break it into tasks.

## Scope

- **In scope:** one new platform adapter (`discovery_instagram.py`) satisfying
  the existing `PlatformAdapter` protocol, wired into the existing
  `ADAPTERS` registry and handle-registration UI. Captures both posts and
  Reels for each tracked Instagram handle. Incremental (`process_handle`)
  and single-item validation (`process_handle_validate`) modes only.
- **Out of scope:** which specific Instagram handles to track (added later
  via the existing add-handle UI, same as any platform); video/image
  download; transcript generation (Bright Data does not provide one for
  Instagram — captions/metadata only, a real gap vs. YouTube's
  transcript-centric corpus, accepted here rather than solved); **backfill
  mode is explicitly unsupported for Instagram in this design** — see
  "Backfill support" below.

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

`discovery_engine.py`'s core algorithm (`process_handle`,
`process_handle_validate`) needs no changes to run this adapter. One small,
explicit exception applies to backfill dispatch — see "Backfill support."

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

1. **Trigger:** POST the handle's profile URL to start a collection job,
   requesting the newest `MAX_ITEMS_PER_RUN` items only (see "Verification
   needed" — this request-time limit is the load-bearing assumption behind
   the whole cost model and must be confirmed against Bright Data's actual
   API before implementation). Returns a snapshot/job ID.
2. **Poll:** GET the job's status on an interval until it reports `ready`
   or `failed`, bounded by a timeout (see "Timeout and error handling").
3. **Fetch:** GET the finished job's result batch — posts and Reels
   together, each row already carrying id, caption, publish date, type
   (post/reel), and engagement counts. No further per-item network call is
   needed to get full content, unlike YouTube's enumerate-then-fetch split.

**Date normalization (gap 4):** Bright Data's publish-date field is expected
to be a full timestamp, not the bare `YYYY-MM-DD` string
`discovery_engine.py` requires (`process_handle` calls
`datetime.strptime(published, "%Y-%m-%d")` — an unnormalized value raises
and surfaces as a per-handle error). `enumerate_newest_first` MUST truncate
to the first 10 characters, the same normalization
`discovery_bluesky.py`'s `created[:10]` already performs, before returning
each item's `published` field. If a row is ever missing a publish date
entirely, drop it from the returned list and log a warning rather than
passing `None` through — a `None` published date on a brand-new handle
counts against `NEW_HANDLE_UNDATED_STOP_GRACE` (5), and since the cap
already bounds the batch to `MAX_ITEMS_PER_RUN` items, silently losing a few
undated rows is a safe, bounded degradation rather than the unbounded-walk
risk that constant exists to guard against.

**`keyword_filter` (gap 6a):** Applied client-side after fetch, the same way
`discovery_bluesky.py` does it (`keyword_filter.lower() in item["title"].lower()`)
— a case-insensitive substring match against the caption. Bright Data's
trigger API is not assumed to support server-side keyword filtering; this
is listed alongside the other unverified assumptions below.

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
  writes the `.md` file. If the cache has no entry for `handle`, or the
  entry exists but doesn't contain `item_id`, this is treated as an error
  (raise `KeyError`) rather than silently degraded output — it lands in
  `discovery_engine.py`'s existing per-handle `except Exception` handler
  (`run_discovery`'s per-handle loop) and is recorded as a normal `error`
  result, safe-fail rather than fail-silent.
- Each successful `enumerate_newest_first` call **overwrites** any prior
  cache entry for that handle; a failed/timed-out call (see below) does not
  write to the cache at all, so it can never clobber a previous successful
  batch still needed by an in-flight `download_item` call.

**Cache concurrency (gap 6b):** the cache is per-process and keyed by
handle only, with no run-id component. Within a single cron run this is
safe — handles are processed sequentially in one thread, and each handle's
`enumerate` immediately precedes its own `download_item` calls with no other
adapter call for that same handle in between. The one scenario where two
calls for the *same* handle could interleave is a `validate_handle` request
(which bypasses the single-flight run lock — see `discovery_engine.py`'s
`run_discovery`) arriving in the same process while an incremental run is
already processing that same handle — e.g. a threaded web server handling
both. Python's GIL makes the dict assignment itself atomic (no corruption),
but the two calls' batches could still overwrite one another, and a
`download_item` call could then read the wrong batch. The failure mode is
bounded and safe: either the id it's looking for still happens to be in
the other run's batch (wrong-but-plausible — accepted risk, low probability,
not solved here) or it isn't, which raises `KeyError` and reports a normal
per-handle `error`, not silent corruption. This is an accepted, explicitly
documented limitation, not a solved problem — a `(handle, run_id)`-keyed
cache would close it but requires threading `run_id` through the
`PlatformAdapter` Protocol, which is out of scope for a single-adapter
change.

- `peek_upload_date(item_id)` returns `None` unconditionally. Every item
  from `enumerate_newest_first` already carries a `published` date (unlike
  YouTube's flat-playlist listing, which doesn't), so `process_handle`'s
  `item.get("published") or adapter.peek_upload_date(item_id)` never falls
  through to it, given the date-normalization guarantee above — same
  dead-code-by-design as `discovery_bluesky.peek_upload_date`.

## Cost model

**Gap 2 fix — the original per-handle framing didn't reconcile against the
platform-wide budget.** The cost-comparison doc assumed **1,000
items/month total for Instagram**, across however many handles are tracked
— not 1,000 per handle. At the original default of `MAX_ITEMS_PER_RUN = 25`
run daily, a single handle alone consumes `25 × 30 ≈ 750` items/month —
about 75% of the entire platform budget from one handle. This revision
lowers the default and states the reconciling arithmetic explicitly:

- **`MAX_ITEMS_PER_RUN` default: 10** (down from 25). At a daily cron,
  that's `10 × 30 = 300` items/month per handle — up to **~3 handles**
  fit inside the cost-comparison doc's 1,000/month assumption at the
  default cap.
- **The cap must be re-tuned as handles are added.** The relationship is
  `platform_monthly_cost ≈ handle_count × 30 × MAX_ITEMS_PER_RUN × per_item_cost`.
  Before registering a 4th Instagram handle, either lower
  `MAX_ITEMS_PER_RUN` further (e.g. 7 for 4 handles, keeping the total near
  300/handle-equivalent) or consciously accept a larger monthly bill —
  this is a manual judgment call at handle-registration time, not something
  the adapter enforces automatically. A future enhancement (not in this
  design) could divide a shared budget across active handle count
  automatically; not built here per YAGNI, since there are currently zero
  Instagram handles registered.
- **Bright Data bills per job/record returned, not per genuinely-new
  item** (see "Verification needed" — this too needs confirming). Local
  dedup via `on_disk_ids` still prevents re-downloading or re-writing files
  for posts already on disk, but that happens *after* the paid collection
  job has already returned those posts — every daily run re-pays to
  re-collect the same top-N posts even on a day with zero new content. The
  cap bounds this, it doesn't eliminate it; there is no cheaper
  "only fetch what changed" mode in Bright Data's API as currently
  understood.
- **A timed-out or failed job is paid-for but unusable** (assuming Bright
  Data charges for job execution regardless of outcome — also unverified),
  and gets re-paid on the next scheduled retry. This is accepted as normal
  operational cost, same category as any other transient failure.

Actual billing should be watched once live; `MAX_ITEMS_PER_RUN` is the
lever to pull if usage runs hotter than expected.

## Backfill support

**Gap 3 fix.** `process_handle_backfill` filters `enumerate_newest_first`'s
output by a caller-supplied date window, but this adapter's enumerate only
ever returns the newest `MAX_ITEMS_PER_RUN` items — any backfill window
older than that cutoff would trigger a full paid Bright Data job and return
zero matching results, silently, with no historical reach and no warning.

This design does not attempt to solve historical backfill for Instagram —
Bright Data's newest-N-only query shape (per "Verification needed") isn't a
good fit for it, and building date-ranged historical fetch is a separate,
larger problem than this adapter's scope. Instead, backfill is **explicitly
rejected** for Instagram handles:

- `run_discovery_cron.py`'s backfill entry point (the CLI/web code path that
  constructs `mode="backfill"` calls into `run_discovery`) gains a guard:
  before dispatching, check the target handle's platform against a small
  `BACKFILL_SUPPORTED_PLATFORMS = {"youtube", "bluesky"}` set, and reject
  the request with a clear "Instagram does not support backfill" message if
  it doesn't match — rather than letting it reach the adapter and silently
  waste a paid job. This is the one small change outside
  `discovery_instagram.py` itself, replacing the original (incorrect) claim
  that no changes anywhere else were needed.
- If a future need for Instagram historical backfill arises, that's a
  separate design (likely requiring Bright Data's date-ranged collection
  parameters, if they exist — unverified here).

## Timeout and error handling

**Gap 1 fix.** The original version of this doc said a timeout or
job-failure would make `enumerate_newest_first` return an empty list, which
`process_handle` and `process_handle_validate` would then treat as "no
results" — but that claim was wrong in both call paths:

- In `process_handle` (normal/incremental runs), an empty list makes
  `status = "no_new_content"` — a **healthy** status, indistinguishable
  from "this handle genuinely posted nothing new today." A paid-but-failed
  Bright Data job would be invisible in run records and the discovery
  email, silently masking real failures.
- In `process_handle_validate` (used once, when a handle is first
  registered), an empty `enumerate_newest_first` result makes the handle
  `status = "invalid"` **and auto-excludes it from all future runs**
  (`discovery_engine.py`'s `run_discovery`, `mode == "validate_handle"`
  branch). A transient Bright Data timeout at registration time would
  permanently remove the handle, not "retry next day" as originally
  claimed.

**Fix:** `enumerate_newest_first` distinguishes "the job failed to
complete" from "the job completed and the profile genuinely has zero
posts":

- **Poll timeout** (job never reaches `ready`/`failed` within the bounded
  window, e.g. 5 minutes) → **raise** an exception (a dedicated
  `BrightDataJobTimeout` or similar, not a bare `Exception`, so it's
  identifiable in logs/error messages) rather than returning `[]`.
- **Job reports `failed`** (Bright Data-side error — invalid/private
  profile, API error) → **raise** as well, same reasoning.
- **Job reports `ready` with zero rows** (profile exists, has no posts, or
  every returned row lacked a usable date after normalization) → return
  `[]`, the one case that correctly means "nothing to report."

With this fix, a timeout/failure during `process_handle` now propagates up
through `_process_one_handle` into `run_discovery`'s per-handle
`except Exception` handler, which already records `status = "error"` with
the exception message — exactly the "retried next day" behavior originally
claimed, now actually true.

**`validate_handle` mode is a known, pre-existing limitation, not a new
one.** Raising during `process_handle_validate` still lands in that mode's
own outer `except Exception` handler, which marks the handle `invalid` and
excludes it — this is *identical* to how a transient network error during
validation already behaves for YouTube and Bluesky today; it is not
Instagram-specific and not introduced by this design. If a validation
transiently fails against Bright Data, the handle will need to be
re-registered by hand — the same recovery path that already applies to
every other platform. No engine change is proposed to fix this pre-existing
behavior; it's called out here only so the design doesn't misstate it.

## Verification log (2026-08-06, post-implementation)

Checked against the Bright Data dashboard's generated API snippets for the
Instagram Posts product plus the published dataset field list. Three of this
design's assumptions were wrong and are now fixed in `discovery_instagram.py`:

- **`[T]` Dataset id is `gd_lk5ns7kz21pck8jpis`** (2026-08-06, dashboard
  snippet) — one dataset serves both discover-by-profile and
  collect-by-post-URL; `type`/`discover_by` select the mode.
- **`[T]` A newest-N-by-profile job requires `type=discover_new` and
  `discover_by=url`** on the trigger query string (2026-08-06, dashboard
  snippet + Bright Data trigger-collection docs). The original implementation
  omitted both, which would have run a collect-by-page job against a profile
  URL — a paid job returning the wrong shape.
- **`[T]` The newest-N limit is real and has two levers** (2026-08-06):
  `limit_per_input` as a trigger query param (server-side, per input) and
  `num_of_posts` as a dataset input field. Both are now set to
  `MAX_ITEMS_PER_RUN`. This confirms the cost model's load-bearing assumption
  below.
- **`[T]` The caption text field is `description`, not `caption`**
  (2026-08-06, published Instagram-Posts field list). `post_id`,
  `date_posted`, `content_type`, `url`, `likes`, `num_comments` were all
  correct. The `caption` misread was the dangerous one: it drops no rows, so
  it would have written one `(empty)` file per already-paid-for post.
- **`[T-unverified, 2026-08-06]`** Billing granularity (per record vs. per
  job minimum) and whether failed/timed-out jobs are charged are still
  unconfirmed — watch the first live runs against the dashboard's usage page.

### Live smoke test (2026-08-06, snapshot `sd_msi9anpb4jxhh8g1x`)

A real 3-record discovery job against `instagram.com/nike` — 3 records, 0
errors, ~84s collection time. Findings, all now fixed and pinned by tests:

- **`[T]` `/trigger` accepts the bare-array body.** Closes the open question
  above; the `{"input": [...]}` object form is `/scrape`-only. The async
  trigger → poll → fetch flow is confirmed end to end, with `progress`
  returning `status: running` → `ready` as assumed.
- **`[T]` `limit_per_input` is honored** — `limit_per_input=3` returned
  exactly 3 records. The cost model's load-bearing assumption holds.
- **`[T]` `date_posted` is a US-format local timestamp, `07/23/2026
  16:00:22` — NOT ISO 8601.** This design's "truncate to the first 10
  characters" rule (gap 4) was wrong, and wrong in the most dangerous
  direction: `"07/23/2026"` fails `strptime(..., "%Y-%m-%d")`, so *every*
  row was dropped as undated, `enumerate_newest_first` returned `[]`, and
  `process_handle` recorded a healthy `no_new_content` for a batch that had
  already been paid for. Date parsing now lives in `_parse_published`, which
  accepts the real format and keeps ISO as a fallback.
- **`[T]` `content_type` includes `Carousel`**, not just `Post`/`Reel`, and
  is display-cased. Normalized to lowercase; the file format below is
  updated.
- **`[T]` No timezone accompanies `date_posted`.** Only dates are compared,
  so the worst case is an off-by-one at a midnight boundary.

Operational note: Bright Data's domains are blocked by DNS-filtering
resolvers that categorize proxy/scraping infrastructure — a live run needs
that path clear or every job fails at name resolution before any HTTP call.

## Verification needed before implementation (gap 5)

Two assumptions this whole design leans on are unverified against Bright
Data's actual current API/dashboard, and should be confirmed as a first
implementation-planning step, not assumed:

- **`[T-unverified, 2026-08-06]`** Bright Data's trigger API supports
  limiting a single collection job to the newest N posts. If it doesn't
  and instead always returns full recent history per profile, the entire
  cost/cap model above is invalid and needs rework before implementation.
- **`[T-unverified, 2026-08-06]`** Bright Data bills per record returned
  with no per-job minimum charge, and charges for failed/timed-out jobs
  the same as successful ones. If there's a per-job minimum, the cost
  model underestimates cost at low volume; if failed jobs are free, the
  "timed-out job is paid-for but unusable" caveat is moot.

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
content_type: post | reel | carousel
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
HTTP layer (no real Bright Data calls), covering:

- Job trigger/poll/fetch happy path, including date truncation to
  `YYYY-MM-DD`.
- Poll timeout **raises** (not returns `[]`) — verifying the gap-1 fix.
- Job-`failed` status **raises**.
- Job `ready` with zero rows returns `[]` cleanly.
- `download_item` reads from the enumerate cache without an extra network
  call; a cache miss (wrong handle or missing item_id) raises rather than
  degrading silently.
- `on_disk_ids` dedup.
- `MAX_ITEMS_PER_RUN` actually bounds the trigger request (once the
  "newest N only" capability is verified — see above — this test also
  documents that verified behavior).
- `keyword_filter` applied client-side against caption text.
- Credential lookup (env var vs. file, matching
  `test_discovery_youtube_api.py`'s coverage of the same pattern).
- Backfill-rejection guard at the `run_discovery_cron.py` entry point
  (Instagram handle + `mode="backfill"` → rejected before any adapter
  call).

## Non-goals

This does not implement Instagram Story capture (Stories aren't part of
Bright Data's Posts Scraper API and expire, making them a poor fit for an
archival pipeline anyway), does not add a generic multi-platform scraping
abstraction (the prior survey doc already recommended against that), does
not implement historical backfill for Instagram (see "Backfill support"),
does not automatically re-tune `MAX_ITEMS_PER_RUN` as handles are added
(manual judgment call, per "Cost model"), and does not verify which
currently-tracked creators are actually active on Instagram — that remains
a prerequisite for actually registering any Instagram handles once this
ships.
