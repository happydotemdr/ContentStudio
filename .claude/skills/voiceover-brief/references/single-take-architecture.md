# Single-take generation — the on-request production pipeline for this channel `[P]`

> **`[T]` facts in this file were web-verified 2026-07-23** against live ElevenLabs documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

Markers: `[C]` corpus-cited `(Channel, video_id)` · `[I]` industry practice · `[T]` web-verified
tool/policy fact · **`[P]` project/operator decision** — a call made by this project's owner and
recorded here. `[P]` states what was decided, never why it is correct — never cite it as corpus
or vendor support for anything.

## The rule `[P]`

**Voiceover for this channel is generated as ONE continuous ElevenLabs call** — the full script,
beats joined with `<break time="Xs" />` tags (`elevenlabs-audio` skill,
`.claude/skills/elevenlabs-audio/references/model-routing.md`) — rather than one call per beat. The resulting `/with-timestamps`
alignment (`docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-implementation.md`) is the
one source of truth for stem placement, ducking, captions, and shot timing on every render.

Decided 2026-08-19, after direct comparison: the operator listened to both a per-beat-stitched
mix and a single-take mix of the same script and judged the single-take version clearly better —
not a measured quality claim, a listening judgment, recorded here as the reason this pipeline
exists, not as its justification.

**Superseded as the unrequested default 2026-08-20** — see "Default sectioning choice:
multi-segment" at the end of this file. The rule above still governs whenever single-take is
requested.

## What this trades away — stated plainly, not silently

`docs/elevenlabs-voiceover-guide.md:96` `[T]`, citing `(Nick Nimmin, IF-PD6XMjYY)`:

> "Generate section-by-section. Don't render one giant block. Section-level generation lets you
> control pacing and re-roll a bad read cheaply — the same logic human narrators use when they
> record each line 2–3 times to have options in the edit."

This channel's own production history backs that reasoning directly: `VO1_provoice_take2.mp3` and
`VO7_provoice_take2.mp3` (the hook and CTA re-rolls from the render that motivated this decision)
are exactly the per-beat re-rolls the corpus describes. **Single-take generation gives that up.**
A flub anywhere in the script means regenerating the whole take — and because TTS is
non-deterministic, every other beat's audio comes out slightly different on a regenerate too,
so a partial fix is not available even in principle with this architecture.

This `[P]` decision overrides that corpus guidance **for this channel's production pipeline**,
on the operator's own judgment of the trade-off, not because the corpus's reasoning was wrong.

## What was verified, not just decided

- `[T]` (verified 2026-08-19) `<break time="Xs" />` works cleanly at 7 breaks across ~950
  characters — no speed-up artifact, no LRA collapse
  (`docs/superpowers/plans/2026-08-19-vo-architecture-test-plan.md` §6c, Call 1/2).
- `[T]` (verified 2026-08-19) `/with-timestamps` gives exact break-timing ground truth (median
  error 69ms, max 207ms across 7 real breaks) — eliminating the need to acoustically guess pause
  locations after the fact.
- `[I]` Splitting the single take at those exact measured boundaries back into per-stem files
  restores `stitcher`'s automatic ducking to its exact designed behavior (`envelope.level_at()`
  returned precisely `gain_db`/`duck_db`, a +7.00dB swing, confirmed directly against the envelope
  math, not inferred from noisy audio measurement) — same doc, §6c, "free follow-up" section. This
  one is this project's own engineering finding, not a vendor fact, hence `[I]` rather than `[T]`.

## Scope boundary

This is a **channel production-pipeline** decision, not a `voice-selection.md` or
`channel-voice.md` change — the pinned voice (`eDwT8Vhp2yxJzAMmuuPA`) and its rationale are
unaffected. It is also not a blanket recommendation for every ElevenLabs job this skill might
support in standalone mode (see `elevenlabs-audio`'s own scope note) — a one-off narration job
with no re-roll history and no downstream timing-derivation pipeline has no reason to adopt this.

## Default sectioning choice: multi-segment `[P]`

**Confirmed 2026-08-20:** absent a specific request for single-take, `voiceover-brief` should default to
multi-segment (per-beat) sectioning rather than reaching for this file's single-take architecture. This is the
operator's explicit, standing preference after a real side-by-side render comparison — **it is not a technical
finding against the architecture documented above**, which remains valid, unmodified, and already validated
(`docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md`). The comparison that informed this
preference actually tested a different, zero-VO-processing package (`native-pipeline`), not this file's
pipeline — see `docs/superpowers/plans/2026-08-20-dual-pipeline-vo-music-test-RESULTS.md` for the full caveat.

**When to still use this file's pipeline:** whenever the user explicitly asks for single-take generation, or
asks to re-run the comparison against this specific (preconditioned) implementation rather than
`native-pipeline`. Nothing about the rule above prevents that — it only changes the unrequested default.
