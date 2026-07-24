# Pacing & editing rules

Provenance: `[C]` corpus-cited `(Channel, video_id)` · `[I]` industry practice · `[T]` web-verified 2026-07-23, re-verify. See `docs/README.md` for the full key.

## Beat timing (from the script, carried into the edit)

The script (from `shorts-scripting`) already fixes beat boundaries; the edit plan inherits them and adds shot-level cut timing inside each beat. Target ~35–45s Short, 90–110 words `[I]` (`docs/headless-shorts-production-playbook.md` §2):

| Beat | Seconds | Job |
|---|---|---|
| Hook | 0–3s | Stop the swipe — visual hook reads before a word is spoken `[C] (vidIQ, DiZnbihU4NM)` |
| Setup | 3–8s | One sentence of context + stakes |
| Build/Value | 8–28s | Escalating steps; re-hook beat at ~15s `[C] (Nate Black, c6X-Ywy3yVU)` |
| Payoff | 28–38s | Resolve the hook's question |
| Loop/CTA | 38–45s | Mirror the hook line so the edit loops `[C] (Jenny Hoyos, mhVDcqnxxaY)` |

For a punchier 20–30s Short, compress Setup to one clause and Build to ~30 words `[I]`.

## Cut cadence

- **Change the on-screen visual every ~3 seconds; never hold one image/clip too long** — strongly-supported `[C] (Make Money Matt, HopTPCLbiiM)`. This is the single hardest numeric constraint on the shot list: at ~3s/cut, a 40s Short is roughly 12–14 shots.
- **Match the visual to what's being said sentence-by-sentence**, or show plain footage with no overlay — a mismatched visual causes confusion and retention decay `[C] (Kallaway, i7upRL4H1FM)`.
- **A static frame is "the visual equivalent of dead air"** `[C] (vidIQ, DiZnbihU4NM)`. Every shot needs either cut motion or an in-shot keyframe move (see below).
- **Slow push-in of a few percent at the open** signals "something's coming" `[C] (vidIQ, DiZnbihU4NM)`; **keyframe still images to scale 15–20%** (playbook: 15–20%; audit: ~110–120%, i.e. the same ~10–20% range) to keep the screen alive `[C] (vidIQ, DiZnbihU4NM)`, applied **mostly on early scenes** for a premium feel `[C] (One Person Business, eVePkmCQV5c)`.
- **Turn spoken stats and lists into on-screen motion graphics** so viewers see the number, not just hear it `[C] (vidIQ, i5bZ-Be9cAQ)`.

## Don't over-edit (strongly-supported, audit §6)

- **Flashbangs, stacked overlays, and constant jump cuts exhaust overstimulated viewers; comprehension comes from deleting edits, not adding them** — rawer/simpler editing reads as more authentic and less AI `[C] (Kallaway, i7upRL4H1FM; Nate Black, J8LrrCpDNJI)`.
- **Do not chase wall-to-wall stimulation and constant jump cuts to fake retention** `[C] (vidIQ, DiZnbihU4NM)`. This directly bounds the ~3s cut rule above: cut on beat, not faster, and don't add cuts that don't carry information.
- **Match editing pace to the audience** — fast cuts for younger audiences, slower for older/learning viewers `[C] (Nick Nimmin, LAzYEKltBwA)`.
- **Retention spikes when you deliver real value (a clear demonstration), which beats any jump cut** `[C] (vidIQ, DiZnbihU4NM)`. If a beat is carrying the payoff, resist the urge to add cuts there just to look busy.

## Muted-viewer optimization & authenticity (audit §4, "Delivery & format")

- **Optimize for the ~80–85% who watch muted** — text and visuals must carry the context on their own, independent of the VO `[C] (Kallaway, i7upRL4H1FM)`. Every beat's caption/overlay must be legible as a silent-film substitute for the line.
- **Leave small imperfections/filler in the cut to feel human, not AI** `[C] (Nick Nimmin, IF-PD6XMjYY)` — don't over-polish away every rough edge in the assembly pass.
- **Engineer authenticity as "Reality + Performance"**: keep real moments but emphasize the best ones; capture/generate more material than you need and don't over-cut down to only the highest-retention instants `[C] (Nate Black, amHDyPaZ_JE; Nate Black, 72-ahy9bYk4)`. `[I]` Applying this to an AI-asset pipeline (the corpus doesn't state this specific translation): generate 1–2 spare takes per shot (extra image variants, extra clip seconds) so the edit has real selection room, rather than cutting the single generation you got.
- **A faceless channel substitutes a visual-demonstration layer for on-camera energy** `[C] (Nate Black, UjeOJb6lk5M)` — every Build/Value shot should show the mechanism, not just illustrate mood.

## AI-video budget discipline (audit §6)

- **Spend premium/expensive AI-video generation only on the hook/intro and occasional cutaway spikes; generate the bulk cheaply or from stock**, and test compositions on a cheap low-res model before spending on a top-tier one `[C] (Make Money Matt, gkaxBe8BGLQ)`. `[I]` Applying this beat-by-beat (the corpus states the principle, not this specific mapping): mark the Hook shot (and any single "wow" cutaway) as the one place to spend the paid-tier video-gen budget; Build/Setup/Loop shots default to stills, stock, or the cheap tier.
- **AI still fails at pure B-roll generation / thumbnails due to an uncanny-valley look** — drop to stock (Pexels/Pixabay/Mixkit/Storyblocks/Artgrid) when a generated clip looks off, and prefer animating a good still over pure text-to-video `[C] (Nate Black, 9CCmMypN8PM; vidIQ, 9z1ACpWW9do)`.
- **Style-mix a visual style from a different niche; intercut real stock footage for concrete objects** `[C] (One Person Business, VqM3xrIHmi0)`.

## Gap flag

The corpus has no findings on current YouTube Shorts duration-eligibility limits (e.g. whether Shorts can run longer than 60s/3min) — this is a live YouTube policy fact outside the 420-video corpus and outside the 2026-07-23 `[T]` tool-note sweep. Verify current Shorts length eligibility on YouTube's own help pages before locking a runtime past the ~45s the templates assume.
