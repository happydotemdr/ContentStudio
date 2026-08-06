# Midjourney Render Console — design

**Date:** 2026-08-06
**Status:** approved (design); implementation plan not yet written
**Scope:** one spec covering three subsystems — the ladder engine and render console, the
cross-project Style Library and `styleboard` stage, and the slot syntax with late binding.

---

## 1. Problem

Three problems, one system.

**The pipeline emits fake data.** `visual-prompts` writes style references like
`--sref SREF-RGS-A-DL01` (see `runs/do-less-20260728-190724/03-visual/artifact.v1.md`).
That is not a Midjourney style code. The skill invents a placeholder because it decides the
world lock and writes the shot prompts in the same turn, so no real code can exist yet.
Every sheet the pipeline has produced carries codes that cannot be pasted into Midjourney.

**Rendering is untracked manual labour.** Producing a Short means running ~16 prompts by
hand, downloading images, and renaming them into `Generated Assets/<run_id>/visuals/` and
`edit-ready/`. Nothing records which prompt produced which file, what it cost, or which
draft candidates were rejected and why.

**Style does not carry between Shorts.** Each sheet re-describes its worlds inline. There is
no place where "RaisingGoodSports / present-day youth soccer / Register A" is defined once
and reused, so consistency across a channel depends on prose being re-derived every time.

## 2. Constraints discovered during research

These shaped the design and are recorded because they are counter-intuitive and expensive to
rediscover. Web-verified 2026-08-06 unless noted.

**There is no official Midjourney API.** No public REST endpoint, SDK, webhook interface, or
API key system. Midjourney has announced it is *exploring* an enterprise API and hosts an
application form; no timeline and no pricing exist. Every product marketed as a "Midjourney
API" (Apiframe, PiAPI, CometAPI, ImaginePro, kie.ai) is a third-party wrapper that automates
the Discord bot or web app. Midjourney's Terms of Service prohibit automated access, and
accounts detected using automation are permanently banned. useapi.net, one of the larger
wrappers, discontinued Midjourney support in June 2026.

The consequence is that the risk to Midjourney spend is not only a runaway agent consuming
GPU minutes — it is losing the account, and with it every harvested `--sref` code, moodboard,
and personalization profile. **This system therefore never calls Midjourney.** A human runs
every prompt.

**`--oref` is incompatible with Draft Mode and Fast Mode**, is incompatible with `--q 4`, and
forces the whole job to render in V7 at 2× GPU cost. `--cref` is V6 legacy and does not apply
to V7/V8. Character identity therefore cannot ride along with a 24-image draft batch; it can
only enter after composition is chosen.

**Draft Mode gives 24 images at 512px for 0.4 GPU minutes**, and with `--sref random` every
thumbnail in the batch receives a *different* style code. This is the cheapest style
exploration Midjourney offers and is the foundation of the discovery ladder.

**V8.2 became the default model on 2026-07-24.** (The `--preview` flag was its pre-release
opt-in mechanism and is now historical.) **Niji 7** — released 2026-01-09, with no Niji 8 in
existence — is a *separate model line*, not a mode within V8.2. Niji 7 does support
Personalization and Moodboards. Selecting Niji for a world means that world's renders are not
V8.2 and its style codes are not interchangeable with V8.2 codes.

**Moodboard `--p` codes change as the board grows.** A code is only valid for the board's
current contents; adding images invalidates prompts that reference the old code.

**GPU costs** — draft 0.4, standard 0.8, HD 1.3 minutes, with `--q` acting as a multiplier —
are the facts most likely to go stale. `midjourney-prompting`'s own reference file flags them
as such. They are therefore configuration, not code (§7).

Attribution matters here, because these numbers gate spend: **draft 0.4 was verified
2026-08-06** by this research. **Standard 0.8 and HD 1.3 were not** — they carry forward from
`midjourney-prompting/references/v82-model-delta.md`, verified 2026-07-26. **Upscale Subtle
and Upscale Creative costs were not verified at all** and are unknown. `gpu_costs.yaml` must
therefore carry a per-entry `verified_on` date, and the upscale entries ship flagged
`unverified` so the console labels their estimates as such until someone checks (§13).

