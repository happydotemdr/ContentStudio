"""Distribution metadata for the pipeline control app.

install_requires is parsed from requirements.txt rather than duplicated, so the
two manifests cannot drift (finding F-75). Test-only dependencies live in
requirements-dev.txt and are deliberately absent here.

RESIDUAL (finding F-64): `scripts/` and `run_discovery_cron.py` sit outside this
distribution and are importable only because `python -m pytest` prepends the
cwd. Bringing them in requires renaming `pipeline-app/scripts/` to
`pipeline-app/tools/` -- the ACCEPTED target. `pipeline_app/scripts/` was
considered and REJECTED. `pipeline-app/tools/` keeps the same directory
depth as today's `pipeline-app/scripts/`, so `setup_discovery_task.py`'s
`Path(__file__).resolve().parents[1]` (how it locates `pipeline-app/` to
register the Windows scheduled task) still resolves correctly after the
move. Moving into `pipeline_app/` instead adds a directory level --
`parents[1]` then resolves one directory short, and the scheduled task ends
up registered against a path that does not exist: it registers cleanly and
then fails on every run, forever, with nothing reported anywhere. That
silent, permanent failure is exactly what the accepted target avoids.

Its three modules are owned by other remediation packages (P8:
setup_discovery_task.py; P10: migrate_handles_from_manifest.py,
backfill_youtube_frontmatter.py), so the rename is not P0's to make. When it
happens, the directory move, the scheduled-task registration path, and every
doc reference to `pipeline-app/scripts` are ONE ATOMIC COMMIT -- see
tests/test_harness_contract.py::test_the_f64_scripts_rename_has_not_silently_landed,
which fails the moment either side of that move lands without the other.
Until it happens the two-suite, two-rootdir rule in CLAUDE.md stands.
"""
from pathlib import Path

from setuptools import find_packages, setup

HERE = Path(__file__).resolve().parent


def _runtime_requirements() -> list[str]:
    out = []
    for raw in (HERE / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            out.append(line)
    return out


setup(
    name="pipeline-app",
    version="0.1.0",
    packages=find_packages(include=["pipeline_app", "pipeline_app.*"]),
    package_data={"pipeline_app": ["templates/*.html", "templates/partials/*.html", "static/*.css"]},
    install_requires=_runtime_requirements(),
    python_requires=">=3.14",
)
