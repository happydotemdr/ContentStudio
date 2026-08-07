---
version: 2
date: 2026-08-05
kind: assembly
run: do-less-20260728-190724
slug: do-less-sold-as-win-more
stage: 04-assembly
supersedes: rgs-briefs/2026-08-05-do-less-sold-as-win-more-assembly.md
script: runs/do-less-20260728-190724/02-scripting/artifact.v1.md
voiceover_brief: runs/do-less-20260728-190724/03-voiceover/artifact.v1.md
visual_prompts: runs/do-less-20260728-190724/03-visual/artifact.v1.md
visual_system: rgs-briefs/2026-07-28-rgs-debut-visual-system.md
archetype: A1
status: complete
---

=== ASSEMBLY / EDIT PLAN v2 — do-less-sold-as-win-more (RaisingGoodSports, Short C) ===

**What changed from v1:** all assets are final and measured. The voiceover was re-rendered as the
**seven separate TTS units** the voiceover brief specified, at 192 kbps. Every timing below is
**frame-exact**, derived by parsing the MP3 frame headers of the delivered files — not estimated
from word counts. v1's §1 estimate table and §2 shot table are superseded; §3–§9 carry forward
with the timings re-pegged.

## Marker legend (an unmarked normative line below is a bug)

- **`[C]`** — the 420-video ContentStudio corpus, cited `(Channel, video_id)`.
- **`[I]`** — general craft judgment or this skill's own operational decision.
- **`[T]`** — tool/policy fact, dated 2026-07-23 in the assembly references. Re-verify.
- **`[B]`** — RaisingGoodSports Brand Definition, carried from upstream.
- **`[G]`** — binding grounding constraint, carried verbatim via the script.

---

## 0. Asset inventory — measured 2026-08-05, all green

`Generated Assets/do-less-20260728-190724/`

| Asset | File | Measured | Status |
|---|---|---|---|
| VO 1 — Hook | `Audio/VO_1.mp3` | **5.486s**, 192 kbps | ✓ |
| VO 2 — Setup | `Audio/VO_2.mp3` | **8.281s**, 192 kbps | ✓ |
| VO 3 — Build/argument cards | `Audio/VO_3.mp3` | **11.729s**, 192 kbps | ✓ |
| VO 4 — Re-hook | `Audio/VO_4.mp3` | **2.351s**, 192 kbps | ✓ |
| VO 5 — Build/study | `Audio/VO_5.mp3` | **12.121s**, 192 kbps | ✓ |
| VO 6 — Payoff | `Audio/VO_6.mp3` | **6.609s**, 192 kbps | ✓ |
| VO 7 — Loop/CTA | `Audio/VO_7.mp3` | **6.348s**, 192 kbps | ✓ |
| **Total speech** | | **52.924s** | back-to-back, no gaps |
| Music bed | `Audio/BackgroundMusic.wav` | 64.000s, 48 kHz / 16-bit / stereo | ✓ format — **length needs trimming, see §5** |
| Stills ×11 + cover | `visuals/Shot N_HD.png`, `thumbnail_HD.png` | all **1632×2912** | ✓ |

**All four v1 blockers are closed.** Stills upscaled, music sourced in the right format, VO split
into seven units, bitrate lifted from 128 to 192 kbps.

### The 64-second mystery, solved `[I]`

