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


@pytest.fixture
def two_stage_client(tmp_path: Path, monkeypatch):
    """ideation -> scripting, mirroring test_routes_approve_edit.py's fixture
    of the same name (not shared/importable across the two test files -- see
    task 19's brief)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
        "    depends_on: [ideation]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app, follow_redirects=False), tmp_path, app


def _new_project(test_client, app, tmp_path: Path, slug="abc", brand="generic"):
    resp = test_client.post("/projects", data={"slug": slug, "brand": brand})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return project_id, tmp_path / "runs" / project["run_id"]


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


def test_a_malformed_artifact_is_a_409_naming_the_file_not_a_500(client):
    """P2 A-68/A-69: parse_frontmatter RAISES MalformedArtifactError now instead
    of returning ({}, text) and masking a truncated artifact as an unversioned
    one. A MalformedArtifactError reaching the operator as a bare 500 is a
    regression, not a fix."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    stage_dir = run_dir / "01-ideation"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "artifact.v1.md").write_text("---\nstage: x\nbody with no closing fence\n",
                                              encoding="utf-8")

    resp = test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    assert resp.status_code == 409
    assert "artifact.v1.md" in resp.text
    row = app.state.conn.execute(
        "SELECT * FROM events WHERE kind = 'artifact.malformed'"
    ).fetchone()
    assert row["severity"] == "error"


def test_a_malformed_artifact_renders_the_stage_page_rather_than_blanking_it(client):
    """The GET path: _stage_context parses the same file. A malformed artifact
    must show as an explicit banner, not as a stage with no output -- which is
    indistinguishable from a stage that never ran."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    stage_dir = run_dir / "01-ideation"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "artifact.v1.md").write_text("---\nstage: x\nbody with no closing fence\n",
                                              encoding="utf-8")

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert page.context["error_banner"]["kind"] == "malformed_artifact"


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


def test_a_missing_upstream_artifact_is_reported_not_dropped(tmp_path: Path, monkeypatch):
    """E-05 FAULT: the `if up_latest is not None` guard skipped an absent
    dependency and the panel rendered the rest with no gap indicated. 'No
    upstream input.' appeared only when EVERY dependency was missing, so the
    operator reviewed a partial input believing it complete -- and the same
    partial context is what the turn was actually given."""
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

    # Only "voiceover" has an artifact; "visual" has none.
    artifacts.write_artifact(run_dir / "03-voiceover", 1, {"stage": "voiceover-brief"}, "voiceover brief text")

    ctx = test_client.get(f"/projects/{project_id}/stages/assembly").context
    assert [i["stage_id"] for i in ctx["inputs"]] == ["voiceover", "visual"]
    assert [i["present"] for i in ctx["inputs"]] == [True, False]


def test_a_missing_upstream_is_distinguishable_from_an_empty_one(tmp_path: Path, monkeypatch):
    """E-05 DISTINGUISHABILITY: an upstream artifact with an empty body and an
    upstream artifact that does not exist are different facts."""
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

    # "voiceover" has an artifact with an EMPTY body; "visual" has no artifact.
    artifacts.write_artifact(run_dir / "03-voiceover", 1, {"stage": "voiceover-brief"}, "")

    ctx = test_client.get(f"/projects/{project_id}/stages/assembly").context
    by_id = {i["stage_id"]: i for i in ctx["inputs"]}
    assert by_id["voiceover"]["present"] is True
    assert by_id["voiceover"]["body"] == ""
    assert by_id["visual"]["present"] is False
    assert by_id["visual"]["body"] is None


def test_every_declared_dependency_appears_even_when_all_are_missing(tmp_path: Path, monkeypatch):
    """E-05 SURFACING: the human-reachable signal is one card per declared
    dependency, always."""
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

    ctx = test_client.get(f"/projects/{project_id}/stages/assembly").context
    assert len(ctx["inputs"]) == 2
    assert all(not i["present"] for i in ctx["inputs"])


def test_a_script_tag_in_an_upstream_artifact_does_not_reach_the_context(tmp_path: Path, monkeypatch):
    """Artifact bodies are model-generated and hand-editable; stage.html renders
    inputs[].html through `| safe`. Sanitize at the producer so no consumer has
    to remember."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "  - id: assembly\n    skill: shorts-assembly\n    dir_prefix: \"04\"\n"
        "    depends_on: [voiceover]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]

    artifacts.write_artifact(
        run_dir / "03-voiceover", 1, {"stage": "voiceover-brief"},
        "<script>alert(1)</script>\n\nnormal text",
    )
    # The assembly stage's own output also carries the same hazard.
    artifacts.write_artifact(
        run_dir / "04-assembly", 1, {"stage": "shorts-assembly"},
        "<script>alert(2)</script>\n\noutput text",
    )

    ctx = test_client.get(f"/projects/{project_id}/stages/assembly").context
    assert "<script>" not in ctx["inputs"][0]["html"]
    assert "normal text" in ctx["inputs"][0]["html"]
    assert "<script>" not in ctx["output_html"]


