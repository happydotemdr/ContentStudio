---
version: 3
date: 2026-08-05
kind: assembly
run: do-less-20260728-190724
slug: do-less-sold-as-win-more
stage: 04-assembly
supersedes: rgs-briefs/2026-08-05-do-less-sold-as-win-more-assembly-v2.md
script: runs/do-less-20260728-190724/02-scripting/artifact.v1.md
voiceover_brief: runs/do-less-20260728-190724/03-voiceover/artifact.v1.md
visual_prompts: rgs-briefs/2026-08-05-do-less-sold-as-win-more-visual-prompts-v2.md
visual_system: rgs-briefs/2026-07-28-rgs-debut-visual-system.md
archetype: A1
status: complete
---

=== ASSEMBLY / EDIT PLAN v3 — do-less-sold-as-win-more (RaisingGoodSports, Short C) ===

**BUILD SHEET. Every asset exists. Nothing further is generated.** This is the plan to cut from,
against the 15 rendered stills, the 7 VO units, and `BackgroundMusic_V2.wav`.

**What changed from v2:** v2's 12-cut list assumed four stills that hadn't been rendered yet. They
now exist, so this is the **16-cut** list against real filenames. It also carries the run owner's
**explicit decision to ship the assets as rendered** rather than re-harvest `--sref` codes and
re-render — see §0.1, which records that decision, what it costs, and the in-edit mitigations that
replace the re-render.

## Marker legend (an unmarked normative line below is a bug)

`[C]` corpus-cited `(Channel, video_id)` · `[I]` general craft or this skill's own call · `[T]`
tool/policy fact dated 2026-07-23, re-verify · `[B]` RaisingGoodSports Brand Definition · `[G]`
binding grounding constraint carried verbatim.

---

## 0. Assets — measured 2026-08-05

| Element | File | Measured |
|---|---|---|
| VO ×7 | `Audio/VO_1..7.mp3` | 5.486 / 8.281 / 11.729 / 2.351 / 12.121 / 6.609 / 6.348 s — **52.924s** total, 192 kbps |
| Music | `Audio/BackgroundMusic_V2.wav` | **55.000s**, 48 kHz / 16-bit / stereo — length matches the cut |
| Stills ×15 | `visuals/*.png` | all **1632×2912** |
| Cover | `visuals/thumbnail_HD.png` | 1632×2912, accent word not baked in ✓ |

### 0.1 The ship-as-rendered decision `[I]`

The prompt sheet specifies a **dual-register** system: Register A photographic/present, Register B
painterly/1900, each locked by its own `--sref` code. The codes on the sheet
(`SREF-RGS-A-DL01`, `SREF-RGS-B-01`) are **placeholders that were never harvested**, so no render in
this Short ever had a style lock applied. The result is a Register B that is only half-delivered:

| Sheet shot | File | Actual look | Verdict |
|---|---|---|---|
| 3 | `Shot 5_HD.png` | **True oil painting** — visible brushwork, canvas tooth, scale on the desk | On-register ✓ |
| 15 | `Shot 11_HD.png` | Warm chiaroscuro, painterly-adjacent | On-register ✓ |
| 2 | `Shot 2_HD.png` | **Flat vector/cel illustration** | Off-register, and see §0.2 |
| 6 | `Shot 6b_HD.png` | Warm photographic still life; none of the prompted motif objects | Off-register |
| 13 | `Shot13.png` | Warm photographic golden hour | Off-register |

**Decision (run owner, 2026-08-05): ship as rendered.** The correct fix — harvest two real style
codes via a Draft Mode job and re-render the six Register B shots — is deferred, not cancelled.

**What this costs, stated plainly:** the register split is no longer carried by *medium*. It has to
be carried by **content plus grade**, which is weaker but workable, because the two on-register
shots (3 and 15) define a look the other Register B shots can be graded toward — warm, low-key,
chiaroscuro. §4 is the grade spec that does that work. **This substitution is this skill's own call
`[I]`, not a corpus finding.** Register A's separate problem — every present-day render drifted
warm golden-hour against a prompt asking for cold teal-grey — is also a grade fix, not a re-render.

