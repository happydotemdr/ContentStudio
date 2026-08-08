# Facebook Discovery Adapter via Bright Data

**Status:** Design (schema verified against five live jobs before writing — see
"Live verification" below; ready for implementation planning)
**Date:** 2026-08-08
**Follows from:** [`2026-08-07-linkedin-brightdata-adapter-design.md`](2026-08-07-linkedin-brightdata-adapter-design.md),
whose adapter this one is modelled on and shares a Bright Data client with, and
[`2026-08-06-instagram-brightdata-adapter-design.md`](2026-08-06-instagram-brightdata-adapter-design.md),
which established the `brightdata_job` error discipline both inherit.

## Purpose

Add Facebook to the discovery pipeline, alongside YouTube, Bluesky, Instagram,
and LinkedIn, using Bright Data's Facebook Pages Posts dataset
(`gd_lkaxegm826bjpoo9m5`) as the data source. It registers as one new platform
value, `facebook`, bringing the engine's adapter registry to six. Captured content serves
the existing `output/brand-intel/` corpus, competitive monitoring, and raw
material for the `social-repurpose` stage — all three satisfied by the same
archival capture, so no new storage model is needed.

## Method note: verification came first

The Instagram adapter shipped and merged with four wrong assumptions, three of
which failed silently; the worst made every row drop while the engine reported
a healthy `no_new_content` for a batch already paid for. LinkedIn responded by
verifying before designing, and that pass dropped one of three requested modes
on evidence.

This design was likewise written *after* five live Bright Data jobs (17 records
total), not before. **The verification changed the scope**: one of the two
datasets originally requested was dropped on evidence.

A review pass then rejected a second thing — a vendor feature that verified
clean and still could not be used, because the defect was in how it interacts
with this engine rather than in the vendor's behavior. That analysis is kept in
full under "Rejected on analysis"; verifying a capability works is not the same
as verifying it helps.

Every field mapping below is `[T]`-marked from observed data, not from the
published field list.

## Scope

- **In scope:** one platform adapter, `facebook`, over Bright Data's Pages
  Posts dataset, satisfying the existing `PlatformAdapter` protocol.
  Incremental (`process_handle`) and single-item validation
  (`process_handle_validate`) modes only.
- **Out of scope:** the Reels dataset (**dropped on evidence** — see "Live
  verification"); server-side dedup via `posts_to_not_include` (**rejected on
  analysis** — verified working, unusable against this engine, see "Rejected on
  analysis"); historical backfill (**deferred to its own spec** — the
  capability is proven and the evidence is recorded under "Backfill"); the
  Profiles, Posts-by-post-URL, Comments, Group Posts, Events, and Marketplace
  datasets; media download; comment capture; and which specific handles to
  track.

## Live verification (2026-08-08)

Five real jobs via the same async `/trigger` → `/progress` → `/snapshot` path
the adapter will use, at `num_of_posts: 3` per input except job 4, which used
`2`:

| # | Dataset | Input | Snapshot | Result |
|---|---|---|---|---|
| 1 | Reels `gd_lyclm3ey2q6rww027t` | `/MrBeast6000`, `/NASA` | `sd_mskdsapv2lkqk4u8gm` | 3 records + 1 error row |
| 2 | Page Posts `gd_lkaxegm826bjpoo9m5` | `/NASA`, `/MrBeast6000` | `sd_mskdsc8e27l3f2p9yn` | 6 records |
| 3 | Page Posts | `/MrBeast6000` + `posts_to_not_include` | `sd_mskdwagt8t6fgd7y` | 1 record |
| 4 | Page Posts | `/zuck`, `/profile.php?id=100044561550831` | `sd_mskdwbl2chtw7pshw` | 4 records |
| 5 | Page Posts | `/NASA`, `01-01-2025`–`03-31-2025` | `sd_mskdwclnbuptgsljw` | 3 records |

### Confirmed sound

- **`[T]` The bare-array body works against `/trigger`** — HTTP 200 on both
  datasets. Bright Data's Facebook documentation shows the `{"input": [...]}`
  object form, but that belongs to the *synchronous* `/scrape` endpoint.
  `brightdata_job.trigger()` already sends the correct shape and needs no
  change.
