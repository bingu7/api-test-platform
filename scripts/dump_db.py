"""Dump all rows from the backend SQLite database (read-only, for learning/debug).

Usage:
    python scripts/dump_db.py             # dump all tables
    python scripts/dump_db.py users       # dump one table
    python scripts/dump_db.py users orders # dump several tables

This is also a minimal teaching example of:
  - how to open a SQLite file with the stdlib `sqlite3` module
  - how row_factory=sqlite3.Row lets you access columns by name
  - the same technique used by utils/db_helper.py for white-box assertions
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import sqlite3

# Resolve the db path the same way db_helper.py does (BACKEND_DB_PATH override included),
# so this works from any cwd.
DB_PATH = Path(os.getenv(
    "BACKEND_DB_PATH",
    Path(__file__).resolve().parent.parent / "apps" / "backend" / "dev.db",
))


def dump(conn: sqlite3.Connection, table: str) -> None:
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
    print(f"=== {table} ({len(rows)} rows) ===")
    if not rows:
        print("  (empty)")
        return
    for r in rows:
        # Don't dump full password hashes to the screen; keep learning-friendly.
        if "hashed_password" in r:
            r["hashed_password"] = r["hashed_password"][:20] + "...(hashed)"
        print(r)
    print()


def main() -> int:
    if not DB_PATH.exists():
        print(f"db not found: {DB_PATH}")
        print("did you start the backend? run: scripts\\start_backend.bat")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # columns accessible by name, like a dict

    requested = sys.argv[1:] or ["users", "products", "orders", "payments"]
    for table in requested:
        dump(conn, table)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
