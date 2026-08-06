# `music-brief` Stage + `elevenlabs-music` Specialist — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an eighth pipeline stage (`music`, skill `music-brief`) that designs a Short's background-music bed arc from corpus rules, plus a vendor-grounded `elevenlabs-music` specialist that converts that arc into a copy-paste UI prompt, a beat-locked Eleven Music composition plan, and an API payload.

**Architecture:** Two skills, mirroring the repo's existing pipeline-skill/specialist split (`voiceover-brief`/`elevenlabs-audio`, `visual-prompts`/`midjourney-prompting`). `music-brief` is corpus-derived and owns the creative call (the bed arc, the hook hold-out, the tone-contradiction check). `elevenlabs-music` is vendor-derived and owns the executable output. They are wired together by `pipeline.yaml`'s existing `specialist:` + `specialist_mode:` mechanism. `assembly.depends_on` does **not** change.

**Tech Stack:** Markdown skills (`SKILL.md` + `references/*.md`), YAML topology (`pipeline.yaml`), Jinja2 stage templates, FastAPI (`pipeline-app/`), pytest.

---

## ⚠ Read this before Task 1 — the task spec's vendor facts were verified and two are wrong

The originating task spec gathered Eleven Music facts on 2026-08-05 via a Context7 mirror,
because `elevenlabs.io` was believed to return HTTP 403. **On 2026-08-06, `elevenlabs.io/docs`
was fetched successfully and directly** (see Task 1 for the URLs). That re-verification confirmed
most of the spec's facts, **corrected two load-bearing ones, and promoted one from
`[T-unverified]` to `[T]`.** This plan is built on the corrected facts. The deviations, stated
once so nobody re-derives them:

| Spec said | Live docs say (2026-08-06) | Consequence |
|---|---|---|
| The `chunks[]` shape is an **inpainting** thing; "do not assert it is the same object as `composition_plan`" | `chunks[]` **is** the composition plan — for `model_id: music_v2`. `sections[]` is the `music_v1` shape (`MusicPrompt`). The how-to guide documents **only** the chunk shape and says "Chunk-based composition plans require the music_v2 model." | Stage B maps beats to **chunks** on `music_v2` as the primary path; the `music_v1` `sections[]` shape is carried as a documented alternative, not the default. |
| Instrumental via `lines: []` is "the likely resolution" — an inference to live-verify | `force_instrumental` is prompt-only and does **not** apply to plans. The documented plan-mode technique is **`negative_styles: ["vocals", "lyrics", …]`**. `music_v2` chunks have **no `lines` field at all** (the field is `text`). | The spec's "belt-and-suspenders" negative-styles guard is promoted from a hedge to **the documented method**. The `lines: []` inference is dropped from `music_v2` and recorded as never-documented for `music_v1`. |
| `seed` gives determinism for re-rolls | "Providing the same seed with the same parameters can help achieve **more consistent** results, but **exact reproducibility is not guaranteed** and outputs may change across system updates." | The "instrumental **vs.** determinism conflict" the spec called "the crux of this skill" largely **dissolves**: plan mode gets instrumental by the documented route, and seed was never a determinism guarantee. Stage D frames seed as a consistency aid, never as reproducibility. **Verification step 8 must not assert byte- or ear-identical re-generation.** |
| 3–120s per-section ceiling is `[T-unverified]` (a search snippet) | `duration_ms` is **3,000–120,000 ms** on the schema page, for **both** plan shapes. Plus: ≤30 chunks, total 3s–10min, `positive_styles`/`negative_styles` ≤50 items each. | Promoted to `[T]`, verified 2026-08-06. Gate 1 checks it as a hard bound. |

