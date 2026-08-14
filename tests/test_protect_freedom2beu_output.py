import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_looks_like_a_write_command_flags_cp_and_mv_aliases():
    assert looks_like_a_write_command('cp x.md Freedom2BeU/converted/y.md') is True
    assert looks_like_a_write_command('mv x.md Freedom2BeU/converted/y.md') is True


def test_looks_like_a_write_command_does_not_false_positive_on_cp_mv_substrings():
    # "cp"/"mv" appear inside these tokens but are not the standalone command word --
    # confirms the whitespace-bounded pattern doesn't create a new false-positive class.
    assert looks_like_a_write_command('cat Freedom2BeU/converted/cpu_report.md') is False
    assert looks_like_a_write_command('cat Freedom2BeU/converted/movie_notes.md') is False


def test_decide_denies_a_differently_cased_converted_path(tmp_path):
    # Windows filesystems are case-insensitive; the path-prefix comparison in decide()
    # must not silently allow a write just because the casing differs from the canonical
    # "Freedom2BeU/converted" spelling.
    project_root = tmp_path
    target = project_root / "Freedom2BeU" / "CONVERTED" / "a.pdf.md"
    reason = decide("Edit", target, project_root)
    assert reason is not None

    target_lower = project_root / "freedom2beu" / "converted" / "a.pdf.md"
    reason_lower = decide("Edit", target_lower, project_root)
    assert reason_lower is not None


def test_decide_denies_a_converted_path_outside_the_project_root(tmp_path):
    """The Windows ACL in lock.py protects the ABSOLUTE cfg.output_root, which
    routinely does not sit under $CLAUDE_PROJECT_DIR -- a git-worktree session
    is rooted at .claude/worktrees/<branch>/, so relative_to() raises
    ValueError. decide() used to return None there, leaving Edit/Write/
    NotebookEdit against the real converted tree with zero hook protection
    while the Bash/PowerShell branch (a root-independent regex) kept working.
    The fallback puts the two branches on equal footing."""
    project_root = tmp_path / ".claude" / "worktrees" / "some-branch"
    project_root.mkdir(parents=True)
    target = Path(r"C:\Projects\ContentStudio\Freedom2BeU\converted\coaching\a.pdf.md")
    reason = decide("Edit", target, project_root)
    assert reason is not None
    assert "read-only by design" in reason


def test_decide_allows_a_non_converted_path_outside_the_project_root(tmp_path):
    """The fallback must not become a blanket deny for everything outside the
    project root -- only paths the converted-tree regex actually matches."""
    project_root = tmp_path / ".claude" / "worktrees" / "some-branch"
    project_root.mkdir(parents=True)
    assert decide("Edit", Path(r"C:\Projects\ContentStudio\Freedom2BeU\_tmp\job-1\staged.md"), project_root) is None
    assert decide("Edit", Path(r"C:\Projects\SomethingElse\notes.md"), project_root) is None


def test_decide_denies_a_converted_path_nested_below_the_project_root(tmp_path):
    """Same fallback also covers the in-project-root-but-not-at-depth-2 case:
    the prefix check only looks at rel.parts[:2]."""
    project_root = tmp_path
    target = project_root / "nested" / "Freedom2BeU" / "converted" / "a.md"
    assert decide("Edit", target, project_root) is not None


def test_decide_ignores_non_write_tools_even_under_converted(tmp_path):
    project_root = tmp_path
    target = project_root / "Freedom2BeU" / "converted" / "a.pdf.md"
    assert decide("Read", target, project_root) is None


@pytest.mark.allow_subprocess
def test_notebook_edit_via_main_denies_converted_path(tmp_path):
    """The real NotebookEdit tool payload uses "notebook_path", not "file_path". This
    exercises main() end-to-end (not just decide()) via a real subprocess invocation
    of the hook script -- a plain local Python interpreter running this repo's own
    hook file, no network, no billed API -- piping a NotebookEdit payload on stdin, to
    prove main() actually resolves the path for that tool and denies it, not just that
    decide() supports it.
    """
    project_root = tmp_path
    notebook_path = project_root / "Freedom2BeU" / "converted" / "nb.ipynb"
    payload = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(notebook_path)},
    }
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_root)
    result = subprocess.run(
        [sys.executable, str(_HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "converted" in result.stderr


@pytest.mark.allow_subprocess
def test_notebook_edit_via_main_allows_path_outside_converted(tmp_path):
    """Same real-subprocess justification as test_notebook_edit_via_main_denies_converted_path
    above -- confirms the NotebookEdit path resolves through main() without a false positive
    on a path outside Freedom2BeU/converted/.
    """
    project_root = tmp_path
    notebook_path = project_root / "notebooks" / "nb.ipynb"
    payload = {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": str(notebook_path)},
    }
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_root)
    result = subprocess.run(
        [sys.executable, str(_HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
