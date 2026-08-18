"""One-time registration of the ContentStudio-CoachPrepAudit Windows Task
Scheduler task. Weekly, Monday 8am -- distinct task name and schedule from
setup_coachprep_task.py's 4-hourly task.

Usage:
  python scripts/setup_audit_task.py            # dry run: prints the command
  python scripts/setup_audit_task.py --apply     # actually registers the task
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ContentStudio-CoachPrepAudit"


def build_schtasks_command(python_exe: Path, audit_script: Path) -> list[str]:
    task_command = f'"{python_exe}" "{audit_script}"'
    return [
        "schtasks", "/Create", "/TN", TASK_NAME,
        "/TR", task_command, "/SC", "WEEKLY", "/D", "MON", "/ST", "08:00", "/F",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually register the task (default: dry run / print only)")
    args = ap.parse_args(argv)

    app_root = Path(__file__).resolve().parents[1]
    python_exe = Path(sys.executable)
    audit_script = app_root / "scripts" / "run_client_audit.py"
    cmd = build_schtasks_command(python_exe, audit_script)

    if not args.apply:
        print("Dry run -- this is the command that would register the scheduled task:")
        print(" ".join(cmd))
        print("\nRe-run with --apply to actually register it.")
        return 0

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    print(f"Registered task '{TASK_NAME}': fires weekly, Monday 8am.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