## 3. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Manual renderer behind a `Renderer` seam; no API calls | No official API exists; wrappers risk a permanent ban. The seam lets an official API drop in later without redesign. |
| D2 | App runs a style-discovery ladder, not just a code registry | The same ladder serves discovery and asset rendering; a registry alone leaves the hard part (finding codes that hold across subjects) unsolved. |
| D3 | Watch-folder ingest with prompt-text filename matching | Midjourney embeds prompt text in filenames. Eliminates the manual download-and-rename work that exists today. |
| D4 | Both a `styleboard` stage **and** generate-time late binding | The stage decides which Library entries a Short uses; late binding means re-locking a look is one binding change, not a sheet regeneration. |
| D5 | Draft probes derived deterministically from the dense prompt | The sheet stays the single source of truth. Derivation is re-runnable and hand-overridable per asset. |
| D6 | Cost estimate + ledger + soft per-project ceiling | Nothing auto-generates, so runaway spend is structurally impossible. What remains is visibility and self-discipline. |
| D7 | Niji 7 allowed as an explicit per-world opt-in | Real stylistic range for illustrative worlds, gated behind a deliberate choice that states the V8.2 trade-off. |
| D8 | One spec covering all three subsystems | The end-to-end workflow is the deliverable; the ladder engine is shared substrate that both consumers need. |

## 4. Architecture

One new surface in the existing FastAPI app, one new pipeline stage, no new services.

The console is **not** a stage. Stages are Claude-CLI turns that produce markdown artifacts
and are approved; the console is human clicks that produce images. Only `styleboard` is a
stage.

### 4.1 Stage topology change

`visual-prompts` currently decides the world lock *and* writes the shot prompts. That is the
direct cause of the fake-code bug: the world is invented in the same turn as the prompts that
need its codes.

```yaml
- id: styleboard
  skill: shorts-styleboard
  dir_prefix: "02b"
  depends_on: [scripting]

- id: visual
  skill: visual-prompts
  specialist: midjourney-prompting
  specialist_mode: auto
  dir_prefix: "03"
  depends_on: [scripting, styleboard]   # was [scripting]
```

`dir_prefix: "02b"` avoids renumbering existing run directories. Stage order in the nav comes
from `stage_defs` order, not from the prefix (see `build_stage_nav`), so `02b` sorts correctly
without migration.

`styleboard` owns: naming the registers and their worlds, binding each register to a Library
entry, and flagging any world with no entry as a discovery request. `visual` consumes the
world lock instead of deciding it.

The dual-register world-lock rules are corpus-derived. They **move wholesale into
`shorts-styleboard` with their `[C]` citations intact** — a relocation, not a rewrite. No new
unsourced normative lines are created by the split, preserving the anti-generic guarantee in
`CLAUDE.md`.

### 4.2 Data model

New SQLite tables in `pipeline-app/pipeline_app/schema.sql`, in three groups.

**Library — cross-project, survives every Short:**

- `worlds` — `(brand, world_key, register)` plus the descriptor block that today lives inline
  in each sheet's `WORLD LOCK`. Written once, reused.
- `style_entries` — `kind` ∈ `sref | moodboard_p | oref | personalization`; `model` ∈
  `v8.2 | niji7`; the code or hosted reference URL; label; rationale; a pointer to the
  `ladder_run` that produced it; `retired_at`. Entries are **retired, never deleted**, so
  historical sheets remain explicable.

**Per-project render state:**

- `render_projects` — binds a pipeline project to its sheet artifact path and sha256 (so a
  regenerated sheet is detectable) and to its GPU budget.
- `render_assets` — one row per shot, plus cover and plates. Holds the dense prompt, the
  derived probe, a `probe_overridden` flag, the unresolved slot map, and state.
- `ladder_runs` — **one row per human click that would cost GPU.** Rung, fully-resolved prompt
  string, params, model, estimated minutes, actual minutes, status.
- `ladder_images` — ingested files: grid index, flagged/selected state, sha256,
  `match_method`, `match_confidence`.

**Spend:**

- `spend_ledger` — append-only. `ladder_run_id` is **nullable** so generations made outside
  the app can be recorded and the monthly total stays honest.

`ladder_runs` is the center of the system. Every expensive action is a row there, created only
by a human click, carrying its estimate before it exists and its actual cost after. Spend
accounting, the ceiling check, the resolved-prompt display, and the ingest matcher all read
that one table. There is no second path to spending money.

### 4.3 Filesystem

`Generated Assets/<run_id>/` is the console's write root — the same `run_id` already shared
with `runs/<run_id>/`. Existing `visuals/`, `edit-ready/`, and `Audio/` are unchanged; the
console adds:

```
Generated Assets/<run_id>/
  _drafts/<asset_key>/NN.png      24-image draft batches
  _locks/<asset_key>/NN.png       full-resolution candidates
  _ledger.json                    human-readable mirror of spend
```

The DB is an **index over files, not the truth**. The filesystem stays browsable and survives
a lost database (§8).

