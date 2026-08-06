# Eleven Music Runbook — endpoints, composition plans, prompt craft & credit discipline

> **Source & scope.** This document is **not corpus-derived.** It was assembled from a supplied
> design brief and then verified claim-by-claim against live ElevenLabs documentation on
> **2026-08-06**. The 420-video ContentStudio corpus contains **zero findings on AI music
> generation** — for the corpus view of what a music bed must *do* (duck depth, tonal match,
> arc), see `.claude/skills/voiceover-brief/references/production-and-loudness.md` and
> `.claude/skills/music-brief/references/bed-arc.md`. The two bodies of knowledge are
> complementary and deliberately separate: those tell you what the bed must accomplish; this
> tells you what the platform actually supports.
>
> **The supplied design brief was wrong in two places and over-cautious in two more.** See §7.
> Do not treat the original brief text as authoritative anywhere it conflicts with this document.

## Provenance markers

This document uses the repo's standard key (`docs/README.md`), with one qualifier added for
material that could not be confirmed:

- **`[T]`** — Tool/policy fact **web-verified against live ElevenLabs docs 2026-08-06**. These go
  stale fast; re-verify before relying on them.
- **`[T-unverified]`** — Asserted by a supplied source and **not confirmed** against live docs.
  Treat as a starting hypothesis, never as a fact. Say so out loud when you use one.
- **`[I]`** — Industry/general practice, not specific to ElevenLabs.
- **`[C]`** — Corpus-cited `(Channel, video_id)`. **Absent here by construction** — the corpus has
  no AI-music-generation findings at all.

A normative line in this document with no marker is a bug.

---

## §1 Endpoints & models

`POST /v1/music` — `prompt` **XOR** `composition_plan`; the two are mutually exclusive `[T]`.
`model_id` enum `music_v1` | `music_v2`, **default `music_v1`** `[T]` — so **set it explicitly** if
you want `music_v2` `[I]`. `music_length_ms` **3,000–600,000 ms, prompt-only** `[T]`.
`force_instrumental` default `false`, **prompt-only**, and when `true` the docs state it
"guarantees that the generated song will be instrumental" `[T]`. `seed` **plan-only** — the
GitHub skill reference states it "cannot be used with `prompt`" `[T]`. `respect_sections_durations`
default `true`, **and this only meaningfully governs `music_v1` plans** — confirmed today: for
`music_v2`, chunk (section) durations "are always enforced" regardless of this flag `[T]`. Also
`finetune_id`, `store_for_inpainting` (default `false`), `sign_with_c2pa` (default `false`,
applicable to mp3 files only) — schema fields, no marker needed. Query param `output_format`,
default `auto`.

`POST /v1/music/detailed` — same body plus `with_timestamps`; multipart response carrying the
resolved plan and `song_metadata`. Confirmed today via the GitHub skill reference, the fuller
endpoint set is: `compose` (this endpoint), `stream` (audio chunks during generation, **paid
plans only**), `compose_detailed`, `compose_detailed_stream` (Server-Sent Events), `upload`
(import audio for inpainting, **enterprise only**), and `video_to_music` (generate a bed from a
video clip) `[T]`.

Plan creation is exposed in the SDK as
`music.composition_plan.create(prompt=…, music_length_ms=…, model_id=…)` `[T]` — confirmed today
directly against the cookbook page, which documents only the SDK call and shows **no REST path**.
**The REST path was not confirmed — the design brief's `/v1/music/plan` remains `[T-unverified]`.**
Also confirmed today, and new to this verification pass: the cookbook page states **"The Eleven
Music API is only available to paid users"** `[T]` — a plan-level gate, not a per-call price (see
§5).

---

## §2 Composition plan shapes — two, and they are model-specific

This is the most consequential fact in the document.

