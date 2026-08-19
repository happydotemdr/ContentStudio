"""Rendered-template assertions for the P15 UI package.

Despite the filename this covers every template except the two Browse
partials (those live in test_routes_browse.py): the shared shell, the
three-section nav, the stage page, the discovery pages, the skill editor
and doctor. Everything here asserts on rendered HTML through the FastAPI
TestClient -- there is no browser automation in this suite.
"""
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
def test_every_page_renders_the_three_section_top_nav(client: TestClient, url: str):
    resp = client.get(url)
    assert resp.status_code == 200
    assert 'class="wordmark"' in resp.text
    assert 'class="top-nav"' in resp.text
    assert 'class="status-dot' in resp.text
    # Exactly three top-level sections -- Skills/Doctor/Inspector/Browse are
    # demoted into Library, and the two Discovery entries collapse to one.
    import re
    nav = re.search(r'<nav class="top-nav">(.*?)</nav>', resp.text, re.S).group(1)
    assert re.findall(r'<a href="([^"]+)"', nav) == ["/", "/discovery/handles", "/browse"]
    assert ">Projects<" in nav and ">Discovery<" in nav and ">Library<" in nav
    assert "Discovery Runs" not in nav


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/skills", ["/browse", "/skills", "/doctor", "/inspector"]),
        ("/doctor", ["/browse", "/skills", "/doctor", "/inspector"]),
        ("/inspector", ["/browse", "/skills", "/doctor", "/inspector"]),
    ],
)
def test_library_pages_render_the_library_tab_strip(client: TestClient, url, expected):
    import re
    resp = client.get(url)
    strip = re.search(r'<nav class="sub-nav">(.*?)</nav>', resp.text, re.S).group(1)
    assert re.findall(r'<a href="([^"#]+)', strip) == expected


def test_the_current_section_and_tab_are_both_marked_active(client: TestClient):
    resp = client.get("/doctor")
    assert '<a href="/browse" class="active">Library</a>' in resp.text
    assert '<a href="/doctor" class="active">System</a>' in resp.text


def test_projects_page_has_no_tab_strip(client: TestClient):
    resp = client.get("/")
    assert 'class="sub-nav"' not in resp.text


def test_pages_without_a_stage_rail_ship_no_aside_at_all(client: TestClient):
    resp = client.get("/")
    assert 'class="app-shell"' in resp.text
    assert 'class="app-main"' in resp.text
    assert "<aside" not in resp.text


def test_a_project_page_does_ship_the_stage_rail_aside(client_with_stage):
    test_client, _app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert 'class="app-sidebar"' in page.text
    assert 'class="pipeline-nav"' in page.text


def test_project_home_and_stage_page_mark_projects_active_with_breadcrumb(client: TestClient):
    resp = client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])

    resp = client.get(f"/projects/{project_id}")
    assert '<a href="/" class="active">Projects</a>' in resp.text
    # The header always renders a breadcrumb once `project` is set, project-home
    # included -- but with no stage_id there is no " / <stage>" segment.
    import re
    run_id = re.search(r'<a href="/projects/\d+">([^<]+)</a>', resp.text).group(1)
    assert f'<a href="/projects/{project_id}">{run_id}</a>' in resp.text
    assert 'class="breadcrumb-current"' not in resp.text  # no stage_id on the project-home page