`Generated Assets/` is currently untracked but absent from `.gitignore`. The console writes
hundreds of PNGs there, so **adding it to `.gitignore` is in scope.**

## 5. The ladder engine

Four rungs, identical for every asset and for style discovery.

| Rung | Prompt used | Result | Cost (fast minutes) |
|---|---|---|---|
| 1 · Draft | derived probe + `--draft --c 25 --weird 0` | 24 images @ 512px | 0.4 |
| 2 · Lock | dense prompt + `--sref` harvested from the winning draft | one full-res candidate per flagged draft | 0.8 SD / 1.3 HD each |
| 3 · Upscale | the selected lock, Subtle or Creative | final-resolution image | unverified — see §2 |
| 4 · Capture | — | filed into `visuals/` and `edit-ready/` | 0 |

**Rung 2 is a fresh submission, not Midjourney's Vary button.** This is the only path that
lets the dense prompt, the real `--sref`, and `--oref` enter — none of which can ride along on
a draft. It matches `midjourney-prompting`'s Phase 2 exactly, so it rests on verified guidance
rather than inferred UI behaviour. A human who prefers Vary for a given shot records the
result identically; the console does not require either route.

**`--oref` enters only at rung 2, and announces its cost.** Binding a character reference
shows, in the confirm dialog: incompatible with Draft and Fast Mode, incompatible with `--q 4`,
and forces V7 at 2× GPU cost.

**Chaos and weird.** Rung 1 defaults to `--c 25 --weird 0` — wide compositional variance,
zero weirdness — per the brief's requirement for 24 differentiated starting points without
the incoherence that `--weird` introduces. Both are per-asset overridable.

### 5.1 The observability problem

The app cannot see Midjourney, so it cannot know a prompt was actually run. Pretending
otherwise would make the ledger fiction.

The generate control is therefore **"Copy prompt & mark launched"**: one click copies the
resolved string to the clipboard and opens a `ladder_run` at `awaiting_capture`, debiting the
estimate immediately. A **"didn't run"** action voids the row and refunds the estimate. Actual
minutes are reconciled when images land. Every ledger row records whether its cost is
`estimated` or `reconciled`; an estimate is never displayed as a fact.

### 5.2 Asset states

`pending → drafted → flagged → locked → selected → upscaled → captured`

Plus `blocked` (an unresolved slot) and `superseded` (the sheet's sha256 changed underneath —
the same staleness mechanic `state_machine.is_stale` already implements for stages).

### 5.3 Ladder run states

`composed → awaiting_capture → captured`, plus `voided` (the "didn't run" path, which refunds
the estimate) and `abandoned` (no images ever captured, closed manually).

There is deliberately no separate `launched` state. The app cannot observe a launch (§5.1);
the human's click *is* the launch, and it moves the run straight to `awaiting_capture`. A
state the system can never confirm entering would be fiction.

## 6. Style Library and discovery

Discovery is the same four rungs with a different terminus: it captures a **code**, not a file.

**Rung 1** runs a short *world* probe — describing the world, not a specific shot — as
`--draft --sref random`. Because every thumbnail in a Draft Mode batch receives a different
style code, one 0.4-minute click samples 24 distinct aesthetics for that world.

**Rung 2 is the step that makes codes reusable.** For each flagged candidate code, the console
runs **three different subjects from the same world** through it — a figure, an environment,
and a macro artifact. A code that holds only on the composition that spawned it is useless for
a 16-shot Short; this finds that out for ~2.4 minutes instead of at shot 11.

**Rungs 3–4** write the winner to `style_entries` with the sample images that justify it and
the human's rationale.

### 6.1 Entry kinds

- **`sref`** — fully covered by the ladder above.
- **`oref`** — character lock. Generate the character, capture the winner, drag it into
  Midjourney's prompt bar to obtain a hosted URL, store URL plus a default `--ow`. (For
  RaisingGoodSports the anonymous-presence rule usually means there is nothing to `--oref`;
  supported, never forced.)
- **`personalization`** — the account's global profile. V7 profiles are compatible with V8.2.
  Recorded as a per-account singleton, opted into per world.
- **`moodboard_p`** — **does not fit the ladder.** Moodboards are built by uploading images in
  Midjourney's UI, not by prompting. The console helps assemble the image set, pulling flagged
  images from anywhere in the Library; the human uploads them and pastes the `--p m…` code
  back. The entry stores the resolved code and a hard warning that adding images later
  invalidates every sheet referencing it.

### 6.2 Slot syntax and late binding

The sheet writes `{style:register_a}`; the console expands it to whatever the binding needs:

