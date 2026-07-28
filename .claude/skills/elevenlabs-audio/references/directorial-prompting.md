# Directorial prompting — the five layers, the tag catalog, and dialogue

Distilled from `docs/elevenlabs-production-runbook.md` §5.

**Everything in this file applies to `eleven_v3` only.** Audio tags and inline IPA are v3
features `[T]`. On every other model the only steering levers are punctuation, capitalization, and
the settings floats — which is not a limitation to work around silently, it's a routing decision
(`model-routing.md`).

## The five layers `[I]`

A construction order, not an ElevenLabs spec. What *is* verified: tags exist, are square-bracketed,
and are interpreted as natural-language delivery instructions `[T]`.

| Layer | What it is | Example |
|---|---|---|
| **1. Structural base** | Punctuation. Commas, em-dashes, ellipses, full stops | `The telemetry is stable — but proceed with caution.` |
| **2. Primary emotion** | Mood for a block | `[confident]` |
| **3. Delivery modifier** | Volume, tempo, projection | `[whispers]`, `[rushed]`, `[drawn out]` |
| **4. Acoustic event** | Inline non-verbal vocalization | `[sighs]`, `[laughs]`, `[gulps]` |
| **5. Role directive** | Accent or character override | `[strong French accent]`, `[pirate voice]` |

**Build layer 1 first and get it right before adding any tag** `[I]`. Punctuation steers delivery on
**every** model `[T]`; tags work on exactly one. A script whose rhythm only works because of tags is
fragile — it breaks the moment it's routed to Flash for a draft.

```
[confident][strong British accent] Welcome back to the main stage.
[sighs] It has been a long journey to reach this point.
[excited] But today — we reveal the final design.
```

## The verified tag catalog `[T]`

Tags documented by ElevenLabs:

| Category | Tags |
|---|---|
| **Emotion / delivery** | `[laughs]` `[whispers]` `[sighs]` `[sarcastic]` `[curious]` `[excited]` `[crying]` `[snorts]` `[mischievously]` |
| **Sound effects** | `[gunshot]` `[applause]` `[swallows]` `[gulps]` `[explosion]` |
| **Experimental** | `[strong X accent]` `[sings]` `[woo]` |

ElevenLabs additionally describes four functional categories `[T]`: situational awareness
(`[WHISPER]`, `[SHOUTING]`, `[SIGH]`), character performance (`[pirate voice]`, `[French accent]`),
emotional context (`[sigh]`, `[excited]`, `[tired]`), and delivery control (`[pause]`, `[rushed]`,
`[stammers]`, `[drawn out]`).

### The catalog is not closed — but going off it is an experiment `[T]`

> "Tags are natural-language instructions, not an enumerated parameter set."

You *may* write a tag that isn't listed. But the further from documented tags you go, the more it
becomes an experiment, and **it must be labelled as one in the output**. Never present an
undocumented tag as known-good. Mark it, and route it through a short v3 probe before it reaches a
master render `[I]`.

### The hard constraint is the voice, not the list `[T]`

> "Don't expect a whispering voice to suddenly shout with a `[shout]` tag."

A tag the voice's training data can't support is ignored or produces an artifact, and **no setting
fixes it**. Check the Voice Profile Card's known-good/known-bad tags before writing (`voice-profiles.md`).

### Syntax rules

- **No closing-tag syntax exists** `[T]`. Never write `[/whispers]`, `[end]`, or similar — it will
  be read as text or ignored. A tag applies forward until redirected by another tag or a structural
  break `[I]`.
- Tags are square-bracketed and can be **stacked**: `[confident][British accent]` `[I]`.
- Place an acoustic-event tag **where the event happens**, mid-sentence if that's where it belongs `[I]`.

### Tags vs. the stability mode — the contradiction to catch `[T]`

On v3, **Robust mode is "less responsive to directional prompts."** Docs recommend **Creative or
Natural for maximum expressiveness with audio tags.**

**A tagged script plus Robust stability is a self-cancelling configuration.** Catch it before the
render, not after. See `voice-settings.md` §v3 modes.

## Capitalization and punctuation `[T]`

ElevenLabs names capitalization and punctuation alongside tags as primary steering levers.

| Device | Effect `[I]` |
|---|---|
| CAPITALS | Emphasis, raised volume |
| Ellipsis `…` | Hesitation, trailing off |
| Em-dash `—` | A sharper break than a comma |
| Comma | Short breath |
| Full stop + line break | Full reset of cadence |
| `?` / `!` | Pitch contour at the phrase end |

Reach for these **before** a tag. They work everywhere, they survive a model change, and they cost
nothing in compatibility risk `[I]`.

## Multi-speaker dialogue — a different endpoint `[T]`

The supplied enterprise runbook showed inline `Speaker A:` / `Speaker B:` labels inside a normal TTS
payload. **That is not the documented mechanism** and will be read as literal text.

**Text to Dialogue:**

- Endpoint `/v1/text-to-dialogue/convert`
- **`eleven_v3` exclusively**
- Input is a **JSON array of turns, each with its own `text` and `voice_id`** — no inline labels
- **≤2,000 characters total across all inputs** — *lower* than v3's own 5,000 TTS cap
- Audio tags go inside each turn's `text` as normal
- **Explicitly not intended for real-time** applications like conversational agents

```json
{
  "inputs": [
    { "text": "[confident] We are ready to launch the system immediately.",
      "voice_id": "VOICE_A" },
    { "text": "[panicked] Wait — [gasp] the cooling line hasn't been verified!",
      "voice_id": "VOICE_B" }
  ],
  "model_id": "eleven_v3"
}
```

Interruption and overlap tags (`[interrupting]`, `[overlapping]`) come from the supplied runbook and
are **`[T-unverified]`** — not in the documented catalog. They may work as natural-language
instructions `[T]`, but flag them as experimental rather than presenting them as dialogue-control
parameters.

## Pre-render checklist for a directorial script

1. Layer 1 (punctuation) works on its own, without tags `[I]`
2. Every tag is either in the catalog `[T]` or **explicitly flagged experimental** `[I]`
3. No closing tags `[T]`
4. Model is `eleven_v3` — if not, every tag is dead weight `[T]`
5. Stability mode is Natural or Creative, not Robust `[T]`
6. Tags are compatible with the voice's known range `[T]`
7. Multiple speakers → Text-to-Dialogue, ≤2,000 chars total `[T]`
8. Numbers, dates, currencies, URLs pre-converted to words `[T]` (see `api-payload.md` §normalization)
9. Chunks under the model's cap, split on sentence breaks `[I]`

Items 3–7 are what Validation Gate 1 checks mechanically (`validation-gates.md`).
