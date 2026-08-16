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
