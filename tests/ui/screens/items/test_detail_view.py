"""Tests for DetailView (SCREEN-C3)."""

from PySide6.QtCore import Qt

from parla.event_bus import EventBus
from parla.ui.screens.items.detail_view import DetailView
from parla.ui.screens.items.detail_view_model import DetailViewModel
from tests.ui.screens.items.conftest import FakeItemQueryService, make_detail


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
        detail = make_detail()
        view, _vm, _bus = _make_view(qtbot, detail=detail)

        assert "present perfect" in view._title_label.text()
        assert "文法" in view._category_label.text()
        assert "2" in view._srs_label.text()

    def test_source_info_displayed(self, qtbot) -> None:
        detail = make_detail()
        view, _vm, _bus = _make_view(qtbot, detail=detail)

        assert "Test Source" in view._source_title_label.text()
        assert "テスト文" in view._source_ja_label.text()
        assert "Test sentence" in view._source_en_label.text()


class TestNavigation:
    def test_back_button_emits_navigate_back(self, qtbot) -> None:
        detail = make_detail()
        view, vm, _bus = _make_view(qtbot, detail=detail)

        with qtbot.waitSignal(vm.navigate_back, timeout=1000):
            qtbot.mouseClick(view._back_btn, Qt.LeftButton)