**Carry this forward:** harvest the two real `--sref` codes before Short D. This defect will repeat
on every Short until the codes exist.

### 0.2 Shot 2 — a grounding constraint, not a preference `[G]`

`Shot 2_HD.png` renders Ellen Key's face **fully lit and legible**. The world lock says "face turned
into shadow — never a likeness of Ellen Key," and grounding constraint 1 makes her
paraphrase-caution. A clear, legible portrait presented as a named 1900 reformer is exactly the
likeness the constraint exists to prevent.

**Mitigation that requires no re-render:** **crop the top ~35% of the frame away** before import.
At 1632×2912 that leaves ~1632×1893 — still well above the 1080-wide canvas, so no quality cost.
What remains is the hand, the pen, the papers, the balance scale and the slate: the shot's actual
motif content, with the face removed. This also softens the flat-illustration read, since the face
is the most stylised element in the frame. **Do this crop. It is not optional** — it is the only
thing standing between the ship-as-rendered decision and a breached publish constraint.

### 0.3 Known weaknesses being shipped `[I]`

- **Shot 6** (`Shot 6b_HD.png`) is the weakest frame: a lamplit desk with a typewriter, carrying
  none of the prompted handiwork/scale/ledger motif, and occupying the same visual territory as
  Shot 2 (another lamplit desk). §5 repurposes it by moving claim card 1 onto it, which gives the
  frame a job it can actually do — see there.
- **Shots 11 and 13 will read as twins** without intervention: both warm, backlit, shallow-DOF
  running children, two cuts apart. The §4 grade split (11 cool, 13 warm and diffused) is what
  separates them. Check this specifically on the phone pass.
- **Shot 15** came back as a MID shot of a bearded man rather than the prompted MACRO on a hand,
  introducing a male figure not in the world lock. Shipping — it is a strong frame and the ledger,
  pen and scale all read. Noted so it isn't mistaken for the plan.

---

## 1. Master audio timeline — frame-exact

Seven VO clips end to end with six gaps. Gap sizes follow the corpus: **short pauses after the hook
and before the payoff, everything else tight — no dead air** `[C] (Jenny Hoyos, oVKBAMEqsPI)`.

| Unit | File | In | Out | Gap after |
|---|---|---|---|---|
| 1 Hook | `VO_1.mp3` | **0.000** | **5.486** | +0.35 |
| 2 Setup | `VO_2.mp3` | **5.836** | **14.117** | 0.00 |
| 3 Build/cards | `VO_3.mp3` | **14.117** | **25.846** | +0.20 |
| 4 Re-hook | `VO_4.mp3` | **26.046** | **28.397** | +0.15 |
| 5 Build/study | `VO_5.mp3` | **28.547** | **40.668** | +0.40 |
| 6 Payoff | `VO_6.mp3` | **41.068** | **47.677** | +0.25 |
| 7 Loop/CTA | `VO_7.mp3` | **47.927** | **54.275** | — |

**VO ends 54.275s. Add a 0.5s visual tail → total runtime ≈ 54.8s.** Set by numeric clip start, not
by dragging. Gaps are silence on the VO track, not crossfades.

---

## 2. Cut list — 16 cuts, real filenames

`[I]` The corpus gives the principles (~3s change-visual, re-hook cadence, keyframe motion,
hook-mirroring loop — all `[C]`). The cut points below are this skill's application of them to
these seven audio files and these fifteen stills. **Estimated times are to be nudged against the
caption track; the "Cut ON" cue word is the authority.**

