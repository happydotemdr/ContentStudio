from pathlib import Path

from pipeline_app.grounding_service import (
    identify_new_brief,
    read_pointer,
    snapshot_rgs_briefs,
    supersede_previous_brief,
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


def test_supersede_archives_previously_pointed_file(tmp_path: Path):
    repo_root = tmp_path
    rgs_briefs = repo_root / "rgs-briefs"
    rgs_briefs.mkdir()
    old_brief = rgs_briefs / "2026-07-25-old.md"
    old_brief.write_text("old content", encoding="utf-8")
    stage_dir = repo_root / "runs" / "x" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-25-old.md")

    supersede_previous_brief(repo_root, stage_dir)

    assert not old_brief.exists()
    archived = rgs_briefs / ".superseded" / "2026-07-25-old.md"
    assert archived.read_text(encoding="utf-8") == "old content"


def test_supersede_is_a_no_op_when_no_pointer(tmp_path: Path):
    stage_dir = tmp_path / "runs" / "x" / "00-grounding"
    stage_dir.mkdir(parents=True)
    supersede_previous_brief(tmp_path, stage_dir)  # should not raise
