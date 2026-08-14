import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))

from setup_ingest_task import TASK_NAME, build_schtasks_command


def test_task_name():
    assert TASK_NAME == "ContentStudio-DocIngest"


def test_build_schtasks_command_uses_30_minute_interval():
    cmd = build_schtasks_command(Path("python.exe"), Path("run_ingest_cron.py"))
    assert cmd[:4] == ["schtasks", "/Create", "/TN", "ContentStudio-DocIngest"]
    assert "/SC" in cmd
    assert cmd[cmd.index("/SC") + 1] == "MINUTE"
    assert cmd[cmd.index("/MO") + 1] == "30"


def test_build_schtasks_command_quotes_the_python_invocation():
    cmd = build_schtasks_command(Path("C:/some path/python.exe"), Path("C:/repo/run_ingest_cron.py"))
    tr_index = cmd.index("/TR")
    assert "some path" in cmd[tr_index + 1]
