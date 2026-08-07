# Prompt sheet format — the exact copy-paste output contract

This file assumes `visual-registers.md` (the register contract and the world-lock keys)
and `visual-arc.md` (the shot-sequence workflow) are already read. It documents the
**literal, byte-level format** that `scripts/lint_prompt_sheet.py`'s parser
(`parse_sheet`, `SHOT_HEADING_RE`, `WORLD_HEADING_RE`, `WORLD_ENTRY_RE`) accepts, so a
sheet built to this spec parses and lints cleanly on the first run. If anything here
ever disagrees with the parser, the parser is the contract — fix this file, not the
linter `[I]`.

## 1. Why the format changed `[I]`

Two concrete reasons, not a style preference:

- **(a) Copy-paste, in one action.** The previous sheet shape was a Markdown table —
  prompt text in one column, `--ar`/`--sref`/`--s` flags in the next. No cell in that
  table was ever a complete, pasteable Midjourney prompt: the user had to manually
  stitch the prompt cell and the params cell back together before submitting a job.
  The format in this file puts the entire prompt — nine layers, `No Text.`, and every
  flag — inside a single fenced block, so one prompt is one copy action `[I]`.
  **One manual step still sits in front of that copy action, until the render console
  exists:** every emitted prompt ends in an unresolved `{style:register_a}` /
  `{style:register_b}` / `{char:<name>}` slot token, not a literal code. Before pasting, look
  up the actual harvested code for the Style Library entry the styleboard's `BINDINGS`
  section names for that slot, and replace the whole token with the real flag(s) it stands
  for (`--sref <code>`, `--p <code>`, an `--oref <url> --ow <n>` pair, or nothing at all for
  a personalization binding). Paste the token as-is and Midjourney renders the literal words
  "style register a" into the image instead of applying a look `[I]`.
- **(b) Gate C needs a machine-parseable artifact.** A checklist an agent can read and
  silently skip is not a gate. Emitting the sheet in a format `scripts/lint_prompt_sheet.py`
  can parse turns "did you follow the register rules" from an honor-system checklist
  into a deterministic pass/fail the agent cannot route around `[I]`.

## 2. The world-lock block — moved to the styleboard

The prompt sheet no longer carries a `WORLD LOCK` block. It lives in the styleboard
artifact (`shorts-styleboard/references/styleboard-format.md`), and Gate C reads it via
`python scripts/lint_prompt_sheet.py <sheet> --styleboard <styleboard>` `[I]`.

What the sheet carries instead is **slot tokens**, in flag position:

- `{style:register_a}` / `{style:register_b}` — the register's style binding.
- `{char:<name>}` — a character binding, where the styleboard declares one.

Each must be declared in the styleboard's world lock as `slot_register_a:`,
`slot_char_<name>:`, etc., or Gate C's **C18** fires. Slots sit **after at least one
literal flag** — `prompt_body`/`prompt_flags` split at the first ` --`, so a slot placed
earlier lands in the prompt body `[I]`.

The `register_a_signature_objects` substring-matching warning below still applies, and
still bites — it is now a property of the styleboard's block, not the sheet's.

