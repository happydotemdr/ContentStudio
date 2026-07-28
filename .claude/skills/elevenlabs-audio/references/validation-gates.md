# Validation gates — fresh-agent dispatch prompts

Three gates. Each dispatches a **fresh `general-purpose` agent** that has **not** seen the authoring
rationale, so it checks the artifact rather than rubber-stamping the reasoning.

**Rules of use:**

- Use the prompts below **as written**. Each already embeds the repo's sub-agent output contract.
- **Gates 1 and 2 are independent — dispatch them in parallel** (one message, two tool calls) once
  both artifacts exist.
- **A gate returning findings blocks emission** until each finding is resolved or the user explicitly
  overrides it.
- **Never report a gate as passed without running it.** Report results verbatim in the spec's
  VALIDATION GATES section.
- Paste the artifact **into the prompt**. The agent must not have to go looking for it, and must not
  be told why any choice was made.

**Why the checklists carry no `[C]`/`[I]`/`[T]` markers.** They are prompt text sent to another
agent, not normative claims addressed to you — a marker inside them would read as noise to the
sub-agent and invite it to weigh rules rather than apply them. **Every factual rule in the three
checklists below is `[T]`, web-verified 2026-07-26**, and traces to
`docs/elevenlabs-production-runbook.md`. If you change a checklist item, verify it there first; an
unverified rule in a gate is worse than no gate, because it manufactures false findings.

---

## Gate 1 — Script & tag validation (after Stage B)

```
You are validating an ElevenLabs directorial script against a fixed compatibility checklist.
You have not seen why any choice was made, and you should not infer intent — check only what
is in front of you. Do not fix anything; report.

TARGET MODEL: <model_id>
STABILITY MODE / VALUE: <value>
VOICE NOTES (known-good/known-bad tags, if any): <notes or "none supplied">

SCRIPT:
---
<the full tagged, chunked script, including per-chunk boundaries>
---

Check each item and report PASS or FINDING with the offending text quoted:

1. MODEL SUPPORTS TAGS. Audio tags ([whispers], [sighs], etc.) are supported ONLY by
   eleven_v3. If the target model is anything else and the script contains bracketed tags,
   that is a FINDING — the tags will be silently dropped, not error.
2. TAG CATALOG. Documented tags are: [laughs] [whispers] [sighs] [sarcastic] [curious]
   [excited] [crying] [snorts] [mischievously] [gunshot] [applause] [swallows] [gulps]
   [explosion] [strong X accent] [sings] [woo], plus commonly documented delivery tags
   [pause] [rushed] [stammers] [drawn out] [shouting] [tired]. Tags outside this set are
   permitted BUT must be explicitly flagged as experimental in the script's annotations.
   An unflagged off-catalog tag is a FINDING.
3. NO CLOSING TAGS. There is no closing-tag syntax. Any [/tag], [end], or similar is a FINDING.
4. ROBUST VS TAGS. On eleven_v3, Robust stability mode is "less responsive to directional
   prompts" and suppresses tags. Robust + a tagged script is a FINDING.
5. VOICE CAPABILITY. If voice notes list known-bad tags, any use of one is a FINDING.
6. NO INLINE SPEAKER LABELS. Multi-speaker requires the separate /v1/text-to-dialogue/convert
   endpoint with a JSON array of {text, voice_id} turns. Inline "Speaker A:" / "Speaker B:"
   labels inside a normal TTS payload are a FINDING.
7. DIALOGUE LENGTH. If this IS a Text-to-Dialogue script, total text across all turns must be
   <= 2,000 characters. Over that is a FINDING.
8. CHUNK CAPS. Per-request caps: eleven_v3 5,000; eleven_multilingual_v2 10,000;
   eleven_flash_v2_5 40,000; eleven_flash_v2 30,000. Any chunk over its cap is a FINDING.
9. CHUNK SPLITS. Chunks must split on sentence boundaries, never mid-sentence. A mid-sentence
   split is a FINDING.
10. INLINE IPA. Text between forward slashes (/ˌkuːbərˈnɛtɪs/) is v3-only. Present on a
    non-v3 model is a FINDING.
11. NORMALIZATION. Raw numbers, currencies, dates, times, phone numbers, URLs, unit
    abbreviations, or keyboard shortcuts that have NOT been spelled out in words are a
    FINDING (these are documented mispronunciation trouble spots).
12. READS ALOUD. Any sentence that is hard to speak in one breath, or reads as written text
    rather than spoken text, is a FINDING.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted, each as "Item N — <quoted offending text> — <one-line why>"
- Recommendation: 1–3 sentences
- Open questions: only if genuinely blocking

DO NOT:
- Paste full file contents or reproduce tool output verbatim
- Restate the task or narrate your process
- Include a preamble, closing summary, or sign-off
```

---

## Gate 2 — Payload validation (after Stage C)

