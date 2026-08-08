# Style Library

The lookup table that turns a styleboard `slot_*` label into a real Midjourney flag.

**Status:** created 2026-08-07. **Both registers harvested 2026-08-08** — the first real style
codes this project has ever had. Every Short before this one rendered with no style lock at
all; see "Why this file exists" below.

**Read `Open questions` §1 before authoring a Register A prompt.** Both harvested codes are
artistic rather than photorealistic, which is a deliberate choice by the run owner and which
puts Register A's `--raw` requirement in tension with its own style code.

---

## What this is

`shorts-styleboard` binds each register to a Library **label**. `visual-prompts` writes an
unresolved **token** into the sheet. This file is where the label becomes a **code**.

| Layer | Carries | Written by |
|---|---|---|
| Styleboard `WORLD LOCK` | `slot_register_a: rgs-present-soccer-a` | `shorts-styleboard` |
| Prompt sheet flag block | `{style:register_a}` | `visual-prompts` |
| **This file** | **`rgs-present-soccer-a` → `--sref <code>`** | **a human, after a harvest** |
| Pasted into Midjourney | `--sref <code>` | a human, per `shorts-assembly` |

Gate C's **C16** rejects a literal invented code in a sheet, and **C18** requires each slot's
declared value to be a kebab-case Library label rather than a raw code. That is deliberate:
the code is resolved here, at render time, not baked into an artifact that outlives it.

Nothing resolves this file automatically yet. `shorts-assembly/SKILL.md:36` calls the
substitution "a manual step until the render console exists."

## Why this file exists

`rgs-briefs/2026-07-28-rgs-debut-visual-system.md:89` locks a two-code protocol and names the
codes `SREF-RGS-A-01` and `SREF-RGS-B-01`. Those are placeholder **names**, never harvested.
The do-less Short shipped against them, and assembly v3 §0.1 records the result: *no render in
this Short ever had a style lock applied*, so Register B came back half oil-painting, half
photographic, and the register split had to be rescued by a colour grade that the renderer
cannot actually apply (see `docs/superpowers/specs/2026-08-07-stitcher-capability-boundary.md`).

C16 now catches that class of defect at the gate. This file is where the fix lands.

## Entry format

```
### <label>                       kebab-case; this is the styleboard slot_* value
  brand:        <brand id>
  register:     A (present day) | B (source era)
  scope:        channel | per-short
  mechanism:    --sref | --p | --oref | none
  world:        what this look depicts, so a future Short can tell whether it fits
  seed:         the description the harvest session was seeded with
  code:         <value> | UNHARVESTED
  harvested_at: <YYYY-MM-DD> | —
```

A `scope: per-short` entry carries a **codes table** instead of a single `code:`, one row per
Short slug.

## How to harvest

Per `rgs-briefs/2026-07-28-rgs-debut-visual-system.md:87-99`, RGS harvests through a
**Style Creator session** — web-only, seeded with the register's palette/mood description —
not through a broad `--sref random` sample. Run previews in `--draft` to keep the session
cheap `[T]`.

**Re-entering a session stacks a new code rather than replacing the old one, so once a code is
locked, do not re-enter its session** `[T]`. That is why the two registers need two separate
sessions rather than one session extended.

`midjourney-prompting/SKILL.md:139` describes the other harvest route — `--draft --sref random`,
24 thumbnails at 512px for 0.4 GPU minutes, each carrying a different style code. That is the
generic style-discovery flow and is the cheaper way to *explore* when no seed description
exists yet. RGS has a seed description, so Style Creator is the specified route here.

Either way: **harvest, then record the code below.** A harvested code that lives only in a
Midjourney session is not recoverable by anyone else.

---

## Entries

### rgs-source-era-b

```
brand:        raisinggoodsports
register:     B (source era)
scope:        channel          # harvested ONCE, reused unchanged on every subsequent Short,
                               # so the historical register reads as one continuous world
                               # across the whole catalogue
mechanism:    --sref
world:        the thinker's own era and place — a lamplit writing study, a period classroom,
              a north-lit desk. Painterly, not photographic: visible brushwork, canvas tooth,
              warm low-key chiaroscuro. Register B shares NO palette family and NO parameter
              band with Register A (visual-registers.md §2), and Gate C's C6/C7/C10/C14
              enforce that separation mechanically.
seed:         the painterly source-era description ONLY — never the photographic palette.
              Warm, low-key, chiaroscuro; brass/leather/ink materials; anonymous presence,
              face turned into shadow, never a likeness of a named historical figure.
code:         6930382708
harvested_at: 2026-08-08
```