**Warning — `register_a_signature_objects` is matched mechanically, not read as prose.**
`scripts/lint_prompt_sheet.py`'s `signature_objects()` splits this value on commas, and
`check_world_lock` (Gate C's **C8**) tests whether **any** of those pieces appears as a
lowercase **substring** of a Register A prompt body. That means:

- Keep each object **short and literal** — `goal net`, not `a regulation goal net with
  white netting`. A long descriptive phrase will almost never appear verbatim inside a
  prompt body, so the substring match silently fails and C8 fires even though the prompt
  is fine to a human reader.
- The match is case-insensitive but otherwise exact-substring, so wording drift between
  the world-lock value and the prompt body (`corner flag` in the lock vs. `flag at the
  corner` in the prompt) also fails to match.

## 3. The per-shot block

Exact format (`SHOT_HEADING_RE`, `OPEN_FENCE_RE`/`CLOSE_FENCE_RE`):

```
### Shot <N> — <Beat> (<time range>) · Register <A|B|PLATE> · <SHOT CLASS> · <SCALE> · <CAMERA HEIGHT>
Changes vs. previous: <one line naming the visual change>

```text
<the entire prompt on ONE line: 9-layer body, then "No Text.", then every flag>
```
```

Separators, spelled out exactly — the regex is whitespace-tolerant but not
punctuation-tolerant:

- `###` then one space, then literally `Shot <N>` (`<N>` is digits).
- An **em dash** (`—`), not a hyphen, before the beat name.
- The beat name may contain its own `(<time range>)` in parentheses — the parser
  captures everything up to the next separator as the beat field, so `Hook (0–3s)` is
  one field, not two.
- A **middot** (`·`), not a pipe or hyphen, between every metadata field from here on:
  `Register <A|B|PLATE>`, shot class, scale, camera height.
- **All metadata values are uppercase except the beat** — `Register A`, `DETAIL`,
  `MACRO`, `LOW`. Shot class and scale may contain hyphens (`ACTION-ADJACENT`,
  `MID-WIDE`); camera height may not (`LOW`/`EYE`/`HIGH`/`OVERHEAD` only).
- A heading the parser cannot match — wrong dash, wrong case, a missing field — is
  **silently skipped**: that shot never enters the sheet at all, no error is raised at
  parse time, and the sheet simply parses with fewer shots than it should. This is why
  Gate C exiting **2** ("no shots parsed") means "check the format," not "the content is
  wrong" — there was no content to check.
- The `Changes vs. previous:` line and any blank lines between the heading and the fence
  are allowed and ignored — the parser scans forward past them looking for the opening
  ` ```text ` fence. If it hits the **next** `### Shot` heading first, it gives up on the
  current shot with an empty prompt rather than reading into the next shot's fence.
- The fence must open with ` ```text ` (only surrounding whitespace tolerated) and close
  with a bare ` ``` ` — no other language tag closes it.

## 4. The one-line rule `[I]`

The prompt inside the fence must be a **single line**. This isn't a parser requirement —
`parse_sheet` will happily join multiple lines inside the fence with spaces — it's a
Gate C content requirement: **C13** counts the lines actually present inside the fence
and fails any shot where that count isn't exactly 1. Wrapping the prompt across lines
defeats the entire reason this format exists (§1a): a multi-line prompt can't be
selected and pasted into Midjourney in one action.

## 5. Prompt density `[I]`, with the conflict stated openly

The prompt body must carry all 9 layers with concrete renderable content — **Gate C's
C12** requires at least 10 comma-separated clauses and at least 60 words in the body.

State the tension in full rather than quietly overriding it. `midjourney-prompting`'s
own `references/prompt-architecture.md` carries:

> **Short usually beats long.** Long prompts dilute which words the model actually weights
> `[C] (Tokenized AI, vezJXJGQMoY)`.

That finding concerns **padding and abstract quality claims** diluting which words get
weighted — not the number of distinct visual attributes specified. Naming a lens, a
light direction, a palette, and a background separation is **denser**, not more diluted;
each clause adds a distinct renderable attribute rather than repeating the same idea in
more words. **Density, not length** is the resolution `[I]` — the buzzword ban (no
"cinematic," "stunning," "professional") and the padding ban both still stand exactly as
`prompt-architecture.md` states them. This is an `[I]` adaptation for this skill's
9-layer, register-locked shot format, not a correction of the `[C]` finding above, and
that `[C]` line is not deleted or softened by this adaptation.

## 6. A full worked shot block

Copied verbatim from `tests/fixtures/passing_sheet.md`, Shot 1 — read the standard, not
a description of it:

```
### Shot 1 — Hook (0–3s) · Register A · DETAIL · MACRO · LOW
Changes vs. previous: opening frame.

```text
documentary sports photography, extreme close-up of a child's small hands pulling a nylon shin-guard strap tight over a club soccer sock, knuckles whitening against the webbing, a scuffed cleat and a mud-flecked ball resting behind on cropped winter turf, a goal net dissolving into unfocused background, low three-quarter angle from knee height, 100mm macro lens at f/2.8, razor-thin focal plane on the buckle, flat blue-grey dawn light from an overcast sky, desaturated palette of turf green and cold slate, fine grain, DSLR, No Text. --ar 9:16 --raw --s 95 {style:register_a}
```
```

## 7. The remaining sheet sections

Everything below sits outside `scripts/lint_prompt_sheet.py`'s parser — it never reads
these sections — but they still travel downstream to `shorts-assembly` and must be
present in every emitted sheet `[I]`:

- **`WHOLE-SHORT SETUP`** — aspect ratio (`--ar 9:16`), the **two style slots**
  (`{style:register_a}`, `{style:register_b}`) and the path to the styleboard artifact
  they resolve against, and the **phase ladder** — the ordered list of script beats this
  sheet covers, so a reader can see the whole arc before reading a single shot block.
  "Phase ladder" is this skill's own name for that list, not a corpus or parser term `[I]`.
- **The cover/thumbnail decision** (`SKILL.md` step 6) — either a `### Cover — <Beat> ·
  Register <A|B|PLATE> · <SHOT CLASS> · <SCALE> · <CAMERA HEIGHT>` block with its own
  fenced prompt, or a line beginning exactly `Cover = Hook` stating the Hook still
  doubles as the cover. Gate C's **C19** rejects a sheet that states neither `[I]`.
- **The I2V block** — for any beat `SKILL.md` step 5 decided needs a real animated clip:
  source still, target tool and one-line why, the i2v prompt text itself, and
  start/end-frame notes, per `references/image-to-video.md` `[I]`.
- **The overlay-copy handoff** — any on-screen text/hook-card/caption copy that was kept
  out of the Midjourney prompt (per `SKILL.md` step 4's "on-screen text never enters the
  prompt" rule) is listed here for `shorts-assembly` to composite `[I]`.
- **The validation line** — reports the outcome of all three gates before handoff: Gate A
  (`midjourney-prompting`'s syntax lint), Gate B (whatever upstream visual-quality check
  applies), and Gate C (`scripts/lint_prompt_sheet.py`, this file's own gate). State pass
  or fail for each; never report Gate C as passed without having actually run it
  (`visual-arc.md` §9) `[I]`.

## 8. The i2v inheritance rule `[I]`

An i2v prompt inherits its source still's register and must not import the other
register's vocabulary. A clip built from a Register A still stays photographic (camera
optics, `documentary sports photography` medium) end to end; a clip built from a
Register B still stays painterly (no camera/lens language, no `DSLR`) end to end — the
same vocabulary-disjunction rule that governs still prompts (`visual-registers.md` §2)
still applies once motion is added, because the i2v tool is only ever transforming one
register's still, never blending the two.
