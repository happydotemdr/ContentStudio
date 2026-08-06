---
name: voiceover-brief
description: Turns a shot-ready faceless-YouTube-Shorts script into an ElevenLabs voiceover production brief — a voice pick with rationale, the four core settings (stability, similarity/clarity, style, speed) plus speaker boost by content type, TTS-formatting notes on the script text (audio tags, phonetic respellings, section breaks), and the -14 LUFS loudness/mix target. Use whenever the user has a finished or near-finished Shorts script and asks to turn it into a voiceover, pick or clone an ElevenLabs voice, set TTS/ElevenLabs settings, prep a script for text-to-speech generation, or figure out loudness/music-ducking for the voice track. Takes the shorts-scripting skill's timed script as input; its output feeds shorts-assembly next, alongside visual-prompts' prompt sheet. Do not use this for picking visuals/B-roll (visual-prompts) or for post-copy/captions (social-repurpose).
---

# Voiceover Brief

Produces an **ElevenLabs voiceover production brief** from a shot-ready script: which voice
and why, the settings to dial in, how to reformat the script text for TTS, and the loudness
target for the mix. This is skill #3 of ContentStudio's six-skill pipeline.

- **Upstream input:** the shot-ready, timed script from `shorts-scripting`.
- **Downstream:** feeds `shorts-assembly` (skill #5), alongside `visual-prompts`'s prompt sheet.
  This skill does not touch visuals — that's `visual-prompts`'s job, run in parallel.
- **Downstream specialist:** `elevenlabs-audio`. This skill produces the *creative* brief — which
  voice and why, the tone per beat, the content type, and the −14 LUFS mix target. It stops at the
  brief. When the user needs the **executable ElevenLabs configuration** — model routing, the
  settings floats or v3 stability mode, tag syntax that actually renders, a PLS pronunciation
  dictionary, the JSON request payload, chunking/stitching, or a credit estimate — hand this brief
  to `elevenlabs-audio` and let it own that layer. It accepts the voice and tone decided here
  without re-litigating them, and it is grounded in web-verified vendor docs
  (`docs/elevenlabs-production-runbook.md`) rather than this corpus.

  **Loudness, ducking, and the music mix stay here** — `elevenlabs-audio` explicitly defers to
  `references/production-and-loudness.md` and must not duplicate or contradict it.

  **Bed generation is downstream too.** Loudness, ducking and the music mix stay here
  (`references/production-and-loudness.md`) — but *designing and sourcing the bed itself* does not.
  The bed's emotional arc, its hook hold-out and the tone-contradiction check belong to
  `music-brief`; the Eleven Music prompt, composition plan and API payload belong to
  `elevenlabs-music`. Hand the tone-per-beat call down and let them own that layer, exactly as this
  skill does with `elevenlabs-audio`.

## Corpus grounding — read before writing any rule

Every normative line in this skill and its `references/` carries a marker, copied verbatim from
`docs/elevenlabs-voiceover-guide.md` and `docs/headless-youtube-audit.md` §5:

- **`[C]`** corpus-cited, as `(Channel, video_id)` — preserve exactly, don't paraphrase away the
  citation.
- **`[I]`** industry/general practice, not specific to this corpus.
- **`[T]`** web-verified ElevenLabs tool/policy fact, dated **2026-07-23** — flag it as needing
  re-verification; ElevenLabs models, settings ranges, and pricing move fast.

**This is a thin corpus theme: only 24 voiceover/audio findings** across the whole 420-video
corpus (`docs/headless-youtube-audit.md` §5, and its "Source coverage & limitations" section).
Most of the settings/model/pricing detail in this skill is `[T]`, not `[C]` — say so in the
brief rather than dressing up web-verified tool facts as corpus consensus. If a user asks for
something the corpus and the guide don't cover (e.g., a specific blended setting for a script
that shifts tone mid-Short), say the gap exists and give the best `[I]`-marked extrapolation
instead of inventing a confident-sounding number.

## Workflow

1. **Read the input script in full**, including any shot/timing markers from `shorts-scripting`.
   Note where the tone shifts (hook vs. body vs. CTA) — this drives both the voice settings and
   the TTS reformatting.
2. **Pick the voice.** Read `references/voice-selection.md`. Default recommendation is a cloned
   own voice; explain the reasoning (shadowban/reach risk of default voices) rather than just
   naming a choice. Note the model (v3 vs. Multilingual v2 vs. Flash/Turbo) and why.
3. **Set the four settings + speaker boost**, per section if the script mixes content types.
   Read `references/settings-by-content-type.md` for the preset table and the mixed-script
   extrapolation rule.
4. **Reformat the script text for TTS.** Read `references/scripting-for-tts.md`: short
   sentences, punctuation-as-pacing, v3 audio tags placed inline, phonetic respellings for
   tricky words, and a check for lines that don't "sound like a person." Section the script
   into TTS generation units (hook / beat / CTA, or matching the upstream shot breaks) so bad
   takes can be re-rolled cheaply.
5. **State the production/loudness target.** Read `references/production-and-loudness.md`:
   −14 LUFS on the voice track, music ducked to the corpus's practitioner depth
   (−21 to −22 dB) with the docs' −12 to −18 dB range given alongside it, and the
   consistency/re-roll notes.
6. **Assemble the brief** using the output format below. See
   `references/worked-example.md` for a full script-to-brief example.

## Output format

Always structure the brief with these sections, in this order:

```
## Voice pick
[Voice + model choice, with rationale citing the relevant rule/marker]

## Settings
[Table: section/beat (if mixed) x stability, similarity, style, speed, speaker boost]

## Script, reformatted for TTS
[The script text with audio tags, pacing punctuation, phonetic respellings,
 and section breaks — annotate what changed and why]

## Production & loudness
[-14 LUFS target; music-ducking depth; any music-matching or re-roll notes]

## Downstream
[One line: feeds shorts-assembly alongside visual-prompts' output]
```

Keep every claim in the brief traceable to a marker. If you had to extrapolate (e.g., a
per-section split for a mixed-tone script), say so explicitly with `[I]` rather than presenting
it as a corpus or tool fact.

## Reference files

- `references/voice-selection.md` — voice/cloning choice, the default-voice warning, model pick.
- `references/settings-by-content-type.md` — stability/similarity/style/speed, preset table,
  mixed-script guidance.
- `references/scripting-for-tts.md` — sentence/punctuation/tag formatting rules for the script
  text itself.
- `references/production-and-loudness.md` — LUFS target, music ducking, consistency, re-rolls.
- `references/worked-example.md` — a full script excerpt run through to a finished brief.

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the upstream script: run
   `python scripts/resolve_brief_version.py --slug <slug> --kind script` from the repo root. Read
   the file it reports, and follow its `concept_brief:`/`grounding:` pointer fields to resolve
   anything further upstream.
   **Staleness check:** re-run the resolver for `--kind script` again right before you finish —
   if a newer version now exists than the one you read, tell the user before proceeding.
2. Before writing the brief, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind voiceover-brief` from the repo
   root (no `--next`). If it prints a path (not `NONE`), that's the current version being
   superseded — remember its printed path verbatim for the `supersedes:` field below; it's already
   `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.
3. After writing the brief, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind voiceover-brief --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in
   addition to the brief body template above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: voiceover-brief
   slug: <slug>
   stage: 03-voiceover
   version: <version from the resolver>
   supersedes: <path from step 2 above — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   concept_brief: <carried through from the script, if present>
   grounding: <carried through from the script, if present>
   archetype: <carried through from the script / concept brief, if present>
   total_runtime_seconds: <carried through from the script, if present>
   status: complete
   ---
   ```
4. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
