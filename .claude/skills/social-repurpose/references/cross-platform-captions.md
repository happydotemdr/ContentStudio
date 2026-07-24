# Cross-platform caption variants — the honest gap

Source: `docs/headless-youtube-audit.md` §2 ("Channel setup & positioning," the one
cross-platform mention) plus extrapolation from the packaging findings in §7. **Read
this whole file before writing a single non-YouTube caption** — it's the part of this
skill where it's easiest to quietly slide into generic social-media advice, which is
the one thing this project exists to prevent.

The corpus is a **YouTube-focused corpus**: 420 videos across 14 creator-education
channels, none of them TikTok/Instagram/X/Bluesky specialists. Treat that as two
separate layers, not one blob of "the corpus doesn't cover this."

## Layer 1: strategic cross-platform findings — these ARE corpus-grounded, use them directly

- **[C] Platform-fit: "fish where your customers are."** B2B audiences → LinkedIn/
  YouTube; commodity-consumer audiences → TikTok/Instagram (Kallaway, bqzd0h0gmU0).
  Before writing captions for a platform, check the Short's audience actually fits
  that platform rather than cross-posting everywhere by default.
- **[C] The modern stack: one short-form platform for reach, one long-form (YouTube)
  for depth, email for nurture** (Kallaway, wKdElDeMXR0). This is the corpus's actual
  cross-platform model — it does not say "post everywhere"; it says pick *one*
  short-form platform deliberately.
- **[C] Beginners can sprint 3–6 months on short-form to build fundamentals before
  attempting cold-start YouTube** (Kallaway, ceRZVxO8KF8) — relevant if the user is
  sequencing platform launch, not just repurposing one Short.
- **[C] Validate a real offer with paying customers before building the content
  engine** (Kallaway, bqzd0h0gmU0) — a monetization-sequencing note, included for
  completeness; usually out of scope for a single repurposing task.
- **[C] Entity cross-linking: build matching-name accounts on Facebook, Instagram, X,
  Pinterest, LinkedIn and cross-link them bidirectionally with the channel** —
  branded/entity channels are reportedly favored ("NavBoost") (Romayroh, ErCV5czVK1g).
  Repost thumbnails to Pinterest (it ranks in Google Images) and publish
  transcript-based Medium articles for external discovery (Romayroh, G9LfE3k-IEI).
  This supports *having* cross-platform presence as a trust/entity signal — it says
  nothing about how to write a good TikTok caption.

## The corpus's own caution about cross-posting — surface this, don't smooth it over

An honest repurposing skill should note that the corpus is actively **ambivalent**
about the very activity it's assisting with:

- **[C] "Concentrate violent volume on one platform"** rather than spreading thin
  across five algorithms — Kallaway posted only on YouTube for 18 months before
  expanding (Kallaway, 46t_cn0lx2E).
- **[C] Don't over-diversify before closing the beginner skill gap** — spreading thin
  across platforms is cited as the main reason beginners quit (Kallaway,
  DFSU-YPRTs8).

Include a short version of this caution in the output package when the user asks for
captions across many platforms at once — it's a legitimate corpus-grounded reason to
suggest they focus on fewer surfaces, not a hedge to bury.

## Layer 2: per-platform mechanics — the corpus has zero data here

No channel in the corpus produces or studies TikTok, Instagram, X, or Bluesky content.
There is no finding on: caption character limits or ideal length per platform,
hashtag *count* conventions (how many, not whether), trending-sound/audio conventions,
per-platform posting-time windows, thread mechanics, or algorithm behavior on any of
these surfaces.

### How to write a caption anyway: the `[C→I]` extrapolation

Where a corpus-cited YouTube *packaging principle* is general enough to plausibly
transfer, apply it and mark it `[C→I]` — state both halves explicitly: the corpus
citation for the underlying principle, and that its application to this platform is
this skill's own `[I]` extrapolation, not corpus-tested.

Principles usable this way:

- **[C→I] Curiosity gap / specificity / front-loaded hook.** Corpus-cited for YouTube
  titles: trigger curiosity rather than describe, be specific about the avatar, keep
  it short (Dan the creator, CWcalhl86DE; Nick Nimmin, LAzYEKltBwA). `[I]` extrapolation:
  the same shape (a specific, curiosity-driving opening line) is a reasonable caption
  opener for TikTok/Instagram/X — but this is this skill's inference, not a
  cross-platform corpus finding.
- **[C→I] Align the hook layers (what's shown, what's written on screen, what's
  said).** Corpus-cited for YouTube Shorts/videos (Kallaway, i7upRL4H1FM). `[I]`
  extrapolation: a TikTok/Reels caption should not contradict or duplicate the video's
  on-screen text — it should add a layer (context, a question, a stake) rather than
  restate what's already visible. Not corpus-tested on these platforms.
- **[C→I] ~80–85% watch muted; text/visuals must carry meaning** (Kallaway,
  i7upRL4H1FM). `[I]` extrapolation: since this muted-viewing behavior is not
  YouTube-specific in cause (it's a mobile-autoplay pattern), it's a *plausible* but
  unverified basis for assuming captions matter for comprehension on other short-form
  platforms too — flag this as the weakest of the three extrapolations, since the
  underlying stat itself is YouTube's own measurement.

### Explicit `[gap]` list — do not write these as confident rules

For each of the following, if the user's request needs it, say plainly: *"the corpus
does not cover platform-specific mechanics for this"* — do not substitute generic
internet knowledge:

- TikTok: caption length norms, hashtag count/style conventions, sound/trend
  attachment practice, duet/stitch caption conventions.
- Instagram (Reels/feed): caption length norms, hashtag count conventions (the
  "30 hashtags" folk wisdom is not in this corpus), Reels-cover text conventions.
- X (threads/single posts): character-limit-driven caption compression, thread
  structuring, quote-post conventions.
- Bluesky: any posting convention at all — the corpus's one Bluesky-adjacent roster
  entry (a general-interest creator) is explicitly out of scope for ContentStudio (see
  project `CLAUDE.md`) and was not consulted for this skill.
- Any platform: optimal posting time/cadence, algorithm ranking behavior, or
  engagement-bait tactics — none of this is in the corpus for non-YouTube platforms.

## Output format for a caption variant

Write each platform's caption, then immediately follow it with its markers, e.g.:

> **TikTok caption:** "Nobody tells you this about [X] — until it's too late."
> *[C→I]: curiosity-gap phrasing extrapolated from YouTube title principle (Dan the
> creator, CWcalhl86DE); TikTok-specific caption-length/hashtag conventions are
> [gap] — not covered by the corpus.*

This keeps the honesty visible in the deliverable itself, not just in this reference
file.
