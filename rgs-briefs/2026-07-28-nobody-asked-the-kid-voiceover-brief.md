---
date: 2026-07-28
kind: voiceover-brief
run: rgs-debut-20260728-055448
slug: nobody-asked-the-kid
stage: 03-voiceover
script: rgs-briefs/2026-07-28-nobody-asked-the-kid-script.md
concept_brief: rgs-briefs/2026-07-28-nobody-asked-the-kid-concept-brief.md
grounding: rgs-briefs/2026-07-28-nobody-asked-the-kid.md
short_a_voiceover_brief: rgs-briefs/2026-07-28-decline-the-next-level-voiceover-brief.md
archetype: A3
total_runtime_seconds: 50
voice_count: 2
status: complete
---

=== VOICEOVER BRIEF + ELEVENLABS CONFIG — nobody-asked-the-kid-01 (Short B) ===

Produced in two authored parts, per the task's division of labour. Part 1 (`voiceover-brief`)
makes the creative call — voice character **for each of the two casts**, tone per beat, pacing
resolution, and the loudness/ducking mix, **plus the 3.0s handoff between the two voices**. Part
2 (`elevenlabs-audio`) accepts that call without re-litigating it and emits the executable
configuration for **each voice separately** — model routing, settings, tagged script,
pronunciation dictionary, request payloads, curl, and credit estimate. **No ElevenLabs API call
was made to produce this document; no credits were spent.**

## Marker legend (an unmarked normative line below is a bug)

- **`[C]`** — the 420-video ContentStudio creator-education corpus, cited `(Channel, video_id)`,
  as `docs/elevenlabs-voiceover-guide.md` and `docs/headless-youtube-audit.md` §5 give it.
- **`[I]`** — general craft judgment, traceable to none of the below. A working decision.
- **`[T]`** — web-verified tool/policy fact. `voiceover-brief`'s `[T]` facts are dated
  **2026-07-23** (`docs/elevenlabs-voiceover-guide.md`); `elevenlabs-audio`'s `[T]` facts are
  dated **2026-07-26** (`docs/elevenlabs-production-runbook.md`). Both surfaces move fast —
  re-verify before relying on either set.
- **`[T-unverified]`** — asserted by the supplied enterprise runbook that seeded
  `elevenlabs-audio` (wrong in eight places — see that doc's §10) but **not** confirmed against
  live ElevenLabs docs. Starting-point numbers, never facts.
- **`[B]`** — RaisingGoodSports Brand Definition (`output/raisinggoodsports-brand-definition.md`).

---

# PART 1 — `voiceover-brief` (the creative call)

## Two voices, one hard boundary — the defining constraint

The script (`nobody-asked-the-kid-script.md`, "Delivery notes") states this as structural, not
optional: **the composite child speaks 0–3s and nowhere else; the adult narrator enters at 3s
and never speaks before it.** No corpus finding covers writing a child's voice — the corpus is
creator-education, not youth-voice-acting, and the script itself says so `[I]`. Every judgment
below about the child is therefore `[B]` (brand) or `[I]` (craft), never `[C]`. This brief treats
the two as fully separate casts: separate persona, separate settings table, separate script
section, separate voice profile — the corpus's usual single-voice-consistency rule
(`voice-selection.md`, "pick ONE voice and keep it consistent") applies **within each cast across
future videos**, not across the two casts inside one Short.

## Voice pick — narrator (adult, 3–50s)

**Same voice as Short A, unchanged.** The task brief's instruction is explicit: use the same
voice unless there is a stated reason not to, and change settings rather than the voice if the A3
vantage argues for something different `[I]` (task-17-brief.md). There is no such reason here —
A3's risk (a parent hearing accusation) is mitigated at the level of *which lines say what* and
*how they're delivered*, not at the level of *whose voice says them*. Carrying the same voice
forward is also itself part of the mitigation: a familiar, already-established calm ally register
is less likely to land any given line as a rebuke than a new, unplaced voice would.

Short A's narrator persona and its rationale are carried forward verbatim, not re-derived:
**calm, warm, grounded — an ally on the same side of the table as the parent. Not urgent, not
alarmed, not authoritative-expert** `[B]` (`output/raisinggoodsports-brand-definition.md`
§Voice). The same "do NOT use a default/popular library voice" warning applies unchanged — the
corpus's strongest-supported signal on this topic — because the channel identity question a
default voice risks (`One Person Business, 84bavOadYCI`; `Make Money Matt, TvJhpOxFRsE`) doesn't
reset per video; it's a channel-wide asset, and this is only the channel's second upload.

**Constraint 3 for this Short specifically — the narrator is a commentator, never a research
authority.** This sharpens Short A's existing "not a lecture" rule rather than replacing it: the
Payoff beat carries a named study, a sample size, and a two-tier figure, and the on-screen
citation plates do the "official" work while the VO hands the fact over conversationally `[I]`,
exactly as Short A's proof beat did. The population-narrowing rule (youth **soccer** players, not
"kids in sport") is a text-content constraint the script has already resolved — this brief does
not reopen it, only notes that the VO's per-beat delivery direction (commentator, not authority)
is what keeps the *reading* of that line from overclaiming, in addition to the words themselves.

**Voice Profile Card: carried forward unfilled, exactly as Short A left it.** Stage A (audition)
was not run for Short A and is not run here — auditioning requires generated audio, and this is a
configuration-only run (Step 3: no API call). The same three candidate personas apply, since the
same voice is being reused:

