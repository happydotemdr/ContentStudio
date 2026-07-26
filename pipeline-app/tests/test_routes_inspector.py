from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path


def test_inspector_form_renders(client):
    test_client, _ = client
    resp = test_client.get("/inspector")
    assert resp.status_code == 200


def test_inspector_parses_frontmatter_and_body(client):
    test_client, tmp_path = client
    fixture = tmp_path / "fixture.md"
    fixture.write_text(
        "---\nstage: shorts-ideation\nversion: 1\n---\n\n# Concept Brief\n\nBody text.\n",
        encoding="utf-8",
    )
    resp = test_client.post("/inspector", data={"path": str(fixture)})
    assert resp.status_code == 200
    assert "shorts-ideation" in resp.text
    assert "Concept Brief" in resp.text
