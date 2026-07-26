from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import artifacts
from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app, follow_redirects=False), tmp_path, app


def test_approve_route_stamps_artifact_final(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    stage_dir = tmp_path / "runs" / project["run_id"] / "01-ideation"
    artifacts.write_artifact(stage_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "body")

    approve_resp = test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    assert approve_resp.status_code in (200, 303, 307)

    meta, _ = artifacts.parse_frontmatter((stage_dir / "artifact.v1.md").read_text(encoding="utf-8"))
    assert meta["status"] == "final"


def test_edit_route_writes_new_version(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    stage_dir = tmp_path / "runs" / project["run_id"] / "01-ideation"
    artifacts.write_artifact(stage_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "old body")

    edit_resp = test_client.post(
        f"/projects/{project_id}/stages/ideation/edit", data={"body": "hand-edited body"}
    )
    assert edit_resp.status_code in (200, 303, 307)
    assert (stage_dir / "artifact.v2.md").exists()
    meta, body = artifacts.parse_frontmatter((stage_dir / "artifact.v2.md").read_text(encoding="utf-8"))
    assert meta["supersedes"] == "artifact.v1.md"
    assert "hand-edited body" in body


def test_approve_route_with_no_artifact_returns_409(client):
    test_client, _tmp_path, _app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    approve_resp = test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    assert approve_resp.status_code == 409
    assert "No artifact to approve" in approve_resp.text


def test_approve_route_unknown_project_404s(client):
    test_client, _tmp_path, _app = client
    resp = test_client.post("/projects/999/stages/ideation/approve")
    assert resp.status_code == 404


def test_approve_route_unknown_stage_404s(client):
    test_client, _tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    unknown_resp = test_client.post(f"/projects/{project_id}/stages/does-not-exist/approve")
    assert unknown_resp.status_code == 404


def test_edit_route_unknown_project_404s(client):
    test_client, _tmp_path, _app = client
    resp = test_client.post(
        "/projects/999/stages/ideation/edit", data={"body": "hand-edited body"}
    )
    assert resp.status_code == 404


def test_edit_route_unknown_stage_404s(client):
    test_client, _tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    unknown_resp = test_client.post(
        f"/projects/{project_id}/stages/does-not-exist/edit", data={"body": "hand-edited body"}
    )
    assert unknown_resp.status_code == 404
