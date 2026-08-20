# Formatting the script for TTS

Distilled from `docs/elevenlabs-voiceover-guide.md` §4 and the delivery-mechanics findings in
`docs/headless-youtube-audit.md` §5. A script written for the eye reads flat through a TTS
model — write (and reformat) for the ear.

## Formatting moves

- **Break into short sentences.** `[C]` Long clauses run the model out of breath and blur the
  meaning — this mirrors human delivery advice that the final words in a line carry the
  meaning, so don't let energy (or, here, the model's phrasing) trail off at the end of a
  clause `(Kallaway, ZM3elcBE48I)`.
- **Use punctuation as pacing.** `[T]` Commas, ellipses (`…`), and line breaks place breaths and
  beats `[T]`. A period is a full stop; an ellipsis is a held pause. Add these deliberately when
  reformatting a script that was written for reading rather than speaking.
- **Use v3 audio tags for emotion, not capitals `[T]`.** In Eleven v3, add emotion inline —
  `[excited]`, `[whispers]`, `[sighs]`, `[laughs]`, `[sarcastic]` — placed immediately before
  the words it should color. Capitals get read as an acronym or ignored outright; a tag is the
  reliable lever `[T]`.
- **Respell tricky words phonetically `[T]`.** Brand names, acronyms, and unusual terms
  mispronounce often — respell them the way they sound (e.g., `nginx` → `engine-x`).
- **End declarative lines on a downward inflection, not upspeak.** `[C]` Upspeak reads as
  uncertainty; keep the CTA and any confident claims phrased so the natural TTS read lands
  down, not up, at the line's end `(Kallaway, ZM3elcBE48I)`.
- **Section the script instead of one giant block `[T]`.** Generate section-by-section (hook /
  beat / CTA, or shot-by-shot if the upstream script is shot-timed). This gives pacing control
  and lets you **re-roll a single bad read cheaply** — the same logic human narrators use when
  they record each line 2–3 times to have options in the edit `(Nick Nimmin, IF-PD6XMjYY)`.

## Before generating: does the script sound like a person?

A subtle but real corpus point, independent of any TTS setting: **lines the writer doesn't
believe read as hollow, even synthetically.** If the script was AI-drafted, spend a few minutes
tweaking it into natural phrasing before committing it to the voice
`(Kallaway, ZM3elcBE48I)`. The "coffee-shop method" — write as if talking to a friend — keeps
delivery from going stiff, whether the read is human or synthetic
`(Dan the creator, bTr-Izh9pkc)`.

`[I]` When producing a voiceover brief, flag any line in the input script that reads as
written-for-the-eye (long, subordinate-clause-heavy, or jargon-dense) and propose a
TTS-friendly rewrite alongside it — don't silently pass such lines through. This procedural
step is this skill's own operationalization of the "sound like a person" finding above, not
a separately corpus-cited rule.

## Output convention for this skill

When annotating a script for TTS, mark it up inline rather than describing changes in prose,
placing the tag immediately before the words it colors, per the source guide's documented
syntax `[T]`:

```
[excited] Ever wonder why your Shorts stop at 3 seconds? That's not bad luck… it's the
algorithm testing you.
```

Only `[excited]`, `[whispers]`, `[sighs]`, `[laughs]`, and `[sarcastic]` are confirmed by the
corpus's source material — the guide does not document a closing-tag syntax, so don't invent
one. Verify the current Eleven v3 tag vocabulary/syntax at elevenlabs.io/docs before production,
since this is a fast-moving `[T]` surface (dated 2026-07-23).
