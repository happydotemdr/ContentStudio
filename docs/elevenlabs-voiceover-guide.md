# ElevenLabs Text-to-Voice / Voiceover Guide for Faceless YouTube

*A production guide for faceless creators shipping both Shorts and long-form. Covers model choice, voice selection and cloning, the settings that matter, scripting for the ear, and mix/loudness practice — current as of 2026-07-23.*

## About this guide

This is a **synthesis guide**, and it's worth being honest about its sources up front. ElevenLabs has **no dedicated YouTube channel worth mining** for real-creator technique, so this guide is built from two places:

- **`[T]` — web-verified ElevenLabs docs/features** (models, settings ranges, pricing, features), verified 2026-07-23. This is the primary source.
- **`[C]` — corpus findings** from faceless creators describing how they actually use AI voice in production, cited as `(Channel, video_id)`.
- **`[I]` — general production practice** where neither source is decisive.

It **expands the voice-overlay section of the Shorts production playbook** — treat that playbook as the workflow spine and this as the deep-dive on the voice layer specifically.

One theme runs through the corpus and deserves stating early: **audio quality beats video quality for retention.** Viewers tolerate rough footage but bail on bad or too-loud audio, and the single most common killer of average view duration (AVD) is not the script or the edit — it's the mix `(Romayroh, Wox4Jt_2t6w)` `(Dan the creator, 9JE8-wM8zKc)`. AI voice is cheap and nearly indistinguishable from human `(Make Money Matt, TvJhpOxFRsE)`; the leverage is in *how* you configure and mix it.

---

## 1. Models (as of 2026-07-23) `[T]`

ElevenLabs offers several TTS model families. Pick by the job, not by newest-is-best.

| Model | Strengths | Languages | Best for |
|---|---|---|---|
| **Eleven v3** | Most expressive; **audio-tag system** (inline `[excited]`, `[whispers]`, `[sighs]` to control emotion/delivery); **Text-to-Dialogue API** (multi-speaker) | 70+ | Narrative, emotional, story-driven VO; Shorts hooks that need punch |
| **Multilingual v2** | High-quality, stable workhorse; very consistent across long runs | 29+ | Long-form narration where consistency matters more than drama |
| **Flash / Turbo v2.5** | Low-latency, cheapest (~$0.05/1k chars); slightly less expressive | Many | High-volume batch generation, real-time, or draft passes |

**Rule of thumb:** Use **v3** when the delivery carries emotion (storytelling, hooks, reactions). Use **Multilingual v2** for steady, book-like long-form. Use **Flash/Turbo** when you're generating a lot of characters and want to keep costs down, or drafting before a final v3 render.

---

## 2. Choosing & cloning a voice

ElevenLabs ships a library of **10,000+ voices** `[T]`, plus three ways to get a voice that's yours:

| Path | What it is | When to use |
|---|---|---|
| **Library voice** | Pick a pre-made voice | Fastest start; but see the warning below |
| **Instant Voice Cloning** | Clone from a short sample (Creator+ tier) | You want *your* voice without a big recording session |
| **Professional Voice Cloning** | Clone from a long, high-quality dataset | Highest fidelity; your channel voice is a long-term asset |
| **Voice Design** | Generate a voice from a text description | You want a distinctive voice no one else has |

### The one rule for faceless channels

**Pick ONE voice and keep it consistent across every video.** That voice *is* your channel identity `[T]` `[I]`. Switching voices between uploads reads as a different creator.

### Do NOT use the default popular voices

This is the strongest signal in the corpus. The most-common preset ElevenLabs voices appear on hundreds of thousands of videos, and creators report YouTube can detect the repeat and treat yours as **another copy — risking limited reach or shadowban** `(One Person Business, 84bavOadYCI)` `(Make Money Matt, TvJhpOxFRsE)`.

Fixes, in rough order of preference:
- **Clone your own voice** — 100% unique, better for the algorithm than a shared stock voice, and (per one creator) a cloned-own voice currently doesn't trigger YouTube's altered-content disclosure `(Romayroh, OrPYWlXMQws)`.
- **Record your own voice** — even a cheap mic and an accent reads as *original* in a sea of polished AI voices; it's also free `(One Person Business, 6s2T2NlWDhQ)`.
- **Pick a lesser-used library voice** — if you must use stock, avoid the obvious defaults `(Make Money Matt, TvJhpOxFRsE)`. One creator even argues higher-tier (double-credit) "pro" voices are less likely to be flagged, treating them as a signal you're using AI seriously — this is a low-confidence theory, not confirmed policy `(Romayroh, e5AvJAbxWW8)`.

### A middle path: the voice-changer

You don't have to choose pure TTS *or* pure recording. ElevenLabs' **voice-changer** lets you **read the script yourself, then convert your read** — keeping your human pauses, breaths, and cadence while cleaning up the sound `(Romayroh, KbUXzJ55eJk)`. Similarly, a cloned voice is great for **patching narration errors over B-roll** without re-recording: type the corrected line and generate — short lines work well, long blocks less so, and speed is adjustable to match cadence `(Nick Nimmin, usll4p9ziRw)`.

