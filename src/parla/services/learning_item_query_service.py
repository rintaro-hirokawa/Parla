"""Learning item list and detail query service."""

from collections.abc import Sequence
from uuid import UUID

import structlog

from parla.domain.learning_item import LearningItem
from parla.ports.feedback_repository import FeedbackRepository
from parla.ports.learning_item_repository import LearningItemRepository
from parla.ports.source_repository import SourceRepository
from parla.services.query_models import (
    LearningItemDetail,
    LearningItemFilter,
    LearningItemRow,
    SentenceItemRow,
)

logger = structlog.get_logger()


class LearningItemQueryService:
    """Service for learning item queries and basic CRUD."""

    def __init__(
        self,
        *,
        item_repo: LearningItemRepository,
        source_repo: SourceRepository,
        feedback_repo: FeedbackRepository,
    ) -> None:
        self._item_repo = item_repo
        self._source_repo = source_repo
        self._feedback_repo = feedback_repo

    # --- Direct item access (used by ViewModels) ---

    def get_item(self, item_id: UUID) -> LearningItem | None:
        """Get a single learning item by ID."""
        return self._item_repo.get_item(item_id)

    def get_items_by_sentence(self, sentence_id: UUID) -> Sequence[LearningItem]:
        """Get learning items associated with a sentence."""
        return self._item_repo.get_items_by_sentence(sentence_id)

    def update_item(self, item_id: UUID, pattern: str, explanation: str) -> None:
        """Update a learning item's pattern and explanation."""
        self._item_repo.update_item(item_id, pattern, explanation)

    def dismiss_item(self, item_id: UUID) -> None:
        """Dismiss a learning item."""
        self._item_repo.dismiss_item(item_id)

    def resolve_review_pairs(
        self, item_ids: Sequence[UUID]
    ) -> list[tuple[UUID, UUID]]:
        """Resolve learning_item_ids to (item_id, source_id) pairs."""
        pairs: list[tuple[UUID, UUID]] = []
        for item_id in item_ids:
            item = self._item_repo.get_item(item_id)
            if item is None:
                logger.warning("item_not_found", item_id=str(item_id))
                continue
            source = self._source_repo.get_source_by_sentence_id(
                item.source_sentence_id
            )
            if source is None:
                logger.warning("source_not_found", item_id=str(item_id))
                continue
            pairs.append((item_id, source.id))
        return pairs

    # --- List & detail queries ---

    def list_items(
        self,
        *,
        filter: LearningItemFilter | None = None,
    ) -> tuple[LearningItemRow, ...]:
        """List stocked learning items with optional filters."""
        items = list(self._item_repo.get_stocked_items())

        if filter is not None:
            items = self._apply_filter(items, filter)

        return tuple(self._to_row(item) for item in items)

    def get_sentence_items(self, sentence_id: UUID) -> tuple[SentenceItemRow, ...]:
        """Get learning items associated with a sentence."""
        items = self._item_repo.get_items_by_sentence(sentence_id)
        return tuple(
            SentenceItemRow(
                id=item.id,
                pattern=item.pattern,
                explanation=item.explanation,
                category=item.category,
                status=item.status,
                is_reappearance=item.is_reappearance,
            )
            for item in items
        )

    def get_item_detail(self, item_id: UUID) -> LearningItemDetail | None:
        """Get detailed info for a single learning item (C3 screen)."""
        item = self._item_repo.get_item(item_id)
        if item is None:
            return None

        source_title, sentence_ja, sentence_en = self._resolve_source_info(item)
        first_utterance = self._get_first_utterance(item)

        return LearningItemDetail(
            id=item.id,
            pattern=item.pattern,
            explanation=item.explanation,
            category=item.category,
            sub_tag=item.sub_tag,
            status=item.status,
            srs_stage=item.srs_stage,
            ease_factor=item.ease_factor,
            next_review_date=item.next_review_date,
            correct_context_count=item.correct_context_count,
            source_title=source_title,
            source_sentence_ja=sentence_ja,
            source_sentence_en=sentence_en,
            first_utterance=first_utterance,
            created_at=item.created_at,
        )

    def _resolve_source_info(self, item: LearningItem) -> tuple[str, str, str]:
        source_title = ""
        sentence_ja = ""
        sentence_en = ""

        source = self._source_repo.get_source_by_sentence_id(item.source_sentence_id)
        if source is not None:
            source_title = source.title

        sentence = self._source_repo.get_sentence(item.source_sentence_id)
        if sentence is not None:
            sentence_ja = sentence.ja
            sentence_en = sentence.en

        return source_title, sentence_ja, sentence_en

    def _get_first_utterance(self, item: LearningItem) -> str:
        feedback = self._feedback_repo.get_feedback_by_sentence(item.source_sentence_id)
        if feedback is None:
            return ""
        return feedback.user_utterance

    def _apply_filter(
        self, items: list[LearningItem], f: LearningItemFilter
    ) -> list[LearningItem]:
        if f.category is not None:
            items = [i for i in items if i.category == f.category]
        if f.status is not None:
            items = [i for i in items if i.status == f.status]
        if f.srs_stage is not None:
            items = [i for i in items if i.srs_stage == f.srs_stage]
        if f.source_id is not None:
            source_sentence_ids = self._get_sentence_ids_for_source(f.source_id)
            items = [i for i in items if i.source_sentence_id in source_sentence_ids]
        return items

    def _get_sentence_ids_for_source(self, source_id: UUID) -> set[UUID]:
        passages = self._source_repo.get_passages_by_source(source_id)
        return {s.id for p in passages for s in p.sentences}

    def _to_row(self, item: LearningItem) -> LearningItemRow:
        source_title, sentence_ja, _ = self._resolve_source_info(item)
        return LearningItemRow(
            id=item.id,
            pattern=item.pattern,
            explanation=item.explanation,
            category=item.category,
            sub_tag=item.sub_tag,
            status=item.status,
            srs_stage=item.srs_stage,
            next_review_date=item.next_review_date,
            source_title=source_title,
            source_sentence_ja=sentence_ja,
            created_at=item.created_at,
        )
