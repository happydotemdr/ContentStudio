# LinkedIn Discovery Adapter via Bright Data

**Status:** Design (schema verified against live jobs before writing — see
"Live verification" below; ready for implementation planning)
**Date:** 2026-08-07
**Follows from:** [`2026-08-06-instagram-brightdata-adapter-design.md`](2026-08-06-instagram-brightdata-adapter-design.md),
whose adapter this one is modelled on and shares a Bright Data client with, and
[`2026-08-06-social-platform-data-access-survey.md`](2026-08-06-social-platform-data-access-survey.md),
which rated LinkedIn the single **High risk** platform of the six surveyed.

## Purpose

Add LinkedIn as a fourth discovery-pipeline platform, alongside YouTube,
Bluesky, and Instagram, using Bright Data's LinkedIn Posts dataset
(`gd_lyy3tktm25m4avu764`) as the data source. Captured content serves the
existing `output/brand-intel/` corpus, competitive monitoring, and raw material
for the `social-repurpose` stage — all three of which are satisfied by the same
archival capture, so no new storage model is needed.

## Method note: verification came first

The Instagram adapter shipped and merged with **four wrong assumptions**, three
of which fail silently; the worst (`date_posted` format) made every row drop
while the engine reported a healthy `no_new_content` for a batch already paid
for. It was caught only by running a real job.

This design was therefore written *after* four live Bright Data jobs (10
records total), not before. Two of the entity types originally requested did
not survive that check. Every field mapping below is `[T]`-marked from observed
data, not from the published field list.

## Risk posture (stated, not solved)

The platform survey rated LinkedIn **High risk** — LinkedIn litigates scraping
vendors, and Proxycurl was shut down in July 2025 after a LinkedIn/Microsoft
suit. Bright Data is the party performing collection and carrying that
exposure; this project's posture is that of a data purchaser. The practical
consequence for this design is **vendor-continuity risk**: this adapter can go
dark on short notice in a way the YouTube and Bluesky adapters cannot. The
design responds by making failure loud and cheap (raise, never return `[]`
silently; a hard per-run cap), not by attempting to mitigate the legal exposure,
which is not an engineering problem.

## Scope