---

## 3. The settings guide (the core) `[T]`

Five sliders do most of the work. Here's what each does and the best-practice range.

| Setting | What it controls | Best-practice range | Notes |
|---|---|---|---|
| **Stability** | Consistency vs. natural variation | Default ~**50%** | Technical/corporate **65–75%** (clarity, avoid robotic flatness); storytelling/character **40–55%** (emotional arcs). Too low = unstable; too high = monotone. |
| **Similarity / Clarity boost** | How closely output tracks the source voice | **75–90%** (~75 default) | **Do NOT push to 100%** → over-enunciated "news anchor" artifacts. |
| **Style exaggeration** | Expressiveness / drama | Narration **10–50%** (0 default) | Higher = more drama but **slower generation**. |
| **Speed** | Pace | Natural **0.9–1.1×** | Marketing/energetic **1.1–1.3×**; slow down for complex topics. |
| **Speaker boost** | Tightens similarity to the source voice | **ON** for most VO | Leave on unless it introduces artifacts. |

### Preset table by content type

| Content type | Stability | Similarity/Clarity | Style | Speed | Speaker boost |
|---|---|---|---|---|---|
| **Narration / technical** | 65–75% | 75–90% | 10–30% | 0.9–1.0× | ON |
| **Storytelling / character** | 40–55% | 75–90% | 30–50% | 0.95–1.1× | ON |
| **Marketing / Shorts** | 50–70% | 75–90% | 40–60% | 1.1–1.3× | ON |

**Reading the table:** technical content wants *stability high, style low, speed slightly under 1×* — clear and unhurried. Storytelling drops stability so the voice can rise and fall with the arc. Shorts push speed and style up because you're competing for attention in the first second and pacing is a weapon.

---

## 4. Scripting for TTS

Great settings can't rescue a script written for the eye. Write for the **ear**.

- **Short sentences.** Long clauses run the model out of breath and blur the meaning. This mirrors human delivery advice: the final words carry the meaning, so don't let energy trail off at the end of a line `(Kallaway, ZM3elcBE48I)`.
- **Punctuation is pacing.** Use commas, ellipses (`…`), and line breaks to place breaths and beats `[T]`. A period is a full stop; an ellipsis is a held pause.
- **v3 audio tags for emotion `[T]`.** In Eleven v3, add emotion inline in the script rather than shouting with capitals: `[excited]`, `[whispers]`, `[sighs]`, `[laughs]`, `[sarcastic]`. Place the tag immediately before the words it should color.
- **Spell tricky words phonetically `[T]`.** Brand names, acronyms, and unusual terms often mispronounce — respell them the way they sound (e.g., `nginx` → `engine-x`).
- **Emphasis via tags, not CAPS `[T]`.** Capitals can be read as an acronym or just ignored; a v3 tag is the reliable lever.
- **Generate section-by-section `[T]`.** Don't render one giant block. Section-level generation lets you control pacing and **re-roll a bad read cheaply** — the same logic human narrators use when they record each line 2–3 times to have options in the edit `(Nick Nimmin, IF-PD6XMjYY)`.
- **Believe the words.** A subtle but real corpus point: lines you don't believe read as hollow, even synthetically. If you write (or AI-generate) a script, spend a few minutes tweaking it into natural phrasing before you commit it to the voice `(Kallaway, ZM3elcBE48I)`. The "coffee-shop method" — write as if talking to a friend — keeps delivery from going stiff `(Dan the creator, bTr-Izh9pkc)`.

---

## 5. Production & mixing

The mix is where most faceless channels quietly lose retention. Get these right every time.

