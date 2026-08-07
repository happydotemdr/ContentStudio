---
version: 1
date: 2026-08-05
kind: assembly
run: do-less-20260728-190724
slug: do-less-sold-as-win-more
stage: 04-assembly
script: runs/do-less-20260728-190724/02-scripting/artifact.v1.md
voiceover_brief: runs/do-less-20260728-190724/03-voiceover/artifact.v1.md
visual_prompts: runs/do-less-20260728-190724/03-visual/artifact.v1.md
visual_system: rgs-briefs/2026-07-28-rgs-debut-visual-system.md
archetype: A1
status: complete
---

=== ASSEMBLY / EDIT PLAN — do-less-sold-as-win-more (RaisingGoodSports, Short C) ===

Produced by `shorts-assembly` from the three upstream artifacts of run
`do-less-20260728-190724`. **Unlike Short A's plan, the assets for this Short already exist**
— this plan is written against the real files in
`Generated Assets/do-less-20260728-190724/`, and its timings are derived from the **actual
47-second** ElevenLabs master, not from the script's planned 45s windows.

Nothing is rendered by this document. It is the plan an editor follows.

## Marker legend (an unmarked normative line below is a bug)

- **`[C]`** — the 420-video ContentStudio corpus, cited `(Channel, video_id)`, carried through
  from `shorts-assembly/references/*.md`.
- **`[I]`** — general craft judgment or this skill's own operational decision.
- **`[T]`** — tool/policy fact, dated 2026-07-23 in the assembly references. Re-verify.
- **`[B]`** — RaisingGoodSports Brand Definition, carried from upstream, never re-derived here.
- **`[G]`** — binding grounding constraint, carried verbatim via the script.

---

## 0. Asset inventory (measured, 2026-08-05)

`Generated Assets/do-less-20260728-190724/`

| Asset | File | Measured | Note |
|---|---|---|---|
| VO master | `Audio/ElevenLabs_2026-08-05T18_12_54__s50_v3.mp3` | **47s**, 128 kbps MP3 | One continuous file, not 7 per-beat units |
| Hook hero | `visuals/Shot 1.png` | 1632×2912 | Upscaled ✓ |
| Setup (Reg B reformer) | `visuals/Shot 2.png` | 1632×2912 | Upscaled ✓ |
| Setup (trophy shelf) | `visuals/Shot 3.png` | 816×1456 | **Under-canvas** |
| Build (wide complex) | `visuals/shot 4.png` | 816×1456 | **Under-canvas** |
| Build (Reg B schoolroom) | `visuals/shot 5.png` | 816×1456 | **Under-canvas** |
| Build (medal podium) | `visuals/Shot 6.png` | 816×1456 | **Under-canvas** |
| Re-hook (balance scale) | `visuals/Shot 7.png` | 816×1456 | **Under-canvas** |
| Stat plate | `visuals/Shot 8.png` | 816×1456 | **Under-canvas** |
| Stat (cleat) | `visuals/Shot 9.png` | 816×1456 | **Under-canvas** |
| Payoff hero | `visuals/Shot 10.png` | 816×1456 | **Under-canvas** |
| Payoff ledger | `visuals/Shot 11.png` | 816×1456 | **Under-canvas** |
| Cover | `visuals/thumbnail.png` | 1632×2912 | Accent word NOT baked in — correct |

### Blocking / near-blocking gaps