- **In scope:** two platform adapters over one shared implementation —
  `linkedin-profile` (a person's own posts) and `linkedin-company` (an
  organization's posts) — satisfying the existing `PlatformAdapter` protocol.
  Incremental (`process_handle`) and single-item validation
  (`process_handle_validate`) modes only.
- **Out of scope:** Pulse articles (**dropped on evidence** — see "Live
  verification"), collect-by-single-post-URL, historical backfill, media
  download, comment capture, and which specific handles to track.

## Live verification (2026-08-07)

Four real discovery jobs via the same async `/trigger` → `/progress` →
`/snapshot` path the adapter will use (not the dashboard's synchronous
`/scrape`), `limit_per_input=3`:

| Mode | `discover_by` | Input | Snapshot | Result |
|---|---|---|---|---|
| profile | `profile_url` | `/in/bettywliu` | `sd_msizuwoz1sxczzt49` | 3 records, 0 errors |
| company | `company_url` | `/company/lanieri` | `sd_msizuxvm1zh3lphp44` | 3 records, 0 errors |
| article | `url` | `/today/author/stevenouri` | `sd_msizuz58ydxnt505b` | 1 record, 0 errors |
| article (retry) | `url` | `/today/author/cristianbrunori` | `sd_msizymmw2pq7uwbs0v` | 3 records, 0 errors |

### Confirmed sound

- **`[T]` All three modes return one unified schema** (40 fields, identical key
  set). One normalization path serves every mode.
- **`[T]` `id` is a JSON string**, not a number — confirmed in the raw payload
  (`"id": "7480621754537701376"`). This matters: `on_disk_ids()` compares
  against filename stems, so a numeric id would never match, and every run
  would re-download and re-pay in silence.
- **`[T]` `date_posted` is genuine ISO 8601 UTC** —
  `2026-07-08T14:00:09.491Z`. Truncation to `[:10]` is correct here, unlike
  Instagram's US-format local timestamp. The formats differ **between two
  Bright Data products**, which is itself the reason neither can be assumed.
- **`[T]` `post_text` is the clean body** — entities decoded, links flattened
  to plain text. `original_post_text` and `post_text_html` are longer but
  carry `&apos;` and `<a class="link">` markup. Longer is not better here.
- **`[T]` `limit_per_input` is honored** — `3` returned exactly 3.
- **`[T]` Job latency 15–75s** across the four runs, well inside a 300s poll
  timeout.
- **`[T]` The async trigger → poll → fetch flow with a bare-array body works**,
  identical to Instagram.

### Broken — Pulse articles (`discover_by=url`)

**`[T]` The article mode does not return articles, and does not return the
requested author's content at all.** Tested against both authors in Bright
Data's own snippet:

- `/today/author/stevenouri` → 1 post by **genai-works**, an Organization
- `/today/author/cristianbrunori` → 3 posts by **andrea-girotto**,
  **francesco-casoli-1a187746**, **giampaolocolletti**

Zero articles, zero by the requested author, two out of two. `post_type` never
returned `article` in any of the 10 records observed.

This mode is **dropped from scope**. Had it shipped, it would have failed in
the worst available way: jobs succeed, records land, files are written, billing
accrues, and the handle's folder fills with strangers' posts indefinitely.

### Constrained — profile mode returns a feed, not authorship

**`[T]` `discover_by=profile_url` returns the tracked person's profile
activity, including posts written by other people.** Querying `/in/bettywliu`
returned 3 rows, one authored by `mattwilkerson` (`user_id` and `use_url` both
his). Company mode showed no such contamination — all 3 `lanieri` rows were
genuinely authored by `lanieri`.

**Decision: profile mode keeps only rows whose `user_id` matches the tracked
handle**, so that `output/brand-intel/linkedin-profile/<handle>/` keeps the
same meaning every other adapter's directory has — "things this account
wrote". Consequences are recorded under "Cost model" and "Error handling"
rather than waved past.

### Other observed facts

- **`[T]` Rows arrive unsorted by date** — the profile batch came back
  `Jul 8, Jul 14, Jul 3`. `enumerate_newest_first` must sort; the engine's
  early-stop dedup assumes newest-first ordering.
- **`[T]` `post_type` observed values: `post`, `repost`.** Display-cased values
  were not observed, but normalization lowercases regardless, matching
  Instagram.
- **`[T]` `account_type` is `Person` or `Organization`.**
- **`[T]` URLs may use locale domains** (`it.linkedin.com/posts/...`), and
  `use_url` sometimes carries `?trk=` tracking parameters. Never key identity
  on a URL; `id` is the key.
- **`[T]` `title` is an SEO-style string** with hashtags and author appended
  (`"#personalbrand #leadership | Betty Liu"`). `headline` is the post's first
  line and is the better title source.
- **`[T-unverified, 2026-08-07]`** Billing granularity — per record vs. per-job
  minimum, and whether failed/timed-out jobs are charged — remains unconfirmed,
  the same open item Instagram left. Four LinkedIn jobs plus the earlier
  Instagram jobs are now on the dashboard's usage page to check against.
- **`[T-unverified, 2026-08-07]`** Profile mode's input accepts
  `start_date`/`end_date` in Bright Data's snippet. Whether `/trigger` honors
  them was not tested. This is the one plausible future path to real LinkedIn
  backfill.

## Architecture

### New: `pipeline_app/brightdata_job.py`

Everything Bright Data-generic, extracted from `discovery_instagram.py` as a
pure refactor with no behavior change:

- `api_key()` — `BRIGHTDATA_API_KEY` env var, then the gitignored
  `brightdata_api_key.txt`, matching `discovery_youtube_api.api_key()`.
- `BrightDataJobTimeout`, `BrightDataJobFailed`.
- `run_job(dataset_id, params, body, *, poll_timeout_s, poll_interval_s) -> list[dict]`
  — trigger → poll → fetch, raising on timeout or `failed` rather than
  returning `[]`.

This cycle is the part that was expensive to get right, and its error
discipline is what keeps a failed paid job from reading as healthy. Two copies
of it would mean the next Bright Data change has to be found and fixed twice.

### New: `pipeline_app/discovery_linkedin.py`

A `LinkedInAdapter` bound to a mode at construction, holding only the
LinkedIn-specific parts: dataset id, `discover_by` value, URL template, author
filter, row normalization. The `PlatformAdapter` protocol is structural, so an
instance satisfies it exactly as a module does.

Its enumerate cache is a **per-instance** dict, not module-level. Two modes
share one class, and a company slug can equal a person slug — a shared
`{handle: rows}` cache would let one mode's batch serve the other's
`download_item`.

### Modified

- `discovery_instagram.py` — delegates its job cycle to `brightdata_job`.
- `run_discovery_cron.py`'s `build_adapters()` — adds `"linkedin-profile"` and
  `"linkedin-company"`.
- `templates/discovery_handles.html` — two new `<option>` values.

### Not modified

`discovery_engine.py`. `BACKFILL_SUPPORTED_PLATFORMS` is a whitelist of
`{"youtube", "bluesky"}`, so both LinkedIn platforms are already rejected from
backfill with a logged skip and no adapter call. Instagram needed that guard
added; LinkedIn inherits it.

### Handle model

Handles are bare slugs — `bettywliu`, `lanieri` — with the mode carried by the
platform value chosen in the dropdown. This keeps `UNIQUE(platform, handle)`
meaningful, makes run records and the discovery email name the mode, and lets
output directories fall out of the existing `handle_dir(repo_root, platform,
handle)` with no path special-casing:

- `linkedin-profile` → `https://www.linkedin.com/in/<slug>` →
  `output/brand-intel/linkedin-profile/<slug>/`
- `linkedin-company` → `https://www.linkedin.com/company/<slug>` →
  `output/brand-intel/linkedin-company/<slug>/`

Storing a full pasted URL as the handle was considered and rejected: LinkedIn
URLs carry `?trk=` tracking parameters, so two rows could describe the same
account, and `slugify()` mangles the result into an unreadable directory name.

## Data contract

| Output field | Source | Note |
|---|---|---|
| `id` | `id` | string; the sole identity key |
| `published` | `date_posted[:10]` | ISO 8601 Z, verified |
| body | `post_text` | **not** `original_post_text` / `post_text_html` |
| `title` | `headline`, else first line of `post_text`, else `id`; truncated to 60 | `title` field is SEO text, unusable |
| `content_type` | `post_type`, lowercased | `post`, `repost` |
| `author` | `user_id` | drives the profile filter |
| `account_type` | `account_type`, lowercased | `person`, `organization` |
| `like_count` | `num_likes` | |
| `comment_count` | `num_comments` | |
| `hashtags` | `hashtags` | list or null; `yaml.safe_dump` renders lists natively |
| `url` | `url` | informational; locale domains possible |

**A row is dropped if** it has no `id`, no parseable `published`, or — in
profile mode only — `user_id` does not match the tracked handle
case-insensitively. Drop counts are logged to stderr, matching Instagram, so a
mode that begins returning strangers becomes visible rather than silent.

**Order of operations:** normalize → drop → **sort newest-first** → cap to
`MAX_ITEMS_PER_RUN` → apply `keyword_filter`. The sort is load-bearing (rows
arrive unsorted, verified); the cap is applied after filtering so it bounds
retained items; `keyword_filter` is a case-insensitive substring match against
`post_text`, matching `discovery_bluesky.py`.

### File format

One `.md` per post, named `<id>.md`, written with the existing
write-temp-then-rename so an interrupted write never leaves a truncated file at
a path `on_disk_ids()` would treat as captured:

```
---
post_id: <string>
url: <string>
handle: <tracked handle>
author: <user_id>
account_type: person | organization
content_type: post | repost
published: <YYYY-MM-DD>
like_count: <int | null>
comment_count: <int | null>
hashtags: [<string>, ...]
fetched_at: <ISO 8601 UTC>
---

<post_text, or "(empty)">
```

`author` is recorded even in profile mode, where the filter guarantees it
matches the handle. It is what makes a filtering regression detectable after
the fact, and it is independently meaningful for company posts.

## Cost model

`MAX_ITEMS_PER_RUN = 10`, daily, both modes — matching Instagram, one constant,
one cadence, no engine change. That is 300 records/month per handle; at the
survey's ~$1.50–4.00/1k, **~$0.45–1.20/month per handle**.

Cost is not the binding constraint here the way it was for Instagram, but two
effects are real:

- **Profile mode pays for rows it discards.** The author filter runs after
  billing. At the observed 1-in-3 contamination rate, effective cost per
  retained file is ~1.5× — call it $0.68–1.80/month for a profile handle. An
  account that mostly engages rather than posts could be far worse, and the
  symptom is a nearly-empty folder rather than an error.
- **Every run re-pays for the same top-N**, including on days with no new
  posts. `on_disk_ids` prevents re-writing files, but only after collection has
  been billed. The cap bounds this; nothing removes it.

Relationship to tune against: `monthly ≈ handles × 30 × MAX_ITEMS_PER_RUN ×
per_record_cost`. Re-tuning is a manual judgment call at registration time; the
adapter does not enforce a budget.

## Error handling

The Instagram contract carries over unchanged:

- **Poll timeout** → raise `BrightDataJobTimeout`.
- **Job reports `failed`** → raise `BrightDataJobFailed`.
- **Job `ready` with zero rows** → return `[]`, the one case that honestly
  means "nothing to report".

Both raises land in `run_discovery`'s per-handle `except Exception`, recorded
as a normal `error` result and retried on the next run.

### The filter opens a new silent-failure door

LinkedIn adds a failure mode Instagram does not have:

> A job returns 10 rows, the author filter drops all 10,
> `enumerate_newest_first` returns `[]`, and `process_handle` records a healthy
> `no_new_content` — for a batch that was paid for.

This is the same *shape* as Instagram's date bug arriving through a different
door. It is not treated as an error, because a legitimate case exists (the
person genuinely only engaged with others' posts this period). Instead, when
`rows_returned > 0 and rows_kept == 0`, the adapter logs a **distinct** warning
naming the filter as the cause, so the condition is diagnosable rather than
mysterious.

### Named limitation: validation can permanently exclude a profile handle

At registration, `process_handle_validate` marks a handle `invalid` **and
auto-excludes it from all future runs** when enumeration returns nothing. For a
`linkedin-profile` handle whose recent activity is entirely third-party posts,
the author filter produces exactly that outcome — a valid, active account
rejected at registration.

This is pre-existing `validate_handle` behavior, identical to how a transient
network error already behaves for every platform, and no engine change is
proposed for it. It is called out because the author filter makes it
meaningfully more likely on LinkedIn than anywhere else. Recovery is to
re-register the handle.

## Backfill

Unsupported, and requires no code: the existing
`BACKFILL_SUPPORTED_PLATFORMS` whitelist already rejects both LinkedIn
platforms before any adapter call, logging a skip.

Unlike Instagram, a future path exists — profile mode's input accepts
`start_date`/`end_date` per Bright Data's snippet (unverified against
`/trigger`). If LinkedIn backfill is ever wanted, that is where to start, and
it would apply to `linkedin-profile` only.

## Testing

Following `test_discovery_instagram.py`, against a fake HTTP layer with no real
Bright Data calls. Each item below that says "pin" is a regression test for
something live verification actually caught:

- Trigger sends the correct `discover_by` per mode, plus `type=discover_new`
  and `limit_per_input`.
- **Pin:** profile mode drops rows whose `user_id` differs from the handle;
  company mode drops none.
- **Pin:** unsorted input returns newest-first.
- **Pin:** body comes from `post_text`, not `original_post_text` or
  `post_text_html`.
- **Pin:** `date_posted` in the verified ISO-Z form normalizes to
  `YYYY-MM-DD`; a malformed value drops the row rather than raising.
- **Pin:** `repost` survives lowercasing as a valid `content_type`.
- **Pin:** rows returned but all filtered → returns `[]` **and** logs the
  distinct all-filtered warning.
- **Pin:** two adapter instances sharing a handle slug do not share cache
  entries.
- Poll timeout raises; job `failed` raises; `ready` with zero rows returns `[]`.
- `download_item` reads the cache with no second network call; a cache miss
  raises rather than degrading silently.
- `on_disk_ids` dedup; `keyword_filter` applied client-side against
  `post_text`.
- Credential lookup (env var vs. file).
- **Extraction gate:** `discovery_instagram.py`'s existing 38 tests stay green
  after the `brightdata_job` refactor, unchanged.

## Non-goals

Pulse articles (dropped on evidence, above); collect-by-single-post-URL mode;
historical backfill; image/video download; comment capture
(`top_visible_comments` is returned but not stored); automatic re-tuning of
`MAX_ITEMS_PER_RUN` as handles are added; and any attempt to reduce the
vendor-continuity risk described under "Risk posture".

Like Instagram, LinkedIn content enters the corpus as post text only — there is
no transcript equivalent. This is a real asymmetry against the transcript-centric
YouTube material the skills were built from, and it is accepted here rather than
solved.

## Operational note

Bright Data's domains are blocked by DNS-filtering resolvers that categorize
proxy/scraping infrastructure — on this machine, Proton VPN's NetShield. A live
run needs that path clear or every job fails at name resolution before any HTTP
call is made.
