# ElevenLabs Production Runbook — engines, configuration, prompting & credit discipline

> **Source & scope.** This document is **not corpus-derived.** It was assembled from a supplied
> enterprise audio-engineering runbook and then verified claim-by-claim against live ElevenLabs
> documentation on **2026-07-26**. For the corpus view of ElevenLabs — the 24 voiceover/audio
> findings extracted from the 420-video creator-education corpus — see
> `docs/elevenlabs-voiceover-guide.md`. The two documents are complementary and deliberately
> separate: that one tells you what working faceless-YouTube creators actually do; this one tells
> you what the platform actually supports.
>
> **The supplied runbook was substantially wrong in eight places.** See §10. Do not treat the
> original runbook text as authoritative anywhere it conflicts with this document.

## Provenance markers

This document uses the repo's standard key (`docs/README.md`), with one qualifier added for
material that could not be confirmed:

- **`[T]`** — Tool/policy fact **web-verified against live ElevenLabs docs 2026-07-26**. These go
  stale fast; re-verify before relying on them.
- **`[T-unverified]`** — Asserted by the supplied enterprise runbook and **not confirmed** against
  live docs on 2026-07-26. Treat as a starting hypothesis, never as a fact. Say so out loud when
  you use one.
- **`[I]`** — Industry/general audio-engineering practice, not specific to ElevenLabs.
- **`[C]`** — Corpus-cited `(Channel, video_id)`. Rare here; the corpus material lives in
  `docs/elevenlabs-voiceover-guide.md`.

A normative line in this document with no marker is a bug.

---

## 1. Engine topology & model routing

### 1.1 The model table `[T]`

| `model_id` | Max chars/request | Languages | Latency | Price | Use it for |
|---|---|---|---|---|---|
| `eleven_v3` | 5,000 | 70+ | not published | standard | Flagship. Expressive delivery, audio tags, multi-speaker dialogue |
| `eleven_multilingual_v2` | 10,000 | 29 | not published | standard | Long-form narration, audiobooks, stable continuous VO |
| `eleven_flash_v2_5` | 40,000 | 32 | ~75 ms | **50% lower per character** | Real-time agents, telephony, **and draft iteration** |
| `eleven_flash_v2` | 30,000 | English only | ~75 ms | 50% lower | Budget English; **the only non-v3 model that honors phoneme tags** (§6) |
| `eleven_multilingual_sts_v2` | 10,000 | 29 | not published | standard | Speech-to-Speech (voice changer) |
| `eleven_english_sts_v2` | 10,000 | English only | not published | standard | Speech-to-Speech, English |

`eleven_v3` is the documented flagship — "our latest and most advanced speech synthesis model,"
with dramatic delivery and native multi-speaker dialogue `[T]`. The API's own default `model_id`
when you omit it is `eleven_multilingual_v2` `[T]` — so an unset `model_id` silently gives you the
stable-but-untagged engine. Always set it explicitly.

`eleven_turbo_v2_5` exists and is referenced in ElevenLabs' pricing material alongside Flash v2.5
as a discounted model `[T]`, but it was **not listed on the models overview page** at verification
time. Its commonly-quoted 250–300 ms latency is **`[T-unverified]`**. Prefer Flash v2.5 unless you
have a specific reason to reach for Turbo, and re-verify before quoting Turbo's specs.

Latency figures other than Flash's ~75 ms are **`[T-unverified]`** — the supplied runbook quoted
~1,000–2,000 ms for v3 and ~500–800 ms for Multilingual v2, and live docs publish neither. Do not
state these as facts. What *is* documented and safe to say: v3 is the most expressive and least
suited to real-time; Flash is the low-latency option `[T]`.

### 1.2 Feature-compatibility matrix `[T]`

This is the table that prevents the most common silent failure — sending a directive to a model
that ignores it. **Nothing errors; the feature is simply dropped and the audio comes back wrong.**

