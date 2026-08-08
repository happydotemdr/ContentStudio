# X.com Discovery Adapter via Bright Data

**Status:** Design (schema verified against six live jobs before writing — see
"Live verification" below; ready for implementation planning)
**Date:** 2026-08-08
**Follows from:** [`2026-08-07-linkedin-brightdata-adapter-design.md`](2026-08-07-linkedin-brightdata-adapter-design.md),
whose adapter this one is modelled on and shares `brightdata_job.py` with;
[`2026-08-06-instagram-brightdata-adapter-design.md`](2026-08-06-instagram-brightdata-adapter-design.md);
and [`2026-08-06-social-platform-data-access-survey.md`](2026-08-06-social-platform-data-access-survey.md),
which rated X "High cost or high risk" and noted that every free path requires
an authenticated session.

## Purpose

Add X.com as a fifth discovery-pipeline platform, alongside YouTube, Bluesky,
Instagram, and LinkedIn, using Bright Data's X Posts dataset
(`gd_lwxkxvnf1cynvib9co`) as the data source. Captured content serves the
existing `output/brand-intel/` corpus, competitive monitoring, and raw material
for the `social-repurpose` stage.

## Method note: verification came first

The Instagram adapter shipped and merged with four wrong assumptions, three of
which failed silently. The LinkedIn design was therefore written after four live
jobs, and that check killed one of the three modes originally requested.

This design was written after **six live jobs (19 records)**. That check killed
one of the two datasets requested, killed backfill outright, and turned up a
field (`is_repost`) that looks exactly like the right filter and is not. Every
field mapping below is `[T]`-marked from observed data, not from the published
field list.

## Risk posture (stated, not solved)

The platform survey rated X **high cost or high risk**: the free API tier was
eliminated in February 2026, Nitter is effectively dead, and every maintained
open-source scraper requires login cookies. Bright Data is the party performing
collection and carrying that exposure; this project's posture is that of a data
purchaser.

The practical consequence is the same **vendor-continuity risk** LinkedIn
carries — this adapter can go dark on short notice in a way the YouTube and
Bluesky adapters cannot. The design responds by making failure loud and cheap
(raise, never return `[]` silently; a hard per-run cap), not by attempting to
mitigate a legal exposure that is not an engineering problem.

## Scope

- **In scope:** one platform adapter, `x`, over the X Posts dataset in
  `discover_by=profile_url` mode, satisfying the existing `PlatformAdapter`
  protocol. Incremental (`process_handle`) and single-item validation
  (`process_handle_validate`) modes only.
- **Out of scope:** the X Profiles dataset (**dropped on evidence** — see
  "Rejected on evidence"), date-ranged backfill (**proven broken**),
  `profiles_array` batching, collect-by-single-post-URL, media download, reply
  and thread reconstruction, and which specific handles to track.

## Live verification (2026-08-08)

Six real jobs through the same async `/trigger` → `/progress` → `/snapshot`
path the adapter will use — not the dashboard snippets' synchronous `/scrape`.

| # | Dataset | Mode | Input | Snapshot | Result | Latency |
|---|---|---|---|---|---|---|
| 1 | Posts | `profile_url`, limit 3 | `x.com/CNN` | `sd_mskd8iv12ivrnbejlz` | 3 records, 0 errors | 75s |
| 2 | Posts | `profile_url`, limit 3 | `x.com/elonmusk` | `sd_mskdach6430yb7zfl` | 3 records, 0 errors | 127s |
| 3 | Profiles | `user_name`, limit 3 | `CNN` | `sd_mskdd54sbcdofoxkm` | 1 record (20 embedded posts) | 22s |
| 4 | Posts | `profile_url`, limit 10 | `x.com/elonmusk` | `sd_mskdghugb6u3685n6` | 10 records | 243s |
| 5 | Posts | `profile_url`, limit 5, dated | `x.com/CNN`, Jun 1–3 | `sd_mskdls3f26klcqyxk9` | 1 error row | 99s |
| 6 | Profiles | `user_name`, limit 1 | `elonmusk` | `sd_mskdnzyr1rfyokzmhd` | 1 record (99 embedded posts) | 15s |

