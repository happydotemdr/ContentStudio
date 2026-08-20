# The channel voice — pinned

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
substitute a "better fit" for a particular script. The voice is the channel's identity `[T]` `[I]`
and consistency across uploads is the point.

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
  Model:            eleven_v3 is this skill's default for Shorts [I]
                    (references/voice-selection.md) — not yet confirmed on this voice
  Stability:        pending
  similarity_boost: pending
  style:            pending
  speed:            pending
  use_speaker_boost:pending

Known-good tags:   PENDING — requires a v3 probe (see Open action 1)
Known-bad tags:    PENDING — requires a v3 probe (see Open action 1)
Dictionaries:      none
Caveats:           PVC on v3 is not fully optimized [T] — the three-way trade-off (run PVC as-is /
                   `use_pvc_as_ivc: true` / fall back to eleven_multilingual_v2) is not yet decided
                   for this voice (see Open action 3;
                   `.claude/skills/elevenlabs-audio/references/voice-profiles.md` "PVC on v3")
Verified on:       2026-08-18 — voice_id recorded; audition not yet run
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

Three real consequences of the PVC path, not housekeeping.

1. **Run one short v3 probe and fill the tag rows.** Tag effectiveness is bounded by the voice's
   training data `[T]` — "don't expect a whispering voice to suddenly shout with a `[shout]`
   tag" `[T]` (`.claude/skills/elevenlabs-audio/references/voice-profiles.md`). If the reference is
   emotionally narrow, v3 tags **underperform silently**: they do not error, the audio just comes
   back flat. Probe before a first master, and record what landed and what did not.
2. **Record the reference audio's condition.** Reference-audio quality still matters for a PVC,
   even though the failure mode is less acute than IVC's — "clean, no reverb, no background
   noise" `[T]`. This connects to a settings symptom worth knowing in advance: noise in the
   reference is exactly what a high `similarity_boost` reproduces faithfully. If the render
   sounds noisy, fix the reference rather than tuning `similarity_boost` down around it `[I]`.
3. **Decide the PVC-on-v3 trade-off.** PVC voices are not fully optimized for `eleven_v3` `[T]`.
   Before the first master, pick one of three options and record the choice on the card: run the
   PVC on v3 as-is (tags work, fidelity not fully optimized), set `use_pvc_as_ivc: true` (lower
   latency, IVC-grade fidelity, deliberate), or route to `eleven_multilingual_v2` (full PVC
   fidelity, no audio tags) `[T]`
   (`.claude/skills/elevenlabs-audio/references/voice-profiles.md` "PVC on v3"). This is a
   fidelity-vs-expressiveness trade that belongs to the user, not a silent default.

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
