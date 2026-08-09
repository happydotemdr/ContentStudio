# P10 — Roster: declarative creator × platform coverage, and a backfill that cannot eat the corpus

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
> The Global Constraints, test standard and Frozen interfaces of
> [`../2026-08-08-audit-remediation.md`](../2026-08-08-audit-remediation.md) are binding on every task below and are
> not restated here.

**Depends on:** P1 (Wave A). P1 creates the `creators` table, `handles.creator_id`, the `handles.platform` CHECK,
`UNIQUE(platform, handle)` and `pipeline_app/obs.py`. This package **populates** them. Do not create them here;
`schema.sql` is P1's file.

**Wave B priority:** run this package first alongside P2. D-04 is the only data-destroying finding outside the
artifact layer.

---

## 1. Scope

### Files this package owns (no other package may touch these)

```
manifests/brand_sources.json                                  (REPO ROOT)
pipeline-app/scripts/migrate_handles_from_manifest.py
pipeline-app/scripts/backfill_youtube_frontmatter.py
pipeline-app/tests/test_migrate_handles.py
pipeline-app/tests/test_backfill_youtube_frontmatter.py
```

### Files this package reads but must NOT modify

| File | Owner | Why we read it |
|---|---|---|
| `pipeline-app/pipeline_app/db.py` | P1 | `get_connection`, `init_db`, `list_platform_handles`, `get_handle_by_platform_and_handle` |
| `pipeline-app/pipeline_app/schema.sql` | P1 | `creators`, `handles.creator_id`, the platform CHECK |
| `pipeline-app/pipeline_app/obs.py` | P1 | `obs.log`, `obs.record_event` |
| `pipeline-app/pipeline_app/discovery_paths.py` | P8 | `handle_slug`, `find_slug_collision` |
| `pipeline-app/run_discovery_cron.py` | P8 | `build_adapters()` — the platform registry our `PLATFORMS` tuple is pinned against |
| `pipeline-app/pipeline_app/discovery_youtube_api.py` | P6 | `api_key()`, `fetch_metadata`, `MAX_IDS_PER_CALL` |
| `pipeline-app/pipeline_app/artifacts.py` | P2 | `parse_frontmatter`, `render_frontmatter` |
| `download_brandintel.py` | **unowned by any package** | It is the manifest's *other* consumer. See the hard constraint below. |

> **Hard constraint — the manifest schema change must be additive.**
> `download_brandintel.py:387-402` reads `roster.get("youtube")`, `roster.get("bluesky")` and `roster.get("rss")`
> as flat arrays and uses only `handle` / `display_name` / `keyword_filter` from each entry. That file is in no
> package's file list, so **we may not edit it**. Therefore the new schema keeps every existing top-level array
> in place with its existing entry shape, and adds new keys and new per-entry fields alongside. Restructuring the
> manifest into a creator-keyed tree would silently break the corpus downloader; do not do it.

### Finding IDs owned (11)

`B-70`, `B-71`, `B-75`, `B-76`, `B-77`, `B-78`, `B-79`, `B-81`, `B-85`, `D-04`, `D-05`

### What "done" means for this package

The operator asks *"are we tracking all social platforms for our key creators?"* and gets an answer from a
committed file plus one command, with **zero `UNANSWERABLE` cells**:

```bash
cd pipeline-app && python scripts/migrate_handles_from_manifest.py --report
```

---

## 2. Finding → task map

Total coverage: every ID below maps to at least one task.

| Finding | Severity | Failure mode | Task(s) | One-line resolution |
|---|---|---|---|---|
| **B-70** | S2 | coverage-gap | T1, T3, T4, T11 | All seven adapter-registry platform keys are present in the manifest (empty arrays where nothing is tracked) and the seeder iterates the registry, so no platform lacks a declarative source. |
| **B-71** | S2 | silent | T2, T3 | An unrecognized top-level manifest key is a hard, non-zero, event-recorded error; recognized platform keys are all read from one shared `PLATFORMS` tuple. |
| **B-75** | S3 | silent | T7 | Seeding writes `status='pending'`; only a real enumerate-and-download round trip may write `validated`. |
| **B-76** | S2 | silent | T8, T9 | Re-running upserts manifest-owned columns and reports manifest-absent DB rows as drift; run-owned columns are never stomped. |
| **B-77** | S4 | latent | T4, T5 | `cohort` is an explicit per-entry manifest field; `derive_cohort` survives only as a fallback and is proven unused by the shipped manifest. |
| **B-78** | S3 | coverage-gap | T4, T6 | `included` is an explicit per-entry manifest field, honored by the seeder; the two declared out-of-scope general-interest entries ship as `"included": false`. |
| **B-79** | S2 | silent | T13 | The `rss` `_comment` states the truth (downloader-only, not on the daily discovery path) and the coverage report classifies `rss` as out-of-app-scope. |
| **B-81** | S3 | latent | T11, T12 | Three tests load the **shipped** `manifests/brand_sources.json`: it parses, every key is recognized, every entry resolves to a creator, and the coverage matrix has no `UNANSWERABLE` cell. |
| **B-85** | S4 | docs-drift | T13 | The `_comment` drops the stale skill count and points at CLAUDE.md's skill table. |
| **D-04** | **S0** | silent | T14, T15, T16, T17 | Key preflight refuses to enrich without a key; a total enrichment miss aborts **before any write**; provenance and existing counts are never downgraded; per-file failures set a non-zero exit. |
| **D-05** | S3 | silent | T18 | Files whose metadata block parsed empty are counted, skipped unless `--rewrite-unparsed`, and marked `metadata_inferred` when written. |

Supporting task with no finding of its own: **T10** (populate `creators` / `handles.creator_id`) is the mechanism
B-70's coverage report and B-72's identity gap both need. B-72 belongs to no package's finding list because it is
schema work; P1 builds the columns, T10 fills them.

---

## 3. The new `brand_sources.json` schema

### 3.1 Shape

Three kinds of top-level key, and nothing else:

| Key | Kind | Read by |
|---|---|---|
| `_comment` | documentation | humans |
| `creators` | **new** — the identity block: `slug → {display_name, note}` | `migrate_handles_from_manifest.py` |
| `youtube`, `bluesky`, `instagram`, `linkedin-profile`, `linkedin-company`, `facebook`, `x` | platform rosters, one array each, **always present even when empty** | `migrate_handles_from_manifest.py` (all seven); `download_brandintel.py` (`youtube`, `bluesky` only) |
| `rss` | downloader-only roster, not a discovery platform | `download_brandintel.py` only |

Any other top-level key is a **hard error** (T2). That is what closes B-71: `"instgram": [...]` no longer vanishes.

**Why seven platform keys and not six.** The audit's matrix uses six columns because it collapses LinkedIn into
one. The adapter registry (`run_discovery_cron.build_adapters()`) and P1's frozen `handles.platform` CHECK both
enumerate **seven** values, splitting `linkedin-profile` from `linkedin-company`. The manifest is pinned to the
registry (T1), so it carries seven keys; the audit's six-column matrix maps onto it 1:1 with `linkedin` expanding
to two columns. Seven is a superset of six — no cell is lost.

### 3.2 Per-entry fields

| Field | Required | Meaning |
|---|---|---|
| `handle` | yes | Platform-native handle. Must not slug-collide with another entry on the same platform. |
| `creator` | yes | A slug that **must** exist in the `creators` block. This is the cross-platform identity (B-72). |
| `display_name` | no | Per-platform display name; falls back to the creator's. Read by `download_brandintel.py`. |
| `cohort` | yes | Explicit — `guru` \| `shorts-specialist` \| `midjourney-source` \| `general-interest`. No longer inferred from prose (B-77). |
| `included` | yes | Explicit — whether the daily discovery run pulls this handle (B-78). |
| `keyword_filter` | no | Title substring filter. Read by `download_brandintel.py`. |
| `note` | no | Free prose. **No longer load-bearing.** |

### 3.3 Worked example entry (the Adam Grant case — one creator, two platforms, both out of scope)

