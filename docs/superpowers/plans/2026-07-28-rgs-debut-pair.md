# RGS Debut Pair — Automated Full-Pipeline Run: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce two validated, asset-ready RaisingGoodSports Shorts packages — the channel's first published content — by running the full ContentStudio pipeline end to end with every decision made autonomously.

**Architecture:** A one-off reference scan (10 transcribed YouTube videos) yields two sparks. Each spark goes through the seven `pipeline.yaml` stages. A visual system is locked once, before either visual stage, so the two Shorts share a still pool. Three fresh persona agents then cold-read both finished packages, and their findings route back to the owning stage for at most two revision rounds.

**Tech Stack:** Python 3.14 venv (`yt-dlp`, `youtube-transcript-api`, `requests`); the ten ContentStudio skills under `.claude/skills/`; local corpora under `output/thinkers/` and `output/youth-sports/`.

## Note on task shape

Most tasks here produce a **document**, not code. There is no unit test to run. The
equivalent gate is the **Acceptance check** in each task: a set of concrete, verifiable
assertions about the artifact that must all hold before committing. Treat a failed
acceptance check exactly like a failing test — fix the artifact, re-check, then commit.
Task 2 is the only task containing real code, and it is throwaway.

## Global Constraints

Every task's requirements implicitly include this section.

- **FamilyBrain firewall (absolute).** No `brain_*` MCP tool is called at any point. The
  thinkers and youth-sports corpora are the local files under `output/thinkers/` and
  `output/youth-sports/`. Never add a FamilyBrain remote, submodule, or path reference.
- **Provenance markers are mandatory.** Every normative line in a pipeline-skill artifact
  carries `[C]` / `[I]` / `[T]`. Tool-specialist artifacts may additionally carry
  `[T-unverified]`. Grounding artifacts use `[THINKER: Name, Work, quotability]` and
  `[RESEARCH: Author Year, quality rating]` instead. **An unmarked normative line is a
  bug.**
- **Anti-generic guarantee.** If the corpus does not cover something, the artifact says so
  and flags it. Never substitute generic content-creation, editing, or social-media advice.
- **Autonomy rule.** Every skill's non-interactive fallback is taken — proceed with the
  top-ranked option and record the rest in an "Alternates considered" section. Never stop
  to ask for a human pick.
- **Brand hard rules** (from `output/raisinggoodsports-brand-definition.md`):
  - The villain is **the system**, never the parent. Never blame, shame, or rage-bait.
  - Banned lexicon: "bad parent," "you're ruining your kid," "if you really cared…,"
    "hack," "crush it," "game-changer," "the secret to," and parent-blaming clickbait
    absolutes.
  - Spine: **hook → turn → payoff → reframe.** One idea per Short. End on relief and agency.
  - The first 2 seconds carry the whole video — visual *and* verbal.
  - **Package before you script.** Title and thumbnail concept first, every time.
  - `quote-ok` thinkers may be quoted verbatim on-screen. **`paraphrase-caution` thinkers
    are paraphrased in voiceover only — never placed on a quote card.**
  - Every health or injury claim is attributed to its named source **on-screen and in
    voiceover** ("a 2024 AAP clinical report found…"). The narrator is a commentator,
    never a health authority.
  - Disclose AI / synthetic media.
- **Palette (exact values):** ground deep teal-ink `#0E3B43`; accent warm amber `#F2A541`;
  type warm off-white `#F7F3E8`; sparing muted clay `#C1543A` (for "the system" framing
  only, never for blame). Two to three colors per image, max. Text/ground contrast ≥4.5:1.
- **Shorts safe zone (working rule, unverified):** keep all text inside the middle ~60%
  vertically, clear of the bottom 25% and the right 15%.
- **Loudness target:** −14 LUFS integrated.
- **Archetype assignment:** Short A = **A1** ("the thinker who saw it coming"). Short B =
  **A3** ("what the kid hears"). **A2 is excluded from the debut** — it routinely cites
  injury/health data and YouTube's inauthentic-content policy bars AI personas presenting
  as health authorities.
- **Repurpose surfaces (exactly six per Short):** YouTube Shorts, TikTok, Instagram Reels
  (one identical 9:16 export, per-platform copy only); Bluesky, Threads, X (text-only).
- **No assets are generated.** This run ends at *ready to generate*. No images, no audio,
  no video, no rendered thumbnails, no ElevenLabs credits consumed.
- **Where things live:** working scratch in `runs/rgs-debut-<ts>/` (git-ignored per
  `.gitignore:20`); committed deliverables in `rgs-briefs/` (the git-tracked production
  ledger); raw transcripts in `output/rgs-reference/2026-07-28/` (git-ignored).
- **Naming for committed artifacts:** `rgs-briefs/2026-07-28-<slug>-<stage>.md`, matching
  the existing `2026-07-25-let-kids-play-act-specialization-*` set.

## File Structure

**Created (committed, in `rgs-briefs/`):**

| File | Responsibility |
|---|---|
| `2026-07-28-rgs-debut-reference-scan.md` | 10-row reference table + white-space analysis |
| `2026-07-28-rgs-debut-sparks.md` | Two sparks, archetypes, dedupe record |
| `2026-07-28-rgs-debut-visual-system.md` | The locked system binding both Shorts |
| `2026-07-28-<slug-a>.md` | Grounding brief, Short A (brief front-matter schema) |
| `2026-07-28-<slug-b>.md` | Grounding brief, Short B (brief front-matter schema) |
| `2026-07-28-<slug-a>-concept-brief.md` … `-script.md`, `-voiceover-brief.md`, `-visual-prompts.md`, `-assembly.md`, `-social-repurpose.md` | Short A stage artifacts |
| `2026-07-28-<slug-b>-*.md` | Short B stage artifacts (same six) |
| `2026-07-28-rgs-debut-validation.md` | Persona panel report + revision record |

**Created (git-ignored):** `runs/rgs-debut-<ts>/` working scratch;
`output/rgs-reference/2026-07-28/<videoId>.md` transcripts.

**Created (throwaway, scratchpad only):** `fetch_reference.py`.

**Modified:** nothing. No skill, no `pipeline.yaml`, no `.gitignore` change.

`<slug-a>` and `<slug-b>` are fixed in Task 5 and used verbatim thereafter.

---

### Task 1: Environment preflight and run scaffold

Nothing touches the network until the toolchain is proven present. Neither `yt-dlp` nor
`youtube-transcript-api` is currently installed and there is no `.venv`.

**Files:**
- Create: `.venv/` (git-ignored)
- Create: `runs/rgs-debut-<ts>/` (git-ignored)
- Create: `output/rgs-reference/2026-07-28/` (git-ignored)

**Interfaces:**
- Produces: `RUN_DIR` — the absolute path to the run scratch folder, used by every later
  task. `REF_DIR` — the absolute path to `output/rgs-reference/2026-07-28/`.

- [ ] **Step 1: Create the venv and install dependencies**

```bash
cd /c/Projects/ContentStudio && python -m venv .venv && ./.venv/Scripts/python.exe -m pip install --quiet --upgrade pip && ./.venv/Scripts/python.exe -m pip install --quiet -r requirements.txt
```

- [ ] **Step 2: Verify the toolchain**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -m yt_dlp --version && ./.venv/Scripts/python.exe -c "import youtube_transcript_api, requests; print('deps ok')"
```

Expected: a yt-dlp version string (e.g. `2025.x.x`) followed by `deps ok`.
If this fails, **stop and report** — per the spec's risk table, an ungrounded scan is not
an acceptable fallback.

- [ ] **Step 3: Verify network reach to YouTube**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -m yt_dlp --skip-download --print "%(title)s" "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1 | tail -3
```

Expected: a title string, not a network error. If it fails with a network error, stop and
report.

- [ ] **Step 4: Create the run scaffold**

```bash
cd /c/Projects/ContentStudio && RUN_DIR="runs/rgs-debut-$(date +%Y%m%d-%H%M%S)" && mkdir -p "$RUN_DIR"/{00-scan,06-validation} "$RUN_DIR"/short-{a,b}/{00-grounding,01-ideation,02-scripting,03-voiceover,03-visual,04-assembly,05-repurpose} output/rgs-reference/2026-07-28 && echo "$RUN_DIR" > "$RUN_DIR/../.rgs-debut-current" && echo "RUN_DIR=$RUN_DIR"
```

- [ ] **Step 5: Verify the scaffold and that nothing is stageable**

```bash
cd /c/Projects/ContentStudio && find runs -type d -name "rgs-debut-*" | head -1 && git status --porcelain
```

Expected: the run directory path, and `git status --porcelain` prints **nothing** — both
`runs/` and `output/` are ignored, so this task creates no commit. That is correct.

**Acceptance check:**
- `yt-dlp` reports a version and `youtube_transcript_api` imports.
- A live YouTube metadata fetch succeeds.
- The run scaffold exists with all 16 subdirectories.
- `git status --porcelain` is empty.

- [ ] **Step 6: No commit**

This task intentionally produces no commit — every path it creates is git-ignored. Record
`RUN_DIR` for later tasks and move on.

---

### Task 2: Reference discovery — build the verified candidate list

