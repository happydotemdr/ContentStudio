# coach-prep-app/tests/test_setup_coachprep_task.py
from __future__ import annotations

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import setup_coachprep_task  # noqa: E402


def test_build_schtasks_command_fires_every_240_minutes():
    cmd = setup_coachprep_task.build_schtasks_command(Path("python.exe"), Path("run_coachprep_cron.py"))
    assert "/MO" in cmd
    assert cmd[cmd.index("/MO") + 1] == "240"
    assert cmd[cmd.index("/TN") + 1] == setup_coachprep_task.TASK_NAME
    assert "/SC" in cmd and cmd[cmd.index("/SC") + 1] == "MINUTE"
