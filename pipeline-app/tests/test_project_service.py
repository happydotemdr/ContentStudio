import datetime
from pathlib import Path

import pytest

from pipeline_app import db
from pipeline_app.pipeline_config import StageDef
from pipeline_app.project_service import create_project

STAGES = [
    StageDef(id="grounding", skill="rgs-grounding", dir_prefix="00", depends_on=[], brand_scope="raisinggoodsports"),
    StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[]),
    StageDef(id="scripting", skill="shorts-scripting", dir_prefix="02", depends_on=["ideation"]),
]


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    connection = db.get_connection(db_path)
    yield connection
    connection.close()


def test_generic_project_has_no_grounding_stage_or_directory(conn, tmp_path: Path):
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    result = create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES, now=now)
    assert result["run_id"] == "why-kids-quit-20260725-143200"
    assert not (result["run_dir"] / "00-grounding").exists()
    assert (result["run_dir"] / "01-ideation").exists()
    rows = db.list_stages(conn, result["project_id"])
    assert {r["stage_id"] for r in rows} == {"ideation", "scripting"}


def test_rgs_project_includes_grounding_stage_and_directory(conn, tmp_path: Path):
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    result = create_project(conn, tmp_path, "why-kids-quit", "raisinggoodsports", STAGES, now=now)
    assert (result["run_dir"] / "00-grounding").exists()
    rows = db.list_stages(conn, result["project_id"])
    assert {r["stage_id"] for r in rows} == {"grounding", "ideation", "scripting"}


def test_traversal_slug_cannot_escape_the_runs_directory(conn, tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    runs_root = (repo_root / "runs").resolve()
    before = {p.name for p in tmp_path.iterdir()}

    result = create_project(conn, repo_root, "../../pwned", "generic", STAGES)

    run_dir = result["run_dir"].resolve()
    assert run_dir.parent == runs_root
    assert run_dir.is_relative_to(runs_root)
    assert ".." not in result["run_id"]
    # nothing new was created alongside/above the repo root
    assert {p.name for p in tmp_path.iterdir()} == before


def test_slug_with_no_usable_characters_is_rejected(conn, tmp_path: Path):
    with pytest.raises(ValueError):
        create_project(conn, tmp_path, "../..", "generic", STAGES)


def test_slug_is_normalised_to_lowercase_hyphenated_form(conn, tmp_path: Path):
    now = datetime.datetime(2026, 7, 25, 14, 32, 0, tzinfo=datetime.timezone.utc)
    result = create_project(conn, tmp_path, "  Why Kids QUIT!  ", "generic", STAGES, now=now)
    assert result["run_id"] == "why-kids-quit-20260725-143200"


def test_stages_with_no_dependencies_start_ready_others_locked(conn, tmp_path: Path):
    result = create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES)
    ideation = db.get_stage(conn, result["project_id"], "ideation")
    scripting = db.get_stage(conn, result["project_id"], "scripting")
    assert ideation["status"] == "ready"
    assert scripting["status"] == "locked"


def _rolled_back_events(db_path: Path) -> list:
    """Read on a fresh connection -- reading on the connection that wrote the
    row would pass whether or not it was ever actually committed."""
    other = db.get_connection(db_path)
    try:
        return other.execute(
            "SELECT * FROM events WHERE kind = 'db.transaction_rolled_back'"
        ).fetchall()
    finally:
        other.close()


