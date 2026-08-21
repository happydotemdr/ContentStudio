# CLAUDE.md — ContentStudio

Standalone local project. Turns a faceless-YouTube-Shorts idea into a produced Short
plus repurposed cross-post copy, using eight atomic Claude Code skills — with every
normative recommendation traced back to a specific real-world corpus, never generic
content-creation advice.

## What this is

A **corpus** (`docs/` + `output/`) plus a **skill set** (`.claude/skills/`) built from it.
The corpus is a synthesis of **1,100+ findings** extracted from a **420-video corpus**
across **14 creator-education YouTube channels**, cross-checked against the live web for
tool/policy facts. It was originally assembled as a research corpus for a separate
project and was copied out into this standalone repo — see "Origin" below.

### The corpus (`docs/`, read in this order)

1. `docs/README.md` — the map, the 14-channel source list, and the **provenance key**.
2. `docs/headless-youtube-audit.md` — the evidence base: 13 themes, Dos/Don'ts, the
   Top-12 pitfalls, and a best-practice checklist. 679 inline citations.
3. `docs/headless-channel-launch-gameplan.md` — the phased launch roadmap.
4. `docs/headless-shorts-production-playbook.md` — Shorts anatomy, tool stack, overlay
   systems, AI asset workflow, 8 production templates.
5. `docs/midjourney-prompting-guide.md` — Midjourney image/video prompting reference.
6. `docs/elevenlabs-voiceover-guide.md` — ElevenLabs voiceover reference.

Raw material backing the guides lives under `output/brand-intel/` (git-ignored,
downloaded locally by the toolkit scripts at repo root — see `README.md`): per-channel
transcripts, the content index, and merged findings JSON.

**Provenance markers.** Every normative claim in the corpus (and in the skills built
from it) carries one of three markers, copied through verbatim:

- **`[C]` Corpus-cited** — extracted from a transcript, cited `(Channel, video_id)`.
  Two-plus channels agreeing = **strongly-supported**.
- **`[I]` Industry practice** — general craft not specific to this corpus.
- **`[T]` Tool/policy fact** — web-verified, dated 2026-07-23. **Re-verify before
  relying on it** — these go stale fast.

A skill rule with no marker is a bug: it means something was invented instead of
sourced. If the corpus is thin on a topic, the skill says so explicitly rather than
filling the gap with generic advice — that discipline is the entire point of this
project (see "Anti-generic guarantee" below).

**One more marker, for decisions rather than evidence:**

- **`[P]` Project/operator decision** — a call made by this project's owner and
  recorded in the repo. It states *what was decided*, never *why it is correct*.
  **Never cite a `[P]` line as corpus or vendor support for anything**, and never
  let one absorb an adjacent claim: a decision recorded beside a `[C]` rationale
  does not inherit that rationale's authority. `[P]` exists for the same reason
  `[REF]` does in `rgs-briefs/` — so a non-corpus source can never masquerade as
  corpus grounding.

The one `[P]` fact in the repo today is the **pinned channel narrator voice**
(`.claude/skills/voiceover-brief/references/channel-voice.md`): a fixed ElevenLabs
`voice_id`, an IVC clone of the operator's own voice, used for every Short across
all brands. `voiceover-brief` reads it before its selection doctrine and
`elevenlabs-audio` skips its audition stage on the strength of it. The pin covers
the narrator only — per-Short casting of any second voice is unaffected.

**Partially in scope:** the toolkit also carries two additional corpora — `thinkers`
(AnchorAndWave public-domain library) and `youth-sports` (RaisingGoodSports) — plus one
general-interest roster entry (`@bigthink`/Adam Grant) inside `output/brand-intel/`. Both
corpora now feed the
RaisingGoodSports-only `rgs-grounding` and `rgs-pairing-review` skills (see
`.claude/skills/rgs-grounding/` and `.claude/skills/rgs-pairing-review/`) — the general-interest
roster entry remains unused by any skill. See `README.md`'s scope note for the full picture.

### The eight skills (`.claude/skills/`)

One atomic skill per production stage, chained by hand (no orchestrator/meta-skill).
Each skill's `SKILL.md` states its own upstream input and downstream next stage.

