# tests/test_routes_browse.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / "output").mkdir()
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path


def _touch(path: Path, text: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_browse_root_renders_top_level_entries(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md")
    _touch(tmp_path / "output" / "alone.md")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "thinkers" in resp.text
    assert "alone.md" in resp.text


def test_browse_root_excludes_md_less_folder(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "transcripts" / "raw.txt")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "transcripts" not in resp.text


def test_browse_root_missing_output_dir_shows_folder_not_found(client):
    test_client, tmp_path = client
    import shutil
    shutil.rmtree(tmp_path / "output")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "Folder not found." in resp.text


def test_browse_tree_items_carry_htmx_attributes_not_ids(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md")
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert 'hx-get="/browse/tree?path=thinkers"' in resp.text
    assert 'hx-trigger="toggle once from:closest details"' in resp.text
    assert 'hx-target="this"' in resp.text

    # The file-row htmx attributes appear one level deeper, once "thinkers"
    # is expanded: list_children (and this route) render one folder's
    # children at a time -- a lazy tree, confirmed by Task 5's
    # nested-folder test -- so a file nested inside a subfolder is not
    # present in the root-level response above. Fetch its parent folder's
    # tree partial directly, exactly as the browser does after a toggle
    # click, instead of asserting it's already present on the root page.
    tree_resp = test_client.get("/browse/tree", params={"path": "thinkers"})
    assert tree_resp.status_code == 200
    # Jinja's `urlencode` filter leaves "/" unescaped (verified against the
    # installed jinja2==3.1.6: only reserved query-string characters like
    # "&"/"="/"+" get percent-encoded) -- a literal, unencoded "/" here is
    # correct, not a bug: FastAPI/Starlette's query-string parsing accepts
    # unencoded slashes in a value just fine.
    assert 'hx-get="/browse/file?path=thinkers/plato.md"' in tree_resp.text
    assert 'hx-sync="#browse-doc:replace"' in tree_resp.text


def test_browse_nav_link_present(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert 'href="/browse"' in resp.text
