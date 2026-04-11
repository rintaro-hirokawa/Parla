"""Phase C practice orchestration service."""

from datetime import datetime
from uuid import UUID

import structlog

from parla.domain.audio import AudioData
from parla.domain.events import (
    LiveDeliveryCompleted,
    ModelAudioFailed,
    ModelAudioReady,
    ModelAudioRequested,
    OverlappingCompleted,
    PassageAchievementRecorded,
)
from parla.domain.practice import (
    ERROR_RATE_THRESHOLD,
    LiveDeliveryResult,
    ModelAudio,
    OverlappingResult,
    PronunciationWord,
    WordTimestamp,
    calculate_error_rate,
    judge_passed,
)
from parla.event_bus import EventBus
from parla.ports.feedback_repository import FeedbackRepository
from parla.ports.practice_repository import PracticeRepository
from parla.ports.pronunciation_assessment import (
    PronunciationAssessmentPort,
    RawAssessedWord,
    RawAssessmentResult,
    StreamingAssessmentSession,
)
from parla.ports.source_repository import SourceRepository
from parla.ports.tts_generation import TTSGenerationPort

logger = structlog.get_logger()


class PracticeService:
    """Orchestrates Phase C: listening, overlapping, live delivery."""

    def __init__(
        self,
        event_bus: EventBus,
        source_repo: SourceRepository,
        feedback_repo: FeedbackRepository,
        practice_repo: PracticeRepository,
        tts_generator: TTSGenerationPort,
        pronunciation_assessor: PronunciationAssessmentPort,
    ) -> None:
        self._bus = event_bus
        self._source_repo = source_repo
        self._feedback_repo = feedback_repo
        self._practice_repo = practice_repo
        self._tts_generator = tts_generator
        self._pronunciation_assessor = pronunciation_assessor

    def get_model_audio(self, passage_id: UUID) -> ModelAudio | None:
        """Look up cached model audio for a passage."""
        return self._practice_repo.get_model_audio(passage_id)

    def request_model_audio(self, passage_id: UUID) -> None:
        """Request TTS generation for a passage's dynamic model answers.

        Called when Phase B begins — the TTS generates in the background
        while the user reviews feedback.
        """
        self._bus.emit(ModelAudioRequested(passage_id=passage_id))

    async def handle_model_audio_requested(self, event: ModelAudioRequested) -> None:
        """Async handler: collect model answers, generate TTS, cache result."""
        # Return cached audio if already generated
        existing = self._practice_repo.get_model_audio(event.passage_id)
        if existing is not None:
            logger.info("model_audio_cache_hit", passage_id=str(event.passage_id))
            self._bus.emit(ModelAudioReady(passage_id=event.passage_id))
            return

        passage = self._source_repo.get_passage(event.passage_id)
        if passage is None:
            logger.error("passage_not_found", passage_id=str(event.passage_id))
            self._bus.emit(ModelAudioFailed(passage_id=event.passage_id, error_message="Passage not found"))
            return

        # Collect model answers from Phase B feedback
        model_answers: list[str] = []
        for sentence in passage.sentences:
            feedback = self._feedback_repo.get_feedback_by_sentence(sentence.id)
            if feedback is None:
                logger.warning("feedback_not_found", sentence_id=str(sentence.id))
                model_answers.append(sentence.en)
            else:
                model_answers.append(feedback.model_answer)

        full_text = " ".join(model_answers)

        source = self._source_repo.get_source(passage.source_id)
        english_variant = source.english_variant if source else "american"

        try:
            raw_tts = await self._tts_generator.generate_with_timestamps(full_text, english_variant)

            model_audio = ModelAudio(
                passage_id=event.passage_id,
                audio=AudioData(
                    data=raw_tts.audio_data,
                    format=raw_tts.audio_format,
                    sample_rate=raw_tts.sample_rate,
                    channels=raw_tts.channels,
                    sample_width=raw_tts.sample_width,
                    duration_seconds=raw_tts.duration_seconds,
                ),
                word_timestamps=tuple(
                    WordTimestamp(word=wt.word, start_seconds=wt.start_seconds, end_seconds=wt.end_seconds)
                    for wt in raw_tts.word_timestamps
                ),
                sentence_texts=tuple(model_answers),
            )
            self._practice_repo.save_model_audio(model_audio)
            self._bus.emit(ModelAudioReady(passage_id=event.passage_id))

        except Exception as exc:
            logger.exception("model_audio_generation_failed", passage_id=str(event.passage_id))
            self._bus.emit(ModelAudioFailed(passage_id=event.passage_id, error_message=str(exc)))

    def start_overlapping_stream(self, passage_id: UUID) -> StreamingAssessmentSession | None:
        """Start a streaming assessment session for overlapping practice.

        Returns None if model audio is not yet available.
        """
        model_audio = self._practice_repo.get_model_audio(passage_id)
        if model_audio is None:
            return None
        reference_text = " ".join(wt.word for wt in model_audio.word_timestamps)
        return self._pronunciation_assessor.start_streaming(reference_text)

    async def finalize_overlapping_stream(
        self, passage_id: UUID, session: StreamingAssessmentSession
    ) -> OverlappingResult:
        """Finalize a streaming session and process overlapping results."""
        model_audio = self._practice_repo.get_model_audio(passage_id)
        if model_audio is None:
            msg = f"Model audio not found for passage {passage_id}"
            raise ValueError(msg)

        raw_result = await session.finalize()

        words = tuple(self._to_pronunciation_word(w) for w in raw_result.words)

        result = OverlappingResult(
            passage_id=passage_id,
            words=words,
            accuracy_score=raw_result.accuracy_score,
            fluency_score=raw_result.fluency_score,
            prosody_score=raw_result.prosody_score,
            pronunciation_score=raw_result.pronunciation_score,
        )
        self._practice_repo.save_overlapping_result(result)

        self._bus.emit(
            OverlappingCompleted(
                passage_id=passage_id,
                pronunciation_score=raw_result.pronunciation_score,
            )
        )

        return result

    async def evaluate_overlapping(self, passage_id: UUID, user_audio: AudioData) -> OverlappingResult:
        """Evaluate overlapping practice against model audio."""
        model_audio = self._practice_repo.get_model_audio(passage_id)
        if model_audio is None:
            msg = f"Model audio not found for passage {passage_id}"
            raise ValueError(msg)

        reference_text = " ".join(wt.word for wt in model_audio.word_timestamps)

        raw_result = await self._pronunciation_assessor.assess(user_audio, reference_text)

        words = tuple(self._to_pronunciation_word(w) for w in raw_result.words)

        result = OverlappingResult(
            passage_id=passage_id,
            words=words,
            accuracy_score=raw_result.accuracy_score,
            fluency_score=raw_result.fluency_score,
            prosody_score=raw_result.prosody_score,
            pronunciation_score=raw_result.pronunciation_score,
        )
        self._practice_repo.save_overlapping_result(result)

        self._bus.emit(
            OverlappingCompleted(
                passage_id=passage_id,
                pronunciation_score=raw_result.pronunciation_score,
            )
        )

        return result

    # --- Live Delivery ---

    def start_live_delivery_stream(self, passage_id: UUID) -> StreamingAssessmentSession | None:
        """Start a streaming assessment session for live delivery practice.

        Returns None if passage or feedback is not available.
        """
        reference_text = self._build_live_delivery_reference(passage_id)
        if reference_text is None:
            return None
        return self._pronunciation_assessor.start_streaming(reference_text)

    async def finalize_live_delivery_stream(
        self,
        passage_id: UUID,
        session: StreamingAssessmentSession,
    ) -> LiveDeliveryResult:
        """Finalize a streaming session and process live delivery results."""
        reference_text = self._build_live_delivery_reference(passage_id)
        if reference_text is None:
            msg = f"Cannot build reference for passage {passage_id}"
            raise ValueError(msg)

        raw_result = await session.finalize()
        return self._process_live_delivery_result(passage_id, raw_result)

    async def evaluate_live_delivery(
        self,
        passage_id: UUID,
        user_audio: AudioData,
    ) -> LiveDeliveryResult:
        """Evaluate live delivery against model answers (batch mode)."""
        reference_text = self._build_live_delivery_reference(passage_id)
        if reference_text is None:
            msg = f"Passage not found: {passage_id}"
            raise ValueError(msg)

        raw_result = await self._pronunciation_assessor.assess(user_audio, reference_text)
        return self._process_live_delivery_result(passage_id, raw_result)

    def _build_live_delivery_reference(self, passage_id: UUID) -> str | None:
        """Build the full reference text for live delivery from model answers."""
        passage = self._source_repo.get_passage(passage_id)
        if passage is None:
            return None
        sentence_model_texts: list[str] = []
        for sentence in passage.sentences:
            feedback = self._feedback_repo.get_feedback_by_sentence(sentence.id)
            if feedback is None:
                sentence_model_texts.append(sentence.en)
            else:
                sentence_model_texts.append(feedback.model_answer)
        return " ".join(sentence_model_texts)

    def _process_live_delivery_result(
        self,
        passage_id: UUID,
        raw_result: RawAssessmentResult,
    ) -> LiveDeliveryResult:
        """Process raw assessment into LiveDeliveryResult, save, and emit events."""
        reference_text = self._build_live_delivery_reference(passage_id)
        if reference_text is None:
            msg = f"Passage not found: {passage_id}"
            raise ValueError(msg)

        words = tuple(self._to_pronunciation_word(w) for w in raw_result.words)
        error_rate = calculate_error_rate(words)
        passed = judge_passed(words)

        result = LiveDeliveryResult(
            passage_id=passage_id,
            passed=passed,
            words=words,
            accuracy_score=raw_result.accuracy_score,
            fluency_score=raw_result.fluency_score,
            prosody_score=raw_result.prosody_score,
            pronunciation_score=raw_result.pronunciation_score,
        )
        self._practice_repo.save_live_delivery_result(result)

        if passed:
            now = datetime.now()
            self._practice_repo.save_achievement(passage_id, now)
            self._bus.emit(PassageAchievementRecorded(passage_id=passage_id))

        self._bus.emit(
            LiveDeliveryCompleted(
                passage_id=passage_id,
                passed=passed,
                error_rate=error_rate,
                error_rate_threshold=ERROR_RATE_THRESHOLD,
            )
        )

        return result

    @staticmethod
    def _to_pronunciation_word(raw: RawAssessedWord) -> PronunciationWord:
        return PronunciationWord(
            word=raw.word,
            accuracy_score=raw.accuracy_score,
            error_type=raw.error_type,
            offset_seconds=raw.offset_seconds,
            duration_seconds=raw.duration_seconds,
        )

