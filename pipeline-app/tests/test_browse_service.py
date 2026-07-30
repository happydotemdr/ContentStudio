# tests/test_browse_service.py
import os
from pathlib import Path

import pytest

from pipeline_app import browse_service, grounding_service


@pytest.fixture
def root(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    return browse_service.output_root(tmp_path)


def test_output_root_resolves_under_repo_root(tmp_path):
    (tmp_path / "output").mkdir()
    result = browse_service.output_root(tmp_path)
    assert result == (tmp_path / "output").resolve()


def test_resolve_under_output_empty_path_returns_root(root):
    assert browse_service.resolve_under_output(root, "") == root


def test_resolve_under_output_nested_path(root):
    nested = root / "thinkers" / "anchorandwave"
    nested.mkdir(parents=True)
    result = browse_service.resolve_under_output(root, "thinkers/anchorandwave")
    assert result == nested.resolve()


def test_resolve_under_output_rejects_dotdot(root):
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "../../../etc")


def test_resolve_under_output_rejects_posix_absolute(root):
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "/etc/passwd")


def test_resolve_under_output_rejects_windows_absolute(root):
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "C:/Windows")


def test_resolve_under_output_rejects_leading_backslash(root):
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "\\Windows\\System32")


def test_resolve_under_output_rejects_drive_relative(root):
    # "C:foo" has a drive but no root -- pathlib's is_absolute() returns
    # False for this form, so it needs its own explicit rejection (a colon
    # anywhere in the input is never valid in a real output/ filename).
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "C:foo")


def test_resolve_under_output_rejects_sibling_prefix_escape(tmp_path):
    (tmp_path / "output").mkdir()
    (tmp_path / "output-old").mkdir()
    (tmp_path / "output-old" / "secret.md").write_text("x", encoding="utf-8")
    root = browse_service.output_root(tmp_path)
    # This particular input is caught by the ".." segment rejection before
    # the containment check even runs -- but is_relative_to() is not truly
    # dead code: a symlink nested inside output/ whose target resolves
    # outside output/ has no ".." segment in the input path at all, yet
    # .resolve() follows the symlink before the containment test runs, so
    # is_relative_to() is exactly what catches that case. This test still
    # matters on its own terms: it's the concrete regression check that a
    # naive str.startswith(str(root)) containment check (which "output-old"
    # would wrongly pass, since it shares the "output" prefix) is never
    # reintroduced here.
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "../output-old/secret.md")


