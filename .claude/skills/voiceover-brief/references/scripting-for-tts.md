# Formatting the script for TTS

> **`[T]` facts in this file were web-verified 2026-07-23** against live ElevenLabs documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

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

## Numbers: always spell them out, considering how they're meant to be vocalized `[P]`

**Every number in a TTS script should be respelled as words in the source text — never left as digits for the
model's own normalizer to interpret.** This is a project decision, recorded after a real, measured failure:
ElevenLabs' `apply_text_normalization: "auto"` produced an audible stutter on "2,556" (a repeated-adjacent-digit
number) — character-level `/with-timestamps` alignment showed individual digits rendering at 3-4x their normal
duration (441-603ms vs. a ~150-175ms baseline), while the visually similar "2,300" elsewhere in the identical
take rendered cleanly. Respelling fixed it completely (verified: zero anomalous character durations across the
full respelled take) `[P]` (`docs/superpowers/plans/2026-08-20-dual-pipeline-vo-music-test-RESULTS.md`).

**How to respell, by number type** `[I]` — this project's own extrapolation from the fix above, not a
separately corpus- or vendor-documented rule. The specific ElevenLabs rendering behaviors below (comma-as-pause,
year cadence, compound-adjective misparsing) were **not independently measured** — only the fix for "2,556" and
"2026" was actually tested. Treat these as this skill's best-guess taxonomy, not verified facts:

- **Counts/quantities:** `[I]` full cardinal words — `2,556` → "two thousand, five hundred fifty-six".
- **Years:** `[I]` the natural two-digit-pair spoken form, not a cardinal count — `2026` → "twenty twenty-six",
  not "two thousand twenty-six" (untested hypothesis for *why* — the tested fact is only that the
  cardinal-count form for this specific year showed a smaller, milder version of the same digit-elongation
  artifact).
- **Compound adjectives** `[I]` (a number modifying a noun with hyphens, e.g. "2,300-year-old"): hyphenate the
  whole spelled-out phrase — "two-thousand-three-hundred-year-old", not "two thousand three hundred year old"
  (untested hypothesis for why the unhyphenated form would misread).
- **Break-tag attribute values are exempt** `[I]` — `<break time="0.9s" />`'s `"0.9s"` is SSML syntax, never
  spoken text, and must stay numeric. Only respell text the model will actually vocalize.

Flag any number this taxonomy doesn't cleanly cover (currency, phone-number-style digit strings, decimals) in
the brief rather than guessing — those weren't tested in the finding above.

**This respelling applies to the TTS payload text only — never to on-screen caption/overlay text `[P]`.**
Operator decision, 2026-08-20: captions and overlay cards must display numbers as numerals ("2,300 years old.",
not "two thousand three hundred years old."), even though the VO payload sent to ElevenLabs spells them out.
The two text tracks are allowed to diverge — a script's *spoken* form and its *written/displayed* form serve
different readability needs, and this is standard captioning practice, not unique to this pipeline. **Concrete
consequence for whoever builds the caption/overlay text:** derive it from the original numeral-form script (or
hand-write it with numerals directly), never by copy-pasting the respelled TTS payload text. See
`caption-overlay-system.md`'s matching note.

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
