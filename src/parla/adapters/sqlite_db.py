"""SQLite database connection and schema management."""

import sqlite3
from pathlib import Path

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS sources (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL DEFAULT '',
    text            TEXT NOT NULL,
    cefr_level      TEXT NOT NULL,
    english_variant TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS passages (
    id             TEXT PRIMARY KEY,
    source_id      TEXT NOT NULL REFERENCES sources(id),
    "order"        INTEGER NOT NULL,
    topic          TEXT NOT NULL,
    passage_type   TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sentences (
    id          TEXT PRIMARY KEY,
    passage_id  TEXT NOT NULL REFERENCES passages(id),
    "order"     INTEGER NOT NULL,
    ja          TEXT NOT NULL,
    en          TEXT NOT NULL,
    hint1       TEXT NOT NULL,
    hint2       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_passages_source_id ON passages(source_id);
CREATE INDEX IF NOT EXISTS idx_sentences_passage_id ON sentences(passage_id);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);
"""


def create_connection(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript(_SCHEMA)


def reset_db(conn: sqlite3.Connection) -> None:
    """Drop all tables and recreate. For prototype-phase use only."""
    conn.executescript("""\
        DROP TABLE IF EXISTS sentences;
        DROP TABLE IF EXISTS passages;
        DROP TABLE IF EXISTS sources;
    """)
    init_schema(conn)
