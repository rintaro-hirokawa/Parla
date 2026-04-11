"""Collects VariationReady events for a batch of review items."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from parla.domain.events import VariationGenerationFailed, VariationReady
from parla.ui.screens.session.speaking_item import SpeakingItem

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from parla.event_bus import EventBus
    from parla.services.review_service import ReviewService

logger = structlog.get_logger()


class VariationCollector:
    """Collects VariationReady events until a batch is complete.

    When all expected variations arrive, calls on_ready with the list of
    SpeakingItems and a mapping from variation_id to (learning_item_id, source_id).
    """

    def __init__(
        self,
        *,
        expected_items: list[tuple[UUID, UUID]],  # (item_id, source_id)
        review_service: ReviewService,
        event_bus: EventBus,
        on_ready: Callable[[list[SpeakingItem], dict[UUID, tuple[UUID, UUID]]], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._expected = {item_id for item_id, _ in expected_items}
        self._item_source_map = {item_id: source_id for item_id, source_id in expected_items}
        self._review_service = review_service
        self._bus = event_bus
        self._on_ready = on_ready
        self._on_error = on_error

        self._collected: dict[UUID, SpeakingItem] = {}  # item_id -> SpeakingItem
        self._variation_map: dict[UUID, tuple[UUID, UUID]] = {}  # variation_id -> (item_id, source_id)
        self._failed: set[UUID] = set()

        self._bus.on_sync(VariationReady)(self._on_variation_ready)
        self._bus.on_sync(VariationGenerationFailed)(self._on_variation_failed)

    def cleanup(self) -> None:
        """Unsubscribe from event bus."""
        self._bus.off_sync(VariationReady, self._on_variation_ready)
        self._bus.off_sync(VariationGenerationFailed, self._on_variation_failed)

    def _on_variation_ready(self, event: VariationReady) -> None:
        if event.learning_item_id not in self._expected:
            return
        if event.learning_item_id in self._collected:
            return

        variation = self._review_service.get_variation(event.variation_id)
        if variation is None:
            logger.error("variation_not_found", variation_id=str(event.variation_id))
            self._failed.add(event.learning_item_id)
            self._check_complete()
            return

        self._collected[event.learning_item_id] = SpeakingItem(
            id=variation.id,
            ja=variation.ja,
            hint1=variation.hint1,
            hint2=variation.hint2,
        )
        source_id = self._item_source_map[event.learning_item_id]
        self._variation_map[variation.id] = (event.learning_item_id, source_id)
        self._check_complete()

    def _on_variation_failed(self, event: VariationGenerationFailed) -> None:
        if event.learning_item_id not in self._expected:
            return
        logger.warning(
            "variation_failed_in_batch",
            item_id=str(event.learning_item_id),
            error=event.error_message,
        )
        self._failed.add(event.learning_item_id)
        self._check_complete()

    def _check_complete(self) -> None:
        total_done = len(self._collected) + len(self._failed)
        if total_done < len(self._expected):
            return

        self.cleanup()

        items = list(self._collected.values())
        if not items:
            if self._on_error:
                self._on_error("All variations in batch failed")
            return

        self._on_ready(items, self._variation_map)