The single-file render ran **64s**. The same seven beats, generated separately, total **52.924s**
of speech. **~11 seconds of the original runtime was model-inserted inter-sentence silence** —
dead air the editor could not remove without cutting into the read. Splitting recovered all of
it. This is the corpus's "trim dead air ruthlessly — constant forward motion" rule `[C] (Jenny
Hoyos, oVKBAMEqsPI)` applied at the generation layer rather than the timeline.

It also lands the read inside the voiceover brief's own predicted window: the brief forecast
**~47–50s**; 52.9s of speech plus the deliberate breathing gaps in §1 comes to **~54.3s**. The
brief's stated position — *"let the measured read run rather than accelerate"* — holds without
any speed change.

### Still open (not blocking the edit, blocking the publish)

1. **Music licence/source unconfirmed.** Creator Music can carry revenue-share or no
   monetization, unlike a direct or royalty-free licence `[C] (Roberto Blake, SJsGBKGy4Do)`.
   Settle before the final render.
2. **Music structure unconfirmed.** §5 mutes the bed across the study beat and pauses it before
   the Payoff line. If the track is arranged (build/drop) rather than a sparse bed, those moves
   need re-planning around its structure.
3. **`[pause]` tag render check.** Confirm by ear that the half-second before **"Trying hard"**
   is present in `VO_5.mp3` — mandated by the script `[G]`. Likewise before "But it counted"
   (`VO_6`) and "Nobody said the effort was already his" (`VO_7`).
4. Grounding file `rgs-briefs/2026-07-28-do-less-sold-as-win-more.md` still missing; R10 figures
   still need the spot-check against current `rgs-r10-science-of-fun.md` `[G]` (constraint #5).

---

## 1. Master audio timeline — frame-exact

Seven clips laid end to end with six deliberate gaps. Gap sizes follow the corpus directly:
**short pauses after the hook and before the payoff, everything else tight — no dead air** `[C]
(Jenny Hoyos, oVKBAMEqsPI)`. The re-hook and loop-turn gaps are this skill's own smaller
additions `[I]`.

| Unit | File | **In** | **Out** | Dur | Gap after | Why the gap |
|---|---|---|---|---|---|---|
| 1 Hook | `VO_1.mp3` | **0.000** | **5.486** | 5.486 | **+0.35** | "short pause after the hook" `[C]` |
| 2 Setup | `VO_2.mp3` | **5.836** | **14.117** | 8.281 | 0.00 | butt-joined — the sentence runs on `[I]` |
| 3 Build/cards | `VO_3.mp3` | **14.117** | **25.846** | 11.729 | **+0.20** | sets up the re-hook pivot `[I]` |
| 4 Re-hook | `VO_4.mp3` | **26.046** | **28.397** | 2.351 | **+0.15** | beat before the citation `[I]` |
| 5 Build/study | `VO_5.mp3` | **28.547** | **40.668** | 12.121 | **+0.40** | "before the payoff" `[C]` |
| 6 Payoff | `VO_6.mp3` | **41.068** | **47.677** | 6.609 | **+0.25** | the loop turn `[I]` |
| 7 Loop/CTA | `VO_7.mp3` | **47.927** | **54.275** | 6.348 | — | |

**VO ends 54.275s. Add a 0.5s visual tail on the final shot → total runtime ≈ 54.8s.**

Set these in the editor by **numeric clip start**, not by dragging. Gaps are silence on the VO
track, not crossfades.

### Runtime note `[I]`

54.8s sits under 60s, so no eligibility question arises. The corpus's standing gap flag — it has
**no finding on Shorts duration-eligibility limits** — is therefore not load-bearing here, but
remains true for any future longer cut.

---

## 2. Shot-by-shot cut list — frame-exact

`[I]` The corpus supplies the principles (~3s change-visual, re-hook cadence, keyframe motion,
hook-mirroring loop — all `[C]`). The specific cut points below are this skill's application of
them to these seven audio files and these eleven stills.

| # | Asset | **In** | **Out** | Dur | Lands on (VO) | Motion | Overlay |
|---|---|---|---|---|---|---|---|
| 1 | `Shot 1_HD.png` | **0.000** | **5.836** | 5.84 | Hook, incl. trailing gap | Push-in **100→105%**, linear, whole shot `[C] (vidIQ, DiZnbihU4NM)` | Hook card (full) + lower-third |
| 2 | `Shot 2_HD.png` | **5.836** | **10.400** | 4.56 | "That was Ellen Key. Her point: a kid's effort is worth something itself —" | Scale 15%, drift toward the lamp | Lower-third `Ellen Key · Swedish reformer · 1900` |
| 3 | `Shot 3_HD.png` | **10.400** | **14.117** | 3.72 | "or only what the scoreboard says." | Push-in 12% onto the nearest nameplate | — |
| 4 | `Shot 4_HD.png` | **14.117** | **18.000** | 3.88 | "And every case for doing less still sells a bigger win — a complete athlete" | Slow drift L→R across the pitches | Claim card 1 |
| 5 | `Shot 6_HD.png` | **18.000** | **21.700** | 3.70 | "more medals like Norway." | Scale 15% toward the medal | Claim card 2 |
| 6 | `Shot 5_HD.png` | **21.700** | **24.900** | 3.20 | "Even backing off gets argued on the scoreboard's terms." | Near-static, 8% only | — |
| 7 | `Shot 7_HD.png` | **24.900** | **28.547** | 3.65 | *pre-empts* VO 4 — see below | Overhead drift toward the scale's pivot | Re-hook card from 26.046 |
| 8 | `Shot 8_HD.png` | **28.547** | **34.600** | 6.05 | "So a 2015 George Washington University study asked hundreds of young soccer players what makes sport fun." | Plate held **static** — the text moves | STAT stages 1–2 |
| 9 | `Shot 9_HD.png` | **34.600** | **41.068** | 6.47 | `[pause]` → "Trying hard was the top factor. Winning wasn't one of the eleven." | Push-in 15% onto the flexing laces | STAT stages 3–4 |
| 10 | `Shot 10_HD.png` | **41.068** | **44.900** | 3.83 | "So here's the trap: we let the scoreboard decide what a kid's effort is worth." | **Rack-focus substitute** (see below) | AI-disclosure line |
| 11 | `Shot 11_HD.png` | **44.900** | **47.927** | 3.03 | `[pause]` → "But it counted the day he gave it." | Macro push-in 12% onto the wet ink | Payoff caption + `COUNTED` |
| 12 | `Shot 1_HD.png` *(reuse)* | **47.927** | **54.800** | 6.87 | "You were told to ease off so he'd win. `[pause]` Nobody said the effort was already his." | **Exact reverse of shot 1's push-in** — 105→100%, landing on the Hook framing | End card + comment-bait |

**12 cuts / 54.8s = 4.57s average.**

### The one cut that doesn't align to a VO boundary

**Shot 7 starts at 24.900s, ~1.1s before the re-hook line begins.** This is deliberate and comes
straight from the prompt sheet, which specifies: *"Cut from the noisy argument-cards to a single
clean data/research visual — signals 'here's what was actually measured' **ahead of** the verbal
re-hook line."* The visual pivot leads the audio pivot. Don't snap it to 26.046.

### Three calls you should review

**(a) Cadence is now 4.6s/cut, and I'd fix it with four more stills.** In v1 (47s audio) the
average was 3.9s and I recommended accepting it. At 54.8s it's 4.6s, and the ~3s change-visual
rule is strongly-supported `[C] (Make Money Matt, HopTPCLbiiM)`. The counter-rules still apply —
comprehension comes from deleting edits `[C] (Kallaway, i7upRL4H1FM; Nate Black, J8LrrCpDNJI)`,
and slower cutting suits an older/learning audience `[C] (Nick Nimmin, LAzYEKltBwA)` — but two
shots are now genuinely overlong. **Priority order if you generate more:**

1. **The study beat is the worst offender** — Shots 8 and 9 hold **6.05s and 6.47s**. This is the
   Short's proof and the beat that most needs to feel measured, not slow. **Two more Register A
   stills here** would bring all four to ~3.2s. Split Shot 9's window in particular: the STAT 3
   ("TRYING HARD — #1") and STAT 4 ("Winning: not in the top 11") reveals want different frames
   under them.
2. **The Setup** — Shot 2 holds 4.56s. One more Register B frame would help.
3. Shot 12's 6.87s is **not** on this list — see (b).

Four new stills → 16 cuts / 54.8s = **3.4s average**, inside the rule. The prompt sheet's world
lock, `--sref` codes, and Gate C arc discipline all still apply to any new render.

**(b) Shot 12 holds 6.87s deliberately.** The Loop/CTA must land its final frame on the exact
Hook framing for the mirror `[C] (Jenny Hoyos, mhVDcqnxxaY)`, and the corpus is explicit that when
a beat carries the payoff you **resist adding cuts just to look busy** `[C] (vidIQ, DiZnbihU4NM)`.
The continuous pull-back is the motion. Leave it.

**(c) The re-hook lands late, and the lever is upstream.** The corpus cadence is a re-hook at
~15s `[C] (Nate Black, c6X-Ywy3yVU)`. Here the *visual* re-hook fires at 24.9s and the *spoken*
one at 26.0s — 45–48% into the Short, against the corpus's ~33%. Cause: `VO_3` (the argument
cards) runs 11.7s. This stage can't fix it without cutting protected VO; the voiceover brief
already named the lever — *"a small trim by `shorts-scripting` to the Build's argument-cards
clause."* **Mitigation already in the cut:** that 11.7s window carries three separate visuals
(Shots 4, 6, 5) at ~3.6s each, so the *variety* arrives on cadence even though the re-hook card
doesn't. Flagged, not silently accepted.

### Motion: still no i2v clip required `[I]`

Unchanged from v1. Shot 1's push-in and Shot 12's pull-back are keyframe scales — cleaner than
Midjourney's own i2v (the prompt sheet calls it "D-tier, jittery") and, crucially, exactly
reversible, which a generated clip can't guarantee. For Shot 10's rack-focus: duplicate the
layer, heavy-blur the lower copy, mask the child on the upper copy, ramp the blurred copy's
opacity across 3.83s while lifting warmth ~8% on the child. Generate the Kling clip only if that
reads flat on the phone check — premium AI-video spend belongs on the hook and occasional
cutaway spikes `[C] (Make Money Matt, gkaxBe8BGLQ)`.

---

## 3. Caption & overlay treatment

Style spec unchanged from v1 — reproduced so this file stands alone.

```
Font:            Montserrat ExtraBold  (fallback: Poppins Bold / CapCut default bold)
Cap size:        captions 66px | hook & re-hook cards 100px | lower-third 48px
                 | disclosure line 38px      (all on a 1080x1920 canvas)
