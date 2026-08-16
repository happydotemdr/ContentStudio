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


@pytest.fixture
def symlink_or_skip(tmp_path):
    def make(link: Path, target: Path):
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"symlinks not permitted on this host: {exc}")
    return make


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


def test_the_editor_reads_the_same_mapping_pipeline_config_publishes(client):
    from pipeline_app.pipeline_config import stage_id_by_skill
    test_client, _ = client
    defs = test_client.app.state.stage_defs
    assert stage_id_by_skill(defs) == {"shorts-ideation": "ideation",
                                       "shorts-scripting": "scripting",
                                       "shorts-styleboard": "styleboard"}


def test_skill_md_save_produces_a_real_scoped_commit(client):
    test_client, tmp_path = client
    body = SKILL_MD.format(name="shorts-ideation") + "edited content\n"

    resp = test_client.post("/skills/shorts-ideation/save",
                            data={"target": "SKILL.md", "content": body},
                            follow_redirects=False)

    assert resp.status_code == 303
    assert (tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md").read_text(
        encoding="utf-8") == body
    files = subprocess.run(["git", "show", "--name-only", "--pretty=format:", "HEAD"],
                           cwd=tmp_path, check=True, capture_output=True,
                           encoding="utf-8", errors="replace").stdout.split()
    assert files == [".claude/skills/shorts-ideation/SKILL.md"]


def test_kickoff_template_save_is_committed_like_skill_md(client):
    """Inverted from test_save_kickoff_template_does_not_commit (F-21), which
    asserted `calls == []` with no rationale and thereby pinned A-52: a bad
    kickoff-template save had no recovery path, while SKILL.md did."""
    test_client, tmp_path = client

    resp = test_client.post("/skills/shorts-ideation/save",
                            data={"target": "kickoff_template",
                                  "content": "/shorts-ideation new kickoff\n"},
                            follow_redirects=False)

    assert resp.status_code == 303
    assert (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").read_text(
        encoding="utf-8") == "/shorts-ideation new kickoff\n"
    show = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:%s", "HEAD"], cwd=tmp_path,
        check=True, capture_output=True, encoding="utf-8", errors="replace").stdout
    assert "ideation" in show.splitlines()[0]        # the message names the stage
    assert show.split()[-1] == "pipeline-app/stage_templates/ideation.md"


def test_both_editable_surfaces_have_the_same_durability(client):
    """Distinguishability: before the fix, SKILL.md produced a commit and a
    kickoff template produced none — the same UI, two different guarantees."""
    test_client, tmp_path = client
    test_client.post("/skills/shorts-ideation/save",
                     data={"target": "SKILL.md",
                           "content": SKILL_MD.format(name="shorts-ideation") + "edit\n"})
    test_client.post("/skills/shorts-ideation/save",
                     data={"target": "kickoff_template", "content": "/shorts-ideation v2\n"})

    log = subprocess.run(["git", "log", "--oneline"], cwd=tmp_path, check=True,
                         capture_output=True, encoding="utf-8", errors="replace").stdout
    assert log.count("skill edit") == 2


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


def test_kickoff_save_for_a_stageless_skill_is_rejected_and_creates_no_None_md(client):
    test_client, tmp_path = client
    templates = tmp_path / "pipeline-app" / "stage_templates"

    resp = test_client.post(
        "/skills/rgs-pairing-review/save",
        data={"target": "kickoff_template", "content": "junk"},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert "rgs-pairing-review" in resp.text
    assert not (templates / "None.md").exists()
    assert sorted(p.name for p in templates.iterdir()) == ["ideation.md", "scripting.md", "styleboard.md"]


def test_stageless_kickoff_rejection_differs_from_a_real_kickoff_save(client):
    test_client, _ = client
    real = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "kickoff_template", "content": "/shorts-ideation v2\n"},
        follow_redirects=False,
    )
    stageless = test_client.post(
        "/skills/rgs-pairing-review/save",
        data={"target": "kickoff_template", "content": "/shorts-ideation v2\n"},
        follow_redirects=False,
    )
    assert (real.status_code, stageless.status_code) == (303, 400)


@pytest.mark.parametrize("blank", ["", "   ", "\n\n", "\r\n\t "])
def test_blank_content_never_truncates_a_file(client, blank):
    test_client, tmp_path = client
    skill_md = tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    before = skill_md.read_text(encoding="utf-8")

    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "SKILL.md", "content": blank},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert skill_md.read_text(encoding="utf-8") == before
    assert skill_md.stat().st_size > 0


