# V8.2 model delta — what changed, and what the corpus now gets wrong

Every line below marked `[T] (verified 2026-07-26)` was read directly off `docs.midjourney.com` on
2026-07-26. The ContentStudio corpus (`docs/midjourney-prompting-guide.md`) is a **2026-07-23 snapshot
documenting V8.1**; V8.2 shipped as default the next day. This file is the delta layer, and it is the
tie-breaker: **where a `[C]` corpus finding about model *behavior* conflicts with a verified `[T]` fact
here, the `[T]` fact wins for V8.2 output — and both stay visible, with the reason.** Never silently
delete a cited corpus line.

`[T]` facts go stale fast. Re-verify at `docs.midjourney.com` before betting a paid render on them.

**Markers used here:** `[T]` web-verified 2026-07-26 · **`[T-unverified]`** asserted by the supplied
V8.2 runbook but **not** confirmed against documentation — say so out loud when you use one ·
`[C]` corpus-cited `(Channel, video_id)` · `[I]` general practice or this skill's own judgment.

**The supplied runbook was wrong in six places** (draft cost multiplier aside, it got `--q 0.25/0.5`,
pairwise profile training, the `--oref` V7 fallback, `--ow`'s failure mode, and two incompatibilities
wrong). Treat plausible-sounding Midjourney "facts" from memory with the same suspicion.

---

## The headline

- **V8.2 released as the default version on 2026-07-24** `[T]`, focused on aesthetics, image quality, and
  Personalization. Midjourney's own words: V8.2 images are "more creative, bold, sophisticated, and
  edgy," and Personalization "understands your aesthetic tastes much better." Set explicitly with
  `--v 8.2` `[T] (verified 2026-07-26, docs.midjourney.com "Version")`.
- V8.1 was default 2026-06-10 → 2026-07-23; V8.2 was previewed behind `--preview` before promotion
  `[T] (verified 2026-07-26)`. **The corpus's one mention of V8.2 as an unreleased `--preview` model
  (`docs/midjourney-prompting-guide.md:103`) is now stale — `--preview` is not how you reach V8.2.**
- Much of Midjourney's own documentation still says "V8.1" in body text while the version-compatibility
  chart says "V8.1 & V8.2". Treat the chart as authoritative and the prose as lagging
  `[T] (verified 2026-07-26)`.

## Corrections to the ContentStudio corpus — apply these

| # | Corpus said | Verified V8.2 truth | Consequence |
|---|---|---|---|
| 1 | `--style raw` `[C]` (corpus; this line was carried in a since-deleted visual-prompts reference file) | The flag is **`--raw`**, compatible v5.1+ | `--style raw` is legacy V5/V6 syntax. Emit `--raw` |
| 2 | Draft = "~1/10 the cost and ~5× the speed" `[T]` (corpus) | Draft = **0.4 min GPU** vs SD's **0.8 min** — exactly **half** | The 1/10 figure is **refuted**. Budget draft at 0.5×, not 0.1× |
| 3 | `--no` "works best for removing colors" `[C]`; guide `:111` says `--no` was **removed in V8** | `--no` is **supported in V8.1 & V8.2** | The guide's removal claim is **refuted**. The `[C]` colors-only caveat still stands as craft advice |
| 4 | Omni Reference is **V7-only**, V8 version "in training" `[T]` (corpus) | `--oref` *works* in V8.2 — but **"adding an Omni Reference will automatically run the prompt in V7"** | See the trap below. The corpus was closer to right than it looks |
| 5 | Fixed seed keeps V8 "~94% identical" `[C]` | Compatibility chart states **99% identical** for V8.1/8.2 seeds | Seed consistency is stronger than the corpus claims |
| 6 | `--s 140–185` sweet spot `[C]` | `--s` is 0–1000, **default 100** | Not a conflict — but see the stylize split below |
| 7 | Guide `:99`: `--sv` is "not in v8" | Midjourney documents `--sv` for **V7 and V6 only**; there is no V8 `--sv` section | Genuinely **ambiguous** — quarantined below, not resolved |

## The `--oref` trap — the single most important V8.2 finding

> "Adding an Omni Reference image to the Imagine bar will automatically run the prompt in V7."
> The version-compatibility chart lists Omni Reference and Omni Reference Weight under V8.1 & V8.2 as
> **"(Uses V7)"** `[T] (verified 2026-07-26, docs.midjourney.com "Omni Reference" + "Version")`.

**You cannot have V8.2 aesthetics and subject-identity lock in the same job.** Choosing `--oref` is
choosing to render in V7 — the warmer, more painterly, less literal model. This is not a footnote; it
changes which consistency mechanism a job should use, and the skill must say so out loud whenever
subject-lock is requested.

Verified `--oref` facts `[T] (verified 2026-07-26)`:
- Costs **2× GPU time**.
- `--ow` accepts **1–1000, default 100**. Midjourney's guidance: **keep it below 400** unless you are
  also using a very high stylize value, "otherwise your results may be unpredictable." *(Note: the
  supplied V8.2 runbook characterized `>400` as "rigid composition lock." The documentation says
  **unpredictable**, not rigid — use the documented wording.)*
