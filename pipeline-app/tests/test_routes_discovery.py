from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    skill_dir = tmp_path / ".claude" / "skills" / "shorts-ideation"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "pipeline-app" / "stage_templates").mkdir(parents=True)
    (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").write_text("/x", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app, follow_redirects=False)


def test_get_handles_page_lists_no_handles_initially(client: TestClient):
    response = client.get("/discovery/handles")
    assert response.status_code == 200
    assert "No handles yet" in response.text


def test_add_handle_creates_pending_row_and_spawns_validation(client: TestClient, monkeypatch):
    spawned = {}

    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        class FakeProc:
            pid = 999
        return FakeProc()

    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", fake_popen)
    response = client.post("/discovery/handles", data={
        "platform": "youtube", "handle": "@NewChannel", "display_name": "New Channel",
        "cohort": "guru", "keyword_filter": "",
    })
    assert response.status_code in (200, 303, 307)
    listing = client.get("/discovery/handles")
    assert "@NewChannel" in listing.text
    assert "pending" in listing.text.lower() or "validating" in listing.text.lower()
    assert "--mode" in spawned["cmd"]
    assert "validate_handle" in spawned["cmd"]


def _no_spawn(monkeypatch):
    """Stub the validate subprocess. A validate run costs a billable Bright Data
    job on the paid platforms, so tests must never let one launch."""
    spawned = []
    monkeypatch.setattr(
        "pipeline_app.routes.discovery.subprocess.Popen",
        lambda cmd, **k: spawned.append(cmd) or type("P", (), {"pid": 1})(),
    )
    return spawned


def _add(client: TestClient, platform: str, handle: str):
    return client.post("/discovery/handles", data={
        "platform": platform, "handle": handle, "display_name": "",
        "cohort": "guru", "keyword_filter": "",
    })


def test_add_handle_rejects_a_handle_that_would_share_a_directory(client: TestClient, monkeypatch):
    """slugify strips periods, so facebook/john.doe.5 and facebook/johndoe5 both
    resolve to output/brand-intel/facebook/johndoe5. Registering both means two
    billed jobs per run writing to one directory, and the second reports the
    healthy 'no_new_content' after reading the first's files."""
    _no_spawn(monkeypatch)
    assert _add(client, "facebook", "johndoe5").status_code in (200, 303, 307)

    response = _add(client, "facebook", "john.doe.5")
    assert response.status_code == 400
    # The message has to name both handles and the shared directory, or the
    # operator cannot tell which existing registration is in the way.
    assert "john.doe.5" in response.text
    assert "johndoe5" in response.text


def test_add_handle_rejects_a_case_only_difference(client: TestClient, monkeypatch):
    _no_spawn(monkeypatch)
    _add(client, "facebook", "NASA")
    assert _add(client, "facebook", "nasa").status_code == 400


def test_add_handle_does_not_spawn_validation_for_a_rejected_handle(client: TestClient, monkeypatch):
    """A rejected registration must not launch a validate run -- on the Bright
    Data platforms that is a billable job for a handle we refused to store."""
    spawned = _no_spawn(monkeypatch)
    _add(client, "facebook", "johndoe5")
    spawned.clear()

    assert _add(client, "facebook", "john.doe.5").status_code == 400
    assert spawned == []


def test_add_handle_does_not_store_a_rejected_handle(client: TestClient, monkeypatch):
    _no_spawn(monkeypatch)
    _add(client, "facebook", "johndoe5")
    _add(client, "facebook", "john.doe.5")

    listing = client.get("/discovery/handles")
    assert "john.doe.5" not in listing.text


def test_add_handle_allows_the_same_slug_on_a_different_platform(client: TestClient, monkeypatch):
    """Directories are namespaced by platform, so facebook/nasa and
    instagram/nasa never share one -- this must not be rejected."""
    _no_spawn(monkeypatch)
    assert _add(client, "facebook", "nasa").status_code in (200, 303, 307)
    assert _add(client, "instagram", "NASA").status_code in (200, 303, 307)


def test_add_handle_still_rejects_an_exact_duplicate_with_its_own_message(client: TestClient, monkeypatch):
    """Regression: the pre-existing exact-match check keeps its own wording, so
    'already registered' and 'shares a directory' stay distinguishable."""
    _no_spawn(monkeypatch)
    _add(client, "facebook", "nasa")

    response = _add(client, "facebook", "nasa")
    assert response.status_code == 400
    assert "already exists" in response.text


def test_toggle_include_flips_and_persists(client: TestClient, monkeypatch):
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", lambda *a, **k: type("P", (), {"pid": 1})())
    client.post("/discovery/handles", data={
        "platform": "youtube", "handle": "@a", "display_name": "A", "cohort": "guru", "keyword_filter": "",
    })
    listing = client.get("/discovery/handles")
    import re
    match = re.search(r'/discovery/handles/(\d+)/toggle', listing.text)
    assert match is not None
    handle_id = match.group(1)
    response = client.post(f"/discovery/handles/{handle_id}/toggle")
    assert response.status_code in (200, 303, 307)


def test_handle_status_endpoint_returns_json(client: TestClient, monkeypatch):
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", lambda *a, **k: type("P", (), {"pid": 1})())
    client.post("/discovery/handles", data={
        "platform": "youtube", "handle": "@a", "display_name": "A", "cohort": "guru", "keyword_filter": "",
    })
    listing = client.get("/discovery/handles")
    import re
    handle_id = re.search(r'/discovery/handles/(\d+)/toggle', listing.text).group(1)
    response = client.get(f"/discovery/handles/{handle_id}/status")
    assert response.status_code == 200
    assert response.json()["status"] in ("pending", "validating", "validated", "invalid")


def test_add_duplicate_handle_returns_400_not_500(client: TestClient, monkeypatch):
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", lambda *a, **k: type("P", (), {"pid": 1})())
    data = {"platform": "youtube", "handle": "@a", "display_name": "A", "cohort": "guru", "keyword_filter": ""}
    first = client.post("/discovery/handles", data=data)
    assert first.status_code in (200, 303, 307)
    second = client.post("/discovery/handles", data=data)
    assert second.status_code == 400


def test_run_now_spawns_incremental_mode(client: TestClient, monkeypatch):
    spawned = {}
    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        return type("P", (), {"pid": 1})()
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", fake_popen)
    response = client.post("/discovery/run-now")
    assert response.status_code in (200, 303, 307)
    assert "incremental" in spawned["cmd"]


def test_run_now_backfill_spawns_backfill_mode_with_dates(client: TestClient, monkeypatch):
    spawned = {}
    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        return type("P", (), {"pid": 1})()
    monkeypatch.setattr("pipeline_app.routes.discovery.subprocess.Popen", fake_popen)
    response = client.post("/discovery/run-now-backfill", data={"start": "2026-06-01", "end": "2026-06-30"})
    assert response.status_code in (200, 303, 307)
    assert "backfill" in spawned["cmd"]
    assert "2026-06-01" in spawned["cmd"]
    assert "2026-06-30" in spawned["cmd"]


def test_update_settings_persists_time_and_timezone(client: TestClient):
    response = client.post("/discovery/settings", data={"time_of_day": "07:30", "timezone": "America/New_York"})
    assert response.status_code in (200, 303, 307)
    from pipeline_app import db as db_mod
    row = db_mod.get_settings(client.app.state.conn)
    assert row["time_of_day"] == "07:30"
    assert row["timezone"] == "America/New_York"


def test_handles_page_shows_current_schedule(client: TestClient):
    client.post("/discovery/settings", data={"time_of_day": "07:30", "timezone": "America/New_York"})
    listing = client.get("/discovery/handles")
    assert "07:30" in listing.text
    assert "America/New_York" in listing.text


def test_discovery_runs_page_lists_runs_newest_first(client: TestClient):
    from pipeline_app import db as db_mod
    conn = client.app.state.conn
    handle_id = db_mod.create_handle(conn, "youtube", "@a", "A", "guru", None, "2026-07-30T00:00:00Z")
    r1 = db_mod.insert_terminal_run(conn, "r1", "manual", "incremental", "completed", "2026-07-30T06:00:00Z", "2026-07-30T06:01:00Z")
    db_mod.record_handle_result(conn, r1, handle_id, "ok", 2)
    r2 = db_mod.insert_terminal_run(conn, "r2", "scheduled", "incremental", "completed_with_errors", "2026-07-30T07:00:00Z", "2026-07-30T07:01:00Z")
    response = client.get("/discovery/runs")
    assert response.status_code == 200
    first_pos = response.text.index("r2")
    second_pos = response.text.index("r1")
    assert first_pos < second_pos  # r2 (newer) rendered before r1
    assert "completed_with_errors" in response.text


def test_discovery_runs_page_empty_state(client: TestClient):
    response = client.get("/discovery/runs")
    assert response.status_code == 200
    assert "No discovery runs yet" in response.text


def test_handles_page_shows_a_handles_current_brand_tags(client: TestClient, monkeypatch):
    _no_spawn(monkeypatch)
    _add(client, "instagram", "aspenprojectplay")
    from pipeline_app import db as db_mod
    conn = client.app.state.conn
    handle_id = db_mod.get_handle_by_platform_and_handle(conn, "instagram", "aspenprojectplay")["id"]
    db_mod.set_handle_brands(conn, handle_id, ["guru", "raisinggoodsports"])

    response = client.get("/discovery/handles")
    assert response.status_code == 200
    assert "raisinggoodsports" in response.text


def test_update_handle_brands_replaces_the_tag_set(client: TestClient, monkeypatch):
    _no_spawn(monkeypatch)
    _add(client, "instagram", "aspenprojectplay")
    from pipeline_app import db as db_mod
    conn = client.app.state.conn
    handle_id = db_mod.get_handle_by_platform_and_handle(conn, "instagram", "aspenprojectplay")["id"]
    db_mod.set_handle_brands(conn, handle_id, ["guru"])

    response = client.post(f"/discovery/handles/{handle_id}/brands",
                           data={"brands": ["guru", "raisinggoodsports"]})
    assert response.status_code in (200, 303, 307)
    assert db_mod.get_handle_brands(conn, handle_id) == ["guru", "raisinggoodsports"]


def test_update_handle_brands_to_no_boxes_checked_clears_all_tags(client: TestClient, monkeypatch):
    _no_spawn(monkeypatch)
    _add(client, "instagram", "aspenprojectplay")
    from pipeline_app import db as db_mod
    conn = client.app.state.conn
    handle_id = db_mod.get_handle_by_platform_and_handle(conn, "instagram", "aspenprojectplay")["id"]
    db_mod.set_handle_brands(conn, handle_id, ["guru"])

    client.post(f"/discovery/handles/{handle_id}/brands", data={})
    assert db_mod.get_handle_brands(conn, handle_id) == []


def test_update_handle_brands_with_stale_handle_id_returns_404_not_500(client: TestClient):
    response = client.post("/discovery/handles/999999/brands", data={"brands": ["guru"]})
    assert response.status_code == 404


def test_brand_choices_matches_email_render_brand_section_order():
    from pipeline_app import email_render
    from pipeline_app.routes.discovery import BRAND_CHOICES
    assert BRAND_CHOICES == list(email_render.BRAND_SECTION_ORDER)
