# Brand-Scoped Discovery Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the daily discovery digest email into three stacked, brand-scoped sections (Freedom2BeU, RaisingGoodSports, Gurus) in one send, each rendered in the exact format the single email uses today.

**Architecture:** Add a many-to-many `handle_brands` table so a handle can carry any number of brand tags. `discovery_notify.build_summary` attaches each item's brand tags (read from that table); `discovery_notify.notify` partitions the flat item list into three brand subsets, runs the existing per-brand spotlight-select + comment-draft logic on each subset independently, and hands three per-brand summaries to a new `email_render.render_brand_digest`, which reuses the existing single-summary renderer verbatim for each section and stitches the three bodies into one email under one subject line.

**Tech Stack:** Python 3.14, FastAPI, sqlite3, pytest. No new dependencies.

**Design reference:** `docs/superpowers/specs/2026-08-15-brand-scoped-discovery-email-design.md` — read it before starting; it records the decisions this plan implements (multi-tag brands, no CHECK constraint, run-status/errors NOT brand-scoped, subject counts distinct items, Freedom2BeU sourced from re-tagged existing handles only).

## Global Constraints

- Run every test from `pipeline-app/`: `cd pipeline-app && python -m pytest`. Running from the repo root shadows this package's `scripts/` with the root's and breaks imports.
- `discovery_digest.py` must stay DB-free (its own docstring's invariant) — brand tags are attached in `discovery_notify.py`, which already holds the DB connection, never inside `discovery_digest.py`.
- `handle_brands.brand` carries **no CHECK constraint** — see the design note's rationale. Do not add one.
- `run_status`, `has_issues`, and `errored` are **not** brand-filtered — every section shows the same run-level operational facts. Only `items`, `spotlight`, and `drafts` are brand-scoped.
- The subject line's post count comes from the pre-partition flat item list (distinct posts), never from summing the three sections' sizes.
- Section order is fixed: `freedom2beu`, `raisinggoodsports`, `guru`.
- Every new function needs a docstring only where the "why" is non-obvious, per this codebase's existing style — look at neighboring functions in the file you're editing before writing one.

---

### Task 1: `handle_brands` schema

**Files:**
- Modify: `pipeline-app/pipeline_app/schema.sql`
- Test: `pipeline-app/tests/test_db.py`

**Interfaces:**
- Produces: a `handle_brands` table with columns `(handle_id INTEGER, brand TEXT)`, primary key `(handle_id, brand)`, `handle_id` referencing `handles(id) ON DELETE CASCADE`. Later tasks depend on this exact shape.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_db.py` (near `test_schema_init_is_idempotent_with_new_discovery_tables`):

```python
def test_handle_brands_table_exists_on_a_fresh_database(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "handle_brands" in tables
    conn.close()


def test_handle_brands_cascades_when_its_handle_is_deleted(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-08-15T00:00:00Z")
    conn.execute("INSERT INTO handle_brands (handle_id, brand) VALUES (?, ?)", (handle_id, "guru"))
    conn.commit()
    conn.execute("DELETE FROM handles WHERE id = ?", (handle_id,))
    conn.commit()
    remaining = conn.execute("SELECT * FROM handle_brands WHERE handle_id = ?", (handle_id,)).fetchall()
    assert remaining == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k handle_brands -v`
Expected: FAIL — `sqlite3.OperationalError: no such table: handle_brands`

- [ ] **Step 3: Add the table to schema.sql**

In `pipeline-app/pipeline_app/schema.sql`, add this block immediately after the `handles_quarantine` table definition (before `discovery_runs`):

```sql
-- Which brand(s) a handle's content serves in the daily digest email.
-- Many-to-many: one handle can be relevant to more than one brand (e.g. a
-- parenting-psychology account can serve both freedom2beu and the general
-- guru roundup), and the digest renders the same item once per brand section
-- it belongs to. `guru` is a real row here, not inferred from
-- handles.cohort -- see the 2026-08-15 design note for why. `brand` carries
-- no CHECK: it is an open, operator-curated taxonomy expected to grow, and
-- widening a CHECK later means the same create-copy-drop-rename rebuild the
-- `handles` table's CHECK columns already cost this codebase once.
CREATE TABLE IF NOT EXISTS handle_brands (
    handle_id INTEGER NOT NULL REFERENCES handles(id) ON DELETE CASCADE,
    brand TEXT NOT NULL,
    PRIMARY KEY (handle_id, brand)
);
CREATE INDEX IF NOT EXISTS idx_handle_brands_brand ON handle_brands(brand);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k handle_brands -v`
Expected: PASS (2 tests). Also run `python -m pytest tests/test_db.py -v` in full to confirm nothing else broke.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/schema.sql pipeline-app/tests/test_db.py
git commit -m "feat(db): add handle_brands table for multi-brand handle tagging"
```

---

### Task 2: `db.py` brand CRUD

**Files:**
- Modify: `pipeline-app/pipeline_app/db.py`
- Test: `pipeline-app/tests/test_db.py`

**Interfaces:**
- Consumes: `handle_brands` table from Task 1.
- Produces: `set_handle_brands(conn, handle_id: int, brands: list[str]) -> None` (replace-semantics: the handle's tag set becomes exactly `brands`, deduplicated; order is not meaningful since `get_handle_brands` always returns alphabetically) and `get_handle_brands(conn, handle_id: int) -> list[str]` (sorted alphabetically). Task 3 and the seeding script (Task 7) call both; the UI route (Task 6) calls both.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_db.py`, near the other handle tests:

```python
def test_set_and_get_handle_brands(conn):
    handle_id = db.create_handle(conn, "instagram", "aspenprojectplay", None, "guru", None, "2026-08-15T00:00:00Z")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])
    assert db.get_handle_brands(conn, handle_id) == ["guru", "raisinggoodsports"]


def test_get_handle_brands_is_empty_for_an_untagged_handle(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-08-15T00:00:00Z")
    assert db.get_handle_brands(conn, handle_id) == []


def test_set_handle_brands_replaces_rather_than_accumulates(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-08-15T00:00:00Z")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])
    db.set_handle_brands(conn, handle_id, ["freedom2beu"])
    assert db.get_handle_brands(conn, handle_id) == ["freedom2beu"]


def test_set_handle_brands_dedupes_repeated_values(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-08-15T00:00:00Z")
    db.set_handle_brands(conn, handle_id, ["guru", "guru", "freedom2beu"])
    assert db.get_handle_brands(conn, handle_id) == ["freedom2beu", "guru"]


def test_set_handle_brands_to_empty_list_clears_all_tags(conn):
    handle_id = db.create_handle(conn, "youtube", "@a", None, "guru", None, "2026-08-15T00:00:00Z")
    db.set_handle_brands(conn, handle_id, ["guru"])
    db.set_handle_brands(conn, handle_id, [])
    assert db.get_handle_brands(conn, handle_id) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k handle_brands -v`
Expected: FAIL — `AttributeError: module 'pipeline_app.db' has no attribute 'set_handle_brands'`

- [ ] **Step 3: Implement in db.py**

In `pipeline-app/pipeline_app/db.py`, add immediately after `set_handle_included` (around line 1697):

```python
def set_handle_brands(conn: sqlite3.Connection, handle_id: int, brands: list[str]) -> None:
    """Replace handle_id's brand tags with exactly `brands` (order-insensitive,
    duplicates collapsed). Delete-then-insert rather than a diff: with at most
    a handful of tags per handle the atomicity is worth more than the extra
    writes, and the caller never needs to know which tags were already there.

    Wrapped in transaction(conn), not a bare commit_unless_in_transaction after
    both statements: this connection is shared across Starlette's threadpool,
    and an uncommitted DELETE sitting on it between the two execute() calls
    would be flushed early by an unrelated leaf helper's commit on the same
    connection if the INSERT ever raised in between -- silently clearing the
    handle's tags with no INSERT to replace them.
    """
    with transaction(conn):
        conn.execute("DELETE FROM handle_brands WHERE handle_id = ?", (handle_id,))
        conn.executemany(
            "INSERT INTO handle_brands (handle_id, brand) VALUES (?, ?)",
            [(handle_id, b) for b in dict.fromkeys(brands)],
        )


def get_handle_brands(conn: sqlite3.Connection, handle_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT brand FROM handle_brands WHERE handle_id = ? ORDER BY brand", (handle_id,)
    ).fetchall()
    return [r["brand"] for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_db.py -k handle_brands -v`
Expected: PASS (7 tests total from Tasks 1+2). Also run the full `test_db.py` file to confirm no regressions.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/db.py pipeline-app/tests/test_db.py
git commit -m "feat(db): add set_handle_brands/get_handle_brands"
```

---

### Task 3: attach brand tags to discovered items

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_notify.py`
- Test: `pipeline-app/tests/test_discovery_notify.py`

**Interfaces:**
- Consumes: `db.get_handle_brands(conn, handle_id) -> list[str]` from Task 2.
- Produces: every item dict in `build_summary(...)["items"]` now carries a `"brands": list[str]` key (the tags of the handle that produced it). Task 5's `notify()` filters on this key.

- [ ] **Step 1: Write the failing test**

Add to `pipeline-app/tests/test_discovery_notify.py`, near `test_build_summary_collects_items_from_every_platform`:

```python
def test_build_summary_attaches_brand_tags_from_the_producing_handle(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "instagram", "aspenprojectplay", "Aspen Project Play")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "instagram", "aspenprojectplay", "p1.md",
                ["url: 'https://instagram.com/p/1'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption.")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert len(summary["items"]) == 1
    assert summary["items"][0]["brands"] == ["guru", "raisinggoodsports"]


def test_build_summary_untagged_handle_produces_items_with_no_brands(notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn)  # no set_handle_brands call -- stays untagged
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_youtube_video(repo_root, "@somechannel", "vid1", "A Video", "2026-08-01T06:01:00+00:00")

    summary = discovery_notify.build_summary(conn, repo_root, run_row_id)

    assert summary["items"][0]["brands"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_notify.py -k brand_tags -v`
Expected: FAIL — `KeyError: 'brands'`

- [ ] **Step 3: Implement in discovery_notify.py**

In `pipeline-app/pipeline_app/discovery_notify.py`, modify the loop inside `build_summary` (currently lines 105–117):

```python
    for result in handle_results:
        handle_row = db_mod.get_handle(conn, result["handle_id"])
        label = handle_row["display_name"] or handle_row["handle"]
        brands = db_mod.get_handle_brands(conn, handle_row["id"])

        if result["status"] == "error":
            errored.append(label)

        found = discovery_digest.collect_new_items(repo_root, handle_row, started_at)
        if len(found) != result["items_downloaded"]:
            print(f"discovery_notify: item count mismatch for {label}: "
                  f"db says {result['items_downloaded']}, found {len(found)} on disk",
                  file=sys.stderr)
        for item in found:
            item["brands"] = brands
        items.extend(found)
```

Update `build_summary`'s docstring to add one sentence after the existing "flat" paragraph:

```python
    Each item also carries a `brands` list -- the tags of the handle that
    produced it (db.get_handle_brands), attached here rather than in
    discovery_digest.collect_new_items because that module is deliberately
    DB-free. notify() reads this key to partition items by brand.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_notify.py -v`
Expected: PASS, including all pre-existing tests in the file (this is a purely additive key on the item dict — nothing reads the full dict via equality, so no existing assertion should break; confirm by reading the failure output if anything does fail).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_notify.py pipeline-app/tests/test_discovery_notify.py
git commit -m "feat(discovery): attach handle brand tags to discovered items"
```

---

### Task 4: `email_render.render_brand_digest`

**Files:**
- Modify: `pipeline-app/pipeline_app/email_render.py`
- Test: `pipeline-app/tests/test_email_render.py`

**Interfaces:**
- Consumes: nothing new from earlier tasks (this task only touches rendering; `render_email`, `_render_text`, `_render_html` are reused unchanged).
- Produces: `BRAND_SECTION_ORDER: tuple[str, ...]` = `("freedom2beu", "raisinggoodsports", "guru")`, `BRAND_LABELS: dict[str, str]`, and `render_brand_digest(overall: dict, sections: dict[str, dict], run_date: str) -> dict` returning `{"subject", "text", "html"}`. `sections` maps a brand string to a summary dict shaped exactly like `render_email`'s existing `summary` parameter (same keys: `run_status`, `has_issues`, `items`, `errored`, `spotlight`, `drafts`). `overall` is the pre-partition summary (same shape) used only for the subject line's post count and issue flag. Task 5's `notify()` calls this.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_email_render.py` (reuse the existing `_item`/`_summary` helpers already in that file):

```python
def test_render_brand_digest_orders_sections_freedom2beu_then_rgs_then_guru():
    sections = {
        "guru": _summary(items=[_item(item_id="g1", title="Guru Post")]),
        "raisinggoodsports": _summary(items=[_item(item_id="r1", title="RGS Post")]),
        "freedom2beu": _summary(items=[_item(item_id="f1", title="F2BU Post")]),
    }
    overall = _summary(items=[_item(item_id="g1"), _item(item_id="r1"), _item(item_id="f1")])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    text = result["text"]
    assert text.index("F2BU Post") < text.index("RGS Post") < text.index("Guru Post")
    html = result["html"]
    assert html.index("F2BU Post") < html.index("RGS Post") < html.index("Guru Post")


def test_render_brand_digest_labels_each_section():
    sections = {"freedom2beu": _summary(items=[_item()]), "raisinggoodsports": _summary(),
                "guru": _summary()}
    overall = _summary(items=[_item()])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert "Freedom2BeU" in result["html"]
    assert "RaisingGoodSports" in result["html"]
    assert "Gurus" in result["html"]


def test_render_brand_digest_omits_a_brand_missing_from_sections():
    # This exercises render_brand_digest's own defensive contract in
    # isolation. notify() (Task 5) always populates all three keys in
    # `sections`, so this branch is not reachable from the real pipeline
    # today -- it exists so render_brand_digest stays correct if ever called
    # with a partial `sections` dict directly (e.g. from a future script or
    # a test), which is exactly what this test does.
    sections = {"guru": _summary(items=[_item()])}
    overall = _summary(items=[_item()])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert "Freedom2BeU" not in result["html"]
    assert "RaisingGoodSports" not in result["html"]
    assert "Gurus" in result["html"]


def test_render_brand_digest_subject_counts_distinct_items_not_section_sum():
    # The same post can render under two sections (multi-tag). The subject
    # must count it once, from `overall`, not twice from summing sections.
    shared = _item(item_id="shared1")
    sections = {
        "guru": _summary(items=[shared]),
        "raisinggoodsports": _summary(items=[shared]),
    }
    overall = _summary(items=[shared])
    result = email_render.render_brand_digest(overall, sections, "2026-08-08")
    assert result["subject"] == "ContentStudio Discovery 2026-08-08: 1 new post(s)"


def test_render_brand_digest_issue_prefix_comes_from_overall_not_sections():
    sections = {"guru": _summary(has_issues=False)}
    overall = _summary(run_status="failed", has_issues=True)
    result = email_render.render_brand_digest(overall, sections, "2026-08-08")
    assert result["subject"].startswith("[ISSUE] ")


def test_render_brand_digest_each_section_keeps_its_own_spotlight_and_drafts():
    f2bu_spot = _item(item_id="f1", title="F2BU Spotlight")
    rgs_spot = _item(item_id="r1", title="RGS Spotlight")
    sections = {
        "freedom2beu": _summary(items=[f2bu_spot], spotlight=f2bu_spot,
                                drafts=["F2BU draft one.", "F2BU draft two.", "F2BU draft three."]),
        "raisinggoodsports": _summary(items=[rgs_spot], spotlight=rgs_spot,
                                      drafts=["RGS draft one.", "RGS draft two.", "RGS draft three."]),
    }
    overall = _summary(items=[f2bu_spot, rgs_spot])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert "F2BU draft one." in result["text"]
    assert "RGS draft one." in result["text"]


def test_render_brand_digest_falls_back_to_no_content_when_every_section_is_empty():
    result = email_render.render_brand_digest(_summary(), {}, "2026-08-15")
    assert "No new content today." in result["text"]
    assert "No new content today." in result["html"]


def test_render_brand_digest_warns_about_items_covered_by_no_section():
    # An untagged handle's items pass through build_summary but match no
    # brand in BRAND_SECTION_ORDER, so no section's `items` list contains
    # them. Without this warning they vanish from the email while the
    # subject's count (drawn from `overall`) still includes them --
    # Critical finding #1 from the pre-execution review.
    orphan = _item(item_id="orphan1", title="Orphan Post")
    overall = _summary(items=[orphan])
    result = email_render.render_brand_digest(overall, {}, "2026-08-15")
    assert result["subject"] == "ContentStudio Discovery 2026-08-15: 1 new post(s)"
    assert "no brand tag" in result["text"].lower()
    assert "no brand tag" in result["html"].lower()


def test_render_brand_digest_no_warning_when_every_item_is_covered():
    covered = _item(item_id="c1")
    sections = {"guru": _summary(items=[covered])}
    overall = _summary(items=[covered])
    result = email_render.render_brand_digest(overall, sections, "2026-08-15")
    assert "no brand tag" not in result["text"].lower()
    assert "no brand tag" not in result["html"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_email_render.py -k render_brand_digest -v`
Expected: FAIL — `AttributeError: module 'pipeline_app.email_render' has no attribute 'render_brand_digest'`

- [ ] **Step 3: Implement in email_render.py**

In `pipeline-app/pipeline_app/email_render.py`, add near the top, after the existing `PLATFORM_LABELS` block (around line 30):

```python
BRAND_SECTION_ORDER = ("freedom2beu", "raisinggoodsports", "guru")
BRAND_LABELS = {
    "freedom2beu": "Freedom2BeU",
    "raisinggoodsports": "RaisingGoodSports",
    "guru": "Gurus",
}
```

Add at the end of the file, after `render_email`:

```python
def render_brand_digest(overall: dict, sections: dict, run_date: str) -> dict:
    """{"subject", "text", "html"} for one finished run, split into per-brand
    sections in BRAND_SECTION_ORDER.

    `overall` is build_summary()'s pre-partition summary -- its `items` is what
    the subject line counts. Brand sections deliberately overlap (multi-tag: an
    item tagged both `raisinggoodsports` and `guru` renders in both sections),
    so summing section sizes would double-count it; `overall["items"]` is the
    one place a post is counted exactly once. `overall["has_issues"]` likewise
    drives the [ISSUE] prefix for the same reason -- it is a run-wide fact, not
    a per-brand one.

    `sections` maps brand -> a summary shaped exactly like render_email's
    parameter, already restricted to that brand's items/spotlight/drafts. A
    brand absent from `sections` is omitted from the email entirely.

    An item in `overall["items"]` that no section's `items` list contains
    (an untagged handle, or one tagged with something outside
    BRAND_SECTION_ORDER) would otherwise vanish from the email silently
    while the subject's count still included it -- Critical finding #1 from
    the pre-execution review. A warning banner makes that discoverable
    instead of silent.
    """
    total = len(overall["items"])
    subject = f"ContentStudio Discovery {run_date}: {total} new post(s)"
    if overall["has_issues"]:
        subject = f"[ISSUE] {subject}"

    def _identity(item):
        return (item["platform"], item["handle"], item["item_id"])

    covered = {_identity(i) for s in sections.values() for i in s["items"]}
    orphan_count = sum(1 for i in overall["items"] if _identity(i) not in covered)
    warning_text = warning_html = ""
    if orphan_count:
        message = (f"{orphan_count} new post(s) came from handle(s) with no brand tag "
                   f"(or a tag outside {', '.join(BRAND_SECTION_ORDER)}) and do not "
                   f"appear in any section below. Tag them at /discovery/handles.")
        warning_text = f"WARNING: {message}\n\n"
        warning_html = f"<p><strong>WARNING:</strong> {_html.escape(message)}</p>\n"

    text_parts: list[str] = []
    html_parts: list[str] = []
    for brand in BRAND_SECTION_ORDER:
        summary = sections.get(brand)
        if summary is None:
            continue
        label = BRAND_LABELS.get(brand, brand.title())
        text_parts.append(f"===== {label.upper()} =====\n\n{_render_text(summary)}")
        html_parts.append(f"<h1>{_html.escape(label)}</h1>\n{_render_html(summary)}")

    text = warning_text + (
        "\n\n".join(text_parts).rstrip() + "\n" if text_parts else NO_CONTENT_TEXT + "\n"
    )
    html = warning_html + (
        "\n<hr>\n".join(html_parts) if html_parts else f"<p>{NO_CONTENT_TEXT}</p>"
    )
    return {"subject": subject, "text": text, "html": html}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_email_render.py -v`
Expected: PASS on the whole file — the new tests plus every pre-existing test (this task adds two module-level constants and one new function; `render_email`/`_render_text`/`_render_html` are untouched).

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/email_render.py pipeline-app/tests/test_email_render.py
git commit -m "feat(email): add render_brand_digest for multi-section emails"
```

---

### Task 5: `notify()` partitions into three brand sections

**Files:**
- Modify: `pipeline-app/pipeline_app/discovery_notify.py`
- Test: `pipeline-app/tests/test_discovery_notify.py`

**Interfaces:**
- Consumes: `build_summary(...)["items"][i]["brands"]` from Task 3; `email_render.BRAND_SECTION_ORDER` and `email_render.render_brand_digest` from Task 4.
- Produces: `notify()`'s observable behavior — it now calls `email_render.render_brand_digest` instead of `email_render.render_email`, and calls `discovery_digest.select_spotlight` / `comment_draft.draft_comments` once per brand in `BRAND_SECTION_ORDER` (up to 3 times each) instead of once.

- [ ] **Step 1: Update the two tests that assert on `render_email`/single-spotlight orchestration**

`test_notify_orchestrates_build_render_send` and `test_notify_threads_spotlight_and_drafts_into_render` in `tests/test_discovery_notify.py` currently monkeypatch `email_render.render_email` and assert a single `select_spotlight`/`draft_comments` call. Replace both with the versions below (same file, replacing the existing two functions):

```python
def test_notify_orchestrates_build_render_send(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T11:00:00+00:00")  # 06:00 America/Chicago (UTC-5)

    calls = {}
    monkeypatch.setattr(discovery_notify, "build_summary",
                         lambda c, r, rid: (calls.setdefault("build_args", (c, r, rid)),
                                             {"run_status": "completed", "has_issues": False,
                                              "items": [], "errored": []})[1])
    monkeypatch.setattr(discovery_notify.discovery_digest, "select_spotlight", lambda items: None)
    monkeypatch.setattr(discovery_notify.email_render, "render_brand_digest",
                         lambda overall, sections, run_date:
                             (calls.setdefault("render_args", (overall, sections, run_date)),
                              {"subject": "s", "text": "t", "html": "h"})[1])
    monkeypatch.setattr(discovery_notify, "send_email",
                         lambda subject, text, html: (calls.setdefault("send_args", (subject, text, html)), True)[1])

    result = discovery_notify.notify(conn, repo_root, run_row_id)

    assert result is True
    assert calls["build_args"] == (conn, repo_root, run_row_id)
    overall, sections, run_date = calls["render_args"]
    assert overall == {"run_status": "completed", "has_issues": False, "items": [], "errored": []}
    assert set(sections) == {"freedom2beu", "raisinggoodsports", "guru"}
    assert run_date == "2026-08-01"
    assert calls["send_args"] == ("s", "t", "h")


def test_notify_threads_spotlight_and_drafts_into_render(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn)
    seen = {}

    item = {"marker": "the-item", "brands": ["guru"], "platform": "youtube", "handle": "@x", "item_id": "i1"}
    spotlight = {"marker": "the-spotlight", "platform": "youtube", "handle": "@x", "item_id": "i1"}
    monkeypatch.setattr(discovery_notify, "build_summary",
                        lambda *a: {"run_status": "completed", "has_issues": False,
                                    "items": [item], "errored": []})
    monkeypatch.setattr(discovery_notify.discovery_digest, "select_spotlight",
                        lambda items: spotlight if items else None)
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments",
                        lambda item, **kw: ["d1", "d2", "d3"])

    def fake_render(overall, sections, run_date):
        seen["sections"] = sections
        seen["run_date"] = run_date
        return {"subject": "S", "text": "T", "html": "<p>H</p>"}

    monkeypatch.setattr(discovery_notify.email_render, "render_brand_digest", fake_render)
    monkeypatch.setattr(discovery_notify, "send_email", lambda *a: True)

    assert discovery_notify.notify(conn, repo_root, run_row_id) is True
    # `item` is tagged "guru" only, so only the guru section sees it as a spotlight.
    assert seen["sections"]["guru"]["spotlight"] == spotlight
    assert seen["sections"]["guru"]["drafts"] == ["d1", "d2", "d3"]
    assert seen["sections"]["freedom2beu"]["spotlight"] is None
    assert seen["sections"]["freedom2beu"]["drafts"] == []
    assert seen["run_date"] == "2026-08-01"


def test_notify_reuses_drafts_when_the_same_item_is_spotlighted_in_two_sections(monkeypatch, notify_db):
    # `guru` is a superset of `raisinggoodsports` here, so the identical post
    # is the best spotlight in both sections. draft_comments (a ~90s `claude
    # -p` subprocess call) must run once, not once per section -- High
    # finding #2 from the pre-execution review.
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "instagram", "aspenprojectplay", "Aspen Project Play")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "instagram", "aspenprojectplay", "p1.md",
                ["url: 'https://instagram.com/p/1'", "like_count: 40",
                 "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption with enough text to be a spotlight candidate.")

    draft_calls = []
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments",
                         lambda item, **kw: draft_calls.append(item["item_id"]) or ["d1", "d2", "d3"])
    monkeypatch.setattr(discovery_notify, "send_email", lambda *a: True)

    discovery_notify.notify(conn, repo_root, run_row_id)

    assert len(draft_calls) == 1
```

Also add a new test proving per-brand item partitioning end to end against the real `build_summary`:

```python
def test_notify_partitions_items_by_brand_and_repeats_multi_tagged_items(monkeypatch, notify_db):
    conn, repo_root = notify_db
    run_row_id = _make_run(conn, started_at="2026-08-01T06:00:00+00:00")
    handle_id = _make_handle(conn, "instagram", "aspenprojectplay", "Aspen Project Play")
    db.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])
    db.record_handle_result(conn, run_row_id, handle_id, "ok", 1)
    _write_post(repo_root, "instagram", "aspenprojectplay", "p1.md",
                ["url: 'https://instagram.com/p/1'", "fetched_at: '2026-08-01T06:01:00+00:00'"],
                "A caption that mentions youth sports parenting.")

    seen = {}
    monkeypatch.setattr(discovery_notify.comment_draft, "draft_comments", lambda item, **kw: [])
    monkeypatch.setattr(discovery_notify.email_render, "render_brand_digest",
                         lambda overall, sections, run_date: seen.setdefault("sections", sections) or
                                                              {"subject": "s", "text": "t", "html": "h"})
    monkeypatch.setattr(discovery_notify, "send_email", lambda *a: True)

    discovery_notify.notify(conn, repo_root, run_row_id)

    assert len(seen["sections"]["guru"]["items"]) == 1
    assert len(seen["sections"]["raisinggoodsports"]["items"]) == 1
    assert len(seen["sections"]["freedom2beu"]["items"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_notify.py -k "notify_orchestrates or notify_threads or notify_partitions" -v`
Expected: FAIL — `AttributeError: module 'pipeline_app.email_render' has no attribute 'render_email'` style mismatch, or `AssertionError` on the old single-spotlight shape, since `notify()` still calls the old code.

- [ ] **Step 3: Rewrite `notify()` in discovery_notify.py**

Replace the current `notify` function (lines 128–143) with:

```python
def notify(conn, repo_root: Path, run_row_id: int) -> bool:
    overall = build_summary(conn, repo_root, run_row_id)

    # Cache keyed by (platform, handle, item_id): `guru` is a superset of the
    # other brands' items, so the same post is frequently the best spotlight
    # both globally and within its specific brand. Without this cache,
    # comment_draft.draft_comments -- a ~90s `claude -p` subprocess call --
    # would run twice for identical input (High finding #2, pre-execution
    # review).
    draft_cache: dict[tuple, list[str]] = {}

    def _drafts_for(spotlight):
        if spotlight is None:
            return []
        key = (spotlight["platform"], spotlight["handle"], spotlight["item_id"])
        if key not in draft_cache:
            draft_cache[key] = comment_draft.draft_comments(spotlight)
        return draft_cache[key]

    sections = {}
    for brand in email_render.BRAND_SECTION_ORDER:
        brand_items = [i for i in overall["items"] if brand in i["brands"]]
        spotlight = discovery_digest.select_spotlight(brand_items)
        # draft_comments never raises and returns [] on every failure path, so a
        # drafting problem costs three drafts for this post, never the
        # section's inventory or the other two sections.
        drafts = _drafts_for(spotlight)
        sections[brand] = {
            "run_status": overall["run_status"],
            "has_issues": overall["has_issues"],
            "items": brand_items,
            "errored": overall["errored"],
            "spotlight": spotlight,
            "drafts": drafts,
        }

    run_row = db_mod.get_run(conn, run_row_id)
    timezone_name = db_mod.get_settings(conn)["timezone"]
    started_at = _dt.datetime.fromisoformat(run_row["started_at"])
    run_date = started_at.astimezone(ZoneInfo(timezone_name)).date().isoformat()

    rendered = email_render.render_brand_digest(overall, sections, run_date)
    return send_email(rendered["subject"], rendered["text"], rendered["html"])
```

Update the module docstring's second paragraph (currently referencing `build_summary`/`render_email`-shaped contract) — after "notify() adding its own would be a second, redundant failure boundary," add:

```
notify() now fans out per brand internally (one select_spotlight call per
entry in email_render.BRAND_SECTION_ORDER, and one draft_comments call per
DISTINCT spotlighted item -- a post spotlighted in two sections is drafted
once and reused), but that fan-out is still inside notify()'s own no-catch
contract: any of those calls raising propagates exactly like the
single-brand path did.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_discovery_notify.py -v`
Expected: PASS on the whole file. `test_notify_end_to_end_uses_real_build_summary_and_render_email` (unrenamed) exercises the real `build_summary` + `render_brand_digest` path already — check its assertions (`"Some Channel" in captured["text"]`, `"Real Contract Video" in captured["text"]`) still hold: the handle in that test is untagged (`_make_handle` doesn't call `set_handle_brands`), so its item carries `brands == []` and appears in **no** section. Since the test only asserts the text contains those strings, and an empty digest would not contain them, this test needs the handle tagged. Fix it by adding one line before `db.record_handle_result(...)`:

```python
db.set_handle_brands(conn, handle_id, ["guru"])
```

Re-run after that fix.

- [ ] **Step 5: Commit**

```bash
git add pipeline-app/pipeline_app/discovery_notify.py pipeline-app/tests/test_discovery_notify.py
git commit -m "feat(discovery): partition the daily digest into brand sections"
```

---

### Task 6: brand-tagging UI

**Files:**
- Modify: `pipeline-app/pipeline_app/routes/discovery.py`
- Modify: `pipeline-app/pipeline_app/templates/discovery_handles.html`
- Test: `pipeline-app/tests/test_routes_discovery.py`

**Interfaces:**
- Consumes: `db.set_handle_brands` / `db.get_handle_brands` from Task 2.
- Produces: `POST /discovery/handles/{handle_id}/brands` (form field `brands`, repeated, one value per checked box) replacing that handle's brand tags and redirecting back to `/discovery/handles`; the handles page now shows each handle's current brand tags and a way to change them.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline-app/tests/test_routes_discovery.py`:

```python
def test_handles_page_shows_a_handles_current_brand_tags(client: TestClient, monkeypatch):
    _no_spawn(monkeypatch)
    _add(client, "instagram", "aspenprojectplay")
    from pipeline_app import db as db_mod
    conn = client.app.state.conn
    handle_id = db_mod.get_handle_by_platform_and_handle(conn, "instagram", "aspenprojectplay")["id"]
    db_mod.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])

    response = client.get("/discovery/handles")
    assert response.status_code == 200
    assert "raisinggoodsports" in response.text


def test_update_handle_brands_replaces_the_tag_set(client: TestClient, monkeypatch):
    _no_spawn(monkeypatch)
    _add(client, "instagram", "aspenprojectplay")
    from pipeline_app import db as db_mod
    conn = client.app.state.conn
    handle_id = db_mod.get_handle_by_platform_and_handle(conn, "instagram", "aspenprojectplay")["id"]
    db_mod.set_handle_brands(conn, handle_id, ["guru"])

    response = client.post(f"/discovery/handles/{handle_id}/brands",
                           data={"brands": ["guru", "raisinggoodsports"]})
    assert response.status_code in (200, 303, 307)
    assert db_mod.get_handle_brands(conn, handle_id) == ["guru", "raisinggoodsports"]


def test_update_handle_brands_to_no_boxes_checked_clears_all_tags(client: TestClient, monkeypatch):
    _no_spawn(monkeypatch)
    _add(client, "instagram", "aspenprojectplay")
    from pipeline_app import db as db_mod
    conn = client.app.state.conn
    handle_id = db_mod.get_handle_by_platform_and_handle(conn, "instagram", "aspenprojectplay")["id"]
    db_mod.set_handle_brands(conn, handle_id, ["guru"])

    client.post(f"/discovery/handles/{handle_id}/brands", data={})
    assert db_mod.get_handle_brands(conn, handle_id) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline-app && python -m pytest tests/test_routes_discovery.py -k handle_brands -v`
Expected: FAIL — `404 Not Found` on the POST (route doesn't exist yet) and the GET test failing because `raisinggoodsports` isn't in the page yet.

- [ ] **Step 3: Implement the route**

In `pipeline-app/pipeline_app/routes/discovery.py`, add near the top:

```python
BRAND_CHOICES = ["guru", "raisinggoodsports", "freedom2beu"]
```

Modify `discovery_handles_page` to also compute and pass each handle's brand tags:

```python
@router.get("/discovery/handles")
def discovery_handles_page(request: Request):
    conn = request.app.state.conn
    handles = db_mod.list_handles(conn)
    handle_brands = {h["id"]: db_mod.get_handle_brands(conn, h["id"]) for h in handles}
    settings = db_mod.get_settings(conn)
    return request.app.state.templates.TemplateResponse(
        request, "discovery_handles.html",
        {
            "handles": handles, "cohort_suggestions": COHORT_SUGGESTIONS,
            "brand_choices": BRAND_CHOICES, "handle_brands": handle_brands,
            "settings": settings,
            "active_nav": "discovery_handles", "cli_available": request.app.state.cli_available,
        },
    )
```

Add a new route after `toggle_handle_included`:

```python
@router.post("/discovery/handles/{handle_id}/brands")
def update_handle_brands(request: Request, handle_id: int, brands: list[str] = Form([])):
    conn = request.app.state.conn
    db_mod.set_handle_brands(conn, handle_id, brands)
    return RedirectResponse(url="/discovery/handles", status_code=303)
```

- [ ] **Step 4: Implement the template**

In `pipeline-app/pipeline_app/templates/discovery_handles.html`, add a `Brands` header cell to the `<thead>` row (after `Cohort`):

```html
<tr><th>Platform</th><th>Handle</th><th>Display name</th><th>Cohort</th><th>Brands</th><th>Status</th><th>Included</th><th>Last seen</th></tr>
```

Add a new `<td>` inside the `{% for h in handles %}` loop, after the Cohort cell:

```html
<td>
  <form method="post" action="/discovery/handles/{{ h.id }}/brands">
    {% for b in brand_choices %}
    <label><input type="checkbox" name="brands" value="{{ b }}"
      {% if b in handle_brands.get(h.id, []) %}checked{% endif %}> {{ b }}</label>
    {% endfor %}
    <button type="submit">Save</button>
  </form>
</td>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd pipeline-app && python -m pytest tests/test_routes_discovery.py -v`
Expected: PASS on the whole file.

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/pipeline_app/routes/discovery.py pipeline-app/pipeline_app/templates/discovery_handles.html pipeline-app/tests/test_routes_discovery.py
git commit -m "feat(discovery-ui): let the operator tag handles with brands"
```

---

### Task 7: apply the initial 15-handle brand tagging

**Files:**
- Create: `pipeline-app/scripts/tag_handle_brands_2026_08.py`
- Test: `pipeline-app/tests/test_tag_handle_brands_2026_08.py`

**Interfaces:**
- Consumes: `db.set_handle_brands`, `db.get_handle_by_platform_and_handle`, `db.list_handles` from Task 2 / existing `db.py`.
- Produces: a script, idempotent, that applies the mapping recorded in the design note's table to the live `pipeline-app/pipeline.db`.

- [ ] **Step 1: Write the failing test**

Create `pipeline-app/tests/test_tag_handle_brands_2026_08.py`:

```python
from pathlib import Path

import pytest

from pipeline_app import db
from scripts import tag_handle_brands_2026_08 as tagger


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def _seed_the_15_live_handles(conn):
    now = "2026-08-01T00:00:00Z"
    for platform, handle in tagger.BRAND_TAGS:
        db.create_handle(conn, platform, handle, None, "guru", None, now)


def test_brand_tags_covers_exactly_the_15_known_live_handles():
    # A dict's length equalling its own key-set length is a tautology (always
    # true, dict keys are already unique) -- Medium finding #5 from the
    # pre-execution review. This pins the actual expected count instead.
    assert len(tagger.BRAND_TAGS) == 15


def test_every_tagged_brand_is_one_of_the_three_known_brands():
    known = {"guru", "raisinggoodsports", "freedom2beu"}
    for brands in tagger.BRAND_TAGS.values():
        assert set(brands) <= known


def test_every_entry_carries_guru():
    for brands in tagger.BRAND_TAGS.values():
        assert "guru" in brands


def test_apply_tags_every_seeded_handle(conn):
    _seed_the_15_live_handles(conn)
    missing, untagged = tagger.apply(conn)
    assert missing == []
    assert untagged == []
    for (platform, handle), brands in tagger.BRAND_TAGS.items():
        handle_id = db.get_handle_by_platform_and_handle(conn, platform, handle)["id"]
        assert db.get_handle_brands(conn, handle_id) == sorted(set(brands))


def test_apply_reports_a_mapped_handle_that_is_not_in_the_db(conn):
    missing, untagged = tagger.apply(conn)
    assert set(missing) == {f"{p}/{h}" for p, h in tagger.BRAND_TAGS}


def test_apply_reports_a_db_handle_the_mapping_does_not_cover(conn):
    db.create_handle(conn, "youtube", "@unmapped", None, "guru", None, "2026-08-01T00:00:00Z")
    missing, untagged = tagger.apply(conn)
    assert "youtube/@unmapped" in untagged


def test_apply_is_idempotent(conn):
    _seed_the_15_live_handles(conn)
    tagger.apply(conn)
    tagger.apply(conn)
    for (platform, handle), brands in tagger.BRAND_TAGS.items():
        handle_id = db.get_handle_by_platform_and_handle(conn, platform, handle)["id"]
        assert db.get_handle_brands(conn, handle_id) == sorted(set(brands))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd pipeline-app && python -m pytest tests/test_tag_handle_brands_2026_08.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.tag_handle_brands_2026_08'`

- [ ] **Step 3: Write the script**

Create `pipeline-app/scripts/tag_handle_brands_2026_08.py`:

```python
"""One-time application of ContentStudio's initial brand tagging to the 15
discovery handles that predate the handle_brands table. See
docs/superpowers/specs/2026-08-15-brand-scoped-discovery-email-design.md for
the RaisingGoodSports/Freedom2BeU classification rationale.

Safe to re-run: set_handle_brands replaces a handle's tag set, so a second run
reproduces the same end state rather than accumulating duplicates.

Usage: python scripts/tag_handle_brands_2026_08.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline_app import db  # noqa: E402

# (platform, handle) -> brand tags. Every entry carries "guru": these are the
# pipeline's original inspiration-roster handles, and this tagging must not
# remove them from that section -- it only adds a more specific brand on top
# where one applies.
BRAND_TAGS: dict[tuple[str, str], list[str]] = {
    ("instagram", "aspenprojectplay"): ["guru", "raisinggoodsports"],
    ("instagram", "ctgprojecthq"): ["guru", "raisinggoodsports"],
    ("linkedin-company", "positive-coaching-alliance"): ["guru", "raisinggoodsports"],
    ("linkedin-profile", "coachjohnosullivan"): ["guru", "raisinggoodsports"],
    ("instagram", "drbeckyatgoodinside"): ["guru", "freedom2beu"],
    ("linkedin-profile", "drbecky"): ["guru", "freedom2beu"],
    ("linkedin-profile", "danielpink"): ["guru", "freedom2beu"],
    ("linkedin-profile", "nireyal"): ["guru", "freedom2beu"],
    ("youtube", "@ImpactParents"): ["guru", "freedom2beu"],
    ("youtube", "@danielpinktv"): ["guru", "freedom2beu"],
    ("youtube", "@drdansiegel"): ["guru", "freedom2beu"],
    ("youtube", "@goodinside"): ["guru", "freedom2beu"],
    ("youtube", "@nirandfar"): ["guru", "freedom2beu"],
    ("youtube", "@positive-intelligence"): ["guru", "freedom2beu"],
    ("youtube", "@NextBigIdeaClub"): ["guru"],
}


def apply(conn) -> tuple[list[str], list[str]]:
    """Apply BRAND_TAGS to `conn`. Returns (missing, untagged):
    `missing` is every BRAND_TAGS entry with no matching DB row (skipped);
    `untagged` is every INCLUDED DB handle BRAND_TAGS does not mention (left
    as-is). Scoped to included_only=True: an excluded handle produces no
    items in any digest run, so flagging it as "untagged" would false-alarm
    on ordinary roster housekeeping rather than a real coverage gap (Low
    finding #6, pre-execution review)."""
    missing: list[str] = []
    for (platform, handle), brands in BRAND_TAGS.items():
        row = db.get_handle_by_platform_and_handle(conn, platform, handle)
        if row is None:
            missing.append(f"{platform}/{handle}")
            continue
        db.set_handle_brands(conn, row["id"], sorted(set(brands)))
        print(f"  {platform}/{handle}: {', '.join(sorted(set(brands)))}")

    untagged = [
        f"{r['platform']}/{r['handle']}" for r in db.list_handles(conn, included_only=True)
        if (r["platform"], r["handle"]) not in BRAND_TAGS
    ]
    return missing, untagged


def main() -> int:
    pipeline_app_root = Path(__file__).resolve().parents[1]
    db_path = pipeline_app_root / "pipeline.db"
    schema_path = pipeline_app_root / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)

    missing, untagged = apply(conn)
    conn.close()

    if missing:
        print(f"\n! not found in the DB (skipped): {', '.join(missing)}", file=sys.stderr)
    if untagged:
        print(f"\n?? handle(s) in the DB not covered by this script: {', '.join(untagged)}",
              file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd pipeline-app && python -m pytest tests/test_tag_handle_brands_2026_08.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Run it for real against the live database**

```bash
cd pipeline-app && python scripts/tag_handle_brands_2026_08.py
```

Confirm the output lists all 15 handles with their tags and reports no `missing` and no unexpected `untagged` entries (the script's own `untagged` warning is expected to be empty if every live handle is one of the 15 in the table — if it reports something new, a handle was added to the roster after this plan was written and needs a tagging decision before the email split is meaningful for it).

- [ ] **Step 6: Commit**

```bash
git add pipeline-app/scripts/tag_handle_brands_2026_08.py pipeline-app/tests/test_tag_handle_brands_2026_08.py
git commit -m "chore(discovery): apply initial brand tagging to the live handle roster"
```

Note: this step also modifies `pipeline-app/pipeline.db`, but that file is git-ignored (`.gitignore:15`) — the commit above only needs the script and its test; the applied tagging lives in the local DB file only, same as every other row this app writes.

---

## After this plan

- `cd pipeline-app && python -m pytest` should be fully green.
- The next real cron run (or a manual `POST /discovery/run-now`) produces a three-section email. There is no dedicated end-to-end test that drives an actual send — verify by triggering a real run once notify is deployed, or by re-running `test_notify_end_to_end_uses_real_build_summary_and_render_email` (Task 5) as the closest automated proxy.
- Future handle additions get their brand tags through the Task 6 UI at add-time or after; nothing else in this plan updates automatically.
