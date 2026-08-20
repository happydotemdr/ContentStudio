# Worked example — copper moka pot, e-commerce hero

> **`[T]` facts in this file were web-verified 2026-07-26** against live docs.midjourney.com documentation (the V8.2 delta)
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

> This example illustrates rules already marked in this skill's other reference files and carries no independent normative weight. Where a line here restates a rule, the marker lives
> on the rule, not on the illustration — do not copy an unmarked line out of this file into a
> real brief as if it were sourced `[I]`.

One job end to end: control surface → draft → lock → gates → production. **This is a real run.** The
Gate B findings below are the actual output of a fresh agent dispatched with the verbatim prompt in
`validation-gates.md` — including the parts where the first attempt was wrong. That is the point of
keeping it: a worked example where nothing fails teaches nothing.

---

## The brief

> A hero product image of a polished copper moka pot for a specialty coffee brand's product page. It
> sits in a set with five other product images sharing one look, so a style code is locked. The brand
> look is warm, tactile, and unfussy — real kitchen, not a white sweep. The pot is the hero and must
> read as premium; **the surface finish is the selling point.**

## Step 0 — Control surface

```
subject:      polished copper moka pot
stage:        production          (user has an approved direction already)
look:         photographic        [default]
format:       4:5                 (e-commerce product page)
consistency:  style-lock          (shared --sref across a 6-image set)
literalism:   obey my words       (finish must render as specified)
variance:     tight               (set coherence beats exploration)
budget:       normal              [default]
```

Assumed defaults named: `look`, `variance` mapping to `--c 0`, `budget`.

## Step 3 — Phase 1, draft (0.4 GPU min)

Even with a direction in hand, the style code has to come from somewhere.

```
product photography of a polished copper moka pot on a dark walnut counter, window light --draft --ar 4:5 --sref random
```

24 thumbnails at 512px, **each with a different style code** `[T] (verified 2026-07-26)`. Harvest the
winner's code — here, `1847302956`. Stop for the user's pick.

## Step 4 — Phase 2, lock (0.8 GPU min)

Swap `--sref random` for the harvested code, add optics and lighting, drop `--c` to 0, stay at SD.
**This is where the style code gets validated against a copper subject** — codes render differently by
subject `[C] (Future Tech Pilot, GAT5A6MqM-E)`.

## Step 5 — Phase 3, production — first attempt

```
product photography of a polished copper moka pot, lid open with faint steam rising from the spout, on a dark walnut counter beside a scattering of roasted beans, three-quarter elevated view, 85mm lens, f/4.0, sharp focal plane across the body, hard morning window light from camera left with a soft bounce fill, long shadows, warm copper against cool grey shadow, muted colors, shot on 35mm film --ar 4:5 --raw --s 95 --c 0 --sref 1847302956 --sw 100 --q 2 --hd
```

**Gate A (first pass): reported clean.** Flags last, single-spaced, no punctuation in the block;
`--ar 4:5` inside the 4:1 `--hd` ceiling; `--s 95` in the photographic band; `--c 0` matches
`variance: tight`; no buzzwords; no `--oref` conflicts.

That clean bill is exactly why Gate B exists.

## Gate B — actual findings

**Weakest layer — 8 (color/atmosphere), fighting both the brief and the style lock.**
`muted colors` desaturates the one thing being sold. `shot on 35mm film` is a **layer-1 medium claim
sitting at position 9**, contradicting `product photography of` at position 1 — two mediums in one
prompt, with film grain landing on a specular surface. `DSLR` is the corpus's actual realism trigger;
`35mm film` was never the load-bearing word `[C] (Tao Prompts, 2psBexPkw3I)`. All three cues also
collide with `--sref`, which already transfers color, medium, texture, and lighting.

**Where literal reading bites.**
- **`hard morning window light` on polished copper destroys the selling point** — hard direct light on
  a mirror finish blows the speculars; a finish you cannot evaluate. Polished metal needs a large soft
  source for a readable gradient.
- **`hard ... light` + `soft bounce fill` + `long shadows` is a mixed signal**, and shadow direction is
  never stated relative to the key, so `long shadows` lands arbitrarily.
- **`lid open with faint steam rising from the spout` is physically incoherent** — a moka pot's spout
  is on the upper chamber, so with the lid open `the spout` is a contested referent, and the open lid
  renders as a black cavity through the top of the hero. The brief asked for neither.
