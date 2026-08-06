# Midjourney Render Console — design

**Date:** 2026-08-06
**Status:** approved (design); implementation plan not yet written
**Scope:** one spec covering three subsystems — the ladder engine and render console, the
cross-project Style Library and `styleboard` stage, and the slot syntax with late binding.
Implemented as **two strictly ordered plans**; see §12.

**Revision:** amended 2026-08-06 after an adversarial review. Corrections are marked inline
where they overturn an earlier claim, rather than being silently rewritten — the largest was a
false `[I]`→`[C]` provenance upgrade in §4.1.

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
`unverified` so the console labels their estimates as such until someone checks (§14).

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
| D8 | One spec, two ordered implementation plans | The end-to-end workflow is the deliverable and the three subsystems are too coupled to design separately; but the contract changes must land before the console is built against them (§12). |

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

**Provenance of what moves — stated correctly.** An earlier draft of this spec claimed the
world-lock rules are corpus-derived and move "with their `[C]` citations intact." That is
false, and the correction matters in a repo whose central rule is that an unmarked normative
line is a bug. `visual-prompts/SKILL.md` says twice, explicitly, that the register system, its
shot-class taxonomy, and the arc-first sequencing discipline are **this skill's own
operational design `[I]`** — "the corpus has nothing to say about pairing a present-day
register with a source-era register." There are no `[C]` citations on these rules to preserve.

What actually moves is `[I]` material, and it must arrive in `shorts-styleboard` still marked
`[I]`, with the same explicit disclaimer that the corpus does not back it. The `[T]` Midjourney
parameter bands the register files cite move with their verification dates. Nothing may be
silently upgraded to `[C]` by the relocation — that would be exactly the failure mode
`CLAUDE.md`'s anti-generic guarantee exists to prevent.

**Existing projects require a DB backfill.** `project_service.create_project` materializes
stage rows once, at project creation. Projects created before this change will have no
`styleboard` row, and `state_machine.stages_to_unlock` requires *all* declared dependencies to
be approved — so `visual` could never unlock for them. A migration must insert a `styleboard`
row for every existing project whose brand scope includes it, at status `approved` with a
synthetic artifact carrying that project's world lock lifted from its existing visual sheet
(or at `ready` for projects that never reached `visual`). Untested against real projects, this
silently wedges every prior run.

**Stage templates are in scope and were omitted.** `prompt_builder.render_kickoff_prompt`
requires one template per stage id, so `pipeline-app/stage_templates/styleboard.md` must be
created. Separately, `stage_templates/visual.md` currently renders `{{ input_file }}` —
singular, the *first* upstream only. With two dependencies, the styleboard artifact would be
hashed into `visual`'s frontmatter and never shown to the model. `visual.md` must be rewritten
to iterate `{{ input_files }}`, naming each upstream by stage.

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
| 1 · Draft | derived probe + bound `{style:…}` + `--draft --c 25 --weird 0` | 24 images @ 512px | 0.4 |
| 2 · Lock | dense prompt + bound `{style:…}` (+ `{char:…}` if any) | one full-res candidate per flagged draft | 0.8 SD / 1.3 HD each |
| 3 · Upscale | the selected lock, Subtle or Creative | final-resolution image | unverified — see §2 |
| 4 · Capture | — | filed into `visuals/` and `edit-ready/` | 0 |

**Asset rendering and discovery take their style from different places — do not conflate
them.** In *asset* rendering (this section) the style code comes from the Library binding
resolved at generate time (§6.2), and it is present from **rung 1 onward** — drafting
off-style would make flagging worthless, since you would be choosing compositions under an
aesthetic the final render won't have. Harvesting a code from a winning draft is the
*discovery* flow (§6) and happens only there. An earlier draft of this spec described rung 2
as using "`--sref` harvested from the winning draft," which described discovery while
appearing in the asset ladder.

**Rung 2 is a fresh submission, not Midjourney's Vary button.** This is the only path that
lets the dense prompt and `--oref` enter — neither of which can ride along on a draft. It
matches `midjourney-prompting`'s Phase 2 structure, so it rests on documented guidance rather
than inferred UI behaviour. A human who prefers Vary for a given shot records the result
identically; the console does not require either route.

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
estimate immediately. A **"didn't run"** action voids the row and refunds the estimate.

Image arrival **confirms a run happened; it carries no cost data.** Ingest therefore cannot
reconcile an estimate into an actual — the only source of actual minutes is the human entering
them from Midjourney's usage page (§8.3). An earlier draft claimed "actual minutes are
reconciled when images land," which overstated what ingest can observe. Every ledger row
records whether its cost is `estimated` or `reconciled`, and the project total shows both
figures separately rather than one blended number that would read as measured.

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

