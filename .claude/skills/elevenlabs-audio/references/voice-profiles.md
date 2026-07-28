# Voice profiles — exploration, cloning, and the reusable profile card

Distilled from `docs/elevenlabs-production-runbook.md` §2, and cross-read with
`.claude/skills/voiceover-brief/references/voice-selection.md` for the corpus view.

## Why voice comes first

**Tag effectiveness is bounded by the voice's training data** `[T]`:

> "Voice selection and training data determine tag effectiveness. Don't expect a whispering voice
> to suddenly shout with a `[shout]` tag."

No setting fixes a voice that cannot perform what the script asks for. That makes voice choice
**upstream of tag choice**, not a parallel decision — pick the voice, then write to what it can do.

For IVC voices destined for `eleven_v3`, prefer a reference recording with **broad emotional
range** `[T]` — v3 can only perform emotions the source demonstrates.

## Exploration workflow (`voice: explore`)

1. **State the performance requirement first**, in plain words: what must this voice be able to do?
   (Shout? Whisper? Sustain 40 minutes of neutral narration? Carry a sarcastic aside?)
2. **Shortlist 3–5 candidates** and say what each is *for* — not a ranked list, a set of distinct
   options. If the job is a ContentStudio Short, `voiceover-brief` has already made this call; do
   not redo it.
3. **Audition on `eleven_flash_v2_5` with a 250–500 character excerpt** `[I]`. Never audition on the
   flagship — auditioning is the single easiest place to waste credits, and voice *fit* is audible
   on Flash.
   - Caveat to state: Flash renders no tags `[T]`, so the audition tests timbre, pace, and
     character — **not** how the voice handles `[whispers]`. Confirm tag behavior with one short v3
     probe before committing.
4. **Pick the excerpt deliberately**: the hardest line in the script, not the first one. A voice
   that survives the hardest beat survives the rest `[I]`.
5. **Emit a Voice Profile Card** for the winner.

The corpus adds one non-obvious argument here: it favors a **cloned own voice over stock/default
voices**, on reach grounds — see `voiceover-brief/references/voice-selection.md` for the `[C]`
citations and the default-voice warning. That is a creative/strategy argument, not a platform one;
keep it attributed rather than restating it as a technical fact.

## IVC vs. PVC `[T]`

| | Instant Voice Cloning | Professional Voice Cloning |
|---|---|---|
| Reference audio | **~1–2 minutes**, clean — no reverb, artifacts, or background noise | **30 minutes minimum**; 2–3 hours for the best result |
| Plan | available on most plans | **Creator plan or above** |
| Mechanism | zero-shot; an educated guess from prior training data — **does not train a custom model** | trains a dedicated model; "virtually indistinguishable from the original" |
| Turnaround | immediate | training time |

This resolves the source inconsistency flagged in
`voiceover-brief/references/voice-selection.md:26-28` (Starter vs. Creator+): **IVC is broadly
available; PVC is the Creator+ gate** `[T]`.

**Reference-audio quality is the whole ballgame for IVC** `[T]`. "Clean, no reverb, no background
noise" is a hard requirement, not a preference — and it connects directly to a settings symptom:
noise in the reference is what a high `similarity_boost` faithfully reproduces (`voice-settings.md`).
Fixing the reference beats tuning around it `[I]`.

## PVC on v3 — the caveat, stated correctly `[T]`

The supplied enterprise runbook claimed PVC voices "fall back to IVC representations" automatically
under v3. **That is not documented.** What is:

- "Professional Voice Clones (PVCs) are currently not fully optimized for Eleven v3."
- **`use_pvc_as_ivc`** is an explicit request parameter (boolean, default `false`) that substitutes
  the IVC version **to reduce latency**.

So the substitution is an **opt-in you control**, not an automatic fallback. When a PVC voice is
routed to v3, present three options rather than one:

| Option | Trade |
|---|---|
| Run the PVC on v3 as-is | Tags work; fidelity is not fully optimized |
| Set `use_pvc_as_ivc: true` | Lower latency, IVC-grade fidelity, deliberate and stated |
| Run on `eleven_multilingual_v2` | Full PVC fidelity; **no audio tags** |

Do not pick silently. This is a genuine fidelity-vs-expressiveness trade and it belongs to the user.

## The Voice Profile Card

Emit this at the end of Stage A. The user pastes it back on later runs to skip straight to Stage C —
which is how a one-off exploration becomes a reusable production asset.

```
=== VOICE PROFILE CARD ===
Name:            [human label]
voice_id:        [20-char id]
Source:          library | IVC | PVC
Reference audio: [duration + quality notes, if cloned]
Persona:         [1-2 lines: age/texture/register/energy the voice actually delivers]

Locked settings:
  Model:            [model_id it was tuned against]
  Stability:        [v3 mode, or float]
  similarity_boost: [value]
  style:            [value]
  speed:            [value]
  use_speaker_boost:[bool]

Known-good tags:   [tags confirmed to land on this voice, from a v3 probe]
Known-bad tags:    [tags that were ignored or produced artifacts]
Dictionaries:      [pronunciation_dictionary_id + version_id, if any]
Caveats:           [e.g. "PVC — not fully optimized for v3"; "narrow emotional range,
                    do not ask for [shouts]"]
Verified on:       [date]
```

Two fields carry most of the value on re-use:

- **Known-good / known-bad tags.** Tag effectiveness is voice-specific `[T]` and cannot be looked
  up — it can only be observed. Recording it once turns an experiment into a fact about *this voice*.
- **Locked settings + the model they were tuned against.** Settings do not transfer cleanly across
  models — a v3 stability *mode* has no float equivalent `[T]`. A card that names its model is
  reusable; one that doesn't is a trap.

Treat a supplied card as authoritative for that voice and re-verify only what changed `[I]`.
