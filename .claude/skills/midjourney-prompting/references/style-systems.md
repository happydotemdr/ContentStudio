# Style systems — choosing a consistency mechanism

Midjourney has four ways to make separate jobs look like they belong together. They are not
interchangeable, they have different costs, and one of them silently changes which model renders your
image. Pick deliberately.

Mechanics `[T] (verified 2026-07-26)` come from `v82-model-delta.md`; craft `[C]` from the corpus
(`docs/midjourney-prompting-guide.md`, 384 findings, 4 Midjourney channels, snapshot 2026-07-23).

## The decision

| You need | Mechanism | Cost | Catch |
|---|---|---|---|
| The *same subject* (person, product, vehicle, creature) across scenes | **Omni Reference** `--oref <url> --ow 50–150` | **2× GPU** | **Renders in V7, not V8.2** |
| One consistent *look* across many images, no recurring subject | **`--sref <code>`** + `--sw` | none | Code behaves differently per subject |
| A look you can *show* but not describe | **Moodboard** `--p <mID>` | none | Blocks `--sv` and `--sw` |
| Your own taste applied globally | **Personalization** `--p` | none | Must unlock Global Profile first |
| Cheap, low-stakes continuity | **Fixed `--seed`** | none | Breaks on a big subject swap |
| Subject-free b-roll / background plates | **None** — shared style is enough | none | — |

Normally **one** mechanism is active. Stacking Omni Reference *and* a moodboard *and* a seed is
possible but adds cost and complexity for little gain — this "pick one" framing is this skill's own
operational guidance `[I]`, not a corpus claim; the guide documents each mechanism independently and
never ranks them.

---

## Omni Reference (`--oref`) — read this before choosing it

**Choosing `--oref` is choosing V7.** Midjourney: "Adding an Omni Reference image to the Imagine bar
will automatically run the prompt in V7," and the V8.1/V8.2 compatibility chart marks both Omni
Reference and Omni Reference Weight **"(Uses V7)"** `[T] (verified 2026-07-26)`.

So the real trade is: **V8.2's bolder, more sophisticated aesthetic, or subject-identity lock — not
both.** Say this to the user whenever they ask for a recurring character or product. If the look
matters more than exact likeness, `--sref` + a strong text description of the subject keeps you in V8.2.

Verified mechanics `[T] (verified 2026-07-26)`:
- `--ow` is **1–1000, default 100**. Keep it **below 400** unless also running very high stylize,
  "otherwise your results may be unpredictable." For scenes where the subject must adapt to new lighting
  and framing, **50–150** leaves room for contextual integration.
- **One reference image only.** For multiple characters, use a single image containing all of them and
  describe them in the text.
- **2× GPU time.**
- **Incompatible with** Draft Mode, Conversational Mode, Fast Mode, `--q 4`, inpainting/outpainting,
  Vary Region, Pan, Zoom Out. *(That means the cheap ideation path and `--oref` are mutually exclusive
  by design — establish the look in draft first, attach `--oref` only at lock.)*
- **Compatible with** Personalization, Moodboards, `--stylize`, Style References.
- High `--stylize` or `--exp` **compete** with `--ow` for influence — raise `--ow` to compensate.

Midjourney's own best practices `[T] (verified 2026-07-26)`: the text prompt still carries the scene —
`--oref` supplies likeness, not context. To push a style different from the reference, name that style
**at both the start and end** of the prompt and lower `--ow`, reinforcing the physical traits you want
kept in the text. Fine details like freckles or clothing logos will not match exactly.

**Building the reference image.** The corpus's method: a character sheet with **four vertical columns
(front, left profile, right profile, back)**, each a full-body shot above a matching close-up, plain
background `[C] (Tao Prompts, 2psBexPkw3I)`. Keep **separate sheets per major state** (with/without a
prop) or the model drifts `[C] (Wade McMaster, g1SRS7-Bqlk)`.

## Style Reference (`--sref`)

Transfers colors, medium, texture, and lighting — **not** subject geometry. Compatible with V6 and later
`[T] (verified 2026-07-26)`.

- `--sw` is **0–1000, default 100**. **Not compatible with Moodboards** `[T] (verified 2026-07-26)`.
- **`--sref random`** resolves to a concrete code on submission. Paired with a **permutation,
  `--repeat`, or Draft Mode**, **every image in the batch gets a different code**
  `[T] (verified 2026-07-26)` — this is the officially supported mechanism behind the cheap style sweep
  in `render-economics.md`, not a community workaround.
- **You cannot create a style code from an uploaded image** `[T] (verified 2026-07-26)`. An upload can
  be *used* as a `--sref`, but it yields no reusable code. *(This narrows the corpus's `[I]` bootstrap
  step: passing the image URL works; "extract a code from that generation" does not.)*
