# Midjourney Prompting & Asset-Creation Guide (Image + Video)

**For a faceless content creator. Current as of 2026-07-23.**

This guide covers best-in-class Midjourney (MJ) prompting, every major parameter and feature, reference/consistency workflows, and image→video asset creation — synthesized from four working MJ YouTube channels (`[C]` findings) plus a web-verified feature snapshot (`[T]` facts). General craft not tied to a specific source is marked `[I]`.

> **Verify the version/pricing specifics — MJ moves fast.** Everything tagged `[T]` (versions, defaults, plan prices, resolution caps) is a 2026-07-23 snapshot. Confirm exact parameter behavior at `docs.midjourney.com` before relying on it. The prompting *fundamentals* (`[C]`/`[I]`) are far more durable — one channel re-recorded its whole course for V8.1 and found "the concepts stood the test of time; only the tools change" (Wade McMaster, `CVRaDA9qHqw`).

> **Provenance legend:** `[C]` = from channel findings, cited `(Channel, video_id)`. `[T]` = current-feature fact (feature notes, "as of 2026-07-23"). `[I]` = general practice.

> **Asset-workflow pointer:** For where these stills/clips slot into a short-form pipeline (hook plate → b-roll → hero cutaway → export), see the shorts production playbook's asset workflow. This guide is the *upstream* generation manual that feeds it.

---

## 1. Current state — V8.1 snapshot `[T]`

| Item | Status (as of 2026-07-23) |
|---|---|
| **Default image model** | **V8.1**, promoted 2026-06-11. ~4–5× faster than earlier; **native 2K HD** output (no separate upscale step). |
| **New in V8.1** | `--raw`, `--hd`/`--sd` options; HD is now 3× faster/cheaper and the default at **2048×2048** (standard = 1024×1024). |
| **V7** | Still fully selectable in settings. Introduced Draft Mode, default Personalization, **Omni Reference**. |
| **Omni Reference** | Currently **V7-only**; an improved V8 version is in training. This is the current character-consistency tool. |
| **V6 / Niji era** | `--cref` (character reference) largely superseded by Omni Reference in V7+. |
| **Access** | Web app (`midjourney.com`) **+ Discord**. V8/8.1 launched on `alpha.midjourney.com`; settings panel position varies by screen size/zoom `[C]` (`0BaPLR3stHc`). |
| **Plan tiers** | Basic ~$10 · Standard ~$30 · Pro ~$60 · Mega ~$120. Fast-GPU hours + relax mode vary by tier. |

**Plan notes from creators `[C]`:** The **$30 Standard plan** is repeatedly called the best-value mid-tier — "never ran out of video credits on the $30 plan" (Tao Prompts, `uCsc0ORcJDo`, `elCv87a4iK4`). **Relax mode** is unlimited on Standard/Pro; route non-urgent jobs there to conserve fast GPU hours, and generate off-peak for shorter queues (Tokenized AI, `o9F_9xKfMNs`). **Stealth mode** (Pro+) keeps generations private — by default all MJ images, prompts, params, and seeds are public and reproducible by anyone (Tokenized AI, `Od11XU98kfE`).

**Reality check on MJ's scope:** MJ's image model is best-in-class for aesthetics/photorealism `[C]` (Tao Prompts, `Dk_duA28W5k`), but its **video generator ranks poorly (D-tier)** — jittery camera, choppy motion, weak prompt-following (Tao Prompts, `uCsc0ORcJDo`). Treat MJ as your **image engine** and animate elsewhere (see §9).

---

## 2. Prompt anatomy & best-in-class prompting

### The core ordering rule
Midjourney **weights earlier words more heavily**; words far back in the prompt often fail to appear `[C]` (Tokenized AI, `4DrNl5lNapo`). Two independent tactics follow from this:
- **Move ignored words to the front.** "Happy" at the end was dropped, but worked when moved forward — or rephrase ("smiling" instead of "happy") (Future Tech Pilot, `ioJ6istzwHw`).
- **Swap subject/setting order to change emphasis.** "Vogue portrait photo of Walter White in an RV" vs "photo of a dirty RV with Walter White in the back" yield different images. Flip them if unhappy (Future Tech Pilot, `ioJ6istzwHw`).

### Recommended token order `[T]` + `[C]`
> **Medium → subject + action → environment/context → composition/shot (camera, lens, angle) → lighting → style → color/mood → parameters.**

Structure it **medium-first, then subject, then environment, then style** so MJ weights the most important elements toward the front (Tokenized AI, `4DrNl5lNapo`).

### The six V8 "visual anchors" `[C]`
Build V8 prompts around six anchors — **style, distance, camera, behavior, material, mood** — the current V8 "meta" that does most of the heavy lifting (Future Tech Pilot, `ioJ6istzwHw`):
- **Camera behavior:** low-angle fisheye, drone, aerial, portrait, side profile.
- **Subject behavior/pose:** an action like "hands pointing at the camera" adds life and escapes static AI images.
- **Material/texture on a smooth→rough scale:** smooth vs rough oil painting; minimal vs ornate design; silk vs denim costume.

### Length: short usually wins `[C]`
- **Short prompts are usually fine and often beat long bloated ones** — long prompts dilute which words matter (Tokenized AI, `vezJXJGQMoY`). Reserve extreme detail for a specific replicated result.
- **In V8, precision of *idea* matters more than precision of *language*.** You can prompt casually as long as you fully describe the picture's content (Future Tech Pilot, `wEwYSBj0qBo`).
- **But verbose can occasionally win a composition** short prompts miss — only "on the screens of a 1980s media wall made of many CRT-TVs" produced a wall of TVs (Wade McMaster, `SjB_-GeI3FQ`).
- MJ flags **overly long prompts** and offers to shorten them, at the cost of some variability (Wade McMaster, `xtJWfxXnhrM`). Use **`/shorten`** to see which words MJ actually weights — it returns five shortened variants and per-word numeric weights; long prompts often reduce to ~five load-bearing words (Tokenized AI, `1GnipTgvLI0`).

### V6-style prose + iterative build `[C]`
For coherence-heavy work, use **full natural-language sentences** and build detail iteratively from a bare skeleton — start "photo of a young man lounging on an orange bean bag," then add composition, wardrobe, atmosphere one pass at a time (Tokenized AI, `K14vPyWOSYw`). A **closing atmosphere sentence** ("the atmosphere is serene, capturing the essence of a quiet personal retreat") adds a subtle final polish.

### Reusable prompt skeleton `[I]` (built from the findings)
```
[medium] of [subject + defining features], [subject behavior/pose],
in [environment/context], [composition — camera angle, lens, distance],
[lighting], [style / art movement / artist], [color palette / mood]
--ar [ratio] --style raw --s [stylize] --c [chaos] [--sref CODE]
```
Worked minimal-to-full example (V6-style iterative build):
```
Pass 1: photo of a young man lounging on an orange bean bag
Pass 2: ...low-angle medium shot, soft window light from the left
Pass 3: ...wearing a charcoal knit sweater, holding a coffee mug
Pass 4: ...muted earth-tone palette, the atmosphere calm and personal --ar 4:5 --style raw --s 150
```

