from pathlib import Path
from xml.etree import ElementTree

from scripts.setup_discovery_task import build_schtasks_command, build_task_xml, main


def _xml():
    return build_task_xml(
        Path("C:/venv/Scripts/python.exe"),
        Path("C:/repo/pipeline-app/run_discovery_cron.py"),
        log_path=Path("C:/repo/pipeline-app/logs/discovery-task.log"),
        run_as="DOMAIN\\bking",
    )


def test_build_schtasks_command_shape():
    cmd = build_schtasks_command(Path("C:/venv/Scripts/python.exe"), Path("C:/repo/pipeline-app/run_discovery_cron.py"))
    assert cmd[0] == "schtasks"
    assert "/Create" in cmd
    assert "ContentStudio-Discovery" in cmd
    assert "/SC" in cmd
    assert "MINUTE" in cmd
    assert "/MO" in cmd
    mo_index = cmd.index("/MO")
    assert cmd[mo_index + 1] == "15"
    tr_index = cmd.index("/TR")
    assert "python.exe" in cmd[tr_index + 1]
    assert "run_discovery_cron.py" in cmd[tr_index + 1]
    assert "--mode" in cmd[tr_index + 1]
    assert "scheduled" in cmd[tr_index + 1]


def test_main_dry_run_does_not_execute(monkeypatch, capsys):
    called = {"n": 0}
    monkeypatch.setattr("scripts.setup_discovery_task.subprocess.run", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    exit_code = main([])
    assert exit_code == 0
    assert called["n"] == 0
    captured = capsys.readouterr()
    assert "schtasks" in captured.out
    assert "--apply" in captured.out


def test_main_apply_executes_schtasks(monkeypatch):
    calls = []
    class FakeResult:
        returncode = 0
        stdout = "SUCCESS"
        stderr = ""
    monkeypatch.setattr("scripts.setup_discovery_task.subprocess.run", lambda cmd, **k: (calls.append(cmd), FakeResult())[1])
    exit_code = main(["--apply"])
    assert exit_code == 0
    assert len(calls) == 1
    assert calls[0][0] == "schtasks"


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