| Feature | `eleven_v3` | `eleven_multilingual_v2` | `eleven_flash_v2_5` | `eleven_flash_v2` |
|---|---|---|---|---|
| Audio tags (`[whispers]`, `[sighs]`…) | **yes** | no | no | no |
| PLS `<phoneme>` tags | **yes** | no — alias only | **no** — alias only | **yes** (English) |
| PLS `<alias>` tags | yes | yes | yes | yes |
| Inline IPA in `/slashes/` | **yes** | no | no | no |
| Multi-speaker dialogue | yes, via Text-to-Dialogue (§5.4) | no | no | no |
| `language_code` enforcement | yes | **not supported** | yes | yes |
| Discrete stability modes | **yes** (§4.1) | no — continuous float | no — continuous float | no — continuous float |

Two rows deserve emphasis because the supplied runbook got them wrong:

- **Phoneme tags are `eleven_v3` + `eleven_flash_v2` only** — *not* `eleven_flash_v2_5` `[T]`.
  Flash v2.5 is the draft/real-time workhorse and it cannot do phonemes. Phoneme tags are
  English-only by default; to use IPA or CMU pronunciations in other languages you must be on
  `eleven_v3` `[T]`.
- **`eleven_multilingual_v2` does not support `language_code`** `[T]` — the parameter is accepted
  and ignored.

---

## 2. Voice cloning: IVC vs. PVC

| | Instant Voice Cloning (IVC) | Professional Voice Cloning (PVC) |
|---|---|---|
| Reference audio | ~1–2 minutes, clean, no reverb/artifacts/background noise `[T]` | 30 minutes minimum; **2–3 hours for the best result** `[T]` |
| Plan | available on most plans `[T]` | **Creator plan or above** `[T]` |
| What it does | zero-shot; makes an educated guess from prior training data — **does not train a custom model** `[T]` | trains a dedicated model on your voice data; "virtually indistinguishable from the original" `[T]` |
| Turnaround | immediate | training time required |

This resolves the source inconsistency flagged in
`.claude/skills/voiceover-brief/references/voice-selection.md` (Starter vs. Creator+ for cloning):
**IVC is broadly available; PVC is the Creator+ gate** `[T]`.

### 2.1 PVC on v3 — the caveat, stated correctly `[T]`

The supplied runbook claimed PVC models "currently fall back to IVC representations" automatically
under v3. **That is not what the docs say.** What is documented:

- "Professional Voice Clones (PVCs) are currently not fully optimized for Eleven v3" `[T]`.
- There is an explicit request parameter, **`use_pvc_as_ivc`** (boolean, default `false`), which
  substitutes the IVC version of a PVC voice **to reduce latency** `[T]`.

So the substitution is an **opt-in you control**, not an automatic fallback. Practical guidance:
if a PVC voice sounds off on v3, that is expected — either accept it, set `use_pvc_as_ivc: true`
deliberately, or render that job on `eleven_multilingual_v2` where the PVC is fully optimized.

For IVC voices destined for v3, prefer a reference recording with **broad emotional range** — v3
can only perform emotions the source voice demonstrates `[T]`.

---

## 3. The API parameter surface `[T]`

Endpoint: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
(append `/stream` for streaming). Auth header: `xi-api-key`.

### 3.1 Request body

