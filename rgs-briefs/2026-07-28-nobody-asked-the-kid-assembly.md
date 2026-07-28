---
version: 1
date: 2026-07-28
kind: assembly
run: rgs-debut-20260728-055448
slug: nobody-asked-the-kid
stage: 04-assembly
script: rgs-briefs/2026-07-28-nobody-asked-the-kid-script.md
voiceover_brief: rgs-briefs/2026-07-28-nobody-asked-the-kid-voiceover-brief.md
visual_prompts: rgs-briefs/2026-07-28-nobody-asked-the-kid-visual-prompts.md
visual_system: rgs-briefs/2026-07-28-rgs-debut-visual-system.md
short_a_assembly: rgs-briefs/2026-07-28-decline-the-next-level-assembly.md
total_runtime_seconds: 50
voice_count: 2
status: complete
---

=== ASSEMBLY / EDIT PLAN — nobody-asked-the-kid (Short B) ===

Produced by `shorts-assembly` from the three converged upstream artifacts: the 50-second
archetype-A3 script (Task 16), the two-cast voiceover brief (Task 17), and the 15-shot dual-register
visual prompt sheet (Task 18), bound by the locked shared visual system (Task 8, as amended
2026-07-28). **No assets are generated and nothing is rendered by this document** — it is the plan
an editor follows once the two ElevenLabs voice tracks, the sixteen Midjourney stills, and the two
Kling i2v clips actually exist. Every figure below is arithmetic applied to those artifacts' own
numbers, except where a plan-level judgment is explicitly flagged as this skill's own.

**Three things Short A's plan does not cover, and this one has to.** `[I]` Stated up front so a
reader coming from Short A knows where the two plans genuinely diverge rather than assuming this is
the same document with new numbers: (1) **two cast voices** with a hard boundary at 3.0s and a
room-tone gap — §3; (2) **two visual registers**, present-day youth soccer and Mason's 1886 England,
whose cut points are the Short's main visual event — §4; (3) **fifteen shots across fifty seconds**
with only two motion clips, which changes both the cut arithmetic and the edit-added-movement
workload — §1, §2.

## Marker legend (an unmarked normative line below is a bug)

- **`[C]`** — the 420-video ContentStudio corpus, cited `(Channel, video_id)`, carried through from
  `shorts-assembly/references/*.md` (which distill `docs/headless-shorts-production-playbook.md`
  and `docs/headless-youtube-audit.md`).
- **`[I]`** — general craft judgment or this skill's own operational decision, traceable to none of
  the below.
- **`[T]`** — tool/policy fact, dated 2026-07-23 in the assembly references; visual/Midjourney facts
  inherited from upstream carry their own 2026-07-26 date where noted. Re-verify before relying on
  it.
- **`[T-unverified]`** — asserted by a supplied source, not confirmed against live vendor docs.
  Starting hypothesis only, flagged wherever used.
- **`[B]`** — RaisingGoodSports Brand Definition, carried from the script / voiceover brief / visual
  system, never re-derived here.
- **`[REF]`** — the ten-video youth-sports reference cohort. Describes those ten videos only.
- **`[THINKER: …]` / `[RESEARCH: …]`** — grounding citations, carried verbatim.

---

## 1. Shot-by-shot pacing and cut cadence

Aspect ratio **1080×1920, 9:16** `[I]` (`pacing-and-editing.md`, `worked-example.md`). Beat
boundaries are inherited unchanged from the script and the sub-cut points are inherited unchanged
from the prompt sheet's arc table — **this stage moves nothing**, it only names what each shot does
in the edit. The governing cadence rule is the corpus's: change the on-screen visual roughly every
~3 seconds and never hold one image too long, because a static frame is "the visual equivalent of
dead air" `[C] (Make Money Matt, HopTPCLbiiM; vidIQ, DiZnbihU4NM)`. Total: **15 distinct visual cuts
across 50 seconds.**

