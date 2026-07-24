# Assembly tool stack — $0 build and paid build

All pricing/product facts below are `[T]`, web-verified **2026-07-23** — re-verify before relying on them; AI-tool pricing moves monthly. Source: `docs/headless-shorts-production-playbook.md` §3. This file covers only the **assembly-relevant** functions (captions, editing, loudness/export). This skill consumes the finished still and video-clip assets — plus their generation prompts, kept for reference/regeneration — from `visual-prompts`; it does not decide which image/video-gen tool to use or author the generation prompts (Kling/Seedance/Midjourney/etc. prompt authoring, including start/end-frame keyframing and motion notes, is `visual-prompts`'s job). Ideation/TTS tool choices likewise belong to the upstream skills, not here.

## Captions / text-overlay

- **Primary ($0): CapCut** `[T]` — best free editor + auto-captions + templates. Default for a $0 start.
- **Alt (best animated captions): Submagic** `[T]` — Pro ~$23/mo annual; filler-word removal; Magic Clips repurposing.
- **Alt (watermark-free cheap): Captions.ai** `[T]` — Pro ~$9.99/mo.

## Editing / assembly

- **Primary: CapCut** `[T]` — free, mobile + desktop, the Shorts default.
- **Alt: Descript** `[T]` — text-based editing + filler removal (edit audio/video by editing the transcript).
- **Premiere Pro** `[T]` — the pro tier, for the Essential Sound panel's one-click ducking (see `loudness-and-mix.md`).

## Scheduling & analytics (last steps after export)

- **Native YouTube Studio scheduling** `[T]`. Don't upload and let a video "sit" a day expecting an algorithmic boost — that's a myth `[C] (Nick Nimmin, 0l2g3Bujy1Y)`.
- **Publish sequence: upload unlisted first, let it fully process/index (transcription, frame analysis, guideline checks), add all metadata, then schedule public** — this earns trust before release rather than exposing an unprocessed video `[C] (Make Money Matt, RsAKa_WN1sU; Romayroh, Wox4Jt_2t6w — the latter also names unlisted upload as the default)`. If posting a batch, space the uploads out rather than dumping them all on one day, so the pacing doesn't read as spam-bot behavior `[C] (Make Money Matt, tqCMF3mI9Pg)`.
- **YouTube Studio (Advanced mode) + vidIQ** `[T]` for the post-publish read: check the first 24–48h of CTR/AVD against the channel average, then double down on what beats it `[C] (vidIQ, ZKsldrcO_fU)`.

## QA gate + Publish gate (run during upload/metadata, before scheduling)

These two gates are the corpus's own pre-publish checklist (Template 6) and end-to-end SOP steps 10–11, in `docs/headless-shorts-production-playbook.md`. Work through both gates while the video is uploaded-unlisted and processing (per the publish sequence above), before flipping it to scheduled/public.

### QA gate
- [ ] **Watched on a phone, sound off then on.** Sound-off pass: this is the muted-viewer rule already in `pacing-and-editing.md` — optimize for the ~80–85% who watch muted `[C] (Kallaway, i7upRL4H1FM)`. Sound-on pass: the phone-speaker mix check already in `loudness-and-mix.md` `[I]`. This item confirms both on the final render, not just the plan.
- [ ] **First 2s stops the swipe — no intro/logo/filler.** Already the Hook-beat rule in `pacing-and-editing.md` `[C] (vidIQ, DiZnbihU4NM)`; this is the final render check, not a new rule.
- [ ] **No text in bottom 20% / right 12% UI zones.** Already the safe-zone map in `caption-overlay-system.md` `[I]`; confirm against the exported video, since captions can drift after final render/crop.
- [ ] **Loudness ~-14 LUFS, voice clear over the bed.** Already the target in `loudness-and-mix.md` `[I]`; confirm on the final mixed export.
- [ ] **No banned openers** ("in this video", "hey guys") `[C] (vidIQ, UCrC5B3Soyc; Nick Nimmin, 2vkX1X1K3WM)` — carried from the script; verify the VO take used didn't drift back toward one.

### Publish gate
- [ ] **AI disclosure set (altered content).** ElevenLabs VO embeds a SynthID watermark — disclose altered content at upload or risk demonetization/YPP rejection `[C] (Romayroh, G9LfE3k-IEI)`.
- [ ] **Made-for-kids OFF** `[C] (One Person Business, eVePkmCQV5c)`.
- [ ] **Studio "restrictions" reads NONE** `[C] (Make Money Matt, 10yFPNpnjY0; Dan the creator, JPTr40J3WXU)`.
- [ ] **Not a duplicate template/script of a recent Short.** One of the corpus's two stated survival invariants for a headless channel — never reuse identical title/script templates or repost identical content across videos or channels `[C] (Romayroh, KbUXzJ55eJk / Wox4Jt_2t6w)`.

## $0 assembly stack

> **Captions + edit:** CapCut (auto-caption, hand-correct, keyframe pushes/scale, music ducking manually via CapCut's audio keyframes). **Loudness:** CapCut's normalize/volume tools toward ~−14 LUFS by ear + phone-speaker check (no LUFS meter in the free tier — approximate). **Schedule:** YouTube Studio native.
> Cost: **$0/mo.** Trade-off: manual ducking (no one-click auto-duck), no built-in LUFS meter, more iteration by ear.

## Paid assembly stack (~$23–pro tier, additive to the ~$65–90/mo full paid stack)

> **Captions:** Submagic ($23/mo annual) for animated karaoke captions + filler-word removal. **Edit:** Descript (transcript-based edit) or Premiere Pro (Essential Sound panel one-click ducking to −22 dB, Remix tool for music-length matching without pitch shift). **Loudness:** Premiere's Essential Sound / a LUFS meter plugin for an exact −14 LUFS target. **Schedule/analytics:** YouTube Studio + vidIQ.
> Reality check from the corpus: **don't overspend on AI tools — most are convenience luxuries, not requirements** `[C] (Romayroh, nFT1xNDprIk)`. Start at $0, upgrade only the bottleneck step. `[I]` The specific claim that captions are usually that bottleneck (manual ducking in CapCut being a more tedious gap than the free caption tool) is this skill's judgment, not a corpus finding — assess per-channel rather than assuming it.

## Asset naming carried into the edit (so the edit plan can reference sources)

```
/shorts/
  /S042_topic-slug/
    script.md
    shotlist.md
    /assets/
      S042_img01_hook.png
      S042_vid02_build.mp4
      S042_broll03_stock-pexels.mp4
      S042_vo_full.wav
      S042_music.mp3
    S042_cover.png
    S042_final_1080x1920.mp4
    S042_metrics.md
```
Convention: `S<###>_<type><##>_<beat>.<ext>`. Type ∈ {img, vid, broll, vo, music, sfx}. One folder per Short `[I]` (`docs/headless-shorts-production-playbook.md` §6).
