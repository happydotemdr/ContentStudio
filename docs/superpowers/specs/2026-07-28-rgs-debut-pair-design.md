# RaisingGoodSports Debut Pair — Automated Full-Pipeline Run

**Date:** 2026-07-28
**Status:** approved design
**Goal:** produce two asset-ready YouTube Shorts packages for RaisingGoodSports' first
published content, by running the full ContentStudio pipeline end to end with every
decision made autonomously.

---

## 1. Objective and definition of done

Deliver two complete, validated Shorts packages — grounding brief, concept brief with
packaging, timed script, runnable ElevenLabs configuration, visual prompt sheet, edit
plan, and multi-surface post copy — such that the next action is generating assets, not
making decisions.

Done means:

- Ten reference videos identified and transcribed; a scan document and two sparks written.
- Both Shorts through all seven pipeline stages, artifacts written to the run folder.
- A locked shared visual system both Shorts conform to.
- A validation report from a three-persona cold read, with any routed revisions applied
  and re-validated.
- No image, audio, or video asset generated. This run ends at *ready to generate*.

## 2. Scope boundaries

**In scope:** reference scan, spark generation, seven pipeline stages run twice, shared
visual-system lock, three-persona validation with a bounded revision loop.

**Out of scope:** generating images, audio, or video; rendering thumbnails; creating new
skills; modifying `pipeline.yaml`; any use of `pipeline-app`; publishing anywhere.

**Firewall:** no `brain_*` MCP tool is used. The thinkers and youth-sports corpora are the
local files under `output/thinkers/` and `output/youth-sports/`. No FamilyBrain path,
remote, or reference is introduced.

## 3. Why the pipeline-app is bypassed

`pipeline-app` is built around per-stage human approval gates (`approval_service.py`,
`state_machine.py`). This run is defined by the absence of those gates. Skills are invoked
directly and artifacts are written to a run folder that mirrors `pipeline.yaml`'s stage
prefixes, so the output remains structurally compatible if it is later imported.

## 4. Run layout

```
runs/rgs-debut-<YYYYMMDD-HHMMSS>/
  00-scan/
    reference-scan.md
    sparks.md
  visual-system.md
  short-a/
    00-grounding/  01-ideation/  02-scripting/
    03-voiceover/  03-visual/    04-assembly/  05-repurpose/
  short-b/
    (same)
  06-validation/
    panel-report.md
```

Raw transcripts land in `output/rgs-reference/2026-07-28/` — git-ignored, consistent with
the existing `output/` convention. Everything under `runs/` is committed; it is the
deliverable.

Grounding briefs are additionally written to `rgs-briefs/YYYY-MM-DD-<slug>.md` per the
`rgs-grounding` skill's own contract, and referenced from the run folder.

## 5. Stage 0 — reference scan

### 5.1 Discovery

Topic seeds: travel and club sports cost, early specialization, kids quitting sports,
sideline parent behavior, youth sports burnout, pay-to-play.

Candidates are surfaced by web search plus `yt-dlp` keyword search, then filtered by hand
for genuine youth-sports-culture relevance. Generic sports highlights, generic parenting
content, and athlete-training content are excluded.

- **5 Shorts** — published within the last 90 days, high view count relative to their
  channel.
- **5 long-form videos** — relevant youth-sports or parenting videos and podcast segments,
  any recency.

**Terminology.** These are described throughout as *high-performing recent* videos, not
*trending*. YouTube exposes no public trending API scoped to a niche; view-sorted search
within a recent window is the available proxy and the spec says so rather than
overclaiming.

### 5.2 Transcription

Transcripts are fetched using the same approach as `download_brandintel.py` — `yt-dlp`
auto-subs written to VTT and cleaned to plain text, with `youtube-transcript-api` as
fallback — pointed at explicit video IDs instead of a channel manifest. No new durable
script is added; this is a one-off fetch.

**Failure handling.** If a video yields no transcript after both paths, it is replaced
with the next qualifying candidate. If fewer than 4 Shorts or 4 long-form videos can be
transcribed, the scan proceeds with what was obtained and `reference-scan.md` states the
shortfall explicitly rather than padding the set.

### 5.3 Output

`00-scan/reference-scan.md` contains:

- A ten-row table: title, channel, view count, publish date, format, **hook pattern**,
  **angle taken**.
- A **white-space section**: what this cohort is not saying that RaisingGoodSports'
  thinker backbone is positioned to say. This section, not the table, is what feeds the
  sparks.

## 6. Stage 0.5 — sparks

Two sparks derived from the white-space section. Each is cross-checked against the brand
focus statement in `output/raisinggoodsports-brand-definition.md` and against the existing
briefs in `rgs-briefs/` so an already-covered topic is not relaunched.

Written to `00-scan/sparks.md`.

### Archetype assignment

- **Short A — A1**, "the thinker who saw it coming." This is the brand's stated
  differentiator and the correct thing to lead a channel with.
- **Short B — A3**, "what the kid hears."

**A2 is deliberately excluded from the debut.** The brand definition records that A2
routinely cites injury and health data, and that YouTube's inauthentic-content policy bars
AI personas presenting as health authorities. That is an unnecessary risk to carry on a
channel's first two uploads.

## 7. Stages 1–7 — the pipeline, run twice

Executed per `pipeline.yaml`:

| Stage | Skill | Specialist | Produces |
|---|---|---|---|
| grounding | `rgs-grounding` | — | verified thinker × research brief |
| ideation | `shorts-ideation` | — | concept brief, angle, hook, packaging |
| scripting | `shorts-scripting` | — | beat-timed shot-ready script |
| voiceover | `voiceover-brief` | `elevenlabs-audio` | runnable TTS configuration |
| visual | `visual-prompts` | `midjourney-prompting` | prompt sheet keyed to beats |
| assembly | `shorts-assembly` | — | edit plan, captions, safe zones, loudness |
| repurpose | `social-repurpose` | — | multi-surface post copy |

