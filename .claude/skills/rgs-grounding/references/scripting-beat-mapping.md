# Scripting Beat Mapping

How a Grounding Brief's brand-bound Hook → Turn → Payoff → Reframe spine maps onto
`shorts-scripting`'s generic Hook → Setup → Build/Value → Payoff → Loop/CTA spine. This mapping
is stated once, here — a Grounding Brief's own Handoff section states only the per-brief
judgment call this mapping still leaves open (see below), never a repeated restatement of the
mapping itself.

## The fixed mapping

- **Hook → Hook.** Direct — use the brief's Hook content as-is for the script's Hook beat.
- **Turn → Setup + early-Build.** The brief's Turn beat names the mechanism plainly (e.g. "this
  isn't about X, it's the same instinct [thinker] named"). Exactly where inside
  `shorts-scripting`'s Setup (3–8s) and early Build/Value (8–~15s) this lands is a per-brief
  judgment call — state it explicitly in the brief's Handoff section (see "Per-brief judgment"
  below), don't leave it to `shorts-scripting` to guess.
- **Payoff → the Build's required proof beat, or Payoff itself.** `shorts-scripting` requires at
  least one concrete proof beat inside Build/Value (its `[I]`-marked proof-beat rule,
  `shorts-scripting/SKILL.md:40-47`). A Grounding Brief's Payoff content — a research finding,
  ideally the source file's own Content Hook — is frequently *exactly* that proof beat. Whether
  it lands in Build/Value as the proof beat or later in the script's own Payoff beat is a
  per-brief call, driven by whether the finding is best used to build the case (Build/Value) or
  resolve the Hook's question (Payoff) — state which one the brief intends.
- **Reframe → split.** The brief's Reframe is a full argumentative move (typically 2–3
  sentences). It does not become the Loop/CTA beat wholesale — `shorts-scripting`'s Loop/CTA is
  5–12 words and must mirror the Hook's phrasing (`shorts-scripting/SKILL.md:107`). Instead:
  - The Reframe's argumentative body lands in the script's own **Payoff** beat (after or combined
    with the research finding, if the finding didn't already fill Payoff above).
  - Only the Reframe's **kicker line** — the one-sentence takeaway ("it was never about your
    kid's talent — that's the good news," in the worked examples) — gets echoed in the
    **Loop/CTA** beat, reworked to mirror the Hook's own phrasing per `shorts-scripting`'s rule,
    never restated in full.

## Per-brief judgment

Every Grounding Brief's Handoff section states, in one or two lines, the two calls this mapping
leaves open for that specific brief:

1. Where the Turn content lands (Setup vs. early-Build) and roughly when.
2. Whether the Payoff content (the research finding) is the Build's proof beat or the script's
   own Payoff beat.

This is genuine per-brief editorial judgment — it depends on how substantial the research finding
is and how much setup the thinker's mechanism needs — not a restatement of the fixed mapping
above, which never changes brief-to-brief.

## Marker and constraint carry-through

The citation text handed to `shorts-scripting` keeps its `[THINKER: ...]` / `[RESEARCH: ...]`
markers intact — `shorts-scripting` preserves them in the script output rather than stripping
them, and restates quotability (quote-ok / paraphrase-caution) at every beat that uses a
citation. Any citation carrying a publish-time constraint (e.g. a mandatory safety-resource line)
is stated as a **"constraints that survive to publish"** line in the brief's Handoff section —
`shorts-scripting` copies this line verbatim into its own Delivery notes field so it reaches
`shorts-assembly` and `social-repurpose` without either skill needing brand-specific knowledge.
