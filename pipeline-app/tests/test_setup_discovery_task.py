import shlex
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

import pipeline_app
from tools.setup_discovery_task import build_task_xml, main


def _xml():
    return build_task_xml(
        Path("C:/venv/Scripts/python.exe"),
        Path("C:/repo/pipeline-app/run_discovery_cron.py"),
        log_path=Path("C:/repo/pipeline-app/logs/discovery-task.log"),
        run_as="DOMAIN\\bking",
    )


class _FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _assert_b10_kwargs(kwargs):
    """B-10 (Global Constraint): every subprocess.run call must pass
    encoding="utf-8", errors="replace" -- never bare text=True."""
    assert kwargs.get("encoding") == "utf-8"
    assert kwargs.get("errors") == "replace"
    assert "text" not in kwargs


def _fake_run(responses):
    """Fake subprocess.run keyed by a tuple of tokens that must all appear in
    the command list, e.g. {("schtasks", "/Query"): 0}. First matching key
    wins; an unmatched command defaults to a successful (0) result."""

    def _run(cmd, **kwargs):
        _assert_b10_kwargs(kwargs)
        for tokens, returncode in responses.items():
            if all(token in cmd for token in tokens):
                return _FakeResult(returncode=returncode)
        return _FakeResult(returncode=0)

    return _run


def _record_calls(monkeypatch):
    """Stubs subprocess.run to always succeed while recording every command
    list issued, in order."""
    calls = []

    def _run(cmd, **kwargs):
        _assert_b10_kwargs(kwargs)
        calls.append(cmd)
        return _FakeResult(returncode=0)

    monkeypatch.setattr("tools.setup_discovery_task.subprocess.run", _run)
    return calls


def test_main_dry_run_does_not_execute(monkeypatch, capsys):
    called = {"n": 0}
    monkeypatch.setattr("tools.setup_discovery_task.subprocess.run", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    exit_code = main([])
    assert exit_code == 0
    assert called["n"] == 0
    captured = capsys.readouterr()
    assert "schtasks" in captured.out
    assert "--apply" in captured.out


@pytest.mark.allow_subprocess
def test_apply_creates_when_no_existing_task(monkeypatch):
    """Replaces the old test_main_apply_executes_schtasks: main() now probes
    for an existing task before creating one, so a plain `--apply` on a clean
    machine issues three calls (probe / create / verify), not one. This keeps
    the old test's intent -- a plain --apply run against a well-behaved
    schtasks ends in success -- under the new verify-before-success flow."""
    calls = []
    responses = iter([1, 0, 0])  # probe: not found; create: ok; verify: ok

    def _run(cmd, **kwargs):
        _assert_b10_kwargs(kwargs)
        calls.append(cmd)
        return _FakeResult(returncode=next(responses))

    monkeypatch.setattr("tools.setup_discovery_task.subprocess.run", _run)
    exit_code = main(["--apply"])
    assert exit_code == 0
    assert len(calls) == 3
    assert calls[0][0] == "schtasks" and "/Query" in calls[0]
    assert "/Create" in calls[1]
    assert "/Query" in calls[2]


@pytest.mark.allow_subprocess
def test_apply_refuses_to_overwrite_an_existing_task_without_force(monkeypatch, capsys):
    """B-46: /F destroyed and recreated the task, wiping any fix applied by
    hand in the Task Scheduler GUI -- the very fixes B-44 calls for."""
    monkeypatch.setattr("tools.setup_discovery_task.subprocess.run",
                        _fake_run({("schtasks", "/Query"): 0}))
    assert main(["--apply"]) != 0
    assert "--force" in capsys.readouterr().err


@pytest.mark.allow_subprocess
def test_apply_verifies_registration_with_a_query_before_reporting_success(monkeypatch):
    calls = _record_calls(monkeypatch)
    main(["--apply", "--force"])
    assert any("/Query" in c for c in calls[-1])


@pytest.mark.allow_subprocess
def test_apply_reports_failure_when_the_verifying_query_finds_nothing(monkeypatch, capsys):
    monkeypatch.setattr("tools.setup_discovery_task.subprocess.run",
                        _fake_run({("schtasks", "/Create"): 0, ("schtasks", "/Query"): 1}))
    assert main(["--apply", "--force"]) != 0
    assert "could not be verified" in capsys.readouterr().err


@pytest.mark.allow_subprocess
def test_remove_deletes_the_task(monkeypatch):
    calls = _record_calls(monkeypatch)
    assert main(["--remove"]) == 0
    assert "/Delete" in calls[0]


def test_task_xml_redirects_stdout_and_stderr_to_a_log_file():
    """D-02: the registered action captured no output, so all 35 stderr
    diagnostics on the scheduled path were written and immediately discarded."""
    xml = build_task_xml(Path("C:/venv/Scripts/python.exe"),
                         Path("C:/repo/pipeline-app/run_discovery_cron.py"),
                         log_path=Path("C:/repo/pipeline-app/logs/discovery-task.log"),
                         run_as="DOMAIN\\bking")
    assert ">>" in xml and "2>&1" in xml
    assert "discovery-task.log" in xml


def test_task_xml_runs_on_battery_and_catches_up_a_missed_start():
    """B-44: schtasks-created tasks inherit DisallowStartIfOnBatteries, so on a
    laptop on battery the run simply does not start, with no diagnostic."""
    xml = _xml()
    assert "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>" in xml
    assert "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>" in xml
    assert "<StartWhenAvailable>true</StartWhenAvailable>" in xml


def test_task_xml_pins_the_logon_model_and_working_directory():
    xml = _xml()
    root = ElementTree.fromstring(xml)
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    assert root.find(".//t:Principal/t:LogonType", ns).text == "S4U"
    assert root.find(".//t:Exec/t:WorkingDirectory", ns).text.endswith("pipeline-app")
    assert root.find(".//t:Repetition/t:Interval", ns).text == "PT15M"


def test_dry_run_prints_a_command_that_survives_a_round_trip_through_the_shell_parser():
    """B-45: ' '.join(cmd) flattened the /TR payload, so pasting the printed
    line bound /TR to the python path alone and left the script as a stray
    argument. The printed line must be byte-for-byte executable."""
    cmd = ["schtasks", "/Create", "/TN", "ContentStudio-Discovery",
           "/XML", r"C:\Program Files\repo\pipeline-app\logs\task.xml", "/F"]
    printed = subprocess.list2cmdline(cmd)
    assert printed != " ".join(cmd)
    assert shlex.split(printed, posix=False)[5].strip('"') == r"C:\Program Files\repo\pipeline-app\logs\task.xml"


def test_dry_run_tells_the_operator_where_the_log_will_be(monkeypatch, capsys):
    main([])
    assert "discovery-task.log" in capsys.readouterr().out


def test_the_app_no_longer_ships_a_package_named_scripts():
    """F-64: two importable packages both named `scripts` -- the repo root's and
    the app's -- so a bare pytest from the root shadows one with the other."""
    assert not (Path(pipeline_app.__file__).parents[1] / "scripts").exists()


def test_the_cron_script_path_survives_the_move():
    """A move that changes this module's depth would make pipeline_app_root()
    resolve one directory too deep, and the registered task would point at a
    file that is not there -- registering cleanly and failing forever,
    invisibly (B-40/B-42). tools/ keeps the depth; this test is what proves it
    rather than assuming it."""
    from tools import setup_discovery_task as sut
    assert sut.pipeline_app_root().name == "pipeline-app"
    assert (sut.pipeline_app_root() / "run_discovery_cron.py").exists()