def test_an_html_entity_decoded_attribute_cannot_inject_a_new_on_attribute(tmp_path: Path, monkeypatch):
    """Regression: HTMLParser hands `handle_starttag` already-entity-decoded
    attribute values, so `&quot;` in the source becomes a literal `"` by the
    time our code sees it. Naively re-serializing that value verbatim into
    `f' {name}="{value}"'` let the decoded quote close the attribute early and
    a NEW `onmouseover=` attribute appear in the final string -- one our
    on*-prefix filter never inspects, because it only ran against the parsed
    attribute *name* (still just `href`), not anything introduced by our own
    string concatenation on output. Escaping the value on reserialization is
    the fix; this reproduces the reviewer's exact repro string end to end
    through the real route."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "  - id: assembly\n    skill: shorts-assembly\n    dir_prefix: \"04\"\n"
        "    depends_on: [voiceover]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]

    artifacts.write_artifact(
        run_dir / "03-voiceover", 1, {"stage": "voiceover-brief"},
        '<a href="x&quot; onmouseover=&quot;alert(1)">y</a>',
    )

    ctx = test_client.get(f"/projects/{project_id}/stages/assembly").context
    html = ctx["inputs"][0]["html"]
    # The exploit's whole point is a literal, unescaped '"' breaking out of the
    # href value and starting a real onmouseover= attribute -- that exact
    # sequence must never appear in the output.
    assert '" onmouseover="' not in html
    assert '<a href="x" onmouseover="alert(1)">y</a>' not in html
    # "onmouseover" surviving as inert TEXT inside the escaped href value is
    # fine and expected -- it is no longer a parsed attribute name.
    assert "&quot;" in html


def test_a_javascript_url_via_ordinary_markdown_link_syntax_is_stripped(tmp_path: Path, monkeypatch):
    """Regression: `markdown.markdown("[click](javascript:alert(1))")` emits
    `<a href="javascript:alert(1)">click</a>` from plain Markdown link syntax --
    no raw HTML required, and artifact bodies are model-generated and
    hand-editable, so this is an ordinary reachable path, not an edge case.
    Tag-allowlisting and on*-attribute-stripping alone don't catch it; only a
    URL-scheme check on href/src does. The tag and its text stay; only the
    unsafe href attribute is dropped."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: voiceover\n    skill: voiceover-brief\n    dir_prefix: \"03\"\n    depends_on: []\n"
        "  - id: assembly\n    skill: shorts-assembly\n    dir_prefix: \"04\"\n"
        "    depends_on: [voiceover]\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]

    artifacts.write_artifact(
        run_dir / "03-voiceover", 1, {"stage": "voiceover-brief"},
        "[click](javascript:alert(1))",
    )

    ctx = test_client.get(f"/projects/{project_id}/stages/assembly").context
    html = ctx["inputs"][0]["html"]
    assert "javascript:" not in html
    assert "click" in html  # the link text and tag survive; only href is dropped


