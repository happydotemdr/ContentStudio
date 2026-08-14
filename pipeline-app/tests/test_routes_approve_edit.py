import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import artifacts, db, gates
from pipeline_app.main import create_app

# The real repo root, for tests that need gates.run_gates_for_stage to load
# the actual scripts/lint_script_language.py rather than error out against an
# isolated tmp_path that has no scripts/ directory of its own.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Repo-root tests/fixtures/, not pipeline-app/tests/fixtures/ -- the fixture
# sheets/styleboards are shared with the Gate C linter's own test suite.
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _install_real_script_linter(tmp_path: Path) -> None:
    dest = tmp_path / "scripts"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        REPO_ROOT / "scripts" / "lint_script_language.py",
        dest / "lint_script_language.py",
    )


CLEAN_SCRIPT = (
    'HOOK (0–3s | 6 words): "Best part was the mud today."\n'
    "GATES\n  Gate E (fresh Opus critic): pass\n"
)


def _new_project(test_client, app, tmp_path: Path, slug="abc", brand="generic"):
    resp = test_client.post("/projects", data={"slug": slug, "brand": brand})
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    return project_id, tmp_path / "runs" / project["run_id"]


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


def test_first_ever_hand_edit_records_a_real_depends_on(two_stage_client):
    """A-60 FAULT: with no prior artifact, prior_meta was {} and depends_on was
    written as []. is_stale([], ...) is False unconditionally, so the staleness
    cascade terminated at that node and every stage below stayed green on
    superseded input."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    ideation_dir = run_dir / "01-ideation"
    artifacts.write_artifact(ideation_dir, 1, {"stage": "shorts-ideation"}, "concept v1")
    _install_real_script_linter(tmp_path)
    assert test_client.post(f"/projects/{project_id}/stages/ideation/approve").status_code == 303

    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT}
    )
    assert resp.status_code == 303
    meta, _ = artifacts.parse_frontmatter(
        (run_dir / "02-scripting" / "artifact.v1.md").read_text(encoding="utf-8")
    )
    assert meta["depends_on"] == [{
        "path": "01-ideation/artifact.v1.md",
        "sha256": artifacts.compute_sha256(ideation_dir / "artifact.v1.md"),
    }]


def test_a_hand_edited_stage_with_no_prior_artifact_still_goes_stale(two_stage_client):
    """A-60 DISTINGUISHABILITY: the empty list and a correct list are not merely
    different values -- they produce different cascade outcomes. A hand-edited
    stage must be indistinguishable from a turn-produced one at the cascade."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _install_real_script_linter(tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})
    test_client.post(f"/projects/{project_id}/stages/scripting/approve")

    test_client.post(f"/projects/{project_id}/stages/ideation/edit", data={"body": "concept v2"})

    assert db.get_stage(app.state.conn, project_id, "scripting")["status"] == "stale"


def test_a_hand_edit_after_the_upstream_advanced_records_the_current_version(two_stage_client):
    """A-60 SURFACING: the copied value named artifact.v1.md while v2 was current,
    so the artifact asserted a provenance it was never derived from. The recorded
    path is the human-reachable signal -- it must name the file actually read."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _install_real_script_linter(tmp_path)
    ideation_dir = run_dir / "01-ideation"
    artifacts.write_artifact(ideation_dir, 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})
    artifacts.write_artifact(ideation_dir, 2, {"stage": "shorts-ideation"}, "concept v2")

    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})

    meta, _ = artifacts.parse_frontmatter(
        (run_dir / "02-scripting" / "artifact.v2.md").read_text(encoding="utf-8")
    )
    assert [d["path"] for d in meta["depends_on"]] == ["01-ideation/artifact.v2.md"]


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
    # This artifact is written straight to disk with no `gates` key -- the
    # pre-existing-artifact shape approve_stage now refuses, because a stage
    # with a registered gate and no recorded result is a gate that never ran,
    # not a gate that passed. The body ("script v1") is not real
    # script-language-gate input either. This test is about hand-edit staleness
    # propagation, not gate content, so it overrides the block rather than
    # fabricating a gate-passing script body -- the same route Task 9 took for
    # test_regenerating_an_approved_stage_marks_approved_dependent_stale.
    assert test_client.post(
        f"/projects/{project_id}/stages/scripting/approve",
        data={"override_reason": "test fixture body is not real script-language-gate input"},
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


def test_a_hand_edit_does_not_touch_the_turn_paths_raw_output(two_stage_client):
    """A-64 FAULT: the edit route truncated the SHARED raw_output.md before
    gating. A crash in that window left the new body in raw_output.md with no
    artifact version recording it, and poisoned the turn path's before_mtime
    baseline."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _install_real_script_linter(tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    scripting_dir = run_dir / "02-scripting"
    scripting_dir.mkdir(parents=True, exist_ok=True)
    (scripting_dir / "raw_output.md").write_text("previous turn output", encoding="utf-8")

    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})

    assert (scripting_dir / "raw_output.md").read_text(encoding="utf-8") == "previous turn output"


