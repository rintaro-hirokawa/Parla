"""Tests for Phase C domain models."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from parla.domain.audio import AudioData
from parla.domain.practice import (
    LiveDeliveryResult,
    ModelAudio,
    OverlappingResult,
    PronunciationWord,
    SentenceStatus,
    WordTimestamp,
    map_words_to_sentence_groups,
)


def _make_audio() -> AudioData:
    return AudioData(
        data=b"\x00" * 100,
        format="wav",
        sample_rate=16000,
        channels=1,
        sample_width=2,
        duration_seconds=1.0,
    )


class TestWordTimestamp:
    def test_construction(self) -> None:
        wt = WordTimestamp(word="hello", start_seconds=0.0, end_seconds=0.5)
        assert wt.word == "hello"
        assert wt.start_seconds == 0.0
        assert wt.end_seconds == 0.5

    def test_negative_start_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WordTimestamp(word="hello", start_seconds=-1.0, end_seconds=0.5)


class TestModelAudio:
    def test_construction(self) -> None:
        pid = uuid4()
        ma = ModelAudio(
            passage_id=pid,
            audio=_make_audio(),
            word_timestamps=(
                WordTimestamp(word="hello", start_seconds=0.0, end_seconds=0.3),
                WordTimestamp(word="world", start_seconds=0.4, end_seconds=0.7),
            ),
        )
        assert ma.passage_id == pid
        assert len(ma.word_timestamps) == 2


class TestPronunciationWord:
    def test_construction(self) -> None:
        pw = PronunciationWord(
            word="hello",
            accuracy_score=95.0,
            error_type="None",
            offset_seconds=0.5,
            duration_seconds=0.3,
        )
        assert pw.accuracy_score == 95.0

    def test_omission_has_default_offset(self) -> None:
        pw = PronunciationWord(
            word="missed",
            accuracy_score=0.0,
            error_type="Omission",
        )
        assert pw.offset_seconds == -1.0

    def test_accuracy_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            PronunciationWord(word="x", accuracy_score=101.0, error_type="None")
        with pytest.raises(ValidationError):
            PronunciationWord(word="x", accuracy_score=-1.0, error_type="None")

    def test_invalid_error_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PronunciationWord(word="x", accuracy_score=50.0, error_type="Unknown")


class TestSentenceStatus:
    def test_construction(self) -> None:
        ss = SentenceStatus(
            sentence_index=0,
            recognized_text="hello world",
            model_text="hello world",
            similarity=1.0,
            status="correct",
        )
        assert ss.status == "correct"

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SentenceStatus(
                sentence_index=0,
                recognized_text="",
                model_text="",
                similarity=0.5,
                status="unknown",
            )


class TestOverlappingResult:
    def test_construction(self) -> None:
        result = OverlappingResult(
            passage_id=uuid4(),
            words=(
                PronunciationWord(
                    word="hello", accuracy_score=90.0, error_type="None", offset_seconds=0.1, duration_seconds=0.3
                ),
            ),
            timing_deviations=(0.1,),
            accuracy_score=90.0,
            fluency_score=85.0,
            prosody_score=80.0,
            pronunciation_score=88.0,
        )
        assert len(result.words) == 1
        assert result.id is not None


class TestLiveDeliveryResult:
    def test_construction(self) -> None:
        result = LiveDeliveryResult(
            passage_id=uuid4(),
            passed=True,
            sentence_statuses=(
                SentenceStatus(
                    sentence_index=0, recognized_text="hello", model_text="hello", similarity=1.0, status="correct"
                ),
            ),
            duration_seconds=30.0,
            wpm=120.0,
        )
        assert result.passed is True
        assert result.wpm == 120.0

    def test_negative_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LiveDeliveryResult(
                passage_id=uuid4(),
                passed=False,
                sentence_statuses=(),
                duration_seconds=-1.0,
                wpm=0.0,
            )


def _pw(word: str, error_type: str = "None", accuracy: float = 90.0) -> PronunciationWord:
    return PronunciationWord(word=word, accuracy_score=accuracy, error_type=error_type)


class TestMapWordsToSentenceGroups:
    def test_basic_two_sentences(self) -> None:
        words = (_pw("Hello"), _pw("world"), _pw("Good"), _pw("morning"))
        sentences = ("Hello world", "Good morning")
        groups = map_words_to_sentence_groups(words, sentences)
        assert len(groups) == 2
        assert [w.word for w in groups[0]] == ["Hello", "world"]
        assert [w.word for w in groups[1]] == ["Good", "morning"]

    def test_insertions_excluded(self) -> None:
        words = (_pw("Hello"), _pw("um", "Insertion"), _pw("world"))
        sentences = ("Hello world",)
        groups = map_words_to_sentence_groups(words, sentences)
        assert len(groups) == 1
        assert [w.word for w in groups[0]] == ["Hello", "world"]

    def test_omissions_kept(self) -> None:
        words = (_pw("Hello"), _pw("world", "Omission", 0.0))
        sentences = ("Hello world",)
        groups = map_words_to_sentence_groups(words, sentences)
        assert [w.error_type for w in groups[0]] == ["None", "Omission"]

    def test_fewer_words_than_expected(self) -> None:
        words = (_pw("Hello"),)
        sentences = ("Hello world", "Good morning")
        groups = map_words_to_sentence_groups(words, sentences)
        assert [w.word for w in groups[0]] == ["Hello"]
        assert groups[1] == ()

    def test_empty_words(self) -> None:
        groups = map_words_to_sentence_groups((), ("Hello world",))
        assert groups == ((),)

    def test_empty_sentences(self) -> None:
        groups = map_words_to_sentence_groups((_pw("Hello"),), ())
        assert groups == ()
