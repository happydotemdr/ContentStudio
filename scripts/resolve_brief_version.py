#!/usr/bin/env python3
"""Resolve the latest version of an rgs-briefs/ artifact, or compute the
filename/version the next write should use.

Version resolution reads the frontmatter `version:` field -- never sorts by
filename alone, since "-v2".."-v9" sort before "-v10" lexically.

Usage:
  resolve_brief_version.py --slug <slug> --kind <kind>            # stage artifact
  resolve_brief_version.py --slug <topic-slug>                    # grounding brief (no --kind)
  resolve_brief_version.py --slug <slug> --kind <kind> --next --date YYYY-MM-DD

Exit codes:
  0  Resolved, or a next filename proposed -- <path>\t<version> or <filename>\t<version>
  3  NONE -- no prior version exists (the expected empty case) -- NONE\t0
  2  Error -- unusable input or an unresolvable state (nothing on stdout; message on stderr)
  1  Retired. Never returned.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

EXIT_OK = 0      # a usable answer was printed
EXIT_ERROR = 2   # unusable input or an unresolvable state (argparse also uses 2)
EXIT_NONE = 3    # the expected empty case: no prior version exists
# Exit 1 is deliberately retired. It used to mean BOTH "no prior version" and
# "a brief is malformed", and callers read it as the former -- which turned a
# corrupt brief into "start at v1". Nothing returns 1 now.


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
    if not directory.is_dir():
        raise FileNotFoundError(
            f"{directory} does not exist or is not a directory -- resolve_brief_version "
            "must be run from the repo root, or given an explicit --dir. Returning "
            '"no prior version" here would propose v1 over a live brief.'
        )
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
    print(f"resolve_brief_version: reading {directory.resolve()}", file=sys.stderr)

    try:
        if args.next:
            if not args.date:
                parser.error("--next requires --date YYYY-MM-DD")
            filename, version = next_filename(directory, args.slug, args.kind, args.date)
            print(f"{filename}\t{version}")
            return EXIT_OK

        path, version = find_latest(directory, args.slug, args.kind)
    except (FileNotFoundError, ValueError) as exc:
        # Deliberately NOT a bare except: these are the two failure classes this
        # resolver can produce, and each is reported with its own message rather
        # than collapsed into the "nothing found" answer.
        print(f"resolve_brief_version: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if path is None:
        print("NONE\t0")
        return EXIT_NONE
    print(f"{path.as_posix()}\t{version}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