**Token position is part of the contract, not a detail.** `lint_prompt_sheet.py`'s
`prompt_body` / `prompt_flags` split a prompt at the **first occurrence of `" --"`**. A
`{style:…}` token does not begin with `--`, so placing it *before* the first real flag would
drop it into the prompt *body*, breaking C13's requirement that the body end with `No Text.`
Slots therefore **must appear after at least one literal flag** — in practice after `--ar`,
which every sheet emits first. Gate C enforces the position rather than leaving it to
convention.

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

## 9. Sheet format and Gate C changes

**This is a sheet-format change with a linter change attached, not a linter change alone.** An
earlier draft scoped it as four edits to `scripts/lint_prompt_sheet.py`; three of the four
require the emitted-sheet contract in
`.claude/skills/visual-prompts/references/prompt-sheet-format.md` to change first. That file
currently mandates "the **two** `--sref` codes" literally in `WHOLE-SHORT SETUP` (that file's
§7, not this document's) — a
direct contradiction of slots — and explicitly places the cover outside the parser.

### 9.1 Sheet format changes

- `WHOLE-SHORT SETUP` stops mandating two literal `--sref` codes and instead names the two
  **slots** the sheet uses.
- The sheet **stops emitting `WORLD LOCK` entirely.** It moves to the styleboard artifact
  (§4.1), which becomes its single source of truth. Two copies with no sync rule would be
  worse than the fake codes this work exists to remove.
- Slot declarations (`slot_register_a:`, `slot_char_coach:`) live in the styleboard artifact's
  world-lock block, in the existing `^\s+[a-z][a-z0-9_]*:\s*value$` shape that
  `WORLD_ENTRY_RE` already matches — so that regex is reused unchanged against a different
  file.
- The `COVER / THUMBNAIL` section gains a parseable heading carrying the same
  register/class/scale/height fields a shot has.

### 9.2 Gate C changes

1. Accept `{style:…}` and `{char:…}` as valid flag-position tokens, **and enforce that they
   appear after at least one literal flag** (§6.2).
2. Require every referenced slot to be declared — now read from the styleboard artifact rather
   than the sheet. Gate C therefore takes a second input path; C8's world-lock field checks
   (`register_a_sport`, signature objects) move to reading that artifact too.
3. Lint the cover as a first-class asset. **It must be excluded from C1–C7**, the
   adjacency/scale/register-balance checks — appending it to the shot list would corrupt every
   one of them, since the cover is a packaging frame with no position in the arc. The
   "cover = reuse the Hook still, no separate generation" branch must also be handled, and
   skipped rather than failed.
4. **Reject any `--sref` value that is not numeric, a URL, or `random`.** This makes
   `SREF-RGS-A-DL01` impossible to reintroduce — the exact defect that motivated this work.
5. **Require every shot to carry a style mechanism at all** — a literal `--sref`/`--p`, or a
   `{style:…}` slot. Without this, checks 1 and 4 together still pass a sheet that simply has
   no style reference anywhere, leaving the underlying defect class alive.

### 9.3 Skill and reference files in scope

The split touches more than the two `SKILL.md` files. All of these must be updated together or
the pipeline's self-description goes stale:

- `visual-prompts/SKILL.md` — frontmatter `description` currently leads with world-locking.
- `visual-prompts/references/visual-registers.md` — §3/§4 (the two-code rule), §7.
- `visual-prompts/references/prompt-sheet-format.md` — §7, per §9.1 above.
- `visual-prompts/references/worked-example.md` — emits literal codes.
- `midjourney-prompting/SKILL.md` — the harvest-and-substitute Phase 2 flow, which now
  describes discovery only.
- `tests/fixtures/passing_sheet.md` — contains a literal `--sref 1122334455`.
- `CLAUDE.md`, `README.md`, and every skill description saying "six skills" — the pipeline
  becomes seven stages.

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
pipeline_app/sheet_parser.py        path-anchored shim over scripts/lint_prompt_sheet.py
```

The console reuses `parse_sheet()` from the repo-root `scripts/lint_prompt_sheet.py` rather
than growing a second parser for the same format — but **a plain `from scripts.lint_prompt_sheet
import parse_sheet` will not work.** Two packages named `scripts` exist, both with
`__init__.py`: the repo root's and `pipeline-app/scripts/`. Existing tests already resolve
`from scripts import …` to the pipeline-app one
(`pipeline-app/tests/test_migrate_handles.py`), so the import would silently bind to the wrong
package depending on `sys.path` order.

Resolution: load it by explicit path via `importlib.util.spec_from_file_location`, anchored on
`repo_root` (already carried on `app.state`), in a single `sheet_parser.py` shim that the rest
of the console imports from. One place to change if the packages are ever renamed.

## 11. Testing

Follows the existing pytest + `tmp_path` + temporary-DB pattern in `pipeline-app/tests/`.

**Fixtures must be committed, not read from `runs/`.** `runs/` is git-ignored, so a suite that
reads `runs/do-less-20260728-190724/03-visual/artifact.v1.md` directly would pass on this
machine and fail everywhere else. Tests read only from `pipeline-app/tests/fixtures/`.

**Two sheet fixtures are needed, and they are not interchangeable.** The `do-less` sheet is in
the **old** format — literal `--sref SREF-RGS-A-DL01`, no slots, `WORLD LOCK` inline. It is the
right fixture for the matcher (real prompt prose) and for the Gate C **regression** asserting
the fake code now fails. It is the wrong fixture for the ladder walkthrough: it has no slots,
so no asset ever reaches `blocked`, and its "resolved" prompt would contain the very fake code
this system exists to eliminate.

- `tests/fixtures/do_less_visual_sheet_legacy.md` — the real sheet, verbatim, for matcher and
  Gate C regression tests.
- `tests/fixtures/slotted_visual_sheet.md` + `tests/fixtures/slotted_styleboard.md` — a
  hand-written new-format pair, for slot resolution, blocked-state, and the ladder integration
  walkthrough.
- `tests/fixtures/mj_filenames.txt` — real Midjourney output filenames for matcher scoring.

**Unit, table-driven:**
- probe derivation from dense prompts;
- slot expansion across all four entry kinds, including the Niji 7 variant;
- cost estimation including the `--oref`→V7 2× penalty and `--q` multipliers;
- matcher scoring against real Midjourney output filenames.

**Gate C:** tests for all four new checks, including a regression asserting that
`--sref SREF-RGS-A-DL01` fails.

**Ladder state machine:** rung transitions, void-and-refund, ceiling warn versus typed
confirm, per-click sanity guard.

**Integration:** build a render project from the committed `tests/fixtures/slotted_visual_sheet.md`
plus its styleboard pair, walk one asset through all four rungs against a fake watch
directory, and assert files land at the expected paths and the ledger balances.

**Migration:** a test that a project created under the old topology (no `styleboard` row) is
backfilled correctly and that `visual` can still unlock afterwards (§4.1). This is the failure
that would wedge every existing run, so it is not optional coverage.

No test can reach Midjourney, because no code path in the application can.

## 12. Implementation ordering

One design spec, but **two implementation plans, strictly ordered.** The coupling that
justified a single spec (slots ↔ Gate C ↔ styleboard) does not make this a single plan: the
first block changes the artifact contract every other skill consumes, and the second is a
seven-table, nine-module application feature.

**Plan A — contract and topology.** The `styleboard` stage and skill, the world-lock
relocation with `[I]` markers preserved (§4.1), the sheet-format changes and the five Gate C
checks (§9), the stage templates, the DB backfill for existing projects, and the skill/doc
updates in §9.3. Ends with the existing test suite green and a new-format sheet passing
Gate C.

**Plan B — console and ladder.** The seven tables, the nine modules, both routes, ingest,
and the spend ledger (§4.2, §5, §7, §8, §10).

Plan A must land first. Building the console against a sheet format that is about to change
would mean writing the slot resolver twice, and the backfill in Plan A is what keeps existing
projects usable throughout.

## 13. Out of scope

- Any call to Midjourney, official or third-party (D1). The `Renderer` seam exists so this can
  change without redesign; it is not exercised.
- Image-to-video and motion prompts — these remain `visual-prompts`' responsibility.
- Changes to `voiceover`, `assembly`, or `repurpose` stages.
- Automatic upload of moodboard image sets to Midjourney (§6.1) — the human uploads and pastes
  the code back.

## 14. Facts to re-verify before implementation

Every `[T]` fact in §2 was verified 2026-08-06 against public sources and Midjourney's
documentation. The following change fastest and should be re-checked when implementation
starts:

- Whether an official or enterprise API has become available (would change D1 materially).
- GPU costs: draft 0.4 / SD 0.8 / HD 1.3, and the `--q` multipliers.
- Whether `--oref` still forces a V7 fallback, or a native V8 Omni Reference has shipped.
- Draft Mode's 24-image / 512px shape and its per-thumbnail style-code behaviour.
- Midjourney's download filename format, on which §8.2's matcher depends.