| # | Beat | Range | Dur | Asset | Reg | Cut note | On-screen text (safe zone) |
|---|---|---|---|---|---|---|---|
| 1 | Hook | 0–3s | 3.0s | **B-01** (Kling i2v — sheet sharp, child moving behind) | A | One continuous shot, no internal cut — the push-in *is* the cadence | `BEST PART WAS THE MUD` 0–2.0s (`MUD` amber) → `IT'S NOT ON HERE` ~2.0–3.0s (`NOT` amber) `[B]` |
| 2 | Setup | 3–5.5s | 2.5s | **B-02** (still — low wide, blurred child fills frame) | A | Hard cut on the voice change at 3.0s (§3) | — (see §5, card gap flagged) |
| 3 | Setup | 5.5–8s | 2.5s | **B-03** (still — 1886 parlour, wide) | B | **Register cut** (§4) | — |
| 4 | Build/Mason | 8–11s | 3.0s | **B-04** (still — marks ledger, macro overhead) | B | Straight cut inside Register B | `CHARLOTTE MASON · 1886` 8–14s, held across the 11s cut `[C] (Kallaway, 6G1wIdxWF5w)` |
| 5 | Build/Mason | 11–14s | 3.0s | **B-05** (still — child in car, mid-telling) | A | **Register cut** back to present | card persists to 14s |
| 6 | Re-hook | 14–17s | 3.0s | **B-06** (still — rack-focus landed on the sheet) | A | One shot; the still's own baked-in focus shift carries the subject change | — (see §5, re-hook card gap flagged) |
| 7 | Build/quote | 17–21.5s | 4.5s | **B-07** (Kling i2v — governess raises the ledger) | B | **Register cut** into the climax; one continuous clip | **Mason quote card opens at 17s** and holds unbroken to 26s (§6) |
| 8 | Build/quote | 21.5–26s | 4.5s | **B-08** (still — copybook, correction stroke) | B | Straight cut inside Register B, **underneath an unbroken card** (§6) | card persists to 26s |
| 9 | Payoff/research | 26–30s | 4.0s | **B-09** (still — XWIDE ground, high) | A | **Register cut** back to present | **Citation plate 1** opens at 26s (§7) |
| 10 | Payoff/research | 30–34s | 4.0s | **B-10** (still — one child mid-effort) | A | Straight cut; **plate 2 reveals ~31s**, one second inside this shot | plate 1 + plate 2 (§7) |
| 11 | Payoff/research | 34–38s | 4.0s | **B-11** (still — 1886 ledger, blank right margin) | B | **Register cut**; plates hold across it — the one deliberate text/register disagreement, §7 | plates persist to 38s |
| 12 | Payoff/reframe | 38–41.5s | 3.5s | **B-12** (still — the sheet alone, no person) | A | **Register cut** back; plates clear at 38s | **AI disclosure line opens at 38s** (§8) |
| 13 | Payoff/reframe | 41.5–45s | 3.5s | **B-13** (still — sheet abandoned on a tailgate) | A | Straight cut inside Register A | disclosure persists to 45s |
| 14 | Loop/CTA | 45–47.5s | 2.5s | **B-14** (still — parlour, ledger lowered, child brightens) | B | **Register cut** — the 1886 world resolves warm | — |
| 15 | Loop/CTA | 47.5–50s | 2.5s | **B-15** (still — Hook's frame, focus pulled the other way) | A | **Register cut** back; closes the visual loop against shot 1 `[C] (Jenny Hoyos, mhVDcqnxxaY — medium confidence, per the script's own flag)` | — |

`B-16` is the dedicated cover/thumbnail and **never appears in the timeline** — §10.

### Timing reconciliation

| Beat | Range | Duration | Shots | Sub-cut sum |
|---|---|---|---|---|
| Hook | 0–3s | 3s | 1 | 3.0 |
| Setup | 3–8s | 5s | 2 | 2.5 + 2.5 |
| Build — Mason's claim | 8–14s | 6s | 2 | 3.0 + 3.0 |
| Re-hook | 14–17s | 3s | 1 | 3.0 |
| Build — quote card | 17–26s | 9s | 2 | 4.5 + 4.5 |
| Payoff — research | 26–38s | 12s | 3 | 4.0 + 4.0 + 4.0 |
| Payoff — reframe | 38–45s | 7s | 2 | 3.5 + 3.5 |
| Loop/CTA | 45–50s | 5s | 2 | 2.5 + 2.5 |
| **Total** | **0–50s** | **50s** | **15** | **3+5+6+3+9+12+7+5 = 50** |

**Total runtime: 50 seconds, confirmed summing.** Every beat range is contiguous and
non-overlapping and matches the script's own reconciliation table exactly.

**Cadence honesty.** Mean shot length is 3.33s, but the distribution is deliberately uneven —
2.5s at the Setup and Loop/CTA, 4.5s under the quote card, 4.0s under the research plates. Those two
long-shot zones are the prompt sheet's own stated departures from the ~3s rule, taken so the
overlays sitting on top stay readable, and they are knowing overrides of a `[C]` rule rather than
readings of it `[C] (Make Money Matt, HopTPCLbiiM)`. The corpus's counter-caution supports the
direction — comprehension comes from *deleting* edits, and chasing wall-to-wall stimulation is a
named failure `[C] (Kallaway, i7upRL4H1FM; Nate Black, J8LrrCpDNJI; vidIQ, DiZnbihU4NM)`. This plan
does not re-cut them faster.

### AI-video budget discipline, confirmed at the edit stage

Only **B-01** (Hook) and **B-07** (Mason quote-card climax) are motion assets; the other thirteen
timeline stills get their movement from the edit (§2) rather than a second round of paid generation.
That matches the corpus's rule to spend premium AI-video budget only on the hook and occasional
cutaway spikes, generating the bulk cheaply `[C] (Make Money Matt, gkaxBe8BGLQ)`, and it is the
motion-rationing decision already taken upstream by the visual system and the prompt sheet. Not
reopened here.

**One clip-length note the editor will otherwise trip on** `[I]`: `B-07`'s clip covers **17–21.5s
only (4.5s)**, not the full 17–26s quote-card beat. The card holds for nine seconds; the clip under
it holds for four and a half, then hard-cuts to the `B-08` still while the card stays put. Do not
stretch or loop the clip to fill nine seconds — the sheet's own arc table splits the beat into two
shots on purpose.

### Reuse status of Short A's pool — stated, not buried

**Zero of Short A's eleven stills (`A-01`…`A-11`) are reused in this timeline.** Every shot above is
a Short-B `NEW` asset. That is the prompt sheet's own audited outcome under the visual system as
amended 2026-07-28, which formally suspended the ≈1.5× asset-economy target for this Short, not a
sourcing failure at this stage `[I]`. The three candidates the sheet tested and rejected — `A-03`
(cleats/shin guards, wrong world lock and wrong motif), `A-07` (Short A's Dewey climax, wrong
argument), `A-11` (Short A's cover, wrong composition) — are recorded there with reasons, and this
plan does not retro-fit any of them into a beat they damage. The shot IDs above are the sheet's own
`B-NN` ids verbatim so the editor can match every row to a rendered file.

---

## 2. Motion assignment for the thirteen timeline stills (edit-added movement)

Per the visual system's own instruction: "every other beat is a still with movement added in the
edit — push-in, parallax, whip cut — specified in the assembly plan" `[B]`. Thirteen stills need a
named move; here they are, one row each, none left unassigned.

**The move grammar is different in the two registers, and that is deliberate** `[I]`:

- **Register A (photographic stills).** The corpus's own still-animation moves apply directly:
  keyframe stills to scale **15–20%**, slow push-in of a few percent at the open to signal
  "something's coming," biased toward early scenes for a premium feel `[C] (vidIQ, DiZnbihU4NM; One
  Person Business, eVePkmCQV5c)`.
- **Register B (painterly stills).** Held to **slow scale only, ≤8%, no parallax layer separation
  and no whip-cut entry.** Two reasons, both this skill's own judgment: a parallax move requires
  cutting a subject away from its ground, which on a painting exposes the brushwork seam rather
  than creating depth; and a hard push on impasto and cracked-varnish texture reads as a digital
  zoom artifact, not a camera move. **The corpus is silent on animating painterly assets** — it
  addresses stills generically and says nothing about medium-specific motion — so this differential
  is flagged as `[I]`, not dressed as a corpus finding `[C] (vidIQ, DiZnbihU4NM — the underlying
  keyframe-stills rule, applied here with a stated restriction the corpus does not state)`.

| Still | Beat / placement | On screen | Reg | Move | Detail |
|---|---|---|---|---|---|
| B-02 | Setup cut 1, 3–5.5s | 2.5s | A | **Push-in, ~15%** | Starts on the voice-change cut at 3.0s and runs the full 2.5s. Early-scene premium bias `[C] (One Person Business, eVePkmCQV5c)`. |
| B-03 | Setup cut 2, 5.5–8s | 2.5s | B | **Slow scale-up, ~6%** | The first Register B frame in the whole channel. Small, steady, no drift on the horizontal — the register change is the event; the move must not compete with it `[I]`. |
| B-04 | Build/Mason cut 1, 8–11s | 3.0s | B | **Slow scale-up, ~6%, centred on the ruled columns** | Overhead macro; keep the move dead-centre so the ledger's ruling stays square to frame under the `CHARLOTTE MASON · 1886` card. |
| B-05 | Build/Mason cut 2, 11–14s | 3.0s | A | **Push-in, ~15%, slight upward drift** | Register cut back to the present; the drift carries the eye toward the child's raised hands. |
| B-06 | Re-hook, 14–17s | 3.0s | A | **Minimal push-in only, ~5%** | The still's own rack-focus end point already carries the subject change; a heavier move fights it, exactly as Short A's `A-06` was handled `[I]`. |
| B-08 | Build/quote cut 2, 21.5–26s | 4.5s | B | **Static hold, no move** | The single no-move shot in the Short, and a deliberate exception to "a static frame is dead air" `[C] (vidIQ, DiZnbihU4NM)`. The verbatim Mason card is being read on top of it for its second half; camera motion under a 22-word block of text degrades reading speed for no informational gain. Flagged as a knowing override, not an oversight. |
| B-09 | Payoff/research cut 1, 26–30s | 4.0s | A | **Very slow push-in, ~8%** | XWIDE establishing frame; a large move on a wide shot reads as a zoom, not a push. The upper third stays clear for citation plate 1 (§7). |
| B-10 | Payoff/research cut 2, 30–34s | 4.0s | A | **Push-in, ~12%, held off the upper third** | Plate 2 reveals ~31s inside this shot; keep the scale origin low so the plate's reserved upper-third band does not creep under the frame edge. |
| B-11 | Payoff/research cut 3, 34–38s | 4.0s | B | **Slow scale-up, ~5%, toward the blank right margin** | The blank margin is the shot's whole point — it pre-figures "nothing has a field for that." The move gives it slightly more of the frame by 38s. |
| B-12 | Payoff/reframe cut 1, 38–41.5s | 3.5s | A | **Static-to-slow push, ~8%** | The disclosure line opens here (§8); keep the move small so the small-set type stays legible. |
| B-13 | Payoff/reframe cut 2, 41.5–45s | 3.5s | A | **Push-in, ~12%, whip cut out at 45s** | The whip out carries into the Loop/CTA's register cut. |
| B-14 | Loop/CTA cut 1, 45–47.5s | 2.5s | B | **Slow scale-up, ~6%, toward the child's lit hands** | The move lands the brightening the still is composed for. No whip entry (Register B rule above). |
| B-15 | Loop/CTA cut 2, 47.5–50s | 2.5s | A | **Push-in, ~10%, resolving on the child** | Mirrors shot 1's push-in direction so the loop reads as the same move with the focus reversed — Short B's variant of Short A's exact-shot loop `[I]`. |

That accounts for all thirteen non-motion timeline stills (`B-02`…`B-06`, `B-08`…`B-15`). `B-01` and
`B-07` are motion clips (§1); `B-16` is the cover and carries no motion (§10).

---

## 3. The two-voice handoff at 3.0s — how the cut is made and levelled

This is the edit's single hardest audio move and the Short's entire differentiator: the composite
child speaks 0–3s and nowhere else; the adult narrator enters at 3s and never before `[B]`/`[I]`.
The voiceover brief fixes the spec; this section states how it is executed on a timeline. **No
corpus finding covers a two-voice Shorts handoff** — the 420-video corpus is creator-education
material and says nothing about child-voiced narration or cast changes mid-Short, so every
numbered step below is `[I]` or inherited `[B]`, and none of it is presented as `[C]`.

**Inputs.** Two independently generated stems — the child's single 43-character render on its own
`voice_id`, and the narrator's seven beat renders on the shared Short A voice. They were
deliberately **not** routed through ElevenLabs' Text-to-Dialogue endpoint precisely so this cut
stays an edit-level decision `[T]` (voiceover brief, Model routing). Do not re-render them as one
combined take to "simplify" the edit — that removes the independent loudness control step 3
depends on.

1. **Trim the child's tail to the end of its decay, not to the last loud sample.** The line ends on
   "over." — cut after the word's natural release has fallen into the noise floor, not mid-decay. A
   mid-decay cut is the classic splice artifact and it will be the first thing a cold reader hears
   `[I]`.
2. **Insert 100–150ms of room tone, not digital silence.** `[I]` (voiceover brief, "The 3.0s
   handoff," point 2). Take the tone from the head or tail of one of the voice renders, or generate
   a matched low-level ambience; a hard zero-sample gap reads as a dropout or an encoder error, not
   as a breath. Lead value: **125ms**, centre of the stated band, so the plan carries a single
   number an editor can actually key in rather than a range to re-decide.
3. **Match short-term perceived loudness across the cut, on the stems, before the master bus.**
   `[I]` (voiceover brief, point 3). Use a 3-second short-term LUFS window on the child clip and on
   the narrator's first beat and bring them within **±1 LU** of each other. Match perceived
   loudness, **not** waveform peaks — a child-register voice and an adult-register voice sit at
   different apparent loudness at identical peaks. The cut must read as a change of *speaker*, never
   a change of *volume*.
4. **Do not normalize the two stems individually to −14 LUFS.** The −14 LUFS integrated target is
   for the finished mix as a whole, once both voices, music and SFX are cut together — never
   per-speaker `[T]`/`[I]` (§9, and voiceover brief point 4). Per-stem normalization would undo
   step 3.
5. **No crossfade, no timbre blend, no EQ-matching between the two voices.** `[I]` (voiceover brief,
   point 1). The viewer is supposed to be able to tell instantly that these are two different
   people. Any processing that narrows the timbral distance between them is working against the
   Short. Shared processing (the same reverb-free chain, the same de-esser settings) is fine;
   matching them *to each other* is not.
6. **Timeline layout, exactly.** Child VO from 0.00s to ≈2.875s → room tone 2.875–3.000s → narrator
   VO from 3.000s. The gap sits **under the tail of shot 1**, so it belongs to the child's beat.
7. **The picture cuts on the voice, at 3.000s.** Shot 1 (`B-01`, i2v) ends and shot 2 (`B-02`)
   begins on the narrator's first word, so the audible speaker change and the visual change land on
   the same frame — the corpus's match-the-visual-to-what-is-being-said rule applied to a cast
   change `[C] (Kallaway, i7upRL4H1FM)`. Do not offset the picture cut into the room-tone gap; a
   picture change during silence reads as a stumble.
8. **The music bed does not exist yet at 3.0s.** Lead call: **hold the bed out entirely for 0–3s**
   and fade it in over ~300ms starting at 3.000s under the narrator's first line `[I]`. The
   voiceover brief offers two options — quieter end of the duck range, or hold out entirely — and
   this plan takes hold-out, because the child's three seconds are the Short's differentiator and a
   first-time viewer should meet that voice with nothing competing for it. The quieter-end
   alternative is recorded, not silently dropped.
9. **What "done" sounds like.** On phone speakers, at arm's length, sound on: two people, one edit
   point, no bump in level, no click, no held breath. If it sounds like one voice pitched up, step 5
   was violated; if it sounds like a volume jump, redo step 3 before touching EQ (voiceover brief,
   QC checklist).

---

## 4. The two visual registers — how the transitions are handled

Register A is present-day youth soccer, shot as documentary photography. Register B is Charlotte
Mason's 1886 England, rendered as luminous oil painting on linen. They share **no** medium, **no**
parameter band, and only the palette's ground and accent. **The cut between them is the Short's main
visual event, and it happens eight times.** `[I]` The whole point of Register B is that the viewer
feels a 140-year distance open and close; how these cuts are handled is the difference between that
and two unrelated slideshows intercut.

**Register order across the fifteen shots:** `A A B B A A B B A A B A A B A`.

**Eight register changes by adjacency**, at the shot boundaries 2→3, 4→5, 6→7, 8→9, 10→11, 11→12,
13→14, 14→15 — i.e. at **5.5s, 11s, 17s, 26s, 34s, 38s, 45s and 47.5s**. `[I]` *(The prompt sheet's
Gate C summary line records "9 alternations"; counting adjacent pairs that differ gives eight. The
discrepancy is noted rather than resolved here — it does not affect Gate C's C7 minimum of ≥2 either
way, and this plan does not edit an upstream artifact to settle an arithmetic footnote.)*

**Rules for every one of the eight, without exception** `[I]`:

1. **Straight cut. One frame. No dissolve, no whip, no film-burn, no transition effect of any
   kind.** The medium change from photograph to oil painting is already the largest visual
   discontinuity available in this Short; adding a transition on top of it is precisely the
   flashbang/stacked-overlay over-editing the corpus names as a viewer-exhausting failure, and the
   corpus's own remedy is deleting edits rather than adding them `[C] (Kallaway, i7upRL4H1FM; Nate
   Black, J8LrrCpDNJI)`.
2. **No SFX on a register cut.** A whoosh on the 1886 cuts converts a narrative device into a
   gimmick and trains the viewer to hear the transition instead of see it. SFX in this Short is
   limited to two placements only (§9).
3. **No music change on a register cut.** The bed tracks the *emotional* arc — warm memory, quiet
   gravity at the quote card, relief at the reframe — not the register. Scoring the register changes
   would make the 1886 world feel like a cutaway segment rather than the same argument seen from a
   different century `[C] (Kallaway, i7upRL4H1FM — music must match the words' tone, never contradict
   it)`.
4. **The overlay system does not change across registers.** Same locked bold sans-serif, same
   `#F7F3E8` body / single `#F2A541` accent word, same safe-zone position, same beat-boundary reveal.
   The constancy of the caption layer is what tells the viewer these are two halves of one video
   `[B]`/`[I]`. Specifically: the `CHARLOTTE MASON · 1886` card holds across the 11s register cut
   and the Mason quote card holds across the 21.5s cut (§6) — cards ignore register boundaries.
