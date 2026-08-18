# doc-ingest-app/tests/test_program_sources.py
from __future__ import annotations

from doc_ingest import program_sources


def test_load_program_sources_reads_the_paths_list(tmp_path):
    yaml_path = tmp_path / "program_sources.yaml"
    yaml_path.write_text(
        "paths:\n  - \"Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md\"\n",
        encoding="utf-8",
    )
    paths = program_sources.load_program_sources(yaml_path)
    assert paths == ["Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md"]


def test_load_program_sources_returns_empty_list_when_file_missing(tmp_path):
    assert program_sources.load_program_sources(tmp_path / "does-not-exist.yaml") == []


def test_check_drift_flags_a_watched_file_not_in_the_allowlist():
    allowlist = ["Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md"]
    warning = program_sources.check_drift(
        "Offer & Coaching Framework/Current finalized documents/New Doc.gdoc.md", allowlist
    )
    assert warning is not None
    assert "New Doc.gdoc.md" in warning


def test_check_drift_is_silent_for_an_allowlisted_file():
    allowlist = ["Offer & Coaching Framework/Current finalized documents/Vision & Passion.gdoc.md"]
    assert program_sources.check_drift(allowlist[0], allowlist) is None


def test_check_drift_is_silent_outside_watched_prefixes():
    allowlist: list[str] = []
    assert program_sources.check_drift("Client Session Outlines/Sean/note.gdoc.md", allowlist) is None
