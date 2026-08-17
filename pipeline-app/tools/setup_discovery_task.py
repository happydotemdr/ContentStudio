"""One-time registration of the ContentStudio-Discovery Windows Task
Scheduler task. Registers a SINGLE fixed 15-minute trigger; run_discovery_cron.py
itself decides on each wake whether a scheduled run is actually due (see
discovery_scheduling.is_due and the design spec's "Scheduling" section).
This script is never invoked from the running web app -- run it by hand,
once, after cloning/setting up the repo.

Usage:
  python tools/setup_discovery_task.py            # dry run: prints the command
  python tools/setup_discovery_task.py --apply     # actually registers the task

The XML-based registration (build_task_xml) pins LogonType S4U -- the task runs
whether the user is logged on or not, without Task Scheduler storing a password.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TASK_NAME = "ContentStudio-Discovery"
LOG_NAME = "discovery-task.log"


def pipeline_app_root() -> Path:
    """The `pipeline-app/` directory, which holds run_discovery_cron.py.

    A function rather than an inline parents[1] so the depth is stated once
    and a test can assert it: get this wrong and setup registers a task
    against a path that does not exist, which succeeds and then fails
    silently forever. The F-64 move to tools/ deliberately preserved this
    depth (pipeline_app/scripts/ would not have).
    """
    return Path(__file__).resolve().parents[1]


def default_log_path(pipeline_app_root: Path) -> Path:
    return pipeline_app_root / "logs" / LOG_NAME


def build_task_action(python_exe: Path, cron_script: Path, log_path: Path) -> str:
    """The command Task Scheduler actually runs. Wrapped in `cmd /c` purely for
    the redirection: without it the child's stdout and stderr go to a console
    that does not exist, which is D-02. The doubled outer quotes are cmd.exe's
    rule for a command line that itself starts with a quote."""
    return (f'/c ""{python_exe}" "{cron_script}" --mode scheduled '
            f'>> "{log_path}" 2>&1"')


def build_task_xml(python_exe: Path, cron_script: Path, *, log_path: Path,
                   run_as: str, working_dir: Path | None = None) -> str:
    working_dir = working_dir or cron_script.parent
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>ContentStudio discovery wake (15-minute trigger; run_discovery_cron.py decides per wake whether a run is due).</Description></RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary>
      <Repetition><Interval>PT15M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals><Principal id="Author">
    <UserId>{run_as}</UserId><LogonType>S4U</LogonType><RunLevel>LeastPrivilege</RunLevel>
  </Principal></Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec>
    <Command>cmd.exe</Command>
    <Arguments><![CDATA[{build_task_action(python_exe, cron_script, log_path)}]]></Arguments>
    <WorkingDirectory>{working_dir}</WorkingDirectory>
  </Exec></Actions>
</Task>
"""


def _default_run_as() -> str:
    """Best-effort `DOMAIN\\user` (or bare user) for the task's <UserId>,
    derived from the ambient Windows environment."""
    domain = os.environ.get("USERDOMAIN")
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "SYSTEM"
    return f"{domain}\\{user}" if domain else user


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """Every subprocess.run call funnels through here so B-10 (encoding='utf-8',
    errors='replace', never bare text=True) is enforced in exactly one place."""
    return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")


def _task_registered() -> bool:
    return _run(["schtasks", "/Query", "/TN", TASK_NAME]).returncode == 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually register the task (default: dry run / print only)")
    ap.add_argument("--force", action="store_true",
                     help="overwrite an already-registered task instead of refusing (B-46: this "
                          "destroys any fix applied by hand in the Task Scheduler GUI)")
    ap.add_argument("--remove", action="store_true", help="delete the registered task and exit")
    args = ap.parse_args(argv)

    if args.remove:
        result = _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
        if result.stdout:
            print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return result.returncode
        print(f"Removed task '{TASK_NAME}'.")
        return 0

    app_root = pipeline_app_root()
    python_exe = Path(sys.executable)
    cron_script = app_root / "run_discovery_cron.py"
    log_path = default_log_path(app_root)

    if not args.apply:
        print("Dry run -- this is what --apply would do:")
        print(f"Write the task XML to a temp file and run: "
              f"schtasks /Create /TN {TASK_NAME} /XML <tmpfile> /F")
        print(f"Task log will be written to: {default_log_path(app_root)}")
        print("\nRe-run with --apply to actually register it.")
        return 0

    if not args.force and _task_registered():
        print(f"Task '{TASK_NAME}' is already registered. Re-run with --force to overwrite it "
              "(B-46: this destroys any fix applied by hand in the Task Scheduler GUI).",
              file=sys.stderr)
        return 1

    xml = build_task_xml(python_exe, cron_script, log_path=log_path, run_as=_default_run_as())

    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-16") as f:
        f.write(xml)
        xml_path = Path(f.name)

    try:
        result = _run(["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"])
    finally:
        xml_path.unlink(missing_ok=True)

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    if not _task_registered():
        print(f"Task '{TASK_NAME}' could not be verified as registered after creation.",
              file=sys.stderr)
        return 1

    print(f"Registered task '{TASK_NAME}': fires every 15 minutes, "
          f"run_discovery_cron.py decides per-wake whether a scheduled run is due.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
