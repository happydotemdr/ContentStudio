import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


def _scaffold_skill(root: Path, name: str) -> None:
    skill_dir = root / ".claude" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")


def _scaffold_template(root: Path, stage_id: str) -> None:
    tdir = root / "pipeline-app" / "stage_templates"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / f"{stage_id}.md").write_text("/x", encoding="utf-8")


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: [ideation]\n",
        encoding="utf-8",
    )
    _scaffold_skill(tmp_path, "shorts-ideation")
    _scaffold_skill(tmp_path, "shorts-scripting")
    _scaffold_template(tmp_path, "ideation")
    _scaffold_template(tmp_path, "scripting")
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


def test_create_project_with_unusable_slug_returns_400(client: TestClient, tmp_path: Path):
    before = {p.name for p in tmp_path.parent.iterdir()}
    response = client.post("/projects", data={"slug": "../..", "brand": "generic"})
    assert response.status_code == 400
    assert {p.name for p in tmp_path.parent.iterdir()} == before
    assert not (tmp_path / "runs").exists()


def test_create_project_with_traversal_slug_stays_inside_runs(client: TestClient, tmp_path: Path):
    before = {p.name for p in tmp_path.parent.iterdir()}
    response = client.post("/projects", data={"slug": "../../pwned", "brand": "generic"})
    assert response.status_code in (200, 303, 307)
    # nothing created outside the repo root
    assert {p.name for p in tmp_path.parent.iterdir()} == before
    runs_root = (tmp_path / "runs").resolve()
    created = list(runs_root.iterdir())
    assert len(created) == 1
    assert created[0].resolve().parent == runs_root
    assert ".." not in created[0].name


def test_project_home_unknown_project_returns_404(client: TestClient):
    response = client.get("/projects/9999")
    assert response.status_code == 404


def test_project_home_shows_stage_names(client: TestClient):
    client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    listing = client.get("/")
    # extract the project id from the link the template renders
    match = re.search(r'/projects/(\d+)', listing.text)
    assert match is not None
    project_id = match.group(1)
    home = client.get(f"/projects/{project_id}")
    assert home.status_code == 200
    assert "ideation" in home.text
    assert "scripting" in home.text


def test_project_home_groups_parallel_stages_and_shows_specialist(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".claude" / "skills" / "elevenlabs-audio").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "elevenlabs-audio" / "SKILL.md").write_text(
        "---\nname: elevenlabs-audio\n---\n", encoding="utf-8",
    )
    (tmp_path / ".claude" / "skills" / "midjourney-prompting").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "midjourney-prompting" / "SKILL.md").write_text(
        "---\nname: midjourney-prompting\n---\n", encoding="utf-8",
    )
    _scaffold_skill(tmp_path, "shorts-scripting")
    _scaffold_skill(tmp_path, "voiceover-brief")
    _scaffold_skill(tmp_path, "visual-prompts")
    _scaffold_template(tmp_path, "scripting")
    _scaffold_template(tmp_path, "voiceover")
    _scaffold_template(tmp_path, "visual")
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: []\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    specialist: elevenlabs-audio\n"
        "    specialist_mode: manual\n    dir_prefix: \"03\"\n    depends_on: [scripting]\n"
        "  - id: visual\n    skill: visual-prompts\n    specialist: midjourney-prompting\n"
        "    specialist_mode: auto\n    dir_prefix: \"03\"\n    depends_on: [scripting]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app)

    test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    listing = test_client.get("/")
    match = re.search(r'/projects/(\d+)', listing.text)
    assert match is not None
    project_id = match.group(1)

    home = test_client.get(f"/projects/{project_id}")
    assert home.status_code == 200
    assert "elevenlabs-audio" in home.text
    assert "midjourney-prompting" in home.text
    # scripting is its own step; voiceover+visual share dir_prefix "03" and
    # must render inside ONE grouped step, not two.
    assert home.text.count('class="pipeline-step"') == 2


def test_project_home_nav_has_no_current_highlight(client: TestClient):
    client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"})
    listing = client.get("/")
    match = re.search(r'/projects/(\d+)', listing.text)
    project_id = match.group(1)
    home = client.get(f"/projects/{project_id}")
    # project-home has no "current" stage, so no stage should render the
    # current-highlight class — checked as the exact class token (not a bare
    # "current" substring, which could false-positive on unrelated text).
    assert 'class="pipeline-stage current"' not in home.text


def test_overlong_slug_returns_400_not_500(client: TestClient):
    resp = client.post("/projects", data={"slug": "x" * 200, "brand": "generic"},
                       follow_redirects=False)
    assert resp.status_code == 400
    assert "60" in resp.text


def test_a_failed_creation_is_a_named_error_and_leaves_an_events_row(client, monkeypatch):
    real_mkdir = Path.mkdir
    monkeypatch.setattr(Path, "mkdir",
                        lambda self, *a, **k: (_ for _ in ()).throw(OSError(28, "no space")))

    resp = client.post("/projects", data={"slug": "why-kids-quit", "brand": "generic"},
                       follow_redirects=False)
    monkeypatch.undo()

    assert resp.status_code == 500
    assert "no space" in resp.text            # not a bare traceback
    rows = client.app.state.conn.execute(
        "SELECT * FROM events WHERE kind = 'project.create_failed'").fetchall()
    assert len(rows) == 1 and rows[0]["severity"] == "error"