### Confirmed sound

- **`[T]` `id` is a JSON string**, not a number — `"id": "2085896713185714235"`.
  This matters: `on_disk_ids()` compares against filename stems, so a numeric id
  would never match and every run would re-download and re-pay in silence. Same
  hazard LinkedIn checked for.
- **`[T]` `date_posted` is genuine ISO 8601 UTC** — `2026-08-08T01:11:45.000Z`.
  Truncation to `[:10]` is correct, as with LinkedIn and unlike Instagram's
  US-format local timestamp. Three Bright Data products, two date formats — which
  is itself the reason none can be assumed from another.
- **`[T]` `description` is the post body**, plain text with entities left as X
  serves them (`&amp;` observed) and `t.co` links inline.
- **`[T]` `limit_per_input` is honored exactly** — 3→3, 10→10.
- **`[T]` The async trigger → poll → fetch flow with a bare-array body works**,
  identical to Instagram and LinkedIn. `brightdata_job.py` needs no change.
- **`[T]` `include_errors=true` yields error rows** carrying `error` and
  `error_code` with every content field null (job 5). They have no `id`, so the
  existing id guard drops them without special-casing.

### Rejected on evidence — the X Profiles dataset

The Profiles dataset (`gd_lwxmeb2u1cniijd7t4`) returns **one record with an
embedded `posts` array**, and `/progress` counts it as `records: 1`. At an
apparent 20 posts per billed record it looked roughly 20× cheaper than the Posts
route, and several times faster (15–22s against 75–243s).

**`[T]` Its posts array is inconsistent in depth, recency, and ordering:**

| Input | Posts | Date span | Newest | Sorted? |
|---|---|---|---|---|
| `CNN` | 20 | Aug 7–8, 2026 | 2026-08-08 (12s old) | yes, desc |
| `elonmusk` | 99 | Oct 2018 – Sep 2025 | **2025-09-21** | no |

For elonmusk the array's newest post was **eleven months stale**, while the
Posts dataset returned that same account's posts from the same morning. There is
no field on the response that distinguishes the two behaviors, and the embedded
posts carry **no author field at all**, so the contamination filter described
below could not be applied.

**This dataset is dropped from scope.** Had it shipped, it would have failed the
way this project keeps getting burned: jobs succeed, records land, files are
written, billing accrues, and a handle silently captures nothing newer than last
year while the engine reports `no_new_content`. Cheap and silently stale is
worse than expensive and correct.

### Broken — date-ranged backfill

**`[T]` `start_date`/`end_date` do not work through `/trigger`.** Job 5, a
two-day window three months back against an account that posts hundreds of times
a day, returned a single error row:

```json
{"error": "No public posts were found in the profile for the specified period.",
 "error_code": "dead_page"}
```

Unlike LinkedIn — where the same parameters were left untested and flagged as
the one plausible future path to backfill — X's are tested and do not work.
There is no backfill path here to leave open.

### Constrained — profile mode returns a timeline, not authorship

**`[T]` `discover_by=profile_url` returns the tracked account's timeline,
including posts written by other people.** Job 4's ten rows for `elonmusk`
included one authored by `arctotherium42` (`user_posted`).

**`[T]` `is_repost` was `False` on that foreign row**, and `False` on all 16 post
records observed. It is the field a maintainer will reach for and it does not
work. **The filter is `user_posted`**, matching LinkedIn's `user_id` filter in
purpose and consequence.

**Decision: keep only rows whose `user_posted` matches the tracked handle**
case-insensitively, so `output/brand-intel/x/<handle>/` keeps the meaning every
other adapter's directory has — "things this account wrote".

### Other observed facts

- **`[T]` `description` is nullable.** Three of elonmusk's ten rows were
  media-only posts with `description: null`. See "Media-only posts" below.
- **`[T]` Rows arrive badly unsorted.** Job 4 returned Aug 6, Aug 8, Aug 7,
  Aug 6, Aug 7, Aug 8, Aug 3, Aug 1, Aug 4, Aug 8. `enumerate_newest_first` must
  sort; the engine's early-stop dedup assumes newest-first.
