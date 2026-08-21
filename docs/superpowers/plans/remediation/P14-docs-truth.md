# P14 — Doc truth

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended)
> or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Binding:** the Global Constraints and the test standard in
> [`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md) apply to every task here.
>
> **Wave C — this package executes LAST.** Six packages owe it contract decisions. Nothing in
> §4 may be implemented by guessing an upstream answer; §2 is the gate.

**The thesis of this package.** Every other package changes code. This one makes the repo's own
documentation true about the code the other fifteen just changed — and, where possible, makes each
documented claim *executable*, so it fails a test the day it stops being true. Four of the
contradictions closed here existed because a prose promise was written once and never checked
again. A prose promise nobody checks is how the repo got them.

---

## 1. Scope

### Files owned by P14 (no other package may touch these)

```
CLAUDE.md                                              (repo root)
README.md                                              (repo root)
pipeline-app/README.md
docs/README.md
rgs-briefs/README.md
rgs-briefs/2026-07-25-let-kids-play-act-script.md
rgs-briefs/2026-07-28-rgs-debut-visual-system.md
docs/audit/appendix-F-tests.md                         (corrections only)
```

Eight files. `README.md` at the repo root is owned but, on the plan below, is only *read* — by
`test_no_doc_claims_a_bare_pytest_is_sufficient` and
`test_every_script_path_a_readme_tells_you_to_run_exists`. It is listed so no other package edits
it while those checks depend on it.

**Two of the owned files are immutable and P14 does not edit them.**
`rgs-briefs/2026-07-25-let-kids-play-act-script.md` and
`rgs-briefs/2026-07-28-rgs-debut-visual-system.md` are versioned artifacts protected by the
`PreToolUse` hook `.claude/hooks/protect_briefs.py` (`rgs-briefs/README.md:96-98`). They are listed
as owned so that no other package edits them either, and so that C-53 and D-53 are resolved
*around* them — by changing the rule and the narration, never the artifact. Any task below that
appears to want an edit inside one of these two files is wrong; re-read this paragraph.

### One new file created by P14

```
tests/test_doc_truth.py          (new; not in any package's audited file list)
```

This is the executable half of the package. It lands in the **repo-root** suite (`pytest.ini`
carries `testpaths = tests`, so it is collected there). It is stdlib + `pytest` only, imports no
app code, and reads documents as text. P14 creates it and no other package modifies it.

**One P0 coupling:** `test_documented_test_commands_collect_what_the_docs_claim` shells out. P0's
`conftest.py` network/subprocess guard will block that unless the test carries
`@pytest.mark.allow_subprocess` (frozen interface, orchestration plan §"conftest.py network
guard"). Apply the marker; do not weaken the guard.

### Findings (9)

`B-80` · `C-52` · `C-53` · `D-40` · `D-53` · `F-10` · `F-29` · `F-30` · `F-62`

### Explicitly out of scope

- Producing a real `styleboard` or `music` artifact (C-52's `fix_cost: M` second half). P14
  documents the contract those stages must honour and states out loud that it is untested. The
  first real artifact is a production job, not a remediation task.
- Backfilling `kind:` onto the ten 2026-07-25 stage artifacts (C-53's first option). Nine of the
  ten are not P14's files and all ten are hook-immutable. P14 takes the second option — the
  positive discriminator — see Task 6.
- `.claude/skills/**` (P13), `pytest.ini` / `conftest.py` / CI (P0), `discovery_digest.py` (P9),
  `migrate_handles_from_manifest.py` (P10), `pipeline.yaml` / stage templates (P4).

---

## 2. Inputs required (the gate)

P14 cannot start Task 2, 3, 6, 9, 10 or 11 until the named package reports. Each row states the
decision needed and the exact doc sentence that changes once it arrives. **Do not guess. Do not
document today's broken state as the target.** If a package reports "no change", that is a valid
answer and the "unchanged" wording branch applies.

| # | From | Status | Decision / what is still needed | Doc sentence affected | P14 task |
|---|---|---|---|---|---|
| I1 | **P0** | **RESOLVED (structure) / OPEN (counts)** | **Two suites and two rootdirs survive.** The F-64 rename landed as `pipeline-app/scripts/` → **`pipeline-app/tools/`** (one atomic commit, accepted by P8 and P10) — it removes the name collision with the repo-root `scripts/` package but does **not** merge the suites. `python -m pytest` stays mandatory in both. **Still needed:** the authoritative collected-test count per suite once every package's tests land (baseline 201 root / 833 app / 1,034 total). | `CLAUDE.md` Conventions, final bullet. `pipeline-app/README.md` §Test. | T2 |
| I2 | **P0** | **RESOLVED** | **No single runner entry point.** P0 is adding markers and a banner; it is explicitly **not** making a bare `pytest` correct. Document `python -m pytest` per suite. Outcome A in T2.3; outcomes B and C are struck. | `CLAUDE.md` Conventions test bullet; `pipeline-app/README.md` §Test. | T2 |
| I3 | **P10** | **RESOLVED (path) / OPEN (spelling)** | The seeding script now lives under `pipeline-app/tools/`. **Still needed:** P10's preferred verbatim invocation — ask P10 directly. Assume `python -m tools.migrate_handles_from_manifest` **only** as a placeholder and replace it before committing. Idempotence (`INSERT OR IGNORE`, no deletion of hand-added rows) is unchanged. | `pipeline-app/README.md` §Setup — the new "Seed the discovery roster" step. | T3 |
| I4 | **P13** | **RESOLVED** | The unmarked-`[C]`-default **survives, scoped to `docs/*.md` only**, with a reciprocal half-sentence in CLAUDE.md. P13's triage: 533 normative blocks, 367 unmarked, of which **215 are real skill-side bugs**; the remainder are 113 RGS alternative-vocabulary lines, 27 worked-example illustrations, 12 structural pointers. Outcome A in T9.3, amended below; outcome B is struck. **Mirror P13's vocabulary names exactly** as they appear in its `ALTERNATIVE_VOCABULARY` test constant. | `docs/README.md:56` **and** `CLAUDE.md:40-43`. | T9 |
| I5 | **P13** | **OPEN** | The canonical `kind:` token for the two never-written stages — `styleboard` vs `style-board`, `music` vs `music-brief` vs `bed-arc` — the `stage:` ordinal each takes, and the resolution of the one on-disk `kind: visual-prompt-sheet` against the six `kind: visual-prompts`. | `rgs-briefs/README.md` §Naming, §Front-matter schema, §`kind:` vocabulary. | T5 |
| I6 | **P13** | **OPEN** | Confirmation that `rgs-grounding` and `rgs-pairing-review` now select grounding briefs **positively** (`thinker` AND `concept` AND `research_codes`) rather than by "lacks `kind:`". If P13 keeps the negative rule, P14 is blocked — see T6.1. | `rgs-briefs/README.md` §"Two file kinds". | T6 |
| I7 | **P6 + P9** | **OPEN** | Is the YouTube-shaped `upload_date` alias removed from `discovery_digest.py`, or retained as a named exception? Orchestrator confirms this is still unresolved — do not guess. | `CLAUDE.md`, "Adding a discovery platform" — the "**no change to any email-side module**" clause. | T10 |
| I8 | **P9** | **RESOLVED** | **The code stays; CLAUDE.md changes.** Capping the excerpt below 280 chars would gut the digest and still would not make "never a full post body" true, because any post shorter than the cap is fully included by definition — the promise is unachievable as worded. P9 pinned the real behaviour in an `email_render.DISCLOSURE` constant; **take the replacement wording verbatim from P9's §6.2(a)**, do not draft your own. Outcome B in T11.3, amended below; outcome A is struck. | `CLAUDE.md` Conventions, exception 1. | T11 |
| I9 | **P4** | **RESOLVED** | `styleboard` and `music` remain stages under those ids. P4 fixed the **graph**, not the skill declarations, because the skills' declared inputs are corpus-traced craft requirements and `pipeline.yaml` had under-declared them: `assembly.depends_on` = `[scripting, styleboard, voiceover, visual]` with a new **`optional_depends_on: [music]`**; `repurpose.depends_on` = `[ideation, scripting, assembly]`. | `rgs-briefs/README.md` §Naming enumeration; `test_rgs_briefs_readme_enumerates_every_producing_pipeline_stage`. | T5 |

**Also resolved, affecting T1 (D-40).** P15 is **vendoring htmx** to
`pipeline-app/pipeline_app/static/htmx-2.0.0.min.js` and deleting the `unpkg.com` reference,
guarded by a P15 test that fails on any `http(s)://` in `templates/**`. The CDN therefore leaves
the outbound roster. The audit's figure is **14 call sites across 9 destinations**; recount against
the **post-fix** state, not today's — see T1.2.

**Recording the answers.** Before implementing, append an "Inputs received" block to the bottom of
this plan file with each input id, the answering package, the date and the verbatim decision. A
task implemented without its row filled in is a plan violation. Six rows above are already
answered; transcribe them there too rather than relying on this table.

---

## 3. Finding → task map

Total coverage: 9 findings, 9 mapped. No finding is unmapped; no task is findingless except the
three relay tasks and the inventory task, which are labelled as such.

| Finding | Sev | What is untrue today | Task |
|---|---|---|---|
| **D-40** | S2 | `CLAUDE.md:194` says there are exactly two outbound network dependencies. The audit counted 14 call sites across 9 destinations, including a billed API and the Anthropic call that is the app's whole purpose. | **T1** |
| **F-62** | S2 | `CLAUDE.md:236-237` says a bare `pytest` "does the right thing in both places". In `pipeline-app/` it fails collection on four files. | **T2** |
| **F-30** | S2 | A bare `pytest` at the repo root prints "201 passed", exits 0, and silently omits 833 app tests. Nothing documents this. | **T2** |
| **B-80** | S2 | The roster-seeding step exists only in a historical plan doc. A fresh checkout following `pipeline-app/README.md` never seeds `handles`, and every discovery run then completes cleanly having fetched nothing. | **T3** |
| **D-53** | S4 | `CLAUDE.md:159-167` enumerates exactly two places FamilyBrain is narrated as history. `rgs-briefs/2026-07-28-rgs-debut-visual-system.md:23` is an unlisted third. | **T4** |
| **C-52** | S3 | `rgs-briefs/README.md:28` enumerates six stages; the pipeline has eight producing stages. `styleboard` and `music` are absent from the contract and have zero artifacts on disk. | **T5** |
| **C-53** | S2 | `rgs-briefs/README.md:39` tells consumers to skip files with `kind:`. Ten stage artifacts predate `kind:` and are therefore read as grounding briefs. | **T6** |
| **F-29** | S3 | `appendix-F-tests.md` §6 was corrected to 11, but `:165` still says "the 2-test `test_turn_service.py`" and `:557` credits the corrected number to the very grep method §5 retracted. | **T7** |
| **F-10** | S1 | 32 S0/S1 defects, 29 of them one assertion away, zero tests written. Nothing in the repo requires a defect writeup to name the assertion that would have caught it, so the gap was measurable only by a one-off audit. | **T8** |

**Relay and hygiene tasks (no P14 finding id — they exist because P14 owns the file):**

| Task | Why |
|---|---|
| **T9** | Provenance-rule reconciliation between `docs/README.md:56` and `CLAUDE.md:40-43`. Driven by P13's triage (I4). |
| **T10** | Adapter-contract sentence in `CLAUDE.md`. Driven by P6/P9 (I7). |
| **T11** | Email-privacy sentence in `CLAUDE.md`. Driven by P9 (I8). |
| **T12** | `docs/README.md` inventory truth: "the five guides" is now nine documents, and the "One further guide sits outside the corpus" vendor-runbook section lists one of two. Not a filed finding — corrected because P14 owns the file and T12's own check would otherwise fail on it. |
| **T13** | Full verification sweep. |

---

## 4. Tasks

Order: T1 → T7 → T8 → T12 (no upstream dependency, do these first) → T2, T3, T4, T5, T6, T9, T10,
T11 (gated on §2) → T13.

Commit after each task. `docs:` for prose-only tasks, `test:` for the test-first step of each.

---

### T1 — CLAUDE.md tells the truth about the network (D-40)

The current bullet claims two outbound dependencies. This replaces it with a measured roster, and
with a test that fails the day the roster and the code disagree in *either* direction.

> **Amendment, 2026-08-21 (P14 kickoff, before T1 dispatch).** The `OUTBOUND_PROBES` list below
> was corrected after a first implementer dispatch surfaced that the code had been refactored
> since this plan's `[C]`ode was drafted, in ways the original probes silently mismatched:
> `discovery_youtube.py`'s three separate inline yt-dlp calls were centralized into one
> `_run_ytdlp()` helper called from three sites (`:157`, `:262`, `:403`), and the original
> `["']yt-dlp["']` literal-string probe both missed those call sites entirely (no literal string on
> the `subprocess.run(cmd, ...)` line itself) and over-matched unrelated label/dict-value strings
> (`source = "yt-dlp"`, `_SOURCE_RANK = {"yt-dlp": 1}`) that are not call sites. Separately,
> `comment_draft.py`'s real Anthropic subprocess call builds its argv via `cli_runner.platform_argv(`,
> not `build_claude_argv(` — the original `claude subprocess` probe never matched it. The corrected
> probes below were verified against every true- and false-positive line found in the live tree
> (see `tests/test_doc_truth.py`'s own T1.2 measured roster once T1 lands) before this amendment.
> No other part of T1 changes.

- [ ] **T1.1 (test first).** Create `tests/test_doc_truth.py` with the enumerator and the first
  check. Run it. It must fail with "call sites in code but not in CLAUDE.md: …" listing every row
  the current two-item bullet omits.

```python
"""Executable checks on the repo's own documentation.

Every assertion here corresponds to a claim some README or CLAUDE.md makes about the
code. The audit (2026-08-08) found four such claims false at once, all of them written
once and never checked again. These tests are the checking.

Stdlib + pytest only. No app imports -- the root suite must stay import-free of
pipeline_app, and these read documents as text anyway.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO / "CLAUDE.md"

# Each probe is (regex, destination-label). A match is an outbound call site.
# Adding a network dependency means adding its probe here AND its row to
# CLAUDE.md -- the test below fails until both exist.
#
# The CDN probe should match nothing: P15 vendored htmx to static/ and deleted the
# unpkg.com reference. It stays as a reintroduction guard, redundant with -- not a
# replacement for -- P15's own templates/** check.
OUTBOUND_PROBES = [
    (re.compile(r"""<script[^>]+src=["']https?://"""), "third-party CDN"),
    (re.compile(r"\brequests\.(?:get|post|put|patch|delete)\s*\("), "requests"),
    (re.compile(r"\burllib\.request\.urlopen\s*\("), "urllib"),
    (re.compile(r"""\[\s*["']yt-dlp["']|["']yt-dlp["']\s*,\s*["']"""), "yt-dlp subprocess (inline argv)"),
    (re.compile(r"(?<!def )\b_run_ytdlp\s*\("), "yt-dlp subprocess (centralized helper)"),
    (re.compile(r"\bYouTubeTranscriptApi\s*\("), "youtube-transcript-api"),
    (re.compile(r"(?<!def )\bplatform_argv\s*\("), "claude subprocess"),
    (re.compile(r"\bsession\.get\s*\("), "requests session"),
]

SCANNED = [
    "pipeline-app/pipeline_app/**/*.py",
    "pipeline-app/pipeline_app/templates/*.html",
    "pipeline-app/tools/*.py",    # post-F-64 rename of pipeline-app/scripts/
    "download_*.py",
]

# A table row cites one path and one or more line numbers:
#   `pipeline_app/brightdata_job.py:64` (trigger), `:76` (poll), `:86` (fetch)
ROW_PATH_RE = re.compile(r"`([\w./-]+\.(?:py|html)):(\d+)`")
ROW_EXTRA_LINE_RE = re.compile(r"`:(\d+)`")


def _measured_call_sites() -> set[str]:
    found = set()
    for pattern in SCANNED:
        for path in REPO.glob(pattern):
            if "test" in path.parts or path.name.startswith("test_"):
                continue
            rel = path.relative_to(REPO).as_posix()
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if line.lstrip().startswith("#"):
                    continue
                if any(rx.search(line) for rx, _ in OUTBOUND_PROBES):
                    found.add(f"{rel}:{lineno}")
    return found


def _network_section() -> str:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    return text[text.index("- **Local only**"): text.index("- **Adding a discovery platform.**")]


def _normalise(path_token: str) -> str:
    """CLAUDE.md cites app modules as `pipeline_app/x.py`; make it repo-relative."""
    if not (REPO / path_token).exists() and (REPO / "pipeline-app" / path_token).exists():
        return f"pipeline-app/{path_token}"
    return path_token


def _documented_call_sites() -> set[str]:
    cited = set()
    for row in _network_section().splitlines():
        anchors = ROW_PATH_RE.findall(row)
        if not anchors:
            continue
        rel = _normalise(anchors[0][0])
        linenos = {lineno for _, lineno in anchors} | set(ROW_EXTRA_LINE_RE.findall(row))
        cited |= {f"{rel}:{lineno}" for lineno in linenos}
    return cited


def _documented_destinations() -> set[str]:
    """First cell of every table row that carries a call-site citation."""
    return {
        row.split("|")[1].strip()
        for row in _network_section().splitlines()
        if row.startswith("|") and ROW_PATH_RE.search(row)
    }


def test_claude_md_lists_every_outbound_call_site():
    measured = _measured_call_sites()
    documented = _documented_call_sites()
    undocumented = sorted(measured - documented)
    phantom = sorted(documented - measured)
    assert not undocumented, (
        "outbound call sites in the code but not in CLAUDE.md's network table:\n  "
        + "\n  ".join(undocumented)
        + "\nAdd a row, or remove the dependency."
    )
    assert not phantom, (
        "CLAUDE.md's network table cites call sites that no longer exist:\n  "
        + "\n  ".join(phantom)
    )
```

- [ ] **T1.2.** Run `python -m pytest tests/test_doc_truth.py -v` and paste the failure list into
  the commit body. **That list is the roster** — it is the authority for the table's rows, not the
  draft below. The audit's figure is *14 call sites across 9 destinations*, but **recount against
  the post-fix state, not today's**: P15 has vendored htmx to
  `pipeline-app/pipeline_app/static/htmx-2.0.0.min.js` and deleted the `unpkg.com` reference, so
  the CDN leaves the roster; multi-call modules like `brightdata_job.py` contribute three sites
  each. **Do not paste "14" into the doc without running the enumerator against the merged tree.**
  Whatever it reports is what the prose states, because T1.3 compares them.

- [ ] **T1.3.** Add the numeral check, so the prose count cannot drift from the table:

```python
COUNT_RE = re.compile(
    r"\*\*(\d+)\*\*\s+outbound call sites? across\s+\*\*(\d+)\*\*\s+destinations"
)


def test_claude_md_network_counts_match_its_own_table():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    match = COUNT_RE.search(text)
    assert match, "CLAUDE.md must state the call-site and destination counts in the documented form"
    claimed_sites, claimed_dests = int(match.group(1)), int(match.group(2))
    assert claimed_sites == len(_measured_call_sites()), (
        "CLAUDE.md's call-site count disagrees with the measured code"
    )
    rows = _documented_destinations()  # distinct values in the table's first column
    assert claimed_dests == len(rows), "CLAUDE.md's destination count disagrees with its own table"
```

- [ ] **T1.4.** Replace `CLAUDE.md`'s current `- Local only.` and `- **Exceptions to "local only":**`
  bullets (lines 193–208) with the following. Fill `N` / `M` and every `file:line` from T1.2's
  output; keep both existing exception rationales verbatim, per D-40's proposed fix.

```markdown
- **Local only** in the sense that nothing here deploys, is hosted externally, or syncs to a
  cloud — but **not** network-free. The repo makes **N** outbound call sites across **M**
  destinations. The tables below are the complete roster;
  `tests/test_doc_truth.py::test_claude_md_lists_every_outbound_call_site` fails if a call site
  exists in the code and not here, or here and not in the code, so this list cannot quietly rot
  the way its two-item predecessor did.

  **App runtime** — reached by running the app or letting the scheduled discovery run fire. No
  operator action required beyond starting it:

  | Destination | Call site(s) | Cost | What leaves this machine |
  |---|---|---|---|
  | Anthropic, via a `claude` subprocess | `pipeline_app/cli_runner.py:239` | **billed to your Claude plan** | Every pipeline stage turn: the rendered kickoff prompt, plus whatever the stage's allowed tools read from this repo. This call *is* the app. |
  | Anthropic, via a `claude -p` subprocess | `pipeline_app/comment_draft.py:253` | **billed** | Exception 2 below. |
  | `api.resend.com` | `pipeline_app/discovery_notify.py:68` | free tier | Exception 1 below. |
  | `api.brightdata.com` | `pipeline_app/brightdata_job.py:64` (trigger), `:76` (poll), `:86` (fetch) | **billed per record — real money, per run** | The target handle or profile URL and the job parameters, for Instagram / LinkedIn / Facebook / X discovery. |
  | `www.googleapis.com/youtube/v3` | `pipeline_app/discovery_youtube_api.py:92` | quota-metered | Video ids and the API key. |
  | `public.api.bsky.app` | `pipeline_app/discovery_bluesky.py:22` | free | The handle being enumerated. |
  | `www.youtube.com`, via `yt-dlp` | `pipeline_app/discovery_youtube.py:61`, `:139`, `:217` | free | The handle or video id — and the session cookies in `pipeline-app/cookies.txt` when that file exists. |
  | `www.youtube.com`, via `youtube-transcript-api` | `pipeline_app/discovery_youtube.py:192` | free | The video id. |

  **Manual toolkit** — only when you run a downloader script by hand. Never reached by the app or
  by the scheduled task:

  | Destination | Call site(s) | What leaves this machine |
  |---|---|---|
  | Project Gutenberg / `archive.org` | `download_thinkers.py:104` | The work URLs listed in `manifests/thinkers.json`. |
  | `public.api.bsky.app` | `download_brandintel.py:69` | The handle being enumerated. |
  | `www.youtube.com`, via `yt-dlp` / `youtube-transcript-api` | `download_brandintel.py:78`, `:91`, `:131`, `:160` | The handle or video id. |

  **Two of these carry corpus content rather than just an identifier.** Both are in the daily
  discovery email path and both are deliberate; their contracts are unchanged:

  1. **Notification email, via Resend's HTTP API.** Sends the day's captured post titles, author
     display names (a handle appears only when no display name is configured for that author),
     engagement metrics, publish dates when known, and post URLs; a ~400 character excerpt of the
     one post the email spotlights; and three AI-drafted comments on it. Never a full transcript,
     never a full post body, never any other corpus content.
     *(Placeholder only — **T11 replaces this paragraph verbatim from P9's §6.2(a)**, pinned to
     `email_render.DISCLOSURE`. If T11 has already run, do not reinstate this text.)*
  2. **Comment drafting, via a `claude -p` subprocess** (`pipeline_app/comment_draft.py`). Sends
     the spotlighted post's full text, or a YouTube transcript truncated to 12,000 characters, to
     Anthropic. One post per day, only the spotlighted one. The turn runs with every tool denied,
     zero MCP servers, and an empty scratch working directory.

  See `docs/superpowers/specs/2026-08-01-discovery-email-summary-design.md` and
  `docs/superpowers/specs/2026-08-08-morning-email-social-expansion-design.md` for the full
  rationale. Adding a **new** destination is a decision, not a detail: it needs a probe in
  `tests/test_doc_truth.py` and a row here in the same commit.

  **Front-end assets are vendored, never fetched.** htmx ships from
  `pipeline_app/static/htmx-2.0.0.min.js`; there is no CDN in the page load path, and a P15 test
  fails on any `http(s)://` appearing under `templates/**`. Do not reintroduce one.
```

- [ ] **T1.5.** Re-run. Both checks green. Commit `docs: enumerate every outbound call site in CLAUDE.md (D-40)`.

---

### T2 — The documented test command is the one that works (F-30, F-62) — **I1/I2 resolved; counts still open**

**P0 has reported.** Two suites and two rootdirs survive; `pipeline-app/scripts/` is renamed
**`pipeline-app/tools/`**, which removes the name collision with the repo-root `scripts/` package
but does not merge the suites. There is no single runner entry point — P0 adds markers and a
banner and is explicitly **not** making a bare `pytest` correct. **Outcome A below is the one to
implement; outcomes B and C are struck** and retained only so a future reader can see what was
considered and rejected.

- [ ] **T2.1.** Obtain the one thing still open in I1: the authoritative collected-test count per
  suite once every package's tests have landed. Measure it yourself at T2 time
  (`python -m pytest tests/ --collect-only -q` and the app equivalent) rather than reusing the
  2026-08-08 baseline of 201 / 833 / 1,034 — every package added tests. Do not write a count you
  have not just observed.

> **Amendment, 2026-08-21 (found by the T2 task reviewer, fixed before this task closes).** The
> code below has been corrected from its first draft. The original `COMMAND_BLOCK_RE`/
> `_claimed_counts` pair only ever recognised a command block whose captured text STARTS with
> literal `python -m pytest` — but T2.3's own target prose documents the app suite as
> `cd pipeline-app && python -m pytest` (a compound command, `cd` first). Against the corrected
> CLAUDE.md text this meant: the app-suite command was never extracted at all (so never run, never
> count-checked), and the per-doc `cwd` selection (based on `doc_name` alone) had no way to run a
> `cd`-prefixed command from the right directory even if it had been extracted, since `CLAUDE.md`
> documents commands for BOTH suites in one file. `pipeline-app/README.md`'s own command WAS
> extracted and run (it's a bare `python -m pytest`, no `cd` prefix, preceded by a separate `cd
> pipeline-app` line) — its collection success was checked, but its claimed count never was,
> because its prose states the count in a separate sentence with no backtick-quoted command on the
> same line, and the regex requires both on one line. Net effect: only the ROOT suite's count was
> ever actually pinned by an equality assertion; the APP suite's count (in both files) was pure
> prose nobody checked — precisely the class of defect this whole task exists to eliminate. Fixed
> below by teaching the regex/test the compound-command shape, and (T2.4, below) rewording
> `pipeline-app/README.md`'s prose to co-locate its command and count on one line, the same style
> `T2.3`'s own target text already uses for the root suite. Verified end to end against the live
> tree before this amendment landed: both files, both commands, both counts, all four checks green.

- [ ] **T2.2 (test first).** Add the check that runs *the command the doc states*, not a copy of it.
  The doc is the input; that is the whole point.

```python
COMMAND_BLOCK_RE = re.compile(
    r"^\s{4,}((?:cd pipeline-app && )?python -m pytest[^\n]*)$", re.MULTILINE
)


def _documented_commands(doc: Path) -> list[str]:
    return [c.strip() for c in COMMAND_BLOCK_RE.findall(doc.read_text(encoding="utf-8"))]


def _claimed_counts(doc: Path) -> dict[str, int]:
    """Maps a documented command to the test count the same doc claims for it."""
    text = doc.read_text(encoding="utf-8")
    return {
        cmd: int(n)
        for cmd, n in re.findall(
            r"`((?:cd pipeline-app && )?python -m pytest[^`]*)`[^\n]*?\b([\d,]+) tests",
            text.replace(",", ""),
        )
    }


@pytest.mark.allow_subprocess
@pytest.mark.parametrize("doc_name", ["CLAUDE.md", "pipeline-app/README.md"])
def test_documented_test_commands_collect_what_the_docs_claim(doc_name):
    if os.environ.get("DOC_TRUTH_CHILD"):
        pytest.skip("child collection run; do not recurse")
    doc = REPO / doc_name
    commands = _documented_commands(doc)
    assert commands, f"{doc_name} must document its test invocation as an indented command block"
    env = {**os.environ, "DOC_TRUTH_CHILD": "1"}
    for command in commands:
        prefix = "cd pipeline-app && "
        if command.startswith(prefix):
            cwd = REPO / "pipeline-app"
            pytest_part = command[len(prefix):]
        else:
            cwd = REPO / "pipeline-app" if doc_name.startswith("pipeline-app") else REPO
            pytest_part = command
        argv = [sys.executable, "-m", "pytest", "--collect-only", "-q",
                "-p", "no:cacheprovider", *pytest_part.split()[3:]]
        proc = subprocess.run(argv, cwd=cwd, capture_output=True,
                              encoding="utf-8", errors="replace", env=env)
        assert proc.returncode == 0, (
            f"{doc_name} documents `{command}`, which does not collect cleanly:\n{proc.stdout}\n{proc.stderr}"
        )
        collected = int(re.search(r"(\d+) tests? collected", proc.stdout).group(1))
        claimed = _claimed_counts(doc).get(command)
        assert claimed is not None, (
            f"{doc_name} documents `{command}` but never states its test count in the "
            "`{command}` ... NNN tests` form on the same line -- an unchecked count is the "
            "defect this test exists to catch"
        )
        assert collected == claimed, (
            f"{doc_name} claims `{command}` runs {claimed} tests; it collects {collected}"
        )


def test_no_doc_claims_a_bare_pytest_is_sufficient():
    """F-62's exact sentence, pinned dead. Bare `pytest` in pipeline-app/ fails collection
    on four files; at the repo root it silently omits 80% of the suite."""
    for doc in (CLAUDE_MD, REPO / "pipeline-app" / "README.md", REPO / "README.md"):
        text = doc.read_text(encoding="utf-8")
        assert "does the right thing in both places" not in text, (
            f"{doc.name} still carries the retracted bare-pytest claim (F-62)"
        )
```

  Run it. It fails: the current `pipeline-app/README.md` §Test documents `python -m pytest` with no
  claimed count, and `CLAUDE.md` still contains the retracted sentence.

- [ ] **T2.3 — outcome A — IMPLEMENT THIS ONE.** Two suites survive. Replace `CLAUDE.md`'s final
  Conventions bullet (lines 232–237) with:

```markdown
- **Tests live in two suites, each run from its own directory, and `python -m pytest` is
  mandatory — not a style preference.**

      python -m pytest tests/

      cd pipeline-app && python -m pytest

  `python -m pytest tests/` at the repo root is the linter / doc-truth / skill-provenance suite
  (`NNN tests`). `cd pipeline-app && python -m pytest` is the app suite (`NNN tests`). **Both must
  be run; neither is a superset of the other.** Three traps, all measured on 2026-08-08:

  - **A bare `pytest` at the repo root is silently wrong.** `pytest.ini`'s `testpaths = tests`
    scopes it to the root suite, so it prints a pass line and exits 0 while never running the app
    suite — four fifths of the repo's tests. A green bare `pytest` is not evidence of anything.
  - **A bare `pytest` inside `pipeline-app/` fails collection.** The console-script entry point
    does not prepend the cwd to `sys.path`; `python -m` does. Without it, the four modules that
    import the app's local `tools` package — `test_backfill_youtube_frontmatter.py`,
    `test_migrate_handles.py`, `test_run_discovery_cron.py`, `test_setup_discovery_task.py` —
    raise `ModuleNotFoundError`. **Re-measure the exact error text at T2 time** and quote what you
    observe: `pipeline-app/scripts/` was renamed `pipeline-app/tools/` on 2026-08-08 (finding
    F-64), so the pre-rename message naming `'scripts'` is stale.
  - **Running the app suite from the repo root is still wrong.** The `tools/` rename removed the
    name collision with the repo-root `scripts/` package, but `pipeline-app` is not on `sys.path`
    from there, so the same four modules fail to import. Verify and quote the current behaviour
    rather than reusing the pre-rename description.

  `tests/test_doc_truth.py::test_documented_test_commands_collect_what_the_docs_claim` executes
  the two commands above exactly as written here and fails if either stops collecting the stated
  count.
```

- [ ] ~~**T2.3 — outcome B: P0 merged the suites.**~~ **STRUCK — P0 kept two suites.** Retained for
  the record only; do not implement.

```markdown
- **One suite, one command.**

      python -m pytest

  Run from the repo root; it collects all `NNN` tests across both trees. `pipeline-app/scripts/`
  was renamed to `pipeline_app/scripts/` so the repo-root `scripts/` package can no longer shadow
  it, and the root `pytest.ini` now carries `testpaths = tests pipeline-app/tests`. There is no
  second rootdir and no second command.

  **Keep the `python -m` form.** It prepends the cwd to `sys.path`, which is what makes *this
  checkout* the thing under test rather than any installed copy of `pipeline_app` — the failure
  mode finding F-63 recorded, where a worktree silently tested the main checkout. The bare
  `pytest` console script does not do this.

  `tests/test_doc_truth.py::test_documented_test_commands_collect_what_the_docs_claim` executes
  the command above exactly as written here and fails if it stops collecting the stated count.
```

- [ ] ~~**T2.3 — outcome C: a single runner entry point.**~~ **STRUCK — P0 introduced none.**
  Retained for the record only; do not implement.

```markdown
- **Run the tests with `<P0's runner invocation>`.** It runs every suite from its own rootdir and
  exits non-zero if any of them does. This exists because "the tests pass" had two meanings and
  the cheaper one was wrong: a bare `pytest` at the repo root prints a pass line, exits 0, and
  never runs the app suite. The underlying commands, if you need one in isolation:

      python -m pytest tests/

      cd pipeline-app && python -m pytest

  `python -m` is mandatory in both — the bare console script does not prepend the cwd to
  `sys.path`, and four app-suite modules fail to import without it.
```

- [ ] **T2.4.** Replace `pipeline-app/README.md`'s `## Test` section with:

```markdown
## Test

Run from this directory. `python -m` is required, not optional — a bare `pytest` here fails
collection on the modules that import the local `tools` package, because the console-script
entry point does not put the cwd on `sys.path`.

    cd pipeline-app
    python -m pytest

`python -m pytest` is the app suite (`NNN tests`). It is **not** run by a `pytest` at the repo
root, which is scoped by `testpaths` to a separate root suite (`NNN tests`). Both must pass before
anything here is called green.
```

  Note the count and its command are on the same sentence — `test_documented_test_commands_collect_what_the_docs_claim`
  requires the two co-located on one line to pin the claimed count against the measured one; two
  separate sentences ("This is the app suite: `NNN tests`.") leave the count unchecked. Keep this
  form.

- [ ] **T2.5.** Re-run T2.2's checks. Green. Commit `docs: document the test invocation that actually works (F-30, F-62)`.

---

### T3 — Setup documents the roster seeding (B-80) — **partially gated on I3**

Today the `handles` table starts empty and nothing in either README says to seed it. A run over
zero included handles reports `completed`. P10 owns the "report a distinct warning" half of B-80's
fix; P14 owns the documentation half.

**The script moved.** `pipeline-app/scripts/` is now `pipeline-app/tools/` (F-64, one atomic
commit accepted by P8 and P10). Every path and command in this task and in the docs it edits uses
`tools`, never `scripts`.

- [ ] **T3.1.** **Ask P10 directly for its preferred verbatim invocation** — this is the one half
  of I3 still open. `python -m tools.migrate_handles_from_manifest` appears below as a
  **placeholder**; replace it with P10's spelling and run it once against a scratch DB to confirm
  it works as written before committing. A setup step nobody executed is how B-80 happened.

- [ ] **T3.2 (test first).** Add:

```python
SETUP_SCRIPT_RE = re.compile(r"`?(?:python -m |python |bash )([\w./-]+)`?")


def test_pipeline_app_setup_seeds_the_discovery_roster():
    text = (REPO / "pipeline-app" / "README.md").read_text(encoding="utf-8")
    assert "migrate_handles_from_manifest" in text, (
        "pipeline-app/README.md Setup must document the roster-seeding step (B-80): "
        "without it the handles table is empty and every discovery run completes having "
        "fetched nothing."
    )


@pytest.mark.parametrize("doc_name", [
    "README.md", "pipeline-app/README.md", "docs/README.md", "rgs-briefs/README.md", "CLAUDE.md",
])
def test_every_script_path_a_readme_tells_you_to_run_exists(doc_name):
    text = (REPO / doc_name).read_text(encoding="utf-8")
    missing = []
    for token in re.findall(r"`([\w./-]+\.(?:py|sh))`", text):
        if token.startswith(("http", "<")) or "*" in token:
            continue
        candidates = [REPO / token, REPO / "pipeline-app" / token, REPO / "scripts" / token]
        if not any(c.exists() for c in candidates):
            missing.append(token)
    assert not missing, f"{doc_name} names files that do not exist: {sorted(set(missing))}"
```

  The first fails today. The second is the cheap general guard that would have caught B-80 the day
  the script moved.

- [ ] **T3.3.** Append to `pipeline-app/README.md` §Setup (substituting P10's exact command from I3):

```markdown
### Seed the discovery roster — required, do not skip

The `handles` table starts **empty**. Until it is seeded from `manifests/brand_sources.json`,
every discovery run has zero included handles and finishes reporting `completed` having fetched
nothing at all — a clean green run that did no work. Seed it once, from this directory:

    python -m tools.migrate_handles_from_manifest

Re-running it is safe: it inserts with `INSERT OR IGNORE` and never deletes a row the manifest
omits, so handles you added by hand through `/discovery/handles` survive a re-seed. The manifest
covers `youtube` and `bluesky` only — Instagram, LinkedIn, Facebook and X handles have no
declarative source and must be added through the UI (finding B-70).
```

- [ ] **T3.4.** Re-run. Green. Commit `docs: document the roster-seeding setup step (B-80)`.

---

### T4 — CLAUDE.md's Origin section accounts for every FamilyBrain mention (D-53)

- [ ] **T4.1 (test first).** This check is the interesting one: it makes the *enumeration* itself
  self-maintaining, so a fourth mention appearing anywhere fails a test rather than sitting
  unexplained for someone to find during a firewall audit.

```python
FIREWALL_EXEMPT = {
    "CLAUDE.md",                # the firewall + Origin sections themselves
    "tests/test_doc_truth.py",  # this file
}


def _tracked_files_mentioning_familybrain() -> set[str]:
    proc = subprocess.run(
        ["git", "grep", "-l", "-i", "familybrain", "--", ".",
         ":(exclude)docs/audit", ":(exclude)docs/superpowers"],
        cwd=REPO, capture_output=True, encoding="utf-8", errors="replace",
    )
    return {p for p in proc.stdout.split() if p and p not in FIREWALL_EXEMPT}


@pytest.mark.allow_subprocess
def test_every_familybrain_mention_is_accounted_for_in_origin():
    origin = CLAUDE_MD.read_text(encoding="utf-8")
    start = origin.index("## FamilyBrain firewall")
    section = origin[start:origin.index("## Using the skills")]
    unexplained = [
        path for path in sorted(_tracked_files_mentioning_familybrain())
        if Path(path).name not in section and path not in section
        and Path(path).parts[0] not in section
    ]
    assert not unexplained, (
        "tracked files mention FamilyBrain but CLAUDE.md's Origin section does not "
        f"account for them: {unexplained}. Explain them as history or remove them -- "
        "an unexplained mention is indistinguishable from a live dependency (D-53)."
    )
```

  Run it. It fails, naming `rgs-briefs/2026-07-28-rgs-debut-visual-system.md`.

- [ ] **T4.2.** Replace `CLAUDE.md`'s `## Origin` body (lines 161–167) with:

```markdown
The corpus was originally built as a research corpus (`corpus-archive/`) inside the
FamilyBrain repo, for an unrelated brand-intel feature. It was copied — not moved,
not `git mv`'d — into this repo as a one-time, one-directional operation: a fresh
`git init` with no shared history or remote.

FamilyBrain is named in exactly **three** places here, all of them historical provenance and none
of them a live dependency:

1. **`README.md`'s "Notes & scope" section and a few source-file headers**, narrating toolkit
   provenance — e.g. `gen_thinkers_manifest.ts` importing a sibling repo's TypeScript source. Not
   runnable against FamilyBrain from here; kept as documentation of where the JSON came from.
2. **`rgs-briefs/2026-07-28-rgs-debut-visual-system.md:23`**, whose `[B]` marker legend records
   that `output/raisinggoodsports-brand-definition.md` was "pulled from the live FamilyBrain Pi
   2026-07-22" — a dated, one-time copy of brand text, not a link to anything. The same file at
   `:64-65` explicitly *rejects* a FamilyBrain infrastructure fact (which fonts the Pi compositor
   ships) as out of scope for this project. That is the firewall working, recorded in place.
3. **This file's "FamilyBrain firewall" section**, which forbids adding a fourth.

`tests/test_doc_truth.py::test_every_familybrain_mention_is_accounted_for_in_origin` fails if a
tracked file mentions FamilyBrain and this list does not account for it. If it fires, the answer is
to explain the mention as history or delete it — never to leave it unexplained, because an
unexplained mention reads exactly like a leak.
```

- [ ] **T4.3.** Re-run. Green. Commit `docs: account for the third FamilyBrain mention in Origin (D-53)`.

---

### T5 — `rgs-briefs/README.md` enumerates every producing stage (C-52) — **I9 resolved; gated on I5**

`pipeline.yaml` has nine stages (`grounding`, `ideation`, `scripting`, `styleboard`, `voiceover`,
`visual`, `music`, `assembly`, `repurpose`). The README enumerates six stage-artifact names.
`styleboard` and `music` have **zero** artifacts on disk — neither stage has ever run end to end
against this ledger, so neither one's frontmatter contract has ever been exercised.

**I9 has resolved.** `styleboard` and `music` remain stages under those ids. P4 fixed the **graph**
rather than the skill declarations — the skills' declared inputs are corpus-traced craft
requirements and `pipeline.yaml` had under-declared them — so `assembly.depends_on` is now
`[scripting, styleboard, voiceover, visual]` with a new **`optional_depends_on: [music]`**, and
`repurpose.depends_on` is `[ideation, scripting, assembly]`. Two consequences for this task:
`styleboard` is a **hard** dependency of assembly, and `music` is a declared-optional one — the
README must say which is which, because "never yet written" reads very differently for a stage
assembly cannot proceed without.

- [ ] **T5.1.** Confirm I5 (canonical `kind:` tokens and `stage:` ordinals) is recorded. Still
  open — do not invent the tokens.

- [ ] **T5.2 (test first).**

```python
def _pipeline_stage_ids() -> list[str]:
    text = (REPO / "pipeline.yaml").read_text(encoding="utf-8")
    return re.findall(r"^\s*-\s*id:\s*(\S+)", text, re.MULTILINE)


def test_rgs_briefs_readme_enumerates_every_producing_pipeline_stage():
    readme = (REPO / "rgs-briefs" / "README.md").read_text(encoding="utf-8")
    # `grounding` produces a grounding brief, not a `<stage>` artifact; every other
    # stage in pipeline.yaml writes one and must appear in the enumeration.
    missing = [s for s in _pipeline_stage_ids() if s != "grounding" and s not in readme]
    assert not missing, (
        f"rgs-briefs/README.md does not enumerate pipeline stages {missing} (C-52). "
        "A stage the ledger's contract omits will write frontmatter nobody specified."
    )


def test_every_kind_value_on_disk_is_enumerated_in_the_readme():
    briefs = REPO / "rgs-briefs"
    readme = (briefs / "README.md").read_text(encoding="utf-8")
    on_disk = set()
    for path in briefs.glob("*.md"):
        if path.name == "README.md":
            continue
        head = path.read_text(encoding="utf-8", errors="replace")[:600]
        found = re.search(r"^kind:\s*(\S+)", head, re.MULTILINE)
        if found:
            on_disk.add(found.group(1))
    missing = sorted(k for k in on_disk if f"`{k}`" not in readme)
    assert not missing, (
        f"kind: values written to rgs-briefs/ that the README's vocabulary omits: {missing}"
    )
```

  Both fail today: `styleboard` and `music` are absent, and `kind: visual-prompt-sheet` (one file)
  is not in the README's vocabulary while `visual-prompts` (six files) is.

- [ ] **T5.3.** Replace `rgs-briefs/README.md` §Naming's stage-artifact paragraph (lines 27–31):

```markdown
Stage artifacts append the stage name to their Short's slug:
`YYYY-MM-DD-<topic-slug>-<stage>.md`, where `<stage>` is one of `concept-brief`, `script`,
`styleboard`, `voiceover-brief`, `visual-prompts`, `music`, `assembly`, `social-repurpose` — one
per producing stage in `pipeline.yaml`, in that order. Run-level documents shared by several
Shorts use a run slug instead of a topic slug — e.g. `2026-07-28-rgs-debut-reference-scan.md`, and
carry `kind:` values of their own (`reference-scan`, `sparks`, `visual-system`).

> **`styleboard` and `music` have never been written.** As of 2026-08-08 this directory holds zero
> artifacts of either kind. Neither `shorts-styleboard` nor `music-brief` has run end to end
> against this ledger, so neither one's frontmatter contract has ever been exercised by a real
> file — the two rows above are a specification, not a precedent. Treat them as untested until the
> first Short produces one, and check the emitted frontmatter against §Front-matter schema by hand
> that first time.
>
> The two are not equally optional. In `pipeline.yaml`, `assembly.depends_on` includes
> **`styleboard`** — a Short cannot reach assembly without one — while `music` sits in
> `assembly.optional_depends_on`. So the missing `styleboard` artifact is a gap in a *required*
> stage that no Short has yet exercised; the missing `music` artifact is a gap in an optional one. `tests/test_doc_truth.py::test_rgs_briefs_readme_enumerates_every_producing_pipeline_stage`
> keeps this enumeration in step with `pipeline.yaml`; it cannot tell you whether the stage works.
```

- [ ] **T5.4.** In §Front-matter schema, extend the parenthetical stage-artifact list in **both**
  places it appears (the schema heading around line 76 and the `status`-vocabulary bullet around
  line 111) from `(concept-brief, script, voiceover-brief, visual-prompts, assembly,
  social-repurpose)` to `(concept-brief, script, styleboard, voiceover-brief, visual-prompts,
  music, assembly, social-repurpose)`.

- [ ] **T5.5.** Resolve the `visual-prompt-sheet` / `visual-prompts` split per I5 by adding the
  vocabulary table after §Naming:

```markdown
### `kind:` vocabulary — the complete set

| `kind:` | Written by | Scope |
|---|---|---|
| `concept-brief` | `shorts-ideation` | one Short |
| `script` | `shorts-scripting` | one Short |
| `styleboard` | `shorts-styleboard` | one Short — **never yet written** |
| `voiceover-brief` | `voiceover-brief` | one Short |
| `visual-prompts` | `visual-prompts` | one Short |
| `music` | `music-brief` | one Short — **never yet written** |
| `assembly` | `shorts-assembly` | one Short |
| `social-repurpose` | `social-repurpose` | one Short |
| `reference-scan` | run-level, by hand | a batch of Shorts |
| `sparks` | run-level, by hand | a batch of Shorts |
| `visual-system` | run-level, by hand | a batch of Shorts |

No other value is valid. `2026-07-25-let-kids-play-act-specialization-visual-prompts.md` carries
the one-off `kind: visual-prompt-sheet`; it is immutable and stays as written, and is listed here
as a known deviation rather than a permitted spelling. Emit `visual-prompts`.
```

  *(If I5 rules otherwise — e.g. `bed-arc` rather than `music` — substitute P13's tokens
  throughout T5.3–T5.5 and in `test_rgs_briefs_readme_enumerates_every_producing_pipeline_stage`'s
  stage-id mapping. Do not carry both spellings.)*

  Then add `visual-prompt-sheet` to the vocabulary test's known-deviation allowlist, with the
  file name in the comment — an allowlist entry that names its one file cannot silently absorb a
  second.

- [ ] **T5.6.** Re-run. Green. Commit `docs: enumerate styleboard and music in the rgs-briefs contract (C-52)`.

---

### T6 — The grounding-brief discriminator becomes positive (C-53) — **gated on I6**

Ten stage artifacts written 2026-07-25 carry only `version: 1` — no `kind:`, no `thinker`. Every
consumer told to "skip files with `kind:`" reads all ten as grounding briefs, finds no
`thinker`/`concept`/`research_codes` to compare, and either crashes or silently corrupts the
recency window. The ten files are hook-immutable and nine of them belong to no package, so **the
rule changes, not the files.**

- [ ] **T6.1.** Confirm I6. **Blocker:** if P13 keeps the negative `kind:`-skipping rule in
  `rgs-grounding` / `rgs-pairing-review`, P14 cannot close C-53 — the README would document a rule
  the skills do not follow, which is the same class of defect. Escalate to the orchestrator rather
  than writing either version.

- [ ] **T6.2 (test first).** This is the distinguishability test the Three-Test Rule asks for: the
  broken classification and the correct one must be observably different, and they are — on
  exactly ten files.

```python
GROUNDING_FIELDS = ("thinker", "concept", "research_codes")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    return dict(re.findall(r"^(\w+):\s*(.*)$", block, re.MULTILINE))


# The ten stage artifacts that predate the `kind:` contract. Frozen deliberately:
# they are immutable (.claude/hooks/protect_briefs.py) and this list is what the
# negative rule got wrong.
KIND_LESS_STAGE_ARTIFACTS = 10


def test_the_documented_discriminator_is_positive_not_kind_based():
    readme = (REPO / "rgs-briefs" / "README.md").read_text(encoding="utf-8")
    assert "MUST skip any file with a `kind:` field" not in readme, (
        "rgs-briefs/README.md still tells consumers to discriminate on the absence of "
        "`kind:` -- ten pre-contract stage artifacts have no `kind:` and are not grounding "
        "briefs (C-53)."
    )
    assert all(f"`{field}`" in readme for field in GROUNDING_FIELDS), (
        "the positive rule must name all three required fields"
    )


def test_positive_and_negative_discriminators_disagree_on_exactly_the_known_ten():
    briefs = [p for p in (REPO / "rgs-briefs").glob("*.md") if p.name != "README.md"]
    by_positive = {p.name for p in briefs
                   if all(f in _frontmatter(p) for f in GROUNDING_FIELDS)}
    by_negative = {p.name for p in briefs if "kind" not in _frontmatter(p)}
    difference = by_negative - by_positive
    assert len(difference) == KIND_LESS_STAGE_ARTIFACTS, (
        f"expected exactly {KIND_LESS_STAGE_ARTIFACTS} files that the old kind:-skipping rule "
        f"misclassifies as grounding briefs; found {len(difference)}: {sorted(difference)}"
    )
    assert not by_positive - by_negative, (
        "a file has all three grounding fields AND a kind: -- the two contracts have collided"
    )
```

  Run it. The first fails on today's README text; the second passes today and is the regression
  pin — it fails the moment someone adds an eleventh `kind:`-less file or backfills one of the ten.

- [ ] **T6.3.** Replace `rgs-briefs/README.md`'s §"Two file kinds" block (lines 33–42) with:

```markdown
## Two file kinds — and the rule that keeps them apart

A **grounding brief** is a file whose front-matter carries all three of `thinker`, `concept` and
`research_codes` (plus `archetype`). Everything else in this directory — stage artifacts and
run-level documents alike — is not a grounding brief.

> **Consumers that glob this directory MUST select grounding briefs positively: a file counts only
> if it has `thinker` AND `concept` AND `research_codes`.**
> This applies to `rgs-grounding`'s recency and repeat checks and to `rgs-pairing-review`.
>
> **Do not use "has no `kind:`" as the test.** Ten stage artifacts written on 2026-07-25 — the
> whole `let-kids-play-act` and `let-kids-play-act-specialization` chains — predate the `kind:`
> contract and carry only `version: 1`. A `kind:`-skipping consumer reads all ten as grounding
> briefs, then finds no `thinker`/`concept`/`research_codes` to compare and either crashes or
> silently corrupts the recency window with ten phantom pairings. Those ten files are immutable
> (`.claude/hooks/protect_briefs.py`), so the discriminator is what changes, not the files.
>
> Every file written since 2026-07-28 does carry `kind:`, and new artifacts must keep carrying it —
> it is how a *human* tells the files apart at a glance, and it is what §"`kind:` vocabulary"
> enumerates. It is simply not what a *program* should branch on.

`tests/test_doc_truth.py::test_positive_and_negative_discriminators_disagree_on_exactly_the_known_ten`
pins the size of that disagreement, so neither an eleventh pre-contract file nor a quiet backfill
can change the rule's blast radius without a test failing.
```

- [ ] **T6.4.** Update §"Who reads this" — replace both `**Must skip `kind:`-bearing files.**`
  bold notes (lines 145 and 149) with `**Must select positively on `thinker` + `concept` +
  `research_codes` — see "Two file kinds" above.**`

- [ ] **T6.5.** Re-run. Green. Commit `docs: make the grounding-brief discriminator positive (C-53)`.

---

### T7 — `appendix-F-tests.md` stops repeating the retracted count (F-29)

§5 and §6 were already corrected to 11 with a "Corrected 2026-08-08" note. Two residues survive:
`:165` still reads "The 2-test `test_turn_service.py`", and `:557` credits the corrected number to
the `def test_` grep that §6 itself retracts as the flawed method.

- [ ] **T7.1 (test first).** Convert this from "corrected once" to "cannot drift", by measuring the
  counts the appendix asserts:

```python
APPENDIX_F = REPO / "docs" / "audit" / "appendix-F-tests.md"
COUNT_CLAIM_RE = re.compile(r"`(test_\w+\.py)`\s*\|\s*\*{0,2}(\d+)\*{0,2}\s*\|")


def test_appendix_f_does_not_repeat_the_retracted_turn_service_count():
    text = APPENDIX_F.read_text(encoding="utf-8")
    stale = re.findall(r"\b2[- ]test\b[^\n]*turn_service", text)
    assert not stale, f"appendix-F still asserts the retracted 2-test count (F-29): {stale}"


@pytest.mark.allow_subprocess
def test_appendix_f_test_counts_match_collection():
    if os.environ.get("DOC_TRUTH_CHILD"):
        pytest.skip("child collection run; do not recurse")
    text = APPENDIX_F.read_text(encoding="utf-8")
    env = {**os.environ, "DOC_TRUTH_CHILD": "1"}
    wrong = []
    for filename, claimed in COUNT_CLAIM_RE.findall(text):
        for cwd, sub in ((REPO, "tests"), (REPO / "pipeline-app", "tests")):
            target = cwd / sub / filename
            if not target.exists():
                continue
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q",
                 "-p", "no:cacheprovider", f"{sub}/{filename}"],
                cwd=cwd, capture_output=True, encoding="utf-8", errors="replace", env=env,
            )
            found = re.search(r"(\d+) tests? collected", proc.stdout)
            if found and int(found.group(1)) != int(claimed):
                wrong.append(f"{filename}: appendix says {claimed}, collects {found.group(1)}")
    assert not wrong, (
        "appendix-F test counts are stale -- `grep -c 'def test_'` is not a test count "
        f"(F-29): {wrong}"
    )
```

  The first fails on `:165`. The second will move as other packages add tests — that is the point;
  it forces the appendix's numbers to be re-measured rather than trusted.

- [ ] **T7.2.** In `docs/audit/appendix-F-tests.md`, replace F-01's `blast_radius` line (`:165`):

  *Old:* `No one could distinguish "tested" from "has a test file named after it". The 2-test
  `test_turn_service.py` reads as adequate against a 98%-covered module because nothing ever
  separated line execution from assertion.`

  *New:*

```markdown
- **blast_radius**: No one could distinguish "tested" from "has a test file named after it". `test_turn_service.py` — 11 tests, all green, against a 98%-covered module — reads as adequate because nothing ever separated line execution from assertion. (This line originally said "the 2-test `test_turn_service.py`"; that count came from the `def test_` grep §6 retracts, and is corrected here per F-29.)
```

- [ ] **T7.3.** Replace §6's method parenthetical (`:557-559`):

  *Old:* `(verified by AST-shaped grep over `def test_`; the other four counts are correct)`

  *New:*

```markdown
T0 lists five. **One of its counts is wrong:** `test_turn_service.py` has **11** test functions,
not 2 — verified by `pytest --collect-only`, which is the authoritative method here; the
`^def test_` grep that produced the original 2 silently missed every `async def test_` (see §6's
correction note). The other four counts survived re-measurement unchanged. The correction makes
the module *worse*, not better — 11 tests that never assert the module's output is a stronger
indictment than 2.
```

- [ ] **T7.4.** Re-run. Green. Commit `docs: correct the residual turn_service test count in appendix F (F-29)`.

---

### T8 — "Which assertion would have failed?" becomes a standing rule (F-10)

32 S0/S1 defects, 29 of them one assertion away, zero tests written — and nothing in the repo asked
the question that would have exposed the gap continuously. The fix is a convention plus the check
that makes the finding→plan mapping total rather than aspirational.

> **Amendment, 2026-08-21 (P14 kickoff, before T8 dispatch).** T8.1's original bijection test
> scanned each plan's ENTIRE pre-`## 4.` text for anything shaped like a finding id. Against the
> live 16-plan corpus this produced 37 false "contested" findings: plans routinely mention another
> package's finding id in a disclaimed cross-reference (`"A-32 is not in P3's finding set"`,
> `"Routed to A-32's owner"`, a `"tracked separately"` handoff sub-table naming the real owner in
> the same row) — every one hand-verified against the claiming plans' own text before this
> amendment landed. The corrected version below scopes each plan's claims to its own
> `## N. Finding → task map` section (present, verbatim-titled, in all sixteen plans — the
> orchestration plan's own Verification §2 requirement) instead of the whole pre-`## 4.` prose, and
> carries two small, explicit, hand-verified exception tables for the residue that survives even
> that narrower scope: ten disclaimed same-table mentions, and one genuinely split finding (F-26,
> closed as two separately-tasked halves by P1's T18 and P4's T19). Both tables are the same
> "explicit ledger, shrink it, never grow it blindly" pattern `tests/test_skill_provenance.py`
> already uses for its own triage ledgers — not a new convention. Verified against the merged tree:
> 328/328 findings claimed, 0 unclaimed, 0 genuinely contested. No other part of T8 changes.

- [ ] **T8.1 (test first).**

```python
AUDIT = REPO / "docs" / "audit"
PLANS = REPO / "docs" / "superpowers" / "plans" / "remediation"
FINDING_HEADING_RE = re.compile(r"^###\s+([A-F]-\d{2,3})\s+·", re.MULTILINE)
FINDING_REF_RE = re.compile(r"\b([A-F]-\d{2,3})\b")
TASK_MAP_HEADING_RE = re.compile(
    r"^##\s+\d+\.\s*Finding\s*(?:→|->)\s*task map", re.MULTILINE | re.IGNORECASE
)
NEXT_H2_RE = re.compile(r"^##\s+\S", re.MULTILINE)

# Verified by hand against the live tree (2026-08-21): the finding's real, sole
# owner is the OTHER plan in the pair. The plan named here mentions the finding
# only inside its own "Finding -> task map" section as a documented
# cross-package dependency/handoff note (e.g. a "tracked separately" sub-table
# naming the true owner in the same row), and that plan's own text disclaims
# ownership. Shrink this dict as plans merge with cleaner cross-references;
# never grow it without re-reading the disclaiming plan's own words.
EXCLUDE_AS_MENTION = {
    "B-01": "P8-engine-cron.md",
    "B-06": "P8-engine-cron.md",
    "B-21": "P8-engine-cron.md",
    "B-72": "P10-roster.md",
    "B-73": "P8-engine-cron.md",
    "B-82": "P8-engine-cron.md",
    "D-47": "P5-skills-editor.md",
    "E-05": "P15-ui.md",
    "E-07": "P15-ui.md",
    "F-64": "P8-engine-cron.md",
}
# Verified by hand: genuinely split and closed by two real, separately-tasked
# halves, each recorded as its own row in each plan's own task map (P1's T18,
# P4's T19).
KNOWN_SPLIT_FINDINGS = {"F-26"}


def test_every_audit_finding_is_claimed_by_exactly_one_remediation_plan():
    findings = set()
    for appendix in AUDIT.glob("appendix-*.md"):
        findings |= set(FINDING_HEADING_RE.findall(appendix.read_text(encoding="utf-8")))
    assert findings, "no findings parsed -- the heading format changed"

    claims: dict[str, list[str]] = {}
    for plan in PLANS.glob("P*.md"):
        text = plan.read_text(encoding="utf-8")
        heading = TASK_MAP_HEADING_RE.search(text)
        assert heading, f"{plan.name} has no '## N. Finding -> task map' section"
        rest = text[heading.end():]
        next_h2 = NEXT_H2_RE.search(rest)
        scope = rest[: next_h2.start()] if next_h2 else rest
        for fid in set(FINDING_REF_RE.findall(scope)) & findings:
            if EXCLUDE_AS_MENTION.get(fid) == plan.name:
                continue
            claims.setdefault(fid, []).append(plan.name)

    unclaimed = sorted(findings - claims.keys())
    contested = sorted(
        f for f, owners in claims.items()
        if len(owners) > 1 and f not in KNOWN_SPLIT_FINDINGS
    )
    assert not unclaimed, f"audit findings no remediation plan claims: {unclaimed}"
    assert not contested, f"audit findings claimed by more than one plan: {contested}"


def test_claude_md_requires_a_failing_assertion_per_defect():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "which assertion would have failed" in text.lower(), (
        "CLAUDE.md must carry the standing rule F-10 exists to install"
    )
```

  The first is the programme-wide gate from the orchestration plan's Verification §2; it passes
  only once all sixteen plans are complete, which is exactly when P14 runs. If it fails after the
  amendment above (a genuinely unclaimed id, or a contested one that isn't in `EXCLUDE_AS_MENTION`
  or `KNOWN_SPLIT_FINDINGS`), name the ids in the report — do not add them to P14, and do not widen
  either exception table without re-verifying the new case by hand the same way this amendment did.

- [ ] **T8.2.** Add to `CLAUDE.md`'s Conventions list, immediately before the test-invocation
  bullet:

```markdown
- **Every defect writeup names the assertion that would have caught it.** The 2026-08-08 audit
  found 32 S0/S1 defects against a 1,034-test suite at 95% line coverage, and **zero** of them had
  a test — not because they were untestable (29 were a single assertion away, 3 partially so, none
  genuinely out of reach) but because nobody was ever required to ask. So: any finding recorded
  under `docs/audit/` and any bug fixed anywhere in this repo carries a *"which assertion would
  have failed?"* line, and the fix lands that assertion as a named regression test that was
  observed failing first. A fix with no such test is not a fix; a finding with no such line is not
  finished. Coverage is not the bar — 95% coexisted with 328 defects.
  `tests/test_doc_truth.py::test_every_audit_finding_is_claimed_by_exactly_one_remediation_plan`
  keeps the finding→plan mapping total, so the gap stays measured instead of being measured once.
```

- [ ] **T8.3.** Re-run. Green. Commit `docs: require a failing assertion per defect writeup (F-10)`.

---

### T9 — Provenance rules reconciled (relay; **I4 RESOLVED**)

`docs/README.md:56` says `[C]` is the "default; usually unmarked in the audit". `CLAUDE.md:40`
says an unmarked rule is a bug. Both can be true, but only if both say so.

**P13 has reported.** The unmarked-`[C]` default **survives, scoped to `docs/*.md` only** — the
whole corpus-document folder, not just `headless-youtube-audit.md` — with a reciprocal
half-sentence added to CLAUDE.md. P13's triage measured 533 normative blocks and 367 unmarked, of
which **215 are genuine skill-side bugs**; the remaining 152 are 113 RGS alternative-vocabulary
lines, 27 worked-example illustrations and 12 structural pointers. Those 215 are P13's to fix, not
P14's. **Outcome A below, as amended, is the one to implement; outcome B is struck.**

- [ ] **T9.1.** Read P13's §-contract and copy the **exact** names it gives the three non-bug
  categories — they must match the `ALTERNATIVE_VOCABULARY` constant in P13's test verbatim. A
  doc that names a category differently from the test that enforces it is the same defect this
  package exists to close.

- [ ] **T9.2 (test first).**

```python
def test_the_two_provenance_rules_name_each_others_scope():
    docs_readme = (REPO / "docs" / "README.md").read_text(encoding="utf-8")
    claude = CLAUDE_MD.read_text(encoding="utf-8")
    if "usually unmarked" in docs_readme:
        assert "`docs/*.md`" in docs_readme, (
            "docs/README.md's unmarked-[C] shorthand must name the scope it applies to"
        )
        assert "`docs/*.md`" in claude, (
            "CLAUDE.md's 'no marker is a bug' rule must name the one documented exemption "
            "and its scope, or the two rules read as a contradiction"
        )
```

- [ ] **T9.3 — outcome A — IMPLEMENT THIS ONE.** The shorthand survives, scoped to `docs/*.md`.
  Replace `docs/README.md:56-57`:

```markdown
- **`[C]` Corpus-cited** — extracted from a transcript, cited as `(Channel, video_id)`. Two or
  more channels agreeing = flagged **strongly-supported**.
  **Scope of the "unmarked" shorthand:** inside `docs/*.md` — this folder's corpus documents, and
  only these — `[C]` is the document-wide default and is usually left off the line: the
  `(Channel, video_id)` citation *is* the marker. The shorthand does **not** extend to
  `.claude/skills/**` or to `rgs-briefs/`, where CLAUDE.md's rule is absolute — a normative line
  with no marker is a bug, not an implied `[C]`.
```

  And replace `CLAUDE.md:40-43`:

```markdown
A skill rule with no marker is a bug: it means something was invented instead of
sourced. If the corpus is thin on a topic, the skill says so explicitly rather than
filling the gap with generic advice — that discipline is the entire point of this
project (see "Anti-generic guarantee" below).

There is exactly **one** documented exemption and it does not reach a skill: the corpus documents
under `docs/*.md` treat `[C]` as their document-wide default and usually leave the marker off,
carrying the `(Channel, video_id)` citation instead — see `docs/README.md`'s provenance key.
Nothing outside `docs/*.md` inherits the shorthand.
```

  Then, using **P13's exact category names** (I4 / T9.1), append to the same CLAUDE.md paragraph a
  sentence naming the three classes of unmarked line that are *not* bugs — RGS alternative
  vocabulary, worked-example illustrations, structural pointers — spelled as P13's
  `ALTERNATIVE_VOCABULARY` constant spells them. Do not paraphrase the names; a paraphrase makes
  the doc and the test disagree.

- [ ] ~~**T9.3 — outcome B: no exemption; every line marked everywhere.**~~ **STRUCK — P13 kept the
  shorthand.** The `docs/headless-youtube-audit.md` backfill blocker this branch carried is
  therefore moot. Retained for the record only; do not implement.

- [ ] **T9.4.** Re-run. Green. Commit `docs: reconcile the provenance rules across CLAUDE.md and docs/README.md`.

---

### T10 — Adapter contract states what is actually true (relay; **gated on I7**)

- [ ] **T10.1.** Confirm I7.

- [ ] **T10.2 — outcome A: P6/P9 removed the `upload_date` fallback.** Amend the
  `- **Adding a discovery platform.**` bullet's promise clause to:

```markdown
  An adapter honoring that contract appears in the daily email — inventory entry, link, title, and
  spotlight eligibility — with **no change to any email-side module**. `discovery_digest.py` and
  `email_render.py` read only the fields named here and carry no platform-specific branch; the
  YouTube-shaped `upload_date` fallback that made this promise false was removed on 2026-08-08.
  A synthetic adapter is driven end to end through the digest by
  `pipeline-app/tests/<P6/P9's test name>`, so the promise is checked rather than asserted.
```

- [ ] **T10.3 — outcome B: the fallback is retained as a named exception.** Amend to:

```markdown
  An adapter honoring that contract appears in the daily email's inventory entry, link, title and
  spotlight eligibility with **no change to any email-side module** — with one named exception.
  **Publish-date rendering:** `discovery_digest.py` reads `published` directly, and *also* accepts
  a YouTube-shaped `upload_date` (`YYYYMMDD`) as a fallback. That fallback is legacy and is the
  only platform-specific shape in the email path. A new adapter that wants its publish date
  rendered must emit `published`; it must not emit `upload_date` expecting it to be understood, and
  no third shape will be added for it.
```

- [ ] **T10.4.** Commit `docs: state the adapter contract that the email path actually honours`.

---

### T11 — Email privacy promise matches the code (relay; **I8 RESOLVED**)

Today's promise — "a ~400 character excerpt… never a full post body" — is false for any spotlight
shorter than 400 characters, which is most Bluesky and X posts.

**P9 has reported: the code stays, CLAUDE.md changes.** The orchestrator accepted P9's reasoning —
capping the excerpt below 280 characters would gut the digest *and still* would not make "never a
full post body" true, because any post shorter than the cap is fully included by definition. The
promise is unachievable as worded, so the wording is what is wrong. P9 has pinned the real
behaviour in an `email_render.DISCLOSURE` constant.

- [ ] **T11.1.** **Take the replacement wording verbatim from P9's plan §6.2(a).** Do not draft
  your own and do not adapt it — the paragraph in CLAUDE.md and the string in
  `email_render.DISCLOSURE` must be the same sentence, or the next reader has two contradictory
  privacy statements instead of one.

- [ ] **T11.2 (test first).** Pin them together, so drift fails a test rather than a review:

```python
def test_claude_md_email_promise_matches_the_pinned_disclosure():
    """P9 pinned the real behaviour in email_render.DISCLOSURE; CLAUDE.md must say the
    same thing. Read as text -- the root suite does not import app code."""
    source = (REPO / "pipeline-app" / "pipeline_app" / "email_render.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'DISCLOSURE\s*=\s*(?:"""|")(.+?)(?:"""|")', source, re.DOTALL)
    assert match, "email_render.DISCLOSURE not found -- P9's pin is missing"
    disclosure = " ".join(match.group(1).split())
    claude = " ".join(CLAUDE_MD.read_text(encoding="utf-8").split())
    assert disclosure in claude, (
        "CLAUDE.md's email privacy paragraph has drifted from email_render.DISCLOSURE. "
        "The doc does not get its own wording for this."
    )


def test_no_doc_repeats_the_unachievable_never_a_full_post_body_promise():
    for doc in (CLAUDE_MD, REPO / "README.md"):
        assert "never a full post body" not in doc.read_text(encoding="utf-8"), (
            f"{doc.name} repeats a promise the code cannot keep: any post shorter than "
            "the excerpt cap is included in full by definition."
        )
```

- [ ] **T11.3.** Replace exception 1's body in `CLAUDE.md` with P9's §6.2(a) text, kept
  byte-identical to `email_render.DISCLOSURE` so T11.2's first check passes. Retain the
  surrounding list structure and the two `docs/superpowers/specs/…` pointers.

- [ ] ~~Outcome A (P9 changes the code, promise kept as worded).~~ **STRUCK — unachievable as
  worded.** Retained for the record only.

- [ ] **T11.4.** Re-run. Green. Commit `docs: state the email privacy contract the code actually implements`.

---

### T12 — `docs/README.md` inventory is true (no filed finding)

Not one of the nine findings. It is fixed here because P14 owns the file, the claims are plainly
false, and T3.2's path check plus the inventory check below would fail on them anyway.

- [ ] **T12.1 (test first).**

```python
def test_docs_readme_accounts_for_every_committed_doc():
    docs = REPO / "docs"
    readme = (docs / "README.md").read_text(encoding="utf-8")
    unlisted = sorted(
        p.name for p in docs.glob("*.md")
        if p.name != "README.md" and p.name not in readme
    )
    assert not unlisted, (
        f"docs/ holds committed documents docs/README.md never mentions: {unlisted}"
    )
```

  Fails today on `elevenlabs-music-runbook.md`, `style-library.md` and
  `script-language-baseline.md`.

- [ ] **T12.2.** Retitle §"Vendor runbooks (not corpus-derived)" and replace its lead sentence:

```markdown
### Vendor runbooks (not corpus-derived)

Two further guides sit outside the corpus. Both are built from vendor documentation rather than
the 420-video corpus, so they are listed separately and carry an extra provenance marker.
```

  and add the second row to that table (measure the word count; do not invent it):

```markdown
| **[elevenlabs-music-runbook.md](elevenlabs-music-runbook.md)** | **Eleven Music platform truth** — composition-plan structure, prompt craft, the API payload surface, and credit discipline. Verified against live ElevenLabs docs **2026-08-06**; §7 records **two places the supplied design brief was wrong**. Backs the `elevenlabs-music` skill. | ~N words |
```

- [ ] **T12.3.** Replace `docs/README.md`'s "committed output" bullet (`:93`):

```markdown
- This `docs/` folder is the **committed** output: the three launch-kit documents and two
  asset-production guides above, the two vendor runbooks, plus `style-library.md` (the style
  registry Gate C resolves `{style:...}` slot labels against) and `script-language-baseline.md`
  (the language baseline Gate D lints against) — nine documents and this README.
  `tests/test_doc_truth.py::test_docs_readme_accounts_for_every_committed_doc` fails if a tenth
  appears without a line here.
```

- [ ] **T12.4.** Re-run. Green. Commit `docs: account for every committed document in docs/README.md`.

---

### T13 — Verification sweep

- [ ] **T13.1.** Run the documented commands, exactly as the docs now state them, and paste the
  output into the commit body:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767" && python -m pytest tests/ -q
```

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest -q
```

- [ ] **T13.2.** Confirm each of these by observation, not by assumption:
  - `tests/test_doc_truth.py` collects and passes every check in §5's table.
  - The counts written into `CLAUDE.md` and `pipeline-app/README.md` in T2 match what T13.1 just
    printed. If a later package added tests after T2 ran, re-measure and re-edit — a stale count is
    the same defect this package exists to close.
  - `git grep -n "does the right thing in both places"` returns nothing.
  - `git grep -n "two outbound network dependencies"` returns nothing.
  - `git grep -rn "MUST skip any file with a \`kind:\` field" rgs-briefs/` returns nothing.
  - `git status` shows no modification to
    `rgs-briefs/2026-07-25-let-kids-play-act-script.md` or
    `rgs-briefs/2026-07-28-rgs-debut-visual-system.md`. Both are immutable; a diff on either is a
    plan violation, not a fix.

- [ ] **T13.3.** Append the "Inputs received" block (§2) to this file with all nine rows filled.
  Commit `docs: close P14 doc-truth package`.

---

## 5. Finding → test map

Every finding is verified by an executing assertion, not by a reviewer's reading. The
Three-Test-Rule role is given for the two findings classed `silent` (C-53, F-30); the rest are
`docs-drift` or `coverage-gap`, where the fault *is* the false statement and the test that reads
the statement is the whole proof.

| Finding | Test (all in `tests/test_doc_truth.py` unless noted) | Role | How it proves the claim rather than asserting it |
|---|---|---|---|
| **D-40** | `test_claude_md_lists_every_outbound_call_site` | fault | Enumerates outbound call sites from the source tree and diffs them against CLAUDE.md's table **in both directions**. Fails on an undocumented dependency and on a phantom row. |
| **D-40** | `test_claude_md_network_counts_match_its_own_table` | distinguishability | The prose numerals ("**N** call sites across **M** destinations") are compared to the measured code and to the table's own rows — so a doc that adds a row without updating its count is observably different from one that is correct. |
| **F-62** | `test_no_doc_claims_a_bare_pytest_is_sufficient` | fault | Greps the three READMEs for the retracted sentence. The claim cannot come back. |
| **F-62** | `test_documented_test_commands_collect_what_the_docs_claim` | fault | **Extracts the command from the doc and runs it.** A doc that documents a broken invocation fails on the child process's non-zero exit — the doc is the test input, so the two cannot diverge. |
| **F-30** | `test_documented_test_commands_collect_what_the_docs_claim` | distinguishability + surfacing | Compares collected count to the count the doc claims. A documented command that silently collects 201 instead of 1,034 is now observably different from one that is right, and the difference surfaces as a named test failure rather than a green exit 0. |
| **B-80** | `test_pipeline_app_setup_seeds_the_discovery_roster` | fault | Asserts the seeding step is present in §Setup. Fails today. |
| **B-80** | `test_every_script_path_a_readme_tells_you_to_run_exists` | surfacing | Resolves every `.py`/`.sh` path any owned README tells you to run. A step that names a moved or deleted script fails here instead of failing on the operator's machine. |
| **D-53** | `test_every_familybrain_mention_is_accounted_for_in_origin` | fault | `git grep`s the tracked tree and requires Origin to account for each hit. The enumeration maintains itself; a fourth mention fails the suite. |
| **C-52** | `test_rgs_briefs_readme_enumerates_every_producing_pipeline_stage` | fault | Parses stage ids out of `pipeline.yaml` and requires each in the README. The contract is derived from the pipeline, not transcribed from it. |
| **C-52** | `test_every_kind_value_on_disk_is_enumerated_in_the_readme` | distinguishability | Collects `kind:` values actually written to disk and requires each in the vocabulary — catching the `visual-prompt-sheet` / `visual-prompts` split that reading the README alone cannot. |
| **C-53** | `test_the_documented_discriminator_is_positive_not_kind_based` | fault | The retracted MUST-skip sentence is pinned absent, and all three required fields must be named. |
| **C-53** | `test_positive_and_negative_discriminators_disagree_on_exactly_the_known_ten` | **distinguishability** | Computes both classifications over the real directory and asserts they differ on exactly ten files. This is the assertion that would have caught C-53: the broken rule and the correct rule produce measurably different sets, and the size of that difference is now pinned. |
| **C-53** | `test_the_documented_discriminator_is_positive_not_kind_based` (README) + P13's skill-side change (I6) | surfacing | The README rule and the skill behaviour are required to agree before T6 may ship; a mismatch is escalated, not documented. |
| **F-29** | `test_appendix_f_does_not_repeat_the_retracted_turn_service_count` | fault | Pins the retracted "2-test" figure absent from the appendix. |
| **F-29** | `test_appendix_f_test_counts_match_collection` | distinguishability | Re-measures every per-file count the appendix asserts with `pytest --collect-only`. Converts F-29 from a one-off correction into a standing check — and encodes the appendix's own lesson that `grep -c 'def test_'` is not a test count. |
| **F-10** | `test_every_audit_finding_is_claimed_by_exactly_one_remediation_plan` | fault | Parses all finding ids from `docs/audit/appendix-*.md` and all claimed ids from `docs/superpowers/plans/remediation/P*.md`, then requires a bijection. This is the programme's Verification §2, executable. |
| **F-10** | `test_claude_md_requires_a_failing_assertion_per_defect` | surfacing | Asserts the standing rule is present in CLAUDE.md, so the requirement survives the session that wrote it. |
| *(T11, no finding)* | `test_claude_md_email_promise_matches_the_pinned_disclosure` | — | Reads P9's `email_render.DISCLOSURE` out of the source and requires CLAUDE.md to contain that exact sentence. The doc does not get its own wording, so it cannot drift from the behaviour. |
| *(T11, no finding)* | `test_no_doc_repeats_the_unachievable_never_a_full_post_body_promise` | — | Pins the retracted promise absent. It was not merely inaccurate — it was unachievable at any cap, since a post shorter than the cap is included whole by definition. |
| *(T9, no finding)* | `test_the_two_provenance_rules_name_each_others_scope` | — | If either document keeps the "usually unmarked" shorthand, both must name the `docs/*.md` scope. Neither can silently widen. |
| *(T12, no finding)* | `test_docs_readme_accounts_for_every_committed_doc` | — | Every committed `docs/*.md` must be named in `docs/README.md`. |

**Why these count as tests and not as lint.** Each one takes a *document* as input and a *fact
about the code* as the expected value. None asserts on a value the doc hard-codes and echoes back
(the F-11 anti-tautology trap): `test_claude_md_network_counts_match_its_own_table` compares the
doc's numeral to a figure derived from the source tree; `test_documented_test_commands_collect_what_the_docs_claim`
executes the doc's own text as a command; `test_rgs_briefs_readme_enumerates_every_producing_pipeline_stage`
derives its expected set from `pipeline.yaml`. Remove the code and every one of them fails.

---

## 6. Tests deleted or inverted

**None.** No existing test in either suite asserts any of the nine false claims — which is
precisely the shape of this package: nine documentation defects survived 1,034 tests because
**zero** of those tests read a document. `tests/test_doc_truth.py` is the first.

Two adjacent files were checked and are deliberately left alone:

- `tests/test_resolve_brief_version.py` exercises `--kind` as a *filename query* parameter. The
  C-53 change is to the *consumer discrimination rule*, not to filename resolution, so nothing
  there encodes the defect and nothing there needs inverting. Confirm this by re-reading it before
  T6.5 rather than assuming it.
- `tests/test_skill_provenance.py` guards the anti-generic guarantee at two specific skill files.
  It is P13-adjacent, does not overlap `test_doc_truth.py`, and P14 does not touch it.

---

## 7. Risks specific to this package

- **Stale counts.** T2 writes test counts into two documents. Any package that lands tests after
  T2 makes them wrong. Mitigation: T13.2 re-measures, and
  `test_documented_test_commands_collect_what_the_docs_claim` fails loudly rather than drifting —
  but only if the doc states a count. State one.
- **`test_every_audit_finding_is_claimed_by_exactly_one_remediation_plan` fails for reasons P14
  cannot fix.** If a finding is genuinely unclaimed, that is an orchestration gap. Report the ids;
  do not annex them into this plan to make the test pass. Making a test pass by moving the
  goalposts is the F-11 defect wearing a different hat.
- **Upstream dependencies — six of nine now answered.** Still open: P0's authoritative post-fix
  test counts (T2, measure them yourself), P10's verbatim seeding invocation (T3, ask P10), P13's
  `kind:` tokens for `styleboard`/`music` (T5) and its positive-discriminator confirmation (T6),
  and P6/P9's `upload_date` alias resolution (T10). If any reports late, implement T1, T7, T8, T9,
  T11 and T12 and hold the rest. Do not ship a half-documented contract — a partly-true document
  is harder to distrust than an obviously stale one.
- **The `scripts/` → `tools/` rename touches prose in three of the docs P14 owns.** Before T13,
  `git grep -n "pipeline-app/scripts" -- '*.md'` over the owned files must return nothing. A
  README that names a directory the rename deleted is B-80 happening a second time.

---

## Inputs received (2026-08-21, P14 kickoff)

All nine gate rows resolved by direct measurement against the merged tree at `main`'s
`5ea160b` (P13 + PR #61 both merged) — no package had a live agent to ask, so each answer
below is sourced from that package's own shipped code/tests/plan text, not a guess.

| # | From | Date | Verbatim decision |
|---|---|---|---|
| I1/I2 | P0 | 2026-08-21 | Confirmed live at T2 time (measure fresh, not reused): two suites, two rootdirs, `python -m pytest` mandatory in both. No single runner entry point exists. Collected counts to be measured during T2 itself. |
| I3 | P10 | 2026-08-21 | Verbatim invocation is **`python tools/migrate_handles_from_manifest.py`** (run from `pipeline-app/`) — confirmed two ways: the script's own `Usage:` docstring line (`pipeline-app/tools/migrate_handles_from_manifest.py:9`, also echoed in `--help`), and P10's own plan text `docs/superpowers/plans/remediation/P10-roster.md:1844` (`> python scripts/migrate_handles_from_manifest.py`, pre-rename spelling — substitute `tools` for `scripts` per the F-64 rename). Not `python -m tools.migrate_handles_from_manifest`; the placeholder in T3.1 is replaced. |
| I4 | P13 | 2026-08-21 | Confirmed against the live `ALTERNATIVE_VOCABULARY`/`STRUCTURAL_SECTIONS`/`WORKED_EXAMPLE_DISCLAIMER` constants in `tests/test_skill_provenance.py:436-451`. The three non-bug category names the plan already uses — "RGS alternative-vocabulary lines", "worked-example illustrations", "structural pointers" — match the live constants' shape and T9 uses them verbatim as drafted. Separately noted (not a T9 input, not P14's to act on): the same test file's `TIER_1_PENDING` ledger (lines 491-501) carries four entries under `.claude/skills/rgs-grounding/**` and `.claude/skills/rgs-pairing-review/SKILL.md` whose notes say "needs a P14 decision on an RGS-side design marker" for those skills' own operational-design bullets (no corpus/vendor marker fits them). P14's own Scope (§1) explicitly excludes `.claude/skills/**`, so this decision has no owner in the current programme — recorded here as a carried-forward open item, same status as the P15↔P3/P5 sanitizer-divergence item, not actioned by P14. |
| I5 | P13 | 2026-08-21 | Confirmed against the live `KIND_REGISTRY` in `tests/test_skill_provenance.py:64-74`: `styleboard` → `kind: styleboard`, `stage: 02b-styleboard`, owned by `shorts-styleboard`; `music` → `kind: music`, `stage: 03-music`, owned by `music-brief`; `visual` → `kind: visual-prompts` (not `visual-prompt-sheet`), `stage: 03-visual`. T5's drafted text already matches these tokens exactly — no substitution needed. |
| I6 | P13 | 2026-08-21 | Confirmed by exhaustive grep: the retracted "MUST skip any file with a `kind:` field" sentence exists nowhere under `.claude/skills/rgs-grounding/**` or `.claude/skills/rgs-pairing-review/**` — its only occurrence in the tree is `rgs-briefs/README.md:39`, the exact line T6 rewrites. `rgs-grounding/SKILL.md:60-64`'s recency check reads a `thinker:` field directly and does not branch on `kind:` absence. T6 is **not blocked**: rewriting the README's rule to positive does not create a mismatch with any live skill behavior, because no skill file encodes the negative rule to begin with. |
| I7 | P6 + P9 | 2026-08-21 | Confirmed against live `pipeline-app/pipeline_app/discovery_digest.py`: the YouTube-shaped `upload_date` alias is **retained**, not removed — `PUBLISHED_FIELDS = ("published", "upload_date")` (line 58), with the module's own docstring (lines 23-27) stating `published` is optional, `upload_date` is accepted as its ONE alias for YouTube's yt-dlp-shaped frontmatter, and no third name is read. **Outcome B (T10.3) applies** — the fallback is a named exception, not a removed one. |
| I8 | P9 | 2026-08-21 | Confirmed live: `pipeline-app/pipeline_app/email_render.py:58-64` defines `DISCLOSURE = ("Each item contributes a derived title of at most " f"{TITLE_MAX_CHARS} characters, which for a platform with no title " "field is the opening of the post text. The spotlight additionally " f"contributes up to {EXCERPT_MAX_CHARS} characters of its " "primary text, which for a post shorter than that is the whole post.")`. T11 takes this string, with `TITLE_MAX_CHARS`/`EXCERPT_MAX_CHARS` substituted for their live values, verbatim into CLAUDE.md. |
| I9 | P4 | 2026-08-21 | Confirmed live against `pipeline.yaml`: `assembly.depends_on: [scripting, styleboard, voiceover, visual]` with `optional_depends_on: [music]` (lines 40-41); `repurpose.depends_on: [ideation, scripting, assembly]` (line 45). Matches the plan's stated resolution exactly. |
