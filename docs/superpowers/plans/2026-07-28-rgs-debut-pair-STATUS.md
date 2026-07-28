# RGS Debut Pair — Run Status

**Date:** 2026-07-28
**Plan:** `docs/superpowers/plans/2026-07-28-rgs-debut-pair.md`
**Spec:** `docs/superpowers/specs/2026-07-28-rgs-debut-pair-design.md`
**Branch:** `rgs-debut-run` (14 commits, `aa81d31`…`6b3dba5`, based on `main` @ `305afff`)
**State:** **PAUSED after Task 17 of 22**, by request, pending a decision on the visual stage.

---

## Why it is paused

A parallel session committed `ffaa53c` ("docs: spec and plan for the dual-register visual
system") to what was then the shared branch. That spec diagnoses five failures in the
`visual-prompts` stage, and **three of them are present in this run's Short A visual sheet**
(verified, not assumed):

| Diagnosed failure | Short A sheet (`…-decline-the-next-level-visual-prompts.md`) |
|---|---|
| Optics copy-pasted | **Present.** `35mm` is the only focal length across all 11 stills. No establishing wide, no long lens, no deep focus. |
| Thinker era absent | **Present.** Dewey (1916) has a quote card but no era visual; every still is modern paperwork and gear. |
| Prompts thin / uncopyable | **Present.** Prompts sit in table cells with parameters in a separate column, so none can be copied into Midjourney in one action. |
| Repeated near-identical stills | **Partial risk.** A-08/09/10 are three ladder shots and A-03/04/05 three gear shots, all inside one motif family. |
| No sport specified | **Avoided.** Soccer, baseball and swimming are named; the banned `empty gym` phrasing does not appear. |

The dual-register spec attributes the root cause to the skill itself —
`visual-prompts/references/worked-example.md:38-40` teaches consistency-by-cloning-the-prompt-body,
and `SKILL.md` never inspects the emitted sheet as a *sequence*. So this run's sheet has the
defect **despite following the skill correctly**, which is why it is a decision rather than a bug
to fix in place.

**Nothing downstream of the visual stage has been built for Short B**, so the cost of changing
course now is one sheet, not six artifacts.

---

## Branch layout (after separation)

| Branch | Tip | Contents |
|---|---|---|
| `rgs-debut-run` | `6b3dba5` | **This run only.** 14 commits. |
| `dual-register-visual-system` | `ffaa53c` | The parallel session's spec + plan, preserved intact. |
| `rgs-debut-pair` | `ffaa53c` | The old combined pointer, left in place. |

Checking out `rgs-debut-run` removes the two dual-register documents from the working tree; they
are safe on their own branch and return with `git checkout dual-register-visual-system`.

---

## What is done — 14 committed artifacts

### Run-level

| File | Contents |
|---|---|
| `…-rgs-debut-reference-scan.md` | 10 transcribed competitor videos, hook-pattern table, five white-space findings, method/limitations disclosures |
| `…-rgs-debut-sparks.md` | The two sparks, slugs, archetypes, dedupe record |
| `…-rgs-debut-visual-system.md` | Palette, `--sref`/seed discipline, still-pool protocol, motion rationing — **subject to the pending decision** |

### Short A — `decline-the-next-level` (A1) — complete, 7 artifacts

Grounding brief · concept brief · script · voiceover brief · visual prompts · assembly · social repurpose.

- **Grounding:** John Dewey, *Democracy and Education* ("play as its own end, not subordinated to
  an outside result") × **R9** (Côté, Lidor & Hackfort 2009 ISSP position stand). `quote-ok`.
- **Title:** *Turning Down the Elite Team Won't Set Your Kid Back*
- **Thumbnail:** registration form sliding back across a table, pen capped — `YOU'RE ALLOWED TO DECLINE`
- **Script:** 45s / 113 words. Opens *"It won't set him back. Not athletically."*
- **Voice:** single narrator, `eleven_v3` master, −14 LUFS.
- **Visuals:** still pool `A-01`…`A-11`; 2 of 11 image-to-video.

### Short B — `nobody-asked-the-kid` (A3) — 4 of 7 artifacts

Grounding brief · concept brief · script · voiceover brief. **Visual prompts, assembly and
repurpose are not built.**

- **Grounding:** Charlotte Mason, *Home Education* ("play as important as lessons") × **R10**
  (Visek et al. 2015 FUN MAPS). `quote-ok` both sides.
- **Title:** *Your Kid Already Knows the Best Part of the Season*
- **Thumbnail:** standings sheet sharp in foreground, child's unwatched moment soft behind — `IT'S NOT ON HERE`
- **Script:** 50s / 127 words. Opens *"Best part was the mud. Everybody fell over."*
- **Voice:** **two cast voices** — composite child (0–3s) and narrator (3–50s), with a
  ~100–150ms room-tone gap at the handoff.

---

## What remains

| Task | Status |
|---|---|
| 18 — Short B visual prompts (REUSE/NEW enforcement) | **Blocked on the visual-stage decision** |
| 19 — Short B assembly plan | Not started |
| 20 — Short B social repurpose | Not started |
| 21 — Three-persona validation panel | Not started |
| 22 — Revision loop + final report | Not started |

---

## Decisions made autonomously during the run

Recorded here because they departed from the plan or spec as written.

1. **Shorts recency window relaxed** 90 days → 180 → narrowed to a preferred 120 days. Two
   Shorts sit in the exception band and are disclosed in the scan's Method section.
2. **A view floor was added** (≥1,000 views, or ≥3× channel median with n≥10) because
   "high relative to channel" admitted a 1-view video.
3. **The long-form slate was rebuilt for register diversity** — four of five original picks made
   the same cost argument, which would have made the white-space analysis vacuous. Final slate:
   two cost/system, one incentive/development, one kid-voice, one coach-side.
4. **Finding 5 was not made a standalone spark**, because it converges on the existing
   Veblen × invidious-comparison × F4 × A1 brief from 2026-07-25.
5. **Short B runs 50s**, a declared departure from the skill's 35–45s band, so the pair reads as
   companions rather than twins.
6. **`[REF]` and `[B]` markers were introduced** and are now documented in `rgs-briefs/README.md`.

## Defects caught and fixed during the run

- **Marker inversion (blocking).** The reference scan initially used `[C]` for its ten-video
  cohort and invented `[C-CS]` for the 420-video corpus — backwards, since every skill reads
  `[C]` as the corpus. Renamed to `[REF]`, with `[C]` restored to its canonical meaning.
- **An unevidenced promise.** Spark A's "your kid will be fine" was banned as unpublishable and
  narrowed to what R9 actually supports: *declining doesn't set your kid back — athletically.*
- **A homogeneous reference slate** (see decision 3).

---

## Open pre-publish actions (accumulated, none blocking this pause)

- Verify the `[T-unverified]` Shorts safe zone on a real phone before locking a template.
- Spot-check R9's postulates and R10's determinant/factor counts against the current corpus
  files (figures are as of the 2026-07-18 edition).
- Re-verify the dated `[T]` policy facts.
- Run Gate B (adversarial art-direction review) before any Midjourney submission.
- Record real Midjourney seed values at first render; the manifest currently holds placeholders.
- Fill both ElevenLabs Voice Profile Cards — Stage A audition needs generated audio, which this
  run deliberately does not produce.
- Resolve the music-rights source and name a font family for burned-in cards (the visual system
  leaves it open rather than inventing one).

## Known check-hygiene note

The banned-lexicon substring check false-positives on **"Hackfort"** (R9's co-author) because it
contains "hack". Use word-boundary matching, or Task 21's panel will raise a phantom finding on
every Short A artifact.
