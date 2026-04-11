"""Tests for PhaseBViewModel."""

import asyncio
from uuid import UUID, uuid4

from parla.domain.audio import AudioData
from tests.conftest import make_wav_audio
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
    return make_wav_audio()


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


class FakeItemRepo:
    def __init__(self) -> None:
        self._items: dict[UUID, list] = {}
        self._by_id: dict[UUID, object] = {}

    def add(self, sentence_id: UUID, item: object) -> None:
        self._items.setdefault(sentence_id, []).append(item)
        self._by_id[item.id] = item  # type: ignore[union-attr]

    def get_items_by_sentence(self, sentence_id: UUID) -> list:
        return self._items.get(sentence_id, [])

    def get_item(self, item_id: UUID) -> object | None:
        return self._by_id.get(item_id)


def _make_vm(
    passage_id: UUID | None = None,
    sentence_ids: list[UUID] | None = None,
    item_repo: FakeItemRepo | None = None,
) -> tuple[PhaseBViewModel, EventBus, FakeFeedbackService, FakePracticeService, FakeFeedbackRepo, UUID]:
    bus = EventBus()
    fb_svc = FakeFeedbackService()
    pr_svc = FakePracticeService()
    fb_repo = FakeFeedbackRepo()
    i_repo = item_repo or FakeItemRepo()
    ctx = SessionContext()

    vm = PhaseBViewModel(
        event_bus=bus,
        feedback_service=fb_svc,
        practice_service=pr_svc,
        feedback_repo=fb_repo,
        item_repo=i_repo,
        session_context=ctx,
    )

    pid = passage_id or uuid4()
    sids = sentence_ids or [uuid4(), uuid4()]
    vm.start(pid, sids)
    vm.activate()

    return vm, bus, fb_svc, pr_svc, fb_repo, pid


class TestOneAtATimeDisplay:
    """Feedback is shown one sentence at a time, in order."""

    def test_feedback_shown_for_current_sentence(self, qtbot) -> None:
        """FeedbackReady for index 0 (current) emits feedback_added."""
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        fb_repo.add(SentenceFeedback(
            sentence_id=s1,
            user_utterance="I go to school",
            model_answer="I went to school",
            is_acceptable=False,
        ))

        with qtbot.waitSignal(vm.feedback_added, timeout=1000) as blocker:
            bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        assert blocker.args[0] == 0
        assert blocker.args[1] == "I go to school"
        assert blocker.args[2] == "I went to school"
        assert blocker.args[3] is False

    def test_feedback_buffered_when_not_current(self, qtbot) -> None:
        """FeedbackReady for index 1 does NOT emit when current is 0."""
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        fb_repo.add(SentenceFeedback(
            sentence_id=s2,
            user_utterance="u2",
            model_answer="m2",
            is_acceptable=True,
        ))

        with qtbot.assertNotEmitted(vm.feedback_added):
            bus.emit(FeedbackReady(passage_id=pid, sentence_id=s2))

        # But it IS buffered
        assert 1 in vm._feedback_buffer

    def test_advance_shows_buffered_feedback(self, qtbot) -> None:
        """advance_sentence() displays already-buffered feedback when current is passed."""
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        # Buffer feedback for both sentences (s1 acceptable → can advance)
        fb_repo.add(SentenceFeedback(sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=True))
        fb_repo.add(SentenceFeedback(sentence_id=s2, user_utterance="u2", model_answer="m2", is_acceptable=False))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s2))

        with qtbot.waitSignal(vm.feedback_added, timeout=1000) as blocker:
            vm.advance_sentence()

        assert blocker.args[0] == 1
        assert blocker.args[1] == "u2"
        assert blocker.args[3] is False

    def test_advance_shows_loading_when_not_ready(self, qtbot) -> None:
        """advance_sentence() emits loading when next feedback hasn't arrived."""
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        # Only buffer index 0 (acceptable → can advance)
        fb_repo.add(SentenceFeedback(sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=True))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        with qtbot.waitSignal(vm.current_sentence_loading, timeout=1000) as blocker:
            vm.advance_sentence()

        assert blocker.args[0] == 1

    def test_late_arrival_triggers_display(self, qtbot) -> None:
        """FeedbackReady arriving for the currently-waiting sentence shows it."""
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        # Show and advance past sentence 0
        fb_repo.add(SentenceFeedback(sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=True))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))
        vm.advance_sentence()  # now current=1, loading

        # Late arrival for sentence 1
        fb_repo.add(SentenceFeedback(sentence_id=s2, user_utterance="u2", model_answer="m2", is_acceptable=True))

        with qtbot.waitSignal(vm.feedback_added, timeout=1000) as blocker:
            bus.emit(FeedbackReady(passage_id=pid, sentence_id=s2))

        assert blocker.args[0] == 1
        assert blocker.args[1] == "u2"

    def test_advance_past_last_calls_proceed(self, qtbot) -> None:
        """advance_sentence() on last sentence triggers navigate_to_next when passed."""
        s1 = uuid4()
        vm, bus, _, pr_svc, fb_repo, pid = _make_vm(sentence_ids=[s1])
        pr_svc._should_skip = False

        fb_repo.add(SentenceFeedback(sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=True))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        with qtbot.waitSignal(vm.navigate_to_next, timeout=1000) as blocker:
            vm.advance_sentence()

        assert blocker.args == [False]

    def test_advance_blocked_when_not_passed(self, qtbot) -> None:
        """advance_sentence() does nothing when current sentence is not passed."""
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        # is_acceptable=False → cannot advance
        fb_repo.add(SentenceFeedback(sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=False))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        with qtbot.assertNotEmitted(vm.current_sentence_changed):
            vm.advance_sentence()

        assert vm._current_index == 0

    def test_advance_unblocked_after_retry_pass(self, qtbot) -> None:
        """After a successful retry, advance_sentence() works."""
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        fb_repo.add(SentenceFeedback(sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=False))
        fb_repo.add(SentenceFeedback(sentence_id=s2, user_utterance="u2", model_answer="m2", is_acceptable=True))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s2))

        # Still blocked
        vm.advance_sentence()
        assert vm._current_index == 0

        # Retry passes
        bus.emit(RetryJudged(sentence_id=s1, attempt=1, correct=True))

        # Now can advance
        with qtbot.waitSignal(vm.feedback_added, timeout=1000):
            vm.advance_sentence()

        assert vm._current_index == 1

    def test_current_sentence_changed_signal(self, qtbot) -> None:
        """advance_sentence() emits current_sentence_changed(index, total) when passed."""
        s1, s2, s3 = uuid4(), uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2, s3])

        fb_repo.add(SentenceFeedback(sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=True))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        with qtbot.waitSignal(vm.current_sentence_changed, timeout=1000) as blocker:
            vm.advance_sentence()

        assert blocker.args == [1, 3]


