# tests/test_browse_service.py
from pathlib import Path

import pytest

from pipeline_app import browse_service


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
    # This is caught by the ".." segment rejection before the containment
    # check even runs -- with that rejection in place, is_relative_to() is
    # currently unreachable dead code for any input, kept only as
    # defense-in-depth (e.g. if the ".." check is ever loosened). This test
    # still matters: it's the concrete regression check that a naive
    # str.startswith(str(root)) containment check (which "output-old" would
    # wrongly pass, since it shares the "output" prefix) is never
    # reintroduced here.
    with pytest.raises(browse_service.PathSafetyError):
        browse_service.resolve_under_output(root, "../output-old/secret.md")


def _touch(path: Path, text: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_list_children_sorts_folders_then_files(root):
    _touch(root / "zeta.md")
    _touch(root / "alpha" / "notes.md")
    _touch(root / "beta.md")
    entries = browse_service.list_children(root, root)
    assert [e.name for e in entries] == ["alpha", "beta.md", "zeta.md"]
    assert [e.is_dir for e in entries] == [True, False, False]


def test_list_children_excludes_folder_with_no_md_anywhere(root):
    _touch(root / "transcripts" / "raw.txt")
    _touch(root / "thinkers" / "plato.md")
    entries = browse_service.list_children(root, root)
    assert [e.name for e in entries] == ["thinkers"]


def test_list_children_hides_non_md_files(root):
    _touch(root / "notes.md")
    _touch(root / "raw.json")
    _touch(root / "clip.vtt")
    entries = browse_service.list_children(root, root)
    assert [e.name for e in entries] == ["notes.md"]


def test_list_children_case_insensitive_md_suffix(root):
    _touch(root / "NOTES.MD")
    entries = browse_service.list_children(root, root)
    assert [e.name for e in entries] == ["NOTES.MD"]


def test_list_children_rel_path_uses_forward_slashes(root):
    _touch(root / "thinkers" / "plato.md")
    entries = browse_service.list_children(root, root)
    assert entries[0].rel_path == "thinkers"
    child_entries = browse_service.list_children(root / "thinkers", root)
    assert child_entries[0].rel_path == "thinkers/plato.md"


def test_list_children_skips_symlinked_dir(root, tmp_path):
    real = tmp_path / "elsewhere"
    _touch(real / "secret.md")
    try:
        (root / "link").symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks require admin rights / Developer Mode on this platform")
    entries = browse_service.list_children(root, root)
    assert entries == []


def test_list_children_skips_symlinked_file(root, tmp_path):
    real_file = tmp_path / "real.md"
    real_file.write_text("x", encoding="utf-8")
    try:
        (root / "link.md").symlink_to(real_file)
    except OSError:
        pytest.skip("symlinks require admin rights / Developer Mode on this platform")
    entries = browse_service.list_children(root, root)
    assert entries == []