1. **Nine stills are 816×1456 — below the 1080×1920 delivery canvas** `[I]`. Fitting them to
   the frame is already a ~1.32× upscale; the plan's keyframe scale moves (15–20%, `[C]
   (vidIQ, DiZnbihU4NM)`) push the effective upscale to ~1.5–1.6×, which reads visibly soft on
   a phone. **Fix before import:** re-upscale each in Midjourney to 1632×2912, matching Shots
   1/2/thumbnail, which are already there. This is the single highest-value pre-edit step.
2. **No music bed exists.** Source before the mix — see §5. `[C] (Roberto Blake, SJsGBKGy4Do)`
3. **No i2v clips exist.** See §2's motion column — the plan does **not** require them; both
   moves are keyframe-able. Flagged as a deliberate call, not an omission.
4. **No overlay assets exist** (claim cards, STAT build, lower-third, end card). All are built
   in the editor — that is correct, they were deliberately kept out of every Midjourney prompt
   `[C] (Tokenized AI, qFYJb0zYztY)`.
5. **Open item carried from upstream:** the grounding file
   `rgs-briefs/2026-07-28-do-less-sold-as-win-more.md` is still missing; and the R10
   determinant/factor counts still need a spot-check against the current
   `rgs-r10-science-of-fun.md` (corpus edition 2026-07-18) before ship `[G]` (constraint #5).

### Audio note — verify before cutting `[I]`

The voiceover brief predicted **~47–50s** at ~155 wpm for ~131–134 words. The delivered master
is **47s** for ~140 spoken words — the **fast end** of that window (~180 wpm effective, above
the corpus's 150–170 wpm narration band `[C] (Nick Nimmin, LAzYEKltBwA)`). Two checks on first
listen, before any cutting:

- **Did the three `[pause]` tags render?** Eleven v3 tags are not guaranteed. The half-second
  beat before **"Trying hard"** is *mandated* by the script's handoff `[G]` — if it isn't
  audible, re-roll that unit rather than fixing it with a gap in the edit.
- **Does the read still land as "measured, not urgent"?** `[B]` If it reads rushed at the Hook
  or the Payoff, re-roll those two units (the brief already budgets 2–3 takes for the Hook, the
  R10 line, and the Loop/CTA `[C] (Nick Nimmin, IF-PD6XMjYY)`).

---

## 1. Timing model — read the real waveform, don't trust the script's windows

**The script's beat second-ranges are now wrong for this audio, and that is expected, not a
defect.** The voiceover brief said so explicitly: *"the VO and the visual beats are not locked
frame-for-frame; `shorts-assembly` places the cuts against the finished audio, not the
reverse."* The prompt sheet's per-shot second-ranges inherit the same drift.

Estimated beat map, derived by weighting each TTS unit's word count across the measured 47s and
adding the three `[pause]` beats:

| # | TTS unit | Words | Script planned | **Est. actual** | Drift |
|---|---|---|---|---|---|
| 1 | Hook | 13 | 0–3s | **0.0–4.2s** | +1.2s |
| 2 | Setup | 20 | 3–8s | **4.2–10.6s** | +2.6s |
| 3 | Build — argument cards | 27 | 8–15s | **10.6–19.3s** | +4.3s |
| 4 | Build — re-hook | 7 | ~15s | **19.3–21.6s** | +4.6s |
| 5 | Build — study/proof | 30 + pause | 15–28s | **21.6–31.7s** | +3.7s |
| 6 | Payoff | 25 + pause | 28–38s | **31.7–40.2s** | +2.2s |
| 7 | Loop/CTA | 18 + pause | 38–45s | **40.2–47.0s** | +2.0s |

`[I]` **These are estimates to be replaced, not targets to cut to.** First editing action: drop
the MP3 on the timeline, run auto-caption, and read the true in/out of each of the seven units
off the caption track. Every "Est." figure below then gets nudged to the real number. The
**cut cue** column is the authority — cut on the *word*, not on the timecode.

Notable consequence: the **re-hook now lands at ~19.3s, not ~15s**. The corpus's re-hook
finding is a cadence at "~15s" `[C] (Nate Black, c6X-Ywy3yVU)`; landing it at ~19s of a 47s
Short is proportionally equivalent (~41% in vs. ~33%) and is accepted rather than forced —
forcing it would mean cutting VO the script deliberately protected. `[I]`

---

## 2. Shot-by-shot pacing

`[I]` The corpus establishes the ~3s change-visual rule, the re-hook cadence, and the
keyframe-motion rules as principles (all `[C]`); the specific cut points, cue words, and motion
assignments below are this skill's application of them to this audio and these twelve files.

| # | Asset file | Est. in–out | Dur | **Cut ON (VO cue)** | Motion | Overlay |
|---|---|---|---|---|---|---|
| 1 | `Shot 1.png` | 0.0–4.2 | 4.2s | *(open cold — no logo, no intro)* | Push-in **5%**, linear, whole shot `[C] (vidIQ, DiZnbihU4NM)` | Hook card (full duration) + lower-third |
| 2 | `Shot 2.png` | 4.2–8.6 | 4.4s | **"That was Ellen Key"** | Slow scale 15%, drift toward the lamp | Lower-third: `Ellen Key · Swedish reformer · 1900` |
| 3 | `Shot 3.png` | 8.6–12.0 | 3.4s | **"or only what the scoreboard says"** | Push-in 12% onto the nearest nameplate | — |
| 4 | `shot 4.png` | 12.0–15.0 | 3.0s | **"a complete athlete"** | Slow drift left→right across the pitches | Claim card 1 |
| 5 | `Shot 6.png` | 15.0–17.4 | 2.4s | **"more medals like Norway"** | Scale 15% toward the medal | Claim card 2 |
| 6 | `shot 5.png` | 17.4–19.3 | 1.9s | **"Even backing off"** | Near-static, 8% only | — |
| 7 | `Shot 7.png` | 19.3–22.2 | 2.9s | **"But someone actually measured"** | Slow overhead drift toward the scale's pivot | Re-hook card |
| 8 | `Shot 8.png` | 22.2–27.5 | 5.3s | **"So a 2015 George Washington…"** | Plate held **static** — the text does the moving | STAT build, stages 1–2 |
| 9 | `Shot 9.png` | 27.5–31.7 | 4.2s | on the **`[pause]`**, landing on **"Trying hard"** | Push-in 15% onto the flexing laces | STAT stages 3–4 |
| 10 | `Shot 10.png` | 31.7–36.2 | 4.5s | **"So here's the trap"** | **Rack-focus substitute** — see below | AI-disclosure line begins |
| 11 | `Shot 11.png` | 36.2–40.2 | 4.0s | on the **`[pause]`**, landing on **"But it counted"** | Macro push-in 12% onto the wet ink | Payoff caption + accent word |
| 12 | `Shot 1.png` *(reuse)* | 40.2–47.0 | 6.8s | **"You were told to ease off"** | **Reverse of shot 1's push-in** — continuous pull-back landing on the exact Hook framing | End card + comment-bait |

**Total: 12 cuts / 47s = ~3.9s average.**

### Three plan-level calls, each flagged

**(a) The cut cadence runs above the ~3s rule, deliberately.** The rule is
strongly-supported — change the visual every ~3s `[C] (Make Money Matt, HopTPCLbiiM)` — and at
that rate a 47s Short wants ~15–16 shots against the 11 unique stills that exist. Rather than
generate four more, this plan holds at 12 and leans on three explicit counter-rules:
comprehension comes from **deleting** edits, not adding them `[C] (Kallaway, i7upRL4H1FM;
Nate Black, J8LrrCpDNJI)`; **don't add cuts that don't carry information** `[C] (vidIQ,
DiZnbihU4NM)`; and **match editing pace to the audience — slower for older/learning viewers**
`[C] (Nick Nimmin, LAzYEKltBwA)`, which is exactly RaisingGoodSports' parent audience holding a
deliberately two-frame argument. Every shot still carries keyframe motion, so no frame is
"dead air" `[C] (vidIQ, DiZnbihU4NM)`. **If a phone-sized watch feels slow, the fix is 3–4
more stills, not faster cuts on the same twelve.** `[I]`

**(b) Shot 12 holds 6.8s — the one real exception, and it's earned.** The Loop/CTA must land
its last frame on the exact Hook framing for the mirror `[C] (Jenny Hoyos, mhVDcqnxxaY)`, and
the corpus says explicitly: when a beat is carrying the payoff, **resist adding cuts there just
to look busy** `[C] (vidIQ, DiZnbihU4NM)`. The continuous pull-back is the motion. `[I]`

**(c) The cut order deviates from the prompt sheet's arc table.** The sheet ordered the Build
as 4 → 5 → 6 (A, B, A) to break the register run. This plan runs **4 → 6 → 5**, putting the
1900 schoolroom on the meta-line *"Even backing off gets argued on the scoreboard's terms"*
rather than between the two present-day claim cards. Reason: **match the visual to what's being
said sentence-by-sentence — a mismatched visual causes confusion and retention decay** `[C]
(Kallaway, i7upRL4H1FM)`, and a Swedish schoolroom under *"more medals like Norway"* is exactly
that mismatch. The cost is a three-shot Register A run (3 → 4 → 6). Gate C governs the prompt
sheet at emission, not the edit order, so this does not invalidate the sheet's PASS. `[I]`
*Alternate if the A-run bothers you on review:* move `shot 5.png` to 10.6–12.0, over *"And every
case for doing less still sells a bigger win —"*, restoring max-run-2. Weaker line match,
better register rhythm — your call on review.

### Motion: no i2v clip is required for v1 `[I]`

The prompt sheet reserved motion for Hook + Payoff. Neither needs a generated clip:

- **Hook (Shot 1)** — the sheet itself specifies a "few-percent breathing push-in" and calls
  Midjourney's own i2v *"D-tier, jittery."* A keyframe scale from 100%→105% is cleaner, free,
  and frame-exact — and it's the same move the corpus prescribes directly `[C] (vidIQ,
  DiZnbihU4NM)`. **Use keyframes.** This also makes Shot 12's pull-back an exact reverse, which
  a generated clip could not guarantee.
- **Payoff (Shot 10)** — the Kling rack-focus is the one shot where a clip would genuinely beat
  a still, and it's the sanctioned place to spend: **premium AI-video budget goes to the hook
  and occasional cutaway spikes only** `[C] (Make Money Matt, gkaxBe8BGLQ)`. **Substitute for
  v1:** duplicate the Shot 10 layer, apply a heavy gaussian blur to the lower copy, mask the
  child on the upper copy, and keyframe the blurred copy's opacity up over 4.5s while lifting
  warmth/exposure ~8% on the child. That reproduces "trophy shelf dissolves further, amber
  light rises." Generate the Kling clip only if the substitute reads flat on the phone check.

---

## 3. Caption & overlay treatment

### Style spec (no placeholders — copy straight into the editor)

```
Font:            Montserrat ExtraBold  (fallback: Poppins Bold / CapCut default bold)
Cap size:        captions 66px | hook & re-hook cards 100px | lower-third 48px
                 | disclosure line 38px      (all on a 1080x1920 canvas)
