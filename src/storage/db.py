"""Database connection and initialization utilities."""

import os
import sqlite3
from typing import Generator

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "marketing.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "schema.sql")


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Return SQLite rows as dictionaries."""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


def get_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open and return a SQLite connection with foreign keys and dict factory enabled."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = dict_factory
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH, schema_path: str = SCHEMA_PATH) -> None:
    """Execute the schema script to ensure all tables exist."""
    conn = sqlite3.connect(db_path)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
