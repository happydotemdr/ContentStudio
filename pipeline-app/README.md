# ContentStudio Pipeline App

Local-only control app for the ContentStudio six-skill pipeline (plus the RaisingGoodSports
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

    python -m pytest
