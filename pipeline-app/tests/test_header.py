"""Rendered-template assertions for the P15 UI package.

Despite the filename this covers every template except the two Browse
partials (those live in test_routes_browse.py): the shared shell, the
three-section nav, the stage page, the discovery pages, the skill editor
and doctor. Everything here asserts on rendered HTML through the FastAPI
TestClient -- there is no browser automation in this suite.
"""
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
    skill_dir = tmp_path / ".claude" / "skills" / "shorts-ideation"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "pipeline-app" / "stage_templates").mkdir(parents=True)
    (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").write_text("/x", encoding="utf-8")
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


def test_no_template_references_an_external_host():
    """CLAUDE.md says local-only. A CDN <script> is an undocumented outbound
    dependency with no SRI (D-41) and a silent offline failure (D-42)."""
    from pipeline_app.main import PACKAGE_DIR
    offenders = []
    for path in sorted((PACKAGE_DIR / "templates").rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for scheme in ("https://", "http://", "//unpkg.com"):
            if scheme in text:
                offenders.append(f"{path.name}: {scheme}")
    assert offenders == []


def test_htmx_is_served_from_the_local_static_mount(client: TestClient):
    from pipeline_app.main import PACKAGE_DIR
    vendored = PACKAGE_DIR / "static" / "htmx-2.0.0.min.js"
    assert vendored.is_file(), "htmx must be vendored, not fetched from a CDN"
    assert vendored.stat().st_size > 10_000, "vendored htmx looks truncated"

    resp = client.get("/")
    assert '<script src="/static/htmx-2.0.0.min.js"></script>' in resp.text

    served = client.get("/static/htmx-2.0.0.min.js")
    assert served.status_code == 200
    assert "javascript" in served.headers["content-type"]