5. **Motion grammar changes, silently.** Register A gets 10–20% push-ins and parallax; Register B
   gets ≤8% slow scale and no parallax (§2). The viewer should not be able to name the difference;
   they should only notice that the paintings feel stiller than the photographs. That stillness is
   period-correct and is the point.
6. **Colour continuity is the weld.** Both registers carry the teal-ink ground and the warm amber
   accent from the locked palette, so the cuts read as a change of *world*, not a change of
   *channel* `[B]`. **Muted clay `#C1543A` is system-as-document only and never touches skin, in
   either register** `[B]` — this binds the grade as well as the generation: do not push a warm grade
   on Register A that pulls skin tones toward clay.
7. **Do not colour-grade the two registers toward each other.** The temptation in the edit will be
   to warm the photographs or cool the paintings so the cuts feel "smoother." Smoother is the failure
   mode here `[I]`.

**The one register cut that needs a second look — 10→11 at 34s.** `[I]` Research citation plate 1
(present-day, 2015) and plate 2 hold across this cut into a Register B painting of an 1886 ledger,
so for four seconds a modern academic citation sits over a Victorian oil painting. The corpus's rule
to match the visual to what is being said argues against it `[C] (Kallaway, i7upRL4H1FM)`. It is
retained because `B-11`'s subject is the ledger's **blank unruled margin** — the visual statement of
"nothing has a field for that," which the VO does not reach until 38s — so the shot is a deliberate
pre-echo of the reframe rather than a mismatch. **Flagged for the cold read** (§12): if a reader
reports the plate reading as misattributed to 1886, the fix is to end plate 2 at 34s rather than to
move the shot, since the plate's copy is binding and the shot's function is load-bearing.

