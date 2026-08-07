# Visual arc — plan the sequence before writing a single prompt

This file assumes `visual-registers.md` (the dual-register contract: Register A/PRESENT,
Register B/SOURCE ERA, PLATE, shot classes, the world-lock block) is already read. It
covers the *workflow discipline* that sits on top of that contract: build the whole shot
sequence as a table first, rotate scale and camera height and optics across it, and know
exactly what Gate C (`scripts/lint_prompt_sheet.py`) will check once the sheet is written.

## 1. The failure this prevents `[I]`

This is not a hypothetical. The prompt sheet at
`runs/letkidsplay-20260727-005326/03-visual/artifact.v1.md` rendered six of its nine
stills as the same photograph — same frame, same composition, same camera position —
varying only the amount of gear visible in shot. The root cause was procedural: prompts
were written one beat at a time, in beat order, and "consistency" was achieved by cloning
the previous prompt's body and swapping a noun or two. Nothing about that process ever
asked "does shot 5 look different from shot 4," because no artifact existed yet that made
the whole sequence visible at once. The failure is not that the prompts were bad
individually — most read fine in isolation — it's that nobody could see the repetition
until all nine were rendered, because the sequence was never laid out as a sequence.
Don't reintroduce this: writing prompts beat-by-beat, in order, with no whole-sheet view
before the first prompt string exists, is precisely the process that produced it `[I]`.

## 2. Arc before prompts `[I]`

The whole sheet is laid out as a sequence — the arc table in §3 — *before* any prompt
string exists. This ordering is not cosmetic:

- Fixing a repetitive arc means editing a table row (change one cell's scale or shot
  class), not rewriting eleven prompt strings that were written under the wrong plan `[I]`.
- It happens before any GPU minute is spent. A repetitive prompt sheet caught at the
  table stage costs nothing; the same defect caught after rendering nine Midjourney jobs
  costs nine renders `[I]`.
- It gives Gate C's C1–C5 checks (§8) something to run against that was designed for
  variety from the start, rather than a set of independently-written prompts hoping to
  pass a linter after the fact `[I]`.

Build the table. Review the table for repetition by eye. Only then write prompt strings
against the finished table.

## 3. The arc table shape `[I]`

One row per shot, columns in this exact order:

| # | Beat | Register | Shot class | Scale | Camera height | What changes vs. previous |
|---|------|----------|------------|-------|----------------|----------------------------|

- **#** — sheet order, matches the shot heading `Shot N` that Gate C's parser reads.
- **Beat** — the script beat this shot serves.
- **Register** — `A`, `B`, or `PLATE` (see `visual-registers.md` §3–§5).
- **Shot class** — from the register's own taxonomy (`ESTABLISHING` / `ACTION-ADJACENT`
  / `DETAIL` / `HUMAN-COST` for Register A; `FIGURE` / `WORLD` / `ARTIFACT` for Register B).
- **Scale** — one of the six values in §4.
- **Camera height** — one of the four values in §5.
- **What changes vs. previous** — mandatory, and it must name a *visual* change: a
  different scale, a different camera height, a different shot class, a different
  register, a different subject or composition. "More gear in frame" is not a visual
  change of frame — it is the same frame with a different prop count, and it is exactly
  the failure described in §1. If this column can't name a change to the frame itself,
  the row needs to change, not the description `[I]`.

## 4. The scale ladder `[I]`

Closed vocabulary — no other scale token is valid on a sheet:

- **`XWIDE`** — establishes geography and scale of the whole space; orients the viewer
  before anything else happens in the shot.
- **`WIDE`** — sets the venue or setting at human scale; the subject exists inside a
  legible place, not floating in a void.
- **`MID-WIDE`** — holds the subject and enough surrounding context to read the action or
  posture, without losing the environment entirely.
- **`MID`** — the standard conversational distance; subject fills most of the frame,
  environment reduced to a supporting edge.
- **`CLOSE`** — a face, a hand, a held object — reads emotion or specific identity, not
  environment.
- **`MACRO`** — extreme close, texture-level detail (strap webbing, brush stroke,
  fingerprint on glass); makes a single object or surface unmistakable.

