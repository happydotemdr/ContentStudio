---
name: elevenlabs-audio
description: Builds a complete, ready-to-run ElevenLabs configuration — voice profile, model routing, voice settings, tag-annotated directorial script, PLS pronunciation dictionary, JSON request payload, curl command, and credit estimate — from a simple set of inputs, with fresh-agent validation gates before anything is rendered. Use whenever the user is generating speech with ElevenLabs and needs the actual setup rather than creative direction: "which ElevenLabs model should I use," "write me the API payload / request body," "what stability and similarity settings," "why does my TTS sound robotic / slurred / monotone," "why are my audio tags being ignored," "how do I stop it mispronouncing this word," "make me a pronunciation dictionary," "clone a voice," "explore/pick a voice," "narrate this audiobook chapter / script / ad," "set up multi-speaker dialogue," "how do I not burn credits iterating." Works standalone for any audio job (audiobook, agent, ad, character dialogue, podcast) AND as the downstream specialist for ContentStudio's `voiceover-brief` skill, which hands down the creative call for a Short and leaves the executable configuration to this skill. Do not use this to make the creative call — which voice a ContentStudio Short should use and why, the tone per beat, the content-type framing, or the loudness/ducking mix are all `voiceover-brief`; this skill converts those into an executable configuration and compatibility-checks the model, settings and tags it is handed. Nor to write the script's content (that is `shorts-scripting`).
---

# ElevenLabs Audio (configuration, prompting & credit discipline)

Turns an audio job into an **executable ElevenLabs setup**: the model, the settings, the tagged
script, the dictionary, the payload, and what it will cost — validated by fresh agents before a
single credit is spent.

## Pipeline position — this skill runs in two modes

**Standalone.** Any audio job, ContentStudio-related or not: an audiobook chapter, a conversational
agent, an ad read, a game character, a podcast intro. Run the full four-stage workflow from Stage A.

**Pipeline (ContentStudio Shorts).** `voiceover-brief` (a stage of ContentStudio's eight-skill
pipeline, following `shorts-scripting`) hands down the corpus-grounded **creative** call: voice
character, tone per beat, content type, and the
−14 LUFS mix target. **Accept that call and do not re-litigate it.** Your job is to convert it into
a working configuration. Enter at Stage B with the voice and tone already decided.

The boundary, stated once so neither skill drifts into the other:

| `voiceover-brief` owns (the call) | `elevenlabs-audio` owns (the execution) |
|---|---|
| Which voice, and why (the shadowban/default-voice reasoning) | The feature-compatibility check that confirms the voice/model pairing renders |
| Tone and delivery intent per beat | The tag syntax that actually produces that delivery |
| Content-type framing | The settings floats / stability mode |
| −14 LUFS target, music ducking, the mix | The request payload, dictionaries, chunking, credit spend |

**Three of those rows arrive partly filled, and you must compatibility-check them rather than
accept them blind** `[I]`. `voiceover-brief` step 2 names a model, step 3 sets the four settings
plus speaker boost, and step 4 places v3 audio tags and phonetic respellings. Treat each as an
**upstream input under review**, not a decided call:

- **Model.** If the named `model_id` cannot render a feature the brief also asks for (a v3-only
  tag on a v2 model, a dictionary on an engine that ignores it), say so and route to the model
  that can. Name the override in `MODEL ROUTING`.
- **Settings.** If a float is out of range for the routed model, or a stability *mode* is named
  where the model takes a float (or vice versa), convert it and say what you converted.
- **Tags.** If a placed tag is not in the routed model's tag catalog, replace it with the nearest
  supported tag or fold the intent into the settings, and say which.

**Do not re-litigate the voice, the tone per beat, the content type, or the mix.** Those four
rows are decided upstream, full stop — that is the "accept the call" rule, and it is scoped to
exactly those four. Loudness and ducking stay with `voiceover-brief`
(`.claude/skills/voiceover-brief/references/production-and-loudness.md`) — do not duplicate or
contradict them here. Downstream of both: `shorts-assembly`.

## Grounding — read before writing any rule

Two sources, deliberately separate:

- **`docs/elevenlabs-production-runbook.md`** — platform truth. Engines, parameters, tags,
  dictionaries, credits. Web-verified against live ElevenLabs docs **2026-07-26**.
- **`docs/elevenlabs-voiceover-guide.md`** — the corpus view (24 findings). Thin, and honest about it.

Markers, copied verbatim wherever a rule is repeated:

- **`[T]`** web-verified 2026-07-26 · **`[T-unverified]`** asserted by the supplied enterprise
  runbook but **not** confirmed — say so out loud when you use one · **`[I]`** general practice ·
  **`[C]`** corpus-cited `(Channel, video_id)`.

