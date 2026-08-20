---
name: social-repurpose
description: Generate multi-surface post copy (YouTube title/description/hashtags plus cross-platform caption variants for TikTok/Instagram/X/Bluesky) from a finished faceless-YouTube-Short's script and packaging direction. This is the final stage of the ContentStudio eight-skill pipeline — use it after a Short has been assembled, with exactly two inputs: the timed script (for hook language and any publish constraint) and shorts-assembly's edit plan and you need publish-ready copy for YouTube and repurposed captions elsewhere. Trigger this whenever the user asks to write a YouTube title, description, or hashtags for a Short; asks to "repurpose," "cross-post," or write captions for TikTok/Instagram/X/Bluesky/Threads from a video; or wants the final post-copy package for a produced Short. Every normative line traces to the ContentStudio corpus (docs/headless-youtube-audit.md) with [C]/[I]/[T] provenance markers — do not invent generic social-media best practices.
---

# Social Repurpose

The final stage of ContentStudio's eight-skill pipeline, following `shorts-assembly`. Turns
a **finished Short** into the **multi-surface post copy** that ships it. There is no
downstream stage: this skill's output is the pipeline's final deliverable.

**Upstream input — two artifacts, no more.** The timed script from `shorts-scripting` (hook
language, AEO specifics, and the `Delivery notes` constraint line) and the edit plan from
`shorts-assembly` (which carries the packaging direction forward, plus its
`## Constraints that survive to publish` section). Thumbnail *design* is not re-derived here —
that is `shorts-ideation`/`shorts-assembly` territory; this skill writes the **text** that
accompanies the finished video.

**Read `shorts-assembly`'s `## Constraints that survive to publish` section** `[I]`. It is never
blank — it carries the literal word "none" when nothing applies. If it names a constraint (e.g. a
mandatory safety-resource mention, or a quotability restriction), honor it in the post copy; this
skill does not need to know what produced the constraint, only that it is flagged.

## Output contract

```
## YouTube package
[Title, description, hashtags, and a pinned-comment suggestion — sized correctly for a Short
 (not the long-form AEO treatment; see references/youtube-description-hashtags.md).]

## Cross-platform caption variants
[For whichever other surfaces the user names (TikTok, Instagram Reels, X, Bluesky, Threads,
 etc.), each one marked per the honest corpus-coverage gap below.]
```

## Handoff contract (machine-checked)

```handoff
produces.kind: social-repurpose
produces.stage: 05-repurpose
produces.section: YouTube package
produces.section: Cross-platform caption variants
consumes: shorts-scripting#HOOK
consumes: shorts-scripting#Delivery notes
consumes: shorts-assembly#Constraints that survive to publish
consumes: shorts-assembly#Shot table
```

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

## File I/O contract

**Artifact vocabulary — one table, copied unchanged into every skill.** The resolver matches
filenames literally, so a `--kind` guessed from a stage id or a skill name returns `NONE` and
exit 1 — which this section documents as the benign "upstream hasn't run yet" case. Copy the
literal string from this table; never infer it `[I]`.

| Stage id (`pipeline.yaml`) | `--kind` | `stage:` frontmatter | Owning skill |
|---|---|---|---|
| `grounding` | `grounding` | `00-grounding` | `rgs-grounding` |
| `ideation` | `concept-brief` | `01-ideation` | `shorts-ideation` |
| `scripting` | `script` | `02-scripting` | `shorts-scripting` |
| `styleboard` | `styleboard` | `02b-styleboard` | `shorts-styleboard` |
| `voiceover` | `voiceover-brief` | `03-voiceover` | `voiceover-brief` |
| `visual` | `visual-prompts` | `03-visual` | `visual-prompts` |
| `music` | `music` | `03-music` | `music-brief` |
| `assembly` | `assembly` | `04-assembly` | `shorts-assembly` |
| `repurpose` | `social-repurpose` | `05-repurpose` | `social-repurpose` |
| — (specialist) | `audio-spec` | `03-voiceover` | `elevenlabs-audio` |
| — (specialist) | `music-spec` | `03-music` | `elevenlabs-music` |
| — (specialist) | *none — transcript-only* | — | `midjourney-prompting` |

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed. Do not also write
to `rgs-briefs/` in this mode.

**Standalone** (no output path was given):

1. Resolve the two upstream inputs: run `python scripts/resolve_brief_version.py --slug <slug>
   --kind script` and `... --kind assembly` from the repo root. Read each file the resolver
   reports.
   Packaging direction and any publish constraint arrive through the edit plan's own sections —
   do not chase the script's `concept_brief:`/`grounding:` pointers `[I]`.
   **Staleness check:** re-run both resolver calls again right before you finish — if a newer
   version now exists for either than the one you read, tell the user before proceeding.
2. Before writing the social-repurpose file, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind social-repurpose` from the repo
   root (no `--next`). If it prints a path (not `NONE`), that's the current version being
   superseded — remember its printed path verbatim for the `supersedes:` field below; it's already
   `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.
3. After assembling the post-copy package, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind social-repurpose --next --date <YYYY-MM-DD>`.
   Write the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter:

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: social-repurpose
   slug: <slug>
   stage: 05-repurpose
   version: <version from the resolver>
   supersedes: <path from step 2 above — only if version > 1>
   script: <the script file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative, don't prepend rgs-briefs/ again>
   assembly: <the assembly file's path, exactly as the resolver printed it in step 1 — already rgs-briefs/-relative>
   concept_brief: <carried through from the script, if present>
   grounding: <carried through from the script, if present>
   archetype: <carried through from the script / concept brief, if present>
   status: complete
   ---
   ```
4. State the exact file path you wrote in your final chat response. This is the pipeline's final
   stage — no downstream skill to point at, but this file remains the durable record of what
   copy was produced for this Short.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