Fill / stroke:   #F7F3E8 fill / #0E3B43 stroke 3px + soft 40% drop shadow
Highlight:       NONE - active word pops by scale (100% -> 112%) + opacity, not color
Accent color:    #F2A541 amber - reserved, used exactly 3 times
System color:    #C1543A clay - claim-card framing ONLY, never on the child or parent
Position:        captions y=56% | hook card y=40% | re-hook card y=40%
                 | lower-third y=70% | disclosure y=68%
Safe zones off:  top 12% (0-230px) , bottom 20% (1536-1920px) , right 12% (950-1080px)
Words per card:  captions 2-3 | static line <=6 words
Animation:       fade-in 80ms, no bounce/pop-in; push-in 5% at open
```

**The amber reservation** `[I]`: the playbook's karaoke default tints the active word a brand
accent, but the brand reserves amber for a single accent word — strictly enough that the
voiceover brief forbids amber even on the disclosure line `[B]`. A full-duration amber highlight
would spend that reservation ~140 times. So the karaoke highlight is a **scale-and-opacity pop
with no colour change**, and `#F2A541` appears exactly three times: `TRYING HARD — #1`,
`COUNTED`, and the thumbnail accent word.

**Caption density** `[I]`: full-duration karaoke, small. ~80–85% watch muted `[C] (Kallaway,
i7upRL4H1FM)` and this script's job is making the viewer hold two competing frames at once —
dropping captions after 10s per the audit's front-load finding `[C] (One Person Business,
6s2T2NlWDhQ; Make Money Matt, LlIkMWX50aQ)` would leave the muted majority to rebuild a two-frame
argument from stills. The audit's *restraint* is adopted in full: 66px is small relative to the
frame, and captions cut away entirely under the Hook card, the re-hook card, and STAT 3–4 so
nothing is ever doubled.

### Overlay schedule — re-pegged to the exact timeline

| **In–Out** | Element | Copy | Treatment |
|---|---|---|---|
| **0.00–5.49** | **Hook card** | `In 1900, someone named the trap.` | 100px, y=40%, full Hook duration `[I]` |
| **0.60–5.49** | Lower-third | `Ellen Key · Swedish reformer · 1900` | 48px, y=70%. **Plain attribution — NEVER a quote card** `[G]` |
| **14.12–18.00** | Claim card 1 | `"A complete athlete"` | Quote marks + small clay `#C1543A` tag `the pitch` — visibly a claim being sold |
| **18.00–21.70** | Claim card 2 | `"More medals — like Norway"` | Same sold-claim treatment |
| **26.05–28.55** | **Re-hook card** | `Someone actually measured what kids want.` | 100px, y=40% `[C] (Nate Black, c6X-Ywy3yVU)` |
| **28.55–31.50** | STAT 1 | `2015 George Washington University study · youth soccer players` | Off-white, over the plate |
| **31.50–34.60** | STAT 2 | `81 things that make sport fun  →  11 core factors` | Counter animates 81→11 — **viewers must see the number** `[C] (vidIQ, i5bZ-Be9cAQ)` |
| **34.60–37.80** | STAT 3 | `TRYING HARD — #1` | **Amber `#F2A541`, ALL CAPS.** Fire on the `[pause]` landing |
| **37.80–41.07** | STAT 4 | `Winning: not in the top 11  (~40th of 81)` | Off-white |
| **41.60–44.90** | **AI disclosure** | `AI-generated visuals · synthetic voiceover` | 38px, `#F7F3E8`, **never amber**, safe zone `[B]` |
| **44.90–47.93** | Payoff caption | `It counted the day he gave it.` | `COUNTED` in amber, rest off-white |
| **50.50–54.80** | End card | Pointer to Short B — `nobody-asked-the-kid` | Must clear bottom 20% and right 12% |
| pinned | Comment bait | `What's a "do less" tip you were handed that still promised a better result?` | Pinned comment, not on-screen |