### Autonomy rule

Every skill's non-interactive fallback is taken: proceed with the top-ranked option and
record the alternatives in an "alternates considered" section rather than stopping for a
human pick. This applies to the `rgs-grounding` pairing slate, the ideation angle choice,
and any other point a skill would normally hand back.

### Grounding constraints

Two briefs, two different thinkers. The recency rule in `rgs-grounding` is applied against
the sixteen existing briefs in `rgs-briefs/`: Plutarch (used 2026-07-27) and Adler are
recently spent and are deprioritized — not excluded. Corpus edition freshness is checked
against `references/pairing-map.md` before citing, per the skill's own protocol.

### Packaging precedence

The brand's binding do/don't rule is honored literally: the title and thumbnail concept
are produced in the ideation stage and evaluated *before* the script is written. If the
packaging is not compelling, that spark is reworked rather than scripted.

### Voice path

ElevenLabs TTS, fully specified. `voiceover-brief` makes the creative call — voice
character, delivery, loudness and music-ducking target — and `elevenlabs-audio` emits the
executable configuration: voice pick, model routing, stability/similarity/style/speed,
tag-annotated directorial script, pronunciation dictionary, JSON request payload, and
credit estimate.

The AI-disclosure line the brand policy mandates is carried into the assembly plan and the
post copy, not left as an afterthought.

## 8. Asset economy

This is the constraint that shapes stages 5 through 7.

### 8.1 The visual system is locked once

`visual-system.md` is written **before either Short's visual stage** and binds both:

- One `--sref` style code strategy and one seed discipline for consistency.
- The palette from the brand's visual block: deep teal-ink `#0E3B43` ground, warm amber
  `#F2A541` accent, warm off-white `#F7F3E8` type, muted clay `#C1543A` reserved for
  "the system" framing only.
- The **anonymous human presence** resolution: cleats on a bench, a parent's shoulders on
  a sideline, hands gripping a fence, a silhouette against field lights. No host face, and
  not an empty frame.
- One caption and overlay treatment; one thumbnail layout — ground field, amber accent
  word, subject right of center, three to five words left.

Per the brand's own conclusion that consistency is the actual asset: change the words, not
the system.

### 8.2 Reuse is explicit, not hoped for

Short A's visual stage runs first and establishes the still pool. Short B's prompt sheet
marks **every shot REUSE or NEW** against that pool. Target combined asset count is
approximately 1.5× a single Short's, not 2×.

Image-to-video prompts are rationed to beats that genuinely require motion. Remaining
beats are stills with movement introduced in the edit (push-in, parallax, whip cut), which
the assembly plan specifies.

### 8.3 One video export, six surfaces

A single 9:16 export per Short serves YouTube Shorts, TikTok, and Instagram Reels
unchanged — only caption and hashtag copy differ per platform. Bluesky, Threads, and X
receive text-only posts that carry the idea without the video.

`social-repurpose` therefore produces, per Short: YouTube title, description, and
hashtags; TikTok and Instagram Reels captions; and three text-only posts.

## 9. Stage 8 — validation

### 9.1 The panel

Three fresh agents with no pipeline context read the finished packages cold, each as a
target audience member:

1. **The over-committed travel-team parent** — spending heavily, privately exhausted.
2. **The quietly-uneasy dad** — suspects it is too much, has not said so out loud.
3. **The youth coach** — secondary audience, sees the system from inside.

### 9.2 Scoring

Each persona scores **relevance, coherence, and engagement**, plus the brand's hard tests:

- Does this blame me, or blame the system?
- Does it read as scoldy, preachy, or doom-mongering?
- Does the hook land within 2 seconds, visually and verbally?
- Is every health or injury claim attributed to a named source on-screen and in voiceover?
- Are quotability flags respected — `paraphrase-caution` thinkers never on a quote card?
- Does it end on relief and agency?
- Is banned lexicon absent?

### 9.3 Revision loop

A finding routes back to the stage that owns it, that stage is re-run, and the package is
re-validated. **Maximum two rounds.** Anything unresolved after the second round is
reported as open rather than looped on further.

Output: `06-validation/panel-report.md`, including what was flagged, what was changed, and
what remains open.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `yt-dlp` unavailable or network-blocked | Verify before the scan begins; fall back to `youtube-transcript-api` directly, and if both fail, stop and report rather than proceeding with an ungrounded scan |
| Transcripts unavailable for chosen videos | Substitute next candidate; report shortfall honestly if the set cannot be filled |
| Corpus edition drift between `pairing-map.md` and the research files | The `rgs-grounding` protocol's edition check is run, not skipped; a mismatch is flagged in the brief |
| Both sparks converge on the same underlying idea | Sparks are checked against each other, not only against existing briefs; the second is reworked if it collapses into the first |
| Shared visual system makes both Shorts feel identical | The system fixes palette, type, and subject treatment — not motif. Each Short gets its own motif family within the shared system |
| Validation loops indefinitely | Hard cap of two rounds, then report open items |

## 11. Assumptions

- Network access is available for video discovery and transcript fetching.
- The local corpora under `output/thinkers/` and `output/youth-sports/` are present and
  current enough to ground two briefs; the edition check will surface it if not.
- `output/raisinggoodsports-brand-definition.md` is the authoritative brand reference for
  this run.
- ElevenLabs credits are not consumed by this run — only the configuration is produced.
