from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient

from pipeline_app import git_helper
from pipeline_app.main import create_app

pytestmark = pytest.mark.allow_subprocess

PIPELINE_YAML = (
    "stages:\n"
    "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n"
    "  - id: scripting\n    skill: shorts-scripting\n    dir_prefix: \"02\"\n"
    "    depends_on: [ideation]\n"
    "  - id: styleboard\n    skill: shorts-styleboard\n    dir_prefix: \"02b\"\n"
    "    depends_on: [scripting]\n"
)

SKILL_MD = "---\nname: {name}\ndescription: A real description.\n---\n\nBody.\n"


def _init_repo(root: Path) -> None:
    # `git init` lands on init.defaultBranch, which is `main` or `master` on
    # most machines -- both PROTECTED_BRANCHES (D-51). The editor's happy path
    # is a working branch, so the fixture models that; the protected-branch
    # refusal gets its own repo in test_git_helper.py.
    subprocess.run(["git", "init", "-b", "skill-edits"], cwd=root, check=True,
                   capture_output=True, encoding="utf-8", errors="replace")
    for key, value in (("user.email", "test@example.com"), ("user.name", "Test User")):
        subprocess.run(["git", "config", key, value], cwd=root, check=True,
                       capture_output=True, encoding="utf-8", errors="replace")
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=root, check=True,
                   capture_output=True, encoding="utf-8", errors="replace")


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(PIPELINE_YAML, encoding="utf-8")
    for name in ("shorts-ideation", "shorts-scripting", "shorts-styleboard",
                 "rgs-pairing-review"):
        skill_dir = tmp_path / ".claude" / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(SKILL_MD.format(name=name), encoding="utf-8")
    templates = tmp_path / "pipeline-app" / "stage_templates"
    templates.mkdir(parents=True)
    (templates / "ideation.md").write_text("/shorts-ideation\n", encoding="utf-8")
    (templates / "scripting.md").write_text("/shorts-scripting\n", encoding="utf-8")
    (templates / "styleboard.md").write_text("/shorts-styleboard\n", encoding="utf-8")
    _init_repo(tmp_path)
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
    assert "Body." in resp.text


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


def test_styleboard_kickoff_template_is_editable(client):
    """shorts-styleboard is a real stage in pipeline.yaml with a real template
    on disk. The hardcoded STAGE_ID_BY_SKILL omitted it, so its editor showed
    an empty box over a populated file (A-48)."""
    test_client, _ = client
    resp = test_client.get("/skills/shorts-styleboard")
    assert resp.status_code == 200
    assert "/shorts-styleboard" in resp.text


def test_missing_template_file_is_distinguishable_from_no_template_at_all(client):
    """Three states rendered identically as "" before this fix:
      (a) skill has no stage    -> no kickoff form applies
      (b) skill has a stage but the template file is absent
      (c) the template file exists and is genuinely empty
    """
    test_client, tmp_path = client
    (tmp_path / "pipeline-app" / "stage_templates" / "styleboard.md").unlink()

    no_stage = test_client.get("/skills/rgs-pairing-review")
    missing_file = test_client.get("/skills/shorts-styleboard")
    present = test_client.get("/skills/shorts-ideation")

    ctx_a = no_stage.context
    ctx_b = missing_file.context
    ctx_c = present.context
    assert (ctx_a["stage_id"], ctx_a["kickoff_template_applies"]) == (None, False)
    assert (ctx_b["stage_id"], ctx_b["kickoff_template_applies"],
            ctx_b["kickoff_template_missing"]) == ("styleboard", True, True)
    assert (ctx_c["stage_id"], ctx_c["kickoff_template_applies"],
            ctx_c["kickoff_template_missing"]) == ("ideation", True, False)
    assert ctx_b["kickoff_template_content"] == ctx_c["kickoff_template_content"] == "" \
        or ctx_c["kickoff_template_content"] != ""


def test_unknown_target_is_rejected_and_writes_nothing(client):
    test_client, tmp_path = client
    skill_md = tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    before = skill_md.read_text(encoding="utf-8")

    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "skill_md", "content": "edited"},   # renamed hidden input
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert "skill_md" in resp.text          # names the target it refused
    assert skill_md.read_text(encoding="utf-8") == before


def test_a_save_that_wrote_nothing_is_not_the_same_response_as_a_save_that_wrote(client):
    """Distinguishability: the 303 was indistinguishable between a real write
    and a no-op (A-49)."""
    test_client, _ = client
    wrote = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "SKILL.md", "content": SKILL_MD.format(name="shorts-ideation")},
        follow_redirects=False,
    )
    wrote_nothing = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "nonsense", "content": "x"},
        follow_redirects=False,
    )
    assert wrote.status_code == 303
    assert wrote_nothing.status_code != wrote.status_code