### Always run multiple aspect ratios `[C]`
Ratio drastically changes composition — try **square, wide, and vertical** for every prompt (Future Tech Pilot, `Tv1dfGcOSnA`). Match ratio to intended output *before* generating: layout concepts work better square; a vertical destination needs `--ar 9:16`.

---

## 3. Parameters reference

Type parameters **in-prompt** (`--s 250`) rather than relying on settings — it's per-job and explicit `[C]`.

| Parameter | What it does | Typical values | When to use |
|---|---|---|---|
| **`--ar w:h`** | Aspect ratio (numbers are ratios: `10:5` = `2:1`). | `1:1`, `16:9`, `9:16`, `2:3`, `4:5` | Always set for the destination. `9:16` for Shorts, `16:9` for YouTube stills. `[C][T]` |
| **`--stylize` / `--s`** | 0–1000, default 100. Trades prompt-accuracy (low) for MJ house beauty (high). Higher = more subject-centric. | `50–80` for long prompts MJ ignores; `~140–185` sweet spot; `300–800` for beauty; `1000` to apply a profile/sref/moodboard hard | Raise for aesthetics; **lower** to force literal prompt adherence. `[C]` (`Tv1dfGcOSnA`, `ioJ6istzwHw`, `1GnipTgvLI0`) |
| **`--chaos` / `--c`** | 0–100, default 0. Grid variety ("variety" in settings). | `3–9` (9 favored) for gentle variety; `40` on a draft grid for max spread | Raise to explore; keep low for tight control. `[C]` (`Tv1dfGcOSnA`, `fMEvMqvzUbc`) |
| **`--weird` / `--w`** | 0–3000. Unconventional/experimental aesthetics. | `1–50` (keep very low) | Rarely; it lives up to its name. `[C]` (`Tv1dfGcOSnA`) |
| **`--raw` / `--style raw`** | Reduces MJ's default stylization; more literal, more realistic. | on/off | **Realism, especially realistic people**; fixing over-styling; text (raises success). `[C][T]` |
| **`--quality` / `--q`** | Render time/detail. | `--q 4` to raise text-render odds (extra cost) | Text troubleshooting; fine detail. `[C]` (`wEwYSBj0qBo`) |
| **`--hd`** | Native 2K reprocess (behavior change, not just resolution); ~4× file size; locks seed. | on/off | Final hero stills. **Turn off in settings** — it drains fast hours. `[C][T]` |
| **`--no`** | Negative prompt (exclude). Works best for **removing colors**; unreliable generally. | `--no red`, `--no skin` | Remove a color/element (e.g. `--no skin` to render tattoo art on plain bg). `[C]` (`Tv1dfGcOSnA`, `IS0Kk9OFaZQ`) |
| **`--seed`** | Locks the generation blueprint (1 to ~4B). | any int | Reproducibility; A/B one variable. With a fixed seed + one small word changed, V8 stays **~94% identical**; big subject swaps break it. `[C]` (`ZPJB6jurDfE`) |
| **`--tile`** | Seamless repeating patterns. | on/off | Textures/patterns. Newer versions may leave a visible seam. `[C]` (`Tv1dfGcOSnA`) |
| **`--iw`** | Image weight — how hard an image reference counts vs text. V8.1 range **0–3**, default 1. | `0.5` ≈ colors only; `2–2.5` near-copy; **halve each pass** (2,1,0.5,0.25) when re-applying | Balance a dropped-in image vs the prompt. `[C][T]` |
| **`--sref [code/url]`** | Style reference (see §5/§7). | code, url, or `random` | Reuse a look across a set. `[C][T]` |
| **`--sw`** | Style-reference weight, 0–1000, default 100. | `40` dampen; `1000` intensify | Dial sref/image-style strength. `[C]` (`Tv1dfGcOSnA`) |
| **`--sv`** | Style version (v7 only), values 1–4. | `--sv 4` | Render a v6 sref code correctly under v7. **Not in v8.** `[C]` (`PEl1Rb9spsk`) |
| **`--repeat`** | Reruns the prompt N times. | `--repeat 5/10` | Sample many styles at once (great with `--sref random`). `[C]` (`Tv1dfGcOSnA`) |
| **`--niji`** | Anime/illustration sibling model. | `--niji 7` (or set default) | Anime; handles text well; most params still apply. `[C]` (`Tv1dfGcOSnA`, `rLEFjBu8X-M`) |
| **`--exp`** | Experimental, 0–100, default 0. Not in settings. | `8–15` (big shift ~15; photo-shoot look ~35) | Unpredictable aesthetic nudge. `[C]` (`Tv1dfGcOSnA`) |
| **`--preview`** | Early access to an unreleased model (~V8.2 at capture). | on/off | Pairs well with mood boards/personalization; not guaranteed stable. `[C]` (`Tv1dfGcOSnA`, `fMEvMqvzUbc`) |
| **`--motion`** | Video motion level (see §9). | `low` / `high` | Overrides the animate button. `[C]` (`Dkj7Jqejfz0`) |

### `::` multi-prompt weighting `[C]`
Activate multi-prompts with a **double colon** and an optional integer weight per segment; omit the integer for a default weight of 1. Weights are **ratios/parts of a sum** — like mixing a cocktail, not absolute values (Tokenized AI, `fjIjF0CfHaw`).

- **Layered multi-prompts:** treat each `::` segment as a painting layer (base scene → subject → lighting) and **repeat the style/medium token in every layer** or the blend drifts to another style.
- **Mirrored:** restate a critical element in a separate segment with different words to reinforce it (`attractive businesswoman standing in the street:: woman wearing black pantsuit`).
- **Negative-weight:** append a segment with a small negative weight to subtract an unwanted quality (e.g. `photography::-.5` to remove photo-realism from an illustration). V8 has **no `--no` negative parameter** — you exclude in natural language, imperfectly (Future Tech Pilot, `0BaPLR3stHc`); asking directly for the color you *want* is more reliable.
- **Per-image weights:** give each image URL its own `::` weight (`image1::1 image2::2 text::3`) for 100% unique blends others can't reproduce (Tokenized AI, `Od11XU98kfE`).

### Permutations (curly braces) `[C]`
Wrap alternatives in `{}` to fan one prompt into many jobs: `{a samurai, a city street, a woman's face, a waterfall}` generates a separate prompt per comma item — ideal for populating mood boards or sweeping a setting like `--stylize {0,100,1000}` or `{1,2}` on image weight (Wade McMaster `PEl1Rb9spsk`; Tokenized AI `o6cAA8jziPU`). **Permutations do NOT work inside a remix/reroll window.**

---

## 4. References & consistency

The V8 "full meta" stacks **prompt detail + parameters + references (srefs + mood boards)** — combined they produce the strongest images, and you can turn a great generated image into a style reference and double it with a mood board (Future Tech Pilot, `ioJ6istzwHw`). **Anchor prompts with visual references** or you get MJ's default, which you likely won't love (Future Tech Pilot, `SVX2Hzi-Idc`).

