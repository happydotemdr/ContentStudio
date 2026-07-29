from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app)


@pytest.mark.parametrize("url", ["/", "/skills", "/doctor", "/inspector"])
def test_every_page_renders_shared_header(client: TestClient, url: str):
    resp = client.get(url)
    assert resp.status_code == 200
    assert 'class="wordmark"' in resp.text
    assert 'class="top-nav"' in resp.text
    assert 'href="/skills"' in resp.text
    assert 'href="/doctor"' in resp.text
    assert 'href="/inspector"' in resp.text
    assert 'class="status-dot' in resp.text


def test_page_shell_wraps_sidebar_and_main(client: TestClient):
    resp = client.get("/")
    assert 'class="app-shell"' in resp.text
    assert 'class="app-sidebar"' in resp.text
    assert 'class="app-main"' in resp.text


def test_active_nav_marks_the_current_top_nav_link(client: TestClient):
    resp = client.get("/")
    assert '<a href="/" class="active">Projects</a>' in resp.text

    resp = client.get("/skills")
    assert '<a href="/skills" class="active">Skills</a>' in resp.text

    resp = client.get("/doctor")
    assert '<a href="/doctor" class="active">Doctor</a>' in resp.text

    resp = client.get("/inspector")
    assert '<a href="/inspector" class="active">Inspector</a>' in resp.text


def test_project_home_and_stage_page_mark_projects_active_with_breadcrumb(client: TestClient):
    client.post("/projects", data={"slug": "abc", "brand": "generic"})
    home = client.get("/")
    import re
    project_id = re.search(r'/projects/(\d+)', home.text).group(1)

    resp = client.get(f"/projects/{project_id}")
    assert '<a href="/" class="active">Projects</a>' in resp.text
    assert 'class="breadcrumb"' not in resp.text  # no stage_id on the project-home page


@pytest.fixture
def client_with_stage(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), app


def test_stage_page_shows_breadcrumb_with_run_id_and_stage_id(client_with_stage):
    test_client, app = client_with_stage

    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()

    stage_resp = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert stage_resp.status_code == 200
    assert 'class="breadcrumb"' in stage_resp.text
    assert f"{project['run_id']} / ideation" in stage_resp.text
