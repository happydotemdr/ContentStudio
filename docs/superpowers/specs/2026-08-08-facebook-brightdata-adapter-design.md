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
datasets originally requested was dropped, and two capabilities neither prior
adapter has were discovered. Every field mapping below is `[T]`-marked from
observed data, not from the published field list.

## Scope

- **In scope:** one platform adapter, `facebook`, over Bright Data's Pages
  Posts dataset, satisfying the existing `PlatformAdapter` protocol.
  Incremental (`process_handle`) and single-item validation
  (`process_handle_validate`) modes only.
- **Out of scope:** the Reels dataset (**dropped on evidence** — see "Live
  verification"); historical backfill (**deferred to its own spec** — the
  capability is proven and the evidence is recorded under "Backfill"); the
  Profiles, Posts-by-post-URL, Comments, Group Posts, Events, and Marketplace
  datasets; media download; comment capture; and which specific handles to
  track.

## Live verification (2026-08-08)

Five real jobs via the same async `/trigger` → `/progress` → `/snapshot` path
the adapter will use, `num_of_posts: 3`:

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
- **`[T]` `num_of_posts` is honored** per input object — `3` returned exactly 3.
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

### New capability — server-side dedup (`posts_to_not_include`)

**`[T]` `posts_to_not_include` is honored.** Job 3 requested `num_of_posts: 3`
from `/MrBeast6000` while excluding the three ids Job 2 had already returned. It
returned **1 record** — `1200229695239406`, dated `2025-07-24`, strictly older
than all three excluded posts, and none of the excluded ids came back.

This is the structural break from the two prior Bright Data adapters, whose
designs both concede that every run re-pays for the same top-N forever. Here the
on-disk ids can be pushed into the request and **the posts already held are
never billed**. See "Cost model" for how it is wired and what it risks.

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
normalization, the exclusion-list builder, and the enumerate cache.

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
[{"url": "...", "num_of_posts": 10, "posts_to_not_include": ["...", ...]}]
```

## Data contract

| Output field | Source | Note |
|---|---|---|
| `id` | `post_id` | string; stable across products; the sole identity key |
| `published` | `date_posted[:10]` | genuine ISO 8601 Z, verified |
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

**Order of operations:** normalize → drop → **sort newest-first** → cap to
`MAX_ITEMS_PER_RUN` → apply `keyword_filter`. The sort is defensive: rows
arrived sorted here, but a sibling Bright Data product returned them unsorted
and the engine's early-stop dedup assumes newest-first. The cap is applied
after filtering so it bounds retained items. `keyword_filter` is a
case-insensitive substring match against `content`, matching
`discovery_bluesky.py`.

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
and LinkedIn, no engine change.

Without dedup that is 300 records/month per handle ≈ **$0.45**. With
`posts_to_not_include`, only genuinely new posts are billed: a 3-posts-a-day
page costs ~90 records ≈ **$0.14**; a weekly poster ~4 records ≈ **$0.006**.
Most handles stay inside the 5K/month free tier indefinitely.

### How the exclusion list is wired, and what it risks

`enumerate_newest_first(handle, keyword_filter)` receives no `repo_root`, so it
cannot read the on-disk ids it needs. It reuses what
`on_disk_ids(repo_root, handle)` already computed — which works only because
`process_handle` calls that first (`discovery_engine.py:43` before `:47`).

**That ordering is an implementation detail of `process_handle`, not part of
the `PlatformAdapter` protocol**, and this adapter is the first to depend on
it. `process_handle_validate` (`:108`) calls `enumerate_newest_first` *without*
any prior `on_disk_ids` call at all.

The two failure modes are not symmetric, and the asymmetry is what makes the
coupling acceptable:

- Ordering changes, or validate mode runs → exclusion list is **empty** → full
  freight is paid and nothing is lost.
- The cache returns **another handle's** ids → posts we do not hold are
  excluded → Bright Data never returns them → **silent, permanent content
  loss.**

The cache is therefore a `{handle: frozenset}` read with
`.get(handle, frozenset())` — never a bare shared set, never a stale fallback.
A miss must degrade to empty, never to another handle's data. This is pinned by
test.

### Two unverified cost assumptions

- **`[T-unverified, 2026-08-08]` Exclusion-list cap of 100, sorted numerically
  descending.** `post_id` rose monotonically with date *within* every account
  observed (NASA `1207935230701851` Mar 2025 → `1596499905178713` Aug 2026;
  MrBeast four-for-four). That is a strong pattern, not a documented guarantee.
  If it is wrong, a suboptimal subset is excluded and slightly more is paid —
  the engine's own `on_disk` check still catches anything re-returned before
  download. The cap exists because the list would otherwise grow without bound
  (a year of daily capture is ~3,650 ids in every request body).
- **`[T-unverified, 2026-08-08]` `num_of_posts` × `posts_to_not_include`
  interaction.** Job 3 requested 3 while excluding the newest 3 and returned 1,
  strictly older than all three. Exclusion is honored; the exact walk semantics
  are not pinned. Consequence: a run may return fewer new items than exist. It
  self-corrects — the next run excludes what was just captured and walks
  further — so a fresh handle with a large backlog fills in over several days
  rather than one.

Relationship to tune against: `monthly ≈ handles × 30 × new_posts_per_day ×
per_record_cost`, bounded above by `handles × 30 × MAX_ITEMS_PER_RUN ×
per_record_cost`. Re-tuning is a manual judgment call at registration time; the
adapter does not enforce a budget.

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
- **Pin:** the exclusion list for handle B never contains handle A's ids.
- **Pin:** `enumerate_newest_first` with no prior `on_disk_ids` call sends an
  empty exclusion list, not a stale one.
- **Pin:** the exclusion list caps at 100, numerically descending.
- **Pin:** unsorted input returns newest-first.
- Poll timeout raises; job `failed` raises; `ready` with zero rows returns `[]`.
- `download_item` reads the cache with no second network call; a cache miss
  raises rather than degrading silently.
- `on_disk_ids` dedup; `keyword_filter` applied client-side against `content`.
- Credential lookup (env var vs. file).
- **Regression gate:** the existing `discovery_instagram` and
  `discovery_linkedin` suites stay green — `brightdata_job.py` is not modified.

## Non-goals

The Reels dataset (dropped on evidence, above); backfill (deferred, above); the
Profiles, Posts-by-post-URL, Comments, Group Posts, Events, and Marketplace
datasets; image/video download; comment capture; reaction-mix and page-metadata
capture; automatic re-tuning of `MAX_ITEMS_PER_RUN` as handles are added.

Like Instagram and LinkedIn, Facebook content enters the corpus as post text
only — there is no transcript equivalent. This is a real asymmetry against the
transcript-centric YouTube material the skills were built from, and it is
accepted here rather than solved.

## Operational note

Bright Data's domains are blocked by DNS-filtering resolvers that categorize
proxy/scraping infrastructure — on this machine, Proton VPN's NetShield. That
path was clear during the 2026-08-08 verification jobs, but a live run needs it
clear or every job fails at name resolution before any HTTP call is made.
