---
date: 2026-08-05
kind: visual-prompts
slug: do-less-sold-as-win-more
stage: 03-visual
version: 2
supersedes: rgs-briefs/2026-08-05-do-less-sold-as-win-more-visual-prompts.md
script: runs/do-less-20260728-190724/02-scripting/artifact.v1.md
concept_brief: runs/do-less-20260728-190724/01-ideation/artifact.v1.md
archetype: A1
visual_system: rgs-briefs/2026-07-28-rgs-debut-visual-system.md
motif_family: tally-of-external-worth
status: complete
---

=== VISUAL PROMPT SHEET — do-less-20260728-190724 · "Youth sports 'do less' advice still keeps score" ===

**Supersedes `runs/do-less-20260728-190724/03-visual/artifact.v1.md` (11 shots).** This sheet adds
**4 new stills** to fix the cut cadence against the finished 54.8s audio, and **re-orders the sheet
into edit order** so the arc Gate C validates is the arc the viewer actually sees. Sport lock,
world lock, both `--sref` codes, and every existing prompt body are carried through **unchanged**.

Sport lock (unchanged): **YOUTH SOCCER.** The measured proof (Visek et al. 2015) surveyed youth
soccer players and the grounding constraint forbids inflating that population, so the present-day
register stays in youth soccer. Ellen Key (1900 Sweden) lives entirely in Register B.

## Renumbering — read before you touch the files

Shots are numbered in **edit order** here, which is not the v1 order. Existing renders keep their
images; only the labels change.

| New # | Beat | Source | Existing file |
|---|---|---|---|
| 1 | Hook | v1 Shot 1 | `Shot 1_HD.png` |
| 2 | Setup | v1 Shot 2 | `Shot 2_HD.png` |
| 3 | Setup | **v1 Shot 5 — moved from Build** | `Shot 5_HD.png` |
| 4 | Setup | v1 Shot 3 | `Shot 3_HD.png` |
| 5 | Build | v1 Shot 4 | `Shot 4_HD.png` |
| 6 | Build | **NEW — render this** | — |
| 7 | Build | v1 Shot 6 | `Shot 6_HD.png` |
| 8 | Build | **NEW — render this** | — |
| 9 | Re-hook | v1 Shot 7 | `Shot 7_HD.png` |
| 10 | Build (stat) | v1 Shot 8 | `Shot 8_HD.png` |
| 11 | Build (stat) | **NEW — render this** | — |
| 12 | Build (stat) | v1 Shot 9 | `Shot 9_HD.png` |
| 13 | Build (stat) | **NEW — render this** | — |
| 14 | Payoff | v1 Shot 10 | `Shot 10_HD.png` |
| 15 | Payoff | v1 Shot 11 | `Shot 11_HD.png` |

**The one structural move:** v1's Shot 5 (the 1900 folk-school classroom) leaves the Build and joins
the **Setup**. In v1 it sat between the two present-day claim cards, which put a Swedish schoolroom
under the line *"more medals like Norway"* — a visual/VO mismatch, and mismatched visuals cause
confusion and retention decay `[C] (Kallaway, i7upRL4H1FM)`. In the Setup it lands on *"a kid's
effort is worth something itself"* over a child bent over work, which is what the image actually
shows. Moving it also frees the Build to alternate registers legally.

WORLD LOCK
  register_a_sport:              youth soccer
  register_a_venue:              a municipal youth soccer complex and clubhouse
  register_a_signature_objects:  goal net, corner flag, soccer ball
  register_a_season_time:        autumn, fading dusk / last light
  register_a_rationale:          the measured proof at the Short's center (Visek 2015) surveyed youth soccer players, so the present-day world must be youth soccer for evidence and image to match
  register_b_thinker:            Ellen Key
  register_b_era_place:          turn-of-the-century Sweden, around 1900 (a reform-era Stockholm study and a Swedish folk-school)
  register_b_locations:          a lamplit writing study, a Swedish folk-school classroom, a north-lit desk
  register_b_artifacts:          brass balance scale, leather ledger, steel-nib pen
  register_b_figure_archetype:   an unnamed Swedish woman reformer in a high-necked charcoal Edwardian dress, face turned into shadow — never a likeness of Ellen Key
  motif:                         the tally of external worth held out of focus behind sharp effort — a trophy-and-medal shelf in Register A, a brass balance scale and leather ledger in Register B