**A normative line with no marker means something was invented instead of sourced.** If the sources
don't cover it, say the gap exists and give a marked `[I]` extrapolation — never a confident
unsourced number. The supplied enterprise runbook that seeded this material was **wrong in eight
places** (`docs/elevenlabs-production-runbook.md` §10); treat plausible-sounding ElevenLabs "facts"
from memory with the same suspicion.

## The control surface — the only inputs you need

Collect these eight. Everything else is derived. **If the user gives you none of them, infer what
you can from the job and then state every default you assumed** — never choose silently.

| Input | Values | Drives |
|---|---|---|
| `phase` | `draft` \| `master` | model tier, `output_format`, excerpt vs. full text |
| `use_case` | `shorts-vo` \| `long-form-narration` \| `character-dialogue` \| `conversational-agent` \| `ad-promo` | model routing, settings band |
| `expressiveness` | `1`–`5` | one dial → stability (or v3 mode) + style |
| `voice` | a `voice_id`, a saved Voice Profile Card, or `explore` | Stage A entry point |
| `language` | ISO 639-1 | eligible models; phoneme availability |
| `length` | characters or minutes | chunking + stitching requirement |
| `privacy` | `standard` \| `zero-retention` | `enable_logging` |
| `determinism` | `on` \| `off` | `seed` |

The full mapping tables — input → `model_id`, settings, `output_format` — are in
`references/control-surface.md`. They are deterministic: the same inputs must always produce the
same configuration, so a user can re-run and get a reproducible setup.

## Workflow — four stages, gated

### Stage A — Voice profile

Skip if the user supplied a `voice_id` or a Voice Profile Card. Otherwise read
`references/voice-profiles.md`:

- `voice: explore` → shortlist candidate voices against the job, and say what each is for. Explore
  on **Flash v2.5 with a 250–500 character excerpt** — never audition voices on the flagship.
- Cloning → IVC (≈1–2 min clean reference, most plans) vs. PVC (30 min–3 hr, **Creator+**) `[T]`.
- If the job is v3 and the voice is a PVC: **say the caveat.** PVCs are "not fully optimized for
  Eleven v3" `[T]`; `use_pvc_as_ivc` is an opt-in boolean, **not** an automatic fallback.
- **Tag effectiveness is bounded by the voice's training data** `[T]` — "don't expect a whispering
  voice to suddenly shout with a `[shout]` tag." Voice choice constrains Stage B; do it first.

Emit a **Voice Profile Card** the user can paste back later to skip straight to Stage C.

### Stage B — Directorial script

Read `references/directorial-prompting.md`. Build the text in five layers: structural punctuation →
primary emotion → delivery modifier → acoustic event → role directive `[I]`.

**Check the feature-compatibility matrix before writing a single tag** (`references/model-routing.md`).
This is the most common silent failure on the platform: tags and phonemes sent to a model that
ignores them **do not error — they are dropped, and the audio comes back subtly wrong** `[T]`.

- Audio tags: **`eleven_v3` only** `[T]`
- Inline IPA in `/slashes/`: **`eleven_v3` only** `[T]`
- On v3, **Robust stability mode suppresses tags** `[T]` — tags plus Robust is a contradiction
- Multi-speaker is a **different endpoint** (`/v1/text-to-dialogue/convert`, v3-only, JSON array of
  `{text, voice_id}` turns, **≤2,000 chars total**) `[T]` — not inline `Speaker A:` labels
- **No closing-tag syntax exists** `[T]` — never write `[/whispers]`
- Capitalization and punctuation steer delivery on **every** model `[T]`; tags work on one. Reach
  for punctuation first.

Chunk the text to the model's cap, splitting on natural sentence breaks, and carry stitching
context across every seam (Stage C wires it).

**→ Validation Gate 1.**

### Stage C — Config, payload & dictionaries

Read `references/api-payload.md` and `references/pronunciation-dictionaries.md`.

- Settings from the control surface. **On v3, stability is three discrete modes — Creative /
  Natural / Robust — not a float** `[T]`. Natural is the default choice for tagged narration.
- Set `model_id` **explicitly**: the API default is `eleven_multilingual_v2`, not the flagship `[T]`.
- `output_format` by phase, respecting the tier gates — `mp3_44100_192` needs Creator+, PCM/WAV
  44.1 kHz needs Pro+ `[T]`.
- Chunking: prefer `previous_request_ids` (max 3, anchors to real audio) over
  `previous_text`/`next_text` `[T]`. **`enable_logging: false` disables request stitching** `[T]` —
  if the job is zero-retention *and* long, say the conflict out loud and fall back to text context.
- Pronunciation: `<phoneme>` works on **`eleven_v3` and `eleven_flash_v2` only** `[T]`. Everything
  else — including Flash v2.5 and Multilingual v2 — needs `<alias>`. PLS matching is
  **case-sensitive**: enumerate lowercase, Title Case, and UPPERCASE `[T]`. Max 3 locators `[T]`.
  Pin `version_id` in production `[I]`.
