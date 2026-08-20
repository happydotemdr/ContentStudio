# Bake In Dual-Pipeline VO+Music Test Learnings — Implementation Plan (rev. 3)

> **rev. 3 changes (operator directives, post-rev.-2 review):** (1) multi-segment is now confirmed as the
> standing sectioning default — recorded as a narrowly-scoped new section in `single-take-architecture.md`
> plus a `SKILL.md` routing update, NOT a supersession of that file's validated pipeline (Task 3, Steps 4-5).
> (2) Captions/overlays must display numbers as numerals even though the VO payload spells them out for TTS —
> new rule in both `scripting-for-tts.md` (Task 2) and `caption-overlay-system.md` (Task 5), plus a concrete
> fix to four of Task 6's validation-render caption entries that had inherited the spelled-out VO text
> (Task 6, Step 4). (3) The captions-are-sidecar-only finding is confirmed as the actual deliverable wanted
> (not a gap to fill with a new burned-in-captions feature) — no follow-up feature is in scope.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Revision note:** rev. 1 of this plan was reviewed by a fresh Opus agent with direct filesystem/artifact
> access and returned a **NEEDS REWORK** verdict: two of the four findings it existed to institutionalize were
> misdiagnosed. This revision incorporates every confirmed finding from that review. The two big corrections,
> read this before anything else:
>
> 1. **The "multi-segment beats single-take" claim was a confounded comparison.** This session's "Track B" used
>    `native-pipeline` — a *separate, deliberately zero-VO-processing* package
>    (`docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md`) whose own design doc
>    already predicted and accepted exactly the failure mode this session reproduced 3/3 times. It is **not**
>    the same single-take implementation `single-take-architecture.md`'s `[P]` pin describes — that pin
>    describes `stitcher`'s own preconditioned single-take chain (`vo_split.py` → `precondition.condition_clip`
>    → `audio.build_audio`), which passed all 5 validation criteria on its first real run
>    (`docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md`) and is untouched by anything in
>    this session. **`single-take-architecture.md` is not being superseded by this plan.** Task 3 below is
>    rewritten accordingly.
> 2. **The duck-depth diagnosis had `gain_db`/`duck_db` backwards.** `duck_db` — not `gain_db` — is the level
>    "ducked under vocals," which is what the corpus's −21/−22dB figure describes and what actually governs
>    audibility for a take that's speaking almost continuously. The old spec's `duck_db: -29.0` sat 7–8dB below
>    the corpus number; `gain_db: -22.0` (the un-ducked baseline, which matters only in real silence) was not
>    the problem. The corrected pair (`gain_db: -14.0 / duck_db: -21.0`) is **not a new guess** — it already
>    matches this repo's own `stitcher/renders/do-less-sold-as-win-more/render-spec.json` and lands `duck_db`
>    exactly on the corpus's cited band. Task 4 keeps the same corrected numbers as rev. 1 but replaces the
>    entire rationale — the old rationale wrongly speculated the corpus finding itself didn't apply here.