---

## 5. Caption / overlay treatment

**Position.** All captions and cards sit inside the middle **~60% vertical safe zone**, clear of the
**bottom 25%** and the **right 15%** — **`[T-unverified]`** (working rule; no official YouTube
safe-zone pixel spec exists and third-party figures openly conflict — verify on a real phone before
this template locks, per the visual system's and the prompt sheet's own caveats).

**Reveal cadence — the locked call, with the corpus tension stated rather than silently resolved.**
The shared visual system locks **one burned-in caption per script beat, revealed at beat boundaries,
not word-by-word karaoke** `[B]`. This is a departure from this skill's own playbook default, and
the corpus genuinely splits on the question:

- **Playbook default `[I]`:** full-duration word-by-word karaoke, 1–3 words per chunk, active word
  tinted.
- **Audit counter-finding `[C]`:** keep captions small and mostly at the start; front-load only for
  the first ~5–10s and rely on auto-subtitles for the body `[C] (One Person Business, 6s2T2NlWDhQ;
  Make Money Matt, LlIkMWX50aQ)`.

**For this Short the brand's fixed system wins over both**, identically to Short A, because the
visual system was locked upstream and governs both debut Shorts; overriding it per-Short would break
the "change the words, not the system" consistency rule the brand treats as its actual asset `[B]`.
Flagged as an explicit judgment call, not a silent pick.

**One Short-B-specific consequence of that call, worth naming.** `[I]` The child's Hook line is
captioned **in the child's own words** (`BEST PART WAS THE MUD`), not summarized by the narrator's
caption, because ~80–85% of viewers watch muted and a muted viewer never hears the voice that is
this Short's entire differentiator `[C] (Kallaway, i7upRL4H1FM)`. The card is therefore doing more
work here than any card in Short A: it is the muted-feed substitute for the cast change itself.
Treat its legibility at phone size as a blocking QA item, not a nice-to-have.

**Style.** One locked bold sans-serif (family TBD at composite time — the visual system reserves
"one bold sans-serif" without naming it, and this plan does not fix it per-Short) `[B]`/`[I]`; body
text `#F7F3E8` on the `#0E3B43` ground wherever a plate is used; the single accent word of any card
in `#F2A541` ALL-CAPS `[B]`. Stroke, shadow or box behind any text placed over a busy frame `[I]`.
One idea per card — no card stacks two thoughts `[I]`.

**Per-beat card schedule (all inside the safe zone):**

