---
version: 1
---
# Edit Plan — "NFL Stat Kills the 'Specialize Early' Advice"

Inputs consumed: `2026-07-25-let-kids-play-act-specialization-script.md`,
`2026-07-25-let-kids-play-act-specialization-voiceover-brief.md`,
`2026-07-25-let-kids-play-act-specialization-visual-prompts.md`. Asset ID prefix: `SPEC01`
(folder `/shorts/SPEC01_let-kids-play-act-specialization/`), per the naming convention in
`references/tool-stack.md`.

## Shot-by-shot pacing

`[I]` note, per this skill's own convention: the ~3s change-visual cadence and the hook/spike
AI-video-budget rule are corpus principles (both `[C]`, see below); the specific sub-cut counts
and cut points below are this skill's application of those principles to this script, not
separate corpus findings.

| # | Beat | Dur | Visual + cut note | On-screen text | Asset source |
|---|---|---|---|---|---|
| 1 | Hook | 0–3s | Still #1 (split composition), slow push-in ~5% `[C] (vidIQ, DiZnbihU4NM)` | Hook card "LONGER, SAFER NFL CAREERS" full 0–3s `[I]` | SPEC01_img01_hook |
| 2 | Setup | 3–8s | Still #2 (backyard sprinkler play); cut/zoom variation at ~3s mark inside this beat to respect the ~3s rule `[C] (Make Money Matt, HopTPCLbiiM)` | Date-stamp card "Rousseau, 1762" (paraphrase label only — see Constraints below) | SPEC01_img02_setup |
| 3a | Build main | 8–11.5s | Still #3 (garage gear-peg wall), static hold | (none — karaoke captions only) | SPEC01_img03_build |
| 3b | Build main (cont.) | 11.5–15s | Still #3, keyframe zoom-in ~15–20% continuation of the same still `[C] (vidIQ, DiZnbihU4NM)` — satisfies the ~3s rule without a second generation | (none — karaoke captions only) | SPEC01_img03_build (reused, zoomed) |
| 4a | Re-hook | 15–18.5s | Still #4 (trainer taping ankle), static hold | Re-hook card "No evidence it's needed" at ~15s `[C] (Nate Black, c6X-Ywy3yVU)` | SPEC01_img04_rehook |
| 4b | Re-hook (cont.) | 18.5–22s | Still #4, keyframe zoom-in continuation | Motion-text "+ injury & burnout risk" (spoken claim rendered on-screen `[C] (vidIQ, i5bZ-Be9cAQ)`) | SPEC01_img04_rehook (reused, zoomed) |
| 5a | Re-hook (cont.) | 22–25s | Still #5 (athlete alone on bench), static hold | (none) | SPEC01_img05_rehook |
| 5b | Re-hook (cont.) | 25–28s | Still #5, keyframe zoom-in continuation | (none) | SPEC01_img05_rehook (reused, zoomed) |
| 6a | Payoff | 28–30.5s | Still #6 (diverging trail, wide), static hold | (none) | SPEC01_img06_payoff |
| 6b | Payoff (cont.) | 30.5–33s | Still #6, keyframe zoom-in continuation | (none) | SPEC01_img06_payoff (reused, zoomed) |
| 7a | Payoff (cont.) | 33–35.5s | Still #7 (signpost close-up), static hold | Motion-graphic stat card "Junior success ≠ world-class success" (spoken statistic rendered on-screen `[C] (vidIQ, i5bZ-Be9cAQ)`) | SPEC01_img07_payoff |
| 7b | Payoff (cont.) | 35.5–38s | Still #7, keyframe zoom-in continuation | (none) | SPEC01_img07_payoff (reused, zoomed) |
| 8 | Loop/CTA | 38–45s | Reused Still #1, composited with the single-uniform side now visibly smaller/isolated, matching shot 1 for the loop `[C] (Jenny Hoyos, mhVDcqnxxaY)` | Mirrored card "Still the shortcut?" | SPEC01_img01_hook (reused, composited) |

Total 45s, 13 shots — within the ~12–14 shot range the ~3s cadence rule implies for a 40–45s
Short `[C] (Make Money Matt, HopTPCLbiiM)`.

**AI-video budget** `[C] (Make Money Matt, gkaxBe8BGLQ)`: shot 1 (Hook) and shot 6 (the Payoff's
wide diverging-trail shot, the visual "reveal" beat) are the two candidates for spending on a
higher fast-generation tier if budget allows; shots 2–5 and 7 run on standard/cheap generation.
No beat in this Short uses paid image-to-video (the visual-prompts sheet already determined no
beat needs a real i2v clip — every "motion" here is a still with `--motion low` or an in-edit
keyframe zoom, not an externally-rendered clip).

## Caption/overlay treatment

Per `references/caption-overlay-system.md`'s fill-in spec — **full-duration karaoke captions**
chosen (the Shorts-specialist default), not the audit's front-loaded-only alternative, since this
is a 45s Short squarely in the Shorts-specialist band the playbook's default is built from; the
audit's *size/restraint* discipline is still pulled in (small, unobtrusive caption typography,
never redundant with hook-card text). Flagging this as an open call, not a settled rule, per the
skill's own instruction — reconsider front-loaded-only captions if this channel's exemplars lean
closer to longer-form faceless-core style than Shorts-specialist style.