def test_stage_page_renders_gate_results_and_override_field(tmp_path: Path, monkeypatch):
    """Finding 2a: the stage page must render the latest artifact's `gates`
    entries -- name, status, and each finding's check/beat/message/kind -- so
    a user facing a failing gate can see WHY, and a `skipped` finding must be
    visually distinguishable (its own CSS class) from a blocking one, since a
    known unknown is not a failure."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "02-scripting"

    meta = {
        "schema_version": 1, "stage": "shorts-scripting", "version": 1, "status": "draft",
        "gates": [{
            "name": "gate_d_script_language", "status": "fail",
            "findings": [
                {"check": "D1", "beat": "HOOK", "message": "em-dash in VO line", "kind": "fail"},
                {
                    "check": "D5", "beat": "SETUP",
                    "message": "no computable time range; pace unchecked", "kind": "skipped",
                },
            ],
        }],
    }
    artifacts.write_artifact(stage_dir, 1, meta, "script body")

    page = test_client.get(f"/projects/{project_id}/stages/scripting")
    assert page.status_code == 200
    assert "gate_d_script_language" in page.text
    assert "em-dash in VO line" in page.text
    assert "gate-finding-blocking" in page.text
    assert "gate-finding-skipped" in page.text
    assert 'name="override_reason"' in page.text


def test_approve_route_blank_override_field_does_not_count_as_override(tmp_path: Path, monkeypatch):
    """Finding 2b: the approve form's override_reason field is optional, and
    the route already does `override_reason.strip() or None` -- a blank or
    whitespace-only field must NOT be treated as an override on a failing
    gate. This is the end-to-end verification the finding asked for, not an
    assumption."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "02-scripting"

    meta = {
        "schema_version": 1, "stage": "shorts-scripting", "version": 1, "status": "draft",
        "gates": [{"name": "gate_d_script_language", "status": "fail", "findings": [
            {"check": "D1", "beat": "HOOK", "message": "em-dash in VO line", "kind": "fail"},
        ]}],
    }
    artifacts.write_artifact(stage_dir, 1, meta, "script body")

    # Whitespace-only override_reason must not count as an override.
    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/approve", data={"override_reason": "   "}
    )
    assert resp.status_code == 409

    # A real reason succeeds.
    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/approve",
        data={"override_reason": "verified manually"},
    )
    assert resp.status_code in (200, 303, 307)


def test_stage_page_renders_markdown_as_html_not_raw_text(client):
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    project = app.state.conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    stage_dir = run_dir / "01-ideation"

    artifacts.write_artifact(
        stage_dir, 1, {"stage": "shorts-ideation", "status": "draft"},
        "## Concept Brief\n\n- angle: contrarian\n- avatar: youth coach\n",
    )

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert "<h2>Concept Brief</h2>" in page.text
    assert "<li>angle: contrarian</li>" in page.text
    assert "## Concept Brief" not in page.text


