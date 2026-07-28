#!/usr/bin/env python3
"""Resolve the latest version of an rgs-briefs/ artifact, or compute the
filename/version the next write should use.

Version resolution reads the frontmatter `version:` field -- never sorts by
filename alone, since "-v2".."-v9" sort before "-v10" lexically.

Usage:
  resolve_brief_version.py --slug <slug> --kind <kind>            # stage artifact
  resolve_brief_version.py --slug <topic-slug>                    # grounding brief (no --kind)
  resolve_brief_version.py --slug <slug> --kind <kind> --next --date YYYY-MM-DD
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("no frontmatter block found")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter did not parse to a mapping")
    return data


def _pattern(slug: str, kind: str | None) -> re.Pattern:
    suffix = f"-{re.escape(kind)}" if kind else ""
    return re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(slug)}{suffix}(-v(\d+))?\.md$")


def find_latest(directory: Path, slug: str, kind: str | None) -> tuple[Path | None, int]:
    if not directory.exists():
        return None, 0
    pattern = _pattern(slug, kind)
    best_path: Path | None = None
    best_version = 0
    for path in sorted(directory.glob("*.md")):
        if not pattern.match(path.name):
            continue
        try:
            meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        version = meta.get("version")
        if not isinstance(version, int):
            raise ValueError(f"{path}: frontmatter missing an integer 'version' field")
        if version > best_version:
            best_version = version
            best_path = path
    return best_path, best_version


def next_filename(directory: Path, slug: str, kind: str | None, date: str) -> tuple[str, int]:
    _, best_version = find_latest(directory, slug, kind)
    next_version = best_version + 1
    suffix = f"-{kind}" if kind else ""
    version_suffix = "" if next_version == 1 else f"-v{next_version}"
    return f"{date}-{slug}{suffix}{version_suffix}.md", next_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="rgs-briefs")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--kind", default=None, help="omit for a grounding brief")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--date", default=None, help="required with --next, e.g. 2026-07-28")
    args = parser.parse_args(argv)

    directory = Path(args.dir)

    if args.next:
        if not args.date:
            parser.error("--next requires --date YYYY-MM-DD")
        filename, version = next_filename(directory, args.slug, args.kind, args.date)
        print(f"{filename}\t{version}")
        return 0

    path, version = find_latest(directory, args.slug, args.kind)
    if path is None:
        print("NONE\t0")
        return 1
    print(f"{path}\t{version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
