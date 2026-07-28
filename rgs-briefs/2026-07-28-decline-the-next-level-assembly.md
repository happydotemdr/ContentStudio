---
date: 2026-07-28
kind: assembly
run: rgs-debut-20260728-055448
slug: decline-the-next-level
stage: 04-assembly
script: rgs-briefs/2026-07-28-decline-the-next-level-script.md
voiceover_brief: rgs-briefs/2026-07-28-decline-the-next-level-voiceover-brief.md
visual_prompts: rgs-briefs/2026-07-28-decline-the-next-level-visual-prompts.md
visual_system: rgs-briefs/2026-07-28-rgs-debut-visual-system.md
status: complete
---

=== ASSEMBLY / EDIT PLAN — decline-the-next-level (Short A) ===

Produced by `shorts-assembly` from the three converged upstream artifacts: the shot-ready
script (Task 10), the voiceover brief (Task 11), and the visual prompt sheet (Task 12), bound
by the locked shared visual system (Task 8). **No assets are generated and nothing is rendered
by this document** — it is the plan an editor follows once the ElevenLabs audio, the Midjourney
stills, and the two Kling i2v clips actually exist. All figures below are the arithmetic
applied to those three artifacts' own numbers, not new creative decisions, except where a
plan-level judgment call is explicitly flagged as this skill's own.

## Marker legend (an unmarked normative line below is a bug)

- **`[C]`** — the 420-video ContentStudio corpus, cited `(Channel, video_id)`, carried through
  from `shorts-assembly/references/*.md`.
- **`[I]`** — general craft judgment or this skill's own operational decision, traceable to none
  of the below.
- **`[T]`** — tool/policy fact, dated 2026-07-23 in the assembly references (Midjourney/visual
  facts inherited from upstream carry their own 2026-07-26 date where noted). Re-verify before
  relying on it.
- **`[T-unverified]`** — asserted by a supplied source, not confirmed against live vendor docs.
  Starting hypothesis only, flagged wherever used.
- **`[B]`** — RaisingGoodSports Brand Definition, carried from the script/voiceover
  brief/visual system, never re-derived here.

---

## 1. Shot-by-shot pacing and cut cadence

Aspect ratio **1080×1920, 9:16** `[I]` (`pacing-and-editing.md`, `worked-example.md`). Beat
boundaries are inherited unchanged from the script; this skill adds only the sub-cut points
inside each beat, following the corpus's ~3-second change-the-visual rule — never hold one
image/clip too long, a static frame is "the visual equivalent of dead air" `[C] (Make Money
Matt, HopTPCLbiiM; vidIQ, DiZnbihU4NM)`. Total shots below: **11 distinct visual cuts** across
45 seconds.

