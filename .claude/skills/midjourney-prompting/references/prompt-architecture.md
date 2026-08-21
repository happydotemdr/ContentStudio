# Prompt architecture — the 9-layer build

> **`[T]` facts in this file were web-verified 2026-07-26** against live docs.midjourney.com documentation (the V8.2 delta)
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

A Midjourney prompt is not a sentence, it is a stack. Build it in this order every time, then let Gate A
check the result.

## The nine layers

| # | Layer | What goes here | Example fragment |
|---|---|---|---|
| 1 | **Medium & modality** | The foundational form | `architectural product photography` · `impasto oil painting` · `editorial fashion portrait` |
| 2 | **Core subject** | The thing, named cleanly, no conversational filler | `a matte ceramic teapot` |
| 3 | **Action, pose, physical state** | The mechanical/spatial state — never a static stand | `positioned at a 45-degree angle, faint steam rising, unpressed seams` |
| 4 | **Environment & spatial framing** | Setting and background depth | `on a dark slate countertop, minimalist tea house softly out of focus` |
| 5 | **Composition & angle** | Camera placement, in professional terms | `three-quarter elevated perspective` · `low-angle shot` · `rule-of-thirds` |
| 6 | **Optics, lens & depth of field** | Focal length and aperture physics | `90mm macro lens, f/4.0, razor-sharp focal plane` |
| 7 | **Lighting mechanics** | Key, fill, and ambient behavior | `diffused side light from a softbox, subtle fill, long soft shadows` |
| 8 | **Color palette & atmosphere** | Tonal distribution and contrast | `cool neutral palette, high contrast, clean atmosphere` |
| 9 | **Parameters** | All flags, at the absolute end | `--ar 4:5 --raw --s 90 --hd` |

This is the supplied V8.2 runbook's architecture, and it is a **superset** of the corpus's own token
order — medium → subject + action → environment → composition (camera, lens, angle) → lighting → style
→ color/mood → parameters `[C] (Tokenized AI, 4DrNl5lNapo)` — which folds optics into composition. The
9-layer split promotes optics to its own decision `[I]`, because focal length and aperture are the two
levers that most reliably separate a photograph from a render, and burying them costs you both.

## Three rules that govern the stack

**Front-load what matters.** Midjourney weights earlier words more heavily and words far back often fail
to appear at all. Move anything important toward the front, and if a word gets dropped, **rephrase**
rather than appending it again — "smiling" instead of a trailing "happy"
`[C] (Future Tech Pilot, ioJ6istzwHw)`.

**Subject/setting order changes emphasis.** "portrait of X in a Y" and "photo of Y with X in it" produce
different images. If the result centers the wrong thing, flip the order
`[C] (Future Tech Pilot, ioJ6istzwHw)`.

**Short usually beats long.** Long prompts dilute which words the model actually weights
`[C] (Tokenized AI, vezJXJGQMoY)`. Precision of *idea* matters more than precision of language — you can
prompt casually as long as you fully describe the picture's content
`[C] (Future Tech Pilot, wEwYSBj0qBo)`. Occasionally a verbose prompt wins a composition a short one
misses `[C] (Wade McMaster, SjB_-GeI3FQ)`, but default to short. **Nine layers does not mean nine
clauses** — a layer that adds nothing for this image should be dropped, not padded.

### Density, not length — the pipeline exception `[I]`

This subsection does not supersede or delete the "Short usually beats long" line above, per this
skill's own conflict rule: never silently delete a cited corpus line. Both stay visible, with the
reason.

- The `[C]` finding concerns **padding and abstract quality claims** diluting which words get
  weighted — not the number of distinct visual attributes specified.
- A prompt that names its lens, its light direction, its palette, and its background separation is
  **denser**, not more diluted. A prompt that says `beautiful, striking, cinematic` is padding, and
  remains banned.
- **In pipeline mode all nine layers are mandatory** `[I]` with concrete renderable content in each;
  minimum 10 clauses and 60 words, enforced by Gate C's C12 (`scripts/lint_prompt_sheet.py`).
- Standalone mode is unchanged — the `[C]` default above still governs there.

The corpus's **six V8 visual anchors** do most of the heavy lifting and map cleanly onto the stack:
**style, distance, camera, behavior, material, mood** `[C] (Future Tech Pilot, ioJ6istzwHw)`. If a
prompt feels flat, check that all six are present before adding length.

## The buzzword ban

Do not write: `photorealistic` · `hyperrealistic` · `8k` · `4k` · `ultra-detailed` · `masterpiece` ·
`highly detailed` · `trending on ArtStation` · `award-winning` · `best quality`.

These are abstract quality *claims*, not visual descriptions — they tell the model nothing renderable.
Replace each with the concrete physical detail you actually mean:

| Instead of | Write |
|---|---|
| `hyperrealistic skin` | `visible pores, fine facial hair, natural skin texture` |
| `photorealistic` | the optics that make it read as a photo — `85mm lens, f/2.0, shallow depth of field` |
| `8k, ultra-detailed` | the material — `brushed steel with fine machining marks, faint fingerprints` |
| `masterpiece, award-winning` | the lighting — `hard directional morning sun, long shadows, subtle rim light` |