| Parameter | Type / range | Default | Notes |
|---|---|---|---|
| `text` | string, required | — | The payload. Billing is per character, including spaces and punctuation. |
| `model_id` | string | `eleven_multilingual_v2` | **Always set explicitly** — the default is not the flagship. |
| `language_code` | ISO 639-1 | — | Ignored by models that don't support it; **unsupported on `eleven_multilingual_v2`**. |
| `voice_settings.stability` | 0–1 | 0.5 | Lower = wider emotional range. On v3, see §4.1 — it's three discrete modes, not a free float. |
| `voice_settings.similarity_boost` | 0–1 | 0.75 | Adherence to the original voice. |
| `voice_settings.style` | **0 and up** (not capped at 1) | 0 | Exaggerates speaker style. **Non-zero increases latency.** |
| `voice_settings.speed` | **0.7–1.2** | 1.0 | Extreme values degrade quality. |
| `voice_settings.use_speaker_boost` | boolean | `true` | Boosts speaker similarity; increases compute. |
| `seed` | integer **0–4,294,967,295** | — | Best-effort deterministic sampling when all other params are identical. |
| `previous_text` / `next_text` | string | — | Prosodic context across chunk boundaries (§7). |
| `previous_request_ids` / `next_request_ids` | array, **max 3 each** | — | Stronger continuity than the text params — stitches to actual prior generations (§7). |
| `pronunciation_dictionary_locators` | array, **max 3** | — | `{pronunciation_dictionary_id, version_id}`; `version_id` optional (latest used if omitted). |
| `use_pvc_as_ivc` | boolean | `false` | See §2.1. |
| `apply_text_normalization` | `auto` \| `on` \| `off` | `auto` | Controls number/date/currency spell-out (§3.3). |
| `apply_language_text_normalization` | boolean | `false` | **Japanese only** at present; significantly increases latency. |

### 3.2 Query parameters

| Parameter | Values | Default | Notes |
|---|---|---|---|
| `output_format` | `{codec}_{sample_rate}_{bitrate}` | `mp3_44100_128` | Full enum in §3.4. **`mp3_44100_192` requires Creator tier+; PCM/WAV at 44.1 kHz requires Pro tier+.** |
| `optimize_streaming_latency` | 0–4 | 0 | 1 ≈ 50% improvement, 2 ≈ 75%, 3 maximum, 4 maximum + text normalizer off. Quality cost rises with the number. |
| `enable_logging` | boolean | `true` | `false` = zero-retention mode. **Enterprise-only, and it disables history *and request stitching*** — so it is mutually exclusive with `previous_request_ids`/`next_request_ids`. |

### 3.3 Text normalization `[T]`

Normalization (spelling out numbers, dates, currencies) is on by default across all TTS models.
Documented problem areas: phone numbers, currencies, calendar events, times, addresses, URLs, unit
abbreviations, keyboard shortcuts. The documented mitigations, in order of reliability:

1. **Pre-convert in the text itself** — `"$1,000"` → `"one thousand dollars"`. Most reliable.
2. **Use a larger model** — Multilingual v2 handles numbers more naturally than Flash v2.5.
3. Regex preprocessing for systematic cases.

Note the interaction: `optimize_streaming_latency: 4` **turns the normalizer off** `[T]`. If you
push latency that far, you own normalization in the text.

### 3.4 `output_format` enum `[T]`

`alaw_8000`, `ulaw_8000`,
`mp3_22050_32`, `mp3_24000_48`, `mp3_44100_32`, `mp3_44100_64`, `mp3_44100_96`, `mp3_44100_128`,
`mp3_44100_192`,
`opus_48000_32`, `opus_48000_64`, `opus_48000_96`, `opus_48000_128`, `opus_48000_192`,
`pcm_8000`, `pcm_16000`, `pcm_22050`, `pcm_24000`, `pcm_32000`, `pcm_44100`, `pcm_48000`,
`wav_8000`, `wav_16000`, `wav_22050`, `wav_24000`, `wav_32000`, `wav_44100`, `wav_48000`.

Practical picks: `mp3_22050_32` for drafts (cheap bandwidth, adequate to judge delivery) `[I]`;
`mp3_44100_192` or `pcm_44100` for masters, **subject to the tier gates above** `[T]`;
`ulaw_8000`/`alaw_8000` for telephony `[I]`.

---

## 4. Voice settings & artifact diagnosis

### 4.1 v3 stability is three discrete modes, not a float `[T]`

This is the single biggest correction to the supplied runbook. On `eleven_v3`, stability is:

| Mode | Behavior (documented) | When |
|---|---|---|
| **Creative** | "More emotional and expressive, but prone to hallucinations" | Maximum tag responsiveness; character work; short payloads you can re-roll |
| **Natural** | "Closest to the original voice recording — balanced and neutral" | **Default choice** for tagged narration |
| **Robust** | "Highly stable, but less responsive to directional prompts" | Consistency-critical long runs — **but it suppresses audio tags** |

