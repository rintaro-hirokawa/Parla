"""Tests for DetailView (SCREEN-C3)."""

from datetime import datetime
from uuid import uuid4

from PySide6.QtCore import Qt

from parla.event_bus import EventBus
from parla.services.query_models import LearningItemDetail, ReviewHistoryEntry, WpmDataPoint
from parla.ui.screens.items.detail_view import DetailView
from parla.ui.screens.items.detail_view_model import DetailViewModel


def _make_detail(**overrides) -> LearningItemDetail:
    defaults = {
        "id": uuid4(),
        "pattern": "present perfect",
        "explanation": "現在完了形",
        "category": "文法",
        "sub_tag": "tense",
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
                variation_ja="テスト問題1",
                variation_en="test variation 1",
                correct=True,
                item_used=True,
                hint_level=0,
                attempt_number=1,
            ),
            ReviewHistoryEntry(
                attempt_date=datetime(2026, 3, 5),
                variation_ja="テスト問題2",
                variation_en="test variation 2",
                correct=False,
                item_used=False,
                hint_level=1,
                attempt_number=1,
            ),
        ),
        "wpm_trend": (
            WpmDataPoint(recorded_at=datetime(2026, 3, 1), wpm=120.0),
            WpmDataPoint(recorded_at=datetime(2026, 3, 5), wpm=135.0),
        ),
        "created_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    return LearningItemDetail(**defaults)


class FakeItemQueryService:
    def __init__(self, detail=None):
        self._detail = detail

    def get_item_detail(self, item_id):
        return self._detail


def _make_view(qtbot, detail=None):
    bus = EventBus()
    service = FakeItemQueryService(detail=detail)
    vm = DetailViewModel(bus, service)
    view = DetailView(vm)
    qtbot.addWidget(view)
    vm.activate()
    if detail is not None:
        vm.load_detail(detail.id)
    return view, vm, bus


class TestDetailDisplay:
    def test_detail_labels_populated(self, qtbot) -> None:
        detail = _make_detail()
        view, _vm, _bus = _make_view(qtbot, detail=detail)

        assert "present perfect" in view._title_label.text()
        assert "文法" in view._category_label.text()
        assert "2" in view._srs_label.text()
        assert "I have been there" in view._first_utterance_label.text()

    def test_review_table_rows(self, qtbot) -> None:
        detail = _make_detail()
        view, _vm, _bus = _make_view(qtbot, detail=detail)

        assert view._review_table.rowCount() == 2

    def test_wpm_chart_receives_data(self, qtbot) -> None:
        detail = _make_detail()
        view, _vm, _bus = _make_view(qtbot, detail=detail)

        assert len(view._wpm_chart.data_points) == 2

    def test_source_info_displayed(self, qtbot) -> None:
        detail = _make_detail()
        view, _vm, _bus = _make_view(qtbot, detail=detail)

        assert "Test Source" in view._source_title_label.text()
        assert "テスト文" in view._source_ja_label.text()
        assert "Test sentence" in view._source_en_label.text()


class TestNavigation:
    def test_back_button_emits_navigate_back(self, qtbot) -> None:
        detail = _make_detail()
        view, vm, _bus = _make_view(qtbot, detail=detail)

        with qtbot.waitSignal(vm.navigate_back, timeout=1000):
            qtbot.mouseClick(view._back_btn, Qt.LeftButton)