Fill / stroke:   #F7F3E8 fill / #0E3B43 stroke 3px + soft 40% drop shadow
Highlight color: NONE - active word pops by scale (100% -> 112%) + opacity, not color. See below.
Accent color:    #F2A541 amber - reserved, used exactly 3 times (see below)
System color:    #C1543A clay - claim-card framing ONLY, never on the child or parent
Position:        captions y=56% | hook card y=40% | re-hook card y=40%
                 | lower-third y=70% | disclosure y=68%
Safe zones off:  top 12% (0-230px) , bottom 20% (1536-1920px) , right 12% (950-1080px)
Words per card:  captions 2-3 | static line <=6 words
Animation:       fade-in 80ms, no bounce/pop-in; push-in 5% at open
```

### The amber-reservation conflict, resolved `[I]`

The playbook's karaoke default tints the active word a brand accent `[I]`. The brand reserves
amber for a **single accent word**, and the voiceover brief enforces this hard enough that it
forbids amber even on the disclosure line `[B]`. A full-duration amber karaoke highlight would
spend that reservation ~140 times. **Resolution: the karaoke highlight is a scale-and-opacity
pop with no color change**, and `#F2A541` appears exactly three times in the finished Short —
`TRYING HARD — #1` (STAT stage 3), `COUNTED` (Payoff), and the thumbnail accent word. This is
this skill's call resolving a `[B]` constraint against an `[I]` default, not a corpus finding.

