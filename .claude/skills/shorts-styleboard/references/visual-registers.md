# Visual registers — a two-world system for pairing present and source-era beats

## 0. Grounding note — read this before trusting any bullet below

The corpus's own visuals theme (`docs/headless-youtube-audit.md` §6, "Visuals & AI assets") is thin —
**27 findings**, and it says nothing about register systems, shot classes, or how to storyboard a Short
that pairs a present-day situation with a historical or external source. **The register system in this
file is this skill's own operational design `[I]`, not a corpus finding.** Do not present it, or read it,
as corpus-derived. Two kinds of claim in this file *are* sourced, and are marked accordingly:

- The Midjourney parameter bands and version mechanics — verified against `docs.midjourney.com` and already established in `midjourney-prompting/references/prompt-architecture.md` and `midjourney-prompting/references/v82-model-delta.md` — carry `[T] (verified 2026-07-26)`.
- The AI-slop and pacing cautions this system exists to guard against trace to `visual-prompts/references/faceless-pacing-rules.md` and carry `[C]` with the original citation.

Everything else — why two registers, the vocabulary-disjunction rule, the shot-class taxonomy, the motif
bridge, the sport-choice procedure — is `[I]`: this skill's own judgment applied to a gap the corpus
doesn't cover. If a future edit adds a new normative line here, it needs one of `[C]` / `[I]` / `[T]`, and
`[C]` may only be used for a claim that genuinely traces to existing corpus text — never invented.

## 1. Why two registers `[I]`

A Short that pairs a present-day situation with an external or historical source has two worlds in it —
the thing happening now, and the thing being drawn on to explain or justify it. If both are rendered in
one visual language, the contrast between them is inaudible: a viewer can't tell "then" from "now" without
a caption doing the work the image should be doing. Separating the two into distinct visual registers
makes the "then vs. now" cut legible in about half a second, on a silent autoplay, with zero text on
screen.

## 2. The vocabulary-disjunction rule `[I]` — the load-bearing mechanism

The two registers must share **no medium, no optics language, no palette family, and no parameter band**.
This is the entire mechanism the system runs on:

- Sharing the medium (e.g. letting a "photograph" register B beat slip in) collapses the visual cue that separates the worlds `[I]`.
- Sharing optics vocabulary (any camera/lens language) in register B specifically breaks the fine-art read and makes it look like a stylized photo instead of a painting `[I]`.
- Sharing a palette family blurs the eras together on a fast scroll `[I]`.
- Sharing a parameter band produces images with the same degree of literalism regardless of which world they belong to, which erases the last cue once the other three are controlled for `[I]`.

This rule is enforced mechanically, not just by convention: it is what Gate C's **C10** check exists to
catch (register-crossing vocabulary), on top of the register-balance and world-lock checks the linter also
runs `[I]`.

## 3. Register A — PRESENT

Full contract for every Register A prompt:

- **Medium.** `documentary sports photography` (or the present-day equivalent for a non-sports brand — the medium token names the real-world present, not a stylization of it) `[I]`.
- **World lock.** One sport per Short, named in every Register A prompt; at least one signature object from the world-lock block must be in frame; the strings `empty gym`, `empty youth gym`, `empty pitch`, `empty stadium`, `empty court`, `vacant gym`, `vacant pitch`, `deserted gym`, `deserted pitch`, `abandoned gym`, `abandoned pitch`, `generic gym` and `generic field` are banned — a present-day beat with no signature object and no human presence reads as a stock-photo void, not a specific world `[I]`.
- **Parameters.** `--raw` present, `--s 80–120` — the documented photographic band, near Midjourney's own default of 100, chosen so optics and lighting lead over the model's automatic styling `[T] (verified 2026-07-26)`.
- **Consistency.** One `--sref` code, reused across every Register A prompt. Its scope is whatever the register's entry in `docs/style-library.md` records — for RaisingGoodSports that is `scope: channel` since 2026-08-08, one durable code reused on every Short, not one harvested per Short as the debut visual system originally specified. Read the entry rather than assuming either `[I]`.
- **Shot classes** (rotate across these four; a sheet is not allowed to lean on only one) `[I]`:
  - `ESTABLISHING` — sets the venue and scale of the present-day world. Example: *a full youth soccer pitch at dawn seen across the touchline, goal net and corner flag anchoring the far end* `[I]`.
  - `ACTION-ADJACENT` — the moment just before or just after the action, not the action itself. This sidesteps the corpus's own caution that AI-generated B-roll still hits an uncanny-valley look `[C] (Nate Black, 9CCmMypN8PM)`, by never asking the model to render fast literal motion in the first place `[I]`. Example: *a child's hands lowering a kit bag onto the painted touchline, the strap slackening as the weight settles* `[I]`.
  - `DETAIL` — a close, specific object or gesture that makes the sport unmistakable. Example: *a child's hands pulling a shin-guard strap tight, knuckles whitening against the webbing* `[I]`.
  - `HUMAN-COST` — the emotional weight of the claim, on a face or body, not a wide shot. Example: *a lone figure sitting on a bench at the edge of a frost-bitten pitch, head down, gear bag untouched beside them* `[I]`.