| Binding kind | Expands to |
|---|---|
| `sref` (v8.2) | `--sref <code>` |
| `sref` (niji7) | `--niji 7 --sref <code>` |
| `moodboard_p` | `--p <code>` |
| `personalization` | *(nothing — the account profile applies implicitly)* |

Characters use `{char:<name>}` → `--oref <url> --ow <n>`.

The token expands to the **entire flag group, not a bare value.** That is what keeps the sheet
ignorant of which mechanism a world uses, and is what makes re-locking a Short's whole look a
single binding change with no sheet regeneration.

### 6.3 Probe derivation (D5)

Deterministic reduction of the dense prompt: strip optics/lens/f-stop, lighting mechanics,
fine surface texture, and `--raw`; keep medium, subject, action/state, environment, and
register; append `--draft --c 25 --weird 0`. The result is displayed before generation and is
hand-overridable per asset, with `probe_overridden` recording that a human intervened.

## 7. Spend control

**Costs are configuration, not code.** `pipeline-app/gpu_costs.yaml` holds the draft/SD/HD
figures, the `--q` multipliers, the `--oref` V7 penalty, and a `verified_on` date. Because
`midjourney-prompting` flags these as its most staleness-prone facts, the console renders
`verified_on` next to the budget — a three-month-old date is visible before it is trusted.

**Three guardrails, none of which blocks mid-flow:**

1. **Per-project soft ceiling**, set when rendering starts. Warns at 80%. Above 100%, the
   overage must be typed to confirm.
2. **Per-click sanity guard**: any single action estimated above 5 GPU-minutes requires a
   confirm regardless of remaining budget. This is what catches "lock all 24 drafts" as a
   misclick.