def test_a_gate_block_re_renders_the_stage_page_with_a_banner(two_stage_client):
    """E-04: eight operator-reachable error states navigated the browser to an
    unstyled text document with no header, no nav, no back link and no form to
    retry from. Recovery was browser-back in every case. Keep the status codes;
    return the page."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    assert test_client.post(f"/projects/{project_id}/stages/ideation/approve").status_code == 303

    artifacts.write_artifact(
        run_dir / "02-scripting", 1,
        {
            "schema_version": 1, "stage": "shorts-scripting", "version": 1, "status": "draft",
            "gates": [{"name": "gate_d_script_language", "status": "fail", "findings": [
                {"check": "D1", "beat": "HOOK", "message": "em-dash in VO line", "kind": "fail"},
            ]}],
        },
        "script body",
    )

    resp = test_client.post(f"/projects/{project_id}/stages/scripting/approve")
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("text/html")
    assert "gate_d_script_language" in resp.text        # the page, not a text file
    assert 'name="override_reason"' in resp.text        # a way forward from here
    assert "error-banner" in resp.text


def test_a_locked_stage_edit_re_renders_with_a_banner(two_stage_client):
    """409 + text/html + 'error-banner', for the edit route's locked-stage
    guard. scripting depends_on: [ideation], which hasn't been approved, so
    scripting is still locked."""
    test_client, tmp_path, app = two_stage_client
    project_id, _run_dir = _new_project(test_client, app, tmp_path)

    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": "sneaky edit"}
    )
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("text/html")
    assert "error-banner" in resp.text
    assert "locked" in resp.text


def test_the_grounding_edit_refusal_keeps_its_message(client):
    """409 + 'rgs-briefs' still present in the rendered page, for the
    grounding edit refusal specifically (use the existing `client` fixture,
    which already declares a `grounding` stage)."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "rgs", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    resp = test_client.post(
        f"/projects/{project_id}/stages/grounding/edit", data={"body": "hand-edited text"}
    )
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("text/html")
    assert "error-banner" in resp.text
    assert "rgs-briefs" in resp.text


def test_the_stage_page_publishes_the_hand_edit_contract(client):
    """A-84/E-07: `POST .../edit` mints a version, re-gates the body, propagates
    staleness and resets the stage -- 60 lines of carefully-reasoned behavior
    with no template posting to it anywhere in the repo. The route is KEPT (its
    four latent defects are closed by T2/T3/T4), so the server must hand the
    template everything it needs to render the form."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "body")
    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    ctx = page.context
    assert ctx["edit_allowed"] is True
    assert ctx["edit_action"] == f"/projects/{project_id}/stages/ideation/edit"
    assert ctx["edit_field"] == "body"


def test_grounding_never_offers_the_hand_edit_form(client):
    """The route already refuses grounding (its output lives in rgs-briefs/),
    so the page must not offer a form that can only 409."""
    test_client, tmp_path, app = client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    ctx = test_client.get(f"/projects/{project_id}/stages/grounding").context
    assert ctx["edit_allowed"] is False
    assert ctx["edit_blocked_reason"]


PUBLISHED_CONTEXT_KEYS = frozenset({
    "gate_view", "has_blocking_gate", "gate_override", "gate_overrides",
    "artifact_version", "artifact_created_at", "artifact_finalized_at",
    "edit_allowed", "edit_blocked_reason", "edit_action", "edit_field",
    "error_banner", "inputs",
})


@pytest.mark.parametrize("with_artifact", [True, False])
def test_every_published_context_key_is_present_on_every_render(client, with_artifact):
    """The contract test for §6. P15 binds templates to these names and Jinja
    renders a missing key as EMPTY -- so an absent key is not a crash, it is a
    blank panel. That is exactly how the first draft of this contract and P15's
    would have silently reimplemented E-03 (a never-ran gate rendering as a
    clean pass). A key that is sometimes absent is the same defect in slower
    motion, so this asserts presence on BOTH the has-artifact and no-artifact
    renders."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    if with_artifact:
        artifacts.write_artifact(
            run_dir / "01-ideation", 1,
            {"stage": "shorts-ideation", "version": 1, "status": "draft",
             "created_at": "2026-08-08T00:00:00+00:00", "finalized_at": None},
            "body",
        )
    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert page.status_code == 200
    assert PUBLISHED_CONTEXT_KEYS <= set(page.context)


