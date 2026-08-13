"""Distribution metadata for doc-ingest-app.

install_requires is parsed from requirements.txt so the two manifests cannot
drift, mirroring pipeline-app/setup.py's rationale. This app is standalone --
no dependency on pipeline_app, no shared install."""
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
    name="doc-ingest-app",
    version="0.1.0",
    packages=find_packages(include=["doc_ingest", "doc_ingest.*"]),
    install_requires=_runtime_requirements(),
    python_requires=">=3.14",
)
