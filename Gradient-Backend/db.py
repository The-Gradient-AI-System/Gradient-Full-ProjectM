"""
Database module.

DuckDB does NOT support concurrent use of a single connection from multiple
threads — even with a mutex the internal vector state can be corrupted when a
background thread (auto-sync) holds a cursor while another thread issues an
UPDATE.

Solution: every caller opens its own short-lived connection via get_conn().

IMPORTANT — DuckDB 1.1.0 bug:
  UPDATE fails with "Vector::Reference used on vector of different type" on any
  table that has a PRIMARY KEY or UNIQUE constraint.  All tables are therefore
  created WITHOUT those constraints; uniqueness is enforced at the application
  layer (duplicate checks before INSERT/UPDATE).

Usage:
    from db import get_conn, db_lock

    with get_conn() as conn:
        row = conn.execute("SELECT ...").fetchone()

    with db_lock:
        with get_conn() as read_conn:
            # validation reads
            ...
        with get_conn() as write_conn:
            write_conn.execute("UPDATE ...")
            write_conn.commit()

db_lock serialises multi-step check-then-write sequences across connections.
"""

import duckdb
import threading
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "database.duckdb"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Global lock for serialising multi-step transactions across connections.
db_lock = threading.RLock()


@contextmanager
def get_conn():
    """Open a fresh DuckDB connection, yield it, then close it."""
    connection = duckdb.connect(str(DB_PATH))
    try:
        yield connection
    finally:
        try:
            connection.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Singleton used ONLY by init_db().  Closed immediately after init.
# ---------------------------------------------------------------------------
conn = duckdb.connect(str(DB_PATH))


def _ensure_column(table: str, column: str, definition: str) -> None:
    exists = conn.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = ? AND column_name = ?
        """,
        [table, column],
    ).fetchone()
    if not exists:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    # NOTE: No PRIMARY KEY / UNIQUE / FOREIGN KEY constraints.
    # DuckDB 1.1.0 has a bug where UPDATE raises
    # "Vector::Reference used on vector of different type" on tables with
    # unique indexes.  Uniqueness is enforced at the application layer.
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER NOT NULL,
        username TEXT NOT NULL,
        email TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'manager',
        is_active BOOLEAN NOT NULL DEFAULT TRUE
    )
    """)

    _ensure_column("users", "is_active", "BOOLEAN DEFAULT TRUE")
    _ensure_column("users", "avatar_url", "TEXT")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS processed_emails (
        gmail_id TEXT,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS gmail_messages (
        gmail_id TEXT,
        status TEXT,
        first_name TEXT,
        last_name TEXT,
        full_name TEXT,
        email TEXT,
        subject TEXT,
        received_at TEXT,
        company TEXT,
        body TEXT,
        phone TEXT,
        website TEXT,
        company_name TEXT,
        company_info TEXT,
        person_role TEXT,
        person_links TEXT,
        person_location TEXT,
        person_experience TEXT,
        person_summary TEXT,
        person_insights TEXT,
        company_insights TEXT,
        is_priority BOOLEAN DEFAULT FALSE,
        pending_review BOOLEAN DEFAULT FALSE,
        preprocessing_status TEXT DEFAULT 'idle',
        preprocessed_replies TEXT,
        preprocessed_at TIMESTAMP,
        assigned_to INTEGER,
        assigned_at TIMESTAMP,
        synced_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    _ensure_column("gmail_messages", "is_priority", "BOOLEAN DEFAULT FALSE")
    _ensure_column("gmail_messages", "pending_review", "BOOLEAN DEFAULT FALSE")
    _ensure_column("gmail_messages", "preprocessing_status", "TEXT DEFAULT 'idle'")
    _ensure_column("gmail_messages", "preprocessed_replies", "TEXT")
    _ensure_column("gmail_messages", "preprocessed_at", "TIMESTAMP")
    _ensure_column("gmail_messages", "last_reply_subject", "TEXT")
    _ensure_column("gmail_messages", "last_reply_body", "TEXT")
    _ensure_column("gmail_messages", "last_replied_at", "TIMESTAMP")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS lead_status_history (
        id TEXT,
        gmail_id TEXT NOT NULL,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        lead_name TEXT,
        status TEXT NOT NULL,
        assignee TEXT,
        rejection_reason TEXT
    )
    """)

    _ensure_column("lead_status_history", "rejection_reason", "TEXT")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT,
        value TEXT NOT NULL
    )
    """)

    conn.execute(
        """
        INSERT INTO app_settings (key, value)
        SELECT * FROM (VALUES
            ('reply_top_block', ?),
            ('reply_bottom_block', ?),
            ('reply_style_official', ?),
            ('reply_style_semi_official', ?),
            ('reply_prompt_follow_up', ?),
            ('reply_prompt_recap', ?),
            ('reply_prompt_quick', ?)
        ) AS defaults(key, value)
        WHERE NOT EXISTS (
            SELECT 1 FROM app_settings WHERE app_settings.key = defaults.key
        )
        """,
        [
            "",
            "",
            "Tone: Official. Write formally, concise, confident, and business-like. Avoid slang or overly casual phrasing.",
            "Tone: Semi-official. Write friendly and professional, slightly warm, but still business appropriate.",
            "Act as a Business Development Manager. Draft a concise follow-up email after an intro call. Use only factual details provided. Keep within 140 words and write in English. The structure must cover: greeting with [NAME]; gratitude referencing [TOPIC DISCUSSED]; phrase 'As promised, I'm sharing [LINK_TO_MATERIAL]'; next steps mentioning [NEXT_CONTACT_DATE]; professional signature placeholder [YOUR_NAME].",
            "Act as a Sales Expert. Prepare a recap & proposal email after a qualification call. Use only supplied information. Keep within 140 words and write in English. The structure must cover: greeting with [CLIENT_NAME]; paragraph recognising pains [CLIENT_PAIN_POINTS]; section describing our solution [SOLUTION_OVERVIEW]; bullet list for three proofs each with [PROJECT_NAME] and [RESULT]; closing call-to-action suggesting [NEXT_STEP].",
            "Act as a Sales Assistant. Write a very short, friendly reply (max 60 words). Keep it clear, warm, and action-oriented. Use only facts from the provided context and do not invent details.",
        ],
    )

    conn.commit()


init_db()
# Close the init connection so it doesn't compete with per-request connections.
conn.close()