- **One image only** per Omni Reference.
- **Incompatible with:** Draft Mode, Conversational Mode, **Fast Mode**, **`--q 4`**, inpainting/
  outpainting, Vary Region, Pan, Zoom Out. *(The runbook missed Fast Mode and `--q 4`.)*
- **Compatible with:** `[T]` Personalization, Moodboards, `--stylize`, Style References.
- Higher `--stylize` or `--exp` values compete with `--ow` for influence — raise `--ow` to compensate.

The same V7-fallback trap applies to the **Style Creator**: "Images generated in the Style Creator use
Midjourney version 7" `[T] (verified 2026-07-26)`.

## Render economics — verified numbers

| Mode | Flag | GPU cost | Output | Resolution |
|---|---|---|---|---|
| Draft | `--draft` | **0.4 min** | **24 images** | 512×512 |
| Standard | `--sd` | **0.8 min** | 4 images | 1024×1024 |
| High-def | `--hd` | **1.3 min** | 4 images | 2048×2048 |
| Quality ×2 | `--q 2` | 2× the above | 4 images | — |
| Quality ×4 | `--q 4` | 4× the above | 4 images | — |

`[T] (verified 2026-07-26, docs.midjourney.com "Version", "Draft & Conversational Modes", "Quality")`

- `--hd` is a **62.5% premium** over `--sd` (1.3 vs 0.8). That is the number that justifies staying in
  SD until composition is locked.
- **Draft Mode is web-only** — not available in Discord. Promote a keeper with **Vary** or **Remix**,
  which regenerates it at SD or HD per your settings.
- **`--q` only affects the first grid of four.** It does nothing for variations, inpainting/outpainting,
  or upscales — so spending `--q 4` before you have the composition is pure waste.
- `--q` accepts **1, 2, 4** with default 1. **`0.25` and `0.5` are not valid** — 0.5 was a V6-era value.
  *(The supplied runbook listed `0.25, 0.5, 1, 2, 4`; the first two are refuted.)*

## Parameter ranges — verified, and what Gate A lints against

| Parameter | Range | Default | Notes |
|---|---|---|---|
| `--stylize` / `--s` | 0–1000 | 100 | Low = literal to prompt; high = Midjourney's own flair |
| `--chaos` / `--c` | 0–100 | 0 | Higher = grid images differ more, adhere less |
| `--sw` (style weight) | 0–1000 | 100 | **Not compatible with Moodboards** |
| `--ow` (omni weight) | 1–1000 | 100 | Keep < 400; forces the job to V7 |
| `--q` | 1, 2, 4 | 1 | First grid only |
| `--sv` | see quarantine | — | **Not compatible with Moodboards** |
| `--ar` | up to **14:1** | 1:1 | **4:1 max when `--hd` is on** — new constraint the corpus lacks |

`[T] (verified 2026-07-26)`

Also live in V8.2 and absent from the supplied runbook: `--exp`, `--weird` / `--w`, `--tile`,
`--repeat` / `--r`, `--iw`, `--stealth`, `--public`, `--relax` / `--fast` / `--turbo`, `--niji`,
`--motion low|high`, `--loop`, `--end`, `--bs` `[T] (verified 2026-07-26, docs.midjourney.com
"Parameter List")`.

Additional verified gotcha: using Pan, Zoom Out, or Edit/Vary Region **on an HD image downscales the
result to SD** — re-upscale to get back to 2K `[T] (verified 2026-07-26)`.

## Syntax rules — verified verbatim

Midjourney's own three rules `[T] (verified 2026-07-26, docs.midjourney.com "Parameter List")`:
1. **Place parameters at the end**, after the prompt text.
2. **Watch the spaces** — a space between prompt text and the dashes.
3. **No punctuation** — no commas, periods, or other punctuation inside parameters.

Their four documented failure cases: no space before the dashes; an extra space between the dashes;
punctuation after a parameter value; prompt text placed after the parameters. Gate A lints all four.

## Style systems — verified behavior

- **`--sref random`** `[T]` converts to a concrete style code on submission. With a **permutation, `--repeat`,
  or Draft Mode** prompt, **each image gets a different code** — this is exactly what makes the
  cheap style-sweep work, and it is officially supported, not a community trick
  `[T] (verified 2026-07-26)`.
- **You cannot create a style code from an uploaded image.** `[T]` An uploaded image can be *used* as a Style
  Reference, but it will not yield a reusable code `[T] (verified 2026-07-26)`. *(This narrows the
  corpus's `[I]` bootstrap step — passing an image URL as `--sref` works;
  "extract a style code from that generation" does not.)*
- `--sref random` and style codes are **only compatible with `--sv 4` and `--sv 6`** `[T] (verified 2026-07-26)`.
- **Style Creator** `[T]` builds custom `--sref` codes from a pick-the-grid session; web-only; **previews
  consume your GPU time**, and Midjourney explicitly suggests adding **`--draft`** to keep that cheap.
  Entering it with an existing style code **stacks** a second code rather than merging — you must then
  carry *both* codes forward to reproduce what you saw `[T] (verified 2026-07-26)`.