```
Font:            Montserrat ExtraBold (bold sans)
Cap size:        captions 70px | hook cards 100px
Fill / stroke:   white fill / black stroke 3px
Highlight color: #FFD24A (active-word karaoke)
Position:        captions y=58% (safe band 45-65%) | hook card y=42%
Safe zones off:  top 12%, bottom 20%, right 12%
Words per card:  captions 1-3 | static line ≤5 words
Animation:       pop-in, push-in ~5% at open (shot 1), keyframe zoom 15-20% on all reused-still sub-cuts
```

Hook card ("LONGER, SAFER NFL CAREERS") on screen the full 0–3s. Re-hook card at ~15s ("No
evidence it's needed"). No on-screen text at any point renders Rousseau as a direct quote — see
Constraints below.

## Aspect / format

1080×1920, 9:16 vertical `[I]`. Runtime 45s sits at the top edge of the templates' 30–45s target
band — this is a standard length, not an unusual one, so no eligibility flag is needed beyond
the corpus's general gap note: verify current Shorts length-eligibility limits on YouTube's own
help pages before locking any future cut that runs materially longer than this.

## Loudness

VO peaks −3 to −6 dB; music bed ducked to ≈−21 to −22 dB under the voice (the corpus's
practitioner number, matching the voiceover brief's own guidance) `[C] (Roberto Blake,
iaTavrWIGDM)` `(Romayroh, Wox4Jt_2t6w)`; target −14 LUFS overall; check the final mix on phone
speakers, not headphones, before scheduling.

## Tool-stack steps

**$0 path:** Import the `SPEC01` assets into CapCut in shot-list order → auto-caption against
`SPEC01_vo_full.wav`, hand-correct against the script → apply the push-in on shot 1 and the
keyframe zoom-ins on every "(cont.)" sub-cut listed above → add the hook/re-hook/payoff text
cards per the caption spec → manually duck the music bed under the VO by ear (~−22 dB target,
no LUFS meter in the free tier — approximate and check by ear/phone) → export 1080×1920 →
verify on a phone (sound off, then on) → upload unlisted in YouTube Studio, let it fully
process, add all metadata, then schedule public `[C] (Make Money Matt, RsAKa_WN1sU)`.

**Paid path:** Assemble in Premiere Pro (Essential Sound panel auto-ducks to ≈−22 dB, Remix
tool matches any music-length adjustment without pitch-shifting) → send the cut to Submagic for
animated karaoke captions + filler-word removal, re-import → final loudness check with a LUFS
meter to −14 → export → upload unlisted, process, add metadata, schedule public via YouTube
Studio, track post-publish CTR/AVD in vidIQ.

## QA gate (run before flipping to scheduled)

- [ ] Watched on a phone, sound off then on — muted pass confirms every card/caption above
      carries the beat's meaning alone; sound-on pass confirms the mix `[C] (Kallaway,
      i7upRL4H1FM)` `[I]`.
- [ ] First 2s stops the swipe — no intro/logo/filler; confirm shot 1's push-in and hook card
      render as planned, no banned opener drifted in during the VO take `[C] (vidIQ,
      UCrC5B3Soyc)`.
- [ ] No text in bottom 20% / right 12% UI zones — confirm against the actual export, since
      captions can drift after final render/crop `[I]`.
- [ ] Loudness ~−14 LUFS, voice clear over the bed — confirm on the final mixed export, not just
      this plan `[I]`.
- [ ] No banned openers ("in this video", "hey guys") — the script has none; verify the VO take
      used didn't drift back toward one `[C] (vidIQ, UCrC5B3Soyc; Nick Nimmin, 2vkX1X1K3WM)`.

## Publish gate

- [ ] AI disclosure set (altered content) — required unless the voice used is a clone of the
      creator's own; ElevenLabs' SynthID watermark makes this checkable either way `[C]
      (Romayroh, G9LfE3k-IEI)`.
- [ ] Made-for-kids OFF `[C] (One Person Business, eVePkmCQV5c)`.
- [ ] Studio "restrictions" reads NONE `[C] (Make Money Matt, 10yFPNpnjY0; Dan the creator,
      JPTr40J3WXU)`.
- [ ] Not a duplicate template/script of a recent Short — this is a distinct angle/pairing from
      the same-day `let-kids-play-act-vulture-investors` Short (different thinker, different
      research code, different premise); confirm no other RGS Short already shares this exact
      hook/premise before scheduling `[C] (Romayroh, KbUXzJ55eJk / Wox4Jt_2t6w)`.
- [ ] Music rights settled (Creator Music / royalty-free / licensed) before final render, not
      after `[C] (Roberto Blake, SJsGBKGy4Do)`.

## Constraints that survive to publish (carried forward verbatim from the script's Delivery notes)

Paraphrase-caution (Rousseau) — never render as an on-screen quote card, voiceover paraphrase
only; this plan's Setup card is a plain date/name label ("Rousseau, 1762"), not a quote, so it
complies. Frame R2's specialization findings as association/balance-of-evidence, not settled
causal science. Name the early-peak-sport exception (gymnastics, figure skating, diving) if any
specific sport is named — moot here since the only sport named (NFL/football) isn't in that
exception class, per the script's own delivery-notes check. R2's edition is dated 2026-07-18 —
spot-check the source file for a refresh if this Short ships well after that date. No sponsor
names, no party references, no "Congress"/"Senate" framing — moot, since the bill was omitted
from the script entirely.

## Downstream

This edit plan (plus the produced/exported Short) feeds `social-repurpose` next, which turns the
finished Short and its script/packaging into multi-surface post copy (YouTube title/description/
hashtags plus TikTok/Instagram/X/Bluesky caption variants).
