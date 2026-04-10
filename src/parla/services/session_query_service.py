"""Session, menu, and passage summary query service."""

from datetime import date
from uuid import UUID

from parla.ports.learning_item_repository import LearningItemRepository
from parla.ports.practice_repository import PracticeRepository
from parla.ports.review_attempt_repository import ReviewAttemptRepository
from parla.ports.session_repository import SessionRepository
from parla.ports.source_repository import SourceRepository
from parla.services.query_models import (
    ActiveSourceOption,
    MenuBlockSummary,
    MenuPreview,
    PassageSummary,
    SessionSummary,
    SessionSummaryBlock,
    TodayDashboard,
)


class SessionQueryService:
    """Read-only service for session/menu/passage summary display."""

    def __init__(
        self,
        *,
        session_repo: SessionRepository,
        source_repo: SourceRepository,
        practice_repo: PracticeRepository,
        item_repo: LearningItemRepository,
        review_attempt_repo: ReviewAttemptRepository,
    ) -> None:
        self._session_repo = session_repo
        self._source_repo = source_repo
        self._practice_repo = practice_repo
        self._item_repo = item_repo
        self._review_attempt_repo = review_attempt_repo

    def get_today_dashboard(self, *, today: date) -> TodayDashboard:
        """Get today's learning tab data (C1 screen)."""
        menu = self._session_repo.get_menu_for_date(today)
        active_state = self._session_repo.get_active_state()

        if menu is None:
            return TodayDashboard(
                has_resumable_session=active_state is not None,
                resumable_session_id=active_state.id if active_state else None,
            )

        blocks = tuple(
            MenuBlockSummary(
                block_type=b.block_type,
                item_count=len(b.items),
                estimated_minutes=b.estimated_minutes,
            )
            for b in menu.blocks
        )
        total = sum(b.estimated_minutes for b in blocks)

        source_title = ""
        if menu.source_id:
            source = self._source_repo.get_source(menu.source_id)
            if source:
                source_title = source.title

        return TodayDashboard(
            has_menu=True,
            menu_confirmed=menu.confirmed,
            menu_id=menu.id,
            pattern=menu.pattern,
            blocks=blocks,
            total_estimated_minutes=total,
            source_title=source_title,
            has_resumable_session=active_state is not None,
            resumable_session_id=active_state.id if active_state else None,
        )

    def get_passage_summary(self, passage_id: UUID) -> PassageSummary | None:
        """Get passage completion summary (E9 screen)."""
        passage = self._source_repo.get_passage(passage_id)
        if passage is None:
            return None

        new_items: list[object] = []
        for sentence in passage.sentences:
            items = self._item_repo.get_items_by_sentence(sentence.id)
            new_items.extend(items)

        has_achievement = self._practice_repo.has_achievement(passage_id)

        results = self._practice_repo.get_live_delivery_results(passage_id)
        last_result = results[-1] if results else None

        return PassageSummary(
            passage_id=passage.id,
            topic=passage.topic,
            sentence_count=len(passage.sentences),
            new_item_count=len(new_items),
            has_achievement=has_achievement,
            live_delivery_wpm=last_result.wpm if last_result else None,
            live_delivery_passed=last_result.passed if last_result else None,
        )

    def get_session_summary(self, session_id: UUID) -> SessionSummary | None:
        """Get session completion summary (F1 screen)."""
        state = self._session_repo.get_state(session_id)
        if state is None:
            return None

        menu = self._session_repo.get_menu(state.menu_id)
        if menu is None:
            return None

        blocks = tuple(
            SessionSummaryBlock(
                block_type=b.block_type,
                item_count=len(b.items),
            )
            for b in menu.blocks
        )

        duration_minutes = 0.0
        if state.started_at and state.completed_at:
            delta = state.completed_at - state.started_at
            duration_minutes = delta.total_seconds() / 60

        return SessionSummary(
            session_id=state.id,
            pattern=menu.pattern,
            blocks=blocks,
            duration_minutes=duration_minutes,
        )

    def get_menu_preview(self, menu_id: UUID) -> MenuPreview | None:
        """Get menu preview for confirmation (F2 screen)."""
        menu = self._session_repo.get_menu(menu_id)
        if menu is None:
            return None

        blocks = tuple(
            MenuBlockSummary(
                block_type=b.block_type,
                item_count=len(b.items),
                estimated_minutes=b.estimated_minutes,
            )
            for b in menu.blocks
        )
        total = sum(b.estimated_minutes for b in blocks)

        source_title = ""
        if menu.source_id:
            source = self._source_repo.get_source(menu.source_id)
            if source:
                source_title = source.title

        active_sources = self._source_repo.get_active_sources()
        active_options = tuple(
            ActiveSourceOption(
                id=s.id,
                title=s.title,
                cefr_level=s.cefr_level,
                remaining_passages=self._count_remaining_passages(s.id),
            )
            for s in active_sources
        )

        return MenuPreview(
            menu_id=menu.id,
            target_date=menu.target_date,
            pattern=menu.pattern,
            blocks=blocks,
            total_estimated_minutes=total,
            source_id=menu.source_id,
            source_title=source_title,
            pending_review_count=menu.pending_review_count,
            active_sources=active_options,
        )

    def _count_remaining_passages(self, source_id: UUID) -> int:
        passages = self._source_repo.get_passages_by_source(source_id)
        return sum(1 for p in passages if not self._practice_repo.has_achievement(p.id))