### The four reference tools
- **Style Reference `--sref <code|url>` (+ `--sw`)** `[C][T]` — ties an aesthetic to a number. Billions of shareable codes; `--sref random` picks one. An sref's look **depends heavily on the subject and the front-of-prompt words** — the same code renders differently by subject, and adding "oil painting" up front shifts it (Future Tech Pilot, `GAT5A6MqM-E`). Some shared codes require `--niji 7` or `--raw` to hit their intended look. **Drag any image** into the style-reference box to reproduce a look you have no code for.
- **Mood boards `--p <code>`** `[C][T]` — curated reference sets defining a custom style profile; the **most control** because you upload the exact images to emulate (Wade McMaster, `TtkenI4wt8I`). Influence is controlled by **`--s` (stylize), not a separate weight** (~50 is a sweet spot; 1000 = max) (Future Tech Pilot, `Tv1dfGcOSnA`). Each board has a long code + a shorter shareable code.
- **Personalization `--p` (no code)** `[C][T]` — MJ learns your taste; on by default in V7. Train by clicking images you like (V8's grid also counts the ones you *don't* pick). Hold multiple named profiles (V6, V7/V8, Niji).
- **Image prompt `--iw`** `[C][T]` — drop an image at the top; blends ~50/50 with text, weighted 0–3 (`0.5` ≈ colors only, `2.5` ≈ near-copy).

### sref version compatibility `[C]`
**V6 codes are incompatible with V7/V8; V7 and V8/8.1 codes are interchangeable** (Wade McMaster, `PEl1Rb9spsk`). To reuse a v6 look in v8: generate it in **v6.1 first, then drag that output into a v8 prompt as a style reference** — or load v6-code generations into a **mood board** and generate with v8.1 selected. In v7 only, `--sv 4` makes a v6 code render.

### Character consistency workflows
The current V7+ tool is **Omni Reference `--oref <url> --ow <0–1000, default 100>`** `[T]` — attach a character image with a scene prompt and MJ places that character into the new environment while preserving style. Do NOT confuse `--ow` (omni weight) with `--iw`/`--sw`.

