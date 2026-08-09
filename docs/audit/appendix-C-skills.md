# Appendix C — Skills, Contracts & Linters

## T8 — Skill contracts & handoff

Scope: the 13 `.claude/skills/*/SKILL.md` files, audited for **contract** defects only — declared
upstream/downstream wiring, frontmatter `description` trigger scope, the three specialist boundaries
CLAUDE.md defines, context minimality (what each skill is told to read), artifact naming coherence
across `pipeline.yaml` / `resolve_brief_version.py --kind` / SKILL.md frontmatter, dead intra-file
cross-references, and handoff format. Provenance markers and every `references/**` file are T9's;
`pipeline.yaml` and `pipeline-app/stage_templates/` are T1's — both were read only as comparison
surfaces, and findings that land there are handed off, not filed here. 35 findings, C-01…C-35.

### Q1 — The handoff chain (declared, as written in each SKILL.md)

| Skill | Declared UPSTREAM input(s) | Declared DOWNSTREAM next stage | Declared at |
|---|---|---|---|
| `rgs-grounding` | none — a raw RGS topic | `shorts-ideation`, plus `shorts-scripting` (citations) and `visual-prompts` (motif) | `rgs-grounding/SKILL.md:18`, `:20` |
| `shorts-ideation` | none by default; optional companion grounding artifact | `shorts-scripting` | `shorts-ideation/SKILL.md:18`, `:20`, `:3` |
| `shorts-scripting` | `shorts-ideation` concept brief; optional grounding artifact | `voiceover-brief` **and** `visual-prompts` | `shorts-scripting/SKILL.md:17`, `:20-22`, `:23-28` |
| `shorts-styleboard` | `shorts-scripting` timed script; optional grounding artifact | `visual-prompts` | `shorts-styleboard/SKILL.md:10-12`, `:15` |
| `voiceover-brief` | `shorts-scripting` timed script | `shorts-assembly`; tone call → `music-brief`; specialist `elevenlabs-audio` | `voiceover-brief/SKILL.md:14`, `:15-17`, `:18` |
| `visual-prompts` | `shorts-scripting` script (Upstream bullet); styleboard artifact (step 2.5 only) | `shorts-assembly`; delegates still prompts to `midjourney-prompting` | `visual-prompts/SKILL.md:10`, `:16-18`, `:95-104`, `:27-30`, `:22-26` |
| `music-brief` | `shorts-scripting` script **and** `voiceover-brief` tone-per-beat call | `shorts-assembly` (**optional**); specialist `elevenlabs-music` | `music-brief/SKILL.md:18-19`, `:20-22` |
| `shorts-assembly` | script + voiceover brief + prompt sheet (all required); music brief (optional) | `social-repurpose` | `shorts-assembly/SKILL.md:14`, `:16-25`, `:29`, `:81` |
| `social-repurpose` | from `shorts-assembly`: script + packaging direction + edit plan (body); script + assembly (File I/O) | none — terminal stage | `social-repurpose/SKILL.md:12-13`, `:128`, `:9-10` |
| `elevenlabs-audio` | `voiceover-brief` creative call (pipeline mode); or 8-input control surface (standalone) | `shorts-assembly` | `elevenlabs-audio/SKILL.md:17-21`, `:33` |
| `elevenlabs-music` | `music-brief` Bed Arc (pipeline mode); or 7-input control surface (standalone) | `shorts-assembly` | `elevenlabs-music/SKILL.md:18-21`, `:33` |
| `midjourney-prompting` | `visual-prompts` per-beat block (pipeline mode); or 9-input control surface | back to `visual-prompts` for its sheet row | `midjourney-prompting/SKILL.md:18-24`, `:181-184` |
| `rgs-pairing-review` | `rgs-grounding/references/pairing-map.md` front-matter + the two corpora | a proposal doc; human then edits `pairing-map.md` | `rgs-pairing-review/SKILL.md:25-26`, `:15-19`, `:71` |

**Asymmetries flagged from this table** (each filed below): `rgs-grounding` names three consumers and
omits `shorts-styleboard`, the skill that actually consumes its thinker/motif (C-02). `shorts-scripting`
names two consumers but four skills claim it upstream (C-05). `shorts-assembly` requires the script while
`pipeline.yaml` does not wire scripting into `assembly` (C-03); `social-repurpose` has the same defect and
additionally states three different input lists in one file (C-04). `elevenlabs-audio` declares
`shorts-assembly` downstream, but `shorts-assembly`'s input list never mentions an AUDIO PRODUCTION SPEC
(C-19) — `elevenlabs-music`'s MIX HANDOFF *is* named there, so the two specialists are wired
asymmetrically. `shorts-assembly` names two voiceover-brief fields (`take count`, `pacing wpm`) that
`voiceover-brief`'s output contract never emits (C-18), and three skills consume a "tone-per-beat call"
that `voiceover-brief`'s output format has no section for (C-01). `rgs-pairing-review` is an orphan in
both directions relative to the pipeline (C-33).

### Q5 — Three (in fact four) artifact vocabularies, side by side

| `pipeline.yaml` stage id | `dir_prefix` | skill name | resolver `--kind` | SKILL.md `stage:` frontmatter | app-driven path |
|---|---|---|---|---|---|
| `grounding` | `00` | `rgs-grounding` | **(none — no `--kind`)** | **(no `stage:` key at all)** | n/a (writes `rgs-briefs/` only) |
| `ideation` | `01` | `shorts-ideation` | `concept-brief` | `01-ideation` | `01-ideation/artifact.v{N}.md` |
| `scripting` | `02` | `shorts-scripting` | `script` | `02-scripting` | `02-scripting/artifact.v{N}.md` |
| `styleboard` | `02b` | `shorts-styleboard` | `styleboard` | `02b-styleboard` | `02b-styleboard/artifact.v{N}.md` |
| `voiceover` | `03` | `voiceover-brief` | `voiceover-brief` | `03-voiceover` | `03-voiceover/artifact.v{N}.md` |
| `visual` | `03` | `visual-prompts` | `visual-prompts` | `03-visual` | `03-visual/artifact.v{N}.md` |
| `music` | `03` | `music-brief` | `music` | `03-music` | `03-music/artifact.v{N}.md` |
| `assembly` | `04` | `shorts-assembly` | `assembly` | `04-assembly` | `04-assembly/artifact.v{N}.md` |
| `repurpose` | `05` | `social-repurpose` | `social-repurpose` | `05-repurpose` | `05-repurpose/artifact.v{N}.md` |

Mismatches: (a) `--kind` mixes stage names (`script`, `styleboard`, `music`, `assembly`), skill names
(`voiceover-brief`, `visual-prompts`, `social-repurpose`) and an artifact noun (`concept-brief`); (b) the
two sibling `03` briefs disagree with each other — `music-brief` → `music` but `voiceover-brief` →
`voiceover-brief`; (c) `repurpose` (stage id) vs `social-repurpose` (kind) is the one row where a single
skill's `stage:` value and `kind:` value are drawn from different vocabularies; (d) grounding has neither
a `kind` nor a `stage`; (e) the app-driven `artifact.v{N}.md` layout is a fourth naming system and is
mentioned in exactly one SKILL.md (`shorts-assembly/SKILL.md:99`). Filed as C-22 and C-23.

---

### C-01 · voiceover-brief's output contract has no tone-per-beat section, yet three skills consume it
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/voiceover-brief/SKILL.md:16`, `.claude/skills/voiceover-brief/SKILL.md:19`, `.claude/skills/voiceover-brief/SKILL.md:89-105`, `.claude/skills/music-brief/SKILL.md:18-19`, `.claude/skills/music-brief/SKILL.md:45`, `.claude/skills/elevenlabs-music/SKILL.md:83`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: `music-brief` blocks on a field that may never exist ("If it is missing, ask for it"), `elevenlabs-music`'s Gate 1 tone check has no data source, and `elevenlabs-audio` enters Stage B expecting a call the brief never named. The whole music branch of the pipeline rests on an undeclared field.
- **trigger**: Any run where `voiceover-brief` emits exactly the five sections its Output format specifies, then `music-brief` is asked for a bed arc.
- **proposed_fix**: Add a named `## Tone per beat` section to `voiceover-brief`'s Output format (one row per beat: beat, tone, delivery intent) and have the three consumers cite that heading by name.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-02 · rgs-grounding's downstream list omits shorts-styleboard, the skill that consumes its motif
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/rgs-grounding/SKILL.md:20`, `.claude/skills/rgs-grounding/SKILL.md:130-132`, `.claude/skills/shorts-styleboard/SKILL.md:10-12`, `.claude/skills/shorts-styleboard/SKILL.md:56`, `.claude/skills/visual-prompts/SKILL.md:66-69`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: The grounding brief's Handoff line tells the operator to carry the artifact to `visual-prompts` for motif cues, but `visual-prompts` now explicitly disclaims that job and points at `shorts-styleboard`. A styleboard run without the grounding artifact invents `register_b_*` keys and the motif rather than inheriting them.
- **trigger**: Any RGS Short where the operator follows the grounding brief's own Handoff section literally.
- **proposed_fix**: Add `shorts-styleboard` to `rgs-grounding`'s Downstream row and to the brief template's Handoff section, and narrow the `visual-prompts` mention to "motif cue for shot composition only".
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-03 · shorts-assembly declares the script REQUIRED but the assembly stage has no scripting dependency
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-assembly/SKILL.md:17`, `.claude/skills/shorts-assembly/SKILL.md:29`, `.claude/skills/shorts-assembly/SKILL.md:74`, `.claude/skills/shorts-assembly/SKILL.md:104-106`
- **component**: skills
- **failure_mode**: loud
- **blast_radius**: In app-driven mode the stage template only passes `depends_on` artifacts, so the script is not among `input_files`; the skill's own rule ("If any of the first three is missing, ask for it") turns every app-driven assembly turn into a blocked request, or into a plan built from the voiceover brief's paraphrase of the script.
- **trigger**: Running the assembly stage from `pipeline-app` rather than standalone.
- **proposed_fix**: Either add `scripting` to the assembly stage's dependencies or downgrade the script to "reachable via the voiceover brief's `script:` pointer" in the SKILL.md; the two must agree. `pipeline.yaml` side is T1's call.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-04 · social-repurpose states three different input lists in one file
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/social-repurpose/SKILL.md:3`, `.claude/skills/social-repurpose/SKILL.md:12-13`, `.claude/skills/social-repurpose/SKILL.md:128-131`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: The description says four artifacts (script + voiceover brief + visual prompts + edit plan), the body says three (script + packaging direction + edit plan), and the File I/O contract resolves two (`script`, `assembly`). A reader cannot tell what is actually required, and the app-driven template passes only one (`input_file`, from `assembly`), so the script arrives by neither route.
- **trigger**: Any repurpose run; the divergence is invisible because the skill can always produce *some* copy.
- **proposed_fix**: Collapse to one input list — the script (for hook language) plus the assembly plan — and make the description, the body, and the File I/O step state exactly that.
- **fix_cost**: S
- **depends_on_finding**: [C-03]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-05 · shorts-scripting declares two downstream consumers; four skills claim it upstream
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-scripting/SKILL.md:23-28`, `.claude/skills/shorts-styleboard/SKILL.md:10`, `.claude/skills/music-brief/SKILL.md:18-19`, `.claude/skills/shorts-assembly/SKILL.md:14`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: An operator reading `shorts-scripting`'s Pipeline position hands the script to voiceover and visual only, and never runs `shorts-styleboard` — which `visual-prompts` step 2.5 then hard-stops on. The script's own "state the up/downstream handoff explicitly" instruction (`:136`) reproduces the stale list into every emitted script.
- **trigger**: Following `shorts-scripting`'s Pipeline position as the routing authority.
- **proposed_fix**: List all four consumers (styleboard, voiceover, visual, and music via voiceover) in the Downstream bullet, marking which are required for the next stage to run.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-06 · shorts-styleboard cites an "Optional input" section it does not contain
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-styleboard/SKILL.md:56`, `.claude/skills/shorts-styleboard/SKILL.md:10-12`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: The one instruction governing how the grounding artifact populates `register_b_*` and `motif` forwards the reader to a section that exists in `shorts-ideation`, `shorts-scripting`, and `visual-prompts` but not here. The reader either follows a sibling skill's section or ignores the rule.
- **trigger**: Reading step 1 of the styleboard workflow with a grounding artifact in hand.
- **proposed_fix**: Either add the "Optional input: a companion grounding artifact" section the other three skills carry, or rewrite `:56` to point at the Pipeline-position bullet at `:10-12`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: grep-sweep

### C-07 · The WORLD LOCK key count is wrong in both skills that state it (11/12 claimed, 13 actual)
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-styleboard/SKILL.md:31`, `.claude/skills/shorts-styleboard/SKILL.md:36-48`, `.claude/skills/visual-prompts/SKILL.md:98`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: The block Gate C parses has 13 keys (5 `register_a_*`, 5 `register_b_*`, `motif`, `slot_register_a`, `slot_register_b`). `shorts-styleboard` calls it "twelve-key (11 real keys plus the heading)" and `visual-prompts` tells the reader to inherit "11 keys ... and its `slot_*` declarations". A styleboard emitted to the stated count drops two keys, and the two slot lines are exactly the ones C20 resolves against the Style Library.
- **trigger**: Emitting or validating a world lock against the stated count rather than the shown block.
- **proposed_fix**: State 13 keys in both files, or drop the count entirely and let the shown block be the contract.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-08 · shorts-assembly's output is "five things" followed by a list of six
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-assembly/SKILL.md:49-55`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: The sixth item is the QA-gate + publish-gate checklist — the one item the skill elsewhere insists must not be skipped (`:80`). A reader counting to five drops precisely the safety checklist.
- **trigger**: Reading the Output line as the deliverable contract.
- **proposed_fix**: Change "five things" to "six things".
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: grep-sweep

### C-09 · midjourney-prompting says "Nine inputs" then instructs inferring "the eight inputs"
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/midjourney-prompting/SKILL.md:64`, `.claude/skills/midjourney-prompting/SKILL.md:105`, `.claude/skills/midjourney-prompting/SKILL.md:212`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: The ninth input is `register` — the pipeline-only input `visual-prompts` hands down and the one that overrides `look`. Step 0's echo-back block and the output contract's CONTROL SURFACE line (`:212`) both enumerate only the original eight, so `register` is silently absent from the echoed control surface in pipeline mode.
- **trigger**: Any pipeline-mode delegation from `visual-prompts` step 4.
- **proposed_fix**: Say "nine inputs" at `:105` and add `register` to the CONTROL SURFACE enumeration at `:212`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: grep-sweep

### C-10 · visual-prompts says "Two things you still own at this step" then lists three
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/SKILL.md:174-191`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: The third bullet is the C11 anti-cloning rule — the one that documents a real production failure (six near-identical stills). A reader counting to two can drop it.
- **trigger**: Reading step 4's retained-ownership list.
- **proposed_fix**: Change "Two things" to "Three things".
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: grep-sweep

### C-11 · shorts-ideation's worked-example pointer says "all five workflow steps"; there are six
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-ideation/SKILL.md:183`, `.claude/skills/shorts-ideation/SKILL.md:91-139`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: Cosmetic; the sixth step is "Assemble the concept brief", which the template section covers independently.
- **trigger**: Reading the Worked example pointer.
- **proposed_fix**: Change "five workflow steps" to "six".
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: grep-sweep