| # | File | In | Out | Dur | Cut ON (VO cue) | Motion | Grade |
|---|---|---|---|---|---|---|---|
| 1 | `Shot 1_HD.png` | **0.000** | **5.836** | 5.84 | *(open cold — no logo, no filler)* | Push-in **100→105%** `[C] (vidIQ, DiZnbihU4NM)` | A |
| 2 | `Shot 2_HD.png` **(cropped, §0.2)** | **5.836** | **8.400** | 2.56 | "That was Ellen Key. Her point:" | Scale 12% toward the scale pan | B |
| 3 | `Shot 5_HD.png` | **8.400** | **11.600** | 3.20 | "a kid's effort is worth something itself —" | Slow drift toward the seated child | B |
| 4 | `Shot 3_HD.png` | **11.600** | **14.117** | 2.52 | "or only what the scoreboard says." | Push-in 12% onto the nearest nameplate | A |
| 5 | `Shot 4_HD.png` | **14.117** | **16.900** | 2.78 | "And every case for doing less still sells a bigger win —" | Drift L→R across the pitches | A |
| 6 | `Shot 6b_HD.png` | **16.900** | **19.900** | 3.00 | "a complete athlete," | Slow push-in 15% onto the shelf clutter | B |
| 7 | `Shot 6_HD.png` | **19.900** | **22.600** | 2.70 | "more medals like Norway." | Scale 15% toward the medal | A |
| 8 | `Shot 8a_HD.png` | **22.600** | **24.900** | 2.30 | "Even backing off gets argued on the scoreboard's terms." | Push-in 12% onto the flip cards | A |
| 9 | `Shot 7_HD.png` | **24.900** | **28.547** | 3.65 | *leads VO_4 by ~1.1s — see below* | Overhead drift toward the pivot | B |
| 10 | `Shot 8_HD.png` (PLATE) | **28.547** | **31.300** | 2.75 | "So a 2015 George Washington University study" | **Static** — the text moves | none |
| 11 | `Shot 11a_HD.png` | **31.300** | **35.400** | 4.10 | "asked hundreds of young soccer players what makes sport fun." | Slow push-in 15% | A |
| 12 | `Shot 9_HD.png` | **35.400** | **38.200** | 2.80 | `[pause]` → "Trying hard was the top factor." | Push-in 15% onto the laces | A |
| 13 | `Shot13.png` | **38.200** | **41.068** | 2.87 | "Winning wasn't one of the eleven." | Slow drift, minimal | B |
| 14 | `Shot 10_HD.png` | **41.068** | **44.900** | 3.83 | "So here's the trap:" | **Rack-focus substitute** — see below | A |
| 15 | `Shot 11_HD.png` | **44.900** | **47.927** | 3.03 | `[pause]` → "But it counted the day he gave it." | Push-in 12% onto the wet ink | B |
| 16 | `Shot 1_HD.png` *(reuse)* | **47.927** | **54.800** | 6.87 | "You were told to ease off so he'd win." | **Exact reverse of cut 1** — 105→100%, landing on the Hook framing | A |

**16 cuts / 54.8s = 3.43s average** — inside the ~3s change-visual rule `[C] (Make Money Matt,
HopTPCLbiiM)`.

**Cut 9 does not align to a VO boundary, deliberately.** The prompt sheet specifies the visual pivot
*leads* the spoken one: *"cut from the noisy argument-cards to a single clean data/research visual —
signals 'here's what was actually measured' ahead of the verbal re-hook line."* Start it at 24.900,
not 26.046.

**Cut 16 holds 6.87s deliberately.** The loop must land its final frame on the exact Hook framing
`[C] (Jenny Hoyos, mhVDcqnxxaY)`, and the corpus is explicit that on a payoff beat you **resist
adding cuts just to look busy** `[C] (vidIQ, DiZnbihU4NM)`. The continuous pull-back is the motion.
Build cut 1's push-in first, then mirror its keyframe values so the inverse is exact.

**Cut 14's rack-focus substitute:** duplicate the layer, heavy-blur the lower copy, mask the child on
the upper copy, ramp the blurred copy's opacity across 3.83s while lifting warmth ~8% on the child.
No Kling render needed — premium AI-video spend belongs on the hook and occasional cutaway spikes
`[C] (Make Money Matt, gkaxBe8BGLQ)`, and this beat doesn't need it.

---

## 3. Aspect, format, runtime

