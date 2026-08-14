import importlib.util
from pathlib import Path

_HOOK_PATH = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "protect_freedom2beu_output.py"
_spec = importlib.util.spec_from_file_location("protect_freedom2beu_output", _HOOK_PATH)
protect_freedom2beu_output = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(protect_freedom2beu_output)
decide = protect_freedom2beu_output.decide
looks_like_a_write_command = protect_freedom2beu_output.looks_like_a_write_command


def test_edit_under_converted_is_denied(tmp_path):
    project_root = tmp_path
    target = project_root / "Freedom2BeU" / "converted" / "a.pdf.md"
    reason = decide("Edit", target, project_root)
    assert reason is not None


def test_write_to_a_new_file_under_converted_is_denied(tmp_path):
    project_root = tmp_path
    target = project_root / "Freedom2BeU" / "converted" / "new.md"
    reason = decide("Write", target, project_root)
    assert reason is not None


def test_edit_outside_freedom2beu_is_allowed(tmp_path):
    project_root = tmp_path
    target = project_root / "docs" / "something.md"
    reason = decide("Edit", target, project_root)
    assert reason is None


def test_edit_under_freedom2beu_tmp_staging_is_allowed(tmp_path):
    project_root = tmp_path
    target = project_root / "Freedom2BeU" / "_tmp" / "job-1" / "staged.md"
    reason = decide("Edit", target, project_root)
    assert reason is None


def test_looks_like_a_write_command_flags_redirection_into_converted():
    assert looks_like_a_write_command('echo "x" > Freedom2BeU/converted/a.pdf.md') is True
    assert looks_like_a_write_command('Remove-Item Freedom2BeU/converted/a.pdf.md') is True


def test_looks_like_a_write_command_flags_append_redirection_into_converted():
    assert looks_like_a_write_command('echo "x" >> Freedom2BeU/converted/a.pdf.md') is True


def test_looks_like_a_write_command_allows_a_read_only_command():
    assert looks_like_a_write_command('cat Freedom2BeU/converted/a.pdf.md') is False
    assert looks_like_a_write_command('python doc_ingest/query.py --search "x"') is False
