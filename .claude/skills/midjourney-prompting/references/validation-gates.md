# Validation gates

> **`[T]` facts in this file were web-verified 2026-07-26** against live docs.midjourney.com documentation (the V8.2 delta)
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

Two gates, deliberately asymmetric. Gate A is free and runs on every prompt. Gate B costs an agent
round-trip and runs only when a render is about to get expensive.

The asymmetry is the point: independent review is worth an agent on a 1.3-GPU-minute HD job, and
worthless on a 0.4-minute draft grid where the whole purpose is to be wrong cheaply.

---

## Gate A — syntax & compatibility lint

**Fires:** on every emitted prompt, in every phase, always. No agent, no cost — you run it inline.
**Blocks:** emission. A failing prompt is fixed, not shipped with a caveat.

### A1. Syntax `[T] (verified 2026-07-26)`

- [ ] Every parameter is at the **absolute end** — no descriptive text after the first `--`
- [ ] Exactly one space before each `--`; no space *inside* the dashes (`- - ar` fails)
- [ ] **No punctuation in the parameter block** — no commas, periods, or semicolons between or after flags
- [ ] Flag names spelled correctly: `--raw` (not `--style raw`), `--ar`, `--s`/`--stylize`, `--c`/`--chaos`

### A2. Value ranges `[T] (verified 2026-07-26)`

- [ ] `--s` 0–1000 · `--c` 0–100 · `--sw` 0–1000 · `--ow` 1–1000 · `--iw` 0–3
- [ ] `--q` is **1, 2, or 4** — `0.25` and `0.5` are invalid in V7/V8
- [ ] `--ar` within 14:1 — and within **4:1 if `--hd` is present**

### A3. Compatibility `[T] (verified 2026-07-26)`

- [ ] `--oref` is **not** combined with `--draft`, Fast Mode, `--q 4`, or Conversational Mode
- [ ] Moodboard `--p` is **not** combined with `--sv` or `--sw`
- [ ] `--sv` is **absent** unless the user explicitly asked for it (no documented V8 behavior)
- [ ] `--sref random` / style codes are not paired with an `--sv` other than 4 or 6
- [ ] No V6-era `--sref` code on a V7/V8 job `[C] (Wade McMaster, PEl1Rb9spsk)`
- [ ] **Pipeline mode** — the consistency flag is an unresolved `{style:…}`/`{char:…}` slot handed
      down by `visual-prompts`, never a literal code, and it sits **last in the flag block**, after
      `--ar`/`--raw`/`--s` (Gate C's C16 rejects an invented code; C18 rejects a slot placed before
      the first ` --`)

### A4. Prompt body

- [ ] **No banned buzzwords**: `photorealistic`, `hyperrealistic`, `8k`, `4k`, `ultra-detailed`,
      `masterpiece`, `highly detailed`, `trending on ArtStation`, `award-winning`, `best quality`
      (`prompt-architecture.md`)
- [ ] Layers 1, 2, and 4 are present at minimum — medium, subject, environment
- [ ] For `photographic` look: layers 6 and 7 (optics, lighting) are present, not implied
- [ ] Prompt stands alone — Midjourney carries **no context between jobs** `[T]`
- [ ] `No Text.` present if the brief involves on-screen copy

### A4b. Pipeline density `[I]` — pipeline mode only

- [ ] **All nine layers present** with concrete renderable content — medium, subject, action/state,
      environment, composition/angle, optics *(Register A only)*, lighting, color/atmosphere, parameters