- **1080×1920, 9:16.** Sources are 1632×2912 (1:1.784 vs. true 1:1.778) — fit **height**, accept
  ~0.4% horizontal crop, never letterbox `[I]`.
- Export H.264 MP4, 1080×1920, 30 fps, high bitrate. Runtime **≈54.8s**.
- The corpus's standing gap flag — no finding on Shorts duration-eligibility limits — isn't
  load-bearing at 54.8s, but remains true for any future longer cut.

---

## 4. Grade — the substitute for the missing register split `[I]`

**This section replaces the re-render.** Two looks, applied per the Grade column in §2. Anchor each
on the shots that already have it and pull the rest toward them.

**Register A (present day) — cool.** Shots 1, 4, 5, 7, 8, 11, 12, 14, 16.
- Shadows toward teal-ink `#0E3B43`; lift the blue/cyan in the low end.
- Reduce amber/orange saturation ~20% — every present-day render drifted warm golden-hour against a
  prompt asking for cold teal-grey, and this is where that's corrected.
- +5 contrast. Keep the amber *rim light* on faces; it's the brand accent, just not the whole frame.

**Register B (1900) — warm, low-key, chiaroscuro.** Shots 2, 3, 6, 9, 13, 15.
- **Anchor on Shots 3 and 15** — they already carry the look; match the others to them, not to a
  spec.
- For Shots 6 and 13 specifically (the two photographic strays): lift blacks slightly, reduce
  clarity/micro-contrast ~15, add soft diffusion or bloom, increase grain. The goal is to remove
  photographic *crispness*, which is the single strongest cue separating them from Shot 3's paint.
- Do **not** cool these. Warmth is what marks the era here now that medium doesn't.

**Shot 10 (PLATE): no grade.** It is already the brand palette.

**The one thing to verify on the phone pass:** cuts 11 → 12 → 13. Shots 11 and 13 were near-twins
ungraded. If they still read as the same shot after grading, push Shot 13 further — more diffusion,
more warmth, less contrast — until they don't.

---

## 5. Caption & overlay treatment

```
Font:            Montserrat ExtraBold  (fallback: Poppins Bold / CapCut default bold)
Cap size:        captions 66px | hook & re-hook cards 100px | lower-third 48px
                 | disclosure line 38px      (on a 1080x1920 canvas)
Fill / stroke:   #F7F3E8 fill / #0E3B43 stroke 3px + soft 40% drop shadow
Highlight:       NONE - active word pops by scale (100% -> 112%) + opacity, not color
Accent color:    #F2A541 amber - reserved, used exactly 3 times
System color:    #C1543A clay - claim-card framing ONLY, never on the child or parent
Position:        captions y=56% | hook card y=40% | re-hook card y=40%
                 | lower-third y=70% | disclosure y=68%
Safe zones off:  top 12% (0-230px) , bottom 20% (1536-1920px) , right 12% (950-1080px)
Words per card:  captions 2-3 | static line <=6 words
Animation:       fade-in 80ms, no bounce/pop-in
```

**The amber reservation** `[I]`: the karaoke default tints the active word a brand accent, but the
brand reserves amber for a single accent word — strictly enough that the voiceover brief forbids
amber even on the disclosure line `[B]`. A full-duration amber highlight would spend that
reservation ~140 times. So the highlight is a **scale-and-opacity pop with no colour change**, and
`#F2A541` appears exactly three times: `TRYING HARD — #1`, `COUNTED`, and the thumbnail word.