```
=== VOICE PROFILE CARD — NARRATOR (shared with Short A, placeholder — Stage A not run) ===
Name:            TBD — audition against Short A's three candidates (see below)
voice_id:        REPLACE_WITH_AUDITIONED_VOICE_ID (same id as Short A once locked)
Source:          library (lesser-used preset, not a top-default voice) [C]
Reference audio: n/a (not a clone)
Persona:         calm, warm, grounded, mid-register, unhurried — ally, not authority [B]

Locked settings: pending audition — see per-beat table below for target values
Known-good tags: pending — confirm [pause]/none land cleanly before committing to a master
Known-bad tags:  pending
Dictionaries:    none needed for this Short's spoken text (see Pronunciation below)
Caveats:         library voice, not a clone — disclosure applies regardless (see below)
Verified on:     not yet — audition is an open pre-production action shared with Short A
```

Candidates (unchanged from Short A, `voiceover-brief/references/voice-profiles.md`): (1)
mid-register, unhurried, warm — primary target; (2) slightly lower register, plainspoken, minimal
vocal fry — fallback if candidate 1 shows tag/pause artifacts; (3) explicitly "conversational"
rather than "narrator"/"announcer" marketing, to avoid a news-anchor over-enunciation risk. **The
audition, once run, locks the voice for both Shorts simultaneously** — it is one channel decision,
not two.

## Voice pick — composite child (0–3s)

**This is the pair's single highest policy-exposure casting decision, and it is bound by one
absolute rule stated three times in the upstream artifacts: no real child's voice, ever, in any
form** — not filmed, not sampled, not cloned, not sourced, not interviewed
(`nobody-asked-the-kid-script.md`, "Constraints that survive to publish" #1; grounding brief;
concept brief) `[B]`.

**Ruling out every path that could touch a real minor's voice, explicitly:**

- **Instant Voice Cloning (IVC) or Professional Voice Cloning (PVC) from any recording of an
  actual child — ruled out categorically.** Both mechanisms require reference audio of a real
  person `[T]` (`elevenlabs-audio/references/voice-profiles.md`); there is no "clone the
  character, not the person" mode. This applies even to a *consented* recording (e.g., a
  production's own child actor) — the script's rule is "not a real child," full stop, not "not a
  non-consenting real child." This brief does not use IVC/PVC for the child voice under any
  circumstance.
- **A library voice whose provenance is ambiguous — ruled out.** ElevenLabs' library carries
  10,000+ voices `[T]` (`voiceover-brief/references/voice-selection.md`), and some catalog
  entries are professionally recorded by real people, potentially including minors with
  parental/guardian consent through ElevenLabs' voice-actor marketplace. This configuration-only
  exercise cannot verify the provenance metadata of a specific catalog listing, so the safe
  default is **not** to pick a library voice on the strength of it merely "sounding right" —
  provenance must be affirmatively confirmed, not assumed, before any specific `voice_id` is
  locked (see Stage A note below).
- **What is used instead: ElevenLabs Voice Design — generate a voice from a text description,
  with no reference audio of any person, real or otherwise.** This is the corpus/guide's
  fourth cloning path, distinct from IVC/PVC/library `[T]` (`voiceover-brief/references/
  voice-selection.md`, "Cloning paths" table, dated 2026-07-23): *"Voice Design | Generate a
  voice from a text description | A distinctive voice no one else has."* Because Voice Design's
  output is synthesized from a description rather than derived from any specific human's
  recording, it is the one path that satisfies "composite, never a real child" **structurally**,
  not just by editorial promise — there is no underlying real-person audio for the composite
  status to be a euphemism for. The exact prompt-engineering mechanics of Voice Design (what
  descriptive fields it accepts, how many candidate takes it returns) are **not** covered in
  `docs/elevenlabs-production-runbook.md`, so treat those specifics as **`[T-unverified]`** —
  the feature's existence is `[T]`, its interface details are not confirmed here.
- **Fallback if Voice Design's output doesn't clear the performance bar** (stated non-interactive
  fallback, per the autonomy rule): a library voice explicitly and affirmatively marketed on its
  own profile page as performed by an **adult voice actor doing a child-like character voice** —
  a standard audiobook/animation-industry practice — confirmed by reading that voice's public
  description before selection, never inferred from how young the sample merely sounds. A voice
  whose profile does not affirmatively state adult-performer sourcing is not used, regardless of
  how it sounds. This fallback is recorded as an alternate, not executed in this run (no audio
  was generated, per Step 3).

**Performance requirement, stated in plain words before any voice is explored** `[T]`
(`elevenlabs-audio/references/voice-profiles.md` — "state the performance requirement first"):
this voice must land 8 words in 3 seconds, in a **matter-of-fact, content register — not
wistful, not wounded, not reproachful, not staged-cute.** It needs to sound like a real kid
recounting a genuinely good memory to whoever's listening, without performing "adorable" or
"sad." It does not need range beyond that single register — it is heard for three seconds, once.

**Constraint 4, the load-bearing one — the child must never sound like an accusation.** A3's
named danger is a parent hearing "you failed me" `[B]`. The mitigation is delivery, not just
words: **warm, unhurried, slightly amused at its own memory** (the "Everybody fell over" clause
should land as a small laugh-adjacent beat, not a punchline and not a complaint). No rising pitch
into a question, no trailing-off, no minor-key inflection. This is the same register the script's
own delivery notes call "a laughing memory" `[C]` (Nick Nimmin, kcSOFqJhR9I — cited there for the
Hook's emotion match, not for child-voice craft specifically, which the corpus doesn't cover).

## Voice character summary, both casts

| | Narrator (3–50s) | Composite child (0–3s) |
|---|---|---|
| Source | Same library voice as Short A (audition pending) | Voice Design (no reference audio); library-child-character fallback, provenance-confirmed only |
| Persona | Calm, warm, grounded ally — not authority `[B]` | Matter-of-fact, content, warm — never wistful or reproachful `[I]`/`[B]` |
| Register across the Short | Commentator handing over a citation, never lecturing `[I]` | Single register, single beat — no arc needed |
| Real-person source | None (library, not a clone) | **None — absolute. No real child's voice in any form.** |
| Disclosure | Synthetic voice, disclosed (see below) | Synthetic **and composite-child**, disclosed — highest exposure element |