def test_a_failed_gate_run_leaves_no_scratch_file_behind(two_stage_client, monkeypatch):
    """A-41 DISTINGUISHABILITY: an escape from the gate must be observably
    different from a clean edit -- no half-written artifact, no orphan scratch,
    and a 409 rather than a 500."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")

    def boom(_repo_root, _stage_id, _path, _upstream):
        raise OSError("disk gone")

    monkeypatch.setattr("pipeline_app.routes.stages.gates.run_gates_for_stage", boom)
    resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT}
    )
    assert resp.status_code == 409
    assert "disk gone" in resp.text
    scripting_dir = run_dir / "02-scripting"
    assert not list(scripting_dir.glob(".edit_scratch*"))
    assert not list(scripting_dir.glob("artifact.v*.md"))


def test_an_edit_whose_gate_escapes_is_recorded_as_an_event(two_stage_client, monkeypatch):
    """A-41 SURFACING: an escaped gate must leave a human-findable record, not
    just a 409 the operator might dismiss."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")

    def boom(_repo_root, _stage_id, _path, _upstream):
        raise OSError("disk gone")

    monkeypatch.setattr("pipeline_app.routes.stages.gates.run_gates_for_stage", boom)
    test_client.post(f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT})

    rows = app.state.conn.execute(
        "SELECT * FROM events WHERE kind = 'gate.escaped'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "disk gone" in rows[0]["message"]


def test_two_overlapping_hand_edits_produce_two_versions_not_one(two_stage_client):
    """reserve_version is exclusive, so two edits of the same stage in
    sequence must produce artifact.v1.md and artifact.v2.md -- never both
    landing on v1 (a lost write)."""
    test_client, tmp_path, app = two_stage_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _install_real_script_linter(tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")
    scripting_dir = run_dir / "02-scripting"

    first_resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": CLEAN_SCRIPT}
    )
    second_body = CLEAN_SCRIPT + "\nSecond edit line.\n"
    second_resp = test_client.post(
        f"/projects/{project_id}/stages/scripting/edit", data={"body": second_body}
    )

    assert first_resp.status_code == 303
    assert second_resp.status_code == 303
    assert (scripting_dir / "artifact.v1.md").exists()
    assert (scripting_dir / "artifact.v2.md").exists()
    _, body_v1 = artifacts.parse_frontmatter(
        (scripting_dir / "artifact.v1.md").read_text(encoding="utf-8")
    )
    _, body_v2 = artifacts.parse_frontmatter(
        (scripting_dir / "artifact.v2.md").read_text(encoding="utf-8")
    )
    assert body_v1 != body_v2


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


def _install_gate_c_inputs(tmp_path: Path) -> None:
    """Gate C in app mode reads scripts/lint_prompt_sheet.py and
    docs/style-library.md relative to repo_root, so an isolated tmp_path repo
    needs both."""
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "scripts" / "lint_prompt_sheet.py",
                tmp_path / "scripts" / "lint_prompt_sheet.py")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "docs" / "style-library.md", tmp_path / "docs" / "style-library.md")


def _unlock_visual_stage(app, project_id: int) -> None:
    """visual depends_on [scripting, styleboard], so create_project seeds its
    row LOCKED. These tests exercise the edit route's own gate/parity
    behaviour against a resolved upstream map, not the approval cascade that
    normally flips a locked stage ready (that's covered elsewhere), so unlock
    it directly rather than routing both upstreams through /approve."""
    row = db.get_stage(app.state.conn, project_id, "visual")
    db.update_stage_status(app.state.conn, row["id"], "ready")


@pytest.fixture
def visual_client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
        "    depends_on: []\n"
        "  - id: styleboard\n    skill: shorts-styleboard\n    dir_prefix: \"02b\"\n"
        "    depends_on: [scripting]\n"
        "  - id: visual\n    skill: visual-prompts\n    dir_prefix: \"03\"\n"
        "    depends_on: [scripting, styleboard]\n",
        encoding="utf-8",
    )
    _install_gate_c_inputs(tmp_path)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app, follow_redirects=False), tmp_path, app


