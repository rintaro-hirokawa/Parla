"""Tests for ItemEditViewModel."""

from uuid import UUID, uuid4

from parla.domain.learning_item import LearningItem
from parla.ui.screens.session.item_edit_view_model import ItemEditViewModel


def _make_item(
    pattern: str = "past tense",
    explanation: str = "use past tense for completed actions",
) -> LearningItem:
    return LearningItem(
        pattern=pattern,
        explanation=explanation,
        category="文法",
        priority=3,
        source_sentence_id=uuid4(),
        is_reappearance=False,
        status="auto_stocked",
    )


class FakeItemRepo:
    def __init__(self) -> None:
        self._items: dict[UUID, LearningItem] = {}
        self.saved: list[LearningItem] = []
        self.dismissed: list[UUID] = []

    def add(self, item: LearningItem) -> None:
        self._items[item.id] = item

    def get_items_by_sentence(self, sentence_id: UUID) -> list[LearningItem]:
        return [i for i in self._items.values() if i.source_sentence_id == sentence_id]

    def save_items(self, items: list[LearningItem]) -> None:
        self.saved.extend(items)
        for item in items:
            self._items[item.id] = item

    def update_item(self, item_id: UUID, pattern: str, explanation: str) -> None:
        if item_id in self._items:
            old = self._items[item_id]
            self._items[item_id] = old.model_copy(update={"pattern": pattern, "explanation": explanation})

    def dismiss_item(self, item_id: UUID) -> None:
        self.dismissed.append(item_id)
        if item_id in self._items:
            old = self._items[item_id]
            self._items[item_id] = old.model_copy(update={"status": "dismissed"})


def _make_vm(
    sentence_id: UUID | None = None,
    items: list[LearningItem] | None = None,
) -> tuple[ItemEditViewModel, FakeItemRepo, UUID]:
    repo = FakeItemRepo()
    sid = sentence_id or uuid4()
    if items:
        for item in items:
            new_item = item.model_copy(update={"source_sentence_id": sid})
            repo.add(new_item)
    vm = ItemEditViewModel(item_query=repo)
    vm.load_items(sid)
    return vm, repo, sid


class TestLoadItems:
    def test_items_loaded(self, qtbot) -> None:
        item = _make_item()
        vm, repo, sid = _make_vm(items=[item])

        assert vm.item_count == 1

    def test_no_items(self, qtbot) -> None:
        vm, repo, sid = _make_vm()
        assert vm.item_count == 0


class TestEditItem:
    def test_update_item(self, qtbot) -> None:
        item = _make_item()
        vm, repo, sid = _make_vm(items=[item])

        items = vm.items
        item_id = items[0].id

        with qtbot.waitSignal(vm.item_updated, timeout=1000):
            vm.update_item(item_id, "present perfect", "for recent events")

    def test_dismiss_item(self, qtbot) -> None:
        item = _make_item()
        vm, repo, sid = _make_vm(items=[item])

        items = vm.items
        item_id = items[0].id

        with qtbot.waitSignal(vm.item_dismissed, timeout=1000):
            vm.dismiss_item(item_id)

        assert item_id in repo.dismissed


class TestDismissSheet:
    def test_dismiss_signal(self, qtbot) -> None:
        vm, _, _ = _make_vm()

        with qtbot.waitSignal(vm.dismissed, timeout=1000):
            vm.dismiss()
