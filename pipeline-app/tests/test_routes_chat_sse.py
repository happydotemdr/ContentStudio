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


@pytest.fixture
def capture() -> list[dict]:
    """Local to this file -- fixtures aren't shared across test files without a
    conftest.py entry, and none exists here. Identical in shape to
    test_turn_service.py's own `capture` fixture."""
    return []


async def _fake_stream_route(prompt, captured):
    captured.append({"prompt": prompt})
    yield {"type": "result", "result": "done", "total_cost_usd": 0.01, "is_error": False}


def test_chat_on_a_stage_with_a_missing_required_upstream_leaves_an_error_event(tmp_path, monkeypatch):
    """Surfacing: the refusal must be findable after the fact. The route raises
    inside the SSE body generator, so the events row is the only durable signal.

    Standalone app/client, following the pattern already established by
    test_chat_endpoint_returns_409_for_locked_stage below -- the shared
    `client` fixture only declares grounding+ideation stages, neither suited
    to a missing-required-upstream scenario."""
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
    (tdir / "scripting.md").write_text("Read `{{ inputs['ideation'] }}`.\n", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    # Deviation from the brief: scripting's initial status is "locked" (its
    # depends_on is non-empty -- state_machine.compute_initial_status), so the
    # route's own pre-check (is_locked_or_running) would return a clean 409
    # before ever reaching turn_service, and the missing-upstream path this
    # test targets would never execute. Force both rows into the DB state a
    # real (buggy) unlock would leave behind -- ideation "approved" without
    # ever having written an artifact -- so scripting unlocks to "ready" while
    # its one required upstream still resolves to no approved artifact on disk.
    app.state.conn.execute(
        "UPDATE stages SET status = 'approved' WHERE project_id = ? AND stage_id = 'ideation'",
        (project_id,))
    app.state.conn.execute(
        "UPDATE stages SET status = 'ready' WHERE project_id = ? AND stage_id = 'scripting'",
        (project_id,))
    app.state.conn.commit()
    with pytest.raises(Exception):
        with test_client.stream("POST", f"/projects/{project_id}/stages/scripting/chat",
                                data={"message": "go"}) as response:
            list(response.iter_lines())
    rows = app.state.conn.execute(
        "SELECT severity, message FROM events WHERE kind = 'handoff.upstream_missing'").fetchall()
    assert rows and rows[0]["severity"] == "error"


def test_chat_kickoff_prompt_reaches_the_cli_with_the_grounding_pointer(client, monkeypatch, tmp_path, capture):
    """A-04 through the real route: routes/stages.py resolves a pointer for every
    non-grounding stage on an RGS project and hands it to run_stage_turn."""
    test_client, app = client
    (tmp_path / "rgs-briefs").mkdir()
    (tmp_path / "rgs-briefs" / "2026-07-25-abc.md").write_text("brief content", encoding="utf-8")
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    from pipeline_app import grounding_service
    run_dir = tmp_path / "runs" / project["run_id"]
    grounding_service.write_pointer(run_dir / "00-grounding", "rgs-briefs/2026-07-25-abc.md", tmp_path)
    app.state.conn.execute(
        "UPDATE stages SET status = 'approved' WHERE project_id = ? AND stage_id = 'grounding'",
        (project_id,))
    app.state.conn.commit()
    # Overwrite the shared client fixture's stub ideation.md with one that
    # actually renders grounding_pointer, so this test can observe it reaching
    # the prompt -- the fixture's default template is an unconditional "/x".
    (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").write_text(
        "/{{ skill }}\n{% if grounding_pointer %}pointer: `{{ grounding_pointer }}`{% endif %}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(turn_service.cli_runner, "stream_claude_turn",
                        lambda prompt, cwd, resume_session_id, **kw: _fake_stream_route(
                            prompt, capture))
    with test_client.stream("POST", f"/projects/{project_id}/stages/ideation/chat",
                            data={"message": "go"}) as response:
        list(response.iter_text())
    assert "rgs-briefs/" in capture[0]["prompt"]


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
