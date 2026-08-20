---
name: shorts-assembly
description: Turns a faceless-YouTube-Shorts script plus its voiceover brief and visual prompt sheet into a concrete assembly/edit plan — shot-by-shot pacing and cut cadence, caption/overlay treatment, aspect-ratio and safe-zone specs, loudness/ducking targets, and a $0-tool-stack vs. paid-tool-stack execution path. Use this once three inputs exist — the timed script, the voiceover brief, and the visual prompt sheet — plus an optional fourth, the music-brief bed arc; it blocks rather than guesses if any of the three is missing — "how do I edit this," "what's my caption style," "build me an edit plan," "what's my pacing/timing," "how should I duck the music," "what tools do I assemble this in." Every rule traces to the ContentStudio corpus (docs/headless-shorts-production-playbook.md, docs/headless-youtube-audit.md) with [C]/[I]/[T] provenance markers — do not answer from generic editing knowledge.
---

# Shorts Assembly

Produces the **edit plan** for one Short: the stage of ContentStudio's eight-skill pipeline that follows `shorts-scripting`, `voiceover-brief`, `visual-prompts`, and `music-brief`, and precedes `social-repurpose`. It does not touch ideation, scripting, voice, or visual-asset generation — those are separate skills. It does not write post copy — that is `social-repurpose`, next.

## Pipeline position

| Upstream | This skill | Downstream |
|---|---|---|
| `shorts-scripting` (script + beat timing), `voiceover-brief` (ElevenLabs voice spec), `visual-prompts` (Midjourney/Kling/Ideogram prompt sheet keyed to beats), `music-brief` (bed arc — **optional**) | **`shorts-assembly`** → edit plan | `social-repurpose` (finished Short + script/packaging → multi-surface post copy) |

**Inputs required to run this skill:**
1. The shot-ready script with beat timing (Hook/Setup/Build/Payoff/Loop, seconds + word counts).
2. The voiceover brief — its `## Voice pick`, `## Tone per beat`, `## Settings`,
   `## Script, reformatted for TTS`, and `## Production & loudness` sections. It does **not**
   carry pacing wpm or a take count: wpm and total runtime come from the script's
   `Total word count: ~N words (150–170 wpm)` line, and no skill in the pipeline emits a take
   count at all `[I]`.
2b. **Optional — the `elevenlabs-audio` AUDIO PRODUCTION SPEC**, if the VO was rendered through
   that specialist. Use its `DIRECTORIAL SCRIPT` chunk boundaries and its rendered-asset filename
   in the shot table and the mix section. Absent, treat the VO as one continuous take `[I]`.
3. The visual prompt sheet keyed to script beats (which shot uses which asset, generated vs. stock).
4. **Optional — the music bed brief** (from `music-brief`, and its `elevenlabs-music` MIX HANDOFF
   if one exists). If present, use its bed arc, hook hold-out and asset filename in the loudness/mix
   section instead of leaving the bed unspecified. **If absent, carry the existing rights-note
   checkpoint unchanged** — a Short with a library track or no bed at all is a legitimate outcome,
   and the corpus is explicit that no music beats the wrong music
   `[C] (Kallaway, i7upRL4H1FM)`.

If input 1 or 3 is missing, ask for it rather than inventing shot content — this skill assembles
what upstream produced, it doesn't re-derive the visuals. **The fourth is genuinely optional and
its absence is never a blocker.**

**Input 1 in app-driven mode.** The `scripting` stage is one of this stage's `depends_on`, so the
script is directly among `input_files` — read its beat table and its `Total word count` line
there, which is where wpm and runtime actually live `[I]`. No pointer-chase through the voiceover
brief is needed; that workaround only applied when `scripting` wasn't a direct dependency.

**Before pasting any prompt from input 3, resolve its slot token — this is a manual step until
the render console exists `[I]`.** Every prompt in the sheet ends in an unresolved
`{style:register_a}` / `{style:register_b}` / `{char:<name>}` token, never a literal `--sref`/`--p`
code — `visual-prompts`' Gate C rejects a literal invented code, so the code was deliberately never
written into the sheet. Before a prompt is run in Midjourney, look up the styleboard's `BINDINGS`
line for that slot, find the actual harvested code for the Style Library entry it names — the
Library is `docs/style-library.md`, and its `Entries` section is where the code lives — and replace
the whole token with the real flag(s) — `--sref <code>`, `--p <code>`, `--oref <url> --ow <n>`, or
nothing at all for a personalization binding. Pasting the token as literal text renders the words
"style register a" into the image instead of applying a look.