**Goal:** Fold three confirmed findings from the 2026-08-20 dual-pipeline VO+music test (number respelling
fixes TTS stutters; `gain_db`/`duck_db` were swapped in effect, making the bed nearly inaudible; captions/cards
should move to Montserrat at sizes that actually reach this project's own documented ranges) into the skill
docs and reference defaults that govern every future Short — plus record, accurately scoped, that
`native-pipeline`'s already-documented "zero VO processing" accepted risk has now fired in 3/3 real attempts.

**Architecture:** Documentation/reference-default change, not application code, except where Task 6's
validation render edits one test workspace's `render-spec.json` (not the protected original Short). One dated
evidence record captures the raw, artifact-verified test data; skill reference files cite it; one validation
task re-renders Track A with every new default applied together, with explicit pass/fail predictions stated in
advance (not just "run it and see"), so a surprise is caught rather than rationalized after the fact.

**Tech Stack:** Markdown skill references (`.claude/skills/**/references/*.md`), the `stitcher` render pipeline
(Python/ffmpeg/Pillow) for the validation render, `C:\Windows\Fonts\Montserrat-*.ttf` (installed system-wide,
confirmed 2026-08-20), `stitcher.overlays.wrap_lines`/`parse_accent` for offline wrap-line verification (no
render needed to check text layout).

## Global Constraints

- Every new normative line added to a skill reference needs a marker (`[C]`/`[I]`/`[T]`/`[P]`) per this repo's
  anti-generic guarantee (root `CLAUDE.md`). **`[P]` carries only the bare decision — the value chosen.** Any
  procedure, recommendation, or causal inference attached to it gets its own `[I]` line with an explicit
  "this project's own extrapolation, not corpus-cited" disclaimer, matching the pattern already used in
  `single-take-architecture.md`'s "free follow-up" finding and `production-and-loudness.md`'s "music too quiet
  beats too loud" line. Never let a `[P]` line cast doubt on an adjacent `[C]` citation — if a `[C]` finding
  turns out to have been misapplied (see the duck-depth correction above), say precisely how it was misapplied,
  never that the corpus was wrong.
- Never delete a superseded decision — mark it superseded in place (`channel-voice.md`'s `voice_id`
  supersession is the worked example). Nothing in this revision supersedes anything, per the correction above —
  if that changes during execution, follow this convention rather than editing history out.
- `stitcher/renders/stop-over-specialization-in-youth-sports-20260811-004711/` (the original validated Short)
  must not be touched. Changes land in skill references and in the `multiseg-test` workspace only.
- No new billed API calls needed anywhere in this plan — Task 6 reuses already-generated audio from this
  session. If execution discovers a step actually needs a fresh TTS/music call, stop and confirm with the user
  first, per this project's standing billing-confirmation practice.
- Every numeric claim in this plan was checked against an on-disk artifact or a real measurement during the
  Opus review or this revision (loudnorm JSON files, `render-spec.json` contents, Pillow-measured cap heights,
  `stitcher.overlays.wrap_lines` output) — not asserted from memory. Where a task still can't verify something
  without running the actual render (e.g. the final loudnorm outcome), it states a numeric prediction to check
  the real result against, not just "run it and see."

---

## Evidence this plan cites (read first)

Three confirmed findings, each with artifact-level evidence, plus one accurately-scoped fourth item:

1. **Number-respelling fixes a real TTS stutter.** Character-level `/with-timestamps` alignment on "2,556"
   showed a `5` rendering at 603ms and a `6` at 441ms — 3–4x the ~150–175ms baseline every other digit in the
   same take showed (verified against "2,300" elsewhere in the identical take, which rendered cleanly at
   117–174ms/digit). Respelling as "two thousand, five hundred fifty-six" produced zero anomalies (full-take
   character scan: 0 characters over 250ms outside natural punctuation pauses). A milder version of the same
   artifact was found on "2026" (a `0` at 603ms); respelled to "twenty twenty-six," also clean.
2. **`duck_db`, not `gain_db`, is what the corpus's −21/−22dB "ducked under vocals" figure describes** —
   confirmed by reading `stitcher/audio.py`'s own comments (`conform_gain` uses `gain_db` as the un-ducked
   baseline; the envelope lands "exactly on `duck_db` relative to voice" at a duck breakpoint). The
   `stop-over-specialization` render-spec had `duck_db: -29.0` — 7–8dB below the corpus's own cited band —
   while `gain_db: -22.0` (the un-ducked baseline, irrelevant for a near-continuously-speaking take) was
   incidentally close to the band and got blamed instead. Direct operator listening feedback on two finished
   masters using these exact numbers: "totally washed out nearly inaudible in the background." Independent
   corroboration: `docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md`'s Problem
   section, written before this session, already root-caused the *same* `-22`/`-29` pair as leaving the bed "at
   roughly -42 LUFS integrated for ~94% of the runtime — effectively inaudible" for the single-take case. And
   `stitcher/renders/do-less-sold-as-win-more/render-spec.json` — an existing, different Short in this same
   repo — already uses `gain_db: -14.0 / duck_db: -21.0`, the exact corrected pair this plan proposes.
