#!/usr/bin/env python3
"""The Cowork plugin's tracked build stamp.

`cowork-plugin/` and `dist/` are git-ignored, so the shipped artifact cannot be
version-tracked and no diff can show that `.claude/skills/` has moved on since
the last build. This file is the tracked witness: a sorted roster plus a content
hash of exactly the tree the plugin ships. The build writes it; the repo-root
test recomputes and compares. One algorithm, two callers, so they cannot drift.

Stdlib only -- scripts/ never imports app code."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXCLUDED_SKILLS = ("rgs-grounding", "rgs-pairing-review")
LOCK_PATH = Path("scripts/cowork-plugin.lock.json")


def shipped_skills(repo: Path) -> list[str]:
    root = repo / ".claude" / "skills"
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and p.name not in EXCLUDED_SKILLS
    )


def compute_stamp(repo: Path) -> dict:
    """Content hash of the shipped skills tree.

    Normalizes CRLF to LF before hashing. Without this, the stamp is
    checkout-environment-dependent: this repo has no .gitattributes, so
    whether a file lands on disk as LF or CRLF depends on the checking-out
    machine's core.autocrlf, and raw path.read_bytes() would hash that
    incidental difference as if it were real content drift -- producing a
    false "stale" failure (or a false pass) purely from which machine last
    ran the build, not from any actual change under .claude/skills/.
    """
    root = repo / ".claude" / "skills"
    digest = hashlib.sha256()
    for name in shipped_skills(repo):
        for path in sorted((root / name).rglob("*")):
            if not path.is_file():
                continue
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
            digest.update(b"\0")
    return {
        "skills": shipped_skills(repo),
        "excluded": list(EXCLUDED_SKILLS),
        "sha256": digest.hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--plugin-dir", default=None)
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    stamp = compute_stamp(repo)

    if args.plugin_dir:
        copied = sorted(
            p.name for p in (repo / args.plugin_dir / "skills").iterdir() if p.is_dir()
        )
        if copied != stamp["skills"]:
            print(
                f"copied roster {copied} != expected {stamp['skills']} -- the plugin "
                "tree is not what .claude/skills/ says it should be",
                file=sys.stderr,
            )
            return 1

    lock = repo / LOCK_PATH
    if args.check:
        if not lock.exists() or json.loads(lock.read_text(encoding="utf-8")) != stamp:
            print("plugin lock is stale -- run: bash scripts/build-cowork-plugin.sh",
                  file=sys.stderr)
            return 1
        return 0

    if args.write:
        lock.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
