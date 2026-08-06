# Social Platform Data Access Survey

**Status:** Reference document (survey, not an implementation spec)
**Date:** 2026-08-06
**Scope:** Instagram, TikTok, X/Twitter, Substack/newsletters, LinkedIn, Threads
**Not covered:** YouTube and Bluesky — already implemented (`pipeline_app/discovery_youtube.py`, `pipeline_app/discovery_bluesky.py`)

## Purpose

The discovery pipeline currently tracks creators on YouTube (via the official Data API)
and Bluesky (via its free, unauthenticated public AppView API). This document surveys
what it would take to add other platforms the same creators post to, so a future
decision about which platform(s) to build next is grounded in current (2026) facts
about API access, cost, and legal/ToS risk — not assumptions.

**This is a survey, not a build plan.** No adapter is being built from this document.
If a specific platform is chosen later, that gets its own brainstorming → design →
plan cycle, following this project's normal process.

## Methodology

Each platform was researched independently via live web search (2026-08-06) against
a common template: official API terms, free/open-source options, paid third-party
aggregators, hard walls, and a fit verdict against this project's existing pattern —
an **unauthenticated, read-only fetch of public content**, matching
`discovery_bluesky.py`'s shape (`on_disk_ids` + `enumerate_newest_first`, no login,
no paid dependency). Every claim below is dated 2026 and sourced; treat pricing and
policy facts as **re-verify-before-relying-on**, consistent with this project's `[T]`
marker convention elsewhere in `docs/`.

## Fit tier summary

| Platform | Fit tier | Cost if pursued | Primary blocker |
|---|---|---|---|
| Substack / beehiiv / Ghost | **Low risk, free** | $0 | None — native public RSS |
| Threads | Medium risk | ~$2/1k (aggregator) | No third-party read API; scraping legally clearer post-2024 ruling but still ToS-violating |
| TikTok | Medium-high risk | ~$1-2/1k (aggregator) or free-but-fragile (yt-dlp) | No usable official API for arbitrary creators; aggressive anti-bot |
| Instagram | Medium-high risk | ~$1-2/1k (aggregator) | Official API needs target's Business/Creator account + app review; personal accounts invisible to API entirely |
| X / Twitter | High cost or high risk | $0.005-0.010/read (official) or account-ban risk (scrapers) | Free tier eliminated Feb 2026; every free path needs an authenticated session |
| LinkedIn | High risk | ~$1.5-4/1k (aggregator) | Read scopes closed to new partners; LinkedIn actively litigates scrapers (Proxycurl shut down mid-2025) |

## Substack / newsletters (Substack, beehiiv, Ghost) `[T, 2026-08-06]`

**Official API / native RSS.** Substack exposes standard Atom/RSS at
`<publication>.substack.com/feed` (works on custom domains too) — no auth required.
Feed caps at ~20 most recent posts, no pagination; paywalled posts show title + short
preview only. beehiiv's RSS Feed is a native, all-plans opt-in feature. Ghost
auto-generates RSS at `/rss/` for every site by default, plus per-tag/author/collection
feeds. Kit (formerly ConvertKit) has no confirmed simple feed URL — needs a
per-creator check.

**Free / open-source options.** None needed — a standard feed parser (e.g. Python
`feedparser`) suffices for Substack, beehiiv, and Ghost. RSS-Bridge exists as a
fallback generator for sites lacking native feeds (e.g. Kit, if it turns out not to
have one).

**Paid third-party aggregators.** Essentially unnecessary for this use case; paid
options (Apify Substack scrapers, FeedMansion) exist for republishing/embedding, not
relevant here.

**What's flatly not possible.** Full paywalled/subscriber-only post body text via RSS
on any of these platforms — Apify's own Substack scraper docs state no
paywall-bypass option exists or will be added.

**Fit verdict.** Realistic and **low** risk/complexity for Substack, beehiiv, and
Ghost — matches the existing unauthenticated-fetch pattern exactly. Kit is the one
gap: verify per-creator whether a usable public feed/archive page exists before
assuming parity; if not, a **medium**-risk HTML-scrape fallback would be needed.

## Threads `[T, 2026-08-06]`

**Official API.** Meta's Threads API (GA July 2024, expanded through 2025-26) is
publish/manage-first — it reads and writes only the *authenticated, connected
account's own* content. An April 2026 update added narrow public-content search
(keyword/media-type/author) and no-token embeds, but there is no endpoint for pulling
an arbitrary creator's full post history. Requires a Meta developer app, app review,
and a linked Instagram/Threads professional account — free but approval-gated.

