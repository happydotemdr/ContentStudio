---
name: shorts-ideation
description: Turns a raw faceless-YouTube-Shorts idea or topic into a validated concept brief — a chosen angle/take, a hook concept, and a title/thumbnail packaging direction — grounded entirely in the ContentStudio corpus's niche-selection, ideation, and packaging findings (never generic content-creation advice). Use this skill whenever the user has a raw idea or topic for a faceless Short and wants to turn it into a concept brief, asks "what angle should I take on this," "help me package this Short," "what's the hook for this idea," "turn this idea into a video concept," or is starting the ideation stage of the ContentStudio eight-skill pipeline before scripting. It has no upstream skill (the input is a raw human idea) and its output feeds directly into `shorts-scripting`.
---

# Shorts Ideation

Turn a raw idea/topic into a **validated concept brief**: a chosen angle/take, a hook
concept, and a title/thumbnail packaging direction. Every normative rule this skill applies
comes from the ContentStudio corpus's `docs/headless-youtube-audit.md` (the corpus audit),
never from generic content-creation instinct — that discipline is the whole point of
ContentStudio (see the project's `CLAUDE.md`).

## Pipeline position

| | |
|---|---|
| **Upstream** | None by default — the input is a raw human idea or topic, however rough. Optionally, a companion grounding artifact from a brand-specific skill (see "Optional input" below) |
| **This skill** | Idea → validated concept brief (angle, hook concept, packaging direction) |
| **Downstream** | `shorts-scripting` — turns this concept brief into a shot-ready script with timing |

Hand the finished concept brief to `shorts-scripting` next. Don't write the script yourself
here — see "Scope boundary" below.

## Optional input: a companion grounding artifact `[I]`

Some brands run a brand-specific skill upstream of this one that produces a **companion
grounding artifact** — a small, brand-neutral packet naming an archetype/angle hint (a
plain-language label + one-line rationale), one or more citations, and (optionally) a
"constraints that survive to publish" line. RaisingGoodSports's `rgs-grounding` is the first
skill that produces one — see its `SKILL.md` — but this skill doesn't hardcode RGS by name; any
brand-specific skill producing the same shape of artifact works the same way here. This is an
interface convention, not a corpus claim — that's why it's marked `[I]`.

When a companion artifact is provided:

- **Prefer an angle consistent with its archetype/angle hint.** Don't invent an angle the
  artifact's citations can't support.
- **If no archetype-consistent angle passes this skill's own validation gate** (step 5 below —
  net information gain, home-feed click test, packaging-compellingness, demonetization screen):
  do not stretch a citation to force a fit. Instead, pick from the artifact's own "alternates
  considered" list if it has one, or report back that the upstream brand skill needs to produce a
  different pairing. Never ship a brief built on an unsupported angle.
