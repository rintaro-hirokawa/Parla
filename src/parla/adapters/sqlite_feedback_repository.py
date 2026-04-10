"""SQLite implementation of FeedbackRepository."""

import sqlite3
from uuid import UUID

from parla.domain.feedback import PracticeAttempt, SentenceFeedback


class SQLiteFeedbackRepository:
    """Persists sentence feedback and practice attempts to SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_feedback(self, feedback: SentenceFeedback) -> None:
        self._conn.execute(
            """INSERT INTO sentence_feedback
               (id, sentence_id, user_utterance, model_answer, is_acceptable, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(feedback.id),
                str(feedback.sentence_id),
                feedback.user_utterance,
                feedback.model_answer,
                int(feedback.is_acceptable),
                feedback.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_feedback_by_sentence(self, sentence_id: UUID) -> SentenceFeedback | None:
        row = self._conn.execute(
            "SELECT * FROM sentence_feedback WHERE sentence_id = ?",
            (str(sentence_id),),
        ).fetchone()
        if row is None:
            return None
        return SentenceFeedback(
            id=UUID(row["id"]),
            sentence_id=UUID(row["sentence_id"]),
            user_utterance=row["user_utterance"],
            model_answer=row["model_answer"],
            is_acceptable=bool(row["is_acceptable"]),
            created_at=row["created_at"],
        )

    def save_practice_attempt(self, attempt: PracticeAttempt) -> None:
        self._conn.execute(
            """INSERT INTO practice_attempts
               (id, sentence_id, attempt_number, correct, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(attempt.id),
                str(attempt.sentence_id),
                attempt.attempt_number,
                int(attempt.correct),
                attempt.reason,
                attempt.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get_attempts_by_sentence(self, sentence_id: UUID) -> list[PracticeAttempt]:
        rows = self._conn.execute(
            "SELECT * FROM practice_attempts WHERE sentence_id = ? ORDER BY attempt_number",
            (str(sentence_id),),
        ).fetchall()
        return [
            PracticeAttempt(
                id=UUID(r["id"]),
                sentence_id=UUID(r["sentence_id"]),
                attempt_number=r["attempt_number"],
                correct=bool(r["correct"]),
                reason=r["reason"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