- **`[T]` `date_posted` is genuine ISO 8601 UTC** —
  `2026-07-06T19:00:51.000Z`. Truncation to `[:10]` is correct, as with
  LinkedIn and unlike Instagram's US-format local timestamp. The `MM-DD-YYYY`
  format in Bright Data's snippets is **input-only** and does not describe
  output.
- **`[T]` `post_id` is a JSON string** and is stable across both Facebook
  products. This matters: `on_disk_ids()` compares against filename stems, so a
  numeric id would never match and every run would re-download and re-pay in
  silence.
- **`[T]` `num_of_posts` is honored exactly** per input object — `3` returned 3
  (jobs 2, 5) and `2` returned 2 (job 4, twice). Not merely an upper bound.
- **`[T]` Job latency 3–56s**, well inside a 300s poll timeout.
- **`[T]` No `type` or `discover_by` parameter is required.** This product has
  no discovery mode; the input URL is the account and the collector walks it.
  `num_of_posts` replaces the `limit_per_input` query param LinkedIn uses.

### Dropped on evidence — the Reels dataset

**`[T]` Every reel returned by the dedicated Reels dataset was also returned by
Pages Posts, tagged `post_type: "Reel"`.** Job 1 and Job 2 ran against
`/MrBeast6000` within the same minute:

```
reels      : 1212030294059346, 1445430590719314, 1479086397353733
page posts : 1212030294059346, 1445430590719314, 1479086397353733, + 3 NASA
overlap    : all three
```

**`[T]` The Reels dataset is also less reliable than the superset.** For
`/NASA` it returned an error row — `error_code: "dead_page"`, `"Seems page have
not reels"` — while Pages Posts returned two NASA rows with `post_type: "Reel"`
in the same minute. The dedicated endpoint denied the existence of reels it was
simultaneously serving through the other product.

The Reels dataset is therefore **dropped from scope**. Reels are captured via
`content_type: reel`.

Two platforms (`facebook-posts` + `facebook-reels`, mirroring the
`linkedin-profile`/`linkedin-company` shape) was considered and rejected. Its
one genuine advantage is cheaper reels-only capture on a mixed-content account;
against that, any handle registered on both platforms would be billed twice and
store every reel in two directories, and the `dead_page` error would mark a
valid Page `invalid` and auto-exclude it at registration. The adapter is
structured so a second mode remains an additive change if that cost profile
ever appears.

### Rejected on analysis — server-side dedup (`posts_to_not_include`)

**`[T]` `posts_to_not_include` is honored.** Job 3 requested `num_of_posts: 3`
from `/MrBeast6000` while excluding the three ids Job 2 had already returned. It
returned **1 record** — `1200229695239406`, dated `2025-07-24`, strictly older
than all three excluded posts, and none of the excluded ids came back.

This looked like the structural break from the two prior Bright Data adapters,
whose designs both concede that every run re-pays for the same top-N forever.
**It is not usable, and the reason is in this engine, not in the vendor.**

`process_handle` has exactly two termination conditions:

- the early-stop counter, which increments only when an already-on-disk id
  **appears** in the enumeration (`discovery_engine.py:54-57`);
- the `NEW_HANDLE_LOOKBACK_DAYS` cutoff, which applies only while `is_new` —
  the handle's first run ever (`:44-45`, `:61-70`).

Excluding on-disk ids server-side removes them from the response, so the first
never fires. After run 1 the handle is no longer new, so the second never
applies. Every subsequent run therefore downloads `MAX_ITEMS_PER_RUN`
progressively **older** posts, daily, until the account's entire back-catalogue
is captured — an unbounded historical walk in the mode whose whole purpose is to
fetch only new content, pulling in exactly the years-old material
`NEW_HANDLE_LOOKBACK_DAYS` exists to keep out.

Job 3 is the evidence for this, read correctly: excluding the newest 3 returned
the *4th*-newest. That is the walk-further behavior, observed. It was initially
mistaken for a self-correcting backlog fill.

