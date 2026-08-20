# Worked example — one job end to end

> This example illustrates rules already marked in this skill's other reference files and carries no independent normative weight. Where a line here restates a rule, the marker lives
> on the rule, not on the illustration — do not copy an unmarked line out of this file into a
> real brief as if it were sourced `[I]`.

A standalone (non-Shorts) job, run through all four stages and all three gates. Read this to see how
the pieces connect; do not copy the values — they are specific to this job.

---

## The request

> "I've got a 6-minute product explainer for our dev tool. Needs to sound like a confident senior
> engineer, not a corporate narrator. It says Kubernetes, nginx, and SQL a lot. Make it not
> mispronounce them. I don't want to burn my whole credit balance getting it right."

## Stage 0 — control surface

Three values were given, five inferred. **Say which is which.**

```
phase:          draft        (assumed — nothing has been rendered yet)
use_case:       ad-promo     (inferred — short-form persuasive explainer, performance matters)
expressiveness: 3            (assumed default — "confident, not corporate" reads as mid-dial)
voice:          explore      (assumed — none supplied)
language:       en           (assumed)
length:         ~5,400 chars (counted: 6 min at ~150 wpm)
privacy:        standard     (assumed)
determinism:    off          (draft)
```

Routing that falls out (`control-surface.md`):

- `ad-promo` + `master` → **`eleven_v3`** — the delivery is performative and will want tags
- 5,400 chars **exceeds v3's 5,000 cap** → **2 chunks**, split on a section break, stitched
- `expressiveness: 3` on v3 → **Natural** mode, `style` 0.30
- English + v3 → **phoneme tags available** — which decides the pronunciation approach

**Note the interaction that only shows up when you run the mappings together:** the jargon
requirement ("don't mispronounce Kubernetes") and the model choice are coupled. On v3 phonemes are
available; had this routed to `eleven_multilingual_v2` for length, they would not be `[T]`.

## Stage A — voice profile

`voice: explore`. Performance requirement stated first: *must carry conviction without shouting;
must handle technical terms without sounding like it's reading a list.*

Auditioned 3 candidates on **`eleven_flash_v2_5`, 380 characters** — the hardest paragraph, not the
intro. Cost: ~570 billed units total for all three, versus ~5,400 per candidate had they been
auditioned full-length on v3.

Flash renders no tags `[T]`, so this tested timbre, pace, and character only. One 300-character v3
probe followed to confirm `[confident]` and `[sighs]` actually land on the winner.

```
=== VOICE PROFILE CARD ===
Name:            Explainer-Senior-Eng
voice_id:        pNInz6obpgDQGcFmaJgB
Source:          library
Persona:         Mid-30s, dry, unhurried. Warm low-mid register. Convincing when
                 understated; thins out when pushed loud.
Locked settings:
  Model:            eleven_v3
  Stability:        Natural
  similarity_boost: 0.75
  style:            0.30
  speed:            1.0
  use_speaker_boost:true
Known-good tags:   [confident] [sighs] [curious]
Known-bad tags:    [shouts] — voice thins out; do not use
Dictionaries:      pending (Stage C)
Caveats:           none
Verified on:       2026-07-26
```

The **known-bad** line is the reusable asset here — it's a fact about this voice that no
documentation could have supplied `[T]`, and it directly constrains Stage B.

## Stage B — directorial script

Excerpt (chunk 1 of 2), layer 1 built first, tags added after:

```
[confident] Most teams don't have a /ˌkuːbərˈnɛtɪs/ problem — they have a
visibility problem.

You ship a change. Something slows down. And then you spend the next forty
minutes in three dashboards trying to work out where.

[sighs] We've all done it.

[curious] So what if the trace just... told you?
```

Decisions worth noting:

- The em-dash and the ellipsis do the pacing work. **Strip every tag and the rhythm still reads** —
  that's the layer-1-first rule `[I]`, and it's what makes the Flash draft meaningful.
- `[shouts]` was wanted for "Something slows down" and **rejected** — the profile card lists it as
  known-bad for this voice `[T]`. Replaced with a sentence break, which is free and works on every
  model.
- Inline IPA for Kubernetes only. `nginx` and `SQL` go in a dictionary instead — they recur too often
  for an 80–90%-consistency mechanism `[T]`.
- Chunk 1 ends on a section break, not at character 5,000.

**→ Gate 1 dispatched** (in parallel with Gate 2 once Stage C completed).

## Stage C — config, payload & dictionary

