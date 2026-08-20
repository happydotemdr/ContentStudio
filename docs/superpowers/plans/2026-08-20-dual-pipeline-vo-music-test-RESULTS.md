# Test Record — Dual-Pipeline VO+Music A/B Test (2026-08-20)

Dated evidence record for a real render session run earlier today against two render
workspaces in this worktree:

- **Track A** — `stitcher/renders/stop-over-specialization-in-youth-sports-multiseg-test/`
  (`stitcher`'s own multi-segment/preconditioned pipeline)
- **Track B** — `stitcher/renders/stop-over-specialization-in-youth-sports-native-test/`
  (the separate `native-pipeline` package, "zero VO processing" by design)

This is a primary evidentiary record, not a skill reference: every numeric claim below was
checked against an on-disk artifact where the artifact still exists, and this doc says so
explicitly where it doesn't. **Read "What this test does NOT show" before the numbers below** —
this session's headline framing ("multi-segment beat single-take") was a confounded comparison,
corrected here.

## Finding 1 — Number-respelling fixes a real TTS stutter

Character-level `/with-timestamps` alignment on "2,556" showed a `5` rendering at 603ms and a `6`
at 441ms — 3–4x the ~150–175ms baseline every other digit in the same take showed (verified
against "2,300" elsewhere in the identical take, which rendered cleanly at 117–174ms/digit).
Respelling as "two thousand, five hundred fifty-six" produced zero anomalies (full-take character
scan: 0 characters over 250ms outside natural punctuation pauses). A milder version of the same
artifact was found on "2026" (a `0` at 603ms); respelled to "twenty twenty-six," also clean.

`[I]` This project's own extrapolation, not corpus-cited: treat a >250ms single-character gap in a
`/with-timestamps` scan as a stutter signal worth respelling, generalized from this one pair of
observations rather than a corpus finding.

## Finding 2 — `duck_db`, not `gain_db`, is the corpus's cited "ducked under vocals" figure

Confirmed by reading `stitcher/stitcher/audio.py`'s own comments: `conform_gain` uses `gain_db` as
the un-ducked baseline, and the envelope lands "exactly on `duck_db` relative to voice" at a duck
breakpoint. The `stop-over-specialization` render-spec had `duck_db: -29.0` — 7–8dB below the
corpus's own cited −21/−22dB band — while `gain_db: -22.0` (the un-ducked baseline, irrelevant for
a near-continuously-speaking take) was incidentally close to the band and got blamed instead.

Direct operator listening feedback on two finished masters using these exact numbers: "totally
washed out nearly inaudible in the background."

