from pathlib import Path

import pytest

from pipeline_app import brightdata_job as bd


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


def test_fetch_results_requests_json_format(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, params=params)
        return _FakeResponse([{"id": "1"}])

    monkeypatch.setattr(bd.requests, "get", fake_get)
    assert bd.fetch_results("https://api.example/v3", "job1", "the-key") == [{"id": "1"}]
    assert captured["url"] == "https://api.example/v3/snapshot/job1"
    assert captured["params"] == {"format": "json"}


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
