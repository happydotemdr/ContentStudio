"""One-time-per-client registration CLI.

Usage:
  python scripts/register_client.py add --slug sean --display-name "Sean" \
      --email sean.carl.tinsley@gmail.com \
      --session-outlines-dir "Client Session Outlines/Sean" \
      --drive-folder-id <id> [--alias-email other@example.com ...]
  python scripts/register_client.py list
  python scripts/register_client.py deactivate --slug sean
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from doc_ingest import clients_db, db


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add")
    add.add_argument("--slug", required=True)
    add.add_argument("--display-name", required=True)
    add.add_argument("--email", required=True)
    add.add_argument("--session-outlines-dir", required=True)
    add.add_argument("--drive-folder-id", required=True)
    add.add_argument("--alias-email", action="append", default=[])

    sub.add_parser("list")

    deact = sub.add_parser("deactivate")
    deact.add_argument("--slug", required=True)

    return ap


def main(argv: list[str] | None = None, db_path: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    resolved_db_path = db_path or (HERE.parent / "doc_ingest.db")
    conn = db.init_db(resolved_db_path)
    try:
        if args.command == "add":
            clients_db.register_client(
                conn, slug=args.slug, display_name=args.display_name,
                primary_email=args.email, session_outlines_dir=args.session_outlines_dir,
                drive_folder_id=args.drive_folder_id, alias_emails=args.alias_email,
            )
            print(f"registered client {args.slug!r}")
        elif args.command == "list":
            for c in clients_db.get_active_clients(conn):
                print(f"{c['slug']}: {c['display_name']} <{c['primary_email']}> -> {c['session_outlines_dir']}")
        elif args.command == "deactivate":
            ok = clients_db.deactivate_client(conn, args.slug)
            print("deactivated" if ok else f"no active client {args.slug!r} found")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
