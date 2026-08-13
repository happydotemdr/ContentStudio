import os
from pathlib import Path

import pytest
import yaml

from pipeline_app import grounding_service
from pipeline_app.grounding_service import (
    InvalidPointerError,
    classify_brief_change,
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


def test_classify_brief_change_when_exactly_one_new_file():
    before = {"a.md": "h1", "b.md": "h2"}
    after = {"a.md": "h1", "b.md": "h2", "c.md": "h3"}
    result = classify_brief_change(before, after)
    assert result.brief == "c.md"
    assert result.added == ["c.md"]


def test_classify_brief_change_detects_same_filename_changed_content():
    """A same-day rerun on the same topic overwrites the brief file in place
    -- same filename, new content. The old set-difference check missed this
    entirely (empty diff -> None -> stage wrongly marked no_artifact)."""
    before = {"2026-07-27-topic.md": "h1"}
    after = {"2026-07-27-topic.md": "h2"}
    result = classify_brief_change(before, after)
    assert result.brief == "2026-07-27-topic.md"


def test_a_new_brief_plus_an_unrelated_edit_still_identifies_the_brief():
    """FAULT. A-81: detection was "exactly one file changed, else nothing
    happened". A grounding turn that wrote its brief AND touched any other
    rgs-briefs/*.md -- a typo fix, a superseded-marker edit, an index update --
    returned None and the route recorded a perfectly good turn as no_artifact,
    orphaning the brief and running every downstream RGS stage with
    grounding_pointer=None."""
    before = {"index.md": "h0", "old.md": "h1"}
    after = {"index.md": "h0-edited", "old.md": "h1", "new-brief.md": "h2"}
    result = classify_brief_change(before, after)
    assert result.brief == "new-brief.md"
    assert result.added == ["new-brief.md"]
    assert result.modified == ["index.md"]


def test_zero_briefs_and_two_briefs_are_distinguishable():
    """DISTINGUISHABILITY. The zero-change case correctly reported nothing but
    was indistinguishable from the ambiguous case."""
    nothing = classify_brief_change({"a.md": "h1"}, {"a.md": "h1"})
    ambiguous = classify_brief_change({"a.md": "h1"},
                                      {"a.md": "h1", "b.md": "h2", "c.md": "h3"})
    assert nothing.brief is None and ambiguous.brief is None
    assert nothing.reason != ambiguous.reason
    assert nothing.reason == "no brief was written"
    assert "expected exactly 1" in ambiguous.reason


def test_the_ambiguous_reason_names_every_file_it_saw():
    """SURFACING. "produced N briefs, expected 1" explicitly, rather than
    collapsing to no_artifact."""
    result = classify_brief_change({}, {"b.md": "h2", "c.md": "h3"})
    assert "b.md" in result.reason and "c.md" in result.reason
    assert "2 added" in result.reason


def test_a_brief_written_into_a_subdirectory_is_seen(tmp_path):
    """snapshot_rgs_briefs globbed only the top level (glob, not rglob), so a
    brief in a subdirectory was invisible and produced the same false
    no_artifact."""
    briefs = tmp_path / "rgs-briefs"
    (briefs / "archive").mkdir(parents=True)
    (briefs / "archive" / "nested.md").write_text("nested", encoding="utf-8")
    (briefs / "top.md").write_text("top", encoding="utf-8")
    snap = grounding_service.snapshot_rgs_briefs(briefs)
    assert set(snap) == {"top.md", "archive/nested.md"}


def test_identify_new_brief_is_gone():
    """The old two-outcome API must not survive alongside the new one -- a
    caller left on it would keep collapsing a real brief to no_artifact."""
    assert not hasattr(grounding_service, "identify_new_brief")


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


@pytest.mark.parametrize("content,fragment", [
    ("just a scalar\n", "not a mapping"),
    ("- a\n- b\n", "not a mapping"),
    ("rgs_brief_path: 42\n", "not a string"),
    ("rgs_brief_path: null\n", "not a string"),
    ("other_key: x\n", "not a string"),
    ("rgs_brief_path: 'unterminated\n", "not valid YAML"),
])
def test_a_malformed_pointer_raises_a_named_error_not_attributeerror(tmp_path, content, fragment):
    """A-82: `yaml.safe_load(...) or {}` guarded only the empty case -- a bare
    scalar or a list parsed to a non-mapping and the immediate .get() raised
    AttributeError and a bare 500."""
    stage_dir = tmp_path / "00-grounding"
    stage_dir.mkdir()
    (stage_dir / "pointer.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(InvalidPointerError) as exc:
        read_pointer(stage_dir)
    assert fragment in str(exc.value)


@pytest.mark.parametrize("value", [
    "C:/Windows/System32/drivers/etc/hosts",
    "/etc/passwd",
    "rgs-briefs/../../pipeline-app/pipeline.db",
    "docs/style-library.md",
    "../secrets.md",
])
def test_a_pointer_outside_rgs_briefs_is_refused(tmp_path, value):
    """resolve_latest_artifact joins the stored value with repo_root / pointer,
    and pathlib lets an ABSOLUTE value override the base entirely -- a
    hand-repaired pointer could make the app read and render a file anywhere on
    the machine. write_pointer was non-atomic (A-63), so a hand-repaired
    pointer is a realistic operator action."""
    stage_dir = tmp_path / "00-grounding"
    stage_dir.mkdir()
    (stage_dir / "pointer.yaml").write_text(
        f"rgs_brief_path: {value!r}\n", encoding="utf-8")
    with pytest.raises(InvalidPointerError) as exc:
        read_pointer(stage_dir)
    assert "rgs-briefs" in str(exc.value)


def test_an_absent_pointer_is_distinguishable_from_a_broken_one(tmp_path):
    """DISTINGUISHABILITY: None means "no pointer", never "the pointer is
    garbage"."""
    stage_dir = tmp_path / "00-grounding"
    stage_dir.mkdir()
    assert read_pointer(stage_dir) is None
    (stage_dir / "pointer.yaml").write_text("[]\n", encoding="utf-8")
    with pytest.raises(InvalidPointerError):
        read_pointer(stage_dir)
