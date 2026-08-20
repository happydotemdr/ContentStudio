# Parameters — the full reference this skill emits from

Two sources, layered. **Craft** (what value to pick, and why) comes from the ContentStudio corpus:
`docs/midjourney-prompting-guide.md`, 384 findings across four dedicated Midjourney YouTube channels
(Future Tech Pilot, Wade McMaster, Tao Prompts, Tokenized AI), snapshot 2026-07-23 — carried through
here with its `[C] (Channel, video_id)` citations intact. **Mechanics** (range, default, compatibility)
come from `v82-model-delta.md`, read off `docs.midjourney.com` on 2026-07-26 and marked
`[T] (verified 2026-07-26)`.

Where the two disagree, `v82-model-delta.md` wins and says so. Read it before this file.

## Syntax — non-negotiable, lints in Gate A

Parameters go **at the absolute end** of the prompt, after all descriptive text. One space before every
`--`. **No commas, periods, or any punctuation inside the parameter block.** No prompt text after the
parameters `[T] (verified 2026-07-26)`.

```
✓  matte ceramic teapot on dark slate, diffused side light --ar 4:5 --raw --s 90 --hd
✗  matte ceramic teapot--ar 4:5                 (no space before dashes)
✗  matte ceramic teapot - - ar 4:5              (extra space between dashes)
✗  matte ceramic teapot --ar 4:5, --raw         (punctuation in the parameter block)
✗  matte ceramic teapot --ar 4:5 on dark slate  (prompt text after parameters)
```

Type parameters **in the prompt** rather than relying on account settings — explicit and per-job
`[C]`. This also matters for reproducibility: a settings-panel default is invisible in the archived
prompt string.

## The table

