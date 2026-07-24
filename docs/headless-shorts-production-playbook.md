# Headless YouTube Shorts Production Playbook

A repeatable, template-driven production system for a **solo operator running a faceless / headless YouTube Shorts channel** with **external creator tools** (no in-house pipeline). Everything here is meant to be filled in, copy-pasted, and run every week without re-deciding the process.

## How to use this playbook

- **Read it alongside the two companion documents** in this same `docs/` folder:
  - the **audit** ([`headless-youtube-audit.md`](headless-youtube-audit.md)) — the evidence base: what the corpus says, what to fix first;
  - the **game plan** ([`headless-channel-launch-gameplan.md`](headless-channel-launch-gameplan.md)) — niche, positioning, cadence targets, and the **rights gate** you must clear before publishing. This playbook's asset/rights sections (§6) cross-reference that gate; do not publish an asset that fails it.
  - and the folder **[README.md](README.md)** for the provenance key and how the three fit together.
- The **Template pack** (§7) is the working core. Copy a template, fill the blanks, ship. The **End-to-end SOP** (§8) ties them together into one numbered run.

### Provenance discipline (read this — it is the honest part)

This corpus is deep on **Shorts structure, retention, hooks, and packaging** and thin on **AI-production mechanics**. So claims are labelled:

- **`[C]`** — a **corpus finding** extracted from creator videos, cited `(Channel, video_id)`. The structure/retention/hook/packaging material in §2, §4, and §5's audio-strategy notes is mostly `[C]`.
- **`[I]`** — **general industry practice**. The specific text-overlay settings, TTS pacing numbers, prompt skeletons, and folder schemes are `[I]` — sensible defaults, not corpus extraction. Labelled honestly so you don't mistake convention for evidence.
- **`[T]`** — a **tool / pricing / policy fact** from the web-verified tool notes, stated **"as of 2026-07-23."** Re-verify pricing before you rely on it; AI-tool pricing moves monthly.

If a line is `[I]`, it is my recommendation, not something a creator in the corpus said. Where the corpus and a tool fact combine (e.g. duck music under voice — a `[C]` principle with an `[I]` dB target), both tags appear.

---

## 2. Shorts anatomy & structure

A Short lives or dies in the **first 1–2 seconds** and is scored on **average percentage viewed**, not raw watch time. Build every Short as a single tight loop, not a mini-documentary.

### The beat model (target: ~30–45s Short)

A ~35s Short runs roughly **90–105 spoken words** at a natural 150–170 wpm narration pace `[I]`. Budget it like this:

| Beat | Seconds | Word budget | Job |
|---|---|---|---|
| **Hook** | 0–3s | 8–15 words | Stop the swipe. State the premise as a provocative question OR drop into action already in progress. |
| **Setup** | 3–8s | 12–20 words | One sentence of context + the stakes. No "in this video." |
| **Build / Value** | 8–28s | 45–60 words | Deliver the single idea in escalating steps, each opening a small new loop. |
| **Payoff** | 28–38s | 15–25 words | Resolve the exact question the hook asked. The reveal. |
| **Loop / CTA** | 38–45s | 5–12 words | Mirror the hook line so the end feeds the start; earn a comment with a specific question. |

**Total ≈ 90–110 words for a 35–45s Short.** For a punchier 20–30s Short, cut Setup to one clause and Build to ~30 words. Nate Black: when reviving a dead/random channel, **err toward shorter, punchier videos** `[C] (Nate Black, wqjiXKKqek4)`.

### The Hook (0–3s) — the whole ballgame

- **On Shorts, 50–60% of the viewers who leave do so within the first 3 seconds** `[C] (vidIQ, UCrC5B3Soyc)`. You are fighting the swipe, not building an intro.
- **Never open with "in this video I'm going to show you"** or treat the top as an intro/summary `[C] (vidIQ, UCrC5B3Soyc)`. Nick Nimmin echoes: don't open with "hey guys, today we're going to talk about" `[C] (Nick Nimmin, 2vkX1X1K3WM)`.
- **Make the first frame a visual hook that raises a question before a word is spoken** `[C] (vidIQ, DiZnbihU4NM)`. Nick Nimmin: if on-camera retention drops at the start, **open on B-roll instead** `[C] (Nick Nimmin, kcSOFqJhR9I)` — for a faceless channel you are *always* opening on B-roll, so make that first frame carry a question.
- **Open by leading with the viewer's problem or a specific stake**, not credentials `[C] (Nick Nimmin, 2vkX1X1K3WM)`. Address a singular **"you,"** not "hey guys" `[C] (Nick Nimmin, IF-PD6XMjYY)`.
- **Start mid-action and explain along the way** rather than building up to the payoff `[C] (vidIQ, DiZnbihU4NM)`; **open with something interesting already happening, not an announcement of what's coming** `[C] (Nate Black, c6X-Ywy3yVU)`.
- Techniques that work as hooks: the **provocative core-premise question** the viewer wants answered `[C] (Jenny Hoyos, BJv4MYm7-rU)`; **in-medias-res** drop into a high-stakes moment `[C] (Jenny Hoyos, fKoAOWQHP0o)`; a **self-deprecating underdog admission** to lower the guard `[C] (Jenny Hoyos, xndW0kxLV6g)`.

### The single-idea rule + curiosity loops

