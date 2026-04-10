"""Block 1/3 review orchestration service."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

import structlog

from parla.domain.audio import AudioData
from parla.domain.events import (
    ReviewAnswered,
    ReviewRetryJudged,
    SRSUpdated,
    VariationGenerationFailed,
    VariationGenerationRequested,
    VariationReady,
)
from parla.domain.learning_item import LearningItem
from parla.domain.review import ReviewAttempt, ReviewResult
from parla.domain.source import Source
from parla.domain.srs import SRSConfig, calculate_next_review
from parla.domain.variation import Variation
from parla.event_bus import EventBus
from parla.ports.audio_storage import AudioStorage
from parla.ports.learning_item_repository import LearningItemRepository
from parla.ports.review_attempt_repository import ReviewAttemptRepository
from parla.ports.review_judgment import ReviewJudgmentPort
from parla.ports.source_repository import SourceRepository
from parla.ports.variation_generation import VariationGenerationPort
from parla.ports.variation_repository import VariationRepository
from parla.services.variation_helper import generate_and_save_variation

logger = structlog.get_logger()


@dataclass(frozen=True)
class _ReviewContext:
    """Resolved entities for a review judgment."""

    variation: Variation
    item: LearningItem
    source: Source


class ReviewService:
    """Orchestrates Block 1/3 review: variation generation, judgment, SRS update."""

    def __init__(
        self,
        event_bus: EventBus,
        source_repo: SourceRepository,
        item_repo: LearningItemRepository,
        variation_repo: VariationRepository,
        attempt_repo: ReviewAttemptRepository,
        audio_storage: AudioStorage,
        variation_generator: VariationGenerationPort,
        review_judge: ReviewJudgmentPort,
        srs_config: SRSConfig,
    ) -> None:
        self._bus = event_bus
        self._source_repo = source_repo
        self._item_repo = item_repo
        self._variation_repo = variation_repo
        self._attempt_repo = attempt_repo
        self._audio_storage = audio_storage
        self._variation_generator = variation_generator
        self._review_judge = review_judge
        self._srs_config = srs_config

    def request_variation(self, learning_item_id: UUID, source_id: UUID) -> None:
        """Request variation generation for a learning item."""
        self._bus.emit(
            VariationGenerationRequested(
                learning_item_id=learning_item_id,
                source_id=source_id,
            )
        )

    async def handle_variation_requested(self, event: VariationGenerationRequested) -> None:
        """Async handler: generate variation via LLM, save to repository."""
        item = self._item_repo.get_item(event.learning_item_id)
        if item is None:
            logger.error("learning_item_not_found", item_id=str(event.learning_item_id))
            return

        source = self._source_repo.get_source(event.source_id)
        if source is None:
            logger.error("source_not_found", source_id=str(event.source_id))
            return

        try:
            variation = await generate_and_save_variation(
                item=item,
                source=source,
                variation_repo=self._variation_repo,
                variation_generator=self._variation_generator,
            )

            self._bus.emit(
                VariationReady(
                    variation_id=variation.id,
                    learning_item_id=item.id,
                )
            )

        except Exception as exc:
            logger.exception(
                "variation_generation_failed",
                item_id=str(event.learning_item_id),
            )
            self._bus.emit(
                VariationGenerationFailed(
                    learning_item_id=event.learning_item_id,
                    error_message=str(exc),
                )
            )

    def _resolve_context(self, variation_id: UUID) -> _ReviewContext:
        """Look up variation, learning item, and source. Raises ValueError if any missing."""
        variation = self._variation_repo.get_variation(variation_id)
        if variation is None:
            msg = f"Variation not found: {variation_id}"
            raise ValueError(msg)

        item = self._item_repo.get_item(variation.learning_item_id)
        if item is None:
            msg = f"Learning item not found: {variation.learning_item_id}"
            raise ValueError(msg)

        source = self._source_repo.get_source(variation.source_id)
        if source is None:
            msg = f"Source not found: {variation.source_id}"
            raise ValueError(msg)

        return _ReviewContext(variation=variation, item=item, source=source)

    async def _judge_audio(self, ctx: _ReviewContext, audio: AudioData) -> ReviewResult:
        """Save audio and judge via LLM."""
        self._audio_storage.save(ctx.variation.id, audio)
        return await self._review_judge.judge(
            audio_data=audio.data,
            audio_format=audio.format,
            target_pattern=ctx.item.pattern,
            reference_answer=ctx.variation.en,
            ja_prompt=ctx.variation.ja,
            cefr_level=ctx.source.cefr_level,
        )

    async def judge_review(
        self,
        variation_id: UUID,
        audio: AudioData,
        hint_level: int,
        timer_ratio: float,
        today: date,
    ) -> ReviewResult:
        """Judge initial review attempt and update SRS.

        This is the initial attempt (attempt_number=1).
        SRS state is updated based on this result only.
        """
        ctx = self._resolve_context(variation_id)
        result = await self._judge_audio(ctx, audio)

        # Record attempt
        attempt = ReviewAttempt(
            variation_id=variation_id,
            learning_item_id=ctx.item.id,
            attempt_number=1,
            correct=result.correct,
            item_used=result.item_used,
            hint_level=hint_level,
            timer_ratio=timer_ratio,
        )
        self._attempt_repo.save_attempt(attempt)

        # Update SRS
        old_stage = ctx.item.srs_stage
        srs_update = calculate_next_review(
            current_stage=ctx.item.srs_stage,
            correct=result.correct,
            hint_level=hint_level,
            timer_ratio=timer_ratio,
            ease_factor=ctx.item.ease_factor,
            today=today,
            config=self._srs_config,
        )

        self._item_repo.update_srs_state(
            item_id=ctx.item.id,
            srs_stage=srs_update.new_stage,
            ease_factor=srs_update.new_ease_factor,
            next_review_date=srs_update.next_review_date,
            correct_context_count=ctx.item.correct_context_count,
        )

        # Emit events
        self._bus.emit(
            ReviewAnswered(
                variation_id=variation_id,
                learning_item_id=ctx.item.id,
                correct=result.correct,
                item_used=result.item_used,
                hint_level=hint_level,
                timer_ratio=timer_ratio,
            )
        )
        self._bus.emit(
            SRSUpdated(
                learning_item_id=ctx.item.id,
                old_stage=old_stage,
                new_stage=srs_update.new_stage,
                next_review_date=srs_update.next_review_date,
            )
        )

        return result

    async def judge_review_retry(
        self,
        variation_id: UUID,
        attempt_number: int,
        audio: AudioData,
    ) -> ReviewResult:
        """Judge a retry attempt. Does NOT update SRS (initial attempt only)."""
        ctx = self._resolve_context(variation_id)
        result = await self._judge_audio(ctx, audio)

        # Record attempt (no SRS update)
        attempt = ReviewAttempt(
            variation_id=variation_id,
            learning_item_id=ctx.item.id,
            attempt_number=attempt_number,
            correct=result.correct,
            item_used=result.item_used,
            hint_level=0,
            timer_ratio=0.0,
        )
        self._attempt_repo.save_attempt(attempt)

        self._bus.emit(
            ReviewRetryJudged(
                variation_id=variation_id,
                attempt=attempt_number,
                correct=result.correct,
            )
        )

        return result

    def get_due_items(self, as_of: date) -> list[LearningItem]:
        """Get learning items due for review."""
        return list(self._item_repo.get_due_items(as_of, limit=self._srs_config.review_limit))