| # | Beat | Range | Dur | Still/clip | Cut note | On-screen text (safe zone) |
|---|---|---|---|---|---|---|
| 1 | Hook | 0–3s | 3s | **A-01** (Kling i2v — hand/forearm sliding form, already in motion) | One continuous shot, no internal cut — the motion itself is the cadence | `IT WON'T SET HIM BACK` — `WON'T` in `#F2A541`, rest `#F7F3E8`, full 0–3s `[B]` |
| 2 | Setup | 3–8s | 5s | **A-02** (still — tiered paperwork stack) | Held with edit-added push-in (§5) for the full 5s — one sub-cut only, within the ~3s rule's spirit since a single continuous move is legible, not a static hold `[C] (Make Money Matt, HopTPCLbiiM)` | `DEWEY SAW IT COMING · 1916` `[C] (Kallaway, 6G1wIdxWF5w)` |
| 3 | Build — proof | 8–11.5s | 3.5s | **A-03** (soccer cleats/shin guards) | Cut 1 of 3 inside this beat, ~3.5s cadence | Citation plate persists (see §4) |
| 4 | Build — proof | 11.5–15s | 3.5s | **A-04** (swim goggles/cap added) | Cut 2 of 3 | Citation plate persists |
| 5 | Build — proof | 15–18s | 3s | **A-05** (three-sport gear wide) | Cut 3 of 3 | Citation plate persists |
| 6 | Re-hook | 18–21s | 3s | **A-06** (letterhead/fee schedule, gear blurred at edge) | One shot, no internal cut — the subject-change is carried by the still's own baked-in focus pull, per `visual-prompts`'s own note | `2ND MISTAKE →` (re-hook card) |
| 7 | Build — Dewey (climax) | 21–28s | 7s | **A-07** (Kling i2v — push-in onto blank signature line) | One continuous shot, no internal cut — this is Short A's climax beat and the corpus's own rule against chasing cuts for their own sake applies directly: retention comes from the demonstration, not from adding a jump cut `[C] (vidIQ, DiZnbihU4NM)` | **Two sequential quote-card reveals** — see §6, binding split |
| 8 | Payoff | 28–31.5s | 3.5s | **A-08** (paperwork ladder, bottom rungs) | Cut 1 of 3 | AI disclosure line appears here (see §8) |
| 9 | Payoff | 31.5–35s | 3.5s | **A-09** (ladder receding, mid rungs softening) | Cut 2 of 3 | — |
| 10 | Payoff | 35–38s | 3s | **A-10** (ladder's top past frame edge) | Cut 3 of 3 | `YOU'RE ALLOWED TO DECLINE IT` |
| 11 | Loop/CTA | 38–45s | 7s | **REUSE A-01** (the Hook's exact i2v clip, held/looped) | One continuous shot — closes the visual loop exactly as the VO line mirrors the Hook `[C] (Jenny Hoyos, mhVDcqnxxaY — medium confidence)` | `It won't set him back.` (mirrored card) |

### Timing reconciliation

| Beat | Range | Duration | Shots | Sum check |
|---|---|---|---|---|
| Hook | 0–3s | 3s | 1 | 3s |
| Setup | 3–8s | 5s | 1 | 5s |
| Build — proof | 8–18s | 10s | 3 (3.5+3.5+3) | 10s |
| Re-hook | 18–21s | 3s | 1 | 3s |
| Build — Dewey | 21–28s | 7s | 1 | 7s |
| Payoff | 28–38s | 10s | 3 (3.5+3.5+3) | 10s |
| Loop/CTA | 38–45s | 7s | 1 | 7s |
| **Total** | **0–45s** | **45s** | **11 cuts** | **3+5+10+3+7+10+7 = 45** |

**Total runtime: 45 seconds, confirmed summing.** Every beat range is contiguous and
non-overlapping (0–3, 3–8, 8–18, 18–21, 21–28, 28–38, 38–45), matching the script's own
reconciliation table exactly — this stage does not move a single beat boundary, only adds
sub-cuts inside beats that already carry more than one still. 11 distinct visual cuts total.
The corpus's gap flag on Shorts duration-eligibility limits (`pacing-and-editing.md`) applies
unchanged: verify current YouTube Shorts length eligibility independently before locking this
runtime; nothing in the corpus addresses it.

### AI-video budget discipline, confirmed at the edit stage

Only A-01 (Hook) and A-07 (Dewey climax) are motion assets; the other nine stills get their
movement from the edit (§5) rather than a second round of paid generation — this matches the
corpus's rule to spend premium AI-video budget only on the hook and occasional cutaway spikes,
generating the bulk cheaply `[C] (Make Money Matt, gkaxBe8BGLQ)`, as already decided upstream
by `visual-prompts`'s motion-rationing table. Not reopened here.

---

## 2. Motion assignment for the nine stills (edit-added movement)

Per the visual system's own instruction: "every other beat is a still with movement added in
the edit — push-in, parallax, whip cut — specified in the assembly plan" `[B]`. Nine stills
need a named move; here they are, one row each, no still left unassigned:

| Still | Beat/placement | Duration on screen | Move | Detail |
|---|---|---|---|---|
| A-02 | Setup, 3–8s | 5s | **Push-in, ~15–20% scale** | Slow keyframe scale-up over the full 5s, biased toward the early-scene "premium feel" treatment the corpus reserves for early beats `[C] (One Person Business, eVePkmCQV5c)`, operationalizing the same push-in note vidIQ gives for signaling "something's coming" `[C] (vidIQ, DiZnbihU4NM)`. |
| A-03 | Build-proof cut 1, 8–11.5s | 3.5s | **Whip cut in, static hold** | Fast cut transition on entry (matches the ~3s cadence rule's "change the visual" mandate `[C] (Make Money Matt, HopTPCLbiiM)`), then a static hold under the citation plate so the plate's own 10s persistence (§4) isn't undercut by simultaneous camera motion. |
| A-04 | Build-proof cut 2, 11.5–15s | 3.5s | **Whip cut in, static hold** | Same treatment as A-03 — three near-identical gear stills read as an escalating list better with a consistent cut rhythm than with three different camera moves competing with the held citation plate. `[I]` |
| A-05 | Build-proof cut 3, 15–18s | 3s | **Slight parallax (background drift only)** | A small parallax separation between the gear layer and the teal-ink ground as the sub-beat closes, giving the three-sport wide shot slightly more life heading into the re-hook cut, without disturbing the citation plate's legibility. |
| A-06 | Re-hook, 18–21s | 3s | **Minimal push-in only, ~5%** | The still's own composition already carries the focus-pull idea (gear blurred at the edge, letterhead sharp) per `visual-prompts`'s own note that "the idea of a subject change is carried by composition, not by an actual camera move" — a heavier edit move here would fight the still's baked-in read rather than support it. `[I]` |
| A-08 | Payoff cut 1, 28–31.5s | 3.5s | **Push-in, ~10%, low-angle emphasis** | Slow push-in reinforcing the low-angle "looking up at a ladder" composition already in the still. |
| A-09 | Payoff cut 2, 31.5–35s | 3.5s | **Continued push-in + slight upward parallax** | Carries the push-in from A-08 forward and adds a touch of vertical drift so the "receding" idea reads as motion, not just as three similar stills in a row. `[I]` |
| A-10 | Payoff cut 3, 35–38s | 3s | **Push-in continuing into negative space, whip cut out at 38s** | The push-in resolves into open negative space above the ladder ("no top visible"), then a whip cut carries into the Payoff's closing card and the Loop/CTA beat. |
| A-11 | Cover/thumbnail only | n/a — not in the video timeline | **No motion — static thumbnail** | A-11 is the dedicated cover/thumbnail still (rule-of-thirds, text-zone-left composition), never a shot inside the assembled video; flagged explicitly here rather than silently omitted, per the visual prompt sheet's own note that the cover diverges from the Hook's frame on purpose. `[I]` |

That accounts for all nine non-motion stills in the pool (A-02 through A-11 minus A-07), each
with a named move and an explicit duration.

---

## 3. Caption/overlay treatment

**Position:** captions and cards sit inside the middle **~60% vertical safe zone**, cleared of
the bottom 25% and the right 15% `[T-unverified]` (working rule, no official YouTube safe-zone
pixel spec exists; third-party numbers conflict — verify on a real phone before this template
locks, per both the visual system's and the corpus's own caveats).

**Reveal cadence — the locked call, with the corpus tension stated rather than silently
resolved.** The shared visual system locks **one burned-in caption per script beat, revealed at
beat boundaries, not word-by-word karaoke** `[B]`. This is a genuine departure from this
skill's own default: the corpus itself splits on caption density —

- **Playbook default `[I]`:** full-duration word-by-word karaoke, 1–3 words per chunk, active
  word tinted.
- **Audit counter-finding `[C]`:** keep captions small and mostly at the start; front-load-only
  for the first ~5–10s, rely on auto-subtitles for the body `[C] (One Person Business,
  6s2T2NlWDhQ; Make Money Matt, LlIkMWX50aQ)`.

For this Short, **the brand's fixed system wins over both corpus defaults** — beat-boundary
burned-in cards, not karaoke — because the visual system was locked upstream of this stage and
governs both debut Shorts identically `[B]`; overriding it per-Short would break the "change
the words, not the system" consistency rule the brand treats as the actual asset. Flagged as an
explicit judgment call, not a silent pick, per this skill's own instruction to always surface
the tension.

**Style:** one locked bold sans-serif (per the visual system, font family TBD at composite
time — not fixed by this plan); body text `#F7F3E8` on the `#0E3B43` ground wherever a plate is
used; the single accent word of any card in `#F2A541` ALL-CAPS `[B]`. Stroke/box behind any
text placed over a busy background, per the corpus's general readability rule `[I]`.

**Per-beat card copy (all inside the safe zone):**

| Beat | Card text | On screen |
|---|---|---|
| Hook | `IT WON'T SET HIM BACK` (`WON'T` amber) | 0–3s, full duration |
| Setup | `DEWEY SAW IT COMING · 1916` | 3–8s |
| Build — proof | Citation plate (§4) | 8–18s, held full 10s |
| Re-hook | `2ND MISTAKE →` | 18–21s |
| Build — Dewey | Two sequential quote-card reveals (§6) | 21–28s |
| Payoff | AI disclosure line (§8) + `YOU'RE ALLOWED TO DECLINE IT` (staggered, not simultaneous — disclosure at beat-open, decline line at ~33s once the ladder framing has read) `[I]` | 28–38s |
| Loop/CTA | `It won't set him back.` (mirrored, not ALL-CAPS — quieter register matching the warmer VO delivery `[I]`) | 38–45s |

One idea per card — no card stacks two thoughts `[I]`.

---

## 4. The R9 attribution plate (research claim — on screen and in voiceover)

Binding requirement carried from the script/voiceover brief: the research claim carries its
named source **on screen and in voiceover**, never as an unattributed claim `[B]`.

- **Voiceover, 8–18s:** "A 2009 international position stand — Côté, Lidor and Hackfort —
  reports that kids who sample many sports still tend to reach elite performance. Late
  focusers tend to catch up."
- **On-screen citation plate, 8–18s, held the full 10 seconds:**
  `Côté, Lidor & Hackfort (2009) · ISSP Position Stand · Int. J. Sport & Exercise Psychology
  7(1):7–17`
- **Placement:** inside the middle-60% safe zone, positioned over the top margin the three
  Build-proof stills (A-03/04/05) were composed with an empty reservation for — the visual
  prompts explicitly left "an empty margin left above the gear reserved for an overlay plate"
  on all three, so the plate does not compete with the gear-cut cadence beneath it.
- **Persistence across cuts:** the plate does **not** re-cut with the three gear stills beneath
  it — it holds fixed for the full 10-second sub-beat while A-03/A-04/A-05 cut underneath at
  ~3.5s intervals, per the visual-prompts sheet's own instruction that the plate is "held the
  full 10 seconds."
- **Never the grey-literature PDF citation** — the Position Stand only, per the research file's
  own quality rating and the script's binding constraint.

---

## 5. The split Dewey quote card — binding requirement, implemented

Inherited as a **binding requirement, not a suggestion**, from `visual-prompts`: the 22-word
verbatim Dewey quote card does not render as a single static card across the full 7-second
Build-Dewey beat — it is split into **two sequential reveals** over A-07's single background
(and its i2v push-in clip), because a single 22-word card at ~3.1 words/second of reading speed
risks the exact "dead air" failure the pacing rules warn about, applied to text density rather
than image staleness `[C] (vidIQ, DiZnbihU4NM, adapted)`.

| Reveal | Range | Dur | On-screen text | Words |
|---|---|---|---|---|
| Reveal 1 | 21–24.5s | 3.5s | "it becomes constrained labor when the consequences are outside of the activity as an end" | 12 |
| Reveal 2 | 24.5–28s | 3.5s | "to which activity is merely a means." — John Dewey, *Democracy and Education*, 1916 | 10 + attribution |

**Implementation notes for the editor:**
- Both halves render over the **same** A-07 background/clip — no second still, no second
  Midjourney generation, exactly as `visual-prompts` specified.
- Cut from Reveal 1 to Reveal 2 is a **hard card swap at 24.5s**, not a cross-fade or
  word-by-word build — this keeps it a caption-timing decision (two sub-beat reveals) rather
  than converting it into karaoke, which would break the beat-boundary reveal rule locked in §3.
- Both halves stay inside the safe zone (middle ~60% vertical, clear of bottom 25%/right 15%)
  `[B][T-unverified]`, same locked bold sans-serif, same weight.
- The attribution line ("— John Dewey, *Democracy and Education*, 1916") is part of Reveal 2,
  not a separate third card — attribution is never optional and never trails off screen after
  the quote fades, per the script's own instruction that "attribution line is part of the card,
  not optional."
- Do not silently re-merge the two reveals back into one card under editing time pressure — this
  was the specific fix for a documented readability problem; re-merging reintroduces it.

---

## 6. Aspect ratio and safe zone

- **Aspect ratio: 1080×1920, 9:16.** `[I]`
- **Safe zone (working rule):** all text inside the **middle ~60% vertically**, clear of the
  **bottom 25%** and the **right 15%**. **`[T-unverified]`** — no official YouTube safe-zone
  pixel spec exists; third-party figures openly conflict on the exact reserve (safe area
  888×1500 vs. ~900×1160; bottom reserve 300 vs. 350 vs. 450px; right 120 vs. 150px, per the
  visual system's own citation of this conflict). **Verify on a real phone before this Short's
  template locks** — this is not a resolved number, it is a working rule carried through three
  upstream stages unchanged.
- Every card/plate specified in §3–§5 above is placed inside this zone; none extend into the
  bottom 25% (handle/title/like-comment-share/Subscribe/progress-bar territory) or the right
  15% (action-rail territory) `[I]` (`caption-overlay-system.md`'s UI-collision map, applied at
  the visual system's coarser percentages rather than its own pixel table, since the visual
  system's numbers are what this Short is bound to).

---

## 7. Loudness and mix

- **Target: −14 LUFS integrated.** `[T]` (YouTube's loudness normalization target;
  `loudness-and-mix.md`, confirmed identically in the voiceover brief's Production & loudness
  section). Normalize the finished mixed export to this value; leave headroom, avoid clipping.
- **Voice peaks −3 to −6 dB.** `[I]`
- **Music ducking under voiceover: lead with −21 to −22 dB**, the range the voiceover brief
  ties directly to a retention complaint rather than a general mixing guideline `[C] (Romayroh,
  Wox4Jt_2t6w; Roberto Blake, iaTavrWIGDM)`; the wider documented band of −12 to −18 dB is
  recorded as the alternate rather than silently dropped `[T]`. **This Short leads with the
  tighter, corpus-cited −21 to −22 dB duck**, inherited unchanged from the voiceover brief.
- **Ducking behavior:** the music bed ducks automatically under every spoken line across all
  seven beats (one-click auto-duck in the paid path, manual keyframes in the $0 path — see §9);
  it does not duck uniformly to a flat level for the whole 45s — it tracks the VO's own presence,
  rising back toward its unducked level only in the brief silences between beats (the two
  `[pause]` tag locations: before "Not athletically." in the Hook, and before "It won't set him
  back." in the Loop/CTA).
- **Music arc matches tone, not just fills silence** `[C] (Kallaway, i7upRL4H1FM)` — Hook
  through the Build-Dewey climax runs on a quiet-resolve-to-gravity bed; the Payoff turns to
  warmth/relief; a single static bed that doesn't track this arc will fight the VO rather than
  support it, per the voiceover brief's own instruction.
- **SFX:** a subtle hit/whoosh on the Hook's opening motion and the Re-hook's subject-change cut
  only — not on every cut, since the corpus explicitly warns against wall-to-wall stimulation
  `[C] (vidIQ, DiZnbihU4NM)`.
- **Check the final mix on phone speakers, not headphones** — that's how it will actually be
  watched `[I]`.
- **Rights note, last checkpoint before bake-in:** confirm the music track source (YouTube
  Creator Music, a royalty-free library, or a cleared license service) before the final render —
  Creator Music can carry a revenue-share/no-monetization condition unlike a direct license
  `[C] (Roberto Blake, SJsGBKGy4Do)`. Not yet settled as of this document; flagged as an open
  pre-render action.

---

## 8. AI / synthetic-media disclosure — three concrete placements

Brand-mandated, carried forward verbatim from the script and voiceover brief as binding, not
discretionary `[B]`. This plan places all three concretely rather than leaving them abstract:

1. **YouTube upload's altered/synthetic-content disclosure box, set at publish time.** Platform
   toggle, not an in-video element — set during the metadata step of the publish sequence (§9),
   before the video is scheduled public `[T]` (YouTube inauthentic-content policy, verified
   2026-07-23 via https://support.google.com/youtube/answer/1311392 — **re-verify before
   publishing**, since this policy area moved once already in 2025).
2. **On-screen line during the Payoff beat, 28–38s**, inside the safe zone, positioned so it
   does not collide with the `YOU'RE ALLOWED TO DECLINE IT` card (staggered per §3 — disclosure
   appears at beat-open, ~28–33s; the decline card follows at ~33–38s so the two never overlap
   in the same safe-zone real estate):
   > AI-generated visuals · synthetic voiceover

   Rendering: small-set, `#F7F3E8`, **never amber** — amber is reserved for the single accent
   word elsewhere in the Short `[B]`.
3. **Video description and every cross-post caption** (TikTok/Instagram/X/Bluesky) carry the
   identical line. The description placement is this plan's responsibility to flag into the
   publish-gate checklist (§9); the actual caption copy is `social-repurpose`'s (Task 14) job to
   write — this plan does not author that copy, only confirms the line ships in it.

All three placements are unconditional regardless of voice choice — the library-voice fallback
locked in the voiceover brief does not clear a disclosure bar the brand already decided to hold
unconditionally for this Short `[B]`.

---

## 9. Tool-stack execution — $0 path and paid path

Assets consumed (from Tasks 11/12, once actually rendered — none exist yet):

```
/shorts/
  /rgs-debut_decline-the-next-level/
    script.md
    voiceover-brief.md
    visual-prompts.md
    assembly.md                              <- this document
    /assets/
      A-01_hook-loop_i2v.mp4                 (Kling, reused at Loop/CTA)
      A-02_setup.png
      A-03_build-proof-1.png
      A-04_build-proof-2.png
      A-05_build-proof-3.png
      A-06_re-hook.png
      A-07_dewey-climax_i2v.mp4              (Kling)
      A-08_payoff-1.png
      A-09_payoff-2.png
      A-10_payoff-3.png
      vo_01_hook.wav … vo_07_loop-cta.wav    (7 beat renders, per voiceover brief's sectioning)
      music_bed.mp3
    A-11_cover.png                           (thumbnail, not composited into the timeline)
    decline-the-next-level_final_1080x1920.mp4
```
Adapted from the corpus's `S<###>_<type><##>_<beat>.<ext>` convention `[I]` (`tool-stack.md`) to
this run's slug-based naming since no `S<###>` id was assigned upstream; the convention's intent
(one folder per Short, typed/beat-labeled filenames) is preserved.

### $0 path

**Captions + edit: CapCut** `[T]` — free, mobile + desktop, the Shorts default. Import all 11
assets in the shot-by-shot order from §1. Build the beat-boundary text cards manually (CapCut's
auto-caption tool is not used for body captions here, since the locked treatment is
beat-boundary cards, not word-by-word karaoke — auto-caption would need to be disabled or
heavily hand-corrected away from its default word-by-word output). Apply the push-in/parallax/
whip-cut moves from §2 via CapCut's keyframe tool on each of the nine non-motion stills. Duck
the music track manually via CapCut's audio keyframes under each VO beat, targeting the −21 to
−22 dB lead figure by ear (no LUFS meter in the free tier — approximate, then verify by ear
against the phone-speaker check). Normalize final loudness toward −14 LUFS using CapCut's
volume/normalize tool, by ear. Export 1080×1920. Verify on a phone before scheduling.
**Cost: $0/mo.** Trade-off: manual ducking, no built-in LUFS meter, hand-built caption cards
instead of an automated pass, more iteration by ear `[T]`.

**Schedule: YouTube Studio native**, following the publish sequence below.

### Paid path

**Edit: Premiere Pro** `[T]` — Essential Sound panel gives one-click auto-ducking, set to ≈−22
dB to match the lead figure directly; use the Remix tool to match music bed length to 45s
without pitch-shifting (rate-stretch alters pitch) `[C] (Roberto Blake, iaTavrWIGDM)`. Build the
beat-boundary cards as titles/graphics layers directly on the timeline (Premiere has no
auto-karaoke tool worth using here since the locked treatment isn't karaoke anyway). Apply the
§2 push-in/parallax/whip-cut moves via keyframed Transform/Position/Scale on each still.
**Loudness: Premiere's Essential Sound panel or a LUFS meter plugin** for an exact −14 LUFS
target on final export. **Captions/disclosure line QC: Submagic** `[T]` (~$23/mo annual) is
available as an alternate captioning pass if the beat-boundary cards need animated polish, but
is not required by this plan's locked treatment — flagged as optional, not part of the core
paid path, since the corpus's own reality check applies: don't overspend on AI tools that are
convenience luxuries, not requirements `[C] (Romayroh, nFT1xNDprIk)`.
**Cost: ~$0–23/mo** depending on whether the optional Submagic pass is used, additive to
whatever tier of Premiere/Creative Cloud is already held.

**Schedule/analytics: YouTube Studio + vidIQ** `[T]` for the post-publish 24–48h CTR/AVD read
against the channel average `[C] (vidIQ, ZKsldrcO_fU)`.

### Publish sequence (both paths converge here)

**Upload unlisted first, let it fully process/index (transcription, frame analysis, guideline
checks), add all metadata (title, description with the AI-disclosure line and the R9 citation
in the description text, tags, the AI/synthetic-content disclosure toggle from §8), then
schedule public** `[C] (Make Money Matt, RsAKa_WN1sU; Romayroh, Wox4Jt_2t6w)`. Do not let the
video "sit" a day post-schedule expecting an algorithmic boost — that is a documented myth
`[C] (Nick Nimmin, 0l2g3Bujy1Y)`. If this Short and Short B post as a batch, space the uploads
out rather than dumping both the same day, so pacing doesn't read as spam-bot behavior `[C]
(Make Money Matt, tqCMF3mI9Pg)`.

---

## 10. QA gate + publish gate (run before scheduling)

### QA gate
- [ ] Watched on a phone, sound off then on. Sound-off pass confirms every beat's meaning
  survives on visual + on-screen text alone `[C] (Kallaway, i7upRL4H1FM)`; sound-on confirms the
  −14 LUFS / −21–22 dB duck mix on phone speakers `[I]`.
- [ ] First 2s stops the swipe — the form is already mid-slide at frame one, no intro/logo/
  filler `[C] (vidIQ, DiZnbihU4NM)`.
- [ ] No text in the bottom 25% / right 15% safe-zone exclusions (§6) — confirm against the
  actual exported video, since captions can drift after final render/crop `[I]`.
- [ ] Loudness ~−14 LUFS confirmed on the final mixed export, voice clear over the bed `[I]`.
- [ ] No banned openers ("in this video," "hey guys") — already absent from the script; verify
  the VO take used didn't drift back toward one `[C] (vidIQ, UCrC5B3Soyc; Nick Nimmin,
  2vkX1X1K3WM)`.
- [ ] The split Dewey card (§5) renders as two distinct reveals at 21–24.5s / 24.5–28s, not one
  merged 22-word card.
- [ ] The R9 citation plate (§4) holds the full 8–18s sub-beat unbroken under the three
  underlying gear cuts.

### Publish gate
- [ ] AI/synthetic-content disclosure set at upload (§8, placement 1) — mandatory, not
  discretionary; disclose or risk demonetization/YPP rejection `[C] (Romayroh, G9LfE3k-IEI)`.
- [ ] On-screen disclosure line present during the Payoff beat (§8, placement 2).
- [ ] Description carries the disclosure line (§8, placement 3).
- [ ] Made-for-kids OFF `[C] (One Person Business, eVePkmCQV5c)`.
- [ ] Studio "restrictions" reads NONE `[C] (Make Money Matt, 10yFPNpnjY0; Dan the creator,
  JPTr40J3WXU)`.
- [ ] Not a duplicate template/script of a recent Short — confirmed distinct from Short B's
  payoff (parent's decision vs. asking the kid), per the script's own distinctness check `[C]
  (Romayroh, KbUXzJ55eJk / Wox4Jt_2t6w)`.
- [ ] Pinned comment / end card points at Short B (`nobody-asked-the-kid`) only once it is live;
  if this Short ships first, the bridge line is held, not replaced with a generic closer `[C]
  (Nick Nimmin, N42_LghZw8k)`.
- [ ] R9 edition spot-check against the current `rgs-r9-play-vs-practice.md` (edition
  `v2-2026-07-18`) completed before ship — carried forward from the script as an open
  pre-publish action, not discharged at this stage.
- [ ] Music rights source confirmed (Creator Music / royalty-free / licensed) before final bake
  (§7).

---

## Gaps flagged honestly

- **No corpus finding on current YouTube Shorts duration-eligibility limits** — this 45s runtime
  sits inside the templates' assumed 30–45s band, but the eligibility ceiling itself is outside
  the 420-video corpus and the 2026-07-23 tool sweep. Verify independently before locking.
- **The safe-zone rule (§6) is `[T-unverified]`** throughout this document — carried unchanged
  from the visual system, not independently re-verified here. Verify on a real phone before this
  Short's template is treated as final.
- **Caption-density is a genuine corpus split (§3), resolved here by brand override, not by
  corpus consensus** — presented as a judgment call, not silently picked.
- **Font family for the burned-in cards is not fixed by this plan** — the visual system reserves
  "one bold sans-serif" without naming it; pick one consistent with the brand kit at composite
  time, not per-Short. `[I]`
- **Motion move durations in §2 are this skill's own application of the corpus's push-in/
  parallax/whip-cut principles to this specific still pool, not corpus findings themselves** —
  same caveat the worked example carries for its own shot-by-shot table.

---

## Downstream

This edit plan, once the described assets exist and are assembled per §1–§9 and pass the §10
gates, is the direct input to **`social-repurpose`** (Task 14), which turns the finished Short
plus its script/packaging into multi-surface post copy — including the description and
cross-post AI-disclosure line this plan specifies in §8 but does not author.