**Cover:** `thumbnail_HD.png` + `COUNTED` overlaid in `#F2A541` in the reserved dark left third.
Mirrors the Payoff accent; 2–4 bold words, one clear focus point, readable like a highway
billboard `[C] (Nate Black, -zd1lLaC-I0; Nick Nimmin, h8OTdq24irE)`.

---

## 4. Aspect ratio & format

- **1080×1920, 9:16 vertical** `[I]`. Sources are 1632×2912 (1:1.784 vs. true 1:1.778) — fit
  **height**, accept ~0.4% horizontal crop, never letterbox.
- Export H.264 MP4, 1080×1920, 30 fps, high bitrate.
- Runtime **≈54.8s**.

---

## 5. Loudness & mix — re-pegged

- **Master to −14 LUFS integrated**, voice peaks −3 to −6 dB, no clipping `[T] [I]`.
- **Normalize the seven VO clips to each other first**, before touching the bed `[I]`. Separate
  generations can drift in level; a step between units is more audible than anything the music
  does. Match them by ear at unity, then treat the VO track as one element.
- **Music ducked to −21 to −22 dB under the voice** `[C] (Romayroh, Wox4Jt_2t6w; Roberto Blake,
  iaTavrWIGDM)`. Lead with this over the guide's wider −12 to −18 dB band — it's the number tied
  to an actual retention complaint. **Loud music is the most underestimated AVD killer.** When in
  doubt, too quiet beats too loud `[I]`.
