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


def test_inspector_sanitizes_script_tags_in_rendered_body(client):
    # inspector.html renders body_html with `| safe`, and the inspected file
    # can be any .md on disk (this route is deliberately unallowlisted --
    # see the route's docstring). Without sanitizing the markdown->HTML
    # output here, a <script> in the inspected document would execute with
    # same-origin authority over this app, the same D-47 vector browse_service
    # already closed for /browse.
    test_client, tmp_path = client
    fixture = tmp_path / "malicious.md"
    fixture.write_text(
        "---\nstage: shorts-ideation\nversion: 1\n---\n\n"
        "<script>alert(1)</script>\n\n"
        '<a href="javascript:alert(1)">click</a>\n',
        encoding="utf-8",
    )
    resp = test_client.post("/inspector", data={"path": str(fixture)})
    assert resp.status_code == 200
    assert "alert(1)" not in resp.text
    assert "javascript:" not in resp.text