## Settings — narrator (per beat)

Seven narrator beats, per the script's own second-ranges. Following Short A's precedent
(`decline-the-next-level-voiceover-brief.md`, "Settings"): section per beat rather than one
blended number, because this is a mixed-register script across a hard 50-second timing model
`[I]` (`voiceover-brief/references/settings-by-content-type.md`).

| Beat | Range | Content register | Stability feel | Style (expressiveness) | Speed feel | Speaker boost |
|---|---|---|---|---|---|---|
| Setup | 3–8s | Ally stating a plain fact about kids, not lecturing | Steady/Natural | Low | Slightly over neutral | ON |
| Build — Mason named | 8–14s | Commentator naming a source and a date, third-person historical | Steady/Natural | Low | Near neutral | ON |
| Build — re-hook | 14–17s | Contrast pivot ("But…"), curiosity, still calm | Steady/Natural | Low-moderate | Slightly over neutral | ON |
| Build — quote (climax) | 17–26s | Quiet gravity around the verbatim fragment; "It was never yours" lands weight, not drama | Steady/Natural | Moderate (highest in this Short) | Under neutral | ON |
| Payoff — research | 26–38s | Commentator handing over a named citation, plain numbers | Steady/Natural | Low-moderate | Near neutral | ON |
| Payoff — reframe | 38–45s | Exoneration beat, warmer — the villain is the system | Steady/Natural | Moderate | Slightly over neutral | ON |
| Loop/CTA | 45–50s | Warmest, most settled — mirrors the Hook's economy, resolved | Steady/Natural | Low | Under neutral | ON |

**No beat uses a "performative" or maximally expressive register** `[I]`, exactly as Short A's
rule — every beat maps to v3's **Natural** mode downstream, never Creative ("prone to
hallucinations" `[T]`, and too hot for the ally register) and never Robust (which would flatten
the delivery this beat table asks for). Exact numeric settings are Part 2's job.

## Settings — composite child (single beat)

| Beat | Range | Content register | Stability feel | Style (expressiveness) | Speed feel | Speaker boost |
|---|---|---|---|---|---|---|
| Hook (composite child) | 0–3s | Matter-of-fact, content, warm — a good memory, not a complaint | Steady/Natural | Low-moderate | Near neutral, unhurried | ON |

Held to **Natural**, same as the narrator — never Creative. A child voice pushed toward Creative
risks exactly the theatrical, "performed-cute" read that Constraint 4 rules out; Natural keeps
the read closer to the voice's own baseline delivery `[T]` (`elevenlabs-audio/references/
control-surface.md`, Mapping 2). Style is set moderate rather than low specifically because a
completely flat, low-style read risks sounding *bored* rather than content, which reads no better
against the accusation-risk than sounding wounded does — the target is animated-but-not-staged.

## The 3.0s handoff — specified exactly

The two-plane visual cut ("adult narrator enters here, and not before") and the two-voice
boundary are the same edit point, and the audio must not soften it into ambiguity or exaggerate
it into a jump-cut artifact `[I]` (no corpus or vendor source covers a two-voice Shorts handoff
specifically — this is this brief's own craft judgment, flagged as such):

1. **No overlap, no crossfade of the two voices' timbres.** The child's line ends cleanly before
   the narrator's first word begins. A timbre-crossfade would blur the very distinction the
   two-voice structure exists to create — the differentiator is that a viewer can *tell* these
   are two different voices, immediately.
2. **A short room-tone gap, not a hard zero-gap splice.** Leave roughly **100–150ms** of
   near-silence (ambient bed only, no voice) between the child's last word ("over.") and the
   narrator's first word ("Kids") `[I]`. This reads as a clean edit-point breath rather than a
   splice error, and it gives the visual cut (Hook → Setup, per the visual notes) a matching
   beat to land on.
3. **Matched perceived loudness across the cut, not matched raw gain.** Because a child-register
   voice and an adult-register voice can sit at different apparent loudness even at identical
   peak levels, match **short-term perceived loudness** between the two clips (bring them within
   roughly ±1 LU of each other) before either goes through final mix — not just level-match their
   waveform peaks `[I]`. The goal is that the cut reads as a change of *speaker*, not a change of
   *volume*.
4. **Both then ride the same LUFS/ducking chain as one continuous track** (see Production &
   loudness below) — there is no separate loudness target per voice; the −14 LUFS integrated
   target is for the finished mix as a whole, not per-speaker.

## Mason's quote card (17–26s) — verbatim status, stated per the constraint

Per Constraint 5: the **on-screen card is verbatim and complete** — the full sentence "so
ingrained is our contempt for children that we see nothing in this but Bobbie's foolish childish
way!" with attribution, exactly as the script's "The one quote card, verbatim" section fixes it.
**The narrator's spoken VO is not a paraphrase and not the full card** — it speaks a **contiguous
verbatim fragment** of the same sentence ("we see nothing in this but Bobbie's foolish childish
way"), framed by narrator commentary that is not Mason's words at all ("Her words: … A hundred
and forty years old. It was never yours.") `[I]`, per the script's own "Beats" and "The one quote
card, verbatim" sections, which state this split explicitly rather than leaving it to this brief
to invent. So: **card = complete verbatim sentence with attribution; VO = shorter verbatim
fragment of the same sentence, plus narrator framing that the card does not carry.** Neither is a
paraphrase of Mason in the sense Short A's Dewey beat used (a summary in the narrator's own
words) — the words Mason is credited with saying, she is quoted as actually having said, in both
channels, just at different lengths. This is a real distinction from Short A's precedent and is
called out rather than assumed to match it.

## Script, reformatted for TTS

Reformatting moves applied, each traceable to `voiceover-brief/references/scripting-for-tts.md`:

- **Sectioned into 8 TTS generation units** — 1 child beat + 7 narrator beats, matching the
  script's own beat/sub-range boundaries exactly `[T]`. This also lets the child beat be
  generated, cast, and re-rolled entirely independently of the narrator's seven, which matters
  more here than in Short A: a bad narrator take never risks re-rolling into the child's voice
  and vice versa, because they are never in the same generation request.
- **No `[pause]` tags added in this pass**, unlike Short A. Short A's two `[pause]` insertions sat
  at hard beat boundaries inside a single continuous voice; here the hardest boundary in the
  whole piece (the 3.0s handoff) is a **voice change**, which is already an unambiguous audio
  discontinuity and doesn't need a delivery tag to mark it (see "The 3.0s handoff" above — that
  boundary is handled in the edit, not in-text). Punctuation alone (the full stops and em-dash
  already in the script) carries the remaining internal pacing, per the brand-driven minimal-
  tagging preference Short A already established `[I]`.
- **One phonetic flag considered and explicitly not actioned: "Visek."** The script's own
  Handoff section flags "Visek" as needing a phonetic respelling downstream. But the locked VO
  line for the Payoff-research beat, as written by `shorts-scripting`, is "A 2015 George
  Washington University study asked hundreds of young soccer players…" — **the name "Visek" does
  not appear in spoken text**; it appears only on the on-screen citation plate. This brief does
  not add the name into the VO to manufacture a use for the flag — TTS reformatting is not
  license to add script content, and the citation plate already carries the name in the muted-
  friendly on-screen channel the script requires. **Recorded rather than silently dropped:** if a
  later script edit adds "Visek" into spoken text, add a PLS `<alias>` entry then (see
  Pronunciation, Part 2) — until that happens, no dictionary entry exists for a word that is
  never spoken. `[I]`
- **Sound-like-a-person check: pass, both casts.** The narrator's seven lines vary 6–30 words and
  read like something a person would say aloud; the child's line uses the deliberately dropped
  article ("Best part was…", not "The best part was…") the script calls out as intentional child
  cadence, not an error `[C]` (Nick Nimmin, IF-PD6XMjYY) — this is preserved verbatim in the TTS
  text below, not "corrected" toward textbook grammar.

```
CHILD — HOOK (0–3s), composite voice, spoken alone:
Best part was the mud. Everybody fell over.