WHOLE-SHORT SETUP
  Aspect ratio:      --ar 9:16
  Register A --sref: SREF-RGS-A-DL01  (harvested this Short; reused across every Register A still)
  Register B --sref: SREF-RGS-B-01    (fixed channel-level painterly signature — do NOT re-harvest)
  Phase ladder:      Hook (0–5.8s) → Setup (5.8–14.1s) → Build/Value (14.1–40.7s, re-hook @ 24.9s visual / 26.0s spoken, stat beat 28.5–40.7s) → Payoff (41.1–47.9s) → Loop/CTA (47.9–54.8s, reuses Shot 1)
  Consistency:       style-lock, both registers. No recurring likeness (anonymous-presence rule), so nothing to `--oref` — which also keeps every render in V8.2 at standard GPU cost rather than falling back to V7 at 2× `[T] (verified 2026-07-26)`.
  Seed discipline:   Shot 1's hero child + blurred trophy shelf shares its seed with Shot 14 and the cover so the child and shelf read as one asset across the loop.
  Notes:             Shots 10–13 back the R10 STAT motion graphic; numbers are composited in `shorts-assembly`, never rendered into a still. Ellen Key is NEVER a quote card.

ARC TABLE (step 3b eyeball pre-check — not parsed by Gate C)
| #  | Beat        | Register | Shot class      | Scale     | Camera height | What changes vs. previous |
|----|-------------|----------|-----------------|-----------|---------------|----------------------------|
| 1  | Hook        | A        | HUMAN-COST      | MID-WIDE  | LOW           | opening hero frame |
| 2  | Setup       | B        | FIGURE          | MID       | EYE           | cut to the 1900 source world, painterly |
| 3  | Setup       | B        | WORLD           | MID-WIDE  | EYE           | pull wide inside 1900 — the schoolroom, a child at work |
| 4  | Setup       | A        | DETAIL          | CLOSE     | EYE           | back to present, tight on the trophy shelf |
| 5  | Build       | A        | ESTABLISHING    | WIDE      | HIGH          | pull wide over the whole complex |
| 6  | Build       | B        | ARTIFACT        | CLOSE     | HIGH          | **NEW** — the "complete child" as a shelf of handiwork, 1900 |
| 7  | Build       | A        | ACTION-ADJACENT | MID       | LOW           | present: a medal podium |
| 8  | Build       | A        | DETAIL          | CLOSE     | EYE           | **NEW** — the scoreboard itself, named by the VO |
| 9  | Re-hook     | B        | ARTIFACT        | MACRO     | OVERHEAD      | one clean "measured" object — the scale |
| 10 | Build(stat) | PLATE    | PLATE           | WIDE      | OVERHEAD      | subject-free plate for the stat graphic |
| 11 | Build(stat) | A        | ACTION-ADJACENT | MID-WIDE  | LOW           | **NEW** — "trying hard" as a scramble of children |
| 12 | Build(stat) | A        | DETAIL          | CLOSE     | EYE           | "trying hard" made physical, single detail |
| 13 | Build(stat) | B        | WORLD           | WIDE      | HIGH          | **NEW** — a yard where nothing is being tallied |
| 14 | Payoff      | A        | HUMAN-COST      | MID       | LOW           | hero child now the only sharp subject |
| 15 | Payoff      | B        | ARTIFACT        | MACRO     | EYE           | the ledger entry — "it counted" |

Registers (PLATE excluded): A B B A A B A A B A A B A B — max run 2 (C3 ok). A=8 / B=6 (C6 ok).
Scales: 5 distinct (C4 ok). Heights: 4 distinct (C5 ok). No consecutive class or scale repeat
(C1/C2 ok). Registers alternate 9 times (C7 ok).

