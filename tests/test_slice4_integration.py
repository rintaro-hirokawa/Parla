"""Slice 4 integration tests: Phase C (通し練習).

Verifies the full flow with real SQLite (:memory:), real EventBus wiring,
real AudioStorage (tmp_path), and Fake external adapters.

Model audio generation:
  request_model_audio → emit(ModelAudioRequested) → handler → Fake TTS
  → model audio saved → ModelAudioReady

Overlapping evaluation:
  evaluate_overlapping(audio) → Fake Azure → timing deviations + pronunciation
  → result saved → OverlappingCompleted

Live delivery evaluation:
  evaluate_live_delivery(audio) → Fake Azure → per-sentence similarity
  → pass/fail → result saved → LiveDeliveryCompleted
  → achievement on pass → PassageAchievementRecorded
"""

from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

import pytest

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_feedback_repository import SQLiteFeedbackRepository
from parla.adapters.sqlite_practice_repository import SQLitePracticeRepository
from parla.adapters.sqlite_source_repository import SQLiteSourceRepository
from parla.domain.audio import AudioData
from parla.domain.events import (
    LiveDeliveryCompleted,
    ModelAudioFailed,
    ModelAudioReady,
    OverlappingCompleted,
    PassageAchievementRecorded,
)
from parla.domain.feedback import SentenceFeedback
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.source import Source
from parla.event_bus import Event, EventBus
from parla.ports.pronunciation_assessment import RawAssessedWord, RawAssessmentResult
from parla.ports.tts_generation import RawTTSResult, RawWordTimestamp
from parla.services.practice_service import PracticeService

# --- Fake adapters ---


