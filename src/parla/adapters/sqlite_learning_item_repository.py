"""SQLite implementation of LearningItemRepository."""

import sqlite3
from collections.abc import Sequence
from uuid import UUID

from parla.domain.learning_item import LearningItem, LearningItemStatus


class SQLiteLearningItemRepository:
    """Persists learning items to SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_items(self, items: Sequence[LearningItem]) -> None:
        for item in items:
            self._conn.execute(
                """INSERT INTO learning_items
                   (id, pattern, explanation, category, sub_tag, priority,
                    source_sentence_id, is_reappearance, matched_item_id,
                    status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(item.id),
                    item.pattern,
                    item.explanation,
                    item.category,
                    item.sub_tag,
                    item.priority,
                    str(item.source_sentence_id),
                    int(item.is_reappearance),
                    str(item.matched_item_id) if item.matched_item_id else None,
                    item.status,
                    item.created_at.isoformat(),
                ),
            )
        self._conn.commit()

    def get_stocked_items(self) -> list[LearningItem]:
        rows = self._conn.execute(
            "SELECT * FROM learning_items WHERE status = 'auto_stocked'"
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_items_by_sentence(self, sentence_id: UUID) -> list[LearningItem]:
        rows = self._conn.execute(
            "SELECT * FROM learning_items WHERE source_sentence_id = ?",
            (str(sentence_id),),
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def update_item_status(self, item_id: UUID, status: LearningItemStatus) -> None:
        self._conn.execute(
            "UPDATE learning_items SET status = ? WHERE id = ?",
            (status, str(item_id)),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> LearningItem:
        return LearningItem(
            id=UUID(row["id"]),
            pattern=row["pattern"],
            explanation=row["explanation"],
            category=row["category"],
            sub_tag=row["sub_tag"],
            priority=row["priority"],
            source_sentence_id=UUID(row["source_sentence_id"]),
            is_reappearance=bool(row["is_reappearance"]),
            matched_item_id=UUID(row["matched_item_id"]) if row["matched_item_id"] else None,
            status=row["status"],
            created_at=row["created_at"],
        )
