from pathlib import Path
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from pipeline_app import turn_service
from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: grounding\n    skill: rgs-grounding\n    dir_prefix: \"00\"\n    depends_on: []\n    brand_scope: raisinggoodsports\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    for skill in ("rgs-grounding", "shorts-ideation"):
        skill_dir = tmp_path / ".claude" / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")
    tdir = tmp_path / "pipeline-app" / "stage_templates"
    tdir.mkdir(parents=True)
    (tdir / "grounding.md").write_text("/x", encoding="utf-8")
    (tdir / "ideation.md").write_text("/x", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    # follow_redirects=False: the /projects POST route responds with a 303
    # redirect to /projects/{id}, and these tests read the new project id off
    # the Location header. httpx's TestClient defaults to following redirects,
    # which would swallow that header (see test_routes_stages.py for the same
    # convention already established in Task 13).
    return TestClient(app, follow_redirects=False), app


def test_chat_endpoint_streams_sse_events(client, monkeypatch):
    test_client, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    async def fake_run_stage_turn(*args, **kwargs) -> AsyncIterator[dict]:
        yield {"type": "system", "subtype": "init", "session_id": "s1"}
        yield {"type": "result", "result": "concept brief drafted"}

    monkeypatch.setattr(turn_service, "run_stage_turn", fake_run_stage_turn)

    with test_client.stream(
        "POST", f"/projects/{project_id}/stages/ideation/chat",
        data={"message": "a Short about burnout"},
    ) as response:
        body = "".join(response.iter_text())

    assert "concept brief drafted" in body
    assert "data:" in body


def test_chat_endpoint_returns_409_when_a_turn_is_already_running(client):
    test_client, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    stage_row = app.state.conn.execute(
        "SELECT * FROM stages WHERE project_id = ? AND stage_id = ?", (project_id, "ideation")
    ).fetchone()
    app.state.conn.execute(
        "INSERT INTO turns (stage_row_id, status, created_at, events_path) VALUES (?, 'running', '2026-07-25T12:00:00Z', 'x')",
        (stage_row["id"],),
    )
    app.state.conn.commit()

    resp = test_client.post(
        f"/projects/{project_id}/stages/ideation/chat", data={"message": "hi"},
    )
    assert resp.status_code == 409


def test_chat_endpoint_returns_404_for_unknown_project(client):
    test_client, app = client
    resp = test_client.post(
        "/projects/999999/stages/ideation/chat", data={"message": "hi"},
    )
    assert resp.status_code == 404


def test_chat_endpoint_returns_404_for_unknown_stage(client):
    test_client, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    resp = test_client.post(
        f"/projects/{project_id}/stages/no-such-stage/chat", data={"message": "hi"},
    )
    assert resp.status_code == 404


def test_grounding_chat_writes_to_rgs_briefs_and_pointer(client, monkeypatch, tmp_path):
    test_client, app = client
    (tmp_path / "rgs-briefs").mkdir()
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()

    async def fake_run_stage_turn(*args, **kwargs):
        assert kwargs.get("finalize_artifact") is False
        (tmp_path / "rgs-briefs" / "2026-07-25-abc.md").write_text("brief content", encoding="utf-8")
        yield {"type": "result", "result": "grounding done"}

    from pipeline_app import turn_service
    monkeypatch.setattr(turn_service, "run_stage_turn", fake_run_stage_turn)

    with test_client.stream(
        "POST", f"/projects/{project_id}/stages/grounding/chat", data={"message": "a topic"},
    ) as response:
        list(response.iter_text())

    grounding_dir = tmp_path / "runs" / project["run_id"] / "00-grounding"
    from pipeline_app.grounding_service import read_pointer
    assert read_pointer(grounding_dir) == "rgs-briefs/2026-07-25-abc.md"
    stage_row = app.state.conn.execute(
        "SELECT * FROM stages WHERE project_id = ? AND stage_id = ?", (project_id, "grounding")
    ).fetchone()
    assert stage_row["status"] == "awaiting_review"


def test_chat_endpoint_returns_409_for_locked_stage(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
        "    depends_on: [ideation]\n",
        encoding="utf-8",
    )
    for skill in ("shorts-ideation", "shorts-scripting"):
        skill_dir = tmp_path / ".claude" / "skills" / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")
    tdir = tmp_path / "pipeline-app" / "stage_templates"
    tdir.mkdir(parents=True)
    (tdir / "ideation.md").write_text("/x", encoding="utf-8")
    (tdir / "scripting.md").write_text("/x", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/chat", data={"message": "hi"},
    )
    assert resp.status_code == 409
    assert "locked" in resp.text
