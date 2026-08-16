"""Bright Data Web Scraper API v3 job client, shared by every Bright
Data-backed discovery adapter (discovery_instagram, discovery_linkedin).

Bright Data's API is asynchronous -- trigger -> poll -> fetch -- and bills per
job/record. The error discipline in await_results is the load-bearing part: a
job that times out or reports 'failed' MUST raise, never return []. An empty
list means "the job completed and there was genuinely nothing", which
discovery_engine records as the healthy status 'no_new_content'. Returning []
on failure would make a paid, failed job indistinguishable from a quiet day --
the exact bug that shipped in the first Instagram adapter. The tests that pin
this invariant are test_brightdata_job.py's *_never_fetches_* and
*_distinguishable_* pair -- deleting them re-opens D-03.

This module knows nothing about any particular dataset. Callers supply the
dataset id, the query params that select the product mode, and the request
body.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

from pipeline_app import obs

BRIGHTDATA_API_BASE = "https://api.brightdata.com/datasets/v3"
REQUEST_TIMEOUT_S = 30

_DIAGNOSTICS: list[dict] = []


def record_diagnostic(*, kind: str, severity: str, source: str, message: str,
                      detail: dict | None = None) -> dict:
    """One structured, durable adapter diagnostic (B-01).

    Writes through to obs.log -- stderr AND the dated log file, which is the
    surface the scheduled task lacks entirely today -- and buffers a record
    for drain_diagnostics(). Never raises: a failure to report must not mask
    the degradation being reported.
    """
    record = {"kind": kind, "severity": severity, "source": source,
              "message": message, "detail": dict(detail or {})}
    _DIAGNOSTICS.append(record)
    try:
        obs.log(kind, level=severity, source=source, message=message, **record["detail"])
    except Exception:  # noqa: BLE001 - see the docstring; never widened
        pass
    return record


def drain_diagnostics() -> list[dict]:
    """Take and clear the buffered diagnostics.

    P8's run loop calls this once per handle and writes each record with
    obs.record_event(conn, run_id=..., **record). Draining rather than
    accumulating keeps one handle's diagnostics off another handle's row.
    """
    drained = list(_DIAGNOSTICS)
    _DIAGNOSTICS.clear()
    return drained


class BrightDataJobTimeout(Exception):
    """A Bright Data collection job did not reach 'ready' within the deadline."""


class BrightDataJobFailed(Exception):
    """A Bright Data collection job reported status 'failed'."""


class BrightDataResponseError(Exception):
    """A Bright Data endpoint returned a body this client cannot use.

    Distinct from an HTTP error: the call succeeded, the shape did not. The
    message names the endpoint AND the keys actually received, which is the
    difference between a five-minute and a two-hour diagnosis across four
    platforms (B-20).
    """


class BrightDataConfigError(Exception):
    """An adapter is configured with a dataset id that cannot be collected."""


def _require_provisioned(dataset_id: str) -> None:
    """B-24: the Instagram adapter carried this check privately, where it was
    unreachable (its DATASET_ID has been real since 2026-08-06). Here it
    covers all four adapters and any future one, and it runs before the POST
    so an unprovisioned id can never start a billed job."""
    if not (dataset_id or "").strip() or dataset_id.startswith("gd_REPLACE"):
        raise BrightDataConfigError(
            f"Bright Data dataset id {dataset_id!r} is not provisioned -- set the "
            "real dataset id for this adapter before triggering a job"
        )


def read_key(env_var: str, key_file: Path) -> str | None:
    """The Bright Data API token, or None if not configured. Env var first --
    the scheduled task inherits the User environment -- then a gitignored
    file for convenience, matching discovery_youtube_api.api_key()."""
    env_key = os.environ.get(env_var, "").strip()
    if env_key:
        return env_key
    if key_file.exists():
        file_key = key_file.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def _shape_of(payload) -> str:
    if isinstance(payload, dict):
        return f"keys {sorted(payload)}"
    return type(payload).__name__


def _json_field(response, endpoint: str, field: str):
    try:
        payload = response.json()
    except ValueError as exc:
        raise BrightDataResponseError(
            f"{endpoint} returned a non-JSON body"
        ) from exc
    if not isinstance(payload, dict) or field not in payload:
        raise BrightDataResponseError(
            f"{endpoint} response has no '{field}' -- received {_shape_of(payload)}"
        )
    return payload[field]


RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 4
RETRY_BASE_S = 2.0


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    response = getattr(exc, "response", None)
    return response is not None and response.status_code in RETRY_STATUSES


def _with_retry(call, *, what: str):
    """Bounded retry with backoff for a NON-BILLING call.

    B-18: a single transient 429/503 on one of up to 60 polls used to abandon
    a collection job that was already triggered and billed. Polling and
    fetching a snapshot cost nothing, so retrying them is free insurance.
    trigger() is deliberately NOT wrapped -- see the comment there.
    On exhaustion the original exception propagates, so a genuine failure
    still reaches the engine's per-handle error path.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - re-raised below unless transient
            if attempt == MAX_ATTEMPTS or not _is_transient(exc):
                raise
            time.sleep(RETRY_BASE_S * (2 ** (attempt - 1)))


