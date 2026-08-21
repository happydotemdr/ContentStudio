# ContentStudio Pipeline App

Local-only control app for the ContentStudio seven-skill pipeline (plus the RaisingGoodSports
grounding stage). Reachable only from `127.0.0.1` — never deploy this.

## Setup

    cd pipeline-app
    python -m venv .venv
    .venv\Scripts\Activate.ps1   # or: source .venv/bin/activate
    pip install -r requirements.txt
    pip install -e .

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
root, which is scoped by `testpaths` to a separate root suite of `543 tests`. Both must pass
before anything here is called green.
