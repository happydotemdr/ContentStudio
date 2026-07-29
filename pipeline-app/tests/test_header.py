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
