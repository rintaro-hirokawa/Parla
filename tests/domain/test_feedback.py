"""Tests for feedback-related domain models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from parla.domain.audio import AudioData
from parla.domain.feedback import PracticeAttempt, RetryResult, SentenceFeedback


class TestSentenceFeedback:
    def test_create(self) -> None:
        fb = SentenceFeedback(
            sentence_id=uuid4(),
            user_utterance="I think this is [pause] very hard.",
            model_answer="I think this is very difficult.",
            is_acceptable=True,
        )
        assert fb.user_utterance == "I think this is [pause] very hard."
        assert fb.is_acceptable is True

    def test_frozen(self) -> None:
        fb = SentenceFeedback(
            sentence_id=uuid4(),
            user_utterance="test",
            model_answer="test",
            is_acceptable=True,
        )
        with pytest.raises(ValidationError):
            fb.model_answer = "changed"  # type: ignore[misc]


class TestRetryResult:
    def test_correct(self) -> None:
        r = RetryResult(correct=True, reason="一致しています")
        assert r.correct is True

    def test_incorrect(self) -> None:
        r = RetryResult(correct=False, reason="日本語の混入")
        assert r.correct is False


class TestPracticeAttempt:
    def test_create(self) -> None:
        a = PracticeAttempt(
            sentence_id=uuid4(),
            attempt_number=1,
            correct=False,
            reason="語句の欠落",
        )
        assert a.attempt_number == 1
        assert a.correct is False

    def test_attempt_number_range(self) -> None:
        for n in (1, 2, 3):
            a = PracticeAttempt(
                sentence_id=uuid4(),
                attempt_number=n,
                correct=True,
            )
            assert a.attempt_number == n

    def test_attempt_below_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PracticeAttempt(
                sentence_id=uuid4(),
                attempt_number=0,
                correct=True,
            )

    def test_attempt_above_3_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PracticeAttempt(
                sentence_id=uuid4(),
                attempt_number=4,
                correct=True,
            )


class TestAudioData:
    def _make_audio(self, **overrides) -> AudioData:
        defaults = {
            "data": b"\x00\x01\x02\x03",
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
            "duration_seconds": 3.5,
        }
        defaults.update(overrides)
        return AudioData(**defaults)

    def test_create(self) -> None:
        a = self._make_audio()
        assert a.format == "wav"
        assert a.sample_rate == 16000
        assert a.channels == 1
        assert a.sample_width == 2
        assert a.duration_seconds == 3.5

    def test_frozen(self) -> None:
        a = self._make_audio()
        with pytest.raises(ValidationError):
            a.data = b"\xff"  # type: ignore[misc]

    def test_zero_duration_allowed(self) -> None:
        a = self._make_audio(duration_seconds=0.0)
        assert a.duration_seconds == 0.0

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_audio(duration_seconds=-1.0)

    def test_zero_channels_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_audio(channels=0)
