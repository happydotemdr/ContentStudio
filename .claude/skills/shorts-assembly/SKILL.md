---
name: shorts-assembly
description: Turns a faceless-YouTube-Shorts script plus its voiceover brief and visual prompt sheet into a concrete assembly/edit plan — shot-by-shot pacing and cut cadence, caption/overlay treatment, aspect-ratio and safe-zone specs, loudness/ducking targets, and a $0-tool-stack vs. paid-tool-stack execution path. Use this whenever the user has a finished Short script (from shorts-scripting) and wants to know how to actually cut it together — "how do I edit this," "what's my caption style," "build me an edit plan," "what's my pacing/timing," "how should I duck the music," "what tools do I assemble this in." Every rule traces to the ContentStudio corpus (docs/headless-shorts-production-playbook.md, docs/headless-youtube-audit.md) with [C]/[I]/[T] provenance markers — do not answer from generic editing knowledge.
---

# Shorts Assembly

Produces the **edit plan** for one Short: the fifth of six atomic ContentStudio skills. It does not touch ideation, scripting, voice, or visual-asset generation — those are separate skills. It does not write post copy — that is `social-repurpose`, next.

## Pipeline position

| Upstream | This skill | Downstream |
|---|---|---|
| `shorts-scripting` (script + beat timing), `voiceover-brief` (ElevenLabs voice spec), `visual-prompts` (Midjourney/Kling/Ideogram prompt sheet keyed to beats) | **`shorts-assembly`** → edit plan | `social-repurpose` (finished Short + script/packaging → multi-surface post copy) |

**Inputs required to run this skill:**
1. The shot-ready script with beat timing (Hook/Setup/Build/Payoff/Loop, seconds + word counts).
2. The voiceover brief (voice pick, pacing wpm, take count) — or at minimum the VO's target wpm and total duration.
3. The visual prompt sheet keyed to script beats (which shot uses which asset, generated vs. stock).

If any of the three is missing, ask for it rather than inventing shot content — this skill assembles what upstream produced, it doesn't re-derive the script or the visuals.

**Optional: constraints that survive to publish.** `[I]` If the incoming script's Delivery notes field
carries a "constraints that survive to publish" line (e.g. a quotability restriction on a
citation, or a mandatory safety-resource line), honor it in the caption/overlay treatment below,
and restate it verbatim in the delivered edit plan's own notes so it carries forward intact —
this skill doesn't need to know what produced the constraint, only that it's flagged and must be
respected.

**Output:** a single edit plan covering five things, every one gated by a corpus rule, not convention:
1. Shot-by-shot pacing/cut timing
2. Caption/overlay treatment
3. Aspect ratio + safe-zone spec
4. Loudness/mix target
5. Concrete tool-stack steps, both a $0 and a paid variant
6. The QA-gate + publish-gate checklist (run before scheduling)

## Provenance discipline (read before writing any line of the plan)

Every normative sentence in the output carries `[C]` (corpus-cited, `(Channel, video_id)` preserved exactly), `[I]` (industry practice, no corpus citation exists), or `[T]` (tool/policy fact, dated 2026-07-23, flag for re-verification). A line with no marker is a bug — it means something was invented instead of sourced. If the corpus is silent on a specific question (e.g. current Shorts duration-eligibility limits), say so explicitly in the plan rather than filling the gap with generic editing advice. See `docs/README.md` for the full provenance key and ContentStudio's `CLAUDE.md` for the anti-generic guarantee.

## How to build the plan

Work through these four reference files in order — each is a distilled, cited rule set pulled from the playbook and the audit, not a re-read of the raw docs:

1. **`references/pacing-and-editing.md`** — beat timing carried from the script, the ~3s change-visual cut cadence, the "don't over-edit" counter-rule, muted-viewer/authenticity rules, and where to spend AI-video budget. Use this to fill in the shot-by-shot table.
2. **`references/caption-overlay-system.md`** — caption style, hook/re-hook card timing, safe-zone map, and the one place the corpus genuinely disagrees with itself (full-duration karaoke captions vs. front-loaded-only captions) — both sides are given; make an explicit call and say why.
3. **`references/loudness-and-mix.md`** — the ducking chain (music ≈−22 dB under voice), the −14 LUFS target, voice-peak range, and the phone-speaker QA step.
4. **`references/tool-stack.md`** — CapCut / Submagic / Descript / Premiere Pro, with a $0 stack and a paid stack, the asset-naming convention so the plan can reference the actual files from upstream, the publish sequence (upload unlisted → let it process → add metadata → schedule public), and the QA-gate + publish-gate checklist that must pass before scheduling.

Then produce the plan itself, structured the same way `references/worked-example.md` is (a full worked run using the corpus's own S042 "coffee trick" script) — copy that structure for the real script, don't reinvent the layout per request.

## Writing the plan for a real request

1. Read the three upstream inputs the user provides (script, VO brief, prompt sheet).
2. Build the shot-by-shot table: one row per beat (or split a long beat into ~3s sub-cuts per the cut-cadence rule), noting visual source, on-screen text, and duration.
3. Fill in the caption/overlay spec using the fill-in template in `caption-overlay-system.md` — don't leave placeholders in the delivered plan.
4. State the aspect ratio (1080×1920, 9:16) and flag the Shorts-length gap if the runtime is unusual.
5. State the loudness targets and the ducking level.
6. Write both the $0 and paid tool-stack execution steps, naming actual tools and actual actions ("import in CapCut, auto-caption, hand-correct against the script...") not abstractions, ending with the publish sequence (unlisted → processed → metadata added → scheduled public) — don't let the plan stop at export.
7. Before scheduling, run the QA-gate + publish-gate checklist from `tool-stack.md` (phone check, swipe-stop, safe zones, loudness, banned openers, AI disclosure, made-for-kids, restrictions, duplicate-content check) and include it in the delivered plan — don't let the plan skip straight from export to "scheduled."
8. Close by stating explicitly that this edit plan (plus the produced Short) feeds `social-repurpose` next.

## Gaps to flag honestly

- No corpus finding on current Shorts duration-eligibility limits (whether Shorts can exceed ~60s/3min) — this is a live policy question outside the corpus and outside the 2026-07-23 `[T]` sweep; tell the user to verify independently before locking an unusual runtime.
- The caption-density tension (full captions vs. front-loaded-only) is a genuine corpus split, not resolved by more research — always present it as a judgment call per `caption-overlay-system.md`, don't silently pick one side without saying why.
