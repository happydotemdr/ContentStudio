#!/usr/bin/env python3
"""PreToolUse hook: enforce rgs-briefs/ immutability.

Denies (exit 2, reason on stderr):
  - any Edit whose file_path resolves under <project_root>/rgs-briefs/
  - any Write whose file_path resolves under <project_root>/rgs-briefs/ and
    already exists on disk

Allows (exit 0) everything else. See
docs/superpowers/specs/2026-07-28-skill-markdown-file-contract-design.md #5
for the full contract and known limitations (Bash-based mutation is not
intercepted by this hook).
"""
import json
import os
import sys
from pathlib import Path


def decide(tool_name: str, resolved_path: Path, project_root: Path) -> str | None:
    """Return a deny reason, or None to allow."""
    try:
        rel = resolved_path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None  # outside the project entirely -- not this hook's concern
    if rel.parts[:1] != ("rgs-briefs",):
        return None
    if rel.name == "README.md":
        return None  # directory documentation, not a versioned artifact
    if tool_name == "Edit":
        return (
            f"rgs-briefs/ files are immutable -- write a new version instead "
            f"of editing {rel}"
        )
    if tool_name == "Write" and resolved_path.exists():
        return (
            f"{rel} already exists -- rgs-briefs/ files are never "
            f"overwritten, write the next version instead"
        )
    return None


def main() -> int:
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name")
    if tool_name not in ("Edit", "Write"):
        return 0
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        return 0

    project_root = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
    resolved_path = Path(file_path)
    if not resolved_path.is_absolute():
        resolved_path = (project_root / resolved_path).resolve()

    reason = decide(tool_name, resolved_path, project_root)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