- **`[T]` `url` is inconsistent across accounts** —
  `https://twitter.com/759251/status/<id>` (legacy domain, numeric profile id)
  for CNN versus `https://x.com/elonmusk/status/<id>` for elonmusk. Never key
  identity on a URL; `id` is the key.
- **`[T]` Every post row denormalizes profile state** — `followers`,
  `following`, `posts_count`, `biography`, `is_verified`, `verification_type`.
  Deliberately not stored: it is profile state, not post data, and would repeat
  on every file.
- **`[T]` Latency scales sharply with `limit_per_input`** — 71–127s at 3,
  **243s at 10**. Ten is the production setting, so the inherited 300s poll
  timeout leaves almost no margin.
- **`[T]` `quoted_post` is always a struct**, `{"photos": null, "videos": null}`
  in all 16 post records, never a text quote. Not stored.
- **`[T-unverified, 2026-08-08]`** Billing granularity — per record vs. per-job
  minimum, and whether failed or error-row jobs are charged — remains
  unconfirmed, the same open item Instagram and LinkedIn left. `/progress`
  reports a `records` count per snapshot, which is suggestive but is not a
  price. Six X jobs are now on the dashboard's usage page to check against.

## Architecture

### New: `pipeline_app/discovery_x.py`

A plain module with module-level functions and a module-level enumerate cache,
matching `discovery_instagram.py`. LinkedIn's bound-instance class exists
because two platforms share one implementation and a person and a company can
have the same slug; X has one working mode and needs neither.

### Not modified

- **`brightdata_job.py`** — trigger/poll/fetch and the raise-never-return-`[]`
  discipline already cover this dataset exactly. No change.
- **`discovery_engine.py`** — `BACKFILL_SUPPORTED_PLATFORMS` is a whitelist of
  `{"youtube", "bluesky"}`, so `x` is already rejected from backfill with a
  logged skip and no adapter call.

### Modified

- `run_discovery_cron.py`'s `build_adapters()` — adds `"x": discovery_x`.
- `templates/discovery_handles.html` — one `<option value="x">X (Twitter)</option>`.
  The label carries "(Twitter)" because a bare "X" is not self-evident in a
  dropdown; the stored value is `x`.

### Handle model

Handles are bare, `@`-stripped — `CNN`, `elonmusk` — resolving to
`https://x.com/<handle>` and, via the existing
`handle_dir(repo_root, "x", handle)`, to `output/brand-intel/x/<handle>/`. No
path special-casing.

Storing a pasted profile URL as the handle is rejected for the reason LinkedIn
rejected it, with an extra one here: X serves both `x.com` and `twitter.com`
forms of the same account, so two rows could describe one account.

## Data contract

| Output field | Source | Note |
|---|---|---|
| `post_id` | `id` | string; the sole identity key |
| `published` | `date_posted[:10]` | ISO 8601 Z, verified |
| body | `description` | **nullable**; `"(empty)"` when null |
| `title` | first line of `description`, else `id`; truncated to 60 | |
| `author` | `user_posted` | drives the filter |
| `url` | `url` | informational; domain varies by account |
| `like_count` | `likes` | |
| `comment_count` | `replies` | named for cross-platform consistency |
| `repost_count` | `reposts` | |
| `view_count` | `views` | nullable on very fresh posts |
| `bookmark_count` | `bookmarks` | |
| `quote_count` | `quotes` | |
| `hashtags` | `hashtags` | list or null |
| `photos` | `photos` | list of expiring CDN URLs |
| `videos` | `videos[].video_url` | flattened; the raw value is a list of structs carrying `duration` |
| `external_url` | `external_url` | outbound link; often null |

**A row is dropped if** it has no `id` (which is what discards
`include_errors` error rows), has no parseable `published`, or its
`user_posted` does not match the tracked handle case-insensitively. Drop counts
go to stderr, matching Instagram and LinkedIn.

