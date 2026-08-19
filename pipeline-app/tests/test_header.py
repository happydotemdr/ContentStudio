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


def test_a_malformed_gates_frontmatter_gets_its_own_explainer(client_with_stage):
    """P3 synthesizes a `malformed` gate entry (routes/stages.py) when the
    artifact's `gates:` value itself isn't a list -- there is no per-gate
    result to interpret, which is a different problem from `unknown` (one
    gate's status string didn't parse). gate_strip.html must not let this
    fall through with no label and no explainer."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    # `gates:` here is a scalar string, not a list -- the malformed shape.
    _stage_with_artifact(app, project["run_id"], "gates: not-a-list\n")
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert "status-malformed" in page
    assert "malformed" in page
    assert "gates:</code> frontmatter" in page or "gates:" in page
    assert "not a list" in page


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


def test_stage_page_ships_a_hidden_turn_complete_affordance(client_with_stage):
    test_client, _app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'id="turn-complete"' in page
    assert "hidden" in page.split('id="turn-complete"')[1][:200]
    assert "Output and Gates below are from before this turn" in page
    assert 'id="turn-complete-reload"' in page


def test_the_sse_result_branch_reveals_the_affordance(client_with_stage):
    """The result branch used to do nothing but statusLine.remove(), which
    reads as 'the turn produced nothing' (E-01)."""
    test_client, _app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'document.getElementById("turn-complete")' in page
    assert "turnComplete.hidden = false" in page


def _seed_run(app, status, error_message=None):
    conn = app.state.conn
    conn.execute(
        "INSERT INTO discovery_runs (run_id, trigger, mode, status, started_at) "
        "VALUES (?, 'manual', 'incremental', ?, '2026-08-08T06:00:00+00:00')",
        (f"run-{status}", status),
    )
    run_row_id = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
    conn.execute(
        "INSERT INTO handles (platform, handle, cohort, added_at) "
        "VALUES ('youtube', ?, 'creator-ed', '2026-08-01T00:00:00+00:00')",
        (f"@thinkmedia-{status}",),
    )
    handle_id = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
    conn.execute(
        "INSERT INTO discovery_run_handles (run_id, handle_id, status, items_downloaded, error_message) "
        "VALUES (?, ?, ?, 0, ?)",
        (run_row_id, handle_id, "error" if error_message else "ok", error_message),
    )
    conn.commit()
    return run_row_id


def test_terminal_run_states_are_visually_distinguishable(client: TestClient):
    app = client.app
    _seed_run(app, "completed")
    _seed_run(app, "completed_with_errors", error_message="HTTP 403 from the API")
    page = client.get("/discovery/runs").text
    assert "status-completed_with_errors" in page
    # A bare "status-completed" in page is also a substring of
    # "status-completed_with_errors", which the line above already
    # separately seeds and asserts -- that would let this pass even if
    # the plain "completed" run's own pill were entirely absent from the
    # page. Anchor on the closing quote of the class attribute so this can
    # only match the exact `status-completed` class, not the errors variant.
    assert 'status-completed"' in page

    css = (Path(__import__("pipeline_app.main", fromlist=["x"]).PACKAGE_DIR)
           / "static" / "style.css").read_text(encoding="utf-8")
    for modifier in (".status-completed_with_errors",
                     ".status-completed",
                     ".status-failed",
                     ".status-queued"):
        assert modifier in css, f"{modifier} pill has no styling -- it renders as a bare pill"


def test_a_run_with_errors_carries_an_error_count_on_its_line(client: TestClient):
    _seed_run(client.app, "completed_with_errors", error_message="HTTP 403 from the API")
    page = client.get("/discovery/runs").text
    assert "1 handle error" in page


@pytest.mark.xfail(
    strict=True,
    reason="db.list_run_handle_results does not yet join handles (P8); until then "
           "the template's honest fallback renders 'unresolved handle id N' instead "
           "of a platform/handle pair. Remove this marker when P8 lands the join.",
)
def test_a_failed_handle_is_named_not_numbered(client: TestClient):
    _seed_run(client.app, "completed_with_errors", error_message="HTTP 403 from the API")
    page = client.get("/discovery/runs").text
    assert "youtube/@thinkmedia" in page
    assert "handle #" not in page, "a bare row id is not an answer to 'which source broke?'"
    assert "HTTP 403 from the API" in page


@pytest.mark.xfail(
    strict=True,
    reason="db.list_run_handle_results does not yet join handles (P8), so neither "
           "row renders a handle name to order by. Remove this marker when P8 lands "
           "the join.",
)
def test_errored_handle_results_are_listed_before_healthy_ones(client: TestClient):
    app = client.app
    run_row_id = _seed_run(app, "completed_with_errors", error_message="HTTP 403 from the API")
    app.state.conn.execute(
        "INSERT INTO handles (platform, handle, cohort, added_at) "
        "VALUES ('bluesky', 'ok.bsky.social', 'creator-ed', '2026-08-01T00:00:00+00:00')"
    )
    ok_id = app.state.conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
    app.state.conn.execute(
        "INSERT INTO discovery_run_handles (run_id, handle_id, status, items_downloaded) "
        "VALUES (?, ?, 'ok', 4)", (run_row_id, ok_id),
    )
    app.state.conn.commit()
    page = client.get("/discovery/runs").text
    assert page.index("@thinkmedia") < page.index("ok.bsky.social")


def test_handle_states_have_distinct_pill_styling(client: TestClient):
    from pipeline_app.main import PACKAGE_DIR
    css = (PACKAGE_DIR / "static" / "style.css").read_text(encoding="utf-8")
    for modifier in (".status-pending", ".status-validating", ".status-validated", ".status-invalid"):
        assert modifier in css


def test_an_invalid_handle_states_a_reason_or_says_none_was_recorded(client: TestClient):
    conn = client.app.state.conn
    conn.execute(
        "INSERT INTO handles (platform, handle, cohort, status, added_at) "
        "VALUES ('youtube', '@gone', 'creator-ed', 'invalid', '2026-08-01T00:00:00+00:00')"
    )
    conn.commit()
    page = client.get("/discovery/handles").text
    assert "status status-invalid" in page
    # No error column exists on `handles` yet, so the honest render is to say
    # so -- never to show a bare word with no recourse.
    assert "no reason recorded" in page


def test_the_status_poller_stops_and_reports_when_a_fetch_fails(client: TestClient):
    page = client.get("/discovery/handles").text
    assert "res.ok" in page
    assert "catch" in page
    assert "status unknown — reload" in page
    assert "clearInterval(poll)" in page


def test_platform_options_match_the_adapter_registry_exactly():
    """The seven <option> values are the only enumeration of trackable
    platforms an operator ever sees, hand-duplicated from build_adapters().
    They agree today and nothing enforced it: a new adapter was silently
    untrackable through the only supported entry point (B-74)."""
    import re
    from pipeline_app.main import PACKAGE_DIR
    from run_discovery_cron import build_adapters

    html = (PACKAGE_DIR / "templates" / "discovery_handles.html").read_text(encoding="utf-8")
    select = re.search(r'<select name="platform">(.*?)</select>', html, re.S).group(1)
    options = set(re.findall(r'<option value="([^"]+)"', select))
    assert options == set(build_adapters().keys())


@pytest.fixture
def client_with_skills(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # shorts-ideation is bound to a real stage so stage_id_by_skill() maps it;
    # midjourney-prompting has no stage entry, so it stays unmapped. The
    # brief's literal fixture used "stages: []", which leaves nothing mapped
    # at all and makes test_a_mapped_skill_still_shows_the_kickoff_editor
    # unsatisfiable regardless of the template fix -- corrected here.
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - id: ideation\n    skill: shorts-ideation\n    dir_prefix: \"01\"\n    depends_on: []\n",
        encoding="utf-8",
    )
    for name in ("shorts-ideation", "midjourney-prompting"):
        d = tmp_path / ".claude" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    (tmp_path / "pipeline-app" / "stage_templates").mkdir(parents=True)
    (tmp_path / "pipeline-app" / "stage_templates" / "ideation.md").write_text(
        "/x", encoding="utf-8"
    )
    app = create_app(repo_root=tmp_path, db_path=tmp_path / "pipeline.db")
    return TestClient(app)


def test_a_skill_with_no_stage_mapping_shows_no_kickoff_editor(client_with_skills):
    """STAGE_ID_BY_SKILL maps 8 of 13 skills. The other five rendered an empty
    textarea with a live Save button targeting a template that does not exist,
    and "no kickoff template" was indistinguishable from "it is empty" (E-15)."""
    page = client_with_skills.get("/skills/midjourney-prompting").text
    assert 'value="kickoff_template"' not in page
    assert "This skill is not bound to a pipeline stage" in page


def test_a_mapped_skill_still_shows_the_kickoff_editor(client_with_skills):
    page = client_with_skills.get("/skills/shorts-ideation").text
    assert 'value="kickoff_template"' in page
    assert 'name="content"' in page


def test_doctor_renders_unacknowledged_error_events(client: TestClient):
    conn = client.app.state.conn
    # The brief's literal fixture hardcoded occurred_at to a fixed calendar
    # date; Doctor's route only shows events within RECENT_EVENT_WINDOW_DAYS
    # (7) of "now", so a fixed date silently ages out of that window as real
    # time passes and the test starts failing for a reason that has nothing
    # to do with Doctor. Timestamped relative to "now" instead, matching the
    # rest of this suite's events (e.g. test_obs.py's use of
    # obs.record_event, which stamps occurred_at itself).
    from datetime import datetime, timezone
    occurred_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO events (occurred_at, kind, severity, source, message, detail, run_id, acknowledged) "
        "VALUES (?, 'adapter.fetch_failed', 'error', "
        "'discovery_youtube', 'yt-dlp exited 1 for @thinkmedia', '{\"handle\": \"@thinkmedia\"}', 4, 0)",
        (occurred_at,),
    )
    conn.commit()
    page = client.get("/doctor").text
    assert "adapter.fetch_failed" in page
    assert "yt-dlp exited 1 for @thinkmedia" in page
    assert "discovery_youtube" in page
    assert "status-error" in page


def test_doctor_says_so_when_there_is_nothing_to_report(client: TestClient):
    page = client.get("/doctor").text
    assert "No unacknowledged errors in the last 7 days." in page


def test_doctor_no_longer_duplicates_the_skill_list(client: TestClient):
    page = client.get("/doctor").text
    assert "Skills discovered:" not in page
    assert 'href="/skills"' in page


def test_a_skipped_orphan_sweep_renders_differently_from_a_clean_one(client: TestClient):
    """P1 types orphaned_count as `int | None`. None means the sweep never ran;
    0 means it ran and found nothing. Rendering both the same -- or printing
    the literal string "None" -- is the same empty-vs-broken confusion this
    programme exists to remove."""
    client.app.state.orphaned_count = 0
    clean = client.get("/doctor").text
    client.app.state.orphaned_count = None
    skipped = client.get("/doctor").text

    assert clean != skipped
    assert "not checked" in skipped
    assert "not checked" not in clean
    assert "None" not in skipped


def test_every_declared_upstream_gets_a_card_including_missing_ones(client_with_stage):
    """A dependency with no artifact used to be dropped by an `is not None`
    guard, so the operator reviewed a partial input believing it complete."""
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert 'class="input-card"' in page
    assert "No upstream input." not in page or 'class="input-card"' in page


def test_a_missing_upstream_is_labelled_missing_not_omitted(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    # `ideation` declares no deps, so this asserts the shape holds at zero;
    # the multi-dep case is P3's fixture. What must never appear is a card
    # that is silently absent.
    assert "input-card-missing" in page or "This stage has no upstream dependencies." in page


def test_the_edit_output_disclosure_exists_when_editing_is_allowed(client_with_stage):
    test_client, app = client_with_stage
    resp = test_client.post(
        "/projects", data={"slug": "abc", "brand": "generic"}, follow_redirects=False
    )
    project_id = int(resp.headers["location"].rsplit("/", 1)[-1])
    project = app.state.conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    _stage_with_artifact(app, project["run_id"], "version: 1\n")
    page = test_client.get(f"/projects/{project_id}/stages/ideation").text
    assert "Edit output" in page
    assert 'name="body"' in page or "edit_field" in page