- **Normalize to −14 LUFS `[T]`.** That's YouTube's loudness target. Leave headroom; avoid clipping. If you recorded with a weak mic, **normalize the detached audio track** to remove peaks and even out volume `(Make Money Matt, LlIkMWX50aQ)`.
- **Duck the music bed under the VO.** Notes target **−12 to −18 dB under voice** `[T]`; corpus creators run music even lower — around **−21 to −22 dB** — and call loud music a *top cause of low AVD* `(Romayroh, Wox4Jt_2t6w)` `(Roberto Blake, iaTavrWIGDM)`. Use one-click **auto-ducking** (e.g., Premiere's Essential Sound music label) so music restores when no voice is present `(Roberto Blake, iaTavrWIGDM)`. **When in doubt, music too quiet beats music too loud.**
- **Match the music's emotion to the words.** Music drives the emotional state that triggers shares; a track that clashes with the script confuses the viewer — **no music beats the wrong music** `(Kallaway, i7upRL4H1FM)`.
- **Consistency across videos.** Lock one voice + one settings preset + one loudness target and reuse them channel-wide `[T]`. Consistency is part of the brand.
- **Avoid artifacts.** Keep clarity ≤ ~90%, don't over-crank style, and listen for the "news anchor" over-enunciation and metallic edges that come from maxed sliders `[T]`.
- **Re-roll bad reads.** Section-level generation makes this nearly free — regenerate one line, not the whole track `[T]`. Consider generating 2–3 takes of key lines (hook, CTA) and picking the best, exactly as human narrators do `(Nick Nimmin, IF-PD6XMjYY)`.
- **Sound design lifts flat VO `[I]`.** Risers into a reveal, a hit on the release, a low drone under a mysterious beat, small whooshes/ticks matched to on-screen motion — and pausing the music right before the big line — all change how a moment lands `(vidIQ, DiZnbihU4NM)`.

---

## 6. Pricing & plans `[T]`

*Verify current numbers at elevenlabs.io/pricing before relying on them.*

| Plan | Price | Includes | Notes |
|---|---|---|---|
| **Free** | $0 | 10,000 credits/mo, MP3 export | No commercial license |
| **Starter** | ~$6/mo (annual) | Entry paid tier | Instant Voice Cloning unlocked |
| **Creator** | **~$22/mo** | **100k chars + commercial license** | **The tier most faceless creators use** |
| Higher tiers | More | More characters + Professional Voice Cloning | Scale up as volume grows |

**Per-character cost:** TTS is **$0.10 / 1,000 chars** (v2/v3) and **$0.05 / 1,000 chars** (Flash/Turbo); 1 credit = 1 input character `[T]`.

**Which tier does a faceless creator need?** **Creator (~$22/mo)** is the answer for almost everyone — it unlocks the commercial license (required for monetized YouTube), instant cloning, and 100k characters (roughly a month of Shorts plus a few long-form scripts). The corpus math backs the value: AI voiceover runs about **$1–2 per video** versus ~$25 for a human voice artist `(Make Money Matt, TvJhpOxFRsE)`.

---

## 7. AI disclosure

**AI voiceover alone does not require YouTube's synthetic-content disclosure, and it is not disqualifying** `[T]`. Disclosing does not hurt reach or monetization. One creator specifically notes that a **cloned-own** voice currently doesn't trigger the altered-content disclosure `(Romayroh, OrPYWlXMQws)`.

The disclosure rules bite on **realistic altered/synthetic depiction of real people, places, or events** — not on the mere use of a TTS narrator. Cross-reference the **launch game plan's rights gate** for the full disclosure/rights checklist before publishing; this guide's scope is the voice layer, not the whole compliance surface.

---

## 8. Settings cheat-sheet + Dos/Don'ts

### Quick-reference

| Lever | Safe default | Push up when… | Push down when… |
|---|---|---|---|
| Stability | 50% | Technical/clarity (→75%) | Emotional storytelling (→40%) |
| Similarity/Clarity | 75% | Voice drifts from source (→90%) | Over-enunciated (never >90%) |
| Style | 10–20% | Shorts/marketing energy (→60%) | Clean narration (→0–10%) |
| Speed | 1.0× | Shorts/energy (→1.3×) | Complex topics (→0.9×) |
| Speaker boost | ON | — | Only if it adds artifacts |
| Loudness | −14 LUFS | — | — |
| Music under VO | −16 dB | — | Anything unclear → quieter |

### Dos

- **Do** clone or pick a lesser-used voice; keep ONE voice channel-wide.
- **Do** normalize to −14 LUFS and duck music well under the voice.
- **Do** write for the ear — short sentences, punctuation as pacing, phonetic spelling.
- **Do** use v3 audio tags for emotion instead of capitals.
- **Do** generate section-by-section and re-roll bad reads.
- **Do** match music emotion to the script.
- **Do** consider the voice-changer (read it yourself, then convert) for a human fingerprint.

### Don'ts

- **Don't** use the default popular ElevenLabs voice — reach/shadowban risk.
- **Don't** push clarity/similarity to 100% — artifacts.
- **Don't** run music loud — it's the #1 AVD killer.
- **Don't** use music whose tone contradicts the words.
- **Don't** render one giant block — you lose pacing control and cheap re-rolls.
- **Don't** ship a script you don't believe — it reads hollow even synthetically.

---

## 9. Source note

This guide combines **web-verified ElevenLabs docs/features** `[T]` (models, settings ranges, pricing, features — verified 2026-07-23 against elevenlabs.io/docs, /v3, /pricing and secondary settings references) with **corpus findings from faceless creators** `[C]` describing real production usage (24 voiceover-audio findings across channels including Kallaway, Nate Black, Roberto Blake, Nick Nimmin, Make Money Matt, Romayroh, One Person Business, vidIQ, and Dan the creator). `[I]` marks general practice.

**Verify pricing and plan details at elevenlabs.io/pricing before relying on them** — TTS pricing and tier limits change. Where the notes and corpus differ (e.g., music-ducking depth: −12 to −18 dB per docs vs. −21 to −22 dB per creators), both are given so you can choose by ear.
