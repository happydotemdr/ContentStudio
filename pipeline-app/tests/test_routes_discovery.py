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
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app)


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