### Caption density — the corpus's genuine split, and the call

- Playbook default: caption every spoken word, karaoke-synced `[I]`.
- Audit counter-finding: **keep captions small and mostly at the start** — front-load ~5–10s,
  then rely on auto-subtitles `[C] (One Person Business, 6s2T2NlWDhQ; Make Money Matt,
  LlIkMWX50aQ)`.

**Call: full-duration karaoke captions, small.** `[I]` Reason specific to this Short — ~80–85%
watch muted `[C] (Kallaway, i7upRL4H1FM)`, and this script's whole job is making the viewer
hold **two competing frames at once**. Dropping captions after 10s would leave the muted
majority to reconstruct a two-frame argument from stills alone. But the audit's *restraint* is
adopted in full: 66px is small relative to the frame, and captions **never repeat** a card
that's already on screen (they cut away entirely under the Hook card, the re-hook card, and
STAT stages 3–4). Re-open this call if the channel drifts toward faceless-core style.

### Overlay schedule

| Est. time | Element | Copy | Treatment |
|---|---|---|---|
| 0.0–4.2 | **Hook card** | `In 1900, someone named the trap.` | 100px, y=40%, full Hook duration `[I]` |
| 0.5–4.2 | Lower-third | `Ellen Key · Swedish reformer · 1900` | 48px, y=70%. **Plain attribution — NEVER a quote card** `[G]` |
| 12.0–15.0 | Claim card 1 | `"A complete athlete"` | Quote marks + small clay `#C1543A` tag `the pitch` — visibly a claim being sold, not a fact |
| 15.0–17.4 | Claim card 2 | `"More medals — like Norway"` | Same sold-claim treatment |
| 19.3–22.2 | **Re-hook card** | `Someone actually measured what kids want.` | 100px, y=40% `[C] (Nate Black, c6X-Ywy3yVU)` |
| 22.2–24.5 | STAT 1 | `2015 George Washington University study · youth soccer players` | Off-white, over the plate |
| 24.5–27.5 | STAT 2 | `81 things that make sport fun  →  11 core factors` | Counter animates 81→11 — **viewers must see the number** `[C] (vidIQ, i5bZ-Be9cAQ)` |
| 27.5–29.8 | STAT 3 | `TRYING HARD — #1` | **Amber `#F2A541`, ALL CAPS.** Lands on the `[pause]` |
| 29.8–31.7 | STAT 4 | `Winning: not in the top 11  (~40th of 81)` | Off-white |
| 32.5–36.2 | **AI disclosure** | `AI-generated visuals · synthetic voiceover` | 38px, `#F7F3E8`, **never amber**, safe zone `[B]` |
| 36.2–40.2 | Payoff caption | `It counted the day he gave it.` | `COUNTED` in amber, rest off-white |
| 43.0–47.0 | End card | Pointer to Short B — `nobody-asked-the-kid` | Must clear bottom 20% and right 12% |
| pinned | Comment bait | `What's a "do less" tip you were handed that still promised a better result?` | Pinned comment, not on-screen |

