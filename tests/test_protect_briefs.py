import importlib.util
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
