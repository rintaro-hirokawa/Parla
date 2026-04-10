"""Tests for PhaseAViewModel."""

from uuid import uuid4

from parla.domain.audio import AudioData
from parla.domain.passage import Hint, Passage, Sentence
from parla.ui.screens.session.phase_a_view_model import PhaseAViewModel


def _make_audio() -> AudioData:
    return AudioData(
        data=b"\x00" * 100,
        format="wav",
        sample_rate=16000,
        channels=1,
        sample_width=2,
        duration_seconds=1.0,
    )


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


class FakeLearningItemQueryService:
    def __init__(self) -> None:
        self._sentence_items: dict = {}

    def set_items(self, sentence_id, items) -> None:
        self._sentence_items[sentence_id] = items

    def get_sentence_items(self, sentence_id):
        return self._sentence_items.get(sentence_id, ())


def _make_vm(
    passage: Passage | None = None,
    feedback_service: FakeFeedbackService | None = None,
    item_query: FakeLearningItemQueryService | None = None,
) -> tuple[PhaseAViewModel, FakeFeedbackService, FakeLearningItemQueryService]:
    fb_svc = feedback_service or FakeFeedbackService()
    iq_svc = item_query or FakeLearningItemQueryService()
    vm = PhaseAViewModel(
        feedback_service=fb_svc,
        item_query_service=iq_svc,
    )
    if passage:
        vm.load_passage(passage)
    return vm, fb_svc, iq_svc


class TestLoadPassage:
    def test_sentences_loaded(self, qtbot) -> None:
        passage = _make_passage(3)
        vm, _, _ = _make_vm(passage)

        assert vm.sentence_count == 3
        assert vm.current_index == 0

    def test_sentence_ja_list(self, qtbot) -> None:
        passage = _make_passage(2)
        vm, _, _ = _make_vm(passage)

        prompts = vm.sentence_ja_list()
        assert prompts == ["日本語0", "日本語1"]


class TestSentenceProgression:
    def test_submit_advances_to_next(self, qtbot) -> None:
        passage = _make_passage(3)
        vm, fb_svc, _ = _make_vm(passage)

        with qtbot.waitSignal(vm.current_sentence_changed, timeout=1000):
            vm.submit_recording(_make_audio())

        assert vm.current_index == 1
        assert len(fb_svc.record_calls) == 1

    def test_all_sentences_done(self, qtbot) -> None:
        passage = _make_passage(2)
        vm, fb_svc, _ = _make_vm(passage)

        vm.submit_recording(_make_audio())  # index 0 → 1

        with qtbot.waitSignal(vm.all_sentences_done, timeout=1000):
            vm.submit_recording(_make_audio())  # index 1 → done

        assert len(fb_svc.record_calls) == 2

    def test_record_sentence_called_with_correct_ids(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, fb_svc, _ = _make_vm(passage)

        vm.submit_recording(_make_audio())

        assert fb_svc.record_calls[0]["passage_id"] == passage.id
        assert fb_svc.record_calls[0]["sentence_id"] == passage.sentences[0].id


class TestHints:
    def test_hint_available_when_items_exist(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, _, iq_svc = _make_vm(passage)

        # Add items for the sentence
        iq_svc.set_items(passage.sentences[0].id, [{"pattern": "test"}])

        assert vm.has_hint_for_current() is True

    def test_hint_not_available_when_no_items(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, _, _ = _make_vm(passage)

        assert vm.has_hint_for_current() is False

    def test_get_hints_returns_items(self, qtbot) -> None:
        passage = _make_passage(1)
        vm, _, iq_svc = _make_vm(passage)

        items = ({"pattern": "verb tense"}, {"pattern": "article"})
        iq_svc.set_items(passage.sentences[0].id, items)

        result = vm.get_hint_items()
        assert len(result) == 2
