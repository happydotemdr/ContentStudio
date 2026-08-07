import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import artifacts, db
from pipeline_app.main import create_app

# The real repo root, for tests that need gates.run_gates_for_stage to load
# the actual scripts/lint_script_language.py rather than error out against an
# isolated tmp_path that has no scripts/ directory of its own.
REPO_ROOT = Path(__file__).resolve().parents[2]


def _install_real_script_linter(tmp_path: Path) -> None:
    dest = tmp_path / "scripts"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        REPO_ROOT / "scripts" / "lint_script_language.py",
        dest / "lint_script_language.py",
    )


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app, follow_redirects=False), tmp_path, app


@pytest.fixture
def two_stage_client(tmp_path: Path, monkeypatch):
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


def test_hand_edit_flips_stage_to_awaiting_review_and_dependent_to_stale(two_stage_client):
    """Design spec §2: a hand edit produces artifact.v{N+1}.md exactly like a
    regenerate, so it must propagate staleness downstream and drop the edited
    stage itself back to awaiting_review."""
    test_client, tmp_path, app = two_stage_client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    ideation_dir = run_dir / "01-ideation"
    scripting_dir = run_dir / "02-scripting"

    artifacts.write_artifact(
        ideation_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "concept v1"
    )
    assert test_client.post(
        f"/projects/{project_id}/stages/ideation/approve"
    ).status_code in (200, 303, 307)

    # scripting's frontmatter records ideation's approved v1 hash
    ideation_v1 = ideation_dir / "artifact.v1.md"
    artifacts.write_artifact(
        scripting_dir, 1,
        {
            "stage": "shorts-scripting",
            "status": "draft",
            "depends_on": [
                {
                    "path": "01-ideation/artifact.v1.md",
                    "sha256": artifacts.compute_sha256(ideation_v1),
                }
            ],
        },
        "script v1",
    )
    assert test_client.post(
        f"/projects/{project_id}/stages/scripting/approve"
    ).status_code in (200, 303, 307)

    assert db.get_stage(app.state.conn, project_id, "ideation")["status"] == "approved"
    assert db.get_stage(app.state.conn, project_id, "scripting")["status"] == "approved"

    edit_resp = test_client.post(
        f"/projects/{project_id}/stages/ideation/edit", data={"body": "concept v2 by hand"}
    )
    assert edit_resp.status_code in (200, 303, 307)
    assert (ideation_dir / "artifact.v2.md").exists()

    assert db.get_stage(app.state.conn, project_id, "ideation")["status"] == "awaiting_review"
    assert db.get_stage(app.state.conn, project_id, "scripting")["status"] == "stale"


def test_hand_edit_runs_gate_d_and_records_real_results(two_stage_client):
    """Finding 1: the hand-edit route must run the stage's registered gates
    over the SAVED content and write the real result into the new version's
    meta -- exactly like turn_service does after a turn -- not mint a version
    with no `gates` key at all. Before this fix, approval_service.approve_stage
    read `meta.get("gates") or []`, saw an empty list, and approved through:
    a silent pass of an unknown gate result on a hand-edited script."""
    test_client, tmp_path, app = two_stage_client
    _install_real_script_linter(tmp_path)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    ideation_dir = run_dir / "01-ideation"
    scripting_dir = run_dir / "02-scripting"

    artifacts.write_artifact(
        ideation_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "concept v1"
    )
    assert test_client.post(
        f"/projects/{project_id}/stages/ideation/approve"
    ).status_code in (200, 303, 307)

    clean_script = (
        'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n"
    )
    edit_resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": clean_script}
    )
    assert edit_resp.status_code in (200, 303, 307)

    meta, _ = artifacts.parse_frontmatter(
        (scripting_dir / "artifact.v1.md").read_text(encoding="utf-8")
    )
    assert meta["gates"][0]["name"] == "gate_d_script_language"
    assert meta["gates"][0]["status"] == "pass"


def test_hand_edit_introducing_a_gate_d_failure_blocks_approval(two_stage_client):
    """Companion to the test above: a hand edit that introduces an em-dash
    into a voiceover line must fail Gate D on the newly-minted version, and
    approval must then refuse without an override -- the exact bypass
    Finding 1 identified (a user hand-editing a script in the UI could not
    previously be blocked by Gate D at all)."""
    test_client, tmp_path, app = two_stage_client
    _install_real_script_linter(tmp_path)
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    run_dir = tmp_path / "runs" / project["run_id"]
    ideation_dir = run_dir / "01-ideation"

    artifacts.write_artifact(
        ideation_dir, 1, {"stage": "shorts-ideation", "status": "draft"}, "concept v1"
    )
    assert test_client.post(
        f"/projects/{project_id}/stages/ideation/approve"
    ).status_code in (200, 303, 307)

    dashed_script = (
        'HOOK (0–5s | 8 words): "It is not more serious play — it is labor."\n'
        "GATES\n  Gate E (fresh Opus critic): pass\n"
    )
    edit_resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": dashed_script}
    )
    assert edit_resp.status_code in (200, 303, 307)

    approve_resp = test_client.post(f"/projects/{project_id}/stages/scripting/approve")
    assert approve_resp.status_code == 409
    assert "gate" in approve_resp.text.lower()


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


def test_approve_route_blocks_locked_stage(two_stage_client):
    test_client, tmp_path, app = two_stage_client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    # scripting depends_on: [ideation], which hasn't been approved, so it's
    # still locked -- even though its directory has no artifact either, the
    # gate must reject it for the right reason (locked, not "no artifact").
    resp = test_client.post(f"/projects/{project_id}/stages/scripting/approve")
    assert resp.status_code == 409
    assert "locked" in resp.text


def test_edit_route_blocks_locked_stage(two_stage_client):
    test_client, tmp_path, app = two_stage_client
    resp = test_client.post("/projects", data={"slug": "abc", "brand": "generic"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    # scripting depends_on: [ideation], which hasn't been approved, so it's
    # still locked -- hand-editing it must be rejected the same way chat and
    # approve already are, or a locked stage can be pushed to
    # awaiting_review/approved by editing around the gate entirely.
    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": "sneaky edit"}
    )
    assert resp.status_code == 409
    assert "locked" in resp.text


def test_edit_route_blocks_grounding(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: grounding\n    skill: rgs-grounding\n    dir_prefix: \"00\"\n"
        "    depends_on: []\n    brand_scope: raisinggoodsports\n",
        encoding="utf-8",
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app, follow_redirects=False)
    resp = test_client.post("/projects", data={"slug": "rgs", "brand": "raisinggoodsports"})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    resp = test_client.post(
        f"/projects/{project_id}/stages/grounding/edit", data={"body": "hand-edited text"}
    )
    assert resp.status_code == 409
    assert "rgs-briefs" in resp.text