**Order of operations:** normalize → drop → **sort newest-first** → cap to
`MAX_ITEMS_PER_RUN` → apply `keyword_filter`. The sort is load-bearing (rows
arrive unsorted, verified); the cap is applied after filtering so it bounds
retained items; `keyword_filter` is a case-insensitive substring match against
`description`.

Media URLs are stored as **pointers, not an archive** — `pbs.twimg.com` and
`video.twimg.com` links expire. No media is downloaded.

### Media-only posts

A row with `description: null` is **kept**, with body `"(empty)"`, matching what
Instagram and LinkedIn already write for empty text. Three of ten observed rows
for one account were media-only, so this is a common case rather than an edge
one, and the frontmatter still carries the published date, six engagement
counts, and the media URLs — enough for the competitive-monitoring use case even
with no text.

Dropping them was considered and rejected: it would pay for rows it discards and
would let a media-heavy day trigger the "billed and captured nothing" warning
for what is actually normal behavior.

### File format

One `.md` per post, named `<id>.md`, written with the existing
write-temp-then-rename so an interrupted write never leaves a truncated file at
a path `on_disk_ids()` would treat as captured:

```
---
post_id: <string>
url: <string>
handle: <tracked handle>
author: <user_posted>
published: <YYYY-MM-DD>
like_count: <int | null>
comment_count: <int | null>
repost_count: <int | null>
view_count: <int | null>
bookmark_count: <int | null>
quote_count: <int | null>
hashtags: [<string>, ...]
photos: [<url>, ...]
videos: [<url>, ...]
external_url: <string | null>
fetched_at: <ISO 8601 UTC>
---

<description, or "(empty)">
```

`author` is recorded even though the filter guarantees it matches the handle: it
is what makes a filtering regression detectable after the fact.

There is no `content_type` key. The dataset's only type-like field is
`is_repost`, which is demonstrably unreliable (see above); a field that is
always `False` would be worse than absent, because it would read as "this
account never reposts". `enumerate_newest_first` returns `content_type: "post"`
to satisfy the engine's item shape, and that constant is not written to disk.

## Cost model

`MAX_ITEMS_PER_RUN = 10`, daily — matching Instagram and LinkedIn, one constant,
one cadence, no engine change. That is 300 records/month per handle. The survey
did not price Bright Data's X product specifically; at the ~$1.50/1k low end of
its aggregator range that is **~$0.45/month per handle**.

Two effects are real and unfixed:

- **The author filter pays for rows it discards.** It runs after billing. At the
  observed 1-in-10 contamination rate, effective cost per retained file is
  ~1.1× — much milder than LinkedIn's observed 1-in-3, but an account that
  mostly amplifies others could be far worse, and the symptom is a sparse folder
  rather than an error.
- **Every run re-pays for the same top-N**, including on days with no new posts.
  `on_disk_ids` prevents re-writing files, but only after collection is billed.

Relationship to tune against: `monthly ≈ handles × 30 × MAX_ITEMS_PER_RUN ×
per_record_cost`. Re-tuning is a manual judgment call at registration time; the
adapter does not enforce a budget.

## Constants

| Constant | Value | Why |
|---|---|---|
| `MAX_ITEMS_PER_RUN` | 10 | matches Instagram/LinkedIn |
| `POLL_INTERVAL_S` | 5 | matches Instagram/LinkedIn |
| `POLL_TIMEOUT_S` | **600** | **raised from the inherited 300.** Measured 243s at `limit_per_input=10`, which is the production setting. 300s would leave under a minute of margin on a normal run, turning ordinary slowness into a `BrightDataJobTimeout` on a job that was billed. |

## Error handling

The LinkedIn contract carries over unchanged:

- **Poll timeout** → raise `BrightDataJobTimeout`.
- **Job reports `failed`** → raise `BrightDataJobFailed`.
- **Job `ready` with zero rows** → return `[]`, the one case that honestly means
  "nothing to report".

Both raises land in `run_discovery`'s per-handle `except Exception`, recorded as
a normal `error` result and retried on the next run.

