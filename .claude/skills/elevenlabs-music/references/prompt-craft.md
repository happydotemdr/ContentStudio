# Prompt craft — the UI prompt, styles, the copyright guard, and arc translation

Distilled from `docs/elevenlabs-music-runbook.md` §1, §4.

This is the reference for Stage C's **UI PROMPT** artifact — the prompt body pasted into the
elevenlabs.io Music app — and for the style vocabulary that also feeds `positive_styles` /
`negative_styles` on a composition plan.

## The UI prompt body — self-contained, no external context `[I]`

The Music app has no access to this conversation, the script, or the Bed Arc. Write the prompt as a
**complete, standalone brief** — genre/mood, tempo feel, instrumentation, structure, and the
instrumental instruction, all in the prompt text itself. Never write something that only makes sense
with context the app doesn't have (e.g. "match the previous section" — the app has no previous
section unless it's inside the same generation).

`prompt` and `composition_plan` are **mutually exclusive on the compose endpoint** `[T]` — a UI
prompt is the prompt-mode path, and it uses `force_instrumental` for the vocal guard rather than
`negative_styles` (`composition-plans.md` covers the plan-mode equivalent). Do not mix the two
techniques in one artifact: a prompt-mode job sets `force_instrumental: true`; a plan-mode job relies
on `negative_styles` on every chunk.

## Include / Exclude Styles `[T]`

`positive_styles` and `negative_styles` (prompt mode calls these Include/Exclude Styles in the UI;
plan mode uses the same field names per-chunk) are:

- **English-only** `[T]`
- **Capped at 50 items each** `[T]` — confirmed on both the compose-endpoint parameter table and the
  composition-plans how-to guide
- Best used as **short, concrete tokens** (genre, instrument, mood, era, mix character), not full
  sentences — a style array reads more like tags than prose `[I]`

## BPM, key, and instrument cues `[I]`

None of this is documented as a dedicated parameter — BPM and key are **prompt-text conventions**,
not structured fields. State a tempo feel in words ("mid-tempo, unhurried," "driving, 120ish BPM")
rather than inventing a numeric field the API doesn't expose. Instrument cues work the same way:
name the instrument as a style token ("solo piano," "warm analog synth pad," "sparse acoustic
guitar") rather than assuming a dedicated instrumentation parameter exists.

## Vocal isolation in prompt mode `[T]`

`force_instrumental` (boolean, default `false`, **prompt-only**) — when `true`, the docs state it
"guarantees that the generated song will be instrumental." This is the one instrumental mechanism
with a documented guarantee — contrast with the plan-mode `negative_styles` technique, which is
`[T-unverified]` on real-world efficacy (`composition-plans.md`). If the job can run in prompt mode
and instrumental is a hard requirement, `force_instrumental: true` is the stronger guarantee; a
`music_v2` plan gives beat-locked chunk control that prompt mode cannot, at the cost of an unverified
vocal guard. Say this trade-off out loud when the user's priority is "definitely no vocals."

## Descriptor layering `[I]`

Layer descriptors from broad to specific, the same craft pattern as image-prompt layering in
`midjourney-prompting`: genre/era first, then mood, then a production/mix character, then a specific
instrument or texture detail last. A prompt that opens with the most specific detail and buries the
genre tends to under-specify the overall shape the model needs to lock onto first.

## The copyright guard — and its full recovery path

Naming a band, musician, or copyrighted lyrics returns a `bad_prompt` error; naming a copyrighted
style inside a composition plan returns a **separate `bad_composition_plan` error** `[T]` — the
plan-mode variant is new to this verification pass and was not in the original design brief.

> **Never put an artist, band, or track name in any style string or prompt body** `[T]` — it trips
> the guard, and it is the one prompt-craft mistake that costs a whole generation. Describe the
> *sound* ("moody synth-pop with a driving bassline"), never the artist ("sounds like [Artist]").

The error is documented as carrying `detail.data.prompt_suggestion` — a clean rewritten prompt to
retry with — per the 2026-08-06 verification pass, though **the exact field path was not
independently re-observed in that pass's fetches**, so treat the field name itself as
`[T-unverified]` pending direct reproduction; the existence of the `bad_prompt` /
`bad_composition_plan` error-and-retry mechanism itself is `[T]`.

**Recovery path** `[I]` — a craft/process recommendation, not a documented vendor procedure:

1. **Catch the error.** Don't retry blind — read the response body first.
2. **Read `detail.data.prompt_suggestion`** (or the plan-mode equivalent field, if present) — the
   vendor's own rewritten version of what you sent.
3. **Diff it against the original** prompt or style string to see exactly which token was removed or
   rewritten. That diff tells you which word tripped the guard — usually an artist/band name or a
   line lifted too close to copyrighted lyrics.
4. **Retry with the suggestion**, not with a guess. If the suggestion also fails, remove the
   suspected token yourself and retry once more before escalating to the user.

## Translating a Bed Arc into style vocabulary `[I]`

The Bed Arc from `music-brief` names movements in **feeling words** ("warm and light," "quiet
gravity," "relief") — the corpus's vocabulary. Eleven Music's `positive_styles` / `negative_styles`
need **concrete tokens** — genre, instrument, production texture. This table is this skill's own
craft inference for bridging the two, not a documented vendor mapping or a corpus finding:

| Arc feeling word | Candidate style tokens `[I]` |
|---|---|
| Warm and light | `warm`, `soft piano`, `gentle strings`, `major key`, `airy`, `low percussion` |
| Rising urgency | `building`, `driving percussion`, `rising strings`, `subtle tension`, `mid-tempo` |
| Quiet gravity | `sparse`, `solo piano`, `minor key`, `slow`, `intimate`, `low dynamics` |
| Relief | `open`, `warm strings`, `resolving`, `gentle build-down`, `major key`, `hopeful` |
| Playful | `light percussion`, `pizzicato strings`, `major key`, `bouncy`, `upbeat` |
| Melancholy | `minor key`, `slow`, `sparse piano`, `subdued`, `reflective` |

Treat this table as a starting shortlist, not a lookup. **Every chunk's `negative_styles` still
carries the vocal guard** (`["vocals", "singing", "spoken word", "lyrics"]`, `composition-plans.md`)
regardless of which positive tokens are drawn from this table — the two lists are independent and
both required on every chunk.

**Never let a style token drift into naming a real artist, track, or band** while translating a
feeling word into a genre reference (e.g. describing "quiet gravity" by genre and instrumentation,
not by naming a specific artist known for that mood) `[T]` — the copyright guard above applies
identically here.
