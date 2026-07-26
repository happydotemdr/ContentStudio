import json
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


def test_stage_page_shows_input_output_and_transcript(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "01-ideation"

    artifacts.write_artifact(stage_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "concept brief text")

    events_dir = stage_dir / "events"
    events_dir.mkdir()
    (events_dir / "1.jsonl").write_text(
        json.dumps({"type": "result", "result": "here is your concept brief"}) + "\n",
        encoding="utf-8",
    )

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "concept brief text" in page.text
    assert "here is your concept brief" in page.text


def test_stage_page_unknown_project_returns_404(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    unknown_project_id = project_id + 1000

    page = test_client.get(f"/projects/{unknown_project_id}/stages/ideation")
    assert page.status_code == 404


def test_stage_page_unknown_stage_returns_404(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    page = test_client.get(f"/projects/{project_id}/stages/not-a-real-stage")
    assert page.status_code == 404
