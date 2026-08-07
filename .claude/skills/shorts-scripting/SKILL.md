---
name: shorts-scripting
description: Writes a shot-ready, beat-timed YouTube Shorts script (hook through loop/CTA) from a validated Shorts concept brief. Every rule traces to the ContentStudio corpus (1,100+ findings, 420 videos, 14 channels) with an explicit [C]/[I]/[T] marker — never generic scriptwriting advice; gaps are flagged, not filled. Use whenever the user has a Shorts concept, angle, or hook direction (including shorts-ideation output) and wants the script written — e.g. "write the script for this Short," "turn this concept into a timed script," "script out this idea," "give me the hook-to-CTA beats for this Short," or "I need a shot-ready script before I brief voiceover/visuals." Also use to punch up or restructure an existing rough Short script against the corpus's hook/retention/ending rules.
---

# Shorts scripting

Turns a validated Shorts **concept brief** into a **shot-ready, beat-timed
script**: Hook → Setup → Build/Value (with a re-hook) → Payoff → Loop/CTA, each
beat carrying a VO line, a timestamp range, a word count, and a one-line visual
note. Every normative choice in the script traces to a corpus finding with a
`[C]`/`[I]`/`[T]` marker — see the project's `CLAUDE.md` for the
project-wide anti-generic guarantee this skill exists to enforce.

## Pipeline position

- **Upstream input:** the `shorts-ideation` skill's concept brief — angle, hook
  concept, packaging direction (title frame, cover text), target avatar. If you
  don't have this, ask for it rather than inventing a concept from scratch;
  this skill scripts a concept, it doesn't originate one. **Optionally**, a companion grounding
  artifact may also be handed to this skill directly, or reached via the concept brief's
  "Grounding" section — see "Optional input" below.
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
- **`[I]`** industry practice — used for five things in this skill: the
  150–170 wpm narration-pace assumption, the re-hook's specific ~15s
  placement (the underlying re-hook *cadence* is `[C]`; the exact timestamp is
  this skill's own synthesis — see `references/beat-timing-model.md`), the
  requirement of at least one concrete proof beat inside Build/Value (the
  corpus's proof-density cadence is stated for long-form; compressing it into
  a single Shorts-scale beat is this skill's adaptation — see
  `references/retention-loops-and-structure.md`), the "Optional input: a
  companion grounding artifact" section below (an interface convention, not a
  corpus claim), and the read-aloud gates' mechanism — Gate D's D2/D4/D6, the
  fresh-critic dispatch, and the no-touch annotation vocabulary
  (`references/read-aloud-gates.md`).
- **`[T]`** — not used by this skill; tool/policy facts belong to
  `voiceover-brief` and `visual-prompts`.
- **`[S]`** script-baseline — derived from an observed failure in this repo's
  own shipped output, cited by file and beat in
  `docs/script-language-baseline.md`. Used only by the read-aloud gates. **An
  `[S]` rule that cannot name a real shipped line violating it is a bug — mark
  it `[I]` instead.**

If a concept brief needs something the corpus doesn't cover (e.g. genre-specific
hook phrasing, a topic this corpus never touches), say so explicitly in the
script's notes rather than inventing generic advice to fill the gap.

## Optional input: a companion grounding artifact `[I]`

If a companion grounding artifact is handed to this skill (directly, or via the concept brief's
"Grounding" section), weave its per-beat citation content into this script's native beats rather
than inventing your own framing for that material:

- Follow the artifact's own stated per-brief mapping judgment (where its Turn-equivalent content
  lands, whether its Payoff-equivalent content is the Build's proof beat or this script's own
  Payoff beat) — the fixed translation rule behind that judgment, if you need the full reasoning,
  is whatever reference file the artifact's producing skill documents (e.g. `rgs-grounding`'s
  `references/scripting-beat-mapping.md`).
- Preserve any citation markers in the artifact's text verbatim (e.g. `[THINKER: ...]`,
  `[RESEARCH: ...]`) in this script's output — don't strip or paraphrase them away.
- Restate any quotability constraint (e.g. quote-ok vs. paraphrase-caution) at every beat that
  uses the citation, not just once.
- If the artifact states a "constraints that survive to publish" line, copy it **verbatim** into
  this script's own Delivery notes field (see the output contract below) so it reaches
  `shorts-assembly` and, through it, `social-repurpose` — those skills honor a flagged
  constraint without needing to know what produced it.

If no companion artifact is provided, this section doesn't apply — script normally.

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
   phrasing so the ending feeds back into the opening. Separately — and not
   satisfied by the loop alone — the audit's strongly-supported rule is to
   *bridge to a specific next video* rather than end with "thanks for
   watching": if there's a specific related Short/video to point to, name it
   in the output contract's `Next-video bridge` field even though the VO line
   itself stays on the mirrored hook (`references/endings-and-ctas.md`).