| Beat | Range | Card | Notes |
|---|---|---|---|
| Hook | 0–2.0s | `BEST PART WAS THE MUD` (`MUD` amber) | The child's own words `[B]` |
| Hook | ~2.0–3.0s | `IT'S NOT ON HERE` (`NOT` amber) | The locked thumbnail line `[B]` |
| Setup | 3–8s | **none authored upstream — see gap below** | |
| Build — Mason | 8–14s | `CHARLOTTE MASON · 1886` | Date front-loaded as the credibility anchor `[C] (Kallaway, 6G1wIdxWF5w)`; holds across the 11s register cut |
| Re-hook | 14–17s | **none authored upstream — see gap below** | |
| Build — quote | 17–26s | Mason verbatim card + attribution (§6) | Single unbroken card, 9s |
| Payoff — research | 26–38s | Citation plate 1 + figure plate 2 (§7) | Plate 1 from 26s; plate 2 from ~31s |
| Payoff — reframe | 38–45s | AI disclosure line (§8) | Small-set, never amber |
| Loop/CTA | 45–50s | **none authored upstream** | The mirrored VO line carries the loop; see gap below |

**Two card gaps, flagged rather than filled.** `[I]` The visual system's rule is one caption per
script beat, but the script's on-screen-text spec and the prompt sheet's overlay-copy handoff — which
are jointly the authority on what words appear — author **no copy for the Setup (3–8s), the Re-hook
(14–17s), or the Loop/CTA (45–50s)**. Two consequences, both stated rather than papered over:

1. **This plan does not invent card copy.** Writing a Setup card or a re-hook card here would be
   this stage authoring script content it does not own, and on an A3 Short whose every line has been
   through a line-by-line blame audit, an invented card is a real safety risk, not a cosmetic one
   `[B]`. The three windows run card-free.
2. **The Re-hook gap is a departure from a `[C]` rule and is recorded as one.** The corpus places a
   secondary-hook text card at ~15s `[C] (Nate Black, c6X-Ywy3yVU)`. This Short has no such card. The
   re-hook is carried instead by the VO's contrast word ("But…") `[C] (Kallaway, pcnrzBwoVUk)` and by
   `B-06`'s rack-focus landing on the record — a visual subject change a beat before the VO names it.
   That is a legitimate substitution for a *sighted* viewer and a genuine loss for a muted one.
   **Recommended resolution: raise it with `shorts-scripting` before render** rather than solving it
   at the edit; if a card is authored, it belongs at 14–17s and must clear the A3 audit.

---

## 6. The Mason quote card (17–26s) — one unbroken card, deliberately not split

Binding, carried verbatim from the script and the prompt sheet `[THINKER: Charlotte Mason, Home
Education, quote-ok]`:

> "so ingrained is our contempt for children that we see nothing in this but Bobbie's foolish
> childish way!"
> — Charlotte Mason, *Home Education*, 1886

**Implementation:**

- **One card, on screen unbroken 17.0–26.0s**, across the shot 7→8 cut at 21.5s. The card does not
  re-cut, re-animate, or re-enter when the image beneath it changes. `[I]`
- **The attribution line is part of the card, not a later reveal** — it is present from 17.0s and
  stays to 26.0s, per the script's binding note that attribution is never optional. `1886` therefore
  holds for the full sub-beat, which is what makes the "our" visibly Mason's era rather than the
  viewer's — the load-bearing A3 mitigation at the script's highest-risk beat `[B]`.
- **Not split into two reveals, and this is a considered divergence from Short A.** `[I]` Short A
  split its Dewey card because 22 words across a 7-second beat is ~3.1 words/second of required
  reading speed. This card is **18 words across 9 seconds** — ~2.0 words/second, comfortably inside
  a phone reader's rate with slack for the attribution line. Splitting it would introduce a card
  swap in the middle of a verbatim quotation for no readability gain, and the script's own
  instruction is that the card is verbatim and complete. Short A's split was a fix for a specific
  density problem this card does not have; copying the fix without the problem would be cargo-cult.
- **If, and only if, a phone-size read shows it does not fit legibly, shorten by trimming from the
  front of the same sentence — never by rewriting it, never by paraphrase, never by dropping the
  exclamation point.** `[THINKER: Charlotte Mason, Home Education, quote-ok]` The standing
  alternative recorded upstream is the swap to the "allowed to lie fallow" passage, which is a
  verified verbatim drop-in at the same beat — that is a script-level decision, not an editor's.
- **The VO is not the card.** The narrator speaks a shorter contiguous verbatim fragment of the same
  sentence, framed by narrator commentary the card does not carry. Do not sync the card to the VO
  word-for-word; they are different lengths on purpose `[I]`.
- **"It was never yours" may not be cut, shortened, or moved.** The script marks that clause as
  uncuttable and it lands within two seconds of the quote — it is the mitigation that keeps a parent
  from hearing themselves inside Mason's "our" `[B]`. If the beat runs long in the edit, take the
  time from elsewhere.

---

## 7. The research attribution plates (26–38s) — on screen and in voiceover

Binding: the source is named in **both** channels, never compressed to an unattributed claim `[B]`.
This beat is flagged upstream as carrying spoken figures, which is exactly the case the corpus says
must render as on-screen text rather than B-roll alone `[C] (vidIQ, i5bZ-Be9cAQ)`.

- **Voiceover, 26–38s:** "A 2015 George Washington University study asked hundreds of young soccer
  players what makes sport fun. Eighty-one things. Eleven factors. Trying hard came first. Winning
  isn't one of the eleven."
- **Plate 1 — opens 26.0s, holds to 38.0s:**
  `Visek et al. (2015) · The Fun Integration Theory · J. Physical Activity & Health 12(3):424–433 ·
  youth soccer players n=142, coaches n=37, parents n=57`
- **Plate 2 — reveals ~31.0s, holds to 38.0s:**
  `81 fun-determinants → grouped into 11 fun-factors · #1 factor: Trying Hard · winning is NOT one
  of the 11 — roughly 40th of the 81`

**Implementation notes:**

- **Plate 2 ships exactly as written, including the word "roughly."** Never "40th of 81 factors,"
  never "81 factors," never "winning ranked 40th out of 81 factors" `[RESEARCH: Visek et al. 2015]`.
  The two tiers garble easily and the compressed form that merges them is wrong. This is not an
  editorial preference an editor may tighten for line length.
- **Neither plate re-cuts with the stills beneath it.** Plate 1 holds fixed for the full twelve
  seconds while `B-09`/`B-10`/`B-11` cut underneath at 4-second intervals; plate 2 appears once at
  ~31s and holds. Position is fixed at reveal and never moves during the hold `[I]`.
- **Reveal is staggered inside shot 10, not on the shot boundary.** Plate 2 comes in ~1 second after
  the 30s cut so the two events do not stack — a card change and an image change landing on the same
  frame reads as a hiccup, and the corpus's warning against stacked simultaneous stimulation applies
  `[C] (vidIQ, DiZnbihU4NM)`.
- **Placement check the editor must actually run.** The prompt sheet reserves clear upper-third
  space in `B-09` and `B-10` for the plates. It does **not** make that reservation in `B-11`, which
  the plates hold across from 34–38s. Before locking: confirm plate 2 clears `B-11`'s dense
  copperplate half and reads against either its blank right margin or its shadowed lower area. **If
  it collides, do not move the plate mid-hold** — instead apply a small scale/offset to `B-11` in
  the edit to open the needed space. A plate that shifts position during a hold reads as an error
  `[I]`.
