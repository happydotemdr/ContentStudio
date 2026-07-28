from pathlib import Path

from pipeline_app.grounding_service import (
    identify_new_brief,
    read_pointer,
    snapshot_rgs_briefs,
    write_pointer,
)


def test_snapshot_returns_filename_to_content_hash(tmp_path: Path):
    import hashlib
    a = tmp_path / "2026-07-25-a.md"
    a.write_text("x", encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text("x", encoding="utf-8")
    expected_hash = hashlib.sha256(b"x").hexdigest()
    snap = snapshot_rgs_briefs(tmp_path)
    assert snap == {"2026-07-25-a.md": expected_hash, "README.md": expected_hash}


def test_identify_new_brief_when_exactly_one_new_file():
    before = {"a.md": "h1", "b.md": "h2"}
    after = {"a.md": "h1", "b.md": "h2", "c.md": "h3"}
    assert identify_new_brief(before, after) == "c.md"


def test_identify_new_brief_returns_none_when_zero_new_files():
    assert identify_new_brief({"a.md": "h1"}, {"a.md": "h1"}) is None


def test_identify_new_brief_returns_none_when_ambiguous():
    before = {"a.md": "h1"}
    after = {"a.md": "h1", "b.md": "h2", "c.md": "h3"}
    assert identify_new_brief(before, after) is None


def test_identify_new_brief_detects_same_filename_changed_content():
    """A same-day rerun on the same topic overwrites the brief file in place
    -- same filename, new content. The old set-difference check missed this
    entirely (empty diff -> None -> stage wrongly marked no_artifact)."""
    before = {"2026-07-27-topic.md": "h1"}
    after = {"2026-07-27-topic.md": "h2"}
    assert identify_new_brief(before, after) == "2026-07-27-topic.md"


def test_write_and_read_pointer_roundtrip(tmp_path: Path):
    stage_dir = tmp_path / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-25-idea.md")
    assert read_pointer(stage_dir) == "rgs-briefs/2026-07-25-idea.md"


def test_read_pointer_none_when_missing(tmp_path: Path):
    assert read_pointer(tmp_path / "00-grounding") is None