**Cover/thumbnail:** `thumbnail.png` + accent word overlaid in `#F2A541`. **Recommend
`COUNTED`** over `SOLD A WIN` — it mirrors the Payoff accent, and the un-thumbnail recipe wants
2–4 bold words with one crystal-clear focus point readable like a highway billboard `[C] (Nate
Black, -zd1lLaC-I0; Nick Nimmin, h8OTdq24irE)`. The render already reserves the dark left third
for it.

---

## 4. Aspect ratio & format

- **1080×1920, 9:16 vertical** `[I]`. Source stills are 816×1456 / 1632×2912 — both are 9:16-ish
  (1:1.784 vs. true 1:1.778); fit **height** and accept ~0.4% horizontal crop rather than
  letterboxing.
- Export H.264 MP4, 1080×1920, 30fps, high bitrate.
- **Runtime 47s.** `[I]` Comfortably inside the templates' 30–45s band's neighborhood and well
  under any plausible limit — but note the corpus's standing gap flag: it has **no finding on
  current Shorts duration-eligibility limits**, which is a live YouTube policy question outside
  both the corpus and the 2026-07-23 `[T]` sweep. Verify on YouTube's own help pages before
  locking anything longer.

---

## 5. Loudness & mix

Inherited from the voiceover brief without re-deriving:

- **Voice track normalized to −14 LUFS integrated**, peaks −3 to −6 dB, no clipping `[T] [I]`.
- **Music ducked to −21 to −22 dB under the voice** `[C] (Romayroh, Wox4Jt_2t6w; Roberto Blake,
  iaTavrWIGDM)`. The brief leads with this number over the guide's wider −12 to −18 dB band
  because it's the one tied to an actual retention complaint — **loud music is the most
  underestimated AVD killer**. When in doubt, too quiet beats too loud `[I]`.
- **Drop the bed entirely across 22.2–31.7s** (the R10 study beat). The numbers and the mandated
  half-second on "Trying hard" must land uncontested `[I]`.