**Honesty about grounding `[I]`.** The supplied V8.2 runbook asserts these terms *actively degrade*
V8.2 output. That claim is **not verified** against Midjourney's documentation and is quarantined in
`v82-model-delta.md` — do not repeat it as fact. The ban stands anyway on its own merits: concrete
description outperforms abstract claims, which the corpus does support in the form "fully describe the
picture's content" `[C] (Future Tech Pilot, wEwYSBj0qBo)`.

**One corpus phrase survives the ban.** The photoreal cue `Photorealistic, DSLR, muted colors, shot on
35mm film.` is corpus-cited, with **DSLR** called out as the key realism trigger
`[C] (Tao Prompts, 2psBexPkw3I)`. `DSLR`, `35mm film`, and `muted colors` are all concrete and stay.
The leading word `Photorealistic` is exactly the kind of abstract claim this section rejects — **drop
it and keep the rest** `[I]`. Preferred form: `DSLR, muted colors, shot on 35mm film.`

## Raw mode — when to bypass Midjourney's taste

`--raw` turns off Midjourney's automatic creative styling. With simple prompts you get more realistic,
photo-like images; with stylistically detailed prompts it lets you dial in the exact look
`[T] (verified 2026-07-26)`.

**Use `--raw`** for commercial product shots, architectural visualization, documentary and street
photography, editorial portraits, and anything where prompt compliance beats visual flair. `--raw`
"most consistently favors realism, especially with real people" `[C] (Future Tech Pilot, Tv1dfGcOSnA)`.

**Omit `--raw`** for fantasy and concept illustration, painterly work, and mood pieces where
Midjourney's automatic polish and composition sense are an asset rather than interference.

`--raw` and `--stylize` are the same dial from two directions: `--raw` removes the house style, low
`--s` reduces its intensity. For maximum literalism use both; for a stylized-but-controlled look, omit
`--raw` and steer with `--s`.

## Stylize by look, not one global default

The corpus gives a single sweet spot of `--s 140–185`
`[C] (Future Tech Pilot, Tv1dfGcOSnA / ioJ6istzwHw; Tokenized AI, 1GnipTgvLI0)`. That is sound general
advice, but it was measured on general-purpose work, not split by intent. Split it `[I]`:

| Look | `--raw` | `--s` | Reasoning |
|---|---|---|---|
| **Photographic** (product, architecture, documentary) | on | **80–120** | Near the documented default of 100 `[T] (verified 2026-07-26)`; lets optics and lighting lead |
| **Balanced / editorial** | optional | **140–185** | The corpus sweet spot `[C] (Future Tech Pilot, Tv1dfGcOSnA / ioJ6istzwHw; Tokenized AI, 1GnipTgvLI0)` |
| **Stylized / branded** | off | **250–400** | Corpus: raise toward 300+ for a deliberately polished, branded look `[C] (Future Tech Pilot, Tv1dfGcOSnA / ioJ6istzwHw; Tokenized AI, 1GnipTgvLI0)` |
| **Fine art / illustrative** | off | **400–700** | Maximum interpretive freedom |
| **A long, detailed prompt is being ignored** | on | **50–80** | Corpus's documented remedy `[C] (Future Tech Pilot, Tv1dfGcOSnA / ioJ6istzwHw; Tokenized AI, 1GnipTgvLI0)` |

The lower photographic band is this skill's adaptation `[I]`, not a corpus finding — it follows from the
documented meaning of `--stylize` (low = literal to the prompt `[T] (verified 2026-07-26)`) applied to a
brief where literalism is the goal. Say so if asked.

## Text in images

Midjourney is weak at legible on-screen text; the corpus's guidance is to generate assets **with no
text** and composite captions or titles in a separate tool afterward
`[C] (Tokenized AI, qFYJb0zYztY)`. When a brief calls for text on the image, end the prompt with
`No Text.` and hand the copy to whatever does the compositing — in pipeline mode, that is
`shorts-assembly`'s caption treatment, never the prompt.

## Worked build

Brief: *a ceramic teapot, for a product page.*

1. Medium — `architectural product photography of`
2. Subject — `a matte ceramic teapot,`
3. State — `centered, faint steam rising,`
4. Environment — `on a dark slate countertop, minimalist tea house background softly out of focus,`
5. Composition — `three-quarter elevated perspective,`
6. Optics — `90mm macro lens, f/4.0 aperture, razor-sharp focal plane,`
7. Lighting — `diffused side lighting from a softbox, subtle fill light,`
8. Color — `cool neutral palette`
9. Parameters — `--ar 4:5 --raw --s 90 --hd`

```
architectural product photography of a matte ceramic teapot, centered, faint steam rising, on a dark slate countertop, minimalist tea house background softly out of focus, three-quarter elevated perspective, 90mm macro lens, f/4.0 aperture, razor-sharp focal plane, diffused side lighting from a softbox, subtle fill light, cool neutral palette --ar 4:5 --raw --s 90 --hd
```

No buzzwords. Flags last, space-separated, no punctuation among them. `--s 90` sits in the photographic
band. `--ar 4:5` is well inside the 4:1 `--hd` ceiling.
