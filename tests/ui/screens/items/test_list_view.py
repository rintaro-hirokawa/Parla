"""Tests for ListView (SCREEN-C2)."""

from datetime import datetime
from uuid import uuid4

from PySide6.QtCore import Qt

from parla.event_bus import EventBus
from parla.services.query_models import LearningItemRow
from parla.ui.screens.items.list_view import ListView
from parla.ui.screens.items.list_view_model import ListViewModel


def _make_row(**overrides) -> LearningItemRow:
    defaults = {
        "id": uuid4(),
        "pattern": "test pattern",
        "explanation": "test explanation",
        "category": "文法",
        "status": "auto_stocked",
        "srs_stage": 0,
        "source_title": "Test Source",
        "source_sentence_ja": "テスト文",
        "created_at": datetime(2026, 1, 1),
    }
    defaults.update(overrides)
    return LearningItemRow(**defaults)


class FakeItemQueryService:
    def __init__(self, items=()):
        self._items = items

    def list_items(self, *, filter=None):
        return self._items


def _make_view(qtbot, items=()):
    bus = EventBus()
    service = FakeItemQueryService(items=items)
    vm = ListViewModel(bus, service)
    view = ListView(vm)
    qtbot.addWidget(view)
    vm.activate()
    vm.load_items()
    return view, vm, bus


class TestItemDisplay:
    def test_items_displayed_in_list(self, qtbot) -> None:
        rows = (_make_row(pattern="p1"), _make_row(pattern="p2"), _make_row(pattern="p3"))
        view, _vm, _bus = _make_view(qtbot, items=rows)

        assert view._item_list.count() == 3

    def test_empty_list(self, qtbot) -> None:
        view, _vm, _bus = _make_view(qtbot, items=())
        assert view._item_list.count() == 0

    def test_item_text_contains_pattern(self, qtbot) -> None:
        row = _make_row(pattern="present perfect")
        view, _vm, _bus = _make_view(qtbot, items=(row,))

        item_text = view._item_list.item(0).text()
        assert "present perfect" in item_text


class TestNavigation:
    def test_item_click_triggers_navigate(self, qtbot) -> None:
        item_id = uuid4()
        row = _make_row(id=item_id)
        view, vm, _bus = _make_view(qtbot, items=(row,))

        with qtbot.waitSignal(vm.navigate_to_detail, timeout=1000) as blocker:
            rect = view._item_list.visualItemRect(view._item_list.item(0))
            qtbot.mouseClick(view._item_list.viewport(), Qt.LeftButton, pos=rect.center())

        assert blocker.args == [item_id]


class TestFilter:
    def test_filter_combo_triggers_apply(self, qtbot) -> None:
        view, vm, _bus = _make_view(qtbot)

        # Select "文法" in category combo (index 1, after "全て")
        view._category_combo.setCurrentIndex(1)

        assert vm.current_filter is not None
        assert vm.current_filter.category == "文法"

    def test_clear_button_resets_filter(self, qtbot) -> None:
        view, vm, _bus = _make_view(qtbot)

        view._category_combo.setCurrentIndex(1)
        assert vm.current_filter is not None

        qtbot.mouseClick(view._clear_btn, Qt.LeftButton)

        assert vm.current_filter is None
        # Combos should be reset to index 0 ("全て")
        assert view._category_combo.currentIndex() == 0
        assert view._status_combo.currentIndex() == 0
        assert view._srs_combo.currentIndex() == 0