- **The `[C]` hedge conflict is inherited, not re-litigated.** The corpus says to state claims with
  certain language and avoid hedges that create exit doors `[C] (Kallaway, pcnrzBwoVUk)`; "roughly"
  is a knowing override because the source file itself hedges the figure. Recorded here so a reader
  sees the override travelled intact rather than being quietly dropped at the last stage.
- **Population never inflated.** "Youth **soccer** players," never "kids in sport"; association,
  never causation; a study, never "science shows" `[RESEARCH: Visek et al. 2015]`.

---

## 8. AI / synthetic-media disclosure — three concrete placements

Brand-mandated and binding, not discretionary `[B]`. **The synthetic child's voice is the highest
policy-exposure element in this pair** — a synthesized minor's voice is exactly the kind of altered
content a platform disclosure control exists for, and the child being a *composite* is what makes
the disclosure sufficient, not a substitute for making it. `shorts-assembly` owns placement timing;
it does not own whether the disclosure ships.

1. **YouTube's altered/synthetic-content disclosure box, set at upload.** A platform toggle, not an
   in-video element — set during the metadata step of the publish sequence (§10), before the video is
   scheduled public `[T]` (YouTube inauthentic-content policy, verified 2026-07-23 via
   https://support.google.com/youtube/answer/1311392 — **re-verify before publishing**).
2. **On-screen line, 38.0–45.0s**, inside the safe zone, over `B-12` and `B-13`:
   > AI-generated visuals · synthetic voices · child's voice is a composite, not a real child

   Rendering: small-set, `#F7F3E8`, **never amber** — amber is reserved for the single accent word
   elsewhere in the Short `[B]`.

   **Why 38–45s and not the whole 26–45s Payoff** `[I]`: the script and voiceover brief place this
   line "in the safe zone during the Payoff beat." The Payoff runs 26–45s, but 26–38s is fully
   occupied by two research plates that may not move and may not be crowded (§7). The reframe
   sub-beat 38–45s is the first window inside the Payoff where the safe zone is clear, it runs seven
   seconds — long enough for a longer-than-Short-A line to be read at phone size — and it sits over
   two frames with **no person in them at all**, which is the correct place for a line about
   synthesis to appear. That is a concrete placement satisfying the upstream instruction, not a
   reinterpretation of it.
3. **Video description and every cross-post caption** carry the identical line `[B]`. Flagging it
   into the publish gate (§11) is this plan's job; authoring the caption copy is `social-repurpose`'s
   (Task 20). This plan does not write that copy, only confirms the line ships in it.

All three are unconditional regardless of which voice path the composite child ends up on — Voice
Design or the provenance-confirmed adult-performer library fallback. Both are synthetic; both
trigger disclosure `[B]`.

---

## 9. Loudness and mix

- **Target: −14 LUFS integrated on the finished mix.** `[T]` (YouTube's loudness normalization
  target; `loudness-and-mix.md`, confirmed identically in the voiceover brief). Applied once, to the
  whole mix, after both voices are cut together — **never per voice** (§3, step 4). Leave headroom;
  avoid clipping.
- **Voice peaks −3 to −6 dB.** `[I]`
- **Music ducking under voiceover: lead with −21 to −22 dB.** `[C] (Romayroh, Wox4Jt_2t6w; Roberto
  Blake, iaTavrWIGDM)` — the range the corpus ties directly to a retention complaint, naming loud
  music as one of the most common and most underestimated average-view-duration killers. The wider
  documented band of −12 to −18 dB is recorded as the alternate rather than silently dropped `[T]`.
  This Short leads with the tighter, corpus-cited figure, inherited unchanged from the voiceover
  brief.
- **Ducking behaviour:** the bed ducks under every spoken line and tracks the VO's presence rather
  than sitting at one flat level for 50 seconds; it rises toward its unducked level only in the
  inter-beat gaps. One-click auto-duck in the paid path, manual keyframes in the $0 path (§10).
- **The bed is out entirely for 0–3s** and fades in over ~300ms from 3.000s (§3, step 8). This is
  the only place in either Short where the music is absent rather than ducked, and it exists because
  the child's line is the differentiator `[I]`.
- **Music arc matches tone, not just fills silence** `[C] (Kallaway, i7upRL4H1FM)`. Three movements,
  matching the voiceover brief's own instruction that a bed treating the child's warm memory and the
  quote card's gravity identically will flatten the arc the Short is built around: warm and light
  from 3s; narrowing to quiet gravity under the re-hook and the 17–26s quote card; opening to relief
  from 38s through the Loop/CTA. Pausing the bed just before a key line is a legitimate device here
  `[C] (vidIQ, DiZnbihU4NM)` — the natural candidate is the half-second before "It was never yours."
- **SFX — two placements only.** A subtle hit on the Hook's opening motion, and a soft mark on the
  Re-hook's focus shift at 14s. **No SFX on any register cut** (§4, rule 2) and none on ordinary
  cuts, since the corpus explicitly warns against wall-to-wall stimulation `[C] (vidIQ,
  DiZnbihU4NM)`.
- **Prioritize audio over video** `[C] (Dan the creator, 9JE8-wM8zKc)` — on this Short especially,
  since the two-voice handoff is the element most likely to read as amateur if it is rushed. Do not
  let the thirteen keyframed still moves absorb the time budget at the expense of §3.
- **Check the final mix on phone speakers, not headphones** `[I]`. The handoff in particular:
  phone speakers roll off low end, which flatters a child-register voice and can make the narrator
  sound quieter than the meters say.
- **Rights note, last checkpoint before bake-in:** confirm the music source (YouTube Creator Music,
  a royalty-free library, or a cleared license) before the final render — Creator Music can carry a
  revenue-share/no-monetization condition unlike a direct license `[C] (Roberto Blake, SJsGBKGy4Do)`.
  Not settled as of this document; flagged as an open pre-render action.

---

## 10. Tool-stack execution — $0 path and paid path

Assets consumed (from Tasks 17/18, once actually rendered — **none exist yet**):

```
/shorts/
  /rgs-debut_nobody-asked-the-kid/
    script.md
    voiceover-brief.md
    visual-prompts.md
    assembly.md                              <- this document
    /assets/
      B-01_hook_i2v.mp4                      (Kling, 3.0s)
      B-02_setup-1.png
      B-03_setup-2-1886.png
      B-04_build-mason-ledger.png
      B-05_build-mason-car.png
      B-06_re-hook-rackfocus.png
      B-07_quote-climax_i2v.mp4              (Kling, 4.5s)
      B-08_quote-copybook.png
      B-09_payoff-research-1.png
      B-10_payoff-research-2.png
      B-11_payoff-research-3-1886.png
      B-12_payoff-reframe-1.png
      B-13_payoff-reframe-2.png
      B-14_loop-1886.png
      B-15_loop-focuspull.png
      vo_child_00_hook.wav                   (composite child, 1 render)
      vo_nar_01_setup.wav … vo_nar_07_loop-cta.wav   (narrator, 7 beat renders)
      room_tone.wav                          (125ms handoff bed, §3)
      music_bed.mp3
    B-16_cover.png                           (thumbnail, never composited into the timeline)
    nobody-asked-the-kid_final_1080x1920.mp4
```

Adapted from the corpus's `S<###>_<type><##>_<beat>.<ext>` convention `[I]` (`tool-stack.md`) to this
run's slug-based naming, since no `S<###>` id was assigned upstream; the convention's intent (one
folder per Short, typed and beat-labelled filenames) is preserved, and the `B-NN` ids match the
prompt sheet exactly so an editor can trace any timeline row to a file.

### $0 path

**Captions + edit: CapCut** `[T]` — free, mobile + desktop, the Shorts default. Import the fifteen
timeline assets in the §1 order. Build the beat-boundary cards manually — CapCut's auto-caption tool
is **not** used for body captions here, since the locked treatment is beat-boundary cards rather than
word-by-word karaoke; auto-caption would have to be disabled or hand-corrected away from its default
output. Apply the §2 push-in / scale / parallax moves via CapCut's keyframe tool on each of the
thirteen non-motion stills, honouring the Register A / Register B move-size split. Cut the two voice
stems per §3: trim the child's tail, drop in the 125ms room-tone clip, and level-match by ear against
the narrator's first beat. Duck the music manually with audio keyframes under each VO beat toward the
−21 to −22 dB lead figure. Normalize the final mix toward −14 LUFS with CapCut's volume/normalize
tools, by ear. Export 1080×1920. **Cost: $0/mo.**

**The $0 path's specific weak point on this Short, named rather than glossed** `[I]`: the free tier
has no loudness meter, so §3's ±1 LU short-term match across the two-voice handoff — the hardest
audio move in either debut Short — is done entirely by ear. Mitigation: cut the two stems
back-to-back on a single track first, listen to that cut in isolation at phone-speaker level, and
only then build the rest of the mix around it. If any single step in this pipeline justifies
upgrading, it is this one, not the captions.

**Schedule: YouTube Studio native**, following the publish sequence below.

### Paid path

**Edit: Premiere Pro** `[T]` — the Essential Sound panel's one-click auto-ducking, set to ≈−22 dB to
match the lead figure directly; the Remix tool to fit the music bed to 50 seconds without
pitch-shifting, since rate-stretch alters pitch `[C] (Roberto Blake, iaTavrWIGDM)`. Build the
beat-boundary cards as title/graphic layers on the timeline (Premiere has no auto-karaoke worth using
here, and the locked treatment is not karaoke anyway). Apply the §2 moves via keyframed
Transform/Scale/Position. **Loudness: Essential Sound or a LUFS meter plugin** for an exact −14 LUFS
integrated target, and — the paid path's real advantage on this Short — a **short-term LUFS readout
for the §3 ±1 LU voice match**, which the $0 path cannot measure. **Captions polish: Submagic** `[T]`
(~$23/mo annual) is available as an optional pass if the cards want animated polish, but is not
required by the locked treatment — flagged as optional, since the corpus's own reality check applies:
don't overspend on AI tools that are convenience luxuries rather than requirements `[C] (Romayroh,
nFT1xNDprIk)`. **Cost: ~$0–23/mo** on top of whatever Creative Cloud tier is already held.

**Schedule/analytics: YouTube Studio + vidIQ** `[T]` for the 24–48h CTR/AVD read against the channel
average `[C] (vidIQ, ZKsldrcO_fU)`.

### Publish sequence (both paths converge here)

**Upload unlisted first, let it fully process and index (transcription, frame analysis, guideline
checks), add all metadata — title, description carrying the AI-disclosure line and the Visek citation
text, tags, and the altered/synthetic-content disclosure toggle from §8 — then schedule public**
`[C] (Make Money Matt, RsAKa_WN1sU; Romayroh, Wox4Jt_2t6w)`. Do not let the video "sit" a day
post-schedule expecting an algorithmic boost — that is a documented myth `[C] (Nick Nimmin,
0l2g3Bujy1Y)`. **This Short and Short A are a pair and must not post the same day** — space them out
so the pacing does not read as spam-bot behaviour `[C] (Make Money Matt, tqCMF3mI9Pg)`. The
next-video bridge is held, not replaced with a generic closer, if Short B ships first `[C] (Nick
Nimmin, N42_LghZw8k)`.

---

## 11. QA gate + publish gate (run before scheduling)

### QA gate

- [ ] **Watched on a phone, sound off then on.** Sound-off confirms every beat's meaning survives on
  visual + on-screen text alone `[C] (Kallaway, i7upRL4H1FM)` — with specific attention to whether a
  muted viewer can tell the Hook line is a *child* speaking, since the caption card is the only
  channel carrying that; sound-on confirms the mix on phone speakers `[I]`.
- [ ] **The 3.0s handoff reads as a speaker change, not a volume jump** (§3, steps 3 and 9).
- [ ] **The 125ms gap is present and contains room tone, not digital silence** (§3, step 2).
- [ ] **No crossfade between the two voices; they still sound like two different people** (§3, step
  5).
- [ ] **First 2s stops the swipe** — the sheet is already up and the child is already mid-answer at
  frame one; no intro, no logo, no channel name, no filler `[C] (vidIQ, DiZnbihU4NM)`.
- [ ] **All eight register cuts are straight cuts** — no dissolve, no whip, no effect, no SFX, no
  music change at any of them (§4).
- [ ] **The Mason quote card renders as one unbroken card 17–26s**, attribution included from 17s,
  surviving the 21.5s image cut beneath it (§6).
- [ ] **Plate 2's figure is exactly as written, including "roughly"** (§7).
- [ ] **Plate 2 is legible across the 34s register cut into `B-11`** and does not move position
  during its hold (§7).
- [ ] **No text in the bottom 25% / right 15% exclusions** — confirm against the exported video, since
  captions drift after final render/crop `[I]`.
- [ ] **Loudness ≈ −14 LUFS on the final mixed export**, voice clear over the bed `[I]`.
- [ ] **No banned openers** ("in this video," "hey guys") — absent from the script; verify neither VO
  take drifted back toward one `[C] (vidIQ, UCrC5B3Soyc; Nick Nimmin, 2vkX1X1K3WM)`.
- [ ] **No face resolves at any focus setting, including after the Loop/CTA focus pull at 47.5s**
  `[B]`.
- [ ] **Muted clay `#C1543A` never touches skin in either register**, including after grading `[B]`.
- [ ] **"It was never yours" is present, uncut, inside the 17–26s beat** `[B]`.
- [ ] **The `B-16` cover passes the 120px squint test.** If it fails, enlarge and brighten the
  background figure — **never sharpen it**, which destroys the motif `[I]`.