- **Pause the music just before the Payoff reframe** (~36.2s, on "But it counted the day he gave
  it") — pausing before the key line changes how it lands `[C] (vidIQ, DiZnbihU4NM)`.
- **Match music to the arc, not just fill silence** `[C] (Kallaway, i7upRL4H1FM)`. This Short's
  arc: quiet-resolve (0–10.6) → skeptical momentum (10.6–19.3) → clean and measured (19.3–31.7,
  bed out) → quiet gravity then warmth and relief (31.7–47). **Never use music whose emotional
  tone contradicts the words — no music beats wrong music.** If nothing fits the Payoff's warmth,
  leave it dry.
- **SFX:** a soft hit on each STAT stage reveal and on the two claim cards. Punctuate, don't
  startle `[I]`. No whooshes on the Payoff or Loop — they'd fight the exoneration register `[B]`.
- **Rights, last checkpoint before render** `[C] (Roberto Blake, SJsGBKGy4Do)`: source from
  YouTube Creator Music, a royalty-free library, or a direct license. **Creator Music can mean
  revenue-share or no monetization** — unlike a direct license. Settle this before the final
  export, not after.
- **Check the final mix on phone speakers, not headphones** `[I]`.

---

## 6. Execution — $0 stack (recommended for this Short)

**Pre-flight (before opening any editor):**
1. Re-upscale the nine 816×1456 stills to 1632×2912 in Midjourney (§0 gap 1).
2. Listen to the VO master end to end; confirm the three `[pause]` tags rendered, especially
   before "Trying hard" (§0 audio note).
3. Source and license the music bed (§5).
4. Rename to the corpus convention `[I]` — `S003_img01_hook.png` … `S003_vo_full.mp3`,
   `S003_music.mp3`, `S003_cover.png`, `S003_final_1080x1920.mp4`. (Also normalizes the
   lowercase `shot 4.png` / `shot 5.png`.)

**CapCut** `[T]` — free, the Shorts default:
5. New 9:16 project, 1080×1920. Import the VO master first and lay it on the timeline.
6. **Auto-caption the VO**, then hand-correct every word against the script `[I]`. This
   caption track is also your timing ruler — read the true in/out of the seven TTS units off it
   and replace every "Est." figure in §1–2.
7. Lay the twelve shots in the §2 order, snapping each cut to its **cue word**, not the estimate.
8. Apply the keyframe moves from §2's motion column. Push-ins concentrate on the early shots for
   a premium feel `[C] (One Person Business, eVePkmCQV5c)`.
9. Build the Shot 10 rack-focus substitute (duplicate layer + masked blur ramp).
10. Style the caption track to §3's spec; add the hook card, claim cards, STAT build, disclosure
    line, Payoff caption, and end card on the §3 schedule.
11. Add the music bed. **Duck it manually with volume keyframes** to −21/−22 dB under the VO —
    CapCut's free tier has no one-click auto-duck. Cut the bed out entirely across the study
    beat and pause it before the Payoff line.
12. Normalize toward −14 LUFS by ear (no LUFS meter in the free tier) + the phone-speaker check.
13. Build the cover from `thumbnail.png` + amber `COUNTED` in the reserved left third.
14. Export 1080×1920 H.264 30fps.

**Paid alternative** `[T]` — only if a step becomes the bottleneck. Premiere Pro's Essential
Sound panel one-click-ducks to ≈−22 dB and its Remix tool matches music length without pitch
shift; Submagic (~$23/mo annual) does animated karaoke captions. **Don't overspend — most AI
tools are convenience luxuries, not requirements** `[C] (Romayroh, nFT1xNDprIk)`. For this
Short the likely bottleneck is CapCut's manual ducking, not its captions.

**Publish sequence** `[C] (Make Money Matt, RsAKa_WN1sU; Romayroh, Wox4Jt_2t6w)`:
15. Upload to YouTube Studio **unlisted**. Let it fully process (transcription, frame analysis,
    guideline checks).
16. While it processes, run both gates in §7 and add all metadata.
17. **Then** schedule public. Don't let it "sit" a day expecting an algorithmic boost — that's a
    myth `[C] (Nick Nimmin, 0l2g3Bujy1Y)`. Space uploads out rather than batching `[C] (Make
    Money Matt, tqCMF3mI9Pg)`.
18. Read CTR/AVD against channel average at 24–48h `[C] (vidIQ, ZKsldrcO_fU)`.

---

## 7. QA gate + Publish gate (run while unlisted, before scheduling)

### QA gate
- [ ] **Watched on a phone, sound off then on.** Sound-off: does the two-frame argument survive
      on visuals + text alone? `[C] (Kallaway, i7upRL4H1FM)` Sound-on: voice clear over the bed
      on phone speakers `[I]`.
- [ ] **First 2s stops the swipe — no intro, no logo, no filler** `[C] (vidIQ, DiZnbihU4NM)`.
- [ ] **No text in the bottom 20% or right 12%** — re-check on the exported file; captions drift
      after render `[I]`.
- [ ] **Loudness ≈ −14 LUFS, music never overpowers the VO** `[I]`.
- [ ] **No banned openers** ("in this video", "hey guys") `[C] (vidIQ, UCrC5B3Soyc; Nick Nimmin,
      2vkX1X1K3WM)` — verify the delivered take didn't drift.
- [ ] **Last frame matches the first frame** — replay it twice and confirm the loop reads as one
      continuous shot `[C] (Jenny Hoyos, mhVDcqnxxaY)`.

### Publish gate
- [ ] **YouTube's altered/synthetic-content disclosure set at upload** `[T]` (verified
      2026-07-23 — **re-verify**). ElevenLabs VO carries a SynthID watermark; undisclosed
      altered content risks demonetization/YPP rejection `[C] (Romayroh, G9LfE3k-IEI)`.