- **Demonetization screen and safety-sensitive citations:** step 2's screen (below) flags
  "sensitive medical/financial framing." A companion artifact's safety-sensitive citation passes
  this screen when it already carries a named source and non-sensational framing (the upstream
  brand skill's own protocol should guarantee this) — the screen's intent is to catch content
  presenting *as* a health/financial authority, and a properly-sourced citation is the opposite
  of that failure mode. Only an unsourced or sensationalized safety-sensitive claim fails the
  screen.
- **Staleness check:** if the artifact's stated date predates the most recent refresh of
  whatever corpus it cites, or its status field indicates it isn't in an active/consumable
  state, flag this before use rather than proceeding silently.
- **Carry it forward, don't re-derive it.** The concept brief's "Grounding" section (see the
  template below) points at the artifact rather than re-typing its citation text — the artifact
  remains the single source of truth for citation content.

## Scope boundary (read before drafting anything)

This skill produces a **concept**, not a script. Concretely:

- **In scope:** which angle/take on the idea, which emotional trigger/title frame the hook
  concept uses, what promise the opening must keep, and the title/thumbnail packaging
  direction.
- **Out of scope (belongs to `shorts-scripting`):** exact opening lines, in-medias-res
  staging, re-hook cadence, contrast-word mechanics ("but/so"), the 2-1-3 point ordering,
  proof-density timing, or any other retention/scripting mechanic. Those come from the
  audit's §4 (Scripting, hooks, retention), which is `shorts-scripting`'s corpus — not
  this skill's.

If you find yourself writing a full opening line or a beat-by-beat retention structure,
stop — that's the next skill's job. Hand off a *promise* and a *direction*, not a draft.

## Provenance markers (carry these through exactly)

Every normative line in this skill and its `references/` files carries one of:

- **`[C]`** corpus-cited, `(Channel, video_id)` — the default; two-plus channels agreeing is
  flagged **strongly-supported**.
- **`[I]`** industry practice, not specific to this corpus.
- **`[T]`** tool/policy fact, web-verified 2026-07-23 — re-verify before relying on it.

If a rule you're about to state has no marker, it's invented — go find the corpus backing
in `docs/headless-youtube-audit.md` or drop the rule. This skill's reference files currently
carry `[C]` markers exclusively (see the citation index at the bottom of this file); if the
corpus is silent on something the user asks for, say so explicitly rather than filling the
gap with generic advice.

## Workflow

### 1. Capture the raw idea

Ask for (or work from) whatever the user has: a topic, a half-formed idea, a competitor
video they liked, a comment thread, anything. Don't require it to already be well-formed —
narrowing it is this skill's job, not a precondition for using it.

### 2. Narrow to an angle/take

Read `references/angle-selection.md`. The order below is this skill's own editorial
prioritization of those marked techniques, not a corpus-stated sequence — apply them in
roughly this order of leverage:

1. Check whether the raw idea is already niche-quilted from elsewhere, or import a proven
   format/angle from an adjacent niche.
2. Look for an outlier-video pattern to build on rather than a mega-channel to imitate.
3. See if two proven ideas can combine into one sharper one.
4. Sharpen the take until it's contrarian and specific to one viewer avatar — not a broad
   topic.
5. Screen out demonetization-magnet territory early (political content, "AI stories,"
   sensitive medical/financial framing) so you don't build packaging on a disqualified idea.

Output of this step: one sentence naming the specific angle and the specific avatar it's
for.

### 3. Develop the hook concept

Read `references/hook-concepts.md`. Pick the emotional trigger (curiosity/fear/desire) and,
if relevant, a title frame from the 2026 lift data. Write down **the exact promise** the
opening must deliver on — this is the single most load-bearing sentence in the brief,
because a mismatch between this promise and the eventual opening is the audit's #5-ranked
pitfall (the "promise-breaker").

### 4. Choose the packaging direction

Read `references/packaging-direction.md`. Produce 2–3 candidate titles and one thumbnail
direction, restating that file's marked title-length/specificity/focal-point/emotion rules
(they should complement, not repeat, each other) — see the reference file for the citations
behind each constraint.

### 5. Validate before finalizing

Read `references/validation-gate.md` and run all four checks: net information gain, the
home-feed click test, packaging-compellingness as an idea-quality signal, and
demonetization/policy safety. If any check fails, go back to step 2 and re-narrow — don't
ship a brief that fails its own gate.

### 6. Assemble the concept brief

Use the template below. Keep it tight — this is a brief, not a document.

## Output contract

```markdown
# Concept Brief: [working title of the idea]

## Angle / take
[One sentence: the specific angle and the specific viewer avatar it's for.]
[1-2 sentences on how it was derived — outlier/remix/combine/contrarian-take — and why it's
differentiated from existing coverage.]

## Hook concept
- Emotional trigger: [curiosity / fear / desire, or a named title frame]
- The promise: [the exact sentence the opening must deliver on]

## Packaging direction
- Title candidates:
  1. [candidate, ≤60 chars]
  2. [candidate]
  3. [candidate]
- Thumbnail direction: [focal point] / [dominant emotion] / [what it shows, distinct from
  what the title says]

## Validation
- Net information gain: [the specific new angle/fact vs. the top 5 existing videos]
- Home-feed click test: [pass/fail + why]
- Packaging-compellingness: [pass/fail + why]
- Demonetization/policy screen: [clear / flagged — note]

## Grounding (omit this section entirely if no companion artifact was provided)
- Source: [companion artifact file path]
- Archetype/angle hint honored: [archetype label]
- Citations carried forward: [thinker/source names — full citation text lives in the artifact,
  not repeated here]

## Handoff
This brief feeds `shorts-scripting` next. Scripting owns the opening lines, retention loop
structure, and pacing — not this brief.
```

## Handoff contract (machine-checked)

```handoff
produces.kind: concept-brief
produces.stage: 01-ideation
produces.section: Angle / take
produces.section: Hook concept
produces.section: Packaging direction
produces.section: Validation
produces.section: Grounding
produces.section: Handoff
```

## Worked example

See `references/worked-example.md` for a full worked run — a raw idea taken through all six
workflow steps to the finished concept brief handed off to `shorts-scripting`.

## Citation index (what's grounded where)

- `references/angle-selection.md` — audit §1 (Niche selection & validation), §3 (Ideation &
  content strategy), plus one cross-reference to the production playbook's idea-vetting step.
  20 corpus-cited rules, all `[C]`.
- `references/hook-concepts.md` — audit §7 (Packaging: titles), §3 (contrarian-take
  framing), Top-12 pitfalls #5. 7 corpus-cited rules, all `[C]`.
- `references/packaging-direction.md` — audit §7 (Packaging: titles/thumbnails/CTR). 13
  corpus-cited rules, all `[C]`.
- `references/validation-gate.md` — audit §7, §3 (home-feed click test), §1, §8 (net
  information gain), and the Top-12 pitfalls list. 4 corpus-cited rules, all `[C]`.
- `references/worked-example.md` — a complete raw-idea-to-concept-brief run, illustrating
  the rules above in use (not a separate source of new rules).

This skill's content carries `[C]` markers exclusively, with one exception: the "Optional
input: a companion grounding artifact" section above, marked `[I]` — an interface convention,
not a corpus claim. If a future edit needs another industry-practice or tool/policy claim, mark
it `[I]`/`[T]` explicitly rather than leaving it bare.

## File I/O contract

This skill participates in ContentStudio's file-based pipeline handoff (see
`docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md`). Two modes:

