# Paid Scraping Aggregator Cost Comparison: Apify vs. Bright Data

**Status:** Reference document (decision analysis, not an implementation spec)
**Date:** 2026-08-06
**Follows from:** [`2026-08-06-social-platform-data-access-survey.md`](2026-08-06-social-platform-data-access-survey.md),
which identified Apify and Bright Data as the only two paid aggregators with
consistent coverage across all five non-RSS platforms (Instagram, TikTok, X/Twitter,
LinkedIn, Threads).

## Purpose

Narrow the prior survey's "paid aggregator" category to a single recommendation, with
a concrete cost estimate at a realistic monitoring volume, so a future decision to
actually integrate one is grounded in real numbers rather than the survey's per-1k
cost ranges.

**This is a decision analysis, not a build plan.** No integration is being built from
this document.

## Volume assumption

**1,000 items/month per platform** (5,000 items/month total across Instagram, TikTok,
X/Twitter, LinkedIn, Threads) — a realistic budget for monitoring a handful of
creators per platform at the pipeline's existing daily-cron cadence. Substack/beehiiv/
Ghost/Medium and YouTube/Bluesky are excluded: the first group is free via native RSS,
the second is already implemented.

## Apify `[T, 2026-08-06]`

**Per-platform actor and pricing** (pay-per-event, verified against apify.com listings):

| Platform | Actor | Cost/1,000 items |
|---|---|---|
| Instagram | `apidojo/instagram-scraper` | $0.47–0.50 |
| TikTok | `clockworks/tiktok-scraper` | $1.70 |
| X/Twitter | `apidojo/tweet-scraper` (Tweet Scraper V2) | $0.40 (min. 50/query) |
| LinkedIn | `harvestapi/linkedin-profile-posts` | $2.00 |
| Threads | `automation-lab/threads-scraper` | $5.02 (Free/Starter tier) → $1.20 (Business tier) |

**Actor usage subtotal at 1,000/platform: ≈ $9.62/month.**

**Platform plans** (apify.com/pricing): Free ($0/mo, $5 credit, 25 concurrent runs) →
Starter ($29/mo, $29 credit) → Scale ($199/mo) → Business ($999/mo). The plan fee
functions as prepaid credit that actor charges draw down.

Free tier's $5/month credit doesn't cover the $9.62 actor usage total, and its low
retention/rate limits make it unreliable for scheduled monitoring. **Starter ($29/mo)
is the realistic minimum** — it fully absorbs the $9.62 in usage with ~$19/mo of
buffer for retries and failed runs.

**Realistic monthly bill: $29/month** (the Starter plan fee itself).

## Bright Data `[T, 2026-08-06]`

**Per-platform product and pricing** (Web Scraper API — structured on-demand
endpoint, verified against brightdata.com product pages):

| Platform | Product | Cost/1,000 items (PAYG) |
|---|---|---|
| Instagram | Instagram Posts Scraper API | ~$2.00 |
| TikTok | TikTok Scraper API | $1.00 |
| X/Twitter | Twitter Scraper API | $1.50 |
| LinkedIn | LinkedIn Posts/Profile Scraper API | $1.50 PAYG ($0.75–0.98 on subscription) |
| Threads | Threads Scraper API | ~$2.50 (estimated; not separately published) |

**Usage subtotal at 1,000/platform: ≈ $8.50/month.**

**Platform plans**: Pay-As-You-Go (no commitment, $4–8/CPM) vs. Growth ($499/mo) vs.
Business ($999/mo) vs. Premium ($1,999/mo) — these govern the underlying proxy
infrastructure some products bill through. Not relevant at this volume; PAYG is
unambiguously cheaper than any subscription tier below ~200K requests/month.

**Every product above ships a recurring 5,000 free records/month.** At 1,000
items/platform/month, usage sits entirely inside each product's own free allowance.

**Realistic monthly bill: $0/month**, using only the recurring free tier — with PAYG
(~$8.50/mo total) as the fallback if free-tier throttling or reliability proves
unsuitable for unattended scheduled monitoring.

## Head-to-head

| | Apify | Bright Data |
|---|---|---|
| Usage cost at 1k/platform | ~$9.62/mo | ~$8.50/mo |
| Realistic monthly bill | **$29/mo** | **$0/mo** |
| Legal standing | No comparable case law | Won *Meta v. Bright Data* (N.D. Cal., Jan 23 2024) — logged-out public scraping doesn't breach ToS, the most consequential U.S. scraping precedent to date |
| Ecosystem | Broader actor marketplace, well-known community-maintained actors per platform | Fewer named per-platform products, more infra-oriented (Scraper API / Datasets) |
| Cheapest single platform | X/Twitter $0.40/1k | TikTok $1.00/1k |
| Most expensive platform | Threads $5.02/1k (Free/Starter) | Threads ~$2.50/1k (estimated) |
| Reliability posture | Actively updated marketplace actors, but community actors break periodically on platform changes | Same general risk; no evidence of materially better uptime at this survey's depth |

## Recommendation

**Bright Data**, for two compounding reasons: it's free at this volume (Apify forces
a paid platform plan even though raw usage is cheap, because Apify has no
usage-only-no-subscription path at reliable scheduling), and it carries the strongest
legal precedent in the paid-aggregator space. Apify's advantages — a broader actor
marketplace and finer per-platform pricing granularity — matter more at higher volume
or as a per-platform fallback than as a wholesale alternative.

**Suggested approach if this is pursued:** start entirely on Bright Data's free tier
to validate reliability empirically before spending anything; keep Apify's
`apidojo/tweet-scraper` ($0.40/1k, cheapest X option found) in reserve as a
per-platform substitute if Bright Data's product for a specific platform proves
unreliable, rather than committing to one vendor exclusively.

## Optimization tactics (both vendors)

- **Reuse the existing watermark pattern.** The YouTube adapter already tracks
  `fetched_at >= run.started_at` to avoid re-processing known items; the same
  approach (track last-seen post ID/date per handle) applies here so scheduled runs
  only pay for genuinely new items, not full re-fetches.
- **Match the existing cron cadence.** Usage cost scales linearly with poll
  frequency — daily polling (matching the current discovery cron) rather than hourly
  keeps volume, and therefore cost, predictable.
- **Validate on free tiers first.** Both vendors offer a free allowance
  (Bright Data's 5,000/month recurring; Apify's $5/month credit) — use these to
  prove out reliability before committing real spend.
- **Mix vendors per platform if needed.** No requirement to use one vendor
  exclusively — if Bright Data's product for a given platform underperforms, swap in
  the cheaper/better-reviewed Apify actor for that platform alone.
- **Budget for actor/product churn as ongoing maintenance,** not a one-time
  integration cost — both vendors' scrapers break periodically when target platforms
  change their internals.

## Non-goals

This document does not recommend building any integration. It assumes but does not
verify that the currently tracked creators are actually active on these platforms —
that per-creator presence check remains a prerequisite for any future build decision,
as noted in the prior survey.