class TestAllFeedbackReceived:
    def test_all_feedback_received(self, qtbot) -> None:
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        fb_repo.add(SentenceFeedback(
            sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=True,
        ))
        fb_repo.add(SentenceFeedback(
            sentence_id=s2, user_utterance="u2", model_answer="m2", is_acceptable=True,
        ))

        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        with qtbot.waitSignal(vm.all_feedback_received, timeout=1000):
            bus.emit(FeedbackReady(passage_id=pid, sentence_id=s2))

    def test_feedback_failed_counts_toward_total(self, qtbot) -> None:
        s1 = uuid4()
        vm, bus, _, _, _, pid = _make_vm(sentence_ids=[s1])

        with qtbot.waitSignal(vm.all_feedback_received, timeout=1000):
            bus.emit(FeedbackFailed(passage_id=pid, sentence_id=s1, error_message="LLM error"))


class TestFeedbackFailed:
    def test_failed_emits_for_current(self, qtbot) -> None:
        s1 = uuid4()
        vm, bus, _, _, _, pid = _make_vm(sentence_ids=[s1])

        with qtbot.waitSignal(vm.feedback_failed, timeout=1000) as blocker:
            bus.emit(FeedbackFailed(passage_id=pid, sentence_id=s1, error_message="LLM error"))

        assert blocker.args[0] == 0
        assert blocker.args[1] == "LLM error"

    def test_failed_buffered_when_not_current(self, qtbot) -> None:
        s1, s2 = uuid4(), uuid4()
        vm, bus, _, _, _, pid = _make_vm(sentence_ids=[s1, s2])

        with qtbot.assertNotEmitted(vm.feedback_failed):
            bus.emit(FeedbackFailed(passage_id=pid, sentence_id=s2, error_message="error"))

        assert 1 in vm._error_buffer


