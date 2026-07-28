# Render economics — spending GPU minutes deliberately

The failure this file exists to prevent: burning fast-GPU hours on high-resolution renders of a
composition that was never going to work. Resolution is the *last* decision, not the first.

All GPU figures `[T] (verified 2026-07-26)` — see `v82-model-delta.md` for sources.

## The cost ladder

| Mode | Flag | GPU / job | Output | Resolution | Use for |
|---|---|---|---|---|---|
| Draft | `--draft` | **0.4 min** | **24 images** | 512×512 | Wide exploration, style sweeps, thumbnailing |
| Standard | `--sd` | **0.8 min** | 4 images | 1024×1024 | Composition, framing, lighting validation |
| High-def | `--hd` | **1.3 min** | 4 images | 2048×2048 | Final deliverables |
| Quality ×2 | `--q 2` | 2× | 4 images | — | Complex surface texture, fine material detail |
| Quality ×4 | `--q 4` | 4× | 4 images | — | Multi-subject scenes, architectural interiors |

Two numbers do the work: **`--hd` is a 62.5% premium over `--sd`** (1.3 vs 0.8), and **`--draft` is
exactly half of `--sd`** (0.4 vs 0.8) while returning **six times as many images**. Draft is therefore
~12× more images per GPU minute than SD. That is the whole argument for exploring in draft.

*(The corpus claims Draft costs "~1/10" of a standard job `[T]` — **refuted**; it is 1/2. The corpus's
"24 images" is correct for the V8 path. See `v82-model-delta.md`.)*

## The three phases

### Phase 1 — wide exploration (`--draft --sd`)

Goal: find a direction, not an image. Never `--hd`, never `--q 2` or higher, never `--oref` — the last
is **incompatible** with Draft Mode anyway `[T] (verified 2026-07-26)`.

Two multipliers stack here:

**Style sweep.** `--sref random` with Draft Mode gives **every one of the 24 thumbnails a different
style code** `[T] (verified 2026-07-26)`. One 0.4-minute job samples 24 aesthetics without writing a
single style adjective. Click a thumbnail to reveal its code.

**Permutations.** `{}` batches variables into one submission — subject, lighting, or composition tested
in parallel `[C] (Wade McMaster, PEl1Rb9spsk; Tokenized AI, o6cAA8jziPU)`:

```
a cinematic studio photograph of a {vintage glass perfume bottle, stainless steel chronograph, leather travel bag}, key light from camera left, neutral seamless background --draft --ar 16:9
```

Three subjects, identical lighting, one submission. Note: a permutation runs as **one job per comma
item**, so cost scales with the item count — three items is three draft jobs, not one.

Promote a keeper with **Vary** or **Remix**, which regenerates it at SD or HD per your settings
`[T] (verified 2026-07-26)`.

**Draft Mode is web-only** — not available in Discord `[T] (verified 2026-07-26)`.

### Phase 2 — compositional lock (`--sd`)

Drop `--draft`, stay at 1024px. This is where the image is actually designed.

- Replace `--sref random` with the harvested `--sref <code>`, or attach the moodboard `--p <code>`.
- Attach `--oref <url> --ow 50–150` **only if** subject-identity lock is required — and tell the user it
  drops the job to V7 at 2× GPU `[T] (verified 2026-07-26)` (`style-systems.md`).
- Add optics and lighting specificity (layers 6 and 7 of `prompt-architecture.md`).
- Drop `--c` toward 0 once you have the direction — variance has done its job.
- Validate framing, subject geometry, and lighting falloff **here**, at 0.8 min, not at 1.3.

### Phase 3 — production render (`--hd`)

Only after Phase 2's composition is approved.

- `--hd` for native 2048px. **Watch the aspect ratio: `--hd` caps at 4:1** `[T] (verified 2026-07-26)`.
- `--q 2` for surface/material density; `--q 4` for multi-subject or architectural complexity.
  **`--q` affects only the first grid of four** — it does nothing for variations, inpainting, or
  upscales, so applying it before composition is locked is pure waste `[T] (verified 2026-07-26)`.
- **`--q 4` is incompatible with `--oref`** `[T] (verified 2026-07-26)`. If a job needs both, it cannot
  have both — say so rather than emitting a prompt that will error.
- `--raw` when literal photographic rendering matters (`prompt-architecture.md`).
- Expect the HD image to **differ from the SD version even at the same seed** — `--hd` changes the
  image, not just its resolution `[C][T] (Future Tech Pilot, Tv1dfGcOSnA / t_xIYKk2ERk)`. Budget one
  more validation look; do not assume the SD approval transfers.
- Editing an HD image with Pan, Zoom Out, or Vary Region **downscales it to SD** — re-upscale after
  `[T] (verified 2026-07-26)`.

Corpus operational note: keep `--hd` **off in account settings** and apply it per-job, or it silently
drains fast-generation hours `[C][T] (Future Tech Pilot, Tv1dfGcOSnA / t_xIYKk2ERk)`.

## Relax mode

`--relax` runs jobs without consuming fast GPU minutes (available by plan tier) `[T] (verified 2026-07-26)`.
Exploration and style sweeps have no deadline — **default Phase 1 to relax** unless the user says they
are in a hurry. Reserve fast/turbo for the production render. Note `--oref` is **incompatible with Fast
Mode** `[T] (verified 2026-07-26)`, so an Omni job is going to relax or standard regardless.

## Stages that must never escalate `[I]`

This section is this skill's own operational design, not a corpus or vendor claim — the corpus never
discusses stage gating. It follows from the verified cost ladder above. Three of this skill's stages
are exploratory by definition and **terminate at Phase 1**:

- **`moodboard`** — generating candidate images to curate into a board. Output quality is irrelevant;
  the board stores style, not pixels.
- **`explore`** — finding a direction. If you don't know what you want yet, resolution cannot help.
- **`profile`** — generating grids to train a Personalization profile by selection.

Emitting `--hd`, `--q 2`+, or `--oref` for any of these is a **Gate A lint failure**, not a judgment
call. It is the specific waste this skill exists to prevent.

## Archive, or you will pay twice

Reproducing an image requires the **exact** string. Record: full prompt text, every parameter, the
resolved `--sref` / `--p` **code** (not the `mID` — moodboard codes change as the board grows
`[T] (verified 2026-07-26)`), the `--oref` URL and `--ow`, the seed, the model version, and the date.
Midjourney carries **no context between jobs** `[T]`, so a prompt that only made sense as a follow-up
to another will not re-render.