| Skill | Stage | Input | Output |
|---|---|---|---|
| `shorts-ideation` | Idea → concept | a raw topic/idea | validated concept brief (angle, hook, packaging direction) |
| `shorts-scripting` | Concept → script | the concept brief | shot-ready script with timing |
| `shorts-styleboard` | Script → world lock | the script | world lock + Style Library bindings (Gate C reads its `WORLD LOCK`) |
| `voiceover-brief` | Script → voice spec | the script | ElevenLabs voiceover production brief |
| `visual-prompts` | Script → visual prompts | the script + the styleboard | dual-register prompt sheet (present-day photographic + source-era painterly), copy-paste ready, Gate C linted |
| `music-brief` | Script + voice spec → bed arc | the script + voiceover brief | bed arc (movements, hook hold-out, tone-contradiction check) |
| `shorts-assembly` | Script + assets → edit plan | script + voiceover brief + prompt sheet (+ optional bed arc) | assembly/edit plan |
| `social-repurpose` | Finished Short → post copy | the finished Short + its script/packaging | multi-surface post copy (YouTube + cross-platform) |

Each skill's `references/` holds the distilled corpus rules for that stage, with
markers and citations intact. `SKILL.md` bodies stay lean (progressive disclosure);
detail lives in `references/`.

### Tool-specialist skills (not corpus-derived — read this before editing them)

Three skills sit **beside** the eight-skill pipeline rather than inside it. Each is
usable standalone for any job in its tool, and each is also the downstream
specialist for one pipeline stage. None is built from the corpus:

| Skill | Tool | Standalone use | Pipeline role |
|---|---|---|---|
| `elevenlabs-audio` | ElevenLabs | Any audio job — audiobook, agent, ad, dialogue | `voiceover-brief` hands down the creative call; this skill emits the executable configuration |
| `midjourney-prompting` | Midjourney | Any image job | `visual-prompts` owns beat mapping; this skill writes the prompts |
| `elevenlabs-music` | Eleven Music | Any music job — podcast bed, ad, game loop, trailer cue | `music-brief` hands down the bed arc; this skill emits the prompt, composition plan and payload |

The boundary is the same in all three cases: **the pipeline skill owns the creative
call, the specialist owns the executable output.** The specialist accepts the
creative call and does not re-litigate it.

Their source of truth is web-verified vendor documentation, not the 420-video
corpus — for `elevenlabs-audio`, `docs/elevenlabs-production-runbook.md`
(verified 2026-07-26); for `midjourney-prompting`,
`.claude/skills/midjourney-prompting/references/v82-model-delta.md` (verified
2026-07-26 against `docs.midjourney.com`), which layers over the corpus's own
`docs/midjourney-prompting-guide.md` §1a and is the tie-breaker where the two
disagree; for `elevenlabs-music`, `docs/elevenlabs-music-runbook.md` (verified
2026-08-06). Because vendor facts go stale and vendor-adjacent
"runbooks" are often wrong, these skills add one marker to the standard three:

- **`[T-unverified]`** — asserted by a supplied source but **not** confirmed
  against live vendor docs. Usable as a starting hypothesis, never stated as
  fact. Say so out loud when you use one.

The enterprise runbook that seeded `elevenlabs-audio` was **wrong in eight
places** — see `docs/elevenlabs-production-runbook.md` §10 for the full
verification log. The V8.2 runbook that seeded `midjourney-prompting` was
**wrong in six** — see that skill's `references/v82-model-delta.md`. The
Eleven Music design brief that seeded `elevenlabs-music` was **wrong in
two** — see `docs/elevenlabs-music-runbook.md` §7. Treat plausible-sounding
vendor facts with the same suspicion, and re-verify before extending these
skills.

## Anti-generic guarantee (read before editing any skill)

The corpus is the **only** knowledge source for the eight pipeline skills. Do not
fall back on general "content creation best practices" — if the corpus doesn't
cover something, the skill must say so and flag it, not silently substitute
generic advice. When editing or extending a skill: every new normative line needs
a `[C]`/`[I]`/`[T]` marker that traces to real corpus text (or is honestly
flagged as a gap).

`[P]` is **not** an escape hatch from this. It may only record a concrete choice
the owner actually made (a pinned `voice_id`, a fixed brand parameter) — never a
craft rule, a recommendation, or a "best practice." If you find yourself reaching
for `[P]` to justify advice, that is the invented-content bug this guarantee
exists to catch.