**Rule: at least 3 distinct scales must appear across the sheet `[I]`.** A sheet that
lives in `MID` and `CLOSE` alone reads as visually flat regardless of how many shots it
has — this is the table-level version of the failure in §1. This is what Gate C's **C4**
check enforces mechanically.

## 5. Camera height `[I]`

Closed vocabulary:

- **`LOW`** — camera below eye line, looking up; lends weight, scale, or a child's-eye
  view depending on subject.
- **`EYE`** — camera at the subject's eye line; the default, neutral, documentary read.
- **`HIGH`** — camera above eye line, looking down; can read as observational, exposed,
  or diminishing depending on context.
- **`OVERHEAD`** — directly above; flattens the subject into a layout/map read, good for
  establishing spatial relationships (a pitch, a table of objects).

**Rule: at least 2 distinct camera heights must appear across the sheet `[I]`.** A sheet
shot entirely at `EYE` height is coherent but monotone — this is what Gate C's **C5**
check enforces mechanically.

## 6. Optics rotation (Register A only) `[I]`

**These specific lens/aperture pairings are this skill's own judgment, not a corpus
finding — there is nothing in the corpus about lens choice.** They exist because a sheet
where every Register A prompt says `35mm f2.8` has no visual grammar: the optics never
change, so nothing about *how* the camera sees changes even when the scale does. A
starting ladder, tied to shot class so the choice isn't arbitrary per-shot:

- **`ESTABLISHING`** → wide, ~24mm, at a deep aperture (e.g. f8–f11) — keeps the whole
  space in focus, consistent with orienting the viewer.
- **`ACTION-ADJACENT`** → ~50mm at a moderate aperture (e.g. f4–f5.6) — a natural,
  unexaggerated field of view for a moment just before or after action.
- **`HUMAN-COST`** → ~35mm at a shallow aperture (e.g. f1.8–f2.8) — isolates the subject
  from the background, consistent with an emotional, singular read.
- **`DETAIL`** → ~100mm macro at a shallow aperture — the long, close, isolating optics a
  physical macro lens actually produces.

