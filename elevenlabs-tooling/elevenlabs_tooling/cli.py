"""CLI entry point: `python -m elevenlabs_tooling send|validate ...`"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from elevenlabs_tooling.client import DEFAULT_TIMEOUT_S
from elevenlabs_tooling.client import send as client_send
from elevenlabs_tooling.client import send_with_timestamps as client_send_with_timestamps
from elevenlabs_tooling.log import log
from elevenlabs_tooling.validate import Finding, is_blocking, validate

EXIT_PASS = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2
EXIT_UNREADABLE_INPUT = 3
EXIT_UNPARSEABLE = 4
EXIT_SEND_FAILED = 5
EXIT_NO_API_KEY = 6

API_KEY_ENV_VAR = "ELEVENLABS_API_KEY"
TIMEOUT_ENV_VAR = "ELEVENLABS_TOOLING_TIMEOUT_S"


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


def _resolve_timeout(cli_value: float | None) -> float:
    """--timeout wins over ELEVENLABS_TOOLING_TIMEOUT_S wins over the
    300s default. An invalid value at EITHER level (non-numeric, zero, or
    negative) warns and falls through to the next level rather than being
    used or crashing."""
    if cli_value is not None:
        if cli_value > 0:
            return cli_value
        print(
            f"elevenlabs_tooling: --timeout {cli_value:g} is not a positive "
            "number of seconds; falling back to the environment/default",
            file=sys.stderr,
        )

    raw = os.environ.get(TIMEOUT_ENV_VAR)
    if raw is None or raw.strip() == "":
        return DEFAULT_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if value <= 0:
        print(
            f"elevenlabs_tooling: {TIMEOUT_ENV_VAR}={raw!r} is not a positive "
            f"number of seconds; using the default of {DEFAULT_TIMEOUT_S:g}s",
            file=sys.stderr,
        )
        return DEFAULT_TIMEOUT_S
    return value


def cmd_send(args: argparse.Namespace) -> int:
    payload_path = Path(args.payload)
    output_path = Path(args.output)

    raw_bytes, payload, error_code = _load_payload(payload_path)
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

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"elevenlabs_tooling: {API_KEY_ENV_VAR} is not set", file=sys.stderr)
        log(
            "send.aborted",
            level="warning",
            url=args.url,
            payload_path=str(payload_path),
            reason="no_api_key",
        )
        return EXIT_NO_API_KEY

    if output_path.exists() and not args.force:
        print(
            f"elevenlabs_tooling: {output_path} already exists; pass --force to overwrite",
            file=sys.stderr,
        )
        log(
            "send.aborted",
            level="warning",
            url=args.url,
            payload_path=str(payload_path),
            output_path=str(output_path),
            reason="output_exists",
        )
        return EXIT_USAGE
    # Path(".").is_dir() is True, so a bare filename like "out.mp3" (parent
    # == the cwd) passes this check correctly rather than being rejected.
    if not output_path.parent.is_dir():
        print(
            f"elevenlabs_tooling: output directory does not exist: {output_path.parent}",
            file=sys.stderr,
        )
        log(
            "send.aborted",
            level="warning",
            url=args.url,
            payload_path=str(payload_path),
            output_path=str(output_path),
            reason="output_parent_missing",
        )
        return EXIT_USAGE

    payload_hash = hashlib.sha256(raw_bytes).hexdigest()
    timeout = _resolve_timeout(args.timeout)
    log(
        "send.attempt",
        url=args.url,
        payload_path=str(payload_path),
        payload_sha256=payload_hash,
        output_path=str(output_path),
        timeout=timeout,
    )

    try:
        result = client_send(args.url, raw_bytes, api_key, timeout=timeout)
    except Exception as exc:
        # client_send() only ever raises here for something outside
        # requests.exceptions.RequestException (e.g. a ValueError from
        # requests' header construction on a malformed API key). str(exc)
        # can embed request internals -- including the API key itself -- so
        # only the exception's type name is ever surfaced, never its message.
        print(
            f"elevenlabs_tooling: unexpected error sending the payload: {type(exc).__name__}",
            file=sys.stderr,
        )
        log(
            "send.failed",
            level="error",
            url=args.url,
            error=type(exc).__name__,
        )
        return EXIT_SEND_FAILED

    if result.ok:
        try:
            output_path.write_bytes(result.body)
        except OSError as exc:
            # Credits are already spent and the audio came back fine -- the
            # failure is purely local disk I/O. Still logged as a failure
            # since nothing usable landed at --output.
            print(
                f"elevenlabs_tooling: send succeeded but writing {output_path} failed: {exc}",
                file=sys.stderr,
            )
            log(
                "send.failed",
                level="error",
                url=args.url,
                status_code=result.status_code,
                error=f"write failed after a successful API call: {exc}",
            )
            return EXIT_SEND_FAILED
        log(
            "send.success",
            url=args.url,
            output_path=str(output_path),
            status_code=result.status_code,
            content_type=result.content_type,
            bytes_written=len(result.body),
        )
        return EXIT_PASS

    if result.body is not None:
        quarantine_path = output_path.with_name(output_path.name + ".unexpected")
        try:
            quarantine_path.write_bytes(result.body)
            quarantine_note = f" (response body saved to {quarantine_path})"
        except OSError as exc:
            quarantine_note = f" (also failed to save the response body: {exc})"
        print(
            f"elevenlabs_tooling: send failed: {result.error_message}{quarantine_note}",
            file=sys.stderr,
        )
        log(
            "send.failed",
            level="error",
            url=args.url,
            status_code=result.status_code,
            content_type=result.content_type,
            error=result.error_message,
        )
        return EXIT_SEND_FAILED

    print(f"elevenlabs_tooling: send failed: {result.error_message}", file=sys.stderr)
    log(
        "send.failed",
        level="error",
        url=args.url,
        status_code=result.status_code,
        error=result.error_message,
    )
    return EXIT_SEND_FAILED


def cmd_generate_vo(args: argparse.Namespace) -> int:
    payload_path = Path(args.payload)
    audio_output_path = Path(args.audio_output)
    alignment_output_path = Path(args.alignment_output)

    raw_bytes, payload, error_code = _load_payload(payload_path)
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

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        print(f"elevenlabs_tooling: {API_KEY_ENV_VAR} is not set", file=sys.stderr)
        log(
            "generate_vo.aborted",
            level="warning",
            url=args.url,
            payload_path=str(payload_path),
            reason="no_api_key",
        )
        return EXIT_NO_API_KEY

    for label, out_path in (("audio", audio_output_path), ("alignment", alignment_output_path)):
        if out_path.exists() and not args.force:
            print(
                f"elevenlabs_tooling: {label} output {out_path} already exists; "
                "pass --force to overwrite",
                file=sys.stderr,
            )
            log(
                "generate_vo.aborted",
                level="warning",
                url=args.url,
                payload_path=str(payload_path),
                reason=f"{label}_output_exists",
            )
            return EXIT_USAGE
        if not out_path.parent.is_dir():
            print(
                f"elevenlabs_tooling: {label} output directory does not exist: {out_path.parent}",
                file=sys.stderr,
            )
            log(
                "generate_vo.aborted",
                level="warning",
                url=args.url,
                payload_path=str(payload_path),
                reason=f"{label}_output_parent_missing",
            )
            return EXIT_USAGE

    payload_hash = hashlib.sha256(raw_bytes).hexdigest()
    timeout = _resolve_timeout(args.timeout)
    log(
        "generate_vo.attempt",
        url=args.url,
        payload_path=str(payload_path),
        payload_sha256=payload_hash,
        audio_output_path=str(audio_output_path),
        alignment_output_path=str(alignment_output_path),
        timeout=timeout,
    )

    try:
        result = client_send_with_timestamps(args.url, raw_bytes, api_key, timeout=timeout)
    except Exception as exc:
        print(
            f"elevenlabs_tooling: unexpected error sending the payload: {type(exc).__name__}",
            file=sys.stderr,
        )
        log("generate_vo.failed", level="error", url=args.url, error=type(exc).__name__)
        return EXIT_SEND_FAILED

    if not result.ok:
        quarantine_note = ""
        if result.raw_body is not None:
            quarantine_path = audio_output_path.with_name(audio_output_path.name + ".unexpected")
            try:
                quarantine_path.write_bytes(result.raw_body)
                quarantine_note = f" (response body saved to {quarantine_path})"
            except OSError as exc:
                quarantine_note = f" (also failed to save the response body: {exc})"
        print(
            f"elevenlabs_tooling: generate-vo failed: {result.error_message}{quarantine_note}",
            file=sys.stderr,
        )
        log(
            "generate_vo.failed",
            level="error",
            url=args.url,
            status_code=result.status_code,
            error=result.error_message,
        )
        return EXIT_SEND_FAILED

    try:
        audio_output_path.write_bytes(result.audio_bytes)
        alignment_output_path.write_text(json.dumps(result.alignment), encoding="utf-8")
    except OSError as exc:
        print(
            f"elevenlabs_tooling: generate-vo succeeded but writing output failed: {exc}",
            file=sys.stderr,
        )
        log(
            "generate_vo.failed",
            level="error",
            url=args.url,
            status_code=result.status_code,
            error=f"write failed after a successful API call: {exc}",
        )
        return EXIT_SEND_FAILED

    log(
        "generate_vo.success",
        url=args.url,
        audio_output_path=str(audio_output_path),
        alignment_output_path=str(alignment_output_path),
        status_code=result.status_code,
        audio_bytes_written=len(result.audio_bytes),
    )
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

    send_parser = subparsers.add_parser("send", help="Validate and send a payload")
    send_parser.add_argument("--payload", required=True)
    send_parser.add_argument("--url", required=True)
    send_parser.add_argument("--output", required=True)
    send_parser.add_argument("--timeout", type=float, default=None)
    send_parser.add_argument("--force", action="store_true")
    send_parser.set_defaults(func=cmd_send)

    generate_vo_parser = subparsers.add_parser(
        "generate-vo",
        help="Validate and send a /with-timestamps TTS payload, writing audio + alignment JSON",
    )
    generate_vo_parser.add_argument("--payload", required=True)
    generate_vo_parser.add_argument("--url", required=True)
    generate_vo_parser.add_argument("--audio-output", required=True)
    generate_vo_parser.add_argument("--alignment-output", required=True)
    generate_vo_parser.add_argument("--timeout", type=float, default=None)
    generate_vo_parser.add_argument("--force", action="store_true")
    generate_vo_parser.set_defaults(func=cmd_generate_vo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
