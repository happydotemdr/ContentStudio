from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: [ideation]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app)


def test_get_root_lists_no_projects_initially(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "No projects yet" in response.text


def test_create_project_then_appears_in_list(client: TestClient):
    response = client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    assert response.status_code in (200, 303, 307)
    listing = client.get("/")
    assert "why-kids-quit" in listing.text


def test_project_home_shows_stage_names(client: TestClient):
    client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    listing = client.get("/")
    # extract the project id from the link the template renders
    import re
    match = re.search(r'/projects/(\d+)', listing.text)
    assert match is not None
    project_id = match.group(1)
    home = client.get(f"/projects/{project_id}")
    assert home.status_code == 200
    assert "ideation" in home.text
    assert "scripting" in home.text
