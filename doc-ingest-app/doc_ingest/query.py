"""CLI query over the FTS5 index -- the entirety of "ease of future use" for
this phase (spec §12). No UI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def search(conn, text: str | None, source_type: str | None, status: str, limit: int) -> list[dict]:
    clauses = []
    params: list = []

    if text:
        base = (
            "SELECT c.output_path, c.source_type, c.status, sf.rel_path, c.converted_at, sf.classification "
            "FROM conversions_fts f JOIN conversions c ON c.id = f.conversion_id "
            "JOIN source_files sf ON sf.id = c.source_file_id "
            # NOTE: MATCH must target the FTS5 table's real name, not the
            # alias `f` -- this SQLite build (3.50.4) raises
            # "no such column: f" for `f MATCH ?` even inside this exact
            # JOIN, while `conversions_fts MATCH ?` resolves correctly.
            # Verified by direct reproduction outside this codebase before
            # changing the brief's given query text.
            "WHERE conversions_fts MATCH ?"
        )
        params.append(text)
    else:
        base = (
            "SELECT c.output_path, c.source_type, c.status, sf.rel_path, c.converted_at, sf.classification "
            "FROM conversions c JOIN source_files sf ON sf.id = c.source_file_id WHERE 1=1"
        )

    if status != "all":
        clauses.append("c.status = ?")
        params.append(status)
        # 'missing'-sourced results are excluded by default, same as
        # 'superseded' -- a search shouldn't surface content whose source no
        # longer exists without saying so (spec §9a).
        clauses.append("sf.classification != 'missing'")
    if source_type:
        clauses.append("c.source_type = ?")
        params.append(source_type)

    query_sql = base + ("".join(f" AND {c}" for c in clauses)) + " ORDER BY c.converted_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query_sql, params).fetchall()
    return [
        {
            "output_path": r[0], "source_type": r[1], "status": r[2], "source_rel_path": r[3],
            "converted_at": r[4], "source_missing": r[5] == "missing",
        }
        for r in rows
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--search")
    ap.add_argument("--type")
    ap.add_argument("--status", default="current", choices=["current", "superseded", "all"])
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--db", default=None)
    args = ap.parse_args(argv)

    from doc_ingest import db as db_mod
    db_path = Path(args.db) if args.db else Path(__file__).resolve().parents[1] / "doc_ingest.db"
    conn = db_mod.get_connection(db_path)
    results = search(conn, args.search, args.type, args.status, args.limit)
    conn.close()
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