The same discipline applies to the tool-specialist skills, with vendor
documentation in place of the corpus: every normative line needs a marker
tracing to verified vendor docs (`[T]`), general practice (`[I]`), or an
honestly-flagged unverified assertion (`[T-unverified]`). An unmarked normative
line is a bug in either case.

## FamilyBrain firewall (absolute, read before touching git remotes or `output/`)

This project has **zero** connection to FamilyBrain (`C:\Projects\FamilyBrain\`) or any
`brain_*` MCP tool. It does not read from, write to, or reference that repo, its
database, its Pi, or its embeddings. Never add a FamilyBrain git remote, submodule, or
path reference here. If corpus content ever needs refreshing from upstream sources,
re-run the toolkit scripts at repo root against the public web — never reach back into
FamilyBrain.

## Origin

The corpus was originally built as a research corpus (`corpus-archive/`) inside the
FamilyBrain repo, for an unrelated brand-intel feature. It was copied — not moved,
not `git mv`'d — into this repo as a one-time, one-directional operation: a fresh
`git init` with no shared history or remote. `README.md`'s "Notes & scope" section and
a few source-file headers narrate this (toolkit provenance, e.g. `gen_thinkers_manifest.ts`
importing a sibling repo's TypeScript source) as historical/structural fact, not as a
live dependency — none of it is runnable against FamilyBrain from here.

## Using the skills

### In Claude Code

Skills at `.claude/skills/<name>/SKILL.md` are auto-discovered when working in this
repo — just describe the stage you want ("turn this idea into a concept brief") and
the matching skill triggers.

### In Claude Cowork

Skills are also packaged as a Cowork plugin. From this repo root:

```bash
bash scripts/build-cowork-plugin.sh
```

This copies `.claude/skills/` into `cowork-plugin/skills/`, writes
`cowork-plugin/.claude-plugin/plugin.json`, and zips the result to
`dist/content-studio.plugin`. Load that `.plugin` file in Cowork to install all eight
skills there. `.claude/skills/` is the single source of truth — never hand-edit
`cowork-plugin/skills/`; re-run the build script instead.

## Conventions

- **Local only** in the sense that nothing here deploys, is hosted externally, or syncs to a
  cloud — but **not** network-free. The repo makes **22** outbound call sites across **11**
  destinations. The tables below are the complete roster;
  `tests/test_doc_truth.py::test_claude_md_lists_every_outbound_call_site` fails if a call site
  exists in the code and not here, or here and not in the code, so this list cannot quietly rot
  the way its two-item predecessor did.

  **App runtime** — reached by running the app or letting the scheduled discovery run fire. No
  operator action required beyond starting it:

  | Destination | Call site(s) | Cost | What leaves this machine |
  |---|---|---|---|
  | Anthropic, via a `claude` subprocess | `pipeline_app/cli_runner.py:291` | **billed to your Claude plan** | Every pipeline stage turn: the rendered kickoff prompt, plus whatever the stage's allowed tools read from this repo. This call *is* the app. |
  | Anthropic, via a `claude -p` subprocess | `pipeline_app/comment_draft.py:353` | **billed** | Exception 2 below. |
  | `api.resend.com` | `pipeline_app/discovery_notify.py:114` | free tier | Exception 1 below. |
  | `api.brightdata.com` | `pipeline_app/brightdata_job.py:348` (trigger), `:361` (poll), `:374` (fetch), `:408` (delete) | **billed per record — real money, per run** | The target handle or profile URL and the job parameters, for Instagram / LinkedIn / Facebook / X discovery. |
  | `www.googleapis.com/youtube/v3` | `pipeline_app/discovery_youtube_api.py:121` | quota-metered | Video ids and the API key. |
  | `public.api.bsky.app` | `pipeline_app/discovery_bluesky.py:35` | free | The handle being enumerated. |
  | `www.youtube.com`, via `yt-dlp` | `pipeline_app/discovery_youtube.py:44`, `:157`, `:262`, `:403` | free | The handle or video id — and the session cookies in `pipeline-app/cookies.txt` when that file exists. |
  | `www.youtube.com`, via `youtube-transcript-api` | `pipeline_app/discovery_youtube.py:380` | free | The video id. |

  **Manual toolkit** — only when you run a downloader script by hand. Never reached by the app or
  by the scheduled task:

  | Destination | Call site(s) | What leaves this machine |
  |---|---|---|
  | Project Gutenberg / `archive.org` | `download_thinkers.py:108` | The work URLs listed in `manifests/thinkers.json`. |
  | `public.api.bsky.app` | `download_brandintel.py:69` (shared `http_get()` helper), `:273` (bsky call site) | The handle being enumerated. |
  | `www.youtube.com`, via `yt-dlp` / `youtube-transcript-api` | `download_brandintel.py:78`, `:87`, `:131`, `:154` | The handle or video id. |
  | arbitrary URL (per `manifests/brand_sources.json`'s `rss` entries) | `download_brandintel.py:336` | The feed URL configured in the roster; no other data — a plain HTTP GET. No feeds are configured today (the `rss` section holds only a `_comment`), but `--platforms` defaults to `youtube,bluesky,rss` and `do_rss` is wired into `main()`, so this destination is live and default-on the moment any feed is added. |

  **Two of these carry corpus content rather than just an identifier.** Both are in the daily
  discovery email path and both are deliberate; their contracts are unchanged:

  1. **Notification email, via Resend's HTTP API.** Sends the day's captured post titles, author
     display names (a handle appears only when no display name is configured for that author),
     engagement metrics, publish dates when known, and post URLs; a ~400 character excerpt of the
     one post the email spotlights; and three AI-drafted comments on it. Never a full transcript,
     never a full post body, never any other corpus content.
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
- **Adding a discovery platform.** A new adapter's `download_item` must write YAML frontmatter
  containing `fetched_at` (an aware-UTC `isoformat(timespec="seconds")` string), with the post's
  text as the markdown body. An adapter honoring that contract appears in the daily email —
  inventory entry, link, title, and spotlight eligibility — with **no change to any email-side
  module**. `fetched_at` is the only **mandatory** field: it is the watermark, and an item without
  it is excluded from the run. `url` is strongly expected but not required — an item missing it is
  still listed, rendered without a link, and a warning goes to stderr. `like_count`,
  `comment_count`, `view_count`, and `published` are optional and are omitted from the render when
  absent. `download_brandintel.py` is a known, deliberate exception: nothing it writes falls inside
  a run's watermark.
- `output/` (the downloaded corpus) is git-ignored — never commit it.
- `cowork-plugin/skills/` and `dist/` are build artifacts of the skills — git-ignored,
  regenerated by `scripts/build-cowork-plugin.sh`.
- When adding corpus-grounded content to a skill, cite it the way the corpus does:
  `(Channel, video_id)` for `[C]`, and keep `[T]` facts dated.
- The `visual-prompts` output format is machine-parseable and enforced by
  `scripts/lint_prompt_sheet.py` (Gate C). Run it as
  `python scripts/lint_prompt_sheet.py <sheet> --styleboard <styleboard>` on any emitted sheet
  before handing off to `shorts-assembly`; a failing gate blocks emission. The sheet carries
  `{style:...}` slots, never literal `--sref` codes — C16 rejects an invented code and C17
  rejects a shot with no style mechanism at all. C20 resolves each slot's declared label
  against `docs/style-library.md`, read from the repo by default (`--style-library` overrides),
  so a label naming no entry fails the gate instead of failing at paste time.
- **Every defect writeup names the assertion that would have caught it.** The 2026-08-08 audit
  found 32 S0/S1 defects against a 1,034-test suite at 95% line coverage, and **zero** of them had
  a test — not because they were untestable (29 were a single assertion away, 3 partially so, none
  genuinely out of reach) but because nobody was ever required to ask. So: any finding recorded
  under `docs/audit/` and any bug fixed anywhere in this repo carries a
  *"which assertion would have failed?"* line, and the fix lands that assertion as a named
  regression test that was observed failing first. A fix with no such test is not a fix; a
  finding with no such line is not finished. Coverage is not the bar — 95% coexisted with 328
  defects.
  `tests/test_doc_truth.py::test_every_audit_finding_is_claimed_by_exactly_one_remediation_plan`
  keeps the finding→plan mapping total, so the gap stays measured instead of being measured once.
- **Tests live in two suites, each run from its own directory.** Repo root:
  `python -m pytest tests/ -v` (the linters and skill provenance). App:
  `cd pipeline-app && python -m pytest`. Run each from the directory named — `pipeline-app`
  has its own `scripts/` package, and invoking its suite from the repo root shadows it with
  the root `scripts/` and raises `ModuleNotFoundError`. A `pytest.ini` at each level pins the
  rootdir so a bare `pytest` does the right thing in both places.