def test_hand_editing_a_visual_sheet_is_gated_against_the_styleboards_world_lock(visual_client):
    """A-30/A-62 FAULT, F-17 coverage. The sheet body is byte-identical in both
    halves; only the styleboard's slot label differs. Before the fix the edit
    path resolved world={} and C20 returned NOTHING (world.get(key) empty ->
    `continue`), so a typo'd label passed the gate and failed at paste time."""
    test_client, tmp_path, app = visual_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _unlock_visual_stage(app, project_id)
    sheet_body = (FIXTURES / "passing_sheet.md").read_text(encoding="utf-8")
    styleboard_body = (FIXTURES / "passing_styleboard.md").read_text(encoding="utf-8").replace(
        "rgs-sourceera-painterly-b", "rgs-sourceera-painterly-c"
    )
    artifacts.write_artifact(run_dir / "02-scripting", 1, {"stage": "shorts-scripting"}, "script")
    artifacts.write_artifact(
        run_dir / "02b-styleboard", 1, {"stage": "shorts-styleboard"}, styleboard_body
    )

    resp = test_client.post(
        f"/projects/{project_id}/stages/visual/edit", data={"body": sheet_body}
    )
    assert resp.status_code == 303
    meta, _ = artifacts.parse_frontmatter(
        (run_dir / "03-visual" / "artifact.v1.md").read_text(encoding="utf-8")
    )
    assert meta["gates"][0]["status"] == "fail"
    c20 = [f for f in meta["gates"][0]["findings"] if f["check"] == "C20"]
    assert c20 and "rgs-sourceera-painterly-c" in c20[0]["message"]


def test_the_edit_path_and_a_direct_gate_run_produce_identical_results(visual_client):
    """THE PARITY TEST. The hand-edit route must record exactly what
    run_gates_for_stage produces when handed the resolved upstream map -- the
    same map turn_service builds. Any future divergence between the two write
    paths is a diff on this equality, not a subtle behavioural drift nobody
    notices."""
    test_client, tmp_path, app = visual_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    _unlock_visual_stage(app, project_id)
    sheet_body = (FIXTURES / "passing_sheet.md").read_text(encoding="utf-8")
    styleboard_path = artifacts.write_artifact(
        run_dir / "02b-styleboard", 1, {"stage": "shorts-styleboard"},
        (FIXTURES / "passing_styleboard.md").read_text(encoding="utf-8"),
    )
    artifacts.write_artifact(run_dir / "02-scripting", 1, {"stage": "shorts-scripting"}, "script")

    test_client.post(f"/projects/{project_id}/stages/visual/edit", data={"body": sheet_body})
    recorded, _ = artifacts.parse_frontmatter(
        (run_dir / "03-visual" / "artifact.v1.md").read_text(encoding="utf-8")
    )

    reference_sheet = tmp_path / "reference_sheet.md"
    reference_sheet.write_text(sheet_body, encoding="utf-8")
    expected = gates.run_gates_for_stage(
        tmp_path, "visual", reference_sheet, {"styleboard": styleboard_path}
    )
    assert recorded["gates"] == expected


@pytest.fixture
def styleboard_client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
        "  - id: styleboard\n    skill: shorts-styleboard\n    dir_prefix: \"02b\"\n"
        "    depends_on: [ideation]\n",
        encoding="utf-8",
    )
    _install_gate_c_inputs(tmp_path)
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app, follow_redirects=False), tmp_path, app


def test_hand_editing_a_styleboard_runs_the_styleboard_gate(styleboard_client):
    """F-17 (styleboard-edit half, deferred from T5 until the styleboard gate
    existed). two_stage_client declares no styleboard stage at all, so this
    uses its own fixture (styleboard: ideation -> styleboard) rather than
    visual_client, whose stages are scripting/styleboard/visual and would
    require unlocking a stage this test has no use for."""
    test_client, tmp_path, app = styleboard_client
    project_id, run_dir = _new_project(test_client, app, tmp_path)
    artifacts.write_artifact(run_dir / "01-ideation", 1, {"stage": "shorts-ideation"}, "concept v1")
    test_client.post(f"/projects/{project_id}/stages/ideation/approve")

    resp = test_client.post(
        f"/projects/{project_id}/stages/styleboard/edit",
        data={"body": "=== STYLEBOARD ===\n\nBINDINGS\n  none\n"},
    )
    assert resp.status_code == 303
    meta, _ = artifacts.parse_frontmatter(
        (run_dir / "02b-styleboard" / "artifact.v1.md").read_text(encoding="utf-8")
    )
    assert meta["gates"][0]["name"] == "gate_s_styleboard"
    assert meta["gates"][0]["status"] == "fail"
