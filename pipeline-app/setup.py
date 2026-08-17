"""Distribution metadata for the pipeline control app.

install_requires is parsed from requirements.txt rather than duplicated, so the
two manifests cannot drift (finding F-75). Test-only dependencies live in
requirements-dev.txt and are deliberately absent here.

RESOLVED (finding F-64): `pipeline-app/scripts/` -- which sat outside this
distribution and was importable only because `python -m pytest` prepends the
cwd -- has been renamed to `pipeline-app/tools/`, the ACCEPTED target.
`pipeline_app/scripts/` was considered and REJECTED. `pipeline-app/tools/`
keeps the same directory depth as the old `pipeline-app/scripts/`, so
`setup_discovery_task.py`'s `pipeline_app_root()` (how it locates
`pipeline-app/` to register the Windows scheduled task) still resolves
correctly after the move. Moving into `pipeline_app/` instead would have
added a directory level -- `parents[1]` would then resolve one directory
short, and the scheduled task would end up registered against a path that
does not exist: it registers cleanly and then fails on every run, forever,
with nothing reported anywhere. That silent, permanent failure is exactly
what the accepted target avoids.

Its four modules were owned by other remediation packages (P8:
setup_discovery_task.py; P10: migrate_handles_from_manifest.py,
backfill_youtube_frontmatter.py, tag_handle_brands_2026_08.py), so the
rename was not P0's to make -- P8 landed it, in one atomic commit covering
the directory move, the scheduled-task registration path, and the
`scripts.*` -> `tools.*` test imports, per
tests/test_harness_contract.py::test_the_f64_scripts_rename_has_landed_completely,
which fails if `pipeline-app/scripts/` still exists or `pipeline-app/tools/`
is missing. The two-suite, two-rootdir rule in CLAUDE.md no longer applies
to this collision -- collecting `tests/` from the repo root no longer
shadows `pipeline-app/tools/` with the repo root's own `scripts/` package.
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