class FakeTTSGenerator:
    """Returns canned audio bytes + synthetic timestamps."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def generate_with_timestamps(self, text: str, english_variant: str) -> RawTTSResult:
        if self._fail:
            msg = "Simulated TTS error"
            raise RuntimeError(msg)

        words = text.split()
        timestamps = tuple(
            RawWordTimestamp(word=w, start_seconds=i * 0.5, end_seconds=i * 0.5 + 0.4) for i, w in enumerate(words)
        )
        return RawTTSResult(
            audio_data=b"\x00" * 1000,
            audio_format="wav",
            sample_rate=16000,
            channels=1,
            sample_width=2,
            duration_seconds=len(words) * 0.5,
            word_timestamps=timestamps,
        )


class FakePronunciationAssessor:
    """Returns pre-configured assessment results based on scenario."""

    def __init__(self, assessed_words: Sequence[RawAssessedWord] | None = None) -> None:
        self._words = tuple(assessed_words) if assessed_words else ()

    async def assess(self, audio: AudioData, reference_text: str) -> RawAssessmentResult:
        if self._words:
            words = self._words
        else:
            # Default: perfect recognition of all reference words
            words = tuple(
                RawAssessedWord(
                    word=w,
                    accuracy_score=95.0,
                    error_type="None",
                    offset_seconds=i * 0.5,
                    duration_seconds=0.4,
                )
                for i, w in enumerate(reference_text.split())
            )

        return RawAssessmentResult(
            recognized_text=" ".join(w.word for w in words if w.error_type != "Omission"),
            words=words,
            accuracy_score=90.0,
            fluency_score=85.0,
            completeness_score=95.0,
            prosody_score=80.0,
            pronunciation_score=88.0,
        )


# --- Test helpers ---


class EventCollector:
    """Collects emitted events for assertions."""

    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        bus.on_sync(ModelAudioReady)(self._collect)
        bus.on_sync(ModelAudioFailed)(self._collect)
        bus.on_sync(OverlappingCompleted)(self._collect)
        bus.on_sync(LiveDeliveryCompleted)(self._collect)
        bus.on_sync(PassageAchievementRecorded)(self._collect)

    def _collect(self, event: Event) -> None:
        self.events.append(event)

    def of_type(self, cls: type) -> list[Event]:
        return [e for e in self.events if isinstance(e, cls)]


def _make_audio() -> AudioData:
    return AudioData(
        data=b"\x00" * 100, format="wav", sample_rate=16000, channels=1, sample_width=2, duration_seconds=5.0
    )


@pytest.fixture
def setup(tmp_path: Path):
    """Create all dependencies for PracticeService integration tests."""
    conn = create_connection()
    init_schema(conn)
    bus = EventBus()

    source_repo = SQLiteSourceRepository(conn)
    feedback_repo = SQLiteFeedbackRepository(conn)
    practice_repo = SQLitePracticeRepository(conn, tmp_path / "audio")

    # Insert test source + passage + sentences
    source_id = uuid4()
    passage_id = uuid4()
    sentence_ids = [uuid4(), uuid4(), uuid4()]

    source = Source(
        id=source_id,
        title="Test Source",
        text="A" * 100,
        cefr_level="B1",
        english_variant="American",
        status="not_started",
    )
    source_repo.save_source(source)

    passage = Passage(
        id=passage_id,
        source_id=source_id,
        order=1,
        topic="Test Topic",
        passage_type="explanation",
        sentences=tuple(
            Sentence(
                id=sid,
                order=i + 1,
                ja=f"日本語{i + 1}",
                en=f"English sentence number {i + 1}",
                hints=Hint(hint1=f"hint1_{i + 1}", hint2=f"hint2_{i + 1}"),
            )
            for i, sid in enumerate(sentence_ids)
        ),
    )
    source_repo.save_passages([passage])

    # Insert feedback (model answers) for each sentence
    for i, sid in enumerate(sentence_ids):
        feedback = SentenceFeedback(
            sentence_id=sid,
            user_utterance=f"user said something {i + 1}",
            model_answer=f"Dynamic model answer for sentence {i + 1}",
            is_acceptable=True,
        )
        feedback_repo.save_feedback(feedback)

    return {
        "conn": conn,
        "bus": bus,
        "source_repo": source_repo,
        "feedback_repo": feedback_repo,
        "practice_repo": practice_repo,
        "source_id": source_id,
        "passage_id": passage_id,
        "sentence_ids": sentence_ids,
        "tmp_path": tmp_path,
    }


def _make_service(setup_data, *, tts=None, assessor=None) -> tuple[PracticeService, EventCollector]:
    bus = setup_data["bus"]
    collector = EventCollector(bus)

    service = PracticeService(
        event_bus=bus,
        source_repo=setup_data["source_repo"],
        feedback_repo=setup_data["feedback_repo"],
        practice_repo=setup_data["practice_repo"],
        tts_generator=tts or FakeTTSGenerator(),
        pronunciation_assessor=assessor or FakePronunciationAssessor(),
    )

    bus.on_async(service.handle_model_audio_requested.__func__.__qualname__)(  # type: ignore[union-attr]
        service.handle_model_audio_requested
    ) if False else None  # noqa: E501 — handler registered below

    return service, collector


# --- Model Audio Generation Tests ---


class TestModelAudioGeneration:
    @pytest.mark.asyncio
    async def test_model_audio_saved(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )
        collector = EventCollector(setup["bus"])

        from parla.domain.events import ModelAudioRequested

        event = ModelAudioRequested(passage_id=setup["passage_id"])
        await service.handle_model_audio_requested(event)

        # Verify model audio saved
        model_audio = setup["practice_repo"].get_model_audio(setup["passage_id"])
        assert model_audio is not None
        assert len(model_audio.word_timestamps) > 0

        # Verify event emitted
        ready_events = collector.of_type(ModelAudioReady)
        assert len(ready_events) == 1
        assert ready_events[0].passage_id == setup["passage_id"]

    @pytest.mark.asyncio
    async def test_model_audio_failed_event(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(fail=True),
            pronunciation_assessor=FakePronunciationAssessor(),
        )
        collector = EventCollector(setup["bus"])

        from parla.domain.events import ModelAudioRequested

        event = ModelAudioRequested(passage_id=setup["passage_id"])
        await service.handle_model_audio_requested(event)

        failed_events = collector.of_type(ModelAudioFailed)
        assert len(failed_events) == 1

    @pytest.mark.asyncio
    async def test_missing_feedback_falls_back_to_en(self, setup) -> None:
        """When feedback is missing for a sentence, use the pre-generated en text."""
        # Delete all feedback
        setup["conn"].execute("DELETE FROM sentence_feedback")
        setup["conn"].commit()

        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )

        from parla.domain.events import ModelAudioRequested

        event = ModelAudioRequested(passage_id=setup["passage_id"])
        await service.handle_model_audio_requested(event)

        model_audio = setup["practice_repo"].get_model_audio(setup["passage_id"])
        assert model_audio is not None


# --- Overlapping Tests ---


class TestOverlapping:
    @pytest.mark.asyncio
    async def test_result_saved_and_event(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )
        collector = EventCollector(setup["bus"])

        # First generate model audio
        from parla.domain.events import ModelAudioRequested

        await service.handle_model_audio_requested(ModelAudioRequested(passage_id=setup["passage_id"]))

        # Evaluate overlapping
        result = await service.evaluate_overlapping(setup["passage_id"], _make_audio())

        assert result.passage_id == setup["passage_id"]
        assert len(result.words) > 0
        assert len(result.timing_deviations) > 0

        events = collector.of_type(OverlappingCompleted)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_timing_deviations_calculated(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )

        from parla.domain.events import ModelAudioRequested

        await service.handle_model_audio_requested(ModelAudioRequested(passage_id=setup["passage_id"]))

        result = await service.evaluate_overlapping(setup["passage_id"], _make_audio())
        # With FakePronunciationAssessor returning same offsets as FakeTTS,
        # deviations should be approximately 0
        for dev in result.timing_deviations:
            assert abs(dev) < 1.0

    @pytest.mark.asyncio
    async def test_no_model_audio_raises(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )

        with pytest.raises(ValueError, match="Model audio not found"):
            await service.evaluate_overlapping(setup["passage_id"], _make_audio())


# --- Live Delivery Tests ---


class TestLiveDelivery:
    @pytest.mark.asyncio
    async def test_pass_all_correct(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )
        collector = EventCollector(setup["bus"])

        result = await service.evaluate_live_delivery(setup["passage_id"], _make_audio(), 30.0)

        assert result.passed is True
        assert all(s.status == "correct" for s in result.sentence_statuses)

        # Achievement recorded
        assert setup["practice_repo"].has_achievement(setup["passage_id"])

        # Events
        achievement_events = collector.of_type(PassageAchievementRecorded)
        assert len(achievement_events) == 1

        delivery_events = collector.of_type(LiveDeliveryCompleted)
        assert len(delivery_events) == 1
        assert delivery_events[0].passed is True

    @pytest.mark.asyncio
    async def test_fail_with_omission(self, setup) -> None:
        """Simulate sentence 2 being completely omitted (no speech)."""
        passage = setup["source_repo"].get_passage(setup["passage_id"])
        model_texts = []
        for s in passage.sentences:
            fb = setup["feedback_repo"].get_feedback_by_sentence(s.id)
            model_texts.append(fb.model_answer if fb else s.en)

        # Build assessed words: sentences 1 and 3 perfect, sentence 2 all Omission
        assessed: list[RawAssessedWord] = []
        offset = 0.0
        for i, text in enumerate(model_texts):
            words = text.split()
            for w in words:
                if i == 1:
                    assessed.append(
                        RawAssessedWord(
                            word=w,
                            accuracy_score=0.0,
                            error_type="Omission",
                            offset_seconds=-1.0,
                            duration_seconds=0.0,
                        )
                    )
                else:
                    assessed.append(
                        RawAssessedWord(
                            word=w,
                            accuracy_score=95.0,
                            error_type="None",
                            offset_seconds=offset,
                            duration_seconds=0.4,
                        )
                    )
                    offset += 0.5

        assessor = FakePronunciationAssessor(assessed_words=assessed)
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=assessor,
        )
        collector = EventCollector(setup["bus"])

        result = await service.evaluate_live_delivery(setup["passage_id"], _make_audio(), 30.0)

        assert result.passed is False
        assert result.sentence_statuses[1].status == "error"
        assert result.sentence_statuses[0].status == "correct"
        assert result.sentence_statuses[2].status == "correct"

        # No achievement
        assert not setup["practice_repo"].has_achievement(setup["passage_id"])
        assert len(collector.of_type(PassageAchievementRecorded)) == 0

    @pytest.mark.asyncio
    async def test_wpm_calculated(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )

        result = await service.evaluate_live_delivery(setup["passage_id"], _make_audio(), 60.0)

        # 3 sentences × 6 words each = 18 words in 60 seconds = 18 WPM
        assert result.wpm > 0
        assert result.duration_seconds == 60.0

    @pytest.mark.asyncio
    async def test_result_persisted(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )

        await service.evaluate_live_delivery(setup["passage_id"], _make_audio(), 30.0)

        results = setup["practice_repo"].get_live_delivery_results(setup["passage_id"])
        assert len(results) == 1
        assert results[0].passed is True


# --- Skip Check Tests ---


class TestSkipCheck:
    def test_skip_when_no_items_and_wpm_ok(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )
        assert service.should_skip(0, 120.0, "B1") is True

    def test_no_skip_when_items_exist(self, setup) -> None:
        service = PracticeService(
            event_bus=setup["bus"],
            source_repo=setup["source_repo"],
            feedback_repo=setup["feedback_repo"],
            practice_repo=setup["practice_repo"],
            tts_generator=FakeTTSGenerator(),
            pronunciation_assessor=FakePronunciationAssessor(),
        )
        assert service.should_skip(2, 120.0, "B1") is False
