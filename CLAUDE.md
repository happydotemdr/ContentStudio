# CLAUDE.md — ContentStudio

Standalone local project. Turns a faceless-YouTube-Shorts idea into a produced Short
plus repurposed cross-post copy, using six atomic Claude Code skills — with every
normative recommendation traced back to a specific real-world corpus, never generic
content-creation advice.

## What this is

A **corpus** (`docs/` + `output/`) plus a **skill set** (`.claude/skills/`) built from it.
The corpus is a synthesis of **1,100+ findings** extracted from a **420-video corpus**
across **14 creator-education YouTube channels**, cross-checked against the live web for
tool/policy facts. It was originally assembled as a research corpus for a separate
project and was copied out into this standalone repo — see "Origin" below.

### The corpus (`docs/`, read in this order)

1. `docs/README.md` — the map, the 14-channel source list, and the **provenance key**.
2. `docs/headless-youtube-audit.md` — the evidence base: 13 themes, Dos/Don'ts, the
   Top-12 pitfalls, and a best-practice checklist. 679 inline citations.
3. `docs/headless-channel-launch-gameplan.md` — the phased launch roadmap.
4. `docs/headless-shorts-production-playbook.md` — Shorts anatomy, tool stack, overlay
   systems, AI asset workflow, 8 production templates.
5. `docs/midjourney-prompting-guide.md` — Midjourney image/video prompting reference.
6. `docs/elevenlabs-voiceover-guide.md` — ElevenLabs voiceover reference.

Raw material backing the guides lives under `output/brand-intel/` (git-ignored,
downloaded locally by the toolkit scripts at repo root — see `README.md`): per-channel
transcripts, the content index, and merged findings JSON.

**Provenance markers.** Every normative claim in the corpus (and in the skills built
from it) carries one of three markers, copied through verbatim:

- **`[C]` Corpus-cited** — extracted from a transcript, cited `(Channel, video_id)`.
  Two-plus channels agreeing = **strongly-supported**.
- **`[I]` Industry practice** — general craft not specific to this corpus.
- **`[T]` Tool/policy fact** — web-verified, dated 2026-07-23. **Re-verify before
  relying on it** — these go stale fast.

A skill rule with no marker is a bug: it means something was invented instead of
sourced. If the corpus is thin on a topic, the skill says so explicitly rather than
filling the gap with generic advice — that discipline is the entire point of this
project (see "Anti-generic guarantee" below).

**Partially in scope:** the toolkit also carries two additional corpora — `thinkers`
(AnchorAndWave public-domain library) and `youth-sports` (RaisingGoodSports) — plus one
general-interest roster entry (`@bigthink`/Adam Grant) inside `output/brand-intel/`. Both
corpora now feed the
RaisingGoodSports-only `rgs-grounding` and `rgs-pairing-review` skills (see
`.claude/skills/rgs-grounding/` and `.claude/skills/rgs-pairing-review/`) — the general-interest
roster entry remains unused by any skill. See `README.md`'s scope note for the full picture.

### The six skills (`.claude/skills/`)

One atomic skill per production stage, chained by hand (no orchestrator/meta-skill).
Each skill's `SKILL.md` states its own upstream input and downstream next stage.

| Skill | Stage | Input | Output |
|---|---|---|---|
| `shorts-ideation` | Idea → concept | a raw topic/idea | validated concept brief (angle, hook, packaging direction) |
| `shorts-scripting` | Concept → script | the concept brief | shot-ready script with timing |
| `voiceover-brief` | Script → voice spec | the script | ElevenLabs voiceover production brief |
| `visual-prompts` | Script → visual prompts | the script | Midjourney prompt sheet keyed to script beats |
| `shorts-assembly` | Script + assets → edit plan | script + voiceover brief + prompt sheet | assembly/edit plan |
| `social-repurpose` | Finished Short → post copy | the finished Short + its script/packaging | multi-surface post copy (YouTube + cross-platform) |

Each skill's `references/` holds the distilled corpus rules for that stage, with
markers and citations intact. `SKILL.md` bodies stay lean (progressive disclosure);
detail lives in `references/`.

## Anti-generic guarantee (read before editing any skill)

The corpus is the **only** knowledge source for these skills. Do not fall back on
general "content creation best practices" — if the corpus doesn't cover something,
the skill must say so and flag it, not silently substitute generic advice. When
editing or extending a skill: every new normative line needs a `[C]`/`[I]`/`[T]`
marker that traces to real corpus text (or is honestly flagged as a gap).

## FamilyBrain firewall (absolute, read before touching git remotes or `output/`)

This project has **zero** connection to FamilyBrain (`C:\Projects\FamilyBrain\`) or any
`brain_*` MCP tool. It does not read from, write to, or reference that repo, its
database, its Pi, or its embeddings. Never add a FamilyBrain git remote, submodule, or
path reference here. If corpus content ever needs refreshing from upstream sources,
re-run the toolkit scripts at repo root against the public web — never reach back into
FamilyBrain.

## Origin

The corpus was originally built as a research corpus (`corpus-archive/`) inside the
FamilyBrain repo, for an unrelated brand-intel feature. It was copied — not moved,
not `git mv`'d — into this repo as a one-time, one-directional operation: a fresh
`git init` with no shared history or remote. `README.md`'s "Notes & scope" section and
a few source-file headers narrate this (toolkit provenance, e.g. `gen_thinkers_manifest.ts`
importing a sibling repo's TypeScript source) as historical/structural fact, not as a
live dependency — none of it is runnable against FamilyBrain from here.

## Using the skills

### In Claude Code

Skills at `.claude/skills/<name>/SKILL.md` are auto-discovered when working in this
repo — just describe the stage you want ("turn this idea into a concept brief") and
the matching skill triggers.

### In Claude Cowork

Skills are also packaged as a Cowork plugin. From this repo root:

```bash
bash scripts/build-cowork-plugin.sh
```

This copies `.claude/skills/` into `cowork-plugin/skills/`, writes
`cowork-plugin/.claude-plugin/plugin.json`, and zips the result to
`dist/content-studio.plugin`. Load that `.plugin` file in Cowork to install all six
skills there. `.claude/skills/` is the single source of truth — never hand-edit
`cowork-plugin/skills/`; re-run the build script instead.

## Conventions

- Local only. No deploying, no external hosting, no cloud sync.
- `output/` (the downloaded corpus) is git-ignored — never commit it.
- `cowork-plugin/skills/` and `dist/` are build artifacts of the skills — git-ignored,
  regenerated by `scripts/build-cowork-plugin.sh`.
- When adding corpus-grounded content to a skill, cite it the way the corpus does:
  `(Channel, video_id)` for `[C]`, and keep `[T]` facts dated.
