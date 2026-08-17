from pathlib import Path

import pytest
import requests

from pipeline_app import brightdata_job as bd


def _http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status}", response=response)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_read_key_prefers_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("SOME_KEY", "env-key")
    key_file = tmp_path / "key.txt"
    key_file.write_text("file-key", encoding="utf-8")
    assert bd.read_key("SOME_KEY", key_file) == "env-key"


def test_read_key_falls_back_to_file_and_strips(monkeypatch, tmp_path):
    monkeypatch.delenv("SOME_KEY", raising=False)
    key_file = tmp_path / "key.txt"
    key_file.write_text("  file-key\n", encoding="utf-8")
    assert bd.read_key("SOME_KEY", key_file) == "file-key"


def test_read_key_none_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.delenv("SOME_KEY", raising=False)
    assert bd.read_key("SOME_KEY", tmp_path / "absent.txt") is None


def test_trigger_posts_dataset_id_with_extra_params_and_returns_snapshot_id(monkeypatch):
    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        captured.update(url=url, params=params, headers=headers, json=json, timeout=timeout)
        return _FakeResponse({"snapshot_id": "snap123"})

    monkeypatch.setattr(bd.requests, "post", fake_post)
    result = bd.trigger("https://api.example/v3", "gd_abc",
                        {"type": "discover_new"}, [{"url": "u"}], "the-key")

    assert result == "snap123"
    assert captured["url"] == "https://api.example/v3/trigger"
    assert captured["params"] == {"dataset_id": "gd_abc", "type": "discover_new"}
    assert captured["headers"]["Authorization"] == "Bearer the-key"
    assert captured["json"] == [{"url": "u"}]
    assert captured["timeout"] == bd.REQUEST_TIMEOUT_S


def test_trigger_refuses_an_unprovisioned_dataset_id_before_any_http_call(monkeypatch):
    """The guard must live where every adapter passes through, and must fire
    BEFORE requests.post -- an unprovisioned trigger that reached Bright Data
    would be a billed job against a nonexistent dataset."""
    def _fail_if_called(*a, **k):
        raise AssertionError("requests.post must not run for an unprovisioned dataset")

    monkeypatch.setattr(bd.requests, "post", _fail_if_called)
    for bad in ("gd_REPLACE_WITH_REAL_DATASET_ID", "", "   "):
        with pytest.raises(bd.BrightDataConfigError, match="not provisioned"):
            bd.trigger("https://api.example/v3", bad, {}, [{"url": "u"}], "k")


def test_poll_status_returns_status_field(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, headers=headers)
        return _FakeResponse({"status": "ready"})

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.poll_status("https://api.example/v3", "job1", "the-key") == "ready"
    assert captured["url"] == "https://api.example/v3/progress/job1"
    assert captured["headers"]["Authorization"] == "Bearer the-key"


def test_poll_status_retries_a_transient_503_and_then_succeeds(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    attempts = iter([_http_error(503), _http_error(429), None])

    def fake_get(url, params=None, headers=None, timeout=None):
        failure = next(attempts)
        if failure is not None:
            raise failure
        return _FakeResponse({"status": "ready"})

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.poll_status("https://api.example/v3", "job1", "k") == "ready"


def test_poll_status_does_not_retry_a_401(monkeypatch):
    """A bad token is not transient. Retrying it wastes four round-trips and
    delays the one message the operator needs."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        raise _http_error(401)

    monkeypatch.setattr(bd.requests, "get", fake_get)
    with pytest.raises(requests.HTTPError):
        bd.poll_status("https://api.example/v3", "job1", "k")
    assert len(calls) == 1


def test_poll_status_raises_after_the_retry_budget_is_exhausted(monkeypatch):
    """The raise-on-exhaustion contract stays intact: a genuine outage still
    surfaces as a per-handle error, it is not swallowed into a default."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.requests, "get",
                        lambda *a, **k: (_ for _ in ()).throw(_http_error(503)))
    with pytest.raises(requests.HTTPError):
        bd.poll_status("https://api.example/v3", "job1", "k")


def test_fetch_results_requests_json_format(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, params=params)
        return _FakeResponse([{"id": "1"}])

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.fetch_results("https://api.example/v3", "job1", "the-key") == [{"id": "1"}]
    assert captured["url"] == "https://api.example/v3/snapshot/job1"
    assert captured["params"] == {"format": "json"}