--- 3.0s HANDOFF: voice change, ~100-150ms room-tone gap, no overlap, no crossfade ---

NARRATOR — SETUP (3–8s):
Kids do that. They come home and hand over the whole account, unprompted.

NARRATOR — BUILD, MASON NAMED (8–14s):
Charlotte Mason wrote that down in 1886. She called it narration. Every child does it.

NARRATOR — BUILD, RE-HOOK (14–17s):
But she also named what happens to it.

NARRATOR — BUILD, QUOTE / CLIMAX (17–26s):
Her words: "we see nothing in this but Bobbie's foolish childish way." A hundred and forty
years old. It was never yours.

NARRATOR — PAYOFF, RESEARCH (26–38s):
A 2015 George Washington University study asked hundreds of young soccer players what makes
sport fun. Eighty-one things. Eleven factors. Trying hard came first. Winning isn't one of
the eleven.

NARRATOR — PAYOFF, REFRAME (38–45s):
Nothing in the system has a field for that. You were handed a standings sheet. Not a report
card.

NARRATOR — LOOP/CTA (45–50s):
Ask what the best part was. Then believe the answer. It's free.
```

## Pacing resolution — the child beat's own edge case

The Hook's 8 words in a 3-second window implies ~160 wpm — inside the script's stated 150–170
wpm band, so no departure to flag on timing grounds alone. But the **register** constraint
narrows the usable speed range more than the timing math does: pushing speed up to hit the top
of a "punchy Shorts hook" feel (as Short A explicitly rejected for its own Hook, on the same
brand grounds) would read as rushed-and-excited, which risks tipping the "amused at its own
memory" register into performed enthusiasm — closer to a commercial-kid read than a real one
`[I]`. Resolved by keeping the child beat's speed **near neutral, not accelerated**, and treating
"Everybody fell over." as its own small unhurried beat rather than a rushed tail — the 3-second
window has enough slack at this word count to allow that without overrunning into the handoff
gap.

## Production & loudness

Carried forward from Short A, restated because it governs this Short's mix too, plus the
two-voice addition:

- **Normalize the finished voice track to −14 LUFS integrated** `[T]` (YouTube's loudness target;
  `voiceover-brief/references/production-and-loudness.md`). This applies to the finished mix as a
  whole, after both voices are cut together — not per voice (see "The 3.0s handoff," point 4).
- **Relative levels between the two voices:** matched short-term perceived loudness across the
  handoff (±1 LU, see above) so the cut reads as a speaker change, not a volume jump; neither
  voice is mixed hotter than the other as a stylistic choice — there is no dominance relationship
  between the child and the narrator in this Short, unlike a dialogue scene with a lead and a
  supporting voice `[I]`.
- **Duck the music bed.** Same documented range as Short A: docs/notes target **−12 to −18 dB**
  under the voice `[T]`, corpus creators run noticeably lower at **−21 to −22 dB** and name loud
  music as the most common beginner cause of low average view duration `[C]` (Romayroh,
  Wox4Jt_2t6w; Roberto Blake, iaTavrWIGDM) — **lead with −21 to −22 dB**, both given rather than
  silently picking one. During the child's 0–3s beat specifically, err toward the quieter end of
  that range or hold music out entirely until the handoff — the child's line is the Short's
  differentiator and must not compete with a bed for a first-time viewer's attention.
- **Match music to tone, not just fill silence** `[C]` (Kallaway, i7upRL4H1FM) — a bed that treats
  the child's warm memory and the quote-card's quiet gravity identically will flatten the arc
  this Short is built around.
- **Re-roll budget for the highest-leverage lines:** the child Hook and the Build-quote climax
  specifically, 2–3 takes each before locking `[C]` (Nick Nimmin, IF-PD6XMjYY) — the child beat
  because Constraint 4's register is the hardest single target in either Short, the quote-card
  beat because it carries the pair's highest per-word citation weight.
- **When in doubt, music too quiet beats music too loud** `[I]` — no corpus report of a video
  failing for underpowered music, only for overpowering it.

## AI/synthetic-media disclosure — carried forward verbatim for Tasks 19 and 20

Per the script's binding, brand-mandated policy `[B]`, longer than Short A's by design because
this Short adds a synthesized minor-register voice — the pair's single highest policy-exposure
element (`nobody-asked-the-kid-script.md`, "Delivery notes"):

**On-screen line (safe zone, during the Payoff beat):**
> AI-generated visuals · synthetic voices · child's voice is a composite, not a real child

Rendering spec: small-set, `#F7F3E8`, **never amber** (amber is reserved for the single accent
word elsewhere in the Short) `[B]`.

