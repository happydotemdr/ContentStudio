"""Regenerates a flat CSV/Markdown manifest, mirroring
output/brand-intel/youtube/_youtube-content-index.csv/.md's existing pattern
in this repo (spec §12)."""
from __future__ import annotations

import csv
from pathlib import Path

_HEADER = ["source_rel_path", "output_path", "source_type", "status", "converted_at"]


def _rows(conn) -> list[dict]:
    query = (
        "SELECT sf.rel_path, c.output_path, c.source_type, c.status, c.converted_at "
        "FROM conversions c JOIN source_files sf ON sf.id = c.source_file_id "
        "ORDER BY sf.rel_path, c.version_number"
    )
    return [dict(zip(_HEADER, row)) for row in conn.execute(query).fetchall()]


def regenerate(conn, output_root: Path) -> tuple[Path, Path]:
    rows = _rows(conn)
    csv_path = output_root / "_freedom2beu-content-index.csv"
    md_path = output_root / "_freedom2beu-content-index.md"
    output_root.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    lines = ["# Freedom2BeU Document Index\n", f"\n- **Conversions indexed:** {len(rows)}\n\n"]
    lines.append("| Source | Output | Type | Status | Converted |\n")
    lines.append("|---|---|---|---|---|\n")
    for row in rows:
        lines.append(
            f"| {row['source_rel_path']} | {row['output_path']} | {row['source_type']} | "
            f"{row['status']} | {row['converted_at']} |\n"
        )
    md_path.write_text("".join(lines), encoding="utf-8")

    return csv_path, md_path
