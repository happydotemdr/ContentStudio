import inspect
import sqlite3
from pathlib import Path

import pytest

from pipeline_app import db
from pipeline_app.discovery_engine import now_iso
from pipeline_app.discovery_scheduling import ScheduleConfigError, encode_watermark
import run_discovery_cron as cron


@pytest.fixture
def repo_root(tmp_path: Path):
    db_path = tmp_path / "pipeline-app" / "pipeline.db"
    db_path.parent.mkdir(parents=True)
    schema_path = Path(__file__).resolve().parents[1] / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    return tmp_path


def test_scheduled_mode_skips_when_not_due(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: False)
    called = {"n": 0}
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert exit_code == cron.Exit.OK
    assert called["n"] == 0


def test_scheduled_mode_runs_when_due(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert exit_code == cron.Exit.OK
    assert calls[0]["trigger"] == "scheduled"
    assert calls[0]["mode"] == "incremental"


def test_incremental_mode_always_runs(monkeypatch, repo_root):
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main(["--mode", "incremental", "--repo-root", str(repo_root)])
    assert exit_code == cron.Exit.OK
    assert calls[0]["trigger"] == "manual"
    assert calls[0]["mode"] == "incremental"


def test_backfill_mode_requires_start_and_end(repo_root):
    with pytest.raises(SystemExit):
        cron.main(["--mode", "backfill", "--repo-root", str(repo_root)])


def test_backfill_mode_passes_dates_through(monkeypatch, repo_root):
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main([
        "--mode", "backfill", "--backfill-start", "2026-06-01", "--backfill-end", "2026-06-30",
        "--repo-root", str(repo_root),
    ])
    assert exit_code == cron.Exit.OK
    assert calls[0]["mode"] == "backfill"
    assert calls[0]["backfill_start"] == "2026-06-01"
    assert calls[0]["backfill_end"] == "2026-06-30"


def test_validate_handle_mode_requires_handle_id(repo_root):
    with pytest.raises(SystemExit):
        cron.main(["--mode", "validate_handle", "--repo-root", str(repo_root)])


def test_validate_handle_mode_passes_handle_id_through(monkeypatch, repo_root):
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main(["--mode", "validate_handle", "--handle-id", "42", "--repo-root", str(repo_root)])
    assert exit_code == cron.Exit.OK
    assert calls[0]["handle_id"] == 42
    assert calls[0]["mode"] == "validate_handle"


def test_scheduled_due_run_calls_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 1, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda conn, repo_root_arg, run_row_id: calls.append(run_row_id) or True)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert calls == [1]


def test_a_locked_run_does_not_notify_and_exits_locked(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 2, "status": "locked"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == cron.Exit.LOCKED
    assert calls == []


def test_a_stored_bad_timezone_exits_scheduler_wedged_not_a_traceback(monkeypatch, repo_root):
    """B-47 (S1): a mistyped timezone made every 15-minute wake for the rest of
    time die with a traceback into a console Task Scheduler destroys."""
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    try:
        db.update_settings(conn, "daily", "06:00", "America/Chicgo")
        conn.commit()
        assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.SCHEDULER_WEDGED
        rows = conn.execute("SELECT severity FROM events WHERE kind = 'discovery.scheduler_wedged'").fetchall()
        assert [r["severity"] for r in rows] == ["critical"]
    finally:
        conn.close()


def test_scheduled_not_due_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: False)
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == cron.Exit.OK
    assert calls == []


def test_incremental_mode_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 3, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "incremental", "--repo-root", str(repo_root)])

    assert exit_code == cron.Exit.OK
    assert calls == []


def test_backfill_mode_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 4, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main([
        "--mode", "backfill", "--backfill-start", "2026-06-01", "--backfill-end", "2026-06-30",
        "--repo-root", str(repo_root),
    ])

    assert exit_code == cron.Exit.OK
    assert calls == []