**Same line required in two more places** `[B]`:
- The video description.
- Every cross-post caption (per `social-repurpose`'s eventual output).

**Plus the platform-level disclosure**, separate from the on-screen/description line: YouTube's
altered/synthetic-content disclosure box, set at upload time `[T]` (YouTube inauthentic-content
policy, verified 2026-07-23 via https://support.google.com/youtube/answer/1311392 — **re-verify
before publishing**). This applies regardless of which specific voice path is used for the child
(Voice Design or the provenance-confirmed library fallback) — both are synthetic, both trigger
disclosure, and the "composite, not a real child" clause is an *addition* to the standard
synthetic-voice disclosure, not a substitute for it. **A synthesized minor's voice is exactly the
kind of altered content a platform disclosure control exists for** — this is not a borderline
call.

`shorts-assembly` and `social-repurpose` own placement timing and copy integration; this brief
does not own whether the disclosure ships — it already isn't optional.

## Downstream

This brief (Part 1's creative call plus Part 2's executable config below), alongside
`visual-prompts`'s prompt sheet for the same script, is the input to `shorts-assembly`.
`shorts-assembly` inherits the −14 LUFS target, the −21 to −22 dB ducking depth, the two-voice
relative-loudness rule, and the exact 3.0s handoff spec from this document without re-deriving
them.

---

# PART 2 — `elevenlabs-audio` (the executable configuration)

Accepting Part 1's creative call as given: two voice characters (narrator: same as Short A;
composite child: Voice Design, no real-person source), per-beat tone for each, the 3.0s handoff
spec, and the −14 LUFS / ducking targets (not restated below — `voiceover-brief` owns them).
This part converts the call into two working ElevenLabs setups. **No API call was made; no
credits were spent.** Fresh-agent Validation Gates 1–3 were run as a **self-checked deterministic
checklist**, exactly as for Short A — no render or spend is at stake for a configuration-only
artifact, and the autonomy rule directs the non-interactive fallback over stopping to ask.

## Control surface (both voices share these except where noted)

| Input | Value | Basis |
|---|---|---|
| `phase` | `draft` → `master` (two-phase; see COST) | `[I]` hard default |
| `use_case` | `shorts-vo`, **and** `character-dialogue` for the routing question (see Model routing below) | Two voices in one Short raises the routing check `elevenlabs-audio` requires |
| `expressiveness` | Narrator: `3`, modulated 2–4 per beat. Child: `3`, single beat | Assumed default `3`, adjusted per Part 1's tables |
| `voice` | Narrator: `explore` → library (locked, shared with Short A). Child: `explore` → Voice Design | Part 1's creative call |
| `language` | `en` | Assumed — script is English |
| `length` | Child ~43 chars; Narrator ~691 chars tagged; ~734 chars total | Counted from the reformatted script above |
| `privacy` | `standard` | Assumed — no zero-retention requirement stated |
| `determinism` | `on` for master, `off` for draft | Default mapping `[T]` |

## Model routing — the two-voice question, resolved explicitly

**This Short is not routed through the Text-to-Dialogue endpoint.** That endpoint exists for
turn-taking dialogue between speakers within one exchange (`/v1/text-to-dialogue/convert`,
`eleven_v3` exclusively, JSON array of `{text, voice_id}` turns, ≤2,000 chars total) `[T]`
(`elevenlabs-audio/references/model-routing.md`). This Short's two voices don't take turns — the
child speaks once, finishes, and the narrator begins; there is no interleaving, no overlap, no
back-and-forth. Routing this through Text-to-Dialogue would be using a conversational-turn
mechanism for what is structurally **two independent single-speaker generations edited together
at a hard cut**, which is both unnecessary (no turn-taking to coordinate) and a worse fit for the
3.0s handoff spec above, which calls for edit-level control (a room-tone gap, independent
loudness matching) that a single combined dialogue render would make harder to adjust
independently. **Each voice is generated as its own standard Text-to-Speech job, on its own
`voice_id`, then cut together in the edit.** Flagging this as a routing decision rather than a
default, since the presence of two voices is exactly the signal `model-routing.md` says to check
before assuming a standard payload is correct — checked here, and standard TTS (times two) is
the correct call, not Text-to-Dialogue `[T]`.