**Free / open-source options.** Unofficial libraries (e.g. `Danie1/threads-api`)
reverse-engineer Threads' internal API; maintenance status is inconsistent —
verify directly before relying on one. RSS-Bridge lists a community-maintained
Threads bridge.

**Paid third-party aggregators.** Apify Threads scrapers ~$2/1k results; Bright Data
general PAYG ~$1.50/1k records (no Threads-specific price confirmed). Several
smaller vendors (KeyAPI, ScrapeCreators, Data365) offer username-lookup access, no
OAuth needed.

**What's flatly not possible.** No true legal wall for *public, logged-out* data —
*Meta Platforms, Inc. v. Bright Data* (N.D. Cal., Jan 2024) held Meta's ToS don't bind
logged-out scraping of public Meta-family data, and this extends to Threads. What
remains hard is purely technical: rate-limiting, IP-blocking, CAPTCHA gates (same
infrastructure as Instagram).

**Fit verdict.** **Medium** complexity, medium-low legal risk. The official API won't
serve this use case without approval and still lacks full third-party post history.
A paid aggregator (~$2/1k) is the most realistic low-maintenance option if some
ongoing cost is acceptable.

## TikTok `[T, 2026-08-06]`

**Official API.** The Research API is free but categorically closed to commercial/
personal use — gated to qualifying academic institutions and registered nonprofits
studying youth safety, with a weeks-to-months manual review. The Display API only
lets an *authenticated user* pull their *own* content via OAuth — no arbitrary-creator
lookup. The Content Posting API is write-only. **No official surface lets you read a
third party's public videos without that creator's own OAuth grant.**

**Free / open-source options.** yt-dlp is actively maintained (daily commits) but
TikTok extraction breaks intermittently — multiple 2025 GitHub issues show TikTok
changes its internal signing/API often enough to cause recurring regressions.
TikTokApi and similar unofficial Python libraries show no reliable current
maintenance signal; general community sentiment is that most TikTok scrapers on
GitHub are dead. TikTok's 2026 anti-bot stack (ML-based canvas/WebGL fingerprinting)
is explicitly breaking prior scraping techniques.

**Paid third-party aggregators.** Apify TikTok actors from ~$29/mo (compute-unit
based); Bright Data ~$1.50/1k pay-as-you-go or ~$0.95/1k on volume plans from
$499/mo. TikTok's ToS bans scraping outright (contract-breach exposure even where
CFAA-only claims have favored scrapers elsewhere).

**What's flatly not possible.** No unauthenticated, no-signup, RSS/JSON-style public
feed endpoint exists or is documented anywhere for an arbitrary creator's videos.

**Fit verdict.** Does not match the unauthenticated-fetch pattern. Closest realistic
options: yt-dlp for periodic low-volume pulls (low-to-medium cost, needs update
maintenance) or a paid aggregator (~$1-2/1k, low complexity, production-grade
reliability but ongoing ToS risk). Treat as **medium-to-high** risk tier overall.

## Instagram `[T, 2026-08-06]`

**Official API.** The Instagram Graph API's Business Discovery endpoint reads a
third party's public content **only if that account is set to Business/Creator
(Professional)** — personal accounts are invisible to the API entirely. Requires
Facebook Login auth and Meta App Review (manual, days-to-weeks). Free, but the
Basic Display API (the simpler personal-account path) was shut down Dec 2024,
narrowing what's reachable without cooperation.

**Free / open-source options.** instaloader remains the most actively maintained
scraper (last commit April 2026, 12.1k stars), pulling captions/dates from public
profiles unauthenticated via undocumented endpoints — breaks when Instagram changes
those endpoints, and is rate-limited aggressively enough to risk temporary IP/account
restriction. *Meta v. Bright Data* (2024-2025) ultimately favored logged-out public
scraping under the CFAA, but it's still a ToS violation.

**Paid third-party aggregators.** Apify Instagram actors ~$1.00-1.90/1k depending on
type; Bright Data ~$2.50/1k records. Both operate in the same legally-narrowed-but-
still-ToS-violating zone as Threads.

**What's flatly not possible.** No unauthenticated, stable, official feed for
arbitrary public accounts. Personal (non-Professional) account content is
unreachable via any official API path.

**Fit verdict.** **Medium-to-high** complexity/risk — no durable zero-auth endpoint
exists. Apify's pay-per-result actors are the most practical near-term option if
pursued; instaloader is viable only for low-volume, infrequent personal use.

## X / Twitter `[T, 2026-08-06]`