def test_validate_handle_mode_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 6, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "validate_handle", "--handle-id", "1", "--repo-root", str(repo_root)])

    assert exit_code == cron.Exit.OK
    assert calls == []


def test_a_failed_send_exits_notify_failed(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
    monkeypatch.setattr(cron, "notify", lambda *a, **k: False)   # send_email's documented False
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.NOTIFY_FAILED


def test_a_sent_and_an_unsent_email_do_not_share_an_exit_code(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
    monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
    sent = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    monkeypatch.setattr(cron, "notify", lambda *a, **k: False)
    unsent = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert sent != unsent


def test_a_notify_exception_does_not_propagate_but_does_change_the_exit_code(monkeypatch, repo_root):
    """Replaces test_notify_exception_does_not_propagate_or_change_exit_code.
    The 'does not propagate' half was right; the 'does not change the exit
    code' half was the defect (B-41/D-01)."""
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))

    def raising_notify(*a, **k):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(cron, "notify", raising_notify)
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.NOTIFY_FAILED


def test_an_unsent_email_leaves_an_error_event(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
    monkeypatch.setattr(cron, "notify", lambda *a, **k: False)
    cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    try:
        rows = conn.execute(
            "SELECT kind, severity FROM events WHERE kind = 'discovery.notify_failed'").fetchall()
        assert [r["severity"] for r in rows] == ["error"]
    finally:
        conn.close()


def test_a_machine_that_was_off_for_two_days_records_a_gap_warning(monkeypatch, repo_root):
    """D-06's proposed fix: surface 'last successful scheduled run' so a gap is
    visible AS a gap rather than as silence. A machine asleep across
    time_of_day skips the day with no signal whatsoever today."""
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    try:
        db.set_last_scheduled_run_date(conn, encode_watermark(
            "2026-07-28", "America/Chicago", "2026-07-28T11:00:00+00:00"))
        conn.commit()
        monkeypatch.setattr(cron, "_is_due_now", lambda c: True)
        monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
        monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=1, attempted=1))
        cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
        row = conn.execute("SELECT * FROM events WHERE kind = 'discovery.days_skipped'").fetchone()
        assert row is not None and row["severity"] == "warning"
        assert "2026-07-28" in row["message"]
    finally:
        conn.close()


def test_build_adapters_includes_every_platform():
    adapters = cron.build_adapters()
    assert set(adapters.keys()) == {
        "youtube", "bluesky", "instagram", "linkedin-profile", "linkedin-company",
        "facebook", "x",
    }


def test_build_adapters_gives_each_linkedin_mode_its_own_instance():
    """Separate instances, so their enumerate caches stay separate -- a person
    and a company can share a slug."""
    adapters = cron.build_adapters()
    profile, company = adapters["linkedin-profile"], adapters["linkedin-company"]
    assert profile is not company
    assert profile.platform == "linkedin-profile"
    assert company.platform == "linkedin-company"


def test_linkedin_platforms_are_excluded_from_backfill():
    """discovery_engine rejects any platform outside this whitelist before an
    adapter is called, so a backfill request can never trigger a paid LinkedIn
    job that would return nothing useful. Instagram needed this guard added;
    LinkedIn inherits it -- pin that it still holds."""
    from pipeline_app.discovery_engine import BACKFILL_SUPPORTED_PLATFORMS

    assert "linkedin-profile" not in BACKFILL_SUPPORTED_PLATFORMS
    assert "linkedin-company" not in BACKFILL_SUPPORTED_PLATFORMS


def test_build_adapters_registers_facebook_as_a_module():
    """One dataset serves both Pages and personal profiles, so unlike
    LinkedIn there is no per-mode instance to construct -- the module itself
    satisfies PlatformAdapter structurally, same as Instagram."""
    from pipeline_app import discovery_facebook

    assert cron.build_adapters()["facebook"] is discovery_facebook


