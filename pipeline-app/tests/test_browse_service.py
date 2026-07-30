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