**Feature check, run for both voices before any tag was written** (`model-routing.md` quick
check):
1. Tags? None added in this pass (see "Script, reformatted for TTS" above) — punctuation only.
   No forced v3 requirement from this row alone.
2. Inline IPA? Not used.
3. `<phoneme>`? Not used — no dictionary entries needed this run (see Pronunciation).
4. Multiple speakers *within one generation request*? **No** — resolved above; each voice is its
   own job.
5. Non-English? No — `en`.
6. Real-time? No — pre-rendered VO, both voices.
7. Longer than the model's cap? No — child beat ~43 chars, narrator ~691 chars tagged across 7
   requests, both far under any model's cap `[T]`.

**Model chosen anyway: `eleven_v3` for both voices' masters, `eleven_flash_v2_5` for both
drafts.** Not forced by a tag requirement this time (no tags in this pass), but by the same
`shorts-vo` routing-table default Short A used `[T]` (`elevenlabs-audio/references/
control-surface.md`, Mapping 1) — v3 remains the flagship for short, performance-heavy Shorts VO,
and staying on the same model family as Short A keeps both Shorts' masters directly comparable
if a later edit reintroduces a tag (e.g., an experimental `[laughs]` on the child beat, see QC
checklist below). `model_id` is set explicitly on every payload; the API default
(`eleven_multilingual_v2`) would be a silent downgrade even without a tag at stake `[T]`.

**No routing contradictions found, either voice.**

## Voice settings — narrator

Converting Part 1's per-beat feel into wire values, identical mechanics to Short A. On
`eleven_v3`, stability is one of three discrete modes `[T]`; every narrator beat uses **Natural**,
per Part 1's rule against Creative (too hot for the ally register) and Robust (would flatten the
delivery Part 1 asks for).

`similarity_boost`: held at **0.78**, unchanged from Short A — inside both cited bands (0.75–0.90
`[T]`, dated 2026-07-23, vs. 0.65–0.75 `[T-unverified]`), and this is the *same* voice as Short A,
so the same locked value applies rather than re-deriving it `[I]`.

Speed values below implement the per-beat feel above at the same **~155 wpm-at-`speed:1.0`**
baseline Short A used — **an assumption, not a documented ElevenLabs figure; no source states a
words-per-minute value for `speed: 1.0`**, carried forward as this brief's own `[I]`
extrapolation, unchanged from Short A. Each value is inside ElevenLabs' documented valid range of
0.7–1.2 `[T]`.

| Beat | Stability mode | `style` | `similarity_boost` | `speed` | `use_speaker_boost` |
|---|---|---|---|---|---|
| Setup | Natural | 0.15 | 0.78 | 1.01 | true |
| Build — Mason named | Natural | 0.15 | 0.78 | 0.97 | true |
| Build — re-hook | Natural | 0.25 | 0.78 | 1.03 | true |
| Build — quote (climax) | Natural | 0.30 | 0.78 | 0.95 | true |
| Payoff — research | Natural | 0.20 | 0.78 | 0.97 | true |
| Payoff — reframe | Natural | 0.25 | 0.78 | 1.05 | true |
| Loop/CTA | Natural | 0.20 | 0.78 | 0.93 | true |

This Short's beat-to-beat implied wpm (144–163) is narrower than Short A's (103–171), so the
resulting `speed` values cluster closer to 1.0 than Short A's did (which needed the 0.70 floor
for its Loop/CTA) — a direct, arithmetic consequence of the two scripts' different timing
profiles, not a separate creative choice `[I]`.

## Voice settings — composite child

```
Beat: Hook (0-3s), single generation
Stability mode: Natural
style:            0.25
similarity_boost: 0.75   [assumed default -- new Voice Design voice, no prior
                          locked value to match, and no cloned-reference-noise
                          risk since there is no reference audio at all] [T]/[I]
speed:            1.00   [near-neutral, per Part 1's "not accelerated" resolution]
use_speaker_boost: true
```

`similarity_boost` is documented as tracking the *voice*, not the performance `[T]`
(`elevenlabs-audio/references/control-surface.md`, Mapping 2) — for a Voice Design voice with no
reference recording to stay faithful to, the standard default (0.75) is used rather than Short
A's tuned-against-a-specific-clone value, since there's nothing here to tune against yet. Locked
once Stage A audition happens.

## Directorial script (tagged, chunked per beat — two casts, eight units)

Each beat is its own generation unit, chained within its own cast only — **the child's unit does
not chain to the narrator's first unit via `previous_request_ids`/`previous_text`**, because they
are different `voice_id`s and stitching context is meant to carry vocal continuity forward within
one voice, not across a cast change `[I]`. The narrator's seven units chain to each other exactly
as Short A's seven did.

```
0. CHILD-HOOK    voice: composite-child    "Best part was the mud. Everybody fell over."
                 (no previous_request_ids -- first and only generation for this voice)

--- 3.0s edit-level handoff; not represented in either payload ---

1. NARRATOR-SETUP        "Kids do that. They come home and hand over the whole account,
                          unprompted."
                          (no previous_request_ids -- first narrator generation; the child's
                          request_id is deliberately not chained here, per the note above)
2. NARRATOR-BUILD-MASON  "Charlotte Mason wrote that down in 1886. She called it narration.
                          Every child does it."
3. NARRATOR-BUILD-REHOOK "But she also named what happens to it."
4. NARRATOR-BUILD-QUOTE  "Her words: \"we see nothing in this but Bobbie's foolish childish
                          way.\" A hundred and forty years old. It was never yours."
5. NARRATOR-PAYOFF-RSCH  "A 2015 George Washington University study asked hundreds of young
                          soccer players what makes sport fun. Eighty-one things. Eleven
                          factors. Trying hard came first. Winning isn't one of the eleven."
6. NARRATOR-PAYOFF-RFRM  "Nothing in the system has a field for that. You were handed a
                          standings sheet. Not a report card."
7. NARRATOR-LOOP-CTA     "Ask what the best part was. Then believe the answer. It's free."
```