class TestLearningItems:
    def test_pre_existing_items_emitted_on_start(self, qtbot) -> None:
        """Items generated during Phase A are emitted on start()."""
        from parla.domain.learning_item import LearningItem

        s1 = uuid4()
        i_repo = FakeItemRepo()
        item = LearningItem(
            pattern="by ~ing",
            explanation="〜することで",
            category="文法",
            sub_tag="動名詞",
            priority=4,
            source_sentence_id=s1,
            is_reappearance=False,
            status="auto_stocked",
        )
        i_repo.add(s1, item)

        signals: list[tuple[int, str, str, bool]] = []

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
            item_repo=i_repo,
            session_context=ctx,
        )
        vm.item_stocked.connect(lambda idx, p, e, r: signals.append((idx, p, e, r)))

        # Also pre-fill feedback so show_initial emits items
        fb_repo.add(SentenceFeedback(
            sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=False,
        ))
        pid = uuid4()
        vm.start(pid, [s1])
        vm.show_initial()

        assert len(signals) == 1
        assert signals[0] == (0, "by ~ing", "〜することで", False)
        assert vm._new_item_count == 1

    def test_items_emitted_with_late_feedback(self, qtbot) -> None:
        """When FeedbackReady arrives late, buffered items are emitted together."""
        from parla.domain.learning_item import LearningItem

        s1 = uuid4()
        i_repo = FakeItemRepo()
        item = LearningItem(
            pattern="chairman",
            explanation="会長・議長を意味する語",
            category="語彙",
            sub_tag="名詞",
            priority=4,
            source_sentence_id=s1,
            is_reappearance=False,
            status="auto_stocked",
        )
        i_repo.add(s1, item)

        # start() with NO feedback in DB yet (simulates late arrival)
        vm, bus, _, _, fb_repo, pid = _make_vm(sentence_ids=[s1], item_repo=i_repo)

        item_signals: list[tuple[int, str, str, bool]] = []
        vm.item_stocked.connect(lambda idx, p, e, r: item_signals.append((idx, p, e, r)))

        # Now feedback arrives late
        fb_repo.add(SentenceFeedback(
            sentence_id=s1, user_utterance="（発話なし）", model_answer="m1", is_acceptable=False,
        ))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))

        assert len(item_signals) == 1
        assert item_signals[0] == (0, "chairman", "会長・議長を意味する語", False)

    def test_items_not_mixed_across_sentences(self, qtbot) -> None:
        """Items from sentence 2 do not appear when viewing sentence 1."""
        from parla.domain.learning_item import LearningItem

        s1, s2 = uuid4(), uuid4()
        i_repo = FakeItemRepo()
        item_s2 = LearningItem(
            pattern="still",
            explanation="まだ・今でも",
            category="語彙",
            sub_tag="副詞",
            priority=3,
            source_sentence_id=s2,
            is_reappearance=False,
            status="auto_stocked",
        )
        i_repo.add(s2, item_s2)

        fb_repo = FakeFeedbackRepo()
        fb_repo.add(SentenceFeedback(
            sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=False,
        ))
        fb_repo.add(SentenceFeedback(
            sentence_id=s2, user_utterance="u2", model_answer="m2", is_acceptable=False,
        ))

        vm, bus, _, _, _, pid = _make_vm(sentence_ids=[s1, s2], item_repo=i_repo)

        item_signals: list[tuple[int, str, str, bool]] = []
        vm.item_stocked.connect(lambda idx, p, e, r: item_signals.append((idx, p, e, r)))

        # _show_current for sentence 0 — should NOT include s2's items
        vm.show_initial()
        assert len(item_signals) == 0

    def test_item_stocked_forwarded_on_event(self, qtbot) -> None:
        """LearningItemStocked event arriving during Phase B is forwarded."""
        from parla.domain.learning_item import LearningItem

        s1, s2 = uuid4(), uuid4()
        i_repo = FakeItemRepo()
        item_id = uuid4()
        item = LearningItem(
            id=item_id,
            pattern="past tense",
            explanation="過去形の使い方",
            category="文法",
            sub_tag="時制",
            priority=4,
            source_sentence_id=s1,
            is_reappearance=False,
            status="auto_stocked",
        )
        i_repo.add(s1, item)

        vm, bus, _, _, _, pid = _make_vm(sentence_ids=[s1, s2], item_repo=i_repo)

        # Event for a NEW item (different id) arriving during Phase B
        new_item_id = uuid4()
        new_item = LearningItem(
            id=new_item_id,
            pattern="present perfect",
            explanation="現在完了形",
            category="文法",
            sub_tag="時制",
            priority=3,
            source_sentence_id=s1,
            is_reappearance=False,
            status="auto_stocked",
        )
        i_repo.add(s1, new_item)

        with qtbot.waitSignal(vm.item_stocked, timeout=1000) as blocker:
            bus.emit(LearningItemStocked(item_id=new_item_id, pattern="present perfect", is_reappearance=False))

        assert blocker.args[0] == 0  # sentence index
        assert blocker.args[1] == "present perfect"
        assert blocker.args[2] == "現在完了形"
        assert blocker.args[3] is False


class TestRetry:
    def test_retry_result_emitted(self, qtbot) -> None:
        s1 = uuid4()
        vm, bus, _, _, _, pid = _make_vm(sentence_ids=[s1])

        with qtbot.waitSignal(vm.retry_result, timeout=1000) as blocker:
            bus.emit(RetryJudged(sentence_id=s1, attempt=1, correct=True))

        assert blocker.args == [0, 1, True]

    async def test_no_retry_limit(self, qtbot) -> None:
        """Retry has no upper limit — users must pass to proceed."""
        s1 = uuid4()
        vm, bus, fb_svc, _, _, _ = _make_vm(sentence_ids=[s1])

        vm._retry_counts[s1] = 10
        vm.retry_sentence(s1, _make_audio())
        await asyncio.sleep(0)
        assert len(fb_svc.retry_calls) == 1

    async def test_retry_current_uses_correct_sentence(self, qtbot) -> None:
        s1, s2 = uuid4(), uuid4()
        vm, bus, fb_svc, _, fb_repo, pid = _make_vm(sentence_ids=[s1, s2])

        # Advance to sentence 1
        fb_repo.add(SentenceFeedback(sentence_id=s1, user_utterance="u1", model_answer="m1", is_acceptable=True))
        bus.emit(FeedbackReady(passage_id=pid, sentence_id=s1))
        vm.advance_sentence()

        vm.retry_current(_make_audio())
        await asyncio.sleep(0)  # let ensure_future task start
        assert len(fb_svc.retry_calls) == 1
        assert fb_svc.retry_calls[0]["sentence_id"] == s2


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

        assert blocker.args == [True]

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