def trigger(api_base: str, dataset_id: str, params: dict, body: list[dict], key: str) -> str:
    """Start a collection job; returns its snapshot id.

    `params` carries the product-mode selectors (type, discover_by,
    limit_per_input, ...) and is merged over dataset_id. `body` is a bare
    array -- /trigger's documented shape, verified live. The dashboard's
    {"input": [...]} object form belongs to the synchronous /scrape endpoint,
    which no adapter uses: a discovery job takes minutes and would hang an
    HTTP call.
    """
    _require_provisioned(dataset_id)
    # NOT wrapped in _with_retry. Bright Data bills per record: a trigger whose
    # response is lost in transit may have started a job on the vendor side, so
    # a retry can create -- and pay for -- a second collection of the same
    # posts. Poll and fetch are free and are retried; this one is not (B-18).
    response = requests.post(
        f"{api_base}/trigger",
        params={"dataset_id": dataset_id, **params},
        headers=_auth(key),
        json=body,
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return _json_field(response, "trigger", "snapshot_id")


def poll_status(api_base: str, job_id: str, key: str) -> str:
    def _do_poll():
        response = requests.get(
            f"{api_base}/progress/{job_id}",
            headers=_auth(key),
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        return _json_field(response, f"progress/{job_id}", "status")

    return _with_retry(_do_poll, what=f"progress/{job_id}")


def fetch_results(api_base: str, job_id: str, key: str) -> list[dict]:
    def _do_fetch():
        response = requests.get(
            f"{api_base}/snapshot/{job_id}",
            params={"format": "json"},
            headers=_auth(key),
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise BrightDataResponseError(
                f"snapshot/{job_id} returned {type(payload).__name__}, not a list of "
                f"rows -- received {_shape_of(payload)}"
            )
        return payload

    return _with_retry(_do_fetch, what=f"snapshot/{job_id}")


def await_results(trigger_fn, poll_fn, fetch_fn, *, label: str,
                  poll_timeout_s: float, poll_interval_s: float) -> list[dict]:
    """Run one full trigger -> poll -> fetch cycle.

    The three callables are injected rather than called directly so each
    adapter keeps its own module-level trigger/poll/fetch functions -- which
    is what lets adapter tests monkeypatch them. `label` is interpolated into
    error messages (e.g. "for nike") so a failure names the handle.
    """
    job_id = trigger_fn()
    deadline = time.monotonic() + poll_timeout_s
    while True:
        status = poll_fn(job_id)
        if status == "ready":
            return fetch_fn(job_id)
        if status == "failed":
            raise BrightDataJobFailed(f"Bright Data job {job_id} {label} failed")
        if time.monotonic() >= deadline:
            raise BrightDataJobTimeout(
                f"Bright Data job {job_id} {label} timed out after {poll_timeout_s}s"
            )
        time.sleep(poll_interval_s)