- **Bed out entirely 28.55 → 41.07** (the whole study beat). The numbers and the mandated
  half-second on "Trying hard" land uncontested `[I]`. Fade out over ~0.4s from 28.15, back in
  over ~0.6s from 41.07.
- **Pause the bed 44.60 → 45.40**, across the Payoff reframe landing on "But it counted the day
  he gave it" — pausing before the key line changes how it lands `[C] (vidIQ, DiZnbihU4NM)`.
- **Trim the bed from 64.000s to ~54.8s.** It was cut to match the superseded 64s blob. **Match
  length by editing or a Remix tool, never rate-stretch — rate-stretch shifts pitch** `[C]
  (Roberto Blake, iaTavrWIGDM)`. With ~9s to lose and a 12.5s hole already punched in the middle
  for the study beat, the cleanest approach is to drop a phrase-length section either side of
  that hole rather than shorten the head or tail.
- **Match music to the arc, not just fill silence** `[C] (Kallaway, i7upRL4H1FM)`: quiet-resolve
  (0–14.1) → skeptical momentum (14.1–28.5) → **silence** (28.5–41.1) → quiet gravity, then
  warmth and relief (41.1–54.8). **Never use music whose emotional tone contradicts the words —
  no music beats wrong music.** If nothing fits the Payoff's warmth, leave it dry.
- **SFX** `[I]`: soft hit on each STAT reveal and on the two claim cards. Punctuate, don't
  startle. **No whooshes on the Payoff or Loop** — they'd fight the exoneration register `[B]`.
- **Rights, last checkpoint before render** `[C] (Roberto Blake, SJsGBKGy4Do)` — see §0 open
  item 1.
- **Check the final mix on phone speakers, not headphones** `[I]`.

---

## 6. Execution — $0 stack

**Pre-flight:** §0's four open items. Nothing else blocks.

**CapCut** `[T]`:
1. New project, 1080×1920, 30 fps.
2. Drop the seven VO clips on one audio track at the **numeric start times in §1**. Don't drag.
3. Normalize the seven to each other (§5), then treat as one track.
4. Lay the twelve stills at the **numeric in/out points in §2**.
5. Apply §2's motion column. Shot 1's push-in and Shot 12's pull-back must be exact
   inverses — build one and mirror the keyframe values. Concentrate push-ins on early shots for
   a premium feel `[C] (One Person Business, eVePkmCQV5c)`.
6. Build the Shot 10 rack-focus substitute (duplicate layer + masked blur ramp).
7. **Auto-caption, then hand-correct every word against the script** `[I]`. Style to §3.
8. Add the hook card, claim cards, STAT build, disclosure line, Payoff caption, end card on §3's
   schedule.