- **`f/4.0` contradicts `sharp focal plane across the body`** — at 85mm and product distance, f/4 is a
  bokeh cue and will blur the pot's rear body.
- **`dark walnut counter` + `cool grey shadow`** is a color-science contradiction: warm wood bouncing
  fill does not produce cool grey shadows.

**What is buried — actually, absent.** The material description doesn't exist. `polished` is one
adjective in layer 2, and **material** is one of the six V8 anchors that carry a prompt
`[C] (Future Tech Pilot, ioJ6istzwHw)`. The brief's core requirement had **zero renderable detail**,
while late-position budget went to beans, film stock, and `muted colors`.

**Flag stack — one real violation and three soft ones.**
- ❌ **`--q 2` is not justified by `budget: normal`.** The control-surface mapping gives `--q 2`+ to
  `budget: no limit` only. It is 2× GPU and **affects only the first grid of four**
  `[T] (verified 2026-07-26)`. With `--hd`, this job ran ~2.6 GPU min against a normal budget.
- ⚠️ `--sw 100` was the default, not a decision — at full strength a code carrying color and lighting
  overrides the very layer needing control on a specular subject. 60–80 holds the look across a set.
- ⚠️ `--sv` omitted: style codes work **only with `--sv 4` or `--sv 6`** `[T] (verified 2026-07-26)`.
  If the account default isn't one of those, `--sref 1847302956` silently does nothing — and the HD
  render bills anyway.
- ⚠️ No `--seed`: for a locked 6-image set the render is unreproducible, and `--hd` differs from SD
  even at the same seed `[C][T] (Future Tech Pilot, Tv1dfGcOSnA / t_xIYKk2ERk)`.

## The revised prompt

```
product photography of a polished copper moka pot, hand-polished surface with fine circular lathe marks and warm specular roll-off, brass fittings, lid closed, on a dark walnut counter with a few roasted beans, three-quarter elevated view, 85mm lens, f/11, deep depth of field sharp front to back, large diffused window light from camera left, white bounce fill from camera right, soft directional shadows falling to the right, warm copper against neutral grey, DSLR --ar 4:5 --raw --s 95 --c 0 --sref 1847302956 --sw 70 --seed 1000 --q 1 --hd
```

Material moved to position 3, directly after the subject. Lighting reconciled to a single quality with
a stated shadow direction. Aperture matched to the stated depth of field. Layer 8 reduced to what the
style code isn't already doing. `--q` returned to the declared budget, `--sw` chosen rather than
defaulted, seed pinned for the set.

**Gate A re-lint on the rewrite** (mandatory — Gate B touched parameters): flags last, single-spaced,
no punctuation; `--ar 4:5` ≤ 4:1 under `--hd`; `--s 95` in band; `--sw 70` in range and legal (no
moodboard); `--q 1` valid and budget-consistent; `--seed` present for a set; no `--oref` conflicts; no
buzzwords. **Clean.**

## What this run changed in the skill

Gate B's `--q 2` catch exposed a real hole: **Gate A checked stage discipline but not budget
discipline.** The stage was `production`, so `--q 2` passed — while contradicting the control surface's
own mapping. `validation-gates.md` §A5 now lints budget, seed-for-sets, and style-code validation
(§A5b) as a direct result.

Two lessons worth carrying:

1. **A clean Gate A is not a good prompt.** Gate A verifies the prompt is *well-formed*. Only Gate B
   asks whether it is *right*. The first attempt was syntactically perfect and would have rendered an
   image that defeated the brief's one stated requirement.
2. **Escalate on the agent's advice, not past it.** Gate B recommended re-running at `--sd --q 1` to
   confirm the style code applies to a copper subject before spending `--hd`. Taking that advice costs
   0.8 GPU min; ignoring it risks 1.3 min on an unstyled image.

## Open questions the gate raised

- Was `--sref 1847302956` validated against a **copper/metal** subject, or harvested on a different
  product? If unvalidated, the SD pass is mandatory, not optional.
- Is the steam/open-lid a client requirement? If so it needs a stove-top environment to be coherent —
  which changes layer 4 across the whole 6-image set, not just this frame.

Both went back to the user rather than being resolved by assumption.
