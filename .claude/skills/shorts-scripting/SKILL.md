---
name: shorts-scripting
description: Writes a shot-ready YouTube Shorts script — hook, setup, build/value, re-hook, payoff, and loop/CTA — with beat-by-beat timing in seconds, from a validated Shorts concept brief (angle, hook concept, packaging direction). Every structural and retention rule is traced to a specific finding in the ContentStudio corpus (1,100+ findings from a 420-video, 14-channel creator-education research base) with an explicit [C]/[I]/[T] provenance marker — this skill never falls back on generic scriptwriting advice, and says so explicitly when the corpus is thin on something. Use this skill whenever the user has a Shorts concept, angle, or hook direction (including output from the shorts-ideation skill) and wants the actual script written — e.g. "write the script for this Short," "turn this concept into a timed script," "script out this idea," "give me the hook-to-CTA beats for this Short," or "I need a shot-ready script before I brief voiceover/visuals." Also use it to punch up or restructure an existing rough Short script against the corpus's hook/retention/ending rules.
---

# Shorts scripting

Turns a validated Shorts **concept brief** into a **shot-ready, beat-timed
script**: Hook → Setup → Build/Value (with a re-hook) → Payoff → Loop/CTA, each
beat carrying a VO line, a timestamp range, a word count, and a one-line visual
note. Every normative choice in the script traces to a corpus finding with a
`[C]`/`[I]`/`[T]` marker — see `C:\Projects\ContentStudio\CLAUDE.md` for the
project-wide anti-generic guarantee this skill exists to enforce.

## Pipeline position

- **Upstream input:** the `shorts-ideation` skill's concept brief — angle, hook
  concept, packaging direction (title frame, cover text), target avatar. If you
  don't have this, ask for it rather than inventing a concept from scratch;
  this skill scripts a concept, it doesn't originate one.
- **Downstream output feeds two separate skills:**
  - **`voiceover-brief`** — needs each beat's VO line, timestamp range, and
    word count to build the ElevenLabs production brief.
  - **`visual-prompts`** — needs each beat's timestamp range and visual note to
    build the Midjourney prompt sheet.
  Both are authored separately — this skill's job ends at a complete,
  self-contained script; don't reach ahead into voice-setting or image-prompt
  territory (see "What this skill does NOT do" below).

## Provenance discipline (read before writing a single line)

Every reference file in `references/` marks each rule:

- **`[C]`** corpus-cited, attributed `(Channel, video_id)` exactly as the
  corpus states it. Where the corpus flags a finding **strongly-supported**
  (2+ channels) or **medium confidence** (Jenny Hoyos's mostly-observed
  structural technique), carry that flag through into the script's delivery
  notes — don't quietly launder a medium-confidence pattern into a
  stated-with-certainty rule.
- **`[I]`** industry practice — used for three things in this skill: the
  150–170 wpm narration-pace assumption, the re-hook's specific ~15s
  placement (the underlying re-hook *cadence* is `[C]`; the exact timestamp is
  this skill's own synthesis — see `references/beat-timing-model.md`), and
  the requirement of at least one concrete proof beat inside Build/Value (the
  corpus's proof-density cadence is stated for long-form; compressing it into
  a single Shorts-scale beat is this skill's adaptation — see
  `references/retention-loops-and-structure.md`).
- **`[T]`** — not used by this skill; tool/policy facts belong to
  `voiceover-brief` and `visual-prompts`.

If a concept brief needs something the corpus doesn't cover (e.g. genre-specific
hook phrasing, a topic this corpus never touches), say so explicitly in the
script's notes rather than inventing generic advice to fill the gap.

## Process

1. **Confirm the concept brief.** Angle, hook concept, packaging direction,
   target avatar. Missing packaging direction is a blocker for the Hook beat
   specifically — the hook has to pay off the packaging promise
   (`references/hooks-and-openings.md`).
2. **Run the net-information-gain check.** What does this premise say that the
   top existing Shorts on the same topic don't already say? This is a 2026
   corpus-grounded ranking lever, not a nice-to-have
   (`references/script-intelligence-and-delivery.md`).
3. **Pick the length band.** Default to the 35–45s standard beat table; use the
   20–30s compressed band if the brief specifies a punchier target or the
   premise is simple enough not to need a full arc
   (`references/beat-timing-model.md`).
4. **Write Hook (0–3s).** Read `references/hooks-and-openings.md` first — this
   is the single highest-leverage beat: 50–60% of Shorts leavers bail within 3
   seconds `[C] (vidIQ, UCrC5B3Soyc)`. Note whether any Jenny Hoyos
   medium-confidence technique is used.
5. **Write Setup (3–8s).** One sentence of context + stakes. No "in this
   video." Keep it short — front-loaded setup/context is the corpus's
   documented #1 cause of mid-video drop `[C] (vidIQ, DiZnbihU4NM)`.
6. **Write Build/Value (8–28s), with the re-hook folded in at ~15s.** Escalating
   steps, at least one proof beat, contrast language. See
   `references/retention-loops-and-structure.md`.
