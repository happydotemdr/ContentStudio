"""Thin HTTP client for the ElevenLabs API.

send() never lets requests.exceptions.RequestException propagate -- it
returns a SendResult instead, so callers get uniform control flow. Any other
exception (a genuine bug) is not caught here.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import requests

DEFAULT_TIMEOUT_S = 300.0


@dataclass(frozen=True)
class SendResult:
    ok: bool
    status_code: int | None
    content_type: str | None
    body: bytes | None
    error_message: str | None


def send(
    url: str,
    payload_bytes: bytes,
    api_key: str,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> SendResult:
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, headers=headers, data=payload_bytes, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        error_response = getattr(exc, "response", None)
        status_code = getattr(error_response, "status_code", None)
        if error_response is not None:
            body_text = error_response.text[:2000]
            message = f"{exc} -- response body: {body_text}"
        else:
            message = str(exc)
        return SendResult(
            ok=False,
            status_code=status_code,
            content_type=None,
            body=None,
            error_message=message,
        )

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("audio/"):
        return SendResult(
            ok=False,
            status_code=response.status_code,
            content_type=content_type,
            body=response.content,
            error_message=(
                f"expected an audio/* response, got Content-Type {content_type!r}"
            ),
        )

    return SendResult(
        ok=True,
        status_code=response.status_code,
        content_type=content_type,
        body=response.content,
        error_message=None,
    )


@dataclass(frozen=True)
class TimestampsResult:
    ok: bool
    status_code: int | None
    audio_bytes: bytes | None
    alignment: dict | None
    error_message: str | None
    # Raw response bytes, populated only on failure paths that actually
    # received a response body (never on a network-level failure with no
    # response at all) -- lets a caller quarantine an unexpected body after
    # a billed call instead of discarding it, mirroring send()'s own
    # quarantine behavior in cmd_send.
    raw_body: bytes | None = None


def send_with_timestamps(
    url: str,
    payload_bytes: bytes,
    api_key: str,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> TimestampsResult:
    """Like send(), but for endpoints that return application/json with a
    base64-encoded audio field (e.g. /text-to-speech/{voice_id}/with-timestamps)
    instead of a raw audio/* body. Never lets requests.exceptions.RequestException
    propagate -- returns a TimestampsResult instead, mirroring send()'s contract.
    """
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, headers=headers, data=payload_bytes, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        error_response = getattr(exc, "response", None)
        status_code = getattr(error_response, "status_code", None)
        if error_response is not None:
            body_text = error_response.text[:2000]
            message = f"{exc} -- response body: {body_text}"
            raw_body = getattr(error_response, "content", None)
        else:
            message = str(exc)
            raw_body = None
        return TimestampsResult(
            ok=False, status_code=status_code, audio_bytes=None, alignment=None,
            error_message=message, raw_body=raw_body,
        )

    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("application/json"):
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=(
                f"expected an application/json response, got Content-Type {content_type!r}"
            ),
            raw_body=response.content,
        )

    try:
        body = response.json()
    except ValueError as exc:
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=f"response Content-Type was application/json but the body did not parse: {exc}",
            raw_body=response.content,
        )

    if not isinstance(body, dict):
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=f"response JSON must be an object, got {type(body).__name__}",
            raw_body=response.content,
        )

    audio_b64 = body.get("audio_base64")
    alignment = body.get("alignment")
    if audio_b64 is None or alignment is None:
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=(
                "response JSON is missing 'audio_base64' or 'alignment' -- "
                f"got keys {sorted(body.keys())}"
            ),
            raw_body=response.content,
        )

    try:
        audio_bytes = base64.b64decode(audio_b64, validate=True)
    except (ValueError, TypeError) as exc:
        return TimestampsResult(
            ok=False, status_code=response.status_code, audio_bytes=None, alignment=None,
            error_message=f"audio_base64 field did not decode as base64: {exc}",
            raw_body=response.content,
        )

    return TimestampsResult(
        ok=True, status_code=response.status_code,
        audio_bytes=audio_bytes, alignment=alignment,
        error_message=None,
    )