| Parameter | Range / values | Default | What it does, and how to choose |
|---|---|---|---|
| `--ar` | up to 14:1; **4:1 max with `--hd`** `[T] (verified 2026-07-26)` | 1:1 | Changes composition, not just crop — decide it deliberately `[C] (Future Tech Pilot, Tv1dfGcOSnA)`. `9:16` for Shorts `[C][T]` |
| `--raw` | flag | off | Turns off Midjourney's "auto-pilot" styling; simple prompts get more photo-like. Compatible v5.1+ `[T] (verified 2026-07-26)`. **The flag is `--raw`, not `--style raw`** — that spelling is legacy |
| `--stylize` / `--s` | 0–1000 | 100 | Low = literal to your prompt; high = Midjourney's own flair `[T] (verified 2026-07-26)`. Corpus sweet spot **140–185** for general work; **300+** for a deliberately branded look; **50–80** when a long, detail-heavy prompt is being ignored `[C] (Future Tech Pilot, Tv1dfGcOSnA / ioJ6istzwHw; Tokenized AI, 1GnipTgvLI0)` |
| `--chaos` / `--c` | 0–100 | 0 | Grid variance. Higher = images differ more **and adhere less** `[T] (verified 2026-07-26)`. Corpus: `3–9` while drafting variants, `0` once locked `[C] (Future Tech Pilot, Tv1dfGcOSnA / fMEvMqvzUbc)` |
| `--q` | **1, 2, 4** | 1 | 2× / 4× GPU time for micro-texture density. **Only affects the first grid of four** — nothing for variations, inpainting, or upscales `[T] (verified 2026-07-26)`. `0.25`/`0.5` are **not valid** in V7/V8 |
| `--hd` / `--sd` | flag | `--sd` | 2048px (1.3 min GPU) vs 1024px (0.8 min) `[T] (verified 2026-07-26)`. `--hd` **changes the image, not just the resolution** — it can differ from the SD version at the same seed `[C][T] (Future Tech Pilot, Tv1dfGcOSnA / t_xIYKk2ERk)` |
| `--draft` | flag | off | 24 images at 512px for 0.4 min GPU — half of SD. Web-only `[T] (verified 2026-07-26)`. See `render-economics.md` |
| `--seed` | integer | random | Locks the generation blueprint. V8 holds **99% identical** with a fixed seed `[T] (verified 2026-07-26)`; a small word change survives, a **big subject swap still breaks it** `[C] (Future Tech Pilot, ZPJB6jurDfE)` |
| `--no` | text | none | **Supported in V8.1/V8.2** `[T] (verified 2026-07-26)`. Works best for removing a **color**; unreliable as a general negative-prompt tool `[C] (Future Tech Pilot, Tv1dfGcOSnA / IS0Kk9OFaZQ)` |
| `--iw` | 0–3 | 1 | Image-prompt weight. `0.5` ≈ colors only, `2–2.5` ≈ near-copy; halve on each re-application pass (2, 1, 0.5, 0.25) `[I]` — downgraded from `[C][T]`: neither a corpus channel/video_id nor a verified-date citation backs this row, so it is carried as this skill's own operational guidance rather than a checkable fact |
| `--sref` | code / URL / `random` | none | Style transfer. See `style-systems.md` |
| `--sw` | 0–1000 | 100 | Style-reference strength. **Incompatible with Moodboards** `[T] (verified 2026-07-26)` |
| `--sv` | see delta | — | **Omit in V8.2** — no V8 `--sv` behavior is documented. **Incompatible with Moodboards** `[T] (verified 2026-07-26)` |
| `--oref` | image URL | none | Subject-identity lock — **forces the job to render in V7**. See `style-systems.md` |
| `--ow` | 1–1000 | 100 | Omni strength. Keep **below 400** or results get unpredictable `[T] (verified 2026-07-26)` |
| `--p` | `pID` / `mID` / `code` | none | Personalization profile or moodboard. See `style-systems.md` |
| `--tile` | flag | off | Seamless repeating pattern `[T] (verified 2026-07-26)` |
| `--repeat` / `--r` | plan-dependent | 1 | Runs the prompt as several jobs. Exact range unverified — see delta quarantine |
| `--weird` / `--w`, `--exp` | — | — | Live in V8.2 `[T] (verified 2026-07-26)`. `--exp` competes with `--ow` for influence; the corpus covers neither |
| `--relax` / `--fast` / `--turbo` | flag | account setting | GPU speed tier. `--relax` is the token-discipline lever for exploratory work |
| `--motion low` / `--motion high` | flag | — | Midjourney's own image→video. Prefer **low** for coherence `[C] (Future Tech Pilot, Dkj7Jqejfz0)`. Motion/i2v belongs to `visual-prompts`, not this skill |

## Compatibility matrix — Gate A rejects these combinations

| This | Cannot combine with | Source |
|---|---|---|
| `--oref` | `--draft`, Conversational Mode, **Fast Mode**, **`--q 4`**, inpainting/outpainting, Vary Region, Pan, Zoom Out | `[T] (verified 2026-07-26)` |
| Moodboard (`--p mID`) | `--sv`, `--sw` | `[T] (verified 2026-07-26)` |
| `--hd` | aspect ratios wider than **4:1** | `[T] (verified 2026-07-26)` |
| `--sref random` / style codes | any `--sv` other than 4 or 6 | `[T] (verified 2026-07-26)` |
| V6 `--sref` codes | V7 / V8 models | `[C] (Wade McMaster, PEl1Rb9spsk)` |
| Pan / Zoom Out / Vary Region | preserving HD — the result **downscales to SD** | `[T] (verified 2026-07-26)` |

## Two silent-cost traps worth stating to the user

1. **`--oref` reruns the entire job in V7** `[T] (verified 2026-07-26)` — at 2× GPU. You are trading
   V8.2's aesthetic for identity lock, not adding one to the other.
2. **Style Creator previews consume GPU time** and also render in V7 `[T] (verified 2026-07-26)`.
   Midjourney's own mitigation is to add `--draft` to the Style Creator prompt.
