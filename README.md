# ContentStudio Corpus Archive Toolkit

A self-contained toolkit to **download the original raw source material** behind
three reference corpora onto your laptop, as plain `.txt` / `.md`, for manual
inspection. It stands alone — no other app, database, or service needs to be
running for it to work.

Every corpus is fetched fresh from its public source (or, for youth-sports,
copied from a local checkout — see the note in that section). The downloaded
texts land in a git-ignored `output/` folder and are never committed.

**Scope note:** ContentStudio's six shorts-production skills (see the
top-level `CLAUDE.md`) are built entirely from the **Brand-intel / headless
YouTube** row below — the `docs/` guides and `output/brand-intel/`. The
**Thinkers** and **Youth sports** rows are inert leftover toolkit capability,
carried over because this toolkit downloads three corpora as a unit; they are
not read by any ContentStudio skill.

## What it collects

| Corpus | Source | What you get |
|---|---|---|
| **Thinkers** (`anchorandwave`, 53 works) | Project Gutenberg + Internet Archive (URLs from `src/library/manifest.ts`) | Raw `.txt` per work, organised by thinker, plus optional boilerplate-stripped `.cleaned.md` |
| **Youth sports** (`raisinggoodsports`) | Already in the repo at `corpus/raisinggoodsports/` | Verbatim copy: `master-edition-v2.md` (the full original digest) + 35 `rgs-*.md` theme files + README |
| **Brand-intel / headless YouTube** | YouTube (`yt-dlp`), Bluesky public API, RSS | Per-video **transcript** + description + metadata; full Bluesky post text; RSS article text |

## Requirements

- **Python 3.9+**
- `pip install -r requirements.txt` — installs `requests`, `yt-dlp`,
  `youtube-transcript-api`
- The youth-sports step (`copy_youthsports.sh`) copies from a sibling
  `corpus/raisinggoodsports/` checkout and is **not runnable standalone in
  this repo** — that source tree lives elsewhere. Its already-downloaded
  output was preserved under `output/youth-sports/` at copy time; the script
  itself is dead weight here (see the scope note above). The other two steps
  only need network.

> Note: some dev machines have a known issue where **Node.js** can't reach
> external HTTPS. This toolkit is deliberately **Python + yt-dlp only** (no
> Node), so it is unaffected. If a plain `python` download ever stalls, `curl -L`
> against the same URL confirms connectivity.

## Quick start

Run from this directory (`ContentStudio/`, the toolkit's own root):

```bash
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

./run_all.sh                    # everything, recent-window YouTube
# or the full YouTube back-catalogue (much larger, slower):
./run_all.sh --full-channel
```

Everything lands under `output/`:

```
output/
  thinkers/anchorandwave/<thinker>/<slug>.txt (+ .cleaned.md)
  youth-sports/raisinggoodsports/…
  brand-intel/youtube/<handle>/<videoId>__<title>.md
  brand-intel/bluesky/<handle>/<rkey>.md
  brand-intel/rss/<feed>/<entry>.md
  brand-intel/_manifest.csv
```

## Run steps individually

```bash
python download_thinkers.py --clean          # 53 works; --clean adds .cleaned.md
python download_thinkers.py --only aurelius-meditations,thoreau-walden

bash copy_youthsports.sh                      # copy the youth-sports corpus

python download_brandintel.py                 # recent window (25/source)
python download_brandintel.py --full-channel  # entire YouTube back-catalogue
python download_brandintel.py --platforms youtube
python download_brandintel.py --limit 50 --sleep 3
```

### If YouTube throttles you

YouTube soft-limits roughly 100–200 transcript fetches per hour per IP. The
downloader already paces requests and retries. If you still get blocked, use
your own logged-in browser session:

```bash
python download_brandintel.py --cookies-from-browser chrome    # or firefox, edge, safari
```

Videos with no captions at all are recorded with `has_transcript=false` in
`_manifest.csv`; the run never aborts on a single missing transcript.

## The roster (`manifests/brand_sources.json`)

- **General-interest, out of scope for ContentStudio:** YouTube `@bigthink`
  (filtered to "Adam Grant"), Bluesky `adamgrant.bsky.social` — a leftover
  entry from the wider toolkit, unrelated to the headless-YouTube corpus.
- **The 14-channel headless-YouTube / MJ corpus** (see `docs/README.md`'s
  provenance section): `@Romayroh`, `@danthecreatr`, `@makemoneymatt`,
  `@kallawaymarketing`, `@One-Person-Business`, `@JennyHoyos`,
  `@ThatNateBlack`, `@vidIQ`, `@nicknimmin`, `@robertoblake`,
  `@FutureTechPilot`, `@WadeMcMaster`, `@TaoPrompts`, `@tokenizedai`.

Edit that JSON to add/remove sources. For RSS, use the feed URL as the `handle`.

## Regenerating the thinkers list

`manifests/thinkers.json` was generated from a sibling app's source-of-truth
manifest via `gen_thinkers_manifest.ts` — see that file's header. It is **not
runnable standalone in this repo** (kept as documentation only; the thinkers
corpus is out of scope for ContentStudio's skills — see the scope note above).

## Notes & scope

- **Transcripts** are the actual spoken-word captions (not just titles +
  descriptions) — this toolkit is the only place they exist locally.
- **Public feeds are windowed**: without `--full-channel`, YouTube gives recent
  uploads; Bluesky returns up to ~100 recent posts. Use `--full-channel` /
  `--limit` for more.
- Everything under `output/` is git-ignored on purpose.
