"""Tests for ReviewViewModel."""

from datetime import date
from uuid import UUID, uuid4

from parla.domain.audio import AudioData
from parla.domain.events import (
    ReviewAnswered,
    ReviewRetryJudged,
    VariationGenerationFailed,
    VariationReady,
)
from parla.domain.variation import Variation
from parla.event_bus import EventBus
from parla.ui.screens.session.review_view_model import ReviewViewModel
from parla.ui.screens.session.session_context import SessionContext
from tests.conftest import make_wav_audio


def _make_audio() -> AudioData:
    return make_wav_audio()


def _make_variation(
    learning_item_id: UUID | None = None,
    source_id: UUID | None = None,
) -> Variation:
    return Variation(
        learning_item_id=learning_item_id or uuid4(),
        source_id=source_id or uuid4(),
        ja="彼は自分自身でテストした",
        en="He tested himself",
        hint1="He ... himself",
        hint2="He + 動詞(過去形) + himself",
    )


class FakeReviewService:
    """Fake matching ReviewService's API used by ViewModel."""

    def __init__(self) -> None:
        self.request_variation_calls: list[tuple[UUID, UUID]] = []
        self.judge_review_calls: list[dict] = []
        self.judge_review_retry_calls: list[dict] = []
        self._variations: dict[UUID, Variation] = {}

    def add_variation(self, v: Variation) -> None:
        self._variations[v.id] = v

    def get_variation(self, variation_id: UUID) -> Variation | None:
        return self._variations.get(variation_id)

    def request_variation(self, learning_item_id: UUID, source_id: UUID) -> None:
        self.request_variation_calls.append((learning_item_id, source_id))

    async def judge_review(
        self, variation_id: UUID, audio: AudioData, hint_level: int, timer_ratio: float, today: date,
    ) -> None:
        self.judge_review_calls.append({
            "variation_id": variation_id,
            "hint_level": hint_level,
            "timer_ratio": timer_ratio,
        })

    async def judge_review_retry(self, variation_id: UUID, attempt_number: int, audio: AudioData) -> None:
        self.judge_review_retry_calls.append({
            "variation_id": variation_id,
            "attempt_number": attempt_number,
        })


class FakeVariationRepo:
    """Minimal fake for looking up variations."""

    def __init__(self) -> None:
        self._variations: dict[UUID, Variation] = {}

    def add(self, v: Variation) -> None:
        self._variations[v.id] = v

    def get_variation(self, variation_id: UUID) -> Variation | None:
        return self._variations.get(variation_id)


def _make_vm(
    event_bus: EventBus | None = None,
    review_service: FakeReviewService | None = None,
    session_context: SessionContext | None = None,
) -> tuple[ReviewViewModel, EventBus, FakeReviewService, SessionContext]:
    bus = event_bus or EventBus()
    svc = review_service or FakeReviewService()
    ctx = session_context or SessionContext()
    vm = ReviewViewModel(
        event_bus=bus,
        review_service=svc,
        session_context=ctx,
    )
    return vm, bus, svc, ctx


class TestStartReview:
    def test_request_variation_called(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()

        assert len(svc.request_variation_calls) == 1
        assert svc.request_variation_calls[0] == (item_id, source_id)


class TestVariationReady:
    def test_question_ready_emitted(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()

        with qtbot.waitSignal(vm.question_ready, timeout=1000):
            bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))

    def test_question_data_correct(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()

        bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))

        assert vm.current_ja == "彼は自分自身でテストした"

    def test_variation_failed_emits_error(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()

        with qtbot.waitSignal(vm.error, timeout=1000):
            bus.emit(VariationGenerationFailed(learning_item_id=item_id, error_message="LLM error"))


class TestHints:
    def test_reveal_hint_increments_level(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()
        bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))

        with qtbot.waitSignal(vm.hint_revealed, timeout=1000) as blocker:
            vm.reveal_hint()
        assert blocker.args == [1, "He ... himself"]

    def test_reveal_hint2(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()
        bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))

        vm.reveal_hint()  # hint1
        with qtbot.waitSignal(vm.hint_revealed, timeout=1000) as blocker:
            vm.reveal_hint()  # hint2
        assert blocker.args == [2, "He + 動詞(過去形) + himself"]

    def test_no_hint_beyond_level2(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()
        bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))

        vm.reveal_hint()
        vm.reveal_hint()
        with qtbot.assertNotEmitted(vm.hint_revealed):
            vm.reveal_hint()


class TestReviewResult:
    def test_correct_emits_result(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()
        bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))

        with qtbot.waitSignal(vm.result_ready, timeout=1000) as blocker:
            bus.emit(ReviewAnswered(
                variation_id=variation.id,
                learning_item_id=item_id,
                correct=True,
                item_used=True,
                hint_level=0,
                timer_ratio=0.5,
            ))
        assert blocker.args[0] is True  # correct

    def test_incorrect_emits_result(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()
        bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))

        with qtbot.waitSignal(vm.result_ready, timeout=1000) as blocker:
            bus.emit(ReviewAnswered(
                variation_id=variation.id,
                learning_item_id=item_id,
                correct=False,
                item_used=False,
                hint_level=0,
                timer_ratio=0.8,
            ))
        assert blocker.args[0] is False
        assert blocker.args[1] == "He tested himself"  # model answer


class TestRetry:
    def test_retry_result_emitted(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()
        bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))
        bus.emit(ReviewAnswered(
            variation_id=variation.id, learning_item_id=item_id,
            correct=False, item_used=False, hint_level=0, timer_ratio=0.5,
        ))

        with qtbot.waitSignal(vm.retry_result, timeout=1000) as blocker:
            bus.emit(ReviewRetryJudged(variation_id=variation.id, attempt=2, correct=True))
        assert blocker.args == [2, True]


class TestAllDone:
    def test_all_done_after_last_item(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()
        variation = _make_variation(learning_item_id=item_id, source_id=source_id)
        svc.add_variation(variation)

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.request_next()
        bus.emit(VariationReady(variation_id=variation.id, learning_item_id=item_id))

        # Correct answer triggers advance
        bus.emit(ReviewAnswered(
            variation_id=variation.id, learning_item_id=item_id,
            correct=True, item_used=True, hint_level=0, timer_ratio=0.5,
        ))

        # After correct, vm should auto-advance. Since last item, emit all_done
        with qtbot.waitSignal(vm.all_done, timeout=1000):
            vm.advance()  # Called by View after 1.5s timer


class TestDeactivate:
    def test_deactivate_unsubscribes(self, qtbot) -> None:
        vm, bus, svc, ctx = _make_vm()
        item_id = uuid4()
        source_id = uuid4()

        vm.start_review([(item_id, source_id)])
        vm.activate()
        vm.deactivate()

        with qtbot.assertNotEmitted(vm.question_ready):
            bus.emit(VariationReady(variation_id=uuid4(), learning_item_id=item_id))
