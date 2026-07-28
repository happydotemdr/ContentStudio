import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import artifacts, db as db_mod
from pipeline_app.grounding_service import write_pointer
from pipeline_app.main import create_app
from pipeline_app.state_machine import StageStatus


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: grounding\n    skill: rgs-grounding\n    dir_prefix: \"00\"\n"
        "    depends_on: []\n    brand_scope: raisinggoodsports\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
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
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "here is your concept brief"},
        ]}}),
        json.dumps({"type": "result", "result": "here is your concept brief"}),
    ]
    (events_dir / "1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "concept brief text" in page.text
    assert "here is your concept brief" in page.text


def test_stage_page_transcript_shows_intermediate_assistant_and_tool_use_events(client):
    """_load_transcript must not wait for the final `result` event -- a
    reloaded page after an aborted turn should still show whatever the
    assistant said/did before the connection dropped, not an empty panel."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "01-ideation"
    events_dir = stage_dir / "events"
    events_dir.mkdir(parents=True)
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Reading the concept brief first."},
        ]}}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "x.md"}},
        ]}}),
    ]
    (events_dir / "1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "Reading the concept brief first." in page.text
    # Not "Read" -- that word already appears in the text block above ("Reading
    # the concept brief"), so a bare substring check would pass even if the
    # tool_use branch were never implemented. "↪ Read" is what only the
    # tool_use branch produces.
    assert "↪ Read" in page.text


def test_stage_page_transcript_does_not_duplicate_final_assistant_text(client):
    """Task 4 added rendering of assistant-type events' text blocks but the
    pre-existing `result` event was still being appended as a separate
    transcript entry too -- and the final assistant event's text is
    byte-identical to the result event's `result` string on a real recorded
    turn, so the final answer rendered twice. The assistant text block(s)
    already cover the result event's content; _load_transcript must not
    append a second entry for it."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "01-ideation"
    events_dir = stage_dir / "events"
    events_dir.mkdir(parents=True)
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "here is your concept brief"},
        ]}}),
        json.dumps({"type": "result", "result": "here is your concept brief"}),
    ]
    (events_dir / "1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert page.text.count("here is your concept brief") == 1


def test_stage_page_shows_grounding_output_via_pointer(client):
    """Grounding writes its real output to rgs-briefs/, referenced by a
    pointer.yaml -- not artifact.v{N}.md like every other stage. The stage
    page's output panel must resolve through the pointer, same as approve."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "rgs", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    grounding_dir = run_dir / "00-grounding"
    rgs_briefs_dir = tmp_path / "rgs-briefs"
    rgs_briefs_dir.mkdir(parents=True)
    (rgs_briefs_dir / "2026-07-27-example-brief.md").write_text(
        "---\nstatus: candidate\n---\n\nBrief body text", encoding="utf-8"
    )
    write_pointer(grounding_dir, "rgs-briefs/2026-07-27-example-brief.md")

    page = test_client.get(f"/projects/{project_id}/stages/grounding")
    assert page.status_code == 200
    assert "Brief body text" in page.text


def test_stage_page_shows_grounding_companion_as_input_for_downstream_stage(client):
    """Ideation has no formal `depends_on` (grounding is an optional RGS
    companion, not a hard pipeline dependency -- see pipeline.yaml), but the
    chat/turn_service path already hands grounding's brief to the AI via
    grounding_pointer (routes/stages.py's stage_chat, turn_service.py:116).
    The Input panel must show the same companion brief, or the page looks
    like grounding produced nothing usable even after being approved."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "rgs", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    grounding_dir = run_dir / "00-grounding"
    rgs_briefs_dir = tmp_path / "rgs-briefs"
    rgs_briefs_dir.mkdir(parents=True)
    (rgs_briefs_dir / "2026-07-27-example-brief.md").write_text(
        "---\nstatus: candidate\n---\n\nGrounding companion body text", encoding="utf-8"
    )
    write_pointer(grounding_dir, "rgs-briefs/2026-07-27-example-brief.md")

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "Grounding companion body text" in page.text


def test_stage_page_grounding_output_pointer_target_missing_shows_no_output(client):
    """Mirrors Task 2's approval_service fix: a dangling pointer.yaml must
    render as no output, never crash the page."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "rgs", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    grounding_dir = run_dir / "00-grounding"
    write_pointer(grounding_dir, "rgs-briefs/does-not-exist.md")

    page = test_client.get(f"/projects/{project_id}/stages/grounding")
    assert page.status_code == 200
    assert "No output yet." in page.text


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


def _generic_project_id(test_client) -> int:
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    return int(resp.headers["location"].rsplit("/", 1)[-1])


def test_stage_page_for_stage_not_applicable_to_brand_returns_404(client):
    """`grounding` is brand_scope: raisinggoodsports, so a generic project has
    no grounding stage row — the page must 404, not render a phantom stage."""
    test_client, _tmp_path, _app = client
    project_id = _generic_project_id(test_client)

    page = test_client.get(f"/projects/{project_id}/stages/grounding")
    assert page.status_code == 404


def test_stage_chat_for_stage_not_applicable_to_brand_returns_404(client):
    test_client, _tmp_path, _app = client
    project_id = _generic_project_id(test_client)

    resp = test_client.post(
        f"/projects/{project_id}/stages/grounding/chat", data={"message": "go"}
    )
    assert resp.status_code == 404


def test_approve_for_stage_not_applicable_to_brand_returns_404(client):
    test_client, _tmp_path, _app = client
    project_id = _generic_project_id(test_client)

    resp = test_client.post(f"/projects/{project_id}/stages/grounding/approve")
    assert resp.status_code == 404


def test_edit_for_stage_not_applicable_to_brand_returns_404(client):
    test_client, _tmp_path, _app = client
    project_id = _generic_project_id(test_client)

    resp = test_client.post(
        f"/projects/{project_id}/stages/grounding/edit", data={"body": "x"}
    )
    assert resp.status_code == 404


def test_stage_page_shows_stale_override_cue_near_approve_button(client):
    """A stale stage can still be approved directly (accepted, sound
    behavior -- see progress ledger), but nothing in the UI previously
    signalled that doing so overrides the staleness cascade rather than
    being a fresh approval. Text cue only, no confirm step."""
    test_client, tmp_path, app = client
    project_id = _generic_project_id(test_client)
    stage_row = db_mod.get_stage(app.state.conn, project_id, "ideation")
    db_mod.update_stage_status(app.state.conn, stage_row["id"], StageStatus.STALE.value)

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "override" in page.text.lower()


def test_stage_page_hides_stale_override_cue_for_non_stale_stage(client):
    test_client, tmp_path, app = client
    project_id = _generic_project_id(test_client)

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "override" not in page.text.lower()


def test_stage_page_shows_pipeline_nav_with_current_highlight(client):
    test_client, _tmp_path, _app = client
    project_id = _generic_project_id(test_client)

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert 'class="pipeline-stage current"' in page.text
    assert "grounding" not in page.text
    assert page.text.count('class="pipeline-step"') == 1


def test_stage_page_shows_grouped_parallel_pair_in_nav(tmp_path: Path, monkeypatch):
    # The shared `client` fixture's pipeline.yaml has no parallel pair, so it
    # can never exercise grouping through the stage route — this test uses
    # its own pipeline.yaml specifically to cover that gap.
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".claude" / "skills" / "elevenlabs-audio").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "elevenlabs-audio" / "SKILL.md").write_text(
        "---\nname: elevenlabs-audio\n---\n", encoding="utf-8",
    )
    (tmp_path / ".claude" / "skills" / "midjourney-prompting").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "midjourney-prompting" / "SKILL.md").write_text(
        "---\nname: midjourney-prompting\n---\n", encoding="utf-8",
    )
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
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    page = test_client.get(f"/projects/{project_id}/stages/voiceover")
    assert page.status_code == 200
    assert "elevenlabs-audio" in page.text
    assert "midjourney-prompting" in page.text
    assert "manual hand-off" in page.text
    assert "auto-delegated" in page.text
    # scripting is its own step; voiceover+visual share dir_prefix "03" and
    # must render inside ONE grouped step, not two.
    assert page.text.count('class="pipeline-step"') == 2
    # voiceover is the current stage on this page
    assert 'class="pipeline-stage current"' in page.text


def test_stage_page_shows_all_upstream_inputs_not_just_first(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "  - id: assembly\n    skill: shorts-assembly\n    dir_prefix: \"04\"\n"
        "    depends_on: [voiceover, visual]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]

    artifacts.write_artifact(run_dir / "03-voiceover", 1, {"stage": "voiceover-brief"}, "voiceover brief text")
    artifacts.write_artifact(run_dir / "03-visual", 1, {"stage": "visual-prompts"}, "visual prompt sheet text")

    page = test_client.get(f"/projects/{project_id}/stages/assembly")
    assert page.status_code == 200
    assert "voiceover brief text" in page.text
    assert "visual prompt sheet text" in page.text