def test_facebook_is_excluded_from_backfill():
    """No engine change is needed: BACKFILL_SUPPORTED_PLATFORMS is a
    whitelist, so facebook is rejected before any adapter call. Backfill IS
    possible for this product (start_date/end_date verified working
    2026-08-08) but needs a PlatformAdapter protocol change, deferred to its
    own spec."""
    from pipeline_app.discovery_engine import BACKFILL_SUPPORTED_PLATFORMS

    assert "facebook" not in BACKFILL_SUPPORTED_PLATFORMS


def test_x_is_registered_as_an_adapter():
    from pipeline_app import discovery_x

    assert cron.build_adapters()["x"] is discovery_x


def test_x_is_excluded_from_backfill():
    """discovery_engine rejects any platform outside this whitelist before an
    adapter is called, so a backfill request can never trigger a paid X job.
    That matters more here than for LinkedIn: X's start_date/end_date were
    tested and return an error row, so there is no backfill path at all."""
    from pipeline_app.discovery_engine import BACKFILL_SUPPORTED_PLATFORMS

    assert "x" not in BACKFILL_SUPPORTED_PLATFORMS


def test_x_adapter_satisfies_the_platform_adapter_protocol():
    """The protocol is structural (typing.Protocol), so callable()/getattr()
    alone would keep passing even if a parameter were dropped or renamed --
    e.g. download_item's unused `title` param. That mismatch surfaces only at
    runtime, mid-run, once discovery_engine.py's real positional call no
    longer lines up: a TypeError raised per handle, AFTER that handle's
    Bright Data job has already been billed. Pin the actual call shape
    discovery_engine.py uses for each of the four protocol functions (via
    inspect.signature(...).bind(...) against the engine's real call sites in
    process_handle/process_handle_backfill/process_handle_validate), not just
    that the attribute exists and is callable."""
    adapter = cron.build_adapters()["x"]
    for name in ("enumerate_newest_first", "on_disk_ids", "peek_upload_date",
                 "download_item"):
        assert callable(getattr(adapter, name)), name

    # Argument counts/positions lifted verbatim from discovery_engine.py's
    # real call sites -- these raise TypeError (failing the test) if a
    # parameter the engine relies on is dropped, renamed, or reordered.
    inspect.signature(adapter.on_disk_ids).bind(Path("."), "CNN")
    inspect.signature(adapter.enumerate_newest_first).bind("CNN", None)
    inspect.signature(adapter.peek_upload_date).bind("1")
    inspect.signature(adapter.download_item).bind(
        Path("."), "CNN", "1", "title", "post")


def test_every_exit_code_is_unique_and_documented():
    """The contract table in docs/superpowers/plans/remediation/P8-engine-cron.md
    is only as good as its enforcement. Two states sharing a code, or a code
    with no operator-facing reason string, silently re-creates B-40."""
    values = [member.value for member in cron.Exit]
    assert len(values) == len(set(values)), "two terminal states share one exit code"
    assert cron.Exit.OK == 0
    assert {1, 2} & set(values) == set(), "1 and 2 belong to CPython and argparse"
    for member in cron.Exit:
        assert cron.EXIT_REASON[member], f"{member.name} has no reason string"


def test_a_startup_failure_exits_startup_failed_and_is_not_confused_with_not_due(monkeypatch, repo_root):
    monkeypatch.setattr(cron.db, "init_db", lambda *a, **k: (_ for _ in ()).throw(
        sqlite3.OperationalError("database is locked")))
    wedged = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert wedged == cron.Exit.STARTUP_FAILED

    monkeypatch.undo()
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: False)
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) != wedged