3. **`native-pipeline`'s documented "zero VO processing" accepted risk fired in 3/3 real attempts.**
   `docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md` ("Decisions" section)
   explicitly predicted this failure mode in advance ("an unusually hot take… can require enough gain… to
   overshoot the -1 dBTP delivery ceiling… This mode accepts that failure mode deliberately") and its "Open
   risks" section states: "If either fires often in practice, that's a signal to revisit 'zero processing.'"
   This session ran it three times on real takes — `input_tp` -1.21, -1.43, -2.08 dBTP, all requiring ~+9 to
   +10dB of loudness-matching gain that overshoots the delivery ceiling every time (`EXIT_RENDER=2`, no
   finished video any of the three times). Two independent attempted fixes (loosening the true-peak ceiling;
   retuning VO `stability`/`style` to reduce crest factor) both failed to move the needle. **This is
   confirmation of an already-known, already-accepted risk meeting its own stated revisit threshold** — it is
   not a new discovery that some other pipeline is broken, and it says nothing about `stitcher`'s own
   preconditioned single-take chain (see the revision note above).
4. **Font/size feedback.** Operator: "increase the size of the text and make sure we are now using the
   installed Montserrat font." `Montserrat-{Thin…Black}[Italic].ttf` confirmed installed system-wide at
   `C:\Windows\Fonts\`. `.claude/skills/shorts-assembly/references/caption-overlay-system.md:12` already names
   "Montserrat ExtraBold" as a caption-style option `[I]` — the render-specs just never followed it, defaulting
   to `arialbd.ttf`. **Important scope correction found during this revision:** `stitcher` composites the 8
   `overlays[]` entries (hook card, re-hook card, 4 stat plates, source card, loop line) as burned-in image
   layers (`stitcher/preflight.py`: "ASS burn-in was rejected in favour of Pillow compositing"), but the
   `captions[]` array / `captions_style` field only drives the `.srt`/`.ass` **sidecar files** — it is never
   composited into the delivered `.mp4` at all (confirmed: `cli.py`'s caption handling writes sidecars only;
   the QA report's `safe_zone` check counts exactly 8 overlays, matching `overlays[]`, never captions). So
   "bigger text" can only be delivered today via the 8 overlay cards — the on-screen spoken-word captions this
   text likely also meant do not currently exist as a burned-in feature at all. Flagged as an out-of-scope gap
   in Task 5, not silently absorbed.

---

### Task 1: Write the dated test-record doc

**Files:**
- Create: `docs/superpowers/plans/2026-08-20-dual-pipeline-vo-music-test-RESULTS.md` (matches this repo's
  existing `<plan-name>-RESULTS.md` naming convention — see `2026-08-19-single-take-vo-pipeline-RESULTS.md`,
  `2026-08-19-fix-bed-vocal-leakage-RESULTS.md`)

**Interfaces:**
- Consumes: nothing (this is the evidence source).
- Produces: a citable, dated record every later task points to by path.

- [ ] **Step 1: Write the doc**, covering the three numbered findings from "Evidence this plan cites" above
  (drop the fourth — the font/size feedback is an operator ask, not a technical finding; it belongs in Task 5's
  own rationale, not here) plus a fourth section explicitly titled "What this test does NOT show," stating in
  its own words the revision note's two corrections (confounded comparison; `native-pipeline` ≠
  `single-take-architecture.md`'s pipeline) so a future reader hits the caveat before the numbers, not after.

  **Evidence-citation correction (from the Opus review):** cite `loudnorm_pass2.json` for the Track B failures,
  not `loudnorm_pass1.json` — pass 1 runs without `linear=true` and reports `"normalization_type": "dynamic"`
  **by construction on every render, including passing ones** (verified: Track A's own passing
  `work/final/audio/loudnorm_pass1.json` also reads `"dynamic"`; the actual gate in `stitcher/audio.py:532`
  reads pass 2). State this explicitly in the doc as a one-line methodology note so nobody re-uses pass 1 as
  evidence of anything later. Quote the three takes' `loudnorm_pass2.json` numbers verbatim (`input_i`/
  `input_tp`/`normalization_type`) — check which are still on disk before writing (this session overwrote take
  1 and take 2's directories when generating take 3; where a take's raw JSON no longer exists, say so and
  quote the number from this plan's own "Evidence" section above with a note that it's transcribed, not
  re-read from a live file).

- [ ] **Step 2: Sanity-read against the actual render artifacts.** Confirm the Track A QA numbers quoted
  (`-13.9 LUFS`, `-1.5 dBTP`, `-7.0 dB duck`) match
  `stitcher/renders/stop-over-specialization-in-youth-sports-multiseg-test/out/stop-over-specialization-in-youth-sports-multiseg-test_v02_qa.md`
  exactly — re-open that file and diff by eye.

- [ ] **Step 3: Commit** (check `git log` for precedent of doc-only commits in this repo before committing
  solo; otherwise leave staged for the end-of-plan checkpoint).

---

### Task 2: Add the number-respelling rule to `voiceover-brief`

**Files:**
- Modify: `.claude/skills/voiceover-brief/references/scripting-for-tts.md`
- Modify: `.claude/skills/voiceover-brief/SKILL.md` (only if step 2 finds it needs a cross-reference)

**Interfaces:**
- Consumes: Task 1's doc path for citation.
- Produces: a new rule voiceover-brief authors read on every future brief (workflow step 4 already sends every
  brief through `scripting-for-tts.md`).

- [ ] **Step 1: Add a new subsection** after "## Formatting moves", before "## Before generating: does the
  script sound like a person?":

```markdown
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

- **Counts/quantities:** full cardinal words — `2,556` → "two thousand, five hundred fifty-six".
- **Years:** the natural two-digit-pair spoken form, not a cardinal count — `2026` → "twenty twenty-six", not
  "two thousand twenty-six" (untested hypothesis for *why* — the tested fact is only that the cardinal-count
  form for this specific year showed a smaller, milder version of the same digit-elongation artifact).
- **Compound adjectives** (a number modifying a noun with hyphens, e.g. "2,300-year-old"): hyphenate the whole
  spelled-out phrase — "two-thousand-three-hundred-year-old", not "two thousand three hundred year old"
  (untested hypothesis for why the unhyphenated form would misread).
- **Break-tag attribute values are exempt** — `<break time="0.9s" />`'s `"0.9s"` is SSML syntax, never spoken
  text, and must stay numeric. Only respell text the model will actually vocalize.

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
```

- [ ] **Step 2: Check `SKILL.md`'s workflow step 4** for whether it needs a cross-reference. Read
  `.claude/skills/voiceover-brief/SKILL.md`'s step 4 text; if it doesn't already gesture at numbers, add one
  clause: `, and respell every number as words (see scripting-for-tts.md)`.

- [ ] **Step 3: Verify markers** — every sentence in the new subsection carries `[P]` or `[I]`; every `[I]`
  line that states an untested hypothesis says so explicitly (per Step 1's instruction above), matching this
  file's existing marker density.

- [ ] **Step 4: Commit**

---

### Task 3: Record that `native-pipeline`'s accepted risk has fired, AND record multi-segment as the standing default

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md` — append to "Open
  risks", do not touch "Decisions" (that section records what was already decided; this is new evidence, not a
  re-decision).