- **Anchor the whole video on a single clear premise plus one explicit constraint or deadline** stated in the opening seconds `[C] (Jenny Hoyos, rGdOljEhqBc)`.
- **Plant an open curiosity loop early** — promise a specific result revealed only at the end `[C] (Jenny Hoyos, oVKBAMEqsPI)`. Roberto Blake: **continuously open new curiosity loops ("mystery boxes")** so every stretch compels the next `[C] (Roberto Blake, q64Iczdhb-Y)`.
- **The biggest mid-video drop is caused by front-loaded setup and context**, not too much detail `[C] (vidIQ, DiZnbihU4NM)`. Get to the value fast.
- **Keep constant forward motion** — rapid segment-to-segment transitions, no dead air `[C] (Jenny Hoyos, oVKBAMEqsPI)` — but **do not chase wall-to-wall stimulation and constant jump cuts** to fake retention `[C] (vidIQ, DiZnbihU4NM)`.

### The ~15s secondary hook (re-hooking)

- **Pair every resolution with a new hook — re-hook viewers repeatedly, not only at the intro** `[C] (Nate Black, c6X-Ywy3yVU)`. On a Short this means a second curiosity beat around the **~15s mark**, right when the opening loop starts to feel answered `[I]`.
- **Compilation / escalation structures retain well** because they inherently stack hook→deliver, setup→payoff cycles `[C] (Nate Black, c6X-Ywy3yVU)`; structure the build as **escalation from small to progressively bigger steps** `[C] (Jenny Hoyos, TmtHoTrL-J8)`.
- Consider a **mid-video twist that subverts the premise's expectation** `[C] (Jenny Hoyos, oVKBAMEqsPI)`.

### Seamless loop-to-start

- **Mirror the opening hook question in the closing line so the video forms a satisfying loop** `[C] (Jenny Hoyos, mhVDcqnxxaY)`. On Shorts this makes the replay seamless — the payoff feeds straight back into the hook, and **low unique-viewers-with-high-views means the video is being rewatched (looped)** `[C] (Nate Black, IHDJkJpYC90)`, which is exactly the signal you want.
- **Resolve on a climactic reveal that directly answers the hook's question** `[C] (Jenny Hoyos, fukTZ82O4TU)`.

### Length & retention findings

- **Retention is judged relative to videos of similar topic and length** — a shorter video with higher retention can beat a longer one with more raw watch time `[C] (vidIQ, SIp7MeYbz8U)`. Shorter-and-tighter is a legitimate strategy, not a compromise.
- **Judge enjoyment by average percentage viewed, not average view duration** `[C] (Nate Black, IHDJkJpYC90)`.
- Roberto Blake's long-form benchmark — **target >35% average-view-duration**, which roughly doubles the odds of converting a casual viewer to a subscriber `[C] (Roberto Blake, q64Iczdhb-Y)` — is a useful north star; on Shorts, chase **>90–100% average-percentage-viewed with re-watches** instead `[I]`.
- **Don't chase a rigid daily quota as the growth lever** — consistency of *quality* drives breakouts more than a rigid schedule `[C] (vidIQ, UCrC5B3Soyc)`, and **uploading 5+ times a week for months burns out ~1 in 4 channels** `[C] (vidIQ, UCrC5B3Soyc)`.

### Faceless-specific structure notes

- **Talking-to-camera relies almost entirely on the speaker's energy** — risky `[C] (Nate Black, UjeOJb6lk5M)`. A faceless channel sidesteps this **only if** it substitutes a strong **visual demonstration layer** `[C] (Nate Black, UjeOJb6lk5M)` and motion.
- **Turn spoken stats and lists into on-screen motion graphics** so viewers *see* the information, not just hear it `[C] (vidIQ, i5bZ-Be9cAQ)`.
- For faceless AI Shorts, use an **image → animate → assemble** stack and **build audience trust rather than posting slop** `[C] (vidIQ, 9z1ACpWW9do)`; **re-inject human elements — personal stories, real proof —** to survive scrutiny and inauthentic-content demonetization `[C] (vidIQ, Sgav7Bkg36M)`. This is the single most important survival rule for a headless channel (see §6 rights line).

---

## 3. Recommended tool stack (opinionated, `[T]`, as of 2026-07-23)

One **primary** + 1–2 **alternates** per function, each with a pricing tier and a one-line "why." All `[T]` from the tool notes; **re-verify pricing before relying on it.**

### By function

**Ideation / scripting / research**
- **Primary: vidIQ** `[T]` — keyword/competitor/title tooling and analytics; the corpus's most-cited research voice. Free tier; paid from ~$/mo.
- **Alt: TubeBuddy** `[T]` — keyword + A/B-title tools.
- Scripting itself: draft in any LLM but **never let AI script word-for-word** — it produces an "AI vibe" `[C] (Nate Black, 9CCmMypN8PM)`. Use bullet points, script only the hook and outro `[C] (Nick Nimmin, IF-PD6XMjYY)`.

**TTS / voiceover**
- **Primary: ElevenLabs** `[T]` — quality leader; Creator ~$22/mo for ~100k chars (~80 min); overage pricey; embeds a **SynthID watermark** (disclosure implications — see §6).
- **Alt (budget high-volume): Murf AI** `[T]` — Falcon API ~$0.01/min; Studio + Dub across 40+ languages.
- **Alt ($0 / local): Chatterbox (Resemble AI)** `[T]` — MIT open-source, free/local, beat ElevenLabs in a blind test (~63.8% preferred). Best free voice.
- **Free tier w/ commercial rights: Google Cloud TTS** `[T]` — ~4k WaveNet chars/mo free.

