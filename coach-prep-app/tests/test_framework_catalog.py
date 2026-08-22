from __future__ import annotations

import json
from pathlib import Path

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


def test_the_real_catalogs_index_fits_the_selection_prompt():
    """Measures the catalog actually committed to this repo, not a synthetic
    one.

    This test asserted against 200 fabricated entries until 2026-08-21 and
    passed comfortably, while the first real build produced 513 entries and an
    index of ~36,600 tokens -- three times the figure the design was written
    around. A budget test that cannot see the real artifact measures nothing.

    The ceiling below is generous because the index has room to grow: the
    selection prompt is the index plus one client's two transcripts and
    fortnight of email, which together run well inside a single context. What
    it rules out is the index quietly becoming the dominant cost, at which
    point "selection sees every option at once" stops being affordable and the
    two-stage design needs revisiting rather than silently degrading."""
    catalog_path = Path(__file__).resolve().parents[1] / "framework_catalog.yaml"
    entries = fc.load_catalog(catalog_path)
    assert entries, "the committed catalog is empty"

    approx_tokens = len(fc.render_index(entries)) / 4
    assert approx_tokens < 60_000, (
        f"the catalog index is ~{approx_tokens:,.0f} tokens across {len(entries)} entries. "
        f"Trim it, or reconsider whether selection can still see the whole corpus at once."
    )


def test_the_committed_catalog_is_loadable_and_internally_consistent():
    """The catalog is a generated artifact committed as source. A malformed
    one fails every client's run at the selection stage, and the failure would
    otherwise only surface on a live wake."""
    catalog_path = Path(__file__).resolve().parents[1] / "framework_catalog.yaml"
    entries = fc.load_catalog(catalog_path)

    assert len(entries) > 100, f"only {len(entries)} entries -- did a build write a partial catalog?"
    assert len({e.id for e in entries}) == len(entries)
    assert all(e.one_line.strip() for e in entries)
    live = [e for e in entries if e.live_ready]
    assert live, "no live-ready entry -- Part 4 has no practice to draw on"


def test_the_committed_catalog_holds_no_reading_list_entries():
    """The reading list reaches stage 2 by its own route, as bundle's
    book_list. A book is not an activity Ryan runs, and resolve() embeds an
    entry's whole source document -- so a pick of one would hand the drafting
    prompt a table of titles and authors as that exercise's instructions."""
    catalog_path = Path(__file__).resolve().parents[1] / "framework_catalog.yaml"
    offenders = [
        e.id for e in fc.load_catalog(catalog_path)
        if "Coaching Book Recommendations" in e.rel_path
    ]
    assert offenders == [], offenders


# --- id collisions across files ---------------------------------------------
#
# Found by the first real build, 2026-08-21: the corpus holds two
# near-duplicate Judge modules ("F2BU_Module_00_The_Judge.docx.md" and the
# same name with " (1)"), and indexing them produced four identical ids --
# judge-three-directions, judge-justification-lies, judge-sage-steps,
# judge-saboteur-assessment. The build crashed on UNIQUE constraint failed
# at sync_to_db. ids can only ever be unique WITHIN a document, because each
# is indexed by its own isolated turn that cannot see the others.

def test_merge_disambiguates_the_same_id_from_two_different_files():
    a = _entry(id="judge-sage-steps", rel_path="Sabatoures/Judge.docx.md")
    b = _entry(id="judge-sage-steps", rel_path="Sabatoures/Judge (1).docx.md")
    merged, _ = fc.merge([], [a, b])
    ids = [e.id for e in merged]
    assert len(ids) == len(set(ids)), ids
    assert "judge-sage-steps" in ids


def test_merge_leaves_a_unique_id_untouched():
    """Disambiguation must be the exception. Rewriting ids that do not collide
    would churn the whole catalog on every rebuild and break curated entries,
    which are matched by id."""
    entries = [_entry(id="a", rel_path="x.md"), _entry(id="b", rel_path="y.md")]
    merged, _ = fc.merge([], entries)
    assert sorted(e.id for e in merged) == ["a", "b"]


