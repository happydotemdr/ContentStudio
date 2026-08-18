from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import backfill_client_tags  # noqa: E402


def _seed_conversion(conn, cfg, rel_path: str, output_path: str, body_with_fm: str, current_client=None):
    final_path = cfg.converted_root / output_path
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(body_with_fm, encoding="utf-8")
    conn.execute(
        "INSERT INTO source_files (rel_path, extension, classification, size_bytes, mtime, "
        "content_hash, first_seen_at, last_seen_at) VALUES (?, 'gdoc', 'gdoc_pointer', 10, 'm', 'h', 'n', 'n')",
        (rel_path,),
    )
    source_file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO conversions (source_file_id, version_number, output_path, status, source_type, "
        "conversion_tool, converted_at, gauntlet_passed_at, client) "
        "VALUES (?, 1, ?, 'current', 'gdoc', 'google-docs-export', 'n', 'n', ?)",
        (source_file_id, output_path, current_client),
    )
    conn.commit()


def test_build_report_classifies_a_session_outlines_file(conn, tmp_path):
    from doc_ingest import clients_db
    from doc_ingest.config import Config
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean@example.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder1",
    )
    cfg = Config(output_root=tmp_path / "output")
    _seed_conversion(
        conn, cfg, "Client Session Outlines/Sean/note.gdoc",
        "Client Session Outlines/Sean/note.gdoc.md",
        "---\nversion: 1\n---\n\nsome content",
    )
    report = backfill_client_tags.build_report(conn, cfg, lambda: None)
    assert len(report) == 1
    assert report[0]["classified_client"] == "sean"
    assert report[0]["current_client"] is None


def test_build_report_skips_non_client_files(conn, tmp_path):
    from doc_ingest.config import Config
    cfg = Config(output_root=tmp_path / "output")
    _seed_conversion(
        conn, cfg, "Offer & Coaching Framework/Current finalized documents/Vision.gdoc",
        "Offer & Coaching Framework/Current finalized documents/Vision.gdoc.md",
        "---\nversion: 1\n---\n\nvision content",
    )
    report = backfill_client_tags.build_report(conn, cfg, lambda: None)
    assert report == []


def test_apply_report_updates_only_changed_rows(conn, tmp_path):
    from doc_ingest import clients_db
    from doc_ingest.config import Config
    clients_db.register_client(
        conn, slug="sean", display_name="Sean", primary_email="sean@example.com",
        session_outlines_dir="Client Session Outlines/Sean", drive_folder_id="folder1",
    )
    cfg = Config(output_root=tmp_path / "output")
    _seed_conversion(
        conn, cfg, "Client Session Outlines/Sean/note.gdoc",
        "Client Session Outlines/Sean/note.gdoc.md", "---\nversion: 1\n---\n\ncontent",
        current_client=None,
    )
    conversion_id = conn.execute("SELECT id FROM conversions").fetchone()[0]

    report = backfill_client_tags.build_report(conn, cfg, lambda: None)
    updated = backfill_client_tags.apply_report(conn, report)
    assert updated == 1

    row = conn.execute("SELECT client FROM conversions WHERE id = ?", (conversion_id,)).fetchone()
    assert row[0] == "sean"

    # Re-running with nothing changed applies zero updates.
    report2 = backfill_client_tags.build_report(conn, cfg, lambda: None)
    assert backfill_client_tags.apply_report(conn, report2) == 0


def test_main_accepts_the_documented_dry_run_flag(tmp_path, monkeypatch, capsys):
    """The module docstring documents `--dry-run` as the way to invoke this
    script, but argparse only defined --apply -- running the documented
    command exited with 'unrecognized arguments: --dry-run'. --dry-run is
    an explicit no-op (dry run is already the default when --apply is
    omitted), so main() just needs to accept it without raising.

    HERE is monkeypatched to an isolated scripts dir so main()'s hardcoded
    `db.init_db(HERE.parent / "doc_ingest.db")` creates a throwaway DB here
    rather than touching the real doc-ingest-app/doc_ingest.db."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(backfill_client_tags, "HERE", scripts_dir)

    rc = backfill_client_tags.main(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry run" in out
