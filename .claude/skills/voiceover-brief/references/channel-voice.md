# The channel voice — pinned

> **`[T]` facts in this file were web-verified 2026-07-23** against live ElevenLabs documentation
> and have not been re-checked since. Vendor facts go stale fast — re-verify before relying on a
> parameter range, a model id, or a credit rate `[T]`.

The narrator voice is **already chosen**. This file records which one, so that
`references/voice-selection.md`'s "pick ONE voice and keep it consistent" rule has an actual
subject and no brief ever ships a placeholder `voice_id` again.

Markers: `[C]` corpus-cited `(Channel, video_id)` · `[I]` industry practice · `[T]` web-verified
tool/policy fact · **`[P]` project/operator decision** — a call made by this project's owner and
recorded here. `[P]` is a *fact of record*, not evidence: it says what was decided, never why it
is correct. Never cite a `[P]` line as corpus or vendor support for anything.

## The rule `[P]`

**`eDwT8Vhp2yxJzAMmuuPA` is the narrator voice for every ContentStudio Short, across all
brands.** Do not audition, do not re-derive it from `voice-selection.md`'s doctrine, do not
substitute a "better fit" for a particular script. The voice is the channel's identity `[I]` —
a branding judgment, not a platform fact; neither ElevenLabs nor YouTube publishes it — and
consistency across uploads is the point.