def test_fetch_results_retries_a_transient_connection_error(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    attempts = iter([requests.ConnectionError("reset by peer"), None])

    def fake_get(url, params=None, headers=None, timeout=None):
        failure = next(attempts)
        if failure is not None:
            raise failure
        return _FakeResponse([{"id": "1"}])

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.fetch_results("https://api.example/v3", "job1", "k") == [{"id": "1"}]


def test_trigger_is_never_retried_because_a_retried_trigger_double_bills(monkeypatch):
    """Bright Data bills per record. A trigger whose response was lost may
    have started a job anyway; retrying it starts -- and pays for -- a second
    one. This is the one call in the module that must fail fast."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    calls = []

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls.append(url)
        raise _http_error(503)

    monkeypatch.setattr(bd.requests, "post", fake_post)
    with pytest.raises(requests.HTTPError):
        bd.trigger("https://api.example/v3", "gd_abc", {}, [{"url": "u"}], "k")
    assert len(calls) == 1, "trigger must be attempted exactly once"


def test_await_results_returns_rows_once_ready(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    statuses = iter(["running", "running", "ready"])
    rows = bd.await_results(
        trigger_fn=lambda: "job1",
        poll_fn=lambda job_id: next(statuses),
        fetch_fn=lambda job_id: [{"id": "1"}],
        label="for someone", poll_timeout_s=300, poll_interval_s=5,
    )
    assert rows == [{"id": "1"}]


def test_await_results_raises_on_failed_status(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    with pytest.raises(bd.BrightDataJobFailed, match="job1 for someone failed"):
        bd.await_results(
            trigger_fn=lambda: "job1",
            poll_fn=lambda job_id: "failed",
            fetch_fn=lambda job_id: [],
            label="for someone", poll_timeout_s=300, poll_interval_s=5,
        )


def test_await_results_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)
    with pytest.raises(bd.BrightDataJobTimeout, match="timed out"):
        bd.await_results(
            trigger_fn=lambda: "job1",
            poll_fn=lambda job_id: "running",  # never ready
            fetch_fn=lambda job_id: [],
            label="for someone", poll_timeout_s=0, poll_interval_s=5,
        )


def test_delete_snapshot_is_off_by_default(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)

    def _fail_if_called(*a, **k):
        raise AssertionError("no delete request may be made unless opted in")

    monkeypatch.setattr(bd.requests, "delete", _fail_if_called)
    assert bd.await_results(trigger_fn=lambda: "j", poll_fn=lambda i: "ready",
                            fetch_fn=lambda i: [{"id": "1"}], label="l",
                            poll_timeout_s=300, poll_interval_s=5) == [{"id": "1"}]


def test_delete_after_fetch_only_runs_once_the_rows_are_in_hand(monkeypatch):
    """Deleting a snapshot destroys paid data. It may only happen AFTER a
    successful fetch -- never on the timeout path, where the snapshot is the
    only copy of what was bought."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)
    monkeypatch.setattr(bd, "DELETE_AFTER_FETCH", True)
    deleted = []
    monkeypatch.setattr(bd, "delete_snapshot",
                        lambda api_base, job_id, key: deleted.append(job_id))
    with pytest.raises(bd.BrightDataJobTimeout):
        bd.await_results(trigger_fn=lambda: "snap-timeout", poll_fn=lambda i: "running",
                         fetch_fn=lambda i: [], label="l",
                         poll_timeout_s=0, poll_interval_s=5)
    assert deleted == []


def test_timeout_exception_carries_the_snapshot_id_as_data_not_only_prose(monkeypatch):
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)
    with pytest.raises(bd.BrightDataJobTimeout) as exc:
        bd.await_results(trigger_fn=lambda: "snap-abc",
                         poll_fn=lambda job_id: "running",
                         fetch_fn=lambda job_id: [],
                         label="for x/CNN", poll_timeout_s=0, poll_interval_s=5)
    assert exc.value.snapshot_id == "snap-abc"
    assert exc.value.label == "for x/CNN"
    assert exc.value.poll_timeout_s == 0


def test_timeout_persists_the_snapshot_for_a_later_free_fetch(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)
    with pytest.raises(bd.BrightDataJobTimeout):
        bd.await_results(trigger_fn=lambda: "snap-abc",
                         poll_fn=lambda job_id: "running",
                         fetch_fn=lambda job_id: [],
                         label="for x/CNN", poll_timeout_s=0, poll_interval_s=5,
                         pending_key="x/CNN")
    assert bd.load_pending("x/CNN")["snapshot_id"] == "snap-abc"


