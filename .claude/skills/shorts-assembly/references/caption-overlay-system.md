# Caption & overlay system

Provenance markers as in `pacing-and-editing.md`. Primary source: `docs/headless-shorts-production-playbook.md` §4 (`[I]` unless noted). Cross-checked against `docs/headless-youtube-audit.md` §6, which is `[C]` but pulls a different direction on caption density — both are given below rather than silently merged, per this project's anti-generic rule.

## Two overlay layers

1. **Spoken-word captions** — synced to the VO, karaoke word-highlight style.
2. **Hook/emphasis text cards** — short standalone lines (the hook line, the re-hook line, key numbers) that work even with sound off.

## Caption style `[I]`

- Bold sans-serif, heavy weight (Montserrat ExtraBold, Poppins Bold, or CapCut default). White fill + thick black stroke (2–4px) or a semi-opaque box behind, so it reads on any background.
- **Karaoke word-highlight** (active word tinted a brand accent) is the modern default and boosts Shorts retention `[I]`; Submagic specializes in this `[T]`.
- 1–3 words per on-screen chunk for karaoke captions; max ~1 short line (≤5–6 words) for a static caption.
- **Don't overload frames with meme-style Impact-font text that just repeats the title** `[C] (vidIQ, g844t-iFzxA)`.

## Caption density — a genuine corpus tension, both sides kept

- **Playbook default (Shorts-specialist grounded, `[I]`):** caption every spoken word throughout the Short, synced word-by-word, karaoke-highlighted.
- **Audit §6 counter-finding (`[C]`, from the faceless-core/craft-general channels):** **"Keep captions small and mostly at the start"** — audiences dislike large captions; consider a small one-word-at-a-time template only for the **first ~5–10 seconds**, then rely on YouTube's auto-subtitles for the body `[C] (One Person Business, 6s2T2NlWDhQ; Make Money Matt, LlIkMWX50aQ)`.
- **Reconciliation (a judgment call, not a corpus finding):** `[I]` these come from different channel populations — the audit's "front-load only" advice is observed mostly on longer-form faceless content, while the playbook's full-caption default is built from Shorts specialists (Jenny Hoyos, Nate Black, vidIQ, Nick Nimmin) whose exemplars run full karaoke captions throughout. For a 30–45s Short, default to **full-duration karaoke captions** (the Shorts-specific finding), but pull the audit's *size and restraint* discipline into it: keep the caption typography small/unobtrusive relative to the frame rather than dominating it, and never let captions repeat the on-screen hook-card text redundantly. Flag this as an open call if the user's channel leans closer to the audit's faceless-core style than the Shorts-specialist style.

## Timing

- Captions appear **in sync with the spoken word** (auto-caption then hand-correct) `[I]`.
- **Hook text card** on screen for the full 0–3s — readable even muted `[I]`, operationalizing the corpus principle that the first frame must raise a question before a word is spoken `[C] (vidIQ, DiZnbihU4NM)`.
- **Secondary-hook (re-hook) text card at ~15s** `[C] (Nate Black, c6X-Ywy3yVU)`.

## Safe zones — the UI-collision map `[I]`

Vertical 1080×1920 canvas:

| Zone | Extent | Rule |
|---|---|---|
| Top | ≈0–220px (~10–12%) | Avoid — YouTube status/back UI |
| Bottom | ≈1540–1920px (~18–22%) | **Hard no-go** — handle, title, like/comment/share, Subscribe, progress bar |
| Right | ≈950–1080px (~12%) | Avoid — action rail (like/comment/share icons) |
| Safe caption zone | y ≈ 45–65%, centered horizontally | Biased slightly above dead-center so captions clear the bottom UI |

## Readability rules `[I]`

- Never place text without a stroke, shadow, or box behind it. Test at phone size and arm's length.
- Captions ~60–80px cap height; hook cards larger (90–120px).
- One idea per card — don't stack two thoughts.
- Motion: slow push-in of a few percent at the open; keyframe stills to scale 15–20% (see `pacing-and-editing.md`) `[C] (vidIQ, DiZnbihU4NM)`.

## Cover / packaging text `[C]`

- **Un-thumbnail recipe:** original image + subtle enhancement + short bold text (2–4 words) + optional familiar symbol; 72% of standout small-channel videos in one study used this `[C] (Nate Black, -zd1lLaC-I0)`.
- **One crystal-clear focus point, the largest object**, readable like a highway billboard `[C] (Nick Nimmin, h8OTdq24irE / LAzYEKltBwA)`.

## Fill-in style spec (copy into the edit plan)

```
Font:            ______________________ (bold sans)
Cap size:        captions ___px | hook cards ___px
Fill / stroke:   ______ fill / ______ stroke ___px
Highlight color: ______ (active-word karaoke)
Position:        captions y=__% (safe band 45-65%) | hook card y=__%
Safe zones off:  top __% , bottom __% , right __%
Words per card:  captions ___ | static line ≤___ words
Animation:       [pop|slide|fade] , push-in ___% at open
```