### C-12 · Three skills cite `references/production-and-loudness.md` relative to their own directory, where it does not exist
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/elevenlabs-audio/SKILL.md:32`, `.claude/skills/elevenlabs-music/SKILL.md:32`, `.claude/skills/music-brief/SKILL.md:25`
- **component**: skills
- **failure_mode**: loud
- **blast_radius**: The file lives only at `.claude/skills/voiceover-brief/references/production-and-loudness.md`. All three citations sit in the exact sentence that defines the loudness/ducking boundary, so an agent trying to honor the deference reads nothing and falls back to invented numbers — the specific drift `elevenlabs-music/SKILL.md:197-201` says the boundary exists to prevent.
- **trigger**: Any attempt to open the cited path from within the citing skill.
- **proposed_fix**: Qualify all three to `.claude/skills/voiceover-brief/references/production-and-loudness.md`, matching how `midjourney-prompting/SKILL.md:36` already qualifies its cross-skill reference.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: grep-sweep

### C-13 · voiceover-brief writes into three of the four rows elevenlabs-audio's boundary table assigns to the specialist
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/elevenlabs-audio/SKILL.md:25-30`, `.claude/skills/voiceover-brief/SKILL.md:68`, `.claude/skills/voiceover-brief/SKILL.md:70-72`, `.claude/skills/voiceover-brief/SKILL.md:73-77`, `.claude/skills/voiceover-brief/SKILL.md:91`, `.claude/skills/voiceover-brief/SKILL.md:94`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: `elevenlabs-audio` claims `model_id` routing, the settings floats/stability mode, and tag syntax; `voiceover-brief` step 2 picks the model, step 3 sets the four settings + speaker boost, and step 4 places v3 audio tags and phonetic respellings. The specialist is told to "accept that call and do not re-litigate it" (`:20`), so a wrong model or a v3-only tag chosen upstream is carried into the payload unchallenged — the feature-compatibility check that exists to catch it never fires.
- **trigger**: Any pipeline-mode handoff where `voiceover-brief` named a model or placed a tag.
- **proposed_fix**: Move model routing, the settings floats and tag placement wholly into `elevenlabs-audio`, leaving `voiceover-brief` with voice, tone-per-beat, content type and the mix target; or amend `elevenlabs-audio`'s boundary table to record these as upstream inputs it must still compatibility-check.
- **fix_cost**: M
- **depends_on_finding**: [C-01]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-14 · voiceover-brief and elevenlabs-audio descriptions trigger on the same phrases
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/voiceover-brief/SKILL.md:3`, `.claude/skills/elevenlabs-audio/SKILL.md:3`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: Both descriptions claim "pick or clone an ElevenLabs voice" and both claim the settings ("the four core settings (stability, similarity/clarity, style, speed)" vs. "what stability and similarity settings"). Their negative-scope lines do not disambiguate — `elevenlabs-audio` disclaims only voice *character* and the mix, `voiceover-brief` disclaims only visuals and post copy. A settings question routes to whichever matched first.
- **trigger**: "what stability should I use for this Short" — matches both descriptions.
- **proposed_fix**: Give each description a disjoint verb ("creative brief / which voice and why" vs. "executable configuration / payload") and add the missing negative-scope clause to each so settings and model routing name exactly one owner.
- **fix_cost**: S
- **depends_on_finding**: [C-13]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-15 · visual-prompts' description advertises shorts-styleboard's trigger phrases and then disclaims them
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/SKILL.md:3`, `.claude/skills/shorts-styleboard/SKILL.md:3`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: `visual-prompts`'s trigger list contains "lock the world/registers" verbatim; its own final sentence then says "Does NOT lock the world or pick the sport — that is `shorts-styleboard`". `shorts-styleboard`'s description triggers on "lock the world" and "set the registers". A world-lock request can land in `visual-prompts`, which then hard-stops at step 2.5 for a missing styleboard it was just invoked to produce.
- **trigger**: The user says "lock the world for this Short".
- **proposed_fix**: Delete "lock the world/registers" from `visual-prompts`'s trigger list; keep only the disclaimer sentence.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-16 · elevenlabs-music's Gate 1 re-litigates music-brief's tone call using an input it never declares
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/elevenlabs-music/SKILL.md:139`, `.claude/skills/elevenlabs-music/SKILL.md:29`, `.claude/skills/elevenlabs-music/SKILL.md:61-69`, `.claude/skills/elevenlabs-music/SKILL.md:75`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: The boundary table at `:29` assigns "the tone-contradiction call" to `music-brief`, yet Gate 1 checks that "arc does not contradict the voiceover brief's tone-per-beat call" — a re-run of the upstream skill's own gate. Neither the voiceover brief nor the timed script appears in the seven-input control surface, so a gate that blocks emission depends on data the skill has no declared route to.
- **trigger**: Running Gate 1 in pipeline mode with only the Bed Arc supplied.
- **proposed_fix**: Reduce Gate 1's tone item to "the Bed Arc's `## Tone-contradiction check` section is present and reports no unresolved MISMATCH", which reads only the declared upstream artifact; and add the timed script to the control surface if Stage A genuinely needs it.
- **fix_cost**: S
- **depends_on_finding**: [C-01]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-17 · midjourney-prompting's deterministic mapping emits a literal `--sref <code>` that Gate C rejects in pipeline mode
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/midjourney-prompting/SKILL.md:94`, `.claude/skills/midjourney-prompting/SKILL.md:160`, `.claude/skills/midjourney-prompting/SKILL.md:192`, `.claude/skills/visual-prompts/SKILL.md:106-110`
- **component**: skills
- **failure_mode**: loud
- **blast_radius**: The control-surface mapping table — the skill's stated deterministic contract — maps `consistency: style-lock` to `--sref <code>`. `visual-prompts` requires `{style:register_a}` / `{style:register_b}` slot tokens instead, and Gate C's C16 rejects an invented code outright. Only step 4's prose (`:160`) mentions the slot form, and Gate A's checklist has no slot-token item, so every delegated prompt can come back in the rejected form and the failure only surfaces at the step-7 sheet lint.
- **trigger**: Any pipeline-mode delegation where the specialist follows its own mapping table.
- **proposed_fix**: Add a pipeline-mode row to the mapping table stating that `style-lock` emits the inherited `{style:…}` slot rather than a literal code, and add the corresponding item to Gate A's checklist.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-18 · shorts-assembly asks the voiceover brief for two fields it does not emit
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-assembly/SKILL.md:18`, `.claude/skills/voiceover-brief/SKILL.md:89-105`, `.claude/skills/shorts-scripting/SKILL.md:180`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: "pacing wpm, take count" appear nowhere in `voiceover-brief`'s five output sections; wpm is actually a `shorts-scripting` field (`Total word count: ~N words (150–170 wpm)`), and no skill emits a take count at all. The fallback clause ("or at minimum the VO's target wpm and total duration") sends the operator back to the script, which C-03 says may not be in scope.
- **trigger**: Building an edit plan from the voiceover brief alone.
- **proposed_fix**: Restate input 2 as the fields the brief actually carries (voice pick, per-beat settings, TTS-reformatted script, LUFS/ducking targets) and source wpm/duration from the script explicitly.
- **fix_cost**: S
- **depends_on_finding**: [C-03]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-19 · elevenlabs-audio declares shorts-assembly downstream; shorts-assembly never names its spec as an input
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/elevenlabs-audio/SKILL.md:33`, `.claude/skills/elevenlabs-audio/SKILL.md:224-226`, `.claude/skills/shorts-assembly/SKILL.md:16-25`, `.claude/skills/elevenlabs-music/SKILL.md:180-183`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: `elevenlabs-music` gets an explicit landing zone — its MIX HANDOFF is named in `shorts-assembly`'s input 4. `elevenlabs-audio` has no equivalent: `shorts-assembly` lists the voiceover *brief*, never the AUDIO PRODUCTION SPEC, and the spec's `NEXT` line says only "the downstream handoff" without naming it. The rendered VO's filename, take structure and chunk seams reach the edit plan by no declared route.
- **trigger**: Assembling a Short whose VO was generated via `elevenlabs-audio`.
- **proposed_fix**: Mirror the music pattern — add an ASSET HANDOFF section to `elevenlabs-audio`'s output contract (asset filename, chunk/seam list, LUFS restated) and name it in `shorts-assembly`'s input list.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-20 · The three specialists emit no file artifact and carry no File I/O contract
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/elevenlabs-audio/SKILL.md:187-226`, `.claude/skills/elevenlabs-music/SKILL.md:154-195`, `.claude/skills/midjourney-prompting/SKILL.md:208-241`, `.claude/skills/shorts-assembly/SKILL.md:88-140`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: All nine pipeline skills carry a "## File I/O contract" section, a resolver `--kind`, and frontmatter. The three specialists carry none, so their specs exist only in a chat transcript. `elevenlabs-music`'s MIX HANDOFF is explicitly designed so "`shorts-assembly` has everything without a lookup" — but there is nothing to look up, and `shorts-assembly`'s standalone resolve step has no `--kind` for it. Every specialist output is lost between sessions.
- **trigger**: Resuming a Short in a new session after the specialist stage ran.
- **proposed_fix**: Give the two ElevenLabs specialists a resolver kind and a File I/O section (`midjourney-prompting` legitimately has none — its output is absorbed into the prompt sheet), or state explicitly in each that its output is transcript-only and must be pasted into the downstream artifact.
- **fix_cost**: M
- **depends_on_finding**: [C-19]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-21 · shorts-assembly's output has no stated structure — only "the same way references/worked-example.md is"
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-assembly/SKILL.md:49-55`, `.claude/skills/shorts-assembly/SKILL.md:70`, `.claude/skills/social-repurpose/SKILL.md:12-13`, `.claude/skills/social-repurpose/SKILL.md:128-131`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: Every other pipeline skill states an output shape inline (a template, a `=== BLOCK ===` contract, or named `##` sections). `shorts-assembly` states only a six-item topic list and defers layout to an example file, so the artifact `social-repurpose` must parse has no named sections. `social-repurpose` looks for "a constraints that survive to publish line" in it (`:17`) with no guarantee of where — or whether — that line appears.
- **trigger**: `social-repurpose` reading an assembly plan produced by a different session.
- **proposed_fix**: Add an explicit output contract to `shorts-assembly` with named headings for the six deliverables plus a constraints-passthrough section, mirroring `music-brief`'s five-section contract.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-22 · Artifact `--kind` values mix stage names, skill names and artifact nouns; app paths add a fourth vocabulary
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-ideation/SKILL.md:223`, `.claude/skills/shorts-scripting/SKILL.md:270`, `.claude/skills/voiceover-brief/SKILL.md:142`, `.claude/skills/music-brief/SKILL.md:110`, `.claude/skills/visual-prompts/SKILL.md:379`, `.claude/skills/social-repurpose/SKILL.md:135`, `.claude/skills/shorts-assembly/SKILL.md:99`
- **component**: skills
- **failure_mode**: loud
- **blast_radius**: See the Q5 table. The resolver matches filenames literally, so a single wrong guess (`--kind repurpose`, `--kind voiceover`, `--kind music-brief`) returns `NONE\t0` and exit 1 — which every skill's File I/O step documents as the benign "no file yet" case. A vocabulary slip therefore reads as "upstream hasn't run", not as an error.
- **trigger**: Any skill or operator inferring a `--kind` from the stage id or the skill name instead of copying the literal string.
- **proposed_fix**: Pick one vocabulary (the `pipeline.yaml` stage ids are the natural choice, since the app directories already use them) and make every `--kind`, `stage:` and pointer-field name derive from it mechanically.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-23 · The grounding brief has no `kind:`, no `stage:` and no resolver kind, unlike every other artifact
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/rgs-grounding/SKILL.md:85-95`, `.claude/skills/rgs-grounding/SKILL.md:149`, `.claude/skills/rgs-grounding/SKILL.md:154`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: Every stage artifact carries `kind:`, `slug:`, `stage:` and `version:`; the grounding brief carries `topic:` and `version:` only. Its filename therefore occupies the *un-suffixed* namespace — `<date>-<slug>.md` — the same pattern a kindless call resolves. Downstream `grounding:` pointer fields hold a bare path with no machine-readable kind to validate against, and the artifact cannot be located by kind at all.
- **trigger**: Any downstream skill trying to confirm that a `grounding:` pointer actually names a grounding brief.
- **proposed_fix**: Add `kind: grounding`, `slug:` and `stage: 00-grounding` to the brief template and give the resolver call an explicit `--kind grounding`, accepting the one-time filename migration.
- **fix_cost**: M
- **depends_on_finding**: [C-22]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-24 · voiceover-brief reads the script "in full" and chases unbounded upstream pointers it does not need
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/voiceover-brief/SKILL.md:58`, `.claude/skills/voiceover-brief/SKILL.md:136-138`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: The skill needs the VO lines, the beat timings and the tone shifts. It is instructed to read the whole script *and* to "follow its `concept_brief:`/`grounding:` pointer fields to resolve anything further upstream" — an unbounded transitive read of the concept brief and the grounding brief, neither of which informs a voice pick that is already pinned (`:62-65`). This is the largest single context over-read in the set.
- **trigger**: Every standalone voiceover-brief run.
- **proposed_fix**: Narrow step 1 to the beat table (VO line, timestamp, word count) and delete the transitive pointer-chase, replacing it with a conditional: follow `grounding:` only if the script's Delivery notes carry a constraints line.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-25 · music-brief reads the full script and the full voiceover brief for two fields
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/music-brief/SKILL.md:44`, `.claude/skills/music-brief/SKILL.md:46`, `.claude/skills/music-brief/SKILL.md:103-105`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: The skill's own description says it "is deliberately thin: it owns the bed's arc and nothing else" (`:13-14`), and its two inputs are beat boundaries in seconds and the tone-per-beat call. It nonetheless resolves and reads both artifacts whole.
- **trigger**: Every standalone music-brief run.
- **proposed_fix**: Instruct reading only the script's beat/timestamp table and the voiceover brief's tone-per-beat section (once C-01 gives that section a name).
- **fix_cost**: S
- **depends_on_finding**: [C-01]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-26 · shorts-styleboard's step 1 names three input sources; its File I/O contract can locate one
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-styleboard/SKILL.md:51-53`, `.claude/skills/shorts-styleboard/SKILL.md:116-120`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: Step 1 requires checking "the incoming script, the concept brief, the grounding artifact — before picking a sport yourself", and the sport is load-bearing (`register_a_rationale` must tie it to the claim's evidence). The File I/O contract resolves only `--kind script`, with no step for the concept brief or the grounding artifact, so in practice the skill picks the sport itself while believing it checked upstream.
- **trigger**: Any standalone styleboard run where an upstream artifact already named the sport.
- **proposed_fix**: Add resolve steps for `--kind concept-brief` and the grounding brief (via the script's `concept_brief:`/`grounding:` frontmatter) to the File I/O contract, or reduce step 1 to the sources it can actually reach.
- **fix_cost**: S
- **depends_on_finding**: [C-23]
- **owner_task**: T8
- **detected_by**: manual-trace

### C-27 · shorts-styleboard instructs writing into visual-prompts' artifact
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-styleboard/SKILL.md:54-55`, `.claude/skills/shorts-styleboard/SKILL.md:13-14`, `.claude/skills/visual-prompts/SKILL.md:99-100`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: "Name the choice at the top of the prompt sheet, not buried in the world-lock block alone" tells the styleboard to write into the prompt sheet — an artifact it does not produce and whose byte-level format is Gate-C-linted. The instruction is a leftover from before the split (the same paragraph's rules "moved here from `visual-prompts`", `:19-22`), and it contradicts `visual-prompts`' "do not re-emit the WORLD LOCK block — one home, no sync rule needed".
- **trigger**: Following step 1 literally while emitting a styleboard.
- **proposed_fix**: Retarget the sentence at the styleboard artifact's own top-level summary, or move the requirement into `visual-prompts` as a sheet field it fills from the inherited world lock.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-28 · visual-prompts still claims ownership of the register system shorts-styleboard now owns
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/SKILL.md:53-54`, `.claude/skills/visual-prompts/SKILL.md:31-33`, `.claude/skills/visual-prompts/SKILL.md:337-344`, `.claude/skills/shorts-styleboard/SKILL.md:19-22`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: `visual-prompts` says "The register system (`references/visual-registers.md`) ... are **this skill's own operational design**" two paragraphs after listing "locking the world, picking the sport ... all `shorts-styleboard`". `shorts-styleboard` says the same rules "moved here from `visual-prompts` unchanged". Both skills ship a `references/visual-registers.md`, so the register contract has two homes and the ownership claim points at the wrong one. (The duplicate file's *contents* are T9's — this finding is the SKILL.md ownership claim only.)
- **trigger**: Editing the register contract, or asking either skill who owns it.
- **proposed_fix**: Rewrite `visual-prompts`' ownership paragraphs to credit `shorts-styleboard` for the register system and keep the claim only for the arc discipline and the sheet format; hand the duplicate-file question to T9.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-29 · Four skill descriptions state no negative scope
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-ideation/SKILL.md:3`, `.claude/skills/shorts-scripting/SKILL.md:3`, `.claude/skills/shorts-assembly/SKILL.md:3`, `.claude/skills/social-repurpose/SKILL.md:3`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: Nine of thirteen descriptions carry an explicit "Do not use this for X" clause; these four do not, even though all four have a body section stating exactly that boundary (`shorts-ideation:58-72`, `shorts-scripting:213-223`, `shorts-assembly:8`, `social-repurpose:15-16`). The trigger text is what routing matches on, so the boundary is invisible at selection time — notably `shorts-scripting`, whose description invites "punch up an existing rough Short script", overlapping `shorts-ideation`'s angle work.
- **trigger**: Skill selection on an ambiguous request.
- **proposed_fix**: Append the body's existing boundary sentence to each of the four descriptions.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-30 · visual-prompts' optional-input section points at "step 4's prompt anatomy", which step 4 disclaims
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/SKILL.md:63-65`, `.claude/skills/visual-prompts/SKILL.md:154`, `.claude/skills/visual-prompts/SKILL.md:22-26`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: "fold it into step 2's still-count decision and step 4's prompt anatomy" describes step 4 as owning prompt anatomy; step 4 is the delegation step and the Pipeline-position bullet says "Do not write Midjourney prompts or pick parameters here". A reader following the pointer writes prompt body content in the wrong skill.
- **trigger**: Handling a grounding artifact's motif cue.
- **proposed_fix**: Reword to "step 4's delegation block for that beat" — the motif belongs in the `subject:` field handed down, not in prompt anatomy.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-31 · visual-prompts' VALIDATION block mislabels Gate B as an "upstream visual-quality check"
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/SKILL.md:289`, `.claude/skills/midjourney-prompting/SKILL.md:193`, `.claude/skills/midjourney-prompting/SKILL.md:195-196`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: Gate B is `midjourney-prompting`'s adversarial art-direction review, fires at `production` stage only, and is *downstream* of the delegation, not upstream. The sheet's own validation line describes it wrongly, so a reader cannot tell what "if applicable" means or who runs it.
- **trigger**: Filling in the sheet's VALIDATION block.
- **proposed_fix**: Relabel to "Gate B (midjourney-prompting adversarial art direction — production-stage prompts only)".
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-32 · rgs-grounding's citation index points at an unnamed "implementation plan"
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/rgs-grounding/SKILL.md:178`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: "the curated matches (Task 2 of the implementation plan; ~18–24 rows...)" cites a build-time work item, not a source. The plan is presumably `docs/superpowers/plans/2026-07-25-raisinggoodsports-grounding-skills.md`, but the reference names no path, so the row-count claim is unverifiable from the skill.
- **trigger**: Auditing where the pairing map came from.
- **proposed_fix**: Replace with the plan's path, or drop the parenthetical and keep the row-count description only.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: grep-sweep

### C-33 · rgs-pairing-review is an orphan in both directions
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/rgs-pairing-review/SKILL.md:8-12`, `.claude/skills/rgs-grounding/SKILL.md:176-187`, `.claude/skills/rgs-grounding/SKILL.md:22-29`
- **component**: skills
- **failure_mode**: coverage-gap
- **blast_radius**: Nothing feeds it and it feeds no skill — it mutates `rgs-grounding/references/pairing-map.md` via a human-approved edit. `rgs-grounding` describes the map as "the only trusted set of matches" and never mentions the skill that maintains it, so an operator hitting an uncovered topic reaches for the live-glob fallback rather than a review pass. Neither SKILL.md states that this skill sits outside the staged pipeline.
- **trigger**: A grounding run that finds no fitting map row.
- **proposed_fix**: Add a one-line pointer from `rgs-grounding`'s map section to `rgs-pairing-review`, and a line in `rgs-pairing-review` stating it is a maintenance skill outside the staged pipeline.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-34 · `docs/style-library.md` is cross-skill mutable state with no declared owner in any I/O contract
- **severity**: S3
- **confidence**: probable
- **evidence**: `.claude/skills/shorts-styleboard/SKILL.md:91`, `.claude/skills/shorts-assembly/SKILL.md:37`, `.claude/skills/midjourney-prompting/SKILL.md:145-149`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: `shorts-styleboard` reads it to bind slots, `shorts-assembly` reads its `Entries` section to resolve slot tokens to real `--sref` codes at paste time, and `midjourney-prompting` **writes** harvested codes into it. Three skills share a mutable registry that appears in no skill's declared inputs or outputs and has no version/staleness rule, unlike every `rgs-briefs/` artifact. A code harvested after a styleboard was written changes what an already-approved sheet resolves to.
- **trigger**: A style-discovery run between styleboard emission and asset rendering.
- **proposed_fix**: Name `docs/style-library.md` as a declared read (and, for `midjourney-prompting`, write) in the affected skills' I/O sections, and state whether a styleboard pins the entry it bound or re-resolves at paste time.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T8
- **detected_by**: manual-trace

### C-35 · shorts-assembly's description implies the script alone is sufficient input
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/shorts-assembly/SKILL.md:3`, `.claude/skills/shorts-assembly/SKILL.md:16-25`, `.claude/skills/shorts-assembly/SKILL.md:29`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: "Use this whenever the user has a finished Short script (from shorts-scripting) and wants to know how to actually cut it together" names one prerequisite; the body requires three and hard-blocks on any of them being absent. The description also omits `music-brief` entirely despite input 4 depending on it. The skill triggers on script-only requests and then immediately refuses.
- **trigger**: "build me an edit plan" with only a script in hand.
- **proposed_fix**: State the three required inputs (and the optional fourth) in the description's trigger sentence.
- **fix_cost**: S
- **depends_on_finding**: [C-03]
- **owner_task**: T8
- **detected_by**: manual-trace

## T9 — Reference integrity & provenance markers

Scope: every `references/**` file under `.claude/skills/` (64 files across 13 skills), `docs/style-library.md`, `rgs-briefs/` (39 files), and provenance-marker defects wherever they appear — including inside `SKILL.md` bodies, whose *contract* findings belong to T8 and whose *marker* findings are filed here. `tests/test_skill_provenance.py` was read only to answer "what does it actually assert" (T14 owns the test suite otherwise). Everything below is measured mechanically over the tree at `claude/pipeline-audit-review-4dd767`; the scan definitions are stated inline so each number is reproducible. 16 findings, C-40…C-55. Documentation-only: nothing was changed.

### Q1 — Broken `references/<file>.md` citations

**Method.** Every occurrence of the literal token `references/<name>.md` inside any `.md` file under `.claude/skills/`. A citation is **qualified** when a skill name immediately precedes it (`voiceover-brief/references/x.md`, `.claude/skills/voiceover-brief/references/x.md`) and **bare** otherwise — a bare citation can only mean "in this skill", because that is the only path a reader of that file can resolve without guessing. **206 citations total: 190 bare, 16 qualified. 6 do not resolve — all 6 bare.** All 16 qualified citations resolve.

**The 6 unresolvable citations (the whole set):**

| citing file:line | cited path | resolves? | verdict |
|---|---|---|---|
| `.claude/skills/music-brief/SKILL.md:25` | `references/production-and-loudness.md` | **NO** — file exists only in `voiceover-brief` | SEED-11. Sentence names `voiceover-brief` on the prior line, so prose disambiguates; the path does not. `music-brief` has exactly one reference file (`bed-arc.md`). |
| `.claude/skills/elevenlabs-audio/SKILL.md:32` | `references/production-and-loudness.md` | **NO** — same target | SEED-11. Same shape. |
| `.claude/skills/elevenlabs-music/SKILL.md:32` | `references/production-and-loudness.md` | **NO** — same target | SEED-11. Same shape; the line is byte-identical to `elevenlabs-audio/SKILL.md:32`. |
| `.claude/skills/rgs-pairing-review/SKILL.md:49` | `references/thinker-corpus-protocol.md` | **NO** — file exists only in `rgs-grounding` | **New.** `rgs-pairing-review` has **no `references/` directory at all**, so every bare `references/…` in it is unresolvable by construction. |
| `.claude/skills/shorts-scripting/SKILL.md:76` | `references/scripting-beat-mapping.md` | **NO** — file exists only in `rgs-grounding` | **New.** Qualifier `` `rgs-grounding`'s `` sits at the end of line 75; the path token wraps onto line 76. |
| `.claude/skills/visual-prompts/references/prompt-sheet-format.md:120` | `references/prompt-architecture.md` | **NO** — file exists only in `midjourney-prompting` | **New.** Qualifier `` `midjourney-prompting`'s own `` ends line 119. |

**The 16 qualified citations (all resolve):** `elevenlabs-audio/references/voice-profiles.md:4,28,44,58` → `voiceover-brief/references/{voice-selection,channel-voice}.md`; `midjourney-prompting/SKILL.md:36,250` → `visual-prompts/references/image-to-video.md`; `music-brief/references/bed-arc.md:7` → `voiceover-brief/references/production-and-loudness.md`; `rgs-pairing-review/SKILL.md:11,25` → `rgs-grounding/references/pairing-map.md`; `shorts-styleboard/references/visual-registers.md:11,11,12` → `midjourney-prompting/references/{prompt-architecture,v82-model-delta}.md` and `visual-prompts/references/faceless-pacing-rules.md`; `visual-prompts/references/image-to-video.md:46` → `midjourney-prompting/references/parameters.md`; `visual-prompts/references/prompt-sheet-format.md:38` → `shorts-styleboard/references/styleboard-format.md`; `visual-prompts/references/visual-registers.md:6` → `shorts-styleboard/references/visual-registers.md`; `voiceover-brief/references/channel-voice.md:81` → `elevenlabs-audio/references/voice-profiles.md`.

**The 184 resolving bare citations, by citing file** (bare-OK / qualified-OK / broken):

| citing file | bare→resolves | qualified→resolves | broken |
|---|---|---|---|
| `.claude/skills/elevenlabs-audio/SKILL.md` | 19 | 0 | **1** |
| `.claude/skills/elevenlabs-audio/references/voice-profiles.md` | 0 | 4 | 0 |
| `.claude/skills/elevenlabs-music/SKILL.md` | 10 | 0 | **1** |
| `.claude/skills/midjourney-prompting/SKILL.md` | 15 | 2 | 0 |
| `.claude/skills/music-brief/SKILL.md` | 3 | 0 | **1** |
| `.claude/skills/music-brief/references/bed-arc.md` | 0 | 1 | 0 |
| `.claude/skills/rgs-grounding/SKILL.md` | 20 | 0 | 0 |
| `.claude/skills/rgs-grounding/references/pairing-map.md` | 1 | 0 | 0 |
| `.claude/skills/rgs-grounding/references/research-corpus-protocol.md` | 2 | 0 | 0 |
| `.claude/skills/rgs-grounding/references/thinker-corpus-protocol.md` | 1 | 0 | 0 |
| `.claude/skills/rgs-pairing-review/SKILL.md` | 0 | 2 | **1** |
| `.claude/skills/shorts-assembly/SKILL.md` | 5 | 0 | 0 |
| `.claude/skills/shorts-ideation/SKILL.md` | 10 | 0 | 0 |
| `.claude/skills/shorts-scripting/SKILL.md` | 23 | 0 | **1** |
| `.claude/skills/shorts-scripting/references/read-aloud-gates.md` | 3 | 0 | 0 |
| `.claude/skills/shorts-styleboard/SKILL.md` | 6 | 0 | 0 |
| `.claude/skills/shorts-styleboard/references/visual-registers.md` | 0 | 3 | 0 |
| `.claude/skills/social-repurpose/SKILL.md` | 10 | 0 | 0 |
| `.claude/skills/visual-prompts/SKILL.md` | 24 | 0 | 0 |
| `.claude/skills/visual-prompts/references/image-to-video.md` | 0 | 1 | 0 |
| `.claude/skills/visual-prompts/references/prompt-sheet-format.md` | 1 | 1 | **1** |
| `.claude/skills/visual-prompts/references/visual-registers.md` | 0 | 1 | 0 |
| `.claude/skills/visual-prompts/references/worked-example.md` | 13 | 0 | 0 |
| `.claude/skills/voiceover-brief/SKILL.md` | 14 | 0 | 0 |
| `.claude/skills/voiceover-brief/references/channel-voice.md` | 4 | 1 | 0 |
| **TOTAL** | **184** | **16** | **6** |

**One citation class the token scan misses, and it is the worst one.** Six further citations name the bare *filename* without the `references/` prefix (`visual-registers.md §2`) — `visual-prompts/references/prompt-sheet-format.md:3,182` and `visual-prompts/references/visual-arc.md:3,50,120,164`. Combined with the eight `references/visual-registers.md` citations inside `visual-prompts`, **14 citations point at `visual-prompts/references/visual-registers.md`, which is a 13-line tombstone with zero `##` sections**; 10 of the 14 name a specific `§2`/`§3–§5`/`§6`/`§8` that exists only in the `shorts-styleboard` copy. These *resolve* — a file of that name exists — which is why no linter would catch them. See C-41.

### Q2 — Orphaned reference files

**None.** All 64 reference files are cited at least once by their own `SKILL.md`. Twelve are additionally cited by a sibling skill (`elevenlabs-audio/voice-profiles.md`, `midjourney-prompting/{parameters,prompt-architecture,v82-model-delta}.md`, `rgs-grounding/pairing-map.md`, `shorts-styleboard/{styleboard-format,visual-registers}.md`, `visual-prompts/{faceless-pacing-rules,image-to-video}.md`, `voiceover-brief/{channel-voice,production-and-loudness,voice-selection}.md`). `rgs-pairing-review` is the only skill with no `references/` directory.

Four filenames are **reused across skills**, which is what makes bare citations fragile: `worked-example.md` (9 skills), `validation-gates.md` (3), `api-payload.md` (2), `visual-registers.md` (2). See C-54.

### Q3 — Provenance census

**Definition of "normative line" (reproducible).** A **normative block** is a markdown list item (`- `, `* `, `+ `, or `N. `) whose visible content begins with a bold span (`**…**`), optionally preceded by an inline-code span — i.e. a bolded directive bullet. The unit is the *whole block*: the bullet's first line plus every following line that is non-blank, is not itself a bullet, is not a heading, and is not a table row. Fenced code is excluded entirely. A block is **marked** if any of `[C]` `[I]` `[T]` `[P]` `[T-unverified]` appears anywhere in it. Marker columns can overlap (a block carrying both `[C]` and `[T]` counts in both), so `C+I+T+P+TU+UNMARKED` may exceed `total`. **Table rows and prose paragraphs are excluded** — that is a deliberate under-count and it matters for `visual-prompts/references/visual-arc.md`, where the Gate C C1–C20 rules are table rows carrying `[I]` and are therefore invisible to this census.

**Calibration against SEED-12.** SEED-12's "96 of 119 unmarked" is the *first-physical-line* count. Reference files wrap their bullets and routinely put the `[C] (Channel, id)` citation on a continuation line — `shorts-scripting/references/retention-loops-and-structure.md:9-16` is typical — so a first-line count overstates unmarked reference bullets by roughly 3×. Block-level, `SKILL.md` bodies are **78 / 117 unmarked (67%)**, not 96/119. The direction of SEED-12 is unchanged; the magnitude for reference files is not.

| Skill | SKILL.md total | [C] | [I] | [T] | [P] | [T-unv] | UNMARKED | % unm | REF total | [C] | [I] | [T] | [P] | [T-unv] | UNMARKED | % unm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `elevenlabs-audio` | 11 | 1 | 1 | 3 | 0 | 1 | 8 | 73% | 41 | 0 | 4 | 13 | 0 | 0 | 25 | 61% |
| `elevenlabs-music` | 5 | 1 | 1 | 1 | 0 | 1 | 4 | 80% | 23 | 1 | 3 | 8 | 0 | 5 | 11 | 48% |
| `midjourney-prompting` | 13 | 4 | 3 | 1 | 0 | 2 | 7 | 54% | 47 | 2 | 3 | 20 | 0 | 0 | 26 | 55% |
| `music-brief` | 8 | 2 | 2 | 1 | 0 | 0 | 3 | 38% | 4 | 0 | 4 | 0 | 0 | 0 | **0** | **0%** |
| `rgs-grounding` | 0 | — | — | — | — | — | 0 | — | 116 | 0 | 1 | 0 | 0 | 0 | **115** | **99%** |
| `rgs-pairing-review` | 3 | 0 | 0 | 0 | 0 | 0 | 3 | **100%** | 0 | — | — | — | — | — | — | — |
| `shorts-assembly` | 5 | 1 | 0 | 0 | 0 | 0 | 4 | 80% | 45 | 30 | 7 | 9 | 0 | 0 | 6 | 13% |
| `shorts-ideation` | 10 | 1 | 1 | 1 | 0 | 0 | 7 | 70% | 45 | 41 | 0 | 0 | 0 | 0 | 4 | **9%** |
| `shorts-scripting` | 23 | 4 | 2 | 1 | 0 | 0 | 17 | 74% | 90 | 70 | 11 | 0 | 0 | 0 | 14 | 16% |
| `shorts-styleboard` | 3 | 0 | 1 | 0 | 0 | 0 | 2 | 67% | 13 | 0 | 10 | 3 | 0 | 0 | **0** | **0%** |
| `social-repurpose` | 11 | 1 | 1 | 1 | 0 | 0 | 8 | 73% | 33 | 25 | 3 | 0 | 0 | 0 | 5 | 15% |
| `visual-prompts` | 13 | 3 | 5 | 0 | 0 | 0 | 6 | 46% | 65 | 18 | 8 | 0 | 0 | 0 | 39 | 60% |
| `voiceover-brief` | 12 | 1 | 1 | 1 | 0 | 0 | 9 | 75% | 16 | 0 | 3 | 8 | 0 | 0 | 6 | 38% |
| **TOTAL** | **117** | **19** | **18** | **10** | **0** | **4** | **78** | **67%** | **538** | **187** | **57** | **61** | **0** | **5** | **251** | **47%** |

**Grand total: 655 normative blocks, 329 unmarked — 50%.**

Worst individual files (unmarked / total): `rgs-grounding/references/pairing-map.md` 95/95 · `visual-prompts/references/visual-arc.md` 21/22 · `visual-prompts/references/worked-example.md` 14/15 · `shorts-scripting/references/worked-example.md` 9/10 · `rgs-grounding/references/worked-example.md` 8/8 · `midjourney-prompting/references/worked-example.md` 7/7 · `elevenlabs-audio/references/worked-example.md` 6/6 · `social-repurpose/references/worked-example.md` 5/5 · `rgs-grounding/references/safety-sensitive-handling.md` 5/5 · `shorts-scripting/references/beat-timing-model.md` 3/3 · `rgs-pairing-review/SKILL.md` 3/3.

Perfect files (0 unmarked): `music-brief/references/bed-arc.md` (4/4 `[I]`), `shorts-styleboard/references/visual-registers.md` (13/13 — the one file the test suite guards).

**Honesty check on the unmarked count.** Only **4** of the 329 unmarked blocks carry a well-formed `(Channel, video_id)` despite having no `[C]` token (`voiceover-brief/references/voice-selection.md` ×2, `shorts-ideation/references/angle-selection.md` ×1, `voiceover-brief/references/production-and-loudness.md` ×1). The other 325 carry neither a marker nor a citation. The census is not a formatting artifact.

### Q4 — Marker correctness, not just presence

**`[C]` citation form.** 319 normative blocks contain a `[C]`. **33 carry no `(Channel, video_id)` anywhere in the block.** Roughly half of those 33 are legitimate meta-mentions of the marker itself (`elevenlabs-music/SKILL.md:49` "the corpus contains zero findings on AI music generation"; the `references/validation-gates.md:18` "why the checklists carry no markers" note in `elevenlabs-audio` and `elevenlabs-music`; `shorts-ideation/SKILL.md:187,190,192,194` index entries counting `[C]` rules; `shorts-scripting/SKILL.md:42,240`). The remainder are genuine uncited normative `[C]` claims, concentrated in three places:

- `midjourney-prompting/references/prompt-architecture.md:116,117,119` — three stylize-band rows asserting "the corpus sweet spot", "Corpus: raise toward 300+", "Corpus's documented remedy", each `[C]` with no citation. The same bands *are* cited at `midjourney-prompting/references/parameters.md:36`, so the fix is mechanical.
- `midjourney-prompting/references/parameters.md:43` — the `--iw` row is `[C][T]` with neither a channel nor a verification date.
- `visual-prompts/references/image-to-video.md` — see below; this file is the outlier.

**Channels cited.** Every named channel across all 13 skills resolves to the 14-channel source list in `docs/README.md:64-70` (vidIQ 43, Kallaway 34, Romayroh 34, Nate Black 28, Nick Nimmin 24, One Person Business 22, Make Money Matt 20, Future Tech Pilot 19, Dan the creator 19, Tao Prompts 14, Roberto Blake 13, Jenny Hoyos 13, Tokenized AI 12, Wade McMaster 6). **No `[C]` in any skill cites a channel outside the 14.** In `rgs-briefs/`, the out-of-corpus channels (Wendover Productions, Chasing the Game, Better Sports Parents, TEDx Talks, Coach Beede, Joon Lee, HBO) appear **only** under `[REF]`, never `[C]` — the boundary is held. See Q8.

**But `visual-prompts/references/image-to-video.md` breaks the citation form entirely.** Of 40 `[C]` occurrences: 14 well-formed, 2 name a channel with no video id (`:69`, `:85` — `[C] (Tao Prompts)`), **6 cite bare video IDs with the channel dropped** (`:98` `(uCsc0ORcJDo, 4tpDAX23RL0, elCv87a4iK4)`, `:99`, `:100`, `:101`, `:102`, `:103`), and 18 are bare `[C]` with no parenthetical at all. `vezJXJGQMoY` is cited at `:102` as a bare id and at `visual-prompts/references/prompt-sheet-format.md:123` as `(Tokenized AI, vezJXJGQMoY)` — confirming these are video ids with the channel stripped, not channel names. See C-45.

**`[T]` verification dates.** Three distinct dates appear inline across the skills: `2026-07-23` (×9), `2026-07-26` (×112), `2026-08-06` (×5). None is *older* than the corresponding CLAUDE.md-stated date, so there is no stale-date defect. The defect is **absent** dates:

- **`elevenlabs-audio` carries 187 `[T]` lines across its 11 files and mentions a date 5 times total** (`SKILL.md:40,45`, `references/model-routing.md:17`, `references/validation-gates.md:21`, `references/worked-example.md:70`). Nine of its 11 files contain no date anywhere. See C-46.
- `voiceover-brief/references/{scripting-for-tts,worked-example,channel-voice}.md` carry 21 `[T]` lines and no date; the sibling files that do carry a header date (`voice-selection.md`, `settings-by-content-type.md`, `production-and-loudness.md`) date to `2026-07-23`, so a reader has no way to tell which snapshot the undated files belong to.
- `visual-prompts/references/image-to-video.md` (3 `[T]`), `shorts-scripting/SKILL.md` (3), `music-brief/SKILL.md` (2), `shorts-assembly/references/{caption-overlay-system,worked-example}.md` — all undated.
- `midjourney-prompting` is the counter-example and the model: 4 of its 7 reference files carry a header verification date and its `[T]` lines mostly carry `(verified 2026-07-26)` inline.

**`[T]` applied to something that is not a tool or policy fact.** `voiceover-brief/references/voice-selection.md:10-11` and `.claude/skills/voiceover-brief/references/channel-voice.md:16` both assert that a consistent voice "*is* the channel's identity `[T]` `[I]`". That is a branding/craft claim; no vendor or platform document states it. `voice-selection.md`'s own header dates its `[T]` facts to 2026-07-23, so the claim is presented as a dated, web-verified fact it never was. See C-47.

### Q5 — `[P]` discipline

`[P]` occurs 13 times repo-wide: 8 in `CLAUDE.md:47-141` (the rule itself), 5 inside skills. Of the 5:

| location | text | verdict |
|---|---|---|
| `voiceover-brief/references/channel-voice.md:8,9,10` | marker-legend definition | legend, not a claim — fine |
| `voiceover-brief/references/channel-voice.md:12` | heading `## The rule [P]` | scoping heading — fine, but see below |
| `voiceover-brief/references/channel-voice.md:27` | `Source: IVC — a clone of the operator's own voice [P]` | **the one genuine `[P]` fact.** A concrete operator choice, no craft claim attached. Correct. |
| `voiceover-brief/references/voice-selection.md:5` | marker-legend definition | legend — fine |
| `voiceover-brief/references/voice-selection.md:15` | "see `channel-voice.md` for the pinned `voice_id` and its recorded rationale `[P]`" | a *pointer* to the decision, not a claim deriving authority from it. Correct. |

**CLAUDE.md's count of exactly one `[P]` fact is accurate.** No `[P]` anywhere in the repo carries a craft rule, a recommendation, or a best practice. `[P]` discipline is the *strongest* provenance discipline in this repo.

One structural risk worth naming, which is the exact absorption CLAUDE.md warns about: the block under `## The rule [P]` at `channel-voice.md:14-17` opens with the concrete pin (legitimately `[P]`) and closes with *"The voice is the channel's identity `[T]` `[I]` and consistency across uploads is the point"* — a craft rationale sitting inside a `[P]`-titled section. It is separately marked, so it is not a `[P]` violation; but the `[T]` on it is wrong (C-47) and the placement is precisely the shape CLAUDE.md tells readers to distrust.

`docs/style-library.md:149` introduces a **sixth, undeclared marker** — `` `[run owner, 2026-08-08]` `` — for what is unambiguously a `[P]` decision (choosing an artistic rather than photorealistic Register A code). See C-49.

### Q6 — What `tests/test_skill_provenance.py` actually asserts

**Six test functions, all against one file: `.claude/skills/shorts-styleboard/references/visual-registers.md`** (plus one line-level assertion against `shorts-styleboard/SKILL.md`).

| # | assertion | what it covers |
|---|---|---|
| 1 | `:40` — the file exists | 1 file |
| 2 | `:45-48` — the file contains the literal `` `[I]` `` and the string `operational design` | substring presence, not per-line markers |
| 3 | `:55` — regex `corpus…is thin` matches somewhere | one disclaimer clause |
| 4 | `:70` — regex `says nothing about register systems` matches | one disclaimer clause |
| 5 | `:78-86` — **the only marker-enforcement test.** Splits on `## 3. Register A` / `## 5. PLATE` and requires every `- **` bullet in that slice to match `\[(?:C\|I\|T\|T-unverified)\]` | **13 bullets, file lines 42–72** |
| 6 | `:91` — `shorts-styleboard/SKILL.md` contains `own operational design \`[I]\`` | one substring |

**Quantitatively: 1 skill of 13 (7.7%). 1 reference file of 64 (1.6%). 13 normative blocks of 655 (2.0%).** The regex does not accept `[P]`, so a legitimately-`[P]`-marked bullet inside that slice would *fail* the test. The test never opens the other 12 skills, never opens `docs/style-library.md`, and never checks that a `[C]` carries a `(Channel, video_id)` — the marker-correctness dimension is entirely unguarded.

**Does it create a false sense of enforcement? Yes — but the file's own docstring is honest about it.** The docstring (`:1-7`) says it "Guards CLAUDE.md's anti-generic guarantee **at the two places it was actually broken**," which is an accurate description of a regression test for one historical incident. The false impression comes from the filename `test_skill_provenance.py` and from `CLAUDE.md`'s "Tests live in two suites… (the linters and skill provenance)" — both of which read as *the marker rule is tested*, when 98% of normative lines and 92% of skills are untested. See C-48.

### Q7 — `docs/style-library.md`

**Machine-parseable: yes, and the parser is deliberately narrow.** `scripts/lint_prompt_sheet.py:842-879` (`parse_style_library`) walks the file, tracks `## Entries` section membership and fenced-code state, takes `### <label>` headings that satisfy `VALID_SLOT_VALUE_RE`, and reads the **first** `code:` line inside each entry's fence. Both Gate C entry points use it — the CLI at `:1011` and `pipeline-app/pipeline_app/gates.py:105` — so the two agree by construction, and `:1012-1017` returns exit 2 rather than silently passing when the Library parses to zero entries. That is a well-built parser and a genuinely closed loop.

**Stability caveats.** The format depends on three unenforced conventions: (a) the section heading must be exactly `## Entries`; (b) every entry must be an `###` heading; (c) the `code:` line must be inside a fence. Nothing in the repo tests the *document* against its own declared "Entry format" spec (`:47-57`) — the tests exercise the parser against inline fixtures (`tests/test_lint_prompt_sheet.py:971-1105`), never against the real file.

**Entry consistency: one defect.** The declared Entry format (`:48-57`) lists eight fields: `brand`, `register`, `scope`, `mechanism`, `world`, `seed`, `code`, `harvested_at`. `rgs-sourceera-painterly-b` (`:87-104`) carries all eight. **`rgs-present-soccer-a` (`:126-138`) omits `seed:` entirely** — the very field the file describes as "the description the harvest session was seeded with", and the only record of how a channel-wide, durable code was produced. See C-50.

**Coverage: complete.** Both slot labels any artifact in the repo binds — `rgs-present-soccer-a` (23 occurrences) and `rgs-sourceera-painterly-b` (12) — have entries. **No orphan entries**: both entries are referenced. The other labels in the tree (`rgs-source-era-b`, `rgs-present-socer-a`, `rgs-unharvested-world-b`, `rgs-sourceera-painterly-c`, `rgs-not-in-the-library`, `rgs-not-in-any-library`) appear only in `tests/test_lint_prompt_sheet.py`, `pipeline-app/tests/test_gates.py`, and the rename note at `docs/style-library.md:111-116` — all deliberate.

**Provenance markers in this file are the weakest in the repo.** `:67` and `:70` carry bare `[T]` with no verification date (C-51), and `:149` uses the invented `[run owner, 2026-08-08]` marker (C-49). Both `scope: per-short` and the `mechanism` values `--p` / `--oref` / `none` are declared but unexercised — no entry uses them, and the codes-table variant described at `:59-60` has never been written.

### Q8 — `rgs-briefs/`

**Styleboard and music artifacts: zero.** 39 files; `ls | grep -E "styleboard|music"` returns nothing. Stage suffixes present: `concept-brief` (4), `script` (4), `voiceover-brief` (4), `visual-prompts` (5), `assembly` (5), `social-repurpose` (3), plus 8 grounding briefs and 3 run-level documents. **`shorts-styleboard` and `music-brief` have never produced a real artifact**, and `rgs-briefs/README.md:28-29` does not list `styleboard` or `music` in its enumeration of valid `<stage>` values either. See C-52.

**Frontmatter vs. `resolve_brief_version.py`: all 38 artifacts conform on the one field the script reads.** Every non-README file parses as a YAML mapping with an integer `version:` (`scripts/resolve_brief_version.py:51-53`). `README.md` has no frontmatter but never matches `_pattern()` at `:33-35`, so it is never parsed — not a defect. The `do-less-sold-as-win-more` chain (`version: 1 / 2 / 3`) resolves correctly.

**But 10 stage artifacts carry `version:` and nothing else.** `2026-07-25-let-kids-play-act{,-specialization}-{concept-brief,script,voiceover-brief,visual-prompts,assembly,social-repurpose}.md` have frontmatter consisting solely of `version: 1` — no `kind`, no `slug`, no `stage`, no `status`, no `date`. `rgs-briefs/README.md:136-139` records this as a deliberate 2026-07-28 backfill. The consequence is not recorded: `README.md:39-42` states that consumers **"MUST skip any file with a `kind:` field"** and that a `kind:`-bearing file "has no `thinker`/`concept`/`research_codes` to compare". These 10 files have **no `kind:` field and no grounding fields either** — they pass the skip filter *as grounding briefs* and then present nothing to compare. See C-53.

**One latent slug/kind collision.** `_pattern()` builds `^\d{4}-\d{2}-\d{2}-{slug}(-{kind})?(-v\d+)?\.md$`, so `--slug let-kids-play-act --kind specialization` matches `2026-07-25-let-kids-play-act-specialization.md`, which is a **grounding brief**, not a stage artifact of kind `specialization`. Nothing in the repo issues that query today; noted, not filed.

**`[REF]` discipline: held.** 108 `[REF]` occurrences across 11 files. `2026-07-28-rgs-debut-reference-scan.md:37-40` states the rule verbatim — `[REF]` findings "describe this ten-video cohort only… nothing marked `[REF]` may be upgraded to `[C]`: the two markers name different evidence bases." A programmatic check of every `(Channel, id)` citation in `rgs-briefs/` whose nearest preceding marker is `[C]` returns **zero** out-of-corpus channels. Every cohort channel (Wendover Productions, Chasing the Game, Better Sports Parents, TEDx Talks, Coach Beede, Joon Lee, HBO) appears exclusively under `[REF]`. **No `[REF]` marker is misused as corpus grounding.** The residual risk is shape, not practice: `[REF]` and `[C]` share the identical `(Channel, video_id)` citation form (`README.md:51-52`), so the marker token is the *only* thing distinguishing them, and a copy that drops the token silently converts a ten-video cohort observation into an apparent 420-video corpus finding.

---

### C-40 · Six bare `references/…` citations name a file absent from the citing skill
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/music-brief/SKILL.md:25`, `.claude/skills/elevenlabs-audio/SKILL.md:32`, `.claude/skills/elevenlabs-music/SKILL.md:32`, `.claude/skills/rgs-pairing-review/SKILL.md:49`, `.claude/skills/shorts-scripting/SKILL.md:76`, `.claude/skills/visual-prompts/references/prompt-sheet-format.md:120`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: A bare `references/x.md` can only mean "in this skill" — that is the only path a reader of that file can resolve. All six name files that live in a different skill. `rgs-pairing-review` has no `references/` directory at all, so its citation is unresolvable by construction. Three are SEED-11; three are new. In every case a nearby sentence names the owning skill, so a careful reader recovers — but an agent following the literal path finds nothing and either invents the content or drops the constraint (loudness/ducking deference, the thinker-corpus protocol, the beat-mapping rule, the prompt-architecture conflict).
- **trigger**: Any skill invocation that follows the cited path literally rather than reading the surrounding prose.
- **proposed_fix**: Qualify all six with the owning skill's name, matching the 16 citations that already do (`voiceover-brief/references/production-and-loudness.md`). Add a repo-root test that resolves every `references/…` token in `.claude/skills/**` against the citing skill's own directory unless a skill name precedes it.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-41 · `visual-prompts/references/visual-registers.md` is a tombstone; 14 citations resolve to a file with no sections
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/references/visual-registers.md:1-14`, `.claude/skills/visual-prompts/references/visual-arc.md:3,50,120,164`, `.claude/skills/visual-prompts/references/prompt-sheet-format.md:3,182`, `.claude/skills/visual-prompts/references/worked-example.md:6,65,74,116,214,238`, `.claude/skills/visual-prompts/SKILL.md:53,337`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: The file is a 13-line redirect with zero `##` headings. Fourteen citations inside `visual-prompts` point at it, and ten of those name a specific section (`§2` the vocabulary-disjunction rule, `§3–§5` the register contracts, `§6` the motif bridge, `§8` sport choice) that exists only in `shorts-styleboard/references/visual-registers.md` (149 lines). Every one of these citations *resolves* — a file of that name exists in the skill — so no existence check catches them. An agent that opens the cited file to find `§2`'s banned-vocabulary list finds a redirect instead and must make a second hop it was never told to make; the banned-vocabulary rule is exactly what Gate C's C10 enforces on the resulting prompts.
- **trigger**: `visual-prompts` reading its own `visual-arc.md:120` or `:164` to determine Register B's banned photographic vocabulary.
- **proposed_fix**: Rewrite the 14 citations to the qualified path `shorts-styleboard/references/visual-registers.md` (as `visual-registers.md:6` itself already does), or delete the tombstone so the citations fail loudly instead of misdirecting.
- **fix_cost**: S
- **depends_on_finding**: [C-40]
- **owner_task**: T9
- **detected_by**: manual-trace

### C-42 · Half of all normative bullets in the skill set carry no provenance marker
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/SKILL.md:1-400` (6/13 unmarked), `.claude/skills/shorts-scripting/SKILL.md:1-260` (17/23), `.claude/skills/visual-prompts/references/visual-arc.md:48-74` (21/22), `.claude/skills/shorts-scripting/references/beat-timing-model.md:1-40` (3/3), `CLAUDE.md:36-53`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: 329 of 655 normative blocks (50%) carry no `[C]`/`[I]`/`[T]`/`[P]`/`[T-unverified]`; 325 of those carry no corpus citation either. CLAUDE.md:53 states flatly that "a skill rule with no marker is a bug: it means something was invented instead of sourced." Under that rule half the skill set is presumed invented. The operator cannot tell, at the point of reading any given rule, whether it traces to the 420-video corpus, to verified vendor docs, or to nothing — which is the exact failure the anti-generic guarantee exists to prevent. Concentrations: every `worked-example.md` (see C-54), `visual-prompts/references/visual-arc.md`, `shorts-scripting/references/beat-timing-model.md`, and all 13 `SKILL.md` bodies except `music-brief`.
- **trigger**: Any skill invocation. It is the steady state, not an edge case.
- **proposed_fix**: Triage by file, not globally: `worked-example.md` files plausibly need a single header disclaimer ("illustrative application of the marked rules above") rather than per-line markers; format/taxonomy definitions like `visual-arc.md:48-74` need `[I]`; genuine craft rules need real markers or an honest gap flag. Then extend the provenance test to enforce the result per file.
- **fix_cost**: L
- **depends_on_finding**: [C-48]
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-43 · `rgs-grounding`'s 116 normative bullets carry no marker and CLAUDE.md never grants the exemption
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/rgs-grounding/SKILL.md:31-33`, `.claude/skills/rgs-grounding/references/pairing-map.md` (95/95 unmarked), `.claude/skills/rgs-grounding/references/worked-example.md` (8/8), `CLAUDE.md:130-146`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: `rgs-grounding/SKILL.md:32-33` declares its own vocabulary — `[THINKER: Name, Work, quotability]` and `[RESEARCH: Author Year, quality rating]` — and states these are used "not `[C]`/`[I]`/`[T]` (those denote the unrelated 14-channel headless-YouTube corpus)." That is a coherent design decision. But CLAUDE.md's Anti-generic guarantee scopes itself to "the eight pipeline skills" and "the tool-specialist skills" and never mentions the two RGS skills, so a reader applying CLAUDE.md literally reads 115 of 116 unmarked blocks as bugs. Five stray `[C]`/`[I]`/`[T]` tokens survive inside `rgs-grounding` despite the disclaimer, so the boundary is not clean either. `rgs-pairing-review/SKILL.md` carries three unmarked normative bullets and declares no vocabulary at all.
- **trigger**: Any audit or edit of `rgs-grounding` performed against CLAUDE.md's stated rule.
- **proposed_fix**: Add a sentence to CLAUDE.md's marker section naming the two RGS skills and their `[THINKER:]`/`[RESEARCH:]`/`[REF]`/`[B]`/`[C→I]` vocabulary, or state the exemption in each skill's own header. Remove or convert the five stray tokens.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-44 · 33 `[C]`-marked normative blocks carry no `(Channel, video_id)` citation
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/midjourney-prompting/references/prompt-architecture.md:116,117,119`, `.claude/skills/midjourney-prompting/references/parameters.md:43`, `.claude/skills/midjourney-prompting/references/v82-model-delta.md:39,41,43,44`, `.claude/skills/visual-prompts/references/image-to-video.md:27,60,63,74,105`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: CLAUDE.md:40-41 defines `[C]` as "extracted from a transcript, **cited `(Channel, video_id)`**" — the citation is constitutive, not decorative. 33 of 319 `[C]` blocks have none. About half are meta-mentions of the marker; the rest are live normative claims (`prompt-architecture.md:116-119`'s three stylize bands asserting "the corpus sweet spot", `parameters.md:43`'s `--iw` halving ladder marked `[C][T]` with neither a channel nor a date). An uncitable `[C]` is functionally identical to an unmarked line — it asserts corpus backing that cannot be checked — but it *passes* a marker-presence test, which is worse.
- **trigger**: Attempting to verify a `[C]` claim, or extending a skill by copying an existing `[C]` line's pattern.
- **proposed_fix**: Backfill the citations from the corpus (`prompt-architecture.md:116-119`'s bands are already cited at `parameters.md:36`), and strengthen the provenance test to require a `(Channel, id)` in the same block as any `[C]` on a normative line.
- **fix_cost**: M
- **depends_on_finding**: [C-48]
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-45 · `image-to-video.md` cites bare video IDs with the channel dropped, breaking traceability
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/references/image-to-video.md:98,99,100,101,102,103`, `.claude/skills/visual-prompts/references/image-to-video.md:69,85`, `.claude/skills/visual-prompts/references/prompt-sheet-format.md:123`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: The model-landscape table at `:96-103` is the file's most consequential content — it tiers Kling / Veo 3 / Seedance 2.0 / Google Omni / Runway Gen-2 / Sora 2 and drives which external i2v tool a Short's motion beats get spent on. Every row cites `[C] (uCsc0ORcJDo, 4tpDAX23RL0, elCv87a4iK4)` — bare video IDs with **no channel name**. `vezJXJGQMoY` is proven to be a Tokenized AI video by `prompt-sheet-format.md:123`, so these are ids, not channels. Two further lines (`:69`, `:85`) cite `(Tao Prompts)` with no id. Of 40 `[C]` occurrences in the file, 14 are well-formed, 8 are malformed, 18 are bare. Nothing in this file can be traced back to a transcript without first reverse-mapping ids to channels through `output/brand-intel/`, which is git-ignored.
- **trigger**: Re-verifying a model tier before spending on i2v renders, or refreshing the file after a model launch.
- **proposed_fix**: Restore the channel name to each of the 8 malformed citations by looking the ids up in the content index, and cite or downgrade the 18 bare `[C]`s.
- **fix_cost**: M
- **depends_on_finding**: [C-44]
- **owner_task**: T9
- **detected_by**: manual-trace

### C-46 · `elevenlabs-audio` carries 187 `[T]` lines and a verification date in only 2 of 11 files
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `.claude/skills/elevenlabs-audio/references/voice-settings.md` (26 `[T]`, 0 dates), `.claude/skills/elevenlabs-audio/references/control-surface.md` (25, 0), `.claude/skills/elevenlabs-audio/references/api-payload.md` (22, 0), `.claude/skills/elevenlabs-audio/references/model-routing.md:17`, `.claude/skills/elevenlabs-audio/SKILL.md:40,45`, `CLAUDE.md:113-116`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: CLAUDE.md defines `[T]` as "web-verified, **dated**" and instructs "re-verify before relying on it — these go stale fast." `elevenlabs-audio` has 187 `[T]` lines across 11 files and mentions a date 5 times; 9 of its 11 files contain no date anywhere. Its entire content — model routing, the full parameter surface, v3 stability modes, the audio-tag catalog, PLS dictionaries, credit arithmetic — is undated vendor fact. The two `SKILL.md` mentions of 2026-07-26 do not propagate into the reference files an agent actually reads at generation time. Because CLAUDE.md also records that the seeding runbook "was **wrong in eight places**", undated vendor claims here are precisely the class the project already knows to distrust. `voiceover-brief`'s three undated files and `visual-prompts/references/image-to-video.md` have the same defect at smaller scale.
- **trigger**: Any ElevenLabs API or pricing change after 2026-07-26 — nothing in the affected files signals which snapshot they belong to.
- **proposed_fix**: Add a dated verification header to every reference file carrying `[T]` lines, matching `midjourney-prompting/references/{parameters,render-economics,style-systems,v82-model-delta}.md`, and assert its presence in the provenance test.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-47 · `[T]` applied to a branding assertion that no vendor or platform document states
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/voiceover-brief/references/voice-selection.md:10-12`, `.claude/skills/voiceover-brief/references/channel-voice.md:14-17`, `.claude/skills/voiceover-brief/references/voice-selection.md:4-6`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: Both files assert that a consistent voice "*is* the channel's identity `[T]` `[I]`". `[T]` means "tool/policy fact, web-verified" — `voice-selection.md:5` dates the file's `[T]` claims to 2026-07-23 — but this is a branding judgment, not a fact ElevenLabs or YouTube publishes. It sits directly above the `[C]`-cited default-voice/shadowban finding, so the misapplied `[T]` borrows credibility from a genuinely-sourced neighbour. In `channel-voice.md:14-17` the same sentence closes a section headed `## The rule [P]`, putting an unsupported craft rationale inside the block CLAUDE.md:49-51 explicitly warns must not absorb adjacent authority.
- **trigger**: A brief citing "the channel's identity" as a verified platform fact when arguing against a per-Short voice change.
- **proposed_fix**: Drop the `[T]` and keep `[I]`, which is what the claim actually is; or cite the corpus line that supports voice consistency and mark it `[C]`.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: manual-trace

### C-48 · `test_skill_provenance.py` guards 13 bullets in 1 of 64 reference files, under a name that implies coverage
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `tests/test_skill_provenance.py:15`, `tests/test_skill_provenance.py:75-86`, `tests/test_skill_provenance.py:16`, `CLAUDE.md:236-241`
- **component**: skills
- **failure_mode**: coverage-gap
- **blast_radius**: The one marker-enforcement assertion (`:75-86`) slices `shorts-styleboard/references/visual-registers.md` between `## 3. Register A` and `## 5. PLATE` and requires a marker on every `- **` bullet there — 13 blocks of the 655 in the skill set (2.0%), in 1 of 64 reference files (1.6%), in 1 of 13 skills (7.7%). The other five tests are substring/regex checks on the same file. Nothing tests the other 12 skills, `docs/style-library.md`, `[C]` citation form, or `[T]` dating. The file's own docstring is honest — it calls itself a regression guard for "the two places it was actually broken" — but the filename and CLAUDE.md's "the linters and skill provenance" both read as *the marker rule is enforced*, and C-42/C-44/C-46 are the measurement of what that impression costs. Secondary defect: `MARKER_RE` at `:16` omits `[P]`, so a correctly-`[P]`-marked bullet inside the guarded slice would fail.
- **trigger**: Any edit that adds an unmarked normative line anywhere except `visual-registers.md` §3–§4. The suite passes.
- **proposed_fix**: Rename to reflect its regression-guard scope, and add a separate parametrized test that walks all 64 reference files and 13 `SKILL.md` bodies, starting with an explicit allowlist of currently-unmarked files so the gap is recorded rather than hidden, then shrinking the allowlist. Add `[P]` to `MARKER_RE`.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: manual-trace

### C-49 · `docs/style-library.md` invents a sixth provenance marker for a `[P]` decision
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `docs/style-library.md:149`, `docs/style-library.md:174`, `CLAUDE.md:44-53`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: `:149` marks the "artistic, not photographic" medium call as `` `[run owner, 2026-08-08]` `` — a marker that appears nowhere in CLAUDE.md's five-marker vocabulary. `:174`'s "**DECIDED 2026-08-08 (run owner)**" records another decision with no marker at all. Both are textbook `[P]`: concrete operator choices, no craft claim attached. Using ad-hoc syntax defeats the purpose `[P]` exists for — a grep for `[P]` to enumerate operator decisions returns one result repo-wide and misses these two. The medium call is load-bearing: it is what puts Register A's `--raw` requirement in tension with its own style code (`:163-182`).
- **trigger**: Enumerating operator decisions by marker, or auditing this file against CLAUDE.md.
- **proposed_fix**: Convert both to `[P]` with the date retained in prose, and add the marker legend to this file's header as `channel-voice.md:7-10` does.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-50 · `rgs-present-soccer-a` omits the `seed:` field its own Entry format declares
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `docs/style-library.md:48-57`, `docs/style-library.md:126-138`, `docs/style-library.md:87-104`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: The Entry format at `:48-57` lists eight fields; `rgs-sourceera-painterly-b` carries all eight, `rgs-present-soccer-a` carries seven — `seed:` is missing. That field is described as "the description the harvest session was seeded with" and is the only record of how a channel-wide, durable `--sref` code was produced. `:69-71` states that re-entering a Style Creator session stacks a new code rather than replacing the old one, so the seed is unrecoverable by re-running the session. If the Register A code ever needs re-harvesting — which `Open questions §1` at `:163-182` explicitly contemplates — there is no recorded input to re-harvest from. `parse_style_library` does not read `seed:`, so Gate C will never notice.
- **trigger**: Re-harvesting Register A after the `--raw` / stylize-band decision at `:174-178` is revisited.
- **proposed_fix**: Record the seed description used for the 2026-08-08 Register A harvest, or state explicitly that the code was supplied by the run owner without a seeded session.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: manual-trace

### C-51 · Two `[T]` lines in `docs/style-library.md` carry no verification date
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `docs/style-library.md:67`, `docs/style-library.md:69-71`, `CLAUDE.md:44-46`
- **component**: skills
- **failure_mode**: docs-drift
- **blast_radius**: `:67` ("Run previews in `--draft` to keep the session cheap `[T]`") and `:69-71` ("Re-entering a session stacks a new code rather than replacing the old one… `[T]`") are undated Midjourney platform claims. The second is the reason the file gives for never re-entering a locked session and for needing two separate sessions per register — an operationally binding rule resting on an unverifiable assertion. The equivalent claims in `midjourney-prompting/references/` carry `(verified 2026-07-26)`.
- **trigger**: Midjourney changing Style Creator session behavior; nothing signals when these were checked.
- **proposed_fix**: Date both against the `midjourney-prompting` verification pass, or cite the reference file that already carries the dated form.
- **fix_cost**: S
- **depends_on_finding**: [C-46]
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-52 · `rgs-briefs/` contains zero styleboard and zero music artifacts — two stages have never run for real
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `rgs-briefs/README.md:27-31`, `.claude/skills/shorts-styleboard/SKILL.md:15`, `.claude/skills/music-brief/SKILL.md:20-22`, `docs/style-library.md:36-43`
- **component**: skills
- **failure_mode**: coverage-gap
- **blast_radius**: 39 files in the ledger; the stage suffixes present are `concept-brief`, `script`, `voiceover-brief`, `visual-prompts`, `assembly`, `social-repurpose` — the exact six `rgs-briefs/README.md:28-29` enumerates. Neither `styleboard` nor `music` appears in the ledger or in that enumeration, so the two newest stages have never produced a versioned artifact and have no worked precedent outside their own `references/worked-example.md`. This is not theoretical: `docs/style-library.md:36-43` records that the do-less Short shipped against placeholder style codes and "no render in this Short ever had a style lock applied" — precisely because no styleboard artifact existed to bind them. `shorts-styleboard`'s output is what Gate C reads its `WORLD LOCK` from, so its untested state propagates into C6/C7/C10/C14/C18/C20.
- **trigger**: The first Short that actually runs styleboard or music-brief end to end.
- **proposed_fix**: Add `styleboard` and `music` to `rgs-briefs/README.md`'s `<stage>` enumeration, and produce one real artifact of each on the next Short so the stages have a worked precedent and the frontmatter contract is exercised.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-53 · Ten stage artifacts carry no `kind:` field, so `kind:`-skipping consumers read them as grounding briefs
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `rgs-briefs/2026-07-25-let-kids-play-act-script.md:1-3`, `rgs-briefs/2026-07-25-let-kids-play-act-specialization-assembly.md:1-3`, `rgs-briefs/README.md:33-42`, `rgs-briefs/README.md:136-139`, `.claude/skills/rgs-grounding/SKILL.md:47-52`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: Ten files — `2026-07-25-let-kids-play-act{,-specialization}-{concept-brief,script,voiceover-brief,visual-prompts,assembly,social-repurpose}.md` — have frontmatter consisting solely of `version: 1`. `rgs-briefs/README.md:39-42` makes the two file kinds separable by exactly one rule: "Consumers that glob this directory MUST skip any file with a `kind:` field", warning that treating a non-grounding file as a grounding brief "will either crash the check or silently corrupt the recency window." These ten have no `kind:` **and** no `thinker`/`concept`/`research_codes`, so they pass the skip filter as grounding briefs and present nothing to compare. `rgs-grounding/SKILL.md:47-52` instructs a glob of "the last ~20 files by date" for its recency and repeat checks; ten of the ledger's 38 artifacts are miscategorised for that purpose. The 2026-07-28 backfill note at `README.md:136-139` records the minimal-frontmatter write but never records this consequence.
- **trigger**: Any `rgs-grounding` invocation whose ~20-file recency window reaches back to 2026-07-25.
- **proposed_fix**: Backfill `kind:` (and `slug`/`stage`) on the ten files under a new version, or make the two-kind test positive (`has thinker+concept+research_codes`) rather than negative (`lacks kind`), and state the chosen rule in `rgs-briefs/README.md` and `rgs-grounding`.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T9
- **detected_by**: manual-trace

### C-54 · Every `worked-example.md` is unmarked — nine files, the pattern skills are told to copy
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `.claude/skills/social-repurpose/references/worked-example.md` (5/5 unmarked), `.claude/skills/visual-prompts/references/worked-example.md` (14/15), `.claude/skills/rgs-grounding/references/worked-example.md` (8/8), `.claude/skills/midjourney-prompting/references/worked-example.md` (7/7), `.claude/skills/elevenlabs-audio/references/worked-example.md` (6/6), `.claude/skills/shorts-assembly/SKILL.md:70`
- **component**: skills
- **failure_mode**: silent
- **blast_radius**: Nine skills each carry a `references/worked-example.md`; seven are majority-unmarked and five are 100% unmarked. These are not incidental files — `shorts-assembly/SKILL.md:70` instructs "produce the plan itself, structured the same way `references/worked-example.md` is… copy that structure for the real script, don't reinvent the layout per request." An unmarked worked example is therefore the template the emitted artifact inherits, so unmarked normative lines propagate from the example into every real brief. This is the mechanism by which C-42 reaches operator-facing output. Extends SEED-12's observation that worked examples are the worst reference outliers.
- **trigger**: Any skill that emits an artifact modeled on its worked example.
- **proposed_fix**: Decide one policy and apply it to all nine: either a header disclaimer stating the example illustrates already-marked rules and carries no independent normative weight, or per-line markers inherited from the reference file each line applies. Assert the chosen policy in the provenance test.
- **fix_cost**: M
- **depends_on_finding**: [C-42]
- **owner_task**: T9
- **detected_by**: grep-sweep

### C-55 · Four reference filenames are reused across skills, making bare citations ambiguous by name
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `.claude/skills/visual-prompts/references/worked-example.md:6`, `.claude/skills/shorts-styleboard/references/visual-registers.md:1`, `.claude/skills/visual-prompts/references/visual-registers.md:1`, `.claude/skills/elevenlabs-music/references/api-payload.md:1`, `.claude/skills/elevenlabs-audio/references/api-payload.md:1`
- **component**: skills
- **failure_mode**: latent
- **blast_radius**: `worked-example.md` exists in 9 skills, `validation-gates.md` in 3, `api-payload.md` in 2, `visual-registers.md` in 2. Combined with 190 bare citations (Q1), a filename alone never identifies a file. This is the mechanism behind C-41 — `visual-registers.md` resolving to the tombstone rather than the 149-line original — and it makes the C-40 class hard to detect by eye, because a bare citation to a duplicated name always *looks* plausible. `elevenlabs-audio` and `elevenlabs-music` both have an `api-payload.md` and both cite it bare while also cross-referencing each other's sibling `voiceover-brief` files.
- **trigger**: Cross-skill citation of any duplicated filename without a skill-name qualifier.
- **proposed_fix**: Require every cross-skill citation to be skill-qualified (16 already are) and enforce it in the same test proposed for C-40; consider prefixing duplicated filenames with the owning skill.
- **fix_cost**: S
- **depends_on_finding**: [C-40, C-41]
- **owner_task**: T9
- **detected_by**: grep-sweep

---

## T10 — Linter scripts

Scope: the five files at repo root that constitute the entire deterministic quality backbone of this system — `scripts/lint_prompt_sheet.py` (Gate C, C1–C20), `scripts/lint_script_language.py` (Gate D, D1–D6), `scripts/resolve_brief_version.py`, `scripts/build-cowork-plugin.sh`, and `scripts/__init__.py`. Only 2 of 9 pipeline stages are gated at all, and both gates are these scripts, so every claim of "the pipeline enforces X" reduces to what these files actually assert. Each linter has two callers with independent code paths: its own `main()` (invoked by a skill instruction from a shell) and `pipeline-app/pipeline_app/gates.py`, which loads the module by file path and calls its internal functions directly. Findings below were produced by manual trace plus 25 executed mutation experiments against the repo's own green fixtures (`tests/fixtures/passing_sheet.md`, `worked_example_sheet.md`, `script_let_kids_play_act.md`); every "confirmed" evasion was run and observed. `pipeline_app/gates.py` is read for comparison only — it belongs to T2, and one finding (C-93) is a hand-off.

**Headline:** the checks are individually well-reasoned, but the *parse layer beneath them is not fail-closed*. A one-character typo in a shot heading deletes that shot from Gate C entirely, and the gate then prints `PASS`. Of the 26 checks, **17 are trivially evadable** (one-line edit, no craft change): C1, C4, C5, C6, C7, C8, C9, C10, C11, C12, C16, C17, C19, C20, D3, D4, D6 — with C2, C3, C13, C14, C15, C18, D1, D2, D5 evadable at moderate cost.

### Q1 — Per-check evadability

Gate C (`scripts/lint_prompt_sheet.py`). "Evasion severity" = what ships if the check is defeated.

| Check | What it actually asserts | Trivially evadable? How | Evasion severity |
|---|---|---|---|
| **C1** :285-296 | Adjacent parsed shots differ in `shot_class` | **Yes** — alternate two classes forever (`DETAIL`/`ESTABLISHING`/`DETAIL`…); asserts difference, never variety | S3 monotonous sheet |
| **C2** :297-302 | Adjacent parsed shots differ in `scale` | Moderate — same ping-pong trick, but interacts with C4's ≥3 floor | S3 |
| **C3** :303-316 | No >2 consecutive non-PLATE shots in one register | Moderate — relabel the third as `Register PLATE` (excluded from the run) | S2 register split collapses |
| **C4** :318-322 | ≥3 *distinct* scales anywhere on the sheet | **Yes** — 3 scales on a 20-shot sheet satisfies it; a set-size test, not a distribution test | S3 |
| **C5** :324-328 | ≥2 distinct camera heights anywhere | **Yes** — same; one off-height shot satisfies a whole sheet | S3 |
| **C6** :344-351 | ≥3 Register A shots, ≥2 Register B | **Yes** — a floor, not a ratio; 3 A + 2 B + 15 PLATE passes | S2 |
| **C7** :353-363 | ≥2 register alternations across the sheet | **Yes** — two switches anywhere satisfies a 20-shot sheet. Its own message ("bookending … is not an intercut rhythm") describes exactly what still passes | S2 |
| **C8** :445-465 | Register A body lowercase-*contains* `register_a_sport`, and ≥1 `register_a_signature_objects` entry | **Yes** — write the sport's name once anywhere in the body, plus one object noun. Substring, not semantics | S2 shot may not depict the sport |
| **C9** :431, 466-475 | Register A body contains neither `"empty gym"` nor `"empty youth gym"` | **Yes** — "vacant gym", "deserted gym", "empty field", "empty pitch" all pass. Two literal strings | S2 generic venue ships |
| **C10** :432-436, 477-498 | Register B body avoids `dslr` / `shot on 35mm film` / `documentary` and `\d+\s*mm`, `\bf/\d` | **Yes** — "photographic", "bokeh", "shallow depth of field", "Leica", "Kodachrome", "cinematic still" all pass; flags aren't scanned at all | S1 the two registers collapse into one look, which is the defect the whole dual-register system exists to prevent |
| **C11** :508-523 | No shot pair shares >5 byte-identical comma clauses | **Yes (confirmed)** — appending one word to each clause of an exact clone took shared clauses 12 → 0 and the sheet passed | S2 cloned prompt bodies ship |
| **C12** :526-545 | Body has ≥10 comma clauses and ≥60 words | **Yes (confirmed)** — ten nonsense clauses of filler words passed the whole gate. A token count standing in for "nine layers of concrete content" | S1 contentless prompts ship |
| **C13** :565-606 | One line; `No Text.` present and last before flags; a flag block exists; `--ar` *present*; no `,`/`;`/`.` in flags | Moderate for the format rules — but **`--ar`'s value is never read**: `--ar 16:9` on a vertical Short passes (confirmed) | S1 wrong aspect ratio renders |
| **C14** :608-629 | A carries `--raw`, B does not; `--s` present and inside the register band | Moderate — relabel the shot `Register PLATE` (bands skipped entirely); or write `--s` twice, only the first is read | S2 |
| **C15** :374-428 | shot_class/scale/camera_height are in their closed sets | Not evadable *within* a parsed heading — but a token that breaks the heading regex (`Mid-Wide`, `MID_WIDE`) removes the shot instead of failing C15, so the docstring's claim holds only for `[A-Z-]+` typos | S1 via C-70 |
| **C16** :634-709 | Literal `--sref` value is digits/URL/`random`; `--p` value is alphanumeric | **Yes (confirmed)** — `--sref 11111111` passed. Any digit string is "plausible", so an invented numeric code is indistinguishable from a harvested one | S1 renders with a nonexistent style code |
| **C17** :715-751 | Every non-PLATE shot carries `--sref`, `--p`, or a `{style:…}` slot | **Yes (confirmed)** — a bare `--p` (no value) satisfies C17 *and* is explicitly exempted by C16, so it is a two-character defeat of both | S1 no style lock; the render depends on whoever's personalization profile is active |
| **C18** :768-830 | Slot tokens sit after the first ` --`, are declared in the world lock, and hold a kebab-case value | Moderate — but wholly optional: a sheet that writes literal `--sref <digits>` never triggers C18 at all | S2 |
| **C19** :174-204 | Exactly one `### Cover — …` block, **or** a `Cover = Hook…` line outside a fence | **Yes** — the literal line `Cover = Hook` satisfies it (by design); nothing checks a hook shot exists. A cover block with an empty fence plus that line leaves the cover entirely unlinted | S2 |
| **C20** :882-926 | Each declared slot value names a `## Entries` label in `docs/style-library.md` | **Yes (confirmed)** — three independent bypasses: (a) don't use slots, use a numeric `--sref`; (b) CLI `--style-library` pointed at a hand-written one-entry file (confirmed passing); (c) add an entry with `code: UNHARVESTED` (documented as deliberate) | S1 the exact failure C20 was built for |

Gate D (`scripts/lint_script_language.py`).

| Check | What it actually asserts | Trivially evadable? How | Evasion severity |
|---|---|---|---|
| **D1** :263-279 | No `–`/`—` **inside a quoted span** of a recognized beat line | Moderate — use ` - ` (ASCII hyphen), `…`, or move the clause outside the quotes (then it is unlinted entirely) | S3 |
| **D2** :280-297 | No `;`, `(...)`, `[...]` inside a quoted span | Moderate — same escapes; commas and colons are unrestricted | S3 |
| **D3** :304-353 | 3 fingerprint phrases + 5 lemma families | **Yes** — the list is closed and small by design (the anti-generic rule forbids inventing a sixth lemma). "in today's world", "let's unpack", "game-changer", "at the end of the day" all pass | S2 AI-voiced script ships |
| **D4** :332-337 | `&`, `§`, `\w+\s*=\s*\d`, `\d+\(\d+\):\d+` | **Yes** — `%`, `#`, `©`, `p<.05`, `et al.`, `vs.`, `3/4`, a URL, roman numerals all pass | S2 TTS mangles the line |
| **D5** :381-442 | Per rated line, wpm ≤ 172; blocks only if *nothing* is ratable | **Yes (confirmed)** — delete the `(a–bs)` range from the over-stuffed beat. It becomes a `skipped` finding (non-blocking) and, as long as one other line still carries a range, the `rated == 0` backstop never fires. 5 of 6 lines went unrated and the gate did not object | S1 unspeakable timing propagates to voiceover-brief and assembly |
| **D6** :457-489 | A `Gate E: <value>` line exists whose value is not the literal template placeholder | **Yes (confirmed)** — appending `Gate E: pass` anywhere in the file satisfies it, including inside a code fence. The docstring concedes this ("raises the cost … from silent to deliberate, and no further"); recorded here for completeness, and because unlike Gate C's fence-aware `declares_cover_reuse` it does no scoping at all | S2 |

### Q2 — Silent-partial-parse paths (the weak point)

Every path below returns a *partial* result without raising, and in every case the checks then run vacuously over the surviving subset.

`parse_sheet` (:48-86) — **the most consequential.** `SHOT_HEADING_RE` (:17-20) demands an exact six-field heading with `—` (U+2014) and `·` (U+00B7) separators and `[A-Z-]+` vocabulary tokens. Any deviation — en-dash, hyphen, `Mid-Wide`, an underscore, a stray trailing space after the last field — makes the line invisible and the shot vanishes with **no finding of any kind**. Confirmed: breaking Shot 4's separator in `worked_example_sheet.md` and replacing its prompt with `empty gym, dslr, 35mm, --sref mj-INVENTED-01` (no `No Text.`, no `--ar`, no `--s`) printed `Gate C: PASS — 10 shots, 0 findings`. Also: (a) the scan is **not fence-aware**, so a `### Shot 99 — …` line inside a documentation fence is parsed as a real shot; (b) the world-lock walk stops at the first line failing `WORLD_ENTRY_RE` (:24), so a blank line mid-block silently truncates it, and unindented entries yield `{}`; (c) a second `WORLD LOCK` heading silently overwrites the first (last-wins); (d) `_read_fenced_prompt` (:230-245) breaks on `SHOT_HEADING_RE` but **not** on `COVER_HEADING_RE`, so a shot whose fence is mistyped (` ```markdown `) can absorb the cover's prompt body.

`parse_world_lock` (:89-97) — delegates to `parse_sheet`, inheriting every path above. Returns `{}` for a styleboard whose block is absent, unindented, or differently named; the CLI does **not** guard this (see C-74).

`parse_cover` (:111-140) — returns `None` for three different states (reuse-the-hook, no block, block-present-but-fenceless) and for a *fourth* undocumented one: a well-formed cover heading whose fence is empty or mistyped. Combined with a `Cover = Hook` line, C19 passes and the cover is never linted.

`parse_style_library` (:842-879) — returns `{}` or a short dict, never raises: a renamed `## Entries` heading → `{}`; a heading with trailing text (`### rgs-a (channel)`) → that entry silently missing; a non-kebab label (`### RGS-A`) → silently missing; an unclosed fence inside an entry → every later entry silently missing (verified: `{'rgs-a': '1'}` where two entries exist). A fully-empty result is caught (`main` :1012, gates.py:112); a *partially* empty one is not, and surfaces as a C20 failure naming the wrong problem.

`sheet_declares_slots` (:957-962) — reads only *parsed* shots plus the cover. A shot dropped by the heading regex takes its slots with it, so the Library is never loaded and C20 goes vacuous for the whole sheet.

`parse_script` (:115-227) — `BEAT_LABEL_RE` (:24) anchors at the start of the stripped line, so `**HOOK**` or `## HOOK` is not a beat. **The existing `partial-parse` finding is not sufficient.** It has exactly two triggers: a *recognized* heading that yielded no quoted span, and a declared-vs-counted shortfall. Neither can see a heading that was never recognized. Confirmed: bolding the HOOK label dropped the beat (6 → 5 VO lines) with zero PARSE findings and silently removed a real D5 violation (260 wpm). Second gap: the shortfall detector is **opt-in via the artifact** — it only runs when the heading carries `| N words` (:35, :173-174). Confirmed: stripping the `| N words` declarations and moving half the HOOK text outside its quotes produced no PARSE finding, and the buzzwords, parenthetical and `n=142` planted in the unquoted tail were all unchecked. Third gap: the 25% + 3-word threshold (:88-97) means up to a quarter of a beat's spoken text can be dropped silently by design.

### Q3 — Two-callers parity

**Gate C — `lint_prompt_sheet.main` (:965-1036) vs `gates.run_prompt_sheet_gate` (gates.py:63-125)**

| Aspect | CLI `main()` | App runner | Same? |
|---|---|---|---|
| World-lock source | `--styleboard` if passed, else the sheet's own block (:989-992) | `upstream["styleboard"]` if present, else the sheet's own block (gates.py:82-86) | Equivalent in shape; the CLI's is operator-chosen per invocation and silently optional |
| **Empty world lock** | **No guard.** Lints against `{}` and emits a wall of C8/C18 findings | Raises `ValueError` → gate status `error`, naming the empty artifact (gates.py:87-96) | **DIFFERENT** → C-74 |
| No shots parsed | print + `return 2` (:994-996) | `raise ValueError` → `error` (gates.py:76-77) | Equivalent (both non-pass) |
| Cover handling | `parse_cover` + `check_cover_present` + `lint(cover=…)` (:998, 1019-1022) | Identical calls (gates.py:98, 121-124) | **Same** |
| **Library path** | `--style-library`, default repo `docs/style-library.md` (:978-984) — **operator-overridable to any file** | Hard-coded `repo_root/docs/style-library.md`, no override (gates.py:105) | **DIFFERENT** → C-75 |
| Library gating | Only when `sheet_declares_slots` (:1004) | Identical (gates.py:104) | **Same** |
| Missing / empty Library | print + `return 2` (:1005-1017) | `raise ValueError` → `error` (gates.py:106-119) | Equivalent |
| Check set & order | `check_cover_present` then `lint(...)` — C1–C20 | Byte-identical call pair | **Same** |
| `skipped` semantics | Gate C's `Finding` (:41-45) has **no `kind` field**; every finding counts | `f.get("kind") != "skipped"` → `None != "skipped"` → every finding blocks (gates.py:167) | Equivalent **by accident** → C-93 |

**Gate D — `lint_script_language.main` (:503-531) vs `gates.run_script_language_gate` (gates.py:50-60)**: no divergence found. Same `parse_script`, same `lint(vo_lines, text, parse_findings)`, same parse-findings inclusion, same `kind != "skipped"` blocking rule (CLI :518, app gates.py:167). The only difference is presentation — the CLI prints `skipped` findings and returns 2 on no-VO-lines where the app raises.

### Q4 — Exit codes

Both linters, verified by execution:

| Situation | `lint_prompt_sheet` | `lint_script_language` | `resolve_brief_version` |
|---|---|---|---|
| Pass | `0` + `Gate C: PASS` | `0` + `Gate D: PASS` | `0` + `<path>\t<version>` |
| Findings | `1` + `Gate C: FAIL` | `1` + `Gate D: FAIL` | n/a |
| No parseable input | `2` + explanatory line (:994-996) | `2` + explanatory line (:513-515) | `1` + `NONE\t0` (:88-89) |
| Missing/unreadable file | **`1`**, traceback on stderr, no stdout (:987) | **`1`**, traceback on stderr (:511) | **`1`**, traceback (malformed frontmatter) |
| argparse usage error | `2` | `2` | `2` |

A crash is **not** confusable with a pass (0 is only ever printed alongside `PASS`), but a crash **is** confusable with a failing gate — both are `1`, distinguished only by stdout being empty. Exit `2` is overloaded across "usage error" and "format unparseable". `skipped` findings do **not** affect either linter's exit code (:518-527) or the app's gate status (gates.py:167). `resolve_brief_version` is the worst case: `1` means both "no prior version exists" (a normal, expected answer) and "a brief has malformed frontmatter" (:52-53).

### Q5 — `skipped` findings

Only **one** check in the whole system emits `kind="skipped"`: D5's unratable-beat branch (`lint_script_language.py:412-419`). Gate C's `Finding` dataclass has no `kind` field at all, so no Gate C finding can ever be non-blocking. A malformed sheet therefore cannot make most findings `skipped` — but it can do something equivalent and worse: make them *not exist* (C-70). On the Gate D side the answer is yes-with-a-caveat: a script that carries a time range on exactly one beat renders the other N-1 beats' pace findings `skipped` and non-blocking, and the `rated == 0` backstop (:431-441) only fires when *zero* lines are ratable — confirmed, 5 of 6 lines unrated with no blocking finding. `PARSE` findings use `kind="partial-parse"`, which correctly blocks.

### Q6 — C20 and the Style Library coupling

`parse_style_library` tolerates a reformatted `docs/style-library.md` **poorly and silently**: the walk requires the section heading to be exactly `## Entries` (:869-870) and each entry heading to be exactly `### <kebab-label>` with nothing else on the line (:838, :876). Renaming the section to `## Library entries` yields `{}` — caught loudly by the empty-Library guard, which at least reports the right file. But adding a parenthetical to an entry heading, capitalizing a label, or leaving a fence unclosed drops individual entries **silently**, and C20 then reports the *sheet* as wrong. Documentation of the coupling is partial: `docs/style-library.md:189-191` (Open questions §2) states that `parse_style_library` "reads the `## Entries` section", but neither the `## Entry format` section (:39-56) nor the `## Entries` heading itself (:83) carries any warning that the heading text and label shape are load-bearing on a gate. An editor tidying the file has no local signal. → C-76, C-77.

### Q7 — `resolve_brief_version.py`

Version resolution reads frontmatter, never filenames, so the documented `v10 vs v9` hazard is genuinely handled (:44-57; verified). The unhandled cases: a **version tie** across two files silently resolves to whichever sorts first (verified — two files both `version: 2`, the earlier date won, no warning); a **date collision** is invisible because dates are never compared; the `-vN` filename suffix is **never cross-checked** against the frontmatter it claims to mirror, so `next_filename` can propose `-v2` while `-v3` sits on disk (verified); a **missing or wrong `--dir`** (default `rgs-briefs`, resolved relative to CWD) returns `(None, 0)` with no error, so `--next` proposes a v1 filename over a live v1 (verified); and `--date` is passed straight into the filename unvalidated (`--date banana` produced `banana-do-less-sold-as-win-more-assembly-v4.md`, exit 0). → C-96 … C-100.

### Q8 — `build-cowork-plugin.sh`

It **does** mirror `.claude/skills/` faithfully — `cp -R .claude/skills/.` copies all 13 skill trees including every `references/`, then deletes the two RGS-only ones, shipping 11. It **does** fail loudly on a copy error (`set -euo pipefail`, :16), and the PowerShell fallback branch was verified to return exit 1 on a `Compress-Archive` failure and to include the dot-prefixed `.claude-plugin/` directory. It does **not** validate the `plugin.json` it writes (it is a static heredoc, so it is always well-formed JSON, but nothing checks it against Cowork's schema), does **not** verify the copied tree (the trailing `find … | wc -l` is printed, never asserted), and is **never run automatically** — the repo has no CI (`.github/` contains only `PULL_REQUEST_TEMPLATE.md`). Combined with a hard-pinned `"version": "0.1.0"` and a git-ignored `dist/`, a stale `.plugin` is undetectable by inspection. The manifest text is also already wrong: it ships 11 skills while calling itself "Seven" in three places. → C-101 … C-104.

### Q9 — Stubs, dead code, uncalled checks

No `TODO`/`FIXME`/stub markers in any owned file. Every check function is reachable: Gate C's C1–C20 all run from `lint` (:929-951), and `lint_cover` (:207-227) deliberately omits C1–C7 and C11 with a stated reason; Gate D's D1–D6 all run from `lint` (:492-500). `check_prompt_quality` (:548-550) is a thin alias over C11+C12 kept for callers; `parse_world_lock` (:89-97) is a documented delegate to `parse_sheet`. The only redundancy is `MOODBOARD_FLAG_RE` (:712) duplicating `P_FLAG_RE`'s prefix pattern under a second name. `scripts/__init__.py` is empty and exists only to make the root `scripts/` importable by the root test suite — the same package identity that shadows `pipeline-app/scripts/` and forces the two-suite invocation rule in CLAUDE.md. → C-105.

### Findings

### C-70 · A one-character shot-heading typo deletes the shot from Gate C, silently
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:17-20`, `scripts/lint_prompt_sheet.py:66-84`, `scripts/lint_prompt_sheet.py:994-996`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `SHOT_HEADING_RE` requires exact `—`/`·` separators and `[A-Z-]+` vocabulary tokens; any deviation makes the line invisible and the shot disappears from every one of C1–C20. Verified: breaking Shot 4's separator in `worked_example_sheet.md` and replacing its prompt with `empty gym, dslr, 35mm, --sref mj-INVENTED-01` (no `No Text.`, no `--ar`, no `--s`) printed `Gate C: PASS — 10 shots, 0 findings`. This is the single largest hole in the enforcement backbone: an unlinted shot is exactly the shot most likely to be malformed.
- **trigger**: An author or model writes an en-dash, hyphen, or non-uppercase vocabulary token in one shot heading.
- **proposed_fix**: Make an unmatched `### Shot`-prefixed line a hard finding rather than a skipped line — match a loose `^###\s+Shot\b` first and fail any line that then fails the strict pattern, reporting the offending heading text.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-71 · No reconciliation of parsed shot count or index contiguity
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:69-80`, `scripts/lint_prompt_sheet.py:1024`, `scripts/lint_prompt_sheet.py:1027`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `Shot.index` is parsed from every heading but never used for anything except finding messages. A sheet whose indices run 1,2,3,5,6,… (one shot lost to C-70) reports `PASS — 10 shots` with no hint that eleven were authored. The operator's only defence is manually counting a sheet the gate just declared clean.
- **trigger**: Any dropped, duplicated, or misnumbered shot heading.
- **proposed_fix**: Assert that parsed indices form a contiguous 1..N run, and echo the count against a declared shot count in the sheet header. Both are whole-sheet checks with no per-shot cost.
- **fix_cost**: S
- **depends_on_finding**: [C-70]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-72 · `parse_sheet` is not fence-aware; a documented example becomes a real shot
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:55-84`, `scripts/lint_prompt_sheet.py:104-108`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: A `### Shot 99 — Demo · Register A · DETAIL · MACRO · LOW` line sitting inside a ```` ```text ```` fence parses as a real shot (verified). It then carries an empty prompt and pollutes C1–C7 adjacency, C4/C5 spread and C6 counts. The neighbouring `declares_cover_reuse` (:148-171) was carefully written to be fence-aware for exactly this reason; the shot walk was not given the same treatment.
- **trigger**: A sheet or template that documents the heading format inline, or a pasted example block.
- **proposed_fix**: Track fence state in `parse_sheet`'s main loop the way `declares_cover_reuse` already does, and ignore headings inside fences.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-73 · World-lock walk truncates at the first non-matching line; duplicates last-win
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:24`, `scripts/lint_prompt_sheet.py:56-64`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: A blank line, comment, or unindented entry mid-block silently ends the walk — verified `WORLD LOCK / a: 1 / <blank> / slot_register_a: x` yields `{'a': '1'}`. Unindented entries yield `{}` entirely. A second `WORLD LOCK` heading anywhere in the file silently overwrites the first. Downstream this surfaces as C8/C18 findings blaming the sheet for a styleboard formatting problem.
- **trigger**: A styleboard author separates world-lock groups with a blank line, or leaves a superseded block above the live one.
- **proposed_fix**: Consume the whole block to the next unindented non-blank line, reporting any line inside it that fails the entry pattern; reject a second `WORLD LOCK` heading outright.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-74 · CLI lacks the empty-world fail-closed guard the app path has
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:989-992`, `pipeline-app/pipeline_app/gates.py:86-96`
- **component**: linters
- **failure_mode**: loud
- **blast_radius**: `gates.py` deliberately raises when a styleboard yields no world lock, with a comment explaining that linting against an empty world "would emit a wall of C8/C18 findings naming the wrong problem". `main()` has no such branch — verified, an empty styleboard produced 14 findings, none of which mention the styleboard. Both paths block, so nothing wrong ships; the operator is pointed at the wrong artifact. This is a live instance of the divergence `run_prompt_sheet_gate`'s own docstring (gates.py:66-71) says must not exist.
- **trigger**: Running the CLI with `--styleboard` pointing at a backfilled or reformatted styleboard.
- **proposed_fix**: Add the same empty-world check to `main()` and return 2 with the styleboard's name, matching the app path's message.
- **fix_cost**: S
- **depends_on_finding**: [C-73]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-75 · `--style-library` is an unconstrained CLI-only escape hatch that voids C20
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:978-984`, `scripts/lint_prompt_sheet.py:1004-1017`, `pipeline-app/pipeline_app/gates.py:104-111`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: The app path hard-codes `repo_root/docs/style-library.md` with no override; the CLI accepts any path. Verified: a four-line hand-written file containing `## Entries` / `### anything-goes` turned a sheet that fails C20 against the real Library into `PASS — 5 shots, 0 findings`. Two gates wearing one name, with the laxer one being the path a skill instruction actually invokes.
- **trigger**: Any invocation that passes `--style-library`, including a well-meant one pointing at a draft Library.
- **proposed_fix**: Either drop the flag and pin the Library to the repo path as the app does, or record the resolved Library path in the PASS/FAIL output so a non-default one is visible in the transcript.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-76 · `parse_style_library` drops individual entries silently on benign reformatting
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:838`, `scripts/lint_prompt_sheet.py:856-879`, `scripts/lint_prompt_sheet.py:1012-1017`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: Verified: `### rgs-a (channel)` → entry missing; `### RGS-A` → entry missing; an unclosed fence inside an entry → every later entry missing. A *fully* empty Library is caught and reported against the right file; a partially parsed one is not, and C20 then fails the sheet with "is not an entry in docs/style-library.md" while listing an incomplete "Known entries" set — pointing the author at a nonexistent typo in their styleboard.
- **trigger**: Anyone editing `docs/style-library.md` who adds a qualifier to an entry heading or leaves a fence unbalanced.
- **proposed_fix**: Within `## Entries`, report any `### `-prefixed line that fails the label pattern rather than skipping it, and detect an unterminated fence at end of file.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-77 · The Style Library does not warn that its headings are load-bearing on Gate C
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `docs/style-library.md:83`, `docs/style-library.md:39-56`, `docs/style-library.md:189-191`
- **component**: linters
- **failure_mode**: docs-drift
- **blast_radius**: The coupling is stated once, buried in "Open questions §2" as prose about a resolved question. Neither the `## Entry format` block that an editor reads before adding an entry, nor the `## Entries` heading itself, says that the section name and the `### <kebab-label>` shape are parsed by a gate. An editor who renames the section or annotates a heading breaks C20 for every Short with no local signal.
- **trigger**: Routine tidying of the Library file.
- **proposed_fix**: Add a one-line machine-coupling warning immediately above `## Entries` and inside the `## Entry format` block, naming `scripts/lint_prompt_sheet.py:parse_style_library` and the exact heading constraints.
- **fix_cost**: S
- **depends_on_finding**: [C-76]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-78 · A cover block with a mistyped or empty fence is silently unlinted
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:111-140`, `scripts/lint_prompt_sheet.py:194-204`, `scripts/lint_prompt_sheet.py:230-245`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `parse_cover` returns `None` when `prompt_lines` is empty (:128-129), collapsing "no cover" and "cover present but unreadable" into one state. If the sheet also carries a `Cover = Hook…` line, C19 is satisfied and `lint_cover` never runs — the thumbnail, the single highest-leverage asset in the Short, ships with zero format, density, or style checks. Separately, `_read_fenced_prompt` breaks on `SHOT_HEADING_RE` but not `COVER_HEADING_RE`, so a shot with a mistyped fence can swallow the cover's prompt body.
- **trigger**: A cover block whose fence is ```` ```markdown ````, or a sheet that keeps a `Cover = Hook` note alongside a real cover block.
- **proposed_fix**: Distinguish "cover heading present but no readable prompt" from "no cover" and make the former a C19 finding; add `COVER_HEADING_RE` to `_read_fenced_prompt`'s break condition.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-79 · C16 accepts any digit string, so an invented numeric `--sref` passes
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:638`, `scripts/lint_prompt_sheet.py:682-690`, `scripts/lint_prompt_sheet.py:957-962`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `VALID_SREF_VALUE_RE` is `^(?:\d+|random|https?://\S+)$`. Verified: replacing both `{style:…}` slots with `--sref 11111111` / `--sref 22222222` produced `PASS — 5 shots, 0 findings`. C16 catches only invented codes that *look* invented (uppercase/hyphenated); a fabricated number is indistinguishable from a harvested one, and because the sheet then declares no slots, `sheet_declares_slots` returns False, the Library is never loaded, and C20 is skipped entirely. The documented failure — "no render in this Short ever had a style lock applied" — remains reachable through a shape C16 was never taught to distrust.
- **trigger**: A model or author writes a plausible-looking numeric style code instead of a `{style:…}` slot.
- **proposed_fix**: Require every non-PLATE shot to use a `{style:…}` slot (making C20 the single resolution path), or resolve literal numeric `--sref` values against the Library's recorded `code:` values so a number that matches no harvested code fails.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-80 · A bare `--p` satisfies C17 while providing no recorded style lock
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:652-671`, `scripts/lint_prompt_sheet.py:712`, `scripts/lint_prompt_sheet.py:737-741`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: C16 explicitly exempts a valueless `--p` (legitimate Midjourney syntax for "apply my active personalization profile"), and C17 accepts `--p` as a style mechanism. Verified: replacing both slots with a bare `--p` produced `PASS — 5 shots, 0 findings`. The result is a sheet that passes Gate C while the actual look depends on whichever operator's profile is active at paste time — unrecorded, unreproducible, and invisible to the Library. Two characters defeat both style checks at once.
- **trigger**: Any prompt written with `--p` and no value.
- **proposed_fix**: Exclude a valueless `--p` from C17's set of accepted mechanisms — it is legitimate syntax but not a *recorded* style lock, which is what C17 exists to require.
- **fix_cost**: S
- **depends_on_finding**: [C-79]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-81 · C13 checks that `--ar` is present, never what it says
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:591-592`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `if "--ar" not in flags` is the entire assertion. Verified: rewriting every `--ar 9:16` to `--ar 16:9` produced `PASS — 5 shots, 0 findings`. Every asset in a vertical Short would render landscape, discovered only at assembly. The register bands beside it (C14) validate their values; the aspect ratio does not.
- **trigger**: A copied prompt from a landscape job, or a model defaulting to `16:9`.
- **proposed_fix**: Parse the `--ar` value and require `9:16` for Shorts (with the ratio as a module constant so a future non-vertical format can override it).
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-82 · C11's anti-clone check is defeated by one word per clause
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:267-269`, `scripts/lint_prompt_sheet.py:508-523`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `body_clauses` lowercases and splits on commas, then C11 intersects the resulting sets — byte-equality per clause. Verified: an exact clone of Shot 1 pasted as Shot 3 fires C11 with 12 shared clauses; appending the single word "here" to each clause takes it to 0 shared and the sheet passes. Cloned prompt bodies are precisely the defect the dual-register system pushes into `--sref`, and the check can be sidestepped without changing a single visual idea.
- **trigger**: An author lightly rewording a copied prompt rather than writing a new one.
- **proposed_fix**: Compare normalized clauses by token-set overlap (e.g. Jaccard above a threshold) rather than exact string equality, or compare whole-body similarity in addition to per-clause equality.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-83 · C12's density check is a token count, satisfied by filler
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:503-506`, `scripts/lint_prompt_sheet.py:526-545`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: The docstring claims C12 verifies "every prompt carries concrete renderable content in all nine layers"; the implementation counts commas and words. Verified: a prompt body of ten repetitions of `wN filler token phrase alpha beta gamma` plus `club soccer goal net` passed the entire gate. Nothing maps clauses to the nine layers, so a prompt can be maximally dense and describe nothing.
- **trigger**: A verbose but contentless prompt, which is exactly what a model produces when padding to a length target.
- **proposed_fix**: Either require named layer markers in the prompt body so the nine layers can be checked structurally, or downgrade the docstring to state honestly that C12 is a length floor and not a content check.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-84 · C9 and C10 are literal-string no-lists of two and three entries
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:431-436`, `scripts/lint_prompt_sheet.py:466-498`
- **component**: linters
- **failure_mode**: coverage-gap
- **blast_radius**: C9 bans `"empty gym"` and `"empty youth gym"`; "vacant gym", "deserted gym", "empty field", "empty pitch" all pass. C10 bans `dslr`, `shot on 35mm film`, `documentary` plus two optics patterns; "photographic", "photorealistic", "bokeh", "shallow depth of field", "Leica", "Kodachrome", "cinematic still" all pass and each collapses Register B into Register A's look. Both are also scoped to `prompt_body`, so photographic vocabulary written into the flag block is unreachable. The register split is the project's central visual claim, and the mechanical half of its enforcement is five strings.
- **trigger**: Any synonym outside the five literals.
- **proposed_fix**: Extend both lists from the corpus's own vocabulary sections with `[C]`-cited terms, and scan the whole prompt rather than the body only.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-85 · `Register PLATE` is an unaudited exemption from C8, C9, C10, C14 and C17
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:303`, `scripts/lint_prompt_sheet.py:384-388`, `scripts/lint_prompt_sheet.py:608-610`, `scripts/lint_prompt_sheet.py:734-735`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: A PLATE shot is skipped by the C3 run computation, excluded from C6/C7 register counts, exempt from the C14 `--raw`/`--s` bands (`REGISTER_BANDS.get` returns None → `continue`), exempt from C17, and never touched by C8/C9/C10 (both are register-scoped). Its only obligation is `shot_class == "PLATE"`. Verified: relabelling a Register B shot as PLATE removed its every register check, leaving only an incidental C6 count failure. Nothing bounds how many shots may be PLATE, and nothing checks a PLATE prompt is actually subject-free.
- **trigger**: Labelling an awkward shot `Register PLATE` to clear a failing gate.
- **proposed_fix**: Cap PLATE shots as a fraction of the sheet and apply the format/style checks (C13, C17) to them, exempting only the register-specific rules the design actually justifies.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-86 · C19 accepts a bare `Cover = Hook` line with no hook shot verification
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:108`, `scripts/lint_prompt_sheet.py:148-171`, `scripts/lint_prompt_sheet.py:194`
- **component**: linters
- **failure_mode**: coverage-gap
- **blast_radius**: `COVER_REUSE_RE` matches `^\s*Cover\s*=\s*Hook\b` case-insensitively. The literal text `cover = hook` on its own line satisfies C19 for any sheet, and nothing verifies that a hook shot exists, that it is Shot 1, or that it is remotely suitable as a 9:16 thumbnail. The fence-awareness work here is careful; the assertion behind it is a string match.
- **trigger**: Declaring cover reuse without a hook still, or a stray line of prose.
- **proposed_fix**: When the reuse branch is taken, require the referenced shot to exist and lint that shot's prompt through `lint_cover`.
- **fix_cost**: S
- **depends_on_finding**: [C-78]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-87 · C8's world-lock test is a lowercase substring plus one signature object
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:441-465`
- **component**: linters
- **failure_mode**: coverage-gap
- **blast_radius**: `sport not in body` and `any(obj in body for obj in objects)` are the whole assertion. Naming the sport once anywhere in a 60-word body, plus one object noun, satisfies C8 regardless of whether the shot depicts the sport. It also matches inside larger words, so an unrelated compound containing the sport's name passes. The check's message ("the sport will not read") promises far more than the implementation delivers.
- **trigger**: A Register A prompt that mentions the sport in passing while depicting something else.
- **proposed_fix**: Require the sport term at word boundaries and require two or more signature objects, or state in the docstring that C8 is a mention check rather than a depiction check.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-88 · An unrecognized beat heading deletes the beat from Gate D with no finding
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/lint_script_language.py:24`, `scripts/lint_script_language.py:63-72`, `scripts/lint_script_language.py:142-165`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `BEAT_LABEL_RE` anchors at the start of the stripped line, so `**HOOK**`, `## HOOK`, or `- HOOK` is not a beat. The `partial-parse` machinery can only fire for a heading it already recognized, so an unrecognized one produces nothing at all. Verified on `script_let_kids_play_act.md`: bolding the HOOK label took the script from 6 to 5 VO lines, emitted zero PARSE findings, and silently removed a real D5 violation (260 wpm). Every D-check then runs vacuously over the surviving beats.
- **trigger**: A script emitted with markdown-styled beat labels.
- **proposed_fix**: Detect beat labels anywhere on a line (or after leading markdown punctuation) and fail loudly on a line that looks like a beat heading but does not parse; cross-check the parsed beat set against the five expected labels.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-89 · The dropped-text detector is opt-in via the artifact it audits
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/lint_script_language.py:35`, `scripts/lint_script_language.py:173-174`, `scripts/lint_script_language.py:193-203`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: The only defence against silent under-extraction runs solely when a heading carries `| N words` — a declaration nothing requires and the linter never checks for. Verified: stripping the `| N words` declarations and moving half the HOOK text outside its quotes yielded no PARSE finding, and the buzzwords, parenthetical and `n=142` planted in the unquoted tail were all unchecked. A script that simply omits the budget annotations reduces Gate D to whatever happens to sit inside quotation marks. The comment at :33-35 calls the declaration "the only independent witness" without noting the witness is optional.
- **trigger**: A script emitted without `| N words` on its beat headings.
- **proposed_fix**: Require a `| N words` declaration on every top-level beat heading and fail its absence, so the detector cannot be disabled by the artifact being audited.
- **fix_cost**: S
- **depends_on_finding**: [C-88]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-90 · D5's `skipped` branch lets one ratable line disable the wpm ceiling
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_script_language.py:397-420`, `scripts/lint_script_language.py:431-441`, `pipeline-app/pipeline_app/gates.py:167`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: A beat with no parseable `(a–bs)` range produces a non-blocking `skipped` finding, and the `rated == 0` backstop only fires when *nothing* was rated. Verified: removing the range from five of six beats left one rated line, five `skipped` findings, and no blocking pace check — the deleted ranges are also the ones an over-stuffed beat most benefits from deleting. Both callers treat `skipped` identically, so the app-mode gate records `pass` on the same input.
- **trigger**: A script where all but one beat heading omits or malforms its time range.
- **proposed_fix**: Fail when the *ratable fraction* falls below a threshold rather than only at zero, and treat a malformed range (start ≥ end) as blocking rather than skipped — it is a defect, not a known unknown.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-91 · D6's pipe heuristic false-fails a legitimate result, and D6 is unscoped
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_script_language.py:445-454`, `scripts/lint_script_language.py:469-489`
- **component**: linters
- **failure_mode**: loud
- **blast_radius**: `_is_unfilled_placeholder` treats any `|` as proof of an unfilled template. Verified: `Gate E: 2 findings | 1 defended` — a genuine result in the contract's own vocabulary — still fires D6, and the comment at :446-449 asserts no genuine result contains a pipe. Conversely `GATE_E_RE` is a plain multiline scan with no fence or section scoping, so `Gate E: pass` typed anywhere, including inside a code fence, satisfies the lock (verified) — a weaker standard than the fence-aware `declares_cover_reuse` applies to C19 in the sibling linter.
- **trigger**: An author separating a Gate E result with a pipe, or a script quoting a Gate E line in an example.
- **proposed_fix**: Detect the template by matching its full alternation text rather than by the presence of `|`, and scope the scan to non-fenced lines as `declares_cover_reuse` does.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-92 · D3 and D4 no-lists are closed and small; the coverage limit is undocumented
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_script_language.py:304-337`, `scripts/lint_script_language.py:340-364`
- **component**: linters
- **failure_mode**: coverage-gap
- **blast_radius**: D3 covers 3 phrases and 5 lemma families; D4 covers `&`, `§`, `\w+\s*=\s*\d` and a journal-citation shape. `p<.05`, `%`, `#`, `©`, `et al.`, `vs.`, `3/4` and any URL all pass D4; "in today's world", "let's unpack", "game-changer" all pass D3. The narrowness is *correct* under the anti-generic guarantee (adding a sixth lemma would be inventing corpus content, as :313-315 says), but nothing tells an operator that a clean D3/D4 result means "none of these eight things" rather than "no AI fingerprints". The gate's pass message makes the broader claim.
- **trigger**: Any AI tell or unspeakable token outside the enumerated set.
- **proposed_fix**: Print the coverage scope alongside a D3/D4 pass ("checked N phrases, M lemmas") so the operator knows the assertion's width; extend only with `[C]`-cited corpus terms.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-93 · Gate C findings carry no `kind`; the two linters' finding records diverge
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:41-45`, `scripts/lint_script_language.py:47-52`, `pipeline-app/pipeline_app/gates.py:164`, `pipeline-app/pipeline_app/gates.py:167`
- **component**: linters
- **failure_mode**: latent
- **blast_radius**: Gate C's `Finding` is `(check, shot_index, message)`; Gate D's is `(check, beat, message, kind)`; the error record `gates.py` synthesizes is `(check, beat, message, kind)`. So a Gate C finding dict has no `beat` and no `kind`. The blocking rule `f.get("kind") != "skipped"` happens to be correct for Gate C only because a missing key yields `None` — correct by accident, not by contract. Any consumer that reads `finding["beat"]` or that adds a `skipped` concept to Gate C will break or silently mis-gate. Hand-off: the consumer side of this record belongs to T2.
- **trigger**: Adding a non-blocking finding kind to Gate C, or a UI/report reading a uniform finding shape.
- **proposed_fix**: Give both linters the same finding record — a shared field set with an explicit default `kind="fail"` and a single location field — so the blocking rule is contractual rather than incidental.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-94 · A missing input file exits 1, indistinguishable from a failing gate
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:987`, `scripts/lint_prompt_sheet.py:990`, `scripts/lint_script_language.py:511`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `read_text` is called before any error handling in both linters. Verified: a nonexistent sheet, a nonexistent styleboard, and a nonexistent script each exit 1 with a traceback on stderr and nothing on stdout — the same exit code as "the gate found findings". A skill or wrapper that checks only the return code reports a typo'd path as a content failure and sends the author to fix a sheet that was never read. A crash is distinguishable from a *pass* (0 is only printed with `PASS`), but not from a fail.
- **trigger**: A mistyped path in a skill's `python scripts/lint_*.py` instruction.
- **proposed_fix**: Catch `OSError` around both reads and return a distinct code (e.g. 3) with a one-line stdout message naming the unreadable path.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-95 · Exit code 2 is overloaded across usage error and unparseable input
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/lint_prompt_sheet.py:994-996`, `scripts/lint_prompt_sheet.py:1010`, `scripts/lint_script_language.py:513-515`
- **component**: linters
- **failure_mode**: latent
- **blast_radius**: argparse exits 2 on a usage error; both linters also return 2 for "no shots/VO lines parsed", and Gate C additionally for "Library missing" and "Library empty". Four distinct operator actions collapse into one code, distinguishable only by parsing prose from stdout versus stderr.
- **trigger**: Any automated caller branching on exit status.
- **proposed_fix**: Reserve 2 for argparse and assign distinct codes to unparseable-artifact and missing-dependency conditions, documenting them in each module docstring.
- **fix_cost**: S
- **depends_on_finding**: [C-94]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-96 · A wrong `--dir` or CWD silently reports "no prior version" and proposes v1
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/resolve_brief_version.py:39-40`, `scripts/resolve_brief_version.py:60-65`, `scripts/resolve_brief_version.py:70`, `scripts/resolve_brief_version.py:77`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `find_latest` returns `(None, 0)` for a nonexistent directory with no message, and `--dir` defaults to the CWD-relative `rgs-briefs`. Verified: against a missing directory, `--next` returned `2026-08-08-x-script.md`, version 1 — the exact filename of a live v1 brief. Ten skills instruct the model to run this from "the repo root"; a run from `pipeline-app/` or a worktree subdirectory produces a confident v1 answer over an existing brief. The `.claude/hooks/protect_briefs.py` Write-deny hook mitigates the overwrite inside Claude Code, but the version-numbering answer is still wrong and the supersedes chain silently restarts.
- **trigger**: Invoking from any directory other than the repo root, or a typo in `--dir`.
- **proposed_fix**: Error out when the target directory does not exist rather than returning `(None, 0)`, and echo the resolved absolute directory on every run.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-97 · Version ties resolve silently to whichever filename sorts first
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/resolve_brief_version.py:44-57`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: `if version > best_version` is strict, so among files declaring the same frontmatter `version` the first in `sorted(glob)` order wins with no warning. Verified: two matching briefs both at `version: 2` resolved to the earlier date. Dates are never compared, so a same-slug/same-kind pair written on different days but sharing a version number resolves by lexical filename accident — the downstream stage then reads the wrong upstream artifact and reports no problem.
- **trigger**: Two briefs with the same slug and kind carrying the same frontmatter version.
- **proposed_fix**: Treat a version tie as an error naming both paths; the resolver cannot correctly choose and should not guess.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-98 · `next_filename` never checks the proposed path, nor the `-vN` suffix against frontmatter
- **severity**: S1
- **confidence**: confirmed
- **evidence**: `scripts/resolve_brief_version.py:60-65`, `scripts/resolve_brief_version.py:33-35`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: The filename `-vN` suffix is captured by the pattern but the capture group is never used, so a file named `-v3` whose frontmatter says `version: 1` is accepted and reported as version 1 (verified). `next_filename` then computes N+1 from frontmatter alone and never tests whether the resulting path already exists — verified proposing `-v2` while `-v3` sat on disk. With a same-day write the proposed name is an existing brief's name. The version chain, which every stage's supersedes line depends on, silently regresses.
- **trigger**: Any brief whose frontmatter `version` drifts from its filename suffix.
- **proposed_fix**: Cross-check the `-vN` suffix against the frontmatter version and fail on mismatch; have `next_filename` reject a proposal whose path already exists.
- **fix_cost**: S
- **depends_on_finding**: [C-97]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-99 · `--date` is interpolated into the filename without validation
- **severity**: S3
- **confidence**: confirmed
- **evidence**: `scripts/resolve_brief_version.py:74`, `scripts/resolve_brief_version.py:60-65`, `scripts/resolve_brief_version.py:82`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: The help text says `YYYY-MM-DD` and the resolver's own `_pattern` requires `\d{4}-\d{2}-\d{2}`, but `next_filename` interpolates the string as given. Verified: `--date banana` returned `banana-do-less-sold-as-win-more-assembly-v4.md` with exit 0. A brief written under that name can never be found again by `find_latest`, so it drops out of the version chain permanently and the next `--next` call re-proposes a colliding number.
- **trigger**: A malformed or differently-formatted date passed by a skill.
- **proposed_fix**: Validate `--date` against the same `\d{4}-\d{2}-\d{2}` pattern the resolver already uses, and error on a mismatch.
- **fix_cost**: S
- **depends_on_finding**: [C-98]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-100 · Exit 1 means both "no prior version" and "a brief is malformed"
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/resolve_brief_version.py:86-91`, `scripts/resolve_brief_version.py:46-57`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: The normal, expected "nothing exists yet" answer prints `NONE\t0` and returns 1. An unhandled `ValueError` from missing frontmatter or a non-integer `version` also exits 1, with a traceback and no stdout. A caller that treats exit 1 as "no prior version" — which the printed contract invites — silently converts a corrupt brief into "start at v1", compounding C-96's overwrite path.
- **trigger**: A brief in `rgs-briefs/` missing frontmatter or carrying a string `version`.
- **proposed_fix**: Return 0 with `NONE\t0` for the expected empty case and reserve non-zero for genuine errors, or assign the two conditions distinct non-zero codes.
- **fix_cost**: S
- **depends_on_finding**: [C-96]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-101 · The plugin ships 11 skills while calling itself "Seven" in three places
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/build-cowork-plugin.sh:2`, `scripts/build-cowork-plugin.sh:34`, `scripts/build-cowork-plugin.sh:42-43`
- **component**: linters
- **failure_mode**: docs-drift
- **blast_radius**: `.claude/skills/` holds 13 trees; the script removes 2, shipping 11 = 8 pipeline + 3 specialists. The header comment says "the seven pipeline skills", the `plugin.json` `description` — which is what a Cowork user reads in the plugin list — says "Seven atomic, corpus-grounded skills", and the bundled README repeats it and omits `shorts-styleboard` from the pipeline chain entirely. `shorts-styleboard` is the stage that produces the world lock Gate C reads, so the shipped documentation describes a pipeline in which Gate C's primary input has no origin.
- **trigger**: Any user installing the plugin and reading its description.
- **proposed_fix**: Update the three strings to eight pipeline skills plus three specialists, add `shorts-styleboard` to the README chain, and derive the count from the copied directory listing so it cannot drift again.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: grep-sweep

### C-102 · plugin.json version is hard-pinned and the build is never verified
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/build-cowork-plugin.sh:30-37`, `scripts/build-cowork-plugin.sh:73`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: Every build writes `"version": "0.1.0"`, so an installed plugin's version string cannot distinguish today's build from one made months and many skill edits ago. Nothing validates the manifest (it is a static heredoc, so it is always well-formed JSON, but nothing checks it against what Cowork actually requires), and the only post-copy verification is a skill-directory count printed in the closing `echo` — never compared to an expected value, so a build that copied 9 skills reports success just as loudly as one that copied 11.
- **trigger**: Any rebuild after a skill is added, removed, or edited.
- **proposed_fix**: Derive the version from a repo signal (date or git describe), assert the copied skill count against an expected list, and validate the written JSON before zipping.
- **fix_cost**: S
- **depends_on_finding**: [C-101]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-103 · Nothing runs the build; a stale `.plugin` is undetectable
- **severity**: S2
- **confidence**: confirmed
- **evidence**: `scripts/build-cowork-plugin.sh:57-71`, `CLAUDE.md:181`, `CLAUDE.md:220-221`
- **component**: linters
- **failure_mode**: silent
- **blast_radius**: The repo has no CI (`.github/` contains only `PULL_REQUEST_TEMPLATE.md`), and the only references to the script are prose instructions in `CLAUDE.md` and two plan documents. `cowork-plugin/` and `dist/` are git-ignored, so the shipped artifact is not version-tracked and no diff, test, or hook detects that `.claude/skills/` has moved on since the last build. A Cowork user can be running skills several revisions behind the repo with nothing anywhere reporting it. The Gate C/D rules those skills instruct are exactly the content that goes stale.
- **trigger**: Editing any skill without remembering to rebuild.
- **proposed_fix**: Add a repo-root test that fails when `dist/content-studio.plugin` is older than the newest file under `.claude/skills/`, so the existing test suite surfaces staleness.
- **fix_cost**: S
- **depends_on_finding**: [C-102]
- **owner_task**: T10
- **detected_by**: manual-trace

### C-104 · The two archive branches produce different artifacts
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `scripts/build-cowork-plugin.sh:60-71`
- **component**: linters
- **failure_mode**: latent
- **blast_radius**: The `zip` branch excludes `*.DS_Store`; the PowerShell `Compress-Archive` branch has no exclusion, so the same source tree yields two different archives depending on the machine. Verified that `zip` is **not** installed on this operator's machine, so the unexcluded branch is the live one here. (Verified separately that `Compress-Archive` does include the dot-prefixed `.claude-plugin/` directory and does return exit 1 on failure, so `set -e` catches a genuine packaging error — those two plausible hazards are not real.)
- **trigger**: Building on a machine without `zip`.
- **proposed_fix**: Prune `.DS_Store` and other junk from the copied tree before packaging, so both branches archive an already-clean directory.
- **fix_cost**: S
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace

### C-105 · `scripts/__init__.py` creates the package-shadowing footgun the docs work around
- **severity**: S4
- **confidence**: confirmed
- **evidence**: `scripts/__init__.py:1`, `CLAUDE.md:232-237`
- **component**: linters
- **failure_mode**: latent
- **blast_radius**: The empty `__init__.py` makes the root `scripts/` an importable package so the root test suite can `from scripts.resolve_brief_version import …`. It is also the reason `pipeline-app`'s own `scripts/` package is shadowed when its suite is run from the repo root, which CLAUDE.md documents as a rule contributors must remember and two `pytest.ini` files exist to pin. A structural collision papered over by convention rather than removed.
- **trigger**: Running `python -m pytest` from the wrong directory.
- **proposed_fix**: Rename one of the two `scripts` packages, or move the root linters into a distinctly-named package, so the collision cannot occur and the two-suite rule becomes unnecessary.
- **fix_cost**: M
- **depends_on_finding**: []
- **owner_task**: T10
- **detected_by**: manual-trace