def test_the_conflict_render_carries_the_same_context_keys_as_the_normal_one(two_stage_client):
    """The 409 body is the same template with the same keys -- differing only in
    error_banner being non-None. P15 binds to that unconditionally."""
    test_client, tmp_path, app = two_stage_client
    project_id, _run_dir = _new_project(test_client, app, tmp_path)
    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": "sneaky edit"}
    )
    assert resp.status_code == 409
    assert PUBLISHED_CONTEXT_KEYS <= set(resp.context)
    assert resp.context["error_banner"]["kind"] == "conflict"


def test_the_stage_page_reports_which_artifact_version_is_on_screen(client):
    """P15's E-06: stage_page parsed the frontmatter into output_meta and then
    discarded it, so an operator could not tell v1 from v7, or whether the body
    had been regenerated since they last looked."""
    test_client, tmp_path, app = client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(
        run_dir / "01-ideation", 1,
        {"stage": "shorts-ideation", "version": 1, "status": "draft",
         "created_at": "2026-08-08T00:00:00+00:00", "finalized_at": None},
        "v1 body",
    )
    artifacts.write_artifact(
        run_dir / "01-ideation", 2,
        {"stage": "shorts-ideation", "version": 2, "status": "final",
         "created_at": "2026-08-08T01:00:00+00:00",
         "finalized_at": "2026-08-08T02:00:00+00:00"},
        "v2 body",
    )
    ctx = test_client.get(f"/projects/{project_id}/stages/ideation").context
    assert ctx["artifact_version"] == 2
    assert ctx["artifact_created_at"] == "2026-08-08T01:00:00+00:00"
    assert ctx["artifact_finalized_at"] == "2026-08-08T02:00:00+00:00"


GATE_MATRIX = [
    ("passing",     [{"name": "gate_d_script_language", "status": "pass", "findings": []}]),
    ("failing",     [{"name": "gate_d_script_language", "status": "fail", "findings": []}]),
    ("errored",     [{"name": "gate_d_script_language", "status": "error", "findings": []}]),
    ("never_ran",   []),
    ("wrong_gate",  [{"name": "gate_c_prompt_sheet", "status": "pass", "findings": []}]),
    ("unknown",     [{"name": "gate_d_script_language", "status": "skipped", "findings": []}]),
    ("no_status",   [{"name": "gate_d_script_language", "findings": []}]),
    ("skipped_only", [{"name": "gate_d_script_language", "status": "pass",
                      "findings": [{"check": "D5", "beat": "SETUP", "kind": "skipped",
                                    "message": "no computable time range"}]}]),
]


@pytest.mark.parametrize("label,gates_block", GATE_MATRIX, ids=[c[0] for c in GATE_MATRIX])
def test_the_page_flag_the_per_gate_tag_and_the_approve_decision_never_disagree(
    two_stage_client, label, gates_block
):
    """E-03's real mechanism, closed structurally. A never-ran gate rendered as
    a clean pass; the approve form rendered WITHOUT the override field; clicking
    Approve returned a bare 409 with no path forward. P15 now renders
    gate_view[].blocking as a per-gate tag and has_blocking_gate as the
    page-level flag, so there are three surfaces that must agree. They all read
    one classifier; this asserts it."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    assert test_client.post(f"/projects/{project_id}/stages/ideation/approve").status_code == 303
    artifacts.write_artifact(
        run_dir / "02-scripting", 1,
        {"schema_version": 1, "stage": "shorts-scripting", "version": 1,
         "status": "draft", "gates": gates_block},
        "script body",
    )

    ctx = test_client.get(f"/projects/{project_id}/stages/scripting").context
    page_flag = ctx["has_blocking_gate"]

    assert page_flag == any(g["blocking"] for g in ctx["gate_view"])
    approve = test_client.post(f"/projects/{project_id}/stages/scripting/approve")
    assert (approve.status_code == 409) == page_flag, (
        f"{label}: page says blocking={page_flag} but approve returned "
        f"{approve.status_code}"
    )
    assert ('name="override_reason"' in test_client.get(
        f"/projects/{project_id}/stages/scripting"
    ).text) == page_flag
