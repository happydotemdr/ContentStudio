from pathlib import Path

import pytest

from pipeline_app.main import create_app


@pytest.fixture
def repo_root(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    return tmp_path


def test_cli_available_true_when_binary_found(repo_root: Path, monkeypatch):
    monkeypatch.setattr(
        "pipeline_app.preflight.check_cli_available",
        lambda: {"available": True, "path": r"C:\fake\claude.CMD", "error": None},
    )
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    assert app.state.cli_available is True


def test_cli_available_false_when_missing(repo_root: Path, monkeypatch):
    monkeypatch.setattr(
        "pipeline_app.preflight.check_cli_available",
        lambda: {"available": False, "path": None, "error": "not found"},
    )
    app = create_app(repo_root=repo_root, db_path=repo_root / "pipeline.db")
    assert app.state.cli_available is False
