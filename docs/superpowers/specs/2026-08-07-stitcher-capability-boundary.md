# Stitcher capability boundary — what a render-spec can and cannot express

**Status:** as-built, verified against `stitcher/` at commit `3966844` and ffmpeg 9.0
**Established by:** the first real render — `do-less-sold-as-win-more`, 16 cuts / 54.8s,
QA PASS, promoted to `_v01_1080x1920.mp4` on 2026-08-07
**Audience:** whoever writes the next `shorts-assembly` edit plan or `shorts-styleboard`
world lock

---

## Why this document exists

`shorts-assembly` writes edit plans with no knowledge of what the renderer can do, because
until now nothing had been rendered. The do-less v3 build sheet is a good plan and a fair
test: of its seven distinct production instructions, **three could not be expressed in a
render-spec at all** and one had to be baked into an asset. None of that is a defect in
either the plan or the stitcher — it is an undocumented scope boundary, and this is the
document.

Read this before authoring an edit plan. Specifying something below costs a re-plan after
the assets are already paid for.

---

## Cannot be expressed — do not specify these

### 1. Audio compression or limiting — and this blocks raw TTS outright

There is no `acompressor`, `alimiter`, or `compand` anywhere in `stitcher/`. Stage C's only
level tools are per-stem `gain_db`, the bed's `gain_db`/`duck_db`, and a two-pass loudnorm.

This is load-bearing, not cosmetic. `verify.py` requires loudnorm to resolve **linearly**,
and linear is only possible when

```
input_tp + (target_i - input_i) <= target_tp
```

— i.e. when the mix's peak-to-loudness ratio is no greater than `target_i - target_tp`. At
−14 LUFS / −1.5 dBTP that budget is **12.5 dB**. Raw ElevenLabs stems mixed to **18.2 dB**,
so the render was correctly refused with exit 2.

Two things that look like fixes and are not, both measured rather than assumed:

- **A lower true-peak target.** loudnorm simply applies less gain; PLR is unchanged (12.9 dB
  whether the ceiling was −3 or −6 dBTP). The error message's advice — *"Lower the true-peak
  target"* — is backwards: a lower target shrinks the budget.
- **A limiter alone.** `alimiter` caps *sample* peak while loudnorm measures *true* peak, and
  inter-sample overshoot on this material was ~1.2 dB. Worse, every 1 dB of ceiling costs
  ~0.55 dB of integrated loudness, so it buys only ~0.45 dB of real headroom per dB — a
  −8 dBFS ceiling to close a 5.7 dB gap.

**What works:** compress before the assets reach the stitcher. Level-match, compress, then
limit. `scratchpad/prep_vo.py` on the do-less run took PLR from 18.2 to ~10.5 dB and stage C
resolved linear on the first try.

> **Plan for it:** an edit plan whose audio is un-mastered TTS must say so, and name the
> conditioning step. "Normalize the clips to each other" (do-less §6 step 7) is necessary but
> not sufficient — it does not reduce PLR.

### 2. Colour grading

No `curves`, `eq`, `colorbalance`, `colorchannelmixer`, `lut3d`, or `colorlevels` in the
codebase. `-colorspace/-color_primaries/-color_trc bt709` are container tags, not a grade.

The do-less §4 grade was the mechanism its "ship as rendered" decision relied on to carry the
Register A/B split after the `--sref` codes went unharvested. The v01 master is ungraded, and
cuts 11 and 13 read as near-twins exactly as §4 predicted they would.

> **Plan for it:** treat the stitcher master as a graded-elsewhere intermediate, or accept an
> ungraded cut. Do not make a grade the thing that carries a register distinction.

### 3. Authorable blur — so no rack focus, no depth ramp

`avgblur` exists in `shots.py:114`, but only inside `whip_filters`: a fixed radius gated to a
`transition_in.kind == "whip"` window of a few frames. There is no per-shot blur field and no
way to ramp one.

do-less §2 cut 14's rack-focus substitute (duplicate layer, heavy-blur the lower copy, mask
the child, ramp opacity over 3.83s) is not expressible. It was degraded to a push-in.

### 4. Per-shot crop or reframe

A `Shot` carries `source`, `source_in`, `source_out`, `motion`, `transition_in` — and nothing
else. The conform is a fixed cover-fit plus centre crop.

This one has teeth: do-less §0.2 is a `[G]` grounding constraint requiring the top ~35% of one
frame be removed to eliminate a legible likeness. With nowhere to express it, the crop had to
be **baked into the asset**. There is then no field recording that a crop was required, and
**QA cannot check it** — stage F reported PASS on a spec that would have been unpublishable
had the asset not been pre-cut.

> **Plan for it:** any framing constraint must be an asset-preparation step with its own
> verification, listed before the render. Never assume the spec will carry it.

