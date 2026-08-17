import inspect
from pathlib import Path

import pytest

from pipeline_app import db
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
    assert exit_code == 0
    assert called["n"] == 0


def test_scheduled_mode_runs_when_due(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])
    assert exit_code == 0
    assert calls[0]["trigger"] == "scheduled"
    assert calls[0]["mode"] == "incremental"


def test_incremental_mode_always_runs(monkeypatch, repo_root):
    calls = []
    monkeypatch.setattr(cron, "run_discovery", lambda *a, **k: (calls.append(k), {"run_row_id": 1, "status": "completed"})[1])
    exit_code = cron.main(["--mode", "incremental", "--repo-root", str(repo_root)])
    assert exit_code == 0
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
    assert exit_code == 0
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
    assert exit_code == 0
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


def test_scheduled_locked_run_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 2, "status": "locked"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert calls == []


def test_scheduled_not_due_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: False)
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert calls == []


def test_incremental_mode_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 3, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "incremental", "--repo-root", str(repo_root)])

    assert exit_code == 0
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

    assert exit_code == 0
    assert calls == []


def test_validate_handle_mode_does_not_call_notify(monkeypatch, repo_root):
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 6, "status": "completed"})
    calls = []
    monkeypatch.setattr(cron, "notify", lambda *a, **k: calls.append(1) or True)

    exit_code = cron.main(["--mode", "validate_handle", "--handle-id", "1", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert calls == []


def test_notify_exception_does_not_propagate_or_change_exit_code(monkeypatch, repo_root, capsys):
    monkeypatch.setattr(cron, "_is_due_now", lambda repo_root_arg: True)
    monkeypatch.setattr(cron, "run_discovery",
                         lambda *a, **k: {"run_row_id": 5, "status": "completed"})

    def raising_notify(*a, **k):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(cron, "notify", raising_notify)

    exit_code = cron.main(["--mode", "scheduled", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert "discovery notification failed" in capsys.readouterr().err


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