- [ ] **Disclosure line also in the description and every cross-post caption** `[B]`.
- [ ] **Made-for-kids OFF** `[C] (One Person Business, eVePkmCQV5c)`.
- [ ] **Studio "restrictions" reads NONE** `[C] (Make Money Matt, 10yFPNpnjY0; Dan the creator,
      JPTr40J3WXU)`.
- [ ] **Not a duplicate template/script** of Short A or Short B `[C] (Romayroh, KbUXzJ55eJk /
      Wox4Jt_2t6w)`.
- [ ] **R10 figures spot-checked** against the current `rgs-r10-science-of-fun.md` `[G]`.

---

## 8. Constraints that survive to publish (carried verbatim `[G]`)

Restated intact so `social-repurpose` inherits them rather than re-deriving them:

1. **Ellen Key is paraphrase-caution — never an on-screen quote/direct-attribution card.**
   Paraphrase in voiceover only; attribute "the reformer Ellen Key, 1900," spoken. Attribute the
   "work for work's sake" line as **Key relaying Ruskin**, not as Key's own words. Keep the
   passage's **corporal-punishment context out of the Short entirely** — the Short is about a
   theory of value, not about punishment.
2. **R10 research phrasing:** keep the two tiers straight (81 determinants → 11 factors; winning
   is not one of the 11 and sits *roughly* 40th of the 81); name the study on-screen and in
   voiceover ("a 2015 George Washington University study"); scope is youth soccer players,
   coaches and parents — don't generalize the measured population; association, never causation.
   Ship the narrowed claim ("effort ranked first; winning wasn't in the top tier"), never "kids
   don't care about winning."
3. **Frame guardrail (the whole point of this Short).** The reframe must resolve on the child's
   *present worth*, and must **never** be re-justified with an outcome — no "and that's how you
   raise a winner," no elite-outlier proof. Resolving on an outcome reinstates the exact "crude
   theory of value" the Short sets down, and the argument then reads as consolation for losing
   instead of a prior claim the culture forgot. The intellectual backbone (Key) is what keeps it
   from reading as consolation; do not cut it to save time.
4. **Villain placement:** the villain is the theory of value / the system that hands it to
   parents as "how sports works" — never the parent. End on relief and agency, not on alarm.
5. Cited figures are as of the **2026-07-18** corpus edition — spot-check against the current
   `rgs-r10-science-of-fun.md` before the Short ships.

**Assembly-stage consequences of the above:** no quotation-mark styling anywhere near the
Ellen Key lower-third (constraint 1); the STAT build must show both tiers, never collapse them
(constraint 2); no end-card copy that promises a result (constraint 3); no accusatory typography
or SFX on "You were told to ease off so he'd win" (constraint 4).

---

## 9. Downstream

This edit plan plus the exported Short is the direct input to **`social-repurpose`**, which
turns the finished Short and its packaging into YouTube title/description/hashtags and
cross-platform caption variants. It inherits the disclosure line, the five publish-survival
constraints in §8, the comment-bait question, and the Short B pointer.
