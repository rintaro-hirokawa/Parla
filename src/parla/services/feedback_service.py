"""Phase A/B feedback orchestration service."""

from uuid import UUID

import structlog

from parla.domain.audio import AudioData
from parla.domain.events import (
    FeedbackFailed,
    FeedbackReady,
    LearningItemStocked,
    RetryJudged,
    SentenceRecorded,
)
from parla.domain.feedback import PracticeAttempt, RetryResult, SentenceFeedback
from parla.domain.learning_item import RawItemData, create_learning_items_from_raw
from parla.event_bus import EventBus
from parla.ports.audio_storage import AudioStorage
from parla.ports.feedback_generation import (
    FeedbackGenerationPort,
    StockedItemInfo,
)
from parla.ports.feedback_repository import FeedbackRepository
from parla.ports.learning_item_repository import LearningItemRepository
from parla.ports.retry_judgment import RetryJudgmentPort
from parla.ports.source_repository import SourceRepository

logger = structlog.get_logger()


class FeedbackService:
    """Orchestrates Phase A recording and Phase B feedback/retry."""

    def __init__(
        self,
        event_bus: EventBus,
        source_repo: SourceRepository,
        feedback_repo: FeedbackRepository,
        item_repo: LearningItemRepository,
        audio_storage: AudioStorage,
        feedback_generator: FeedbackGenerationPort,
        retry_judge: RetryJudgmentPort,
    ) -> None:
        self._bus = event_bus
        self._source_repo = source_repo
        self._feedback_repo = feedback_repo
        self._item_repo = item_repo
        self._audio_storage = audio_storage
        self._generator = feedback_generator
        self._retry_judge = retry_judge

    def get_feedback_by_sentence(self, sentence_id: UUID) -> SentenceFeedback | None:
        """Look up feedback for a sentence."""
        return self._feedback_repo.get_feedback_by_sentence(sentence_id)

    def record_sentence(
        self,
        passage_id: UUID,
        sentence_id: UUID,
        audio: AudioData,
    ) -> None:
        """Phase A: Save audio and emit SentenceRecorded for background processing."""
        self._audio_storage.save(sentence_id, audio)
        self._bus.emit(SentenceRecorded(passage_id=passage_id, sentence_id=sentence_id))

    async def handle_sentence_recorded(self, event: SentenceRecorded) -> None:
        """Async handler: generate feedback, stock learning items."""
        passage = self._source_repo.get_passage(event.passage_id)
        if passage is None:
            logger.error("passage_not_found", passage_id=str(event.passage_id))
            return

        sentence = next((s for s in passage.sentences if s.id == event.sentence_id), None)
        if sentence is None:
            logger.error("sentence_not_found", sentence_id=str(event.sentence_id))
            return

        source = self._source_repo.get_source(passage.source_id)
        if source is None:
            logger.error("source_not_found", source_id=str(passage.source_id))
            return

        audio = self._audio_storage.load(event.sentence_id)
        if audio is None:
            logger.error("audio_not_found", sentence_id=str(event.sentence_id))
            return

        try:
            stocked_items = self._item_repo.get_stocked_items()
            stocked_info = [
                StockedItemInfo(
                    item_id=str(item.id),
                    pattern=item.pattern,
                    category=item.category,
                    example_sentence=item.explanation[:80],
                )
                for item in stocked_items
            ]

            raw_feedback = await self._generator.generate_feedback(
                audio_data=audio.data,
                audio_format=audio.format,
                ja_prompt=sentence.ja,
                cefr_level=source.cefr_level,
                english_variant=source.english_variant,
                stocked_items=stocked_info,
            )

            user_utterance = raw_feedback.user_utterance
            model_answer = raw_feedback.model_answer

            if not user_utterance or user_utterance == "<no_speech>":
                user_utterance = "（発話なし）"

            feedback = SentenceFeedback(
                sentence_id=event.sentence_id,
                user_utterance=user_utterance,
                model_answer=model_answer,
                is_acceptable=raw_feedback.is_acceptable,
            )
            self._feedback_repo.save_feedback(feedback)

            raw_item_data = [
                RawItemData(
                    pattern=ri.pattern,
                    explanation=ri.explanation,
                    category=ri.category,
                    sub_tag=ri.sub_tag,
                    priority=ri.priority,
                    is_reappearance=ri.is_reappearance,
                    matched_stock_item_id=ri.matched_stock_item_id,
                )
                for ri in raw_feedback.items
            ]
            learning_items = create_learning_items_from_raw(
                raw_item_data,
                event.sentence_id,
            )
            if learning_items:
                self._item_repo.save_items(learning_items)
                for item in learning_items:
                    if item.status == "auto_stocked":
                        self._bus.emit(
                            LearningItemStocked(
                                item_id=item.id,
                                pattern=item.pattern,
                                is_reappearance=item.is_reappearance,
                            )
                        )

            self._bus.emit(
                FeedbackReady(
                    passage_id=event.passage_id,
                    sentence_id=event.sentence_id,
                )
            )

        except Exception as exc:
            logger.exception(
                "feedback_generation_failed",
                sentence_id=str(event.sentence_id),
            )
            self._bus.emit(
                FeedbackFailed(
                    passage_id=event.passage_id,
                    sentence_id=event.sentence_id,
                    error_message=str(exc),
                )
            )

    async def judge_retry(
        self,
        sentence_id: UUID,
        attempt: int,
        audio: AudioData,
    ) -> RetryResult:
        """Phase B: Judge retry utterance and record attempt."""
        self._audio_storage.save(sentence_id, audio)

        feedback = self._feedback_repo.get_feedback_by_sentence(sentence_id)
        if feedback is None:
            msg = f"No feedback found for sentence {sentence_id}"
            raise ValueError(msg)

        result = await self._retry_judge.judge(
            audio_data=audio.data,
            audio_format=audio.format,
            reference_answer=feedback.model_answer,
        )

        practice = PracticeAttempt(
            sentence_id=sentence_id,
            attempt_number=attempt,
            correct=result.correct,
            reason=result.reason,
        )
        self._feedback_repo.save_practice_attempt(practice)

        self._bus.emit(
            RetryJudged(
                sentence_id=sentence_id,
                attempt=attempt,
                correct=result.correct,
            )
        )

        return result

