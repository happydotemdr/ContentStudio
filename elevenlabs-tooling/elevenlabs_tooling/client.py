"""Thin HTTP client for the ElevenLabs API.

send() never lets requests.exceptions.RequestException propagate -- it
returns a SendResult instead, so callers get uniform control flow. Any other
exception (a genuine bug) is not caught here.
"""

from __future__ import annotations

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