Docs recommend **Creative or Natural for maximum expressiveness with audio tags** `[T]`. The
corollary is a hard rule: **if you wrote audio tags and selected Robust, the tags are being
fought.** That is the correct, verified form of the runbook's claim that "high stability prevents
the engine from executing dramatic tags."

On the non-v3 models, `stability` is the continuous 0–1 float, default 0.5 `[T]`.

### 4.2 Numeric bands for the non-v3 models

The supplied runbook's specific bands could not be verified against live docs and are marked
accordingly. They are reasonable starting points, not facts:

| Setting | Suggested band | Marker |
|---|---|---|
| `stability`, long-form narration | 0.50–0.65 | `[T-unverified]` |
| `stability`, expressive delivery | 0.30–0.45 | `[T-unverified]` |
| `similarity_boost` | 0.65–0.75; above ~0.85 risks reproducing noise present in the reference audio | `[T-unverified]` |
| `style` | 0.30–0.50 for noticeable exaggeration without identity drift | `[T-unverified]` |

What *is* verified: the defaults (0.5 / 0.75 / 0 / 1.0 / speaker boost on), the ranges, that
non-zero `style` increases latency, and that speaker boost increases compute `[T]`.

### 4.3 Artifact → cause → fix

Directionally sound, mechanistically unverified — the causal claims below are the runbook's, not
ElevenLabs'. Marked `[T-unverified]` except where noted.

| Symptom | Likely cause | Fix |
|---|---|---|
| Slurring, vocal fry, wild emotional swings | `stability` too low | Raise stability; on v3 move Creative → Natural `[T]` |
| Flat, monotone, no inflection | `stability` too high | Lower it; on v3 move Robust → Natural `[T]` |
| Audio tags ignored | Robust mode on v3, or a non-v3 model `[T]` | Switch to Natural/Creative; confirm the model supports tags (§1.2) `[T]` |
| High-frequency hiss, ringing, metallic edge | `similarity_boost` too high — over-fitting to noise in the reference | Lower toward 0.65–0.75; fix the reference audio |
| Voice drifts from the intended character | `style` too high | Lower style |
| Cadence drops or pitch jumps at chunk seams | Missing stitching context | Add `previous_text`/`next_text`, or better `previous_request_ids` (§7) `[T]` |
| Numbers, dates, URLs read wrong | Text normalization | Pre-convert in the text (§3.3) `[T]` |
| Proper nouns / jargon mispronounced | No pronunciation rule | Dictionary or inline IPA (§6) `[T]` |

Before changing settings, check the two things that are free: **is the model right (§1.2), and is
the text itself the problem (§3.3)?** Most "bad voice settings" are actually one of those `[I]`.

---

## 5. Directorial prompting (v3)

### 5.1 The five layers `[I]`

A repeatable construction order. The layering itself is craft framing, not an ElevenLabs spec —
what *is* verified is that tags exist, are square-bracketed, and are interpreted as natural-language
delivery instructions `[T]`.

1. **Structural base** — punctuation. Commas, em-dashes, ellipses, full stops set baseline rhythm
   and pause length. Do this first; it survives every model.
2. **Primary emotion** — the mood for a block: `[confident]`, `[melancholic]`, `[excited]`.
3. **Delivery modifier** — volume, tempo, projection: `[whispers]`, `[shouts]`, `[rushed]`,
   `[drawn out]`.
4. **Acoustic event** — inline non-verbal vocalizations: `[sighs]`, `[laughs]`, `[gulps]`.
5. **Role directive** — accent or character override: `[strong French accent]`, `[pirate voice]`.

### 5.2 Verified tag vocabulary `[T]`

Tags documented by ElevenLabs, by category:

- **Emotion / delivery:** `[laughs]`, `[whispers]`, `[sighs]`, `[sarcastic]`, `[curious]`,
  `[excited]`, `[crying]`, `[snorts]`, `[mischievously]`