Treat this ladder as a starting point to rotate from, not a rule to apply identically on
every Short — the point is that optics vary with shot class, not that these four exact
pairings are mandatory. Register B carries no optics language at all (see
`visual-registers.md` §2 and §4's banned-vocabulary list) — this ladder applies to
Register A prompts only.

## 7. Pacing interaction `[C]`

Two different problems, easy to conflate:

- The **~3-second cadence rule** — change the on-screen visual every ~3 seconds; never
  hold one image/clip too long `[C] (Make Money Matt, HopTPCLbiiM)` — sets the *shot
  count* for a given VO duration. It answers "how many shots."
- **This file** sets the *shot variety* — scale, camera height, shot class, optics — once
  the shot count is fixed. It answers "how different do consecutive shots need to be."

They are not substitutes for each other: hitting the cadence with nine shots that are all
`MID` / `EYE` / `35mm` satisfies the pacing rule and still produces the exact failure in
§1. Both have to be true at once.

The over-editing caution applies here too: a random, mismatched visual causes confusion
and viewer drop-off `[C] (Kallaway, i7upRL4H1FM)`, and over-editing — flashbangs, stacked
overlays, constant jump cuts — exhausts viewers; comprehension comes from *deleting*
edits, and rawer/simpler editing increasingly reads as more authentic
`[C] (Kallaway, i7upRL4H1FM; Nate Black, J8LrrCpDNJI)`. Rotating scale/height/optics is
not license to cut for its own sake — cut because the VO content changed, and let the
arc table's variety do the work of keeping each cut visually distinct once a cut is
already warranted.

## 8. The Gate C table `[I]`

Run `scripts/lint_prompt_sheet.py` against an emitted sheet and it reports findings
tagged with these check IDs. This table lets you map a finding straight back to the rule
it enforces. `[I]` — this lint gate and its check IDs are this skill's own operational
tooling, not extracted from the corpus.

| Check | What it enforces |
|-------|-------------------|
| **C1** | No two consecutive shots share the same shot class. |
| **C2** | No two consecutive shots share the same scale. |
| **C3** | No register (A or B, PLATE excluded) runs for more than 2 consecutive shots. |
| **C4** | At least 3 distinct scales appear across the whole sheet. |
| **C5** | At least 2 distinct camera heights appear across the whole sheet. |
| **C6** | At least 3 Register A shots and at least 2 Register B shots appear on the sheet. |
| **C7** | Registers (A/B, PLATE excluded) alternate at least twice — bookending the source era at the open and close only does not count as an intercut rhythm. |
| **C8** | Every Register A prompt names the world lock's `register_a_sport` and contains at least one of its `register_a_signature_objects`. |
| **C9** | No Register A prompt contains a banned generic-venue string (`empty gym`, `empty youth gym`). |
| **C10** | No Register B prompt contains banned photographic vocabulary (`DSLR`, `shot on 35mm film`, `documentary`, any `<n>mm` token, any `f/<n>` token) — this is the vocabulary-disjunction rule from `visual-registers.md` §2, enforced mechanically. |
| **C11** | No two shots share more than 5 identical prompt-body clauses — consistency belongs in the register's style slot, not in a cloned prompt body. |
| **C12** | Every prompt body has at least 10 clauses and at least 60 words — density enough that all layers carry concrete renderable content. |
| **C13** | Copy-paste format: prompt is one contiguous line, `No Text.` appears immediately before the flags, a parameter block exists, `--ar` is present, and no stray punctuation (`,` `;` `.`) sits inside the parameter block. |
| **C14** | Register parameter bands: Register A requires `--raw` and `--s` in 80–120; Register B must not carry `--raw` and requires `--s` in 400–700. |
| **C15** | Shot class, scale, and camera height are each members of their closed vocabulary: Register A shot class ∈ `{ESTABLISHING, ACTION-ADJACENT, DETAIL, HUMAN-COST}`, Register B shot class ∈ `{FIGURE, WORLD, ARTIFACT}`, PLATE shot class must be literally `PLATE`; scale ∈ `{XWIDE, WIDE, MID-WIDE, MID, CLOSE, MACRO}`; camera height ∈ `{LOW, EYE, HIGH, OVERHEAD}`. Catches typos (`MIDWIDE` for `MID-WIDE`) that would otherwise dodge C2 and inflate C4's distinct-scale count `[I]`. |
| **C16** | Every literal `--sref` value is a real code (a number, a URL, or the literal `random`) and every literal `--p` value is a plausible pID/mID/resolved code (alphanumeric, no separators) — not an invented placeholder (`--sref SREF-RGS-A-DL01`, `--p mj-INVENTED-01`). A `{style:...}`/`{char:...}` slot used *as* an `--sref`/`--p` value also fails — a slot expands to the whole flag group, not a single value. A `--sref` written with no value at all (nothing before the next flag or end of prompt) fails too, since it references nothing; a bare `--p` is exempt, because Midjourney's own syntax uses it alone to mean "apply my active personalization profile" `[I]`. |
| **C17** | Every non-PLATE shot carries some style mechanism in its parameter block — a literal `--sref`, a literal `--p`, or a `{style:...}` slot — or it renders in whatever look the model defaults to. PLATE shots are exempt (no register look to lock) `[I]`. |
| **C18** | Every `{style:...}`/`{char:...}` slot sits after at least one literal flag, never in the prompt body, and is declared in the styleboard's `WORLD LOCK` as a `slot_*` line. That line's *value* must itself be a Style Library entry label (e.g. `rgs-present-soccer-a`) — not a raw Midjourney code or an invented placeholder (`SREF-RGS-A-DL01`) — because the code is resolved later, at render time, against the Library `[I]`. |
| **C19** | The sheet states its cover decision exactly once — either a `### Cover — ...` block or an explicit `Cover = Hook beat still #1` declaration — never zero, never more than one `[I]`. |

## 9. How to run Gate C `[I]`

```bash
python scripts/lint_prompt_sheet.py <path-to-sheet.md> --styleboard <path-to-styleboard.md>
```

**`--styleboard` is required, not optional** — the sheet no longer carries its own
`WORLD LOCK` block, so omitting it resolves an empty world lock and produces a wall of
false C8/C18 findings instead of a clear error `[I]`.

Exit 0 clean · exit 1 findings · exit 2 nothing parsed (usually a format error — see
`prompt-sheet-format.md`). `[I]` — this skill's own operational rule: a failing gate
**blocks emission**. Never report Gate C as passed without running it.
