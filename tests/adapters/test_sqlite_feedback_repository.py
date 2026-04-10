"""Tests for SQLiteFeedbackRepository."""

from uuid import uuid4

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_feedback_repository import SQLiteFeedbackRepository
from parla.domain.feedback import PracticeAttempt, SentenceFeedback


def _setup():
    conn = create_connection(":memory:")
    init_schema(conn)
    repo = SQLiteFeedbackRepository(conn)

    # Insert parent rows for FK constraints
    source_id = uuid4()
    conn.execute(
        """INSERT INTO sources (id, title, text, cefr_level, english_variant,
                                status, created_at, updated_at)
           VALUES (?, '', ?, 'B1', 'American', 'not_started', '', '')""",
        (str(source_id), "a" * 200),
    )
    passage_id = uuid4()
    conn.execute(
        """INSERT INTO passages (id, source_id, "order", topic, passage_type, created_at)
           VALUES (?, ?, 0, 'test', '説明型', '')""",
        (str(passage_id), str(source_id)),
    )
    sentence_id = uuid4()
    conn.execute(
        """INSERT INTO sentences (id, passage_id, "order", ja, en, hint1, hint2)
           VALUES (?, ?, 0, 'テスト', 'test', 'h1', 'h2')""",
        (str(sentence_id), str(passage_id)),
    )
    conn.commit()
    return repo, sentence_id


class TestSentenceFeedbackCRUD:
    def test_save_and_get(self) -> None:
        repo, sid = _setup()
        fb = SentenceFeedback(
            sentence_id=sid,
            user_utterance="I think this is hard.",
            model_answer="I think this is very difficult.",
            is_acceptable=True,
        )
        repo.save_feedback(fb)

        result = repo.get_feedback_by_sentence(sid)
        assert result is not None
        assert result.id == fb.id
        assert result.user_utterance == "I think this is hard."
        assert result.model_answer == "I think this is very difficult."
        assert result.is_acceptable is True

    def test_get_nonexistent_returns_none(self) -> None:
        repo, _ = _setup()
        assert repo.get_feedback_by_sentence(uuid4()) is None


class TestPracticeAttemptCRUD:
    def test_save_and_get(self) -> None:
        repo, sid = _setup()
        attempt = PracticeAttempt(
            sentence_id=sid,
            attempt_number=1,
            correct=False,
            reason="語句の欠落",
        )
        repo.save_practice_attempt(attempt)

        attempts = repo.get_attempts_by_sentence(sid)
        assert len(attempts) == 1
        assert attempts[0].attempt_number == 1
        assert attempts[0].correct is False
        assert attempts[0].reason == "語句の欠落"

    def test_multiple_attempts_ordered(self) -> None:
        repo, sid = _setup()
        for n in (1, 2, 3):
            repo.save_practice_attempt(PracticeAttempt(
                sentence_id=sid, attempt_number=n, correct=(n == 3),
            ))

        attempts = repo.get_attempts_by_sentence(sid)
        assert len(attempts) == 3
        assert [a.attempt_number for a in attempts] == [1, 2, 3]
        assert attempts[2].correct is True

    def test_get_empty_returns_empty_list(self) -> None:
        repo, _ = _setup()
        assert repo.get_attempts_by_sentence(uuid4()) == []