- **The failure mode this exists to prevent.** A prompt sheet built entirely of `HUMAN-COST` shots is the thing this taxonomy is designed to stop: it reads as manipulative rather than evidentiary, and it is visually monotonous regardless of intent — rotating all four classes is what keeps a Register A run from collapsing into one repeated emotional beat `[I]`.

## 4. Register B — SOURCE ERA

Full contract for every Register B prompt:

- **Medium.** One fixed painterly signature, held channel-wide, varied only in *content* (era, place, figure) from Short to Short — never in medium, never in technique `[I]`.
- **Parameters.** No `--raw`, `--s 400–700` — the documented fine-art/illustrative band, at the opposite end of the stylize range from Register A, chosen for maximum interpretive freedom rather than literalism `[T] (verified 2026-07-26)`.
- **Consistency.** One `--sref` code harvested **once** via Style Creator's pick-the-grid session, stored as a repo-level channel asset, and reused on every Short thereafter — never re-harvested per Short `[I]`. Record the resolved `--sref` code itself (Style Creator's output); only run Style Creator again if the channel's painterly signature is deliberately changing `[I]`.
- **Banned vocabulary**, verbatim: `DSLR`, `shot on 35mm film`, `documentary`, `photorealistic`, `photographic`, `photograph`, `bokeh`, `shallow depth of field`, `depth of field`, `leica`, `kodachrome`, `cinematic still`, `film still`, `lens flare`, `telephoto`, `wide-angle lens`, `macro lens`, `iso`, any `<n>mm` token, any `f/<n>` token — exactly the optics/photography markers that would collapse register B back into register A's visual language (see §2) `[I]`.
- **Figure treatment.** Archetype only — unnamed, face averted or lost in shadow, dressed and posed to the role, never an attempt at a specific likeness `[I]`.
- **The `--oref` consequence.** Because no likeness is being locked, Omni Reference is unnecessary for register B figures — and that matters beyond style: adding an Omni Reference to a prompt automatically routes the whole job through V7 instead of V8.2, at **2× GPU cost**, so staying archetype-only keeps every Register B render in V8.2 at standard cost `[T] (verified 2026-07-26)`.
- **Shot classes** (rotate across these three) `[I]`:
  - `FIGURE` — the archetype, on their own, doing something tied to the source claim. Example: *a cloaked scholar seated at a stone table, one hand resting on an unrolled scroll, face turned into shadow* `[I]`.
  - `WORLD` — the era's setting, wide enough to place the figure in a specific time and place. Example: *a first-century Greek colonnade opening onto a sun-bleached terrace at dawn, worn limestone steps and terracotta roof tiles* `[I]`.
  - `ARTIFACT` — a period object that carries the claim's evidence, in close detail. Example: *a terracotta watering vessel tipped over a small clay pot on a sun-warmed stone ledge, water spilling past the rim* `[I]`.

## 5. PLATE — neither register

