"""Learning history query service."""

from collections import defaultdict
from datetime import date

from parla.ports.learning_item_repository import LearningItemRepository
from parla.ports.practice_repository import PracticeRepository
from parla.ports.review_attempt_repository import ReviewAttemptRepository
from parla.ports.session_repository import SessionRepository
from parla.services.query_models import (
    CalendarMarker,
    DailySummary,
    HistoryOverview,
    WpmDataPoint,
)


class HistoryQueryService:
    """Read-only service for learning history display (C4 screen)."""

    def __init__(
        self,
        *,
        session_repo: SessionRepository,
        practice_repo: PracticeRepository,
        item_repo: LearningItemRepository,
        review_attempt_repo: ReviewAttemptRepository,
    ) -> None:
        self._session_repo = session_repo
        self._practice_repo = practice_repo
        self._item_repo = item_repo
        self._review_attempt_repo = review_attempt_repo

    def get_history_overview(self) -> HistoryOverview:
        """Get calendar markers and WPM trend for history tab."""
        markers = self._build_calendar_markers()
        wpm_trend = self._build_wpm_trend()
        return HistoryOverview(
            calendar_markers=tuple(markers),
            wpm_trend=tuple(wpm_trend),
        )

    def get_daily_summary(self, target_date: date) -> DailySummary:
        """Get learning summary for a specific date."""
        completed_states = self._session_repo.get_completed_states()
        day_states = [
            s for s in completed_states
            if s.completed_at is not None and s.completed_at.date() == target_date
        ]
        session_count = len(day_states)

        passage_count = 0
        for state in day_states:
            menu = self._session_repo.get_menu(state.menu_id)
            if menu is not None:
                passage_count += sum(
                    len(b.items) for b in menu.blocks if b.block_type == "new_material"
                )

        all_items = self._item_repo.get_stocked_items()
        new_item_count = sum(
            1 for i in all_items
            if i.created_at.date() == target_date
        )

        all_attempts = self._review_attempt_repo.get_all_attempts()
        day_attempts = [
            a for a in all_attempts
            if a.created_at.date() == target_date
        ]
        review_count = len(day_attempts)
        review_correct_count = sum(1 for a in day_attempts if a.correct)

        all_results = self._practice_repo.get_all_live_delivery_results()
        day_results = [
            r for r in all_results
            if r.created_at.date() == target_date
        ]
        average_wpm = 0.0
        if day_results:
            average_wpm = sum(r.wpm for r in day_results) / len(day_results)

        return DailySummary(
            date=target_date,
            session_count=session_count,
            passage_count=passage_count,
            new_item_count=new_item_count,
            review_count=review_count,
            review_correct_count=review_correct_count,
            average_wpm=average_wpm,
        )

    def _build_calendar_markers(self) -> list[CalendarMarker]:
        completed_states = self._session_repo.get_completed_states()
        date_counts: dict[date, int] = defaultdict(int)
        for state in completed_states:
            if state.completed_at is not None:
                date_counts[state.completed_at.date()] += 1

        return [
            CalendarMarker(date=d, session_count=count)
            for d, count in sorted(date_counts.items())
        ]

    def _build_wpm_trend(self) -> list[WpmDataPoint]:
        results = self._practice_repo.get_all_live_delivery_results()
        return [
            WpmDataPoint(recorded_at=r.created_at, wpm=r.wpm)
            for r in results
        ]