3. **Batch aggregate display**: batch actions always show the total ("lock 6 flagged →
   4.8 min") before the confirm, never the per-item cost alone.

## 8. Console, ingest, and error handling

### 8.1 Routes and layout

- `/projects/{id}/studio` — per-project console.
- `/studio/library` — cross-project Library.

The console shows one row per asset in sheet order, carrying its identity from the sheet
(beat · register · shot class · scale · camera height), a state badge, and a four-chip ladder
rail. Expanding a row reveals three things, per the brief's requirement that the human always
sees the real prompt:

1. the **fully-resolved prompt in monospace** — character-for-character what goes to Midjourney;
2. the derived probe, with an edit affordance;
3. the slot bindings, showing what each `{style:…}` expanded to and why.

The draft grid is 24 click-to-flag thumbnails with a running
"Lock N flagged → X.X min" action that never fires without a confirm.

The Library page groups entries brand → world → register, each showing sample images, code,
model badge, and how many projects depend on it — so retiring an entry states what it breaks
before it breaks it.

### 8.2 Ingest

A stdlib poller (2-second interval; no `watchdog` dependency) over a configured Midjourney
download directory.

Midjourney embeds prompt text in output filenames. The matcher strips the username prefix and
uuid suffix, normalizes underscores to words, and scores the remainder against the prompt body
of every `ladder_run` at `awaiting_capture`. Every image records `match_method`
(`filename` | `manual`) and `match_confidence`, so a bad auto-file is findable.

Two concrete thresholds, both configurable: a file auto-files only at **≥ 0.75** normalized
token-overlap against the best-scoring run, and only if that best score beats the runner-up by
**≥ 0.15**. Failing either — too weak a match, or two runs too close to separate — sends the
file to an **unmatched tray** for one-click assignment. The margin rule matters because a
Short's shots share heavy vocabulary (the `do-less` sheet repeats "documentary sports
photography … youth soccer …" across six Register A shots), so absolute score alone would
mis-file confidently.

Grid index is arrival order within a run; Midjourney does not guarantee grid order on
download, and flagging is per image rather than per index, so this is sufficient.

**Files are copied, not moved.** The app never touches originals in the download directory.
They land in `_drafts/<asset_key>/NN.png`, promote to `_locks/`, and at capture are renamed
into `visuals/` and `edit-ready/cutNN_<slug>.png`, matching the convention already present in
`Generated Assets/do-less-20260728-190724/edit-ready/`.

A per-step drop zone is always available as a fallback path.

### 8.3 Error handling

| Case | Behaviour |
|---|---|
| Sheet regenerated mid-render | Affected assets flip `superseded`; console shows which shots changed; human re-adopts per shot. Flagged and locked work is never silently discarded. |
| Unresolved slot | Asset sits `blocked`; generate disabled; reason states which world and register has no entry. |
| Download directory unreadable | Banner; drop-zone fallback remains available. |
| Ambiguous filename match | Unmatched tray, never a guess. |
| Ledger drift | Reconcile view accepts actual minutes from Midjourney's usage page as a manual adjustment — the reason `spend_ledger.ladder_run_id` is nullable. |
| DB lost or corrupted | Rebuild command re-scans `Generated Assets/<run_id>/` and reconstructs rows from disk. |

## 9. Gate C changes

`scripts/lint_prompt_sheet.py` gains four checks:

1. Accept `{style:…}` and `{char:…}` as valid flag-position tokens.
2. Require every referenced slot to be declared in the sheet's `WORLD LOCK` block. Declaration
   keys follow the block's existing `^\s+[a-z][a-z0-9_]*:\s*value$` shape that
   `WORLD_ENTRY_RE` already matches, named `slot_<name>` — so `{style:register_a}` requires a
   `slot_register_a:` line naming the Library entry label it binds to, and `{char:coach}`
   requires `slot_char_coach:`. No parser change is needed for the block itself.
3. Parse the `COVER / THUMBNAIL` prompt as a first-class asset. `parse_sheet()` currently
   matches only `### Shot` headings and walks past the cover, so the cover has never been
   linted.
4. **Reject any `--sref` value that is not numeric, a URL, or `random`.** This makes
   `SREF-RGS-A-DL01` impossible to reintroduce — the exact defect that motivated this work.

## 10. Module layout

Kept small and single-purpose to match the existing app rather than one large
`studio_service.py`:

```
pipeline_app/probe_derivation.py    dense prompt -> draft probe
pipeline_app/slot_resolution.py     {style:...} / {char:...} -> flag groups
pipeline_app/gpu_cost.py            estimation from gpu_costs.yaml
pipeline_app/ladder_service.py      rung transitions, launch/void/capture
pipeline_app/ingest_watcher.py      download-directory poller
pipeline_app/ingest_matcher.py      filename -> ladder_run scoring
pipeline_app/library_service.py     worlds and style_entries CRUD
pipeline_app/routes/studio.py       per-project console
pipeline_app/routes/library.py      cross-project Library
```

The console imports `parse_sheet()` from `scripts/lint_prompt_sheet.py` rather than growing a
second parser for the same format.

## 11. Testing

Follows the existing pytest + `tmp_path` + temporary-DB pattern in `pipeline-app/tests/`.

**Fixtures must be committed, not read from `runs/`.** `runs/` is git-ignored, so a suite that
reads `runs/do-less-20260728-190724/03-visual/artifact.v1.md` directly would pass on this
machine and fail everywhere else. The sheet is copied once into
`pipeline-app/tests/fixtures/do_less_visual_sheet.md` and committed, along with a small set of
real Midjourney output filenames in `pipeline-app/tests/fixtures/mj_filenames.txt`. Tests read
only from `tests/fixtures/`.

**Unit, table-driven, using the committed `do-less` prompts as fixtures:**
- probe derivation from dense prompts;
- slot expansion across all four entry kinds, including the Niji 7 variant;
- cost estimation including the `--oref`→V7 2× penalty and `--q` multipliers;
- matcher scoring against real Midjourney output filenames.

**Gate C:** tests for all four new checks, including a regression asserting that
`--sref SREF-RGS-A-DL01` fails.

**Ladder state machine:** rung transitions, void-and-refund, ceiling warn versus typed
confirm, per-click sanity guard.

**Integration:** build a render project from the committed
`tests/fixtures/do_less_visual_sheet.md`, walk one asset through all four rungs against a fake
watch directory, and assert files land at the expected paths and the ledger balances.

No test can reach Midjourney, because no code path in the application can.

## 12. Out of scope

- Any call to Midjourney, official or third-party (D1). The `Renderer` seam exists so this can
  change without redesign; it is not exercised.
- Image-to-video and motion prompts — these remain `visual-prompts`' responsibility.
- Changes to `voiceover`, `assembly`, or `repurpose` stages.
- Automatic upload of moodboard image sets to Midjourney (§6.1) — the human uploads and pastes
  the code back.

## 13. Facts to re-verify before implementation

Every `[T]` fact in §2 was verified 2026-08-06 against public sources and Midjourney's
documentation. The following change fastest and should be re-checked when implementation
starts:

- Whether an official or enterprise API has become available (would change D1 materially).
- GPU costs: draft 0.4 / SD 0.8 / HD 1.3, and the `--q` multipliers.
- Whether `--oref` still forces a V7 fallback, or a native V8 Omni Reference has shipped.
- Draft Mode's 24-image / 512px shape and its per-thumbnail style-code behaviour.
- Midjourney's download filename format, on which §8.2's matcher depends.
