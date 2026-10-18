"""
Database configuration and connection management.
Provides a context-managed connection factory and schema initialization.
"""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("SHOP_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "shop_manager.db"))


def _ensure_data_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Create a new database connection with row factory and pragmas."""
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    """Context manager that yields a DB connection and auto-closes."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else None


def rows_to_list(rows):
    """Convert a list of sqlite3.Row to a list of dicts."""
    return [dict(r) for r in rows]