Capping the exclusion list does not fix it, only swaps the failure mode. Past
the cap, the newest non-excluded posts are ones already on disk, so they are
returned and billed on every run while the engine correctly declines to download
them: full freight, with extra steps.

Two further costs, moot now but recorded so the idea is not re-proposed
unexamined:

- `enumerate_newest_first(handle, keyword_filter)` receives no `repo_root`, so
  the exclusion list could only be built by reusing what `on_disk_ids()` had
  already computed — depending on a call ordering (`discovery_engine.py:43`
  before `:47`) that is an implementation detail of `process_handle`, not part
  of the `PlatformAdapter` protocol.
- A cache that ever returned **another handle's** ids would exclude posts never
  captured, which Bright Data would then never return — silent, permanent
  content loss, as opposed to the merely expensive failure of sending none.

A bounded variant is plausible: `start_date` set a few days before the newest
captured post, which keeps on-disk items visible in the response so the early
stop still fires. It needs a date source `on_disk_ids()` does not provide, and a
too-recent `start_date` loses posts silently. It belongs with backfill, in a
spec that changes the protocol deliberately rather than leaning on an ordering
accident.

### Available but deferred — date-ranged collection

**`[T]` `start_date`/`end_date` are honored, in `MM-DD-YYYY`.** Job 5 requested
`01-01-2025`–`03-31-2025` against `/NASA` and returned 3 records, all inside the
window (Mar 27–28, 2025), in 3 seconds.

**Facebook backfill is therefore genuinely possible** — the one thing both
prior Bright Data specs list as permanently out of reach. It is deferred rather
than dropped; see "Backfill".

### Other observed facts

- **`[T]` "Pages Posts" is misnamed — it handles personal profiles too.**
  `/zuck` returned 2 records with `is_page: false`; Page accounts return
  `is_page: true`.
- **`[T]` `profile.php?id=<numeric>` works as input** and resolves in the output
  to the vanity handle (`profile_handle: "NASA"`), not the numeric id.
- **`[T]` `timestamp` is scrape time, not post time** — `2026-08-08T13:00:50Z`
  on a post dated `2026-07-06`. It reads as a plausible date field and is wrong
  by however long ago the post was made.
- **`[T]` `shortcode` is not a stable identity.** For post
  `1479086397353733` the Reels product returned `shortcode:
  "1157962813213302"` and Pages Posts returned `shortcode:
  "1479086397353733"`. Never key on it; `post_id` is the key.
- **`[T]` `page_likes` is unreliable** — `0` on an account reporting
  `page_followers: 1400000`.
- **`[T]` `likes` is the reaction total** (2836). `num_likes_type` is a dict
  holding only the `Like` subtotal (2429) and is not the same number.
- **`[T]` `hashtags` is inconsistently shaped** — the key was *absent* from
  Pages Posts rows and present-but-`null` on Reels rows.
- **`[T]` `post_type` observed values: `Post`, `Reel`** — display-cased,
  confirming that LinkedIn's defensive lowercasing was the right call.
- **`[T]` Rows arrived newest-first within each input**, grouped by input.
  LinkedIn's sibling product returned rows unsorted, so the adapter sorts
  regardless.
- **`[T]` Error rows are structured.** With `include_errors=true`, a failure
  arrives as a row carrying `error` and `error_code` instead of as an absence:
  `{"timestamp": ..., "input": {...}, "error": "Seems page have not reels",
  "error_code": "dead_page"}`.
- **`[T]` Pricing 2026-08-08:** $1.50/1k records pay-as-you-go, 5K
  records/month free tier.
- **`[T-unverified, 2026-08-08]`** Billing granularity — per record vs. per-job
  minimum, and whether failed or timed-out jobs are charged — remains the same
  open item Instagram and LinkedIn both left.

## Architecture

### New: `pipeline_app/discovery_facebook.py`

A plain module, not a class. LinkedIn needed a class because two modes shared
one implementation and each required its own enumerate cache; Facebook has one
mode, so it matches `discovery_instagram`'s module shape.

It holds only the Facebook-specific parts: dataset id, URL construction, row
normalization, and the enumerate cache.

### Modified

