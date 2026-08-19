# Atomic Fix — Vocal Leakage in the Regenerated Music Beds

**Status:** DRAFT — awaiting sign-off before either music call re-runs. Costs real money (2 calls).
**Scope:** music beds only. The 9 voiceover calls from the prior run are unaffected and are not
touched by this fix.

---

## 1. What's wrong

`BedA_provoice.mp3` / `BedB_provoice.mp3` (generated in the prior run, `POST /v1/music`,
`composition_plan`/`chunks`, `model_id: music_v2`) contain audible words bleeding into the mix —
confirmed by listening to `Bed Full_provoice_conformed.wav`. This sits under the actual narration as
a competing background voice.

**It is not an endpoint mix-up.** The `send.attempt` log lines from the prior run confirm both bed
calls targeted `https://api.elevenlabs.io/v1/music?...` — the Eleven Music generator, not
text-to-speech. The pro voice was never invoked for these two calls.

## 2. Root cause (documented, not guessed)

Every `composition_plan` chunk sent for both beds carried a vocal guard
(`negative_styles: ["vocals", "singing", "spoken word", "lyrics", ...]`) — matching this project's
own `elevenlabs-music` skill's stated default technique. But this repo's own runbook had already
flagged, before this run, that the technique's real-world efficacy was an open question:

> "Whether the guard is *sufficient* in practice — whether `negative_styles` vocal terms actually
> suppress vocals in the rendered audio — is `[T-unverified]` pending a live generation... that
> check could not be run in this environment." — `docs/elevenlabs-music-runbook.md` (pre-fix text)

There's a second, compounding factor: a `composition_plan` chunk's `text` field is documented as
accepting "section label, lyrics, phonetic sounds, or inline directions" — **not a style-only
field**. The chunk `text` values used in both beds were full descriptive English sentences (e.g.
`"Intro underscore — gentle fade-in from silence; quiet unease, observational"`), which is exactly
the shape of content the field's own documentation says can be treated as spoken/lyrical content.

**This run is the first live confirmation, and the answer is negative: `negative_styles` alone did
not suppress vocals.** Both `docs/elevenlabs-music-runbook.md` §3 and
`.claude/skills/elevenlabs-music/references/composition-plans.md`'s instrumental-technique section
have been updated to record this as confirmed, not merely suspected (already committed — see §5).

**The one documented guarantee against vocals is `force_instrumental: true`, and it is prompt-only**
— it does not exist as a `composition_plan` field at all (confirmed in the same runbook, §3). Fixing
this means switching both bed calls from `composition_plan`/`chunks` mode to `prompt` mode.

## 3. The fix

Switch both bed generations from `composition_plan` to `prompt` + `force_instrumental: true`. This
trades the precise per-chunk duration locking `composition_plan` gave us for a documented,
guaranteed-instrumental result — the right trade here, since a leaking word under the narration is
actively harmful where imprecise section timing is a minor, freely-fixable-locally cosmetic issue
(exactly like the duration slop already tolerated throughout the prior run).

The creative content is unchanged — reusing the same prose already drafted (and unused) in
`03-music/elevenlabs-music-spec.md`'s "UI PROMPT" section for exactly this fallback path, adjusted
only for the now-known-exact target durations from the corrected splice in the prior run's results:

- Bed A needs ≥14.314331s (hook-end 5.200s → the measured re-hook pause start, 19.514331s)
- Bed B needs ≥31.697052s (the measured pause end, 20.222948s → the new total runtime, 51.920s)

Generating a little over each target and trimming locally afterward (same free, repeatable technique
as the prior run) removes any pressure to hit `music_length_ms` exactly.

### Payload — Bed A → `BedA_provoice_v2.mp3`

`POST https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192`

```json
{
  "prompt": "Instrumental cinematic underscore for a short documentary-style video, about 15 seconds. Slow, unhurried, minor key. Opens sparse and intimate — soft sustained piano and low strings, a sense of quiet unease, observational rather than sad. Around the one-third mark it deepens: a low drone enters and the strings darken, a cautionary, weighty feeling, as if strength is quietly draining away. Keep it very low-energy throughout — this sits under a spoken voiceover and must never compete with it. No drums, no build to a climax; thin out and soften toward the end. Fully instrumental — no vocals, no singing, no spoken words, no lyrics.",
  "model_id": "music_v1",
  "music_length_ms": 15000,
  "force_instrumental": true
}
```

