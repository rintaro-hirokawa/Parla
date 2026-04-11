"""Tests for RecordingViewModel."""

from uuid import uuid4

from parla.domain.audio import AudioData
from parla.ui.screens.session.recording_view_model import RecordingViewModel
from parla.ui.screens.session.speaking_item import SpeakingItem
from tests.conftest import make_wav_audio


def _make_audio() -> AudioData:
    return make_wav_audio()


def _make_items(count: int = 3) -> list[SpeakingItem]:
    return [
        SpeakingItem(
            id=uuid4(),
            ja=f"日本語{i}",
            hint1=f"hint1_{i}",
            hint2=f"hint2_{i}",
        )
        for i in range(count)
    ]


def _make_vm(
    items: list[SpeakingItem] | None = None,
) -> RecordingViewModel:
    vm = RecordingViewModel()
    if items:
        vm.load_items(items)
    return vm


class TestLoadItems:
    def test_items_loaded(self, qtbot) -> None:
        items = _make_items(3)
        vm = _make_vm(items)

        assert vm.sentence_count == 3
        assert vm.current_index == 0

    def test_sentence_ja_list(self, qtbot) -> None:
        items = _make_items(2)
        vm = _make_vm(items)

        prompts = vm.sentence_ja_list()
        assert prompts == ["日本語0", "日本語1"]


class TestCarousel:
    def test_prev_current_next(self, qtbot) -> None:
        items = _make_items(3)
        vm = _make_vm(items)

        assert vm.prev_ja == ""
        assert vm.current_ja == "日本語0"
        assert vm.next_ja == "日本語1"

    def test_middle_position(self, qtbot) -> None:
        items = _make_items(3)
        vm = _make_vm(items)

        vm.stop_recording(_make_audio())  # advance to 1

        assert vm.prev_ja == "日本語0"
        assert vm.current_ja == "日本語1"
        assert vm.next_ja == "日本語2"

    def test_last_position(self, qtbot) -> None:
        items = _make_items(2)
        vm = _make_vm(items)

        vm.stop_recording(_make_audio())  # advance to 1

        assert vm.prev_ja == "日本語0"
        assert vm.current_ja == "日本語1"
        assert vm.next_ja == ""


class TestRecordingSubmission:
    def test_submit_advances_to_next(self, qtbot) -> None:
        items = _make_items(3)
        vm = _make_vm(items)

        submitted = []
        vm.recording_submitted.connect(lambda iid, audio: submitted.append(iid))

        with qtbot.waitSignal(vm.current_sentence_changed, timeout=1000):
            vm.stop_recording(_make_audio())

        assert vm.current_index == 1
        assert len(submitted) == 1
        assert submitted[0] == items[0].id

    def test_all_sentences_done(self, qtbot) -> None:
        items = _make_items(2)
        vm = _make_vm(items)

        vm.stop_recording(_make_audio())  # index 0 → 1

        with qtbot.waitSignal(vm.all_sentences_done, timeout=1000):
            vm.stop_recording(_make_audio())  # index 1 → done

    def test_submitted_ids_match_items(self, qtbot) -> None:
        items = _make_items(1)
        vm = _make_vm(items)

        submitted = []
        vm.recording_submitted.connect(lambda iid, audio: submitted.append(iid))

        vm.stop_recording(_make_audio())

        assert submitted[0] == items[0].id


class TestHints:
    def test_reveal_hint1(self, qtbot) -> None:
        items = _make_items(1)
        vm = _make_vm(items)

        with qtbot.waitSignal(vm.hint_revealed, timeout=1000) as blocker:
            vm.reveal_hint()

        assert blocker.args == [1, "hint1_0"]
        assert vm.hint_level == 1

    def test_reveal_hint2(self, qtbot) -> None:
        items = _make_items(1)
        vm = _make_vm(items)

        vm.reveal_hint()  # hint1

        with qtbot.waitSignal(vm.hint_revealed, timeout=1000) as blocker:
            vm.reveal_hint()  # hint2

        assert blocker.args == [2, "hint2_0"]
        assert vm.hint_level == 2

    def test_reveal_hint_caps_at_2(self, qtbot) -> None:
        items = _make_items(1)
        vm = _make_vm(items)

        vm.reveal_hint()  # hint1
        vm.reveal_hint()  # hint2
        vm.reveal_hint()  # should be no-op

        assert vm.hint_level == 2

    def test_hint_level_resets_on_next_sentence(self, qtbot) -> None:
        items = _make_items(3)
        vm = _make_vm(items)

        vm.reveal_hint()  # hint_level = 1
        assert vm.hint_level == 1

        vm.stop_recording(_make_audio())  # advance to sentence 1

        assert vm.hint_level == 0

    def test_hint_level_resets_on_load_items(self, qtbot) -> None:
        items = _make_items(1)
        vm = _make_vm(items)

        vm.reveal_hint()
        assert vm.hint_level == 1

        vm.load_items(_make_items(2))
        assert vm.hint_level == 0

    def test_reveal_hint_noop_without_items(self, qtbot) -> None:
        vm = _make_vm()

        vm.reveal_hint()  # should not raise
        assert vm.hint_level == 0


class TestTimer:
    def test_timer_limit_calculated(self, qtbot) -> None:
        items = _make_items(1)
        vm = _make_vm(items)

        assert vm._timer_limit >= 15
        assert vm._timer_remaining == vm._timer_limit

    def test_timer_emits_on_load(self, qtbot) -> None:
        vm = RecordingViewModel()
        signals = []
        vm.timer_updated.connect(lambda r, t, s: signals.append((r, t, s)))
        vm.load_items(_make_items(1))

        assert len(signals) == 1
        assert signals[0][2] == "normal"