- `run_discovery_cron.py`'s `build_adapters()` — one entry, `"facebook"`.
- `templates/discovery_handles.html` — one new `<option>`.

### Not modified

`discovery_engine.py` and `brightdata_job.py`. `BACKFILL_SUPPORTED_PLATFORMS`
is a whitelist of `{"youtube", "bluesky"}`, so `facebook` is already rejected
from backfill with a logged skip and no adapter call — the guard is inherited,
not added. `brightdata_job.py` stays untouched, which makes the existing
Instagram and LinkedIn suites a regression gate on this work.

### Handle model

Handles are bare slugs — `NASA`, `MrBeast6000`, `zuck` — matching LinkedIn.
This keeps `UNIQUE(platform, handle)` meaningful and lets the output directory
fall out of the existing `handle_dir(repo_root, platform, handle)` with no path
special-casing: `output/brand-intel/facebook/<handle>/`.

Facebook has two input URL shapes, selected on the handle itself:

- all-digit handle → `https://www.facebook.com/profile.php?id=<handle>`
- otherwise → `https://www.facebook.com/<handle>`

The numeric branch uses `profile.php?id=` specifically **because that is the
form that was tested**. The bare `facebook.com/<numeric-id>` form was not, and
there is no reason to guess when a verified form exists.

Storing a full pasted URL as the handle was rejected for the same reasons as
LinkedIn: Facebook URLs carry tracking parameters and appear in at least four
shapes (`/<slug>`, `/profile.php?id=`, `/people/<name>/<id>/`,
`/<numeric>/reels/`), so several strings could describe one account, and
`slugify()` mangles the result into an unreadable directory name.

**No author filter.** LinkedIn profile mode needed one because it returned
other people's posts. Across all 17 Facebook records, `profile_handle` matched
the requested account every time. Filtering would additionally be *wrong* here:
a numeric handle returns `profile_handle: "NASA"`, so a naive comparison would
discard every row. `profile_handle` is still recorded in frontmatter, which is
what makes a future regression detectable.

### Request shape

```
POST /trigger?dataset_id=gd_lkaxegm826bjpoo9m5&include_errors=true&notify=false
[{"url": "...", "num_of_posts": 10}]
```

No `posts_to_not_include`, no `start_date`, no `end_date` — all three verified
working, all three deliberately unused. Dedup is the engine's job, client-side,
exactly as it is for Instagram and LinkedIn.

## Data contract

| Output field | Source | Note |
|---|---|---|
| `id` | `post_id` | string; stable across products; the sole identity key |
| `published` | `date_posted[:10]` | genuine ISO 8601 Z, verified |
| `published_ts` | `date_posted` (full) | internal sort key only; never written to frontmatter |
| body | `content` | the caption |
| `title` | first line of `content`, else `post_id`; truncated to 60 | no `headline` equivalent exists |
| `content_type` | `post_type`, lowercased | `post`, `reel` |
| `author` | `profile_handle` | recorded, never filtered on |
| `profile_id` | `profile_id` | numeric account id; survives a vanity-slug rename |
| `is_page` | `is_page` | `true` = Page, `false` = personal profile |
| `like_count` | `likes` | **not** `num_likes_type`, which holds only the `Like` subtotal |
| `comment_count` | `num_comments` | |
| `share_count` | `num_shares` | |
| `view_count` | `video_view_count` | null on non-video posts |
| `hashtags` | `hashtags` or `[]` | key absent on posts rows, null on reels rows |
| `url` | `url` | informational |

**Three fields deliberately unused**, each a live trap: `timestamp` (scrape
time, not post time), `shortcode` (two different values for one post across
products), `page_likes` (`0` on a 1.4M-follower account).

**Available but not stored**, matching how LinkedIn declined
`top_visible_comments`: `count_reactions_type` (the full reaction mix),
`page_followers`, `attachments` (CDN media URLs — media download is out of
scope), and the page-metadata block (`page_category`, `page_intro`,
`page_email`, …).

**A row is dropped if** it has no `post_id` or no parseable `date_posted`. Drop
counts and any `error_code` are logged to stderr.

