# Worked example: a scripted Short → a dual-register Midjourney prompt sheet

This walks a real `letkidsplay`-style RaisingGoodSports Short — a five-beat script pairing a
present-day club-soccer claim with a Plutarch citation — through every step of `SKILL.md`'s
workflow, in order, ending in a sheet that passes Gate C on this file's own first successful run
(see §9). Read this after `references/visual-registers.md` and `references/visual-arc.md` — it
assumes both are already understood and shows them applied, not re-explained.

## 1. Input (from the script)

| # | Beat | Dur | VO line | Markers |
|---|---|---|---|---|
| 1 | Hook | 0–3s | "Club soccer costs $5,000 a year and takes every weekend your kid has." | — |
| 2 | Setup | 3–9s | "Here's who told parents this was fine 2,000 years before travel teams existed..." | `[THINKER: Plutarch]` |
| 3 | Build | 9–30s | "Plutarch watched Athenian fathers push their sons into one sport, year-round, before the boy had a say. He called it planting a tree and drowning the roots — you get growth, then you get nothing." | `[RESEARCH: early-specialization burnout attrition]` |
| 4 | Re-hook | 30–34s | "The travel-team pipeline is doing the same thing his neighbors did — just with a scoreboard." | — |
| 5 | Payoff/Loop | 34–45s | "Water the roots, not just the branch. Let the kid play more than one sport." | — |

## 2. Step 2 — shot counts, applying the ~3s cadence rule `[C] (Make Money Matt, HopTPCLbiiM)`

- **Hook (3s):** 1 shot — already at the cadence limit.
- **Setup (6s):** 2 shots — the present-day claim, then the register switch that introduces the
  source era.
- **Build (21s):** 21s ÷ ~3–4s ≈ 5 shots — the longest beat, carrying both the burnout evidence
  and its period illustration, so it's the one beat that earns the full register alternation.
- **Re-hook (4s):** 1 shot — back to the present for the pivot line.
- **Payoff/Loop (11s):** 2 shots — the motif's present-day and source-era close, mirroring the
  loop technique `[C] (Jenny Hoyos, mhVDcqnxxaY)` without literally reusing a still, since the
  motif itself (not a repeated frame) is what closes the loop here.

Total: **11 shots.**

## 3. Step 2.5 — the world lock

```
WORLD LOCK
  register_a_sport:              club soccer
  register_a_venue:              municipal club soccer complex
  register_a_signature_objects:  goal net, corner flag, painted touchline
  register_a_season_time:        winter dawn
  register_a_rationale:          club soccer's $5,000/yr fees, no free weekends, and scholarship-chase culture are the closest present-day analogue to the claim's burnout evidence
  register_b_thinker:            Plutarch
  register_b_era_place:          first-century Greece, a hillside estate near Chaeronea
  register_b_locations:          colonnaded terrace, olive-terraced hillside, stone courtyard
  register_b_artifacts:          terracotta watering vessel, wax writing tablet, olive branch
  register_b_figure_archetype:   an unnamed tutor, plain wool himation, face turned into shadow
  motif:                         a watering can, modern plastic in Register A and a terracotta vessel in Register B
```

Sport-choice check, in order (`references/visual-registers.md` §8): the incoming script doesn't
name a sport, the concept brief doesn't either, but the grounding artifact's `[THINKER: Plutarch]`
citation and its burnout research supply both the thinker and a clear economic parallel — club
soccer's cost-and-time structure is what makes the $5,000/yr framing land, so it's named here with
that one-line rationale rather than picked for its visuals alone `[I]`.

## 4. Step 3a — consistency

Two `--sref` codes, one per register, per `references/visual-registers.md` §3–§4:

- **Register A `--sref`:** harvested for this Short specifically (present-day club-soccer look).
- **Register B `--sref`:** the channel's fixed painterly signature, harvested once and reused
  unchanged on every Short — not re-harvested here.

No `--oref` on either register: Register A has no recurring named character to lock a likeness
for, and Register B's figure treatment is archetype-only by contract (unnamed, face averted or
shadowed, dressed to the role) — there is no likeness to lock, and adding one would force the
whole job into V7 at 2× GPU cost for no visual gain `[T] (verified 2026-07-26)`.