- Codes and `--sref random` work **only with `--sv 4` or `--sv 6`** `[T] (verified 2026-07-26)`.
- V6 codes are **incompatible** with V7/V8 `[C] (Wade McMaster, PEl1Rb9spsk)`.
- The same code renders differently by subject and by what leads the prompt — adding "oil painting" up
  front shifts it. **Re-test a code against your actual subject** rather than assuming it transfers
  `[C] (Future Tech Pilot, GAT5A6MqM-E)`.

Midjourney's prompting guidance with a `--sref` active `[T] (verified 2026-07-26)`: keep the text prompt
simple and avoid style words that fight the reference; describe **what you want to see**, not how to
modify the reference. "detailed portrait of a dog" ✓ — "the look of this image but a dog" ✗.

**Style Explorer** browses and searches the internal style library ("photographic", "anime"), with Try
Style / Copy / Search-similar and a Likes tab. Liking style codes does **not** affect Personalization
profiles `[T] (verified 2026-07-26)`.

## Style Creator

Builds a **custom `--sref` code** from a pick-from-the-grid session; it uses the styles you pick *and
the ones you don't*. Web-only `[T] (verified 2026-07-26)`.

Three things that cost people money and reproducibility:
- **Previews consume your GPU time.** Midjourney's own mitigation: add **`--draft`** to the Style
  Creator prompt `[T] (verified 2026-07-26)`.
- **It renders in V7**, so a prompt carrying V7-incompatible parameters may error until you strip them
  `[T] (verified 2026-07-26)`.
- **Codes stack, they do not merge.** Entering the Style Creator with an existing `--sref` adds a second
  code alongside it; the previews you are judging use **both**. To reproduce that look later you must
  carry **both codes** forward `[T] (verified 2026-07-26)`.

The prompt you type only generates the preview images — it does **not** steer the Style Creator itself.
Use a **simple** prompt for a clear read on what the style actually does `[T] (verified 2026-07-26)`.

*(The supplied V8.2 runbook claimed a "5 to 15 evaluation rounds" benchmark. Not documented —
quarantined in `v82-model-delta.md`.)*

## Moodboards (`--p <mID>`)

Curated images become a persistent style. Broader aesthetic range than a Style Reference, which is more
specific — "for when words just aren't enough" `[T] (verified 2026-07-26)`.

- **Incompatible with `--sv` and `--sw`** `[T] (verified 2026-07-26)`. Dial influence with `--stylize`
  instead — the corpus puts the sweet spot around **50**, with 1000 the max
  `[C] (Wade McMaster, TtkenI4wt8I; Future Tech Pilot, Tv1dfGcOSnA)`.
- `--p mID` **auto-converts to `--p code`** on submit. Adding or removing images generates a **new
  code**; older codes keep working, and **codes survive deleting the board** `[T] (verified 2026-07-26)`.
  → Archive the resolved `--p code`, not the `mID`, or the look drifts as the board grows.
- Multiple boards can be active at once `[T] (verified 2026-07-26)`.
- Curation craft: keep a board to one coherent palette, lighting scheme, and texture family — mixing
  conflicting styles dilutes it `[I]`. *(The runbook's specific "20–50 images, max 100" figures are
  **not documented** — quarantined. Do not quote them as limits.)*
- To populate a board efficiently, fan asset types through **one** permutation job:
  `{a product hero, a lifestyle scene, a texture macro, a hero portrait}` + shared subject/environment
  `[C] (Wade McMaster, PEl1Rb9spsk; Tokenized AI, o6cAA8jziPU)`.

## Personalization (`--p`)

Midjourney learns your taste from images you select.

- **Unlock the Global Profile first** — `--p` errors until you do `[T] (verified 2026-07-26)`.
- **Training is grid selection, not pairwise ranking.** Midjourney: "Rating image pairs has been
  replaced with selecting images from a grid" `[T] (verified 2026-07-26)`. *(The runbook's pairwise
  description is refuted — that flow no longer exists.)*
- **The Global V7 Profile works in V8.1 and V8.2.** You can create additional V8 profiles, but there is
  **no Global V8 Profile** `[T] (verified 2026-07-26)`.
- `--p pID` → `--p code` on submit; multiple profiles supported `[T] (verified 2026-07-26)`.
- Liking images on the Explore page **influences your Global Profile** — check which version an image
  was made with `[T] (verified 2026-07-26)`.
- *(That `--stylize` scales **profile** influence is **not documented** — quarantined. The `--stylize`
  ↔ **moodboard** relationship above is separately corpus-cited and does stand.)*

## Fixed seed

Cheapest continuity, good enough when perfection isn't critical
`[C] (Tokenized AI, MfK-WkKUnKQ)`. V8 holds **99% identical** on a fixed seed
`[T] (verified 2026-07-26)`, and survives a small word change — but a **large subject swap still breaks
it**, so don't lean on it across genuinely different scenes `[C] (Future Tech Pilot, ZPJB6jurDfE)`.

## Subject-free plates

No mechanism needed beyond a shared style. Generate with "no animals and creatures, no people" so the
plate composites cleanly and doesn't drag a subject's color into the palette
`[C] (Tokenized AI, lCFzMnBDqEc)`.
