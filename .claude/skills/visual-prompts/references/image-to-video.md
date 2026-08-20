# Image-to-video prompting — distilled for a faceless-Shorts beat pipeline

Distilled from `docs/midjourney-prompting-guide.md` §8 "Video generation & motion (image→video)"
(lines ~220-306), plus the workflow golden rule from §9 and the model-fit note from §6/§7. This is
the corpus's largest single Midjourney-guide theme (79 findings) — it exists because MJ makes the
*stills* but the guide is explicit that "the motion mostly happens in adjacent tools." Provenance
markers carried through verbatim: `[C]` corpus-cited `(Channel, video_id)`, `[T]` tool/feature fact
(re-verify before relying on it), `[I]` general practice / this skill's own operational judgment.
Read the full guide section for anything not covered here (this file keeps only what a Short-length
beat needs — it skips the guide's longer-form scale-reality numbers and most of its lip-sync/talking-
clone depth, which target longer narrative or talking-head formats, not a faceless Shorts pipeline).

## Why this lives here now, not just "downstream"

MJ's own image→video is **D-tier — jittery, choppy, weak prompt-following** `[C] (Tao Prompts,
uCsc0ORcJDo)`. That doesn't mean motion prompting is out of scope for this skill — it means the
*target tool* for the actual clip is usually not Midjourney. This skill still owns writing the
prompt: the MJ still is the input, an external i2v tool renders the clip, and the prompt for that
tool is authored here, at the same time as the still, because it's the same prompt-authoring job
continued one step further (see `SKILL.md` workflow step on deciding still-vs-clip per beat).

## The five methods of AI video `[C] (Tao Prompts, 9os35azf4Jw)`

1. **Text-to-video** — least controllable; never start from a bare text prompt, make a reference
   image first `[C] (Tao Prompts, RUAuMD5hUBw)`.
2. **Image-to-video** — the recommended default for this pipeline; animates the MJ still directly.
3. **Elements-to-video (ingredients)** — mixes multiple references but is lower quality and lets
   characters drift; combine elements into one image first, then image-to-video `[C]`.
4. **Lip sync** — talking characters; rarely needed for a faceless format, see the brief note below.
5. **Video-to-video** — motion capture/transfer; out of scope for a stills-based pipeline.

**The golden rule (image-first pipeline):** never generate video from a bare text prompt — build the
reference image first, because images are far cheaper/faster to iterate than video `[C] (Tao Prompts,
JQzF5LP4VTs, RUAuMD5hUBw)`. Concretely for this skill: the MJ still from step 4 of the main workflow
*is* that reference image — don't skip straight to a video prompt without one.

## Deciding still vs. `--motion low` vs. a real i2v clip (this skill's own decision framework `[I]`)

The corpus doesn't rank these three options against each other for a Shorts beat specifically — this
ordering is this skill's own operational judgment, built from the cited facts below, not a single
corpus claim on its own:

| Need | Choice |
|---|---|
| Beat just needs visual variety over ~3s spans | Additional stills (cheapest, matches the cited "AI slideshow" cadence — see `faceless-pacing-rules.md`) |
| A hero/product still should breathe slightly (subtle push-in, gentle steam/water motion) | MJ's own `--motion low` image→video, per `.claude/skills/midjourney-prompting/references/parameters.md` |
| The beat's VO explicitly describes continuous action, a camera move, or a transformation that a static image can't sell (a reveal, an orbit, a bloom-in-motion) | A real i2v clip via an external tool (Kling/Seedance/etc.), prompted per this file |

MJ's own i2v is usable for the middle row only — it's D-tier `[C]` and expensive: **~5s clips**,
extendable in 4s steps to ~21s, HD capped at 720p, must supply a starting image `[C][T] (Future Tech
Pilot, Dkj7Jqejfz0)`; a default video grid costs ~8× an image, HD video ~25×, relax-unlimited applies
to SD video only, and success rate is only ~25% (keep batch at 4) `[C][T]`. For the bottom row, hand
the still to an external i2v tool instead.

## Writing the i2v prompt (once a beat needs one)

**Start/end-frame keyframing is the control workhorse** `[C] (Tao Prompts, lbMcDszm0Mc; Wade McMaster,
ckeY9tswmrM)`:
- The **start frame is the MJ still already generated** for that beat.
- For an **end frame**, edit that same image (angle/pose/lighting change) in an external image editor
  (the guide names Nano Banana 2) rather than generating an unrelated second image — start and end
  frames must be a variation of each other, or the cut reads as jarring `[C]`.
- When describing the end frame, name **both the new camera angle and what becomes visible from it**
  ("look down from above so we see the top of the frame") `[C]`.
- For more than a start/end pair, some tools support **up to six intermediate keyframes** on a
  timeline — space them out, since tight spacing on complex motion is harder to interpolate `[C] (Wade
  McMaster, D-dB2sdsMIk)`.

**Prompt techniques that carry over to any i2v tool** `[C] (Tao Prompts)`:
- Keep it short — 1-2 subjects, 1-2 actions; complexity adds control, not quality `[C] (9os35azf4Jw,
  4LI8JKPdOmU)`.
- State **speed explicitly** ("slowly"/"quickly") — the single most useful lever, and it makes
  otherwise-ignored camera moves actually happen `[C] (Future Tech Pilot, Dkj7Jqejfz0)`.
- Phrase camera moves as *what the camera sees now → what it will see next* ("the camera zooms out to
  reveal...") `[C]`.
- **Anchor** `[C]` off-screen or currently-invisible details in words, so they stay consistent once a camera
  move reveals them `[C] (Tao Prompts, zzBmvzR-URg)`.
- **Restate framing** `[C]` even when the start frame already shows it ("start with a side profile of...")
  `[C] (Tao Prompts, M7p7HrJjcdA)`.
- Say **"in a single shot, no cuts"** to stop a big move from being auto-split into multiple shots
  `[C] (Tao Prompts, ckeY9tswmrM)`.
- Say **"no subtitles and no music"** on every prompt — several tools burn in subtitles/music that
  ruin splicing into the edit `[C] (Tao Prompts, JQzF5LP4VTs)`.
- Use **negative prompts** for what you don't want ("no windows," "completely silent, no gunshots") —
  easier than describing the desired result `[C] (Tao Prompts)`.

**Realism rules for AI video** `[C] (Tao Prompts, LOAHPLUbmPQ)`:
- Keep the subject large in frame (close/medium) — small or distant subjects degrade.
- Two-to-three subjects max — crowds vanish or all do the same action.
- Slower, continuous motion reads as more realistic than fast motion — the word "slow" keeps it
  smooth; speed the clip up in the editor afterward if needed, not in the prompt.
- "in the same visual style as image X" keeps lighting/color coherent with the source still.

## Which external tool (model landscape, condensed) `[C]`

| Model | Strength | Watch out |
|---|---|---|
| **Kling** (A-tier) | Sharp detail, strong prompt adherence, best for over-the-top action; best dedicated motion-transfer/lip-sync mapping. Excels at start/end-frame transformations. | Fast fight motion can warp/flicker bodies `[C] (uCsc0ORcJDo, 4tpDAX23RL0, elCv87a4iK4)`. |
| **Google Veo 3** (B-tier) | Dialogue/audio, small movements, consistency. | Smooths/washes out detail; max 8s clips `[C] (uCsc0ORcJDo, 4tpDAX23RL0)`. |
| **Seedance 2.0** | Best multi-shot model — one prompt cuts between angles/dialogue; organic human movement; ~90% usable. | Most expensive (a 10s clip can top $5 vs ~30¢ on Google Omni); no native extend `[C] (RUAuMD5hUBw, gpkbPCrGF6g, j8ImtURt9-0)`. |
| **Google Omni** | Cheap (~30¢/10s) video *editing* (style transfer, character swap). | Max 10s, heavily censored, blocks character-ref images `[C] (elCv87a4iK4)`. |
| **Runway Gen-2** | Motion Brush (mask up to 5 regions, direction + z-axis). | Hit-or-miss, distorts faces (best on close-ups) `[C] (vezJXJGQMoY, MfK-WkKUnKQ)`. |
| **Sora 2** | Strong for memes/short-form. | Heavily censored; blocks people images for image-to-video `[C] (uCsc0ORcJDo)`. |

**Common across models:** most add too much motion by default; people deform under big motions;
extend features tend to "lose the plot" over multiple generations `[C]`. For a single Short beat this
mostly argues for **one clip per beat, not a chained extend sequence** — see below.

## Multi-shot beats (rare for a single Short beat, but the corpus covers it) `[C]`

- **Seedance 2.0 is the named best multi-shot model** `[C]` (cuts between angles/dialogue from one prompt)
  but the most expensive option `[C] (Tao Prompts, RUAuMD5hUBw)`.
- Structure a multi-shot prompt with **explicit timestamps + referenced images**: "0-3s: wide tracking
  shot of [subject] (@image1); 3-6s: close-up ... (@image2)" — the `@image1`/`@image2` tags point each
  segment at the right labeled reference `[C] (Tao Prompts, UHv61jUBx7M; Wade McMaster, H29b2gjX6Kg)`.
- **Multi-shot is still unreliable** `[C]` — rendering separate single shots and editing them together in
  the assembly stage yields higher quality `[C] (Wade McMaster, g1SRS7-Bqlk)`. Default to single-shot
  i2v prompts per beat unless the beat genuinely needs an in-clip cut.

## Extending a clip, if a beat needs more than ~5s of motion `[C]`

- Prefer **generating a second still + a second short clip** over MJ's own extend feature — MJ
  coherence decays fast; extract the final frame of a clip and start the next generation from it
  instead `[C] (Future Tech Pilot, Dkj7Jqejfz0)`.
- If the external tool has no native extend either, attach the prior clip as a video reference and
  **re-describe the exact ending** of the prior clip in the new prompt, or it loses the plot `[C] (Tao
  Prompts, j8ImtURt9-0)`.
- Joining two clips almost always leaves a small jump cut — that trim happens in `shorts-assembly`'s
  edit, not here.

## Dialogue / lip-sync (brief — rarely load-bearing for a faceless format)

If a beat's script ever calls for an on-camera speaking character (uncommon for this pipeline), the
corpus's guidance is: generate the dialogue audio separately in a TTS tool first, then lip-sync it —
in-model video audio is limited `[C] (Tao Prompts, JgxVyB9M62I)`. That audio generation is
`voiceover-brief`'s job (ElevenLabs), not this skill's — this file only notes that a lip-sync i2v
prompt should expect a separately-produced voice line as input, not generate one itself.

## Scale reality (one line, per the guide's own caution)

Full AI-video productions burn far more generations than expected — one cited 5-minute AI trailer used
~1,848 MJ images to land ~170 final clips `[C] (Tokenized AI, 8rR2IdCT-lI)`. Budget heavy exploration
overhead even for a single Short beat; a "one clip, done" expectation is optimistic.

## Output shape this skill uses (see `SKILL.md`'s prompt-sheet contract)

For any beat that gets a real i2v clip instead of (or in addition to) a still, the prompt sheet
carries an explicit block: **source still** (which MJ still is the start frame) → **target tool**
(named, from the table above, with a one-line reason) → **prompt text** (built from the techniques
above) → **start/end-frame notes** (what the end frame is and how it was produced, if used). Never
just write "animate this in Kling" with no prompt — the whole point of owning this stage is that the
prompt gets authored here, not left as a placeholder for `shorts-assembly`.
