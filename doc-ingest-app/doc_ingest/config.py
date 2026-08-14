"""All doc-ingest-app tunables in one place -- see the implementation plan's
Task 1 table for the rationale behind each default. Precedence: env var >
YAML file > default."""
from __future__ import annotations

import dataclasses
import os
import typing
from pathlib import Path

import yaml

_ENV_PREFIX = "DOC_INGEST_"


@dataclasses.dataclass(frozen=True)
class Config:
    input_root: Path = Path(r"C:\Projects\Freedom2BeU_Google_Drive\coaching")
    output_root: Path = Path(r"C:\Projects\ContentStudio\Freedom2BeU")
    worker_pool_size: int = 4
    job_timeout_s: int = 600
    reclaim_heartbeat_interval_s: int = 30
    reclaim_staleness_threshold_s: int = 180
    run_time_budget_s: int = 1500
    long_path_threshold_chars: int = 240
    oversized_file_cap_bytes: int = 52428800
    drive_export_size_cap_bytes: int = 10485760
    word_count_tolerance_pct: float = 0.15
    row_count_tolerance_pct: float = 0.05
    sheet_count_tolerance: int = 0
    size_ratio_floor: float = 0.05
    scanned_pdf_words_per_page_floor: float = 3.0
    replacement_char_ratio_max: float = 0.01
    drive_metadata_batch_size: int = 100
    drive_retry_max_attempts: int = 5
    drive_retry_base_delay_s: float = 2.0

    @property
    def converted_root(self) -> Path:
        return self.output_root / "converted"

    @property
    def tmp_root(self) -> Path:
        return self.output_root / "_tmp"


# NOTE: this module keeps `from __future__ import annotations` for consistency
# with the rest of the codebase (see pipeline_app/*.py), which means
# `dataclasses.fields(Config)[i].type` is the *string* "int"/"float"/"Path",
# not the real type object -- `f.type is int` is never true under PEP 563.
# typing.get_type_hints() is the one API that actually resolves those strings
# back to real type objects (it re-evaluates each annotation against the
# defining module's globals), so it's used here instead of a plain
# dataclasses.fields() walk.
_FIELD_TYPES = typing.get_type_hints(Config)


def _coerce(name: str, raw: str):
    field_type = _FIELD_TYPES[name]
    if field_type is int:
        return int(float(raw))
    if field_type is float:
        return float(raw)
    if field_type is Path:
        return Path(raw)
    return raw


def load_config(path: Path | None = None) -> Config:
    values: dict = {}
    if path is not None and path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key, value in raw.items():
            if key not in _FIELD_TYPES:
                raise ValueError(
                    f"Unknown config key in {path}: {key!r}; valid keys: "
                    f"{', '.join(sorted(_FIELD_TYPES.keys()))}"
                )
            values[key] = _coerce(key, str(value))

    for field_name in _FIELD_TYPES:
        env_key = _ENV_PREFIX + field_name.upper()
        if env_key in os.environ:
            values[field_name] = _coerce(field_name, os.environ[env_key])

    return Config(**values)
