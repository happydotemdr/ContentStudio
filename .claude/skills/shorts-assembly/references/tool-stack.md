# Assembly tool stack — $0 build and paid build

All pricing/product facts below are `[T]`, web-verified **2026-07-23** — re-verify before relying on them; AI-tool pricing moves monthly. Source: `docs/headless-shorts-production-playbook.md` §3. This file covers only the **assembly-relevant** functions (captions, editing, loudness/export); ideation/TTS/image/video-gen tool choices belong to the upstream skills, not here.

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
- **YouTube Studio (Advanced mode) + vidIQ** `[T]` for the post-publish read: check the first 24–48h of CTR/AVD against the channel average, then double down on what beats it `[C] (vidIQ, ZKsldrcO_fU)`.

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