def test_a_failed_job_is_not_persisted_because_there_is_nothing_to_recover(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    with pytest.raises(bd.BrightDataJobFailed):
        bd.await_results(trigger_fn=lambda: "snap-dead",
                         poll_fn=lambda job_id: "failed",
                         fetch_fn=lambda job_id: [],
                         label="for x/CNN", poll_timeout_s=300, poll_interval_s=5,
                         pending_key="x/CNN")
    assert bd.load_pending("x/CNN") is None


def test_pending_store_survives_a_corrupt_file(monkeypatch, tmp_path):
    """The store is a recovery aid, never a dependency: a truncated write from
    a killed process must not take the next run down with it."""
    store = tmp_path / "pending.json"
    store.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", store)
    assert bd.load_pending("x/CNN") is None
    bd.record_pending("x/CNN", "snap-1")
    assert bd.load_pending("x/CNN")["snapshot_id"] == "snap-1"


def test_await_results_never_fetches_when_job_fails(monkeypatch):
    """A failed job must raise, not fall through to an empty fetch -- an empty
    return would be recorded by the engine as the healthy status
    'no_new_content' for a batch that was billed."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)

    def _fail_if_called(job_id):
        raise AssertionError("fetch must not run for a failed job")

    with pytest.raises(bd.BrightDataJobFailed):
        bd.await_results(
            trigger_fn=lambda: "job1",
            poll_fn=lambda job_id: "failed",
            fetch_fn=_fail_if_called,
            label="for someone", poll_timeout_s=300, poll_interval_s=5,
        )


def test_await_results_raises_and_never_fetches_on_timeout(monkeypatch):
    """Fault test. A timeout must raise, not fall through to a fetch whose
    empty result the engine records as the healthy status 'no_new_content'."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)
    monkeypatch.setattr(bd.time, "monotonic", lambda: 10_000.0)

    def _fail_if_called(job_id):
        raise AssertionError("fetch must not run for a timed-out job")

    with pytest.raises(bd.BrightDataJobTimeout):
        bd.await_results(
            trigger_fn=lambda: "job1",
            poll_fn=lambda job_id: "running",
            fetch_fn=_fail_if_called,
            label="for someone", poll_timeout_s=0, poll_interval_s=5,
        )


def test_trigger_names_the_endpoint_and_the_received_keys_on_a_bad_body(monkeypatch):
    monkeypatch.setattr(bd.requests, "post",
                        lambda *a, **k: _FakeResponse({"error": "bad token"}))
    with pytest.raises(bd.BrightDataResponseError) as exc:
        bd.trigger("https://api.example/v3", "gd_abc", {}, [{"url": "u"}], "k")
    assert "trigger" in str(exc.value)
    assert "snapshot_id" in str(exc.value)
    assert "error" in str(exc.value)          # the keys actually received


def test_fetch_results_rejects_a_dict_payload_instead_of_handing_it_on(monkeypatch):
    """A dict response used to reach _normalize_row, which iterated key
    STRINGS and died with AttributeError naming neither the endpoint nor the
    cause."""
    monkeypatch.setattr(bd.requests, "get",
                        lambda *a, **k: _FakeResponse({"error": "snapshot expired"}))
    with pytest.raises(bd.BrightDataResponseError, match="not a list of rows"):
        bd.fetch_results("https://api.example/v3", "job1", "k")


def test_failed_job_is_distinguishable_from_a_genuinely_empty_one(monkeypatch):
    """Distinguishability test. The whole discipline is that these two
    outcomes must NOT look the same to the caller."""
    monkeypatch.setattr(bd.time, "sleep", lambda s: None)

    empty = bd.await_results(
        trigger_fn=lambda: "job-empty",
        poll_fn=lambda job_id: "ready",
        fetch_fn=lambda job_id: [],
        label="for quiet-account", poll_timeout_s=300, poll_interval_s=5,
    )
    assert empty == []

    with pytest.raises(bd.BrightDataJobFailed):
        bd.await_results(
            trigger_fn=lambda: "job-failed",
            poll_fn=lambda job_id: "failed",
            fetch_fn=lambda job_id: [],
            label="for broken-account", poll_timeout_s=300, poll_interval_s=5,
        )


def test_record_diagnostic_buffers_a_record_shaped_for_the_events_table():
    bd.drain_diagnostics()
    bd.record_diagnostic(kind="adapter.billed_nothing", severity="error",
                         source="discovery_facebook", message="NASA captured nothing",
                         detail={"platform": "facebook", "handle": "NASA"})
    drained = bd.drain_diagnostics()
    assert len(drained) == 1
    record = drained[0]
    assert record["kind"] == "adapter.billed_nothing"
    assert record["severity"] == "error"
    assert record["source"] == "discovery_facebook"
    assert record["detail"]["handle"] == "NASA"
    # obs.record_event's severity vocabulary -- a record P8 cannot write is useless.
    assert record["severity"] in {"info", "warning", "error", "critical"}


def test_drain_diagnostics_empties_the_buffer_so_a_second_handle_sees_only_its_own():
    bd.drain_diagnostics()
    bd.record_diagnostic(kind="k", severity="warning", source="s", message="m")
    assert len(bd.drain_diagnostics()) == 1
    assert bd.drain_diagnostics() == []


def test_record_diagnostic_writes_through_to_obs_log(monkeypatch):
    """Surfacing. The event row is P8's half; the log FILE is this package's,
    and it is the surface that exists whether or not a run row does."""
    emitted = []
    monkeypatch.setattr(bd.obs, "log",
                        lambda event, **fields: emitted.append((event, fields)))
    bd.record_diagnostic(kind="adapter.billed_nothing", severity="error",
                         source="discovery_x", message="CNN captured nothing",
                         detail={"handle": "CNN"})
    assert emitted == [("adapter.billed_nothing",
                        {"level": "error", "source": "discovery_x",
                         "message": "CNN captured nothing", "handle": "CNN"})]


def test_record_diagnostic_never_masks_the_thing_it_is_reporting(monkeypatch):
    """A broken logger must not turn a reportable degradation into a crash."""
    def _boom(*a, **k):
        raise OSError("log directory is read-only")

    bd.drain_diagnostics()  # isolation: the prior test's write-through leaves a record
    monkeypatch.setattr(bd.obs, "log", _boom)
    bd.record_diagnostic(kind="k", severity="error", source="s", message="m")
    assert bd.drain_diagnostics()[0]["kind"] == "k"


def test_resume_pending_collects_a_ready_snapshot_without_triggering_anything(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    bd.record_pending("x/CNN", "snap-abc")
    rows = bd.resume_pending("x/CNN",
                             poll_fn=lambda job_id: "ready",
                             fetch_fn=lambda job_id: [{"id": "1"}])
    assert rows == [{"id": "1"}]
    assert bd.load_pending("x/CNN") is None      # collected, so no longer pending


def test_resume_pending_returns_none_and_keeps_the_entry_while_still_running(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    bd.record_pending("x/CNN", "snap-abc")
    assert bd.resume_pending("x/CNN",
                             poll_fn=lambda job_id: "running",
                             fetch_fn=lambda job_id: [{"id": "1"}]) is None
    assert bd.load_pending("x/CNN")["snapshot_id"] == "snap-abc"


def test_resume_pending_drops_a_failed_snapshot_and_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")
    bd.record_pending("x/CNN", "snap-dead")
    bd.drain_diagnostics()
    assert bd.resume_pending("x/CNN",
                             poll_fn=lambda job_id: "failed",
                             fetch_fn=lambda job_id: []) is None
    assert bd.load_pending("x/CNN") is None
    assert [d["kind"] for d in bd.drain_diagnostics()] == ["brightdata.resume_failed"]


def test_resume_pending_is_a_no_op_when_nothing_is_pending(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "PENDING_STORE_PATH", tmp_path / "pending.json")

    def _fail_if_called(job_id):
        raise AssertionError("the happy path must not poll anything")

    assert bd.resume_pending("x/CNN", poll_fn=_fail_if_called,
                             fetch_fn=_fail_if_called) is None


def test_config_int_prefers_an_environment_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_TEST_KNOB", "25")
    assert bd.config_int("BRIGHTDATA_TEST_KNOB", 10) == 25


def test_config_int_falls_back_to_the_default_and_reports_a_bad_override(monkeypatch):
    """A typo'd knob must not silently become a different number, and must not
    crash a run either -- it reports and uses the default."""
    monkeypatch.setenv("BRIGHTDATA_TEST_KNOB", "twenty")
    bd.drain_diagnostics()
    assert bd.config_int("BRIGHTDATA_TEST_KNOB", 10) == 10
    assert [d["kind"] for d in bd.drain_diagnostics()] == ["config.bad_override"]


def test_config_int_rejects_a_nonpositive_override(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_TEST_KNOB", "0")
    assert bd.config_int("BRIGHTDATA_TEST_KNOB", 10) == 10