- Modify: `.claude/skills/voiceover-brief/references/single-take-architecture.md` — **add a new, narrowly
  scoped section only** (Step 4 below). Do not touch the existing "## The rule `[P]`" body, its title, or
  anything else in the file — that section documents a different, still-valid, still-untouched pipeline. If
  you find yourself editing anything other than adding the new section at the end, stop — you have mis-scoped
  the change.
- Modify: `.claude/skills/voiceover-brief/SKILL.md` — update workflow step 4's routing logic (Step 5 below).

**Interfaces:**
- Consumes: Task 1's doc path.
- Produces: a dated confirmation entry the `native-pipeline` design doc's own "Open risks" section already
  anticipated needing.

- [ ] **Step 1: Append to "Open risks"** in the design doc, under the existing "Zero VO processing removes the
  one safety net…" bullet:

```markdown
- **2026-08-20 update: this risk has fired.** Three real end-to-end attempts on the same script/voice all hit
  the accepted failure mode above — `input_tp` -1.21, -1.43, -2.08 dBTP, all requiring more loudness-matching
  gain than the -1.0 dBTP delivery ceiling allows, `EXIT_RENDER=2` all three times
  (`docs/superpowers/plans/2026-08-20-dual-pipeline-vo-music-test-RESULTS.md`). Two independent attempted
  mitigations — relaxing the true-peak ceiling to -0.15 dBTP; retuning VO `stability`/`style` toward a flatter
  delivery — both failed to meaningfully change the measured crest factor. Per this section's own stated bar
  ("if either fires often in practice, that's a signal to revisit 'zero processing'"): 3/3 meets that bar.
  **This is a `native-pipeline`-scoped finding only** — it says nothing about `stitcher`'s own preconditioned
  single-take chain (`vo_split.py` → `precondition.condition_clip`), a different, working implementation
  validated in `docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md`. Revisiting "zero
  processing" for `native-pipeline` specifically (e.g. an opt-in precondition step) is a real design decision
  for whoever picks this package back up — not something this note decides unilaterally.
```

- [ ] **Step 2: Report the corrected framing to the user** (this is a plan step, not a file edit): the operator
  described "Track A is the hands-down winner" based on this session's A/B test; that test's single-take arm
  was `native-pipeline`, not the pipeline `single-take-architecture.md`'s `[P]` pin is actually about. This was
  already surfaced and the operator confirmed, with the corrected picture in hand, that multi-segment should be
  the standing default anyway (see Step 4) — this step is a record of that exchange, not a re-ask.

- [ ] **Step 3: Skip if already confirmed.** The corrected-framing conversation in Step 2 already happened in
  this session; if you're executing this plan in a fresh context, treat Step 2 as already satisfied by this
  note and proceed to Step 4 without re-asking the operator.

- [ ] **Step 4: Add a new section to `single-take-architecture.md`**, at the very end of the file, after "##
  Scope boundary" (and after Task 3's own supersession-notice edits, if a future task ever adds one — as of
  this plan, none does):

```markdown
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
```

- [ ] **Step 5: Update `SKILL.md`'s workflow step 4** (`.claude/skills/voiceover-brief/SKILL.md`). Read its
  current wording first — it currently states that `single-take-architecture.md` "supersedes the per-beat
  sectioning above" for this channel. Replace that with wording matching the new default: per-beat sectioning
  is the default; `single-take-architecture.md` is read only when the user explicitly requests single-take
  generation. Keep the rest of step 4 (settings-band derivation, mixed-script handling) unchanged — only the
  routing sentence changes.

- [ ] **Step 6: Commit**

---

### Task 4: Correct the duck-depth default (rationale rewritten, values unchanged from rev. 1)

**Files:**
- Modify: `.claude/skills/voiceover-brief/references/production-and-loudness.md`
- Modify: `.claude/skills/shorts-assembly/references/loudness-and-mix.md`