```json
{
  "_comment": "The headless YouTube / brand-intel roster, and the declarative source of truth for which creators we track on which platforms. EVERY adapter-registry platform has a key here; an empty array means 'we deliberately track nobody on this platform', which is a statement, not a gap. Each entry names a `creator` slug from the `creators` block -- that slug is the only cross-platform identity, so one creator's handles on different platforms are joinable. `cohort` and `included` are explicit fields; nothing is inferred from `note`. The @bigthink + adamgrant.bsky.social pair is a general-interest psychology source unrelated to the headless-YouTube corpus; it is kept here because this manifest tracks the whole brand-intel roster this toolkit can pull, and it ships `included: false` so the daily discovery run does not pull it. None of ContentStudio's pipeline skills use it -- see CLAUDE.md's skill table for the current skill set, and docs/README.md's 14-channel list for the actual corpus. Seeded into the app by `cd pipeline-app && python scripts/migrate_handles_from_manifest.py`; inspect coverage with `--report`.",

  "creators": {
    "adam-grant":          { "display_name": "Adam Grant",          "note": "general-interest psychology; not part of the 14-channel corpus" },
    "romayroh":            { "display_name": "Romayroh" },
    "dan-the-creator":     { "display_name": "Dan the Creator" },
    "make-money-matt":     { "display_name": "Make Money Matt" },
    "kallaway":            { "display_name": "Kallaway" },
    "one-person-business": { "display_name": "One Person Business" },
    "jenny-hoyos":         { "display_name": "Jenny Hoyos" },
    "nate-black":          { "display_name": "Nate Black" },
    "vidiq":               { "display_name": "vidIQ" },
    "nick-nimmin":         { "display_name": "Nick Nimmin" },
    "roberto-blake":       { "display_name": "Roberto Blake" },
    "future-tech-pilot":   { "display_name": "Future Tech Pilot" },
    "wade-mcmaster":       { "display_name": "Wade McMaster" },
    "tao-prompts":         { "display_name": "Tao Prompts" },
    "tokenized-ai":        { "display_name": "Tokenized AI" }
  },

  "youtube": [
    { "handle": "@bigthink", "creator": "adam-grant", "display_name": "Adam Grant (via Big Think)",
      "cohort": "general-interest", "included": false, "keyword_filter": "Adam Grant",
      "note": "Big Think channel filtered to Adam Grant videos; out of corpus scope" },
    { "handle": "@Romayroh", "creator": "romayroh", "display_name": "Romayroh",
      "cohort": "guru", "included": true, "keyword_filter": null, "note": "manual-seed" },
    { "handle": "@danthecreatr", "creator": "dan-the-creator", "display_name": "Dan the Creator",
      "cohort": "guru", "included": true, "keyword_filter": null, "note": "manual-seed" },
    { "handle": "@makemoneymatt", "creator": "make-money-matt", "display_name": "Make Money Matt",
      "cohort": "guru", "included": true, "keyword_filter": null, "note": "manual-seed" },
    { "handle": "@kallawaymarketing", "creator": "kallaway", "display_name": "Kallaway",
      "cohort": "guru", "included": true, "keyword_filter": null, "note": "manual-seed" },
    { "handle": "@One-Person-Business", "creator": "one-person-business", "display_name": "One Person Business",
      "cohort": "guru", "included": true, "keyword_filter": null, "note": "manual-seed" },
    { "handle": "@JennyHoyos", "creator": "jenny-hoyos", "display_name": "Jenny Hoyos",
      "cohort": "shorts-specialist", "included": true, "keyword_filter": null,
      "note": "exemplar shorts; added 2026-07-23 for the shorts-launch corpus" },
    { "handle": "@ThatNateBlack", "creator": "nate-black", "display_name": "Nate Black",
      "cohort": "shorts-specialist", "included": true, "keyword_filter": null,
      "note": "data-driven teaching; added 2026-07-23 for the shorts-launch corpus" },
    { "handle": "@vidIQ", "creator": "vidiq", "display_name": "vidIQ",
      "cohort": "guru", "included": true, "keyword_filter": null,
      "note": "shorts/algorithm teaching; added 2026-07-23 for the shorts-launch corpus" },
    { "handle": "@nicknimmin", "creator": "nick-nimmin", "display_name": "Nick Nimmin",
      "cohort": "guru", "included": true, "keyword_filter": null,
      "note": "small-channel tactics + packaging teaching; added 2026-07-23" },
    { "handle": "@robertoblake", "creator": "roberto-blake", "display_name": "Roberto Blake",
      "cohort": "guru", "included": true, "keyword_filter": null,
      "note": "monetization + packaging teaching; added 2026-07-23" },
    { "handle": "@FutureTechPilot", "creator": "future-tech-pilot", "display_name": "Future Tech Pilot",
      "cohort": "midjourney-source", "included": true, "keyword_filter": null,
      "note": "Midjourney prompting/features/styles (image+video); added 2026-07-23" },
    { "handle": "@WadeMcMaster", "creator": "wade-mcmaster", "display_name": "Wade McMaster",
      "cohort": "midjourney-source", "included": true, "keyword_filter": null,
      "note": "Midjourney art styles + tutorials; added 2026-07-23" },
    { "handle": "@TaoPrompts", "creator": "tao-prompts", "display_name": "Tao Prompts",
      "cohort": "midjourney-source", "included": true, "keyword_filter": null,
      "note": "Midjourney prompting + AI film/video workflows; added 2026-07-23" },
    { "handle": "@tokenizedai", "creator": "tokenized-ai", "display_name": "Tokenized AI",
      "cohort": "midjourney-source", "included": true, "keyword_filter": null,
      "note": "Midjourney + AI video/creative (Runway/Luma); added 2026-07-23" }
  ],

  "bluesky": [
    { "handle": "adamgrant.bsky.social", "creator": "adam-grant", "display_name": "Adam Grant",
      "cohort": "general-interest", "included": false, "keyword_filter": null,
      "note": "out of corpus scope; same creator as the @bigthink YouTube entry" }
  ],

  "instagram":        [],
  "linkedin-profile": [],
  "linkedin-company": [],
  "facebook":         [],
  "x":                [],

  "rss": [
    { "_comment": "RSS is served ONLY by download_brandintel.py (`python download_brandintel.py --platforms rss`). There is no RSS adapter in run_discovery_cron.build_adapters(), so a feed added here does NOT reach the daily discovery run, the handles table, or the morning email. Add feeds as {\"handle\": \"https://example.com/feed.xml\", \"display_name\": \"...\"} for the downloader only." }
  ]
}
```

**Empty arrays are the entire point.** `"instagram": []` is a committed statement that we track nobody on
Instagram. That is what turns 74 `UNANSWERABLE` matrix cells into 74 honest `not tracked` cells (B-70).

### 3.4 Behavior change this ships (call it out in the commit and in P14's README step)

`@bigthink` and `adamgrant.bsky.social` move from `included=true` to `included=false`. After T8's upsert lands, a
re-run of the seeder propagates that to an existing DB and the daily discovery run stops pulling them. This is
B-78's fix. To revert, flip the two `included` fields to `true` and re-run the seeder — one field, one diff line.

---

## 4. Tasks

Each task is a full TDD cycle: **write the failing test → run it → see it fail for the right reason → implement →
see it pass → commit.** Every test in this section belongs to one of the two test files this package owns.

App-suite commands throughout (never run these from the repo root — the root `scripts/` shadows
`pipeline-app/scripts/`):

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app"
python -m pytest tests/test_migrate_handles.py -q
python -m pytest tests/test_backfill_youtube_frontmatter.py -q
```

---

### T1 — `PLATFORMS` is pinned to the adapter registry  · B-70

- [ ] **Test** — append to `pipeline-app/tests/test_migrate_handles.py`:

```python
from run_discovery_cron import build_adapters
from scripts.migrate_handles_from_manifest import PLATFORMS


def test_platforms_tuple_matches_the_adapter_registry():
    """The manifest's platform keys ARE the trackable platforms. If an adapter
    is added or renamed and this tuple is not updated, that platform has no
    declarative roster and silently becomes untrackable (B-70)."""
    assert sorted(PLATFORMS) == sorted(build_adapters())
    assert len(PLATFORMS) == 7
```

- [ ] **Run** → `ImportError: cannot import name 'PLATFORMS'`.
- [ ] **Implement** — in `migrate_handles_from_manifest.py`, below the imports:

```python
# The trackable platforms, in registry order. Pinned to
# run_discovery_cron.build_adapters() by
# test_platforms_tuple_matches_the_adapter_registry, and to P1's
# handles.platform CHECK constraint. `rss` is deliberately NOT here: it has a
# manifest key and a download_brandintel.py branch but no adapter (B-79).
PLATFORMS: tuple[str, ...] = (
    "youtube", "bluesky", "instagram",
    "linkedin-profile", "linkedin-company", "facebook", "x",
)

DOWNLOADER_ONLY_KEYS: frozenset[str] = frozenset({"rss"})
NON_ROSTER_KEYS: frozenset[str] = frozenset({"_comment", "creators"})
KNOWN_KEYS: frozenset[str] = frozenset(PLATFORMS) | DOWNLOADER_ONLY_KEYS | NON_ROSTER_KEYS
```

- [ ] **Run** → pass. **Commit:** `feat(roster): pin the manifest platform list to the adapter registry`

---

### T2 — An unrecognized top-level manifest key is a hard error  · B-71 *(silent → all three tests)*

- [ ] **Test** — three tests, one per Three-Test-Rule role:

```python
import pytest
from scripts import migrate_handles_from_manifest as mig


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "brand_sources.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _empty_manifest(tmp_path: Path) -> Path:
    return _write(tmp_path, {"creators": {}, **{p: [] for p in mig.PLATFORMS}, "rss": []})


def test_unknown_platform_key_raises_manifest_error(conn, tmp_path):
    """FAULT: a typo'd platform key must fail, not be skipped (B-71)."""
    path = _write(tmp_path, {
        "creators": {"a": {"display_name": "A"}},
        **{p: [] for p in mig.PLATFORMS},
        "rss": [],
        "instgram": [{"handle": "@a", "creator": "a", "cohort": "guru", "included": True}],
    })
    with pytest.raises(mig.ManifestError) as excinfo:
        mig.migrate(conn, path, now="2026-08-08T00:00:00+00:00")
    assert "instgram" in str(excinfo.value)


def test_unknown_key_is_distinguishable_from_an_empty_manifest(conn, tmp_path):
    """DISTINGUISHABILITY: 'we track nobody' and 'your key was dropped' must
    not produce the same outcome. Before the fix both returned 0."""
    good = mig.migrate(conn, _empty_manifest(tmp_path), now="2026-08-08T00:00:00+00:00")
    assert good.seeded == 0 and good.errors == []

    bad_path = _write(tmp_path, {"creators": {}, **{p: [] for p in mig.PLATFORMS},
                                 "rss": [], "instgram": []})
    with pytest.raises(mig.ManifestError):
        mig.migrate(conn, bad_path, now="2026-08-08T00:00:00+00:00")


def test_main_exits_nonzero_and_records_an_event_for_an_unknown_key(tmp_path, capsys):
    """SURFACING: non-zero exit + an `events` row, not just a print (D-02)."""
    db_path = tmp_path / "pipeline.db"
    bad_path = _write(tmp_path, {"creators": {}, **{p: [] for p in mig.PLATFORMS},
                                 "rss": [], "instgram": []})
    rc = mig.main(["--manifest", str(bad_path), "--db-path", str(db_path)])
    assert rc == 2
    conn = db.get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM events WHERE kind = 'roster.manifest_invalid'").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "instgram" in rows[0]["message"]
```

- [ ] **Run** → `AttributeError: module ... has no attribute 'ManifestError'`.
- [ ] **Implement**:

```python
class ManifestError(Exception):
    """The manifest is structurally wrong. Always fatal: a roster we cannot
    fully read is worse than no roster, because the operator believes it."""