### 5. Burned-in captions

`assemble.py` composites `overlay_pngs` only. `derive.py` writes `.srt` and `.ass` **sidecars**
from `captions[]`. Nothing burns a caption into the master.

do-less §5 specifies a full-duration karaoke track, justified by the corpus finding that
80–85% watch muted. It is not in the master.

> **Plan for it:** design copy that must be on screen goes in `overlays[]` (which does burn
> in). `captions[]` is a transcript for a downstream burn-in, and `derive.py`'s own docstring
> is explicit that the two are different things — sidecars are built from spoken lines, never
> from card copy.

### 6. Cover-only text

`Cover.overlays` is a list of ids that must resolve against `overlays[]` (`spec.py:402`), and
stage E composites the same full-canvas PNGs stage B produced for the video. **Any text on the
cover is necessarily also in the video**, at that overlay's `in`/`out`.

do-less §5 wants amber `COUNTED` on the cover in a treatment that appears nowhere in the cut.
Not expressible; the cover shipped clean.

### 7. Motion on a `clip` shot

Explicitly rejected at `spec.py:332` rather than ignored, because `clip_filters` never reads
`shot.motion` and it would render motionless. Stills only for Ken Burns.

---

## Traps — expressible, but silently wrong

### A zero-amount motion renders static, with no signal

`motion.py` computes the crop offset as `anchor * (scaled - crop)`. With `kind: "none"` or
`amount_pct: 0` the scaled and crop sizes are equal, so **a moving `anchor_start` →
`anchor_end` pair has zero room to move**. No error, no warning, no QA check.

do-less §2 asks for a "drift" on cuts 3, 5, 9 and 13 with no zoom. Authored literally, four of
sixteen cuts would have rendered dead still and nothing would have said so.

> **Author a drift as `scale_up` with a non-zero `amount_pct` plus differing anchors.**
> `push_in` and `scale_up` are the same function (`1 + amount*p`); only `pull_out` inverts it
> (`1 + amount*(1-p)`), which is what makes an exact mirror of an opening push-in possible.

### Overlay count is bounded in practice

Every overlay is a separate `-i` input to a single `filter_complex` chain
(`assemble.py:113`). Twelve is comfortable. A word-level caption track (~140 cards) is not a
realistic overlay list — that is the sidecar's job.

### `max_lines` is a hard preflight gate, and font metrics decide it

`preflight._check_fonts` loads each `font_file` with Pillow and pre-wraps every overlay
against real metrics. Overflow is a **preflight error**, before any encode. This is good
design — it fails in seconds, not after stage A — but it means a font substitution changes
what fits. Substituting Arial Bold for Montserrat ExtraBold on do-less cost exactly one
round-trip (`claim_card` needed 3 lines, not 2).

> `font_file` must be an absolute path to a TTF that Pillow can open. Budget one preflight
> iteration whenever the specified font is not installed.

---

## What the renderer does well — use these freely

- **Ken Burns** — `push_in` / `pull_out` / `scale_up`, four easings, moving anchors, `hold_s`,
  supersampled ×4 on final for clean lanczos.
- **Automatic 9:16 conform** — cover-fit then centre crop. 1632×2912 sources cost 7 px of
  height. No need to pre-conform aspect.
- **Whip transitions** with directional blur.
- **Accent spans** — `[[text]]` inside overlay copy renders in the style's `accent` colour,
  so a single amber word inside an off-white line is one overlay, not two.
- **Bed ducking** — voice-relative `gain_db`/`duck_db`, attack/release, non-overlapping
  `windows` (`out`/`ducked`/`full`) and `fades`. Measured afterwards, not asserted.
- **Safe-zone enforcement from real geometry** — stage B writes a bbox sidecar per overlay and
  stage F checks each against the declared rect. This is a genuine measurement, not a guess.
- **Honest QA** — twelve checks, and `preview_audio` states in the report itself when a mix is
  not conforming. Only a PASS mints a version.

---

## Open follow-ups

1. **No `shorts-assembly` → `render-spec.json` adapter.** The do-less spec was hand-authored
   from the v3 build sheet; the mapping is mechanical enough to automate and is now
   demonstrated end to end. Deferred out of stitcher v1 by design
   (`2026-08-06-automated-asset-stitcher-design.md` §9).
2. **The loudnorm failure message advises the wrong remedy** (see §1). One-line fix.
3. **A crop/reframe field on `Shot`**, so a framing constraint is recorded in the spec and
   visible to QA rather than living only in a pre-cut asset.
4. **A pre-conditioning stage or an explicit "assets must arrive mastered" precondition**, so
   the PLR failure is caught at preflight with a diagnosis instead of at stage C with a
   backwards hint.
