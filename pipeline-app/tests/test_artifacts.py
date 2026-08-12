import os
from pathlib import Path

import pytest

from pipeline_app import artifacts
from pipeline_app.artifacts import (
    _atomic_write_text,
    ArtifactExistsError,
    compute_sha256,
    latest_artifact_path,
    next_version_number,
    parse_frontmatter,
    render_frontmatter,
    resolve_latest_artifact,
    stamp_final,
    write_artifact,
)
from pipeline_app.grounding_service import write_pointer


def test_render_and_parse_frontmatter_roundtrip():
    meta = {"schema_version": 1, "stage": "shorts-ideation", "depends_on": []}
    text = render_frontmatter(meta, "# Concept Brief\n\nBody text here.")
    parsed_meta, body = parse_frontmatter(text)
    assert parsed_meta["schema_version"] == 1
    assert parsed_meta["stage"] == "shorts-ideation"
    assert "Concept Brief" in body


def test_parse_frontmatter_on_plain_text_returns_empty_meta():
    meta, body = parse_frontmatter("just plain text, no frontmatter")
    assert meta == {}
    assert body == "just plain text, no frontmatter"


def test_next_version_number_empty_dir_is_one(tmp_path: Path):
    assert next_version_number(tmp_path) == 1


def test_next_version_number_increments(tmp_path: Path):
    (tmp_path / "artifact.v1.md").write_text("x", encoding="utf-8")
    (tmp_path / "artifact.v2.md").write_text("x", encoding="utf-8")
    assert next_version_number(tmp_path) == 3


def test_latest_artifact_path_picks_highest_version(tmp_path: Path):
    (tmp_path / "artifact.v1.md").write_text("old", encoding="utf-8")
    (tmp_path / "artifact.v2.md").write_text("new", encoding="utf-8")
    assert latest_artifact_path(tmp_path).name == "artifact.v2.md"


def test_latest_artifact_path_none_when_empty(tmp_path: Path):
    assert latest_artifact_path(tmp_path) is None


def test_write_artifact_creates_versioned_file(tmp_path: Path):
    path = write_artifact(tmp_path, 1, {"stage": "shorts-ideation"}, "hello body")
    assert path.name == "artifact.v1.md"
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["stage"] == "shorts-ideation"
    assert "hello body" in body


def test_compute_sha256_is_stable(tmp_path: Path):
    f = tmp_path / "a.md"
    f.write_text("same content", encoding="utf-8")
    h1 = compute_sha256(f)
    h2 = compute_sha256(f)
    assert h1 == h2
    assert len(h1) == 64


def test_stamp_final_sets_status_and_hash_reflects_stamped_content(tmp_path: Path):
    path = write_artifact(tmp_path, 1, {"status": "draft"}, "content")
    hash_before_stamp = compute_sha256(path)
    stamp_final(path, "2026-07-25T00:00:00+00:00")
    meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert meta["finalized_at"] == "2026-07-25T00:00:00+00:00"
    hash_after_stamp = compute_sha256(path)
    # The file's bytes changed because of the stamp, so the hash a downstream
    # stage would record must be taken AFTER stamping, never before.
    assert hash_before_stamp != hash_after_stamp


def test_resolve_latest_artifact_delegates_for_non_grounding_stage(tmp_path: Path):
    stage_dir = tmp_path / "01-ideation"
    write_artifact(stage_dir, 1, {"stage": "shorts-ideation"}, "body")
    resolved = resolve_latest_artifact(tmp_path, "ideation", stage_dir)
    assert resolved == stage_dir / "artifact.v1.md"


def test_resolve_latest_artifact_grounding_resolves_via_pointer(tmp_path: Path):
    rgs_briefs = tmp_path / "rgs-briefs"
    rgs_briefs.mkdir()
    brief = rgs_briefs / "2026-07-27-x.md"
    brief.write_text("---\nstatus: candidate\n---\n\nbody", encoding="utf-8")
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/2026-07-27-x.md")

    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) == brief


def test_resolve_latest_artifact_grounding_no_pointer_returns_none(tmp_path: Path):
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    stage_dir.mkdir(parents=True)
    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) is None


def test_resolve_latest_artifact_grounding_pointer_target_missing_returns_none(tmp_path: Path):
    """The pointer file exists but the brief it names was deleted or never
    written -- must return None, not raise. This is the exact case the old
    inline branches in approval_service.py and routes/stages.py got wrong in
    two of three copies (they skipped the .exists() check)."""
    stage_dir = tmp_path / "runs" / "r1" / "00-grounding"
    write_pointer(stage_dir, "rgs-briefs/does-not-exist.md")
    assert resolve_latest_artifact(tmp_path, "grounding", stage_dir) is None


def test_atomic_write_leaves_prior_bytes_intact_when_the_write_dies_midway(tmp_path, monkeypatch):
    """A-63: the whole point. Path.write_text opens "w", truncating the target
    to zero before a byte of new content lands. Kill the write partway and the
    previous content must still be there, in full, and still parseable."""
    target = tmp_path / "artifact.v1.md"
    original = "---\nstatus: final\nversion: 1\n---\n\napproved body\n"
    target.write_text(original, encoding="utf-8")

    real_fsync = os.fsync

    def die_after_partial_write(fd):
        real_fsync(fd)
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", die_after_partial_write)

    with pytest.raises(OSError):
        _atomic_write_text(target, "---\nstatus: final\nversion: 2\n---\n\nnew body\n")

    assert target.read_text(encoding="utf-8") == original
    meta, body = artifacts.parse_frontmatter(target.read_text(encoding="utf-8"))
    assert meta["status"] == "final"
    assert "approved body" in body


def test_atomic_write_leaves_no_temp_file_behind_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "artifact.v1.md"
    target.write_text("original", encoding="utf-8")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))

    with pytest.raises(OSError):
        _atomic_write_text(target, "replacement")

    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [target]


def test_write_artifact_refuses_to_overwrite_an_existing_version(tmp_path):
    """A-65/A-73: write_text overwrote silently, so two callers that computed
    the same N discarded one artifact version and its recorded gate results
    with no error surfaced anywhere."""
    write_artifact(tmp_path, 1, {"stage": "shorts-styleboard"}, "the real world lock")

    with pytest.raises(ArtifactExistsError) as exc:
        write_artifact(tmp_path, 1, {"stage": "shorts-styleboard"}, "clobber")

    assert "artifact.v1.md" in str(exc.value)
    assert "the real world lock" in (tmp_path / "artifact.v1.md").read_text(encoding="utf-8")


def test_write_artifact_uses_the_atomic_primitive(tmp_path, monkeypatch):
    calls = []
    real = artifacts._atomic_write_text
    monkeypatch.setattr(
        artifacts, "_atomic_write_text",
        lambda p, t: (calls.append(p), real(p, t))[1],
    )
    write_artifact(tmp_path, 1, {"stage": "x"}, "body")
    assert (tmp_path / "artifact.v1.md") in calls
