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
    LiveDeliveryResult,
    ModelAudio,
    OverlappingResult,
    PronunciationWord,
    SentenceStatus,
    WordTimestamp,
)
from parla.domain.similarity import calculate_similarity, judge_passage, judge_sentence_status
from parla.domain.timing import calculate_timing_deviations
from parla.domain.wpm import calculate_wpm, should_skip_phase_c
from parla.event_bus import EventBus
from parla.ports.feedback_repository import FeedbackRepository
from parla.ports.practice_repository import PracticeRepository
from parla.ports.pronunciation_assessment import PronunciationAssessmentPort, RawAssessedWord
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

    # --- TTS Pre-generation ---

    def request_model_audio(self, passage_id: UUID) -> None:
        """Request TTS generation for a passage's dynamic model answers.

        Called when Phase B begins — the TTS generates in the background
        while the user reviews feedback.
        """
        self._bus.emit(ModelAudioRequested(passage_id=passage_id))

    async def handle_model_audio_requested(self, event: ModelAudioRequested) -> None:
        """Async handler: collect model answers, generate TTS, cache result."""
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
            )
            self._practice_repo.save_model_audio(model_audio)
            self._bus.emit(ModelAudioReady(passage_id=event.passage_id))

        except Exception as exc:
            logger.exception("model_audio_generation_failed", passage_id=str(event.passage_id))
            self._bus.emit(ModelAudioFailed(passage_id=event.passage_id, error_message=str(exc)))

    # --- Skip Check ---

    def should_skip(self, new_item_count: int, wpm: float, cefr_level: str) -> bool:
        """Check if Phase C should be skipped (0 new items AND WPM in target)."""
        return should_skip_phase_c(new_item_count, wpm, cefr_level)

    # --- Overlapping ---

    async def evaluate_overlapping(self, passage_id: UUID, user_audio: AudioData) -> OverlappingResult:
        """Evaluate overlapping practice against model audio."""
        model_audio = self._practice_repo.get_model_audio(passage_id)
        if model_audio is None:
            msg = f"Model audio not found for passage {passage_id}"
            raise ValueError(msg)

        reference_text = " ".join(wt.word for wt in model_audio.word_timestamps)

        raw_result = await self._pronunciation_assessor.assess(user_audio, reference_text)

        words = tuple(self._to_pronunciation_word(w) for w in raw_result.words)

        # Calculate timing deviations against reference timestamps
        user_offsets = [w.offset_seconds for w in words if w.error_type != "Omission" and w.offset_seconds >= 0]
        ref_offsets = [wt.start_seconds for wt in model_audio.word_timestamps]
        n = min(len(user_offsets), len(ref_offsets))
        deviations = calculate_timing_deviations(user_offsets[:n], ref_offsets[:n], baseline_correction=False)

        result = OverlappingResult(
            passage_id=passage_id,
            words=words,
            timing_deviations=tuple(deviations),
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

    async def evaluate_live_delivery(
        self,
        passage_id: UUID,
        user_audio: AudioData,
        duration_seconds: float,
    ) -> LiveDeliveryResult:
        """Evaluate live delivery against model answers."""
        passage = self._source_repo.get_passage(passage_id)
        if passage is None:
            msg = f"Passage not found: {passage_id}"
            raise ValueError(msg)

        # Collect model answer texts per sentence
        sentence_model_texts: list[str] = []
        for sentence in passage.sentences:
            feedback = self._feedback_repo.get_feedback_by_sentence(sentence.id)
            if feedback is None:
                sentence_model_texts.append(sentence.en)
            else:
                sentence_model_texts.append(feedback.model_answer)

        full_reference = " ".join(sentence_model_texts)

        raw_result = await self._pronunciation_assessor.assess(user_audio, full_reference)

        words = tuple(self._to_pronunciation_word(w) for w in raw_result.words)

        # Map words to sentences and calculate per-sentence status
        sentence_statuses = self._map_words_to_sentences(sentence_model_texts, words)

        status_strings = [s.status for s in sentence_statuses]
        passed = judge_passage(status_strings)

        total_words = sum(len(t.split()) for t in sentence_model_texts)
        wpm = calculate_wpm(total_words, duration_seconds)

        result = LiveDeliveryResult(
            passage_id=passage_id,
            passed=passed,
            sentence_statuses=tuple(sentence_statuses),
            duration_seconds=duration_seconds,
            wpm=wpm,
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
                wpm=wpm,
            )
        )

        return result

    # --- Internal helpers ---

    @staticmethod
    def _to_pronunciation_word(raw: RawAssessedWord) -> PronunciationWord:
        return PronunciationWord(
            word=raw.word,
            accuracy_score=raw.accuracy_score,
            error_type=raw.error_type,  # type: ignore[arg-type]
            offset_seconds=raw.offset_seconds,
            duration_seconds=raw.duration_seconds,
        )

    @staticmethod
    def _map_words_to_sentences(
        sentence_texts: list[str],
        assessed_words: tuple[PronunciationWord, ...],
    ) -> list[SentenceStatus]:
        """Map assessed words to sentences and calculate per-sentence similarity."""
        # Build sentence word ranges from reference texts
        sentence_word_counts = [len(text.split()) for text in sentence_texts]

        # Filter out Insertions for reference-aligned word list
        ref_aligned = [w for w in assessed_words if w.error_type != "Insertion"]

        results: list[SentenceStatus] = []
        word_offset = 0

        for i, (text, word_count) in enumerate(zip(sentence_texts, sentence_word_counts, strict=True)):
            sentence_words = ref_aligned[word_offset : word_offset + word_count]
            word_offset += word_count

            # User's recognized text (exclude Omissions)
            user_words = [w.word for w in sentence_words if w.error_type != "Omission"]
            user_text = " ".join(user_words) if user_words else "(no speech)"

            # Similarity
            similarity = calculate_similarity(text, user_text)

            # Omission ratio
            omission_count = sum(1 for w in sentence_words if w.error_type == "Omission")
            omission_ratio = omission_count / max(len(sentence_words), 1)

            status = judge_sentence_status(similarity, omission_ratio)

            results.append(
                SentenceStatus(
                    sentence_index=i,
                    recognized_text=user_text,
                    model_text=text,
                    similarity=similarity,
                    status=status,  # type: ignore[arg-type]
                )
            )

        return results