**App-driven** (a `pipeline-app` turn already told you an output path, e.g. "Write your final
concept brief to `runs/.../raw_output.md`"): follow that instruction exactly — write only to the
named path, overwrite it each turn as instructed. Do not also write to `rgs-briefs/` in this
mode; that stays `pipeline-app`'s job.

**Standalone** (no output path was given):

1. This skill has no upstream stage file to resolve — its input is a raw idea, plus optionally a
   companion grounding artifact (see "Optional input" above), which you locate by asking the user
   or by checking whether `rgs-grounding` already produced one for this topic.
2. Choose a `slug`: a short kebab-case identifier for this Short, derived from its working title
   (e.g. "Decline the Next Level" → `decline-the-next-level`). This slug is used by every
   downstream stage — state it explicitly in your final output so the human can carry it forward.
3. After assembling the concept brief, run
   `python scripts/resolve_brief_version.py --slug <slug> --kind concept-brief`
   from the repo root (no `--next`). If it prints a path (not `NONE`), that's the current version
   being superseded — remember its printed path verbatim for the `supersedes:` field below; it's
   already `rgs-briefs/`-relative, don't prepend `rgs-briefs/` again.
4. Then run `python scripts/resolve_brief_version.py --slug <slug> --kind concept-brief --next --date <YYYY-MM-DD>`
   to get the exact filename and version number to write. This prints `<filename>\t<version>`. Write
   the file at `rgs-briefs/<filename>` via the `Write` tool with this frontmatter (in addition to
   the concept-brief body template above):

   ```yaml
   ---
   date: <YYYY-MM-DD>
   kind: concept-brief
   slug: <slug>
   stage: 01-ideation
   version: <version from the resolver>
   supersedes: <path from step 3 above — only if version > 1>
   grounding: <path to the companion grounding artifact, only if one was used>
   archetype: <carried through from the companion grounding artifact, if present>
   status: complete
   ---
   ```
5. State the exact file path you wrote in your final chat response, and the `slug` you chose, so
   `shorts-scripting` can be pointed at it directly.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this. A revision
(e.g. the user asks for a different angle on the same idea) is always a new, higher-version file
for the same slug.