COVER / THUMBNAIL
  Dedicated cover prompt — carried through from v1 unchanged, already rendered as `thumbnail_HD.png`.
  Amber accent word supplied by `shorts-assembly` as overlay (locked: "COUNTED") — never baked in.

```text
documentary sports photography, tight close-up of a determined young youth soccer player mid-effort framed to the right of the frame, jaw set and eyes fixed off-camera, sweat and a smear of pitch mud on one cheek, a soccer ball blurred at the lower edge, a shelf of gold trophies melted into deep bokeh on the far left, dramatic warm amber rim light carving the face from a cold teal-ink background, shallow depth of field on an 85mm lens at f1.8, the left third kept dark and empty for a title overlay, muted palette of teal-ink amber and off-white, crisp skin and fabric texture, fine film grain, DSLR, No Text. --ar 9:16 --raw --s 110 --sref SREF-RGS-A-DL01
```

### Shot 1 — Hook (0–5.8s) · Register A · HUMAN-COST · MID-WIDE · LOW
Changes vs. previous: opening frame.

```text
documentary sports photography, a lone child in a plain training kit practicing keepie-uppies in the fading last light on a municipal youth soccer pitch, a scuffed soccer ball frozen just above the laces, a trophy-and-medal shelf dissolved into deep bokeh on a clubhouse ledge far behind, low three-quarter angle from ankle height looking up, 35mm lens at f1.8, a razor-thin focal plane holding the child sharp while the distant silverware melts to soft blur, warm amber last-light rim against cold teal-grey dusk shadow, desaturated palette of pitch green teal-ink and off-white, fine film grain, DSLR, No Text. --ar 9:16 --raw --s 100 --sref SREF-RGS-A-DL01
```

### Shot 2 — Setup (5.8–8.9s) · Register B · FIGURE · MID · EYE
Changes vs. previous: cut to the 1900 source world — painterly register, a seated reformer at her desk.

```text
muted oil painting in soft candlelit glazes, an unnamed Swedish woman reformer in a high-necked charcoal Edwardian dress seated at a lamplit writing desk in turn-of-the-century Stockholm, her face turned into shadow away from the flame, a steel-nib pen resting mid-sentence on an open manuscript, a brass balance scale and a worn leather ledger sitting unlit at the desk's far edge, a small child's wooden school slate propped against the desk leg, warm lamp glow pooling on the paper and falling to deep umber in the corners, restrained palette of teal-ink shadow amber lamplight and aged parchment, visible brushwork and thin scumbled highlights, a quiet contemplative mood, No Text. --ar 9:16 --s 550 --sref SREF-RGS-B-01
```

### Shot 3 — Setup (8.9–11.5s) · Register B · WORLD · MID-WIDE · EYE
Changes vs. previous: stay in 1900 but pull wide — the schoolroom, a child bent over work; effort as its own worth.

```text
muted oil painting with soft diffuse glazes, a modest turn-of-the-century Swedish folk-school classroom lit by tall north windows, rows of worn wooden desks and slates with a single child bent over work in the middle distance, chalk dust hanging in the pale daylight, a brass balance scale sitting forgotten on the teacher's lectern beside a leather ledger, plaster walls and a birch floor rendered in loose painterly strokes, cool northern daylight balanced against warm wood tones, a restrained palette of teal-ink shadow honeyed wood and chalk white, thick impasto in the highlights and thin washes in the shadows, a calm studious mood, No Text. --ar 9:16 --s 500 --sref SREF-RGS-B-01
```

### Shot 4 — Setup (11.5–14.1s) · Register A · DETAIL · CLOSE · EYE
Changes vs. previous: register returns to present; tight on the trophy shelf — the scoreboard's side of the split.