def test_a_wake_is_logged_before_the_database_is_touched(monkeypatch, repo_root, tmp_path):
    """D-06: everything the recovery machinery does is downstream of
    insert_running_run. The attempt marker has to be written before init_db
    can fail, which means the log file, not the events table."""
    monkeypatch.setattr(cron.db, "init_db", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    logs = sorted((Path(cron.__file__).resolve().parent / "logs").glob("app-*.log"))
    text = logs[-1].read_text(encoding="utf-8")
    assert "discovery.wake" in text
    assert "discovery.startup_failed" in text


def _result(status, **counts):
    base = {"total": 0, "attempted": 0, "skipped": 0, "failed": 0, "by_status": {}}
    return {"run_row_id": 1, "status": status, "counts": {**base, **counts}}


def test_classify_exit_distinguishes_a_partial_failure_from_a_total_one():
    partial = cron.classify_exit(_result("completed_with_errors", total=3, attempted=3, failed=1))
    total = cron.classify_exit(_result("completed_with_errors", total=3, attempted=3, failed=3))
    assert partial != total
    assert partial == cron.Exit.HANDLES_ERRORED
    assert total == cron.Exit.ALL_HANDLES_ERRORED


def test_a_run_with_errored_handles_exits_nonzero(monkeypatch, repo_root):
    """B-40: Task Scheduler's Last Run Result was 0x0 for a run in which every
    tracked handle failed. That is the whole defect, in one assertion."""
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result(
        "completed_with_errors", total=3, attempted=3, failed=3))
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.ALL_HANDLES_ERRORED


def test_a_broken_run_and_a_clean_run_do_not_share_an_exit_code(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda conn: True)
    monkeypatch.setattr(cron, "notify", lambda *a, **k: True)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("completed", total=3, attempted=3))
    clean = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: _result("failed", total=0))
    broken = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert clean != broken


def _raise(exc: BaseException):
    def _fn(*a, **k):
        raise exc
    return _fn


def _stub(monkeypatch, *, due=True, result=None, notify=None, init_db_error=None, tz=None):
    if init_db_error is not None:
        monkeypatch.setattr(cron.db, "init_db",
                            lambda *a, **k: (_ for _ in ()).throw(init_db_error))
        return
    if tz is not None:
        monkeypatch.setattr(cron, "_is_due_now",
                            lambda conn: (_ for _ in ()).throw(ScheduleConfigError(tz)))
    else:
        monkeypatch.setattr(cron, "_is_due_now", lambda conn: due)
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: result)
    monkeypatch.setattr(cron, "notify", notify if notify is not None else (lambda *a, **k: True))


# (state label, stub kwargs, expected Exit)  -- one row per row of the contract table
EXIT_CONTRACT = [
    ("not due",                 dict(due=False),                                                          cron.Exit.OK),
    ("clean run",               dict(result=_result("completed", total=3, attempted=3)),                  cron.Exit.OK),
    ("lock lost in engine",     dict(result=_result("locked")),                                           cron.Exit.LOCKED),
    ("every handle skipped",    dict(result=_result("completed", total=4, attempted=0, skipped=4)),       cron.Exit.NO_WORK),
    ("no api key",              dict(result=_result("completed", total=1, attempted=1),
                                     notify=lambda *a, **k: False),                                       cron.Exit.NOTIFY_FAILED),
    ("send failed",             dict(result=_result("completed", total=1, attempted=1),
                                     notify=lambda *a, **k: False),                                       cron.Exit.NOTIFY_FAILED),
    ("notify raised",           dict(result=_result("completed", total=1, attempted=1),
                                     notify=_raise(RuntimeError("resend is down"))),                      cron.Exit.NOTIFY_FAILED),
    ("one handle errored",      dict(result=_result("completed_with_errors", total=3, attempted=3, failed=1)),
                                                                                                          cron.Exit.HANDLES_ERRORED),
    ("every handle errored",    dict(result=_result("completed_with_errors", total=3, attempted=3, failed=3)),
                                                                                                          cron.Exit.ALL_HANDLES_ERRORED),
    ("validate: not found",     dict(result=_result("completed_with_errors", total=1, attempted=1, failed=1)),
                                                                                                          cron.Exit.ALL_HANDLES_ERRORED),
    ("crash outside the loop",  dict(result=_result("failed", total=0)),                                  cron.Exit.RUN_FAILED),
    ("validate: adapter raised",dict(result=_result("failed", total=1, attempted=1, failed=1)),           cron.Exit.RUN_FAILED),
    ("run deadline exceeded",   dict(result=_result("failed", total=5, attempted=5, failed=2)),           cron.Exit.RUN_FAILED),
    ("scheduler wedged",        dict(tz="unknown timezone 'America/Chicgo'"),                             cron.Exit.SCHEDULER_WEDGED),
    ("startup failed",          dict(init_db_error=sqlite3.OperationalError("database is locked")),       cron.Exit.STARTUP_FAILED),
    ("clean + unsent email",    dict(result=_result("completed", total=1, attempted=1),
                                     notify=lambda *a, **k: False),                                       cron.Exit.NOTIFY_FAILED),
    ("errored + unsent email",  dict(result=_result("completed_with_errors", total=3, attempted=3, failed=1),
                                     notify=lambda *a, **k: False),                                       cron.Exit.HANDLES_ERRORED),
]