def test_create_project_leaves_nothing_behind_when_it_fails_partway(conn, tmp_path: Path, monkeypatch):
    """FAULT + SURFACING + DISTINGUISHABILITY (A-70, the Three-Test Rule).
    create_project inserts the project row, then a stage row per stage. Without a
    transaction boundary the project row commits immediately, so an interruption
    during stage-row creation leaves an orphaned project with no stages -- exactly
    A-70's failure mode.

    A-70 is `failure_mode: silent`, so proving the rollback happened (FAULT) is
    not enough on its own: the rolled-back database is byte-identical to "no
    project was ever created" -- zero project rows either way. Without a durable,
    human-findable trace of the failure, "nothing here" and "something went
    wrong" are the same database, which is the exact defect class this programme
    exists to close. SURFACING closes that: an events row records the rollback.
    DISTINGUISHABILITY closes the other half: the legitimate-empty state (never
    attempted) and the failed-creation state must differ observably, not just in
    theory -- zero events before, exactly one after, on a connection that only
    ever sees committed state."""
    from pipeline_app import obs
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path / "logs")

    def raise_on_stage_row(*args, **kwargs):
        raise RuntimeError("boom mid-way through stage row creation")

    monkeypatch.setattr(db, "create_stage_row", raise_on_stage_row)

    db_path = Path(conn.execute("PRAGMA database_list").fetchone()[2])

    # Legitimate-empty baseline, BEFORE anything is attempted: zero projects,
    # zero rollback events. This is the state a genuinely-empty pipeline and a
    # not-yet-attempted creation share.
    assert db.list_projects(conn) == []
    assert _rolled_back_events(db_path) == []

    with pytest.raises(RuntimeError):
        create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES)

    # FAULT: the first step's row (the project) did not survive the interrupted
    # second step (the first stage-row insert) either.
    assert db.list_projects(conn) == []

    # SURFACING: a durable, human-findable trace of the rollback exists, read on
    # a SECOND connection so an uncommitted-but-visible-to-the-writer row can't
    # pass this check.
    rows = _rolled_back_events(db_path)
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert "RuntimeError" in rows[0]["message"]

    # DISTINGUISHABILITY: the database now differs observably from the
    # legitimate-empty baseline above -- same zero projects, but ONE rollback
    # event where there were zero. "Nothing was created" and "creation blew up
    # halfway" are no longer the same database.


def test_an_overlong_slug_is_rejected_before_anything_is_created(conn, tmp_path: Path):
    """Nothing bounded the slug, and the deepest run path is
    runs/<slug>-<ts>/02b-styleboard/events/<ms>.jsonl — an OSError partway
    through left a committed project with a partial set of stage rows (A-78)."""
    from pipeline_app.project_service import MAX_SLUG_LENGTH

    with pytest.raises(ValueError) as exc:
        create_project(conn, tmp_path, "a" * (MAX_SLUG_LENGTH + 1), "generic", STAGES)

    assert str(MAX_SLUG_LENGTH) in str(exc.value)
    assert db.list_projects(conn) == []
    assert not (tmp_path / "runs").exists()


def test_a_slug_at_the_limit_is_still_accepted(conn, tmp_path: Path):
    """Distinguishability: the bound must reject the overlong case only, not
    quietly narrow what a legitimate project may be called."""
    from pipeline_app.project_service import MAX_SLUG_LENGTH

    result = create_project(conn, tmp_path, "a" * MAX_SLUG_LENGTH, "generic", STAGES)
    assert result["run_dir"].is_dir()
    assert len(db.list_projects(conn)) == 1


def test_a_failure_partway_leaves_no_project_at_all(conn, tmp_path: Path, monkeypatch):
    """The project row was inserted and committed, then run_dir.mkdir, then
    one stage row + one mkdir per stage with a commit per row. A failure
    partway left a committed project with a partial set of stage rows that
    nothing repairs, permanently unusable but normal-looking (A-78)."""
    real_mkdir = Path.mkdir
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:            # run_dir succeeds, the first stage dir does not
            raise OSError(28, "No space left on device")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", flaky)

    with pytest.raises(OSError):
        create_project(conn, tmp_path, "why-kids-quit", "generic", STAGES)

    monkeypatch.undo()
    assert db.list_projects(conn) == []
    assert list((tmp_path / "runs").iterdir()) == []


def test_a_half_created_project_is_distinguishable_from_a_whole_one(conn, tmp_path, monkeypatch):
    """The distinguishability the audit asks for: 'broken' must not present
    as 'a project'. Before the fix the broken run appeared in the project list
    exactly like the good one, minus stage rows nobody looks at."""
    good = create_project(conn, tmp_path, "good-run", "generic", STAGES)
    assert {r["stage_id"] for r in db.list_stages(conn, good["project_id"])} == \
        {"ideation", "scripting"}

    real_mkdir = Path.mkdir
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(28, "No space left on device")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", flaky)
    with pytest.raises(OSError):
        create_project(conn, tmp_path, "bad-run", "generic", STAGES)
    monkeypatch.undo()

    projects = db.list_projects(conn)
    assert [p["slug"] for p in projects] == ["good-run"]
