"""
Database module.

- If DATABASE_URL is set → PostgreSQL (Neon) via psycopg; short-lived connections via get_conn().
- Otherwise → local DuckDB file; short-lived connections via get_conn().

DuckDB 1.x: avoid PRIMARY KEY/UNIQUE on tables used with UPDATE (known bug).
PostgreSQL: use PK/UNIQUE on gmail_id and app_settings.key for idempotency.

Usage:
    from db import get_conn, db_lock

    with get_conn() as conn:
        row = conn.execute("SELECT ... WHERE id = ?", [id]).fetchone()
"""

from __future__ import annotations

import logging
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import duckdb
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "db" / "database.duckdb")))
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip() or None
USE_POSTGRES = bool(DATABASE_URL)

db_lock = threading.RLock()

if not USE_POSTGRES:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class _CompatResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows[0]

    def fetchall(self):
        return list(self._rows)


class _PostgresCompatConnection:
    """psycopg wrapper with DuckDB-style execute(?, params) API."""

    def __init__(self, dsn: str):
        import psycopg

        self._conn = psycopg.connect(dsn)

    @staticmethod
    def _adapt_query(query: str) -> str:
        return re.sub(r"\?", "%s", query)

    def execute(self, query: str, params=None):
        normalized = self._adapt_query(query)
        with self._conn.cursor() as cur:
            cur.execute(normalized, params or [])
            rows = cur.fetchall() if cur.description else []
        return _CompatResult(rows)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def is_postgres() -> bool:
    return USE_POSTGRES


def log_database_backend() -> None:
    if USE_POSTGRES:
        host = "unknown"
        try:
            host = urlparse(DATABASE_URL).hostname or "unknown"
        except Exception:
            pass
        logger.info("Database backend: PostgreSQL (Neon), host=%s", host)
        print(f"[db] PostgreSQL (Neon), host={host}")
    else:
        logger.info("Database backend: DuckDB, path=%s", DB_PATH)
        print(f"[db] DuckDB, path={DB_PATH}")


@contextmanager
def get_conn():
    """Open a fresh DB connection (PostgreSQL or DuckDB), then close it."""
    if USE_POSTGRES:
        connection = _PostgresCompatConnection(DATABASE_URL)
    else:
        connection = duckdb.connect(str(DB_PATH))
    try:
        yield connection
    finally:
        try:
            connection.close()
        except Exception:
            pass


