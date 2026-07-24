# Worked example — S042 "The $2 coffee trick"

This runs the full upstream chain (script → voiceover brief → prompt sheet) through to an edit plan. The script, shot list, and AI prompts are the corpus's own worked example, reused verbatim from `docs/headless-shorts-production-playbook.md` Template Pack (§7) items 1–3; the voiceover brief is constructed the way `voiceover-brief` would produce it, following the same playbook's §5 voice-overlay rules. Markers as elsewhere; anything without one traces to a cited rule already established in `pacing-and-editing.md` / `caption-overlay-system.md` / `loudness-and-mix.md`.

## Inputs assumed

**Script (from `shorts-scripting`)** — `docs/headless-shorts-production-playbook.md` §7 Template 1 worked example:
- Hook (0–3s, 9w): "Your drip coffee tastes flat — and it's not the beans."
- Setup (3–8s, 14w): "Cafes do one thing at home you skip. It costs about two dollars."
- Build/Value (8–28s, 46w): bloom-the-grounds explanation, with a re-hook line at ~15s.
- Payoff (28–38s, 22w): the second fix (water temp/timing).
- Loop/CTA (38–45s, 13w): mirrors the hook.

**Voiceover brief (from `voiceover-brief`)** — following §5: one consistent narrator voice; ElevenLabs Stability ~40–55% / Similarity ~75% / Style exaggeration low-moderate for lively-but-clear narration `[I]/[T]`; 2–3 takes generated for the hook line and the best read chosen `[C] (Nick Nimmin, IF-PD6XMjYY)`; target 150–170 wpm.

**Prompt sheet (from `visual-prompts`)** — §7 Templates 3a/3b worked examples: Ideogram hook image (text-in-image "IT'S NOT THE BEANS"), Kling image-to-video for the bloom shot.

## Output: the edit plan

### Shot-by-shot pacing (from §7 Template 2, extended with cut-cadence discipline)

`[I]` note: the corpus establishes the ~3s change-visual rule and the hook/spike AI-video-budget rule as principles (both `[C]`, see `pacing-and-editing.md`); the specific sub-cut counts, cut points, and per-shot budget assignments below are this skill's application of those principles to this particular script, not corpus findings themselves.

| # | Beat | Dur | Visual + cut note | On-screen text | Asset source |
|---|---|---|---|---|---|
| 1 | Hook | 3s | Close-up flat coffee, slow push-in ~4% `[C] (vidIQ, DiZnbihU4NM)` | Hook card "IT'S NOT THE BEANS" full 0–3s `[I]` | S042_img01 (Ideogram) |
| 2 | Setup | 5s | Cafe counter b-roll; cut at ~3s mark inside this beat to respect the ~3s change-visual rule `[C] (Make Money Matt, HopTPCLbiiM)` | "$2 fix" | S042_broll02 (Pexels) |
| 3 | Build | 14s | Grounds blooming, bubbles rising (animated still, Kling i2v); split into 4–5 sub-cuts (~3s each) rather than one static 14s hold `[C] (Make Money Matt, HopTPCLbiiM)` | "BLOOM 30s" then re-hook card at the ~15s mark: "2nd mistake ->" `[C] (Nate Black, c6X-Ywy3yVU)` | S042_vid03 (Kling i2v) |
| 4 | Re-hook | 4s | Kettle, steam | "2nd mistake ->" | S042_broll04 (Pexels) |
| 5 | Payoff | 10s | Pour into clear mug, taste-reaction cue; ~3 sub-cuts | "SMOOTH" | S042_vid05 (Kling) |
| 6 | Loop/CTA | 8s | Return to hero mug shot, matching shot 1 for the loop `[C] (Jenny Hoyos, mhVDcqnxxaY)` | "So... never the beans" | S042_img01 (reused) |

Total 44s. AI-video budget: shot 1 (hook) and shot 3 (the demonstration payoff shot) are the two candidates for the paid/high-tier generation spend; shots 2 and 4 run on cheap stock, per the "spend premium AI-video budget only on the hook and occasional cutaway" rule `[C] (Make Money Matt, gkaxBe8BGLQ)`.

### Caption/overlay treatment

- Full-duration karaoke captions, 2 words/chunk, Montserrat ExtraBold, white fill/black 3px stroke, highlight #FFD24A, y=58%, safe zones top 12%/bottom 20%/right 12% (per `caption-overlay-system.md`'s fill-in spec).
- Hook card y=40%, 100px, on screen the full 0–3s.
- Re-hook card at ~15s, same static-card treatment, ≤5 words.

### Aspect / format

- 1080×1920, 9:16 vertical `[I]`. See `pacing-and-editing.md`'s gap flag: this worked example assumes a ~44s runtime inside the templates' 30–45s target; verify current Shorts length eligibility independently before locking a longer cut.

### Loudness

- VO peaks −3 to −6 dB; music bed ducked to ≈−22 dB `[C] (Roberto Blake, iaTavrWIGDM)`; target −14 LUFS overall; check final on phone speakers.

### Tool-stack steps

**$0 path:** CapCut — import S042 assets in shot-list order, auto-caption, hand-correct against the script, apply push-in/keyframe scale on shots 1 and 3, manually ducking the music track under the VO by ear, export 1080×1920, verify on a phone before scheduling in YouTube Studio.

**Paid path:** Assemble in Premiere Pro (Essential Sound panel auto-ducks to ≈−22 dB, Remix tool matches music length), send the cut to Submagic for animated karaoke captions, re-import, final loudness check with a LUFS meter to −14, export, schedule via YouTube Studio + track in vidIQ.

### Downstream

This edit plan (plus the produced/exported Short) is the direct input to **`social-repurpose`**, which turns the finished Short and its script/packaging into multi-surface post copy.