```text
documentary sports photography, a close view of a crowded clubhouse shelf lined with gold-plastic youth soccer trophies and hanging medals, a curling league-standings printout pinned to the shelf edge, the blurred white of a goal net visible through a window behind, eye-level framing square to the shelf, 100mm lens at f2.8, sharp focus skimming the nearest trophy nameplate while the rest of the row falls away, hard cold teal-grey window light with a thin amber reflection on the brass, muted palette of trophy gold teal-ink and off-white, faint dust and fingerprint texture on the plastic, fine film grain, DSLR, No Text. --ar 9:16 --raw --s 95 --sref SREF-RGS-A-DL01
```

### Shot 5 — Build (14.1–17.0s) · Register A · ESTABLISHING · WIDE · HIGH
Changes vs. previous: pull wide to the whole complex — the backdrop the "complete athlete" claim card composites over.

```text
documentary sports photography, a wide elevated vantage over a municipal youth soccer complex at dusk with several marked pitches receding into haze, a lone corner flag leaning in the near foreground and a distant goal net catching the last light, kit bags and training cones stacked along a quiet touchline, an elevated three-quarter angle looking down across the fields, 24mm lens at f8, deep focus keeping the foreground flag and the far goalposts equally crisp, flat cold teal-grey overcast light with a low amber band on the horizon, a wide desaturated palette of turf green teal-ink and pale amber sky, soft atmospheric haze and fine film grain, DSLR, No Text. --ar 9:16 --raw --s 105 --sref SREF-RGS-A-DL01
```

### Shot 6 — Build (17.0–20.0s) · Register B · ARTIFACT · CLOSE · HIGH
Changes vs. previous: NEW — cut back to 1900 for the "complete child" pitch, made physical as a row of handiwork.

```text
muted oil painting in cool north-light glazes, a schoolroom display shelf holding one child's varied handiwork arranged in a careful row, a whittled wooden bird, a knitted woollen square, a pressed-flower card, a small fired clay bowl, and a folded paper star, a brass balance scale standing at the row's end with both of its shallow pans empty, a closed leather ledger resting on the bench below, seen from slightly above and looking down the length of the row, pale northern daylight sliding along the objects and pooling to umber at the shelf's back edge, a restrained palette of honeyed wood chalk white and teal-ink shade, thin scumbled highlights on the glazed clay against dry stippled wool, a patient orderly mood, No Text. --ar 9:16 --s 540 --sref SREF-RGS-B-01
```

### Shot 7 — Build (20.0–22.6s) · Register A · ACTION-ADJACENT · MID · LOW
Changes vs. previous: present again — a medal podium, the backdrop for the "more medals, like Norway" claim.

```text
documentary sports photography, the moment just after a youth soccer medal ceremony with a small tiered podium and a coach's hands lowering a ribboned medal toward a child's neck, a soccer ball tucked under one arm and a corner flag blurred at the pitch edge behind, a low angle from just below podium height looking up, 50mm lens at f4, natural focus on the medal and ribbon with the small crowd softened away, warm amber floodlight against cool teal-grey evening air, a muted palette of medal gold teal-ink and off-white, a faint sweat-sheen and woven-fabric texture, fine film grain, DSLR, No Text. --ar 9:16 --raw --s 100 --sref SREF-RGS-A-DL01
```

### Shot 8 — Build (22.6–24.9s) · Register A · DETAIL · CLOSE · EYE
Changes vs. previous: NEW — the scoreboard the VO literally names, isolated as the thing doing the arguing.

```text
documentary sports photography, a close view of a portable youth soccer scoreboard propped at the touchline with its plastic number cards caught half-flipped mid-change, a scuffed soccer ball resting against the frame's foot, the white mesh of a goal net thrown far out of focus behind it, eye-level framing square to the board's weathered face, 90mm lens at f3.2, crisp focus skimming the nearest digit while the far edge of the panel falls away, hard cold teal-grey overcast light with a thin amber glint along the metal bracket, a muted palette of weathered white teal-ink and pale amber, chipped enamel and rain-spotting texture across the plastic, fine grain, DSLR, No Text. --ar 9:16 --raw --s 95 --sref SREF-RGS-A-DL01
```