**AI static images**
- **Primary (text-in-image): Ideogram 3.0** `[T]` — **the one to use when the image needs on-image text** (reliable spelling); free tier; Plus ~$20/mo. **Nano Banana Pro** is also strong for text-in-image `[T]`.
- **Alt (aesthetic, NO text): Midjourney v8.1** `[T]` — best stylized look but **cannot spell** — never for text-in-image.
- **Alt (open/local/cheap): Flux 2** `[T]` — Klein variant runs locally; hosted ~$0.01–0.10/image.

**AI short video clips**
- **Primary (quality): Google Veo 3.1** `[T]` — best overall Western option.
- **Primary (value): Kling 3.0** `[T]` — ~$0.84 per 10s (Standard) with audio, licensable, from $7.99/mo. Best value/quality.
- **Alt (free/value): MiniMax Hailuo 2.3** `[T]` (free tier, watermark/caps) · **Luma Dream Machine** `[T]` (free tier).
- Reality check: **AI still fails at pure B-roll generation due to an uncanny-valley look** `[C] (Nate Black, 9CCmMypN8PM)` — animate a still or use stock before you gamble minutes on text-to-video.

**Captions / text-overlay**
- **Primary ($0): CapCut** `[T]` — best free editor + auto-captions + templates. The default for a $0 start.
- **Alt (best animated captions): Submagic** `[T]` — Pro ~$23/mo annual, filler-word removal, Magic Clips repurposing.
- **Alt (watermark-free cheap): Captions.ai** `[T]` — Pro ~$9.99/mo.

**Editing / assembly**
- **Primary: CapCut** `[T]` — free, mobile + desktop, the Shorts default.
- **Alt: Descript** `[T]` — text-based editing + filler removal (edit audio by editing the transcript). **Premiere Pro** `[T]` for the pro tier.

**Long→short clipping (if repurposing)**
- **Opus Clip** `[T]` — long→short auto-clipping; from $15/mo, free 60 credits (watermarked). Nick Nimmin uses it to stay consistent across platforms `[C] (Nick Nimmin, usll4p9ziRw)`. **Reap** ranked #1 in an April 2026 benchmark `[T]`.

**Thumbnails / covers**
- **Primary: Canva** `[T]` (fast templates) · **Ideogram** `[T]` for AI + reliable text · **Photoshop** for control. Shorts cover = the first frame or a **custom cover image** (custom Shorts thumbnails now exist in desktop Studio) `[C] (vidIQ, mgqkfDBT7gU)`.

**Scheduling**
- **Native YouTube Studio scheduling** `[T]`. Don't upload and let a video "sit" a day expecting a boost — that's a myth `[C] (Nick Nimmin, 0l2g3Bujy1Y)`.

**Analytics**
- **YouTube Studio (Advanced mode) + vidIQ** `[T]`. Read the **first 24–48h of CTR and AVD against your channel average**, then double down on what beats it `[C] (vidIQ, ZKsldrcO_fU)`.

### Summary table

| Function | Primary | Alt 1 | Alt 2 | Tier |
|---|---|---|---|---|
| Research/titles | vidIQ | TubeBuddy | — | Free→paid |
| TTS voice | ElevenLabs | Chatterbox (free/local) | Murf AI | $0→$22/mo |
| Static images | Ideogram 3.0 (text) | Midjourney (no text) | Flux 2 | Free→$20/mo |
| Video clips | Kling 3.0 (value) | Veo 3.1 (quality) | Hailuo (free) | Free→pay-per-clip |
| Captions | CapCut | Submagic | Captions.ai | $0→$23/mo |
| Edit/assemble | CapCut | Descript | Premiere Pro | $0→pro |
| Thumbnails | Canva | Ideogram | Photoshop | Free→paid |
| Schedule | YT Studio | — | — | Free |
| Analytics | YT Studio | vidIQ | — | Free→paid |

### $0 starter stack

> **Research** vidIQ free + YouTube Studio · **Script** any LLM (bullets only) · **Voice** Chatterbox (local) or Google Cloud TTS free tier · **Images** Ideogram free / Flux Klein local · **Video** Hailuo/Luma free tiers or animate stills in CapCut · **Captions + edit** CapCut · **Thumbnail** Canva free · **Schedule/analytics** YouTube Studio.
> Cost: **$0/mo.** Trade-off: watermarks on some free video tiers, more manual work, slower.

### Paid stack (~$65–90/mo)

> **Research** vidIQ paid · **Voice** ElevenLabs Creator ($22) · **Images** Ideogram Plus ($20) · **Video** Kling ($7.99+ / pay-per-clip) · **Captions** Submagic ($23) · **Edit** CapCut/Descript · **Thumbnail** Canva Pro.
> Cost: **~$65–90/mo** depending on video-clip volume. Reality check from the corpus: **don't overspend on AI tools — most are convenience luxuries, not requirements** `[C] (Romayroh, nFT1xNDprIk)`. Start at $0, upgrade only the bottleneck.

---

## 4. Text-overlay system `[I]` (+ packaging `[C]`)

For a faceless Short, on-screen text is half the show. Two layers: **spoken-word captions** and **hook/emphasis text cards**.

### Caption style

