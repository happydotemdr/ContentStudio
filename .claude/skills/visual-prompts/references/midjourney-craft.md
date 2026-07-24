# Midjourney craft — distilled for beat-to-prompt work

Distilled from `docs/midjourney-prompting-guide.md` (384 findings, 4 dedicated Midjourney YouTube
channels — Future Tech Pilot, Wade McMaster, Tao Prompts, Tokenized AI — plus web-verified features,
snapshot dated 2026-07-23). Provenance markers carried through verbatim: `[C]` corpus-cited
`(Channel, video_id)`, `[T]` tool/feature fact (re-verify before relying on it), `[I]` general practice.
Read the full guide at `docs/midjourney-prompting-guide.md` for anything not covered here (video
generation depth, upscaling, cross-tool pipelines) — this file only carries what a beat-to-prompt
workflow needs.

## Prompt anatomy

- **Recommended token order:** medium → subject + action → environment/context → composition (camera,
  lens, angle) → lighting → style → color/mood → parameters `[T]` + `[C] (Tokenized AI, 4DrNl5lNapo)`.
- **Earlier words are weighted more heavily; words far back often fail to appear.** Move anything
  important to the front; rephrase a dropped word instead of just appending it ("smiling" instead of a
  late "happy") `[C] (Future Tech Pilot, ioJ6istzwHw)`.
- **Subject/setting order changes emphasis** — "portrait of X in a Y" vs "photo of Y with X in it"
  produce different images; flip the order if the result centers the wrong thing `[C] (Future Tech Pilot, ioJ6istzwHw)`.
- **The six V8 "visual anchors"** that do most of the heavy lifting: **style, distance, camera,
  behavior, material, mood** `[C] (Future Tech Pilot, ioJ6istzwHw)`. Concretely: name a camera behavior
  (low-angle, drone, portrait, side profile), give the subject an action/pose (not a static stand), and
  place material/texture on a smooth↔rough scale.
- **Short prompts usually beat long, bloated ones** — long prompts dilute which words matter
  `[C] (Tokenized AI, vezJXJGQMoY)`. In V8, precision of *idea* matters more than precision of language
  — you can prompt casually as long as you fully describe the picture's content `[C] (Future Tech Pilot, wEwYSBj0qBo)`.
  Occasionally a verbose prompt wins a composition a short one misses `[C] (Wade McMaster, SjB_-GeI3FQ)`,
  but default to short.