**Caption density** `[I]`: full-duration karaoke, small. ~80–85% watch muted `[C] (Kallaway,
i7upRL4H1FM)` and this script asks the viewer to hold two competing frames at once — dropping
captions after 10s per the audit's front-load finding `[C] (One Person Business, 6s2T2NlWDhQ; Make
Money Matt, LlIkMWX50aQ)` would leave the muted majority to rebuild the argument from stills. The
audit's *restraint* is adopted in full: 66px is small relative to the frame, and captions cut away
entirely under the Hook card, the re-hook card and STAT 3–4 so nothing is ever doubled.

### Overlay schedule

| In–Out | Element | Copy | Treatment |
|---|---|---|---|
| **0.00–5.49** | **Hook card** | `In 1900, someone named the trap.` | 100px, y=40%, full Hook duration |
| **0.60–5.49** | Lower-third | `Ellen Key · Swedish reformer · 1900` | 48px, y=70%. **Plain attribution — NEVER a quote card** `[G]` |
| **16.90–19.90** | Claim card 1 | `"A complete athlete"` | Quote marks + small clay `#C1543A` tag `the pitch` |
| **19.90–22.60** | Claim card 2 | `"More medals — like Norway"` | Same sold-claim treatment |
| **26.05–28.55** | **Re-hook card** | `Someone actually measured what kids want.` | 100px, y=40% `[C] (Nate Black, c6X-Ywy3yVU)` |
| **28.55–31.30** | STAT 1 | `2015 George Washington University study · youth soccer players` | Off-white, over the plate |
| **31.30–35.40** | STAT 2 | `81 things that make sport fun  →  11 core factors` | Counter animates 81→11 — **viewers must see the number** `[C] (vidIQ, i5bZ-Be9cAQ)` |
| **35.40–38.20** | STAT 3 | `TRYING HARD — #1` | **Amber `#F2A541`, ALL CAPS.** Fire on the `[pause]` landing |
| **38.20–41.07** | STAT 4 | `Winning: not in the top 11  (~40th of 81)` | Off-white |
| **41.60–44.90** | **AI disclosure** | `AI-generated visuals · synthetic voiceover` | 38px, `#F7F3E8`, **never amber**, safe zone `[B]` |
| **44.90–47.93** | Payoff caption | `It counted the day he gave it.` | `COUNTED` in amber, rest off-white |
| **50.50–54.80** | End card | Pointer to Short B — `nobody-asked-the-kid` | Must clear bottom 20% and right 12% |
| pinned | Comment bait | `What's a "do less" tip you were handed that still promised a better result?` | Pinned comment, not on-screen |

**Claim card 1 moved onto cut 6** `[I]` — a change from v2, forced by what actually rendered.
`Shot 6b_HD.png` is a lamplit desk crowded with accumulated objects, bottles, books and a clock. It
carries none of the prompted handiwork motif, so as a silent cut it would be a confusing 3-second
detour. With `"A complete athlete"` stamped on it as a sold claim, the accumulation *becomes* the
pitch — the well-stocked life sold as completeness. That gives the weakest frame in the Short a job
it can actually do, and it keeps the sold-claim framing the grounding constraint requires.

**Cover:** `thumbnail_HD.png` + `COUNTED` in `#F2A541` in the reserved dark left third. Mirrors the
Payoff accent; 2–4 bold words, one clear focus point, readable like a highway billboard `[C] (Nate
Black, -zd1lLaC-I0; Nick Nimmin, h8OTdq24irE)`.

---

## 6. Loudness & mix

- **Master to −14 LUFS integrated**, voice peaks −3 to −6 dB, no clipping `[T] [I]`.
- **Normalize the seven VO clips to each other first** `[I]`. Separate generations drift in level;
  a step between units is more audible than anything the music does. Match at unity, then treat the
  VO as one element.
- **Music ducked to −21 to −22 dB under the voice** `[C] (Romayroh, Wox4Jt_2t6w; Roberto Blake,
  iaTavrWIGDM)` — the number tied to an actual retention complaint, not a general mixing guideline.
  **Loud music is the most underestimated AVD killer.** Too quiet beats too loud `[I]`.
- **Listen to the bed before cutting it.** It was generated with a near-silent breakdown prompted at
  **0:28–0:41**. If that rendered, the study beat already clears itself — just duck normally and
  don't cut. If it didn't, fade the bed out over ~0.4s from 28.15 and back in over ~0.6s from 41.07.
- **Pause the bed 44.60 → 45.40**, across the Payoff landing on "But it counted the day he gave it"
  — pausing before the key line changes how it lands `[C] (vidIQ, DiZnbihU4NM)`.
