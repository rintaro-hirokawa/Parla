"""Tests for SessionSummaryViewModel."""

from uuid import uuid4

from parla.domain.session import SessionPattern
from parla.services.query_models import SessionSummary
from parla.ui.screens.session.session_summary_view_model import SessionSummaryViewModel


class FakeSessionQueryService:
    def __init__(self, summary: SessionSummary | None = None) -> None:
        self._summary = summary

    def get_session_summary(self, session_id):
        return self._summary


def _make_summary() -> SessionSummary:
    return SessionSummary(
        session_id=uuid4(),
        pattern=SessionPattern.REVIEW_AND_NEW,
    )


class TestLoad:
    def test_summary_loaded(self, qtbot) -> None:
        summary = _make_summary()
        svc = FakeSessionQueryService(summary)
        vm = SessionSummaryViewModel(session_query_service=svc)

        with qtbot.waitSignal(vm.summary_loaded, timeout=1000):
            vm.load(summary.session_id)

        assert vm.pattern == SessionPattern.REVIEW_AND_NEW

    def test_load_not_found(self, qtbot) -> None:
        svc = FakeSessionQueryService(None)
        vm = SessionSummaryViewModel(session_query_service=svc)

        with qtbot.waitSignal(vm.error, timeout=1000):
            vm.load(uuid4())


class TestNavigation:
    def test_proceed_emits_navigate(self, qtbot) -> None:
        summary = _make_summary()
        svc = FakeSessionQueryService(summary)
        vm = SessionSummaryViewModel(session_query_service=svc)
        vm.load(summary.session_id)

        with qtbot.waitSignal(vm.navigate_to_menu, timeout=1000):
            vm.proceed()
