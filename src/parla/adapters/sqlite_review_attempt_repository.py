"""SQLite implementation of ReviewAttemptRepository."""

import sqlite3
from datetime import datetime
from uuid import UUID

from parla.domain.review import ReviewAttempt


class SQLiteReviewAttemptRepository:
    """Persists Block 1/3 review attempts to SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_attempt(self, attempt: ReviewAttempt) -> None:
        self._conn.execute(
            """INSERT INTO review_attempts
               (id, variation_id, learning_item_id, attempt_number,
                correct, item_used, hint_level, timer_ratio, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(attempt.id),
                str(attempt.variation_id),
                str(attempt.learning_item_id),
                attempt.attempt_number,
                int(attempt.correct),
                int(attempt.item_used),
                attempt.hint_level,
                attempt.timer_ratio,
                attempt.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_attempts_by_variation(self, variation_id: UUID) -> list[ReviewAttempt]:
        rows = self._conn.execute(
            "SELECT * FROM review_attempts WHERE variation_id = ? ORDER BY attempt_number",
            (str(variation_id),),
        ).fetchall()
        return [self._row_to_attempt(r) for r in rows]

    @staticmethod
    def _row_to_attempt(row: sqlite3.Row) -> ReviewAttempt:
        return ReviewAttempt(
            id=UUID(row["id"]),
            variation_id=UUID(row["variation_id"]),
            learning_item_id=UUID(row["learning_item_id"]),
            attempt_number=row["attempt_number"],
            correct=bool(row["correct"]),
            item_used=bool(row["item_used"]),
            hint_level=row["hint_level"],
            timer_ratio=row["timer_ratio"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
