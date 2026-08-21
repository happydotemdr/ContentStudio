"""All coach-prep-app tunables in one place. Precedence: env var > YAML file
> default -- mirrors doc_ingest/config.py's pattern exactly."""
from __future__ import annotations

import dataclasses
import os
import sys
import typing
from pathlib import Path

import yaml

_ENV_PREFIX = "COACH_PREP_"

# coach-prep-app's own directory, wherever it actually lives on disk right
# now -- this worktree during development, the main checkout after merge.
# Defaults below are computed relative to this rather than hardcoded as an
# absolute path, so cross-app imports and doc_ingest.db/converted_root
# lookups resolve correctly in BOTH locations with no override needed. A
# hardcoded main-checkout path here would silently point every test at the
# wrong checkout until this branch merges.
_APP_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _APP_ROOT.parent


@dataclasses.dataclass(frozen=True)
class Config:
    doc_ingest_app_root: Path = dataclasses.field(default_factory=lambda: _REPO_ROOT / "doc-ingest-app")
    doc_ingest_db_path: Path = dataclasses.field(
        default_factory=lambda: _REPO_ROOT / "doc-ingest-app" / "doc_ingest.db"
    )
    converted_root: Path = dataclasses.field(default_factory=lambda: _REPO_ROOT / "Freedom2BeU" / "converted")
    program_sources_path: Path = dataclasses.field(
        default_factory=lambda: _REPO_ROOT / "doc-ingest-app" / "program_sources.yaml"
    )
    coach_email: str = "admin@freedom2beu.com"
    pending_review_drive_folder_id: str = ""
    notify_recipient: str = "brian@happydotemdr.com"
    lookahead_hours: int = 48
    daily_ready_hour_local: int = 7
    timezone_name: str = "America/Chicago"
    last_meeting_email_staleness_days: int = 30
    generation_timeout_s: int = 180
    # How much client history the bundle carries. Two weeks of sent email
    # covers the post-call email plus any mid-week nudge; two meeting notes
    # give the prep doc's summary a trajectory rather than a snapshot. The
    # email cap keeps a chatty fortnight from pushing the framework material
    # out of the drafting prompt.
    framework_catalog_path: Path = dataclasses.field(
        default_factory=lambda: _APP_ROOT / "framework_catalog.yaml"
    )
    email_window_days: int = 14
    max_recent_emails: int = 5
    meeting_notes_count: int = 2


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


def ensure_doc_ingest_importable(doc_ingest_app_root: Path) -> None:
    """Idempotent sys.path insert so `from doc_ingest import ...` resolves --
    coach-prep-app has an explicit one-way dependency on doc-ingest-app's
    pure/shared modules (client_matching, eid, program_sources, frontmatter),
    the reverse of doc-ingest-app's own standalone packaging."""
    entry = str(doc_ingest_app_root)
    if entry not in sys.path:
        sys.path.insert(0, entry)