- Numbers, dates, currencies, URLs: **pre-convert them in the text** — most reliable fix `[T]`.

**→ Validation Gate 2.**

### Stage D — QC, cost & credit discipline

Read `references/cost-and-credits.md` and `references/voice-settings.md` §artifact table.

**The two-phase protocol is a hard default, not a suggestion.** Do not emit a master payload on
`eleven_v3` or `eleven_multilingual_v2` until a Flash draft payload has been emitted and the user
has confirmed the direction. If the user asks for a master render immediately, produce the draft
payload first and explain why in one line — then produce the master once they confirm.

- Draft: `eleven_flash_v2_5`, `mp3_22050_32`, **250–500 characters** covering only the passages
  actually in question `[T]`/`[I]`
- Master: `eleven_v3` or `eleven_multilingual_v2`, `mp3_44100_192`/`pcm_44100`, fixed `seed`,
  `version_id` pinned

**State the two honest limits of the draft phase** `[I]` rather than overselling it: Flash v2.5
renders **no audio tags and no phonemes** (§1.2), so a Flash draft validates text, pacing, and
voice fit but **not tag execution** — budget one short v3 probe for tag-heavy scripts. And Flash
handles numbers less naturally than the larger models `[T]`, so a normalization problem in the
draft may be a Flash artifact rather than a script defect.

**Assume every API call is billed.** The two free regenerations are **website-only and explicitly
not available via the API** `[T]`. If the user wants free re-rolls while tuning sliders on fixed
text, tell them to do that tuning in the web UI and port the settled values into the payload.

Diagnose bad output against the artifact → cause → fix table before touching settings — check the
two free things first: **is the model right, and is the text itself the problem?** `[I]`

**→ Validation Gate 3 (pre-master spend gate).**

## Fresh-agent validation gates

Each gate dispatches a **fresh `general-purpose` agent** that has not seen your authoring
rationale, so it checks the artifact rather than rubber-stamping the reasoning. The verbatim
dispatch prompts and full checklists are in `references/validation-gates.md` — use them as written;
each already embeds the repo's sub-agent output contract.

| Gate | Fires | Checks |
|---|---|---|
| **1 — Script & tag** | after Stage B | tags exist and are model-supported; no invented closing tags; no inline speaker labels outside Text-to-Dialogue; chunk sizes under the cap; ≤2,000 chars for dialogue; text reads aloud cleanly; numbers/URLs pre-normalized |
| **2 — Payload** | after Stage C | every param in range; model↔feature compatibility; `output_format` matches phase and tier; `enable_logging` matches `privacy`; the zero-retention ↔ stitching conflict; `seed` present when `determinism: on`; every seam carries stitching context; ≤3 locators; PLS case variants covered; `<phoneme>` only on v3/flash_v2 |
| **3 — Pre-master spend** | before any master payload | a draft was rendered and confirmed; credit estimate stated; master text is the approved draft text; re-roll budget named; no reliance on non-existent API free retries |

**Gates 1 and 2 are independent — dispatch them in parallel** (single message, two tool calls) once
both artifacts exist. **A gate returning findings blocks emission** until resolved or explicitly
overridden by the user. Report gate results in the output; never claim a gate passed without
running it.

## Output contract

Emit one **AUDIO PRODUCTION SPEC** with these sections, in this order. Omit a section only when it
genuinely does not apply, and say why rather than dropping it silently.

```
=== AUDIO PRODUCTION SPEC — [job name] — [DRAFT | MASTER] ===

CONTROL SURFACE
  phase / use_case / expressiveness / voice / language / length / privacy / determinism
  Assumed defaults: [every value you chose for the user, named explicitly]

VOICE PROFILE
  voice_id · name · IVC|PVC|library · persona · known-good tags · caveats

MODEL ROUTING
  model_id: [...]  — why, and the feature check that confirms it (tags? phonemes? dialogue?)

VOICE SETTINGS
  | stability (or v3 mode) | similarity_boost | style | speed | use_speaker_boost |

DIRECTORIAL SCRIPT
  [tagged text, chunked, each chunk with its previous_text/next_text or previous_request_ids
   slot; annotate what each tag is doing and why]

PRONUNCIATION
  [inline IPA (v3) and/or PLS XML + locator wiring — or "none needed", stated explicitly]

REQUEST PAYLOAD
  [JSON body + query params]
  [curl command]

COST
  Draft: [chars] × [rate] = [estimate]   Master: [chars] × [rate] = [estimate]
  Note: API calls are billed; no free regenerations via API [T]

QC CHECKLIST
  [what to listen for on playback, and the parameter fix for each symptom]

VALIDATION GATES
  Gate 1: [pass | findings]   Gate 2: [pass | findings]   Gate 3: [pass | findings | n/a]

NEXT
  [draft → confirm → master. Then hand this spec to `shorts-assembly` as its optional input 2b:
   it reads the DIRECTORIAL SCRIPT's chunk boundaries and the rendered asset filename.]
```