7. **Write Payoff (28–38s).** Must resolve the *exact* question the Hook asked,
   with a concrete detail, not a vague resolution
   (`references/endings-and-ctas.md`).
8. **Write Loop/CTA (38–45s) + the comment-bait question.** Mirror the Hook's
   phrasing so the ending feeds back into the opening (`references/endings-
   and-ctas.md`).
9. **Run the humanize pass.** Vary sentence length, cut any AI-fingerprint
   phrase or buzzword, fact-check any specific claim
   (`references/script-intelligence-and-delivery.md`).
10. **Add a one-line visual note per beat** — plain language describing what's
    on screen, not a rendered image/video prompt (that's `visual-prompts`'
    job). Flag any beat carrying a spoken statistic or list so it's rendered
    as on-screen text/graphic downstream.
11. **Fill the output contract exactly** (below) and state the up/downstream
    handoff explicitly at the end of the response.

## Beat-timing model (standard 35–45s band)

| Beat | Seconds | Word budget | Job |
|---|---|---|---|
| Hook | 0–3s | 8–15 words | Stop the swipe; provocative question or mid-action drop. |
| Setup | 3–8s | 12–20 words | One sentence of context + stakes. |
| Build/Value | 8–28s | 45–60 words | Escalating steps; re-hook folded in at ~15s. |
| Payoff | 28–38s | 15–25 words | Resolve the exact question the Hook asked. |
| Loop/CTA | 38–45s | 5–12 words | Mirror the Hook; earn a comment with a specific question. |

Total ≈ 90–110 words. Marker key for this table: each beat's **Job** is `[C]`
(cited in `references/hooks-and-openings.md`, `retention-loops-and-structure.md`,
and `endings-and-ctas.md` respectively); the **word-rate assumption** (150–170
wpm) and the **re-hook's ~15s placement** are `[I]` — the underlying re-hook
*cadence* is `[C]`, only the exact timestamp is this skill's synthesis. Full
grounding, the 20–30s compressed band, and the re-hook-timing caveat are in
`references/beat-timing-model.md` — read it before finalizing timing on
anything other than a standard-length Short.

## Output contract

Deliver every script in exactly this shape:

```
=== SHORT SCRIPT — <ID> ===
Concept brief source: <where this came from — e.g. shorts-ideation angle>
Working title:   <from packaging direction>
Single premise:  <one idea only>
Constraint/stake: <the specific limiting factor, if any>
Net-info-gain check: <what this says that the top existing Shorts don't> [C]

HOOK        (0–3s  | N words): "<VO line>"
SETUP       (3–8s  | N words): "<VO line>"
BUILD/VALUE (8–28s | N words): "<VO line(s)>"
  [re-hook beat @ ~15s]: "<VO line>"
PAYOFF      (28–38s | N words): "<VO line>"
LOOP/CTA    (38–45s | N words, mirrors hook): "<VO line>"
Comment-bait question: "<specific question>"
Total word count: ~N words (150–170 wpm)

Visual notes (for visual-prompts downstream):
  Hook: <one line>
  Setup: <one line>
  Build: <one line>
  Re-hook: <one line>
  Payoff: <one line>
  Loop/CTA: <one line>

Delivery notes: <muted-friendly check, medium-confidence flags used (if any),
  humanize-pass confirmation>
```

A full worked example (concept brief → finished script, with citations
annotating each choice) is in `references/worked-example.md` — read it before
your first script if this is a new session.

## What this skill does NOT do

- **Doesn't set ElevenLabs voice/model settings** (stability, similarity,
  audio tags) — that's `voiceover-brief`. Hand it the VO lines and timing only.
- **Doesn't write Midjourney/image-video prompts** — that's `visual-prompts`.
  Hand it the visual notes and timing only.
- **Doesn't decide the concept, title, or thumbnail** — that's `shorts-
  ideation`, upstream. If a concept brief is missing, ask for it.
- **Doesn't invent packaging-adjacent SEO/AEO content** (descriptions,
  hashtags, chapters) — those are long-form-specific corpus findings that
  belong to packaging/repurposing work, not the script itself.

## Reference files

- `references/hooks-and-openings.md` — the 0–3s beat in full, including the
  three Jenny Hoyos medium-confidence techniques.
- `references/retention-loops-and-structure.md` — Setup through Build, the
  re-hook mechanic, contrast/proof-density rules, and the loop-to-start payoff
  mechanic.
- `references/endings-and-ctas.md` — Payoff and Loop/CTA beats, the
  comment-bait question, and where a subscribe ask can fit.
- `references/script-intelligence-and-delivery.md` — the 2026 net-information-
  gain and AI-humanizing rules, plus muted-autoplay/visual-carry delivery
  rules.
- `references/beat-timing-model.md` — the full timing scaffold, the 20–30s
  compressed band, and the re-hook-timing `[I]` caveat explained.
- `references/worked-example.md` — a complete concept-brief-to-script run with
  inline citations.
