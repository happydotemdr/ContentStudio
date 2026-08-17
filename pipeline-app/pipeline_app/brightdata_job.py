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

import datetime as _dt
import json
import os
import time
from pathlib import Path

import requests

from pipeline_app import obs

BRIGHTDATA_API_BASE = "https://api.brightdata.com/datasets/v3"
REQUEST_TIMEOUT_S = 30

_DIAGNOSTICS: list[dict] = []

PENDING_STORE_PATH = Path(__file__).resolve().parent.parent / "logs" / "brightdata-pending.json"
PENDING_MAX_AGE_H = 48


def _read_store() -> dict:
    try:
        payload = json.loads(PENDING_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_store(payload: dict) -> None:
    # Write-temp-then-rename, same as every adapter's download_item: a killed
    # process must never leave a half-written store that reads as valid.
    PENDING_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PENDING_STORE_PATH.with_name(PENDING_STORE_PATH.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(PENDING_STORE_PATH)


def record_pending(key: str, snapshot_id: str) -> None:
    """Remember a snapshot that was paid for and not collected (B-19)."""
    store = _read_store()
    store[key] = {
        "snapshot_id": snapshot_id,
        "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    _write_store(store)


def load_pending(key: str) -> dict | None:
    """The pending entry for this platform/handle, or None if absent or older
    than PENDING_MAX_AGE_H (Bright Data snapshots do not live forever, and a
    stale entry would cost one wasted poll every run)."""
    entry = _read_store().get(key)
    if not entry:
        return None
    try:
        recorded = _dt.datetime.fromisoformat(entry["recorded_at"])
    except (KeyError, TypeError, ValueError):
        return None
    age_h = (_dt.datetime.now(_dt.timezone.utc) - recorded).total_seconds() / 3600
    return None if age_h > PENDING_MAX_AGE_H else entry


def clear_pending(key: str) -> None:
    store = _read_store()
    if store.pop(key, None) is not None:
        _write_store(store)


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


def config_int(name: str, default: int) -> int:
    """An operational knob: environment override, module literal as default.

    B-03: every cap and timeout was a source literal. Overrides are read PER
    PLATFORM and never shared -- discovery_x.py:40-43 records why one number
    does not fit all four. Note that raising an ITEM CAP raises Bright Data
    spend proportionally; raising a TIMEOUT does not.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        record_diagnostic(kind="config.bad_override", severity="warning",
                          source="brightdata_job",
                          message=f"{name}={raw!r} is not a positive integer; using {default}",
                          detail={"name": name, "raw": raw, "default": default})
        return default
    return value


def is_saturated(collected: int, *, cap: int) -> bool:
    """True when the cap, not the account, decided where this batch ended.

    B-02 (S1): the four Bright Data platforms fetch at most `cap` posts per
    handle per run and are all excluded from BACKFILL_SUPPORTED_PLATFORMS, so
    anything above the cap is dropped with no recovery path at all. A
    saturated batch is therefore a data-loss event, not a busy day.
    """
    return cap > 0 and collected >= cap


class _BrightDataJobError(Exception):
    """Base for job-level failures. Carries the snapshot id as an ATTRIBUTE,
    not only inside the message: a snapshot the operator paid for must be
    recoverable by code, not by reading prose out of error_message (B-19)."""

    def __init__(self, message: str, *, snapshot_id: str | None = None,
                 label: str = "", poll_timeout_s: float | None = None):
        super().__init__(message)
        self.snapshot_id = snapshot_id
        self.label = label
        self.poll_timeout_s = poll_timeout_s


class BrightDataJobTimeout(_BrightDataJobError):
    """A Bright Data collection job did not reach 'ready' within the deadline."""


class BrightDataJobFailed(_BrightDataJobError):
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


# Default OFF. Deleting a snapshot is free but irreversible: run it only once
# the operator is satisfied the fetched rows reached disk. It is NEVER called
# on the timeout path -- that snapshot is the only copy of data already paid
# for, and T8/T9 exist to recover it.
DELETE_AFTER_FETCH = False


def delete_snapshot(api_base: str, job_id: str, key: str) -> None:
    """Delete a collected snapshot from Bright Data's side (B-19 cost item C6).

    Free to call, but irreversible: a deleted snapshot cannot be recovered by
    resume_pending or anything else. Callers must only invoke this once the
    corresponding rows are already safely in hand -- see DELETE_AFTER_FETCH
    and its use in await_results.
    """
    def _do_delete():
        response = requests.delete(
            f"{api_base}/snapshot/{job_id}",
            headers=_auth(key),
            timeout=REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        return response

    _with_retry(_do_delete, what=f"delete snapshot/{job_id}")


def await_results(trigger_fn, poll_fn, fetch_fn, *, label: str,
                  poll_timeout_s: float, poll_interval_s: float,
                  pending_key: str | None = None,
                  cleanup_fn=None) -> list[dict]:
    """Run one full trigger -> poll -> fetch cycle.

    The three callables are injected rather than called directly so each
    adapter keeps its own module-level trigger/poll/fetch functions -- which
    is what lets adapter tests monkeypatch them. `label` is interpolated into
    error messages (e.g. "for nike") so a failure names the handle.

    `pending_key` identifies this platform/handle for the durable pending-
    snapshot store (B-19). On timeout the job's snapshot id is persisted so a
    later run can fetch it for free instead of abandoning paid-for data. A
    failed job is not persisted -- there is nothing to recover.

    `cleanup_fn`, if given, is called ONLY in the ready branch, after
    fetch_fn has already returned successfully -- never on the failed or
    timeout paths, where the snapshot may be the only copy of data already
    paid for. Callers wire delete_snapshot in here when DELETE_AFTER_FETCH
    is True; this function does not consult that flag itself.
    """
    job_id = trigger_fn()
    deadline = time.monotonic() + poll_timeout_s
    while True:
        status = poll_fn(job_id)
        if status == "ready":
            rows = fetch_fn(job_id)
            if cleanup_fn is not None:
                cleanup_fn(job_id)
            return rows
        if status == "failed":
            raise BrightDataJobFailed(
                f"Bright Data job {job_id} {label} failed",
                snapshot_id=job_id, label=label, poll_timeout_s=poll_timeout_s
            )
        if time.monotonic() >= deadline:
            if pending_key:
                record_pending(pending_key, job_id)
            record_diagnostic(
                kind="brightdata.snapshot_abandoned", severity="error",
                source=label,
                message=f"Bright Data job {job_id} {label} timed out after "
                         f"{poll_timeout_s}s -- snapshot {job_id} left uncollected",
                detail={"snapshot_id": job_id, "label": label,
                        "poll_timeout_s": poll_timeout_s, "pending_key": pending_key},
            )
            raise BrightDataJobTimeout(
                f"Bright Data job {job_id} {label} timed out after {poll_timeout_s}s",
                snapshot_id=job_id, label=label, poll_timeout_s=poll_timeout_s
            )
        time.sleep(poll_interval_s)


def resume_pending(key: str, poll_fn, fetch_fn) -> list[dict] | None:
    """One free attempt to collect a snapshot a previous run paid for and
    abandoned (B-19).

    Returns the rows if the snapshot is now ready, None otherwise. NEVER
    triggers a new job: the whole point is that this data is already bought.
    A poll error is swallowed into None -- deliberately, because this is a
    best-effort recovery running before the real job, and failing here must
    not fail a run that is otherwise fine. That is the ONE place in this
    module where an error becomes None, and it is why it is loud in the
    diagnostics buffer.
    """
    entry = load_pending(key)
    if not entry:
        return None
    snapshot_id = entry["snapshot_id"]
    try:
        status = poll_fn(snapshot_id)
    except Exception as exc:  # noqa: BLE001 - see the docstring
        record_diagnostic(kind="brightdata.resume_poll_failed", severity="warning",
                          source="brightdata_job",
                          message=f"could not poll abandoned snapshot {snapshot_id}: {exc}",
                          detail={"key": key, "snapshot_id": snapshot_id})
        return None
    if status == "ready":
        rows = fetch_fn(snapshot_id)
        clear_pending(key)
        record_diagnostic(kind="brightdata.resumed", severity="warning",
                          source="brightdata_job",
                          message=(f"recovered {len(rows)} row(s) from snapshot "
                                   f"{snapshot_id}, abandoned by an earlier run"),
                          detail={"key": key, "snapshot_id": snapshot_id, "rows": len(rows)})
        return rows
    if status == "failed":
        clear_pending(key)
        record_diagnostic(kind="brightdata.resume_failed", severity="error",
                          source="brightdata_job",
                          message=(f"abandoned snapshot {snapshot_id} reported 'failed'; "
                                   f"its records are lost"),
                          detail={"key": key, "snapshot_id": snapshot_id})
    return None