**Order of operations:** normalize → drop → **sort newest-first on
`published_ts`** → cap to `MAX_ITEMS_PER_RUN` → apply `keyword_filter`. The cap
is applied after filtering so it bounds retained items. `keyword_filter` is a
case-insensitive substring match against `content`, matching
`discovery_bluesky.py`.

The sort is defensive — rows arrived newest-first here, but a sibling Bright
Data product returned them unsorted. **It must key on the full timestamp, not
on `published`.** Python's sort is stable, so a date-truncated key leaves
same-day rows in Bright Data's arbitrary arrival order, which can place a
genuinely newer post behind ones already on disk and trip the early-stop dedup
before reaching it. Both sibling adapters carry a separate `published_ts` for
exactly this reason (`discovery_linkedin.py:93-101`,
`discovery_instagram.py:227-231`); a contract exposing only `published` would
reintroduce a bug those two already paid for.

### File format

One `.md` per post, named `<post_id>.md`, written with the existing
write-temp-then-rename so an interrupted write never leaves a truncated file at
a path `on_disk_ids()` would treat as captured:

```
---
post_id: <string>
url: <string>
handle: <tracked handle>
author: <profile_handle>
profile_id: <string>
is_page: true | false
content_type: post | reel
published: <YYYY-MM-DD>
like_count: <int | null>
comment_count: <int | null>
share_count: <int | null>
view_count: <int | null>
hashtags: [<string>, ...]
fetched_at: <ISO 8601 UTC>
---

<content, or "(empty)">
```

`content` is genuinely empty on image-only posts, so `(empty)` is a real case
rather than a defensive branch.

## Cost model

`MAX_ITEMS_PER_RUN = 10`, daily — one constant, one cadence, matching Instagram
and LinkedIn, no engine change. That is 300 records/month per handle; at
$1.50/1k, **$0.45/month per handle**. The 5K/month free tier covers roughly 16
handles at that rate.

**Every run re-pays for the same top-N**, including on days with no new posts.
`on_disk_ids` prevents re-*writing* files, but only after collection has been
billed. The cap bounds this; nothing removes it. This is the same concession
Instagram and LinkedIn make, and "Rejected on analysis" above records in detail
why the apparent escape from it does not work — the saving was real, and it
bought an unbounded historical walk.

Relationship to tune against: `monthly ≈ handles × 30 × MAX_ITEMS_PER_RUN ×
per_record_cost`. Re-tuning is a manual judgment call at registration time; the
adapter does not enforce a budget.

### Duplicate-handle double capture

One account can be registered twice under two different handles — its vanity
slug (`NASA`) and its numeric id (`100044561550831`) — because
`UNIQUE(platform, handle)` sees two distinct strings. The result is two
directories, two daily jobs, and double billing for one account.

No dedup is proposed. The adapter cannot learn the numeric id behind a slug
without running a job, which would make registration itself billable. The
frontmatter records both `author` (`profile_handle`) and `profile_id` on every
row, so the duplication is greppable after the fact even though it cannot be
prevented at registration.

## Error handling

The contract carries over unchanged from Instagram and LinkedIn:

- **Poll timeout** → raise `BrightDataJobTimeout`.
- **Job reports `failed`** → raise `BrightDataJobFailed`.
- **Job `ready` with zero rows** → return `[]`, the one case that honestly
  means "nothing to report".

Both raises land in `run_discovery`'s per-handle `except Exception`, recorded
as a normal `error` result and retried on the next run.

Facebook improves on LinkedIn's diagnostics. Because failures arrive as
structured rows rather than absences, the adapter logs the vendor's own reason
instead of a bare count — `dead_page: Seems page have not reels` rather than
`dropped 1 unusable row(s)`. When rows are returned but none survive — the
silent-failure shape both prior specs warn about — the loud warning names the
`error_code`s seen, so a dead slug reads as a dead slug instead of a mystery.

### Named limitation: validation can permanently exclude a handle

`process_handle_validate` marks a handle `invalid` **and auto-excludes it from
all future runs** when enumeration returns nothing. A mistyped slug produces
exactly that, which is correct. A real account with zero posts also produces
it, which is a false rejection.