### Rows returned, none survived

When `rows_returned > 0 and rows_kept == 0`, the adapter logs a distinct warning
naming the cause, because `process_handle` would otherwise record the healthy
status `no_new_content` for a batch that was paid for. X has **two** causes and
they need different advice:

- **All rows unusable** (no `id`) — this is the observed error-row shape, e.g. a
  suspended, renamed, or protected account. Advice: check whether the handle is
  still valid.
- **All rows filtered** by authorship — the account posted nothing of its own in
  this window. Advice: check whether the account posts its own content.

Mixed causes get both. This mirrors LinkedIn, where the same distinction was
added because pointing an operator at the wrong cause wastes their time.

### Named limitation: validation can permanently exclude a handle

At registration, `process_handle_validate` marks a handle `invalid` and
auto-excludes it from future runs when enumeration returns nothing. An account
whose recent timeline is entirely other people's posts produces exactly that
outcome — a valid, active account rejected at registration.

This is pre-existing `validate_handle` behavior, identical for every platform,
and no engine change is proposed. It is called out because the author filter
makes it more likely on X than on YouTube or Bluesky. Recovery is to re-register.

## Testing

Following `test_discovery_linkedin.py`, against a fake HTTP layer with no real
Bright Data calls. Every "pin" below is a regression test for something live
verification actually caught:

- Trigger sends `type=discover_new`, `discover_by=profile_url`, and
  `limit_per_input`.
- **Pin:** a row whose `user_posted` differs from the handle is dropped —
  the `arctotherium42`-in-elonmusk's-timeline case.
- **Pin:** `is_repost` is **not** consulted. A foreign row with
  `is_repost: false` must still be dropped, so a future maintainer who
  "simplifies" the filter to `is_repost` breaks a test that explains why.
- **Pin:** `description: null` yields a **kept** row whose body is `"(empty)"`,
  not a dropped row.
- **Pin:** unsorted input returns newest-first.
- **Pin:** an `include_errors` error row (no `id`, `error`/`error_code` present)
  is dropped without raising.
- **Pin:** `date_posted` in the verified ISO-Z form normalizes to `YYYY-MM-DD`;
  a malformed value drops the row rather than raising.
- **Pin:** two rows with the two different `url` domain shapes are both keyed on
  `id`, and identity never reads `url`.
- **Pin:** rows returned but all dropped → returns `[]` **and** logs the warning
  naming the correct cause, for all-unusable, all-filtered, and mixed.
- **Pin:** `videos` is flattened from the struct list to a URL list.
- Poll timeout raises; job `failed` raises; `ready` with zero rows returns `[]`.
- `download_item` reads the cache with no second network call; a cache miss
  raises rather than degrading silently.
- `on_disk_ids` dedup; `keyword_filter` applied client-side against
  `description`.
- Credential lookup (env var vs. file).
- `POLL_TIMEOUT_S` is 600, guarding the deliberate divergence from the other two
  adapters against a well-meaning "make the constants consistent" edit.
- Registration: `build_adapters()` exposes `"x"`, and `"x"` is not in
  `BACKFILL_SUPPORTED_PLATFORMS`.

## Non-goals

The X Profiles dataset (dropped on evidence); date-ranged backfill (proven
broken); `profiles_array` batching; collect-by-single-post-URL; media download;
reply and thread reconstruction; storing denormalized profile state
(`followers`, `posts_count`) per post; automatic re-tuning of
`MAX_ITEMS_PER_RUN`; and any attempt to reduce the vendor-continuity risk
described under "Risk posture".

Like Instagram and LinkedIn, X content enters the corpus as post text only —
there is no transcript equivalent, and X posts are shorter than either. This is
a real asymmetry against the transcript-centric YouTube material the skills were
built from, and it is accepted here rather than solved.

## Operational note

Bright Data's domains are blocked by DNS-filtering resolvers that categorize
proxy and scraping infrastructure — on this machine, Proton VPN's NetShield. A
live run needs that path clear, or every job fails at name resolution before any
HTTP call is made. The six jobs above were run with it clear.