**Building a reusable character `[C]`:**
1. **Character reference sheet, four angles.** The standard prompt asks for four vertical columns (front, left profile, right profile, back), each with a full-body shot on top and a matching close-up below, plain background — this locks appearance across angles for later images *and* video (Tao Prompts, `2psBexPkw3I`). Build one from an existing character by adding "based on the uploaded image."
2. **Separate sheets per major state** (helmet on/off, with/without weapon) or the AI drifts (Wade McMaster, `g1SRS7-Bqlk`).
3. **From one full-body image**, generate every angle in a chat editor (Nano Banana Pro): prompt distance changes (zoom out, close-up, extreme long) and angle changes (low "seen from below," high "seen from above," Dutch, bird's-eye, over-shoulder, POV) (Tao Prompts, `rZtjmaLef1U`). Keep **lighting consistent by describing the light source** ("light gray dreary day with subtle orange light from the lava"), not "muted colors" (which goes flat gray).
4. **Nine shots in one image:** a "cinematic 3×3 grid presenting multiple camera angles" + subject + angle list + "consistent subject appearance across all frames" + "no grid lines and no borders. No Text" (Tao Prompts, `OA5g63cBp7A`). In grids, faces drift and small faces become blurry blobs — **crop a good face and reuse it** to regenerate.

**MJ-native (Vary/Pan/Zoom) `[C]`:** Character consistency can start from a headshot on white, then **Vary Strong** to add scene/wardrobe, **Pan** to extend the body, **Zoom** to widen context — constant feature-switching balances out anatomy deformations (Tokenized AI, `4DrNl5lNapo`). **Don't Pan more than once or twice** or body proportions warp. Reintroduce a character into a new panel by pasting its **full original character text prompt** into the Pan/remix window.

**Face-swap methods `[C]`:**
- **Insight Face Swap** (Discord bot) — near-perfect facial consistency: `/saveid` a headshot (up to 10 IDs, ~50 free credits/day), then INSwapper/`/swapid` into any MJ image (Tokenized AI, `gtclb5aiN34`). **Leans photorealistic — fails on comic/line-art** and swaps *all* faces in a multi-character image at once. Fix illustrated art with a second Stable Diffusion inpaint pass (Roop, denoise ~0.4) to re-apply the style (`G-c7BlEyuP8`).
- **Vary Region face-swap** — paste an upscaled image's URL as the region prompt over the target face; best when heads are similar-shaped (Tokenized AI, `bRYFObeyzR0`).

**Multi-character interaction:** **MJ cannot combine two characters interacting in one shot** — use **Nano Banana** for character-to-character composition, describing the spatial relationship explicitly ("a close-up side profile of the large orc with a hammer surrounded by human soldiers") (Tao Prompts, `4tpDAX23RL0`, `4tpDAX23RL0`). Put all references into **one collage image** rather than separate uploads to preserve each likeness. Nano Banana 2 accepts up to **14 references** but per-character likeness degrades as you add more.

**Cheapest consistency:** a **fixed seed alone** with a fixed character prompt is good-enough for trailer shots where perfection isn't critical (Tokenized AI, `MfK-WkKUnKQ`).

---

## 5. Modes & editing

| Feature | What it does | Key notes `[C]`/`[T]` |
|---|---|---|
| **Draft Mode** (lightning-bolt toggle or `--draft`) | 24 low-res (512×512) images, ~1/10 cost, ~5× faster. | Concept/direction-finding, NOT final. Any draft image upscales to full V8.1 via **"very subtle"** (even with draft still on), then optionally HD. **Turn it off** before real generations. Pair with high chaos to explore. |
| **Vary (Region)** = inpaint | Select an area (rectangle/lasso) and prompt only that region. Requires remix mode. | Good at add/remove objects, swap outfits/expressions. **Reads whole-image context**, so it's less faithful and struggles in dense scenes; select a *wider* area to remove objects. **Fails at whole-character replacement** (e.g. gender swap). Clear prior selections (undo) before a new one. |
| **Pan / Zoom Out / Outpaint** | Extend the canvas (1.5×, 2×, make-square, custom-zoom 1–2). | Does **not** increase resolution. More zoom-out = more artifacts. Panned regions inherit stale prompt words — **rewrite the prompt for the new area**. |
| **Remix** | Change the prompt while keeping composition. Toggle via `/settings` or `/remix`. | Required for Vary/Pan/Zoom to open an editable prompt window. **Vary Strong** = high variation; **Vary Subtle** = low variation (composition-focused). |
| **Blend** | Merge images. | Blended outputs look smooth/unreal — refine with a very-subtle remix using a synthesized text prompt (§8). |
| **Permutations** | Batch prompt variants via `{}`. | See §3. Not available inside a remix window. |
| **Retexture** | Restyle keeping structure. | `[T]` |
| **Editor** | Web canvas edit. | `[T]` |
| **Describe** | Drag an image in → four prompts reverse-engineering the look. | Learn richer vocabulary; add the source as an sref to get regenerations closer to the original. `[C]` |
| **Conversation mode** | LLM rewrites your prompt (even by voice). | Chatbot-style interpretation, useful in 8.1 for complex asks (five-panel meme with stylized text). `[C]` |
| **Envelope reaction** (Discord) | DMs the four grid images as separate files + the hidden seed. | The way to retrieve a seed not shown in the prompt. `[C]` |

**Upscaling caveat `[C]`:** Converting a standard V8.1 image to **HD can change the image substantially** — it's an unreliable upscaler substitute (a dedicated upscaler was "coming"). For real enlargement use external tools (§8).

**Adjacent editors (name the tool) `[C]`:** For precise/whole-scene edits MJ is weak at, creators reach for **Nano Banana 2 / Pro** (prompt "keep the rest of the layout and scene identical" for small edits; `@image1`/`@image2` tags to target sources; colored-annotation edits with a legend), and **Adobe Firefly/Photoshop Generative Fill** ("relight and clean up this photo *so it looks like professional photography*"). Firefly is **commercially safe** (licensed Adobe Stock training).

---

## 6. Styles & aesthetics

### How to get a specific look
- **Append style phrases at the end, comma-separated**, to restyle any subject (`3D-rendered iridescent glass`, `found camcorder footage`) — a whole "style volume" format (Wade McMaster, `AaelDla4F7U`). **Swap a single word** inside a style phrase to tailor without rewriting ("golden neon" → "lime neon"; "as a guinea pig" → any animal).
- **Stack multiple descriptors** in one phrase to blend (`analog, punk zine aesthetic, symmetrical design with halftone dots`), and pull compound styles apart to remix ("chaotic rough charcoal sketch" → "chaotic pen/pencil/painting") (Wade McMaster, `gLG_5_Mp6kM`).
- **Name a real artist** — high-leverage with little text. Formulas: `subject in the style of ARTIST` (default); `artwork by ARTIST of subject` (prioritize the artist); `a MEDIUM (drawing/sculpture) of subject by ARTIST` when the artist worked across formats (Wade McMaster, `P48xB2zNM80`). MJ **interprets** rather than exactly reproduces; famous artists align better than obscure ones. Specify the medium ("a sculpture of," "building designed by") when an artist worked in several.
- **Descriptive effect styles** ("bold linocut print," "high-contrast B&W photocopy," "dusty folded passport photo") change *presentation, not the subject's form* — and you can dictate colors within them (Wade McMaster, `QcGYg5uiTLk`).
- **Knolling** — "knolling of \<items\>" lays objects flat in a neat 90° grid and communicates the direct-overhead angle for free; add surface ("on snow"), layout ("symmetrical, circular"), color, or style words (Tokenized AI, `UFH1GQDirtI`). One of the highest-ROI prompts.

### sref libraries & discovery `[C]`
- **`--sref random` in draft mode** → 24 images each with a unique reusable code (add `--repeat 5` for 120 codes). **Blend codes** by space-separating them, weighting each with `:n` (`code1 code2:3 code3:0.5`). **Double up two `--sref random`** for wilder novel styles.
- **Explore page → Styles** — sort by top day/week/month, hot, or random; click to copy a code, heart to save. Search finds codes by aesthetic word ("cinematic").
- **Style Creator** — click images matching a target aesthetic until it hits the "ideal minimum"; the resulting custom code lands on your Create page. Treat it as **discovery, not building to a fixed target** — the **first style you pick has the biggest influence** (Future Tech Pilot, `KgWRMNlZ9rs`).
- **Void prompt** — type meaningless symbols instead of a subject to see a style's *true essence* during exploration (Future Tech Pilot, `vqg-fUi98x8`).
- **Formalize a favorite** into a **mood board** (permutations → many subjects → "add from creations") for forever-access, strengthened with `--stylize` up to 1000.

### Camera & cinematography vocabulary `[C]`
Core AI-film camera moves: **static, rack focus, dolly (physical forward/back), pan (rotate on a swivel), truck (slide on a track), tilt/pedestal (vertical), orbit (circle subject), Dutch angle (tilt for unease)** (Tao Prompts, `Zh45I_eVb6k`). Prefix **"fast"/"slow"** to a move to control speed. Note AI can't reliably distinguish a pan (rotate) from a truck (slide) — use "camera rotate" explicitly; guide orbit direction by naming a **landmark** ("rotate behind the Viking"), not left/right.

**Style-consistency across shots:** a strong subject **color bleeds** into a color-driven style — generate a **subject-free base** (with "no animals and creatures") first, then remix, to avoid feature bleed (Tokenized AI, `lCFzMnBDqEc`). Reinsert the **medium token at the front** of a remix prompt ("graphic novel illustration") or the result drifts to photorealism.

**Model-fit for styles `[C]`:** For nailing art styles, **MJ 8.1 ranks first, then GPT Image 2, then Nano Banana 2** (which imposes its own cartoony look) (Wade McMaster, `SkzG7_Ya99M`). There's an **intelligence-vs-aesthetics tradeoff**: pick the less "intelligent" model (MJ) for pure aesthetics; a smarter model (Nano Banana 2) for semantically demanding effects (a real heat-map, an accurate era change).

---

## 7. Realism & quality

- **`--raw` / `--style raw` for realism**, especially realistic people — it most consistently favors realism (Future Tech Pilot, `Tv1dfGcOSnA`).
- **Generate SD first, rerun the keepers as `--hd`** (2048², ~5MB vs ~1.5MB; a behavior change, not just resolution — can differ even at the same seed) (Future Tech Pilot, `Tv1dfGcOSnA`, `0BaPLR3stHc`, `t_xIYKk2ERk`).
- **MJ focuses detail on the foreground** and gets loose with backgrounds (often masked by throwing them out of focus). Nano Banana 2 has the cleanest fine detail; **MJ maxes at 2K while GPT Image 2 / Nano Banana 2 reach 4K** (Wade McMaster, `SkzG7_Ya99M`).
- **MJ v6 handles hands/feet worse than v5** — a current limitation to watch (Tokenized AI, `K14vPyWOSYw`).
- **Fastest quality lift:** set **black and white levels with eyedroppers** in a levels panel (pick darkest with black, brightest with white, slide the mid triangle) — far moodier (Future Tech Pilot, `vqg-fUi98x8`).
- **V8.1 restores ~90–95% of V7's aesthetic** with V8's higher prompt intelligence — creators **float between V7 and V8.1 by preference** rather than always using the newest (Wade McMaster, `xtJWfxXnhrM`).

### Camera/lens language for photorealism `[C]`
End character-sheet/portrait prompts with **"Photorealistic, DSLR, muted colors, shot on 35mm film. No Text."** — **DSLR is the key realism cue** (Tao Prompts, `2psBexPkw3I`). For *video* realism, name the **exact real-world medium** ("VHS camcorder footage," documentary, smartphone) — never leave the medium to the AI — and use **motivated/natural light** (a window, a single lamp) not perfect studio light (Tao Prompts, `LOAHPLUbmPQ`).

### Upscaling `[C]`
- **Choose by need:** Firefly for accuracy (safe all-rounder, retains grain), **Topaz Gigapixel** for max resolution + face recovery, **Topaz Bloom** for sharpest scenery detail (regenerates, so not for portraits) (Wade McMaster, `zteVoDeS2hw`).
- **Nano Banana 2 as a fallback upscaler:** prompt "4K, enhance details, keep layout and look identical, crisp professional photograph" (can't exceed 4K).
- **Two-stage for video:** upscale the still (Magnific, resemblance slider) → generate video → upscale the video (Topaz, up to 4K/8K) (Tao Prompts, `sYYZ_MyB-zU`).
- Add a **16mm film-grain overlay** (~30% opacity, overlay blend) + slight desaturation to defeat the too-perfect AI look — "grain should be felt, not seen" (Tao Prompts, `LOAHPLUbmPQ`; Wade McMaster, `g1SRS7-Bqlk`).

---

## 8. Video generation & motion (image→video)

> **This is the section the faceless creator needs most.** MJ makes the *stills*; the motion mostly happens in adjacent tools. Every non-MJ tool is named inline.

### Midjourney's own image→video `[C][T]`
- **Image-to-video only**, ~5s per clip, extendable in 4s steps to ~**21s**; HD video is only 720p, no video upscaler. You must supply a starting image (Future Tech Pilot, `Dkj7Jqejfz0`).
- **Expensive:** a default video grid ≈ 8 GPU minutes (~8× an image); **HD video ≈ 25**. Pro relax-unlimited applies to **SD video only**.
- **~25% success rate** — keep batch at 4 for decent odds.
- **Prefer low motion** (`--motion low`) for coherence; high motion looks cinematic but gets wacky. Watch out: a manual high-motion job **silently makes high motion your default** (costly) — restart the manual process to reset.
- **Prompt levers that work:** include **speed** ("quickly"/"slowly") — the single most helpful lever, and it makes otherwise-ignored camera moves happen. Keep prompts **simple** (only ~5s to animate). Phrase camera moves as *what the camera sees now → what it will see* ("the camera zooms out to reveal she is in an aquarium"). Motion words: **"shimmy" not "dancing"**; add **"slightly"** to tone down exaggerated emotion. "**static still wallpaper**" + low motion approximates a still.
- **Don't use MJ's extend** — coherence decays fast; instead **extract the final frame** (open video in new tab, right-click save frame) and start a new generation from it, stitching in an editor. **Ctrl/Cmd+scroll** scrubs playback frame-by-frame.
- **MJ video animates text/logos and grids/collages especially well** (Future Tech Pilot, `Dkj7Jqejfz0`). But overall it's D-tier for motion (Tao Prompts, `uCsc0ORcJDo`) — use it for simple hero-still motion, animate elsewhere for anything dynamic.

### The five methods of AI video `[C]` (Tao Prompts, `9os35azf4Jw`)
1. **Text-to-video** — simplest, least controllable. **Never start from a bare text prompt** — make a reference image first (Tao Prompts, `RUAuMD5hUBw`).
2. **Image-to-video** — the recommended default; animates a reference image.
3. **Elements-to-video (ingredients)** — mixes multiple references; easy but lower quality and less dynamic (characters drift). **Combine elements into one image first, then image-to-video.**
4. **Lip sync** — talking characters (§below).
5. **Video-to-video** — AI motion capture / motion transfer.

Six deeper features go beyond prompting: image-to-video, multi-shot, **start/end-frame keyframing**, motion transfer, dialogue, video editing (Tao Prompts, `lbMcDszm0Mc`).

### Start/end-frame keyframing `[C]` — the control workhorse
Supply the **first and last frame** and prompt the transition to direct transformations and precise camera moves (Tao Prompts, `lbMcDszm0Mc`; Wade McMaster, `ckeY9tswmrM`):
- **Generate the start frame, then edit *that same image*** into an end frame (angle/pose/lighting change) in Nano Banana 2, and feed both to **Seedance 2 / Kling**.
- When editing an end frame, **describe both the new camera angle AND what's visible from it** ("look down from above so we see the top of the pyramid and the streets").
- **Start-and-end frames must be related** (a variation or one-detail edit) — two random images produce a jarring cut.
- **Any-Frame-to-video** lets you place **up to six intermediate keyframes** on a timeline for full motion control; space frames out (tight spacing / complex motion is harder to interpolate) (Wade McMaster, `D-dB2sdsMIk`).
- **Kling start/end frame** excels at seamless transformations (water orbs → water shield; illustration → real photo); chain differing angles to fly the camera around a fight; 5s clips suit fast motion (Tao Prompts, `4zu2CclB-EI`, `sYYZ_MyB-zU`).

### Multi-shot & directing `[C]`
- **Seedance 2.0 is the best multi-shot model** (one prompt cuts between angles/dialogue seamlessly) but the most expensive (a 10s clip can top $5 vs ~30¢ for Google Omni) (Tao Prompts, `RUAuMD5hUBw`).
- **Structure multi-shot prompts with explicit timestamps + referenced images:** "0–3s: wide tracking shot of both explorers (image one); then close-up on the female explorer (image two) saying [line]" (Tao Prompts, `UHv61jUBx7M`). Or hand Seedance just an idea + an establishing reference and let it direct.
- **Multi-shot is still unreliable** — rendering **separate single shots and editing them together** yields higher quality (Wade McMaster, `g1SRS7-Bqlk`).
- **`@image1`/`@image2` tags** (type `@`) point each prompt part at the right labeled reference (images labeled in upload order) — works in Seedance/OpenArt/Higgsfield/Nano Banana (Tao Prompts, `UHv61jUBx7M`; Wade McMaster, `H29b2gjX6Kg`).

### Prompt techniques for motion `[C]` (Tao Prompts)
- **Keep it short** — 1–2 characters, 1–2 actions; think like a director but stay concise. Complexity adds *control*, not quality (`9os35azf4Jw`, `4LI8JKPdOmU`).
- **Anchor prompts** — restate details the model can't currently see ("he has red embers and ash on him") so later frames stay consistent; describe off-screen details before a camera rotation reveals them (`zzBmvzR-URg`).
- **Negative prompts** — state what you *don't* want ("no windows," "completely silent, no gunshots") — easier than describing the result and suppresses auto-added SFX.
- **Repeat critical instructions** ("static camera" at both start and end) to enforce them (`9os35azf4Jw`).
- **Restate framing** even when the reference defines it ("start with a side profile of the woman") (`M7p7HrJjcdA`).
- **List actions chronologically**, describe the *mechanics* of movement, add timestamps (`ckeY9tswmrM`).
- **"in a single shot" / "no cuts"** stops big moves being auto-split (`ckeY9tswmrM`).
- **"no subtitles and no music"** on every Seedance prompt — it burns in subtitles/music that ruin splicing (`JQzF5LP4VTs`).
- **JSON vs prose** — JSON organizes keywords cleanly but produces the **same** result as an equivalent prose prompt; its value is easy swapping for large databases/teams (`4LI8JKPdOmU`).
- **Seven prompt styles** cover any AI video: cinematic, timestamp, cutscene, GPT, anchor, image, negative (`zzBmvzR-URg`). Cutscenes break style consistency if you cut too far from the original shot.

### Realism rules for AI video `[C]` (Tao Prompts, `LOAHPLUbmPQ`)
- **Keep subjects large in frame** (close/medium) — more pixels = better lip-sync, expressions, gestures; small/distant subjects melt.
- **Two-to-three subjects max** — big crowds vanish, turn to smoke, or all do the same action.
- **Smaller/slower/continuous motion** looks far more realistic; the word "slow" keeps animation smooth — **speed it up in the editor** later.
- **"in the same visual style as image X"** keeps lighting/color coherent across shots.

### Model landscape (2026) `[C]`
| Model | Strength | Watch out |
|---|---|---|
| **Kling** (A-tier) | Sharp detail, prompt adherence, explosive over-the-top action; best dedicated **motion transfer**/lip-sync mapping. | Fast fight motion can warp/flicker bodies. `uCsc0ORcJDo`, `4tpDAX23RL0`, `elCv87a4iK4` |
| **Google Veo 3** (B-tier) | Dialogue/audio, small movements, consistency. | Smooths/washes detail; **max 8s clips**; big action lacks impact. `uCsc0ORcJDo`, `4tpDAX23RL0` |
| **Seedance 2.0** (top multi-shot) | Organic human movement, action choreography, cinematic audio, multi-modal refs (image+audio+video), ordered multi-action; ~90% usable. | Most expensive; hard to use photorealistic-*people* refs (create by text); geo-restricted, higher-tier plan, launched 720p. `gpkbPCrGF6g`, `ckeY9tswmrM`, `UHv61jUBx7M` |
| **Sora 2** | Memes/short-form only (A-tier there). | Heavily censored; blocks people images for image-to-video. `uCsc0ORcJDo` |
| **Google Omni** | Cheap (~30¢/10s) video *editing* (style transfer, character swap). | Max 10s, heavily censored, blocks character-ref images, weak high-action. `elCv87a4iK4` |
| **Runway Gen-2** | Motion Brush (mask up to 5 regions, each with direction + z-axis). | Hit-or-miss, distorts faces (best on close-ups). `vezJXJGQMoY`, `MfK-WkKUnKQ` |
| **Midjourney** | Its **image** model. | D-tier video: jittery, choppy, weak prompt-following. `uCsc0ORcJDo` |

**Common across models:** most add **too much motion**; Veo/WAN/Grok smooth detail; people deform in big motions; extend features "lose the plot." **Test multiple generators** — each renders the same prompt with different intensity (Tao Prompts, `Zh45I_eVb6k`, `uCsc0ORcJDo`). On an **all-in-one aggregator** (OpenArt, Higgsfield, InVideo, Dzine, Artlist) you can switch per task.

### Extending & stitching `[C]`
- Seedance has **no native extend** — attach the prior clip as a **video reference**, keep the character sheets, and prompt "**Extend @video one**" + the new action; **re-describe the exact ending** of the prior clip or it loses the plot (Tao Prompts, `j8ImtURt9-0`).
- **Re-attach character reference sheets on *every* extension** — a common credit-waster (Tao Prompts, `j8ImtURt9-0`).
- Joining two clips almost always shows a **small jump cut** — trim/nudge the timeline in an editor.
- Animate a 12-panel storyboard **one row (4 panels) at a time**, not all 12 in one clip; extract each row's last frame as the next row's first frame for seamless transitions (Tao Prompts, `JQzF5LP4VTs`, `KxRR8uiex_s`).

### Dialogue, voice & lip sync `[C]` (Tao Prompts)
- **Generate dialogue separately in a TTS tool, then lip-sync** — in-model audio (Veo 3) is limited (max 8s) with little voice control (`JgxVyB9M62I`).
- **ElevenLabs Voice Design** — prompt gender/age/accent/tone for three voice options; **v3 Alpha** takes bracketed emotion tags (`[exhausted, desperate]`) mid-line. **Speech-to-speech** (record your own VO) beats text-to-speech for natural trailer dialogue (`8rR2IdCT-lI`).
- **Lip-sync models:** **Creatify Aurora** (best-looking, up to 60s) and **Omnihuman 1.5** (bigger movements) are strong; **LTX** over-smooths skin and is priciest. Prompt **both movement and emotion** ("she's frustrated, slumping her shoulders"); keep lip-sync prompts simple (`JgxVyB9M62I`).
- **Talking clone of yourself:** train **HeyGen** on a 1–2 min clean-audio video, **always select Avatar 4** (Avatar 3 is bad); HeyGen can also dub into other languages keeping your voice fingerprint (`Ov-SrWJsp8I`). Enhance source audio with free **Adobe Podcast/Audio Enhance**.
- **Motion-capture yourself onto a character:** **WAN Animate** photo-animate (face clearly visible, max 15s/clip), then swap your voice via **ElevenLabs voice changer** (`amX3FlcnpHw`).
- Video models often generate **consistent character voices + ambient sound** natively; add reverb/echo to dry AI dialogue to sell realism (Wade McMaster, `g1SRS7-Bqlk`).

### Blending real footage + AI `[C]`
Shoot ordinary phone/green-screen footage, then layer AI holograms/characters/sets on top while **keeping the real actor's actions unchanged** — realism/control from the real footage, flair from AI (Tao Prompts, `tWS_TiheWsU`). Screenshot a real set, restyle the still in Nano Banana ("add cyberpunk decay, keep structure"), then tell Seedance to map it back onto the footage.

### Scale reality `[C]`
A 5-minute AI trailer took **~1,848 MJ images → 624 shortlisted → 962 Runway clips → ~170 used**, ~50 hours over two weeks (Tokenized AI, `8rR2IdCT-lI`). A 20-min cinema short: solo, ~$1,000, ~3.5 months, one ~15s shot at a time (Wade McMaster, `g1SRS7-Bqlk`). **Budget heavy exploration overhead.**

---

## 9. Workflow & iteration

### The image-first pipeline `[C]` (the golden rule)
**Never generate video from a bare text prompt — build a reference image first.** The pro pipeline is **design sheet → storyboard → animate**, because images are far cheaper/faster than video (Tao Prompts, `JQzF5LP4VTs`, `RUAuMD5hUBw`):
1. **Design sheet** — characters, props, palette, style. Put *yourself* in via a grid of real photos facing different directions.
2. **Storyboard** — a 12-panel or 3×3 grid mapping every shot, generated at **4K** (each panel is small).
3. **Animate** row-by-row; **use each good AI output as the reference for the next shot** to build a consistent world.

**Minimum stack:** one image model + one video model + one audio generator. A recommended three-tool stack: **Claude** (writes design-sheet/storyboard/video prompts via an installable skill) + **GPT Image 2 or Nano Banana Pro** (images) + **Seedance 2.0** (video) (Tao Prompts, `JQzF5LP4VTs`, `RUAuMD5hUBw`).

### Iterate efficiently `[C]`
- **Draft mode + `--sref random`** = 24 styles for under one generation's cost; click a grid image to reveal its code, "very subtle" the keepers.
- **`--repeat`** to sample many styles in one submission; **high chaos (40)** on a draft grid for max spread.
- **Run Describe** on your own outputs to learn richer vocabulary; add the source as an sref to pull regenerations closer.
- **`/shorten`** to find the load-bearing words.
- **Re-roll** — some styles land on a spectrum ("Unreal Engine 3D cubism" ranges Picasso→plain shapes); re-roll until the target point appears.
- While a video clip processes, **generate the next scene's stills** — scene-by-scene beats batching everything first (Tokenized AI, `MfK-WkKUnKQ`).
- **Approve each step** in guided tools (OpenArt Director "guide me") and **edit the treatment before generating video** to save credits (Wade McMaster, `CrnRF8bvqM0`). **Fix by editing (trim/cut/bridge) rather than always regenerating.**

### Organize `[C]`
- **Heart/like** good images and styles; **lock** a dragged-in reference to reuse across prompts without re-adding.
- Filter by **liked** on the organize page; generate inside **folders** for long projects.
- Collect discovered **sref codes into tagged mood boards** (append tags like "-IL" to board names for search).
- **Color-match a batch** to one anchor image so a set reads like one photo shoot (a match-confidence meter warns when two are too far apart).

### Cross-tool tricks `[C]`
- **DALL-E 3 coherence + MJ aesthetics:** generate the specific scene in DALL-E 3, feed it into MJ as a reference at `--iw 2` + a seed, then very-subtle remix (ref removed) for MJ texture/grading (Tokenized AI, `uCIhb4vLd2I`).
- **Impossible camera angles:** lock style → Vary Strong to place the character → combine with a movie-still reference at `--iw 1–2` to force composition → very-subtle remix halving `--iw` each pass (Tokenized AI, `o6cAA8jziPU`). **Keep reference and generation aspect ratios aligned** or you get stubborn black bars.
- **Environments separate from characters**, then composite — gives multiple consistent shots of one location (Tao Prompts, `9os35azf4Jw`).

---

## 10. Asset use-cases for a faceless channel

| Asset | How `[C]` |
|---|---|
| **Thumbnails** | Set the platform ratio first (4K YouTube; 9:16 reels; IG 3:4). AI thumbnail makers (SnapThumb) store a saved face and offer **replica/co-star/faceless modes** + a custom featured element. Fix broken thumbnail text in Nano Banana. `H29b2gjX6Kg`, `gUydJBBSjCs` |
| **Shorts b-roll / hero stills** | MJ still → `--motion low` clip, or start/end keyframe in Kling/Seedance. Keep subject large, motion slow. `Dkj7Jqejfz0`, `LOAHPLUbmPQ` |
| **9:16 background plates** | `--ar 9:16`; generate a **subject-free environment base** ("no animals and creatures") so it composites cleanly. `lCFzMnBDqEc` |
| **Recurring characters** | Character reference sheet (§4) → Omni Reference / Nano Banana. Separate sheets per state; re-attach on every extension. `2psBexPkw3I`, `j8ImtURt9-0` |
| **Brand-consistent sets** | Mood board locks a style code; reuse across new subjects with `--ar 16:9`. Color-match batches to an anchor. `Dk_duA28W5k`, `nr_BEWmFPaM` |
| **Product photography / mockups** | Name product + setting + audience ("modern product photography for this clock in a luxury setting for a millennial audience"); drag a logo for t-shirt/hoodie mockups. Nano Banana Pro reproduces a real product ~99% in new scenes. `H29b2gjX6Kg`, `7KZ495jea4c` |
| **"Burst mode" shot library** | Prompt Seedance "generate 20 shots in rapid fire" at 4K/7s, then extract keyframes as stills. `M7p7HrJjcdA` |
| **Text-bearing designs** | Generate MJ **placeholder assets** (photos, vines, off-white-bg elements) and composite + add text in Affinity/Photoshop — the intended workflow. `qFYJb0zYztY` |
| **Print-on-demand / vectors** | **Tracejourney** (Discord bot) removes backgrounds and converts to SVG better than Illustrator's tracer; prompt on white bg, `--ar 4:5` for tees. Or **Recraft** for native vector/SVG. `o9Sd4OfuIOg`, `245Y0JTDFtI` |
| **Photo restoration** | One-line Nano Banana 2: "repair, restore, and recolor this photo" at 4K. `H29b2gjX6Kg` |

**Commercial-use note `[I]`/`[C]`:** MJ commercial rights follow your paid-plan terms — **verify current MJ ToS** (and per-tool ToS for each generator you chain in). **Adobe Firefly is the commercially-safe choice** for client/advertising/publishing work because it's trained on licensed Adobe Stock, unlike partner models (Wade McMaster, `fK5Df-hddJ0`). Some tools (Higgsfield) reject celebrity/movie references by design and sometimes wrongly flag *your own* characters (re-upload to pass) (Tao Prompts, `KxRR8uiex_s`).

---

## 11. Tips, tricks & lesser-known techniques

- **Text in quotes:** put desired words in `"quotation marks"`; **split long text into several separate quotes** (batches) for far cleaner rendering. A solid **black background** helps typographic compositions (Future Tech Pilot, `wEwYSBj0qBo`).
- **Text troubleshooting:** `--raw`, `--q 4`, lower stylize, `--hd`. Note **V8.1's text is noticeably worse than V8's** (a tradeoff for beauty) — fix broken text in **Gemini's Nano Banana** outside MJ.
- **`--sref random` void prompt:** meaningless symbols reveal a style's true essence.
- **Envelope reaction (Discord):** DMs the four grid images as separate files + the otherwise-hidden **seed**.
- **Prepend an upscaled image's URL** to a text prompt to reuse it as a blend/reference (a Chrome extension can automate the tedious Discord copy/append).
- **`--sref random` + `--repeat`** to farm dozens of reusable style codes at once.
- **Colored-annotation edits (Nano Banana 2):** draw a yellow circle + typed "remove," add a legend in the prompt ("in the yellow circle change the text to Pepsi").
- **Turn off the platform "prompt improver"** (Dzine) when you want on-intent realism.
- **Restyle a stubborn video** by generating a styled *reference image* instead of prompting the style in text (Seedance ignored "mid-90s anime" as text but honored a matching reference image) (Wade McMaster, `gpkbPCrGF6g`).
- **Empty-scene-then-subject-appears effect:** start frame = empty plate (remove vehicles in Nano Banana) → end frame = populated → prompt them arriving (Tao Prompts, `A5QVQEaia9k`).

---

## 12. Common mistakes & pitfalls (Don'ts)

- **Don't leave Draft mode on** for real generations (you keep getting 24-image grids) — the toggle persists (Future Tech Pilot, `vqg-fUi98x8`).
- **Don't leave HD on in settings** — it drains fast hours even though it's cheaper than before (Future Tech Pilot, `t_xIYKk2ERk`).
- **Don't use MJ's extend / don't Pan more than once or twice** — coherence and body proportions break down (Future Tech Pilot, `Dkj7Jqejfz0`; Tokenized AI, `4DrNl5lNapo`).
- **Don't mismatch reference vs generation aspect ratios** — you get stubborn black bars (Tokenized AI, `o6cAA8jziPU`).
- **Don't forget to rewrite the prompt for a panned/new region** — stale words ("bright red braided bun") bleed into areas with no such content (Tokenized AI, `4DrNl5lNapo`).
- **Don't crowd shots** — 2–3 subjects max; background crowds go static/warp/smoke even when foreground looks great (Tao Prompts, `LOAHPLUbmPQ`, `4tpDAX23RL0`).
- **Don't expect Vary Region to replace a whole character** (e.g. gender swap) — it deletes/distorts figures (Tokenized AI, `bRYFObeyzR0`).
- **Don't rely on MJ inpainting for extending scenery** — Adobe Generative Fill is cleaner and wastes fewer GPU hours (Tokenized AI, `ZMaUHJvXEI8`).
- **Content filters are unpredictable:** MJ silently flags words like "blood" (the prompt goes ephemeral on refresh) — phrase around it ("stained by battle"). Different models enforce different restrictions, so **switching models can get a blocked generation through** (Tokenized AI, `uCIhb4vLd2I`; Wade McMaster, `SkzG7_Ya99M`).
- **A wrongly-composed reference breaks the shot** — an AI video generator reproduces whatever's in your reference (a sandworm shown already-emerged won't burst from the ground); fix the *reference* first (Tao Prompts, `UHv61jUBx7M`).
- **Don't over-edit inside video generators** — the more you edit, the more faces blur and lose detail (Tao Prompts, `4zu2CclB-EI`).

---

## 13. Prompt recipes (ready to fill)

**A. Photoreal thumbnail subject (16:9)**
```
close-up portrait of [subject + defining features], [expression],
[environment], dramatic rim lighting, shallow depth of field,
Photorealistic, DSLR, muted colors, shot on 35mm film. No Text.
--ar 16:9 --style raw --s 150
```
Worked: `close-up portrait of a weathered lighthouse keeper, wide-eyed alarm, storm-lashed cliff at dusk, dramatic rim lighting, shallow depth of field, Photorealistic, DSLR, muted colors, shot on 35mm film. No Text. --ar 16:9 --style raw --s 150`

**B. Consistent character reference sheet**
```
professional character reference sheet [based on the uploaded image],
four vertical columns — front, left profile, right profile, back —
each a full-body shot on top with a matching close-up portrait below,
plain neutral background, [style keywords],
consistent subject appearance across all frames. No Text.
--ar 16:9 --style raw
```
Then re-upload and prompt: `make the third-column full-body shot face the opposite direction` if both profiles face the same way.

**C. 9:16 Shorts background plate (subject-free, composites cleanly)**
```
[medium] of [environment/location], [time of day], [lighting],
[color palette / mood], no animals and creatures, no people
--ar 9:16 --style raw --s 120 [--sref YOURCODE]
```
Worked: `cinematic photo of a fog-drenched Nordic pine valley at blue hour, cold gray palette, faint teal mist, no animals and creatures, no people --ar 9:16 --style raw --s 120`

**D. Image→video hero shot (start/end keyframe, in Kling/Seedance)**
```
Start frame: [the MJ still]
End frame:   [same image edited in Nano Banana — new angle/pose/lighting]
Prompt: start with [restate framing]; [subject] [slow action]; slow camera
[dolly in / orbit behind the (landmark)]; in a single shot, no cuts;
no subtitles and no music. [anchor: restate any off-screen detail]
```
Worked: `start with a wide low-angle shot of the knight; the knight slowly raises the sword; slow camera dolly in; in a single shot, no cuts; no subtitles and no music. He is covered in ash and glowing embers.`

**E. Multi-shot directed clip (Seedance 2.0)**
```
0-3s: wide tracking shot of [char A] (@image1) in [environment];
3-6s: close-up on [char B] (@image2) saying "[line]";
6-10s: [over-shoulder / reaction], slow motion.
Keep character appearance consistent with the reference sheets.
The scene ends with [end state] inside @image1.
no subtitles and no music
```

**F. Reusable brand style set (mood board / sref)**
```
{a product hero, a lifestyle scene, a texture macro, a hero portrait}
[your subject], [environment], [lighting]
--ar 4:5 --sref YOURCODE --sw 100 --s 250
```
Fan four on-brand assets in one job; raise `--s`/`--sw` to deepen the brand look, lower to let the subject lead.

---

## 14. Source coverage & limitations

**Corpus:** 384 findings mined from four Midjourney-focused YouTube channels, all tagged `provenance: midjourney`:

- **Tao Prompts** — deepest on AI *video* (image→video, multi-shot, keyframing, lip-sync, model comparisons).
- **Wade McMaster** — styles/artist vocabulary, references, Nano Banana editing, AI-film workflow.
- **Future Tech Pilot** — parameters, V8/8.1 behavior, draft mode, MJ video mechanics.
- **Tokenized AI** — prompt anatomy, multi-prompts, consistency, remix/Vary/Zoom, cross-tool pipelines.

**Findings by theme:** video-generation 79 · workflow-iteration 50 · references-consistency 48 · prompt-anatomy 37 · styles-aesthetics 32 · modes-editing 32 · realism-quality 28 · parameters 23 · asset-use-cases 21 · access-plans 17 · mistakes-pitfalls 9 · tips-tricks 8.

**Limitations:**
- **`[T]` specifics go stale fast.** Versions (V8.1 default), resolution caps (MJ 2K; GPT Image 2 / Nano Banana 2 4K), plan prices, and Omni Reference's V7-only status are 2026-07-23 facts — **re-verify at `docs.midjourney.com`** before relying on exact behavior. The `[C]` fundamentals are far more durable.
- **Adjacent-tool churn:** many video/edit findings reference non-MJ tools (Nano Banana 2/Pro, Seedance 2.0, Kling, Veo, ElevenLabs, HeyGen, Runway, OpenArt) whose versions and pricing change monthly — treat named models as "current best-in-class *examples*," not permanent recommendations.
- **Confidence varies** per finding (high/medium/low in the source); lower-confidence tips (e.g. some seed/mirror-flip and multi-shot claims) are worth testing before adopting.
- Findings are **creator-reported**, not vendor documentation — the exact numbers (success rates, GPU minutes, "~94% identical") are their observations at their capture dates.