- `music_v2` → `CompositionPlan`: `chunks[]`, **≤30 chunks, total 3s–10min** `[T]`. Each generation
  chunk: `text` (section label, lyrics, phonetic sounds, inline directions), `duration_ms`
  **3,000–120,000** `[T]`, `positive_styles` (≤50; docs recommend "at least 6-7 styles in early
  chunks" `[T]`), `negative_styles` (≤50, optional) `[T]`, `context_adherence` ∈
  `low`|`medium`|`high`, **default `high`** `[T]` — how strictly the chunk mirrors surrounding
  sections. The how-to guide states, confirmed today verbatim: "Chunk-based composition plans
  require the music_v2 model. Pass model_id='music_v2' when composing." `[T]`
- **Confirmed today, not in the original brief:** `chunks[]` can also contain `AudioRefChunk`
  objects (`song_id` + a `{start_ms, end_ms}` range) for referencing previously stored audio, and a
  generation chunk may itself carry an optional `conditioning_ref` (an `AudioRefChunk`) plus
  `condition_strength` ∈ `low`|`medium`|`high`|`xhigh` to match an existing recording's aesthetic
  `[T]`. **This means `chunks[]` supports from-scratch generation and inpainting-style referencing
  in the same array** — it is not an either/or split, and it is emphatically not inpainting-only.
- `music_v1` → `MusicPrompt`: `positive_global_styles[]`, `negative_global_styles[]`, `sections[]`
  of `{section_name` (1–100 chars)`, duration_ms` (3,000–120,000)`, lines[]` (≤30 lines,
  ≤200 chars each)`, positive_local_styles[], negative_local_styles[], source_from}` `[T]`.
- **Both** shapes bound `duration_ms` to 3,000–120,000 ms `[T]` — confirmed today for both the
  `v1` section schema and the `v2` chunk schema. This is the bound that makes beat-locking work
  and the one Gate 1 enforces.
- **Correction to the design brief:** the brief mistook the chunk shape for an inpainting-only
  object. It is the general-purpose `music_v2` composition plan, capable of pure from-scratch
  generation, pure inpainting/referencing, or a mix of both within one plan (see §7) `[T]`.

---

## §3 Instrumental control

`force_instrumental` is prompt-only and does **not** apply to composition plans `[T]`.
**The documented plan-mode technique is `negative_styles` carrying vocal terms** — confirmed
today, the how-to guide's own chunk examples use `"negative_styles": ["vocals", "lyrics", "pop",
"electronic", "bright"]` on one chunk and `"negative_styles": ["vocals"]` on another to keep those
sections instrumental `[T]`. (Note this is a slightly longer example list than a shorter
three-term version quoted elsewhere — record what was actually seen today, above.) `music_v2`
chunks have **no `lines` field** — confirmed today; the field is `text` `[T]`. For `music_v1`, an
empty `lines: []` is **not documented as an instrumental guarantee** — record it as
`[T-unverified]` and do not rely on it alone. **Every plan this skill emits carries the vocal
guard on every chunk**, regardless of shape `[I]`. Whether the guard is *sufficient* in practice —
whether `negative_styles` vocal terms actually suppress vocals in the rendered audio — is
`[T-unverified]` pending a live generation (§7): **that check could not be run in this
environment.**

---

## §4 Prompt craft & the copyright guard

Naming a band, musician, or copyrighted lyrics returns a `bad_prompt` error. Confirmed today via
the GitHub skills reference, which independently lists `bad_prompt` for copyrighted artist/band
references and a **separate `bad_composition_plan` error for copyrighted styles inside a plan**
`[T]` — the latter is new to this verification pass and not in the original design brief. The
error is documented (per the 2026-08-06 design-brief verification pass) as carrying
`detail.data.prompt_suggestion` — a clean rewritten prompt to retry with; **the exact field path
was not independently re-observed in today's five fetches**, so treat the field name itself as
`[T-unverified]` pending direct reproduction, while the existence of the `bad_prompt` /
`bad_composition_plan` error-and-retry mechanism is `[T]`.

Document the **recovery path**, not just the warning: catch the error, read the suggestion, diff
it against the original prompt to learn which token tripped the guard, retry with the suggestion
`[I]` — this is a craft/process recommendation, not a documented vendor procedure.

`positive_styles`/`negative_styles` are English-only and capped at **50 items each** `[T]` —
confirmed today on both the compose-endpoint parameter table and the composition-plans how-to
guide.

---

## §5 Cost & iteration

**`[T-unverified]` throughout — say so up front.** Credit cost per generation was **not** found in
any of today's five fetched pages. Whether `composition_plan.create` itself is billed was **not**
confirmed; the design brief's "costs no credits" claim remains a hypothesis. **New fact confirmed
today:** the cookbook page states plainly that "the Eleven Music API is only available to paid
users" `[T]` — this is a plan-tier gate, not evidence about per-call pricing, and does not resolve
whether plan creation specifically is free. **Assume every compose call is billed until proven
otherwise** `[I]`. Seed: confirmed today, "providing the same seed with the same parameters can
help achieve **more consistent** results" `[T]` — **never present seed as determinism**; treat any
stronger reproducibility claim (e.g. that results are unaffected by system updates) as carried
from the original 2026-08-06 pass rather than independently re-quoted today (see §7).

---

## §6 Rights & commercial use

The docs say Eleven Music is "cleared for nearly all commercial uses, from film and television to
podcasts and social media videos, and from advertisements to gaming" — confirmed today verbatim
against the live capabilities page, which also directs users to `elevenlabs.io/music-terms` for
per-plan detail `[T]`. **Per-tier terms and ownership were not read** — the `music-terms` page
itself was not one of the five pages fetched, so this remains `[T-unverified]`. State plainly:
this is *not* sufficient to retire `shorts-assembly`'s rights checkpoint. The argument that a
generated bed sidesteps the Creator-Music revenue-share problem is `[I]` — a genuinely new
inference the corpus does not make — and it is **contingent on terms nobody has read yet.**

---

## §7 Verification log — 2026-08-06

### Confirmed `[T]`

| Claim | Outcome |
|---|---|
| Parameter surface: `prompt` XOR `composition_plan`; `model_id` default `music_v1`; `music_length_ms` 3,000–600,000 ms prompt-only; `force_instrumental` default `false` prompt-only; `seed` plan-only | Confirmed today via direct fetch of the compose parameter table |
| Both plan shapes (`MusicPrompt` for `music_v1`, `CompositionPlan` for `music_v2`) | Confirmed today, including the previously-undocumented `AudioRefChunk`/`conditioning_ref` mixing inside `chunks[]` |
| 3,000–120,000 ms bound on `duration_ms` in both shapes | Confirmed today |
| ≤30 chunks / 3s–10min total plan bound | Confirmed today via the composition-plans how-to guide |
| `force_instrumental` prompt-only, guarantees instrumental | Confirmed today (compose table + GitHub skill reference) |
| `seed` plan-only | Confirmed today (GitHub skill reference: "cannot be used with `prompt`") |
| `context_adherence` default `high` | Confirmed today (compose table + composition-plans guide) |
| `music_v2` requirement for chunk-based plans | Confirmed today, verbatim: "Chunk-based composition plans require the music_v2 model." |
| Commercial-use sentence and `music-terms` pointer | Confirmed today verbatim against the live capabilities page |
| `respect_sections_durations` nuance: default `true`, but for `music_v2` chunk durations are always enforced regardless | Confirmed today — new detail beyond the original design brief |
| Eleven Music API is paid-users-only | Confirmed today via the cookbook page — new fact, not in the original design brief |
| `bad_composition_plan` error (copyrighted styles in a plan) | Confirmed today via the GitHub skill reference — new fact, not in the original design brief |

### Corrected — the supplied design brief was wrong

1. **Chunks are the `music_v2` composition plan, not an inpainting-only shape.** Confirmed
   today, with the added nuance that `chunks[]` can mix ordinary generation chunks with
   `AudioRefChunk` inpainting/reference chunks in the same plan — it does both, not one or the
   other.
2. **Plan-mode instrumental is `negative_styles`, not `lines: []`**, and `music_v2` has no
   `lines` field at all. Confirmed today via the composition-plans how-to guide's own chunk
   examples.
3. **Seed is a consistency aid, not determinism** — the brief's "instrumental vs. determinism
   conflict" is largely dissolved. Confirmed today in shorter form ("more consistent results");
   the fuller non-determinism disclaimer (behavior may shift across system updates) was part of
   the original 2026-08-06 pass and was not independently re-quoted verbatim from today's five
   fetches, but nothing contradicts it.
4. **The 3,000–120,000 ms ceiling was marked unverified but is on the schema page for both
   shapes** — confirmed today for both `v1` sections and `v2` chunks.

### Could not verify `[T-unverified]`

- Credit cost per generation — not present on any of today's five fetched pages.
- Whether plan creation (`composition_plan.create`) specifically is free — not confirmed; the
  adjacent fact that the API overall is paid-users-only does not resolve this.
- The REST path for plan creation — confirmed today that the cookbook page documents only the
  SDK call and shows no REST path; the design brief's `/v1/music/plan` stays unconfirmed.
- The 4,100-character prompt cap.
- Per-tier rate limits.
- Ownership and per-tier commercial terms — the `music-terms` page was not one of the five URLs
  fetched and remains unread.
- The exact `detail.data.prompt_suggestion` field path on the `bad_prompt` error — the error's
  existence and trigger conditions were cross-confirmed today via the GitHub skill reference, but
  the specific response field path was not independently re-observed in today's fetches.
- **Whether the vocal guard (`negative_styles` carrying vocal terms) actually suppresses vocals
  in rendered audio.** This required a live `POST /v1/music` call, which **could not be run in
  this environment: there is no `ELEVENLABS_API_KEY` in the environment** (confirmed via
  `env | grep -i eleven`, which matched only the worktree path, not a key). No claim about the
  vocal guard's real-world efficacy should be treated as verified.

### Re-verify first, next time

Model IDs and whether a `music_v3` has shipped; pricing and credit rates; the plan-creation
endpoint's path and cost; the `music-terms` page; the chunk cap and duration bounds; whether
`music_v1`'s `sections[]` shape is still supported.

### Sourcing caveat

The originating design-brief spec reported `elevenlabs.io` returning **HTTP 403** to plain
fetches and fell back to a Context7 mirror for two facts. **Today's direct `WebFetch` calls to
all five URLs succeeded — no 403 was encountered on any of them.** This is a stronger source than
the mirror the original spec relied on for two of its facts, and today's direct reads corroborate
rather than contradict those two corrected facts (§2's chunk shape and §3's instrumental
technique). A mirror is a weaker source than a direct read; that the mirrored round produced two
wrong facts and today's direct round did not is recorded here rather than smoothed over.