def validate_keys(data: dict) -> None:
    unknown = sorted(set(data) - KNOWN_KEYS)
    if unknown:
        raise ManifestError(
            f"unrecognized top-level key(s) {unknown} in the manifest. "
            f"Recognized platform keys are {list(PLATFORMS)}; `rss` is "
            f"downloader-only; `creators` and `_comment` are metadata. "
            f"A platform key that is not in the adapter registry has no "
            f"adapter and would be tracked by nothing."
        )
    missing = [p for p in PLATFORMS if p not in data]
    if missing:
        raise ManifestError(
            f"missing platform key(s) {missing}. Every adapter-registry "
            f"platform must have a key -- use [] to declare 'we track nobody "
            f"here', so a gap is stated rather than absent."
        )
```

Call `validate_keys(data)` as the first statement of `migrate()` after the `json.loads`. In `main()`:

```python
    try:
        result = migrate(conn, manifest_path, now)
    except ManifestError as exc:
        obs.log("roster.manifest_invalid", level="error", manifest=str(manifest_path),
                error=str(exc))
        obs.record_event(conn, kind="roster.manifest_invalid", severity="error",
                         source="migrate_handles_from_manifest",
                         message=str(exc), detail={"manifest": str(manifest_path)})
        print(f"! {exc}", file=sys.stderr)
        conn.close()
        return 2
```

- [ ] **Run** → pass. **Commit:** `fix(roster): reject an unrecognized manifest platform key instead of dropping it`

---

### T3 — The seeding loop is registry-driven, not two hardcoded keys  · B-70, B-71

- [ ] **Test**:

```python
def test_every_platform_key_is_seeded_not_just_youtube_and_bluesky(conn, tmp_path):
    """migrate() read only `youtube` and `bluesky` (:68, :76). A handle under
    any other platform key was silently dropped (B-70/B-71)."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    for platform in mig.PLATFORMS:
        payload[platform] = [{"handle": f"@on-{platform}", "creator": "c",
                              "cohort": "guru", "included": True}]
    result = mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")

    assert result.seeded == len(mig.PLATFORMS)
    for platform in mig.PLATFORMS:
        assert db.get_handle_by_platform_and_handle(
            conn, platform, f"@on-{platform}") is not None
```

- [ ] **Run** → fails: 2 seeded, 7 expected.
- [ ] **Implement** — replace the two hardcoded loops with one, and give `migrate()` a real return type:

```python
@dataclass
class MigrateResult:
    seeded: int = 0
    updated: int = 0
    skipped: int = 0
    drift: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def migrate(conn, manifest_path: Path, now: str) -> MigrateResult:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_keys(data)
    creators = data.get("creators") or {}
    creator_ids = upsert_creators(conn, creators)          # T10
    result = MigrateResult()
    for platform in PLATFORMS:
        for entry in data[platform]:
            _seed_entry(conn, platform, entry, creators, creator_ids, now, result)
    result.drift = find_drift(conn, data)                  # T9
    return result
```

`_seed_entry` keeps the existing `find_slug_collision` guard verbatim (it is correct and tested) and increments
`result.skipped` plus `result.errors` instead of returning a bare bool.

- [ ] **Run** → pass. **Commit:** `feat(roster): seed every registry platform from the manifest`

---

### T4 — Rewrite `manifests/brand_sources.json` to the new schema  · B-70, B-77, B-78

- [ ] **Test** — the schema-shape test on the **shipped** file (this is the B-81 wedge; T12 adds the rest):

```python
REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_MANIFEST = REPO_ROOT / "manifests" / "brand_sources.json"


def test_shipped_manifest_declares_every_platform_and_resolves_every_creator():
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    mig.validate_keys(data)                       # raises if a key is unknown or missing
    creators = data["creators"]
    assert len(creators) == 15
    for platform in mig.PLATFORMS:
        for entry in data[platform]:
            assert entry["creator"] in creators, f"{platform}/{entry['handle']}"
            assert entry["cohort"] in {
                "guru", "shorts-specialist", "midjourney-source", "general-interest"}
            assert isinstance(entry["included"], bool)
    assert len(data["youtube"]) == 15
    assert len(data["bluesky"]) == 1
```

- [ ] **Run** → fails: `ManifestError: missing platform key(s) ['instagram', ...]`.
- [ ] **Implement** — write the file exactly as in §3.3.
- [ ] **Verify the downloader still parses it** (it is not ours to fix, so prove we did not break it):

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767"
python -c "import json,pathlib; d=json.loads(pathlib.Path('manifests/brand_sources.json').read_text(encoding='utf-8')); print(len([s for s in d['youtube'] if 'handle' in s]), len([s for s in d['bluesky'] if 'handle' in s]), len([s for s in d['rss'] if s.get('handle','').startswith('http')]))"
```

Expect `15 1 0` — identical to what `download_brandintel.py:394-402` sees today.

- [ ] **Run** → pass. **Commit:** `feat(roster): declare all seven platforms, creator identity, explicit cohort and included`

---

### T5 — Explicit `cohort` wins; `derive_cohort` is fallback only  · B-77

- [ ] **Test**:

```python
def test_explicit_cohort_beats_the_note_derived_one(conn, tmp_path):
    """The note says 'guru channel' -- a prose rewrite must never be able to
    reclassify an entry that states its cohort (B-77)."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@c", "creator": "c", "cohort": "shorts-specialist",
                           "included": True, "note": "guru channel (manual-seed)"}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    assert db.get_handle_by_platform_and_handle(
        conn, "youtube", "@c")["cohort"] == "shorts-specialist"


def test_shipped_manifest_never_needs_the_derive_cohort_fallback():
    """derive_cohort defaults to 'general-interest', this repo's label for
    'out of scope'. Prove no shipped entry can fall into it by accident."""
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    for platform in mig.PLATFORMS:
        for entry in data[platform]:
            assert "cohort" in entry, f"{platform}/{entry['handle']} would be inferred"
```

- [ ] **Run** → first test fails (`guru`).
- [ ] **Implement** — in `_seed_entry`:

```python
    cohort = entry.get("cohort") or derive_cohort(entry.get("note", ""), handle)
```

Leave `derive_cohort` in place and add to its docstring: *"Legacy fallback only. Every shipped manifest entry
carries an explicit `cohort`; this exists so a hand-written third-party manifest without one still imports
(B-77)."*

- [ ] **Run** → pass. **Commit:** `fix(roster): make cohort an explicit manifest field, not prose inference`

---

### T6 — `included` is honored, and the out-of-scope entries ship excluded  · B-78

- [ ] **Test**:

```python
def test_included_false_entry_is_seeded_but_excluded(conn, tmp_path):
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@out", "creator": "c",
                           "cohort": "general-interest", "included": False}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    row = db.get_handle_by_platform_and_handle(conn, "youtube", "@out")
    assert row is not None, "an excluded creator is still declared, still visible"
    assert row["included"] == 0


def test_shipped_general_interest_entries_are_not_pulled_by_daily_runs(conn):
    """B-78: the manifest's own comment calls these out of scope, and the app
    used to pull them every day anyway."""
    mig.migrate(conn, SHIPPED_MANIFEST, now="2026-08-08T00:00:00+00:00")
    included = {(r["platform"], r["handle"]) for r in db.list_handles(conn, included_only=True)}
    assert ("youtube", "@bigthink") not in included
    assert ("bluesky", "adamgrant.bsky.social") not in included
    assert ("youtube", "@JennyHoyos") in included      # not a blanket exclusion
```

- [ ] **Run** → fails: `included == 1`.
- [ ] **Implement** — in `_seed_entry`, `included = bool(entry.get("included", True))`, threaded through the upsert.
- [ ] **Run** → pass. **Commit:** `fix(roster): honor the manifest's included flag and stop pulling out-of-scope sources`

---

### T7 — Seed as `pending`, never `validated`  · B-75 *(silent → all three tests)*

- [ ] **Test**:

```python
def test_seeded_handles_are_pending_not_validated(conn, tmp_path):
    """FAULT: 'validated' must be earned by a real fetch (discovery_engine.py:
    245-249). A JSON file is not evidence a channel still exists (B-75)."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@c", "creator": "c", "cohort": "guru", "included": True}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    row = db.get_handle_by_platform_and_handle(conn, "youtube", "@c")
    assert row["status"] == "pending"
    assert row["validated_at"] is None


def test_a_seeded_handle_is_distinguishable_from_a_fetch_validated_one(conn, tmp_path):
    """DISTINGUISHABILITY: before the fix both read `validated`, so the status
    column told the operator nothing."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@seeded", "creator": "c", "cohort": "guru", "included": True}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    seeded = db.get_handle_by_platform_and_handle(conn, "youtube", "@seeded")

    real_id = db.create_handle(conn, "youtube", "@fetched", "F", "guru", None,
                               "2026-08-08T00:00:00+00:00")
    db.set_handle_status(conn, real_id, "validated", validated_at="2026-08-08T00:01:00+00:00")
    fetched = db.get_handle(conn, real_id)

    assert seeded["status"] != fetched["status"]


def test_main_reports_seeded_handles_need_validation(conn, tmp_path, capsys):
    """SURFACING: the operator is told the roster is unverified."""
    rc = mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(tmp_path / "p.db")])
    assert rc == 0
    assert "pending validation" in capsys.readouterr().out
```

- [ ] **Run** → fails: `'validated' == 'pending'`.
- [ ] **Implement** — the upsert writes `status="pending"`; `main()` prints
  `f"  {result.seeded} handle(s) pending validation -- run a discovery validate pass to confirm each is live"`.
- [ ] **Run** → pass. **Commit:** `fix(roster): seed handles as pending; only a real fetch may write validated`

---

### T8 — Re-running applies manifest edits without stomping run-owned columns  · B-76 *(silent → all three tests)*