- [ ] Body is **>= 10 comma-separated clauses and >= 60 words** (Gate C's C12)
- [ ] Prompt is a **single contiguous line**, `No Text.` last before the flags (Gate C's C13)
- [ ] `register: A` carries `--raw` with `--s` 80-120; `register: B` carries no `--raw` with
      `--s` 400-700 (Gate C's C14)
- [ ] `register: B` contains **no** `DSLR`, `shot on 35mm film`, `documentary`, focal length or
      f-stop (Gate C's C10)
- [ ] Shot class, scale, and camera height are each a member of their closed vocabulary — not a
      typo or a free-text stand-in (Gate C's **C15**) `[I]`

This section is an `[I]` adaptation for pipeline mode and does **not** apply to standalone jobs,
where "Short usually beats long" `[C] (Tokenized AI, vezJXJGQMoY)` still governs.

### A5. Stage discipline — the token-waste guard

- [ ] Flags match the declared stage (`render-economics.md`)
- [ ] **`moodboard` / `explore` / `profile` carry no `--hd`, no `--q 2`+, and no `--oref`** — these
      stages terminate at Phase 1 by design
- [ ] `--hd` appears only at `production`
- [ ] `--q 2`+ appears only at `production`, and only after composition is locked (`--q` affects the
      first grid only `[T] (verified 2026-07-26)`)
- [ ] **`--q 2`+ requires `budget: no limit`.** At `budget: normal` or `cheap`, `--q` stays at 1 —
      the control-surface mapping in `SKILL.md` gives `--q 2`+ to `no limit` only. *(This check exists
      because Gate B caught exactly this violation in the worked example; the stage was right and the
      budget was ignored.)*
- [ ] `--relax` present when `budget: cheap`
- [ ] A `--seed` is present at `production` when the job belongs to a **set** — an unseeded hero
      render is unreproducible, and `--hd` differs from SD even at the same seed
      `[C][T] (Future Tech Pilot, Tv1dfGcOSnA / t_xIYKk2ERk)`

### A5b. Style-code sanity `[T] (verified 2026-07-26)`

- [ ] If `--sref <code>` is present, the code was **validated against this subject** at SD — codes
      render differently per subject `[C] (Future Tech Pilot, GAT5A6MqM-E)`. An unvalidated code on
      an `--hd` job is a blind expensive render
- [ ] If `--sref <code>` is present, confirm the account's `--sv` is 4 or 6 — codes silently do
      **nothing** otherwise, and the render burns anyway
- [ ] `--sw` was **chosen**, not left at the 100 default, when the prompt also specifies lighting a
      style code would override `[I]`

### A6. Provenance

- [ ] Every normative line in the emitted output carries `[C]` / `[I]` / `[T]` / `[T-unverified]`
- [ ] Any `[T-unverified]` claim load-bearing on this job is **stated as uncertain**, not asserted

**On failure:** fix and re-lint. Report which checks failed in the output's `VALIDATION` line — a
silent fix teaches the user nothing about why their instinct was wrong.

---

## Gate B — fresh-agent adversarial art direction

**Fires:** at `production` stage only, before the `--hd` render.
**Blocks:** emission of the production prompt until findings are resolved or the user overrides.

Dispatch a **fresh `general-purpose` agent**. Give it the prompt, the control surface, and the brief —
but **not your authoring rationale**. An agent that has seen why you made a choice will rationalize it;
one that hasn't has to judge the artifact. Its job is to **find the failure**, not to approve.

This is a net-new pattern for this repo `[I]` — no corpus finding backs it. It is here because the
production render is the one step where being wrong costs real money and a wrong prompt looks exactly
like a right one until it renders.

### Verbatim dispatch prompt

Substitute the bracketed values. Do not soften the adversarial framing — a validator told to "check"
returns "looks good."

```
You are reviewing a Midjourney V8.2 prompt before an expensive production render. Your job is to
FIND THE FAILURE, not to approve it. Assume it is flawed and locate the flaw. "Looks good" is a
failed review — if you genuinely find nothing, say which specific checks you ran that came back clean.

THE BRIEF (what the user actually wants):
[one-paragraph statement of the brief, in the user's terms]

CONTROL SURFACE:
  subject / stage / look / format / consistency / literalism / variance / budget / register
  [the nine resolved values]

THE PROMPT:
[full prompt string including all parameters]

Midjourney V8.2 renders prompts literally and weights earlier words more heavily than later ones;
words far back in a prompt often fail to appear at all.

Evaluate against the 9-layer architecture — 1 medium, 2 subject, 3 action/pose/state,
4 environment, 5 composition/angle, 6 optics/lens/depth-of-field, 7 lighting mechanics,
8 color palette/atmosphere, 9 parameters — and answer:

1. WHICH LAYER IS WEAKEST? Name the one layer most likely to render wrong or generic. Quote the
   text that is doing (or failing to do) that job.
2. WHERE WILL LITERAL READING BITE? Find any phrase a literal-minded model would render in a way
   the brief clearly did not intend — ambiguous referents, unintended objects, physically
   contradictory descriptions (a light direction that fights the stated shadow, a lens/aperture
   that contradicts the stated depth of field).
3. WHAT IS BURIED? Name anything important sitting so late in the prompt it will likely be dropped,
   and say what should move forward.
4. DOES THE FLAG STACK MATCH THE STATED INTENT? Particularly: does --raw / --s match the requested
   look? Does --ar match the stated output format? Is any flag present that the brief does not
   justify?
5. ONE CONCRETE REWRITE. Give the full revised prompt string, not a description of changes.

Be specific. "Add more detail" is useless; "layer 7 says 'dramatic lighting' with no direction or
quality — specify hard vs diffuse and where it comes from" is useful.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted facts with file:line citations where applicable
- Recommendation: 1–3 sentences
- Open questions: only if genuinely blocking

DO NOT:
- Paste full file contents or reproduce tool output verbatim
- Restate the task or narrate your process
- Include a preamble, closing summary, or sign-off
```

### Handling the result

- **Surface the findings to the user** `[I]` alongside the revised prompt. Never auto-apply a rewrite
  silently — the user may have wanted the thing the agent flagged.
- If Gate B's rewrite changes parameters, **re-run Gate A** on it. An art-direction fix can easily
  introduce a syntax or compatibility failure.
- If the user overrides a finding, note the override in the archive block so the next run doesn't
  re-litigate it.
- **Never claim a gate passed without running it.** `[I]`

### When Gate B is skipped

At `moodboard`, `explore`, `profile`, `draft`, and `refine`. Say so explicitly in the output
(`Gate B: n/a — [stage]`) rather than omitting the line, so a skipped gate is never mistaken for a
passed one.