**Official API.** As of Feb 6, 2026, X eliminated subscription tiers for new
signups in favor of pay-per-use credits: $0.005/post read, $0.010/user read,
$0.015/post create. **No free tier remains.** Legacy subscriptions (Basic $200/mo,
Pro $5,000/mo) are being migrated to pay-per-use. Reading one creator's timeline is
technically supported but now carries a running per-request dollar cost with no
free allotment.

**Free / open-source options.** Nitter is effectively dead — X pulled guest API
access in 2023, and nearly all public instances are decommissioned; self-hosted
instances need rotating authenticated guest tokens and are fragile. snscrape is
broken (no meaningful commits since ~2023). Actively maintained alternatives
(Twikit, Twscrape, Scweet) all require login/cookies — none are unauthenticated.

**Paid third-party aggregators.** Apify actors ~$0.15-0.50/1k tweets — the cheapest
practical route if X coverage is required. The official pay-per-use API itself
functions as a paid option now too.

**What's flatly not possible.** No free, unauthenticated, X-hosted way to fetch a
public timeline; no durable free Nitter mirror; scraping without an account
session or paid API key isn't viable at any real reliability.

**Fit verdict.** **Does not fit** the unauthenticated-fetch pattern at all — every
path costs money (official API) or requires session/credential management with ban
risk (scrapers). If X coverage becomes a requirement, use a paid aggregator (Apify)
as a periodic pull rather than trying to match the RSS/JSON pattern.

## LinkedIn (+ business-centric platforms generally) `[T, 2026-08-06]`

**Official API.** Split into ~5 gated tiers; the relevant one (Marketing Developer
Platform) requires a manual partner application, undisclosed timeline (realistically
4 weeks to 4 months), at LinkedIn's discretion. **Critically, `r_member_social`
(read a member's posts/feed) is closed to new partner applications entirely as of
2026** — there is effectively no official, cost-free path to read a third party's
public posts.

**Free / open-source options.** Unofficial libraries (`linkedin-api` forks) wrap
LinkedIn's internal "Voyager" endpoints via a logged-in session cookie; maintenance
is inconsistent, and READMEs explicitly warn of ToS §8.2 violations and ban risk.
Legal landscape: *hiQ Labs v. LinkedIn* (Ninth Circuit, 2022) held scraping publicly
accessible data doesn't violate the CFAA, but the case **settled in Dec 2022** with
hiQ paying LinkedIn $500k and agreeing to a permanent injunction — LinkedIn can still
win on contract/ToS-breach grounds even without a CFAA claim. LinkedIn has enforced
this aggressively since: **Proxycurl shut down July 2025** after a LinkedIn/Microsoft
lawsuit over scraping via fake accounts.

**Paid third-party aggregators.** Apify ~$4/1k profiles; Bright Data ~$1.5-2.5/1k
records. All operate in the same legal exposure zone that closed Proxycurl.

**What's flatly not possible.** No public, unauthenticated read API for a
member/company's posts. `r_member_social` closed to new partners.

**Fit verdict.** **High** risk tier — not realistic at low risk for anything beyond
occasional manual lookups, given LinkedIn's demonstrated willingness to sue
scraping vendors at scale. **Notable adjacent finding:** Medium exposes public RSS
per user/publication (`medium.com/feed/@username`) with zero auth and zero ToS
conflict — a genuinely low-risk business-adjacent platform if any tracked creators
publish there, unlike LinkedIn itself.

## Cross-platform observations

- **RSS-native platforms (Substack/beehiiv/Ghost/Medium) are the only category that
  cleanly matches this project's existing "unauthenticated public fetch" pattern.**
  Everything else requires either paying per-request, running an authenticated
  scraping session with ban risk, or both.
- **The Meta-family platforms (Instagram, Threads) benefit from *Meta v. Bright
  Data*'s 2024 ruling** that logged-out scraping of public content doesn't violate
  the CFAA — but this doesn't eliminate ToS-breach exposure or Meta's ability to
  rate-limit/block at will.
- **X and LinkedIn are the two platforms where pursuing coverage now looks
  actively worse than a year ago** — X eliminated its free tier in Feb 2026, and
  LinkedIn's Proxycurl lawsuit (mid-2025) is a live deterrent example, not a
  hypothetical risk.
- **If a specific platform becomes a priority**, the recommended next step is a
  narrow brainstorm scoped to that one platform (mirroring how `discovery_bluesky.py`
  was built) rather than attempting several at once — cost, auth, and ToS posture
  differ enough that a shared adapter abstraction isn't warranted yet.

## Non-goals

This document does not recommend building any specific adapter. It does not assess
per-creator platform presence (i.e., which of the currently tracked YouTube/Bluesky
creators are actually active on these other platforms) — that would be a
prerequisite question before greenlighting any specific build.