**Files:**
- Create: `<scratchpad>/fetch_reference.py` (throwaway, never committed)
- Create: `<RUN_DIR>/00-scan/candidates.json`

**Interfaces:**
- Consumes: `RUN_DIR`, `REF_DIR` from Task 1.
- Produces: `candidates.json` — a JSON array of exactly 10 objects, each
  `{"video_id": str, "title": str, "channel": str, "url": str, "views": int,
  "upload_date": "YYYYMMDD", "format": "short" | "long", "why_relevant": str}`.
  Task 3 reads this file.

**Discovery seeds (use verbatim):** `travel sports cost parents`, `early specialization
youth sports`, `why kids quit sports`, `sideline parents youth sports`, `youth sports
burnout`, `pay to play youth sports`.

**Selection rules:**
- 5 with `"format": "short"` — uploaded within the last 90 days (on or after 2026-04-29),
  high view count relative to their channel.
- 5 with `"format": "long"` — relevant youth-sports or parenting videos and podcast
  segments, any recency.
- **Exclude:** generic sports highlights, athlete training/technique content, and generic
  parenting content with no youth-sports-culture angle.
- Every entry must be about youth-sports *culture* — cost, status, specialization,
  burnout, dropout, parent behavior.

- [ ] **Step 1: Search for candidates**

Use `WebSearch` against the six seeds to surface named videos and channels, then confirm
each candidate's real metadata with `yt-dlp`. Do not trust a search snippet's view count
or date — `yt-dlp` is the source of truth for both.

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -m yt_dlp --skip-download --print "%(id)s|%(title)s|%(uploader)s|%(view_count)s|%(upload_date)s|%(duration)s" "ytsearch20:travel sports cost parents" 2>/dev/null
```

Repeat per seed. `duration` ≤ 60 means `"format": "short"`; longer means `"long"`.

- [ ] **Step 2: Verify each shortlisted video individually**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -m yt_dlp --skip-download --print "%(id)s|%(title)s|%(uploader)s|%(view_count)s|%(upload_date)s|%(duration)s" "https://www.youtube.com/watch?v=<VIDEO_ID>"
```

Expected: one pipe-delimited line per video, with real numbers.

- [ ] **Step 3: Write `candidates.json`**

Write exactly 10 verified entries. `why_relevant` is one sentence stating the
youth-sports-culture angle — not a summary of the video.

- [ ] **Step 4: Validate the file**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import json,sys,pathlib
p=sorted(pathlib.Path('runs').glob('rgs-debut-*/00-scan/candidates.json'))[-1]
d=json.loads(p.read_text(encoding='utf-8'))
assert len(d)==10, f'expected 10, got {len(d)}'
shorts=[x for x in d if x['format']=='short']; longs=[x for x in d if x['format']=='long']
assert len(shorts)==5, f'expected 5 shorts, got {len(shorts)}'
assert len(longs)==5, f'expected 5 long, got {len(longs)}'
assert len({x['video_id'] for x in d})==10, 'duplicate video_id'
for x in shorts: assert x['upload_date']>='20260429', f\"{x['video_id']} too old: {x['upload_date']}\"
for x in d:
    for k in ('video_id','title','channel','url','views','upload_date','format','why_relevant'):
        assert x.get(k) not in (None,''), f'{k} missing on {x.get(video_id, \"?\")}'
print('candidates.json OK')
"
```

Expected: `candidates.json OK`.

**Acceptance check:**
- Exactly 10 entries, 5 short + 5 long, no duplicate `video_id`.
- Every Shorts entry has `upload_date >= 20260429`.
- Every entry's `why_relevant` names a youth-sports-culture angle, not a topic summary.
- No entry is generic sports or generic parenting content.

- [ ] **Step 5: No commit**

`candidates.json` lives under git-ignored `runs/`. No commit.

---

### Task 3: Fetch the ten transcripts

**Files:**
- Create: `<scratchpad>/fetch_reference.py`
- Create: `output/rgs-reference/2026-07-28/<video_id>.md` × 10

**Interfaces:**
- Consumes: `candidates.json` from Task 2.
- Produces: one markdown file per video containing YAML front-matter (`video_id`, `title`,
  `channel`, `url`, `views`, `upload_date`, `format`) followed by `## Description` and
  `## Transcript` sections. Task 4 reads these.

- [ ] **Step 1: Write the fetch script**

Create `fetch_reference.py` in the scratchpad directory:

```python
#!/usr/bin/env python3
"""One-off: fetch transcripts for the RGS reference scan. Not committed."""
import json, pathlib, re, subprocess, sys, tempfile, time

REPO = pathlib.Path(r"C:\Projects\ContentStudio")
PY = REPO / ".venv" / "Scripts" / "python.exe"
OUT = REPO / "output" / "rgs-reference" / "2026-07-28"
CAND = sorted(REPO.glob("runs/rgs-debut-*/00-scan/candidates.json"))[-1]


def vtt_to_text(vtt: str) -> str:
    lines = []
    for line in vtt.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return " ".join(lines)


def via_ytdlp(vid: str) -> tuple[str, str]:
    """Return (description, transcript). Either may be ''."""
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        subprocess.run(
            [str(PY), "-m", "yt_dlp", "--skip-download", "--write-description",
             "--write-auto-subs", "--write-subs", "--sub-langs", "en.*",
             "--sub-format", "vtt", "-o", str(td / "%(id)s.%(ext)s"),
             f"https://www.youtube.com/watch?v={vid}"],
            capture_output=True, timeout=180)
        desc = next((p.read_text("utf-8", errors="replace") for p in td.glob("*.description")), "")
        vtt = next((p.read_text("utf-8", errors="replace") for p in td.glob("*.vtt")), "")
        return desc.strip(), vtt_to_text(vtt) if vtt else ""


def via_api(vid: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        parts = YouTubeTranscriptApi().fetch(vid)
        return " ".join(p.text for p in parts).strip()
    except Exception as exc:
        print(f"    api fallback failed: {exc}", file=sys.stderr)
        return ""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = json.loads(CAND.read_text("utf-8"))
    failed = []
    for row in rows:
        vid = row["video_id"]
        dest = OUT / f"{vid}.md"
        if dest.exists():
            print(f"[skip] {vid}")
            continue
        print(f"[get ] {vid} — {row['title'][:60]}")
        desc, text = via_ytdlp(vid)
        if not text:
            print("    no subs from yt-dlp; trying youtube-transcript-api")
            text = via_api(vid)
        if not text:
            failed.append(vid)
            print(f"    FAILED {vid}", file=sys.stderr)
            continue
        fm = "\n".join(f'{k}: {json.dumps(row[k])}' for k in
                       ("video_id", "title", "channel", "url", "views", "upload_date", "format"))
        dest.write_text(
            f"---\n{fm}\n---\n\n## Description\n\n{desc}\n\n## Transcript\n\n{text}\n",
            encoding="utf-8")
        print(f"    wrote {dest.name} ({len(text)} chars)")
        time.sleep(2)
    if failed:
        print(f"\nFAILED ({len(failed)}): {', '.join(failed)}", file=sys.stderr)
        return 1
    print("\nall transcripts fetched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe "$SCRATCHPAD/fetch_reference.py"
```

Expected: ten `wrote <id>.md` lines and `all transcripts fetched`.

- [ ] **Step 3: Handle failures**

If the script exits 1, for each failed `video_id`: remove it from `candidates.json`, pick
the **next qualifying candidate** from Task 2's search results (same format, same
selection rules), verify it with `yt-dlp`, append it, and re-run Step 2.

**Hard floor:** if after substitution fewer than **4 Shorts** or fewer than **4 long-form**
videos have transcripts, stop substituting. Proceed with what was obtained and record the
exact shortfall in Task 4's scan document. Do not pad the set.

- [ ] **Step 4: Verify the transcripts are real**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib
ps=sorted(pathlib.Path('output/rgs-reference/2026-07-28').glob('*.md'))
print(f'files: {len(ps)}')
for p in ps:
    t=p.read_text('utf-8').split('## Transcript',1)
    n=len(t[1].strip()) if len(t)>1 else 0
    flag='  <-- THIN' if n<400 else ''
    print(f'  {p.stem}: {n} chars{flag}')
"
```

Expected: at least 8 files; each transcript ≥400 characters. Anything marked `THIN` is
treated as a failure and substituted per Step 3.

**Acceptance check:**
- At least 8 transcript files exist (≥4 short, ≥4 long).
- Every file has non-empty `## Transcript` content of ≥400 characters.
- Every file's front-matter `video_id` matches its filename.
- Any shortfall below 10 is written down for Task 4 to disclose.

- [ ] **Step 5: No commit**

`output/` is git-ignored. No commit.

---

### Task 4: Write the reference scan

**Files:**
- Create: `<RUN_DIR>/00-scan/reference-scan.md`
- Create: `rgs-briefs/2026-07-28-rgs-debut-reference-scan.md` (copy — this one is committed)

**Interfaces:**
- Consumes: the transcript files from Task 3.
- Produces: the **white-space section**, which is the sole input Task 5 uses for sparks.

- [ ] **Step 1: Read every transcript**

