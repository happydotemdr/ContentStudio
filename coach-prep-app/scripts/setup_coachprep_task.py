"""One-time registration of the ContentStudio-CoachPrep Windows Task
Scheduler task. Fixed 4-hour trigger, no additional due-gating on top --
trigger.is_due (coach_prep_app/trigger.py) is what decides whether any given
wake actually does anything. Mirrors doc-ingest-app/scripts/setup_ingest_task.py.

Usage:
  python scripts/setup_coachprep_task.py            # dry run: prints the command
  python scripts/setup_coachprep_task.py --apply     # actually registers the task
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ContentStudio-CoachPrep"


def build_schtasks_command(python_exe: Path, cron_script: Path) -> list[str]:
    task_command = f'"{python_exe}" "{cron_script}"'
    return [
        "schtasks", "/Create", "/TN", TASK_NAME,
        "/TR", task_command, "/SC", "MINUTE", "/MO", "240", "/F",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually register the task (default: dry run / print only)")
    args = ap.parse_args(argv)

    app_root = Path(__file__).resolve().parents[1]
    python_exe = Path(sys.executable)
    cron_script = app_root / "scripts" / "run_coachprep_cron.py"
    cmd = build_schtasks_command(python_exe, cron_script)

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
    print(f"Registered task '{TASK_NAME}': fires every 4 hours.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