9. **Run Gate D, then Gate E.** Gate D is the deterministic linter
   (`scripts/lint_script_language.py`) — run it directly in standalone mode; in
   app-driven mode record `deferred — app-run`, because the app runs it. Gate E
   dispatches a fresh Opus critic that has not seen your authoring rationale.
   **A failing gate blocks emission** until resolved or explicitly overridden,
   and a Gate E finding may be resolved by defending the line in writing rather
   than changing it. Fact-check any specific claim while you are here
   (`references/script-intelligence-and-delivery.md`). Full rules, the verbatim
   dispatch prompt, and the no-touch annotation vocabulary are in
   `references/read-aloud-gates.md` — read it before running either gate.
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
Next-video bridge: <name a specific related Short/video to point to (pinned
  comment or on-screen card), or write "none available" — never leave this
  silently blank; the corpus treats skipping it as a strongly-supported miss>
Total word count: ~N words (150–170 wpm)

GATES
  Gate D (scripts/lint_script_language.py): <replace this slot with the real result: "pass", "N findings", or "deferred — app-run">
  Gate E (fresh Opus critic):               <replace this slot with the real result: "pass", "N findings", "N findings, N defended", or "overridden: reason">

Visual notes (for visual-prompts downstream):
  Hook: <one line>
  Setup: <one line>
  Build: <one line>
  Re-hook: <one line>
  Payoff: <one line>
  Loop/CTA: <one line>

Delivery notes: <muted-friendly check, medium-confidence flags used (if any),
  the written defence of any Gate E finding resolved by the defend path (its [C]
  citation or its binding constraint — this is where a defence is recorded, and
  the GATES block's "N defended" counts them), and — only if a companion grounding artifact was used — its
  citation markers verbatim (e.g. [THINKER: ...], [RESEARCH: ...]) for each citation actually
  used in the script, plus its "constraints that survive to publish" line,
  copied verbatim>
```

**Every `<…>` above is a slot, and the two `GATES` slots are the ones a gate
checks: D6 rejects a `Gate E:` value still wrapped in `<…>` or `[…]`, or still
carrying the template's `|` bars** `[I]`. Emitting the contract unfilled is a
Gate D failure, not a report. **This still does not prove Gate E ran** `[I]` —
nothing in Gate D can; see `references/read-aloud-gates.md` "Known limits".

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
- `references/beat-timing-model.md` — the standard-band table lives above in
  this file; this reference adds only the word-rate `[I]`-reasoning, the
  20–30s compressed band, and the re-hook-timing `[I]` caveat in full.
- `references/read-aloud-gates.md` — Gates D and E in full: the six Gate D
  checks with their `[C]`/`[I]`/`[S]` provenance, the two-mode run rule, Gate
  E's verbatim dispatch prompt, the no-touch annotation vocabulary, and the
  three resolution paths. Read it before running either gate.
- `references/worked-example.md` — a complete concept-brief-to-script run with
  inline citations.

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the upstream concept brief: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind concept-brief` from the repo
   root (you need the `slug` the concept brief's author stated — ask for it if you don't have
   it). This prints `<path>\t<version>` where `<path>` is already `rgs-briefs/`-relative (or, if
   nothing is found yet, prints `NONE\t0` and exits 1 — that's the expected "no file yet, fall
   back to chat-pasted input" case, not an error). Read the file it reports. If it points at a
   `grounding:` field, treat that as the companion grounding artifact per "Optional input" above.
   **Staleness check:** re-run `resolve_brief_version.py --slug <slug> --kind concept-brief`
   again right before you finish — if a newer version now exists than the one you read, tell the
   user before proceeding rather than silently scripting against a stale concept.
2. Before writing the script, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script` from the repo root
   (no `--next`). If it prints a path (not `NONE`), that's the current version being superseded
   — remember its printed path verbatim for the `supersedes:` field below; it's already
   `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.
3. After writing the script, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script --next --date <YYYY-MM-DD>`.
   It prints `<filename>\t<version>` — a bare filename this time (no directory prefix). Write the
   file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in addition to the
   script body's own output contract above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: script
   slug: <slug>
   stage: 02-scripting
   version: <version from the resolver>
   supersedes: <path from step 2 above — only if version > 1>
   concept_brief: <the concept-brief file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   grounding: <carried through from the concept brief, if present>
   archetype: <carried through from the concept brief / grounding artifact, if present>
   visual_system: <carried through from the concept brief or a run-level document, if one was provided>
   total_runtime_seconds: <the script's total runtime, if the concept brief or your own timing states one>
   status: complete
   ---
   ```
4. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