**What remains genuinely `[T-unverified]`** and must be marked as such everywhere: credit cost per
generation; whether creating a composition plan is free; the exact REST path for plan creation
(the SDK surface is `music.composition_plan.create`; the spec's `/v1/music/plan` was not confirmed);
the 4,100-character prompt cap; per-tier rate limits; ownership and per-tier commercial terms
(`elevenlabs.io/music-terms` was not read); and — most importantly — **whether the negative-styles
vocal guard actually suppresses vocals in practice**, which needs a live generation.

**There is no `ELEVENLABS_API_KEY` in this environment** (`env | grep -i eleven` returns nothing).
Task 1 attempts the live generation and, failing that, records the failure. Do not fake it.

---

## Global Constraints

- **Marker discipline.** Every normative line in both new skills and the new runbook carries
  `[C]` (corpus-cited, `(Channel, video_id)` preserved verbatim), `[I]` (general practice),
  `[T]` (vendor-verified, dated), or `[T-unverified]`. **An unmarked normative line is a bug.**
- **Never fill a corpus gap with generic content-creation advice.** Flag the gap instead.
  This is the single rule the project cares most about (`CLAUDE.md`, "Anti-generic guarantee").
- **The corpus has zero findings on AI music generation.** Nearly every normative line in
  `elevenlabs-music` will be `[T]`/`[I]`. Say so in its grounding section.
- **Boundary, stated once:** the pipeline skill owns the creative call, the specialist owns the
  executable output. The specialist accepts the creative call and does not re-litigate it.
- **`voiceover-brief` keeps duck depth and LUFS.** If `music-brief` or `elevenlabs-music` starts
  restating `−21 to −22 dB` or `−14 LUFS` as its own decision, it has drifted. `elevenlabs-music`'s
  `MIX HANDOFF` section **restates, never re-decides**.
- **Do NOT change `assembly.depends_on`.** It stays `[voiceover, visual]`. See Task 6.
- **FamilyBrain firewall.** Zero connection to `C:\Projects\FamilyBrain\` or any `brain_*` MCP tool.
  Never add a FamilyBrain remote, submodule, or path reference.
- **Local only.** No deploying, no external hosting, no cloud sync.
- **Never hand-edit `cowork-plugin/skills/` or `dist/`** — build artifacts. Re-run
  `scripts/build-cowork-plugin.sh`.
- **Never edit an existing `rgs-briefs/*.md` file** — a `PreToolUse` hook
  (`.claude/hooks/protect_briefs.py`) enforces this.
- **`output/` is git-ignored** — never commit it.
- Verified vendor facts are dated **2026-08-06** and sourced to `elevenlabs.io/docs`.

---

## File Structure

**Create:**

| Path | Responsibility |
|---|---|
| `docs/elevenlabs-music-runbook.md` | Vendor source of truth for `elevenlabs-music`. Format mirrors `docs/elevenlabs-production-runbook.md` exactly, incl. the §-numbered body and the closing verification log. |
| `.claude/skills/music-brief/SKILL.md` | Pipeline stage skill: bed arc, hook hold-out, tone-contradiction check, File I/O contract. Deliberately thin. |
| `.claude/skills/music-brief/references/bed-arc.md` | The `[C]` corpus findings translated into arc-design rules + the RGS three-movement worked precedent. |
| `.claude/skills/elevenlabs-music/SKILL.md` | Specialist: four gated stages, control surface, output contract. |
| `.claude/skills/elevenlabs-music/references/composition-plans.md` | Both plan shapes, the beat→chunk mapping method, `respect_sections_durations`, the instrumental technique. |
| `.claude/skills/elevenlabs-music/references/prompt-craft.md` | UI prompt body, style vocabulary, BPM/key cues, copyright guard, bed-arc → style translation. |
| `.claude/skills/elevenlabs-music/references/api-payload.md` | Endpoints, parameter conflicts, curl templates, cost/iteration discipline, `bad_prompt` recovery. |
| `.claude/skills/elevenlabs-music/references/validation-gates.md` | Three verbatim fresh-agent dispatch prompts + reporting template. |
| `pipeline-app/stage_templates/music.md` | Jinja2 kickoff template. **Required** — `prompt_builder.render_kickoff_prompt` does `env.get_template(f"{stage_id}.md")`; a missing file is a `TemplateNotFound` at the stage's first turn. |

**Modify:**

| Path | Change |
|---|---|
| `pipeline.yaml` | Add the `music` stage between `visual` and `assembly`. |
| `pipeline-app/pipeline_app/routes/skills.py` | Add `"music-brief": "music"` to `STAGE_ID_BY_SKILL`. **Do not add `elevenlabs-music`** — that dict deliberately omits both existing specialists. |
| `.claude/skills/shorts-assembly/SKILL.md` | Music brief becomes an **optional fourth input**. Pipeline-position table, inputs list, frontmatter contract. Rights checkpoint unchanged. |
| `.claude/skills/voiceover-brief/SKILL.md` | One line pointing bed *generation* downstream. Duck depth and LUFS stay. |
| `CLAUDE.md` | Seven pipeline skills; three tool specialists; "six" → "seven" in live prose. |
| `README.md`, `pipeline-app/README.md` | "six generic skills" → "seven". |
| `docs/superpowers/plans/2026-07-28-skill-markdown-file-contract.md` | Add `music` to the `<kind>` enum (spec text only). |
| `scripts/build-cowork-plugin.sh` | Header comment + `plugin.json` description + `README.md` heredoc: seven skills, three specialists. |
| `pipeline-app/tests/test_pipeline_config.py` | Rename the stage-count canary; add `music` assertions. |
| `pipeline-app/tests/test_prompt_builder.py` | Add a `music` template test. |
| `pipeline-app/tests/test_routes_skills.py` | Add a `STAGE_ID_BY_SKILL` mapping test. |

**Explicitly NOT created:** `scripts/lint_composition_plan.py`. `scripts/lint_prompt_sheet.py` is
visual-prompts-specific with no generic analogue; voiceover and assembly ship without one. The
composition plan's arithmetic invariants are Gate 1's job, consistent with how `elevenlabs-audio`
handles its payload. A linter is a reasonable follow-up if the gate proves too soft — not here.

**Note on TDD in this plan.** Six of the eight tasks produce Markdown, which carries no test
cycle. The genuine red-green-refactor work concentrates in **Task 5** (pipeline registration) and
its test additions. Tasks 1–4 and 6–7 are gated by grep-based verification steps instead — these
are real checks with expected output, not hand-waving, and each task ends with a commit.

---

## Task 1: Vendor runbook (`docs/elevenlabs-music-runbook.md`)

Both skills cite this file, so it lands first. It is the only place the corrected vendor facts are
recorded in full; the skills reference it rather than restating it.

**Files:**
- Create: `docs/elevenlabs-music-runbook.md`
- Reference for format: `docs/elevenlabs-production-runbook.md` (blockquote scope header →
  `## Provenance markers` → `---` → numbered sections → closing verification log)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `docs/elevenlabs-music-runbook.md` with sections `§1` Endpoints & models,
  `§2` Composition plan shapes, `§3` Instrumental control, `§4` Prompt craft & the copyright guard,
  `§5` Cost & iteration, `§6` Rights & commercial use, `§7` Verification log. Tasks 3 and 4 cite
  these section numbers — do not renumber them without updating those tasks.

- [ ] **Step 1: Attempt the live verification, and record what actually happened**

Two things need a live check. Do them first; their outcome changes what Step 3 writes.

```bash
env | grep -i eleven || echo "NO ELEVENLABS API KEY IN ENV"
```

If a key exists, generate from a chunk-based plan carrying the vocal guard and listen to the result:

```bash
curl -s -X POST https://api.elevenlabs.io/v1/music -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" -d '{"model_id":"music_v2","composition_plan":{"chunks":[{"text":"[Intro]","duration_ms":8000,"positive_styles":["ambient","warm pads","slow"],"negative_styles":["vocals","singing","lyrics","spoken word"],"context_adherence":"high"}]}}' -o /tmp/music-probe.mp3
```

**Expected in this environment: no API key, so this cannot run.** That is the anticipated outcome,
not a failure of the task. If it cannot run, write exactly that into §7's
`### Could not verify [T-unverified]` block — naming the missing key as the reason — and mark every
line about the vocal guard's *actual efficacy* `[T-unverified]`. **Do not silently assume it works,
and do not claim a verification you did not run.**

- [ ] **Step 2: Re-confirm the doc facts against live pages**

Fetch each and confirm the claims in the deviation table at the top of this plan still hold. They
were read on 2026-08-06; if a page has moved on, the runbook records what *you* saw, with your date.

- `https://elevenlabs.io/docs/api-reference/music/compose` — the parameter table and both plan schemas
- `https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans` — the chunk shape, the `music_v2` requirement, the `negative_styles` instrumental technique
- `https://elevenlabs.io/docs/eleven-api/guides/cookbooks/music` — the `composition_plan.create` SDK surface
- `https://elevenlabs.io/docs/overview/capabilities/music` — the commercial-use sentence
- `https://github.com/elevenlabs/skills/blob/main/music/references/api_reference.md` — ElevenLabs' own published skill reference; a useful `[T]`-grade cross-check

**Note the sourcing caveat for §7:** the originating spec reported `elevenlabs.io` returning HTTP 403
to plain fetches and fell back to a Context7 mirror. Direct fetches **succeeded** on 2026-08-06.
Record both facts — the mirror-sourced round is why two facts were wrong, and that is exactly the
kind of thing this repo's house style says out loud.

- [ ] **Step 3: Write the runbook**

Open with the house-style scope header, verbatim shape from `docs/elevenlabs-production-runbook.md`:

```markdown
# Eleven Music Runbook — endpoints, composition plans, prompt craft & credit discipline

> **Source & scope.** This document is **not corpus-derived.** It was assembled from a supplied
> design brief and then verified claim-by-claim against live ElevenLabs documentation on
> **2026-08-06**. The 420-video ContentStudio corpus contains **zero findings on AI music
> generation** — for the corpus view of what a music bed must *do* (duck depth, tonal match,
> arc), see `.claude/skills/voiceover-brief/references/production-and-loudness.md` and
> `.claude/skills/music-brief/references/bed-arc.md`. The two bodies of knowledge are
> complementary and deliberately separate: those tell you what the bed must accomplish; this
> tells you what the platform actually supports.
>
> **The supplied design brief was wrong in two places and over-cautious in two more.** See §7.
> Do not treat the original brief text as authoritative anywhere it conflicts with this document.

## Provenance markers

This document uses the repo's standard key (`docs/README.md`), with one qualifier added for
material that could not be confirmed:

- **`[T]`** — Tool/policy fact **web-verified against live ElevenLabs docs 2026-08-06**. These go
  stale fast; re-verify before relying on them.
- **`[T-unverified]`** — Asserted by a supplied source and **not confirmed** against live docs.
  Treat as a starting hypothesis, never as a fact. Say so out loud when you use one.
- **`[I]`** — Industry/general practice, not specific to ElevenLabs.
- **`[C]`** — Corpus-cited `(Channel, video_id)`. **Absent here by construction** — the corpus has
  no AI-music-generation findings at all.

A normative line in this document with no marker is a bug.

---
```

Then the numbered body. Required content, all `[T]` verified 2026-08-06 unless marked otherwise:

**§1 Endpoints & models.** `POST /v1/music` — `prompt` **XOR** `composition_plan`, mutually
exclusive. `model_id` enum `music_v1` | `music_v2`, **default `music_v1`** — so set it explicitly.
`music_length_ms` 3,000–600,000 ms, **prompt-only**. `force_instrumental` default `false`,
**prompt-only**, and when true it *guarantees* instrumental. `seed` **plan-only** ("cannot be used
in conjunction with prompt"). `respect_sections_durations` default `true`. Also `finetune_id`,
`store_for_inpainting`, `sign_with_c2pa`. Query param `output_format`, default `auto`.
`POST /v1/music/detailed` — same body plus `with_timestamps`; multipart response carrying the
resolved plan and `song_metadata`. Plan creation is exposed in the SDK as
`music.composition_plan.create(prompt=…, music_length_ms=…, model_id=…)`; **the REST path was not
confirmed — the design brief's `/v1/music/plan` is `[T-unverified]`.**

**§2 Composition plan shapes — two, and they are model-specific.** State this as the section's
headline; it is the most consequential fact in the document.

- `music_v2` → `CompositionPlan`: `chunks[]`, **≤30 chunks, total 3s–10min**. Each chunk:
  `text` (section label, lyrics, phonetic sounds, inline directions), `duration_ms`
  **3,000–120,000**, `positive_styles` (≤50), `negative_styles` (≤50), `context_adherence`
  ∈ `low`|`medium`|`high`, **default `high`** — how strictly the chunk mirrors surrounding
  sections. The how-to guide states: "Chunk-based composition plans require the music_v2 model.
  Pass model_id='music_v2' when composing."
- `music_v1` → `MusicPrompt`: `positive_global_styles[]`, `negative_global_styles[]`, `sections[]`
  of `{section_name` (1–100 chars)`, duration_ms` (3,000–120,000)`, lines[]` (≤30 lines,
  ≤200 chars each)`, positive_local_styles[], negative_local_styles[], source_from}`.
- **Both** shapes bound `duration_ms` to 3,000–120,000 ms. This is the bound that makes beat-locking
  work and the one Gate 1 enforces.
- Record explicitly that the design brief mistook the chunk shape for an inpainting-only object.

**§3 Instrumental control.** `force_instrumental` is prompt-only and does **not** apply to
composition plans. **The documented plan-mode technique is `negative_styles` carrying vocal terms** —
the docs' own cinematic example uses `"negative_styles": ["vocals", "lyrics", "pop"]`. `music_v2`
chunks have **no `lines` field**; the field is `text`. For `music_v1`, an empty `lines: []` is
**not documented as an instrumental guarantee** — record it as `[T-unverified]` and do not rely on
it alone. **Every plan this skill emits carries the vocal guard on every chunk**, regardless of
shape `[I]`. Whether the guard is *sufficient* in practice is `[T-unverified]` pending a live
generation (§7).

**§4 Prompt craft & the copyright guard.** Naming a band, musician, or copyrighted lyrics returns a
`bad_prompt` error carrying `detail.data.prompt_suggestion` — a clean rewritten prompt to retry
with. Document the **recovery path**, not just the warning: catch, read the suggestion, diff it
against the original to learn which token tripped the guard, retry. `positive_styles`/
`negative_styles` are English-only and capped at 50 items each.

**§5 Cost & iteration.** `[T-unverified]` throughout — say so at the top of the section.
Credit cost per generation was **not** found in the docs. Whether `composition_plan.create` is free
was **not** confirmed; the design brief's "costs no credits" claim is a hypothesis. **Assume every
compose call is billed until proven otherwise** `[I]`. Seed: "can help achieve **more consistent**
results, but **exact reproducibility is not guaranteed** and outputs may change across system
updates" `[T]` — never present seed as determinism.

**§6 Rights & commercial use.** The docs say Eleven Music is "cleared for nearly all commercial
uses, from film and television to podcasts and social media videos, and from advertisements to
gaming," and direct users to `elevenlabs.io/music-terms` for per-plan detail `[T]`. **Per-tier
terms and ownership were not read — `[T-unverified]`.** State plainly: this is *not* sufficient to
retire `shorts-assembly`'s rights checkpoint. The argument that a generated bed sidesteps the
Creator-Music revenue-share problem is `[I]` — a genuinely new inference the corpus does not make —
and it is **contingent on terms nobody has read yet.**

**§7 Verification log — 2026-08-06.** Four blocks, exactly as
`docs/elevenlabs-production-runbook.md` §10 does it:

- `### Confirmed [T]` — the parameter surface; both plan shapes; the 3,000–120,000 ms bound;
  the ≤30-chunk / 3s–10min plan bound; `force_instrumental` prompt-only; `seed` plan-only;
  `context_adherence` default `high`; the `music_v2` requirement for chunk plans; the
  commercial-use sentence.
- `### Corrected — the supplied design brief was wrong` — (1) chunks are the `music_v2`
  composition plan, not an inpainting-only shape; (2) plan-mode instrumental is `negative_styles`,
  not `lines: []`, and `music_v2` has no `lines` field; (3) seed is a consistency aid, not
  determinism — the brief's "instrumental vs. determinism conflict" is largely dissolved;
  (4) the 3–120s ceiling was marked unverified but is on the schema page for both shapes.
- `### Could not verify [T-unverified]` — credit cost; whether plan creation is free; the REST
  path for plan creation; the 4,100-char prompt cap; per-tier rate limits; ownership and per-tier
  commercial terms; **and whether the vocal guard actually suppresses vocals**, with the reason
  (no API key in the environment) named explicitly.
- `### Re-verify first, next time` — model IDs and whether a `music_v3` has shipped; pricing and
  credit rates; the plan-creation endpoint's path and cost; the `music-terms` page; the chunk cap
  and duration bounds; whether `music_v1`'s `sections[]` shape is still supported.

**Sourcing caveat, recorded in §7:** the originating spec used a Context7 mirror after reporting
HTTP 403 from `elevenlabs.io`. Direct fetches succeeded on 2026-08-06. A mirror is a weaker source
than a direct read, and the two corrected facts above both came from the mirrored round.

- [ ] **Step 4: Verify every normative line carries a marker**

```bash
grep -nE '^[-*] |^[0-9]+\. ' docs/elevenlabs-music-runbook.md | grep -vE '\[C\]|\[I\]|\[T\]|\[T-unverified\]'
```

Read every line this prints. A purely descriptive line (a schema field listing, a URL) needs no
marker; a **normative** one — anything telling a reader what to do or asserting a platform fact —
does. Add markers until only descriptive lines remain.

- [ ] **Step 5: Commit**

```bash
git add docs/elevenlabs-music-runbook.md && git commit -m "docs: add Eleven Music runbook, web-verified 2026-08-06"
```

---

## Task 2: `music-brief` skill

The corpus-derived pipeline skill. Deliberately thin: it owns the bed **arc** and nothing else.
Most of its corpus material already lives in
`.claude/skills/voiceover-brief/references/production-and-loudness.md` — **do not duplicate it.**

**Files:**
- Create: `.claude/skills/music-brief/SKILL.md`
- Create: `.claude/skills/music-brief/references/bed-arc.md`
- Read first: `.claude/skills/voiceover-brief/SKILL.md` (shape to copy, incl. the File I/O contract
  section verbatim in structure), `rgs-briefs/2026-07-28-nobody-asked-the-kid-assembly.md` §9

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the **Bed Arc** artifact that Task 3's Stage A consumes. Its output sections are fixed
  and Task 3 references them by name: `## Bed arc`, `## Hook hold-out`, `## Tone-contradiction check`,
  `## Deferred to elevenlabs-music`, `## Downstream`. Frontmatter `kind: music`, `stage: 03-music`.

- [ ] **Step 1: Write `references/bed-arc.md`**

The `[C]` findings, translated into arc-design rules. Cite them **exactly** as
`production-and-loudness.md` does — do not paraphrase a citation away.

Required content:

- **Match tone, never contradict.** "No music beats the wrong music — don't add a bed just to fill
  silence if nothing matches the beat's tone" `[C] (Kallaway, i7upRL4H1FM)`. This is the single
  strongest finding behind this skill, and it is also the reason the `music` stage is **not** a
  hard dependency of `assembly` — a no-bed Short is a legitimate outcome of this skill.
- **Low-energy bed; emotion comes from events, not from the bed's own volume.** Risers into a
  reveal, a hit on the release, a low drone under a mysterious beat
  `[C] (vidIQ, DiZnbihU4NM)`.
- **Pausing the music before the big line changes how the moment lands** `[C] (vidIQ, DiZnbihU4NM)`.
  Treat this as a first-class arc device with an explicit timestamp, not an afterthought.
- **Loud music is the most-underestimated AVD killer** `[C] (Romayroh, Wox4Jt_2t6w)`
  `[C] (Roberto Blake, iaTavrWIGDM)` — stated here **only** as the reason the arc must stay
  low-energy. **The duck depth number itself belongs to `voiceover-brief`; do not restate it.**
- **Length-matching is moot for a generated bed** `[I]`. The corpus's rule is to length-match with
  a Remix-style tool and **never rate-stretch, which alters pitch**
  `[C] (Roberto Blake, iaTavrWIGDM)`. A bed composed to the script's own beat durations has nothing
  to remix and nothing to stretch — say this explicitly as the reason the rule is inherited but
  does not bind.
- **The three-movement worked precedent** `[I]`, from
  `rgs-briefs/2026-07-28-nobody-asked-the-kid-assembly.md` §9. Reproduce its shape as the model
  a new arc is built against: **bed out entirely 0–3s** under the hook (the differentiator line
  carries alone), **fade in ~300ms from 3.0s**, warm and light; **narrowing to quiet gravity**
  under the re-hook and the 17–26s quote card; **opening to relief from 38s** through the Loop/CTA.
  Note that brief's rule that the bed tracks the **emotional** arc, not the visual register — a bed
  scored to visual cuts turns a narrative device into a cutaway segment
  `[C] (Kallaway, i7upRL4H1FM)`.
- **Gaps to flag honestly `[I]`:** the corpus has no finding on BPM, key, genre, or instrumentation
  for a Shorts bed, and none at all on AI music generation. Where the user asks for one, say the
  gap exists and hand the question to `elevenlabs-music`, which is vendor-grounded — do not invent
  a confident-sounding tempo.

- [ ] **Step 2: Write `SKILL.md`**

Frontmatter — `name` and `description` only, matching the house shape:

```yaml
---
name: music-brief
description: Designs the background-music bed arc for a faceless YouTube Short — the emotional arc mapped to the script's beat timings, the hook hold-out, the pause-before-the-big-line placement, and a tone-contradiction check against the voiceover brief's tone-per-beat call. Use whenever a Short has a timed script and an approved voiceover brief and the user asks what the music should do — "what music does this Short need," "design the bed," "should there be music under the hook," "what's the music arc," "does this track fit the script," "when should the bed drop out." Takes shorts-scripting's timed script and voiceover-brief's tone call as input; its Bed Arc feeds the elevenlabs-music specialist, which owns the prompt wording, composition plan, and API payload. Every rule traces to the ContentStudio corpus with [C]/[I]/[T] markers. Do not use this to pick duck depth or the LUFS target (that is voiceover-brief), to write the Eleven Music prompt or payload (that is elevenlabs-music), or to write the edit plan (that is shorts-assembly).
---
```

Body sections, in this order:

1. **Title + one-paragraph statement of what it produces.** Describe it as a stage of
   ContentStudio's **seven-skill pipeline**. **Do not assign it an ordinal number** — `voiceover-brief`
   and `visual-prompts` are both "skill #3"-ish (they share `dir_prefix "03"` and run in parallel),
   so a bare "#4" would contradict them. Task 7 decides whether to renumber the pipeline coherently;
   until then, name the position by its neighbours, not by a number.
2. **Pipeline position.** Upstream: `shorts-scripting`'s timed script **and** `voiceover-brief`'s
   tone-per-beat call (both, because the arc cannot be designed before the tone is settled).
   Downstream: an **optional** input to `shorts-assembly`. Downstream specialist:
   `elevenlabs-music`.
   State deference in one explicit paragraph: **duck depth and the −14 LUFS target stay with
   `voiceover-brief` (`references/production-and-loudness.md`) — do not duplicate or contradict
   them here. Prompt wording, composition plan, and API payload belong to `elevenlabs-music`.**
3. **Corpus grounding.** Copy the marker key from `voiceover-brief/SKILL.md`. Add the honest gap:
   **the corpus has zero findings on AI music generation** — this skill covers what the bed must
   *do*; how it gets made is `elevenlabs-music`'s vendor-grounded territory.
4. **Workflow**, five steps:
   1. Read the timed script in full, noting every beat boundary in seconds.
   2. Read the voiceover brief's tone-per-beat call. **If it is missing, ask for it** rather than
      inferring tone from the script — inferring is exactly the tone contradiction this skill
      exists to prevent.
   3. Derive the emotional arc: name each movement, its beat range in seconds, and its intended
      feeling. Read `references/bed-arc.md`.
   4. Decide the **hook hold-out** — whether the bed is absent under the hook, and if so, the exact
      fade-in time. Default to holding out when the hook's differentiator is a spoken line `[I]`,
      per the RGS precedent.
   5. Run the **tone-contradiction check**: for every beat, does the arc's intended feeling match
      the voiceover brief's tone for that same beat? Any mismatch is reported, not silently
      reconciled `[C] (Kallaway, i7upRL4H1FM)`. **If no movement matches a beat's tone, recommend
      no bed for that beat** — "no music beats the wrong music."
5. **Output format** — a fenced block with these exact sections:

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

6. **Reference files** — one line for `references/bed-arc.md`.
7. **File I/O contract** — copy the structure from `voiceover-brief/SKILL.md` verbatim, changing
   only: `--kind music`; `stage: 03-music`; upstream resolvers for **both** `--kind script` and
   `--kind voiceover-brief` (with the staleness re-check on both); and frontmatter carrying
   `script:` and `voiceover_brief:` pointers plus the usual
   `date/kind/slug/stage/version/supersedes/status` fields. Keep the closing line: *"Never edit an
   existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this."*

- [ ] **Step 3: Verify the skill loads and carries markers**

```bash
python -c "import re,sys; t=open('.claude/skills/music-brief/SKILL.md',encoding='utf-8').read(); assert t.startswith('---'); print('frontmatter ok'); print('name ok' if re.search(r'^name: music-brief$',t,re.M) else 'NAME MISSING')"
```

Then the marker sweep and the no-drift check:

```bash
grep -nE '^[-*] |^[0-9]+\. ' .claude/skills/music-brief/SKILL.md .claude/skills/music-brief/references/bed-arc.md | grep -vE '\[C\]|\[I\]|\[T\]|\[T-unverified\]'
```

```bash
grep -nE '\-14 LUFS|\-21|\-22 dB' .claude/skills/music-brief/SKILL.md .claude/skills/music-brief/references/bed-arc.md
```

Expected for the second: **either no hits, or only hits that name `voiceover-brief` as the owner in
the same line.** A bare restatement of the duck depth or LUFS target as this skill's own decision is
the drift this task is guarding against — remove it.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/music-brief && git commit -m "feat(skills): add music-brief stage skill for bed arc design"
```

---

## Task 3: `elevenlabs-music` — SKILL.md, composition plans, prompt craft

The specialist's spine plus its two content references. Task 4 adds the payload and gate references.
Mirror `.claude/skills/elevenlabs-audio/SKILL.md`'s anatomy **precisely** — read it before writing.

**Files:**
- Create: `.claude/skills/elevenlabs-music/SKILL.md`
- Create: `.claude/skills/elevenlabs-music/references/composition-plans.md`
- Create: `.claude/skills/elevenlabs-music/references/prompt-craft.md`

**Interfaces:**
- Consumes: `docs/elevenlabs-music-runbook.md` §1–§4 and §6 (Task 1); `music-brief`'s Bed Arc
  output sections (Task 2).
- Produces: the four stage names (`A — Bed profile`, `B — Section map`, `C — Prompt + plan +
  payload`, `D — Iteration & credit discipline`) and the **MUSIC PRODUCTION SPEC** output contract,
  both of which Task 4's gate prompts reference by name.

- [ ] **Step 1: Write `SKILL.md` frontmatter**

Only `name` and `description`. The description is one long line with the four-move shape —
(a) deliverables as a comma-list, (b) `Use whenever…` + ~10 quoted first-person utterances,
(c) the dual-mode statement, (d) an explicit negative boundary:

```yaml
---
name: elevenlabs-music
description: Builds a complete, ready-to-run Eleven Music setup — a bed profile card, a beat-locked section map, a copy-paste prompt for the elevenlabs.io Music app, a composition-plan JSON pinned to the script's own beat durations, a JSON request payload and curl command, and a cost/iteration plan — with fresh-agent validation gates before anything is generated. Use whenever the user is generating music with ElevenLabs and needs the actual setup rather than creative direction: "generate a track for this," "write me the Eleven Music prompt," "build the composition plan," "how do I make the music match my beat timings," "how do I stop it adding vocals," "my prompt got a bad_prompt error," "the track came back the wrong length," "what does context_adherence do," "how do I not burn credits iterating," "make me an instrumental bed for this Short." Works standalone for any music job (podcast bed, ad, game loop, trailer cue, background track) AND as the downstream specialist for ContentStudio's `music-brief` skill, which hands down the corpus-grounded bed arc and leaves the executable configuration to this skill. Do not use this to decide duck depth or the LUFS target (that is `voiceover-brief`), to design the bed arc or the hook hold-out (that is `music-brief`), or to write the edit plan (that is `shorts-assembly`).
---
```

- [ ] **Step 2: Write `SKILL.md` body — sections in `elevenlabs-audio`'s exact order**

**§ Pipeline position — two modes**, then the two-column ownership table:

| `music-brief` owns | `elevenlabs-music` owns |
|---|---|
| The emotional arc and its movements | The style vocabulary that renders that arc |
| The hook hold-out and pause placements | The chunk boundaries and `duration_ms` arithmetic |
| The tone-contradiction call | `model_id`, plan shape, and the parameter conflicts |
| Whether the Short gets a bed at all | The prompt, payload, and credit spend |

Then one line: **Loudness and ducking stay with `voiceover-brief`** (`references/production-and-loudness.md`)
— do not duplicate or contradict them here. Downstream of both: `shorts-assembly`.

**§ Grounding — read before writing any rule.** One source: `docs/elevenlabs-music-runbook.md`,
web-verified **2026-08-06**. Then the marker key (`[T]` / `[T-unverified]` / `[I]` / `[C]`), then
the enforcement sentence copied in spirit from `elevenlabs-audio`:

> **A normative line with no marker means something was invented instead of sourced.**

Then the honest gap, stated plainly:

> **The 420-video ContentStudio corpus contains zero findings on AI music generation.** Nearly every
> normative line in this skill is `[T]` or `[I]`, not `[C]`. The corpus's contribution is entirely
> upstream — what the bed must *do* — and it arrives here through `music-brief`'s Bed Arc. Do not
> dress a vendor fact up as corpus consensus. **The supplied design brief that seeded this skill was
> wrong in two places** (`docs/elevenlabs-music-runbook.md` §7); treat plausible-sounding Eleven
> Music "facts" from memory with the same suspicion.

**§ The control surface — the only inputs you need.** Seven inputs, everything else derived. If the
user gives none, infer from the job and **state every default you assumed**:

| Input | Values | Drives |
|---|---|---|
| `phase` | `draft` \| `master` | `output_format`, chunk count, spend gate |
| `use_case` | `shorts-bed` \| `podcast-bed` \| `ad` \| `trailer-cue` \| `game-loop` | style vocabulary, energy band |
| `bed_arc` | a `music-brief` Bed Arc, a saved Bed Profile Card, or `derive` | Stage A entry point |
| `runtime` | total seconds + per-beat boundaries | chunk `duration_ms` arithmetic |
| `vocals` | `instrumental` \| `vocal` | the guard on every chunk; `force_instrumental` in prompt mode |
| `plan_shape` | `chunks` (`music_v2`, default) \| `sections` (`music_v1`) | `model_id`, schema, field names |
| `consistency` | `on` \| `off` | `seed` (a consistency aid, **not** determinism `[T]`) |

**§ Workflow — four stages, gated:**

- **Stage A — Bed profile.** Consume the Bed Arc + timed script. In pipeline mode the arc is
  already decided — **accept it and do not re-litigate it.** Emit a reusable **Bed Profile Card**
  (mirror `elevenlabs-audio`'s Voice Profile Card pattern) the user can paste back later to skip
  straight to Stage C. The card carries: use case, global positive styles, global negative styles
  incl. the vocal guard, energy band, and the arc's movement names.
- **Stage B — Section map.** **This is the stage that earns the whole skill.** Read
  `references/composition-plans.md`. Map script beats → plan chunks; `duration_ms` must sum to the
  exact runtime; every chunk within **3,000–120,000 ms** `[T]`; **≤30 chunks, total 3s–10min**
  `[T]`. Assign per-chunk `positive_styles`/`negative_styles` and `context_adherence`. A beat longer
  than 120s splits across chunks; a beat under 3s **merges with its neighbour** and the merge is
  stated, not silent. The hook hold-out is realized as a **hold-out**, not as a silent chunk —
  the bed simply starts at the fade-in time and the plan's total runs from there; say so explicitly
  so the editor does not expect audio for the held-out span. **→ Gate 1.**
- **Stage C — Prompt + plan + payload.** Read `references/prompt-craft.md` and
  `references/api-payload.md`. Emit the three copy-paste artifacts: the UI prompt body, the
  composition-plan JSON, and the API request payload + curl. **→ Gate 2.**
- **Stage D — Iteration & credit discipline.** Read `references/api-payload.md` §cost. Explore on
  the plan-creation endpoint before composing; seed re-rolls for consistency (**never presented as
  reproducibility** `[T]`); draft → master; `bad_prompt` recovery via
  `detail.data.prompt_suggestion`; off-length handling via `respect_sections_durations`.
  **Assume every compose call is billed** `[I]` — the "plan creation is free" claim is
  `[T-unverified]`. **→ Gate 3 (a spend authorization: `AUTHORIZED` / `BLOCKED`, not a correctness
  check).**

**§ Fresh-agent validation gates** — the summary table (full prompts live in
`references/validation-gates.md`, Task 4):

| Gate | Fires | Checks |
|---|---|---|
| **1 — Section map** | after Stage B | durations sum to runtime; every chunk within 3,000–120,000 ms; ≤30 chunks; vocal guard present on every chunk; no lyric/vocal content in any `text`; no artist/band/track name in any style string; arc does not contradict the voiceover brief's tone-per-beat call |
| **2 — Payload** | after Stage C | `model_id` explicit and matching the plan shape; prompt XOR `composition_plan`; no `seed` with `prompt`; no `force_instrumental` with a plan; no `music_length_ms` with a plan; style arrays ≤50; `output_format` matches phase |
| **3 — Pre-master spend** | before any master render | a draft was emitted and confirmed; cost stated as an estimate with its `[T-unverified]` status named; re-roll budget named; no reliance on unverified free-plan claims |

Then, copied in substance from `elevenlabs-audio`: **Gates 1 and 2 are independent — dispatch them
in parallel** (single message, two tool calls) once both artifacts exist. **A gate returning
findings blocks emission** until resolved or explicitly overridden by the user, and **an override is
recorded as an override, never as a pass** `[I]`. **Never claim a gate passed without running it.**

**§ Output contract** — an in-chat fenced block, ALL-CAPS unnumbered sections, two-space-indented
content. **Omit a section only when it genuinely does not apply, and say why rather than dropping it
silently:**

```
=== MUSIC PRODUCTION SPEC — [short] — [DRAFT | MASTER] ===

CONTROL SURFACE
  phase / use_case / bed_arc / runtime / vocals / plan_shape / consistency
  Assumed defaults: [every value you chose for the user, named explicitly]

BED PROFILE
  use case · global positive styles · global negative styles (incl. vocal guard) · energy band
  · movement names — reusable as a Bed Profile Card

SECTION MAP
  | # | beat | start–end (s) | duration_ms | positive_styles | negative_styles | context_adherence |
  Sum: [arithmetic shown] = [runtime]

UI PROMPT
  [the prompt body to paste into the elevenlabs.io Music app, verbatim and self-contained]

COMPOSITION PLAN
  [the plan JSON, copy-paste ready]

REQUEST PAYLOAD
  [JSON body + query params]
  [curl command]

MIX HANDOFF
  Duck depth and LUFS target, restated from voiceover-brief — NOT re-decided here.
  Asset filename: S<###>_music.mp3

COST
  [estimate + the [T-unverified] status of the credit rate, stated plainly]

QC CHECKLIST
  [what to listen for, and the parameter fix for each symptom]

VALIDATION GATES
  Gate 1: [pass | findings]   Gate 2: [pass | findings]   Gate 3: [pass | findings | n/a]

NEXT
  [draft → confirm → master, or the handoff to shorts-assembly]
```

**`MIX HANDOFF` has no analogue in `elevenlabs-audio`.** Its whole job is to **restate, never
re-decide**, the duck depth and LUFS target inherited from `voiceover-brief`, plus the
`S<###>_music.mp3` filename, so `shorts-assembly` has everything without a lookup. If this section
ever picks a *different* number from the one upstream chose, that is the drift the boundary exists
to prevent.

**§ What this skill does NOT do:**
- **Call the Eleven Music API.** It emits payloads and curl commands; you run them. It never handles
  an API key, never renders audio, and never spends credits on its own.
- **Duck depth, LUFS, or the mix** — `voiceover-brief`.
- **The bed arc, the hook hold-out, or whether the Short gets a bed at all** — `music-brief`.
- **The edit plan** — `shorts-assembly`. **The script** — `shorts-scripting`.

**§ `[T]` facts most likely to be stale** — model IDs and whether a `music_v3` has shipped; the
`music_v1` `sections[]` shape's continued support; credit rates; the plan-creation endpoint's path
and cost; per-tier commercial terms; the ≤30-chunk and 3,000–120,000 ms bounds; `context_adherence`'s
default. Plus: **everything `[T-unverified]`** — the credit cost, the free-plan claim, and above all
**whether the vocal guard actually suppresses vocals** — is a starting point, never a fact.

**§ Reference files** — one line each for the four references.

- [ ] **Step 3: Write `references/composition-plans.md`**

Covers: both plan shapes with full field tables (from runbook §2); the beat→chunk mapping method
worked as arithmetic; the split rule (>120s) and merge rule (<3s) with the requirement that a merge
is stated; `respect_sections_durations` (default `true`, and what setting it `false` costs you);
`context_adherence` (`low`/`medium`/`high`, default `high`) and when to lower it — a movement that
must feel *different* from its neighbours, e.g. the quiet-gravity centre of the RGS three-movement
arc; and **the instrumental technique with its verification status stated plainly**:

> **`negative_styles` carrying vocal terms is the documented plan-mode instrumental technique**
> `[T]` (2026-08-06) — `force_instrumental` is prompt-only and does not apply to plans, and
> `music_v2` chunks have no `lines` field. **Every chunk this skill emits carries
> `["vocals", "singing", "spoken word", "lyrics"]` in `negative_styles`** `[I]`. **Whether that
> guard is sufficient in practice is `[T-unverified]`** — it has not been confirmed by a live
> generation (`docs/elevenlabs-music-runbook.md` §7). Say so out loud when you emit a plan, and
> tell the user to listen to the first render specifically for vocalise or humming.

- [ ] **Step 4: Write `references/prompt-craft.md`**

Covers: the UI prompt body for the elevenlabs.io Music app (self-contained, no external context);
Include/Exclude Styles and their ≤50-item, English-only caps `[T]`; BPM and key cues; instrument
and vocal isolation; descriptor layering; **the copyright guard with its full recovery path** —
catch `bad_prompt`, read `detail.data.prompt_suggestion`, diff it against the original to learn
which token tripped the guard, retry `[T]`; and **translating a bed arc into style vocabulary** —
a table mapping the arc's feeling words ("warm and light", "quiet gravity", "relief") to concrete
style tokens, marked `[I]` because it is this skill's craft inference, not a documented mapping.

Include the standing prohibition: **never put an artist, band, or track name in any style string or
prompt body** `[T]` — it trips the guard, and it is the one prompt-craft mistake that costs a whole
generation.

- [ ] **Step 5: Verify markers and boundary**

```bash
grep -nE '^[-*] |^[0-9]+\. ' .claude/skills/elevenlabs-music/SKILL.md .claude/skills/elevenlabs-music/references/*.md | grep -vE '\[C\]|\[I\]|\[T\]|\[T-unverified\]'
```

```bash
grep -nE 'lines: \[\]|force_instrumental.*plan|seed.*determinis|reproducib' .claude/skills/elevenlabs-music/SKILL.md .claude/skills/elevenlabs-music/references/*.md
```

Expected for the second: hits only where the file is **correcting** these — e.g. "seed is not a
reproducibility guarantee". A line asserting `lines: []` gives instrumental output, or that seed
gives determinism, is a regression against Task 1's verified facts.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/elevenlabs-music && git commit -m "feat(skills): add elevenlabs-music specialist spine, plans and prompt craft"
```

---

## Task 4: `elevenlabs-music` — API payload and validation gates

The two remaining references. Split from Task 3 because a reviewer can meaningfully reject the gate
checklists while accepting the prompt craft.

**Files:**
- Create: `.claude/skills/elevenlabs-music/references/api-payload.md`
- Create: `.claude/skills/elevenlabs-music/references/validation-gates.md`
- Read first: `.claude/skills/elevenlabs-audio/references/validation-gates.md` — the gate mechanics
  are copied from it verbatim in structure.

**Interfaces:**
- Consumes: Task 1's runbook §1, §3, §5; Task 3's stage names and output contract.
- Produces: three verbatim dispatch prompts referenced by `SKILL.md`'s gate table.

- [ ] **Step 1: Write `references/api-payload.md`**

Covers the three endpoints (runbook §1), then **the parameter conflicts, stated as a table** because
they are the failure mode:

| Conflict | Rule `[T]` 2026-08-06 |
|---|---|
| `prompt` vs `composition_plan` | Mutually exclusive. One or the other, never both. |
| `seed` | Plan-only — "cannot be used in conjunction with prompt". |
| `force_instrumental` | Prompt-only. Does **not** apply to composition plans. |
| `music_length_ms` | Prompt-only, 3,000–600,000 ms. With a plan, length comes from the chunks. |
| `model_id` | Default is `music_v1`, **not** the newer model — set it explicitly. Chunk plans require `music_v2`. |

Then: `output_format` (query param, default `auto`) by phase; curl templates for compose-from-plan,
compose-from-prompt, and plan creation; and **cost/iteration discipline** —

- Explore with plan creation before composing `[I]`; the design brief's "costs no credits" claim is
  **`[T-unverified]`** and must be presented as a hypothesis, not a free lunch.
- **Assume every compose call is billed** `[I]`. The credit rate per generation is
  **`[T-unverified]`** — not found in the docs on 2026-08-06.
- Seed re-rolls: same seed + same params → *more consistent* results; **exact reproducibility is not
  guaranteed and output may change across system updates** `[T]`. Never promise a re-render matches.
- Draft → master: draft at a low `output_format` and a reduced chunk count covering only the
  movements in question; master at full runtime `[I]`.
- `bad_prompt` recovery: catch, read `detail.data.prompt_suggestion`, retry with it `[T]`.
- Off-length handling: `respect_sections_durations` defaults to `true` `[T]`; if a render still
  comes back off-length, fix the **plan arithmetic**, and **never rate-stretch the audio** — it
  alters pitch `[C] (Roberto Blake, iaTavrWIGDM)`. A composed-to-length bed should not need this at
  all, which is the point.

- [ ] **Step 2: Write `references/validation-gates.md`**

Open with the **Rules of use** block and the **no-markers rationale**, both carried over from
`elevenlabs-audio/references/validation-gates.md`:

```markdown
# Validation gates — fresh-agent dispatch prompts

Three gates. Each dispatches a **fresh `general-purpose` agent** that has **not** seen the authoring
rationale, so it checks the artifact rather than rubber-stamping the reasoning.

**Rules of use:**

- Use the prompts below **as written**. Each already embeds the repo's sub-agent output contract.
- **Gates 1 and 2 are independent — dispatch them in parallel** (one message, two tool calls) once
  both artifacts exist.
- **A gate returning findings blocks emission** until each finding is resolved or the user explicitly
  overrides it.
- **Never report a gate as passed without running it.** Report results verbatim in the spec's
  VALIDATION GATES section.
- Paste the artifact **into the prompt**. The agent must not have to go looking for it, and must not
  be told why any choice was made.

**Why the checklists carry no `[C]`/`[I]`/`[T]` markers.** They are prompt text sent to another
agent, not normative claims addressed to you — a marker inside them would read as noise to the
sub-agent and invite it to weigh rules rather than apply them. **Every factual rule in the three
checklists below is `[T]`, web-verified 2026-08-06**, and traces to
`docs/elevenlabs-music-runbook.md`. If you change a checklist item, verify it there first; an
unverified rule in a gate is worse than no gate, because it manufactures false findings.
```

Then Gate 1, written out in full — a numbered CAPS-LABEL checklist where **every item names its own
failure condition as a FINDING** (the house phrasing is "… is a FINDING", as in
`elevenlabs-audio/references/validation-gates.md`; do not invent a `= FINDING` suffix that file does
not use), closed by the fixed ~1,500-token deliverable footer:

```
You are validating an Eleven Music section map against a fixed checklist. You have not seen
why any choice was made, and you should not infer intent — check only what is in front of
you. Do not fix anything; report.

TARGET MODEL: <music_v1 | music_v2>
PLAN SHAPE: <sections | chunks>
DECLARED TOTAL RUNTIME (seconds): <value>
VOICEOVER BRIEF TONE PER BEAT: <the tone call, beat by beat, or "none supplied">

SECTION MAP:
---
<the full section/chunk table including every duration_ms and every style array>
---

Check each item and report PASS or FINDING with the offending value quoted:

1. DURATION SUM. The duration_ms values must sum to exactly the declared total runtime
   (in milliseconds). Show your arithmetic. Any mismatch is a FINDING.
2. PER-CHUNK BOUNDS. Every duration_ms must be between 3,000 and 120,000 inclusive. Any
   value outside that range is a FINDING.
3. PLAN SIZE. A composition plan supports at most 30 chunks/sections, with a total duration
   between 3 seconds and 10 minutes. Exceeding either is a FINDING.
4. VOCAL GUARD. Every chunk/section must carry vocal-exclusion terms (e.g. "vocals",
   "singing", "spoken word", "lyrics") in its negative styles array. Any chunk missing the
   guard is a FINDING.
5. NO LYRIC CONTENT. For a chunk plan, each chunk's `text` must be a structural label or
   instrumental direction, never singable lyrics. For a sections plan, every `lines` array
   must be empty. Lyric content in an instrumental brief is a FINDING.
6. NO NAMED ARTISTS. No artist, band, musician, album, or track name may appear in any style
   string, in any `text`, or in the prompt body. Naming one triggers a bad_prompt error.
   Any occurrence is a FINDING.
7. STYLE ARRAY CAPS. positive and negative style arrays are capped at 50 items each and are
   English-only. Exceeding either is a FINDING.
8. TONE CONTRADICTION. Compare each section's intended feeling against the voiceover brief's
   tone for the same beat. Any section whose feeling contradicts the spoken tone at that beat
   is a FINDING — report it even if the contradiction looks deliberate.
9. COVERAGE. Every beat in the declared runtime must be accounted for, either by a chunk or
   by an explicitly stated hold-out. An unexplained gap is a FINDING.
10. MODEL/SHAPE MATCH. A chunks[] plan requires model_id music_v2. A sections[] plan is the
    music_v1 shape. A mismatch between the declared model and the plan shape is a FINDING.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted, each as "Item N — <quoted offending value> — <one-line why>"
- Recommendation: 1–3 sentences
- Open questions: only if genuinely blocking

DO NOT:
- Paste full file contents or reproduce tool output verbatim
- Restate the task or narrate your process
- Include a preamble, closing summary, or sign-off
```

Write Gate 2 (payload) to the same shape, checking: `model_id` present and explicit (the API default
is `music_v1`, so an absent value silently selects it); `prompt` and `composition_plan` never both
present; `seed` absent whenever `prompt` is used; `force_instrumental` absent whenever a
`composition_plan` is used; `music_length_ms` absent whenever a `composition_plan` is used and within
3,000–600,000 when present; `output_format` appropriate to the declared phase;
`context_adherence` ∈ {low, medium, high}; the plan embedded in the payload being byte-identical to
the one Gate 1 saw.

Write Gate 3 (pre-master spend) as an authorization, not a correctness check — `AUTHORIZED` or
`BLOCKED`. It must check: a draft was emitted and the user explicitly confirmed it (silence is not
confirmation); the master plan is the confirmed draft plan, not a rewrite that was never drafted;
a cost estimate was shown **with its `[T-unverified]` status stated** — presenting an unverified
credit rate as a firm number is grounds to BLOCK; a re-roll budget is named; and **the spec does not
claim seed guarantees reproducibility**, since the docs explicitly disclaim it — any such claim is
grounds to BLOCK.

Close the file with the `## Reporting gate results` template, modelled on `elevenlabs-audio`'s:

```markdown
## Reporting gate results

```
VALIDATION GATES
  Gate 1 (section map):  PASS
  Gate 2 (payload):      2 FINDINGS — resolved:
                         · Item 4: force_instrumental present with a composition_plan → removed
                         · Item 1: model_id absent → set explicitly to music_v2
  Gate 3 (spend):        AUTHORIZED
```

If the user overrides a finding, record it as an override with their reason — not as a pass `[I]`.
```

- [ ] **Step 3: Verify the gate files' shape**

```bash
grep -c "FINDING" .claude/skills/elevenlabs-music/references/validation-gates.md
```

Expected: **at least 20**. Grep is case-sensitive, so this counts only the ALL-CAPS token: Gate 1's
ten item-level "is a FINDING" clauses plus its "report PASS or FINDING" header (11), and Gate 2's
equivalent (~11). It does **not** count Gate 3, which reports `AUTHORIZED`/`BLOCKED` rather than
findings, nor the footer's lowercase "Findings:". Then confirm the footer appears three times:

```bash
grep -c "DELIVERABLE FORMAT (hard limit ~1,500 tokens)" .claude/skills/elevenlabs-music/references/validation-gates.md
```

Expected: `3`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/elevenlabs-music/references && git commit -m "feat(skills): add elevenlabs-music payload reference and validation gates"
```

---

## Task 5: Pipeline registration

The only task with real code. TDD applies: the stage-count canary in
`pipeline-app/tests/test_pipeline_config.py` fails the moment `pipeline.yaml` changes, and the
template test guards a failure mode that is otherwise only discoverable at runtime.

**Files:**
- Modify: `pipeline.yaml`
- Create: `pipeline-app/stage_templates/music.md`
- Modify: `pipeline-app/pipeline_app/routes/skills.py`
- Test: `pipeline-app/tests/test_pipeline_config.py`, `pipeline-app/tests/test_prompt_builder.py`,
  `pipeline-app/tests/test_routes_skills.py`

**Interfaces:**
- Consumes: `.claude/skills/music-brief/SKILL.md` and `.claude/skills/elevenlabs-music/SKILL.md`
  must both exist — `_validate_topology` raises if `stage.specialist`'s `SKILL.md` is missing, so
  Tasks 2–4 are hard prerequisites.
- Produces: stage id `music`, consumed by Task 6's `shorts-assembly` note and Task 8's UI checks.

- [ ] **Step 1: Write the failing tests**

In `pipeline-app/tests/test_pipeline_config.py`, **rename** `test_load_topology_has_seven_stages`
(it is eight stages now) and add the `music` assertions:

```python
def test_load_topology_has_eight_stages():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    assert len(stages) == 8
    ids = [s.id for s in stages]
    assert ids == [
        "grounding", "ideation", "scripting", "voiceover", "visual", "music",
        "assembly", "repurpose",
    ]


def test_music_stage_is_registered_with_its_specialist():
    stages = load_topology(REPO_ROOT / "pipeline.yaml")
    music = next(s for s in stages if s.id == "music")
    assert music.skill == "music-brief"
    assert music.depends_on == ["scripting", "voiceover"]
    assert music.specialist == "elevenlabs-music"
    assert music.specialist_mode == "manual"
    assert music.dir_prefix == "03"


def test_music_stage_has_a_kickoff_template():
    """prompt_builder does env.get_template(f"{stage_id}.md"); a missing file is a
    TemplateNotFound raised at the stage's first turn, which is otherwise only
    discoverable at runtime."""
    assert (REPO_ROOT / "pipeline-app" / "stage_templates" / "music.md").exists()
```

**Leave `test_assembly_depends_on_both_branch_stages` untouched** — assembly's deps do not move.
If you find yourself editing it, re-read Task 6.

In `pipeline-app/tests/test_prompt_builder.py`:

```python
def test_music_template_lists_script_and_voiceover_inputs():
    prompt = render_kickoff_prompt(TEMPLATES_DIR, "music", {
        "skill": "music-brief",
        "user_message": "",
        "grounding_pointer": None,
        "input_file": "runs/x/02-scripting/artifact.v1.md",
        "input_files": [
            "runs/x/02-scripting/artifact.v1.md",
            "runs/x/03-voiceover/artifact.v1.md",
        ],
        "raw_output_path": "runs/x/03-music/raw_output.md",
    })
    assert prompt.strip().startswith("/music-brief")
    assert "runs/x/02-scripting/artifact.v1.md" in prompt
    assert "runs/x/03-voiceover/artifact.v1.md" in prompt
    assert "runs/x/03-music/raw_output.md" in prompt
```

In `pipeline-app/tests/test_routes_skills.py`:

```python
def test_stage_id_by_skill_maps_music_brief_but_not_the_specialist():
    """STAGE_ID_BY_SKILL is a duplicate registry that fails silently in the in-app
    skill editor when a stage skill is missing. Specialists are deliberately absent
    from it — elevenlabs-audio and midjourney-prompting are not keys either."""
    from pipeline_app.routes.skills import STAGE_ID_BY_SKILL
    assert STAGE_ID_BY_SKILL["music-brief"] == "music"
    assert "elevenlabs-music" not in STAGE_ID_BY_SKILL
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd pipeline-app && python -m pytest tests/test_pipeline_config.py tests/test_prompt_builder.py tests/test_routes_skills.py -v
```

Expected: `test_load_topology_has_eight_stages` FAILS (`assert 7 == 8`),
`test_music_stage_is_registered_with_its_specialist` FAILS (`StopIteration`),
`test_music_stage_has_a_kickoff_template` FAILS, `test_music_template_lists_script_and_voiceover_inputs`
FAILS (`TemplateNotFound: music.md`), `test_stage_id_by_skill_maps_music_brief_but_not_the_specialist`
FAILS (`KeyError: 'music-brief'`).

- [ ] **Step 3: Add the stage to `pipeline.yaml`**

Insert between the `visual` and `assembly` blocks, matching the file's existing two-space indent:

```yaml
  - id: music
    skill: music-brief
    specialist: elevenlabs-music
    specialist_mode: manual
    dir_prefix: "03"
    depends_on: [scripting, voiceover]
```

`dir_prefix: "03"` groups it with voiceover and visual in the sidebar (`build_stage_nav` groups by
`dir_prefix` in `stage_defs` order). `depends_on: [scripting, voiceover]` keeps it LOCKED until the
tone call is approved. `specialist_mode` **must** be exactly `"auto"` or `"manual"` —
`_validate_topology` rejects anything else, because `sidebar.html` treats a missing or typo'd value
as `(auto-delegated)`, the stronger and wrong claim.

- [ ] **Step 4: Create `pipeline-app/stage_templates/music.md`**

`turn_service` builds `input_files` from `depends_on` filtered in `all_stage_defs` order, so
`input_files[0]` is the **script** and `input_files[1]` is the **voiceover brief**. Both matter, so
loop them like `assembly.md` does rather than using `input_file`:

```jinja
/{{ skill }}

Read the following upstream artifacts and produce the music bed brief:
{% for f in input_files %}
- `{{ f }}`
{% endfor %}
{% if grounding_pointer %}
A companion grounding artifact is available at `{{ grounding_pointer }}` — carry forward any
citations or constraints it names.
{% endif %}
{{ user_message }}

Write your final brief to `{{ raw_output_path }}` (overwrite it completely each time you produce a
new draft).
```

- [ ] **Step 5: Register the skill→stage mapping**

In `pipeline-app/pipeline_app/routes/skills.py`, add one entry to `STAGE_ID_BY_SKILL`, after
`"visual-prompts": "visual",`:

```python
    "music-brief": "music",
```

**Do not add `elevenlabs-music`.** That dict deliberately omits both existing specialists
(`elevenlabs-audio` and `midjourney-prompting` are absent); the `/skills` *list* page auto-discovers
from the filesystem, so the specialist still appears there.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd pipeline-app && python -m pytest -q
```

Expected: all pass, including the previously-failing five. If `_validate_topology` raises
`specialist 'elevenlabs-music' has no skill at …`, Task 3 did not land — fix that first.

- [ ] **Step 7: Commit**

```bash
git add pipeline.yaml pipeline-app/stage_templates/music.md pipeline-app/pipeline_app/routes/skills.py pipeline-app/tests && git commit -m "feat(pipeline): register music stage with elevenlabs-music specialist"
```

---

## Task 6: Neighbour skills — `shorts-assembly` and `voiceover-brief`

**Files:**
- Modify: `.claude/skills/shorts-assembly/SKILL.md`
- Modify: `.claude/skills/voiceover-brief/SKILL.md`

**Interfaces:**
- Consumes: the stage id `music` and the artifact `kind: music` from Tasks 2 and 5.
- Produces: no new interface — this task makes the music brief *consumable* downstream.

### ⚠ Do NOT change `assembly.depends_on`

**This is the trap a naive implementation walks into.** It stays `[voiceover, visual]`. Two
independent reasons, both verified in this codebase:

1. **It would permanently brick every existing project.** Stage rows are materialized only at
   project creation — `project_service.create_project` loops `applicable` stage defs and calls
   `db_mod.create_stage_row` once per stage. The unlock loop in `approval_service` only promotes
   stages that *have* a DB row (`if row is not None and row["status"] == StageStatus.LOCKED.value`).
   A pre-existing project has no `music` row → `music` can never be approved → `assembly` would
   stay LOCKED forever. There is no fix short of a backfill migration.
2. **The corpus argues against it.** "No music beats the wrong music — don't add a bed just to fill
   silence if nothing matches the beat's tone" `[C] (Kallaway, i7upRL4H1FM)`. And
   `rgs-briefs/2026-07-28-nobody-asked-the-kid-assembly.md` §9 leaves the source open among library
   options. A no-bed Short and a library-track Short would both get a mandatory generation stage in
   the critical path.

- [ ] **Step 1: Make the music brief an optional fourth input to `shorts-assembly`**

Three edits to `.claude/skills/shorts-assembly/SKILL.md`:

**(a) Pipeline-position table.** Add the music brief to the Upstream cell, marked optional:
`` `music-brief` (bed arc — **optional**) ``.

**(b) Inputs required.** The list currently ends: *"If any of the three is missing, ask for it
rather than inventing shot content."* Change to three required + one optional, and add the fourth
item:

```markdown
4. **Optional — the music bed brief** (from `music-brief`, and its `elevenlabs-music` MIX HANDOFF
   if one exists). If present, use its bed arc, hook hold-out and asset filename in the loudness/mix
   section instead of leaving the bed unspecified. **If absent, carry the existing rights-note
   checkpoint unchanged** — a Short with a library track or no bed at all is a legitimate outcome,
   and the corpus is explicit that no music beats the wrong music
   `[C] (Kallaway, i7upRL4H1FM)`.

If any of the first three is missing, ask for it rather than inventing shot content — this skill
assembles what upstream produced, it doesn't re-derive the script or the visuals. **The fourth is
genuinely optional and its absence is never a blocker.**
```

**(c) File I/O contract.** In the standalone-mode resolver step, add an optional fourth resolve
(`--kind music`) whose absence is not an error, and add to the frontmatter block:

```yaml
   music: <the music file's path as the resolver printed it, if one exists — omit the key entirely if not>
```

**Leave the rights checkpoint exactly as it is.** Task 1's §6 confirmed only a general commercial-use
sentence; per-tier terms and ownership are `[T-unverified]`. Retiring the checkpoint on that basis
would be exactly the unsourced confidence this repo forbids.

**Note the app-mode limitation honestly.** Because `assembly.depends_on` does not include `music`,
`turn_service` will **not** pass the music artifact to `shorts-assembly` in app-driven mode — it
builds `input_files` from `depends_on` only. Add one line to the App-driven paragraph of the File
I/O contract saying so, and telling the skill to check the run's `03-music/` directory for an
`artifact.v*.md` if the user mentions a bed:

```markdown
**App-driven note.** The `music` stage is not one of this stage's `depends_on`, so a music brief is
not passed in automatically. If the user references a bed, look for the run's
`03-music/artifact.v*.md` (highest version wins) and read it; if there is none, proceed with the
rights-note checkpoint as normal `[I]`.
```

- [ ] **Step 2: Point bed generation downstream from `voiceover-brief`**

In `.claude/skills/voiceover-brief/SKILL.md`, in the **Downstream specialist** bullet where it
already defers to `elevenlabs-audio`, add one paragraph mirroring that shape:

```markdown
  **Bed generation is downstream too.** Loudness, ducking and the music mix stay here
  (`references/production-and-loudness.md`) — but *designing and sourcing the bed itself* does not.
  The bed's emotional arc, its hook hold-out and the tone-contradiction check belong to
  `music-brief`; the Eleven Music prompt, composition plan and API payload belong to
  `elevenlabs-music`. Hand the tone-per-beat call down and let them own that layer, exactly as this
  skill does with `elevenlabs-audio`.
```

**Do not move or weaken the existing duck-depth and LUFS material.** It stays here, and the
`elevenlabs-music` MIX HANDOFF restates it rather than re-deciding it.

- [ ] **Step 3: Verify the boundary held**

```bash
grep -n "music" .claude/skills/shorts-assembly/SKILL.md
```

Confirm the music brief reads as optional everywhere it appears, and that the rights-note
checkpoint text is unchanged.

```bash
grep -n "depends_on" pipeline.yaml
```

Confirm `assembly` still reads `depends_on: [voiceover, visual]`.

```bash
cd pipeline-app && python -m pytest tests/test_pipeline_config.py -q
```

Expected: all pass, including the untouched `test_assembly_depends_on_both_branch_stages`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/shorts-assembly .claude/skills/voiceover-brief && git commit -m "feat(skills): treat music brief as optional assembly input; defer bed generation"
```

---

## Task 7: Docs and build

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `pipeline-app/README.md`,
  `docs/superpowers/plans/2026-07-28-skill-markdown-file-contract.md`,
  `scripts/build-cowork-plugin.sh`

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: no code interface.

### ⚠ Scope the "six" → "seven" edit correctly

The originating task spec says *"grep for `six` and fix every hit."* **That instruction is too
broad and following it literally would corrupt the repo's history.** A grep for `six` returns ~100
hits, and most are in files that must **not** be retro-edited:

- **`docs/superpowers/plans/*` and `docs/superpowers/specs/*`** (except the file-contract plan's
  `<kind>` enum, which is a live contract) are **dated historical records** of what was decided at
  the time. "The six existing generic skills are not modified here" was true when written. Editing
  it rewrites history.
- **`rgs-briefs/*.md`** are **immutable** — a `PreToolUse` hook blocks the write outright.
- Many hits are the ordinary English word ("six thousand athletes", "six V8 anchors", "six
  surfaces", "age six") and have nothing to do with the skill count.

**Edit only these live, normative surfaces:**

| File | Hit |
|---|---|
| `CLAUDE.md` | lines with "six atomic Claude Code skills", "### The six skills", "the six-stage pipeline", "the six pipeline skills", "install all six" |
| `README.md` | "ContentStudio's six generic shorts-production skills" |
| `pipeline-app/README.md` | "the ContentStudio six-skill pipeline" |
| `.claude/skills/shorts-assembly/SKILL.md` | "the fifth of six atomic ContentStudio skills" |
| `.claude/skills/voiceover-brief/SKILL.md` | "skill #3 of ContentStudio's six-skill pipeline" |
| `.claude/skills/elevenlabs-audio/SKILL.md` | "skill #3 of the six-skill pipeline" |
| `.claude/skills/rgs-grounding/SKILL.md` | frontmatter: "not for the six generic ContentStudio pipeline skills' brands" |
| `.claude/skills/shorts-ideation/SKILL.md` | frontmatter: "the ContentStudio six-skill pipeline" — the **count** only (see below) |
| `.claude/skills/social-repurpose/SKILL.md` | frontmatter: "the ContentStudio six-skill pipeline" — the **count** only (see below) |
| `scripts/build-cowork-plugin.sh` | header comment, `plugin.json` description, `README.md` heredoc |

**Separate the count from the ordinal.** These files carry two different stale things, and only one
of them is optional:

- **The bare count** ("six-skill pipeline") is simply wrong once the stage lands. **Fix it
  everywhere it appears**, including in `shorts-ideation` and `social-repurpose`.
- **The ordinal** ("This is skill #1 of 6" in `shorts-ideation`; "the fifth of six" in
  `shorts-assembly`; "skill #3" in `voiceover-brief`) is a renumbering decision. Renumbering the
  whole pipeline coherently is fine and preferable — but do it consistently or not at all. A
  half-renumbered pipeline is worse than a stale ordinal. Note that `voiceover-brief` and
  `visual-prompts` run in parallel and share `dir_prefix "03"`, so any renumbering has to decide
  what to do with that pair before it can be consistent.

- [ ] **Step 1: Update `CLAUDE.md`**

Three substantive edits beyond the count:

**(a)** The pipeline-skills table gains a row, placed after `visual-prompts` to match `pipeline.yaml`
order:

```markdown
| `music-brief` | Script + voice spec → bed arc | the script + voiceover brief | bed arc (movements, hook hold-out, tone-contradiction check) |
```

**(b)** The tool-specialist table gains a row:

```markdown
| `elevenlabs-music` | Eleven Music | Any music job — podcast bed, ad, game loop, trailer cue | `music-brief` hands down the bed arc; this skill emits the prompt, composition plan and payload |
```

**(c)** In the paragraph naming each specialist's source of truth, add: for `elevenlabs-music`,
`docs/elevenlabs-music-runbook.md` (verified **2026-08-06**). And extend the sentence about
vendor runbooks being wrong — the enterprise runbook was wrong in eight places, the V8.2 runbook in
six, **and the Eleven Music design brief in two** (`docs/elevenlabs-music-runbook.md` §7).

- [ ] **Step 2: Update the file-contract `<kind>` enum**

In `docs/superpowers/plans/2026-07-28-skill-markdown-file-contract.md`, Global Constraints, the
`<kind>` enum becomes:

```
`concept-brief, script, voiceover-brief, visual-prompts, music, assembly, social-repurpose`
```

**Spec text only — no code change.** `scripts/resolve_brief_version.py` takes `--kind` as a free
string (`parser.add_argument("--kind", default=None, …)`), so `music` already resolves. Verify:

```bash
python scripts/resolve_brief_version.py --slug nobody-asked-the-kid --kind music
```

Expected: it prints `NONE\t0` (no music brief exists yet) **and exits with code 1** — that is the
resolver's normal "nothing found" signal, not a crash. Do not wrap this call in a `set -e` script
without handling the nonzero exit.

- [ ] **Step 3: Update the build script**

In `scripts/build-cowork-plugin.sh`, three text updates. The header comment ("the six pipeline
skills plus the two tool-specialist skills") becomes seven and three. The `plugin.json` description
and the `README.md` heredoc likewise, adding the two new skills to the heredoc's skill listing.

**Critical:** the script `rm -rf`s the two RGS-only skills. **`music-brief` and `elevenlabs-music`
are generic and must NOT be added to that removal line** — they are auto-included by the
`cp -R .claude/skills/.` and must stay.

- [ ] **Step 4: Verify the build**

```bash
bash scripts/build-cowork-plugin.sh
```

Expected: the closing line reports **10** skills — 10 existing skill dirs plus the 2 new ones, minus
the 2 RGS-only dirs the script removes.

```bash
ls cowork-plugin/skills/ && test -f dist/content-studio.plugin && echo "PLUGIN BUILT"
```

Expected: `music-brief` and `elevenlabs-music` both present; `rgs-grounding` and
`rgs-pairing-review` both absent; `PLUGIN BUILT` printed.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md pipeline-app/README.md docs/superpowers/plans/2026-07-28-skill-markdown-file-contract.md scripts/build-cowork-plugin.sh .claude/skills && git commit -m "docs: seven-stage pipeline, three tool specialists"
```

`cowork-plugin/` and `dist/` are git-ignored build artifacts — they will not appear in the commit.
That is correct.

---

## Task 8: Full verification pass

Run all of it. Report honestly — a skipped step reported as passed is worse than a failure.

**Files:** none modified (fix-forward if a check fails, then re-run).

- [ ] **Step 1: Test suites**

```bash
cd pipeline-app && python -m pytest -q
```

Expected: all pass, including the five new/renamed assertions.

```bash
python -m pytest tests/ -v
```

Run from the repo root. Expected: unchanged, still green — this suite covers
`lint_prompt_sheet`, `protect_briefs` and `resolve_brief_version`, none of which this change touches.

- [ ] **Step 2: New-project UI check**

```bash
cd pipeline-app && python -m uvicorn pipeline_app.main:create_default_app --factory --host 127.0.0.1 --port 8420
```

Create a new project and confirm, in the sidebar: `music` renders in the **`03`** group alongside
voiceover and visual; it shows **"(manual hand-off)"** for its specialist (not "(auto-delegated)" —
that would mean `specialist_mode` did not parse); it starts **LOCKED**; and it unlocks only after
**both** `scripting` and `voiceover` are approved.

- [ ] **Step 3: Pre-existing-project regression check — do not skip this**

**This is the specific regression the whole design exists to avoid.** Open a project created
**before** this change (one whose stage rows were materialized without a `music` row) and confirm
`assembly` still unlocks normally once `voiceover` and `visual` are approved.

If `assembly` stays LOCKED, `assembly.depends_on` was changed — revert that immediately and re-read
Task 6. There is no fix short of a backfill migration.

- [ ] **Step 4: End-to-end run on the RGS reference brief**

Run the `music` stage against `rgs-briefs/2026-07-28-nobody-asked-the-kid-script.md` and
`…-voiceover-brief.md`, then hand the Bed Arc to `elevenlabs-music`.

**Acceptance:** the emitted section map reproduces that brief's §9 music design — **three
movements** (warm and light from 3s; quiet gravity under the re-hook and the 17–26s quote card;
relief from 38s through the Loop/CTA), with the **bed held out entirely under the 0–3s hook** and
fading in over ~300ms from 3.0s. If the output cannot reproduce this, the skill is not done.

- [ ] **Step 5: Inspect the emitted spec**

Check by hand, against the fenced output block:
- `duration_ms` values sum to the script runtime (50,000 ms for this Short, **less** the 3,000 ms
  hold-out — the spec must state which convention it used, not leave it ambiguous)
- every `duration_ms` is within 3,000–120,000
- the chunk count is ≤30
- every chunk carries the negative-styles vocal guard
- for a chunk plan, no `text` field carries lyrics; for a sections plan, every `lines` array is empty
- no artist, band, or track name appears in any style string

- [ ] **Step 6: Confirm the gates actually ran**

The `VALIDATION GATES` section must show a real result for each of the three — not `n/a` on a gate
that should have fired, and not a claimed pass. **Never claim a gate passed without running it.**
An override must be recorded as an override, with the user's reason.

- [ ] **Step 7: Live generation — attempt, and report the outcome truthfully**

Paste the emitted UI prompt into the elevenlabs.io Music app, and POST the composition plan to
`/v1/music`. Confirm: the returned track's length matches the plan, and **the track is
instrumental** — this is the check that finally settles Task 1's open `[T-unverified]` item.

**On seed:** confirm that re-running with the same seed produces a *similar* track. **Do not assert
identity.** The docs explicitly disclaim exact reproducibility, so an equality assertion here would
be testing something the vendor does not promise.

**If there is no API key, say so plainly and stop.** Do not report this step as passed. Any
divergence — or the inability to run it at all — goes into `docs/elevenlabs-music-runbook.md` §7.
**That log is part of the deliverable, not an afterthought.**

- [ ] **Step 8: Marker sweep across both new skills**

```bash
grep -rnE '^[-*] |^[0-9]+\. ' .claude/skills/music-brief/ .claude/skills/elevenlabs-music/ | grep -vE '\[C\]|\[I\]|\[T\]|\[T-unverified\]'
```

Read every hit. Descriptive lines (field listings, file pointers, JSON) are fine. **A normative line
with no marker is a bug** — fix it before calling this done.

- [ ] **Step 9: Commit any fixes**

```bash
git add -A && git commit -m "fix: verification pass corrections for music stage"
```

---

## Self-Review

**Spec coverage.** Every section of the originating task spec maps to a task: §3 vendor facts →
Task 1; §4 corpus facts → Task 2 (`bed-arc.md`); §5.1 `music-brief` → Task 2; §5.2
`elevenlabs-music` → Tasks 3–4; §5.3 registration → Task 5; §5.4 gating → Task 6; §5.5 docs/build →
Task 7; §5.6 tests → Task 5; §6 order of work → task order; §7 verification → Task 8; §8 standing
constraints → Global Constraints.

**Three deliberate deviations from the spec, all flagged inline:**

1. **Step-zero verification was performed during planning, not deferred.** The spec's step 0 assumed
   `elevenlabs.io` was unreachable. It is reachable; the facts were re-verified, and two were wrong.
   Task 1 carries the corrected facts and re-attempts only the part that genuinely needs an API key.
2. **`music_v2`/chunks is the primary plan shape, not `music_v1`/sections with `lines: []`.** Forced
   by the live docs. Both shapes are documented; the `lines: []` instrumental inference is dropped.
3. **The "grep for `six` and fix every hit" instruction is scoped down** to live normative surfaces.
   Following it literally would retro-edit dated design records and hit the immutability hook on
   `rgs-briefs/`.

**Placeholder scan.** No "TBD", no "add appropriate error handling", no "similar to Task N". Each
code step carries its actual code; each Markdown step carries its actual required content and, where
the wording is load-bearing (frontmatter descriptions, gate prompts, output contracts), the verbatim
text.

**Type consistency.** `StageDef` fields used in Task 5's tests (`skill`, `depends_on`, `specialist`,
`specialist_mode`, `dir_prefix`) all exist on the dataclass in `pipeline_app/pipeline_config.py` —
no `pipeline_config.py` change is needed. `render_kickoff_prompt(templates_dir, stage_id, context)`
and its six context keys (`skill`, `user_message`, `grounding_pointer`, `input_file`, `input_files`,
`raw_output_path`) match `turn_service.py`. `STAGE_ID_BY_SKILL` is a module-level dict in
`routes/skills.py`. Stage id `music` and `dir_prefix "03"` yield `stage_dir_name` → `03-music`,
which is what Task 6's app-driven note and Task 8's checks reference.

**One known limitation, stated rather than hidden.** In app-driven mode the music artifact is not
passed to `shorts-assembly`, because `turn_service` derives `input_files` from `depends_on` and
`assembly.depends_on` deliberately does not include `music`. Task 6 handles this with an explicit
directory-check instruction rather than by changing `depends_on` — which would brick every existing
project.