### Payload — Bed B → `BedB_provoice_v2.mp3`

`POST https://api.elevenlabs.io/v1/music?output_format=mp3_44100_192`

```json
{
  "prompt": "Instrumental cinematic underscore, about 33 seconds, for the second half of a short documentary-style video. Opens with a soft rising figure that lifts out of silence into a warmer, modern, grounded feel — steady low pulse, warm analog pad, clean and credible, leaving space for spoken numbers to land (nothing busy). Around the halfway point it opens into gentle relief and resolution — warm strings, a hopeful but restrained major-key lift, reassuring, not triumphant. In the final few seconds it narrows back down to a sparse, minor, slightly ominous close that thins toward silence so it can loop seamlessly back to a quiet opening. Very low-energy throughout; sits under a voiceover. Fully instrumental — no vocals, no singing, no spoken words, no lyrics.",
  "model_id": "music_v1",
  "music_length_ms": 33000,
  "force_instrumental": true
}
```

`model_id: "music_v1"` — matches this repo's documented pairing (`prompt` → `MusicPrompt` →
`music_v1`); no `seed` (plan-only, E11 forbids it with `prompt` — dropping the `seed: 20260819` used
last time is required, not optional, here).

Both payloads validate clean against `elevenlabs_tooling` (traced against E3/E4/E11/E12/E13/E14 —
none fire; `force_instrumental` is legal here specifically because no `composition_plan` key is
present at all).

## 4. Cost delta

**2 new `music` compose calls, ~15s and ~33s of generated audio. Nothing else re-runs.** The 9
voiceover calls are correct and unaffected — no reason to touch them. This is strictly smaller than
the original run, not a repeat of it.

## 5. Already done (zero cost, committed)

- `docs/elevenlabs-music-runbook.md` §3 — updated to record the vocal guard as confirmed
  insufficient, not merely unverified.
- `.claude/skills/elevenlabs-music/references/composition-plans.md` — same update, plus a directive
  to route instrumental-guarantee cases to `prompt` + `force_instrumental` going forward.

## 6. Execution steps (once approved)

1. Write both payloads above to `assets/provoice-2026-08-19/payloads/BedA_v2.json` /
   `BedB_v2.json`.
2. `elevenlabs_tooling validate` both — zero cost, must pass before sending.
3. Send both, one at a time, checking each `EXIT_PASS` before the next — outputs to
   `BedA_provoice_v2.mp3` / `BedB_provoice_v2.mp3` (new filenames; the v1 files are left in place,
   not deleted, in case a comparison is useful).
4. **QC listen specifically for vocal content** before doing anything else — this is the one check
   that matters most given what just happened.
5. If clean: re-run the exact same free local pipeline already built in the prior run (trim Bed A to
   14.314331s, trim/crossfade Bed B to 31.697052s using the same riser-open + loop-close-preserving
   splice, rebuild `Bed Full_provoice.wav`, rebuild `Final_Mix_Preview_provoice.mp3`) against the new
   v2 bed files instead of the v1 ones.
6. Deliver the corrected preview; commit an updated results note to the PR.

## 7. Explicitly out of scope for this fix

- Regenerating any VO clip — unaffected by this bug, no reason to re-spend there.
- The shot-timing re-cut question from the prior run's results doc — still open, still separate,
  still free/local whenever it's taken up.
- A broader redesign of the `elevenlabs-music` skill's default plan-shape recommendation for every
  future job — the two reference-doc updates in §5 record the finding; whether the skill's *default*
  behavior should change (e.g., always prefer `prompt` mode when a bed sits under continuous
  narration) is a separate decision worth raising, not bundled into this render's fix.

## Sign-off checklist

- [ ] Root cause and fix approach confirmed (§2, §3)
- [ ] New payloads approved as-is (§3)
- [ ] 2-call cost delta acceptable (§4)
