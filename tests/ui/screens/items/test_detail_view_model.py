"""Tests for DetailViewModel (SCREEN-C3)."""

from datetime import date, datetime
from uuid import uuid4

from parla.domain.events import SRSUpdated
from parla.event_bus import EventBus
from parla.services.query_models import LearningItemDetail, ReviewHistoryEntry, WpmDataPoint
from parla.ui.screens.items.detail_view_model import DetailViewModel


def _make_detail(**overrides) -> LearningItemDetail:
    defaults = {
        "id": uuid4(),
        "pattern": "present perfect",
        "explanation": "現在完了形",
        "category": "文法",
        "status": "auto_stocked",
        "srs_stage": 2,
        "ease_factor": 1.3,
        "correct_context_count": 3,
        "source_title": "Test Source",
        "source_sentence_ja": "テスト文",
        "source_sentence_en": "Test sentence",
        "first_utterance": "I have been there",
        "review_history": (
            ReviewHistoryEntry(
                attempt_date=datetime(2026, 3, 1),
                variation_ja="テスト問題",
                variation_en="test variation",
                correct=True,
                item_used=True,
                hint_level=0,
                attempt_number=1,
            ),
        ),
        "wpm_trend": (
            WpmDataPoint(recorded_at=datetime(2026, 3, 1), wpm=120.0),
        ),
        "created_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    return LearningItemDetail(**defaults)


class FakeItemQueryService:
    def __init__(self, detail=None):
        self._detail = detail
        self.detail_calls: list = []

    def get_item_detail(self, item_id):
        self.detail_calls.append(item_id)
        return self._detail


class TestLoadDetail:
    def test_load_detail_emits_detail_loaded(self, qtbot) -> None:
        detail = _make_detail()
        service = FakeItemQueryService(detail=detail)
        vm = DetailViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.detail_loaded, timeout=1000) as blocker:
            vm.load_detail(detail.id)

        assert blocker.args == [detail]
        assert vm.detail is detail

    def test_load_detail_emits_not_found(self, qtbot) -> None:
        service = FakeItemQueryService(detail=None)
        vm = DetailViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.detail_not_found, timeout=1000):
            vm.load_detail(uuid4())

        assert vm.detail is None


class TestNavigation:
    def test_go_back_emits_navigate_back(self, qtbot) -> None:
        service = FakeItemQueryService()
        vm = DetailViewModel(EventBus(), service)

        with qtbot.waitSignal(vm.navigate_back, timeout=1000):
            vm.go_back()


class TestEventHandling:
    def test_srs_updated_reloads_matching_item(self, qtbot) -> None:
        item_id = uuid4()
        detail = _make_detail(id=item_id)
        service = FakeItemQueryService(detail=detail)
        bus = EventBus()
        vm = DetailViewModel(bus, service)
        vm.activate()
        vm.load_detail(item_id)

        service.detail_calls.clear()
        bus.emit(SRSUpdated(
            learning_item_id=item_id,
            old_stage=2, new_stage=3,
            next_review_date=date(2026, 5, 1),
        ))

        assert len(service.detail_calls) == 1
        assert service.detail_calls[0] == item_id

    def test_srs_updated_ignores_different_item(self, qtbot) -> None:
        item_id = uuid4()
        detail = _make_detail(id=item_id)
        service = FakeItemQueryService(detail=detail)
        bus = EventBus()
        vm = DetailViewModel(bus, service)
        vm.activate()
        vm.load_detail(item_id)

        service.detail_calls.clear()
        bus.emit(SRSUpdated(
            learning_item_id=uuid4(),  # different item
            old_stage=0, new_stage=1,
            next_review_date=date(2026, 5, 1),
        ))

        assert len(service.detail_calls) == 0