**Interfaces:**
- Consumes: Task 1's doc path.
- Produces: the corrected `gain_db`/`duck_db` starting point.

- [ ] **Step 1: In `production-and-loudness.md`**, under "## Ducking the music bed", add a new bullet
  immediately after the existing "Corpus creators run noticeably lower..." bullet:

```markdown
- **Parameter-mapping correction, this project `[P]`:** this channel's render-spec implemented the corpus's
  -21/-22dB "ducked under vocals" figure on the wrong key. `stitcher`'s `Bed.duck_db` — not `Bed.gain_db` — is
  the level while the voice is present (`stitcher/audio.py`'s ducking envelope lands exactly on `duck_db`
  relative to voice at a breakpoint); `gain_db` is the un-ducked baseline, which matters only during real
  silence. The render-spec had `duck_db: -29.0` — 7-8dB below the corpus's own cited band — while `gain_db:
  -22.0` incidentally sat near the band and drew the scrutiny instead. For a take that's speaking almost
  continuously, `duck_db` is what an audience actually hears, so this mapping error is what produced direct
  operator feedback that the bed was "totally washed out nearly inaudible"
  (`docs/superpowers/plans/2026-08-20-dual-pipeline-vo-music-test-RESULTS.md`) even though the automated
  duck-depth QA check passed (it only verifies the *swing* matches spec, not that the spec itself is audible).
  **Corrected pair: `gain_db: -14.0 / duck_db: -21.0`** (same 7dB swing, both raised ~8dB) — this puts
  `duck_db` exactly on the corpus's -21/-22dB band and matches this repo's own
  `stitcher/renders/do-less-sold-as-win-more/render-spec.json`, an independent existing precedent, not a fresh
  guess. `[I]`: `gain_db: -14.0` (the un-ducked baseline) sits a few dB above `loudness-and-mix.md`'s own "bed
  sits ~15-20dB below the voice" figure — an acceptable, deliberate consequence of preserving the swing rather
  than a contradiction, since that figure describes the ducked (in-narration) level, which this correction
  targets via `duck_db` instead.
```

- [ ] **Step 2: In `loudness-and-mix.md`** (shorts-assembly), add a parallel note immediately after the
  existing "Audit corroborates..." bullet under "## Ducking (the single most important mix rule)":

```markdown
- **This channel's actual numbers, corrected `[P]`:** don't hand a fresh multi-segment edit plan `gain_db:
  -22.0 / duck_db: -29.0` — that pairing put `duck_db` (the level under voice, what a listener actually hears
  through a near-continuously-speaking take) 7-8dB below this file's own -21/-22dB citation, and drew direct
  operator feedback that the bed was "totally washed out nearly inaudible"
  (`docs/superpowers/plans/2026-08-20-dual-pipeline-vo-music-test-RESULTS.md`). Use `gain_db: -14.0 / duck_db:
  -21.0` (same 7dB swing, both raised ~8dB, `duck_db` now landing exactly on this file's own cited band) —
  already this repo's own precedent in `stitcher/renders/do-less-sold-as-win-more/render-spec.json`, not a
  fresh guess.
```

- [ ] **Step 3: Commit**

---

### Task 5: Update the caption/overlay typography default (Montserrat + verified sizes)

**Files:**
- Modify: `.claude/skills/shorts-assembly/references/caption-overlay-system.md`

**Interfaces:**
- Consumes: Task 1's doc path; Pillow-measured cap heights (this revision measured `Montserrat-Bold`/
  `Montserrat-ExtraBold` directly: `cap_height ≈ size_px × 0.70`, e.g. size_px 130 → cap height 91px); wrap-line
  counts measured against this Short's real overlay text via `stitcher.overlays.wrap_lines` (see table below).