- **Sound effects:** `[gunshot]`, `[applause]`, `[swallows]`, `[gulps]`, `[explosion]`
- **Experimental:** `[strong X accent]`, `[sings]`, `[woo]`

ElevenLabs describes the broader categories as situational awareness (`[WHISPER]`, `[SHOUTING]`,
`[SIGH]`), character performance (`[pirate voice]`, `[French accent]`), emotional context
(`[sigh]`, `[excited]`, `[tired]`), and delivery control (`[pause]`, `[rushed]`, `[stammers]`,
`[drawn out]`) `[T]`.

**Tags are natural-language instructions, not an enumerated parameter set** `[T]`. The list above
is not a closed vocabulary — you may write a tag that isn't on it. But the further you get from
documented tags, the more it becomes an experiment, and it must be labelled as one. Never present
an undocumented tag as a known-good one.

**The hard constraint on tags is the voice, not the tag list** `[T]`:

> "Voice selection and training data determine tag effectiveness. Don't expect a whispering voice
> to suddenly shout with a `[shout]` tag."

So tag choice is downstream of voice choice. A tag that the voice's training data can't support
will be ignored or produce an artifact, and no setting fixes that.

There is **no documented closing-tag syntax.** Do not invent `[/whispers]` or similar. A tag
applies forward until the delivery is redirected by another tag or a structural break `[I]`.

### 5.3 Capitalization and punctuation `[T]`

ElevenLabs' own prompting guidance names capitalization and punctuation — alongside tags — as
primary steering levers. Caps read as emphasis/volume; ellipses create hesitation; em-dashes create
sharper breaks than commas `[I]`. Use these before reaching for a tag: they work on **every** model,
tags work on one.

### 5.4 Multi-speaker dialogue is a different endpoint `[T]`

The supplied runbook showed inline `Speaker A:` / `Speaker B:` labels inside a normal TTS payload.
**That is not the documented mechanism.** Multi-speaker uses **Text to Dialogue**:

- Endpoint: `/v1/text-to-dialogue/convert`
- **Eleven v3 exclusively**
- Input is a **JSON array of turns, each with its own `text` and `voice_id`** — there are no inline
  speaker labels in the text
- **Keep total text across all inputs at or below 2,000 characters per request**
- Audio tags go inside each turn's `text` as usual
- Explicitly **not intended for real-time applications** like conversational agents

Note the 2,000-character dialogue ceiling is *lower* than v3's own 5,000-character TTS cap.

---

## 6. Pronunciation control

Two separate mechanisms. Pick by model.

### 6.1 Inline IPA — v3 only `[T]`

On `eleven_v3`, write IPA between forward slashes directly in the text:

```
The cluster runs on /ˌkuːbərˈnɛtɪs/ in production.
```

Include stress markers (`ˈ` primary, `ˌ` secondary). ElevenLabs reports roughly **80–90%
pronunciation consistency** with this method `[T]` — good, not deterministic. For a term that must
be right every single time in a long run, a dictionary is the stronger tool.

### 6.2 PLS pronunciation dictionaries `[T]`

Files in `.PLS` (W3C Pronunciation Lexicon Specification) or `.TXT` format, uploaded once and
attached to requests by locator.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0"
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.w3.org/2005/01/pronunciation-lexicon
    http://www.w3.org/TR/2007/CR-pronunciation-lexicon-20071212/pls.xsd"
    alphabet="ipa" xml:lang="en-US">

  <!-- phoneme: eleven_v3 and eleven_flash_v2 ONLY -->
  <lexeme>
    <grapheme>Kubernetes</grapheme>
    <phoneme>ˌkuːbərˈnɛtɪs</phoneme>
  </lexeme>

  <!-- alias: works on EVERY model - the safe default -->
  <lexeme>
    <grapheme>SQL</grapheme>
    <alias>Sequel</alias>
  </lexeme>

  <!-- case sensitivity: enumerate every casing you expect to see -->
  <lexeme>
    <grapheme>nginx</grapheme>
    <alias>engine ex</alias>
  </lexeme>
  <lexeme>
    <grapheme>NGINX</grapheme>
    <alias>engine ex</alias>
  </lexeme>
  <lexeme>
    <grapheme>Nginx</grapheme>
    <alias>engine ex</alias>
  </lexeme>