No tags are used on either cast this pass; punctuation carries all delivery, per Part 1's
minimal-tagging decision. **Pre-render checklist** (`directorial-prompting.md`), run for both
casts:

1. Punctuation alone reads sensibly without any tag — yes, both casts.
2. No tags used, so nothing to catalog-check this pass. If a `[laughs]` experiment is added to
   the child beat later (see QC checklist), it is catalog-confirmed `[T]` but must be explicitly
   flagged as an experiment on this specific voice per Voice Profile Card rules, since tag
   effectiveness is voice-specific and this voice has no known-good/known-bad tag history yet.
3. No closing-tag syntax used — confirmed.
4. Model is `eleven_v3` for both masters — confirmed.
5. Stability mode is Natural for every beat, both casts — confirmed, never Robust.
6. Tags compatible with the voice's known range — n/a this pass (no tags used).
7. Multiple speakers → resolved above as two independent standard-TTS jobs, not Text-to-Dialogue.
8. Numbers pre-checked — "1886," "2015," and the spoken figures ("Eighty-one," "Eleven") are
   ordinary number-words or year-reads; ElevenLabs' text normalizer handles calendar-adjacent
   numbers by default `[T]`, called out in the QC checklist rather than assumed silently correct.
9. Each chunk is far under either model's cap — confirmed (largest narrator beat, Payoff—
   research, is ~199 characters; the child beat is ~43).

## Pronunciation

**No dictionary is created for this run.** The one name the script's Handoff section flags
("Visek") does not appear in the spoken text of either cast, only on the on-screen citation
plate — see "Script, reformatted for TTS" above for why this brief does not manufacture a spoken
occurrence to justify a dictionary entry. **Stated explicitly rather than left as a silent gap:**
if a future script revision moves "Visek" (or "Fun Integration Theory," which is currently also
on-screen-only) into spoken VO, create a `<alias>`-only PLS dictionary at that point, following
Short A's exact pattern (`<alias>` chosen over `<phoneme>` because the draft phase runs on
`eleven_flash_v2_5`, which does not support `<phoneme>` at all `[T]`, and because a name used once
doesn't need phoneme-level control `[I]`) — case variants (lowercase/Title Case/UPPERCASE)
enumerated per the mandatory case-sensitivity rule `[T]`. Not created now because nothing in
either cast's locked VO text requires it.

## Request payloads — one per voice

Per the task's requirement that both voices' payloads be shown: the **child's single beat is
shown in full** (it is the only generation for that voice, so there is nothing to omit), and the
**narrator's Build-quote climax beat** is shown as the worked example for that cast, following
Short A's precedent of showing the tightest/highest-weight beat in full and noting the other six
follow the identical shape.

**Child — Hook (0–3s), full and only generation for this voice:**

```json
{
  "text": "Best part was the mud. Everybody fell over.",
  "model_id": "eleven_v3",
  "voice_settings": {
    "stability": "natural",
    "similarity_boost": 0.75,
    "style": 0.25,
    "speed": 1.00,
    "use_speaker_boost": true
  },
  "seed": 20260728,
  "apply_text_normalization": "auto"
}
```

Query parameters: `output_format=mp3_44100_192&enable_logging=true`

**curl (child):**

```bash
curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/REPLACE_WITH_CHILD_VOICE_ID?output_format=mp3_44100_192&enable_logging=true" -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" -d @child-hook.json --output child-hook.mp3
```

**Narrator — Build, quote / climax (17–26s), worked example; the other six narrator beats follow
the identical shape, substituting each beat's `text` and the Voice Settings table's row above:**

```json
{
  "text": "Her words: \"we see nothing in this but Bobbie's foolish childish way.\" A hundred and forty years old. It was never yours.",
  "model_id": "eleven_v3",
  "voice_settings": {
    "stability": "natural",
    "similarity_boost": 0.78,
    "style": 0.30,
    "speed": 0.95,
    "use_speaker_boost": true
  },
  "seed": 20260728,
  "previous_request_ids": ["REQUEST_ID_FROM_NARRATOR_BEAT_3_REHOOK"],
  "previous_text": "But she also named what happens to it.",
  "next_text": "A 2015 George Washington University study asked hundreds of young soccer players what makes sport fun.",
  "apply_text_normalization": "auto"
}
```

Query parameters: `output_format=mp3_44100_192&enable_logging=true`

**curl (narrator, this beat):**

```bash
curl -X POST "https://api.elevenlabs.io/v1/text-to-speech/REPLACE_WITH_AUDITIONED_VOICE_ID?output_format=mp3_44100_192&enable_logging=true" -H "xi-api-key: $ELEVENLABS_API_KEY" -H "Content-Type: application/json" -d @narrator-build-quote.json --output narrator-build-quote.mp3
```

**Note on the `stability` field's wire shape**, carried from Short A: v3 exposes stability as the
three discrete modes; both payloads write it as the string `"natural"`, but the exact wire
representation (mode string vs. an SDK-mapped value) should be confirmed against the live API
reference before either payload is actually sent `[T]`/`[I]`. Everything else is written as
documented. **Neither payload was sent** — no API key was used, no request was made, no credits
were spent.

## Cost