def _ensure_column(conn, table: str, column: str, definition: str) -> None:
    if USE_POSTGRES:
        exists = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ? AND column_name = ?
            """,
            [table, column],
        ).fetchone()
    else:
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


def _ensure_gmail_messages_status_fields(conn) -> None:
    """Ensure status workflow columns on gmail_messages (new installs + ALTER migrations)."""
    _ensure_column(conn, "gmail_messages", "assigned_manager_id", "INTEGER")
    _ensure_column(conn, "gmail_messages", "last_action_by", "TEXT")

    conn.execute(
        "UPDATE gmail_messages SET status = 'новий' WHERE status IS NULL OR TRIM(status) = ''"
    )
    try:
        conn.execute(
            "ALTER TABLE gmail_messages ALTER COLUMN status SET DEFAULT 'новий'"
        )
    except Exception:
        logger.debug(
            "Could not set default on gmail_messages.status",
            exc_info=True,
        )


def insert_processed_email(conn, gmail_id: str) -> None:
    if USE_POSTGRES:
        conn.execute(
            "INSERT INTO processed_emails (gmail_id) VALUES (?) ON CONFLICT (gmail_id) DO NOTHING",
            [gmail_id],
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO processed_emails (gmail_id) VALUES (?)",
            [gmail_id],
        )


def upsert_app_setting(conn, key: str, value: str) -> None:
    if USE_POSTGRES:
        conn.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            [key, value],
        )
    else:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            [key, value],
        )


_APP_SETTINGS_SEED = [
    "",
    "",
    "Tone: Official. Write formally, concise, confident, and business-like. Avoid slang or overly casual phrasing.",
    "Tone: Semi-official. Write friendly and professional, slightly warm, but still business appropriate.",
    "Act as a Business Development Manager. Draft a concise follow-up email after an intro call. Use only factual details provided. Keep within 140 words and write in English. The structure must cover: greeting with [NAME]; gratitude referencing [TOPIC DISCUSSED]; phrase 'As promised, I'm sharing [LINK_TO_MATERIAL]'; next steps mentioning [NEXT_CONTACT_DATE]; professional signature placeholder [YOUR_NAME].",
    "Act as a Sales Expert. Prepare a recap & proposal email after a qualification call. Use only supplied information. Keep within 140 words and write in English. The structure must cover: greeting with [CLIENT_NAME]; paragraph recognising pains [CLIENT_PAIN_POINTS]; section describing our solution [SOLUTION_OVERVIEW]; bullet list for three proofs each with [PROJECT_NAME] and [RESULT]; closing call-to-action suggesting [NEXT_STEP].",
    "Act as a Sales Assistant. Write a very short, friendly reply (max 60 words). Keep it clear, warm, and action-oriented. Use only facts from the provided context and do not invent details.",
]


def _seed_app_settings(conn) -> None:
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
        _APP_SETTINGS_SEED,
    )


def _init_db_duckdb(conn) -> None:
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

    _ensure_column(conn, "users", "is_active", "BOOLEAN DEFAULT TRUE")
    _ensure_column(conn, "users", "avatar_url", "TEXT")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS processed_emails (
        gmail_id TEXT,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS gmail_messages (
        gmail_id TEXT,
        status TEXT DEFAULT 'новий',
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
        assigned_manager_id INTEGER,
        assigned_at TIMESTAMP,
        last_action_by TEXT,
        synced_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    _ensure_column(conn, "gmail_messages", "is_priority", "BOOLEAN DEFAULT FALSE")
    _ensure_column(conn, "gmail_messages", "pending_review", "BOOLEAN DEFAULT FALSE")
    _ensure_column(conn, "gmail_messages", "preprocessing_status", "TEXT DEFAULT 'idle'")
    _ensure_column(conn, "gmail_messages", "preprocessed_replies", "TEXT")
    _ensure_column(conn, "gmail_messages", "preprocessed_at", "TIMESTAMP")
    _ensure_column(conn, "gmail_messages", "last_reply_subject", "TEXT")
    _ensure_column(conn, "gmail_messages", "last_reply_body", "TEXT")
    _ensure_column(conn, "gmail_messages", "last_replied_at", "TIMESTAMP")
    _ensure_gmail_messages_status_fields(conn)

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

    _ensure_column(conn, "lead_status_history", "rejection_reason", "TEXT")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT,
        value TEXT NOT NULL
    )
    """)

    _seed_app_settings(conn)
    _ensure_indexes(conn)


def _ensure_indexes(conn) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gmail_messages_created_at ON gmail_messages (created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lsh_gmail_changed ON lead_status_history (gmail_id, changed_at DESC)"
    )


def _init_db_postgres(conn) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'manager',
        is_active BOOLEAN NOT NULL DEFAULT TRUE
    )
    """)

    _ensure_column(conn, "users", "is_active", "BOOLEAN DEFAULT TRUE")
    _ensure_column(conn, "users", "avatar_url", "TEXT")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS processed_emails (
        gmail_id TEXT PRIMARY KEY,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS gmail_messages (
        gmail_id TEXT PRIMARY KEY,
        status TEXT DEFAULT 'новий',
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
        assigned_manager_id INTEGER,
        assigned_at TIMESTAMP,
        last_action_by TEXT,
        synced_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    _ensure_column(conn, "gmail_messages", "is_priority", "BOOLEAN DEFAULT FALSE")
    _ensure_column(conn, "gmail_messages", "pending_review", "BOOLEAN DEFAULT FALSE")
    _ensure_column(conn, "gmail_messages", "preprocessing_status", "TEXT DEFAULT 'idle'")
    _ensure_column(conn, "gmail_messages", "preprocessed_replies", "TEXT")
    _ensure_column(conn, "gmail_messages", "preprocessed_at", "TIMESTAMP")
    _ensure_column(conn, "gmail_messages", "last_reply_subject", "TEXT")
    _ensure_column(conn, "gmail_messages", "last_reply_body", "TEXT")
    _ensure_column(conn, "gmail_messages", "last_replied_at", "TIMESTAMP")
    _ensure_gmail_messages_status_fields(conn)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS lead_status_history (
        id TEXT PRIMARY KEY,
        gmail_id TEXT NOT NULL,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        lead_name TEXT,
        status TEXT NOT NULL,
        assignee TEXT,
        rejection_reason TEXT
    )
    """)

    _ensure_column(conn, "lead_status_history", "rejection_reason", "TEXT")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    _seed_app_settings(conn)
    _ensure_indexes(conn)


def init_db() -> None:
    with get_conn() as conn:
        if USE_POSTGRES:
            _init_db_postgres(conn)
        else:
            _init_db_duckdb(conn)
        conn.commit()


init_db()
log_database_backend()
