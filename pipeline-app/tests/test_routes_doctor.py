from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


def test_doctor_page_renders_without_real_claude_installed(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    client = TestClient(app)
    resp = client.get("/doctor")
    assert resp.status_code == 200
    assert "Claude CLI" in resp.text