- [ ] **Test**:

```python
def test_rerun_applies_a_changed_display_name_and_keyword_filter(conn, tmp_path):
    """FAULT: INSERT OR IGNORE (db.py:186-189) meant the manifest stopped being
    the source of truth after the first run (B-76)."""
    base = {"creators": {"c": {"display_name": "C"}},
            **{p: [] for p in mig.PLATFORMS}, "rss": []}
    base["youtube"] = [{"handle": "@c", "creator": "c", "display_name": "Old",
                        "cohort": "guru", "included": True, "keyword_filter": None}]
    path = _write(tmp_path, base)
    mig.migrate(conn, path, now="2026-08-08T00:00:00+00:00")

    base["youtube"][0].update(display_name="New", keyword_filter="only this",
                              cohort="shorts-specialist", included=False)
    path.write_text(json.dumps(base), encoding="utf-8")
    result = mig.migrate(conn, path, now="2026-08-08T01:00:00+00:00")

    row = db.get_handle_by_platform_and_handle(conn, "youtube", "@c")
    assert row["display_name"] == "New"
    assert row["keyword_filter"] == "only this"
    assert row["cohort"] == "shorts-specialist"
    assert row["included"] == 0
    assert result.updated == 1 and result.seeded == 0


def test_rerun_preserves_run_owned_status_and_last_seen(conn, tmp_path):
    """DISTINGUISHABILITY: manifest-owned columns move, run-owned columns do
    not. A re-seed must not erase what a real fetch learned."""
    base = {"creators": {"c": {"display_name": "C"}},
            **{p: [] for p in mig.PLATFORMS}, "rss": []}
    base["youtube"] = [{"handle": "@c", "creator": "c", "display_name": "C",
                        "cohort": "guru", "included": True}]
    path = _write(tmp_path, base)
    mig.migrate(conn, path, now="2026-08-08T00:00:00+00:00")
    row_id = db.get_handle_by_platform_and_handle(conn, "youtube", "@c")["id"]
    db.set_handle_status(conn, row_id, "invalid", validated_at="2026-08-08T00:30:00+00:00")
    db.set_handle_last_seen(conn, row_id, "2026-08-07T00:00:00+00:00")

    base["youtube"][0]["display_name"] = "C2"
    path.write_text(json.dumps(base), encoding="utf-8")
    mig.migrate(conn, path, now="2026-08-08T01:00:00+00:00")

    row = db.get_handle(conn, row_id)
    assert row["display_name"] == "C2"                       # manifest-owned: moved
    assert row["status"] == "invalid"                        # run-owned: untouched
    assert row["validated_at"] == "2026-08-08T00:30:00+00:00"
    assert row["last_seen_published_at"] == "2026-08-07T00:00:00+00:00"


def test_main_prints_updated_separately_from_seeded(conn, tmp_path, capsys):
    """SURFACING: `migrated N handles` counted rows it did not write. The
    summary must distinguish inserted from updated from unchanged."""
    db_path = tmp_path / "p.db"
    mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(db_path)])
    capsys.readouterr()
    mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(db_path)])
    out = capsys.readouterr().out
    assert "inserted : 0" in out
    assert "updated  : 0" in out
```

