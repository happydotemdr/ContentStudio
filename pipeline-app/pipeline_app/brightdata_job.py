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

BRIGHTDATA_API_BASE = "https://api.brightdata.com/datasets/v3"
REQUEST_TIMEOUT_S = 30


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
    response = requests.get(
        f"{api_base}/progress/{job_id}",
        headers=_auth(key),
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    return _json_field(response, f"progress/{job_id}", "status")


def fetch_results(api_base: str, job_id: str, key: str) -> list[dict]:
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