</lexicon>
```

Verified rules:

- **`<phoneme>` works only on `eleven_v3` and `eleven_flash_v2`.** Every other model — including
  `eleven_multilingual_v2` and `eleven_flash_v2_5` — requires `<alias>` `[T]`.
- **Phoneme tags are English-only by default**; for IPA/CMU in other languages you must use
  `eleven_v3` `[T]`.
- Alphabets: **IPA** or **CMU Arpabet**. Docs recommend **CMU Arpabet for reliability** on the v2
  SSML path (`<phoneme alphabet="cmu-arpabet" ph="...">word</phoneme>`) `[T]`.
- Phoneme substitution operates on **individual words only** `[T]`.
- **PLS matching is case-sensitive** — the docs' own example includes a term both with and without
  a capital letter for this reason `[T]`. Enumerate lowercase, Title Case, and UPPERCASE.
- **Maximum 3 locators per request** `[T]`.
- Create via `pronunciation_dictionaries.create_from_file()` (SDK) or the equivalent REST
  create-from-file / add-from-rules endpoints; apply via `pronunciation_dictionary_locators` with
  `{pronunciation_dictionary_id, version_id}` — `version_id` is optional and defaults to latest
  `[T]`.

**Pin `version_id` in production.** Omitting it means a dictionary edit silently changes the audio
of a job you thought was reproducible `[I]`.

### 6.3 Choosing between them `[I]`

| Situation | Use |
|---|---|
| One-off odd word, v3, short script | Inline IPA (§6.1) |
| Same terms recur across many jobs | Dictionary (§6.2) |
| Model is not v3 or flash_v2 | Dictionary with `<alias>` — no other option |
| Must be exactly right every time | Dictionary, `version_id` pinned |
| Non-English phonemes | v3 + dictionary |

---

## 7. Chunk boundaries & context stitching `[T]`

Splitting a long script into per-request chunks produces audible seams: cadence resets, pitch
drops, unnatural pauses. Two mechanisms, in ascending order of strength:

**Weaker — text context.** Pass `previous_text` and `next_text` with the surrounding copy. The
runbook's "final/first ~100 characters" heuristic is `[I]`, not a documented figure; what's
documented is only that these parameters improve continuity across split generations `[T]`. A
sentence or two of real context on each side is a sensible read of that.

**Stronger — request stitching.** Pass `previous_request_ids` (and/or `next_request_ids`, **max 3
each**) referencing the actual prior generations `[T]`. This anchors to rendered audio rather than
to text, and is the better choice whenever you have the IDs. The supplied runbook omitted this
mechanism entirely.

```
Chunk N-1  ──request_id: abc123──┐
                                 ▼
Chunk N    previous_request_ids: ["abc123"]
           previous_text: "...the last sentence of chunk N-1."
           next_text:     "The first sentence of chunk N+1..."
                                 │
                                 ▼