### Shot 9 — Re-hook (24.9–28.5s) · Register B · ARTIFACT · MACRO · OVERHEAD
Changes vs. previous: from the noisy claim cards to one clean "measured" object — an overhead macro of the balance scale.

```text
muted oil painting in crisp still-life glazes, an overhead study of an antique brass balance scale resting in perfect equilibrium on a dark writing desk, one shallow pan holding a child's small chalk slate and the other pan left empty, an open leather ledger and a steel-nib pen laid neatly beside the scale, a single dried flower stem lying across the ledger's page, warm lamplight raking low across the brass to catch every scratch and dent, deep umber shadow pooling around the base, a restrained palette of aged brass teal-ink shadow and parchment cream, meticulous fine brushwork on the metal against a softly blended ground, a still contemplative mood, No Text. --ar 9:16 --s 620 --sref SREF-RGS-B-01
```

### Shot 10 — Build (28.5–31.5s) · Register PLATE · PLATE · WIDE · OVERHEAD
Changes vs. previous: subject-free motion-graphic plate for the R10 stat build (81 → 11, "Trying Hard" #1).

```text
a subject-free abstract background plate in deep teal-ink, a smooth vertical gradient from near-black at the base to muted teal at the top, a faint grid of thin off-white lines suggesting a quiet data field, a soft amber glow blooming low-left where an accent number will later sit, gentle film-grain texture and a barely-there paper fibre, no people, no animals, no creatures, even negative space held clear across the middle third for composited figures, subtle vignetting drawing the eye to the centre, a restrained palette of teal-ink amber and off-white, a matte finish with no glare, No Text. --ar 9:16 --raw --s 150 --no people
```

### Shot 11 — Build (31.5–34.6s) · Register A · ACTION-ADJACENT · MID-WIDE · LOW
Changes vs. previous: NEW — "trying hard" as visible collective effort, before the single-detail close.

```text
documentary sports photography, four children in mismatched training bibs straining after the same loose ball in a small-sided youth soccer game on a worn municipal pitch, legs bent mid-stride and breath showing in the cold air, a leaning corner flag and a sagging goal net closing the far edge of play, a low angle from just above the turf looking up into the scramble, 50mm lens at f4.5, natural focus holding the nearest two children while the others soften away, flat cold teal-grey dusk light with a low amber band behind the treeline, a muted palette of pitch green teal-ink and off-white, scuffed turf and damp jersey texture, fine grain, DSLR, No Text. --ar 9:16 --raw --s 105 --sref SREF-RGS-A-DL01
```

### Shot 12 — Build (34.6–37.8s) · Register A · DETAIL · CLOSE · EYE
Changes vs. previous: the "trying hard" factor narrowed to one physical detail after the wider scramble.

```text
documentary sports photography, a clean close study of a child's mud-caked youth soccer cleat planted in wet grass mid-effort with turf and water flicking up around the studs, a soccer ball half in frame catching the low light, the white of a goal net reduced to a soft wash far behind, eye-level framing low to the ground, 105mm lens at f2.5, sharp focus on the flexing laces and the straining ankle, cool overcast teal-grey light with a faint warm edge, a muted palette of grass green teal-ink and off-white, crisp water-droplet and wet-mud texture, fine film grain, DSLR, No Text. --ar 9:16 --raw --s 95 --sref SREF-RGS-A-DL01
```

### Shot 13 — Build (37.8–41.1s) · Register B · WORLD · WIDE · HIGH
Changes vs. previous: NEW — a world where the game carries no tally at all; lands "winning wasn't one of the eleven."

```text
muted oil painting with broad diffuse glazes, a walled folk-school yard in turn-of-the-century Sweden where a dozen children play a loose running game across packed earth, pinafores and knee socks caught mid-motion, a birch fence and a low red timber schoolhouse closing the far side of the yard, an empty brass balance scale and a shut leather ledger left forgotten on a bench in the near corner, an elevated vantage looking down across the whole yard, thin autumn sunlight falling flat and even with long soft shadows reaching toward the fence, a restrained palette of packed-earth ochre birch grey and teal-ink shade, loose painterly strokes in the running figures against a thinly washed ground, an unhurried unsupervised mood, No Text. --ar 9:16 --s 480 --sref SREF-RGS-B-01
```

### Shot 14 — Payoff (41.1–44.9s) · Register A · HUMAN-COST · MID · LOW
Changes vs. previous: return to the hero child, now the only sharp subject; the trophies recede further.

```text
documentary sports photography, the same lone child on the youth soccer pitch now turned toward the lens catching a breath after effort with the chest rising, a soccer ball settling at their feet, the distant trophy shelf reduced to an almost-gone smear of gold in deep background blur, a low angle from knee height looking up to lend the child weight, 35mm lens at f2, a tight focus wrapping the child while everything behind dissolves, warm amber last-light rim against cool teal-grey dusk, a quiet palette of pitch green teal-ink and off-white, soft skin and worn-cotton texture, fine film grain, DSLR, No Text. --ar 9:16 --raw --s 110 --sref SREF-RGS-A-DL01
```

### Shot 15 — Payoff (44.9–47.9s) · Register B · ARTIFACT · MACRO · EYE
Changes vs. previous: the reframe's proof object — a hand entering a single line in the ledger, the balance settling level.

```text
muted oil painting in warm candlelit glazes, a close eye-level study of a weathered hand pressing a steel-nib pen to a single fresh line in an open leather ledger, the brass balance scale beside it just tipping level, lamplight catching the wet ink and the ledger's gilt edge, the rest of the desk sinking into umber shadow, a child's chalk slate resting half-seen at the frame edge, a restrained palette of ink black aged brass and warm parchment amber, delicate fine brushwork on the pen nib against a soft blended darkness, a faint teal-ink cast held in the deepest shadow, an intimate resolved mood, No Text. --ar 9:16 --s 580 --sref SREF-RGS-B-01
```

LOOP / CTA (47.9–54.8s) — no new still.
  Reuse Shot 1's hero still (same asset, same locked seed) for a seamless match-back loop. In the
  edit, run the Hook's slow push-in in reverse — a gentle pull-back to the exact Shot 1 framing —
  so the last frame equals the first. Handled in `shorts-assembly`, not a separate generation.

I2V PROMPTS (motion rationed to Hook + Payoff climax per the shared visual system)
| Beat | Source still | Target tool | I2V prompt | Start/end-frame notes |
|---|---|---|---|---|
| Hook (Shot 1) | Shot 1 | Midjourney `--motion low` — the move is a few-percent breathing push-in, exactly the "hero still should breathe slightly" tier; MJ's own i2v (D-tier, jittery) is acceptable at this low amplitude. **`shorts-assembly` has elected to do this with editor keyframes instead**, which is cleaner and makes the Loop's pull-back an exact inverse. Prompt retained if that call is revisited. | Start on a low three-quarter view of the lone child mid keepie-uppie on the youth soccer pitch, trophy shelf soft behind. Very slowly push the camera in a few percent toward the child in a single shot, no cuts. Keep the child sharp and the distant trophies in soft blur throughout. Slow, smooth, almost imperceptible motion. No subtitles and no music. | Single frame, no end-keyframe needed. Reverse this same move in the edit to build the Loop/CTA pull-back. |
| Payoff (Shot 14) | Shot 14 | Kling — A-tier sharpness and strong prompt adherence, best for a controlled start/end-frame rack-focus the still can't sell. | Start on a low medium shot of the same child on the youth soccer pitch, breath rising, a soccer ball at their feet, the distant trophy shelf a faint gold blur behind. Slowly rack the focus fully onto the child while the trophy shelf dissolves further into nothing, and let the amber last light rise a touch on the child's face, in a single shot, no cuts. Slow, continuous, gentle motion. No subtitles and no music. | End frame: the child fully sharp, trophy shelf gone to near-black blur, warm rim light peaked. Produce it by editing the Shot 14 still in an external image editor so start and end frames are variations of one image. |

OVERLAY COPY HANDOFF (kept out of every Midjourney prompt — Midjourney can't render legible text `[C] (Tokenized AI, qFYJb0zYztY)`; composited in `shorts-assembly`)
  - Hook lower-third: "Ellen Key · Swedish reformer · 1900" — plain lower-third + spoken attribution
    ONLY. NEVER a quote/quotation card (paraphrase-caution, grounding constraint 1). Keep all
    corporal-punishment context out entirely.
  - Setup (Shots 2–3): no card needed — the Register B figure and schoolroom carry the attribution.
  - Build claim cards, each visibly STAMPED as a claim being sold, not a fact:
      • over Shot 5: "'A complete athlete'" — quotation marks + a small clay `#C1543A` "the pitch" tag
      • over Shot 7: "'More medals — like Norway'" — same sold-claim treatment
    Clay is for the framing of "the system / the pitch" only, never on the child or parent.
      • Shot 6 (NEW) carries **no card** — it is the visual rebuttal to the "complete" pitch and
        works silently; a card here would over-explain it.
      • Shot 8 (NEW) carries **no card** — the VO names the scoreboard as the image shows it.
  - STAT motion graphic (Shots 10 → 11 → 12 → 13), built up on screen so viewers SEE the number:
      1) over Shot 10: "2015 George Washington University study · youth soccer players"
      2) over Shot 10: "81 things that make sport fun  →  11 core factors"
      3) over Shot 11→12: accent (amber ALL-CAPS) "TRYING HARD — #1"
      4) over Shot 13: "Winning: not in the top 11  (~40th of 81)"
    Guardrails carried verbatim: association, not causation; scope is youth soccer players (n=142) +
    coaches + parents — don't inflate to "kids in sport"; ship "effort ranked first; winning wasn't
    in the top tier," NEVER "kids don't care about winning."
  - Re-hook caption (from 26.0s): "Someone actually measured what kids want."
  - AI disclosure (Shot 14 window): "AI-generated visuals · synthetic voiceover" — off-white, never amber.
  - Payoff caption: "It counted the day he gave it." (accent word: "COUNTED")
  - Loop/CTA: end card + pinned-comment pointer to Short B "nobody-asked-the-kid"; comment-bait:
    "What's a 'do less' tip you were handed that still promised a better result?"
  - Villain framing (constraint 4): the villain is the theory of value / the system, never the parent
    — end on relief and agency. The reframe resolves on the child's present worth and is never
    re-justified with an outcome (constraint 3).