```
You are validating an ElevenLabs API request payload against a fixed checklist. You have not
seen why any value was chosen, and you should not infer intent — check only what is in front
of you. Do not fix anything; report.

DECLARED INTENT (from the control surface):
  phase: <draft|master>   privacy: <standard|zero-retention>   determinism: <on|off>
  language: <code>        use_case: <value>

PAYLOAD (body + query params):
---
<the full JSON body and query string>
---

PRONUNCIATION DICTIONARY (if any):
---
<the PLS XML>
---

Check each item and report PASS or FINDING:

1. MODEL SET EXPLICITLY. model_id must be present. The API default is eleven_multilingual_v2,
   so an absent model_id silently selects the non-flagship model. Absent = FINDING.
2. PARAMETER RANGES. stability 0–1; similarity_boost 0–1; style 0 and up (uncapped);
   speed 0.7–1.2; seed 0–4,294,967,295. Out of range = FINDING.
3. V3 STABILITY. On eleven_v3, stability is three discrete modes (Creative / Natural /
   Robust), not a free float. A raw float on v3 without a stated mode mapping is a FINDING.
4. PHONEME MODEL SUPPORT. PLS <phoneme> tags work ONLY on eleven_v3 and eleven_flash_v2.
   <phoneme> present with any other model_id — including eleven_multilingual_v2 and
   eleven_flash_v2_5 — is a FINDING. (<alias> works on all models.)
5. PHONEME LANGUAGE. Phoneme tags are English-only by default; non-English phonemes require
   eleven_v3. A violation is a FINDING.
6. PLS CASE VARIANTS. PLS grapheme matching is case-sensitive. Any term appearing in only one
   casing, where other casings plausibly occur in the text (acronyms, brand names,
   sentence-initial proper nouns), is a FINDING.
7. LOCATOR LIMIT. Maximum 3 pronunciation_dictionary_locators. More = FINDING.
8. VERSION PINNING. If phase is master, each locator should pin version_id. Unpinned = FINDING.
9. OUTPUT FORMAT VS PHASE. draft should be a low-bitrate format (e.g. mp3_22050_32);
   master should be mp3_44100_192 or pcm_44100/wav_44100. A mismatch is a FINDING.
10. OUTPUT FORMAT TIER GATE. mp3_44100_192 requires Creator tier or above; PCM/WAV at 44.1 kHz
    requires Pro tier or above. If either is used without the gate being flagged in the spec,
    that is a FINDING.
11. LOGGING VS PRIVACY. privacy: zero-retention requires enable_logging=false;
    privacy: standard requires enable_logging true/absent. A mismatch is a FINDING.
12. ZERO-RETENTION VS STITCHING. enable_logging=false DISABLES request stitching. If
    enable_logging is false AND previous_request_ids or next_request_ids are present, that is
    a FINDING (mutually exclusive).
13. SEED VS DETERMINISM. determinism: on requires a seed; determinism: off should omit it.
    A mismatch is a FINDING.
14. STITCHING COVERAGE. If the job is chunked, every chunk after the first must carry
    previous_text and/or previous_request_ids. Any bare seam is a FINDING.
15. LANGUAGE_CODE SUPPORT. language_code is NOT supported on eleven_multilingual_v2. Present
    with that model = FINDING.
16. LATENCY SIDE EFFECTS. optimize_streaming_latency=4 disables the text normalizer. If it is
    set to 4 and the text still contains raw numbers/dates/URLs, that is a FINDING.
17. TAGS VS MODEL. If the payload text contains bracketed audio tags and model_id is not
    eleven_v3, that is a FINDING.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted, each as "Item N — <the offending field and value> — <one-line why>"
- Recommendation: 1–3 sentences
- Open questions: only if genuinely blocking

DO NOT:
- Paste full file contents or reproduce tool output verbatim
- Restate the task or narrate your process
- Include a preamble, closing summary, or sign-off
```

---

## Gate 3 — Pre-master spend gate (before any master payload)

Fires **only** when a master render is about to be emitted. This is a spend authorization, not a
correctness check.

```
You are authorizing a paid ElevenLabs master render. You have not seen the authoring
rationale. Refuse to authorize unless every condition below is demonstrably met by the
evidence supplied. Do not fix anything; report.

EVIDENCE:
  Draft payload emitted:      <yes/no — include it>
  User confirmed the draft:   <yes/no — quote the confirmation>
  Draft text:                 <text>
  Master text:                <text>
  Master model / format:      <values>
  Cost estimate stated:       <the arithmetic as shown to the user>
  Re-roll budget stated:      <value or "none">
  Tag-heavy script?           <yes/no>
  v3 tag probe run?           <yes/no>

Check each and report AUTHORIZED or BLOCKED with the reason:

1. A draft payload was emitted on eleven_flash_v2_5 before this master.
2. The user explicitly confirmed the draft direction. Silence is not confirmation.
3. The master text is the confirmed draft text (tags restored, full length) — not a
   substantively rewritten script that was never drafted.
4. A cost estimate was shown to the user, with its arithmetic, on the per-input-character
   basis (including spaces and punctuation).
5. A re-roll budget is named. If the master uses eleven_v3 Creative mode, a re-roll budget is
   MANDATORY — Creative is documented as "prone to hallucinations."
6. If the script is tag-heavy, a short v3 tag probe was run. A Flash draft does NOT validate
   tag execution — Flash v2.5 renders no tags at all. Relying on a Flash draft to prove tags
   work is grounds to BLOCK.
7. The spec does NOT rely on API free regenerations. Two free regenerations exist on the
   WEBSITE ONLY and are explicitly unavailable via the API. Any claim of free API retries is
   grounds to BLOCK.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted, each as "Item N — <what is missing> — <one-line why it blocks>"
- Recommendation: AUTHORIZED or BLOCKED, plus 1–3 sentences
- Open questions: only if genuinely blocking

DO NOT:
- Paste full file contents or reproduce tool output verbatim
- Restate the task or narrate your process
- Include a preamble, closing summary, or sign-off
```

---

## Reporting gate results

```
VALIDATION GATES
  Gate 1 (script & tag): PASS
  Gate 2 (payload):      2 FINDINGS — resolved:
                         · Item 4: <phoneme> with eleven_multilingual_v2 → converted to <alias>
                         · Item 6: "SQL" single-casing → added "sql", "Sql"
  Gate 3 (spend):        AUTHORIZED
```

If the user overrides a finding, record it as an override with their reason — not as a pass `[I]`.
