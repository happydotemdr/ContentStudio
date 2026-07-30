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


def test_browse_tree_nested_folder_returns_children(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "anchorandwave" / "plato.md")
    resp = test_client.get("/browse/tree", params={"path": "thinkers"})
    assert resp.status_code == 200
    assert "anchorandwave" in resp.text


def test_browse_tree_dotdot_traversal_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"path": "../../../etc"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_tree_windows_drive_override_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"path": "C:/Windows"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_tree_leading_backslash_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"path": "\\Windows\\System32"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_tree_sibling_prefix_folder_not_admitted(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output-old" / "secret.md")
    resp = test_client.get("/browse/tree", params={"path": "../output-old"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text
    assert "secret.md" not in resp.text


def test_browse_tree_missing_folder_returns_folder_not_found(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"path": "does/not/exist"})
    assert resp.status_code == 200
    assert "Folder not found." in resp.text


def test_browse_tree_uppercase_md_extension_listed(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "notes" / "NOTES.MD")
    resp = test_client.get("/browse/tree", params={"path": "notes"})
    assert resp.status_code == 200
    assert "NOTES.MD" in resp.text


def test_browse_tree_folder_with_no_md_anywhere_is_empty_not_error(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "empty_ish" / "raw.txt")
    resp = test_client.get("/browse/tree", params={"path": "empty_ish"})
    # Empty, not an error: no error partial, and none of the excluded
    # folder's contents leak into the response either.
    assert resp.status_code == 200
    assert "browse-error" not in resp.text
    assert "raw.txt" not in resp.text


def test_browse_file_renders_frontmatter_and_body(client):
    test_client, tmp_path = client
    _touch(
        tmp_path / "output" / "thinkers" / "plato.md",
        "---\nera: classical\n---\n\n# Plato\n\nBody.\n",
    )
    resp = test_client.get("/browse/file", params={"path": "thinkers/plato.md"})
    assert resp.status_code == 200
    assert "classical" in resp.text
    assert "<h1>Plato</h1>" in resp.text


def test_browse_file_malformed_yaml_shows_error_not_500(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "bad.md", "---\nstage: [unterminated\n---\n\nBody.\n")
    resp = test_client.get("/browse/file", params={"path": "bad.md"})
    assert resp.status_code == 200
    assert "Frontmatter is not valid YAML." in resp.text


def test_browse_file_non_mapping_frontmatter_shows_error(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "listfm.md", "---\n- one\n- two\n---\n\nBody.\n")
    resp = test_client.get("/browse/file", params={"path": "listfm.md"})
    assert resp.status_code == 200
    assert "Frontmatter is not a key/value mapping." in resp.text


def test_browse_file_oversize_shows_message(client):
    test_client, tmp_path = client
    import pipeline_app.browse_service as browse_service
    f = tmp_path / "output" / "huge.md"
    f.write_bytes(b"x" * (browse_service.MAX_FILE_BYTES + 1))
    resp = test_client.get("/browse/file", params={"path": "huge.md"})
    assert resp.status_code == 200
    assert "too large to preview" in resp.text


def test_browse_file_missing_file_returns_path_does_not_exist(client):
    test_client, _ = client
    resp = test_client.get("/browse/file", params={"path": "nope.md"})
    assert resp.status_code == 200
    assert "Path does not exist." in resp.text


def test_browse_file_directory_path_returns_error(client):
    test_client, tmp_path = client
    (tmp_path / "output" / "thinkers").mkdir()
    resp = test_client.get("/browse/file", params={"path": "thinkers"})
    assert resp.status_code == 200
    assert "Path is a directory, not a file." in resp.text


def test_browse_file_wrong_suffix_returns_error(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "raw.txt")
    resp = test_client.get("/browse/file", params={"path": "raw.txt"})
    assert resp.status_code == 200
    assert "Not a valid .md file path." in resp.text


def test_browse_file_traversal_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/file", params={"path": "../../../etc/passwd"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_file_uppercase_extension_renders(client):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "NOTES.MD", "# Upper\n\nBody.\n")
    resp = test_client.get("/browse/file", params={"path": "NOTES.MD"})
    assert resp.status_code == 200
    assert "<h1>Upper</h1>" in resp.text
