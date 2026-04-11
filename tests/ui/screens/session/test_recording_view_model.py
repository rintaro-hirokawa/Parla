"""Tests for RecordingViewModel."""

from uuid import uuid4

from parla.domain.audio import AudioData
from parla.domain.passage import Hint, Passage, Sentence
from parla.ui.screens.session.recording_view_model import RecordingViewModel
from tests.conftest import make_wav_audio


def _make_audio() -> AudioData:
    return make_wav_audio()


def _make_passage(sentence_count: int = 3) -> Passage:
    source_id = uuid4()
    sentences = tuple(
        Sentence(
            order=i,
            ja=f"日本語{i}",
            en=f"English sentence {i}",
            hints=Hint(hint1=f"hint1_{i}", hint2=f"hint2_{i}"),
        )
        for i in range(sentence_count)
    )
    return Passage(
        source_id=source_id,
        order=0,
        topic="test topic",
        passage_type="dialogue",
        sentences=sentences,
    )


class FakeFeedbackService:
    def __init__(self) -> None:
        self.record_calls: list[dict] = []

    def record_sentence(self, passage_id, sentence_id, audio) -> None:
        self.record_calls.append({
            "passage_id": passage_id,
            "sentence_id": sentence_id,
        })


def _make_vm(
    passage: Passage | None = None,
    feedback_service: FakeFeedbackService | None = None,
) -> tuple[RecordingViewModel, FakeFeedbackService]:
    fb_svc = feedback_service or FakeFeedbackService()
    vm = RecordingViewModel(
        feedback_service=fb_svc,
    )
    if passage:
        vm.load_passage(passage)
    return vm, fb_svc


class TestLoadPassage:
    def test_sentences_loaded(self, qtbot) -> None:
        passage = _make_passage(3)
        vm, _ = _make_vm(passage)

        assert vm.sentence_count == 3
        assert vm.current_index == 0

    def test_sentence_ja_list(self, qtbot) -> None:
        passage = _make_passage(2)
        vm, _ = _make_vm(passage)

        prompts = vm.sentence_ja_list()
        assert prompts == ["日本語0", "日本語1"]


class TestSentenceProgression:
    def test_submit_advances_to_next(self, qtbot) -> None:
        passage = _make_passage(3)
        vm, fb_svc = _make_vm(passage)

        with qtbot.waitSignal(vm.current_sentence_changed, timeout=1000):
            vm.submit_recording(_make_audio())

        assert vm.current_index == 1
        assert len(fb_svc.record_calls) == 1

    def test_all_sentences_done(self, qtbot) -> None:
        passage = _make_passage(2)
        vm, fb_svc = _make_vm(passage)

        vm.submit_recording(_make_audio())  # index 0 → 1

        with qtbot.waitSignal(vm.all_sentences_done, timeout=1000):
            vm.submit_recording(_make_audio())  # index 1 → done

        assert len(fb_svc.record_calls) == 2

    def test_record_sentence_called_with_correct_ids(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, fb_svc = _make_vm(passage)

        vm.submit_recording(_make_audio())

        assert fb_svc.record_calls[0]["passage_id"] == passage.id
        assert fb_svc.record_calls[0]["sentence_id"] == passage.sentences[0].id


class TestHints:
    def test_reveal_hint1(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, _ = _make_vm(passage)

        with qtbot.waitSignal(vm.hint_revealed, timeout=1000) as blocker:
            vm.reveal_hint()

        assert blocker.args == [1, "hint1_0"]
        assert vm.hint_level == 1

    def test_reveal_hint2_includes_hint1(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, _ = _make_vm(passage)

        vm.reveal_hint()  # hint1

        with qtbot.waitSignal(vm.hint_revealed, timeout=1000) as blocker:
            vm.reveal_hint()  # hint2

        assert blocker.args == [2, "hint1_0\nhint2_0"]
        assert vm.hint_level == 2

    def test_reveal_hint_caps_at_2(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, _ = _make_vm(passage)

        vm.reveal_hint()  # hint1
        vm.reveal_hint()  # hint2
        vm.reveal_hint()  # should be no-op

        assert vm.hint_level == 2

    def test_hint_level_resets_on_next_sentence(self, qtbot) -> None:
        passage = _make_passage(3)
        vm, _ = _make_vm(passage)

        vm.reveal_hint()  # hint_level = 1
        assert vm.hint_level == 1

        vm.submit_recording(_make_audio())  # advance to sentence 1

        assert vm.hint_level == 0

    def test_hint_level_resets_on_load_passage(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, _ = _make_vm(passage)

        vm.reveal_hint()
        assert vm.hint_level == 1

        vm.load_passage(_make_passage(2))
        assert vm.hint_level == 0

    def test_reveal_hint_noop_without_passage(self, qtbot) -> None:
        vm, _ = _make_vm()

        vm.reveal_hint()  # should not raise
        assert vm.hint_level == 0