Chunk N+1  previous_request_ids: ["<chunk N's id>"]
```

**Hard conflict to check:** `enable_logging: false` (zero-retention) **disables request
stitching** `[T]`. You cannot have both zero-retention and `previous_request_ids`. If a job is
zero-retention and long, you fall back to `previous_text`/`next_text` and accept weaker seams —
say so rather than silently emitting a payload that will be rejected or degraded.

---

## 8. Cost, credits & the two-phase protocol

### 8.1 Billing basis `[T]`

Billing is **per character of input text, including spaces and punctuation.** Flash and Turbo
models are **50% lower per character for API generations** `[T]`; ElevenLabs quotes Text-to-Speech
at roughly **$0.05 per 1,000 characters on Flash/Turbo** `[T]`. Standard-tier per-minute figures
from the supplied runbook ($0.12/min standard, $0.06/min discounted) could **not** be confirmed and
are `[T-unverified]`. Quote the per-character basis, not the per-minute one.

### 8.2 The two-phase protocol `[I]`

The economic core of this document. Iterating on a flagship model is the main way to waste credits.

**Phase 1 — Draft / directional exploration.**
- Model `eleven_flash_v2_5` (50% cost, ~75 ms, 40k cap) `[T]`
- **250–500 characters**, containing only the passages where the delivery is actually in question —
  the emotional transitions, the tricky pronunciation, the hook
- `output_format: mp3_22050_32`
- Iterate freely here: pacing, punctuation, phrasing, voice choice

**Phase 2 — Master render.**
- Model `eleven_v3` (tagged/expressive) or `eleven_multilingual_v2` (long-form stable) `[T]`
- Full text, `mp3_44100_192` or `pcm_44100` (tier permitting — §3.2)
- Fixed `seed`, dictionary `version_id` pinned

Worked comparison, 10 iterations × 1,000 characters:

```
Draft on Flash v2.5:  10 × 1,000 × 0.5 =  5,000 billed units
Same 10 on v3:        10 × 1,000 × 1.0 = 10,000 billed units
                                          ─────────────────