### Publish gate

- [ ] **Altered/synthetic-content disclosure set at upload** (§8, placement 1) — mandatory, not
  discretionary; disclose or risk demonetization / YPP rejection `[C] (Romayroh, G9LfE3k-IEI)`.
- [ ] **On-screen disclosure line present 38–45s**, exact wording, small-set `#F7F3E8`, never amber
  (§8, placement 2).
- [ ] **Description carries the identical disclosure line** (§8, placement 3).
- [ ] **The composite-child clause is present.** "Composite, not a real child" is an *addition* to
  the standard synthetic-voice disclosure, never a substitute for it `[B]`.
- [ ] **No real child's voice anywhere in the chain** — the child track is Voice Design (or the
  provenance-confirmed adult-performer library fallback), never IVC/PVC of any real minor's
  recording `[B]`.
- [ ] **Made-for-kids OFF** `[C] (One Person Business, eVePkmCQV5c)`.
- [ ] **Studio "restrictions" reads NONE** `[C] (Make Money Matt, 10yFPNpnjY0; Dan the creator,
  JPTr40J3WXU)`.
- [ ] **Not a duplicate template/script of a recent Short** — confirmed distinct from Short A, whose
  payoff is a decision the parent makes where this one is a question the parent asks `[C] (Romayroh,
  KbUXzJ55eJk / Wox4Jt_2t6w)`.
