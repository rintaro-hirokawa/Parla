"""SQLite implementation of LearningItemRepository."""

import sqlite3
from collections.abc import Sequence
from datetime import date
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
                    status, created_at,
                    srs_stage, ease_factor, next_review_date, correct_context_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    item.srs_stage,
                    item.ease_factor,
                    item.next_review_date.isoformat() if item.next_review_date else None,
                    item.correct_context_count,
                ),
            )
        self._conn.commit()

    def get_stocked_items(self) -> list[LearningItem]:
        rows = self._conn.execute("SELECT * FROM learning_items WHERE status = 'auto_stocked'").fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_items_by_sentence(self, sentence_id: UUID) -> list[LearningItem]:
        rows = self._conn.execute(
            "SELECT * FROM learning_items WHERE source_sentence_id = ?",
            (str(sentence_id),),
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def update_item(self, item_id: UUID, pattern: str, explanation: str) -> None:
        self._conn.execute(
            "UPDATE learning_items SET pattern = ?, explanation = ? WHERE id = ?",
            (pattern, explanation, str(item_id)),
        )
        self._conn.commit()

    def dismiss_item(self, item_id: UUID) -> None:
        self._conn.execute(
            "UPDATE learning_items SET status = 'dismissed' WHERE id = ?",
            (str(item_id),),
        )
        self._conn.commit()

    def update_item_status(self, item_id: UUID, status: LearningItemStatus) -> None:
        self._conn.execute(
            "UPDATE learning_items SET status = ? WHERE id = ?",
            (status, str(item_id)),
        )
        self._conn.commit()

    def get_item(self, item_id: UUID) -> LearningItem | None:
        row = self._conn.execute(
            "SELECT * FROM learning_items WHERE id = ?",
            (str(item_id),),
        ).fetchone()
        return self._row_to_item(row) if row else None

    def count_due_items(self, as_of: date) -> int:
        """Count total pending review items without loading them."""
        row = self._conn.execute(
            """SELECT COUNT(*) as cnt FROM learning_items
               WHERE status = 'auto_stocked'
                 AND (next_review_date IS NULL OR next_review_date <= ?)""",
            (as_of.isoformat(),),
        ).fetchone()
        return int(row["cnt"])

    def get_due_items(self, as_of: date, limit: int = 20) -> list[LearningItem]:
        """Get auto_stocked items due for review, ordered by most overdue first."""
        rows = self._conn.execute(
            """SELECT * FROM learning_items
               WHERE status = 'auto_stocked'
                 AND (next_review_date IS NULL OR next_review_date <= ?)
               ORDER BY next_review_date ASC
               LIMIT ?""",
            (as_of.isoformat(), limit),
        ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def update_srs_state(
        self,
        item_id: UUID,
        srs_stage: int,
        ease_factor: float,
        next_review_date: date,
        correct_context_count: int,
    ) -> None:
        self._conn.execute(
            """UPDATE learning_items
               SET srs_stage = ?, ease_factor = ?, next_review_date = ?,
                   correct_context_count = ?
               WHERE id = ?""",
            (srs_stage, ease_factor, next_review_date.isoformat(), correct_context_count, str(item_id)),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> LearningItem:
        next_review = row["next_review_date"]
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
            srs_stage=row["srs_stage"],
            ease_factor=row["ease_factor"],
            next_review_date=date.fromisoformat(next_review) if next_review else None,
            correct_context_count=row["correct_context_count"],
        )
