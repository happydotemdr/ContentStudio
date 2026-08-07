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
checklists below is `[T]`, web-verified 2026-08-06**, and traces to
`docs/elevenlabs-music-runbook.md`. If you change a checklist item, verify it there first; an
unverified rule in a gate is worse than no gate, because it manufactures false findings.

---

## Gate 1 — Section map validation (after Stage B)

```
You are validating an Eleven Music section map against a fixed checklist. You have not seen
why any choice was made, and you should not infer intent — check only what is in front of
you. Do not fix anything; report.

TARGET MODEL: <music_v1 | music_v2>
PLAN SHAPE: <sections | chunks>
DECLARED AUDIO-EMITTING RUNTIME (seconds): <value — script end minus fade-in start; excludes
  any hold-out>
HOLD-OUT (seconds, or "none"): <value>
VOICEOVER BRIEF TONE PER BEAT: <the tone call, beat by beat, or "none supplied">
BED ARC TONE-CONTRADICTION CHECK: <the Bed Arc's own declared MISMATCH rows with their stated
  rationale, beat by beat, or "none declared">

SECTION MAP:
---
<the full section/chunk table including every duration_ms and every style array>
---

Check each item and report PASS or FINDING with the offending value quoted:

1. DURATION SUM. The duration_ms values must sum to exactly the declared audio-emitting
   runtime (in milliseconds) — the span the plan actually covers, script end minus fade-in
   start. This total excludes any declared hold-out. Show your arithmetic. Any mismatch is a
   FINDING.
2. PER-CHUNK BOUNDS. Every duration_ms must be between 3,000 and 120,000 inclusive. Any
   value outside that range is a FINDING.
3. PLAN SIZE. A composition plan supports at most 30 chunks/sections, with a total duration
   between 3 seconds and 10 minutes. Exceeding either is a FINDING.
4. VOCAL GUARD. Every chunk/section must carry vocal-exclusion terms (e.g. "vocals",
   "singing", "spoken word", "lyrics") in its negative styles array. Any chunk missing the
   guard is a FINDING.
5. NO LYRIC CONTENT. For a chunk plan, each chunk's `text` must be a structural label or
   instrumental direction, never singable lyrics. For a sections plan, every `lines` array
   must be empty. Lyric content in an instrumental brief is a FINDING.
6. NO NAMED ARTISTS. No artist, band, musician, album, or track name may appear in any style
   string, in any `text`, or in the prompt body. Naming one triggers a bad_prompt error.
   Any occurrence is a FINDING.
7. STYLE ARRAY CAPS. positive and negative style arrays are capped at 50 items each and are
   English-only. Exceeding either is a FINDING.
8. TONE CONTRADICTION. Compare each section's intended feeling against the voiceover brief's
   tone for the same beat. Any section whose feeling contradicts the spoken tone at that beat
   is a FINDING — UNLESS the supplied Bed Arc's own tone-contradiction check already declares
   that beat a MISMATCH with a stated rationale, in which case it is a declared, upstream-owned
   call and is not a FINDING. An undeclared contradiction — one the Bed Arc's tone-contradiction
   check is silent on — is still a FINDING.
9. COVERAGE. The declared hold-out plus the declared audio-emitting runtime must together
   account for every beat of the full script — each beat is covered by either a chunk or the
   stated hold-out, with no beat falling in neither. An unexplained gap is a FINDING.
10. MODEL/SHAPE MATCH. A chunks[] plan requires model_id music_v2. A sections[] plan is the
    music_v1 shape. A mismatch between the declared model and the plan shape is a FINDING.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted, each as "Item N — <quoted offending value> — <one-line why>"
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
You are validating an Eleven Music API request payload against a fixed checklist. You have not
seen why any value was chosen, and you should not infer intent — check only what is in front of
you. Do not fix anything; report.

DECLARED INTENT (from the control surface):
  phase: <draft|master>        plan_shape: <chunks|sections>      model_id: <value>
  use_case: <value>

PAYLOAD (body + query params):
---
<the full JSON body and query string>
---

SECTION MAP GATE 1 VALIDATED (for the identity check in item 9):
---
<the same section/chunk table pasted into Gate 1>
---

Check each item and report PASS or FINDING with the offending field and value quoted:

1. MODEL EXPLICIT. model_id must be present in the body. The API default is music_v1, so an
   absent model_id silently selects it instead of the model the plan actually requires. Absent
   is a FINDING.
2. MODE EXCLUSIVITY. prompt and composition_plan must never both appear in the same body — they
   are mutually exclusive. Both present is a FINDING.
3. SEED VS PROMPT. seed is plan-only. Any seed present alongside a prompt body is a FINDING.
4. FORCE_INSTRUMENTAL VS PLAN. force_instrumental is prompt-only and has no effect on a
   composition plan. Present alongside a composition_plan is a FINDING.
5. MUSIC_LENGTH_MS VS PLAN. music_length_ms is prompt-only; a composition plan's length comes
   from its chunks, not this field. Present alongside a composition_plan is a FINDING.
6. MUSIC_LENGTH_MS RANGE. When music_length_ms is present (prompt mode only), it must fall
   between 3,000 and 600,000 ms inclusive. A value outside that range is a FINDING.
7. OUTPUT_FORMAT VS PHASE. output_format must be a concrete value appropriate to the declared
   phase (draft: fast/low-fidelity; master: full-fidelity), never left as an unexamined default
   on a master render. A mismatch is a FINDING.
8. CONTEXT_ADHERENCE ENUM. Every chunk's or section's context_adherence, if present, must be
   one of low, medium, or high. Any other value is a FINDING.
9. PLAN IDENTITY. The composition_plan (or sections) embedded in this payload must be
   byte-identical to the section map Gate 1 validated — same chunk count, same duration_ms
   values, same style arrays, same order. Any divergence is a FINDING.
10. STYLE ARRAY CAPS. Every chunk's or section's positive_styles / positive_local_styles and
    negative_styles / negative_local_styles arrays, as they appear in this payload, must be
    capped at 50 items each and English-only. Exceeding either cap, or any non-English token,
    is a FINDING.
11. MODEL/SHAPE MATCH (PAYLOAD). The model_id actually present in this payload must match the
    plan shape actually present in this same payload: a body containing chunks[] must declare
    model_id music_v2; a body containing sections[] must declare music_v1 (or omit model_id,
    which silently defaults to music_v1 — see item 1). Check the payload itself, not the
    section map Gate 1 saw — the payload is a separate artifact and can drift from the map it
    was built from. Any mismatch between the payload's declared model_id and its own plan
    shape is a FINDING.

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
You are authorizing a paid Eleven Music master render. You have not seen the authoring
rationale. Refuse to authorize unless every condition below is demonstrably met by the
evidence supplied. Do not fix anything; report.

EVIDENCE:
  Draft plan emitted:                          <yes/no — include it>
  User confirmed the draft:                    <yes/no — quote the confirmation>
  Draft plan:                                  <the plan JSON>
  Master plan:                                 <the plan JSON>
  Cost estimate stated:                        <the estimate as shown to the user>
  Cost estimate's [T-unverified] status named: <yes/no — quote how it was framed>
  Re-roll budget stated:                       <value or "none">
  Seed reproducibility language:                <quote any claim made about seed, or "none made">

Check each and report AUTHORIZED or BLOCKED with the reason:

1. A draft was emitted and the user explicitly confirmed it. Silence is not confirmation — an
   unanswered or unacknowledged draft is grounds to BLOCK.
2. The master plan is the confirmed draft plan — same chunk structure, same styles, same
   arithmetic — not a rewrite introduced only at master time that was never drafted. A
   substantive rewrite is grounds to BLOCK.
3. A cost estimate was shown to the user with its unverified status stated alongside it.
   Presenting the credit rate as a firm, verified number — with no unverified caveat named — is
   grounds to BLOCK.
4. A re-roll budget is named — how many re-rolls the user is willing to pay for before accepting
   the result. An unstated budget is grounds to BLOCK.
5. The spec does not claim, anywhere, that a seed guarantees reproducibility. The vendor
   disclaims this explicitly: the same seed and parameters can help achieve more consistent
   results, but exact reproducibility is not guaranteed and output may change across system
   updates. Any claim that a seed guarantees or reproduces an exact prior result is grounds to
   BLOCK.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted, each as "Item N — <what is missing or wrong> — <one-line why it blocks>"
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
  Gate 1 (section map):  PASS
  Gate 2 (payload):      2 FINDINGS — resolved:
                         · Item 4: force_instrumental present with a composition_plan → removed
                         · Item 1: model_id absent → set explicitly to music_v2
  Gate 3 (spend):        AUTHORIZED
```

If the user overrides a finding, record it as an override with their reason — not as a pass `[I]`.
