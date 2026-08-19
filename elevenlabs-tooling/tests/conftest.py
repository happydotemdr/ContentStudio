import pytest

import elevenlabs_tooling.log as log_module


@pytest.fixture(autouse=True)
def _isolate_log_dir(tmp_path, monkeypatch):
    """Every test in this suite writes logs into its own throwaway tmp_path,
    never the real elevenlabs-tooling/logs/ directory. Autouse -- no test
    file needs to request this explicitly."""
    monkeypatch.setattr(log_module, "LOG_DIR", tmp_path / "logs")