Read all files in `output/rgs-reference/2026-07-28/`. For each, identify:
- **Hook pattern** — what the first 1–3 seconds (Shorts) or first 30 seconds (long-form)
  actually does. Be specific: "cold number, no setup," "second-person accusation,"
  "personal confession," "on-screen text question."
- **Angle taken** — the position the video argues, in one clause.

- [ ] **Step 2: Write the document**

````markdown
# RGS Reference Scan — 2026-07-28

**Method.** Candidates surfaced by keyword search across six youth-sports-culture seeds,
then metadata-verified with `yt-dlp` and transcribed from auto-captions.

**Terminology.** These are *high-performing recent* videos, not "trending." YouTube exposes
no public trending API scoped to a niche; view-sorted search within a recent window is the
available proxy. [I]

[If fewer than 10 were transcribed, state the exact shortfall here and why.]

## The cohort

| # | Title | Channel | Views | Date | Format | Hook pattern | Angle taken |
|---|---|---|---|---|---|---|---|
| 1 | … | … | … | … | Short | … | … |

## What this cohort does well

[2–4 bullets. Observed patterns across the ten, each pointing at specific rows.]

## White space — what nobody here is saying

[The section that matters. 3–5 bullets. Each names a gap the cohort leaves open AND
states why RaisingGoodSports' thinker backbone is positioned to fill it. A gap that RGS
cannot uniquely fill does not belong in this list.]

## Anti-patterns observed

[Framings this cohort uses that RGS must NOT copy, checked against the brand's banned
lexicon and the never-blame-the-parent rule. Name the row each came from.]
````

