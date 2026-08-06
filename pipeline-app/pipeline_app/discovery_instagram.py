"""Instagram platform adapter for the discovery engine, backed by Bright
Data's Instagram Posts Scraper API. Isolates the Bright Data HTTP calls so
discovery_engine's core algorithm can be unit-tested with no network access,
the same isolation discovery_bluesky.py and discovery_youtube.py use.

Bright Data's API is asynchronous (trigger -> poll -> fetch) and bills per
record, unlike YouTube's Data API or Bluesky's AppView which answer
synchronously. See docs/superpowers/specs/2026-08-06-instagram-brightdata-
adapter-design.md for the full design, including why enumerate_newest_first
runs the whole job cycle once per handle per run and caches results for
download_item to read from -- calling Bright Data once per item would
double-pay for the same posts.
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
import time
from pathlib import Path

import requests

from pipeline_app import artifacts
from pipeline_app.discovery_paths import handle_dir

BRIGHTDATA_API_BASE = "https://api.brightdata.com/datasets/v3"

# Key lookup order: env var first (works for the scheduled task, which
# inherits the User environment), then a gitignored file for convenience --
# same pattern as discovery_youtube_api.api_key() / discovery_notify.api_key().
KEY_ENV_VAR = "BRIGHTDATA_API_KEY"
KEY_FILE = Path(__file__).resolve().parent.parent / "brightdata_api_key.txt"

# Bright Data dataset id for the Instagram Posts Scraper API product. Not a
# secret -- a one-time value from the Bright Data dashboard when the product
# is provisioned. Placeholder until that provisioning step happens; replace
# before the first real run.
DATASET_ID = "gd_REPLACE_WITH_REAL_DATASET_ID"

REQUEST_TIMEOUT_S = 30


def api_key() -> str | None:
    """The Bright Data API token, or None if not configured."""
    env_key = os.environ.get(KEY_ENV_VAR, "").strip()
    if env_key:
        return env_key
    if KEY_FILE.exists():
        file_key = KEY_FILE.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key
    return None
