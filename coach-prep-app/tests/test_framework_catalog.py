from __future__ import annotations

import json

import pytest
import yaml

from coach_prep_app import db, framework_catalog as fc


def _entry(**overrides):
    base = {
        "id": "jscc-a3-2-examining-fear",
        "title": "Examining Fear",
        "framework": "ABC's of Coaching -- Accountability",
        "kind": "activity",
        "rel_path": "Frameworks to consider/ABC's of coaching/Awareness/Fear.pdf.md",
        "source_label": "jscccoachingtoola3-2examiningfear",
        "one_line": "Rates a named fear and traces it to the avoidance it drives.",
    }
    base.update(overrides)
    return fc.CatalogEntry(**base)


def _write(path, entries):
    path.write_text(
        yaml.safe_dump([e.to_yaml_dict() for e in entries], sort_keys=False), encoding="utf-8"
    )
    return path


# --- loading and validation -------------------------------------------------

def test_load_catalog_returns_empty_for_a_missing_file(tmp_path):
    assert fc.load_catalog(tmp_path / "nope.yaml") == []


def test_load_catalog_round_trips_every_field(tmp_path):
    original = _entry(
        use_when=("avoidance", "procrastination"), anchor="## Examining Fear",
        source_version=3, live_ready=True, duration_min=10, curated=True,
    )
    path = _write(tmp_path / "catalog.yaml", [original])
    assert fc.load_catalog(path) == [original]


def test_write_catalog_then_load_is_stable(tmp_path):
    entries = [_entry(), _entry(id="wol-1", title="Wheel of Life", kind="assessment")]
    path = tmp_path / "catalog.yaml"
    fc.write_catalog(path, entries)
    assert fc.load_catalog(path) == entries


@pytest.mark.parametrize("field", ["id", "title", "framework", "rel_path", "source_label", "one_line"])
def test_load_catalog_rejects_a_missing_required_field(tmp_path, field):
    raw = _entry().to_yaml_dict()
    raw[field] = ""
    (tmp_path / "catalog.yaml").write_text(yaml.safe_dump([raw]), encoding="utf-8")
    with pytest.raises(fc.CatalogError, match=field):
        fc.load_catalog(tmp_path / "catalog.yaml")


def test_load_catalog_rejects_an_unknown_kind(tmp_path):
    raw = _entry().to_yaml_dict()
    raw["kind"] = "worksheet"
    (tmp_path / "catalog.yaml").write_text(yaml.safe_dump([raw]), encoding="utf-8")
    with pytest.raises(fc.CatalogError, match="worksheet"):
        fc.load_catalog(tmp_path / "catalog.yaml")


def test_load_catalog_rejects_a_duplicate_id(tmp_path):
    """Selection validates its picks by id. A duplicate makes one of the two
    entries unreachable -- the model can name it and get the other one's
    source text embedded in the prompt instead."""
    path = _write(tmp_path / "catalog.yaml", [_entry(), _entry(title="A different activity")])
    with pytest.raises(fc.CatalogError, match="duplicate id"):
        fc.load_catalog(path)


def test_load_catalog_rejects_a_top_level_mapping(tmp_path):
    (tmp_path / "catalog.yaml").write_text(yaml.safe_dump({"entries": []}), encoding="utf-8")
    with pytest.raises(fc.CatalogError, match="expected a list"):
        fc.load_catalog(tmp_path / "catalog.yaml")


# --- merge: hand edits must survive a rebuild -------------------------------

def test_merge_adds_entries_that_are_new():
    existing = [_entry()]
    fresh = _entry(id="wol-1", title="Wheel of Life", framework="Wheel of Life")
    merged, kept = fc.merge(existing, [fresh])
    assert {e.id for e in merged} == {"jscc-a3-2-examining-fear", "wol-1"}
    assert kept == []


def test_merge_overwrites_an_uncurated_entry():
    existing = [_entry(one_line="stale text", source_version=1)]
    rebuilt = [_entry(one_line="fresh text", source_version=2)]
    merged, kept = fc.merge(existing, rebuilt)
    assert [e.one_line for e in merged] == ["fresh text"]
    assert kept == []


def test_merge_never_overwrites_a_curated_entry():
    """The build pass gets entries wrong; a human corrects them and sets
    curated. If a rebuild silently reverted that, every correction would be
    lost on the next corpus refresh and there would be no reason to make one."""
    existing = [_entry(one_line="hand-corrected by Ryan", curated=True, source_version=1)]
    rebuilt = [_entry(one_line="model's guess", source_version=2)]
    merged, kept = fc.merge(existing, rebuilt)
    assert [e.one_line for e in merged] == ["hand-corrected by Ryan"]
    assert kept == ["jscc-a3-2-examining-fear"]


