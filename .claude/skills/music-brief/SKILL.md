---
name: music-brief
description: Designs the background-music bed arc for a faceless YouTube Short — the emotional arc mapped to the script's beat timings, the hook hold-out, the pause-before-the-big-line placement, and a tone-contradiction check against the voiceover brief's tone-per-beat call. Use whenever a Short has a timed script and an approved voiceover brief and the user asks what the music should do — "what music does this Short need," "design the bed," "should there be music under the hook," "what's the music arc," "does this track fit the script," "when should the bed drop out." Takes shorts-scripting's timed script and voiceover-brief's tone call as input; its Bed Arc feeds the elevenlabs-music specialist, which owns the prompt wording, composition plan, and API payload. Every rule traces to the ContentStudio corpus with [C]/[I]/[T] markers. Do not use this to pick duck depth or the LUFS target (that is voiceover-brief), to write the Eleven Music prompt or payload (that is elevenlabs-music), or to write the edit plan (that is shorts-assembly).
---

# Music Brief

Produces the **Bed Arc** for one Short: the background-music bed's emotional shape mapped to the
script's beat timings — which movement plays where, whether the bed holds out under the hook, and
where a pause is a deliberate device. This is a stage of ContentStudio's eight-skill pipeline,
sharing the `03` group with `voiceover-brief` and `visual-prompts` — but unlike `visual-prompts`,
it is not parallel to `voiceover-brief`: it runs after both `shorts-scripting` and
`voiceover-brief`, depending on the latter's tone-per-beat call. It is deliberately thin: it owns
the bed's arc and nothing else.

## Pipeline position

**Upstream:** `shorts-scripting`'s timed script **and** `voiceover-brief`'s tone-per-beat call —
both are required, because the arc cannot be designed before the tone per beat is settled.
**Downstream:** an **optional** input to `shorts-assembly` — a no-bed Short is a legitimate
outcome of this skill, so `assembly` does not hard-depend on it. **Downstream specialist:**
`elevenlabs-music`.

**Deference, stated explicitly:** duck depth and the −14 LUFS target stay with `voiceover-brief`
(`references/production-and-loudness.md`) — this skill does not duplicate or contradict them.
Prompt wording, the composition plan, and the API payload belong to `elevenlabs-music` — this
skill hands down the creative call (the arc) and does not write any of that executable output.

## Corpus grounding — read before writing any rule

Every normative line in this skill and its `references/` carries a marker:

- **`[C]`** corpus-cited, as `(Channel, video_id)` — preserve exactly, don't paraphrase away the
  citation.
- **`[I]`** industry/general practice, not specific to this corpus.
- **`[T]`** web-verified tool/policy fact, dated and flagged for re-verification.

**The corpus has zero findings on AI music generation.** This skill covers what the bed must *do*
— its emotional arc, its hold-outs, its pauses — never how it gets made. BPM, key, genre, and
instrumentation are `elevenlabs-music`'s vendor-grounded territory, not this corpus's.

## Workflow

1. **Read the timed script in full**, noting every beat boundary in seconds.
2. **Read the voiceover brief's tone-per-beat call.** If it is missing, ask for it rather than
   inferring tone from the script — inferring is exactly the tone contradiction this skill exists
   to prevent.
3. **Derive the emotional arc:** name each movement, its beat range in seconds, and its intended
   feeling. Read `references/bed-arc.md`.
4. **Decide the hook hold-out** — whether the bed is absent under the hook, and if so, the exact
   fade-in time. Default to holding out when the hook's differentiator is a spoken line `[I]`, per
   the worked precedent in `references/bed-arc.md`.
5. **Run the tone-contradiction check:** for every beat, does the arc's intended feeling match the
   voiceover brief's tone for that same beat? Any mismatch is reported, not silently reconciled
   `[C] (Kallaway, i7upRL4H1FM)`. If no movement matches a beat's tone, recommend no bed for that
   beat — "no music beats the wrong music."

## Output format

Always structure the brief with these sections, in this order:

```
## Bed arc
[One row per movement: movement name | beat range (s) | intended feeling | energy | events
 (riser/hit/drone/pause), each with its marker]

## Hook hold-out
[In or out; if out, the exact fade-in timestamp and duration, with rationale]

## Tone-contradiction check
[One row per beat: beat | voiceover-brief tone | bed movement feeling | match / MISMATCH
 — every MISMATCH stated, never silently reconciled]

## Deferred to elevenlabs-music
[Anything the corpus does not cover — BPM, key, genre, instrumentation — named as a gap and
 handed downstream, not guessed]

## Downstream
[One line: feeds elevenlabs-music for the executable output; optional input to shorts-assembly]
```

Keep every claim in the brief traceable to a marker. If you had to extrapolate (e.g., a movement
boundary not directly named by a corpus finding), say so explicitly with `[I]` rather than
presenting it as a corpus fact.

## Reference files

- `references/bed-arc.md` — the corpus's `[C]` findings on tone-matching, low-energy beds,
  pause-before-the-line, and the three-movement worked precedent, translated into arc-design
  rules; also where the AI-music-generation gap is flagged.

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the two upstream inputs: run `python scripts/resolve_brief_version.py --slug <slug>
   --kind script` and `... --kind voiceover-brief` from the repo root. Read each file the resolver
   reports.
   **Staleness check:** re-run both resolver calls again right before you finish — if a newer
   version now exists for either of them than the one you read, tell the user before proceeding.
2. Before writing the brief, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind music` from the repo root (no
   `--next`). If it prints a path (not `NONE`), that's the current version being superseded —
   remember its printed path verbatim for the `supersedes:` field below; it's already
   `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.
3. After writing the brief, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind music --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in
   addition to the brief body template above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: music
   slug: <slug>
   stage: 03-music
   version: <version from the resolver>
   supersedes: <path from step 2 above — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   voiceover_brief: <the voiceover-brief file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative>
   concept_brief: <carried through from the script, if present>
   grounding: <carried through from the script, if present>
   archetype: <carried through from the script / concept brief, if present>
   total_runtime_seconds: <carried through from the script, if present>
   status: complete
   ---
   ```
4. State the exact file path you wrote in your final chat response.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