- [ ] **Step 3: Copy to the committed ledger**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp "$RUN_DIR/00-scan/reference-scan.md" rgs-briefs/2026-07-28-rgs-debut-reference-scan.md && wc -l rgs-briefs/2026-07-28-rgs-debut-reference-scan.md
```

**Acceptance check:**
- The table has one row per transcribed video, with real view counts and dates from
  `yt-dlp` — not estimates.
- Every "hook pattern" cell describes a concrete technique, not a topic.
- The white-space section has 3–5 entries, each stating the RGS-specific positioning
  advantage.
- Any shortfall below 10 videos is disclosed in the Method block.
- The anti-patterns section cites specific rows.

- [ ] **Step 4: Commit**

```bash
cd /c/Projects/ContentStudio && git add rgs-briefs/2026-07-28-rgs-debut-reference-scan.md && git commit -m "content(rgs): reference scan of 10 youth-sports videos for debut pair"
```

---

### Task 5: Generate the two sparks

**Files:**
- Create: `<RUN_DIR>/00-scan/sparks.md`
- Create: `rgs-briefs/2026-07-28-rgs-debut-sparks.md`

**Interfaces:**
- Consumes: the white-space section from Task 4.
- Produces: **`<slug-a>` and `<slug-b>`** — short kebab-case topic slugs used verbatim in
  every committed filename from Task 6 onward. Also produces the one-paragraph topic
  statement each grounding task feeds to `rgs-grounding`.

- [ ] **Step 1: Read the constraints**

Read `output/raisinggoodsports-brand-definition.md` (focus statement, audience, lexicon)
and list every existing brief:

```bash
cd /c/Projects/ContentStudio && ls rgs-briefs/*.md | grep -v README && echo "--- topics ---" && grep -h "^topic:" rgs-briefs/*.md
```

- [ ] **Step 2: Draft two sparks from the white space**

Each spark must:
- Trace to a specific white-space entry from Task 4.
- Sit inside the brand focus statement (youth-sports culture's effect on kids and families).
- **Not duplicate** any existing brief topic listed in Step 1.
- **Not collapse into the other spark** — they must differ in underlying mechanism, not
  just in wording.

- [ ] **Step 3: Write the document**

````markdown
# RGS Debut Sparks — 2026-07-28

## Spark A — <slug-a>

- **Archetype:** A1 — "the thinker who saw it coming"
- **Topic statement:** [one paragraph, written as the input `rgs-grounding` will receive]
- **White-space entry it fills:** [quote the entry from reference-scan.md]
- **Why it fits the brand focus statement:** [one sentence]
- **Audience pain it names:** [one sentence, from the brand's Audience block]

## Spark B — <slug-b>

- **Archetype:** A3 — "what the kid hears"
- [same five fields]

## Dedupe record

- **Checked against:** [N] existing briefs in `rgs-briefs/`.
- **Nearest existing topic to Spark A:** [filename] — [why this is genuinely distinct]
- **Nearest existing topic to Spark B:** [filename] — [why this is genuinely distinct]
- **A vs. B distinctness:** [the differing mechanism, stated plainly]

## Archetype rationale

A2 ("the number they don't tell you") is deliberately excluded from the debut: it routinely
cites injury and health data, and YouTube's inauthentic-content policy bars AI personas
presenting as health authorities. Not a risk worth carrying on uploads #1 and #2. [T]
(verified 2026-07-23 via the brand definition's monetization-policy citation —
re-verify before relying on it)

## Alternates considered

[Other white-space entries that could have become sparks, one line each with why not.]
````

- [ ] **Step 4: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp "$RUN_DIR/00-scan/sparks.md" rgs-briefs/2026-07-28-rgs-debut-sparks.md && git add rgs-briefs/2026-07-28-rgs-debut-sparks.md && git commit -m "content(rgs): two debut sparks from reference-scan white space"
```

**Acceptance check:**
- Both sparks cite a specific white-space entry verbatim.
- Neither duplicates an existing `rgs-briefs/` topic; the dedupe record names the nearest
  one for each and argues the distinction.
- The two sparks differ in underlying mechanism, stated explicitly.
- `<slug-a>` and `<slug-b>` are fixed and recorded — every later filename uses them.
- Archetypes are A1 and A3; the A2 exclusion rationale is present.

---

### Task 6: Grounding brief — Short A

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-a>.md`
- Copy to: `<RUN_DIR>/short-a/00-grounding/artifact.v1.md`

**Interfaces:**
- Consumes: Spark A's topic statement from Task 5.
- Produces: a Grounding Brief with the exact front-matter schema in
  `rgs-briefs/README.md` and the section structure in `.claude/skills/rgs-grounding/SKILL.md`
  (Pairing, Hook, Turn, Payoff, Reframe, [Safety handling], Verification record,
  [Gap-fill flag], Handoff, Alternates considered). Tasks 9 and 10 consume it.

- [ ] **Step 1: Invoke the skill**

Invoke `rgs-grounding` with Spark A's topic statement. Take the **non-interactive
fallback**: build the Pairing Slate, proceed with the top-ranked row, and include the
"Alternates considered" appendix instead of stopping for a pick.

- [ ] **Step 2: Apply the recency rule against the existing ledger**

```bash
cd /c/Projects/ContentStudio && grep -h "^thinker:" rgs-briefs/*.md | sort | uniq -c | sort -rn
```

**Plutarch** (used 2026-07-27) and **Adler** are recently spent — deprioritize them, do not
exclude them. Record the recency flag on each slate row.

- [ ] **Step 3: Verify against source — mandatory, not skippable**

Open the thinker's cleaned text under `output/thinkers/anchorandwave/<thinker>/` and the
research file under `output/youth-sports/raisinggoodsports/rgs-<code>-*.md`. Confirm the
exact passage and the exact finding are present **in this invocation**. Check the research
file's front-matter `edition:` against the edition recorded in
`.claude/skills/rgs-grounding/references/pairing-map.md`; flag any mismatch in the brief.

This is the step the whole skill exists to enforce. Writing a `[THINKER:` or `[RESEARCH:`
citation without having opened that exact file is a failure, not a shortcut.

- [ ] **Step 4: Write the brief and verify its shape**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re,sys
p=pathlib.Path('rgs-briefs').glob('2026-07-28-*.md')
p=[x for x in p if 'rgs-debut' not in x.name]
assert p, 'no grounding brief found'
t=p[0].read_text('utf-8')
for k in ('date:','topic:','thinker:','concept:','research_codes:','archetype:','status:'):
    assert k in t, f'front-matter missing {k}'
for h in ('## Pairing','## Hook','## Turn','## Payoff','## Reframe','## Verification record','## Handoff'):
    assert h in t, f'section missing {h}'
assert '[THINKER:' in t and '[RESEARCH:' in t, 'citation markers missing'
assert 'archetype: A1' in t, 'Short A must be archetype A1'
print(f'{p[0].name} OK')
"
```

- [ ] **Step 5: Copy to the run folder and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-a>.md "$RUN_DIR/short-a/00-grounding/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-a>.md && git commit -m "content(rgs): grounding brief for debut Short A"
```

**Acceptance check:**
- Front-matter matches `rgs-briefs/README.md`'s schema exactly; `archetype: A1`.
- The Verification record names **actual file paths and line/section references** that
  exist on disk — spot-check one by opening it.
- The thinker is not Plutarch or Adler unless the brief explicitly argues past the recency
  flag.
- Quotability is restated per beat; if the thinker is `paraphrase-caution`, the
  "Constraints that survive to publish" line says so.
- The corpus edition check is recorded.

---

### Task 7: Grounding brief — Short B

Identical procedure to Task 6, with three changes. The code is repeated rather than
referenced because tasks may be executed out of order.

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-b>.md`
- Copy to: `<RUN_DIR>/short-b/00-grounding/artifact.v1.md`

**Interfaces:**
- Consumes: Spark B's topic statement from Task 5; the thinker chosen in Task 6.
- Produces: the Short B Grounding Brief. Tasks 15 and 16 consume it.

- [ ] **Step 1: Invoke the skill with Spark B**

Invoke `rgs-grounding` with Spark B's topic statement, non-interactive fallback as before.

- [ ] **Step 2: Exclude Short A's thinker**

```bash
cd /c/Projects/ContentStudio && grep -h "^thinker:" rgs-briefs/2026-07-28-*.md
```

**Short B must use a different thinker than Short A** — this is a hard constraint from the
spec ("two briefs, two different thinkers"), stronger than the skill's soft recency rule.
Plutarch and Adler remain deprioritized.

- [ ] **Step 3: Verify against source — mandatory**

Open the thinker's cleaned text under `output/thinkers/anchorandwave/<thinker>/` and the
research file under `output/youth-sports/raisinggoodsports/rgs-<code>-*.md`. Confirm the
exact passage and finding are present in this invocation. Check `edition:` against
`pairing-map.md`.

- [ ] **Step 4: Write the brief and verify its shape**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib
ps=[x for x in pathlib.Path('rgs-briefs').glob('2026-07-28-*.md') if 'rgs-debut' not in x.name]
assert len(ps)==2, f'expected 2 grounding briefs, got {len(ps)}'
ts=[x.read_text('utf-8') for x in ps]
for t,p in zip(ts,ps):
    for k in ('date:','topic:','thinker:','concept:','research_codes:','archetype:','status:'):
        assert k in t, f'{p.name}: front-matter missing {k}'
    for h in ('## Pairing','## Hook','## Turn','## Payoff','## Reframe','## Verification record','## Handoff'):
        assert h in t, f'{p.name}: section missing {h}'
    assert '[THINKER:' in t and '[RESEARCH:' in t, f'{p.name}: citation markers missing'
import re
th=[re.search(r'^thinker:\s*(.+)$',t,re.M).group(1).strip() for t in ts]
assert th[0]!=th[1], f'both briefs use the same thinker: {th[0]}'
arch=sorted(re.search(r'^archetype:\s*(\w+)',t,re.M).group(1) for t in ts)
assert arch==['A1','A3'], f'expected A1 and A3, got {arch}'
print(f'both briefs OK — thinkers: {th}')
"
```

Expected: `both briefs OK` with two distinct thinker names.

- [ ] **Step 5: Copy to the run folder and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-b>.md "$RUN_DIR/short-b/00-grounding/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-b>.md && git commit -m "content(rgs): grounding brief for debut Short B"
```

**Acceptance check:**
- Two grounding briefs exist with **different thinkers** and archetypes A1 and A3.
- Short B's Verification record names real, openable file paths — spot-check one.
- Quotability constraints are restated per beat.

---

### Task 8: Lock the shared visual system

This runs **before either Short's ideation stage**, because ideation produces thumbnail
concepts that must already conform.

**Files:**
- Create: `rgs-briefs/2026-07-28-rgs-debut-visual-system.md`
- Copy to: `<RUN_DIR>/visual-system.md`

**Interfaces:**
- Consumes: the visual block of `output/raisinggoodsports-brand-definition.md`; both
  grounding briefs' "visual motif cue" lines from their Handoff sections.
- Produces: the binding system. Tasks 9, 12, 13, 15, 18, 19 all conform to it.

- [ ] **Step 1: Read the brand visual block and both motif cues**

```bash
cd /c/Projects/ContentStudio && sed -n '/^# Visual brand kit/,/^---$/p' output/raisinggoodsports-brand-definition.md && echo "=== motifs ===" && grep -A2 "visual motif cue" rgs-briefs/2026-07-28-*.md
```

- [ ] **Step 2: Write the system**

````markdown
# RGS Shared Visual System — Debut Pair (locked 2026-07-28)

Binds both debut Shorts. **Change the words, not the system.** [C] (brand visual block:
consistency "turns your thumbnails into a brand")

## What is shared (identical across both Shorts)

- **Palette:** ground `#0E3B43`, accent `#F2A541`, type `#F7F3E8`, sparing `#C1543A`
  (reserved for "the system" framing — never for blame). 2–3 colors per image, max.
  Text/ground contrast ≥4.5:1. [C]
- **Type:** one bold sans-serif (DejaVu Sans Bold is the shipping face — the compositor
  has no other font installed). ALL-CAPS only for the single accent word. ≥60pt at
  1280×720. [C][T]
- **Subject treatment — anonymous human presence:** cleats on a bench, a parent's shoulders
  on a sideline, hands gripping a fence, a silhouette against field lights. Never a host
  face; never an empty frame. [C] (the brand's own resolution of the faceless-face tension)
- **Midjourney consistency mechanism:** [state the exact `--sref` strategy and seed
  discipline, per `.claude/skills/midjourney-prompting/`] [T]
- **Caption/overlay treatment:** [one specification — position, weight, reveal timing]
- **Thumbnail layout:** ground field; amber accent word; subject right of center; 3–5 words
  of text left; rule of thirds; must read at 120px wide. [C]
- **Safe zone:** text inside the middle ~60% vertically, clear of the bottom 25% and right
  15%. **UNVERIFIED** — no official YouTube safe-zone spec exists; third-party numbers
  conflict. Verify on a phone before committing a template. [T-unverified]

## What differs per Short (deliberately)

- **Motif family.** Short A: [from brief A's motif cue]. Short B: [from brief B's motif cue].

The system fixes palette, type, and subject treatment. It does **not** fix motif — that is
what keeps the pair from reading as the same video twice.

## Still pool protocol

Short A's visual stage (Task 12) establishes the pool and numbers every still `A-01`,
`A-02`, … Short B's prompt sheet (Task 18) marks **every** shot `REUSE <id>` or `NEW`.

**Target:** combined asset count ≈1.5× a single Short's, not 2×.

## Motion rationing

Image-to-video prompts go only to beats that genuinely require motion. Every other beat is
a still with movement added in the edit (push-in, parallax, whip cut), specified in the
assembly plan. [I]
````

- [ ] **Step 3: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-rgs-debut-visual-system.md "$RUN_DIR/visual-system.md" && git add rgs-briefs/2026-07-28-rgs-debut-visual-system.md && git commit -m "content(rgs): lock shared visual system for the debut pair"
```

**Acceptance check:**
- All four hex values appear verbatim and match the brand definition.
- Every normative line carries a marker; the safe-zone line is marked `[T-unverified]`.
- The two motif families are distinct and each traces to its brief's Handoff motif cue.
- The still-pool numbering scheme and the ≈1.5× target are stated.

---

### Task 9: Short A — ideation (packaging first)

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-a>-concept-brief.md`
- Copy to: `<RUN_DIR>/short-a/01-ideation/artifact.v1.md`

**Interfaces:**
- Consumes: `rgs-briefs/2026-07-28-<slug-a>.md` (grounding brief, as `shorts-ideation`'s
  optional companion grounding artifact); `2026-07-28-rgs-debut-visual-system.md`.
- Produces: a concept brief containing **angle**, **hook concept**, and **packaging
  direction (title + thumbnail concept)**. Task 10 consumes it.

- [ ] **Step 1: Invoke `shorts-ideation`**

Pass the grounding brief as the companion grounding artifact per the skill's "Optional
input" section, and run the staleness check it specifies. Take the non-interactive
fallback on the angle pick and record alternates.

- [ ] **Step 2: Enforce packaging-before-script**

The brand's binding rule: **write the title and build the thumbnail concept first.** The
concept brief must contain both, and an explicit go/no-go line. If the packaging is not
compelling, rework the concept — do not proceed to Task 10 with weak packaging.

Package for the viewer who **stays**, not the viewer who clicks: YouTube's built-in A/B
test optimizes watch time, not CTR. [T] (verified 2026-07-23 — re-verify)

- [ ] **Step 3: Conform the thumbnail to the locked system**

The thumbnail concept must use the locked layout: ground field, amber accent word, subject
right of center, 3–5 words left, anonymous human presence, readable at 120px.

- [ ] **Step 4: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib
p=pathlib.Path('rgs-briefs/2026-07-28-<slug-a>-concept-brief.md')
t=p.read_text('utf-8')
import re
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} provenance markers — expected several'
for w in ('bad parent','crush it','game-changer','the secret to','hack'):
    assert w.lower() not in t.lower(), f'banned lexicon: {w}'
print(f'concept brief OK — {n} markers')
"
```

- [ ] **Step 5: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-a>-concept-brief.md "$RUN_DIR/short-a/01-ideation/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-a>-concept-brief.md && git commit -m "content(rgs): Short A concept brief and packaging"
```

**Acceptance check:**
- A concrete title string and a thumbnail concept are both present, with a go/no-go line.
- Thumbnail conforms to the locked layout and uses 3–5 words.
- The angle traces to the grounding brief's pairing.
- Every normative line carries a marker; no banned lexicon.
- The villain is the system, not the parent.

---

### Task 10: Short A — script

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-a>-script.md`
- Copy to: `<RUN_DIR>/short-a/02-scripting/artifact.v1.md`

**Interfaces:**
- Consumes: the Task 9 concept brief; the Task 6 grounding brief (citation text per beat,
  mapped per `.claude/skills/rgs-grounding/references/scripting-beat-mapping.md`).
- Produces: a beat-timed script with per-beat timings in seconds. Tasks 11, 12, 13 consume
  it.

- [ ] **Step 1: Invoke `shorts-scripting`**

Pass both the concept brief and the grounding brief. Apply the fixed
Hook/Turn/Payoff/Reframe → Hook/Setup/Build/Payoff/Loop-CTA mapping, using the **per-brief
mapping judgment** recorded in the grounding brief's Handoff section.

- [ ] **Step 2: Apply the hard hook constraint**

The first 2 seconds carry the whole video — **visual and verbal**. One idea only. The
script must state what is on screen and what is said in that window, separately.

- [ ] **Step 3: Apply the citation constraints**

- `paraphrase-caution` thinkers: voiceover paraphrase only. **Never** an on-screen quote
  card. If brief A's thinker is `paraphrase-caution`, the script says so at the beat.
- Every health or injury claim is attributed to its named source **on-screen and in
  voiceover**. The narrator is a commentator, never an expert persona.
- Hedge any prevalence number the grounding brief flags.

- [ ] **Step 4: End on relief and agency**

The final beat locates the villain in the system and hands back agency. Not a scold, not a
cliffhanger of dread.

- [ ] **Step 5: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-a>-script.md').read_text('utf-8')
secs=re.findall(r'(\d+(?:\.\d+)?)\s*s\b',t)
assert secs, 'no per-beat timings found'
assert re.search(r'hook',t,re.I), 'no hook beat'
for w in ('bad parent','crush it','game-changer','the secret to'):
    assert w.lower() not in t.lower(), f'banned lexicon: {w}'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} provenance markers'
print(f'script OK — {n} markers, {len(secs)} timing marks')
"
```

- [ ] **Step 6: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-a>-script.md "$RUN_DIR/short-a/02-scripting/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-a>-script.md && git commit -m "content(rgs): Short A beat-timed script"
```

**Acceptance check:**
- Every beat has a timing in seconds; total runtime is stated.
- The 0–2s window specifies the visual hook and the verbal hook separately.
- Quotability constraint honored — no quote card for a `paraphrase-caution` thinker.
- Every health/injury claim names its source in both the on-screen and voiceover columns.
- The final beat ends on relief and agency, villain located in the system.

---

### Task 11: Short A — voiceover brief and ElevenLabs configuration

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-a>-voiceover-brief.md`
- Copy to: `<RUN_DIR>/short-a/03-voiceover/artifact.v1.md`

**Interfaces:**
- Consumes: the Task 10 script.
- Produces: the creative brief **and** the runnable ElevenLabs configuration. Task 13
  consumes the loudness and ducking targets.

- [ ] **Step 1: Invoke `voiceover-brief`**

It makes the creative call: voice pick with rationale, the four core settings (stability,
similarity/clarity, style, speed) plus speaker boost by content type, TTS-formatting notes
on the script text, and the **−14 LUFS** loudness/mix target.

Voice character must match the brand: calm, warm, grounded — an ally on the same side of
the table. Not urgent, not alarmed, not authoritative-expert.

- [ ] **Step 2: Hand down to `elevenlabs-audio`**

The specialist accepts the creative call and **does not re-litigate it**. It emits: voice
pick, model routing, voice settings, tag-annotated directorial script, PLS pronunciation
dictionary, JSON request payload, curl command, and credit estimate.

- [ ] **Step 3: Do not spend credits**

Produce the configuration only. **Do not call the ElevenLabs API.** The spec is explicit
that no credits are consumed by this run.

- [ ] **Step 4: Carry the AI disclosure forward**

The brand policy mandates disclosed synthetic media. Record the exact disclosure line here
so Tasks 13 and 14 place it in the edit plan and the post copy.

- [ ] **Step 5: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re,json
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-a>-voiceover-brief.md').read_text('utf-8')
for k in ('stability','similarity','style','speed','LUFS'):
    assert re.search(k,t,re.I), f'missing setting: {k}'
assert '-14' in t or '−14' in t, 'missing -14 LUFS target'
assert re.search(r'model',t,re.I), 'no model routing'
assert '{' in t and '}' in t, 'no JSON payload block'
assert re.search(r'disclos',t,re.I), 'no AI disclosure line'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
print(f'voiceover brief OK — {n} markers')
"
```

- [ ] **Step 6: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-a>-voiceover-brief.md "$RUN_DIR/short-a/03-voiceover/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-a>-voiceover-brief.md && git commit -m "content(rgs): Short A voiceover brief and ElevenLabs config"
```

**Acceptance check:**
- All four core settings have concrete values, plus speaker boost.
- A complete JSON request payload and a curl command are present.
- Credit estimate is stated. **No API call was made.**
- −14 LUFS target and ducking guidance present.
- The AI disclosure line is written out verbatim for downstream reuse.
- Voice rationale ties to the brand's calm/warm/ally voice traits.

---

### Task 12: Short A — visual prompt sheet (establishes the still pool)

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-a>-visual-prompts.md`
- Copy to: `<RUN_DIR>/short-a/03-visual/artifact.v1.md`

**Interfaces:**
- Consumes: the Task 10 script; `2026-07-28-rgs-debut-visual-system.md`.
- Produces: **the still pool** — every still numbered `A-01`, `A-02`, … Task 18 marks
  reuse against these exact IDs. Also produces the cover/thumbnail prompt.

- [ ] **Step 1: Invoke `visual-prompts`**

It owns beat mapping: shot count per beat at the corpus's ~3-second visual cadence, the
still-vs-motion decision per beat, the i2v prompts, and the cover/thumbnail decision.

- [ ] **Step 2: Delegate every still prompt to `midjourney-prompting`**

`visual-prompts` does not write Midjourney prompt wording. Hand each beat's visual note to
`midjourney-prompting`, which owns the 9-layer prompt body, the parameter stack, the
consistency mechanism, and the syntax lint.

- [ ] **Step 3: Conform to the locked system**

Every prompt uses the locked palette, the anonymous-human-presence subject treatment, and
the `--sref`/seed discipline from `visual-system.md`. Short A's motif family only.

- [ ] **Step 4: Ration motion**

Only beats that genuinely require movement get an i2v prompt. State the rationale per
motion beat. Everything else is a still with edit-added movement, noted for Task 13.

- [ ] **Step 5: Number the pool**

Every still gets an ID `A-NN`. The sheet ends with a **Still pool index**: a table of
`A-NN` → one-line description, which is what Task 18 reads.

- [ ] **Step 6: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-a>-visual-prompts.md').read_text('utf-8')
ids=sorted(set(re.findall(r'\bA-\d{2}\b',t)))
assert len(ids)>=4, f'still pool too small: {ids}'
assert 'Still pool index' in t, 'missing Still pool index section'
assert '--' in t, 'no Midjourney parameter flags found'
assert re.search(r'#0E3B43|teal-ink',t,re.I), 'palette not referenced'
assert re.search(r'i2v|image-to-video|motion',t,re.I), 'no motion decision recorded'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
print(f'visual prompts OK — pool {ids}, {n} markers')
"
```

- [ ] **Step 7: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-a>-visual-prompts.md "$RUN_DIR/short-a/03-visual/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-a>-visual-prompts.md && git commit -m "content(rgs): Short A visual prompt sheet and still pool"
```

**Acceptance check:**
- Every script beat maps to a shot count at ~3s cadence.
- Every still has an `A-NN` ID and appears in the Still pool index.
- Every prompt carries the locked palette and subject treatment; no host face.
- Motion beats are justified individually; the rest note edit-added movement.
- A cover/thumbnail prompt exists and matches the locked thumbnail layout.

---

### Task 13: Short A — assembly plan

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-a>-assembly.md`
- Copy to: `<RUN_DIR>/short-a/04-assembly/artifact.v1.md`

**Interfaces:**
- Consumes: Task 10 script, Task 11 voiceover brief, Task 12 prompt sheet.
- Produces: the edit plan. Task 14 consumes its packaging summary.

- [ ] **Step 1: Invoke `shorts-assembly`**

It produces five gated things: shot-by-shot pacing and cut cadence; caption/overlay
treatment; aspect-ratio and safe-zone specs; loudness/ducking targets; and both a
**$0 tool-stack** and a **paid tool-stack** execution path.

- [ ] **Step 2: Carry the locked constraints**

- 9:16. Safe zone: middle ~60% vertically, clear of bottom 25% and right 15% — marked
  `[T-unverified]`, verify on a phone.
- Caption treatment exactly as locked in `visual-system.md`.
- −14 LUFS integrated; ducking per the voiceover brief.
- Edit-added movement for every non-motion still, per Task 12's notes.
- The AI disclosure line from Task 11, placed concretely.

- [ ] **Step 3: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-a>-assembly.md').read_text('utf-8')
assert '9:16' in t, 'no aspect ratio'
assert '-14' in t or '−14' in t, 'no LUFS target'
assert re.search(r'safe.?zone',t,re.I), 'no safe-zone spec'
assert re.search(r'caption',t,re.I), 'no caption treatment'
assert re.search(r'duck',t,re.I), 'no ducking spec'
assert re.search(r'disclos',t,re.I), 'no AI disclosure placement'
assert re.search(r'\$0|free',t,re.I) and re.search(r'paid',t,re.I), 'missing one of the two tool stacks'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
print(f'assembly OK — {n} markers')
"
```

- [ ] **Step 4: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-a>-assembly.md "$RUN_DIR/short-a/04-assembly/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-a>-assembly.md && git commit -m "content(rgs): Short A assembly and edit plan"
```

**Acceptance check:**
- Shot-by-shot cadence references the `A-NN` still IDs from Task 12.
- Both tool stacks are specified end to end.
- Safe-zone spec is present and marked unverified.
- The AI disclosure has a concrete on-screen placement and timing.

---

### Task 14: Short A — social repurpose copy

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-a>-social-repurpose.md`
- Copy to: `<RUN_DIR>/short-a/05-repurpose/artifact.v1.md`

**Interfaces:**
- Consumes: Task 10 script, Task 9 packaging, Task 13 assembly plan.
- Produces: copy for exactly six surfaces. Task 21 validates it.

- [ ] **Step 1: Invoke `social-repurpose`**

Produce, for Short A:
- **YouTube:** title, description, hashtags. Front-load the important words. Title and
  thumbnail must tell one story. [T]
- **TikTok** caption + hashtags; **Instagram Reels** caption + hashtags. Same 9:16 export,
  copy differs only.
- **Bluesky**, **Threads**, **X**: text-only posts that carry the idea without the video.

- [ ] **Step 2: Enforce the asset constraint explicitly**

State in the document that all three video surfaces take the **identical export** — no
re-cut, no re-crop, no alternate aspect. This is the whole point of the constraint.

- [ ] **Step 3: Carry brand and policy constraints**

- No banned lexicon; villain is the system; no parent-blame; no clickbait absolute.
- AI disclosure present where each platform requires it.
- Health/injury claims attributed in the copy, not just the video.

- [ ] **Step 4: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-a>-social-repurpose.md').read_text('utf-8')
for s in ('YouTube','TikTok','Instagram','Bluesky','Threads','X'):
    assert re.search(rf'\b{s}\b',t), f'missing surface: {s}'
assert re.search(r'identical export|same export|no re-?cut',t,re.I), 'asset-constraint statement missing'
for w in ('bad parent','crush it','game-changer','the secret to'):
    assert w.lower() not in t.lower(), f'banned lexicon: {w}'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
print(f'repurpose OK — {n} markers')
"
```

- [ ] **Step 5: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-a>-social-repurpose.md "$RUN_DIR/short-a/05-repurpose/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-a>-social-repurpose.md && git commit -m "content(rgs): Short A multi-surface post copy"
```

**Acceptance check:**
- All six surfaces have complete, ready-to-paste copy.
- The identical-export statement is present.
- YouTube title front-loads and pairs with the thumbnail concept from Task 9.
- No banned lexicon anywhere; no parent-blame.

---

### Task 15: Short B — ideation (packaging first)

Same procedure as Task 9, against Short B's inputs. Repeated in full because tasks may be
executed out of order.

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-b>-concept-brief.md`
- Copy to: `<RUN_DIR>/short-b/01-ideation/artifact.v1.md`

**Interfaces:**
- Consumes: `rgs-briefs/2026-07-28-<slug-b>.md`; `2026-07-28-rgs-debut-visual-system.md`;
  Task 9's concept brief (read **only** to confirm the two do not converge).
- Produces: Short B's concept brief with angle, hook concept, and packaging direction.

- [ ] **Step 1: Invoke `shorts-ideation`**

Pass the Short B grounding brief as the companion grounding artifact, run the staleness
check, take the non-interactive fallback, record alternates.

- [ ] **Step 2: Enforce packaging-before-script**

Title and thumbnail concept first, with a go/no-go line. Package for the viewer who stays,
not the viewer who clicks. [T]

- [ ] **Step 3: Conform to the locked system, in Short B's motif family**

Locked layout and palette; **Short B's motif family**, not Short A's. This is where the
pair stays distinguishable.

- [ ] **Step 4: Confirm non-convergence with Short A**

Read Task 9's concept brief. If Short B's angle or hook restates Short A's, rework Short B
now — before scripting. Record the distinction explicitly in the document.

- [ ] **Step 5: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-b>-concept-brief.md').read_text('utf-8')
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
for w in ('bad parent','crush it','game-changer','the secret to','hack'):
    assert w.lower() not in t.lower(), f'banned lexicon: {w}'
assert re.search(r'distinct|differs from|non-?converg',t,re.I), 'no non-convergence statement vs Short A'
print(f'concept brief B OK — {n} markers')
"
```

- [ ] **Step 6: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-b>-concept-brief.md "$RUN_DIR/short-b/01-ideation/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-b>-concept-brief.md && git commit -m "content(rgs): Short B concept brief and packaging"
```

**Acceptance check:**
- Title string and thumbnail concept present, with a go/no-go line.
- Thumbnail uses the locked layout but Short B's motif family.
- An explicit statement of how B differs from A.
- Markers present; no banned lexicon; villain is the system.

---

### Task 16: Short B — script

Same procedure as Task 10, against Short B's inputs.

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-b>-script.md`
- Copy to: `<RUN_DIR>/short-b/02-scripting/artifact.v1.md`

**Interfaces:**
- Consumes: Task 15 concept brief; Task 7 grounding brief.
- Produces: a beat-timed script. Tasks 17, 18, 19 consume it.

- [ ] **Step 1: Invoke `shorts-scripting`**

Pass both documents. Apply the fixed beat mapping using brief B's per-brief mapping
judgment from its Handoff section.

- [ ] **Step 2: Apply the hard hook constraint**

First 2 seconds carry the video — visual and verbal, stated separately. One idea only.

Note the archetype: Short B is **A3, "what the kid hears."** The hook should land from the
child's vantage, not the parent's.

- [ ] **Step 3: Apply the citation constraints**

`paraphrase-caution` → voiceover paraphrase only, never a quote card. Health/injury claims
attributed on-screen and in voiceover. Hedge any prevalence number the brief flags.

- [ ] **Step 4: End on relief and agency**

Villain in the system. A3 carries a specific risk: a Short written from the kid's vantage
can slide into implying the parent is the one hurting them. It must not. The reframe beat
has to land the system as the villain unambiguously.

- [ ] **Step 5: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-b>-script.md').read_text('utf-8')
secs=re.findall(r'(\d+(?:\.\d+)?)\s*s\b',t)
assert secs, 'no per-beat timings'
for w in ('bad parent','crush it','game-changer','the secret to'):
    assert w.lower() not in t.lower(), f'banned lexicon: {w}'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
print(f'script B OK — {n} markers, {len(secs)} timing marks')
"
```

- [ ] **Step 6: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-b>-script.md "$RUN_DIR/short-b/02-scripting/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-b>-script.md && git commit -m "content(rgs): Short B beat-timed script"
```

**Acceptance check:**
- Every beat timed; total runtime stated; 0–2s visual and verbal hooks stated separately.
- **The A3 vantage never implies the parent is the villain** — read the reframe beat
  specifically for this.
- Quotability and health-attribution constraints honored.

---

### Task 17: Short B — voiceover brief and ElevenLabs configuration

Same procedure as Task 11, against Short B's script.

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-b>-voiceover-brief.md`
- Copy to: `<RUN_DIR>/short-b/03-voiceover/artifact.v1.md`

**Interfaces:**
- Consumes: Task 16 script; Task 11's voice pick (for consistency).
- Produces: creative brief plus runnable ElevenLabs configuration.

- [ ] **Step 1: Invoke `voiceover-brief`**

Voice pick, four core settings plus speaker boost, TTS-formatting notes, −14 LUFS target.

**Use the same voice as Short A** unless there is a stated reason not to — this is the
channel's debut and voice consistency is part of the shared system. If the A3 vantage
argues for a different delivery, change the *settings*, not the voice.

- [ ] **Step 2: Hand down to `elevenlabs-audio`**

Specialist accepts the creative call without re-litigating it. Emits model routing, voice
settings, tag-annotated script, PLS dictionary, JSON payload, curl command, credit estimate.

- [ ] **Step 3: Do not spend credits**

Configuration only. **No API call.**

- [ ] **Step 4: Carry the AI disclosure forward**

Same disclosure line as Task 11, recorded here for Tasks 19 and 20.

- [ ] **Step 5: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-b>-voiceover-brief.md').read_text('utf-8')
for k in ('stability','similarity','style','speed','LUFS'):
    assert re.search(k,t,re.I), f'missing setting: {k}'
assert '-14' in t or '−14' in t, 'missing -14 LUFS'
assert '{' in t and '}' in t, 'no JSON payload'
assert re.search(r'disclos',t,re.I), 'no AI disclosure line'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
print(f'voiceover brief B OK — {n} markers')
"
```

- [ ] **Step 6: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-b>-voiceover-brief.md "$RUN_DIR/short-b/03-voiceover/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-b>-voiceover-brief.md && git commit -m "content(rgs): Short B voiceover brief and ElevenLabs config"
```

**Acceptance check:**
- Same voice as Short A, or a stated reason for differing.
- All four settings, JSON payload, curl command, credit estimate present.
- No API call made.

---

### Task 18: Short B — visual prompt sheet (REUSE/NEW marked)

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-b>-visual-prompts.md`
- Copy to: `<RUN_DIR>/short-b/03-visual/artifact.v1.md`

**Interfaces:**
- Consumes: Task 16 script; `visual-system.md`; **Task 12's Still pool index** (the `A-NN`
  IDs).
- Produces: Short B's prompt sheet with per-shot `REUSE A-NN` or `NEW B-NN` marking, and a
  combined asset count. This task is where the asset constraint is actually enforced.

- [ ] **Step 1: Read Short A's still pool index**

```bash
cd /c/Projects/ContentStudio && sed -n '/Still pool index/,$p' rgs-briefs/2026-07-28-<slug-a>-visual-prompts.md
```

- [ ] **Step 2: Invoke `visual-prompts`**

Beat mapping at ~3s cadence, still-vs-motion decision per beat, i2v prompts, cover decision
— as in Task 12.

- [ ] **Step 3: Mark every shot REUSE or NEW**

For **every** shot, write `REUSE A-NN` (naming the exact still) or `NEW B-NN`. A shot may
only be marked REUSE if the Short A still genuinely serves the beat — do not force reuse
that damages the beat. Where reuse is rejected, say why in one line.

- [ ] **Step 4: Delegate new prompts to `midjourney-prompting`**

Only `NEW B-NN` shots need prompt writing. They use the locked `--sref`/seed discipline so
they sit in the same visual world as the A pool, but in **Short B's motif family**.

- [ ] **Step 5: Report the asset math**

End the sheet with:

```markdown
## Asset economy

- Short A pool: [N] stills, [M] i2v clips
- Short B: [R] REUSE, [S] NEW stills, [T] NEW i2v clips
- **Combined new assets: [N+S] stills, [M+T] clips**
- **Ratio vs. a single Short: [x]×** (target ≈1.5×; state plainly if exceeded and why)
```

- [ ] **Step 6: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
a=pathlib.Path('rgs-briefs/2026-07-28-<slug-a>-visual-prompts.md').read_text('utf-8')
b=pathlib.Path('rgs-briefs/2026-07-28-<slug-b>-visual-prompts.md').read_text('utf-8')
pool=set(re.findall(r'\bA-\d{2}\b',a))
reused=set(re.findall(r'REUSE\s+(A-\d{2})',b))
assert reused, 'no REUSE marks — the asset constraint is not being enforced'
bad=reused-pool
assert not bad, f'REUSE references stills not in Short A pool: {sorted(bad)}'
assert 'Asset economy' in b, 'missing Asset economy section'
assert re.search(r'NEW\s+B-\d{2}',b), 'no NEW shots marked'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',b))
assert n>=5, f'only {n} markers'
print(f'visual prompts B OK — reuses {sorted(reused)} of pool {sorted(pool)}')
"
```

Expected: at least one REUSE, every REUSE ID present in Short A's pool.

- [ ] **Step 7: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-b>-visual-prompts.md "$RUN_DIR/short-b/03-visual/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-b>-visual-prompts.md && git commit -m "content(rgs): Short B visual prompts with REUSE/NEW asset marking"
```

**Acceptance check:**
- **Every** shot carries a `REUSE A-NN` or `NEW B-NN` mark — none unmarked.
- Every REUSE ID exists in Short A's pool.
- The Asset economy section reports the combined count and the ratio.
- If the ratio exceeds ≈1.5×, the sheet says so plainly rather than hiding it.
- Short B's NEW prompts use Short B's motif family within the shared system.

---

### Task 19: Short B — assembly plan

Same procedure as Task 13, against Short B's inputs.

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-b>-assembly.md`
- Copy to: `<RUN_DIR>/short-b/04-assembly/artifact.v1.md`

**Interfaces:**
- Consumes: Task 16 script, Task 17 voiceover brief, Task 18 prompt sheet.
- Produces: Short B's edit plan.

- [ ] **Step 1: Invoke `shorts-assembly`**

Five gated outputs: pacing/cut cadence, caption/overlay treatment, aspect and safe zone,
loudness/ducking, and both $0 and paid tool-stack paths.

- [ ] **Step 2: Carry the locked constraints**

9:16; safe zone middle ~60% vertically, clear of bottom 25% and right 15%
(`[T-unverified]`); caption treatment as locked; −14 LUFS; edit-added movement for
non-motion stills; the AI disclosure line placed concretely.

- [ ] **Step 3: Reference reused stills by their A-NN IDs**

The shot list must use the same IDs Task 18 assigned, so the editor knows which asset is
already rendered.

- [ ] **Step 4: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-b>-assembly.md').read_text('utf-8')
assert '9:16' in t, 'no aspect ratio'
assert '-14' in t or '−14' in t, 'no LUFS target'
assert re.search(r'safe.?zone',t,re.I), 'no safe-zone spec'
assert re.search(r'duck',t,re.I), 'no ducking spec'
assert re.search(r'disclos',t,re.I), 'no AI disclosure placement'
assert re.search(r'\$0|free',t,re.I) and re.search(r'paid',t,re.I), 'missing a tool stack'
assert re.search(r'\b[AB]-\d{2}\b',t), 'shot list does not reference still IDs'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
print(f'assembly B OK — {n} markers')
"
```

- [ ] **Step 5: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-b>-assembly.md "$RUN_DIR/short-b/04-assembly/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-b>-assembly.md && git commit -m "content(rgs): Short B assembly and edit plan"
```

**Acceptance check:**
- Shot list references `A-NN`/`B-NN` IDs so reused assets are identifiable.
- Both tool stacks specified; safe zone marked unverified.
- AI disclosure has concrete placement and timing.

---

### Task 20: Short B — social repurpose copy

Same procedure as Task 14, against Short B's inputs.

**Files:**
- Create: `rgs-briefs/2026-07-28-<slug-b>-social-repurpose.md`
- Copy to: `<RUN_DIR>/short-b/05-repurpose/artifact.v1.md`

**Interfaces:**
- Consumes: Task 16 script, Task 15 packaging, Task 19 assembly plan.
- Produces: copy for the same six surfaces. Task 21 validates it.

- [ ] **Step 1: Invoke `social-repurpose`**

YouTube title/description/hashtags; TikTok and Instagram Reels captions; Bluesky, Threads,
and X text-only posts.

- [ ] **Step 2: State the asset constraint**

All three video surfaces take the identical export — no re-cut, no re-crop.

- [ ] **Step 3: Carry brand and policy constraints**

No banned lexicon; villain is the system; AI disclosure where required; health/injury
claims attributed in the copy.

**A3-specific check:** copy written from the kid's vantage must not read as an accusation
of the parent reading it.

- [ ] **Step 4: Verify**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-<slug-b>-social-repurpose.md').read_text('utf-8')
for s in ('YouTube','TikTok','Instagram','Bluesky','Threads','X'):
    assert re.search(rf'\b{s}\b',t), f'missing surface: {s}'
assert re.search(r'identical export|same export|no re-?cut',t,re.I), 'asset-constraint statement missing'
for w in ('bad parent','crush it','game-changer','the secret to'):
    assert w.lower() not in t.lower(), f'banned lexicon: {w}'
n=len(re.findall(r'\[(C|I|T|T-unverified)\]',t))
assert n>=5, f'only {n} markers'
print(f'repurpose B OK — {n} markers')
"
```

- [ ] **Step 5: Copy and commit**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && cp rgs-briefs/2026-07-28-<slug-b>-social-repurpose.md "$RUN_DIR/short-b/05-repurpose/artifact.v1.md" && git add rgs-briefs/2026-07-28-<slug-b>-social-repurpose.md && git commit -m "content(rgs): Short B multi-surface post copy"
```

**Acceptance check:**
- All six surfaces complete; identical-export statement present.
- No copy reads as an accusation of the parent.

---

### Task 21: Validation — three-persona cold read

**Files:**
- Create: `<RUN_DIR>/06-validation/persona-<1|2|3>.md` (three files)

**Interfaces:**
- Consumes: all twelve committed Short artifacts.
- Produces: three independent verdicts. Task 22 synthesizes them.

- [ ] **Step 1: Assemble the review packet**

```bash
cd /c/Projects/ContentStudio && ls rgs-briefs/2026-07-28-*.md
```

Each persona receives **only** the two Shorts' scripts, packaging, assembly plans, and post
copy. They do **not** receive the grounding briefs, the reference scan, the sparks, the
visual system, or this plan. The whole value of the panel is that it reads cold.

- [ ] **Step 2: Dispatch three subagents in parallel**

Dispatch all three in one message so they run concurrently. Each gets this prompt shape,
with `<PERSONA>` swapped:

````
You are <PERSONA>. You are NOT a content strategist, marketer, or reviewer — react as
this person actually would.

<PERSONA> definitions:
1. "A parent of an 11-year-old on a travel soccer team. You spend about $8,000 a year on
   it. You are privately exhausted and have never said so out loud."
2. "A dad of a 9-year-old who just got pushed to pick one sport year-round. You suspect
   this is too much but everyone around you seems certain it's normal."
3. "A youth sports coach of 12 years. You see families burn out from the inside and you
   are tired of content that blames parents."

Read the two YouTube Shorts packages below cold. For EACH Short, answer:

1. RELEVANT — does this speak to your actual life? Score 1–5, one sentence why.
2. COHERENT — did you follow it? Where exactly did you get lost, if anywhere?
   Score 1–5.
3. ENGAGING — would you watch past 2 seconds? Would you send it to another parent?
   Score 1–5. Quote the exact line that made you stay or leave.
4. BLAME TEST — does this make you feel judged, scolded, or blamed? Quote any line
   that does. This is the most important question; answer it honestly even if the
   rest is good.
5. TRUST TEST — do the claims feel earned or asserted? Does anything read as a
   stranger claiming medical authority?
6. The single change that would most improve it.

Be blunt. A polite review is a useless review.

DELIVERABLE FORMAT (hard limit ~1,500 tokens):
- Findings: bulleted, per Short, per question above
- Recommendation: 1–3 sentences
- Open questions: only if genuinely blocking

DO NOT:
- Paste full file contents or reproduce tool output verbatim
- Restate the task or narrate your process
- Include a preamble, closing summary, or sign-off

PACKAGES:
[paste the full text of both Shorts' -script.md, -concept-brief.md, -assembly.md, and
-social-repurpose.md]
````

- [ ] **Step 3: Save the three verdicts**

Write each subagent's response verbatim to `<RUN_DIR>/06-validation/persona-1.md`, `-2.md`,
`-3.md`.

- [ ] **Step 4: Verify**

```bash
cd /c/Projects/ContentStudio && RUN_DIR=$(find runs -maxdepth 1 -type d -name "rgs-debut-*" | sort | tail -1) && for f in "$RUN_DIR"/06-validation/persona-*.md; do echo "=== $f ==="; grep -ci "blame" "$f"; done && ls "$RUN_DIR"/06-validation/
```

Expected: three files, each with a blame-test answer.

**Acceptance check:**
- Three verdict files exist, from three independent agents.
- Each covers both Shorts across all six questions.
- Each blame-test answer is substantive, not a one-word "no."
- No persona was given the grounding briefs or the visual system.

- [ ] **Step 5: No commit yet**

Verdicts stay in the git-ignored run folder until Task 22 synthesizes them.

---

### Task 22: Revision loop and final validation report

**Files:**
- Create: `rgs-briefs/2026-07-28-rgs-debut-validation.md`
- Modify: whichever stage artifacts the findings route back to

**Interfaces:**
- Consumes: the three persona verdicts from Task 21.
- Produces: the final report and any revised artifacts. This is the last task.

- [ ] **Step 1: Triage the findings**

Route each finding to the stage that owns it:

| Finding type | Owning stage | Artifact to revise |
|---|---|---|
| Hook doesn't land / not engaging in 2s | scripting | `-script.md` |
| Blamed or judged | scripting, then repurpose | `-script.md`, `-social-repurpose.md` |
| Confusing / lost the thread | scripting | `-script.md` |
| Title/thumbnail mismatch | ideation | `-concept-brief.md` |
| Claim feels asserted or authority-ish | scripting + grounding | `-script.md`, brief |
| Caption/overlay unreadable or mistimed | assembly | `-assembly.md` |
| Post copy off-tone | repurpose | `-social-repurpose.md` |

**Severity rule:** any **blame-test failure** is blocking and must be fixed. A score of
1–2 on relevance, coherence, or engagement from **two or more** personas is blocking.
A single persona's 3 is noted, not fixed.

- [ ] **Step 2: Re-run the owning stages**

For each blocking finding, re-invoke the owning skill with the finding as explicit input,
rewrite the artifact, and commit:

```bash
cd /c/Projects/ContentStudio && git add rgs-briefs/2026-07-28-<slug>-<stage>.md && git commit -m "content(rgs): revise <slug> <stage> per validation round 1"
```

- [ ] **Step 3: Re-validate**

Dispatch the same three personas again with the revised packages, using the identical
prompt from Task 21 Step 2. Save to `persona-<1|2|3>-r2.md`.

- [ ] **Step 4: Stop at two rounds**

**Maximum two rounds.** Anything unresolved after round 2 is reported as open, not looped
on further.

- [ ] **Step 5: Write the final report**

````markdown
# RGS Debut Pair — Validation Report (2026-07-28)

## Panel

Three fresh agents, no pipeline context: the over-committed travel-team parent, the
quietly-uneasy dad, the youth coach. Each read both packages cold — scripts, packaging,
assembly plans, and post copy only.

## Round 1 scores

| Persona | Short | Relevant | Coherent | Engaging | Blame test | Trust test |
|---|---|---|---|---|---|---|

## Blocking findings and what changed

| # | Finding | Persona(s) | Owning stage | Change made |
|---|---|---|---|---|

## Round 2 scores

[same table]

## Still open

[Anything unresolved after round 2, stated plainly. "None" if none.]

## Verdict

- **Short A — <slug-a>:** [ready to generate assets / open items listed above]
- **Short B — <slug-b>:** [same]

## What to generate next

- Stills: [count] — see `2026-07-28-<slug-a>-visual-prompts.md` and
  `2026-07-28-<slug-b>-visual-prompts.md`
- i2v clips: [count]
- Voiceover: two ElevenLabs runs, payloads in the two `-voiceover-brief.md` files,
  estimated [N] credits total
- Thumbnails: 2, layouts in the two `-concept-brief.md` files
````

- [ ] **Step 6: Verify and commit**

```bash
cd /c/Projects/ContentStudio && ./.venv/Scripts/python.exe -c "
import pathlib,re
t=pathlib.Path('rgs-briefs/2026-07-28-rgs-debut-validation.md').read_text('utf-8')
for h in ('## Panel','## Round 1 scores','## Blocking findings','## Still open','## Verdict','## What to generate next'):
    assert h in t, f'missing section: {h}'
assert re.search(r'Short A',t) and re.search(r'Short B',t), 'both Shorts must have verdicts'
print('validation report OK')
" && git add rgs-briefs/2026-07-28-rgs-debut-validation.md && git commit -m "content(rgs): validation report for the debut pair"
```

- [ ] **Step 7: Final inventory**

```bash
cd /c/Projects/ContentStudio && ls rgs-briefs/2026-07-28-*.md && echo "--- count ---" && ls rgs-briefs/2026-07-28-*.md | wc -l && echo "--- clean tree? ---" && git status --porcelain
```

Expected: 16 files (scan, sparks, visual system, validation, 2 grounding briefs, 2×6 stage
artifacts minus the 2 counted as grounding = 16), and a clean tree.

**Acceptance check:**
- Every blame-test failure from round 1 was fixed and re-validated.
- Round 2 scores are recorded, or the report states that round 1 was clean.
- Anything still open is stated plainly — not hidden.
- The "What to generate next" section gives real counts, so the next action is generating
  assets with zero further decisions.
- Working tree is clean; 16 committed artifacts.

---

## Self-review notes

**Spec coverage:** §4 run layout → Task 1 (corrected: `runs/` is git-ignored, so committed
deliverables go to `rgs-briefs/` per the repo's existing convention). §5 reference scan →
Tasks 2–4. §6 sparks and archetypes → Task 5. §7 pipeline stages → Tasks 6–7, 9–20. §8
asset economy → Task 8 (system lock), Task 12 (pool), Task 18 (REUSE/NEW enforcement).
§9 validation → Tasks 21–22. §10 risks → Task 1 Steps 2–3 (toolchain/network), Task 3 Step
3 (transcript shortfall), Tasks 6–7 Step 3 (edition drift), Task 5 Step 2 and Task 15 Step
4 (spark convergence), Task 8 (motif divergence), Task 22 Step 4 (loop cap).

**Known deviation from spec:** the spec's §4 says run artifacts are committed. They are
not — `.gitignore:20` ignores `runs/`. The plan commits to `rgs-briefs/` instead and keeps
`runs/` as scratch, matching the existing `2026-07-25-let-kids-play-act-specialization-*`
artifact set.

**Placeholder scan:** `<slug-a>` and `<slug-b>` are the only unresolved tokens; they are
deliberately fixed in Task 5 Step 3 and used verbatim thereafter. Bracketed content inside
document templates is content to be authored, not a plan gap.

**ID consistency:** `A-NN` still IDs are created in Task 12 Step 5, read in Task 18 Step 1,
enforced in Task 18 Step 6, and referenced in Task 19 Step 3. `RUN_DIR` is created in Task 1
Step 4 and re-derived by the same `find … | sort | tail -1` idiom in every later task.
