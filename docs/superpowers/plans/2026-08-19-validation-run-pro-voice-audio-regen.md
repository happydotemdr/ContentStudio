# Real-World Validation Run — Regenerate Audio Assets for `stop-over-specialization-in-youth-sports-20260811-004711`

**Status:** DRAFT — awaiting sign-off on the decisions in §2 before any `elevenlabs_tooling send` call runs.
**Costs real money. Runs once.** Every design choice below exists to make that true.

---

## 0. What this validates and what it doesn't

This is the first real-money exercise of `elevenlabs-tooling` (PR #55, branch `claude/elevenlabs-tooling`)
against a real, already-produced Short. The goal is to prove the mechanism end-to-end:

- `voiceover-brief` → `elevenlabs-audio` payload construction → `elevenlabs_tooling send` → a usable
  narration track, using the **new pinned PVC voice** (`eDwT8Vhp2yxJzAMmuuPA`), not the retired IVC
  (`5kVvcrJnhhULT5LdbshJ`) the current assets were built with.
- `music-brief` → `elevenlabs-music` payload construction → `elevenlabs_tooling send` → two music beds
  that match this Short's arc.

**Out of scope for this run** (see §8): re-cutting `render-spec.json`'s shot timings, regenerating
captions/overlays, or producing a new final video. Swapping the narrator voice will almost certainly
change every VO clip's duration (see §1.3) — reconciling that against the visual edit is a separate,
free, non-API-spending follow-up this plan sets up but does not execute.

---

## 1. Ground truth (verified against the actual files, not against stale docs)

### 1.1 The voice pin changed, and only on this unmerged branch

`channel-voice.md` currently disagrees between branches:

| Branch | `voice_id` | Type |
|---|---|---|
| `main` (where the render's source docs live) | `5kVvcrJnhhULT5LdbshJ` | IVC — retired |
| `claude/elevenlabs-tooling` (where `elevenlabs-tooling` and the new pin live) | `eDwT8Vhp2yxJzAMmuuPA` | **PVC — current** |

`eDwT8Vhp2yxJzAMmuuPA` is "our new pro voice ID" — a Professional Voice Clone, retiring the old IVC
2026-08-18. This is also the exact value `elevenlabs_tooling.validate.PINNED_NARRATOR_VOICE_ID` checks
against for the E7 rule (PVC-on-v3 requires `use_pvc_as_ivc` set explicitly — see §2.1). This run **must**
target `eDwT8Vhp2yxJzAMmuuPA`, confirmed correct by the user's explicit instruction.

The render assets live as git-ignored local files directly under `C:\Projects\ContentStudio\stitcher\renders\...`
(the plain checkout, not any worktree) — `elevenlabs-tooling` itself only exists on the unmerged branch.
Execution will run `elevenlabs_tooling` from its worktree checkout
(`C:\Projects\ContentStudio\.claude\worktrees\elevenlabs-tooling-impl\elevenlabs-tooling`) with `--output`
paths pointing at the real render directory. No branch merge is required to do this.

### 1.2 The finished render's real timeline (measured, not the stale draft)

`render-spec.json` and the actual asset files agree on a **60.865188s** total runtime — not the 53.0s
the draft `elevenlabs-music-spec.md` (written mid-pipeline, before final assembly) assumed. Every VO
clip is placed back-to-back with **zero gaps** — each stem's `at` equals the exact cumulative sum of the
prior stems' measured durations:

| # | Beat | Text (TTS-formatted, from `03-voiceover/artifact.v1.md`) | Chars | Old duration (IVC) | Placed at |
|---|---|---|---:|---:|---:|
| VO1 | Hook | "The oldest warning about pushing your kid into one sport? Twenty-three-hundred years old." | 89 | 5.642438s | 0.000000 |
| VO2 | Setup | "Aristotle watched the ancient Olympics… and noticed the boy champions almost never won again as men." | 100 | 6.426083s | 5.642438 |
| VO3 | Build — mechanism | "He blamed the early training. Push a young body that hard, and it burns the strength you were building." | 103 | 7.549375s | 12.068521 |
| VO4 | Re-hook | "Here's the strange part. Jump forward twenty-three-hundred years… and the modern data agrees." | 93 | 5.955917s | 19.617896 |
| VO5 | Build — proof | "Chundi and colleagues followed two-thousand-five-hundred-fifty-six en-eff-ell players in a twenty-twenty-six study. The ones who played multiple sports had longer careers, and fewer injuries. Twelve more games. Nearly an extra season." | 234 | 15.072625s | 25.573813 |
| VO6 | Payoff | "So the kid who plays everything isn't falling behind. Even the researchers who pushed back agree. Güllich and colleagues showed playing many sports is what builds the athlete who lasts." | 185 | 14.027750s | 40.646438 |
| VO7 | Loop/CTA | "That twenty-three-hundred-year-old warning? The one-sport kid was never the safe bet." | 85 | 6.191000s | 54.674188 |

**Total: 889 characters, 60.865188s at the old voice's pace.**

The per-beat settings (stability / similarity / style / speed / speaker boost) are unchanged from the
brief — they're a voice-agnostic creative call, not tied to the old `voice_id`:

| Beat | Stability | Similarity | Style | Speed | Speaker boost |
|---|---:|---:|---:|---:|---|
| Hook | 0.55 | 0.80 | 0.45 | 1.10 | true |
| Setup | 0.45 | 0.80 | 0.40 | 1.00 | true |
| Build — mechanism | 0.45 | 0.80 | 0.40 | 0.98 | true |
| Re-hook | 0.55 | 0.80 | 0.45 | 1.10 | true |
| Build — proof | 0.70 | 0.80 | 0.15 | 0.95 | true |
| Payoff | 0.50 | 0.80 | 0.35 | 1.00 | true |
| Loop/CTA | 0.55 | 0.80 | 0.45 | 1.05 | true |

### 1.3 The central risk: new voice ⇒ new durations ⇒ shot-timing drift

Every shot cut, overlay timestamp, and the bed's hold-out placement in this render were built by
**measuring the old voice's actual output**, then cutting the video to match — not the other way around.
A different voice (even reading the identical text) will almost certainly produce different per-beat
durations. That drift will NOT be reconciled by this run (see §8) — it will be measured and reported so
you can decide whether a re-cut is warranted.

### 1.4 "Prep" is just a format conversion, not a content-altering step

Verified with `ffprobe`: `VO1 - ....mp3` (mono, 44100Hz, 5.642438s) vs. `VO1_prepped.wav` (mono, 48000Hz,
5.642458s — a 20-microsecond difference, i.e. resampling rounding only). **No trimming, no loudness
normalization, no silence removal happens in "prep."** It is exactly:

```bash
ffmpeg -i "VO1 - ....mp3" -ar 48000 -c:a pcm_s16le "VO1_prepped.wav"
```

Confirmed independently: `stitcher`'s own render pipeline re-encodes every input to 48kHz/16-bit PCM
internally regardless of what you feed it (`stitcher/audio.py:262-284`), so this conversion is
belt-and-suspenders, not a hard requirement — but matching the existing convention costs nothing and
keeps `assets/` consistent.

### 1.5 `Bed Full.wav` is fully pre-mixed; no combiner script exists in this repo

No code anywhere in `stitcher/`, `pipeline-app/`, or `scripts/` combines `BedA Music.wav` +
`BedB Music.wav` into `Bed Full.wav`, and no code produces the hook hold-out (bed silent 0–5.6s) or the
re-hook pause (bed silent for part of the re-hook beat). `render-spec.json`'s `audio.bed.windows`/`.fades`
are both empty — confirming those silences are **baked into the WAV file's actual samples**, not applied
at render time. `stitcher` only does two things to the bed at render time: `-stream_loop -1 -t <runtime>`
(loop-and-trim to fit whatever runtime it's given — `audio.py:316-323`) and gain-conform + auto-duck under
the VO spans (`audio.py:288-339`). This means:

- The new `Bed Full.wav` only needs to be **at least** as long as the final runtime — `stitcher` trims
  any excess for free. Being a couple of seconds long is harmless; being short causes an audible loop-repeat.
- Exact splice-point precision doesn't need to be nailed in the API payload's `duration_ms` — that value
  is a **soft target** anyway (the existing `BedA Music.wav`/`BedB Music.wav` came back at clean 15.0s/30.0s
  against a 15.3s/30.5s target — ElevenLabs music generation doesn't hit `duration_ms` exactly). Final
  precision is achieved for free, locally, with `ffmpeg`, after generation.
- Building `Bed Full.wav` — silence, then Bed A content, then the pause silence, then Bed B content,
  padded to the full runtime — is new work this plan does with local `ffmpeg`, not existing tooling.

### 1.6 `elevenlabs_tooling` cannot use the `/with-timestamps` TTS variant today

`client.py`'s response handling requires `Content-Type: audio/*`; the `/with-timestamps` endpoint returns
`application/json` (base64 audio + a character-timing array) and would be misclassified as a failed send.
**This run uses the standard TTS endpoint only.** Precise pause placement (§1.3, §3.2) is instead
recovered for free after the fact with `ffmpeg silencedetect` against the generated VO4 clip, which should
show a natural pause where the script's "…" sits.

---

## 2. Decisions that need your explicit sign-off before any `send` call

Each blocks execution until answered. Recommendation stated; default is what gets used if you don't
override it.

### 2.1 PVC-on-v3 trade-off (blocks `validate` — this is `elevenlabs_tooling`'s E7 check)

`channel-voice.md`'s Open action 3, undecided. Three options, per
`.claude/skills/elevenlabs-audio/references/voice-profiles.md`:

| Option | Trade | `use_pvc_as_ivc` | `model_id` |
|---|---|---|---|
| **Run PVC on v3 as-is** *(recommended)* | Tags work; fidelity not fully optimized for v3 yet | `false` | `eleven_v3` |
| Force IVC-grade fidelity | Lower latency, deliberate fidelity trade-down | `true` | `eleven_v3` |
| Full PVC fidelity, no tags | Best fidelity; loses tag support entirely | n/a | `eleven_multilingual_v2` |

**Recommendation: option 1.** This script places no v3 emotion tags in this pass anyway (per the brief —
the pinned voice hasn't been tag-probed yet), so the "tags work" upside is moot *this run*, but the whole
point of upgrading to a PVC is fidelity — don't trade it away for a latency benefit nobody needs on a
batch job. **Default: `use_pvc_as_ivc: false`, `model_id: eleven_v3`.**

### 2.2 Pronunciation — "Chundi" and "Güllich"

Two names, unverified pronunciation, flagged by the brief as needing either a PLS pronunciation
dictionary or inline phonetic respelling. `elevenlabs_tooling`'s E8 check supports
`pronunciation_dictionary_locators` (up to 3), but standing one up is an untested, extra API surface for
a single-shot run.

**Recommendation: inline phonetic respelling in the `text` field, not a PLS dictionary.** Lower risk,
zero extra setup, standard TTS practice. Proposed respellings (used in the VO5/VO6 payloads in §3.1):
- `Chundi` → `Chun-dee`
- `Güllich` → `Goo-lik` *(the brief's own noted "commonly anglicized" option — say if you want the
  German-correct `Guel-ish` instead)*

### 2.3 Re-roll budget for Hook and CTA

The brief recommends 2–3 takes of the Hook and CTA (the highest-leverage lines) and picking the best.
That's additional spend beyond the one-take-per-beat baseline.

**Recommendation: one extra take each for VO1 (Hook) and VO7 (CTA), 2 takes total per line, decided
without listening (i.e., pre-committed, not "generate and see").** This keeps the run's total call count
fixed and known before execution: 7 baseline + 2 re-rolls = 9 TTS calls. **If you'd rather keep this to a
strict 7-calls/7-beats, single-take policy, say so — that's the cheaper default if declined.**

### 2.4 Output format / quality tier

The existing `elevenlabs-music-spec.md` was explicitly a **draft** (`mp3_44100_128`, stepping up to
`mp3_44100_192` only at a master pass). Since this is framed as "a full and real test," not a throwaway
draft:

**Recommendation: `output_format=mp3_44100_192` for both VO and music.** Output format does not change
ElevenLabs' per-character/per-generation credit cost (only file size/quality) — confirm this against your
account if you want certainty, but nothing in this repo's verified docs suggests otherwise.

### 2.5 Music composition plan — target durations (real timeline, not the stale 53s draft)

Recomputed against the real 60.865188s timeline (§1.2), using `ffmpeg silencedetect` on the *newly
generated* VO4 to locate the actual re-hook pause before finalizing the splice (§6.2) — no re-spend
needed regardless of where it lands, because both beds are generated deliberately long enough to cover
the full range of plausible pause placement, then trimmed for free:

**Bed A** (`music_v2`, covers 5.642438s → worst-case 25.573813s, ~19.9s total):
- Chunk A1 "Setup — quiet unease, observational (fade-in)": `duration_ms: 6427`
- Chunk A2 "Mechanism — low drone deepens, strings darken; thins toward the pause": `duration_ms: 13505`

**Bed B** (`music_v2`, covers worst-case-earliest-pause-end 19.617896s → 60.865188s, ~41.2s total):
- Chunk B1 "Riser out of silence into a warm, grounded, steady pulse — leave space for spoken numbers": `duration_ms: 21029`
- Chunk B2 "Resolution / relief — opens warmer, major-key lift, reassuring not triumphant": `duration_ms: 14028`
- Chunk B3 "Loop close — narrows back to sparse, minor, faintly ominous; thins toward silence": `duration_ms: 6191`

Full chunk text/styles carried forward unchanged from `03-music/elevenlabs-music-spec.md` (§3.2) — only
the durations are recomputed. **Recommendation: accept these as computed; they're mechanical, not
creative, calls.**

### 2.6 Non-destructive staging (not really optional, but confirm the location)

New assets are generated to `assets/provoice-2026-08-19/` (a new subfolder), never directly overwriting
`VO1 - ....mp3`, `Bed Full.wav`, etc. `elevenlabs_tooling send` already refuses to overwrite an existing
file without `--force`, and `--force` is **never used** in this run's send calls — that's a deliberate
guardrail (see §4). Moving the reviewed, approved files into `assets/` proper is a separate, manual,
zero-cost step after QC (§6.4).

---

## 3. Exact payloads

All calls target `https://api.elevenlabs.io/v1/...` with `output_format=mp3_44100_192` (§2.4, pending
sign-off). `ELEVENLABS_API_KEY` must be the account holding the new PVC voice.

### 3.1 Voiceover — 7 payloads (9 calls if §2.3's re-roll budget is approved)

URL template: `https://api.elevenlabs.io/v1/text-to-speech/eDwT8Vhp2yxJzAMmuuPA?output_format=mp3_44100_192`

Common payload shape per beat:

```json
{
  "text": "<beat text — see table>",
  "model_id": "eleven_v3",
  "use_pvc_as_ivc": false,
  "voice_settings": {
    "stability": <per-beat>,
    "similarity_boost": 0.80,
    "style": <per-beat>,
    "speed": <per-beat>,
    "use_speaker_boost": true
  }
}
```

| File | `text` | stability | style | speed |
|---|---|---:|---:|---:|
| `VO1_provoice.mp3` (×2 if re-rolling) | `The oldest warning about pushing your kid into one sport? Twenty-three-hundred years old.` | 0.55 | 0.45 | 1.10 |
| `VO2_provoice.mp3` | `Aristotle watched the ancient Olympics… and noticed the boy champions almost never won again as men.` | 0.45 | 0.40 | 1.00 |
| `VO3_provoice.mp3` | `He blamed the early training. Push a young body that hard, and it burns the strength you were building.` | 0.45 | 0.40 | 0.98 |
| `VO4_provoice.mp3` | `Here's the strange part. Jump forward twenty-three-hundred years… and the modern data agrees.` | 0.55 | 0.45 | 1.10 |
| `VO5_provoice.mp3` | `Chun-dee and colleagues followed two-thousand-five-hundred-fifty-six en-eff-ell players in a twenty-twenty-six study. The ones who played multiple sports had longer careers, and fewer injuries. Twelve more games. Nearly an extra season.` | 0.70 | 0.15 | 0.95 |
| `VO6_provoice.mp3` | `So the kid who plays everything isn't falling behind. Even the researchers who pushed back agree. Goo-lik and colleagues showed playing many sports is what builds the athlete who lasts.` | 0.50 | 0.35 | 1.00 |
| `VO7_provoice.mp3` (×2 if re-rolling) | `That twenty-three-hundred-year-old warning? The one-sport kid was never the safe bet.` | 0.55 | 0.45 | 1.05 |

(`similarity_boost: 0.80`, `use_speaker_boost: true` constant across all 7.) A re-roll take is named
`VO1_provoice_take2.mp3` / `VO7_provoice_take2.mp3` — identical payload, same call repeated once.

### 3.2 Music — 2 payloads

URL for both: `https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192`

**Bed A** → `BedA_provoice.mp3`:

```json
{
  "model_id": "music_v2",
  "seed": 20260819,
  "composition_plan": {
    "chunks": [
      {
        "text": "Intro underscore — gentle fade-in from silence; quiet unease, observational",
        "duration_ms": 6427,
        "positive_styles": ["cinematic underscore","soft piano","sustained low strings","minor key","slow","unhurried","intimate","low dynamics","sparse","airy"],
        "negative_styles": ["vocals","singing","spoken word","lyrics","drums","percussion","loud","busy"],
        "context_adherence": "high"
      },
      {
        "text": "Cautionary deepening — low drone enters, strings darken; thins toward the pause",
        "duration_ms": 13505,
        "positive_styles": ["cinematic underscore","low drone","dark strings","minor key","sparse","slow","subdued","tension","low dynamics"],
        "negative_styles": ["vocals","singing","spoken word","lyrics","drums","percussion","loud","busy","bright"],
        "context_adherence": "high"
      }
    ]
  }
}
```

**Bed B** → `BedB_provoice.mp3`:

```json
{
  "model_id": "music_v2",
  "seed": 20260819,
  "composition_plan": {
    "chunks": [
      {
        "text": "Modern lift — soft riser out of silence into a warm, grounded, steady pulse; leave space for spoken numbers",
        "duration_ms": 21029,
        "positive_styles": ["modern cinematic","warm analog synth pad","rising strings","steady low pulse","grounded","mid-tempo","clean","spacious","low percussion"],
        "negative_styles": ["vocals","singing","spoken word","lyrics","busy","loud","aggressive"],
        "context_adherence": "high"
      },
      {
        "text": "Resolution / relief — opens warmer, major-key lift, reassuring not triumphant",
        "duration_ms": 14028,
        "positive_styles": ["cinematic underscore","warm strings","resolving","major key","hopeful","open","gentle build","low percussion","uplifting but restrained"],
        "negative_styles": ["vocals","singing","spoken word","lyrics","busy","loud","aggressive","triumphant fanfare"],
        "context_adherence": "high"
      },
      {
        "text": "Loop close — narrows back to sparse, minor, faintly ominous; thins toward silence for a seamless loop",
        "duration_ms": 6191,
        "positive_styles": ["cinematic underscore","sparse","low drone","minor key","intimate","unresolved","fading","low dynamics"],
        "negative_styles": ["vocals","singing","spoken word","lyrics","busy","loud","percussion","bright"],
        "context_adherence": "medium"
      }
    ]
  }
}
```

(`seed` bumped to `20260819` — today's date — since this is a distinct generation family from the
original `20260811` beds, per the corpus tool doc's framing of seed as a coherence aid, not
reproducibility.)

### Total calls, worst case

7 VO (or 9 with re-rolls, §2.3) + 2 Music = **9–11 `send` calls total**, each preceded by a free
`validate` call. No call repeats unless a `validate`-caught defect is fixed *before* that call's first
`send` (see §4).

---

## 4. Safety rails (how "don't run this twice" is actually enforced)

1. **`validate` every payload before `send`-ing any of them — all 9–11, in one batch, zero cost.**
   `python -m elevenlabs_tooling validate --payload <file> --url <url>` for every payload in §3, using
   the real URLs (including `eDwT8Vhp2yxJzAMmuuPA` and `use_pvc_as_ivc: false`) so E7 is actually
   exercised, not skipped. Fix anything E-level before touching `send`. This is the main lever for "get
   it right the first time" — everything checkable for free gets checked before a credit is spent.
2. **No `send` runs until every validate call in step 1 passes AND you've confirmed §2's five decisions.**
3. **Every `send` writes to a new file under `assets/provoice-2026-08-19/`** — never the existing
   `VO1 - ....mp3` / `Bed Full.wav` etc. `--force` is never passed; if a file already exists (e.g. a retry
   after a local bug, not an API failure), that's `elevenlabs_tooling`'s own collision guard doing its job
   — investigate before deleting anything.
4. **`send` calls run one at a time, sequentially, each checked before the next fires.** A `validate`
   pass doesn't guarantee the *live* call succeeds (network, account, moderation) — if call N fails
   (`EXIT_SEND_FAILED`/`EXIT_NO_API_KEY`), **stop and diagnose** rather than continuing down the list;
   most failure modes (bad key, account issue) will fail identically on every subsequent call, so
   continuing just burns partial credits on calls likely to fail too.
5. **Every attempt is logged** — `elevenlabs-tooling/logs/tooling-YYYY-MM-DD.log` — this run's log lines
   are the audit trail for exactly what was sent and what came back, before any local post-processing
   touches the files.

---

## 5. Execution runbook (ordered)

Run from `C:\Projects\ContentStudio\.claude\worktrees\elevenlabs-tooling-impl\elevenlabs-tooling`
unless noted. `$RENDER` = `C:\Projects\ContentStudio\stitcher\renders\stop-over-specialization-in-youth-sports-20260811-004711`.

1. **Create the staging directory:** `$RENDER\assets\provoice-2026-08-19\`.
2. **Write all 9–11 payload JSON files** (§3) to a scratch location.
3. **Validate every payload** (§4.1) — zero cost. Fix and re-validate anything that fails; this loop is
   free and can run as many times as needed.
4. **Stop here and get explicit final go-ahead** — restate the total call count, the resolved §2
   decisions, and the estimated cost (§7) — before the first `send`.
5. **Send the 7 (or 9) VO calls, one at a time**, output to `$RENDER\assets\provoice-2026-08-19\VO#_provoice.mp3`.
   Check each `EXIT_PASS` before firing the next.
6. **Send the 2 Music calls**, output to `$RENDER\assets\provoice-2026-08-19\BedA_provoice.mp3` /
   `BedB_provoice.mp3`.
7. **All API spend is now committed — everything past this point is free, local, and freely repeatable.**

---

## 6. Post-generation reconciliation (free, local, repeat as needed)

### 6.1 Prep the VO clips
`ffmpeg -i VO#_provoice.mp3 -ar 48000 -c:a pcm_s16le VO#_provoice_prepped.wav` for each (§1.4).

### 6.2 Locate the real re-hook pause
`ffmpeg -i VO4_provoice.mp3 -af silencedetect=noise=-30dB:d=0.3 -f null -` — read the detected
`silence_start`/`silence_end` from stderr. This is the actual pause boundary for the new voice's read of
the "…" in VO4's text, used to splice Bed A's tail against Bed B's entry in §6.3.

### 6.3 Build `Bed Full_provoice.wav`
Concatenate, with `ffmpeg`: silence (0 → new VO1 duration) + Bed A content (trimmed to end at the
detected pause start) + silence (pause span) + Bed B content (starting fresh at the detected pause end,
run to its own natural length) + pad/fade the tail with a touch of silence if short of the new total
runtime. Exact splice arithmetic is mechanical once §6.1/§6.2's real numbers are in hand — this plan
doesn't hardcode it because it depends on results that don't exist until after §5 runs.

### 6.4 Measure the drift, report, don't auto-apply
Compare new VO#_provoice durations against the table in §1.2. Produce a short diff report: per-beat
duration delta, new total runtime, and how far every downstream shot cut / overlay timestamp would need
to move to stay in sync. **Do not edit `render-spec.json`, shot timings, or captions in this pass** — hand
the report back for a decision on whether a re-cut is warranted (§8).

### 6.5 QC listen
Against the checklist already in `03-music/elevenlabs-music-spec.md`'s "QC CHECKLIST" section (vocal
leakage, Bed A thinning by the pause, Bed B riser audible out of silence, no swelling over VO5's numbers,
B2 not triumphant, B3 thins for the loop) plus a listen for the new voice: does it sound like the
intended PVC, any artifacts from `similarity_boost: 0.80`, any v3-on-PVC fidelity issues per §2.1's
un-probed caveat.

### 6.6 Promote, don't overwrite
Only after QC passes, manually copy the approved files from `provoice-2026-08-19/` over the originals (or
leave both and point a new render-spec variant at the new set) — a deliberate, reviewable step, not
something this plan does automatically.

---

## 7. Cost estimate

No confirmed $/credit rate exists in this repo's verified docs (`docs/elevenlabs-production-runbook.md`
and `docs/elevenlabs-music-runbook.md` both explicitly decline to quote one — pricing is account-tier
dependent and wasn't confirmed against live docs). What's known:

- **Voiceover:** 889 characters baseline (7 beats), 1,063 if the §2.3 re-roll budget is approved
  (+89 Hook +85 CTA). `eleven_v3` is priced at the "standard" tier per the model table (not the 50%-cheaper
  Flash tier) — this is the brief's own choice for tag-capable delivery, unchanged by this run.
- **Music:** 2 `music_v2` compose calls, ~20s and ~41s of generated audio respectively (over-length by
  design, per §1.5/§2.5 — trimmed for free afterward). Eleven Music is paid-tier only; per-call credit
  cost isn't published in this repo's verified sources.
- **Action before executing:** check your ElevenLabs account's current plan/credit balance and confirmed
  per-character and per-music-generation rates directly (account dashboard or a fresh doc lookup) so
  §4's final go-ahead includes a real dollar number, not just a character/duration count.

---

## 8. Explicitly out of scope for this run

- Regenerating or patching `render-spec.json`'s shot `in`/`out` timings, `audio.stems[].at` offsets, or
  the cover.
- Regenerating captions (`.srt`/`.ass`) or overlay JSON/PNGs.
- Re-running `stitcher`'s render step to produce a new `.mp4`.
- Standing up an ElevenLabs PLS pronunciation dictionary (§2.2 recommends inline respelling instead).
- Filling in `channel-voice.md`'s `Locked settings`/tag-probe rows on `main` — that update lives on
  `claude/elevenlabs-tooling` only; merging that pin to `main` is a separate decision from this
  validation run.

Each of these is a legitimate, cheap (no additional API spend) follow-up once §6.4's drift report is in
hand — just not bundled into this single-shot execution.

---

## 9. Sign-off checklist

Before I run a single `send`:

- [ ] §2.1 — PVC-on-v3 trade-off confirmed (default: run as-is, `use_pvc_as_ivc: false`)
- [ ] §2.2 — pronunciation approach confirmed (default: inline respelling, `Goo-lik` for Güllich)
- [ ] §2.3 — re-roll budget confirmed (default: 1 extra take each for Hook + CTA, 9 VO calls total)
- [ ] §2.4 — output format confirmed (default: `mp3_44100_192` for both VO and music)
- [ ] §2.5 — music composition-plan durations confirmed (default: as computed in this doc)
- [ ] §2.6 — staging location confirmed (default: `assets/provoice-2026-08-19/`, no `--force` ever)
- [ ] §7 — actual account cost checked and acceptable
