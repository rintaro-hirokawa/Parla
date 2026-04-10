"""Tests for PhaseBViewModel."""

from uuid import UUID, uuid4

from parla.domain.audio import AudioData
from parla.domain.events import (
    FeedbackFailed,
    FeedbackReady,
    LearningItemStocked,
    RetryJudged,
)
from parla.domain.feedback import SentenceFeedback
from parla.event_bus import EventBus
from parla.ui.screens.session.phase_b_view_model import PhaseBViewModel
from parla.ui.screens.session.session_context import SessionContext


def _make_audio() -> AudioData:
    return AudioData(
        data=b"\x00" * 100,
        format="wav",
        sample_rate=16000,
        channels=1,
        sample_width=2,
        duration_seconds=1.0,
    )


class FakeFeedbackService:
    def __init__(self) -> None:
        self.retry_calls: list[dict] = []

    async def judge_retry(self, sentence_id: UUID, attempt: int, audio: AudioData) -> None:
        self.retry_calls.append({
            "sentence_id": sentence_id,
            "attempt": attempt,
        })


class FakePracticeService:
    def __init__(self) -> None:
        self.model_audio_calls: list[UUID] = []
        self._should_skip = False

    def request_model_audio(self, passage_id: UUID) -> None:
        self.model_audio_calls.append(passage_id)

    def should_skip(self, new_item_count: int, wpm: float, cefr_level: str) -> bool:
        return self._should_skip


class FakeFeedbackRepo:
    def __init__(self) -> None:
        self._feedbacks: dict[UUID, SentenceFeedback] = {}

    def add(self, fb: SentenceFeedback) -> None:
        self._feedbacks[fb.sentence_id] = fb

    def get_feedback_by_sentence(self, sentence_id: UUID) -> SentenceFeedback | None:
        return self._feedbacks.get(sentence_id)


def _make_vm(
    passage_id: UUID | None = None,
    sentence_ids: list[UUID] | None = None,
) -> tuple[PhaseBViewModel, EventBus, FakeFeedbackService, FakePracticeService, FakeFeedbackRepo, UUID]:
    bus = EventBus()
    fb_svc = FakeFeedbackService()
    pr_svc = FakePracticeService()
    fb_repo = FakeFeedbackRepo()
    ctx = SessionContext()

    vm = PhaseBViewModel(
        event_bus=bus,
        feedback_service=fb_svc,
        practice_service=pr_svc,
        feedback_repo=fb_repo,
        session_context=ctx,
    )

    pid = passage_id or uuid4()
    sids = sentence_ids or [uuid4(), uuid4()]
    vm.start(pid, sids)
    vm.activate()

    return vm, bus, fb_svc, pr_svc, fb_repo, pid


class TestProgressiveDisplay:
    def test_feedback_added_on_event(self, qtbot) -> None:
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])
        pid = pid

        fb_repo.add(SentenceFeedback(
            sentence_id=s1,
            user_utterance="I go to school",
            model_answer="I went to school",
            is_acceptable=False,
        ))

        with qtbot.waitSignal(vm.feedback_added, timeout=1000) as blocker:
            bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        assert blocker.args[0] == 0  # sentence index
        assert blocker.args[1] == "I go to school"  # user utterance
        assert blocker.args[2] == "I went to school"  # model answer
        assert blocker.args[3] is False  # is_acceptable

    def test_all_feedback_received(self, qtbot) -> None:
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])
        pid = pid

        fb_repo.add(SentenceFeedback(
            sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=True,
        ))
        fb_repo.add(SentenceFeedback(
            sentence_id=s2, user_utterance="u2", model_answer="m2", is_acceptable=True,
        ))

        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        with qtbot.waitSignal(vm.all_feedback_received, timeout=1000):
            bus.emit(FeedbackReady(passage_id=pid, sentence_id=s2))

    def test_feedback_failed_emits_signal(self, qtbot) -> None:
        s1 = uuid4()
        vm, bus, _, _, _, pid = _make_vm(sentence_ids=[s1])
        pid = pid

        with qtbot.waitSignal(vm.feedback_failed, timeout=1000) as blocker:
            bus.emit(FeedbackFailed(passage_id=pid, sentence_id=s1, error_message="LLM error"))

        assert blocker.args[0] == 0  # sentence index
        assert blocker.args[1] == "LLM error"


class TestLearningItems:
    def test_item_stocked_forwarded(self, qtbot) -> None:
        vm, bus, _, _, _, _ = _make_vm()

        with qtbot.waitSignal(vm.item_stocked, timeout=1000) as blocker:
            bus.emit(LearningItemStocked(item_id=uuid4(), pattern="past tense", is_reappearance=False))

        assert blocker.args[0] == "past tense"
        assert blocker.args[1] is False


class TestRetry:
    def test_retry_result_emitted(self, qtbot) -> None:
        s1 = uuid4()
        vm, bus, _, _, _, pid = _make_vm(sentence_ids=[s1])

        with qtbot.waitSignal(vm.retry_result, timeout=1000) as blocker:
            bus.emit(RetryJudged(sentence_id=s1, attempt=1, correct=True))

        assert blocker.args == [0, 1, True]  # sentence_index, attempt, correct

    def test_retry_max_3_enforced(self, qtbot) -> None:
        s1 = uuid4()
        vm, bus, fb_svc, _, _, _ = _make_vm(sentence_ids=[s1])

        # Record 3 failed retries
        vm._retry_counts[s1] = 3

        # 4th retry should be blocked
        vm.retry_sentence(s1, _make_audio())
        assert len(fb_svc.retry_calls) == 0


class TestModelAudioRequest:
    def test_model_audio_requested_on_start(self, qtbot) -> None:
        pid = uuid4()
        vm, bus, _, pr_svc, _, _ = _make_vm(passage_id=pid)

        assert pid in pr_svc.model_audio_calls


class TestNavigation:
    def test_proceed_skip_phase_c(self, qtbot) -> None:
        vm, bus, _, pr_svc, _, _ = _make_vm()
        pr_svc._should_skip = True

        with qtbot.waitSignal(vm.navigate_to_next, timeout=1000) as blocker:
            vm.proceed()

        assert blocker.args == [True]  # skip_phase_c

    def test_proceed_to_phase_c(self, qtbot) -> None:
        vm, bus, _, pr_svc, _, _ = _make_vm()
        pr_svc._should_skip = False

        with qtbot.waitSignal(vm.navigate_to_next, timeout=1000) as blocker:
            vm.proceed()

        assert blocker.args == [False]


class TestDeactivate:
    def test_deactivate_unsubscribes(self, qtbot) -> None:
        vm, bus, _, _, _, _ = _make_vm()
        vm.deactivate()

        with qtbot.assertNotEmitted(vm.feedback_added):
            bus.emit(FeedbackReady(passage_id=uuid4(), sentence_id=uuid4()))