Subject-free background plates (for motion-graphic cards, lower thirds, transitions) belong to neither
register. Generate with `no animals and creatures, no people` so the plate composites cleanly and doesn't
drag a subject's color into the palette on remix `[C] (Tokenized AI, lCFzMnBDqEc)`. PLATE shots are
exempt from the world lock, from both register vocabularies, and from the register A/B parameter bands —
they are **not** exempt from prompt density or the copy-paste prompt format the rest of the sheet uses.

## 6. The motif bridge `[I]`

If the grounding artifact (from `rgs-grounding` or an equivalent upstream brief) supplies a motif, render
that motif in **both** registers, not just one. A motif that crosses eras is what welds the two registers
into a single story instead of two intercut, unrelated slideshows. Worked example: a watering can appears
as a modern object in a Register A `DETAIL` shot, and again as a terracotta vessel on a period terrace in
a Register B `ARTIFACT` shot — same idea, two visual languages, one thread a viewer can follow across the
cut.

## 7. The world-lock block

Emit this block once per Short, verbatim in the format Gate C's parser reads (`register_a_*` /
`register_b_*` / `motif` keys, one `key: value` pair per line under a `WORLD LOCK` heading) `[I]`. Every
downstream prompt in the sheet inherits from this block — it is written once, before any per-shot prompt
exists `[I]`.

```
WORLD LOCK
  register_a_sport:              [one sport]
  register_a_venue:              [venue type]
  register_a_signature_objects:  [2-3 objects that make the sport unmistakable]
  register_a_season_time:        [season / time of day]
  register_a_rationale:          [one line tying the sport to the claim's evidence]
  register_b_thinker:            [name]
  register_b_era_place:          [specific era and place]
  register_b_locations:          [2-3 named period locations]
  register_b_artifacts:          [2-3 period objects]
  register_b_figure_archetype:   [role and dress; never a likeness]
  motif:                         [the grounding brief's motif, rendered in BOTH registers]
  slot_register_a:               [Library entry label bound to Register A]
  slot_register_b:               [Library entry label bound to Register B]
```

Filled-in RaisingGoodSports example:

```
WORLD LOCK
  register_a_sport:              club soccer
  register_a_venue:              municipal club soccer complex
  register_a_signature_objects:  goal net, corner flag, painted touchline
  register_a_season_time:        winter dawn
  register_a_rationale:          club soccer's early-specialization pipeline is the sharpest present-day
                                  analogue to the claim's evidence on burnout
  register_b_thinker:            Plutarch
  register_b_era_place:          first-century Greece, a hillside estate near Chaeronea
  register_b_locations:          colonnaded terrace, olive-terraced hillside, stone courtyard
  register_b_artifacts:          terracotta watering vessel, wax writing tablet, olive branch
  register_b_figure_archetype:   an unnamed tutor, plain wool himation, face turned into shadow
  motif:                         a watering can — modern plastic in Register A, terracotta vessel in
                                  Register B
  slot_register_a:               rgs-present-soccer-a
  slot_register_b:               rgs-sourceera-painterly-b
```

**Slot declarations `[I]`.** Every `{style:…}` or `{char:…}` token a downstream prompt
sheet uses must be declared here as a `slot_<name>:` line whose value names the Style
Library entry it binds to. Gate C's **C18** rejects an undeclared slot. The literal
`--sref` code is deliberately *not* written here — it is resolved at generate time from
the Library, so re-locking a Short's look is one binding change rather than a sheet
regeneration.

## 8. Choosing the sport `[I]`

This skill is responsible for picking `register_a_sport` and stating a one-line rationale
(`register_a_rationale`) that ties the chosen sport to the claim's evidence — the sport is not a free
aesthetic choice, it is part of the argument. Before picking anything, check three places in order: the
incoming script, the concept brief, and the grounding artifact. Only pick a sport yourself if none of the
three names one. Name the choice at the top of the prompt sheet, not buried in the world-lock block alone
— an unstated sport lock is indistinguishable from a forgotten one, and a reviewer needs to be able to see
the decision was made deliberately.