@pytest.mark.parametrize("label,kwargs,expected", EXIT_CONTRACT, ids=[r[0] for r in EXIT_CONTRACT])
def test_exit_code_contract(monkeypatch, repo_root, label, kwargs, expected):
    """The whole of B-40/F-16 in one table. Before the fix, 8 of these 17 rows
    returned 0 and were indistinguishable from a clean run."""
    _stub(monkeypatch, **kwargs)
    assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == expected


def test_exit_contract_covers_every_declared_exit_code():
    """A new Exit member with no contract row is a state nobody can observe."""
    covered = {expected for _, _, expected in EXIT_CONTRACT}
    assert covered == set(cron.Exit)


def test_bad_cli_arguments_still_exit_two():
    with pytest.raises(SystemExit) as excinfo:
        cron.main(["--mode", "nonsense"])
    assert excinfo.value.code == 2


def test_a_stale_run_is_reclaimed_even_when_today_is_not_due(monkeypatch, repo_root):
    """B-52: reclaim lived inside run_discovery, which the scheduled path never
    reaches once is_due returns False -- so a Run Now that died hard after the
    day's scheduled run left a row 'in progress' until tomorrow."""
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    try:
        stale_id = db.insert_running_run(conn, "dead", "manual", "incremental", "2026-07-30T05:00:00+00:00")
        conn.commit()
        monkeypatch.setattr(cron, "_is_due_now", lambda c: False)
        assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.OK
        assert db.get_run(conn, stale_id)["status"] == "abandoned"
    finally:
        conn.close()


def test_the_scheduled_path_short_circuits_when_a_run_is_already_active(monkeypatch, repo_root):
    """B-49: a 90-minute Bright Data run left five locked rows and five junk
    files -- one per 15-minute scheduled wake that found the lock held. The
    engine must never even be reached when a run is already active."""
    conn = db.get_connection(repo_root / "pipeline-app" / "pipeline.db")
    try:
        db.insert_running_run(conn, "in-flight", "manual", "incremental", now_iso())
        conn.commit()
        monkeypatch.setattr(cron, "_is_due_now", lambda c: True)
        monkeypatch.setattr(cron, "run_discovery",
                            lambda *a, **k: pytest.fail("the engine must not be reached"))
        assert cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)]) == cron.Exit.LOCKED
        assert len(db.list_runs(conn)) == 1     # no junk 'locked' row was added
    finally:
        conn.close()


def test_every_tunable_is_reachable_from_the_command_line():
    """B-64(3): five module/default constants with no settings or CLI exposure,
    so tuning any of them was a code edit."""
    parser_flags = {a.dest for a in cron._build_parser()._actions}
    assert {"heartbeat_interval_s", "stale_after_s", "per_handle_deadline_s",
            "run_deadline_s", "new_handle_lookback_days"} <= parser_flags
