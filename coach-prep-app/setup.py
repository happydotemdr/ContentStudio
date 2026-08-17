"""Distribution metadata for coach-prep-app. Mirrors doc-ingest-app's
setup.py: install_requires parsed from requirements.txt so the manifests
cannot drift."""
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
    name="coach-prep-app",
    version="0.1.0",
    packages=find_packages(include=["coach_prep_app", "coach_prep_app.*"]),
    install_requires=_runtime_requirements(),
    python_requires=">=3.14",
)