def test_merge_disambiguation_is_stable_across_rebuilds():
    """The suffix derives from rel_path, not from ordering or a counter. An id
    that changed between runs would orphan its curated edits."""
    a = _entry(id="dup", rel_path="one.md")
    b = _entry(id="dup", rel_path="two.md")
    first, _ = fc.merge([], [a, b])
    second, _ = fc.merge([], [b, a])
    assert sorted(e.id for e in first) == sorted(e.id for e in second)


def test_merge_keeps_the_same_id_from_the_same_file():
    """Re-indexing one file must not disambiguate its entry against its own
    previous self -- that is a replacement, not a collision."""
    old = _entry(id="dup", rel_path="one.md", source_version=1)
    new = _entry(id="dup", rel_path="one.md", source_version=2)
    merged, _ = fc.merge([old], [new])
    assert [(e.id, e.source_version) for e in merged] == [("dup", 2)]


def test_merged_catalog_always_loads_back(tmp_path):
    """merge feeds write_catalog, and load_catalog rejects duplicate ids. A
    merge that emitted one would write a catalog the app cannot read."""
    colliding = [
        _entry(id="dup", rel_path=f"file-{i}.md", framework=f"F{i}") for i in range(3)
    ]
    merged, _ = fc.merge([], colliding)
    path = tmp_path / "catalog.yaml"
    fc.write_catalog(path, merged)
    assert len(fc.load_catalog(path)) == 3


def test_sync_to_db_accepts_a_merged_catalog_with_collisions(tmp_path):
    """The exact crash: UNIQUE constraint failed: framework_catalog.id."""
    conn = db.init_db(tmp_path / "coach_prep.db")
    try:
        merged, _ = fc.merge([], [
            _entry(id="dup", rel_path="one.md"),
            _entry(id="dup", rel_path="two.md"),
        ])
        assert fc.sync_to_db(conn, merged) == 2
    finally:
        conn.close()


def test_write_catalog_refuses_a_duplicate_id(tmp_path):
    """The first real build crashed at sync_to_db AFTER write_catalog had
    already run, stranding a YAML with duplicate ids. Every subsequent run then
    died at startup in load_catalog, before reaching any code that could fix
    it. Enforcing the invariant at the write boundary makes that unreachable."""
    path = tmp_path / "catalog.yaml"
    with pytest.raises(fc.CatalogError, match="refusing to write"):
        fc.write_catalog(path, [_entry(id="dup", rel_path="a.md"), _entry(id="dup", rel_path="b.md")])
    assert not path.exists()


def test_no_source_label_in_the_committed_catalog_covers_two_documents():
    """A source_label IS the citation gate's allowlist entry and the line the
    closing manifest prints. Two documents sharing one means a draft given
    "To-Be List" can cite the label of "Examining Fear" and pass the gate,
    and Ryan cannot tell from the manifest which document the note read.

    Measured 2026-08-21: slugify_source_label cut filenames at the first dot,
    so the 43 Jay Shetty tools -- whose names carry dots, A3.2, C2.3 -- shared
    just 10 labels between them."""
    from collections import defaultdict

    catalog_path = Path(__file__).resolve().parents[1] / "framework_catalog.yaml"
    by_label = defaultdict(set)
    for entry in fc.load_catalog(catalog_path):
        by_label[entry.source_label].add(entry.rel_path)

    colliding = {label: sorted(paths) for label, paths in by_label.items() if len(paths) > 1}
    assert colliding == {}, colliding


def test_every_committed_source_label_is_matchable_by_the_citation_gate():
    """gates.citation_gate only recognises [a-z0-9-]. A label carrying
    anything else is a tag the gate cannot see at all."""
    import re

    catalog_path = Path(__file__).resolve().parents[1] / "framework_catalog.yaml"
    bad = [
        e.source_label for e in fc.load_catalog(catalog_path)
        if not re.fullmatch(r"[a-z0-9-]+", e.source_label)
    ]
    assert bad == [], bad
