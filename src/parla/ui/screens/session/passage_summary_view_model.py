"""ViewModel for passage completion summary (SCREEN-E9)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from uuid import UUID

    from parla.services.query_models import PassageSummary
    from parla.services.session_query_service import SessionQueryService

logger = structlog.get_logger()


class PassageSummaryViewModel(QObject):
    """Loads and exposes passage summary data."""

    summary_loaded = Signal()
    navigate_next_passage = Signal()
    navigate_block_complete = Signal()
    error = Signal(str)

    def __init__(self, *, session_query_service: SessionQueryService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._query = session_query_service
        self._summary: PassageSummary | None = None
        self._has_more = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def topic(self) -> str:
        return self._summary.topic if self._summary else ""

    @property
    def sentence_count(self) -> int:
        return self._summary.sentence_count if self._summary else 0

    @property
    def new_item_count(self) -> int:
        return self._summary.new_item_count if self._summary else 0

    @property
    def has_achievement(self) -> bool:
        return self._summary.has_achievement if self._summary else False

    @property
    def wpm(self) -> float | None:
        return self._summary.live_delivery_wpm if self._summary else None

    @property
    def passed(self) -> bool | None:
        return self._summary.live_delivery_passed if self._summary else None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def load(self, passage_id: UUID) -> None:
        logger.info("passage_summary_load", passage_id=str(passage_id))
        self._summary = self._query.get_passage_summary(passage_id)
        if self._summary is None:
            logger.warning("passage_summary_not_found", passage_id=str(passage_id))
            self.error.emit("Passage summary not found")
            return
        logger.info(
            "passage_summary_loaded",
            passage_id=str(passage_id),
            topic=self._summary.topic,
            sentence_count=self._summary.sentence_count,
            new_item_count=self._summary.new_item_count,
            has_achievement=self._summary.has_achievement,
            live_delivery_wpm=self._summary.live_delivery_wpm,
        )
        self.summary_loaded.emit()

    def set_has_more_passages(self, has_more: bool) -> None:
        self._has_more = has_more

    def proceed(self) -> None:
        if self._has_more:
            self.navigate_next_passage.emit()
        else:
            self.navigate_block_complete.emit()