def test_merge_reports_curated_entries_whose_source_moved_on():
    """Reported, not silently kept: a curated entry pinned to a version of the
    source that no longer exists is genuinely stale, and the operator is the
    only one who can judge whether it still holds."""
    existing = [_entry(curated=True, source_version=1), _entry(id="b", curated=True, source_version=1)]
    rebuilt = [_entry(source_version=2), _entry(id="b", source_version=2)]
    _, kept = fc.merge(existing, rebuilt)
    assert kept == ["b", "jscc-a3-2-examining-fear"]


def test_merge_is_deterministic_in_order():
    a = _entry(id="a", framework="Zebra", rel_path="z.md")
    b = _entry(id="b", framework="Alpha", rel_path="a.md")
    merged_one, _ = fc.merge([a], [b])
    merged_two, _ = fc.merge([b], [a])
    assert [e.id for e in merged_one] == [e.id for e in merged_two] == ["b", "a"]


# --- needs_rebuild ----------------------------------------------------------

def test_needs_rebuild_is_true_for_an_uncatalogued_file():
    assert fc.needs_rebuild([], "new.md", 1) is True


def test_needs_rebuild_is_false_when_the_version_is_unchanged():
    entries = [_entry(rel_path="a.md", source_version=2)]
    assert fc.needs_rebuild(entries, "a.md", 2) is False


def test_needs_rebuild_is_true_when_the_source_version_moved():
    entries = [_entry(rel_path="a.md", source_version=2)]
    assert fc.needs_rebuild(entries, "a.md", 3) is True


def test_needs_rebuild_is_true_when_any_entry_from_the_file_is_stale():
    """One file yields several entries. If a rebuild updated only some of them,
    the rest would keep describing text that is no longer there."""
    entries = [
        _entry(id="a", rel_path="guide.md", source_version=3),
        _entry(id="b", rel_path="guide.md", source_version=2),
    ]
    assert fc.needs_rebuild(entries, "guide.md", 3) is True


# --- the SQLite cache -------------------------------------------------------

def test_sync_to_db_writes_every_entry(tmp_path):
    conn = db.init_db(tmp_path / "coach_prep.db")
    try:
        entries = [_entry(use_when=("avoidance",), live_ready=True, duration_min=10)]
        assert fc.sync_to_db(conn, entries) == 1
        row = conn.execute(
            "SELECT id, kind, use_when_json, live_ready, duration_min, curated "
            "FROM framework_catalog"
        ).fetchone()
        assert row[0] == "jscc-a3-2-examining-fear"
        assert row[1] == "activity"
        assert json.loads(row[2]) == ["avoidance"]
        assert (row[3], row[4], row[5]) == (1, 10, 0)
    finally:
        conn.close()


def test_sync_to_db_drops_entries_deleted_from_the_yaml(tmp_path):
    """The YAML is truth. A partial upsert would leave a row behind for an
    entry a human removed, and selection reads the cache."""
    conn = db.init_db(tmp_path / "coach_prep.db")
    try:
        fc.sync_to_db(conn, [_entry(id="a"), _entry(id="b")])
        fc.sync_to_db(conn, [_entry(id="a")])
        remaining = [r[0] for r in conn.execute("SELECT id FROM framework_catalog").fetchall()]
        assert remaining == ["a"]
    finally:
        conn.close()


# --- the rendered index -----------------------------------------------------

def test_render_index_groups_by_framework():
    entries = [
        _entry(id="a", framework="CBT"),
        _entry(id="b", framework="NLP"),
        _entry(id="c", framework="CBT"),
    ]
    rendered = fc.render_index(entries)
    assert rendered.index("### CBT") < rendered.index("### NLP")
    assert rendered.count("### CBT") == 1


def test_render_index_carries_what_selection_needs_to_choose_on():
    entry = _entry(use_when=("avoidance", "stalled-follow-through"), live_ready=True, duration_min=10)
    rendered = fc.render_index([entry])
    assert entry.id in rendered
    assert entry.one_line in rendered
    assert "live-ready" in rendered
    assert "10min" in rendered
    assert "avoidance,stalled-follow-through" in rendered


def test_render_index_omits_absent_optional_fields():
    """A terse line matters: the whole corpus index ships in every selection
    prompt alongside the client material."""
    rendered = fc.render_index([_entry()])
    assert "live-ready" not in rendered
    assert "min |" not in rendered
    assert "when:" not in rendered


def test_render_index_of_the_whole_corpus_stays_within_prompt_budget():
    """The catalog exists so selection can see EVERY option at once. That only
    holds while the index stays small -- roughly 12K tokens for ~200 entries.
    If it outgrows that, the design needs revisiting, not a silent truncation."""
    entries = [
        _entry(
            id=f"entry-{i}", framework=f"Framework {i % 8}",
            use_when=("avoidance", "confidence", "boundaries"),
            live_ready=True, duration_min=15,
        )
        for i in range(200)
    ]
    rendered = fc.render_index(entries)
    approx_tokens = len(rendered) / 4
    assert approx_tokens < 15000, f"catalog index is ~{approx_tokens:.0f} tokens"
