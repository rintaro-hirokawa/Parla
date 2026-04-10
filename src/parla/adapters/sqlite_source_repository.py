"""SQLite implementation of SourceRepository."""

import sqlite3
from collections.abc import Sequence
from uuid import UUID

from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.source import Source


class SQLiteSourceRepository:
    """Persists sources and passages to SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_source(self, source: Source) -> None:
        self._conn.execute(
            """INSERT INTO sources (id, title, text, cefr_level, english_variant,
                                    status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(source.id),
                source.title,
                source.text,
                source.cefr_level,
                source.english_variant,
                source.status,
                source.created_at.isoformat(),
                source.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_source(self, source_id: UUID) -> Source | None:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE id = ?", (str(source_id),)
        ).fetchone()
        if row is None:
            return None
        return Source(
            id=UUID(row["id"]),
            title=row["title"],
            text=row["text"],
            cefr_level=row["cefr_level"],
            english_variant=row["english_variant"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update_source(self, source: Source) -> None:
        self._conn.execute(
            """UPDATE sources
               SET title = ?, text = ?, cefr_level = ?, english_variant = ?,
                   status = ?, updated_at = ?
               WHERE id = ?""",
            (
                source.title,
                source.text,
                source.cefr_level,
                source.english_variant,
                source.status,
                source.updated_at.isoformat(),
                str(source.id),
            ),
        )
        self._conn.commit()

    def save_passages(self, passages: Sequence[Passage]) -> None:
        for passage in passages:
            self._conn.execute(
                """INSERT INTO passages (id, source_id, "order", topic, passage_type, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(passage.id),
                    str(passage.source_id),
                    passage.order,
                    passage.topic,
                    passage.passage_type,
                    "",
                ),
            )
            for sentence in passage.sentences:
                self._conn.execute(
                    """INSERT INTO sentences (id, passage_id, "order", ja, en, hint1, hint2)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(sentence.id),
                        str(passage.id),
                        sentence.order,
                        sentence.ja,
                        sentence.en,
                        sentence.hints.hint1,
                        sentence.hints.hint2,
                    ),
                )
        self._conn.commit()

    def get_passages_by_source(self, source_id: UUID) -> list[Passage]:
        passage_rows = self._conn.execute(
            'SELECT * FROM passages WHERE source_id = ? ORDER BY "order"',
            (str(source_id),),
        ).fetchall()

        passages: list[Passage] = []
        for p_row in passage_rows:
            sentence_rows = self._conn.execute(
                'SELECT * FROM sentences WHERE passage_id = ? ORDER BY "order"',
                (p_row["id"],),
            ).fetchall()

            sentences = tuple(
                Sentence(
                    id=UUID(s["id"]),
                    order=s["order"],
                    ja=s["ja"],
                    en=s["en"],
                    hints=Hint(hint1=s["hint1"], hint2=s["hint2"]),
                )
                for s in sentence_rows
            )

            passages.append(
                Passage(
                    id=UUID(p_row["id"]),
                    source_id=UUID(p_row["source_id"]),
                    order=p_row["order"],
                    topic=p_row["topic"],
                    passage_type=p_row["passage_type"],
                    sentences=sentences,
                )
            )

        return passages
