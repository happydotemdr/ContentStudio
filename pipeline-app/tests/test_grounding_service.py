import os
from pathlib import Path

import pytest
import yaml

from pipeline_app.grounding_service import (
    identify_new_brief,
    read_pointer,
    snapshot_rgs_briefs,
    verify_pointer,
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
    briefs = tmp_path / "rgs-briefs"
    briefs.mkdir()
    (briefs / "2026-07-25-idea.md").write_text("the idea brief", encoding="utf-8")
    stage_dir = tmp_path / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-25-idea.md", tmp_path)
    assert read_pointer(stage_dir) == "rgs-briefs/2026-07-25-idea.md"
    data = yaml.safe_load((stage_dir / "pointer.yaml").read_text(encoding="utf-8"))
    assert len(data["sha256"]) == 64
    assert data["size"] == len(b"the idea brief")
    assert data["written_at"].endswith("+00:00")


def test_read_pointer_none_when_missing(tmp_path: Path):
    assert read_pointer(tmp_path / "00-grounding") is None


def test_write_pointer_survives_a_crash_without_destroying_the_prior_pointer(tmp_path, monkeypatch):
    repo_root = tmp_path
    briefs = repo_root / "rgs-briefs"
    briefs.mkdir()
    (briefs / "a.md").write_text("brief a", encoding="utf-8")
    (briefs / "b.md").write_text("brief b", encoding="utf-8")
    stage_dir = repo_root / "runs" / "r1" / "00-grounding"

    write_pointer(stage_dir, "rgs-briefs/a.md", repo_root)
    before = (stage_dir / "pointer.yaml").read_text(encoding="utf-8")

    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError):
        write_pointer(stage_dir, "rgs-briefs/b.md", repo_root)

    assert (stage_dir / "pointer.yaml").read_text(encoding="utf-8") == before
    assert read_pointer(stage_dir) == "rgs-briefs/a.md"


def _setup(tmp_path, name="2026-08-08-topic.md", text="the brief as approved"):
    briefs = tmp_path / "rgs-briefs"
    briefs.mkdir(exist_ok=True)
    (briefs / name).write_text(text, encoding="utf-8")
    return tmp_path / "runs" / "r1" / "00-grounding"


def test_pointer_records_the_hash_size_and_time_of_its_target(tmp_path):
    """A-80: write_pointer stored a single key, rgs_brief_path -- no sha256, no
    version, no timestamp -- while snapshot_rgs_briefs computed a sha256 for
    every brief and identify_new_brief threw it away."""
    stage_dir = _setup(tmp_path)
    write_pointer(stage_dir, "rgs-briefs/2026-08-08-topic.md", tmp_path)
    data = yaml.safe_load((stage_dir / "pointer.yaml").read_text(encoding="utf-8"))
    assert data["rgs_brief_path"] == "rgs-briefs/2026-08-08-topic.md"
    assert len(data["sha256"]) == 64
    assert data["size"] == len(b"the brief as approved")
    assert data["written_at"].endswith("+00:00")


def test_editing_the_brief_under_an_approved_stage_is_detected(tmp_path):
    """FAULT. The brief an approved grounding stage points at could be
    rewritten with no staleness signal whatsoever."""
    stage_dir = _setup(tmp_path)
    write_pointer(stage_dir, "rgs-briefs/2026-08-08-topic.md", tmp_path)
    (tmp_path / "rgs-briefs" / "2026-08-08-topic.md").write_text(
        "a corrected brief", encoding="utf-8")

    status = verify_pointer(stage_dir, tmp_path)
    assert status.state == "hash_mismatch"
    assert status.recorded_sha256 != status.actual_sha256


def test_an_edited_brief_is_distinguishable_from_an_unchanged_one(tmp_path):
    """DISTINGUISHABILITY."""
    stage_dir = _setup(tmp_path)
    write_pointer(stage_dir, "rgs-briefs/2026-08-08-topic.md", tmp_path)
    assert verify_pointer(stage_dir, tmp_path).state == "ok"
    (tmp_path / "rgs-briefs" / "2026-08-08-topic.md").write_text("x", encoding="utf-8")
    assert verify_pointer(stage_dir, tmp_path).state == "hash_mismatch"


@pytest.mark.parametrize("state,setup", [
    ("no_pointer", lambda sd, rr: None),
    ("missing_target", lambda sd, rr: (rr / "rgs-briefs" / "2026-08-08-topic.md").unlink()),
])
def test_verify_pointer_names_each_broken_state_distinctly(tmp_path, state, setup):
    """SURFACING. Each state is a distinct, reportable value the caller records
    as an event and renders -- not a shared None."""
    stage_dir = _setup(tmp_path)
    if state != "no_pointer":
        write_pointer(stage_dir, "rgs-briefs/2026-08-08-topic.md", tmp_path)
    else:
        stage_dir.mkdir(parents=True, exist_ok=True)
    setup(stage_dir, tmp_path)
    assert verify_pointer(stage_dir, tmp_path).state == state
