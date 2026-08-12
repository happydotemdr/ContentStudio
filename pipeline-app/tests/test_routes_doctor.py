"""Doctor is the operator's only 'what is this app actually seeing' surface.

Finding F-27: this file held one test asserting a 200 and the substring
"Claude CLI" -- a literal the template hard-codes, true whether or not Doctor
reports anything correctly. These assert the five things Doctor uniquely
reports, each by changing the state and observing the report change.

Two departures from the brief's literal test code, both forced by things the
brief text could not have known:

- Each test below needs a differently-configured app (a distinct repo root, a
  distinct skill set, a mutated app.state, or a patched CLI probe), so none of
  them can reuse the shared `client` fixture from tests/conftest.py, which is
  fixed to one tmp_path/skills-dir/config. `create_app()` opens
  app.state.conn, and this suite's `_no_leaked_sqlite_connections` guard fails
  any test that leaves one open (this module is not in conftest.py's
  `_CONNECTION_LEAKS_BY_PACKAGE` allowlist, so a leak here is a hard failure,
  not a warning). `_doctor_client` below is a local, closing-in-`finally`
  stand-in for that fixture, built the same way the shared one is, instead of
  the brief's bare `TestClient(_app_at(...))` -- which would run no lifespan at
  all and so would not close the connection either.

- The CLI-absent/CLI-present test does not monkeypatch `shutil.which`
  directly, despite that being the obvious lever. `check_cli_available`'s
  `which_fn` parameter defaults to `shutil.which`
  (pipeline_app/preflight.py), and that default is bound once, at
  function-definition time -- patching the `shutil.which` module attribute
  afterwards never reaches a call made with no explicit `which_fn`, because
  the bound default is a reference to the original function object, not a
  live lookup. Confirmed empirically: `preflight.check_cli_available.__defaults__[0] is
  shutil.which` stays true after `monkeypatch.setattr(shutil, "which", ...)`.
  On this machine `claude` is genuinely on PATH, so a plain
  `monkeypatch.setattr(shutil, "which", ...)` would make both the "absent"
  and "present" cases render the *same* real result, and every assertion
  below would fail regardless of which case the test intended -- not a
  failure that says anything about Doctor.

  The fix does *not* reassign `check_cli_available.__defaults__` either
  (an earlier version of this test did). That works today, but it assumes
  `which_fn` is the sole, first positional-default parameter of a function
  in `preflight.py` -- a file this task does not own, and one the very next
  package in this programme is about to modify. A parameter added there
  would make the tuple assignment silently target the wrong slot, and this
  test would then fail in a way that looks unrelated to whatever changed.

  Instead, this patches `pipeline_app.preflight.check_cli_available` -- the
  shared `_CliProbe` (main.py) is the only thing Doctor's route now calls
  through, and it calls that module attribute, not a name bound into
  doctor.py's own namespace (A-83 removed doctor.py's direct import of
  `check_cli_available` entirely, so that binding no longer exists to
  patch). That depends only on the stable `{available, path, error}` dict
  contract, not on `check_cli_available`'s parameter shape, and reaches into
  no other package's internals. The trade-off: it exercises only Doctor's
  own rendering, not `check_cli_available`'s/`resolve_claude_binary`'s real
  branching logic -- correct scope for this finding, since that logic is
  `preflight.py`'s own behaviour to cover, not Doctor's.
"""
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from pipeline_app import preflight
from pipeline_app.main import create_app


def _app_at(root: Path, monkeypatch, skills: tuple[str, ...] = ()):
    monkeypatch.chdir(root)
    (root / "pipeline.yaml").write_text("stages: []\n", encoding="utf-8")
    skills_dir = root / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for name in skills:
        (skills_dir / name).mkdir(exist_ok=True)
    return create_app(repo_root=root, db_path=root / "pipeline.db")


@contextmanager
def _doctor_client(root: Path, monkeypatch, skills: tuple[str, ...] = ()):
    """TestClient(_app_at(...)) that closes app.state.conn on the way out.

    create_app() unconditionally opens app.state.conn and registers a lifespan
    that closes it on ASGI shutdown (A-85), which is why the app is entered as
    a context manager here rather than passed bare to TestClient. The `finally`
    stays because it covers the path the lifespan cannot -- startup itself
    raising, so no shutdown event is ever sent. See tests/conftest.py's `client`
    fixture docstring.
    """
    app = _app_at(root, monkeypatch, skills)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.state.conn.close()


def test_doctor_reports_the_repo_root_the_app_is_actually_using(tmp_path, monkeypatch):
    one = tmp_path / "checkout-one"
    one.mkdir()
    with _doctor_client(one, monkeypatch) as client:
        resp = client.get("/doctor")
    assert resp.status_code == 200
    # Scoped to the "Repo root:" line, not a bare substring check: db_path is
    # built as `root / "pipeline.db"`, so its own rendered line always
    # contains str(root) as a prefix too -- a bare `str(one) in resp.text`
    # would pass even if the repo_root context key itself were wrong, because
    # the db_path line would carry it instead.
    assert f"Repo root: {one}" in resp.text


def test_doctor_lists_exactly_the_skills_present_on_disk(tmp_path, monkeypatch):
    with _doctor_client(tmp_path, monkeypatch, skills=("shorts-ideation", "voiceover-brief")) as client:
        text = client.get("/doctor").text
    assert "shorts-ideation" in text
    assert "voiceover-brief" in text
    assert "music-brief" not in text


def test_doctor_distinguishes_a_missing_cli_from_a_found_one(tmp_path, monkeypatch):
    """Distinguishability: 'CLI absent' and 'CLI present' must not render the
    same page. check_cli_available is the only place the app tells an
    operator the pipeline cannot run at all. See the module docstring for why
    this patches `pipeline_app.preflight.check_cli_available` rather than
    shutil.which or check_cli_available.__defaults__."""

    a = tmp_path / "a"
    a.mkdir()
    b = tmp_path / "b"
    b.mkdir()

    monkeypatch.setattr(
        preflight, "check_cli_available",
        lambda: {"available": False, "path": None, "error": "claude CLI not found on PATH."},
    )
    with _doctor_client(a, monkeypatch) as client:
        absent = client.get("/doctor").text

    monkeypatch.setattr(
        preflight, "check_cli_available",
        lambda: {"available": True, "path": r"C:\fake\claude.cmd", "error": None},
    )
    with _doctor_client(b, monkeypatch) as client:
        present = client.get("/doctor").text

    assert "NOT FOUND" in absent
    assert r"C:\fake\claude.cmd" in present
    assert "NOT FOUND" not in present
    assert absent != present


def test_doctor_reports_the_orphaned_turn_count_from_app_state(tmp_path, monkeypatch):
    with _doctor_client(tmp_path, monkeypatch) as client:
        client.app.state.orphaned_count = 7
        text = client.get("/doctor").text
    # Scoped to the actual line, not a bare "7" substring check: tmp_path is a
    # pytest-numbered directory (e.g. "...\\pytest-1367\\..."), so a bare "7"
    # can appear in the rendered repo_root/db_path lines by pure chance and
    # pass even when orphaned_count itself is wrong -- confirmed empirically,
    # this exact false positive fired on one run with orphaned_count
    # hardcoded to 0 in doctor.py.
    assert "Orphaned turns reconciled at startup: 7" in text
