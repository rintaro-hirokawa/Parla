"""SQLite implementation of VariationRepository."""

import sqlite3
from datetime import datetime
from uuid import UUID

from parla.domain.variation import Variation


class SQLiteVariationRepository:
    """Persists variations (practice questions) to SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_variation(self, variation: Variation) -> None:
        self._conn.execute(
            """INSERT INTO variations
               (id, learning_item_id, source_id, ja, en, hint1, hint2, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(variation.id),
                str(variation.learning_item_id),
                str(variation.source_id),
                variation.ja,
                variation.en,
                variation.hint1,
                variation.hint2,
                variation.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_variation(self, variation_id: UUID) -> Variation | None:
        row = self._conn.execute(
            "SELECT * FROM variations WHERE id = ?",
            (str(variation_id),),
        ).fetchone()
        return self._row_to_variation(row) if row else None

    def get_variations_by_item(self, item_id: UUID) -> list[Variation]:
        rows = self._conn.execute(
            "SELECT * FROM variations WHERE learning_item_id = ? ORDER BY created_at",
            (str(item_id),),
        ).fetchall()
        return [self._row_to_variation(r) for r in rows]

    @staticmethod
    def _row_to_variation(row: sqlite3.Row) -> Variation:
        return Variation(
            id=UUID(row["id"]),
            learning_item_id=UUID(row["learning_item_id"]),
            source_id=UUID(row["source_id"]),
            ja=row["ja"],
            en=row["en"],
            hint1=row["hint1"],
            hint2=row["hint2"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