Independent corroboration:
- `docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md`'s Problem
  section, written before this session, already root-caused the same `-22`/`-29` pair as leaving
  the bed "at roughly -42 LUFS integrated for ~94% of the runtime — effectively inaudible" for the
  single-take case (verified: that doc's Problem section, lines 12–15, reads exactly this).
- `stitcher/renders/do-less-sold-as-win-more/render-spec.json` — an existing, different Short in
  this same repo — already uses `gain_db: -14.0` / `duck_db: -21.0` (verified: lines 694–695 of
  that file), the exact corrected pair this plan proposes.

## Finding 3 — `native-pipeline`'s documented "zero VO processing" accepted risk fired in 3/3 real attempts

`docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md` ("Decisions"
section, verified lines 67–72) explicitly predicted this failure mode in advance: "an unusually
hot take… can require enough gain… to overshoot the -1 dBTP delivery ceiling… This mode accepts
that failure mode deliberately." Its "Open risks" section (verified lines 416–421) states: "If
either fires often in practice, that's a signal to revisit 'zero processing,'" not something the
design resolves in advance.

This session ran Track B three times on real takes. Verified against on-disk `loudnorm_pass2.json`
and the render logs in `stitcher/renders/stop-over-specialization-in-youth-sports-native-test/logs/`
(see methodology note below — this run overwrote takes 1 and 2 in place, so recovery of their raw
JSON was partial, not total, once this doc's author actually looked):

| Take | `input_tp` (dBTP) | `input_i` (LUFS) | `normalization_type` | Source |
|---|---|---|---|---|
| 1 | **-1.21** | -23.13 | dynamic | Transcribed from this plan's own prior "Evidence" text — take 1's `loudnorm_pass2.json` no longer exists in `work/draft/` or `work/final/` (both were overwritten by later takes). Corroborated non-authoritatively by `logs/2026-08-20T18-50-27Z_final.log` (still on disk), which shows the same `input_i`/`input_tp` pair. |
| 2 | **-1.43** | -23.55 | dynamic | Re-read live from `work/draft/loudnorm_pass2.json`, which — contrary to this task's starting assumption that `work/draft/` and `work/final/` both hold only the most recent (3rd) take — actually still holds take 2's numbers, not take 3's. `target_offset: 0.93`. |
| 3 | **-2.08** | -24.28 | dynamic | Re-read live from `work/final/loudnorm_pass2.json` (the current, most recent render). `target_offset: 1.48`. |

All three requiring roughly +9 to +10dB of loudness-matching gain to reach target, overshooting
the -1 dBTP delivery ceiling every time (`EXIT_RENDER=2`, no finished video produced any of the
three times). The `EXIT_RENDER=2` figure and "no finished video" claim are transcribed from this
plan's own prior "Evidence" text, not independently re-confirmed here: the on-disk logs under
`logs/` are per-step ffmpeg command logs (written via `ffmpeg.run(cmd, log_path)`), not a capture
of the CLI process's own stderr, so they contain no `EXIT_RENDER`/`LoudnormNotLinearError` text to
check either way. What *is* independently verified is the code path that would produce that
outcome: `stitcher/stitcher/cli.py:42-46` defines `EXIT_RENDER = 2`, and `cli.py:181-184` returns
exactly that code — printing `"render failed: {exc}"` to stderr — when `audio.LoudnormNotLinearError`
is raised, which is exactly the gate at `stitcher/stitcher/audio.py:532` that fires whenever pass
2's `normalization_type != "linear"` for a non-preview render. Every `input_tp` in the table above
is well above what take-1's numbers alone would need to trip that gate.

Two independent attempted fixes — loosening the true-peak ceiling; retuning VO `stability`/`style`
to reduce crest factor — both failed to move the needle.

**This is confirmation of an already-known, already-accepted risk meeting its own stated revisit
threshold.** It is not a new discovery that some other pipeline is broken, and it says nothing
about `stitcher`'s own preconditioned single-take chain — see the next section.

### Methodology note — why `loudnorm_pass2.json`, never `loudnorm_pass1.json`

Pass 1 runs without `linear=true` and reports `"normalization_type": "dynamic"` **by construction
on every render, including passing ones** — verified directly: Track A's own passing render's
`work/final/audio/loudnorm_pass1.json` also reads `"normalization_type": "dynamic"`
(`input_i: -26.26`, `input_tp: -13.80`, `output_i: -14.15`, `output_tp: -1.64`), even though that
render's pass-2 gate (per `stitcher/stitcher/audio.py:532`) is what actually determines pass/fail.
Every number quoted in this doc for Track B failures is from `loudnorm_pass2.json`, never pass 1.

## What this test does NOT show

**1. "Multi-segment beats single-take" was a confounded comparison, not a validated result.**
This session's Track B ran `native-pipeline` — a separate package that was designed, by its own
spec (`docs/superpowers/specs/2026-08-20-native-single-generation-render-mode-design.md`), to skip
VO processing entirely. That design doc already predicted and accepted the exact overshoot failure
this session reproduced 3/3 times; Finding 3 above is that prediction coming true, not evidence
that single-take VO is inherently worse than multi-segment VO. `native-pipeline` is **not** the
same implementation `single-take-architecture.md`'s `[P]` pin describes. That pin covers
`stitcher`'s own preconditioned single-take chain (`vo_split.py` → `precondition.condition_clip` →
`audio.build_audio`), which is a different code path, was untouched by anything in this session,
and passed all 5 of its own validation criteria the one time it was run for real
(`docs/superpowers/plans/2026-08-19-single-take-vo-pipeline-RESULTS.md`). `single-take-architecture.md`
is not being superseded or contradicted by anything in this doc.

**2. The duck-depth diagnosis initially had `gain_db` and `duck_db` backwards.** The level that's
actually "ducked under vocals" — the figure the corpus's −21/−22dB citation describes, and the one
that governs audibility for a take speaking almost continuously — is `duck_db`, not `gain_db`.
`gain_db` is the *un-ducked* baseline, which only matters during real silence. The original spec's
`duck_db: -29.0` sat 7–8dB below the corpus's own number, which is what actually produced the
"washed out" masters; `gain_db: -22.0` was coincidentally close to the corpus band and was blamed
by mistake. See Finding 2 above for the corrected pair and its precedent elsewhere in this repo.

## Deliverables from this session

No finished Track B video from any of the 3 native-pipeline attempts (`EXIT_RENDER=2` all three
times — see Finding 3). Track A's `v02` render passed QA outright; its full report is at
`stitcher/renders/stop-over-specialization-in-youth-sports-multiseg-test/out/stop-over-specialization-in-youth-sports-multiseg-test_v02_qa.md`,
sanity-checked verbatim against this doc's summary numbers below.

| Check | QA report | This doc |
|---|---|---|
| `integrated_loudness` | -13.9 LUFS vs -14.0 target | -13.9 LUFS |
| `true_peak` | -1.5 dBTP vs -0.15 dBTP ceiling | -1.5 dBTP |
| `duck_depth` | expected -7.0 dB, worst measured -7.0 dB | -7.0 dB |

All three match exactly — no transcription drift found.

## Status

Evidentiary record only. No downstream skill doc has been changed by this file; Tasks 2–5 of the
parent plan (`2026-08-20-bake-in-dual-pipeline-test-learnings.md`) are what bake these corrected
findings into skill references, and Task 6 is what re-validates with a real render. This doc is
what they cite by path.