```
COST
  Child voice (1 beat, full script -- there is only one):
    Draft:  ~43 chars x Flash v2.5 rate ($0.05/1,000 chars, T) ~= $0.002
    Master: ~43 chars x master rate (~$0.10/1,000 chars -- T-unverified,
            inferred as 2x the Flash discount, not a directly quoted master
            figure) ~= $0.004
    Re-roll budget: 3 re-rolls (Constraint 4's register is the hardest single
            target in either Short) ~= $0.01-0.02 additional

  Narrator voice (7 beats, ~691 chars tagged, full script):
    Draft:  ~166 chars (Build-quote excerpt, the tightest/highest-weight beat)
            x Flash v2.5 rate ~= $0.008
    Master: ~691 chars x master rate (T-unverified, same basis as above)
            ~= $0.07
    Re-roll budget: 2 re-rolls for the Build-quote climax beat specifically
            ~= $0.01-0.02 additional

  Basis:  per input character, including spaces and punctuation, per voice [T]
  Note:   API calls are billed; the two free regenerations are website-only,
          not available via the API [T] -- if free re-rolls are wanted while
          tuning fixed text, do that tuning in the web UI and port settled
          values into these payloads
  Total estimate, both voices, draft + master + budgeted re-rolls:
          roughly $0.10-0.13
```

Comparable in order of magnitude to Short A's $0.10–0.12 estimate despite the second voice,
because the child's entire contribution is one 43-character generation — the second cast adds
routing complexity and a distinct policy burden, but almost no additional character cost `[I]`.
This is well below the corpus's ~$1–2/video figure `[C]` (Make Money Matt, TvJhpOxFRsE), which
appears to bundle iteration and multiple full-script takes rather than the per-beat, sectioned
generation this brief uses.

## QC checklist

| Symptom | Likely cause | Fix |
|---|---|---|
| Child voice sounds sad/wistful rather than content | `style` too low, or the wrong Voice Design candidate | Nudge `style` up within 0.20–0.30 before touching `stability`; if unresolved, re-audition against Constraint 4's stated register `[T]`/`[I]` |
| Child voice sounds performed/commercial-cute | `speed` pushed above neutral, or `style` too high | Pull `speed` back toward 1.00 and `style` toward 0.20; the register wants unhurried, not energetic `[I]` |
| The 3.0s cut sounds like a volume jump | Voices not loudness-matched pre-mix | Re-check the ±1 LU short-term match called out in Part 1 before touching EQ `[I]` |
| The 3.0s cut sounds like a splice error / mid-breath cut | Room-tone gap too short or missing | Confirm the 100–150ms gap is present and contains ambient bed, not hard silence `[I]` |
| "1886" / "2015" read oddly (e.g. digit-by-digit instead of as a year) | Normalizer trouble spot not explicitly confirmed for calendar years | Pre-convert to "eighteen eighty-six" / "twenty-fifteen" in the text if the auto read is wrong `[T]`/`[I]` |
| Flat, monotone delivery on the Build-quote beat | `style` too low for the climax read | Nudge `style` up within the 0.25–0.35 band before touching `stability` `[T]` |
| Draft sounds worse than expected on numbers, either voice | Flash v2.5 artifact, not a script defect | Re-check on the v3 master before rewriting anything `[T]` |
| Child voice can't sustain a `[laughs]` tag if added | Tag effectiveness is bounded by the voice's training data — untested for a fresh Voice Design voice `[T]` | Treat as an experimental tag on this specific voice (Voice Profile Card rule); confirm via a v3 probe before committing, and drop it rather than force it if it produces an artifact |

## Validation gates (self-checked deterministic pass, not a live fresh-agent dispatch)

- **Gate 1 — Script & tag:** PASS. No tags used on either cast (punctuation-only this pass), so no
  catalog/closing-tag/Robust-contradiction findings apply; correct model (v3) for both masters;
  all 8 chunks (1 child + 7 narrator) far under the 5,000-char cap; the two-voice question was
  explicitly checked against the Text-to-Dialogue routing rule and resolved as two independent
  standard-TTS jobs, not a dialogue-endpoint or inline-speaker-label error; numbers flagged in the
  QC checklist rather than assumed safe.
- **Gate 2 — Payload:** PASS. Every setting in its documented valid range (narrator `speed`
  0.93–1.05, inside 0.7–1.2; narrator `style` ≤0.30; child `speed` 1.00, child `style` 0.25;
  `similarity_boost` 0.78 narrator / 0.75 child, both inside or at documented defaults); `model_id`
  set explicitly on every request, both voices; `output_format` matches the master phase and names
  the Creator+ tier gate; `enable_logging: true` matches `privacy: standard`; `seed` present and
  fixed for both masters; the narrator's seams carry `previous_request_ids` and `previous_text`/
  `next_text`; the child's single request correctly carries neither (nothing to chain to); no
  pronunciation dictionary created, correctly, since nothing spoken requires one this run.
- **Gate 3 — Pre-master spend:** N/A for this run — no draft was rendered for either voice and no
  master will be sent from this document; it is a configuration artifact. Recorded as `n/a`, not
  claimed as `pass`.

## Next

1. Run the Stage A audition for the narrator (shared with Short A — one audition locks the voice
   for both Shorts) and fill in the narrator Voice Profile Card.
2. Run Voice Design generation for the composite child persona (Constraint 4's register stated
   above as the brief), confirm the provenance is generation-only with no reference audio, and
   fill in a child Voice Profile Card; if Voice Design underperforms, fall back to the
   provenance-confirmed adult-voice-actor library path named in Part 1 — never to IVC/PVC of any
   real child recording.
3. Render both drafts (child beat in full; narrator's Build-quote excerpt) and confirm direction,
   including the 3.0s handoff's loudness-match and room-tone gap, before any master spend, per the
   two-phase protocol.
4. Feeds `shorts-assembly` next, alongside `visual-prompts`'s prompt sheet for the same script —
   `shorts-assembly` inherits the −14 LUFS target, the −21 to −22 dB ducking depth, the two-voice
   relative-loudness rule, the exact 3.0s handoff spec, and the full disclosure line, all recorded
   in Part 1 above.
