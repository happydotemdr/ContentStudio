---
name: social-repurpose
description: Generate multi-surface post copy (YouTube title/description/hashtags plus cross-platform caption variants for TikTok/Instagram/X/Bluesky) from a finished faceless-YouTube-Short's script and packaging direction. This is the final stage of the ContentStudio six-skill pipeline — use it after a Short has been assembled (script + voiceover brief + visual prompts + edit plan from shorts-assembly) and you need publish-ready copy for YouTube and repurposed captions elsewhere. Trigger this whenever the user asks to write a YouTube title, description, or hashtags for a Short; asks to "repurpose," "cross-post," or write captions for TikTok/Instagram/X/Bluesky/Threads from a video; or wants the final post-copy package for a produced Short. Every normative line traces to the ContentStudio corpus (docs/headless-youtube-audit.md) with [C]/[I]/[T] provenance markers — do not invent generic social-media best practices.
---

# Social Repurpose

Stage 6 of 6 — the final stage of the ContentStudio pipeline. Turns a **finished Short**
into the **multi-surface post copy** that ships it. There is no downstream stage: this
skill's output is the pipeline's final deliverable.

**Upstream input** (from `shorts-assembly`): the finished Short's script, its packaging
direction (working title/angle decided at `shorts-ideation`), and the edit/assembly plan.
You need the script text (for AEO specifics and hook language) and whatever title/thumbnail
direction earlier stages already committed to — this skill does not re-derive thumbnail
design (that's `shorts-ideation`/`shorts-assembly` territory); it writes the **text** that
accompanies the finished video. **If the script or assembly plan carries a "constraints that survive to publish" line** (e.g. a mandatory safety-resource mention), honor it in the
post copy you write — this skill doesn't need to know what produced the constraint, only that it's
flagged.

**Output contract:**
1. A **YouTube package** — title, description, hashtags, and a pinned-comment
   suggestion — sized correctly for a Short (not the long-form AEO treatment; see
   `references/youtube-description-hashtags.md`).
2. **Cross-platform caption variants** for whichever other surfaces the user names
   (TikTok, Instagram Reels, X, Bluesky, Threads, etc.), each one marked per the honest
   corpus-coverage gap below.

## Provenance discipline (read before writing anything)

Every normative sentence you write carries a marker, copied verbatim from the corpus:

- **`[C]` corpus-cited** — `(Channel, video_id)`, exactly as it appears in
  `docs/headless-youtube-audit.md`.
- **`[I]` industry practice** — not corpus-specific.
- **`[T]` tool/policy fact** — dated 2026-07-23, flag as needing re-verification.
- **`[C→I]` compound marker** (this skill's own convention, explained below) — a
  corpus-cited *principle* extrapolated to a surface the corpus doesn't cover.
- **`[gap]`** — the corpus is silent and no reasonable extrapolation exists; say so
  instead of inventing a rule.

A line with no marker is a bug — it means you invented it. This applies with extra force
in this skill, because its whole second half (cross-platform captions) sits on the
thinnest part of the corpus. See "The honest gap" below before writing any non-YouTube
copy.

## The honest gap: this is a YouTube corpus

The 420-video / 14-channel corpus is YouTube-focused. It is **dense** on YouTube
packaging (titles, thumbnails, CTR — audit §7) and YouTube distribution/AEO (audit §8).
It has only a **thin, strategic** mention of cross-platform distribution (audit §2 —
Kallaway's platform-fit and "one short-form platform + one long-form + email" framing)
and **zero** channel-specific findings on TikTok, Instagram, X, or Bluesky mechanics —
no caption-length norms, no per-platform hashtag counts, no trending-sound conventions,
no posting-time data for those surfaces. No channel in the corpus is a specialist on
those platforms.

Do not fill that gap with invented "social media best practices." Instead, for each
cross-platform caption:
- If it's a direct application of a corpus-cited YouTube packaging *principle*
  (curiosity gap, specificity, front-loaded hook, hook-layer alignment, muted-viewing
  text-carries-context), write it, mark it `[C→I]`, and state both halves: which
  finding is `[C]`-cited and that its use on this platform is your own `[I]`
  extrapolation, not corpus-tested.
- If there's no principle to extrapolate from (a platform mechanic — length limits,
  hashtag conventions, algorithm behavior), write `[gap]: the corpus does not cover
  platform-specific mechanics for <surface>` rather than guessing.

Full detail and the per-platform breakdown: `references/cross-platform-captions.md`.

## Workflow

1. **Gather inputs.** Confirm you have: the Short's script/hook language, its working
   title/angle from upstream, and which non-YouTube surfaces (if any) the user wants
   captions for. If a surface isn't named, ask rather than defaulting to all of them.

2. **Write the YouTube title.** Apply the corpus-dense title rules —
   `references/youtube-title-rules.md`. Check the title against the 2026 title-frame
   lift data and the revenue-title data in that file; note which frame(s) you used.

3. **Write the YouTube description + hashtags, sized for a Short.** This is the part
   most likely to go wrong by over-applying long-form advice — the corpus's dense
   500+-word AEO description guidance is long-form-cited (94%+ of AI-cited videos were
   long-form). For a standalone Short, the corpus prescribes a *lighter* package: a
   short SEO description and 1–6 niche hashtags, plus a pinned-comment suggestion
   (open-ended question, optionally linking a related money/pillar video). Read
   `references/youtube-description-hashtags.md` before writing this section — it also
   holds the corpus's own preserved SEO-dead-vs-AEO-critical disagreement, the
   pinned-comment rule, and what to do differently if this Short has a long-form
   companion piece.

4. **Write cross-platform caption variants**, per the honest-gap handling above and
   the full detail in `references/cross-platform-captions.md`. Every caption gets a
   marker; platforms with no corpus grounding at all still get a caption (using the
   `[C→I]` extrapolation) but flagged mechanics (`[gap]`) stay flagged, not smoothed
   over into confident advice.

5. **Assemble the final package** in the format shown in
   `references/worked-example.md` — YouTube block first, then one block per requested
   platform, each caption followed by its markers/citations so the user can see exactly
   what's corpus-grounded and what's extrapolated.

## Reference files

- `references/youtube-title-rules.md` — title-writing rules, 2026 frame-lift data,
  revenue-title data, the Shorts-specific title constraint (one title, no A/B test).
- `references/youtube-description-hashtags.md` — description sizing (Short vs
  long-form), hashtag count, AEO specifics, the preserved SEO-dead/AEO-critical
  disagreement, transcript/chapter notes (chapters are N/A for a pure Short), and the
  pinned-comment rule.
- `references/cross-platform-captions.md` — the strategic cross-platform findings that
  *are* corpus-grounded, the `[C→I]` extrapolation method, and the explicit `[gap]`
  list of what the corpus doesn't cover.
- `references/worked-example.md` — a full run: a finished Short's script/packaging
  through to a complete multi-surface post-copy package, with markers intact.
