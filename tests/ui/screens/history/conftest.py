"""Shared test fixtures for history screen tests."""

from datetime import date, datetime

from parla.services.query_models import (
    CalendarMarker,
    DailySummary,
    HistoryOverview,
    WpmDataPoint,
)


def make_overview() -> HistoryOverview:
    return HistoryOverview(
        calendar_markers=(
            CalendarMarker(date=date(2026, 4, 1), session_count=1),
            CalendarMarker(date=date(2026, 4, 5), session_count=2),
        ),
        wpm_trend=(
            WpmDataPoint(recorded_at=datetime(2026, 4, 1), wpm=110.0),
            WpmDataPoint(recorded_at=datetime(2026, 4, 5), wpm=125.0),
        ),
    )


def make_summary(target_date: date | None = None) -> DailySummary:
    return DailySummary(
        date=target_date or date(2026, 4, 5),
        session_count=2,
        passage_count=3,
        new_item_count=5,
        review_count=10,
        review_correct_count=8,
        average_wpm=130.0,
    )


class FakeHistoryQueryService:
    def __init__(self, overview=None, summary=None):
        self._overview = overview or HistoryOverview()
        self._summary = summary or DailySummary(date=date(2026, 1, 1))
        self.overview_calls: int = 0
        self.summary_calls: list[date] = []

    def get_history_overview(self):
        self.overview_calls += 1
        return self._overview

    def get_daily_summary(self, target_date):
        self.summary_calls.append(target_date)
        return self._summary