This is pre-existing `validate_handle` behavior, identical across every
platform, and no engine change is proposed for it. Recovery is to re-register
the handle. It is milder here than on LinkedIn, where the author filter made it
meaningfully more likely.

## Backfill

Unsupported in this spec, and requires no code: the existing
`BACKFILL_SUPPORTED_PLATFORMS` whitelist already rejects `facebook` before any
adapter call, logging a skip.

Unlike Instagram and LinkedIn, the capability is **proven** (Job 5, above), so
a future spec starts from evidence rather than research. What it will have to
solve is an engine change, not a vendor question:
`process_handle_backfill` calls `enumerate_newest_first(handle,
keyword_filter)` and filters the results client-side, never passing the date
window to the adapter. For a paid, date-capable API that is the wrong shape —
an old window would trigger a billed job that matches nothing, which is exactly
why Instagram is excluded today. Real Facebook backfill means extending the
`PlatformAdapter` protocol so the window reaches the request, which touches
shared code that the YouTube and Bluesky adapters also run through. That blast
radius is why it is not bundled here.

## Testing

Following `test_discovery_instagram.py`, against a fake HTTP layer with no real
Bright Data calls. Each item marked "pin" is a regression test for something
live verification actually caught:

- Trigger sends a bare array with `num_of_posts`, and no `type`/`discover_by`.
- **Pin:** the trigger body carries **no** `posts_to_not_include`,
  `start_date`, or `end_date` key. All three verified working and all three
  deliberately unused; a well-meaning future edit adding the first would
  reintroduce the unbounded walk described under "Rejected on analysis".
- **Pin:** numeric handle → `profile.php?id=`; non-numeric → `/<slug>`.
- **Pin:** `date_posted` in the verified ISO-Z form normalizes to
  `YYYY-MM-DD`; a malformed value drops the row rather than raising.
- **Pin:** body comes from `content`; `timestamp` is never used as a date.
- **Pin:** `like_count` comes from `likes`, not `num_likes_type`'s inner `num`.
- **Pin:** `hashtags` absent *and* `hashtags: null` both normalize to `[]`.
- **Pin:** `Reel` survives lowercasing as a valid `content_type`.
- **Pin:** an `include_errors` error row (no `post_id`) is dropped, and its
  `error_code` reaches the log.
- **Pin:** rows returned but all dropped → returns `[]` **and** logs the
  distinct all-dropped warning.
- **Pin:** unsorted input returns newest-first.
- **Pin:** two rows sharing a `published` date but differing in the full
  `date_posted` timestamp sort by the timestamp, newest first — the
  date-truncated-sort-key bug both sibling adapters carry a `published_ts` to
  avoid.
- Poll timeout raises; job `failed` raises; `ready` with zero rows returns `[]`.
- `download_item` reads the cache with no second network call; a cache miss
  raises rather than degrading silently.
- `on_disk_ids` dedup; `keyword_filter` applied client-side against `content`.
- Credential lookup (env var vs. file).
- **Regression gate:** the existing `discovery_instagram` and
  `discovery_linkedin` suites stay green — `brightdata_job.py` is not modified.

## Non-goals

The Reels dataset (dropped on evidence, above); `posts_to_not_include`
(rejected on analysis, above); backfill (deferred, above); the Profiles,
Posts-by-post-URL, Comments, Group Posts, Events, and Marketplace datasets;
image/video download; comment capture; reaction-mix and page-metadata capture;
duplicate-handle detection; automatic re-tuning of `MAX_ITEMS_PER_RUN` as
handles are added.

Like Instagram and LinkedIn, Facebook content enters the corpus as post text
only — there is no transcript equivalent. This is a real asymmetry against the
transcript-centric YouTube material the skills were built from, and it is
accepted here rather than solved.

## Operational note

Bright Data's domains are blocked by DNS-filtering resolvers that categorize
proxy/scraping infrastructure — on this machine, Proton VPN's NetShield. That
path was clear during the 2026-08-08 verification jobs, but a live run needs it
clear or every job fails at name resolution before any HTTP call is made.
