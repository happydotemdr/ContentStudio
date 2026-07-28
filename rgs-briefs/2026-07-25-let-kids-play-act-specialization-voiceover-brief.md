---
version: 1
---
## Voice pick
**Cloned own voice, Eleven v3 model.** A cloned-own voice is the corpus's top pick on two
grounds: it's 100% unique against the sea of library-voice channels (avoiding the
detected-repeat/shadowban risk library voices carry `(One Person Business, 84bavOadYCI)`
`(Make Money Matt, TvJhpOxFRsE)`), and it's currently the one path that needs no YouTube
altered-content disclosure `(Romayroh, OrPYWlXMQws)`. Eleven v3 over Multilingual v2/Flash
because this script mixes a punchy stat-drop Hook/Loop with a narrative Setup/Build — v3's
audio-tag system and Text-to-Dialogue expressiveness earn their keep on exactly that mix `[I]`
(this skill's extrapolation from the model table, not a corpus-stated default). If a library
voice is used instead, pick a lesser-used one, never a default preset `(Make Money Matt,
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

Hook/Loop sit at the lower end of the Marketing/Shorts ranges rather than the top — the
script's own content is a measured, evidence-led warning, not hype/clickbait delivery, so
pushing style/speed to the preset's max would fight the material. Similarity is held at 80%
across every beat, per the settings guide: never push past ~90% (over-enunciated "news anchor"
artifact) `[T]`.

## Script, reformatted for TTS
Six generation units (five beats, Build/Value split at the re-hook) so a bad take re-rolls
cheaply without regenerating the whole track `[T]`.

```
[HOOK]
Multi-sport NFL players had longer, safer careers… than the ones who specialized early.

[SETUP]
Over 260 years ago, Roo-SOH warned about trading a kid's present joy… for a future that
might never come.

[BUILD/VALUE]
That's the exact trade a family makes — cutting three sports down to one by age nine,
chasing "the path."

[RE-HOOK @ ~15s]
But the medical establishment's own position on this is blunt: there's no evidence early
specializing is needed for elite success… just extra injury and burnout risk.

[PAYOFF]
A review of six thousand athletes found the twist: early specializing predicts junior
success… not senior, world-class success.

[LOOP/CTA]
So does specializing early… actually get them there?
```

Annotations:
- No v3 audio tags (`[excited]`, `[whispers]`, etc.) applied — the script's tone is a measured,
  evidence-led warning rather than theatrical, and none of the five confirmed tags fit without
  forcing one; ellipses do the pacing work instead `[T]`.
- Ellipses placed before each beat's contrast/punchline clause (Hook's "than…", Setup's
  "for a future…", the re-hook's "just extra injury…", Payoff's "not senior…", Loop's "actually
  get them there") — punctuation-as-pacing to land the twist word, per the corpus's "but is the
  most powerful word" finding carried over from the script itself.
- **Phonetic respelling applied:** "Rousseau" → `Roo-SOH` in the generation text above (the
  written proper noun stays "Rousseau" everywhere else — script, on-screen text, captions —
  only the TTS input is respelled). Flagged because a French proper noun is a genuine
  mispronunciation risk in a way the prior script's "Aristotle" wasn't `[T]`; spot-check the
  generated take before locking it in.
- "Six thousand" is written as words, not digits ("6,000"), since TTS models read digit strings
  less reliably than spelled-out numbers for a spoken figure this size `[T]`.
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
  doesn't clash with the measured, evidence-led tone; no music beats the wrong music
  `(Kallaway, i7upRL4H1FM)`.
- AI-disclosure reminder: only exempt if the voice is a clone of your own; any library voice
  or non-own clone needs the YouTube altered-content disclosure box `[C] (Romayroh,
  G9LfE3k-IEI)`.

## Downstream
Feeds `shorts-assembly`, alongside `visual-prompts`'s prompt sheet.