**Verified sizing** (every value below was checked against the documented cap-height range AND real wrap
behavior for this Short's actual overlay strings — not asserted):

| Style | Font | size_px | cap height | Doc range | In range? | Wrap check (real text) |
|---|---|---|---|---|---|---|
| `hook_card` | Montserrat-ExtraBold | 130 | 91px | 90-120px hook | yes | "2,300 years old." → **2 lines**, within `max_lines: 3` |
| `plate_stat` | Montserrat-Bold | 62 | 43px | (no separate doc range; scaled proportionally) | n/a | all stat texts → 1 line |
| `plate_stat_accent` | Montserrat-Bold | 84 | 59px | n/a | n/a | "[[+12 games]]" → 1 line |
| `plate_source` | Montserrat-Bold | 52 | 36px | n/a | n/a | "Göllich et al. 2022" → 1 line |
| `loop_line` | Montserrat-ExtraBold | 70 | 49px | (shares hook-card family; kept smaller — it's a closing line, not the primary hook) | n/a | "The one-sport kid was never the safe bet." → **3 lines, at the `max_lines: 3` ceiling — no headroom left for a longer loop line in a future script** |
| `captions` | Montserrat-Bold | 90 | 63px | 60-80px captions | **over** the documented range by design — see Step 1's caveat below | n/a — does not render in the delivered video at all (see caveat) |

**Important finding, stated once here so Step 1-3 don't have to repeat it:** `captions[]` in the render-spec
schema drives only the `.srt`/`.ass` sidecar files — `stitcher` never composites it into the delivered `.mp4`
(confirmed: `stitcher/preflight.py` states burn-in was rejected in favor of Pillow-compositing the `overlays[]`
array specifically; the QA report's `safe_zone` check counts exactly the 8 `overlays[]` entries). **Changing
the `captions` style changes nothing visible in the final video.** If "bigger text" was meant to include the
on-screen spoken-word captions viewers see throughout the Short (not just the 8 punctuation-moment cards), that
is a real, unbuilt `stitcher` feature (burned-in caption compositing) — a separate scoped project, not a style
value. Task 5 below still updates the `captions` style entry (for whenever that feature exists, and because the
`.srt`/`.ass` sidecars are real deliverables in their own right), but flags this gap explicitly rather than
letting the operator believe it fixed something it didn't.

- [ ] **Step 1: Replace the existing bullet under "## Caption style `[I]`"**:

Old:
```markdown
- Bold sans-serif, heavy weight (Montserrat ExtraBold, Poppins Bold, or CapCut default). White fill + thick black stroke (2–4px) or a semi-opaque box behind, so it reads on any background.
```

New:
```markdown
- Bold sans-serif, heavy weight (Montserrat ExtraBold, Poppins Bold, or CapCut default). White fill + thick black stroke (2–4px) or a semi-opaque box behind, so it reads on any background.
  **This channel's concrete default, set 2026-08-20 `[P]`:** `Montserrat-Bold.ttf` for the four stat/source
  plates, `Montserrat-ExtraBold.ttf` for the hook card, re-hook card, and loop line — both confirmed installed
  system-wide at `C:/Windows/Fonts/`. Replaces the prior `arialbd.ttf` default, which was never actually
  documented here — it was just what every render-spec happened to copy forward
  (`docs/superpowers/plans/2026-08-20-dual-pipeline-vo-music-test-RESULTS.md`).
  **The `captions` style entry (below) does not currently affect the delivered video** — `stitcher` only
  burns in the `overlays[]` cards; `captions[]` drives `.srt`/`.ass` sidecars only. Operator decision,
  2026-08-20: the sidecar files are the actual deliverable wanted here (not a burned-in captions feature) — no
  new `stitcher` feature is in scope.
  **Numbers display as numerals in captions and overlays, never as the spelled-out words the VO script uses
  for TTS pronunciation `[P]`:** "2,300 years old.", not "two thousand three hundred years old." — the two
  text tracks (spoken vs. displayed) are expected to diverge; see `scripting-for-tts.md`'s matching note for
  the TTS-side half of this rule. Building `captions[]` text by copy-pasting the respelled VO payload is the
  wrong source — pull from the original numeral-form script, or hand-write the caption text directly with
  numerals.
```

- [ ] **Step 2: Replace the size line under "## Readability rules `[I]`"**:

Old:
```markdown
- Captions ~60–80px cap height; hook cards larger (90–120px).
```

New:
```markdown
- Captions ~60–80px cap height; hook cards larger (90–120px). **This channel's concrete default, set
  2026-08-20 `[P]`, verified against real cap-height measurements and real wrap behavior for this Short's
  overlay text** (not just chosen and asserted): hook/re-hook cards **130px** (91px cap height, top of the
  documented hook range; wraps to 2 lines for this Short's actual hook text, which is within `max_lines: 3`
  and was checked, not assumed), loop line **70px** (wraps to 3 lines — at the `max_lines: 3` ceiling, flag
  for anyone extending the loop line's copy in future scripts), stat plates **62px** (accent stat **84px**),
  source-citation plate **52px**. **The corpus's own genuine size tension, named at :20-21 above (small/
  restrained vs. these larger values) still applies — this `[P]` overrides it for this channel on the
  operator's explicit ask, the same way `single-take-architecture.md`'s `[P]` overrides `(Nick Nimmin,
  IF-PD6XMjYY)`'s per-beat-generation guidance** — say so if a future brief questions the size.
  `captions` style itself: 78-90px is a reasonable sidecar default, but changing it has **no visible effect on
  the delivered video today** — see the caveat above before treating this as having satisfied a "bigger
  captions" ask.
```

- [ ] **Step 3: Update the fill-in style spec template** at the bottom of the file:

Old:
```markdown
Font:            ______________________ (bold sans)
Cap size:        captions ___px | hook cards ___px
```

New:
```markdown
Font:            Montserrat-Bold.ttf (plates) / Montserrat-ExtraBold.ttf (hook/re-hook/loop)
Cap size:        hook/re-hook cards 130px | loop line 70px | stat plates 62px (accent 84px) | source 52px
                 (captions sidecar 78-90px — no visible effect on the delivered .mp4, see note above)
```

- [ ] **Step 4: Commit**

---

### Task 6: Validation render — apply every new default together, with predictions stated in advance

**Files:**
- Modify: `stitcher/renders/stop-over-specialization-in-youth-sports-multiseg-test/render-spec.json` (the test
  workspace, not the protected original Short)
- No new asset generation: `VO{1..7}_prepped.wav` and `Bed_prepped.wav` are already on disk from this session.

**Interfaces:**
- Consumes: the values from Task 4 (`gain_db`/`duck_db`) and Task 5 (six style values above).
- Produces: `stop-over-specialization-in-youth-sports-multiseg-test_v03_1080x1920.mp4`.

**Predicted outcome, stated before running** (so a surprise is caught, not rationalized after the fact — this
number was computed from real measurements of the already-generated `Bed_prepped.wav`, not guessed):
`Bed_prepped.wav` measures `input_i -20.81 / input_tp -13.86`. Raising `gain_db` from -22 to -14 (+8dB) is
predicted to move the pre-mix conform gain from ≈-27.4dB to ≈-19.4dB, landing the bed's contribution around
-33 dBTP — still ~19dB of margin below the mix's own measured peak (~-13.8 dBTP). **Prediction: this render
should still pass the loudnorm-linearity gate.** If it doesn't, that's a real, reportable finding (the margin
estimate was wrong), not something to silently work around with a heavier limiter pass.

- [ ] **Step 1: Confirm font availability** (not "copy" — both fonts are already installed)

Run: `powershell -Command "Test-Path 'C:\Windows\Fonts\Montserrat-Bold.ttf'; Test-Path 'C:\Windows\Fonts\Montserrat-ExtraBold.ttf'"`
Expected: both `True`.

- [ ] **Step 2: Edit `render-spec.json`'s `styles` block** — six edits, `font_file` and `size_px` only, every
  other field (`body`, `accent`, `max_width_px`, `max_lines`, `stroke_px`, `stroke_color`, `line_spacing`)
  unchanged:

```json
"hook_card":        { "font_file": "C:/Windows/Fonts/Montserrat-ExtraBold.ttf", "size_px": 130, ... },
"plate_stat":        { "font_file": "C:/Windows/Fonts/Montserrat-Bold.ttf",      "size_px": 62,  ... },
"plate_stat_accent": { "font_file": "C:/Windows/Fonts/Montserrat-Bold.ttf",      "size_px": 84,  ... },
"plate_source":      { "font_file": "C:/Windows/Fonts/Montserrat-Bold.ttf",      "size_px": 52,  ... },
"loop_line":         { "font_file": "C:/Windows/Fonts/Montserrat-ExtraBold.ttf", "size_px": 70,  ... },
"captions":          { "font_file": "C:/Windows/Fonts/Montserrat-Bold.ttf",      "size_px": 90,  ... }
```

(These are the exact same six values as Task 5's table — cross-checked; if you find a mismatch, Task 5's table
is the source of truth, fix Task 6 to match it, not the other way around.)

- [ ] **Step 3: Edit `render-spec.json`'s `audio.bed` block**:

```json
"bed": {
  "file": "Bed_prepped.wav",
  "gain_db": -14.0,
  "duck_db": -21.0,
  "duck_attack_ms": 120,
  "duck_release_ms": 400,
  "windows": [ { "in": 0.0, "out": 3.0, "mode": "out" } ],
  "fades": [ { "at": 3.0, "kind": "in", "ms": 300 } ]
}
```

- [ ] **Step 4: Fix `render-spec.json`'s `captions[]` array text back to numerals.** The current v02 spec's
  captions were built from the respelled (words-for-numbers) VO payload text — correct for TTS, wrong for the
  sidecar files per Task 2/Task 5's new rule. Four of the seven caption entries need their text restored to
  numeral form (the other three have no numbers and are already correct):

```json
{ "in": 0.0, "out": 6.287029, "text": "The oldest warning about pushing your kid into one sport? 2,300 years old." },
{ "in": 20.340045, "out": 28.066712, "text": "Here's the strange part. Jump forward 2,300 years — and the modern data agrees." },
{ "in": 28.066712, "out": 43.681043, "text": "Chundi and colleagues followed 2,556 NFL players in a 2026 study. The ones who played multiple sports had longer careers, and fewer injuries. Twelve more games. Nearly an extra season." },
{ "in": 56.3839, "out": 61.58517, "text": "That 2,300-year-old warning? The one-sport kid was never the safe bet." }
```

(Only the `text` field changes on these four entries — `in`/`out` timing is unaffected, since it was derived
from the real measured VO audio, not from the text content.) Confirm the eight `overlays[]` entries are
untouched — they were already authored with numerals directly (`"2,300 years old."`, `"2,556 NFL players"`,
etc.), never copy-pasted from the VO script, so they need no fix.

- [ ] **Step 5: Offline wrap-line check before rendering** (catches a layout problem without spending render
  time):

```python
import sys; sys.path.insert(0, ".")
import json
from PIL import ImageFont
from stitcher.overlays import parse_accent, wrap_lines

spec = json.load(open(r"C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-multiseg-test\render-spec.json", encoding="utf-8"))
for o in spec["overlays"]:
    style = spec["styles"][o["style"]]
    font = ImageFont.truetype(style["font_file"], style["size_px"])
    n = len(wrap_lines(parse_accent(o["text"]), font, style["max_width_px"]))
    status = "OK" if n <= style["max_lines"] else "OVERFLOW"
    print(f"{o['id']:14s} {n} line(s) / max {style['max_lines']}  {status}")
```

Expected: every row `OK`. An `OVERFLOW` row is a real preflight-failure-in-waiting — fix the size or the copy
before running the render, don't let `stitcher`'s own preflight catch it after the fact.

- [ ] **Step 6: Run the render**

Run: `cd C:\Projects\ContentStudio\stitcher && python -m stitcher render stop-over-specialization-in-youth-sports-multiseg-test --root "C:\Projects\ContentStudio\stitcher\renders" --mode final --force`
Expected: exit code 0, matching this task's stated prediction above. If it exits 2 on the loudnorm gate, report
the actual `loudnorm_pass1.json` numbers next to the predicted ones — the discrepancy itself is the finding.

- [ ] **Step 7: Check the QA report**

Read: `stitcher/renders/stop-over-specialization-in-youth-sports-multiseg-test/out/stop-over-specialization-in-youth-sports-multiseg-test_v03_qa.md`
Expected: `PASS` on every row. Specifically check `duck_depth`'s window count against v02's report (which read
"6 window(s) below the measurement floor") — raising `gain_db` lifts the floor `base` level (`verify.py`'s
`base + expected <= -60` skip condition), so some of those 6 windows will likely become measurable for the
first time. **A newly-measurable window reading outside ±1.5dB of the expected -7.0dB swing is a real finding
to report, not a regression caused by this task** — say so explicitly if it happens, don't just report pass/
fail.

- [ ] **Step 8: Report to the user** — send the v03 file; state the new measured LUFS/dBTP/duck numbers next to
  v02's; confirm the sidecar `.srt`/`.ass` now show numerals where the audio speaks words; ask whether the bed
  now reads audible and the larger overlay text reads well (this task can only verify "did every automated gate
  pass," not "does it sound/look right").

- [ ] **Step 9: Commit** the `render-spec.json` change (check `git status`/`git log` for whether
  `stitcher/renders/**` output artifacts are tracked in this repo before adding the `.mp4`/`.png`/QA files —
  don't assume either way).

---

## Self-Review (rev. 2)

**Spec coverage:** number respelling (Task 2), the corrected duck-depth fix (Task 4), Montserrat + verified
sizes (Task 5), and an accurately-scoped record of the `native-pipeline` finding (Task 3) are all covered.
Task 6 proves they compose without conflict, with predictions instead of blind "run and hope."

**What changed from rev. 1, for the record:** Task 3 no longer supersedes `single-take-architecture.md` (it
was never actually invalidated). Task 4 keeps the same target values but the rationale no longer casts
unsourced doubt on the `[C]` corpus finding — it identifies a parameter-mapping error instead. Task 5's sizes
are now derived from real Pillow cap-height measurements and real `wrap_lines` output against this Short's
actual overlay text, not asserted. The captions-sidecar-only gap is now stated as a named limitation in three
places (Evidence section, Task 5, Task 6 Step 7) rather than silently absorbed. Every `[P]` block was checked
for embedded craft-rule/procedure/causal-inference language and split into `[P]` (bare decision) + `[I]`
(extrapolation, marked as such) pairs. The evidence doc cites `loudnorm_pass2.json`, not `pass1`, with a
methodology note explaining why pass 1 is not diagnostic.

**Placeholder scan:** every code/markdown block above is literal insertable text — no "TBD"/"add appropriate
X" patterns.

**Type/value consistency:** Task 5's table and Task 6 Step 2 use the identical six style values (cross-checked
by construction — Task 6 explicitly says "source of truth is Task 5's table" rather than repeating and risking
drift, which is exactly the bug rev. 1 had). Task 4's `gain_db`/`duck_db` pair matches Task 6 Step 3 exactly.
The evidence-doc filename (`2026-08-20-dual-pipeline-vo-music-test-RESULTS.md`) is identical across every
citation in Tasks 2-6.