## 5. Step 3b — the arc table

| # | Beat | Register | Shot class | Scale | Camera height | What changes vs. previous |
|---|------|----------|------------|-------|----------------|----------------------------|
| 1 | Hook (0–3s) | A | DETAIL | MACRO | LOW | opening frame |
| 2 | Setup (3–6s) | A | ESTABLISHING | XWIDE | HIGH | pulls back from macro to the whole complex; register stays present |
| 3 | Setup (6–9s) | B | WORLD | WIDE | EYE | register switch to the source era; scale and height both change |
| 4 | Build (9–14s) | B | ARTIFACT | CLOSE | OVERHEAD | register stays but shot class, scale and height all change; motif appears in source-era form |
| 5 | Build (14–18s) | A | HUMAN-COST | MID | LOW | register switch back to the present; shot class, scale and height all change |
| 6 | Build (18–22s) | A | ACTION-ADJACENT | MID-WIDE | EYE | shot class, scale and height all change; stillness shifts to just-before motion |
| 7 | Build (22–26s) | B | FIGURE | MID | EYE | register switch to the source era; shot class and scale both change |
| 8 | Build (26–30s) | B | WORLD | XWIDE | HIGH | shot class, scale and height all change; widest frame on the sheet |
| 9 | Re-hook (30–34s) | A | ESTABLISHING | WIDE | HIGH | register switch back to the present; shot class and scale both change |
| 10 | Payoff (34–40s) | A | DETAIL | MACRO | LOW | shot class, scale and height all change; motif returns in present-day form |
| 11 | Payoff/Loop (40–45s) | B | ARTIFACT | CLOSE | OVERHEAD | register switch to the source era; motif closes the loop in source-era form |

By-eye check against `references/visual-arc.md` §4–§7 before a single prompt string was written:

- **Scales used:** `MACRO, XWIDE, WIDE, CLOSE, MID, MID-WIDE` — 6 distinct, well over the 3 Gate
  C's C4 requires, and no two consecutive rows repeat a scale.
- **Camera heights used:** `LOW, HIGH, EYE, OVERHEAD` — 4 distinct, over C5's minimum of 2.
- **Shot classes:** no two consecutive rows repeat a shot class (C1); Register A visits all four
  of its classes (`ESTABLISHING`, `ACTION-ADJACENT`, `DETAIL`, `HUMAN-COST`) and Register B visits
  all three of its classes (`FIGURE`, `WORLD`, `ARTIFACT`) — nothing leans on one shot class.
