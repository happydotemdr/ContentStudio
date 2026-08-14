"""Config module tests: defaults, YAML override, env var precedence, immutability."""
from __future__ import annotations

from pathlib import Path

import pytest

from doc_ingest.config import Config, load_config


def test_defaults_are_populated_without_a_config_file(tmp_path):
    cfg = load_config(tmp_path / "nonexistent.yaml")
    assert cfg.worker_pool_size == 4
    assert cfg.reclaim_staleness_threshold_s == 180
    assert cfg.oversized_file_cap_bytes == 52428800


def test_yaml_file_overrides_defaults(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("worker_pool_size: 8\njob_timeout_s: 120\n", encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.worker_pool_size == 8
    assert cfg.job_timeout_s == 120
    assert cfg.reclaim_staleness_threshold_s == 180  # untouched field keeps default


def test_env_var_overrides_yaml(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("worker_pool_size: 8\n", encoding="utf-8")
    monkeypatch.setenv("DOC_INGEST_WORKER_POOL_SIZE", "2")
    cfg = load_config(cfg_path)
    assert cfg.worker_pool_size == 2


def test_config_is_frozen():
    cfg = load_config(Path("nonexistent.yaml"))
    with pytest.raises(Exception):
        cfg.worker_pool_size = 99


def test_unknown_yaml_key_raises_error(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("worker_pol_size: 8\n", encoding="utf-8")  # typo: 'pol' instead of 'pool'
    with pytest.raises(ValueError, match="Unknown config key"):
        load_config(cfg_path)


def test_numeric_type_coercion_from_yaml(tmp_path):
    # Float value for an int field should be coerced to int
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("worker_pool_size: 8.5\n", encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.worker_pool_size == 8
    assert isinstance(cfg.worker_pool_size, int)


def test_numeric_type_coercion_from_env(monkeypatch):
    # Float string in env for an int field should be coerced to int
    monkeypatch.setenv("DOC_INGEST_WORKER_POOL_SIZE", "8.5")
    cfg = load_config(Path("nonexistent.yaml"))
    assert cfg.worker_pool_size == 8
    assert isinstance(cfg.worker_pool_size, int)


def test_int_to_float_coercion_from_yaml(tmp_path):
    # Int value for a float field should be coerced to float
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("word_count_tolerance_pct: 20\n", encoding="utf-8")
    cfg = load_config(cfg_path)
    assert cfg.word_count_tolerance_pct == 20.0
    assert isinstance(cfg.word_count_tolerance_pct, float)