- [ ] **Run** → fails: `display_name == "Old"`.
- [ ] **Implement** — a local upsert in the script (we may not edit `db.py`; `upsert_handle_from_migration` is
  P1's file and is still used by nothing else after this change):

```python
_MANIFEST_OWNED = ("display_name", "cohort", "keyword_filter", "included", "creator_id")


def upsert_handle(conn, platform, handle, *, display_name, cohort, keyword_filter,
                  included, creator_id, added_at) -> str:
    """Insert or update ONE handle. Returns 'inserted' | 'updated' | 'unchanged'.

    Only manifest-owned columns are written. status / validated_at /
    last_seen_published_at are owned by the discovery run and are never touched
    here -- a re-seed must not un-learn what a real fetch discovered (B-75/B-76).
    """
    before = db.get_handle_by_platform_and_handle(conn, platform, handle)
    conn.execute(
        "INSERT INTO handles (platform, handle, display_name, cohort, keyword_filter, "
        "                     included, status, added_at, creator_id) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?) "
        "ON CONFLICT(platform, handle) DO UPDATE SET "
        "  display_name = excluded.display_name, "
        "  cohort       = excluded.cohort, "
        "  keyword_filter = excluded.keyword_filter, "
        "  included     = excluded.included, "
        "  creator_id   = excluded.creator_id",
        (platform, handle, display_name, cohort, keyword_filter,
         1 if included else 0, added_at, creator_id),
    )
    conn.commit()
    after = db.get_handle_by_platform_and_handle(conn, platform, handle)
    if before is None:
        return "inserted"
    return "unchanged" if all(before[c] == after[c] for c in _MANIFEST_OWNED) else "updated"
```

`main()` prints:

```
roster sync: {manifest}  ->  {db_path}
  inserted : {result.seeded}
  updated  : {result.updated}
  skipped  : {result.skipped}
  drift    : {len(result.drift)}
```

Update the module docstring: the script is no longer "one-off" and no longer "never overwrites"; it is
`roster sync`, the manifest is authoritative for manifest-owned columns, and the DB is authoritative for
run-owned ones.

- [ ] **Run** → pass. **Commit:** `fix(roster): make manifest edits propagate on re-run without stomping run state`

---

### T9 — DB rows absent from the manifest are reported as drift  · B-76 *(surfacing)*

- [ ] **Test**:

```python
def test_a_db_handle_missing_from_the_manifest_is_reported_as_drift(conn, tmp_path, capsys):
    db.create_handle(conn, "instagram", "@ghost", "Ghost", "guru", None,
                     "2026-08-01T00:00:00+00:00")
    payload = {"creators": {}, **{p: [] for p in mig.PLATFORMS}, "rss": []}
    result = mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")

    assert ("instagram", "@ghost") in result.drift
    assert db.get_handle_by_platform_and_handle(conn, "instagram", "@ghost") is not None, \
        "drift is reported, never auto-deleted -- deletion is the operator's call"


def test_drift_records_a_warning_event(tmp_path):
    db_path = tmp_path / "p.db"
    db.init_db(db_path, Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql")
    conn = db.get_connection(db_path)
    db.create_handle(conn, "instagram", "@ghost", "Ghost", "guru", None,
                     "2026-08-01T00:00:00+00:00")
    conn.close()

    rc = mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(db_path)])
    assert rc == 0                                  # drift is a warning, not a failure

    conn = db.get_connection(db_path)
    rows = conn.execute("SELECT * FROM events WHERE kind = 'roster.drift'").fetchall()
    conn.close()
    assert len(rows) == 1 and rows[0]["severity"] == "warning"
    assert "@ghost" in rows[0]["message"]
```

- [ ] **Run** → fails: `result.drift` is empty.
- [ ] **Implement**:

```python
def find_drift(conn, data: dict) -> list[tuple[str, str]]:
    """(platform, handle) rows in the DB that the manifest does not declare.

    Reported, never deleted: a hand-added handle is a legitimate way to work,
    and the point is that the divergence stops being invisible (B-76).
    """
    declared = {(p, e["handle"]) for p in PLATFORMS for e in data[p] if e.get("handle")}
    return sorted(
        (row["platform"], row["handle"])
        for row in db.list_handles(conn)
        if (row["platform"], row["handle"]) not in declared
    )
```

In `main()`, when `result.drift` is non-empty: print each pair, `obs.log("roster.drift", level="warning", ...)`,
and one `obs.record_event(..., kind="roster.drift", severity="warning", ...)` naming them.

- [ ] **Run** → pass. **Commit:** `feat(roster): report DB handles the manifest does not declare as drift`

---

### T10 — Populate `creators` and `handles.creator_id`  · mechanism for B-70/B-72

- [ ] **Test**:

```python
def test_handles_of_one_creator_share_a_creator_id(conn, tmp_path):
    """The join key that makes 'does this creator have a platform we are not
    tracking?' computable. Adam Grant is on two platforms, unlinked before."""
    payload = {"creators": {"adam-grant": {"display_name": "Adam Grant"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@bigthink", "creator": "adam-grant",
                           "cohort": "general-interest", "included": False}]
    payload["bluesky"] = [{"handle": "adamgrant.bsky.social", "creator": "adam-grant",
                           "cohort": "general-interest", "included": False}]
    mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")

    yt = db.get_handle_by_platform_and_handle(conn, "youtube", "@bigthink")
    bs = db.get_handle_by_platform_and_handle(conn, "bluesky", "adamgrant.bsky.social")
    assert yt["creator_id"] is not None
    assert yt["creator_id"] == bs["creator_id"]
    row = conn.execute("SELECT * FROM creators WHERE id = ?", (yt["creator_id"],)).fetchone()
    assert row["slug"] == "adam-grant" and row["display_name"] == "Adam Grant"


def test_an_entry_naming_an_undeclared_creator_is_a_manifest_error(conn, tmp_path):
    payload = {"creators": {}, **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@x", "creator": "nobody",
                           "cohort": "guru", "included": True}]
    with pytest.raises(mig.ManifestError) as excinfo:
        mig.migrate(conn, _write(tmp_path, payload), now="2026-08-08T00:00:00+00:00")
    assert "nobody" in str(excinfo.value)
```

- [ ] **Run** → fails: no `upsert_creators`.
- [ ] **Implement**:

```python
def upsert_creators(conn, creators: dict) -> dict[str, int]:
    """slug -> creators.id, inserting or updating each declared creator."""
    ids: dict[str, int] = {}
    for slug, spec in creators.items():
        display_name = (spec or {}).get("display_name") or slug
        conn.execute(
            "INSERT INTO creators (slug, display_name) VALUES (?, ?) "
            "ON CONFLICT(slug) DO UPDATE SET display_name = excluded.display_name",
            (slug, display_name),
        )
        ids[slug] = conn.execute(
            "SELECT id FROM creators WHERE slug = ?", (slug,)).fetchone()["id"]
    conn.commit()
    return ids
```

In `_seed_entry`, before the collision guard:

```python
    slug = entry.get("creator")
    if slug not in creator_ids:
        raise ManifestError(
            f"{platform}/{entry.get('handle')} names creator {slug!r}, which is not "
            f"in the manifest's `creators` block. Every handle must belong to a "
            f"declared creator -- that slug is the only cross-platform identity."
        )
```

- [ ] **Run** → pass. **Commit:** `feat(roster): populate creators and handles.creator_id from the manifest`

---

### T11 — `--report`: the creator × platform coverage matrix, with zero `UNANSWERABLE` cells  · B-70, B-81

This is the permanent answer to the operator's question.

- [ ] **Test**:

```python
def test_coverage_report_cell_states_are_exhaustive(tmp_path):
    """A cell is one of exactly three states. UNANSWERABLE means 'the manifest
    has no key for this platform, so we cannot say' -- 74 of 90 cells were in
    that state before this package (B-70)."""
    payload = {"creators": {"c": {"display_name": "C"}},
               **{p: [] for p in mig.PLATFORMS}, "rss": []}
    payload["youtube"] = [{"handle": "@c", "creator": "c", "cohort": "guru", "included": True}]
    payload["x"] = [{"handle": "@c_x", "creator": "c", "cohort": "guru", "included": False}]
    del payload["facebook"]                                   # simulate the old manifest

    report = mig.build_coverage_report(
        json.loads(_write(tmp_path, payload).read_text(encoding="utf-8")))

    assert report.cell("c", "youtube").state == "tracked"
    assert report.cell("c", "x").state == "declared-excluded"
    assert report.cell("c", "instagram").state == "not tracked"
    assert report.cell("c", "facebook").state == "UNANSWERABLE"


def test_shipped_manifest_has_zero_unanswerable_cells():
    """THE coverage test. 'Are we tracking all social platforms for our key
    creators?' is answerable from the repo for every creator and every
    platform, or this fails (B-70, B-81)."""
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    report = mig.build_coverage_report(data)

    # Anti-tautology: a report over zero creators or zero platforms would also
    # have zero UNANSWERABLE cells. Pin the shape first.
    assert sorted(report.platforms) == sorted(mig.PLATFORMS)
    assert len(report.creators) == 15
    assert len(report.cells) == 15 * len(mig.PLATFORMS) == 105

    unanswerable = [(c, p) for (c, p), cell in report.cells.items()
                    if cell.state == "UNANSWERABLE"]
    assert unanswerable == [], (
        f"{len(unanswerable)} creator x platform cells cannot be answered from "
        f"the repo: {unanswerable[:10]}")


def test_report_mode_prints_the_matrix_and_exits_zero(tmp_path, capsys):
    rc = mig.main(["--manifest", str(SHIPPED_MANIFEST),
                   "--db-path", str(tmp_path / "p.db"), "--report"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "UNANSWERABLE : 0" in out
    assert "adam-grant" in out
    assert "linkedin-profile" in out


def test_report_mode_writes_nothing_to_the_database(tmp_path):
    """--report is read-only: an operator answering a coverage question must
    not accidentally re-seed the roster."""
    db_path = tmp_path / "p.db"
    mig.main(["--manifest", str(SHIPPED_MANIFEST), "--db-path", str(db_path), "--report"])
    conn = db.get_connection(db_path)
    assert db.list_handles(conn) == []
    conn.close()
```

- [ ] **Run** → fails: no `build_coverage_report`.
- [ ] **Implement**:

```python
@dataclass(frozen=True)
class Cell:
    state: str                     # tracked | declared-excluded | not tracked | UNANSWERABLE
    handle: str | None = None


@dataclass
class CoverageReport:
    creators: dict[str, str]                    # slug -> display_name
    platforms: tuple[str, ...]
    cells: dict[tuple[str, str], Cell]

    def cell(self, creator: str, platform: str) -> Cell:
        return self.cells[(creator, platform)]

    def count(self, state: str) -> int:
        return sum(1 for c in self.cells.values() if c.state == state)


def build_coverage_report(data: dict) -> CoverageReport:
    """The creator x platform matrix, computed from the manifest ALONE.

    Deliberately does not read the database: the operator's question has to be
    answerable from a fresh checkout, in a diff, on another machine. A cell is
    UNANSWERABLE only when the manifest carries no key for that platform at
    all -- which is exactly the B-70 state this package eliminates.
    """
    creators = {slug: (spec or {}).get("display_name") or slug
                for slug, spec in (data.get("creators") or {}).items()}
    declared: dict[tuple[str, str], dict] = {}
    for platform in PLATFORMS:
        for entry in data.get(platform) or []:
            if entry.get("creator") and entry.get("handle"):
                declared[(entry["creator"], platform)] = entry

    cells: dict[tuple[str, str], Cell] = {}
    for slug in creators:
        for platform in PLATFORMS:
            if platform not in data:
                cells[(slug, platform)] = Cell("UNANSWERABLE")
                continue
            entry = declared.get((slug, platform))
            if entry is None:
                cells[(slug, platform)] = Cell("not tracked")
            elif entry.get("included", True):
                cells[(slug, platform)] = Cell("tracked", entry["handle"])
            else:
                cells[(slug, platform)] = Cell("declared-excluded", entry["handle"])
    return CoverageReport(creators, PLATFORMS, cells)


_GLYPH = {"tracked": "YES", "declared-excluded": "off", "not tracked": "-",
          "UNANSWERABLE": "??"}


def print_coverage_report(report: CoverageReport) -> None:
    width = max((len(s) for s in report.creators), default=7) + 2
    print("creator x platform coverage (from the manifest alone)\n")
    print(" " * width + "  ".join(f"{p:<17}" for p in report.platforms))
    for slug in sorted(report.creators):
        row = "  ".join(f"{_GLYPH[report.cell(slug, p).state]:<17}" for p in report.platforms)
        print(f"{slug:<{width}}{row}")
    print("\n  YES tracked          :", report.count("tracked"))
    print("  off declared-excluded:", report.count("declared-excluded"))
    print("  -   not tracked      :", report.count("not tracked"))
    print("  ??  UNANSWERABLE     :", report.count("UNANSWERABLE"))
    print("\n  `rss` is intentionally not a column: it has a manifest key and a")
    print("  download_brandintel.py branch, but no adapter, so it is not part of")
    print("  the daily discovery path.")
```

`main()` gains `--report` and, when set, validates keys, prints the matrix, and returns **before** opening any
write path (a `ManifestError` here still returns 2 via the same handler).

- [ ] **Run** → pass. **Commit:** `feat(roster): add a creator x platform coverage report with no unanswerable cells`

---

### T12 — Shipped-manifest integrity, and the misleading test name  · B-81

- [ ] **Test**:

```python
def test_shipped_manifest_has_no_slug_collisions():
    """handle_slug is lossy (periods stripped, lowercased). Two colliding
    handles on one platform get billed twice into one directory."""
    from pipeline_app.discovery_paths import handle_slug
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    for platform in mig.PLATFORMS:
        slugs = [handle_slug(e["handle"]) for e in data[platform]]
        assert len(slugs) == len(set(slugs)), f"slug collision on {platform}: {slugs}"


def test_shipped_manifest_seeds_every_declared_handle(conn):
    """Replaces test_migrate_seeds_all_16_handles_as_validated, whose name
    promised a coverage guarantee over three synthetic entries (B-81)."""
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    expected = sum(len(data[p]) for p in mig.PLATFORMS)
    result = mig.migrate(conn, SHIPPED_MANIFEST, now="2026-08-08T00:00:00+00:00")
    assert expected == 16
    assert result.seeded == expected
    assert result.skipped == 0 and result.errors == []
    assert len(db.list_handles(conn)) == expected
```

- [ ] **Run** → the collision test should pass immediately; the seeding test fails until T4's file is in place
  (it is, so this task is mostly test-only — if `test_shipped_manifest_seeds_every_declared_handle` passes on the
  first run, note it and move on; its value is as a regression lock on the shipped file).
- [ ] **Implement** — delete `test_migrate_seeds_all_16_handles_as_validated`
  (`pipeline-app/tests/test_migrate_handles.py:34-56`) and `test_migrate_is_idempotent` (`:110-121`); their
  replacements are T7's, T8's and this task's tests. See §6.
- [ ] **Run** → pass. **Commit:** `test(roster): exercise the shipped manifest and drop the misnamed coverage test`

---

### T13 — Manifest `_comment` truth: rss scope and the skill count  · B-79, B-85

- [ ] **Test**:

```python
def test_manifest_comments_do_not_misdescribe_the_discovery_path():
    """B-79: the rss comment told the operator that adding a feed URL would
    include it. True for download_brandintel.py, false for the app.
    B-85: the top comment claimed 'six skills'; the repo ships eight."""
    data = json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8"))
    top = data["_comment"]
    assert "six skills" not in top
    assert "CLAUDE.md" in top                      # points at the live skill table instead
    assert "migrate_handles_from_manifest.py" in top

    rss_comment = data["rss"][0]["_comment"]
    assert "download_brandintel.py" in rss_comment
    assert "daily discovery run" in rss_comment


def test_rss_is_not_a_coverage_report_platform():
    assert "rss" not in mig.PLATFORMS
    assert "rss" in mig.DOWNLOADER_ONLY_KEYS
    report = mig.build_coverage_report(
        json.loads(SHIPPED_MANIFEST.read_text(encoding="utf-8")))
    assert "rss" not in report.platforms
```

- [ ] **Run** → fails on `"six skills" not in top` and the rss assertions.
- [ ] **Implement** — the `_comment` values are already written verbatim in §3.3. Apply them.
- [ ] **Run** → pass. **Commit:** `docs(roster): correct the manifest's rss scope claim and stale skill count`

---

### T14 — **S0** · The backfill refuses to enrich without a working API key  · D-04 *(fault)*

> This is the highest-priority task in the package. `--apply` with no key currently rewrites 420 corpus files
> with null metadata, relabels `metadata_source`, and returns 0 — against a git-ignored tree with no recovery
> path.

- [ ] **Test**:

```python
def test_apply_without_an_api_key_refuses_to_run(tmp_path, monkeypatch, capsys):
    """FAULT: D-04. fetch_metadata returns {} for a missing key, an exhausted
    quota and a dead network alike; the script then wrote nulls over
    everything and exited 0."""
    monkeypatch.setattr(backfill.youtube_api, "api_key", lambda: None)
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    before = path.read_text(encoding="utf-8")

    rc = backfill.main(["--corpus-root", str(tmp_path), "--apply"])

    assert rc == 2
    assert path.read_text(encoding="utf-8") == before, "not one byte may be written"
    err = capsys.readouterr().err
    assert "YOUTUBE_API_KEY" in err and "--no-api" in err


def test_no_api_is_the_explicit_escape_hatch(tmp_path, monkeypatch):
    """The refusal is not a wall: --no-api is the deliberate way through, and
    it must never claim API provenance."""
    monkeypatch.setattr(backfill.youtube_api, "api_key", lambda: None)
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    assert backfill.main(["--corpus-root", str(tmp_path), "--no-api", "--apply"]) == 0
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["metadata_source"] == "yt-dlp"
```

- [ ] **Run** → fails: `rc == 0` and the file was rewritten.
- [ ] **Implement** — first thing in `main()`, before `args.corpus_root.exists()` and before `collect()`:

```python
    if not args.no_api and youtube_api.api_key() is None:
        obs.log("backfill.preflight_failed", level="error", reason="no_api_key")
        print(
            "! refusing to run: Data API enrichment was requested but no key is "
            f"configured ({youtube_api.KEY_ENV_VAR} env var or "
            f"{youtube_api.KEY_FILE.name}).\n"
            "  Without a key every record would be rewritten with null view/like/"
            "comment counts and a downgraded metadata_source, over a git-ignored "
            "corpus with no recovery path.\n"
            "  Set the key, or pass --no-api to reformat on-disk data only.",
            file=sys.stderr,
        )
        return 2
```

Add `from pipeline_app import obs  # noqa: E402` to the imports.

- [ ] **Run** → pass. **Commit:** `fix(backfill): refuse to run without a Data API key instead of nulling the corpus`

---

### T15 — **S0** · A total enrichment miss aborts before any write  · D-04 *(distinguishability)*

A key can be present and still yield nothing: exhausted quota, network down, revoked key. The preflight cannot
see that; only the result can.

- [ ] **Test**:

```python
def test_total_enrichment_miss_aborts_before_writing_anything(tmp_path, monkeypatch, capsys):
    """DISTINGUISHABILITY: 'the API returned nothing for all 420 ids' must be
    observably different from 'the API had nothing to add'. Before the fix both
    printed `got metadata for 0/N` and rewrote everything (D-04)."""
    monkeypatch.setattr(backfill.youtube_api, "api_key", lambda: "k")
    monkeypatch.setattr(backfill.youtube_api, "fetch_metadata", lambda ids, **kw: {})
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    before = path.read_text(encoding="utf-8")

    rc = backfill.main(["--corpus-root", str(tmp_path), "--apply"])

    assert rc == 2
    assert path.read_text(encoding="utf-8") == before
    assert "0 of 1" in capsys.readouterr().err


def test_partial_enrichment_is_not_treated_as_a_total_miss(tmp_path, monkeypatch):
    """The counterpart: a genuinely partial result (deleted/private videos) is
    normal and must still write. Same shape, different outcome."""
    monkeypatch.setattr(backfill.youtube_api, "api_key", lambda: "k")
    monkeypatch.setattr(backfill.youtube_api, "fetch_metadata",
                        lambda ids, **kw: {"0l2g3Bujy1Y": {"view_count": 7}})
    good = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    _corpus(tmp_path, "blocked1__y.md", OLD_FORMAT_NO_TRANSCRIPT)

    rc = backfill.main(["--corpus-root", str(tmp_path), "--apply"])

    assert rc == 3                                   # partial: written, but not clean
    meta, _ = artifacts.parse_frontmatter(good.read_text(encoding="utf-8"))
    assert meta["view_count"] == 7
```

- [ ] **Run** → fails: `rc == 0`, files rewritten.
- [ ] **Implement** — after the `fetch_metadata` call, before the write loop:

```python
        api_records = youtube_api.fetch_metadata(ids)
        unique = len(set(ids))
        print(f"  got metadata for {len(api_records)}/{unique}")
        if unique and not api_records:
            obs.log("backfill.enrichment_total_miss", level="error", requested=unique)
            print(
                f"! refusing to write: Data API enrichment returned 0 of {unique} "
                "records. A key is configured, so this is an exhausted quota, a "
                "revoked key, or a network failure -- not an empty result.\n"
                "  Nothing has been written. Re-run when the API is reachable, or "
                "pass --no-api to reformat on-disk data only.",
                file=sys.stderr,
            )
            return 2
```

- [ ] **Run** → pass. **Commit:** `fix(backfill): abort before writing when enrichment returns nothing at all`

---

### T16 — **S0** · Never downgrade provenance, never null an existing value  · D-04

Even a partial run must not degrade the files it touches without enrichment.

- [ ] **Test**:

```python
ALREADY_ENRICHED = """---
video_id: enriched1
url: https://www.youtube.com/watch?v=enriched1
handle: '@nicknimmin'
channel: Nick Nimmin
upload_date: '2025-08-16'
duration_s: 441
view_count: 24013
like_count: 1184
comment_count: 97
manual_captions: true
transcript_status: present
transcript_source: yt-dlp
metadata_source: youtube-data-api-v3
fetched_at: '2026-07-23T17:58:26+00:00'
---

# Already Enriched

## description

d

## transcript

t
"""


def test_build_meta_never_downgrades_metadata_source(tmp_path):
    """D-04: the record must never end up ASSERTING a weaker provenance than
    the data it replaced."""
    rec = backfill.parse_existing(_corpus(tmp_path, "enriched1__x.md", ALREADY_ENRICHED))
    meta = backfill.build_meta(rec, None)
    assert meta["metadata_source"] == "youtube-data-api-v3"


def test_build_meta_never_nulls_an_existing_count(tmp_path):
    rec = backfill.parse_existing(_corpus(tmp_path, "enriched1__x.md", ALREADY_ENRICHED))
    meta = backfill.build_meta(rec, None)
    assert meta["view_count"] == 24013
    assert meta["like_count"] == 1184
    assert meta["comment_count"] == 97
    assert meta["manual_captions"] is True


def test_a_fresh_api_record_still_wins_over_stale_stored_counts(tmp_path):
    """Preserve-on-absent must not become never-update."""
    rec = backfill.parse_existing(_corpus(tmp_path, "enriched1__x.md", ALREADY_ENRICHED))
    meta = backfill.build_meta(rec, {"view_count": 99999, "manual_captions": False})
    assert meta["view_count"] == 99999
    assert meta["manual_captions"] is False
```

- [ ] **Run** → fails: `metadata_source == 'yt-dlp'`, `view_count is None`.
- [ ] **Implement** — carry the existing values through `parse_existing`:

```python
        "metadata_source": meta.get("metadata_source") or "",
        "view_count": meta.get("view_count"),
        "like_count": meta.get("like_count"),
        "comment_count": meta.get("comment_count"),
        "manual_captions": meta.get("manual_captions"),
```

and in `build_meta`, replace the four bare `api_record.get(...)` lines and the `metadata_source` expression:

```python
_SOURCE_RANK = {"": 0, "none": 0, "yt-dlp": 1, "youtube-data-api-v3": 2}


def _keep(api_value, existing_value):
    """API wins when it says anything; otherwise keep what the file already
    held. Never replace a real value with None (D-04)."""
    return existing_value if api_value is None else api_value


# ... inside build_meta:
    derived_source = "youtube-data-api-v3" if api_record else (
        "yt-dlp" if existing["upload_date"] else "none")
    existing_source = existing["metadata_source"]
    metadata_source = max(
        (derived_source, existing_source),
        key=lambda s: _SOURCE_RANK.get(s, 0),
    )

    return {
        ...
        "view_count": _keep(api_record.get("view_count"), existing["view_count"]),
        "like_count": _keep(api_record.get("like_count"), existing["like_count"]),
        "comment_count": _keep(api_record.get("comment_count"), existing["comment_count"]),
        "manual_captions": _keep(api_record.get("manual_captions"), existing["manual_captions"]),
        ...
        "metadata_source": metadata_source,
    }
```

- [ ] **Run** → pass. Also re-run the whole file: `test_build_meta_without_api_keeps_ytdlp_provenance`
  (`:112-117`) must still pass unchanged — the old-format record has no stored `metadata_source`, so `yt-dlp`
  still wins.
- [ ] **Commit:** `fix(backfill): never downgrade metadata_source or null an existing count`

---

### T17 — **S0** · Per-file failures are counted and reflected in the exit code  · D-04 *(surfacing)*

- [ ] **Test**:

```python
def test_a_file_that_fails_to_write_does_not_abort_the_rest_and_sets_the_exit_code(
        tmp_path, monkeypatch, capsys):
    """SURFACING: a crash at file 300 of 420 left the corpus half-converted
    with nothing indicating where it stopped, and the script returned 0."""
    good = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    _corpus(tmp_path, "blocked1__y.md", OLD_FORMAT_NO_TRANSCRIPT)

    real_render = backfill.render

    def exploding_render(existing, meta):
        if existing["video_id"] == "blocked1":
            raise OSError("disk full")
        return real_render(existing, meta)

    monkeypatch.setattr(backfill, "render", exploding_render)
    rc = backfill.main(["--corpus-root", str(tmp_path), "--no-api", "--apply"])

    assert rc == 3
    out, err = capsys.readouterr().out, capsys.readouterr().err
    assert "failed" in out
    meta, _ = artifacts.parse_frontmatter(good.read_text(encoding="utf-8"))
    assert meta["transcript_status"] == "present", "the healthy file still converted"


def test_a_clean_apply_run_exits_zero(tmp_path):
    _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    assert backfill.main(["--corpus-root", str(tmp_path), "--no-api", "--apply"]) == 0


def test_dry_run_remains_the_default_with_no_flags(tmp_path, capsys):
    """The safety property D-04 depends on. Locked so no future flag reorder
    can make --apply implicit."""
    path = _corpus(tmp_path, "0l2g3Bujy1Y__x.md", OLD_FORMAT)
    before = path.read_text(encoding="utf-8")
    assert backfill.main(["--corpus-root", str(tmp_path), "--no-api"]) == 0
    assert path.read_text(encoding="utf-8") == before
    assert "Dry run" in capsys.readouterr().out
```

- [ ] **Run** → fails: `rc == 0` and the `OSError` escapes.
- [ ] **Implement** — wrap the per-file write, count failures, and pick the exit code:

```python
    failed: list[tuple[Path, str]] = []
    ...
        if args.apply:
            path = existing["path"]
            tmp = path.with_name(path.name + ".tmp")
            try:
                tmp.write_text(render(existing, meta), encoding="utf-8")
                tmp.replace(path)
            except Exception as exc:  # noqa: BLE001 -- one bad file must not
                # abandon the corpus half-converted; the counter and the exit
                # code are what make the partial state visible (D-04).
                failed.append((path, f"{type(exc).__name__}: {exc}"))
                tmp.unlink(missing_ok=True)
                obs.log("backfill.file_write_failed", level="error",
                        path=str(path), error=str(exc))
                print(f"  !! {path.name}: {exc}", file=sys.stderr)
    ...
    print(f"  failed to write        : {len(failed)}")
    if failed:
        for path, why in failed:
            print(f"    - {path}: {why}")
    enrichment_incomplete = (not args.no_api) and enriched < len(files)
    if failed or enrichment_incomplete or unparsed_skipped:      # unparsed: T18
        return 3
    return 0
```

- [ ] **Run** → pass. **Commit:** `fix(backfill): count per-file write failures and exit non-zero on a partial run`

---

### T18 — Unparsed metadata is counted, skipped, and marked inferred  · D-05 *(silent → all three tests)*

- [ ] **Test**:

```python
UNPARSEABLE = """# Hand Edited Record

## metadata

video_id = abc999
channel = Somebody

## description

d

## transcript

t
"""


def test_a_file_whose_metadata_did_not_parse_is_flagged(tmp_path):
    """FAULT: parse_existing silently reconstructed video_id from the filename
    and handle from the directory, with no indication (D-05)."""
    rec = backfill.parse_existing(_corpus(tmp_path, "abc999__hand-edited.md", UNPARSEABLE))
    assert rec["meta_parsed"] is False
    assert set(rec["inferred_fields"]) >= {"video_id", "handle"}


def test_an_inferred_record_is_distinguishable_from_a_read_one(tmp_path):
    """DISTINGUISHABILITY: both used to produce identical-looking frontmatter."""
    inferred = backfill.parse_existing(_corpus(tmp_path, "abc999__a.md", UNPARSEABLE))
    read = backfill.parse_existing(_corpus(tmp_path, "0l2g3Bujy1Y__b.md", OLD_FORMAT))
    assert inferred["meta_parsed"] != read["meta_parsed"]
    assert backfill.build_meta(inferred, None).get("metadata_inferred")
    assert "metadata_inferred" not in backfill.build_meta(read, None)


def test_unparsed_files_are_skipped_by_default_and_reported(tmp_path, capsys):
    """SURFACING: non-zero exit + a named count, and the file is untouched."""
    path = _corpus(tmp_path, "abc999__a.md", UNPARSEABLE)
    _corpus(tmp_path, "0l2g3Bujy1Y__b.md", OLD_FORMAT)
    before = path.read_text(encoding="utf-8")

    rc = backfill.main(["--corpus-root", str(tmp_path), "--no-api", "--apply"])

    assert rc == 3
    assert path.read_text(encoding="utf-8") == before
    assert "metadata did not parse : 1" in capsys.readouterr().out


def test_rewrite_unparsed_opts_in_and_records_the_inference(tmp_path):
    path = _corpus(tmp_path, "abc999__a.md", UNPARSEABLE)
    rc = backfill.main(["--corpus-root", str(tmp_path), "--no-api", "--apply",
                        "--rewrite-unparsed"])
    assert rc == 0
    meta, _ = artifacts.parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["video_id"] == "abc999"
    assert set(meta["metadata_inferred"]) >= {"video_id", "handle"}
```

- [ ] **Run** → fails: `KeyError: 'meta_parsed'`.
- [ ] **Implement** — in `parse_existing`, track what was read versus reconstructed:

```python
    if not meta:
        meta = {k: v.strip() for k, v in _OLD_META_RE.findall(sections.get("metadata", ""))}
    meta_parsed = bool(meta)

    inferred: list[str] = []
    video_id = meta.get("video_id")
    if not video_id:
        video_id = path.name.split("__", 1)[0]
        inferred.append("video_id")
    handle = meta.get("handle")
    if not handle:
        handle = f"@{path.parent.name}"
        inferred.append("handle")
    for field_name in ("channel", "upload_date", "fetched_at"):
        if not meta.get(field_name):
            inferred.append(field_name)

    return {
        ...
        "meta_parsed": meta_parsed,
        "inferred_fields": inferred,
    }
```

In `build_meta`, add `metadata_inferred` **only** when the field list is non-empty and the metadata block did not
parse — a plain old-format file with an empty `upload_date` is a read absence, not an inference:

```python
    if not existing["meta_parsed"] and existing["inferred_fields"]:
        out["metadata_inferred"] = sorted(existing["inferred_fields"])
```

In `main()`, add `--rewrite-unparsed` and skip those files unless it is set:

```python
    ap.add_argument("--rewrite-unparsed", action="store_true",
                    help="also rewrite files whose metadata block did not parse; "
                         "their inferred fields are recorded in metadata_inferred")
    ...
    unparsed = [f for f in files if not f["meta_parsed"]]
    unparsed_skipped = 0 if args.rewrite_unparsed else len(unparsed)
    ...
        if not existing["meta_parsed"] and not args.rewrite_unparsed:
            continue                        # counted below, never written
    ...
    print(f"  metadata did not parse : {len(unparsed)}"
          + ("" if args.rewrite_unparsed else "  (skipped; pass --rewrite-unparsed to convert)"))
```

- [ ] **Run** → pass. **Commit:** `fix(backfill): flag and skip records whose metadata block did not parse`

---

### T19 — Whole-package verification

- [ ] Run both suites and confirm green:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app" && python -m pytest -q
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767" && python -m pytest tests/ -q
```

- [ ] Run the coverage report by hand and paste the matrix into the commit body — it is the artifact the operator
  asked for:

```bash
cd "C:/Projects/ContentStudio/.claude/worktrees/pipeline-audit-review-4dd767/pipeline-app"
python scripts/migrate_handles_from_manifest.py --report
```

Expect `??  UNANSWERABLE     : 0`.

- [ ] Confirm the corpus downloader still reads the manifest (the `15 1 0` check from T4).
- [ ] **Commit:** `test(roster): verify both suites and the zero-unanswerable coverage report`

---

## 5. Finding → test map

Every finding, the named test that proves it closed, and its Three-Test-Rule role where the finding is `silent`.

| Finding | Mode | Test (file · name) | Role |
|---|---|---|---|
| **B-70** | coverage-gap | `test_migrate_handles.py · test_platforms_tuple_matches_the_adapter_registry` | — |
| | | `test_migrate_handles.py · test_every_platform_key_is_seeded_not_just_youtube_and_bluesky` | — |
| | | `test_migrate_handles.py · test_shipped_manifest_has_zero_unanswerable_cells` | **the coverage answer** |
| **B-71** | **silent** | `test_migrate_handles.py · test_unknown_platform_key_raises_manifest_error` | fault |
| | | `test_migrate_handles.py · test_unknown_key_is_distinguishable_from_an_empty_manifest` | distinguishability |
| | | `test_migrate_handles.py · test_main_exits_nonzero_and_records_an_event_for_an_unknown_key` | surfacing |
| **B-75** | **silent** | `test_migrate_handles.py · test_seeded_handles_are_pending_not_validated` | fault |
| | | `test_migrate_handles.py · test_a_seeded_handle_is_distinguishable_from_a_fetch_validated_one` | distinguishability |
| | | `test_migrate_handles.py · test_main_reports_seeded_handles_need_validation` | surfacing |
| **B-76** | **silent** | `test_migrate_handles.py · test_rerun_applies_a_changed_display_name_and_keyword_filter` | fault |
| | | `test_migrate_handles.py · test_rerun_preserves_run_owned_status_and_last_seen` | distinguishability |
| | | `test_migrate_handles.py · test_main_prints_updated_separately_from_seeded` | surfacing |
| | | `test_migrate_handles.py · test_a_db_handle_missing_from_the_manifest_is_reported_as_drift` | fault (drift half) |
| | | `test_migrate_handles.py · test_drift_records_a_warning_event` | surfacing (drift half) |
| **B-77** | latent | `test_migrate_handles.py · test_explicit_cohort_beats_the_note_derived_one` | — |
| | | `test_migrate_handles.py · test_shipped_manifest_never_needs_the_derive_cohort_fallback` | — |
| **B-78** | coverage-gap | `test_migrate_handles.py · test_included_false_entry_is_seeded_but_excluded` | — |
| | | `test_migrate_handles.py · test_shipped_general_interest_entries_are_not_pulled_by_daily_runs` | — |
| **B-79** | **silent** | `test_migrate_handles.py · test_manifest_comments_do_not_misdescribe_the_discovery_path` | fault (the false claim is the defect) |
| | | `test_migrate_handles.py · test_rss_is_not_a_coverage_report_platform` | distinguishability (rss ≠ a tracked platform) |
| | | `test_migrate_handles.py · test_report_mode_prints_the_matrix_and_exits_zero` | surfacing (report states rss is out of path) |
| **B-81** | latent | `test_migrate_handles.py · test_shipped_manifest_declares_every_platform_and_resolves_every_creator` | — |
| | | `test_migrate_handles.py · test_shipped_manifest_has_no_slug_collisions` | — |
| | | `test_migrate_handles.py · test_shipped_manifest_seeds_every_declared_handle` | — |
| **B-85** | docs-drift | `test_migrate_handles.py · test_manifest_comments_do_not_misdescribe_the_discovery_path` | — |
| **D-04** | **silent · S0** | `test_backfill_youtube_frontmatter.py · test_apply_without_an_api_key_refuses_to_run` | fault |
| | | `test_backfill_youtube_frontmatter.py · test_total_enrichment_miss_aborts_before_writing_anything` | fault |
| | | `test_backfill_youtube_frontmatter.py · test_partial_enrichment_is_not_treated_as_a_total_miss` | distinguishability |
| | | `test_backfill_youtube_frontmatter.py · test_build_meta_never_downgrades_metadata_source` | distinguishability |
| | | `test_backfill_youtube_frontmatter.py · test_build_meta_never_nulls_an_existing_count` | distinguishability |
| | | `test_backfill_youtube_frontmatter.py · test_a_file_that_fails_to_write_does_not_abort_the_rest_and_sets_the_exit_code` | surfacing |
| | | `test_backfill_youtube_frontmatter.py · test_dry_run_remains_the_default_with_no_flags` | surfacing (safety lock) |
| **D-05** | **silent** | `test_backfill_youtube_frontmatter.py · test_a_file_whose_metadata_did_not_parse_is_flagged` | fault |
| | | `test_backfill_youtube_frontmatter.py · test_an_inferred_record_is_distinguishable_from_a_read_one` | distinguishability |
| | | `test_backfill_youtube_frontmatter.py · test_unparsed_files_are_skipped_by_default_and_reported` | surfacing |

**Adversarial parse coverage (the C-70 rule).** `parse_existing` and `validate_keys` are both text→structure
layers. `test_a_file_whose_metadata_did_not_parse_is_flagged` and
`test_unknown_platform_key_raises_manifest_error` are their adversarial tests: malformed input is *rejected*, not
silently skipped.

---

## 6. Tests deleted or inverted

| File · line | Test | Action | Why | Replacement |
|---|---|---|---|---|
| `pipeline-app/tests/test_migrate_handles.py:34-56` | `test_migrate_seeds_all_16_handles_as_validated` | **deleted** (name + body both wrong) | Two defects in one test. Its name promises a 16-handle coverage guarantee over **three synthetic entries** asserting `count == 3` (B-81). Its body asserts `status == "validated"`, freezing B-75 — a test named for a coverage guarantee that instead affirms the defective status. | T12 `test_shipped_manifest_seeds_every_declared_handle` (real file, real count) + T7 `test_seeded_handles_are_pending_not_validated` (inverted status assertion) |
| `pipeline-app/tests/test_migrate_handles.py:110-121` | `test_migrate_is_idempotent` | **inverted** | Asserts a row manually set to `invalid` survives a re-run *unchanged* — i.e. it pins `INSERT OR IGNORE` as correct and is the test that locked B-76 in. "Idempotent" was the wrong property; the right one is "manifest-owned columns converge, run-owned columns are preserved." | T8 `test_rerun_applies_a_changed_display_name_and_keyword_filter` + `test_rerun_preserves_run_owned_status_and_last_seen` (which keeps the *correct* half of the old assertion: `status` stays `invalid`) |
| `pipeline-app/tests/test_migrate_handles.py:20-31` | `test_derive_cohort` (8 params) | **kept, demoted** | Not defect-affirming — `derive_cohort` remains as the legacy fallback and these still describe it correctly. But it must stop reading as the primary contract. | Retitle the block comment to `# derive_cohort: legacy fallback only -- see test_explicit_cohort_beats_the_note_derived_one` and add T5's two tests above it |
| `pipeline-app/tests/test_backfill_youtube_frontmatter.py:78-80` | `test_parse_existing_falls_back_to_filename_for_video_id` | **inverted** | Asserts D-05's silent reconstruction is the correct behavior: it takes a file with no metadata whatsoever and asserts the `video_id` was invented from the filename, with no assertion that anything recorded the inference. | T18 `test_a_file_whose_metadata_did_not_parse_is_flagged` — same input, but now asserts `meta_parsed is False` and `"video_id" in inferred_fields`. The fallback still happens; it is no longer silent. |
| `pipeline-app/tests/test_backfill_youtube_frontmatter.py:112-117` | `test_build_meta_without_api_keeps_ytdlp_provenance` | **kept, extended** | Correct but incomplete: its fixture has no stored `metadata_source`, so it cannot catch D-04's downgrade of a file that already claims `youtube-data-api-v3`. Keeping it proves T16 did not regress the old-format path. | Add T16 `test_build_meta_never_downgrades_metadata_source` + `test_build_meta_never_nulls_an_existing_count` alongside it |

No other test in either owned file encodes a defect. `test_migrate_skips_a_handle_colliding_with_one_already_registered`,
`test_migrate_skips_a_collision_between_two_manifest_entries` and `test_migrate_seeds_the_rest_despite_one_collision`
are all correct and must keep passing unchanged through T3's loop rewrite — treat them as the regression lock on
`_seed_entry`.

---

## 7. Contract for P14 (documentation package)

P10 owns none of the docs. These are the statements P14 must write, and they are only true **after** this package
lands. B-80 (the seeding script is undocumented outside a historical plan doc) is P14's finding; this section is
its input.

### 7.1 `pipeline-app/README.md` — Setup section, after the venv/pip steps

> **Required.** A fresh checkout starts with an **empty** `handles` table, and a discovery run over zero handles
> completes with status `completed` and an empty email — indistinguishable from a quiet day (B-80). The setup
> must not be considered done until this has been run:
>
> ```bash
> cd pipeline-app
> python scripts/migrate_handles_from_manifest.py
> ```
>
> Seeds the `creators` and `handles` tables from `manifests/brand_sources.json`. Safe and expected to re-run after
> any manifest edit: manifest-owned columns (`display_name`, `cohort`, `keyword_filter`, `included`, `creator_id`)
> converge on the file; run-owned columns (`status`, `validated_at`, `last_seen_published_at`) are never touched.
> Handles seeded this way are `pending`, not `validated` — `validated` is only ever written by a real fetch.

### 7.2 `pipeline-app/README.md` — a coverage subsection

> **"Are we tracking all social platforms for our key creators?"**
>
> ```bash
> cd pipeline-app
> python scripts/migrate_handles_from_manifest.py --report
> ```
>
> Prints the creator × platform matrix from the manifest alone (no DB read, so it works on a fresh checkout).
> Every cell is `tracked`, `declared-excluded` or `not tracked`; `UNANSWERABLE` means the manifest is missing a
> platform key, and `test_shipped_manifest_has_zero_unanswerable_cells` fails if that ever happens again.

### 7.3 Root `README.md` — the manifest description

Currently describes `manifests/brand_sources.json` as "the roster" without saying anything imports it. It must
say: the manifest is the declarative roster for **both** `download_brandintel.py` (the corpus downloader —
`youtube`, `bluesky`, `rss`) **and** the pipeline app (all seven adapter platforms, via the seeding script above);
that every adapter platform has a key, with `[]` meaning "we deliberately track nobody here"; and that `rss` is
downloader-only with no adapter and no path into the daily discovery run (B-79).

### 7.4 `CLAUDE.md` — Conventions

Add one line to the "Adding a discovery platform" convention: a new adapter also requires a new key in
`manifests/brand_sources.json` and an entry in `migrate_handles_from_manifest.PLATFORMS`, or
`test_platforms_tuple_matches_the_adapter_registry` fails.

### 7.5 Behavior change to announce

`@bigthink` and `adamgrant.bsky.social` now ship `"included": false` (B-78) and are no longer pulled by the daily
discovery run or listed in the morning email. Revert by flipping both `included` fields to `true` and re-running
the seeding script.

---

## 8. Risks and non-goals

- **Not fixed here (other packages' files):** B-72's schema (P1), B-73's platform CHECK enforcement in
  `add_handle` (P8), B-74's template/registry drift (P15), B-80's README text (P14), B-82's status downgrade
  (P8), B-83's `copy_youthsports.sh` (unowned), `download_brandintel.py`'s own fixed key list (unowned).
  B-71's *second* consumer therefore stays hardcoded; our `_comment` and `--report` both state that
  `download_brandintel.py` reads only `youtube`/`bluesky`/`rss`, so the divergence is documented rather than
  silent.
- **`manifests/thinkers.json` is out of scope.** 53 public-domain works by 41 authors, no handles, no platforms,
  no discovery path — a content manifest for `download_thinkers.py`. It contributes **zero** creators to the
  matrix. Do not add it to the coverage report and do not conflate its authors with roster creators.
- **T8 changes an operator-visible property**: after this lands, editing the manifest and re-running the seeder
  *does* change the app. That is the fix, but it means a stale local manifest can now overwrite a deliberate UI
  edit to a manifest-owned column. Mitigation: run-owned columns are excluded from the upsert, and drift is
  reported both ways (T9).
- **The `creators` block is hand-maintained.** Nothing derives creator identity automatically; a new handle
  requires a `creator` slug or T10's `ManifestError` blocks the import. That is deliberate — an auto-generated
  per-handle creator would silently recreate B-72 while looking fixed.