Dictionary — note the casing enumeration and the alias/phoneme split:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0"
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    alphabet="ipa" xml:lang="en-US">
  <lexeme><grapheme>nginx</grapheme><alias>engine ex</alias></lexeme>
  <lexeme><grapheme>NGINX</grapheme><alias>engine ex</alias></lexeme>
  <lexeme><grapheme>Nginx</grapheme><alias>engine ex</alias></lexeme>
  <lexeme><grapheme>SQL</grapheme><alias>Sequel</alias></lexeme>
  <lexeme><grapheme>sql</grapheme><alias>Sequel</alias></lexeme>
</lexicon>
```

Aliases were chosen over phonemes even though v3 supports both — "engine ex" is readable,
reviewable, and survives a routing change `[I]`.

Master payload, chunk 2 (showing the stitching):

```json
{
  "text": "[confident] That's the whole idea behind the tool...",
  "model_id": "eleven_v3",
  "voice_settings": {
    "stability": "natural",
    "similarity_boost": 0.75,
    "style": 0.3,
    "speed": 1.0,
    "use_speaker_boost": true
  },
  "seed": 8814,
  "previous_request_ids": ["<chunk 1 request_id>"],
  "previous_text": "So what if the trace just... told you?",
  "pronunciation_dictionary_locators": [
    { "pronunciation_dictionary_id": "DICT_ID", "version_id": "VERSION_ID" }
  ],
  "apply_text_normalization": "auto"
}
```

Query: `?output_format=mp3_44100_192&enable_logging=true`

`privacy: standard` → `enable_logging: true` → **request stitching is available**, so
`previous_request_ids` is used rather than text context alone `[T]`. Had this been zero-retention,
that line would be illegal and the spec would have to say so `[T]`.

**→ Gate 2 dispatched in parallel with Gate 1.**

## Gates 1 & 2 — results

```
Gate 1 (script & tag): 1 FINDING — resolved
  · Item 11: "forty minutes" was originally "40 minutes" — raw numeral in a documented
    normalization trouble spot. Spelled out.

Gate 2 (payload): 2 FINDINGS — resolved
  · Item 6: "SQL" appeared in one casing only; the script also contains "sql" in a code
    reference. Added the lowercase lexeme.
  · Item 10: mp3_44100_192 requires Creator tier and the gate was not flagged in the spec.
    Added the flag; offered mp3_44100_128 as the ungated fallback.
```

Neither finding was something the authoring pass would have caught by re-reading its own reasoning —
which is the argument for a fresh agent that hasn't seen it `[I]`.

## Stage D — cost, draft, then master

```
COST
  Draft:  380 chars × 3 candidates × Flash rate (50%)   ≈ 570 billed units
  v3 tag probe: 300 chars × standard rate               ≈ 300 billed units
  Master: 5,400 chars × standard rate                   ≈ 5,400 billed units
  Basis:  per input character, incl. spaces & punctuation [T]
  Note:   API calls are billed — no free regenerations via API [T]
  Re-roll budget: 1 chunk re-roll (Natural mode, low hallucination risk)

  For comparison: 10 iterations on the full script at v3 = ~54,000 units.
  Draft-first cost here: ~6,270 units.
```

Draft emitted → user confirmed → **Gate 3**:

```
Gate 3 (spend): AUTHORIZED
  1. Flash draft emitted ✓   2. User confirmed ✓   3. Master text = confirmed draft ✓
  4. Cost arithmetic shown ✓  5. Re-roll budget named ✓
  6. Tag-heavy → v3 probe was run ✓  (a Flash draft alone would have BLOCKED here)
  7. No reliance on API free regenerations ✓
```

Item 6 is the one that most often blocks a real job. The Flash draft sounded great — and proved
nothing about whether `[confident]` and `[sighs]` would land, because Flash renders neither `[T]`.

## What this example demonstrates

1. **The control surface does the routing.** Eight values determined the model, the caps, the
   chunking, and — indirectly — whether phonemes were even available.
2. **Voice choice constrains the script.** `[shouts]` was cut because of an observed voice limit, not
   a rule in any document.
3. **Layer 1 first** made the Flash draft meaningful — the rhythm survives without tags.
4. **The gates caught two real defects** that a self-review would have missed: a raw numeral and a
   missing case variant.
5. **The draft phase saved ~48,000 units** — mostly by drafting an excerpt, not by the model discount.
6. **The v3 probe was not optional.** Gate 3 exists specifically to stop a tag-heavy script from
   riding a Flash draft's false confidence into a paid master render.
