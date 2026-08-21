# Headless YouTube Channel — Research, Launch & Production Kit

This folder is a kit for launching and producing a **brand-new, faceless/headless YouTube channel —
Shorts-first, long-form later**. It has two parts: a **3-document launch kit** (strategy) and a set of
**asset-production guides** (the tools you'll actually run). It was built by extracting and synthesizing
**1,100+ findings** from a **420-video corpus** of creator-education + tool-tutorial YouTube transcripts
(**14 channels**), then cross-checking tooling and policy against the live web.

Everything here is **derived from real creator transcripts** (not opinion), with every corpus-grounded
claim cited to its source video. Where the corpus runs thin (specific AI tools, current monetization
thresholds, fast-moving product features), the claims are **web-verified and dated**, and labelled as such.

---

## The three documents (read in this order)

| # | Document | What it is | Size |
|---|----------|-----------|------|
| 1 | **[headless-youtube-audit.md](headless-youtube-audit.md)** | **The evidence base.** Every learning, do/don't, pitfall, and best practice from the corpus, organized into 13 themes, plus Dos/Don'ts, Top-12 pitfalls, and a best-practice checklist. 679 inline citations. | ~14,800 words |
| 2 | **[headless-channel-launch-gameplan.md](headless-channel-launch-gameplan.md)** | **The roadmap.** A phased plan — niche selection (with a fill-in worksheet) → channel foundation → 90-day Shorts sprint → long-form expansion → monetization gates → rights/policy gate. | ~3,555 words |
| 3 | **[headless-shorts-production-playbook.md](headless-shorts-production-playbook.md)** | **The how-to.** Shorts anatomy, an opinionated external tool stack (with a $0 and a paid build), text/voice overlay systems, AI asset workflow, and **8 fill-in production templates**. | ~6,010 words |

**Suggested flow:** read the **audit** to understand the space → use the **game plan** to sequence your
launch → keep the **playbook** open while you produce.

## Asset-production guides (the tools you'll run)

Deep-dive references for the two AI tools the playbook leans on most. Use them alongside the playbook's
asset-workflow (§6) and voice-overlay (§5) sections.

| Guide | What it is | Size |
|-------|-----------|------|
| **[midjourney-prompting-guide.md](midjourney-prompting-guide.md)** | **Midjourney (image + video).** Current V8.1 feature snapshot, prompt anatomy, a full parameter reference, references/consistency (Omni Reference, `--sref`, moodboards), modes/editing, image→video, faceless-channel asset use-cases, and fill-in **prompt recipes**. Built from 384 findings across 4 dedicated MJ channels + web-verified features. | ~6,300 words |
| **[elevenlabs-voiceover-guide.md](elevenlabs-voiceover-guide.md)** | **ElevenLabs (text-to-voice).** Models (v3/v2/Flash), voice choice & cloning, the full **settings guide** (stability/similarity/style/speed with content-type presets), scripting for TTS, −14 LUFS production, pricing, and a cheat-sheet. Web-verified `[T]` + the corpus's real voiceover findings `[C]`. | ~1,900 words |

### Vendor runbooks (not corpus-derived)

Two further guides sit outside the corpus. Both are built from vendor documentation rather than
the 420-video corpus, so they are listed separately and carry an extra provenance marker.

| Runbook | What it is | Size |
|-------|-----------|------|
| **[elevenlabs-production-runbook.md](elevenlabs-production-runbook.md)** | **ElevenLabs platform truth** — engine topology and the feature-compatibility matrix, the full API parameter surface, v3's three stability modes, the verified audio-tag catalog, PLS pronunciation dictionaries, chunking and request stitching, credit discipline, and zero-retention. Verified against live ElevenLabs docs **2026-07-26**; §10 is a claim-by-claim verification log recording **eight places the supplied source runbook was wrong**. Backs the `elevenlabs-audio` skill. | ~4,600 words |
| **[elevenlabs-music-runbook.md](elevenlabs-music-runbook.md)** | **Eleven Music platform truth** — composition-plan structure, prompt craft, the API payload surface, and credit discipline. Verified against live ElevenLabs docs **2026-08-06**; §7 records **two places the supplied design brief was wrong**. Backs the `elevenlabs-music` skill. | ~2,300 words |

This runbook adds **`[T-unverified]`** to the marker key below: *asserted by a supplied source but
**not** confirmed against live vendor docs.* Treat it as a starting hypothesis, never as fact. The
two documents are complementary and deliberately separate — the guide above tells you what working
creators do; the runbook tells you what the platform actually supports.

---

## Provenance key

Every substantive claim carries one of three markers so you always know how much to trust it:

- **`[C]` Corpus-cited** (default; usually unmarked in the audit) — extracted from a transcript, cited as
  `(Channel, video_id)`. Two or more channels agreeing = flagged **strongly-supported**.
- **`[I]` Industry practice** — well-established general craft not specific to this corpus.
- **`[T]` Tool / policy fact** — product, pricing, or YouTube-policy specifics, **web-verified 2026-07-23**.
  These go stale fast — **re-verify tool pricing before relying on it.**

---

## The source corpus (14 channels, 420 videos)

**Faceless-core** (operators running faceless channels): One Person Business, Make Money Matt, Romayroh.
**Craft-general** (transferable YouTube craft): Dan the creator, Kallaway.
**Shorts-specialists** (ground the Shorts playbook): Jenny Hoyos, Nate Black, vidIQ, Nick Nimmin, Roberto Blake.
**Midjourney / AI assets** (added 2026-07-23 to ground the Midjourney guide): Future Tech Pilot,
Wade McMaster, Tao Prompts, Tokenized AI.

Finding counts by provenance: faceless-core 230 · craft-general 189 · shorts-specialist 326 ·
midjourney 384. The full per-video **content index** (all 420 videos, with AI-generated summaries/topics)
is at `../output/brand-intel/youtube/_youtube-content-index.md` / `.csv`.

**Honest limitations** (see the audit's *Source coverage* section for detail):
- The corpus is long-form-faceless heavy; **Shorts-specific production mechanics** were the thinnest
  themes (voiceover-audio 24, visuals-ai-assets 27), so the playbook's tooling sections lean on
  web-verified `[T]` / `[I]` rather than the corpus — and say so.
- Jenny Hoyos's findings are mostly **observed structural technique** reverse-engineered from her
  exemplar Shorts (medium confidence), not stated advice.
- `[T]` tool/pricing/policy facts are a **2026-07-23 snapshot**.

---

## Where the underlying data lives

- Raw transcripts + the content index: `../output/brand-intel/youtube/` (git-ignored).
- Extracted findings, merged + validated, per-video index metadata, and the web-verified notes:
  `../output/brand-intel/_work/` (git-ignored: `findings_*.json`, `findings_merged.json`,
  `findings_mj_merged.json`, `yt_meta_*.json`, `tool_policy_notes.md`, `midjourney_feature_notes.md`,
  `elevenlabs_notes.md`).
- This `docs/` folder is the **committed** output: the three launch-kit documents and two
  asset-production guides above, the two vendor runbooks, plus `style-library.md` (the style
  registry Gate C resolves `{style:...}` slot labels against) and `script-language-baseline.md`
  (the language baseline Gate D lints against) — nine documents and this README.
  `tests/test_doc_truth.py::test_docs_readme_accounts_for_every_committed_doc` fails if a tenth
  appears without a line here.

> These are working strategy documents. When a tool price or YouTube policy changes, update the relevant
> `[T]` line rather than trusting the date stamp.