Use as `--sref 6930382708`. Channel-wide and durable: reuse this exact value on every
subsequent Short's Register B shots, unchanged, so the historical register reads as one
continuous world across the catalogue. Do not re-enter its session to "improve" it — a
re-entry stacks a second code rather than replacing this one.

**Anchor reference:** the do-less run produced two frames that already carry this look —
`Generated Assets/do-less-20260728-190724/visuals/Shot 5_HD.png` (true oil painting, visible
brushwork) and `Shot 11_HD.png` (warm chiaroscuro). Assembly v3 §4 calls them the anchor the
other Register B shots should be matched to. Use them to judge whether a candidate code is
on-register.

### rgs-present-soccer-a

```
brand:        raisinggoodsports
register:     A (present day)
scope:        channel          # CHANGED 2026-08-08 -- was per-short. See the note below.
mechanism:    --sref
world:        present-day youth sport — a municipal complex, clubhouse, sideline, pitch.
              Cold palette: teal-ink ground (#0E3B43), amber (#F2A541) reserved as a rim-light
              accent only, muted clay (#C1543A) reserved for claim-card framing and never on a
              child or parent. Anonymous human presence — no identifiable faces.
              NOT photorealistic — see "Medium" below.
code:         832507909
harvested_at: 2026-08-08
```

Use as `--sref 832507909`.

**Scope changed to `channel`.** `rgs-briefs/2026-07-28-rgs-debut-visual-system.md:87` specifies
Register A as harvested *per Short* (`SREF-RGS-A-<short>`), with only Register B channel-wide.
The run owner supplied one durable code for the soccer world instead, which supersedes that
line. Two consequences, both good: the two registers now follow the same one-code-per-register
rule, and the label→code resolution ambiguity recorded here on 2026-08-07 disappears —
`rgs-present-soccer-a` now maps to exactly one value regardless of Short.

**Medium: artistic, not photographic** `[run owner, 2026-08-08]`. The code was chosen on its
look and is more stylized than the photorealistic treatment the debut visual system assumed.
That is a deliberate call, and it changes what carries the register split — see
`Open questions` §1 before writing Register A prompts.

**Known drift, still relevant:** every present-day render in the do-less Short came back warm
golden-hour against a prompt asking for cold teal-grey (assembly v3 §0.1). The palette
requirement above is unchanged by the medium change — hold the prompt body to the cold
teal-ink ground and check the first renders for warm drift.

---

## Open questions

1. **Register A's `--raw` requirement now fights its own style code. Decide before Track C's
   prompt sheet is written.** `scripts/lint_prompt_sheet.py:557` sets
   `REGISTER_BANDS = {"A": (80, 120, True), "B": (400, 700, False)}` — Register A **must**
   carry `--raw` (C14) and must sit at `--s 80-120`. Both settings exist to push Register A
   photographic, and both actively suppress a stylized `--sref`. Register B is the mirror:
   `--raw` forbidden, `--s 400-700`.

   Gate C will still PASS either way — C14 checks that the flag is present, not that the image
   came out photographic — so this will not be caught mechanically. It shows up as diluted
   renders that do not look like the code that was picked.

   **DECIDED 2026-08-08 (run owner): keep the bands unchanged for now.** Run the first Short
   end to end on `--raw` + `--s 80-120` and judge the actual renders before touching a gate
   three skills depend on. The alternative — dropping `needs_raw` and raising the stylize band
   in `REGISTER_BANDS`, with `visual-prompts/references/visual-registers.md` §2 updated to
   match — stays on the table and is the fix if Register A comes back diluted.

   **What to look at when the first Register A renders land:** whether they read as the code
   that was picked, or as generic photographic stock with a faint stylization. If the latter,
   `--raw` is the thing to drop first.

   The mechanical separation Gate C enforces (C6/C7/C9/C10, and the disjoint `--s` bands)
   survives either choice — the two registers still share no palette family and no parameter
   band. What changes is whether *medium* is still one of the cues. Note that assembly v3 §0.1
   records what happened last time medium stopped carrying the split: the register read
   collapsed and had to be rescued by a colour grade the renderer cannot apply.
2. **Nothing validates a code against this file.** C18 checks a slot's value looks like a
   Library label; it cannot check the label *exists* here, because nothing parses this file.
   A label typo passes Gate C and fails at paste time.
3. **`--oref` is rejected for this pool** (`visual-system.md:104`): it forces V7 regardless of
   requested version, costs 2× GPU, accepts one reference image, and is Draft-incompatible.
   The pool has no recurring face to lock — only the style must hold constant. Recorded so the
   decision is not relitigated per Short.