**Optional: constraints that survive to publish.** `[I]` If the incoming script's Delivery notes field
carries a "constraints that survive to publish" line (e.g. a quotability restriction on a
citation, or a mandatory safety-resource line), honor it in the caption/overlay treatment below,
and restate it verbatim in the delivered edit plan's own notes so it carries forward intact —
this skill doesn't need to know what produced the constraint, only that it's flagged and must be
respected.

**Output:** a single edit plan covering six things, every one gated by a corpus rule, not convention:
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

Then produce the plan itself under these seven headings, in this order. `references/worked-example.md`
(a full worked run using the corpus's own S042 "coffee trick" script) shows each heading filled in
— copy the *content depth* from it, and the *headings* from here. A downstream skill parses these
headings by name; renaming one breaks `social-repurpose` `[I]`.

## Output contract

```
## Shot table
[One row per cut: # | beat | time range | visual source (sheet shot #) | on-screen text | duration]

## Caption & overlay treatment
[Caption style, hook/re-hook card timing, safe-zone map, and the explicit call on the
 full-duration vs. front-loaded caption split with the reason]

## Aspect ratio & safe zones
[1080×1920, 9:16, plus the safe-zone insets and any runtime-eligibility caveat]

## Loudness & mix
[-14 LUFS integrated, ducking depth, voice-peak range, phone-speaker QA step, bed asset
 filename if a music brief was supplied]

## Tool stack
[The $0 path and the paid path, each as concrete named steps ending in the publish sequence:
 upload unlisted → let it process → add metadata → schedule public]

## QA gate & publish gate
[The checklist from tool-stack.md, every item marked pass/fail — never omitted]

## Constraints that survive to publish
[Any constraint line carried verbatim from the script's or grounding brief's Delivery notes,
 or the literal word "none". Never blank — social-repurpose reads this section by name.]
```

## Handoff contract (machine-checked)

```handoff
produces.kind: assembly
produces.stage: 04-assembly
produces.section: Shot table
produces.section: Caption & overlay treatment
produces.section: Aspect ratio & safe zones
produces.section: Loudness & mix
produces.section: Tool stack
produces.section: QA gate & publish gate
produces.section: Constraints that survive to publish
consumes: shorts-scripting#Total word count
consumes: shorts-scripting#Visual notes
consumes: shorts-scripting#Delivery notes
consumes: voiceover-brief#Voice pick
consumes: voiceover-brief#Tone per beat
consumes: voiceover-brief#Settings
consumes: voiceover-brief#Script, reformatted for TTS
consumes: voiceover-brief#Production & loudness
consumes: visual-prompts#WHOLE-SHORT SETUP
consumes: visual-prompts#COVER / THUMBNAIL
consumes: music-brief#Bed arc
consumes: music-brief#Hook hold-out
reads: docs/style-library.md
```

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

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**App-driven note.** The `music` stage is not one of this stage's `depends_on`, so a music brief is
not passed in automatically. If the user references a bed, look for the run's
`03-music/artifact.v*.md` (highest version wins) and read it; if there is none, proceed with the
rights-note checkpoint as normal `[I]`.

**Standalone** (no output path was given):

1. Resolve the three upstream inputs: run `python scripts/resolve_brief_version.py --slug <slug>
   --kind script`, `... --kind voiceover-brief`, and `... --kind visual-prompts` from the repo
   root. Read each file the resolver reports.
   Also try an optional fourth resolve, `... --kind music`; its absence is not an error — if it
   prints `NONE`, proceed without a music brief.
   **Staleness check:** re-run all three required resolver calls again right before you finish — if a
   newer version now exists for any of them than the one you read, tell the user before
   proceeding.
2. Before writing the assembly file, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind assembly` from the repo
   root (no `--next`). If it prints a path (not `NONE`), that's the current version being
   superseded — remember its printed path verbatim for the `supersedes:` field below; it's already
   `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.
3. After writing the plan, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind assembly --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter:

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: assembly
   slug: <slug>
   stage: 04-assembly
   version: <version from the resolver>
   supersedes: <path from step 2 above — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   voiceover_brief: <the voiceover-brief file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative>
   visual_prompts: <the visual-prompts file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative>
   music: <the music file's path as the resolver printed it, if one exists — omit the key entirely if not>
   visual_system: <carried through from the visual-prompts file, if present>
   archetype: <carried through from the script / concept brief, if present>
   status: complete
   ---
   ```
4. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
