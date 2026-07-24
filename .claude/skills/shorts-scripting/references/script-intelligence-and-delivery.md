# The 2026 script-intelligence layer, and delivery/format rules

Distilled from `docs/headless-youtube-audit.md` §4 ("2026 script-intelligence
layer" and "Delivery & format") and `docs/headless-shorts-production-playbook.md`
§2 ("Faceless-specific structure notes") and §3 (never let AI script
word-for-word). Apply this as a pass over the whole script, not just one beat —
it's the corpus's answer to "how do I know this script won't read as generic
AI slop or get suppressed as a duplicate."

## Net information gain — run this check before writing a word

- **Net information gain is the core 2026 ranking lever — strongly-supported.**
  YouTube's Gemini reads the full transcript on upload; if the script repeats
  what other videos already say, it won't be pushed `[C] (One Person Business,
  MP7JYOm25-g; Romayroh, mPHdSkvoN10; Dan the creator, 4GAKrgNN8zQ)`. Before
  writing the script, check what the top competing Shorts on this exact
  premise already say, and make sure the single premise adds something they
  don't cover.
- **Seed the script with the exact recognized terms for the topic's "semantic
  ID"** (proper nouns, named concepts) rather than vague paraphrases `[C]
  (Romayroh, mPHdSkvoN10)`.
- **Pack the script with citable specifics** — exact numbers, full names,
  dates, places — and answer the core question as early as the format allows
  `[C] (Romayroh, G9LfE3k-IEI; Romayroh, mPHdSkvoN10)`. This is a long-form AEO
  finding (aimed at descriptions/full transcripts get cited by AI answer
  engines); on a Short, the transferable piece is: prefer one concrete, citable
  detail over a vague generality in the Build/Payoff beats.
- If the concept brief's premise is a well-worn topic and you can't identify a
  genuine information-gain angle, say so explicitly rather than writing a
  script that just restates the obvious version — that's the anti-generic
  guarantee applied to net info gain specifically.

## Humanize the script — don't let it read as AI-written

- **Humanize AI scripts: perplexity, burstiness, complexity — strongly-
  supported.** Use surprising specifics (dates, events, opinions), varied
  sentence length instead of uniform AI-typical sentences, and vivid concrete
  vocabulary. Predictable scripts get flagged as reused/AI and lower trust
  score `[C] (Romayroh, ErCV5czVK1g)`.
- **Block AI "fingerprint" phrases** ("it's important to note," "some may
  argue") **and buzzwords** (delve, leverage, comprehensive, robust, holistic)
  `[C] (Romayroh, ErCV5czVK1g)` — treat these as a hard no-list when drafting
  or reviewing any beat.
- **Never let AI script word-for-word** — it produces an "AI vibe" and can
  hallucinate fake facts/dates to hit a word count `[C] (Nate Black,
  9CCmMypN8PM; Romayroh, _mKpc4-_on8; One Person Business, s2knfD7QuCM)`. In
  practice for this skill: draft, then run a deliberate humanize pass — don't
  ship the first-draft phrasing.
- **Fact-check any claim in the script with the strongest available model
  before treating the script as final** `[C] (One Person Business,
  s2knfD7QuCM)` — especially any specific number, date, or name pulled in
  during the net-information-gain pass above.
- **Write in four steps: topics → research → write → humanize** — the research
  step is essential because a script must be told specifics, not assumed to
  invent them accurately `[C] (Romayroh, RQs3so8RHGw)`.

## Delivery & format — write for what actually gets consumed

- **Optimize for the ~80–85% who watch muted** — the on-screen text and visuals
  must carry the context, not rely on the VO alone `[C] (Kallaway,
  i7upRL4H1FM)`. Every beat needs a visual note (see the output template)
  precisely because of this — a script that only works with sound on is
  incomplete.
- **Leave small imperfections/filler in the cut to feel human, not AI** `[C]
  (Nick Nimmin, IF-PD6XMjYY)` — don't over-polish the VO line into
  textbook-perfect grammar; a little natural cadence is a feature.
- **Talking-head Shorts are risky — they rely wholly on energy/story.** A
  faceless channel only sidesteps this if it substitutes a strong **visual
  demonstration layer** `[C] (Nate Black, UjeOJb6lk5M)`. This is a hard
  requirement on the Build beat's visual note: it must show the thing
  happening, not just illustrate the narrator talking.
- **Turn spoken stats and lists into on-screen motion graphics** so viewers
  *see* the number, not just hear it `[C] (vidIQ, i5bZ-Be9cAQ)` — flag any beat
  with a spoken statistic so the visual-prompts skill knows to render it as
  on-screen text/graphic, not just B-roll.
- **Positive emotions perform best; a belonging/familiarity feeling in the
  first moments drives repeat viewership** `[C] (Nate Black, acOx8xUNXyQ)`.
- **Build the outline around one of five audience modes — solve, journey,
  belong, expand, feel** `[C] (Nate Black, lRLwjsyAOi4)` — useful as a
  one-word check on what kind of premise this Short actually is, which should
  already be legible from the upstream concept brief's angle.

## What the corpus does NOT give us

The corpus's AEO guidance (chapters, 500-word descriptions, corrected
transcripts) is long-form-specific and belongs to packaging/description work
downstream of this skill, not the script itself — don't pull those rules into
a Short script's beats.
