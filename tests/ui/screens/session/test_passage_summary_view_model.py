"""Tests for PassageSummaryViewModel."""

from uuid import uuid4

from parla.services.query_models import PassageSummary
from parla.ui.screens.session.passage_summary_view_model import PassageSummaryViewModel


class FakeSessionQueryService:
    def __init__(self, summary: PassageSummary | None = None) -> None:
        self._summary = summary

    def get_passage_summary(self, passage_id):
        return self._summary


def _make_summary() -> PassageSummary:
    return PassageSummary(
        passage_id=uuid4(),
        topic="Daily routine",
        sentence_count=5,
        new_item_count=3,
        has_achievement=True,
        live_delivery_wpm=130.5,
        live_delivery_passed=True,
    )


class TestLoad:
    def test_summary_loaded(self, qtbot) -> None:
        summary = _make_summary()
        svc = FakeSessionQueryService(summary)
        vm = PassageSummaryViewModel(session_query_service=svc)

        with qtbot.waitSignal(vm.summary_loaded, timeout=1000):
            vm.load(summary.passage_id)

        assert vm.topic == "Daily routine"
        assert vm.sentence_count == 5
        assert vm.new_item_count == 3
        assert vm.has_achievement is True

    def test_load_not_found(self, qtbot) -> None:
        svc = FakeSessionQueryService(None)
        vm = PassageSummaryViewModel(session_query_service=svc)

        with qtbot.waitSignal(vm.error, timeout=1000):
            vm.load(uuid4())


class TestNavigation:
    def test_proceed_next_passage(self, qtbot) -> None:
        summary = _make_summary()
        svc = FakeSessionQueryService(summary)
        vm = PassageSummaryViewModel(session_query_service=svc)
        vm.load(summary.passage_id)
        vm.set_has_more_passages(True)

        with qtbot.waitSignal(vm.navigate_next_passage, timeout=1000):
            vm.proceed()

    def test_proceed_block_complete(self, qtbot) -> None:
        summary = _make_summary()
        svc = FakeSessionQueryService(summary)
        vm = PassageSummaryViewModel(session_query_service=svc)
        vm.load(summary.passage_id)
        vm.set_has_more_passages(False)

        with qtbot.waitSignal(vm.navigate_block_complete, timeout=1000):
            vm.proceed()