- **No trim needed.** `BackgroundMusic_V2.wav` is 55.000s against a 54.8s cut — align at 0.000 and
  fade the last ~0.3s.
- **Never use music whose emotional tone contradicts the words — no music beats wrong music** `[C]
  (Kallaway, i7upRL4H1FM)`. If the bed fights the Payoff's warmth, leave that beat dry.
- **SFX** `[I]`: soft hit on each STAT reveal and on the two claim cards. Punctuate, don't startle.
  **No whooshes on the Payoff or Loop** — they'd fight the exoneration register `[B]`.
- **Music rights: settled** — generated in ElevenLabs, owned by the channel (run owner confirmed
  2026-08-05). This closes the publish-gate rights item `[C] (Roberto Blake, SJsGBKGy4Do)`.
- **Check the final mix on phone speakers, not headphones** `[I]`.

---

## 7. Build steps — CapCut ($0 stack) `[T]`

**Pre-flight:**
1. **Crop the top ~35% off `Shot 2_HD.png`** and save as a new file (§0.2). Mandatory.
2. Listen to all seven VO units; confirm the `[pause]` before **"Trying hard"** rendered in `VO_5`
   `[G]`. If it didn't, re-roll that unit rather than faking the gap in the edit.
3. Listen to `BackgroundMusic_V2.wav`; note whether the 0:28–0:41 breakdown rendered (§6).
4. Copy the stills into edit order under neutral names so the old/new numbering can't cause a
   mis-cut — see the command in the handoff notes.

**Edit:**
5. New project, 1080×1920, 30 fps.
6. Lay the seven VO clips at the **numeric starts in §1**. Don't drag.
7. Normalize the seven to each other, then treat as one track.
8. Lay the sixteen stills at the **numeric in/out points in §2**.
9. Apply §2's motion column. Build cut 1's push-in, then mirror its values for cut 16 so the inverse
   is exact. Concentrate push-ins on early shots for a premium feel `[C] (One Person Business,
   eVePkmCQV5c)`.
10. Build cut 14's rack-focus substitute.
11. **Apply the §4 grade, per shot.** This is the step that recovers the register split — don't skip
    it or the Short reads as one flat look.
12. **Auto-caption, then hand-correct every word against the script** `[I]`. Style to §5.
13. Add the hook card, claim cards, STAT build, disclosure line, Payoff caption and end card on §5's
    schedule.
14. Lay the bed at 0.000, duck with volume keyframes to −21/−22 dB, apply the study-beat and Payoff
    moves per §6.
15. Normalize toward −14 LUFS by ear — no LUFS meter in the free tier — then phone-speaker check.
16. Build the cover from `thumbnail_HD.png` + amber `COUNTED`.
17. Export 1080×1920 H.264 30 fps.

