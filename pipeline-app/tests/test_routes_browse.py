# tests/test_routes_browse.py
import os
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
    assert 'hx-get="/browse/tree?path=thinkers&root=output"' in resp.text
    assert 'hx-trigger="toggle from:closest details"' in resp.text
    assert 'hx-target="this"' in resp.text

    tree_resp = test_client.get("/browse/tree", params={"path": "thinkers", "root": "output"})
    assert tree_resp.status_code == 200
    assert 'hx-get="/browse/file?path=thinkers/plato.md&root=output"' in tree_resp.text
    assert 'hx-sync="#browse-doc:replace"' in tree_resp.text


def test_browse_nav_link_present(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert 'href="/browse"' in resp.text


def test_browse_root_marks_nav_link_active(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert '<a href="/browse" class="active">Library</a>' in resp.text
    assert '<a href="/browse" class="active">Files</a>' in resp.text


def test_browse_root_cli_status_reflects_app_state_true(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(
        "pipeline_app.preflight.check_cli_available",
        lambda: {"available": True, "path": r"C:\fake\claude.CMD", "error": None},
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app)
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert 'class="status-dot online"' in resp.text
    assert "SYSTEM ONLINE" in resp.text
    assert "CLI UNAVAILABLE" not in resp.text


def test_browse_root_cli_status_reflects_app_state_false(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    (tmp_path / "output").mkdir()
    monkeypatch.setattr(
        "pipeline_app.preflight.check_cli_available",
        lambda: {"available": False, "path": None, "error": "not found"},
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    test_client = TestClient(app)
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert 'class="status-dot offline"' in resp.text
    assert "CLI UNAVAILABLE" in resp.text


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


def test_browse_tree_scandir_oserror_returns_error_not_500(client, monkeypatch):
    test_client, tmp_path = client
    (tmp_path / "output" / "thinkers").mkdir()

    def _raise(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("os.scandir", _raise)
    resp = test_client.get("/browse/tree", params={"path": "thinkers"})
    assert resp.status_code == 200
    assert "Could not read folder:" in resp.text


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


def test_browse_root_shows_pipeline_and_corpus_headings(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "Pipeline Outputs" in resp.text
    assert "Corpus Docs" in resp.text


def test_browse_root_no_runs_dir_shows_empty_message(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert resp.status_code == 200
    assert "No pipeline runs yet." in resp.text


def test_browse_tree_pipeline_root_lists_projects_from_filesystem(client):
    test_client, tmp_path = client
    _touch(tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation" / "artifact.v1.md")
    resp = test_client.get("/browse/tree", params={"root": "pipeline"})
    assert resp.status_code == 200
    assert "my-run-20260728-120000" in resp.text


def test_browse_tree_pipeline_root_annotates_brand_from_db(client):
    test_client, tmp_path = client
    _touch(tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation" / "artifact.v1.md")
    from pipeline_app import db as db_mod
    db_mod.create_project(
        test_client.app.state.conn, "my-run-20260728-120000", "my-run",
        "raisinggoodsports", "2026-07-28T12:00:00Z",
    )
    resp = test_client.get("/browse/tree", params={"root": "pipeline"})
    assert resp.status_code == 200
    assert "my-run-20260728-120000 (raisinggoodsports)" in resp.text


def test_browse_tree_pipeline_stage_lists_artifact_versions_numerically(client):
    test_client, tmp_path = client
    stage_dir = tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation"
    _touch(stage_dir / "artifact.v2.md")
    _touch(stage_dir / "artifact.v10.md")
    _touch(stage_dir / "artifact.v1.md")
    resp = test_client.get(
        "/browse/tree",
        params={"root": "pipeline", "path": "my-run-20260728-120000/01-ideation"},
    )
    assert resp.status_code == 200
    assert resp.text.index("artifact.v1.md") < resp.text.index("artifact.v2.md") < resp.text.index("artifact.v10.md")


def test_browse_tree_pipeline_excludes_raw_output(client):
    test_client, tmp_path = client
    stage_dir = tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation"
    _touch(stage_dir / "artifact.v1.md")
    _touch(stage_dir / "raw_output.md")
    resp = test_client.get(
        "/browse/tree",
        params={"root": "pipeline", "path": "my-run-20260728-120000/01-ideation"},
    )
    assert resp.status_code == 200
    assert "raw_output.md" not in resp.text


def test_browse_tree_pipeline_project_shows_grounding_folder_when_pointer_valid(client):
    test_client, tmp_path = client
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "2026-07-28-topic.md").write_text("# Brief", encoding="utf-8")
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "rgs-briefs/2026-07-28-topic.md",
        tmp_path,
    )
    resp = test_client.get(
        "/browse/tree", params={"root": "pipeline", "path": "my-run-20260728-120000"}
    )
    assert resp.status_code == 200
    assert "00-grounding" in resp.text


def test_browse_tree_pipeline_grounding_no_pointer_excluded_from_project(client):
    test_client, tmp_path = client
    (tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding" / "events").mkdir(parents=True)
    resp = test_client.get(
        "/browse/tree", params={"root": "pipeline", "path": "my-run-20260728-120000"}
    )
    assert resp.status_code == 200
    assert "00-grounding" not in resp.text


def test_browse_tree_pipeline_grounding_stage_shows_synthetic_current_brief_entry(client):
    test_client, tmp_path = client
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "2026-07-28-topic.md").write_text("# Brief", encoding="utf-8")
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "rgs-briefs/2026-07-28-topic.md",
        tmp_path,
    )
    resp = test_client.get(
        "/browse/tree",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding"},
    )
    assert resp.status_code == 200
    assert "current-brief.md (2026-07-28-topic.md)" in resp.text


def test_browse_file_pipeline_artifact_renders(client):
    test_client, tmp_path = client
    _touch(
        tmp_path / "runs" / "my-run-20260728-120000" / "01-ideation" / "artifact.v1.md",
        "---\nstatus: draft\n---\n\n# Concept\n\nBody.\n",
    )
    resp = test_client.get(
        "/browse/file",
        params={"root": "pipeline", "path": "my-run-20260728-120000/01-ideation/artifact.v1.md"},
    )
    assert resp.status_code == 200
    assert "<h1>Concept</h1>" in resp.text


def test_browse_file_pipeline_grounding_pointer_renders_target(client):
    test_client, tmp_path = client
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    (briefs_dir / "2026-07-28-topic.md").write_text("# Grounded Brief\n", encoding="utf-8")
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "rgs-briefs/2026-07-28-topic.md",
        tmp_path,
    )
    resp = test_client.get(
        "/browse/file",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding/pointer.yaml"},
    )
    assert resp.status_code == 200
    assert "<h1>Grounded Brief</h1>" in resp.text


def test_browse_file_pipeline_grounding_pointer_missing_target_shows_error(client):
    test_client, tmp_path = client
    from pipeline_app import grounding_service
    briefs_dir = tmp_path / "rgs-briefs"
    briefs_dir.mkdir()
    brief_path = briefs_dir / "does-not-exist.md"
    brief_path.write_text("temporary", encoding="utf-8")
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "rgs-briefs/does-not-exist.md",
        tmp_path,
    )
    brief_path.unlink()
    resp = test_client.get(
        "/browse/file",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding/pointer.yaml"},
    )
    assert resp.status_code == 200
    assert "does not exist" in resp.text


def test_browse_file_pipeline_grounding_pointer_outside_rgs_briefs_shows_error(client):
    # End-to-end containment check: a pointer.yaml whose content resolves
    # somewhere else under repo_root (not rgs-briefs/) must not be followed
    # and must not leak that file's content into the viewer.
    test_client, tmp_path = client
    secret = tmp_path / "runs" / "other-run" / "secret.md"
    secret.parent.mkdir(parents=True)
    secret.write_text("# Secret\n", encoding="utf-8")
    from pipeline_app import grounding_service
    grounding_service.write_pointer(
        tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding",
        "runs/other-run/secret.md",
        tmp_path,
    )
    resp = test_client.get(
        "/browse/file",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding/pointer.yaml"},
    )
    assert resp.status_code == 200
    assert "could not be parsed" in resp.text
    assert "Secret" not in resp.text


def test_browse_file_unknown_root_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/file", params={"root": "bogus", "path": "x.md"})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_tree_unknown_root_returns_invalid_path(client):
    test_client, _ = client
    resp = test_client.get("/browse/tree", params={"root": "bogus", "path": ""})
    assert resp.status_code == 200
    assert "Invalid path." in resp.text


def test_browse_page_carries_a_global_htmx_error_banner(client):
    test_client, _ = client
    resp = test_client.get("/browse")
    assert 'id="htmx-error-banner"' in resp.text
    assert 'role="alert"' in resp.text
    assert "htmx:responseError" in resp.text
    assert "htmx:sendError" in resp.text


def test_browse_tree_expansion_can_be_retried_after_a_failure(client):
    """`once` meant a subtree whose first fetch failed stayed empty forever."""
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md")
    resp = test_client.get("/browse")
    assert 'hx-trigger="toggle from:closest details"' in resp.text
    assert "toggle once" not in resp.text


def test_browse_file_unexpected_exception_renders_an_error_not_a_500(client, monkeypatch):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "plato.md", "---\na: 1\n---\n\nBody.\n")

    def _boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("pipeline_app.browse_service.render_md_file", _boom)
    resp = test_client.get("/browse/file", params={"path": "thinkers/plato.md"})
    assert resp.status_code == 200          # htmx only swaps 2xx
    assert "Could not render this document" in resp.text
    assert "kaboom" in resp.text


def test_browse_file_render_failure_is_distinct_from_an_empty_document(client, monkeypatch):
    test_client, tmp_path = client
    _touch(tmp_path / "output" / "thinkers" / "empty.md", "---\na: 1\n---\n")
    ok = test_client.get("/browse/file", params={"path": "thinkers/empty.md"}).text

    def _boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr("pipeline_app.browse_service.render_md_file", _boom)
    broken = test_client.get("/browse/file", params={"path": "thinkers/empty.md"}).text
    assert broken != ok
    assert "browse-error" in broken
    assert "browse-error" not in ok


def test_unreadable_folder_renders_as_a_disabled_row_with_a_reason(client, monkeypatch):
    """SURFACING."""
    test_client, tmp_path = client
    unreadable = tmp_path / "output" / "locked"
    unreadable.mkdir()
    real_scandir = os.scandir

    def _raise_for_locked(path, *args, **kwargs):
        if Path(path) == unreadable:
            raise OSError("permission denied")
        return real_scandir(path, *args, **kwargs)

    monkeypatch.setattr(os, "scandir", _raise_for_locked)
    resp = test_client.get("/browse")
    assert "locked" in resp.text
    assert "browse-unreadable" in resp.text
    assert "could not be read" in resp.text


def test_broken_grounding_pointer_stays_reachable_through_the_tree(client):
    """SURFACING. The route's 'Grounding pointer could not be resolved.'
    message was unreachable: list_children skipped the entry, so there was
    nothing left to click (E-14b)."""
    test_client, tmp_path = client
    grounding = tmp_path / "runs" / "my-run-20260728-120000" / "00-grounding"
    grounding.mkdir(parents=True)
    (grounding / "pointer.yaml").write_text("brief_path: [unclosed\n", encoding="utf-8")

    project = test_client.get(
        "/browse/tree", params={"root": "pipeline", "path": "my-run-20260728-120000"}
    )
    assert "00-grounding" in project.text            # the folder did not vanish

    stage = test_client.get(
        "/browse/tree",
        params={"root": "pipeline", "path": "my-run-20260728-120000/00-grounding"},
    )
    assert "unresolvable" in stage.text
    assert "browse-broken" in stage.text