## Handoff contract (machine-checked)

```handoff
produces.kind: audio-spec
produces.stage: 03-voiceover
produces.section: CONTROL SURFACE
produces.section: VOICE PROFILE
produces.section: MODEL ROUTING
produces.section: VOICE SETTINGS
produces.section: DIRECTORIAL SCRIPT
produces.section: PRONUNCIATION
produces.section: REQUEST PAYLOAD
produces.section: COST
produces.section: QC CHECKLIST
produces.section: VALIDATION GATES
produces.section: NEXT
consumes: voiceover-brief#Voice pick
consumes: voiceover-brief#Tone per beat
consumes: voiceover-brief#Settings
consumes: voiceover-brief#Script, reformatted for TTS
```

## What this skill does NOT do

- **Call the ElevenLabs API.** It emits payloads and curl commands; you run them. It never handles
  an API key, never renders audio, and never spends credits on its own.
- **Loudness, ducking, or the music mix** — `voiceover-brief`.
- **Decide a Short's voice character or creative tone** in pipeline mode — `voiceover-brief` already did.
- **Write the script's content** — `shorts-scripting`.
- **Visuals** — `visual-prompts`. **Edit/assembly** — `shorts-assembly`.

## `[T]` facts most likely to be stale — re-verify before relying on them

These moved recently or are the kind that move often (`docs/elevenlabs-production-runbook.md` §10):

- Model IDs and character caps (5,000 / 10,000 / 40,000), and whether a newer flagship has shipped.
- Pricing, the Flash/Turbo 50% discount, and the per-character rate.
- The v3 stability mode names (Creative / Natural / Robust) — recently replaced a float slider.
- **Phoneme-tag model support** — currently `eleven_v3` + `eleven_flash_v2` only, and the
  runbook-sourced claim that Flash v2.5 supports them is **wrong**.
- The free-regeneration policy — website-only, not API.
- PVC-on-v3 optimization status, and whether `use_pvc_as_ivc` is still needed.
- `output_format` tier gates (Creator+ / Pro+) and the Text-to-Dialogue 2,000-character ceiling.
- `eleven_turbo_v2_5`'s specs — it was absent from the models overview page at verification.

Anything marked **`[T-unverified]`** — all latency envelopes except Flash's ~75 ms, per-minute
pricing, and every specific numeric settings band — should be presented as a starting point, never
as a fact.

## Reference files

- `references/control-surface.md` — the eight inputs and the deterministic mapping tables. Start here.
- `references/model-routing.md` — model table + the feature-compatibility matrix.
- `references/voice-profiles.md` — exploration, IVC vs. PVC, the Voice Profile Card schema.
- `references/directorial-prompting.md` — five layers, verified tag catalog, dialogue, the voice constraint.
- `references/voice-settings.md` — ranges, v3 modes, per-use-case bands, artifact → cause → fix.
- `references/api-payload.md` — full parameter surface, JSON/curl templates, chunking and stitching.
- `references/pronunciation-dictionaries.md` — inline IPA vs. PLS, alias fallback, case variants.
- `references/cost-and-credits.md` — billing basis, two-phase protocol, the free-regeneration truth.
- `references/validation-gates.md` — the three verbatim fresh-agent dispatch prompts.
- `references/worked-example.md` — one job end to end: inputs → draft → gates → master.

## File I/O contract

**App-driven** (a `pipeline-app` turn already told you an output path): follow that instruction
exactly — write only to the named path, overwrite it each turn as instructed.

**Standalone** (no output path was given): run
`python scripts/resolve_brief_version.py --slug <slug> --kind audio-spec --next --date <YYYY-MM-DD>`
and write the AUDIO PRODUCTION SPEC at `rgs-briefs/<filename>` with this frontmatter:

```yaml
---
date: <YYYY-MM-DD>
kind: audio-spec
slug: <slug>
stage: 03-voiceover
version: <version from the resolver>
supersedes: <path from the plain (non---next) resolver call — only if version > 1>
voiceover_brief: <the voiceover brief's path, exactly as the resolver printed it>
status: complete
---
```

State the exact file path in your final chat response. **Outside a ContentStudio Short there is no
slug and no `rgs-briefs/`** — emit the spec in chat and say so explicitly, so the operator knows
it is transcript-only and must be pasted into whatever record they keep `[I]`.

Never edit an existing `rgs-briefs/*.md` file — a `PreToolUse` hook enforces this.
