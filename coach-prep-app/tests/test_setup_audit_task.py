# coach-prep-app/tests/test_setup_audit_task.py
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import setup_audit_task  # noqa: E402


def test_build_schtasks_command_fires_weekly():
    cmd = setup_audit_task.build_schtasks_command(Path("python.exe"), Path("run_client_audit.py"))
    assert cmd[cmd.index("/SC") + 1] == "WEEKLY"
    assert cmd[cmd.index("/TN") + 1] == setup_audit_task.TASK_NAME
    assert setup_audit_task.TASK_NAME != "ContentStudio-CoachPrep"  # distinct from Task 22's task
