---
version: 1
---
## Voice pick
**Cloned own voice, Eleven v3 model.** A cloned-own voice is the corpus's top pick on two
grounds: it's 100% unique against the sea of library-voice channels (avoiding the
detected-repeat/shadowban risk library voices carry `(One Person Business, 84bavOadYCI)`
`(Make Money Matt, TvJhpOxFRsE)`), and it's currently the one path that needs no YouTube
altered-content disclosure `(Romayroh, OrPYWlXMQws)`. Eleven v3 over Multilingual v2/Flash
because this script mixes a punchy Hook/Loop with a narrative Build beat — v3's audio-tag
system and Text-to-Dialogue expressiveness earn their keep on exactly that mix `[I]` (this
skill's extrapolation from the model table, not a corpus-stated default). If a library voice
is used instead, pick a lesser-used one, never a default preset `(Make Money Matt,
TvJhpOxFRsE)`, and disclose via YouTube's altered-content box `[C] (Romayroh, G9LfE3k-IEI)`.

## Settings
This script mixes content types across its beats — no corpus/guide source gives a single
blend number for that, so each beat is generated as its own section with its own settings
rather than one setting for the whole track `[I]` (extrapolated from the preset table, per
`references/settings-by-content-type.md`'s "Mixed scripts" note).

| Beat | Type | Stability | Similarity/Clarity | Style | Speed | Speaker boost |
|---|---|---|---|---|---|---|
| Hook (0–3s) | Marketing/Shorts | 60% | 80% | 40% | 1.1× | ON |
| Setup (3–8s) | Narration/technical | 70% | 80% | 15% | 0.95× | ON |
| Build/Value + re-hook (8–28s) | Storytelling/character | 50% | 80% | 35% | 1.0× | ON |
| Payoff (28–38s) | Narration/technical | 70% | 80% | 15% | 0.95× | ON |
| Loop/CTA (38–45s) | Marketing/Shorts | 60% | 80% | 40% | 1.1× | ON |

Hook/Loop sit at the lower end of the Marketing/Shorts ranges rather than the top (e.g. 60%
style, not 60%) — the script's own content is a measured explainer, not hype/clickbait
delivery, so pushing style/speed to the preset's max would fight the material. Similarity is
held at 80% across every beat, per the settings guide: never push past ~90% (over-enunciated
"news anchor" artifact) `[T]`.

## Script, reformatted for TTS
Six generation units (five beats, Build/Value split at the re-hook) so a bad take re-rolls
cheaply without regenerating the whole track `[T]`.

```
[HOOK]
Why would a federal proposal count your kid's registration app… as "youth sports"?

[SETUP]
Because 2,300 years ago, Aristotle named two very different ways to make money.

[BUILD/VALUE]
One kind earns money by making or trading something people need, with a natural stopping
point. The other has none — because nothing's actually being made.

[RE-HOOK @ ~15s]
His proof: a trader who quietly bought up every oil press in town… but once he had them
all, he charged whatever he wanted.

[PAYOFF]
Because that's the monopoly move — so the proposal counts leagues, facilities, and apps
the same way, with forced sellbacks and fee refunds.

[LOOP/CTA]
When "youth sports" means an app… what's really being sold?
```

Annotations:
- No v3 audio tags (`[excited]`, `[whispers]`, etc.) applied — the script's tone is measured
  explainer rather than theatrical, and none of the five confirmed tags fit without forcing
  one; ellipses do the pacing work instead `[T]`.
- Ellipses placed before the Hook's and Loop's punchline word, and before "but" in the
  re-hook — punctuation-as-pacing to land the contrast word, per the corpus's "but is the
  most powerful word" finding carried over from the script itself.
- Flag for spot-check, not a respelling: "Aristotle" and "2,300" are common enough that v3
  should render them correctly, but verify the generated take before locking it in — this is
  the one proper noun and one number in the script.
- Generate the Hook and Loop/CTA lines as 2–3 takes each and pick the best — these are the
  highest-leverage lines in the script `(Nick Nimmin, IF-PD6XMjYY)`.

## Production & loudness
- **Normalize the voice track to −14 LUFS** `[T]` — YouTube's loudness target; leave headroom,
  avoid clipping.
- **Duck the music bed to −21 to −22 dB under the voice** — the corpus's practitioner number,
  tied directly to an AVD complaint `(Romayroh, Wox4Jt_2t6w)` `(Roberto Blake, iaTavrWIGDM)` —
  given alongside the settings guide's more general −12 to −18 dB range (−16 dB safe default)
  `[T]`, since the two sources disagree and neither is silently preferred.
- Use one-click auto-ducking rather than hand-riding the fader `(Roberto Blake, iaTavrWIGDM)`.
- No music beat/genre guidance is corpus-specific to this script's content — pick a bed that
  doesn't clash with the measured, explainer tone; no music beats the wrong music
  `(Kallaway, i7upRL4H1FM)`.
- AI-disclosure reminder: only exempt if the voice is a clone of your own; any library voice
  or non-own clone needs the YouTube altered-content disclosure box `[C] (Romayroh,
  G9LfE3k-IEI)`.

## Downstream
Feeds `shorts-assembly`, alongside `visual-prompts`'s prompt sheet.
