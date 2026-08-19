"""CLI entry point: `python -m elevenlabs_tooling send|validate ...`"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from elevenlabs_tooling.log import log
from elevenlabs_tooling.validate import Finding, is_blocking, validate

EXIT_PASS = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_UNREADABLE_INPUT = 3
EXIT_UNPARSEABLE = 4
EXIT_SEND_FAILED = 5
EXIT_NO_API_KEY = 6


def _print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.check}: {finding.message}", file=sys.stderr)


def _load_payload(payload_path: Path) -> tuple[bytes | None, dict | None, int | None]:
    """Returns (raw_bytes, parsed_dict, error_exit_code).

    On success, error_exit_code is None and the other two are set. On
    failure, raw_bytes and parsed_dict are None and error_exit_code names
    the exit code to return. Every failure mode -- missing file, unreadable
    file, invalid JSON, invalid UTF-8, valid JSON that isn't an object --
    is caught here rather than left to crash the process.
    """
    if not payload_path.is_file():
        print(f"elevenlabs_tooling: payload file not found: {payload_path}", file=sys.stderr)
        return None, None, EXIT_UNREADABLE_INPUT

    try:
        raw_bytes = payload_path.read_bytes()
    except OSError as exc:
        print(f"elevenlabs_tooling: cannot read payload file {payload_path}: {exc}", file=sys.stderr)
        return None, None, EXIT_UNREADABLE_INPUT

    try:
        parsed = json.loads(raw_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"elevenlabs_tooling: payload is not valid JSON: {exc}", file=sys.stderr)
        return None, None, EXIT_UNPARSEABLE

    if not isinstance(parsed, dict):
        print(
            f"elevenlabs_tooling: payload must be a JSON object, got {type(parsed).__name__}",
            file=sys.stderr,
        )
        return None, None, EXIT_UNPARSEABLE

    return raw_bytes, parsed, None


def cmd_validate(args: argparse.Namespace) -> int:
    payload_path = Path(args.payload)
    _raw_bytes, payload, error_code = _load_payload(payload_path)
    if error_code is not None:
        return error_code

    findings = validate(payload, args.url)
    _print_findings(findings)
    blocking = [f for f in findings if is_blocking(f)]
    if blocking:
        log(
            "validate.rejected",
            level="warning",
            url=args.url,
            payload_path=str(payload_path),
            findings=[f.check for f in blocking],
        )
        return EXIT_FINDINGS

    log("validate.passed", url=args.url, payload_path=str(payload_path))
    return EXIT_PASS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m elevenlabs_tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a payload against a URL without sending it"
    )
    validate_parser.add_argument("--payload", required=True)
    validate_parser.add_argument("--url", required=True)
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
