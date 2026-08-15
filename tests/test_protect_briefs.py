import importlib.util
import io
import json
import sys
from pathlib import Path

_HOOK_PATH = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "protect_briefs.py"
_spec = importlib.util.spec_from_file_location("protect_briefs", _HOOK_PATH)
protect_briefs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(protect_briefs)
decide = protect_briefs.decide


def test_edit_under_rgs_briefs_is_denied(tmp_path: Path):
    root = tmp_path
    target = root / "rgs-briefs" / "2026-07-28-my-short-script.md"
    reason = decide("Edit", target, root)
    assert reason is not None
    assert "rgs-briefs" in reason


def test_write_to_new_path_under_rgs_briefs_is_allowed(tmp_path: Path):
    root = tmp_path
    (root / "rgs-briefs").mkdir()
    target = root / "rgs-briefs" / "2026-07-28-my-short-script-v2.md"
    assert decide("Write", target, root) is None


def test_write_to_existing_path_under_rgs_briefs_is_denied(tmp_path: Path):
    root = tmp_path
    briefs = root / "rgs-briefs"
    briefs.mkdir()
    target = briefs / "2026-07-28-my-short-script.md"
    target.write_text("existing", encoding="utf-8")
    reason = decide("Write", target, root)
    assert reason is not None


def test_edit_outside_rgs_briefs_is_allowed(tmp_path: Path):
    root = tmp_path
    target = root / "docs" / "notes.md"
    assert decide("Edit", target, root) is None


def test_write_outside_rgs_briefs_is_allowed_even_if_existing(tmp_path: Path):
    root = tmp_path
    (root / "docs").mkdir()
    target = root / "docs" / "notes.md"
    target.write_text("existing", encoding="utf-8")
    assert decide("Write", target, root) is None


def test_path_outside_project_root_is_allowed(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "elsewhere" / "2026-07-28-my-short-script.md"
    assert decide("Edit", outside, root) is None


def test_edit_of_rgs_briefs_readme_is_allowed(tmp_path: Path):
    root = tmp_path
    target = root / "rgs-briefs" / "README.md"
    assert decide("Edit", target, root) is None


def _hook(monkeypatch, tmp_path, tool_name, file_path) -> int:
    payload = {"tool_name": tool_name, "tool_input": {"file_path": str(file_path)}}
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return protect_briefs.main()


def test_hook_main_denies_a_write_over_an_existing_brief(monkeypatch, tmp_path, capsys):
    """C-96 surfacing test. This hook is the only thing standing between a
    wrong-CWD v1 proposal and a destroyed brief; the deny path must be proven
    end to end, not just in its helper."""
    briefs = tmp_path / "rgs-briefs"
    briefs.mkdir()
    target = briefs / "2026-07-28-my-short-script.md"
    target.write_text("the live brief\n", encoding="utf-8")
    assert _hook(monkeypatch, tmp_path, "Write", target) == 2
    assert "never overwritten" in capsys.readouterr().err


def test_hook_main_accepts_a_relative_path_the_way_the_tool_sends_it(monkeypatch, tmp_path):
    """The wrong-CWD scenario produces a project-relative path. main() resolves
    it against CLAUDE_PROJECT_DIR; if that ever regressed, the mitigation would
    silently stop applying to exactly the case C-96 describes."""
    briefs = tmp_path / "rgs-briefs"
    briefs.mkdir()
    (briefs / "2026-07-28-my-short-script.md").write_text("live\n", encoding="utf-8")
    assert _hook(monkeypatch, tmp_path, "Write",
                 Path("rgs-briefs/2026-07-28-my-short-script.md")) == 2


def test_hook_main_allows_a_genuinely_new_version(monkeypatch, tmp_path):
    """Distinguishability: denying everything would be a different bug."""
    (tmp_path / "rgs-briefs").mkdir()
    assert _hook(monkeypatch, tmp_path, "Write",
                 tmp_path / "rgs-briefs" / "2026-07-28-my-short-script-v2.md") == 0