Saved:                                     5,000 units (50%)
```

**Two honest caveats on this protocol** `[I]`:
1. Flash v2.5 **cannot render audio tags or phonemes** (§1.2). A Flash draft validates *text,
   pacing, punctuation, and voice fit* — it does **not** validate tag execution. Tag behavior can
   only be checked on v3. Budget one short v3 probe for tag-heavy scripts rather than pretending
   the Flash draft proved something it didn't.
2. Flash handles numbers less naturally than the larger models `[T]` — a normalization problem that
   appears in the draft may be a Flash artifact, not a script defect.

Drafting on a 250–500 character excerpt rather than the full script is where most of the real
saving comes from — the model discount is secondary to not rendering 4,000 characters to hear
whether one line lands `[I]`.

### 8.3 Free regenerations — **website only, not the API** `[T]`

The supplied runbook described a payload-hash-matching free-retry workflow for API calls. That is
wrong on nearly every point. What is actually documented:

- Two free regenerations for Text-to-Speech and Speech-to-Speech `[T]`
- **Available only via the website — explicitly *not* available via the API** `[T]`
- Conditions: the **text, voice, and model** stay the same; the first generation was **less than
  two hours ago**; you have **not refreshed or left the page** `[T]`
- **Voice setting sliders MAY be changed** and you keep the free regeneration `[T]` — the direct
  opposite of the runbook's "adjusting stability by 0.01 invalidates the retry"

**Consequence for any API-based workflow: assume every API call is billed.** There is no free
retry to fall back on. This is precisely why §8.2's draft phase matters. If you want free re-rolls
while tuning sliders on a fixed piece of text, do that tuning **in the web UI**, then port the
settled settings into the API payload.

---

## 9. Compliance & zero retention `[T]`

By default, requests log text and generated audio to history. `enable_logging=false` activates
zero-retention mode: synthesis is processed without writing text or audio artifacts.

Three things to know before you set it:

1. It is **enterprise-only** `[T]`.
2. It **disables history features and request stitching** `[T]` — see the §7 conflict.
3. It is a per-request query parameter, so it must be set on **every** call in a job, not once.

---

## 10. Verification log — 2026-07-26

Every claim group from the supplied enterprise runbook, with outcome.

### Confirmed `[T]`

| Claim | Outcome |
|---|---|
| Model IDs `eleven_v3` / `eleven_multilingual_v2` / `eleven_flash_v2_5` | Confirmed, all current |
| Char caps 5,000 / 10,000 / 40,000 | Confirmed |
| Language counts 70+ / 29 / 32 | Confirmed |
| Flash ~75 ms latency | Confirmed |
| Flash/Turbo 50% lower per-character price | Confirmed |
| `eleven_v3` is the flagship | Confirmed |
| Billing per input character incl. spaces/punctuation | Confirmed |
| `stability` 0–1 default 0.5; `similarity_boost` 0–1 default 0.75; `use_speaker_boost` default true | Confirmed |
| `seed`, `previous_text`, `next_text`, `enable_logging`, `pronunciation_dictionary_locators` all exist as described | Confirmed |
| `enable_logging=false` = zero retention | Confirmed |
| PLS dictionaries, IPA + CMU alphabets, case-sensitive grapheme matching | Confirmed |
| `eleven_multilingual_v2` needs `<alias>`, not `<phoneme>` | Confirmed |
| Audio tags are square-bracketed natural-language delivery instructions | Confirmed |
| IVC ≈1–2 min reference; PVC 30 min–3 hr and Creator+ | Confirmed |

### Corrected — the supplied runbook was **wrong**

| # | Runbook claim | Verified reality |
|---|---|---|
| 1 | v3 `stability` is a float; use 0.30–0.45 | **Three discrete modes: Creative / Natural / Robust.** Docs recommend Creative or Natural for tag expressiveness (§4.1) |
| 2 | Phoneme tags work on `eleven_v3` **and `eleven_flash_v2_5`** | **`eleven_v3` and `eleven_flash_v2`** — *not* Flash v2.5. English-only by default (§6.2) |
| 3 | Two free API regenerations on exact payload-hash match; changing stability by 0.01 invalidates | **Website only, not available via API.** Voice settings **may** change. 2-hour window, no page refresh (§8.3) |
| 4 | Multi-speaker via inline `Speaker A:` labels in a TTS payload | **Separate `/v1/text-to-dialogue/convert` endpoint**, v3-only, JSON array of `{text, voice_id}` turns, ≤2,000 chars total (§5.4) |
| 5 | PVC requests "fall back to IVC" automatically under v3 | PVCs are "not fully optimized for v3"; substitution is an **opt-in `use_pvc_as_ivc` boolean**, default false (§2.1) |
| 6 | `style` range is 0.0–1.0 | **0 and up**, uncapped; default 0; non-zero increases latency (§3.1) |
| 7 | `enable_logging=false` is a general compliance toggle | **Enterprise-only**, and it **disables request stitching** — conflicts with `previous_request_ids` (§7, §9) |
| 8 | `output_format` freely selectable | **Tier-gated**: `mp3_44100_192` needs Creator+; PCM/WAV 44.1 kHz needs Pro+ (§3.2) |

### Omitted by the runbook, added here `[T]`

`previous_request_ids` / `next_request_ids` (stronger stitching, max 3 each) · `apply_text_normalization`
(`auto`/`on`/`off`) · `apply_language_text_normalization` (Japanese only) · `use_pvc_as_ivc` ·
`optimize_streaming_latency` (0–4; level 4 disables the normalizer) · `speed` range 0.7–1.2 ·
API default `model_id` is `eleven_multilingual_v2` · `language_code` unsupported on Multilingual v2 ·
`eleven_flash_v2` (30k chars, English, phoneme-capable) · inline IPA in `/slashes/` on v3 at ~80–90%
consistency · max 3 dictionary locators per request · seed range 0–4,294,967,295 · tag effectiveness
is bounded by the voice's training data.

### Could not verify `[T-unverified]`

Latency envelopes for v3, Multilingual v2, and Turbo v2.5 · per-minute pricing ($0.12 / $0.06) ·
`eleven_turbo_v2_5` full specs (absent from the models overview page) · all specific numeric setting
bands (stability 0.50–0.65 / 0.30–0.45, similarity 0.65–0.75, style 0.30–0.50) · the mechanism
claims in the artifact-diagnosis table (e.g. similarity >0.85 reproducing reference noise) · the
"100 characters" context-stitching heuristic.

### Re-verify first, next time

Model IDs and char caps · pricing and the Flash discount · v3 stability mode names · phoneme-tag
model support · the free-regeneration policy · PVC/v3 optimization status · `output_format` tier
gates · Text-to-Dialogue character ceiling.