@pytest.mark.parametrize("body, reason", [
    ("just prose, no frontmatter\n", "frontmatter"),
    ("---\nname: x\n", "not closed"),
    ("---\nname: x\n---\n\nbody\n", "description"),
    ("---\ndescription: y\n---\n\nbody\n", "name"),
    ("---\nname: [oops\n---\n\nbody\n", "valid YAML"),
])
def test_skill_md_save_requires_loadable_frontmatter(client, body, reason):
    test_client, tmp_path = client
    skill_md = tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md"
    before = skill_md.read_text(encoding="utf-8")

    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "SKILL.md", "content": body},
        follow_redirects=False,
    )

    assert resp.status_code == 400
    assert reason in resp.text
    assert skill_md.read_text(encoding="utf-8") == before


def test_a_kickoff_template_is_not_held_to_the_frontmatter_rule(client):
    """Distinguishability: the SKILL.md rule must not leak onto templates,
    which are plain slash-command text."""
    test_client, tmp_path = client
    resp = test_client.post(
        "/skills/shorts-ideation/save",
        data={"target": "kickoff_template", "content": "/shorts-ideation go\n"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").read_text(
        encoding="utf-8") == "/shorts-ideation go\n"


def test_detail_flags_a_missing_skill_md_instead_of_rendering_empty(client):
    test_client, tmp_path = client
    (tmp_path / ".claude" / "skills" / "shorts-scripting" / "SKILL.md").unlink()

    present = test_client.get("/skills/shorts-ideation")
    absent = test_client.get("/skills/shorts-scripting")

    assert present.context["skill_md_missing"] is False
    assert absent.context["skill_md_missing"] is True
    assert absent.context["skill_md_content"] == ""


@pytest.mark.parametrize("target, rel", [
    ("SKILL.md", (".claude", "skills", "shorts-ideation", "SKILL.md")),
    ("kickoff_template", ("pipeline-app", "stage_templates", "ideation.md")),
])
def test_browser_crlf_is_written_as_lf_not_doubled(client, target, rel):
    """A <textarea> submits CRLF; write_text(newline=None) then translated
    every \\n to os.linesep, producing \\r\\r\\n on Windows (A-55)."""
    test_client, tmp_path = client
    body = ("---\r\nname: shorts-ideation\r\ndescription: d\r\n---\r\n\r\nline one\r\nline two\r\n"
            if target == "SKILL.md" else "/shorts-ideation\r\nline two\r\n")

    resp = test_client.post(f"/skills/shorts-ideation/save",
                            data={"target": target, "content": body}, follow_redirects=False)

    assert resp.status_code == 303
    raw = tmp_path.joinpath(*rel).read_bytes()
    assert b"\r\r\n" not in raw
    assert b"\r" not in raw
    assert raw.decode("utf-8").endswith("line two\n")


def test_a_symlinked_skill_directory_is_not_discovered(client, symlink_or_skip, tmp_path):
    """is_dir() follows symlinks, so a link in .claude/skills/ joined the
    discovered set and the save route wrote THROUGH it (A-56)."""
    outside = tmp_path.parent / "outside-the-repo"
    outside.mkdir(exist_ok=True)
    (outside / "SKILL.md").write_text("victim\n", encoding="utf-8")
    test_client, root = client
    symlink_or_skip(root / ".claude" / "skills" / "escape", outside)

    listing = test_client.get("/skills")
    detail = test_client.get("/skills/escape")
    save = test_client.post("/skills/escape/save",
                            data={"target": "SKILL.md", "content": "pwned\n"},
                            follow_redirects=False)

    assert "escape" not in listing.text
    assert detail.status_code == 404
    assert save.status_code == 404
    assert (outside / "SKILL.md").read_text(encoding="utf-8") == "victim\n"


def test_a_failed_commit_still_saves_the_file_and_warns_rather_than_500ing(client, monkeypatch):
    """The write happened first, then two check=True subprocesses; a failing
    hook 500'd a save that had in fact succeeded (A-54)."""
    from pipeline_app import git_helper
    test_client, tmp_path = client
    monkeypatch.setattr(
        git_helper, "commit_skill_edit",
        lambda *a, **k: git_helper.CommitResult(status="failed", detail="pre-commit hook failed"),
    )
    body = SKILL_MD.format(name="shorts-ideation")

    resp = test_client.post("/skills/shorts-ideation/save",
                            data={"target": "SKILL.md", "content": body},
                            follow_redirects=False)

    assert resp.status_code == 303
    assert "warning=" in resp.headers["location"]
    assert (tmp_path / ".claude" / "skills" / "shorts-ideation" / "SKILL.md").read_text(
        encoding="utf-8") == body


def test_the_three_save_outcomes_are_three_different_responses(client, monkeypatch):
    """Distinguishability, the whole point of this package: saved+committed,
    saved-but-not-committed, and wrote-nothing were ONE 303."""
    from pipeline_app import git_helper
    test_client, _ = client
    body = SKILL_MD.format(name="shorts-ideation")

    committed = test_client.post("/skills/shorts-ideation/save",
                                 data={"target": "SKILL.md", "content": body},
                                 follow_redirects=False)
    monkeypatch.setattr(git_helper, "commit_skill_edit",
                        lambda *a, **k: git_helper.CommitResult(status="failed", detail="nope"))
    uncommitted = test_client.post("/skills/shorts-ideation/save",
                                   data={"target": "SKILL.md", "content": body + "# more\n"},
                                   follow_redirects=False)
    nothing = test_client.post("/skills/shorts-ideation/save",
                               data={"target": "bogus", "content": body},
                               follow_redirects=False)

    outcomes = {
        (committed.status_code, "warning=" in committed.headers.get("location", "")),
        (uncommitted.status_code, "warning=" in uncommitted.headers.get("location", "")),
        (nothing.status_code, False),
    }
    assert len(outcomes) == 3


def events(test_client, kind: str) -> list[dict]:
    """Query the events table by kind, returning a list of dicts."""
    import json
    app = test_client.app
    rows = app.state.conn.execute(
        "SELECT id, kind, severity, source, message, detail FROM events WHERE kind = ? ORDER BY id",
        (kind,),
    ).fetchall()
    result = []
    for row in rows:
        row_dict = dict(row)
        if row_dict.get("detail"):
            row_dict["detail"] = json.loads(row_dict["detail"])
        result.append(row_dict)
    return result


@pytest.mark.parametrize("finding, skill, data, kind", [
    ("A-49", "shorts-ideation",
     {"target": "typo", "content": "x"}, "skill_editor.save_rejected"),
    ("A-50", "rgs-pairing-review",
     {"target": "kickoff_template", "content": "x"}, "skill_editor.save_rejected"),
    ("A-51-blank", "shorts-ideation",
     {"target": "SKILL.md", "content": "   "}, "skill_editor.save_rejected"),
    ("A-51-frontmatter", "shorts-ideation",
     {"target": "SKILL.md", "content": "no frontmatter\n"}, "skill_editor.save_rejected"),
])
def test_a_rejected_save_is_findable_afterwards(client, finding, skill, data, kind):
    """Not a print(): a human-reachable row. Asserting a print happened is
    exactly the 35-site defect D-02."""
    test_client, _ = client
    assert events(test_client, kind) == []

    test_client.post(f"/skills/{skill}/save", data=data, follow_redirects=False)

    rows = events(test_client, kind)
    assert len(rows) == 1
    assert rows[0]["severity"] == "warning"
    assert rows[0]["source"] == "routes.skills"
    assert skill in rows[0]["message"] or skill in (rows[0]["detail"] or "")


def test_a_successful_save_is_findable_and_is_a_different_row(client):
    test_client, _ = client
    test_client.post("/skills/shorts-ideation/save",
                     data={"target": "SKILL.md",
                           "content": SKILL_MD.format(name="shorts-ideation") + "x\n"})
    saved = events(test_client, "skill_editor.saved")
    assert len(saved) == 1
    assert saved[0]["severity"] == "info"
    assert events(test_client, "skill_editor.save_rejected") == []


def test_a_failed_commit_is_findable_at_error_severity(client, monkeypatch):
    from pipeline_app import git_helper
    test_client, _ = client
    monkeypatch.setattr(git_helper, "commit_skill_edit",
                        lambda *a, **k: git_helper.CommitResult(status="failed", detail="hook"))
    test_client.post("/skills/shorts-ideation/save",
                     data={"target": "SKILL.md",
                           "content": SKILL_MD.format(name="shorts-ideation") + "x\n"})
    rows = events(test_client, "skill_editor.commit_failed")
    assert len(rows) == 1 and rows[0]["severity"] == "error"


def test_a_stage_with_no_editor_binding_is_findable(client, tmp_path):
    from pipeline_app import obs
    test_client, root = client
    (root / "pipeline-app" / "stage_templates" / "styleboard.md").unlink()
    test_client.get("/skills/shorts-styleboard")
    # obs.log's LOG_DIR is fixed to the real pipeline-app/logs/, not repo_root -- it is NOT
    # sandboxed per-test, so assert against the real location and only check for the event's
    # presence (not exclusivity: other tests running in the same process may also log here).
    logs = sorted(obs.LOG_DIR.glob("app-*.log"))
    assert logs and "skill_editor.template_file_missing" in logs[-1].read_text(encoding="utf-8")