- [ ] **Pinned comment / end card points at Short A (`decline-the-next-level`) only once it is live**;
  if this Short ships first the bridge line is held, not replaced with a generic closer `[C] (Nick
  Nimmin, N42_LghZw8k)`.
- [ ] **R10 edition spot-check** — re-check the determinant/factor counts against the current
  `rgs-r10-science-of-fun.md` (edition `v2-2026-07-18`) before ship. Carried forward from the script
  and the prompt sheet as an open pre-publish action, **not discharged at this stage**
  `[RESEARCH: Visek et al. 2015]`.
- [ ] **Music rights source confirmed** before final bake (§9).

---

## 12. Gaps flagged honestly

- **The 50-second runtime is outside the templates' assumed band, and the corpus cannot rule on
  eligibility.** `pacing-and-editing.md`'s own gap flag applies with more force here than on Short
  A's 45s: there is **no corpus finding on current YouTube Shorts duration-eligibility limits**, and
  it is outside the 2026-07-23 `[T]` sweep. **Verify current Shorts length eligibility on YouTube's
  own help pages before locking this runtime** — do not infer it from Short A shipping at 45s.
- **The safe zone is `[T-unverified]` throughout this document** — middle ~60% vertical, clear of the
  bottom 25% and right 15%, carried unchanged through three upstream stages and not independently
  re-verified here. Verify on a real phone before this template is treated as final.
- **Caption density is a genuine corpus split (§5), resolved by brand override, not by corpus
  consensus** — presented as a judgment call, not silently picked.
- **No card copy exists for the Setup, Re-hook or Loop/CTA windows (§5)**, and the missing re-hook
  card is a departure from a `[C]` rule `[C] (Nate Black, c6X-Ywy3yVU)`. This plan does not invent
  copy for an A3 Short; the gap is routed back to `shorts-scripting`.
- **The Register B motion restriction (§2, §4) is `[I]` with the corpus silent.** The corpus's
  keyframe-stills findings do not distinguish media, and nothing in it addresses animating a
  painterly asset. The ≤8%-scale, no-parallax rule is this skill's own judgment and a reader is
  entitled to disagree with it.
- **The 34s plate-over-Register-B decision (§4, §7) is a knowing tension with a `[C]` rule** and is
  the single item most worth watching in the cold read.
- **Register-alternation count disagrees with the prompt sheet** — eight by adjacency here, nine
  stated there (§4). Immaterial to Gate C, recorded rather than reconciled by editing an upstream
  file.
- **`--sref` codes and seeds are placeholders upstream.** `SREF-RGS-A-02` and `SREF-RGS-B-01` have
  never been harvested and no seeds are recorded. Nothing in this timeline can be assembled until
  they are, and this plan's shot IDs point at files that do not yet exist.
- **Gate B (adversarial art-direction review) never ran** upstream because nothing is rendered. It is
  still open and belongs before render, not before edit.
- **Font family is not fixed by this plan** — the visual system reserves "one bold sans-serif" without
  naming it; pick one consistent with the brand kit at composite time, channel-wide, not per-Short
  `[I]`.
- **Motion move sizes and durations in §2 are this skill's application of the corpus's
  push-in/parallax/whip-cut principles to this specific still pool, not corpus findings in
  themselves** — the same caveat the worked example carries.
- **The corpus is silent on this niche and on two-voice Shorts.** It is creator-education material
  with no view into youth-sports-parent content `[REF]` (scan, Method §6), and it contains no finding
  on child-voiced narration, cast changes mid-Short, or dual-register visual grammar. Every judgment
  in §3 and §4 is `[I]` or `[B]`. No corpus line was stretched to cover subject matter it never saw.

---

## Constraints that survive to publish (carried verbatim, not re-derived)

1. **The child is a composite, always.** No real child is filmed, sourced, quoted, interviewed or
   otherwise exposed in this Short — the voice is written, not recorded from a real kid, and must
   never be presented or implied to be a real interviewed child.
2. **AI/synthetic-media disclosure applies.** The synthetic child voice is disclosed as AI/altered
   content per the brand's Do/Don't rule, on the upload and wherever the platform provides a
   disclosure control.
3. **Research phrasing:** keep the two tiers straight (81 determinants → 11 factors; winning is not
   one of the 11 and sits *roughly* 40th of the 81); name the study on-screen and in voiceover ("a
   2015 George Washington University study"); scope is youth soccer players, coaches and parents —
   don't generalize the measured population; association, never causation. Ship the narrowed claim
   ("winning wasn't in the top tier of what kids named"), never "your kid doesn't care about
   winning."
4. **Register:** no quit-and-overdose framing, no elite-outcome resolution, and the child's
   disappointment must never read as an accusation against the parent — the villain is a system with
   no field for the child's answer. End on relief and agency.
5. Cited figures are as of the **2026-07-18** corpus edition — spot-check against the current
   `rgs-r10-science-of-fun.md` before the Short ships.

Plus, added upstream and binding here: the two-voice boundary at 3.0s; the "It was never yours"
clause as uncuttable; the anonymous-presence rule holding through the Loop/CTA focus pull; the 120px
squint-test fix direction (enlarge and brighten, never sharpen); the quote card's verbatim status;
plate 2's exact wording including "roughly"; and the next-video bridge publish gate.

---

## Downstream

This edit plan, once the described assets exist and are assembled per §1–§10 and pass the §11 gates,
is the direct input to **`social-repurpose`** (Task 20), which turns the finished Short plus its
script and packaging into multi-surface post copy — including the description and cross-post
AI-disclosure line this plan specifies in §8 but does not author.