- **Style:** bold sans-serif, heavy weight (e.g. Montserrat ExtraBold, Poppins Bold, or CapCut's default), **white fill + thick black stroke/outline** (2–4 px) or a semi-opaque box behind, so it reads on any background `[I]`.
- **Karaoke word-highlight** (active word tinted a brand accent) is the modern default and boosts retention on Shorts `[I]`; Submagic specializes in these `[T]`. But **don't overload thumbnails/frames with meme-style Impact-font text that just repeats the title** `[C] (vidIQ, g844t-iFzxA)`.
- **Words per card:** 1–3 words per on-screen chunk for karaoke captions; **max ~1 short line (≤5–6 words)** for a static caption `[I]`.

### Timing

- Captions appear **in sync with the spoken word** (auto-caption then hand-correct) `[I]`.
- **Hook text card** on screen for the full **0–3s** — the viewer should read the premise even with sound off `[I]`. This is the "first frame raises a question before a word is spoken" principle `[C] (vidIQ, DiZnbihU4NM)` made literal.
- **Secondary-hook text card** at ~15s to re-hook `[C] (Nate Black, c6X-Ywy3yVU)`.

### Safe zones (the UI-collision map)

Vertical 1080×1920. Keep all critical text inside the middle band:

- **Top ~10–12% (≈0–220px):** avoided — YouTube status/back UI.
- **Bottom ~18–22% (≈1540–1920px):** **hard no-go** — channel handle, title, like/comment/share buttons, "Subscribe," progress bar all live here.
- **Right ~12% (≈950–1080px):** avoided — the action rail (like/comment/share icons).
- **Safe caption zone:** roughly **y = 45–65% vertically, centered horizontally**, biased slightly above dead-center so captions sit above the bottom UI `[I]`.

### Readability rules `[I]`

- **Contrast first:** never place text without a stroke, shadow, or box behind it. Test at phone size and at arm's length.
- **Font size:** captions ~60–80px cap height; hook cards larger (90–120px). Big enough to read on a 5" screen in a glance.
- **One idea per card.** Don't stack two thoughts.
- **Motion:** a **slow push-in of a few percent at the open** makes a static shot read as "something's coming" `[C] (vidIQ, DiZnbihU4NM)`; **keyframe still images to scale 15–20%** to keep the screen alive `[C] (vidIQ, DiZnbihU4NM)`.

### Packaging text (cover / first frame)

- **Un-thumbnail recipe:** original image + subtle enhancement + **short bold text (2–4 words)** + optional familiar symbol `[C] (Nate Black, -zd1lLaC-I0)`. In one study **72% of standout small-channel videos used un-thumbnails** `[C] (Nate Black, -zd1lLaC-I0)`.
- **One crystal-clear focus point, the largest object**, readable at a glance like a highway billboard `[C] (Nick Nimmin, h8OTdq24irE / LAzYEKltBwA)`.

---

## 5. Voice-overlay system `[I]/[T]` (+ audio strategy `[C]`)

Repeatable path: **script → TTS voice → pacing → music bed + ducking → mix/loudness.**

### Script → TTS voice selection

- Write the VO as the **spoken-word script** from Template (1), 90–110 words for a 35–45s Short.
- **Voice pick:** one consistent narrator voice per channel (brand consistency). Match the voice's energy to the niche — **raise energy before "recording"** `[C] (Nick Nimmin, IF-PD6XMjYY)`; for TTS, pick a voice with natural inflection and, in ElevenLabs, nudge **Stability ~40–55% / Similarity ~75% / Style exaggeration low-moderate** for lively-but-clear narration `[I]/[T]`.
- **Generate 2–3 takes** of the hook line and pick the best read — the human-recording principle "record each line multiple times" `[C] (Nick Nimmin, IF-PD6XMjYY)` applies to TTS regeneration too.
- You can **clone a voice in ElevenLabs to fix narration errors over B-roll without re-recording** the whole track `[C] (Nick Nimmin, usll4p9ziRw)`.

### Pacing / timing `[I]`

- **150–170 wpm** natural narration; faster (up to ~180) for high-energy niches, slower for teaching. **Match editing pace to the audience** — fast for younger, slower for older/learning viewers `[C] (Nick Nimmin, LAzYEKltBwA)`.
- Insert **short pauses** after the hook and before the payoff (breathing room = comprehension). In TTS, use punctuation/`<break>` tags or trim silences in the edit.
- Trim dead air ruthlessly — **constant forward motion, no dead air** `[C] (Jenny Hoyos, oVKBAMEqsPI)`.

### Music bed + ducking

- Add a **low-energy music bed** that matches emotion; **use risers, hits, and drones to convey emotion** and give on-screen visuals matching sounds `[C] (vidIQ, DiZnbihU4NM)`.
- **Duck the music under the voice to about −22 dB** (or one-click auto-ducking) so it never overpowers the VO `[C] (Roberto Blake, iaTavrWIGDM)`. This is the single most important mix rule.
- **Music rights:** use YouTube's free Creator Music library, a royalty-free source (see §6), or a license service like **Lickd** for famous tracks — Creator Music often means revenue-share/no-monetization, unlike a direct license `[C] (Roberto Blake, SJsGBKGy4Do)`.

### Mixing / loudness `[I]`

- **Voice peaks around −3 to −6 dB; loudness target ≈ −14 LUFS** (YouTube normalizes toward this).
- **Music bed sits ~15–20 dB below the voice** (i.e. the −22 dB duck above).
- **SFX** (whoosh on cuts, subtle hits on text-card reveals) at a level that punctuates without startling.
- Check the final on **phone speakers**, not headphones — that's how it'll be watched.

---

## 6. Digital asset creation workflow

### Prompt patterns

**AI static image skeleton** `[I]` (use **Ideogram** if the image needs legible text; **Midjourney/Flux** if not):
```
[SUBJECT, specific] , [ACTION/POSE] , [SETTING/BACKGROUND] ,
[LIGHTING] , [MOOD/EMOTION] , [STYLE: photoreal | 3D render | flat vector | cinematic] ,
[COLOR PALETTE / brand accent] , vertical 9:16 , negative: text, watermark, extra fingers, distortion
```
For a text-in-image cover (Ideogram): add `large bold headline text reading "<2-4 WORDS>" , high contrast , thumbnail composition`.

**AI short-video-clip skeleton** `[I]` (Kling / Veo / Hailuo):
```
[SUBJECT] [SINGLE CLEAR ACTION] , [CAMERA MOVE: slow push-in | orbit | static] ,
[SETTING] , [LIGHTING/TIME] , [STYLE/look] , [duration 3-6s] , 9:16 vertical ,
consistent lighting, no morphing, no on-screen text
```
Keep clips to **one action, 3–6s** — text-to-video degrades fast beyond a single motion, and AI B-roll can hit uncanny valley `[C] (Nate Black, 9CCmMypN8PM)`. Prefer **animating a good still** (Ideogram → Kling image-to-video) over pure text-to-video `[C] (vidIQ, 9z1ACpWW9do)`.

### B-roll fallback (stock)

When AI B-roll looks off, drop to stock: **Pexels, Pixabay, Mixkit** (free, commercial-OK), **Storyblocks** (subscription), **Artgrid** (paid, premium). Always confirm the license per clip (below).

### Asset naming / folder scheme `[I]`

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
Convention: `S<###>_<type><##>_<beat>.<ext>`. Type ∈ {img, vid, broll, vo, music, sfx}. One folder per Short, numbered sequentially so batches stay ordered.

### Rights line per asset class — the publish gate

Cross-reference the **game plan's rights gate** ([`headless-channel-launch-gameplan.md`](headless-channel-launch-gameplan.md)); nothing publishes until every asset clears its line. The corpus is blunt: **if a video takes under two hours to make it's probably too low-effort and will get demonetized** `[C] (Romayroh, 1UkLWW0bs7o)`, and **lazy AI automation gets channels terminated** `[C] (Romayroh, OrPYWlXMQws)`.

| Asset class | Rights line |
|---|---|
| **AI images (Ideogram/MJ/Flux)** `[T]` | Check each tool's commercial-use terms for your plan tier (paid tiers generally grant commercial use; free tiers vary). Note: **100% AI-generated content cannot be copyrighted** `[C] (vidIQ, 4kKbMY5NIVs)` — you can use it, but you can't own/defend it. |
| **AI video clips (Kling/Veo/Hailuo)** `[T]` | Same — verify commercial rights per plan; Kling is explicitly licensable `[T]`. Free tiers may add watermarks or restrict commercial use. |
| **TTS voice** `[T]` | Commercial use per your plan. **AI voiceover alone does NOT require AI disclosure and is not disqualifying** `[T]`. But **ElevenLabs embeds a SynthID watermark** — disclose altered content at upload or risk demonetization/YPP rejection `[C] (Romayroh, G9LfE3k-IEI)`. |
| **Music** `[C]` | YouTube Creator Music (may revenue-share), royalty-free libraries, or a direct license (Lickd) for famous tracks `[C] (Roberto Blake, SJsGBKGy4Do)`. Never drop a copyrighted track raw. |
| **Stock footage/images** `[I]` | Confirm the specific license allows commercial + YouTube use; keep the license/source per clip. **Don't build videos from other people's reused footage** — claims can seize revenue `[C] (One Person Business, eVePkmCQV5c)`. |
| **Whole video** `[T]/[C]` | **Add original input:** real curation/research, original script, consistent style — the line that survives the **inauthentic-content** policy `[T]`. **Re-inject human elements** (personal stories, real proof) `[C] (vidIQ, Sgav7Bkg36M)`. **Disclose AI** when it meaningfully alters/generates realistic content `[T]`; mark "not made for kids"; check every video reads **restrictions: none** in Studio `[C] (Dan the creator, JPTr40J3WXU)`. **Never reuse identical title/script templates across videos** — flagged as spam `[C] (Romayroh, KbUXzJ55eJk)`; **never post identical content across channels** — termination `[C] (Romayroh, Wox4Jt_2t6w)`. |

---

## 7. Template pack

Eight fill-in templates. Each has a **blank** and a **worked example**. Copy the blank, fill it, ship.

### (1) Short Script Template

```
=== SHORT SCRIPT — BLANK ===
Short ID:        S___
Working title:   ______________________
Single premise:  ______________________ (one idea only)
Constraint/stake:______________________

HOOK        (0-3s | 8-15 words):  ________________________________________
SETUP       (3-8s | 12-20 words): ________________________________________
BUILD/VALUE (8-28s | 45-60 words):________________________________________
                                  ________________________________________
  [re-hook card @ ~15s]:          ________________________________________
PAYOFF      (28-38s | 15-25 words):_______________________________________
LOOP/CTA    (38-45s | 5-12 words): _______________________________________ (mirror the hook)
Comment-bait question:            ________________________________________
Total word count target: 90-110
```
```
=== SHORT SCRIPT — WORKED EXAMPLE (S042) ===
Short ID:        S042
Working title:   The $2 coffee trick baristas won't tell you
Single premise:  A cheap home hack makes drip coffee taste like a cafe pour-over
Constraint/stake:Under $2, 30 seconds, no machine

HOOK        (0-3s): Your drip coffee tastes flat — and it's not the beans.   (9 words)
SETUP       (3-8s): Cafes do one thing at home you skip. It costs about two dollars. (14 words)
BUILD/VALUE (8-28s): Bloom the grounds first: pour just enough hot water to soak them,
                     wait thirty seconds, then finish the pour. That gas escaping? It's what
                     made your cup bitter. Same beans, same machine — one pause changes everything. (46 words)
  [re-hook card @ ~15s]: "But there's a second mistake almost everyone makes..."
PAYOFF      (28-38s): The second fix: water off the boil, ninety seconds after. Now taste it —
                     smooth, not sharp. That's the cafe difference. (22 words)
LOOP/CTA    (38-45s): So it was never the beans. What flat cup are you fixing tonight? (13 words)
Comment-bait question: Drip, French press, or pour-over — which do you run?
Total: ~104 words
```

### (2) Shot List / Storyboard Template

```
=== SHOT LIST — BLANK ===
Short ID: S___   Duration target: __s
| # | Beat        | Visual (what's on screen)        | On-screen text     | VO line          | Asset source          | Dur |
|---|-------------|----------------------------------|--------------------|------------------|-----------------------|-----|
| 1 | Hook        |                                  |                    |                  | img/vid/broll/stock   |  _s |
| 2 | Setup       |                                  |                    |                  |                       |  _s |
| 3 | Build       |                                  |                    |                  |                       |  _s |
| 4 | Re-hook     |                                  |                    |                  |                       |  _s |
| 5 | Payoff      |                                  |                    |                  |                       |  _s |
| 6 | Loop/CTA    |                                  |                    |                  |                       |  _s |
```
```
=== SHOT LIST — WORKED EXAMPLE (S042) ===
Short ID: S042   Duration target: 44s
| # | Beat     | Visual                                   | On-screen text            | VO line                          | Asset source            | Dur |
|---|----------|------------------------------------------|---------------------------|----------------------------------|-------------------------|-----|
| 1 | Hook     | Close-up flat black coffee, slow push-in | "It's NOT the beans"      | Your drip coffee tastes flat...  | S042_img01 (Ideogram)   |  3s |
| 2 | Setup    | Cafe counter b-roll                      | "$2 fix"                  | Cafes do one thing you skip...   | S042_broll02 (Pexels)   |  5s |
| 3 | Build    | Grounds blooming, bubbles rising (anim.) | "BLOOM 30s"               | Bloom the grounds first...       | S042_vid03 (Kling i2v)  | 14s |
| 4 | Re-hook  | Kettle, steam                            | "2nd mistake ->"          | But there's a second mistake...  | S042_broll04 (Pexels)   |  4s |
| 5 | Payoff   | Pour into clear mug, taste-reaction cue  | "SMOOTH"                  | Water off the boil, 90s after... | S042_vid05 (Kling)      | 10s |
| 6 | Loop/CTA | Return to hero mug (matches shot 1)      | "So... never the beans"   | So it was never the beans...     | S042_img01 (reused)     |  8s |
```

### (3a) AI Image Prompt Template + (3b) AI Video Prompt Template

```
=== AI IMAGE PROMPT — BLANK (Ideogram=text / Midjourney=no text) ===
Subject:        ______________________
Action/pose:    ______________________
Setting:        ______________________
Lighting:       ______________________
Mood:           ______________________
Style:          [photoreal|3D|flat vector|cinematic]
Palette:        ______________________
On-image text:  "______" (Ideogram only; leave blank for MJ/Flux)
Fixed tail:     vertical 9:16, high contrast | negative: text(if none), watermark, extra fingers, distortion
```
```
=== AI IMAGE PROMPT — WORKED EXAMPLE (S042 hook) ===
Ideogram 3.0:
"Extreme close-up of a black cup of drip coffee, flat dull surface, slight steam,
kitchen counter softly blurred behind, warm morning window light, moody and a little
disappointing, photoreal, warm brown + cream palette, large bold headline text reading
'IT'S NOT THE BEANS', high contrast thumbnail composition, vertical 9:16
--negative: watermark, extra fingers, distortion"
```
```
=== AI VIDEO PROMPT — BLANK (Kling/Veo/Hailuo) ===
Subject + single action: ______________________
Camera move:   [slow push-in|orbit|static|tilt]
Setting:       ______________________
Lighting/time: ______________________
Style/look:    ______________________
Fixed tail:    3-6s, 9:16 vertical, consistent lighting, no morphing, no on-screen text
```
```
=== AI VIDEO PROMPT — WORKED EXAMPLE (S042 build) ===
Kling 3.0 (image-to-video from S042_img_grounds.png):
"Coffee grounds blooming as hot water hits them, bubbles and gas rising slowly,
slow push-in, ceramic dripper on a wood counter, soft overhead kitchen light,
photoreal macro, 5s, 9:16 vertical, consistent lighting, no morphing, no on-screen text"
```

### (4) Caption / Overlay Style Spec

```
=== CAPTION/OVERLAY STYLE SPEC — BLANK ===
Font:            ______________________ (bold sans)
Cap size:        captions ___px | hook cards ___px
Fill / stroke:   ______ fill / ______ stroke ___px
Highlight color: ______ (active-word karaoke)
Position:        captions y=__% (safe band 45-65%) | hook card y=__%
Safe zones off:  top __% , bottom __% , right __%
Words per card:  captions ___ | static line ≤___ words
Animation:       [pop|slide|fade] , push-in ___% at open
```
```
=== CAPTION/OVERLAY STYLE SPEC — WORKED EXAMPLE (channel default) ===
Font:            Montserrat ExtraBold
Cap size:        captions 70px | hook cards 100px
Fill / stroke:   white fill / black stroke 3px
Highlight color: #FFD24A (brand amber), active-word karaoke
Position:        captions y=58% | hook card y=40%
Safe zones off:  top 12% , bottom 20% , right 12%
Words per card:  captions 2 | static line <=5 words
Animation:       pop-in on captions , 4% slow push-in at open
```

### (5) Packaging Template

```
=== PACKAGING — BLANK ===
Title options (<=60 chars, pick 1 for A/B):
  A: ______________________________________
  B: ______________________________________
  C: ______________________________________
Frame(s) used: [witness | transformation | access "Inside X" | warning | number+identity]
Cover text (2-4 words): ______________________
Description (1-2 lines + disclosure): ____________________________________
Hashtags (3-5): #______ #______ #______
AI disclosure set? [Y/N]   Made-for-kids OFF? [Y/N]   Restrictions=none? [Y/N]
```
```
=== PACKAGING — WORKED EXAMPLE (S042) ===
Title options (<=60 chars):
  A: The $2 coffee fix baristas won't tell you        (48)
  B: Why your drip coffee tastes flat (it's not beans) (49)
  C: Inside the 30-second cafe coffee trick            (39)  <- access frame
Frames: transformation (A) + access "Inside X" (C)
Cover text: "NOT THE BEANS"
Description: The bloom trick that fixes flat drip coffee in 30 seconds. Contains AI-generated visuals.
Hashtags: #coffee #coffeetips #barista #kitchenhacks
AI disclosure set? Y   Made-for-kids OFF? Y   Restrictions=none? Y
```
Packaging rules baked in: titles **under 60 chars, ideally 52–53** `[C] (Nick Nimmin, LAzYEKltBwA)`, **~40–50 chars is the sweet spot** `[C] (Nate Black, 9mLuaqqW1jY)`; **avoid colons, em-dashes, semicolons** `[C] (Nick Nimmin, LCU3tjJHOaY)`; use **witness (4.41x) / transformation (3.22x) / access "Inside X" (2.5x)** frames `[C] (vidIQ, n5NER9cbueY)`; **plain, literally descriptive** so the algorithm doesn't guess `[C] (vidIQ, SIp7MeYbz8U)`; **value-explicit for small channels** `[C] (Nate Black, DNQ4YIkNBms)`; **near-zero payoff from tags/hashtags/description** — packaging is title+hook+cover `[C] (Nate Black, J8LrrCpDNJI)`; **decide title + cover BEFORE making the video** `[C] (Nick Nimmin, kcSOFqJhR9I)`.

### (6) Production Checklist (gated)

```
=== PRODUCTION CHECKLIST — S___ ===
[ PRE-PRO GATE ]
[ ] Single premise + constraint written (Template 1)
[ ] Title + cover decided BEFORE production
[ ] Idea passes brand-fit (in niche, not a chased outlier)
[ ASSETS GATE ]
[ ] All images generated/sourced, named per scheme
[ ] All video clips <=6s, one action each
[ ] VO generated, best hook take chosen
[ ] Music bed chosen + rights confirmed
[ ] Every asset's rights line cleared (§6 table)
[ ASSEMBLY GATE ]
[ ] Shot list assembled in order (Template 2)
[ ] Captions synced + hand-corrected
[ ] Hook card 0-3s, re-hook card ~15s
[ ] Music ducked to ~-22dB under VO
[ ] Loop: final shot matches/mirrors opening
[ QA GATE ]
[ ] Watched on a PHONE, sound off then on
[ ] First 2s stops the swipe (no intro/logo/filler)
[ ] No text in bottom 20% / right 12% UI zones
[ ] Loudness ~-14 LUFS, voice clear over bed
[ ] No banned openers ("in this video", "hey guys")
[ PUBLISH GATE ]
[ ] AI disclosure set (altered content)
[ ] Made-for-kids OFF
[ ] Studio "restrictions" reads NONE
[ ] Not a duplicate template/script of a recent Short
[ ] Scheduled in YT Studio
```

### (7) Weekly Batch-Production SOP

```
=== WEEKLY BATCH SOP — BLANK (target ___ Shorts/week) ===
MON  Ideation + scripting:  pick ___ topics, write ___ scripts (Template 1), decide titles+covers
TUE  Voice + assets:        generate all VO, all images, all video clips; clear rights lines
WED  Assemble:              build all ___ Shorts (shot list -> edit -> music duck)
THU  Caption + QA:          sync captions, run QA gate on each, fix
FRI  Package + schedule:    finalize packaging (Template 5), set disclosures, schedule the week
SAT/SUN  Off / engage comments only
Weekly review: read last week's metrics (Template 8), decide keep/kill/iterate per format
```
```
=== WEEKLY BATCH SOP — WORKED EXAMPLE (target 5 Shorts/week) ===
MON  Wrote 5 scripts (S041-S045), decided 3 title options + cover text each
TUE  Generated 5 VO tracks (ElevenLabs, 2 takes/hook), 18 images (Ideogram), 9 Kling clips; logged licenses
WED  Assembled S041-S045 in CapCut, ducked beds to -22dB, built loop shots
THU  Auto-captioned + corrected all 5, ran QA gate, refilmed 1 weak hook (S043)
FRI  Packaged all 5, set AI disclosure + made-for-kids off, scheduled Mon-Fri 11:00
Review: S039 (transformation frame) beat channel avg 2x -> make 2 more in that format
```
Batch discipline from the corpus: **schedule each separate part of the job (ideas, research, scripting, recording, editing) into your week** `[C] (Nick Nimmin, kcSOFqJhR9I)`; **keep production cost low enough to survive bad months** `[C] (vidIQ, 9z1ACpWW9do)`; but **consistency of quality, not a rigid quota, drives breakouts** `[C] (vidIQ, UCrC5B3Soyc)`.

### (8) Metrics Tracking Template

```
=== METRICS — PER-SHORT ROW (fill 24-48h after publish, then at 7d) ===
| Short | Format/frame | Views 48h | Views 7d | Avg % viewed | Swipe-away <3s % | CTR (if shown) | Subs gained | Comments | Decision |
|-------|--------------|-----------|----------|--------------|------------------|----------------|-------------|----------|----------|
| S___  |              |           |          |              |                  |                |             |          | keep/kill/iterate |

=== WEEKLY KPI ROW ===
| Week | Shorts pub | Total views | Median % viewed | Best format | Worst format | Subs +/- | Action next week |
|------|------------|-------------|-----------------|-------------|--------------|----------|------------------|

DECISION RULE (per Short):
  KEEP/DOUBLE-DOWN  if avg % viewed beats channel median AND views > channel median at 48h
                    -> make 2 more in this format/frame next batch
  ITERATE           if avg % viewed is good but views low -> repackage title+cover only (don't remake)
  KILL              if swipe-away <3s is high (>60%) -> the HOOK failed; retire this hook style
  WAIT              if slow starter -> do NOT kill or over-tweak; breakouts often take >a few days
```
```
=== METRICS — WORKED EXAMPLE ===
| Short | Format/frame     | Views 48h | Views 7d | Avg % viewed | Swipe <3s | Subs | Comments | Decision |
|-------|------------------|-----------|----------|--------------|-----------|------|----------|----------|
| S042  | transformation   | 3,100     | 9,400    | 96%          | 41%       | +58  | 22       | KEEP -> +2 next batch |
| S043  | question title   | 480       | 610      | 62%          | 71%       | +3   | 1        | KILL hook (swipe high) |
| S040  | access "Inside X"| 900       | 5,200    | 88%          | 48%       | +19  | 9        | WAIT was slow starter, recovering |
```
Decision-rule grounding: **read the first 24–48h of CTR/AVD vs channel average, double down on what beats it** `[C] (vidIQ, ZKsldrcO_fU)`; **repackage high-AVD low-CTR videos by changing only title+thumbnail** `[C] (vidIQ, rBIeT9iLmnU)`; **don't kill or over-tweak a slow starter** — breakouts often take far longer than a few days `[C] (vidIQ, UCrC5B3Soyc)`; **check analytics weekly, not minute-by-minute** `[C] (Make Money Matt, RsAKa_WN1sU / vidIQ, UCrC5B3Soyc)`; scored against **your own last ~10 videos**, not a universal bar `[C] (vidIQ, SIp7MeYbz8U)`.

---

## 8. End-to-end production SOP

A single run from idea to published Short, tying the templates together.

1. **Pick the idea.** In-niche, mass-appeal shell over the niche core (Trojan horse) `[C] (vidIQ, VLfzk9NlZyI)`. When videos fail, **the problem is almost always the idea** `[C] (Kallaway, i7upRL4H1FM)` — vet it first.
2. **Decide title + cover BEFORE producing** (Template 5) `[C] (Nick Nimmin, kcSOFqJhR9I)`. Titles <60 chars, use a witness/transformation/access frame `[C] (vidIQ, n5NER9cbueY)`.
3. **Write the script** (Template 1): single premise + constraint, hook 0–3s, re-hook ~15s, payoff mirrors hook. 90–110 words. Bullet-driven, hook + outro scripted `[C] (Nick Nimmin, IF-PD6XMjYY)`, never full AI word-for-word `[C] (Nate Black, 9CCmMypN8PM)`.
4. **Build the shot list** (Template 2): per-beat visual, on-screen text, VO line, asset source, duration.
5. **Generate the VO** (§5): pick voice, 2–3 hook takes, 150–170 wpm, pauses at hook/payoff.
6. **Create assets** (§6): Ideogram for text-in-image, Kling/Veo for clips (one action, ≤6s), animate stills over pure text-to-video, stock fallback. Name per scheme. **Clear every rights line** (§6 table) and set the AI-disclosure intent now.
7. **Assemble** (Template 2 order): edit in CapCut, slow push-in at open, keyframe stills 15–20%, no dead air, loop the final shot to the first.
8. **Caption + overlay** (Template 4): auto-caption → hand-correct, karaoke highlight, hook card 0–3s, re-hook card ~15s, all text inside safe zones.
9. **Mix** (§5): duck music to ~−22 dB under VO, target ~−14 LUFS, add SFX on cuts.
10. **QA gate** (Template 6): watch on a phone sound-off then on; first 2s must stop the swipe; no banned openers; nothing in bottom-20%/right-12% UI zones.
11. **Package + publish gate** (Templates 5 + 6): finalize title/cover/description, **set AI disclosure**, **made-for-kids OFF**, confirm **restrictions = none**, verify it's **not a template/script duplicate** of a recent Short.
12. **Schedule** in YouTube Studio (native).
13. **Measure** (Template 8): log at 24–48h and 7d, apply the keep/kill/iterate rule, feed the winning format back into next week's batch (Template 7). Repackage — don't remake — high-AVD/low-CTR Shorts.

**The two invariants for a headless channel:** (a) put **original human input** into every Short — real research, curation, script, story — so you clear the inauthentic/reused-content policies `[T]` and **re-inject human elements** `[C] (vidIQ, Sgav7Bkg36M)`; (b) **never reuse identical title/script templates or repost identical content** across videos or channels `[C] (Romayroh, KbUXzJ55eJk / Wox4Jt_2t6w)`. Everything else is optimization; these two are survival.
