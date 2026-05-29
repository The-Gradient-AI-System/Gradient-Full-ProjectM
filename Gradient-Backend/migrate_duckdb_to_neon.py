"""
One-off migration: local DuckDB file → Neon PostgreSQL (DATABASE_URL).

Safe by default: upserts via ON CONFLICT, no TRUNCATE unless --truncate is passed.

Usage:
    set DATABASE_URL=postgresql://...
    python migrate_duckdb_to_neon.py
    python migrate_duckdb_to_neon.py --truncate   # destructive: clears target tables first
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb
import psycopg
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DUCKDB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "db" / "database.duckdb")))

TABLES = [
    "users",
    "processed_emails",
    "gmail_messages",
    "lead_status_history",
    "app_settings",
]

# ON CONFLICT target column(s) per table (must match PostgreSQL schema in db.py)
CONFLICT_KEYS: dict[str, list[str]] = {
    "users": ["id"],
    "processed_emails": ["gmail_id"],
    "gmail_messages": ["gmail_id"],
    "lead_status_history": ["id"],
    "app_settings": ["key"],
}


def _require_database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        print("ERROR: DATABASE_URL is not set. Aborting.", file=sys.stderr)
        sys.exit(1)
    if not url.lower().startswith(("postgres://", "postgresql://")):
        print("ERROR: DATABASE_URL must be a PostgreSQL connection string.", file=sys.stderr)
        sys.exit(1)
    return url


def _require_duckdb_file() -> Path:
    if not DUCKDB_PATH.is_file():
        print(f"ERROR: DuckDB file not found: {DUCKDB_PATH}", file=sys.stderr)
        sys.exit(1)
    return DUCKDB_PATH


def _table_columns(src: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [row[0] for row in src.execute(f"DESCRIBE {table}").fetchall()]


def _migrate_table(
    cur: psycopg.Cursor,
    src: duckdb.DuckDBPyConnection,
    table: str,
    *,
    truncate: bool,
) -> int:
    rows = src.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        print(f"{table}: 0 rows (skip)")
        return 0

    cols = _table_columns(src, table)
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    conflict_cols = CONFLICT_KEYS[table]
    conflict_clause = ", ".join(f'"{c}"' for c in conflict_cols)

    if truncate:
        cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')

    update_assignments = ", ".join(
        f'"{c}" = EXCLUDED."{c}"' for c in cols if c not in conflict_cols
    )
    if update_assignments:
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            f"ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_assignments}"
        )
    else:
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            f"ON CONFLICT ({conflict_clause}) DO NOTHING"
        )

    cur.executemany(sql, rows)
    print(f"{table}: migrated {len(rows)} rows")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate DuckDB data to Neon PostgreSQL")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE each target table before insert (destructive)",
    )
    args = parser.parse_args()

    database_url = _require_database_url()
    duckdb_path = _require_duckdb_file()

    if args.truncate:
        print("WARNING: --truncate will delete existing data in target tables.")

    print(f"Source DuckDB: {duckdb_path}")
    print("Target: PostgreSQL (DATABASE_URL set)")

    # Ensure target schema exists
    import db  # noqa: F401 — runs init_db() for PostgreSQL

    src = duckdb.connect(str(duckdb_path))
    total = 0
    try:
        with psycopg.connect(database_url) as pg:
            with pg.cursor() as cur:
                for table in TABLES:
                    try:
                        total += _migrate_table(cur, src, table, truncate=args.truncate)
                    except Exception as exc:
                        print(f"{table}: ERROR — {exc}", file=sys.stderr)
                        raise
            pg.commit()
    finally:
        src.close()

    print(f"Done. Total rows processed: {total}")


if __name__ == "__main__":
    main()