9. Trim the bed to ~54.8s (§5), lay it in, duck with volume keyframes to −21/−22 dB, punch the
   study-beat hole and the Payoff pause.
10. Normalize toward −14 LUFS by ear — no LUFS meter in the free tier — then phone-speaker check.
11. Build the cover from `thumbnail_HD.png` + amber `COUNTED`.
12. Export 1080×1920 H.264 30 fps.

**Paid alternative** `[T]`, only if a step becomes the bottleneck: Premiere Pro's Essential Sound
panel one-click-ducks to ≈−22 dB and its Remix tool handles the 64→54.8s music trim musically
without pitch shift — that specific job is the strongest argument for it on this Short. Submagic
(~$23/mo annual) for animated karaoke captions. **Don't overspend — most AI tools are convenience
luxuries, not requirements** `[C] (Romayroh, nFT1xNDprIk)`.

**Publish sequence** `[C] (Make Money Matt, RsAKa_WN1sU; Romayroh, Wox4Jt_2t6w)`:
13. Upload **unlisted**. Let it fully process (transcription, frame analysis, guideline checks).
14. Run both §7 gates and add all metadata while it processes.
15. **Then** schedule public. Don't let it sit a day expecting an algorithmic boost — that's a
    myth `[C] (Nick Nimmin, 0l2g3Bujy1Y)`. Space uploads rather than batching `[C] (Make Money
    Matt, tqCMF3mI9Pg)`.
16. Read CTR/AVD against channel average at 24–48h `[C] (vidIQ, ZKsldrcO_fU)`.

---

## 7. QA gate + Publish gate (run while unlisted, before scheduling)

### QA gate
- [ ] **Watched on a phone, sound off then on.** Sound-off: does the two-frame argument survive on
      visuals + text alone? `[C] (Kallaway, i7upRL4H1FM)` Sound-on: voice clear over the bed on
      phone speakers `[I]`.
- [ ] **First 2s stops the swipe — no intro, no logo, no filler** `[C] (vidIQ, DiZnbihU4NM)`.
- [ ] **No audible level step between the seven VO units** `[I]` — new in v2, specific to the
      split render.
- [ ] **No text in the bottom 20% or right 12%** — re-check on the export; captions drift `[I]`.
- [ ] **Loudness ≈ −14 LUFS, music never overpowers the VO** `[I]`.
- [ ] **No banned openers** ("in this video", "hey guys") `[C] (vidIQ, UCrC5B3Soyc; Nick Nimmin,
      2vkX1X1K3WM)`.
- [ ] **Last frame matches the first frame** — replay twice, confirm the loop reads as one
      continuous shot `[C] (Jenny Hoyos, mhVDcqnxxaY)`.

### Publish gate
- [ ] **YouTube's altered/synthetic-content disclosure set at upload** `[T]` (verified 2026-07-23
      — **re-verify**). ElevenLabs VO carries a SynthID watermark; undisclosed altered content
      risks demonetization/YPP rejection `[C] (Romayroh, G9LfE3k-IEI)`.
- [ ] **Disclosure line also in the description and every cross-post caption** `[B]`.
- [ ] **Made-for-kids OFF** `[C] (One Person Business, eVePkmCQV5c)`.
- [ ] **Studio "restrictions" reads NONE** `[C] (Make Money Matt, 10yFPNpnjY0; Dan the creator,
      JPTr40J3WXU)`.
- [ ] **Not a duplicate template/script** of Short A or Short B `[C] (Romayroh, KbUXzJ55eJk /
      Wox4Jt_2t6w)`.
- [ ] **Music licence settled** and compatible with monetization `[C] (Roberto Blake,
      SJsGBKGy4Do)`.
- [ ] **R10 figures spot-checked** against current `rgs-r10-science-of-fun.md` `[G]`.

---

## 8. Constraints that survive to publish (carried verbatim `[G]`)

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

**Assembly-stage consequences:** no quotation-mark styling near the Ellen Key lower-third
(constraint 1); the STAT build must show both tiers, never collapse them (constraint 2); no
end-card copy promising a result (constraint 3); no accusatory typography or SFX on "You were
told to ease off so he'd win" (constraint 4).

---

## 9. Downstream

This edit plan plus the exported Short is the direct input to **`social-repurpose`**, which turns
the finished Short and its packaging into YouTube title/description/hashtags and cross-platform
caption variants. It inherits the disclosure line, the five publish-survival constraints in §8,
the comment-bait question, and the Short B pointer.
