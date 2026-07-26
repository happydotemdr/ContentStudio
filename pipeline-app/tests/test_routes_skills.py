from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline_app import git_helper
from pipeline_app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    skill_dir = tmp_path / ".claude" / "skills" / "shorts-ideation"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("original content", encoding="utf-8")
    (tmp_path / "pipeline-app" / "stage_templates").mkdir(parents=True)
    (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").write_text("/shorts-ideation", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), tmp_path


def test_skill_list_shows_discovered_skill(client):
    test_client, tmp_path = client
    resp = test_client.get("/skills")
    assert resp.status_code == 200
    assert "shorts-ideation" in resp.text


def test_skill_detail_shows_skill_md_content(client):
    test_client, tmp_path = client
    resp = test_client.get("/skills/shorts-ideation")
    assert resp.status_code == 200
    assert "original content" in resp.text


def test_save_skill_md_writes_file_and_commits(client, monkeypatch):
    test_client, tmp_path = client
    calls = []
    monkeypatch.setattr(
        git_helper, "commit_skill_edit",
        lambda repo_root, file_path, skill_name, now=None: calls.append((file_path, skill_name)),
    )
    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "SKILL.md", "content": "edited content"},
    )
    assert resp.status_code in (200, 303, 307)
    saved = (tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md").read_text(encoding="utf-8")
    assert saved == "edited content"
    assert len(calls) == 1


def test_save_kickoff_template_does_not_commit(client, monkeypatch):
    test_client, tmp_path = client
    calls = []
    monkeypatch.setattr(
        git_helper, "commit_skill_edit",
        lambda *a, **k: calls.append(1),
    )
    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "kickoff_template", "content": "/shorts-ideation new kickoff"},
    )
    assert resp.status_code in (200, 303, 307)
    saved = (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").read_text(encoding="utf-8")
    assert saved == "/shorts-ideation new kickoff"
    assert calls == []


def test_save_rejects_unknown_skill_name(client):
    test_client, tmp_path = client
    resp = test_client.post(
        "/skills/..%2f..%2f..%2fetc/save",
        data={"target": "SKILL.md", "content": "malicious"},
    )
    assert resp.status_code == 404


def test_detail_rejects_unknown_skill_name(client):
    test_client, tmp_path = client
    resp = test_client.get("/skills/not-a-real-skill")
    assert resp.status_code == 404


def test_save_rejects_unknown_skill_name_clean_segment(client, monkeypatch):
    # Unlike the `..%2f...`-encoded case above (which may 404 purely from
    # route/path normalization before ever reaching our handler), this uses a
    # single clean path segment that unambiguously matches the
    # `/skills/{skill_name}/save` route but is absent from the discovered
    # set — proving the discovered-set validation itself runs on the save
    # path, not just that some 404 happens to come back.
    test_client, tmp_path = client
    calls = []
    monkeypatch.setattr(
        git_helper, "commit_skill_edit",
        lambda *a, **k: calls.append(1),
    )
    resp = test_client.post(
        "/skills/not-a-real-skill/save",
        data={"target": "SKILL.md", "content": "malicious"},
    )
    assert resp.status_code == 404
    assert not (tmp_path / ".claude" / "skills" / "not-a-real-skill").exists()
    assert calls == []