def _touch(path: Path, text: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_list_children_sorts_folders_then_files(root, tmp_path):
    _touch(root / "zeta.md")
    _touch(root / "alpha" / "notes.md")
    _touch(root / "beta.md")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["alpha", "beta.md", "zeta.md"]
    assert [e.is_dir for e in entries] == [True, False, False]


def test_list_children_excludes_folder_with_no_md_anywhere(root, tmp_path):
    _touch(root / "transcripts" / "raw.txt")
    _touch(root / "thinkers" / "plato.md")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["thinkers"]


def test_list_children_hides_non_md_files(root, tmp_path):
    _touch(root / "notes.md")
    _touch(root / "raw.json")
    _touch(root / "clip.vtt")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["notes.md"]


def test_list_children_case_insensitive_md_suffix(root, tmp_path):
    _touch(root / "NOTES.MD")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["NOTES.MD"]


def test_list_children_rel_path_uses_forward_slashes(root, tmp_path):
    _touch(root / "thinkers" / "plato.md")
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries[0].rel_path == "thinkers"
    child_entries = browse_service.list_children(root / "thinkers", root, tmp_path)
    assert child_entries[0].rel_path == "thinkers/plato.md"


def test_list_children_skips_symlinked_dir(root, tmp_path):
    real = tmp_path / "elsewhere"
    _touch(real / "secret.md")
    try:
        (root / "link").symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks require admin rights / Developer Mode on this platform")
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries == []


def test_list_children_skips_symlinked_file(root, tmp_path):
    real_file = tmp_path / "real.md"
    real_file.write_text("x", encoding="utf-8")
    try:
        (root / "link.md").symlink_to(real_file)
    except OSError:
        pytest.skip("symlinks require admin rights / Developer Mode on this platform")
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries == []


def test_list_children_scandir_oserror_raises_folder_read_error(root, tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(os, "scandir", _raise)
    with pytest.raises(browse_service.FolderReadError):
        browse_service.list_children(root, root, tmp_path)


def test_has_md_below_scandir_oserror_returns_false(root, tmp_path, monkeypatch):
    subfolder = root / "sub"
    subfolder.mkdir()
    _touch(subfolder / "note.md")

    real_scandir = os.scandir

    def _raise_for_subfolder(path, *args, **kwargs):
        if Path(path) == subfolder:
            raise OSError("permission denied")
        return real_scandir(path, *args, **kwargs)

    monkeypatch.setattr(os, "scandir", _raise_for_subfolder)
    assert browse_service._has_md_below(subfolder, tmp_path) is False
    # And the unreadable subfolder is excluded from its parent's listing
    # rather than blowing up the whole scan.
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries == []


def test_render_md_file_returns_frontmatter_and_body(tmp_path):
    f = tmp_path / "fixture.md"
    f.write_text("---\nstage: shorts-ideation\n---\n\n# Title\n\nBody text.\n", encoding="utf-8")
    result = browse_service.render_md_file(f)
    assert result["frontmatter"] == {"stage": "shorts-ideation"}
    assert "<h1>Title</h1>" in result["body_html"]


def test_render_md_file_no_frontmatter(tmp_path):
    f = tmp_path / "plain.md"
    f.write_text("# Just a title\n", encoding="utf-8")
    result = browse_service.render_md_file(f)
    assert result["frontmatter"] == {}
    assert "<h1>Just a title</h1>" in result["body_html"]


def test_render_md_file_malformed_yaml_returns_error(tmp_path):
    f = tmp_path / "bad.md"
    f.write_text("---\nstage: [unterminated\n---\n\nBody.\n", encoding="utf-8")
    result = browse_service.render_md_file(f)
    assert result == {"error": "Frontmatter is not valid YAML."}


def test_render_md_file_non_mapping_frontmatter_returns_error(tmp_path):
    f = tmp_path / "listfm.md"
    f.write_text("---\n- one\n- two\n---\n\nBody.\n", encoding="utf-8")
    result = browse_service.render_md_file(f)
    assert result == {"error": "Frontmatter is not a key/value mapping."}


def test_render_md_file_bad_encoding_returns_error(tmp_path):
    f = tmp_path / "binary.md"
    f.write_bytes(b"\xff\xfe\x00\x01not utf-8 \xff")
    result = browse_service.render_md_file(f)
    assert "error" in result
    assert result["error"].startswith("Could not read file:")


def test_render_md_file_oversize_never_reads_content(tmp_path, monkeypatch):
    f = tmp_path / "huge.md"
    f.write_bytes(b"x" * (browse_service.MAX_FILE_BYTES + 1))

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("read_text should not be called for an oversize file")

    monkeypatch.setattr(Path, "read_text", _fail_if_called)
    result = browse_service.render_md_file(f)
    assert result["oversize"] is True
    assert result["cap_mb"] == pytest.approx(5.0)
    assert result["size_mb"] > 5.0
    assert result["abs_path"] == str(f)


def test_render_md_file_stat_error_returns_error_not_500(tmp_path, monkeypatch):
    f = tmp_path / "vanishes.md"
    f.write_text("# Title\n", encoding="utf-8")

    def _raise(*args, **kwargs):
        raise OSError("file vanished")

    monkeypatch.setattr(Path, "stat", _raise)
    result = browse_service.render_md_file(f)
    assert result == {"error": "Could not read file: file vanished"}


def test_runs_root_resolves_under_repo_root(tmp_path):
    (tmp_path / "runs").mkdir()
    result = browse_service.runs_root(tmp_path)
    assert result == (tmp_path / "runs").resolve()


def test_root_path_dispatches_output(tmp_path):
    (tmp_path / "output").mkdir()
    assert browse_service.root_path(tmp_path, "output") == browse_service.output_root(tmp_path)


def test_root_path_dispatches_pipeline(tmp_path):
    (tmp_path / "runs").mkdir()
    assert browse_service.root_path(tmp_path, "pipeline") == browse_service.runs_root(tmp_path)


def test_root_path_rejects_unknown_root(tmp_path):
    with pytest.raises(ValueError):
        browse_service.root_path(tmp_path, "bogus")


def test_resolve_grounding_pointer_returns_target_when_valid(tmp_path):
    (tmp_path / "rgs-briefs").mkdir()
    brief = tmp_path / "rgs-briefs" / "2026-07-28-topic.md"
    brief.write_text("# Brief", encoding="utf-8")
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    grounding_service.write_pointer(pointer_dir, "rgs-briefs/2026-07-28-topic.md")
    result = browse_service.resolve_grounding_pointer(pointer_dir, tmp_path)
    assert result == brief.resolve()


def test_resolve_grounding_pointer_returns_none_when_no_pointer(tmp_path):
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    pointer_dir.mkdir(parents=True)
    assert browse_service.resolve_grounding_pointer(pointer_dir, tmp_path) is None


def test_resolve_grounding_pointer_returns_none_when_target_missing(tmp_path):
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    grounding_service.write_pointer(pointer_dir, "rgs-briefs/does-not-exist.md")
    assert browse_service.resolve_grounding_pointer(pointer_dir, tmp_path) is None


def test_resolve_grounding_pointer_rejects_path_outside_rgs_briefs(tmp_path):
    # A corrupted/hand-edited pointer.yaml pointing elsewhere under repo_root
    # (e.g. another project's runs/ folder) must not be followed, even
    # though the resolved path is still technically "under repo_root". The
    # target here is repo-root-relative ("runs/other-run/secret.md"), same
    # form pointer.yaml actually stores its values in -- not a "../" escape,
    # which is a distinct case already covered by the traversal test below.
    secret = tmp_path / "runs" / "other-run" / "secret.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("secret", encoding="utf-8")
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    grounding_service.write_pointer(pointer_dir, "runs/other-run/secret.md")
    assert browse_service.resolve_grounding_pointer(pointer_dir, tmp_path) is None


def test_resolve_grounding_pointer_rejects_traversal_outside_repo_root(tmp_path):
    pointer_dir = tmp_path / "runs" / "my-run" / "00-grounding"
    grounding_service.write_pointer(pointer_dir, "../../../etc/passwd")
    assert browse_service.resolve_grounding_pointer(pointer_dir, tmp_path) is None


def test_list_children_excludes_raw_output_md(root, tmp_path):
    _touch(root / "01-ideation" / "artifact.v1.md")
    _touch(root / "01-ideation" / "raw_output.md")
    entries = browse_service.list_children(root / "01-ideation", root, tmp_path)
    assert [e.name for e in entries] == ["artifact.v1.md"]


def test_list_children_sorts_artifact_versions_numerically(root, tmp_path):
    _touch(root / "stage" / "artifact.v2.md")
    _touch(root / "stage" / "artifact.v10.md")
    _touch(root / "stage" / "artifact.v1.md")
    entries = browse_service.list_children(root / "stage", root, tmp_path)
    assert [e.name for e in entries] == ["artifact.v1.md", "artifact.v2.md", "artifact.v10.md"]


def test_has_md_below_true_when_valid_grounding_pointer_present(root, tmp_path):
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "topic.md").write_text("# Brief", encoding="utf-8")
    grounding_dir = root / "00-grounding"
    grounding_service.write_pointer(grounding_dir, "rgs-briefs/topic.md")
    assert browse_service._has_md_below(grounding_dir, tmp_path) is True


def test_has_md_below_false_when_only_raw_output_md_present(root, tmp_path):
    # _has_md_below and list_children must agree on raw_output.md: if
    # list_children hides it but _has_md_below still counts it as content,
    # a stage folder containing only raw_output.md would show up as an
    # expandable folder that renders completely empty when opened.
    stage_dir = root / "01-ideation"
    _touch(stage_dir / "raw_output.md")
    assert browse_service._has_md_below(stage_dir, tmp_path) is False
    entries = browse_service.list_children(root, root, tmp_path)
    assert entries == []


def test_has_md_below_false_when_no_pointer_and_no_md(root, tmp_path):
    grounding_dir = root / "00-grounding"
    (grounding_dir / "events").mkdir(parents=True)
    assert browse_service._has_md_below(grounding_dir, tmp_path) is False


def test_has_md_below_false_when_pointer_target_missing(root, tmp_path):
    grounding_dir = root / "00-grounding"
    grounding_service.write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")
    assert browse_service._has_md_below(grounding_dir, tmp_path) is False


def test_list_children_includes_grounding_folder_when_pointer_valid(root, tmp_path):
    # This is the parent-level survival check the Opus review caught as
    # broken: without the _has_md_below fix, "00-grounding" never appears
    # here at all, regardless of what list_children itself would do with it.
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "topic.md").write_text("# Brief", encoding="utf-8")
    grounding_service.write_pointer(root / "00-grounding", "rgs-briefs/topic.md")
    entries = browse_service.list_children(root, root, tmp_path)
    assert [e.name for e in entries] == ["00-grounding"]


def test_list_children_synthesizes_current_brief_entry_for_pointer(root, tmp_path):
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "2026-07-28-topic.md").write_text("# Brief", encoding="utf-8")
    grounding_dir = root / "00-grounding"
    grounding_service.write_pointer(grounding_dir, "rgs-briefs/2026-07-28-topic.md")
    entries = browse_service.list_children(grounding_dir, root, tmp_path)
    assert len(entries) == 1
    assert entries[0].name == "current-brief.md (2026-07-28-topic.md)"
    assert entries[0].rel_path == "00-grounding/pointer.yaml"
    assert entries[0].is_dir is False


def test_list_children_omits_pointer_entry_when_target_missing(root, tmp_path):
    grounding_dir = root / "00-grounding"
    grounding_service.write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")
    entries = browse_service.list_children(grounding_dir, root, tmp_path)
    assert entries == []