**Supersedes `5kVvcrJnhhULT5LdbshJ`** (the previous IVC pin, retired 2026-08-18 in favor of a
higher-fidelity PVC trained on the same operator's voice — see "The card" below). Any prior
render referencing the old `voice_id` was produced under that earlier pin; do not backfill it.

Two things this rule does **not** do — see "Scope boundary" below before treating it as absolute.

## The card

```
=== VOICE PROFILE CARD — CHANNEL NARRATOR (pinned) ===
Name:            TBD — label the voice in the ElevenLabs dashboard and record it here
voice_id:        eDwT8Vhp2yxJzAMmuuPA
Source:          PVC — a Professional Voice Clone of the operator's own voice [P]
Reference audio: 30+ minutes [P] — meets the PVC minimum; quality notes still TBD (see Open action 2)
Persona:         TBD — describe what the voice actually delivers (age/texture/register/energy),
                 not what it was intended to deliver

Locked settings: PENDING AUDITION — no master render has been made against this voice yet.
  Model:            eleven_v3, single continuous generation per Short (not
                     per-beat chunking) — operator decision 2026-08-21,
                     REVISING the earlier same-day decision below (which had
                     itself just resolved Open action 3 to
                     eleven_multilingual_v2) after a live listening
                     comparison. Bracket audio tags ([excited], [whispers],
                     [sighs], [pause], etc.) carry delivery, applied only
                     where they genuinely fit — not every beat needs one.
                     No per-beat numeric speed/style variation: a single
                     constant stability/similarity_boost/style/speed
                     baseline across the whole take. [P]
  Stability:        pending
  similarity_boost: pending
  style:            pending
  speed:            pending
  use_speaker_boost:pending

Known-good tags:   PENDING — requires a v3 probe (see Open action 1, reopened below)
Known-bad tags:    PENDING — requires a v3 probe (see Open action 1, reopened below)
Dictionaries:      none
Caveats:           SUPERSEDED 2026-08-21 [P]: earlier the same day, Open
                   action 3 was resolved to "full PVC fidelity via
                   eleven_multilingual_v2, no audio tags." That resolution
                   was then tested against a v3+tags alternative in a live
                   side-by-side comparison, and the v3+tags result was
                   judged clearly better — more natural intonation, no
                   audible per-segment "AI-ish" discontinuity. The
                   multilingual_v2 decision's own reasoning (PVC fidelity
                   loss on v3) is real but was outweighed in practice.
                   Three eleven_v3 API behaviors this session found
                   undocumented or mis-documented, now load-bearing for
                   this pin:
                   1. eleven_v3's /text-to-speech (and /with-timestamps)
                      REJECTS voice_settings.stability as the string
                      "natural" — 422 "Input should be a valid number" —
                      despite this skill's own model-routing.md/
                      api-payload.md describing string mode names. Send a
                      float (Natural ≈ 0.5) instead. [T]
                   2. eleven_v3 REJECTS previous_text/next_text outright —
                      400 "Providing previous_text or next_text is not yet
                      supported with the 'eleven_v3' model" — so a
                      single-take generation has no request-level
                      stitching context to lose in the first place; this
                      is a non-issue for the single-continuous-take
                      approach specifically.
                   3. eleven_v3 has no <break> tag (already correctly
                      documented elsewhere in this skill) — bracket tags
                      and punctuation carry pacing instead.
Verified on:       2026-08-21 — voice_id and model routing recorded; audition not yet run
```

**Until the settings block is filled, briefs still derive settings per-script** from
`references/settings-by-content-type.md`. A pinned voice is not a pinned configuration — only
the `voice_id` is locked today. Say so in the brief rather than implying the settings came from
a verified card.

## Why this voice

Carry this rationale into briefs by citation; do not re-argue the casting call.

A **cloned own voice is the corpus's top-ranked fix** for the default-voice problem
(`references/voice-selection.md`, fix #1). The problem it solves: the handful of most-common
ElevenLabs preset voices already appear on hundreds of thousands of videos, and creators report
YouTube can detect the repeat and treat a new channel as another copy of the same voice —
risking limited reach or shadowban `(One Person Business, 84bavOadYCI)` `(Make Money Matt, TvJhpOxFRsE)` `[C]`.
A cloned own voice is 100% unique, so the risk does not arise.

One creator additionally reports that a cloned-*own* voice does not currently trigger YouTube's
altered-content/AI disclosure `(Romayroh, OrPYWlXMQws)` `[C]`. **State this as that creator's
report, not as platform policy** — it is a single-channel observation, it is undated relative to
current policy, and disclosure rules move. Do not let a brief upgrade it into a compliance claim.

So the pin **satisfies** the corpus rule rather than creating an exception to it. That is worth
saying explicitly in a brief, because the corpus's default-voice warning is loud enough that a
reader may otherwise expect the pin to be conceding something.

## Open actions

One reopened, one still open, one resolved-then-superseded.

1. **Run one short v3 probe and fill the tag rows.** Reopened 2026-08-21 — the
   2026-08-21 routing decision moved this voice back onto `eleven_v3`, so the
   probe this action originally called for is live again. Tag effectiveness is
   bounded by the voice's training data `[T]` — "don't expect a whispering
   voice to suddenly shout with a `[shout]` tag" `[T]`
   (`.claude/skills/elevenlabs-audio/references/voice-profiles.md`). If the
   reference is emotionally narrow, v3 tags **underperform silently**: they do
   not error, the audio just comes back flat. Probe before a first master, and
   record what landed and what did not.
2. **Record the reference audio's condition.** Reference-audio quality still matters for a PVC,
   even though the failure mode is less acute than IVC's — "clean, no reverb, no background
   noise" `[T]`. This connects to a settings symptom worth knowing in advance: noise in the
   reference is exactly what a high `similarity_boost` reproduces faithfully. If the render
   sounds noisy, fix the reference rather than tuning `similarity_boost` down around it `[I]`.
3. **Decide the PVC-on-v3 trade-off.** Resolved 2026-08-21 `[P]` to
   `eleven_multilingual_v2` (full PVC fidelity, no audio tags) — then
   SUPERSEDED the same day `[P]`: a live listening comparison favored
   `eleven_v3` + bracket tags enough to outweigh the fidelity trade. See the
   Caveats line on the card above for the full reasoning and the three
   live-API corrections this decision depends on.

## Scope boundary

**This pins the narrator, and only the narrator.** Two limits:

- **Non-narrator casting is decided per-Short and this pin does not override it.** `[P]` Where a Short
  casts a second voice, that casting runs the full `voice-selection.md` process on its own
  terms and is bound by whatever constraints its script carries. The worked case:
  `rgs-briefs/2026-07-28-nobody-asked-the-kid-voiceover-brief.md` casts a composite child under
  an absolute "no real child's voice, ever — not filmed, not sampled, not cloned" rule, and
  reaches ElevenLabs Voice Design as the one path that satisfies it structurally. **A pinned
  narrator is never licence to voice a second character with it.**
- **An explicit user override still wins.** `[I]` If the user names a different `voice_id` for a
  specific job, use it — and say plainly in the brief that the channel pin was overridden, so
  the inconsistency is a recorded choice rather than a silent drift `[I]`.