- **Always consider aspect ratio deliberately — it changes composition, not just framing.** For a
  Shorts destination this is a non-decision: `--ar 9:16` `[C][T]`. (The guide's broader advice to test
  square/wide/vertical applies when the destination isn't fixed yet — Future Tech Pilot, `Tv1dfGcOSnA`.)

## Parameters this skill actually uses

| Parameter | Default this skill applies | Why |
|---|---|---|
| `--ar 9:16` | always, for Shorts | Destination format `[C][T]` |
| `--style raw` | on by default | Most consistently favors realism, especially real people `[C] (Future Tech Pilot, Tv1dfGcOSnA)` |
| `--stylize` / `--s` | `140–185` sweet spot | Balances literal prompt-adherence vs MJ's default "house beauty"; raise toward 300+ for a deliberately more polished/branded look, lower toward 50–80 if a long, detail-heavy prompt is being ignored `[C] (Future Tech Pilot, Tv1dfGcOSnA / ioJ6istzwHw; Tokenized AI, 1GnipTgvLI0)` |
| `--chaos` / `--c` | `3–9` while drafting variants, `0` for a locked-in final | Grid variety; raise to explore several looks per beat, drop to 0 once you've picked the winner `[C] (Future Tech Pilot, Tv1dfGcOSnA / fMEvMqvzUbc)` |
| `--no` | only for excluding a color/element | Works best for removing colors; unreliable as a general negative-prompt tool `[C] (Future Tech Pilot, Tv1dfGcOSnA / IS0Kk9OFaZQ)` |
| `--seed` | when using fixed-seed consistency | Locks the generation blueprint; with a fixed seed + one small word changed, V8 stays ~94% identical, but a big subject swap still breaks it — don't rely on it across very different beats `[C] (Future Tech Pilot, ZPJB6jurDfE)` |
| `--iw` | only when dropping in a reference image | Image weight 0–3, default 1; `0.5` ≈ colors only, `2–2.5` ≈ near-copy; halve it on each re-application pass (2, 1, 0.5, 0.25) `[C][T]` |
| `--hd` | only for a final hero still, never mid-draft | Native 2K reprocess; **changes the image, not just resolution** — can differ from the SD version even at the same seed; drains fast-generation hours, so turn it off in settings and apply per-job `[C][T] (Future Tech Pilot, Tv1dfGcOSnA / t_xIYKk2ERk)` |
| `--motion low` | only when a beat needs simple animated motion | Prefer low motion for coherence; high motion looks more cinematic but gets unpredictable, and a manual high-motion job can silently become the new default `[C] (Future Tech Pilot, Dkj7Jqejfz0)` |

Type parameters in-prompt (e.g. `--s 160`) rather than relying on account settings — it's explicit and
per-job `[C]`.

## Consistency decision (pick one per Short)

- **Recurring character across beats → character reference sheet + Omni Reference.**
  Build a reusable character once: a reference sheet with **four vertical columns (front, left profile,
  right profile, back)**, each a full-body shot on top with a matching close-up below, plain background
  `[C] (Tao Prompts, 2psBexPkw3I)`. Keep **separate sheets per major state** (e.g. with/without a prop)
  or the model drifts `[C] (Wade McMaster, g1SRS7-Bqlk)`. Drive every later beat with **Omni Reference**
  — `--oref <url> --ow <0-1000, default 100>` — which places the character into a new scene while
  preserving style `[T]`. Currently **V7-only**; an improved V8 version is "in training" `[T]` — flag
  for re-verification.
- **No recurring character, but one consistent look across the Short → `--sref` or a mood board.**
  `--sref <code|url>` ties an aesthetic to a shareable code; the same code renders differently by
  subject and by what's up front in the prompt (e.g. adding "oil painting" shifts it), so re-test the
  code against your actual subject rather than assuming it transfers `[C] (Future Tech Pilot, GAT5A6MqM-E)`.
  A **mood board** (`--p <code>`) gives the most control because you upload the exact images to emulate,
  and its influence is dialed with `--stylize` (not a separate weight) — ~50 is a sweet spot, 1000 is
  max `[C] (Wade McMaster, TtkenI4wt8I; Future Tech Pilot, Tv1dfGcOSnA)`.
- **Cheap/low-stakes consistency → a fixed seed alone.** Good-enough when perfection isn't critical
  `[C] (Tokenized AI, MfK-WkKUnKQ)`.
- **Subject-free b-roll/background plates → no consistency mechanism needed**, just a shared style.
  Generate the environment with "no animals and creatures, no people" so it composites cleanly and
  doesn't drag a subject's color into the palette `[C] (Tokenized AI, lCFzMnBDqEc)`.

**sref version note:** V6 codes are incompatible with V7/V8; V7 and V8/8.1 codes are interchangeable
`[C] (Wade McMaster, PEl1Rb9spsk)`.

## The no-text rule (why every prompt here ends "No Text")

Midjourney is weak at rendering legible on-screen text; the corpus's asset-workflow guidance is to
generate **placeholder MJ assets with no text** and composite captions/titles in a separate tool
afterward `[C] (Tokenized AI, qFYJb0zYztY)`. Practically: whatever on-screen text or
hook card the script beat specifies is **not** written into the MJ prompt — it's handed to
`shorts-assembly` as overlay copy, applied after the still is generated.

## Faceless-channel asset recipes relevant to this skill

- **9:16 Shorts background plate (subject-free):**
  `[medium] of [environment/location], [time of day], [lighting], [color palette/mood], no animals and
  creatures, no people --ar 9:16 --style raw --s 120 [--sref CODE]` `[C] (Tokenized AI, lCFzMnBDqEc)`.
- **Photoreal hero/hook still:** end the prompt with `Photorealistic, DSLR, muted colors, shot on 35mm
  film. No Text.` — DSLR is called out as the key realism cue `[C] (Tao Prompts, 2psBexPkw3I)`.
- **Reusable brand style set:** fan multiple asset types through one job with **permutations**
  (`{}`-wrapped alternatives, one job per comma item — ideal for populating a mood board)
  `[C] (Wade McMaster, PEl1Rb9spsk; Tokenized AI, o6cAA8jziPU)`: e.g.
  `{a product hero, a lifestyle scene, a texture macro, a hero portrait}` + shared subject/environment +
  `--sref CODE --sw 100 --s 250` — raise `--s`/`--sw` to deepen the brand look, lower to let the literal
  subject lead. The specific recipe combination (which four asset types, this exact param stack) is
  this skill's own composition `[I]`, built from the cited permutation mechanic and the cited `--sw`
  behavior above, not a single corpus finding on its own.

## Video note (kept deliberately light — this is an image-prompt skill)

MJ's image model is best-in-class for aesthetics/photorealism, but its **video generator is D-tier —
jittery camera, choppy motion, weak prompt-following** `[C] (Tao Prompts, uCsc0ORcJDo)`. When a beat
genuinely needs simple motion from a still, prefer **`--motion low`** for coherence over high motion,
which looks more cinematic but gets unpredictable `[C] (Future Tech Pilot, Dkj7Jqejfz0)`. Anything more
demanding than a single hero-still breathing (multi-shot, dialogue, big camera moves) is out of scope
here — that tool choice and prompt-craft belongs to `shorts-assembly`, which sees the full script and
voiceover brief together.