VALIDATION
  Gate A (midjourney-prompting syntax lint): PASS — all four new prompts authored to the 9-layer
    body + V8.2 band contract; no quality buzzwords; Register A carries `--raw` with `--s` in
    80–120 and concrete optics plus the DSLR realism cue; Register B carries no `--raw`, `--s` in
    400–700, and no optics vocabulary of any kind; every prompt is one line ending "No Text."
    immediately before its flags; no stray punctuation inside any parameter block.
  Gate B (adversarial art direction): n/a — stage is `production` for the 11 carried-through shots
    (already rendered and accepted) and `draft` for the four new ones. Run Gate B before escalating
    any new shot to `--hd`.
  Gate C (scripts/lint_prompt_sheet.py): **PASS — 15 shots, 0 findings** (run 2026-08-05).

    v1 of this sheet reported `PASS — 14 shots`: the PLATE heading was written
    `· PLATE · PLATE ·` instead of `· Register PLATE · PLATE ·`, and the parser's
    `SHOT_HEADING_RE` requires the literal word `Register` before `A|B|PLATE`. A heading the
    parser can't match is **silently skipped**, so Shot 10 never entered the sheet and the gate
    passed on 14 of 15 shots. Fixed here.

    **The same defect is present upstream** in `runs/do-less-20260728-190724/03-visual/artifact.v1.md`,
    whose PLATE heading (its Shot 8) has the identical form — so that sheet's recorded
    "Gate C: PASS" was a pass over 10 of its 11 shots, not 11. Worth correcting there before it
    propagates to another Short.