**Publish sequence** `[C] (Make Money Matt, RsAKa_WN1sU; Romayroh, Wox4Jt_2t6w)`:
18. Upload **unlisted**. Let it fully process (transcription, frame analysis, guideline checks).
19. Run both §8 gates and add all metadata while it processes.
20. **Then** schedule public. Don't let it sit a day expecting an algorithmic boost — a myth `[C]
    (Nick Nimmin, 0l2g3Bujy1Y)`. Space uploads rather than batching `[C] (Make Money Matt,
    tqCMF3mI9Pg)`.
21. Read CTR/AVD against channel average at 24–48h `[C] (vidIQ, ZKsldrcO_fU)`.

Paid alternative if a step becomes the bottleneck `[T]`: Premiere Pro's Essential Sound panel
one-click-ducks to ≈−22 dB; Submagic (~$23/mo annual) for animated karaoke captions. **Don't
overspend — most AI tools are convenience luxuries, not requirements** `[C] (Romayroh, nFT1xNDprIk)`.

---

## 8. QA gate + Publish gate (run while unlisted, before scheduling)

### QA gate
- [ ] **Watched on a phone, sound off then on.** Sound-off: does the two-frame argument survive on
      visuals + text alone? `[C] (Kallaway, i7upRL4H1FM)` Sound-on: voice clear over the bed `[I]`.
- [ ] **First 2s stops the swipe — no intro, no logo, no filler** `[C] (vidIQ, DiZnbihU4NM)`.
- [ ] **Cuts 11 and 13 read as different shots** after grading (§4). New in v3.
- [ ] **Shot 2 crop applied — no legible Ellen Key likeness anywhere in the cut** `[G]`. New in v3.
- [ ] **No audible level step between the seven VO units** `[I]`.
- [ ] **No text in the bottom 20% or right 12%** — re-check on the export; captions drift `[I]`.
- [ ] **Loudness ≈ −14 LUFS, music never overpowers the VO** `[I]`.
- [ ] **No banned openers** ("in this video", "hey guys") `[C] (vidIQ, UCrC5B3Soyc; Nick Nimmin,
      2vkX1X1K3WM)`.
- [ ] **Last frame matches the first frame** — replay twice, confirm the loop reads as continuous
      `[C] (Jenny Hoyos, mhVDcqnxxaY)`.

### Publish gate
- [ ] **YouTube's altered/synthetic-content disclosure set at upload** `[T]` (verified 2026-07-23 —
      **re-verify**). ElevenLabs VO carries a SynthID watermark; undisclosed altered content risks
      demonetization/YPP rejection `[C] (Romayroh, G9LfE3k-IEI)`.
- [ ] **Disclosure line also in the description and every cross-post caption** `[B]`.
- [ ] **Made-for-kids OFF** `[C] (One Person Business, eVePkmCQV5c)`.
- [ ] **Studio "restrictions" reads NONE** `[C] (Make Money Matt, 10yFPNpnjY0; Dan the creator,
      JPTr40J3WXU)`.
- [ ] **Not a duplicate template/script** of Short A or Short B `[C] (Romayroh, KbUXzJ55eJk /
      Wox4Jt_2t6w)`.
- [x] **Music licence settled** — ElevenLabs-generated, channel-owned.
- [ ] **R10 figures spot-checked** against current `rgs-r10-science-of-fun.md` `[G]`.

---

## 9. Constraints that survive to publish (carried verbatim `[G]`)

1. **Ellen Key is paraphrase-caution — never an on-screen quote/direct-attribution card.**
   Paraphrase in voiceover only; attribute "the reformer Ellen Key, 1900," spoken. Attribute the
   "work for work's sake" line as **Key relaying Ruskin**, not as Key's own words. Keep the
   passage's **corporal-punishment context out of the Short entirely.**
2. **R10 research phrasing:** keep the two tiers straight (81 determinants → 11 factors; winning is
   not one of the 11 and sits *roughly* 40th of the 81); name the study on-screen and in voiceover;
   scope is youth soccer players, coaches and parents — don't generalize; association, never
   causation. Ship "effort ranked first; winning wasn't in the top tier," never "kids don't care
   about winning."
3. **Frame guardrail.** The reframe resolves on the child's *present worth* and must **never** be
   re-justified with an outcome. Resolving on an outcome reinstates the exact theory of value the
   Short sets down, and the argument then reads as consolation for losing. The Key backbone is what
   keeps it from reading as consolation; do not cut it to save time.
4. **Villain placement:** the villain is the theory of value / the system — never the parent. End on
   relief and agency, not alarm.
5. Cited figures are as of the **2026-07-18** corpus edition — spot-check before ship.

**Assembly-stage consequences:** no quotation-mark styling near the Ellen Key lower-third, and the
face crop of §0.2 (constraint 1); the STAT build must show both tiers, never collapse them
(constraint 2); no end-card copy promising a result (constraint 3); no accusatory typography or SFX
on "You were told to ease off so he'd win" (constraint 4).

---

## 10. Downstream

This plan plus the exported Short is the direct input to **`social-repurpose`**, which produces the
YouTube title/description/hashtags and cross-platform captions. It inherits the disclosure line, the
five constraints in §9, the comment-bait question, and the Short B pointer.
