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

CREATE TABLE IF NOT EXISTS learning_items (
    id                    TEXT PRIMARY KEY,
    pattern               TEXT NOT NULL,
    explanation           TEXT NOT NULL,
    category              TEXT NOT NULL,
    sub_tag               TEXT NOT NULL DEFAULT '',
    priority              INTEGER NOT NULL,
    source_sentence_id    TEXT NOT NULL REFERENCES sentences(id),
    is_reappearance       INTEGER NOT NULL DEFAULT 0,
    matched_item_id       TEXT,
    status                TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    srs_stage             INTEGER NOT NULL DEFAULT 0,
    ease_factor           REAL NOT NULL DEFAULT 1.0,
    next_review_date      TEXT,
    correct_context_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sentence_feedback (
    id              TEXT PRIMARY KEY,
    sentence_id     TEXT NOT NULL REFERENCES sentences(id),
    user_utterance  TEXT NOT NULL,
    model_answer    TEXT NOT NULL,
    is_acceptable   INTEGER NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS practice_attempts (
    id              TEXT PRIMARY KEY,
    sentence_id     TEXT NOT NULL REFERENCES sentences(id),
    attempt_number  INTEGER NOT NULL,
    correct         INTEGER NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS variations (
    id                TEXT PRIMARY KEY,
    learning_item_id  TEXT NOT NULL REFERENCES learning_items(id),
    source_id         TEXT NOT NULL REFERENCES sources(id),
    ja                TEXT NOT NULL,
    en                TEXT NOT NULL,
    hint1             TEXT NOT NULL,
    hint2             TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_attempts (
    id                TEXT PRIMARY KEY,
    variation_id      TEXT NOT NULL REFERENCES variations(id),
    learning_item_id  TEXT NOT NULL REFERENCES learning_items(id),
    attempt_number    INTEGER NOT NULL,
    correct           INTEGER NOT NULL,
    item_used         INTEGER NOT NULL,
    hint_level        INTEGER NOT NULL DEFAULT 0,
    timer_ratio       REAL NOT NULL DEFAULT 0.0,
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_items_status ON learning_items(status);
CREATE INDEX IF NOT EXISTS idx_learning_items_sentence ON learning_items(source_sentence_id);
CREATE INDEX IF NOT EXISTS idx_learning_items_review ON learning_items(next_review_date);
CREATE INDEX IF NOT EXISTS idx_sentence_feedback_sentence ON sentence_feedback(sentence_id);
CREATE INDEX IF NOT EXISTS idx_practice_attempts_sentence ON practice_attempts(sentence_id);
CREATE INDEX IF NOT EXISTS idx_variations_item ON variations(learning_item_id);
CREATE INDEX IF NOT EXISTS idx_review_attempts_variation ON review_attempts(variation_id);

CREATE TABLE IF NOT EXISTS model_audio (
    passage_id    TEXT PRIMARY KEY REFERENCES passages(id),
    audio_path    TEXT NOT NULL,
    timestamps    TEXT NOT NULL,
    generated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS overlapping_results (
    id                  TEXT PRIMARY KEY,
    passage_id          TEXT NOT NULL REFERENCES passages(id),
    words               TEXT NOT NULL,
    timing_deviations   TEXT NOT NULL,
    accuracy_score      REAL NOT NULL,
    fluency_score       REAL NOT NULL,
    prosody_score       REAL NOT NULL,
    pronunciation_score REAL NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS live_delivery_results (
    id                  TEXT PRIMARY KEY,
    passage_id          TEXT NOT NULL REFERENCES passages(id),
    passed              INTEGER NOT NULL,
    sentence_statuses   TEXT NOT NULL,
    duration_seconds    REAL NOT NULL,
    wpm                 REAL NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS passage_achievements (
    passage_id    TEXT PRIMARY KEY REFERENCES passages(id),
    achieved_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_overlapping_passage ON overlapping_results(passage_id);
CREATE INDEX IF NOT EXISTS idx_live_delivery_passage ON live_delivery_results(passage_id);
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
        DROP TABLE IF EXISTS passage_achievements;
        DROP TABLE IF EXISTS live_delivery_results;
        DROP TABLE IF EXISTS overlapping_results;
        DROP TABLE IF EXISTS model_audio;
        DROP TABLE IF EXISTS review_attempts;
        DROP TABLE IF EXISTS variations;
        DROP TABLE IF EXISTS practice_attempts;
        DROP TABLE IF EXISTS sentence_feedback;
        DROP TABLE IF EXISTS learning_items;
        DROP TABLE IF EXISTS sentences;
        DROP TABLE IF EXISTS passages;
        DROP TABLE IF EXISTS sources;
    """)
    init_schema(conn)