@pytest.fixture
def client_with_stage(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n"
        "  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    skill_dir = tmp_path / ".claude" / "skills" / "shorts-ideation"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "pipeline-app" / "stage_templates").mkdir(parents=True)
    (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").write_text("/x", encoding="utf-8")
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app), app


def test_stage_page_shows_breadcrumb_with_run_id_and_stage_id(client_with_stage):
    test_client, app = client_with_stage

    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()

    stage_resp = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert stage_resp.status_code == 200
    assert 'class="breadcrumb"' in stage_resp.text
    assert f'<a href="/projects/{project_id}">{project["run_id"]}</a>' in stage_resp.text
    assert '<span class="breadcrumb-current">ideation</span>' in stage_resp.text


def test_stage_breadcrumb_links_back_to_the_project(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()

    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert f'<a href="/projects/{project_id}">{project["run_id"]}</a>' in page.text
    assert "ideation" in page.text


def test_no_template_references_an_external_host():
    """CLAUDE.md says local-only. A CDN <script> is an undocumented outbound
    dependency with no SRI (D-41) and a silent offline failure (D-42)."""
    from pipeline_app.main import PACKAGE_DIR
    offenders = []
    for path in sorted((PACKAGE_DIR / "templates").rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for scheme in ("https://", "http://", "//unpkg.com"):
            if scheme in text:
                offenders.append(f"{path.name}: {scheme}")
    assert offenders == []


def test_project_home_shows_a_gate_roll_up_and_a_next_action(client_with_stage):
    test_client, _app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}")
    assert page.status_code == 200
    assert 'class="project-rollup"' in page.text
    assert "Next action" in page.text
    # A fresh project's only stage is ready -- the overview must name it and
    # link straight to it rather than making the operator read the rail.
    assert f'href="/projects/{project_id}/stages/ideation"' in page.text
    assert "ready" in page.text


def test_htmx_is_served_from_the_local_static_mount(client: TestClient):
    from pipeline_app.main import PACKAGE_DIR
    vendored = PACKAGE_DIR / "static" / "htmx-2.0.0.min.js"
    assert vendored.is_file(), "htmx must be vendored, not fetched from a CDN"
    assert vendored.stat().st_size > 10_000, "vendored htmx looks truncated"

    resp = client.get("/")
    assert '<script src="/static/htmx-2.0.0.min.js"></script>' in resp.text

    served = client.get("/static/htmx-2.0.0.min.js")
    assert served.status_code == 200
    assert "javascript" in served.headers["content-type"]


@pytest.mark.parametrize(
    "url,heading",
    [
        ("/browse", "Files"),
        ("/doctor", "System"),
        ("/inspector", "Open by path"),
        ("/discovery/handles", "Sources"),
        ("/discovery/runs", "Runs"),
    ],
)
def test_page_heading_matches_its_own_tab_label(client: TestClient, url, heading):
    resp = client.get(url)
    assert f"<h1>{heading}</h1>" in resp.text


def test_stage_page_status_strip_states_status_version_and_generated_at(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    stage_dir = app.state.repo_root / "runs" / project["run_id"] / "01-ideation"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "artifact.v3.md").write_text(
        "---\nversion: 3\ncreated_at: '2026-08-08T10:00:00+00:00'\n"
        "finalized_at: '2026-08-08T10:05:00+00:00'\n"
        "gate_override:\n  reason: dash is inside a verbatim 1886 quote\n"
        "  at: '2026-08-08T10:05:00+00:00'\n---\n\nBody.\n",
        encoding="utf-8",
    )
    page = test_client.get(f"/projects/{project_id}/stages/ideation")
    assert 'class="status-strip"' in page.text
    assert "artifact v3" in page.text
    assert "2026-08-08T10:00:00+00:00" in page.text
    assert "dash is inside a verbatim 1886 quote" in page.text


def _stage_with_artifact(app, project_run_id, frontmatter):
    stage_dir = app.state.repo_root / "runs" / project_run_id / "01-ideation"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "artifact.v1.md").write_text(
        f"---\n{frontmatter}---\n\n# Artifact body\n", encoding="utf-8"
    )
    return stage_dir


def test_gate_panel_renders_above_the_artifact_body(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "gates:\n  - name: gate-x\n    status: pass\n")
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert page.index('class="gates-panel"') < page.index("Artifact body"), \
        "the gate verdict is the page's most decision-relevant fact and must precede the body"


def test_a_gate_that_never_ran_is_rendered_as_never_ran(client_with_stage):
    """THE E-02/E-03 test. An artifact carrying no result for a registered
    gate must not present as a clean pass."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "version: 1\n")   # no `gates:` key at all
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'class="gates-panel"' in page, "the panel must not vanish when no gate ran"
    assert "never ran" in page
    assert "status-never_ran" in page


def test_never_ran_page_differs_from_a_genuinely_clean_pass(client_with_stage):
    """Distinguishability: broken != legitimately-fine."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    url = f"/projects/{project_id}/stages/ideation"

    _stage_with_artifact(app, project["run_id"], "version: 1\n")
    never_ran = test_client.get(url).text

    # Uses the ideation stage's actual registered gate name
    # (gates.GATE_REGISTRY["ideation"]) rather than the placeholder "gate-x" --
    # classify_gates unions recorded results with the registry by name, so a
    # recorded result under any other name still leaves the real registered
    # gate reading as never_ran, which would make this "clean" page
    # indistinguishable from the never-ran one and defeat the test's point.
    stage_dir = app.state.repo_root / "runs" / project["run_id"] / "01-ideation"
    (stage_dir / "artifact.v2.md").write_text(
        "---\nversion: 2\ngates:\n  - name: gate_o_ideation_contract\n    status: pass\n---\n\n# Artifact body\n",
        encoding="utf-8",
    )
    clean = test_client.get(url).text

    assert never_ran != clean
    assert "never ran" in never_ran and "never ran" not in clean


def test_an_unrecognised_gate_status_reads_as_unverified_not_as_a_pass(client_with_stage):
    """P3's fifth state. A typo'd or future status string must not fall
    through to something that looks benign."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "gates:\n  - name: gate-x\n    status: passsed\n")
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert "status-unknown" in page
    assert "unrecognised result" in page
    assert "passsed" in page          # status_raw is shown, not swallowed
    assert "status-passed" not in page


def test_never_ran_gate_page_offers_a_usable_next_action(client_with_stage):
    """THE mandated E-03 test. A gate that never ran must (a) say so and
    (b) leave a way to complete the approval from inside the UI."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "version: 1\n")   # no gate result recorded

    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert "never ran" in page                                  # (a) it says so
    assert 'name="override_reason"' in page                     # (b) the field exists
    assert 'id="approve-blocked-reason"' in page                # and the reason is inline


def test_a_blocked_approve_re_renders_the_stage_page_not_plain_text(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "version: 1\n")

    blocked = test_client.post(
        f"/projects/{project_id}/stages/ideation/approve",
        data={"override_reason": ""}, follow_redirects=False,
    )
    assert blocked.status_code == 409
    assert 'class="top-nav"' in blocked.text          # a real page, not a text document
    assert 'class="approval-error"' in blocked.text
    assert "data-error-kind=" in blocked.text         # P3's error_banner.kind
    assert 'name="override_reason"' in blocked.text   # retry without navigating back


def test_a_healthy_stage_approve_form_has_no_override_field(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    # NOTE: uses "gate_o_ideation_contract" -- the stage's actual GATE_REGISTRY
    # entry (see gates.py) -- rather than the brief's literal "gate-x", which
    # would leave the real registered gate unreported and therefore
    # synthesized as a blocking never_ran result regardless of template
    # changes. test_never_ran_page_differs_from_a_genuinely_clean_pass above
    # establishes the same pattern for its "clean" case.
    _stage_with_artifact(
        app, project["run_id"], "gates:\n  - name: gate_o_ideation_contract\n    status: pass\n"
    )
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'name="override_reason"' not in page
