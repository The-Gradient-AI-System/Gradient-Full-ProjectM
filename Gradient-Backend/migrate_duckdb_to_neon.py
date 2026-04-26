import os
import duckdb
import psycopg

DUCKDB_PATH = "db/database.duckdb"
DATABASE_URL = os.environ["DATABASE_URL"]

TABLES = [
    "users",
    "processed_emails",
    "gmail_messages",
    "lead_status_history",
    "app_settings",
]

src = duckdb.connect(DUCKDB_PATH)
with psycopg.connect(DATABASE_URL) as pg:
    with pg.cursor() as cur:
        for table in TABLES:
            rows = src.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                print(f"{table}: 0 rows")
                continue

            cols = [c[0] for c in src.execute(f"DESCRIBE {table}").fetchall()]
            placeholders = ", ".join(["%s"] * len(cols))
            col_list = ", ".join(cols)

            cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE;')
            cur.executemany(
                f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})',
                rows,
            )
            print(f"{table}: {len(rows)} rows")

    pg.commit()

print("Done")