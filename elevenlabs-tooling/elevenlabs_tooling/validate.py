"""Payload/URL validation -- the hard gate before any ElevenLabs API call.

Structure mirrors scripts/lint_prompt_sheet.py (Gate C) in the parent repo: a
flat list of Finding(check, message) accumulated by running every check to
completion, never stopping at the first problem. "E#" findings block a send;
"W#" findings are informational only.

Every check that reads a payload field guards its type before comparing or
measuring it: a malformed payload must produce a Finding, never an uncaught
TypeError from a tool whose entire job is to fail safely on bad input.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

PINNED_NARRATOR_VOICE_ID = "eDwT8Vhp2yxJzAMmuuPA"
ALLOWED_HOST = "api.elevenlabs.io"
ALLOWED_SCHEME = "https"
OUT_OF_SCOPE_PATH_MARKERS = (
    "/stream",
    "/compose_stream",
    "/music/detailed",
    "/compose_detailed",
    "/compose_detailed_stream",
)


@dataclass(frozen=True)
class Finding:
    check: str
    message: str


def is_blocking(finding: Finding) -> bool:
    return finding.check.startswith("E")


def validate(payload: dict, url: str) -> list[Finding]:
    """Run every check; return every finding. Never stops at the first one."""
    findings: list[Finding] = []
    findings.extend(_check_url(url))
    findings.extend(_check_shape(payload))
    return findings


def _check_url(url: str) -> list[Finding]:
    findings: list[Finding] = []
    parts = urlsplit(url)
    if parts.scheme != ALLOWED_SCHEME or parts.hostname != ALLOWED_HOST:
        findings.append(Finding(
            "E1",
            f"URL must be {ALLOWED_SCHEME}://{ALLOWED_HOST}/... , got "
            f"{parts.scheme!r}://{parts.hostname!r}",
        ))
    lowered_path = parts.path.lower()
    for marker in OUT_OF_SCOPE_PATH_MARKERS:
        if marker in lowered_path:
            findings.append(Finding(
                "E2",
                f"URL path {parts.path!r} targets a v1-out-of-scope endpoint "
                f"({marker}) -- streaming and multipart-detailed responses "
                "are not supported by this tool",
            ))
            break
    return findings


def _check_shape(payload: dict) -> list[Finding]:
    has_text = bool(payload.get("text"))
    has_prompt = payload.get("prompt") is not None
    has_plan = payload.get("composition_plan") is not None
    music_field_count = sum([has_prompt, has_plan])

    if has_text and music_field_count == 0:
        return []
    if not has_text and music_field_count == 1:
        return []
    if has_text and music_field_count > 0:
        return [Finding(
            "E3",
            "payload has both a TTS field (text) and a music field "
            "(prompt/composition_plan) -- pick one shape",
        )]
    if music_field_count > 1:
        return [Finding(
            "E3",
            "payload has both prompt and composition_plan -- they are "
            "mutually exclusive",
        )]
    return [Finding(
        "E3",
        "payload is neither TTS-shaped (non-empty text) nor music-shaped "
        "(exactly one of prompt/composition_plan)",
    )]
