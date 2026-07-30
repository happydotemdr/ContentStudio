from pathlib import Path

from scripts.setup_discovery_task import build_schtasks_command, main


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
