# ContentStudio Pipeline App

Local-only control app for the ContentStudio seven-skill pipeline (plus the RaisingGoodSports
grounding stage). Reachable only from `127.0.0.1` — never deploy this.

## Setup

    cd pipeline-app
    python -m venv .venv
    .venv\Scripts\Activate.ps1   # or: source .venv/bin/activate
    pip install -r requirements.txt
    pip install -e .

### Seed the discovery roster — required, do not skip

The `handles` table starts **empty**. Until it is seeded from `manifests/brand_sources.json`,
every discovery run has zero included handles and finishes reporting `completed` having fetched
nothing at all — a clean green run that did no work. Seed it once, from this directory:

    python tools/migrate_handles_from_manifest.py

Re-running it is safe: manifest-owned columns (`display_name`, `cohort`, `keyword_filter`,
`included`, `creator_id`) are upserted to match the manifest on every run, but it never touches
run-owned columns (`status`, `validated_at`, `last_seen_published_at`) and it never deletes a
row — a handle you added by hand through `/discovery/handles` that the manifest doesn't declare
is left alone (reported as drift, not removed), so it survives a re-seed. The manifest covers
`youtube` and `bluesky` only — Instagram, LinkedIn, Facebook and X handles have no declarative
source and must be added through the UI (finding B-70).

## Run

    uvicorn pipeline_app.main:create_default_app --factory --host 127.0.0.1 --port 8420

## Test

Run from this directory. `python -m` is required, not optional — a bare `pytest` here fails
collection on six test modules that import this app's local code by a bare module name
(`tools.*` or `run_discovery_cron`), because the console-script entry point does not put the
cwd on `sys.path`.

    cd pipeline-app
    python -m pytest

`python -m pytest` is the app suite (`1960 tests`). It is **not** run by a `pytest` at the repo
root — that's a separate root suite (see `CLAUDE.md`'s Conventions section for its current
count). Both must pass before anything here is called green.
