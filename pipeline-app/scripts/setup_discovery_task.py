"""One-time registration of the ContentStudio-Discovery Windows Task
Scheduler task. Registers a SINGLE fixed 15-minute trigger; run_discovery_cron.py
itself decides on each wake whether a scheduled run is actually due (see
discovery_scheduling.is_due and the design spec's "Scheduling" section).
This script is never invoked from the running web app -- run it by hand,
once, after cloning/setting up the repo.

Usage:
  python scripts/setup_discovery_task.py            # dry run: prints the command
  python scripts/setup_discovery_task.py --apply     # actually registers the task
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "ContentStudio-Discovery"


def build_schtasks_command(python_exe: Path, cron_script: Path) -> list[str]:
    task_command = f'"{python_exe}" "{cron_script}" --mode scheduled'
    return [
        "schtasks", "/Create", "/TN", TASK_NAME,
        "/TR", task_command, "/SC", "MINUTE", "/MO", "15", "/F",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually register the task (default: dry run / print only)")
    args = ap.parse_args(argv)

    pipeline_app_root = Path(__file__).resolve().parents[1]
    python_exe = Path(sys.executable)
    cron_script = pipeline_app_root / "run_discovery_cron.py"
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
    print(f"Registered task '{TASK_NAME}': fires every 15 minutes, "
          f"run_discovery_cron.py decides per-wake whether a scheduled run is due.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
