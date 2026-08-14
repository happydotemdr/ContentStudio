#!/usr/bin/env python3
"""PreToolUse hook: fast-fail layer for Freedom2BeU/converted/ immutability.

This is layer 2 of the design's two-layer read-only enforcement (spec §10) --
the Windows ACL deny-write (doc-ingest-app/doc_ingest/lock.py) is the real
backstop; this hook only rejects the call before it reaches the OS, and only
inside Claude Code sessions that load this repo's settings.json. Extends
protect_briefs.py's Edit/Write-path pattern with a heuristic scan of
Bash/PowerShell command text, since those tools aren't caught by a
file_path-based check alone.
"""
import json
import os
import re
import sys
from pathlib import Path

_PROTECTED_PREFIX = ("Freedom2BeU", "converted")

_WRITE_VERB_RE = re.compile(
    r"(^|\s)(>>|>|Remove-Item|del|rm|move|mv|Move-Item|copy|cp|Copy-Item|Set-Content|Add-Content|ren|Rename-Item)(\s|$)",
    re.IGNORECASE,
)
_CONVERTED_PATH_RE = re.compile(r"Freedom2BeU[\\/]converted", re.IGNORECASE)


def decide(tool_name: str, resolved_path: Path, project_root: Path) -> str | None:
    try:
        rel = resolved_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None
    if tuple(p.lower() for p in rel.parts[:2]) != tuple(p.lower() for p in _PROTECTED_PREFIX):
        return None
    if tool_name in ("Edit", "Write", "NotebookEdit"):
        return (
            f"{rel} is under Freedom2BeU/converted/ -- validated conversions are "
            f"read-only by design (spec §10); write a new version through the "
            f"doc-ingest-app pipeline instead"
        )
    return None


def looks_like_a_write_command(command_text: str) -> bool:
    if not _CONVERTED_PATH_RE.search(command_text):
        return False
    return bool(_WRITE_VERB_RE.search(command_text))


def main() -> int:
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name")
    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()

    if tool_name in ("Edit", "Write", "NotebookEdit"):
        tool_input = payload.get("tool_input", {})
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not file_path:
            return 0
        resolved_path = Path(file_path)
        if not resolved_path.is_absolute():
            resolved_path = (project_root / resolved_path).resolve()
        reason = decide(tool_name, resolved_path, project_root)
        if reason:
            print(reason, file=sys.stderr)
            return 2
        return 0

    if tool_name in ("Bash", "PowerShell"):
        command_text = payload.get("tool_input", {}).get("command", "")
        if looks_like_a_write_command(command_text):
            print(
                "This command looks like it writes to Freedom2BeU/converted/ -- "
                "validated conversions are read-only by design (spec §10)",
                file=sys.stderr,
            )
            return 2
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