- **Personalization** `[T]` requires unlocking the Global Profile first; `--p` errors otherwise. The **Global
  V7 Profile works in V8.1 and V8.2**, additional V8 profiles can be created, and **there is currently
  no Global V8 Profile** `[T] (verified 2026-07-26)`.
- **Profiles are trained by selecting images from a grid.** `[T]` Midjourney's note: "Rating image pairs has
  been replaced with selecting images from a grid" `[T] (verified 2026-07-26)`. *(The supplied runbook
  described pairwise ranking — **refuted**, that flow no longer exists.)*
- `--p mID` (moodboard) and `--p pID` (profile) both **auto-convert to `--p code`** on submission. A
  moodboard's code changes when you add or remove images; old codes keep working, and codes survive
  deleting the board `[T] (verified 2026-07-26)`.
- **Moodboards are incompatible with both `--sv` and `--sw`** `[T] (verified 2026-07-26)`. Confirms the
  runbook.

## `[T-unverified]` — asserted by the supplied runbook, NOT confirmed

Every item here appeared in the supplied V8.2 runbook but could **not** be confirmed against
Midjourney's documentation on 2026-07-26. They carry the marker **`[T-unverified]`** wherever they
appear in this skill — the same convention the sibling `elevenlabs-audio` skill uses. Do not state
these as fact; **say the uncertainty out loud** when one is load-bearing, and if it matters to a job,
test it.

- **"V8.2 enforces strict prompt literalism; loose prompts render flat and unadorned."** Midjourney
  describes V8.2 as *more* creative, bold, and edgy — which if anything cuts the other way. The
  literalism claim is the runbook's central thesis and it is **unverified**. The documented lever for
  literalism is `--raw`, plus low `--stylize`.
- **"Quality buzzwords (photorealistic, 8k, masterpiece, ultra-detailed) actively degrade V8.2 output."**
  Not documented. *Prefer concrete physical description anyway* — that is defensible as `[I]` craft and
  is corroborated by the corpus's own "describe the picture's content fully"
  `[C] (Future Tech Pilot, wEwYSBj0qBo)` — but do **not** claim the model penalizes buzzwords.
- Wall-clock render times (≈4s SD, ≈12s HD, ≈2–4s draft). GPU-minute costs are verified; **seconds are not**.
- Moodboard capacity ("up to 100 images") and the "20–50 curated images" sweet spot. No count is documented.
- Style Creator round count ("5 to 15 evaluation rounds"). Not documented.
- `--stylize` scaling the influence of a **Personalization profile**. Not documented. *(The corpus does
  cite `--stylize` dialing **moodboard** influence, ~50 as a sweet spot
  `[C] (Wade McMaster, TtkenI4wt8I; Future Tech Pilot, Tv1dfGcOSnA)` — that citation stands on its own.)*
- Exporting/sharing profile IDs **across accounts or teams**. Codes are reusable within your own prompts;
  cross-account portability is not documented.
- `--repeat` range ("1 to 40, plan dependent"). Range not verified.
- `--sv 6` being the **V8.2** default. Verified only for **V7**: six versions, `--sv 6` default, `--sv 4`
  the pre-2025-06-16 model. Midjourney documents no V8 `--sv` section at all, and the V8 compatibility
  chart has no `--sv` row. **Genuinely ambiguous — omit `--sv` from V8.2 prompts unless you have tested it.**

## Sources

All `[T]` lines above were read on 2026-07-26 from `docs.midjourney.com`:
[Version](https://docs.midjourney.com/hc/en-us/articles/32199405667853-Version) ·
[Parameter List](https://docs.midjourney.com/hc/en-us/articles/32859204029709-Parameter-List) ·
[Omni Reference](https://docs.midjourney.com/hc/en-us/articles/36285124473997-Omni-Reference) ·
[Style Reference](https://docs.midjourney.com/hc/en-us/articles/32180011136653-Style-Reference) ·
[Style Creator](https://docs.midjourney.com/hc/en-us/articles/41308374558221-Style-Creator) ·
[Personalization](https://docs.midjourney.com/hc/en-us/articles/32433330574221-Personalization) ·
[Moodboards](https://docs.midjourney.com/hc/en-us/articles/39193335040013-Moodboards) ·
[Draft & Conversational Modes](https://docs.midjourney.com/hc/en-us/articles/35577175650957-Draft-Conversational-Modes) ·
[Quality](https://docs.midjourney.com/hc/en-us/articles/32176522101773-Quality) ·
[Stylize](https://docs.midjourney.com/hc/en-us/articles/32196176868109-Stylize) ·
[Chaos / Variety](https://docs.midjourney.com/hc/en-us/articles/32099348346765-Chaos-Variety) ·
[Raw](https://docs.midjourney.com/hc/en-us/articles/32634113811853-Raw)
