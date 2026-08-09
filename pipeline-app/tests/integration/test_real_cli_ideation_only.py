"""ONE stage, against the real Claude CLI. Not end-to-end -- the nine-stage
walk is test_stubbed_cli_e2e.py. Renamed from test_real_cli_e2e.py because the
old name claimed coverage it did not have (finding F-72).

Still opt-in: it costs real subscription usage.
"""
import os
from pathlib import Path

import pytest

from pipeline_app import artifacts, db, turn_service
from pipeline_app.pipeline_config import StageDef
from pipeline_app.project_service import create_project

pytestmark = pytest.mark.skipif(
    os.environ.get("PIPELINE_APP_RUN_INTEGRATION") != "1",
    reason="Costs real Claude Code subscription usage — set PIPELINE_APP_RUN_INTEGRATION=1 to run.",
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = REPO_ROOT / "pipeline-app" / "stage_templates"

STAGES = [StageDef(id="ideation", skill="shorts-ideation", dir_prefix="01", depends_on=[])]


@pytest.mark.asyncio
async def test_real_ideation_turn_produces_an_artifact(tmp_path: Path):
    db_path = tmp_path / "pipeline.db"
    schema_path = REPO_ROOT / "pipeline-app" / "pipeline_app" / "schema.sql"
    db.init_db(db_path, schema_path)
    conn = db.get_connection(db_path)

    # repo_root=tmp_path, not REPO_ROOT: this used to create
    # <repo>/runs/integration-test-topic-<timestamp>/ in the working tree and
    # never clean it up (finding F-72).
    result = create_project(conn, tmp_path, "integration-test-topic", "generic", STAGES)

    async for _ in turn_service.run_stage_turn(
        conn, REPO_ROOT, result["run_dir"], TEMPLATES_DIR,
        result["project_id"], result["run_id"], STAGES[0], STAGES,
        "a Short about why beginner runners overtrain",
    ):
        pass

    stage_dir = result["run_dir"] / "01-ideation"
    latest = artifacts.latest_artifact_path(stage_dir)
    assert latest is not None
    body = latest.read_text(encoding="utf-8")
    assert len(body.strip()) > 200, "the CLI produced an artifact with no substance"
    assert not (REPO_ROOT / "runs").exists() or not any(
        p.name.startswith("integration-test-topic") for p in (REPO_ROOT / "runs").iterdir()
    ), "the test wrote into the real working tree"
    conn.close()
