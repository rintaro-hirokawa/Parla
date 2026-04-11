"""Tests for SQLitePracticeRepository."""

from datetime import datetime
from uuid import uuid4

import pytest

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_practice_repository import SQLitePracticeRepository
from parla.domain.audio import AudioData
from parla.domain.practice import (
    LiveDeliveryResult,
    ModelAudio,
    OverlappingResult,
    PronunciationWord,
    SentenceStatus,
    WordTimestamp,
)
from tests.conftest import make_wav_audio


def _make_audio() -> AudioData:
    return make_wav_audio()


def _insert_source_and_passage(conn, source_id, passage_id) -> None:
    """Insert minimal source + passage rows for FK constraints."""
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO sources (id, title, text, cefr_level, english_variant, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (str(source_id), "Test", "text", "B1", "american", "not_started", now, now),
    )
    conn.execute(
        'INSERT INTO passages (id, source_id, "order", topic, passage_type, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (str(passage_id), str(source_id), 1, "test", "explanation", now),
    )
    conn.commit()


@pytest.fixture
def repo(tmp_path):
    conn = create_connection()
    init_schema(conn)
    return SQLitePracticeRepository(conn, tmp_path / "audio"), conn


class TestModelAudio:
    def test_save_and_load(self, repo, tmp_path) -> None:
        practice_repo, conn = repo
        source_id, passage_id = uuid4(), uuid4()
        _insert_source_and_passage(conn, source_id, passage_id)

        model_audio = ModelAudio(
            passage_id=passage_id,
            audio=_make_audio(),
            word_timestamps=(
                WordTimestamp(word="hello", start_seconds=0.0, end_seconds=0.3),
                WordTimestamp(word="world", start_seconds=0.4, end_seconds=0.7),
            ),
        )
        practice_repo.save_model_audio(model_audio)

        loaded = practice_repo.get_model_audio(passage_id)
        assert loaded is not None
        assert loaded.passage_id == passage_id
        assert len(loaded.word_timestamps) == 2
        assert loaded.word_timestamps[0].word == "hello"
        assert loaded.audio.data == model_audio.audio.data

    def test_load_missing_returns_none(self, repo) -> None:
        practice_repo, _ = repo
        assert practice_repo.get_model_audio(uuid4()) is None

    def test_save_overwrites(self, repo) -> None:
        practice_repo, conn = repo
        source_id, passage_id = uuid4(), uuid4()
        _insert_source_and_passage(conn, source_id, passage_id)

        ma1 = ModelAudio(
            passage_id=passage_id,
            audio=_make_audio(),
            word_timestamps=(WordTimestamp(word="first", start_seconds=0.0, end_seconds=0.3),),
        )
        practice_repo.save_model_audio(ma1)

        ma2 = ModelAudio(
            passage_id=passage_id,
            audio=_make_audio(),
            word_timestamps=(WordTimestamp(word="second", start_seconds=0.0, end_seconds=0.5),),
        )
        practice_repo.save_model_audio(ma2)

        loaded = practice_repo.get_model_audio(passage_id)
        assert loaded is not None
        assert loaded.word_timestamps[0].word == "second"


class TestOverlappingResult:
    def test_save(self, repo) -> None:
        practice_repo, conn = repo
        source_id, passage_id = uuid4(), uuid4()
        _insert_source_and_passage(conn, source_id, passage_id)

        result = OverlappingResult(
            passage_id=passage_id,
            words=(
                PronunciationWord(
                    word="hello", accuracy_score=90.0, error_type="None", offset_seconds=0.1, duration_seconds=0.3
                ),
                PronunciationWord(
                    word="world",
                    accuracy_score=85.0,
                    error_type="Mispronunciation",
                    offset_seconds=0.5,
                    duration_seconds=0.3,
                ),
            ),
            timing_deviations=(0.05, 0.12),
            accuracy_score=87.5,
            fluency_score=90.0,
            prosody_score=80.0,
            pronunciation_score=85.0,
        )
        practice_repo.save_overlapping_result(result)

        # Verify it was persisted
        row = conn.execute("SELECT * FROM overlapping_results WHERE id = ?", (str(result.id),)).fetchone()
        assert row is not None
        assert row["passage_id"] == str(passage_id)


class TestLiveDeliveryResult:
    def test_save_and_load(self, repo) -> None:
        practice_repo, conn = repo
        source_id, passage_id = uuid4(), uuid4()
        _insert_source_and_passage(conn, source_id, passage_id)

        result = LiveDeliveryResult(
            passage_id=passage_id,
            passed=True,
            sentence_statuses=(
                SentenceStatus(
                    sentence_index=0,
                    recognized_text="hello world",
                    model_text="hello world",
                    similarity=1.0,
                    status="correct",
                ),
                SentenceStatus(
                    sentence_index=1,
                    recognized_text="good morning",
                    model_text="good morning",
                    similarity=0.95,
                    status="correct",
                ),
            ),
            duration_seconds=30.0,
            wpm=120.0,
        )
        practice_repo.save_live_delivery_result(result)

        results = practice_repo.get_live_delivery_results(passage_id)
        assert len(results) == 1
        loaded = results[0]
        assert loaded.passed is True
        assert loaded.wpm == pytest.approx(120.0)
        assert len(loaded.sentence_statuses) == 2
        assert loaded.sentence_statuses[0].status == "correct"

    def test_multiple_results_ordered(self, repo) -> None:
        practice_repo, conn = repo
        source_id, passage_id = uuid4(), uuid4()
        _insert_source_and_passage(conn, source_id, passage_id)

        for i, passed in enumerate([False, True]):
            result = LiveDeliveryResult(
                passage_id=passage_id,
                passed=passed,
                sentence_statuses=(),
                duration_seconds=30.0 + i,
                wpm=100.0 + i * 10,
                created_at=datetime(2026, 4, 10, 10, i),
            )
            practice_repo.save_live_delivery_result(result)

        results = practice_repo.get_live_delivery_results(passage_id)
        assert len(results) == 2
        assert results[0].passed is False
        assert results[1].passed is True


class TestPassageAchievement:
    def test_no_achievement(self, repo) -> None:
        practice_repo, _ = repo
        assert practice_repo.has_achievement(uuid4()) is False

    def test_save_achievement(self, repo) -> None:
        practice_repo, conn = repo
        source_id, passage_id = uuid4(), uuid4()
        _insert_source_and_passage(conn, source_id, passage_id)

        practice_repo.save_achievement(passage_id, datetime(2026, 4, 10, 12, 0))
        assert practice_repo.has_achievement(passage_id) is True

    def test_idempotent_save(self, repo) -> None:
        practice_repo, conn = repo
        source_id, passage_id = uuid4(), uuid4()
        _insert_source_and_passage(conn, source_id, passage_id)

        practice_repo.save_achievement(passage_id, datetime(2026, 4, 10, 12, 0))
        practice_repo.save_achievement(passage_id, datetime(2026, 4, 10, 13, 0))
        assert practice_repo.has_achievement(passage_id) is True