- **Register rhythm:** `A A B B A A B B A A B` — no run longer than 2 (C3), registers alternate 5
  times (well over C7's minimum of 2), and counts land at 6 Register A / 5 Register B, both above
  C6's minimums.
- **The motif bridge:** the watering can appears exactly twice — Shot 4 (`ARTIFACT`, terracotta,
  Register B) and Shot 10 (`DETAIL`, modern plastic, Register A) — carrying the same idea across
  both visual languages per `references/visual-registers.md` §6, without the two shots reading as
  the same frame.

This table is what made Gate C pass on the first run against the finished prompts (§9) — the
sequencing decisions were made here, at the table stage, not discovered after nine or eleven
Midjourney jobs had already rendered (`references/visual-arc.md` §1).

## 6. Step 4 — the per-shot blocks

Each block below is exactly what was handed to `midjourney-prompting` (subject, register,
shot_class, look, format, consistency) and exactly what came back — not rewritten here. Every
prompt carries all 9 layers, at least 10 comma-separated clauses, at least 60 words, and ends
`No Text.` immediately before its flags, on a single line, per `references/prompt-sheet-format.md`.

```
### Shot 1 — Hook (0–3s) · Register A · DETAIL · MACRO · LOW
Changes vs. previous: opening frame.

```text
documentary sports photography, extreme close-up of a nine-year-old's fingers lacing a club soccer boot tight against a frost-stiffened tongue, breath fogging faintly at the very edge of frame, a corner flag blurred to a soft orange smear behind the wrist, a scuffed size-one ball resting just outside sharp focus, low three-quarter angle from just above the turf, 100mm macro lens at f/2.8, razor focus on the laces and the slack skin around the knuckle, flat grey pre-dawn light with no direct sun, cold desaturated palette of frost white and charcoal, fine visible grain, No Text. --ar 9:16 --raw --s 95
```

### Shot 2 — Setup (3–6s) · Register A · ESTABLISHING · XWIDE · HIGH
Changes vs. previous: pulls back from macro to the whole complex; register stays present.

```text
documentary sports photography, an elevated wide view over a municipal club soccer complex at first light, six floodlit pitches receding toward a distant tree line, a goal net and a row of corner flags anchoring the nearest field, parents' cars queued along a gravel access road at the far edge, high angle from a scoreboard gantry, 24mm wide lens at f9, deep focus holding every pitch legible, cold blue winter dawn light with frost still on the grass, muted green and slate palette under a colourless sky, No Text. --ar 9:16 --raw --s 100
```

### Shot 3 — Setup (6–9s) · Register B · WORLD · WIDE · EYE
Changes vs. previous: register switch to the source era; scale and height both change.

```text
luminous oil painting on aged linen, a colonnaded terrace on a hillside estate near Chaeronea opening onto a sun-bleached olive-terraced slope, worn limestone steps descending toward a stone courtyard below, a lone olive branch resting across the nearest column base, a shallow clay basin set on the topmost step, distant hills softening into a pale haze, frontal wide view from the level of the terrace floor, warm low Mediterranean sun raking in from the left casting long hard shadows, ochre and umber and olive-green palette, cracked varnish and visible brush texture, No Text. --ar 9:16 --s 520
```

### Shot 4 — Build (9–14s) · Register B · ARTIFACT · CLOSE · OVERHEAD
Changes vs. previous: register stays but shot class, scale and height all change; the motif appears in its source-era form.

```text
luminous oil painting on aged linen, a terracotta watering vessel tipped over a shallow clay basin on a sun-warmed stone ledge, water spilling past the rim and darkening the dust in a widening stain, a wax writing tablet and a stylus set just beyond the spreading water, a single olive leaf drifting on the surface, close overhead view looking straight down onto the ledge, compressed flat composition with almost no horizon, warm afternoon light pooling from the upper left, ochre and terracotta and deep green palette, thick impasto ridges catching the light, No Text. --ar 9:16 --s 560
```

### Shot 5 — Build (14–18s) · Register A · HUMAN-COST · MID · LOW
Changes vs. previous: register switch back to the present; shot class, scale and height all change.

```text
documentary sports photography, a lone child sitting on a metal bench at the edge of a frost-bitten club soccer pitch, head down, gear bag untouched on the painted touchline beside them, other kids and parents blurred and distant near the goal net, low angle from bench height looking slightly up at the hunched shoulders, 35mm lens at f2, shallow depth isolating the child from the field behind, thin grey overcast light with no warmth in it, cold flat palette of slate and dull green, No Text. --ar 9:16 --raw --s 90
```

### Shot 6 — Build (18–22s) · Register A · ACTION-ADJACENT · MID-WIDE · EYE
Changes vs. previous: shot class, scale and height all change; the moment shifts from stillness to just-before motion.

```text
documentary sports photography, a club soccer coach crouching beside a line of cones handing a water bottle to a waiting player, a corner flag catching a gust just behind them, cleats and shin guards scattered on the painted touchline nearby, a stack of folded practice bibs set on the grass to one side, eye-level three-quarter view from pitch side, 50mm lens at f4, moderate depth holding both figures and the cones legible, a thin shaft of morning sun breaking through low cloud, palette warming from cold slate toward pale gold, No Text. --ar 9:16 --raw --s 105
```

### Shot 7 — Build (22–26s) · Register B · FIGURE · MID · EYE
Changes vs. previous: register switch to the source era; shot class and scale both change.

```text
luminous oil painting on aged linen, an unnamed tutor in a plain wool himation seated on a low stone bench in a quiet courtyard, one hand resting on a closed wax writing tablet, face turned fully into shadow beneath a raised hood of fabric, an olive branch propped against the bench leg, a stylus laid across the tablet's edge, mid-distance frontal view holding the whole seated figure, soft diffused daylight falling from a high unseen window, muted ochre and umber palette against pale stone, visible canvas weave through thin glaze, No Text. --ar 9:16 --s 480
```

### Shot 8 — Build (26–30s) · Register B · WORLD · XWIDE · HIGH
Changes vs. previous: shot class, scale and height all change; widest frame of the whole sheet.

```text
luminous oil painting on aged linen, a sweeping view down over the olive-terraced hillside toward a distant stone courtyard and the colonnaded terrace beyond, rows of silvered olive trees stepping down the slope in soft ranks, a thin footpath cutting between the terraces, a hawk suspended small and distant over the valley, a low stone wall marking the nearest terrace edge, elevated view looking down from above the topmost terrace, warm hazy midday light flattening the distance, sage green and dusty gold and pale stone palette, loose confident brushwork in the foreground foliage, No Text. --ar 9:16 --s 610
```

### Shot 9 — Re-hook (30–34s) · Register A · ESTABLISHING · WIDE · HIGH
Changes vs. previous: register switch back to the present; shot class and scale both change.

```text
documentary sports photography, a wide elevated view across a single club soccer pitch at first light, a goal net and corner flag anchoring the nearest end, a scattered line of kit bags along the painted touchline, a knot of children jogging a slow warm-up lap near the centre circle, high angle from the top of a low spectator bank, 24mm wide lens at f8, even focus holding the whole pitch sharp, cold flat winter-dawn light with long low shadows, cool green and grey palette under a pale sky, No Text. --ar 9:16 --raw --s 100
```

### Shot 10 — Payoff (34–40s) · Register A · DETAIL · MACRO · LOW
Changes vs. previous: shot class, scale and height all change; the motif returns in its present-day form.

```text
documentary sports photography, extreme close-up of a small plastic watering can tipped against a row of potted marigolds beside a club soccer clubhouse doorway, water beading on a stack of folded team bibs just behind it, a corner flag leaning against the wall further back and slightly out of focus, low angle from just above the concrete step, 100mm macro lens at f2.8, razor focus on the spout and the falling water, cold flat winter-dawn light with a faint blue cast, muted plastic-blue and marigold-orange palette, fine visible grain, No Text. --ar 9:16 --raw --s 95
```

### Shot 11 — Payoff/Loop (40–45s) · Register B · ARTIFACT · CLOSE · OVERHEAD
Changes vs. previous: register switch to the source era; the motif closes the loop in its source-era form.

```text
luminous oil painting on aged linen, a terracotta watering vessel resting empty on a low stone courtyard wall, a scattering of olive leaves and a coiled length of cord beside it, faint dark water-staining still visible on the stone beneath the vessel's mouth, a single wax writing tablet propped just out of frame at the wall's edge, close overhead view looking straight down onto the wall, compressed flat composition with the vessel centred, cooling late-afternoon light pooling from the upper right, terracotta and pale stone and olive-green palette, thick impasto ridges along the vessel's rim, No Text. --ar 9:16 --s 540
```
```

## 7. Step 5 — the i2v decision

Running the decision table from `references/image-to-video.md` against each beat: every shot here
is either an establishing/detail/artifact/figure frame that reads fully as a still, or a
just-before-action beat (Shot 6) that deliberately sidesteps needing real motion in the first
place (`references/visual-registers.md` §3's `ACTION-ADJACENT` class exists precisely to avoid the
AI-video uncanny-valley problem `[C] (Nate Black, 9CCmMypN8PM)`). Nothing in this sheet needs a
real animated clip — but the motif overflow originally planned for a coffee-Short i2v beat is kept
here in updated form as a worked illustration of the i2v inheritance rule
(`references/prompt-sheet-format.md` §8): if the watering vessel in Shot 11 were instead animated
as it tips and settles, the i2v prompt would stay entirely in Register B's painterly vocabulary,
inheriting the still's medium end to end:

```
I2V PROMPT — Shot 11 overflow (illustrative, not required by this sheet)

Source still:        Shot 11 (terracotta watering vessel resting on a stone courtyard wall)
Target tool:          Kling — start/end-frame keyframing suits a single continuous settling
                      motion; Seedance's multi-shot strength isn't needed for one static object
Start frame:          Shot 11 (as generated)
End frame:            the same vessel tipped slightly further, a thin new trickle of water
                      just beginning to darken the stone — produced by editing the Shot 11 still
                      in an external image editor, not a second generation
I2V prompt text:      the terracotta vessel on the stone wall tips slightly further, a thin
                      trickle of water spilling and darkening the stone beneath the rim; slow,
                      continuous motion, painterly light holding steady; in a single shot, no
                      cuts; no subtitles and no music.
```

Register B's vocabulary-disjunction rule (`references/visual-registers.md` §2) governs this i2v
prompt exactly as it governs the still: no camera/lens language, no `DSLR`, nothing that would pull
the clip back toward Register A's photographic look.

## 8. Step 6 — the cover decision

The packaging direction (a stopped, disappointed present-day beat vs. an ancient claim that
predates it) is already fully delivered by Shot 1's DETAIL still — a child's hands lacing a boot
in the cold, tight and specific. Nothing about it calls for a separately staged cover shot, so:
**Cover = Shot 1's still + `shorts-assembly`'s text overlay. No separate generation.**

## 9. Step 7 — Gate A / Gate B / Gate C results

- **Gate A** (`midjourney-prompting`'s syntax lint): pass — every flag block carries `--ar 9:16`,
  the correct register-band `--s` value, `--raw` present only on Register A shots, and no stray
  punctuation inside the parameter block.
- **Gate B** (upstream visual-quality check): pass — no upstream quality flags applied to this
  Short.
- **Gate C** (`scripts/lint_prompt_sheet.py`): run against the sheet exactly as emitted above
  (extracted verbatim into `tests/fixtures/worked_example_sheet.md`):

```bash
python scripts/lint_prompt_sheet.py tests/fixtures/worked_example_sheet.md
```

```
Gate C: PASS — 11 shots, 0 findings.
```

This sheet did **not** pass on the first attempt at every single rule during drafting — five early
prompts (Setup/WORLD, ACTION-ADJACENT, FIGURE, WORLD, and the closing ARTIFACT shots) needed one
extra clause each to clear C12's 10-clause floor before Gate C reported clean. The fix in every
case was adding one more concrete renderable detail to the prompt body — never touching the arc
table, since the sequencing itself (register rhythm, scale/height spread, shot-class rotation) was
correct from the table stage in §5 onward. That is the process working as designed
(`references/visual-arc.md` §2): the table stayed fixed, only prompt density needed a second pass.

## 10. The handoff — literal sheet skeleton

`prompt-sheet-format.md` §7 requires every emitted sheet to carry a `WHOLE-SHORT SETUP` block,
a cover decision (already called in §8 above), an i2v block where applicable (already shown in
§7 above), an overlay-copy handoff, and a validation line — in the literal shape below, not as
narrative prose. This is what the sheet handed to `shorts-assembly` actually looks like:

```
WHOLE-SHORT SETUP
  --ar 9:16
  Register A --sref 2481950736   (harvested for this Short — present-day club-soccer look)
  Register B --sref 9057261843   (channel-fixed painterly signature, reused unchanged every Short)
  Phase ladder: Hook → Setup → Build → Re-hook → Payoff/Loop

OVERLAY COPY HANDOFF
  No on-screen text for this Short — the VO carries the full hook, claim, and CTA, and no
  hook-card, lower-third, or caption copy was held out of any prompt for `shorts-assembly`
  to composite.

VALIDATION
  Gate A: pass — every flag block carries --ar 9:16, the correct register-band --s value,
          --raw present only on Register A shots, no stray punctuation in the parameter block.
  Gate B: pass — no upstream quality flags applied to this Short.
  Gate C: pass, 11 shots, 0 findings — `python scripts/lint_prompt_sheet.py
          tests/fixtures/worked_example_sheet.md`
```

The `--sref` values above are illustrative placeholders in the style Midjourney actually uses
(numeric codes), not real harvested codes — this is a worked example, not a production run, so
no real style reference exists to cite.
