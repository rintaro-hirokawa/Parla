"""Tests for FeedbackService."""

from collections.abc import Sequence
from uuid import UUID

import pytest

from parla.domain.audio import AudioData
from parla.domain.events import (
    FeedbackFailed,
    FeedbackReady,
    LearningItemStocked,
    RetryJudged,
    SentenceRecorded,
)
from parla.domain.feedback import PracticeAttempt, RetryResult, SentenceFeedback
from parla.domain.learning_item import LearningItem, LearningItemStatus
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.source import Source
from parla.event_bus import Event, EventBus
from parla.ports.feedback_generation import RawFeedback, RawLearningItem, StockedItemInfo
from parla.services.feedback_service import FeedbackService

# --- Fakes ---


def _make_audio() -> AudioData:
    return AudioData(
        data=b"\x00" * 320,
        format="wav",
        sample_rate=16000,
        channels=1,
        sample_width=2,
        duration_seconds=0.01,
    )


class FakeAudioStorage:
    def __init__(self) -> None:
        self._store: dict[UUID, AudioData] = {}

    def save(self, sentence_id: UUID, audio: AudioData) -> None:
        self._store[sentence_id] = audio

    def load(self, sentence_id: UUID) -> AudioData | None:
        return self._store.get(sentence_id)

    def delete(self, sentence_id: UUID) -> None:
        self._store.pop(sentence_id, None)


class FakeFeedbackGenerator:
    def __init__(self, result: RawFeedback | None = None, *, fail: bool = False) -> None:
        self._result = result or RawFeedback(
            user_utterance="I think this is hard.",
            model_answer="I think this is very difficult.",
            is_acceptable=True,
            items=(
                RawLearningItem(
                    pattern="difficult",
                    explanation="「難しい」の形容詞",
                    category="語彙",
                    sub_tag="形容詞",
                    priority=4,
                ),
            ),
        )
        self._fail = fail
        self.last_stocked_items: Sequence[StockedItemInfo] = []

    async def generate_feedback(
        self,
        audio_data: bytes,
        audio_format: str,
        ja_prompt: str,
        cefr_level: str,
        english_variant: str,
        stocked_items: Sequence[StockedItemInfo],
    ) -> RawFeedback:
        self.last_stocked_items = stocked_items
        if self._fail:
            msg = "Simulated LLM error"
            raise RuntimeError(msg)
        return self._result


class FakeRetryJudge:
    def __init__(self, result: RetryResult | None = None) -> None:
        self._result = result or RetryResult(correct=True, reason="一致しています")

    async def judge(
        self,
        audio_data: bytes,
        audio_format: str,
        reference_answer: str,
    ) -> RetryResult:
        return self._result


class FakeSourceRepo:
    def __init__(self) -> None:
        self._sources: dict[UUID, Source] = {}
        self._passages: dict[UUID, Passage] = {}

    def save_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def get_source(self, source_id: UUID) -> Source | None:
        return self._sources.get(source_id)

    def update_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def save_passages(self, passages: Sequence[Passage]) -> None:
        for p in passages:
            self._passages[p.id] = p

    def get_passages_by_source(self, source_id: UUID) -> list[Passage]:
        return [p for p in self._passages.values() if p.source_id == source_id]

    def get_passage(self, passage_id: UUID) -> Passage | None:
        return self._passages.get(passage_id)


class FakeFeedbackRepo:
    def __init__(self) -> None:
        self._feedback: dict[UUID, SentenceFeedback] = {}
        self._attempts: list[PracticeAttempt] = []

    def save_feedback(self, feedback: SentenceFeedback) -> None:
        self._feedback[feedback.sentence_id] = feedback

    def get_feedback_by_sentence(self, sentence_id: UUID) -> SentenceFeedback | None:
        return self._feedback.get(sentence_id)

    def save_practice_attempt(self, attempt: PracticeAttempt) -> None:
        self._attempts.append(attempt)

    def get_attempts_by_sentence(self, sentence_id: UUID) -> list[PracticeAttempt]:
        return [a for a in self._attempts if a.sentence_id == sentence_id]


class FakeItemRepo:
    def __init__(self) -> None:
        self._items: list[LearningItem] = []

    def save_items(self, items: Sequence[LearningItem]) -> None:
        self._items.extend(items)

    def get_stocked_items(self) -> list[LearningItem]:
        return [i for i in self._items if i.status == "auto_stocked"]

    def get_items_by_sentence(self, sentence_id: UUID) -> list[LearningItem]:
        return [i for i in self._items if i.source_sentence_id == sentence_id]

    def update_item_status(self, item_id: UUID, status: LearningItemStatus) -> None:
        for i, item in enumerate(self._items):
            if item.id == item_id:
                self._items[i] = item.model_copy(update={"status": status})


class EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        bus.on_sync(SentenceRecorded)(self._collect)
        bus.on_sync(FeedbackReady)(self._collect)
        bus.on_sync(FeedbackFailed)(self._collect)
        bus.on_sync(LearningItemStocked)(self._collect)
        bus.on_sync(RetryJudged)(self._collect)

    def _collect(self, event: Event) -> None:
        self.events.append(event)

    def types(self) -> list[type[Event]]:
        return [type(e) for e in self.events]


# --- Fixtures ---


def _make_source_and_passage() -> tuple[Source, Passage]:
    source = Source(text="a" * 200, cefr_level="B1", english_variant="American")
    sentence = Sentence(
        order=0,
        ja="これはとても難しいと思います。",
        en="I think this is very difficult.",
        hints=Hint(hint1="I think ... difficult", hint2="主語 + think + that節"),
    )
    passage = Passage(
        source_id=source.id,
        order=0,
        topic="test",
        passage_type="説明型",
        sentences=(sentence,),
    )
    return source, passage


def _setup(
    *,
    fail_feedback: bool = False,
    retry_result: RetryResult | None = None,
    feedback_result: RawFeedback | None = None,
) -> tuple[
    FeedbackService,
    FakeSourceRepo,
    FakeFeedbackRepo,
    FakeItemRepo,
    FakeAudioStorage,
    EventBus,
    EventCollector,
    Source,
    Passage,
]:
    bus = EventBus()
    source_repo = FakeSourceRepo()
    feedback_repo = FakeFeedbackRepo()
    item_repo = FakeItemRepo()
    audio_storage = FakeAudioStorage()
    generator = FakeFeedbackGenerator(result=feedback_result, fail=fail_feedback)
    judge = FakeRetryJudge(result=retry_result)

    service = FeedbackService(
        event_bus=bus,
        source_repo=source_repo,
        feedback_repo=feedback_repo,
        item_repo=item_repo,
        audio_storage=audio_storage,
        feedback_generator=generator,
        retry_judge=judge,
    )

    source, passage = _make_source_and_passage()
    source_repo.save_source(source)
    source_repo.save_passages([passage])

    collector = EventCollector(bus)
    bus.on_async(SentenceRecorded)(service.handle_sentence_recorded)

    return (
        service,
        source_repo,
        feedback_repo,
        item_repo,
        audio_storage,
        bus,
        collector,
        source,
        passage,
    )


class TestRecordSentence:
    async def test_saves_audio_and_emits_event(self) -> None:
        service, _, _, _, audio_storage, _, collector, _, passage = _setup()
        sid = passage.sentences[0].id

        service.record_sentence(passage.id, sid, _make_audio())

        assert audio_storage.load(sid) is not None
        assert SentenceRecorded in [type(e) for e in collector.events]


def _emit_and_get_handler_task(
    bus: EventBus,
    audio_storage: FakeAudioStorage,
    passage: Passage,
):
    """Pre-store audio then emit SentenceRecorded, return the async task."""
    sid = passage.sentences[0].id
    audio_storage.save(sid, _make_audio())
    tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
    return tasks[0], sid


class TestHandleSentenceRecorded:
    async def test_generates_feedback_and_saves(self) -> None:
        _, _, feedback_repo, _, audio_storage, bus, _, _, passage = _setup()

        task, sid = _emit_and_get_handler_task(bus, audio_storage, passage)
        await task

        fb = feedback_repo.get_feedback_by_sentence(sid)
        assert fb is not None
        assert fb.model_answer == "I think this is very difficult."

    async def test_stocks_learning_items(self) -> None:
        _, _, _, item_repo, audio_storage, bus, _, _, passage = _setup()

        task, sid = _emit_and_get_handler_task(bus, audio_storage, passage)
        await task

        items = item_repo.get_items_by_sentence(sid)
        assert len(items) == 1
        assert items[0].pattern == "difficult"
        assert items[0].status == "auto_stocked"

    async def test_emits_feedback_ready(self) -> None:
        _, _, _, _, audio_storage, bus, collector, _, passage = _setup()

        task, _ = _emit_and_get_handler_task(bus, audio_storage, passage)
        await task

        assert FeedbackReady in collector.types()

    async def test_emits_learning_item_stocked(self) -> None:
        _, _, _, _, audio_storage, bus, collector, _, passage = _setup()

        task, _ = _emit_and_get_handler_task(bus, audio_storage, passage)
        await task

        stocked_events = [e for e in collector.events if isinstance(e, LearningItemStocked)]
        assert len(stocked_events) == 1
        assert stocked_events[0].pattern == "difficult"

    async def test_review_later_items_not_emitted_as_stocked(self) -> None:
        feedback = RawFeedback(
            user_utterance="test",
            model_answer="test answer",
            is_acceptable=True,
            items=(
                RawLearningItem(
                    pattern="passenger seat",
                    explanation="テスト",
                    category="語彙",
                    sub_tag="名詞",
                    priority=2,
                ),
            ),
        )
        _, _, _, item_repo, audio_storage, bus, collector, _, passage = _setup(
            feedback_result=feedback,
        )

        task, sid = _emit_and_get_handler_task(bus, audio_storage, passage)
        await task

        items = item_repo.get_items_by_sentence(sid)
        assert items[0].status == "review_later"

        stocked_events = [e for e in collector.events if isinstance(e, LearningItemStocked)]
        assert len(stocked_events) == 0

    async def test_failure_emits_feedback_failed(self) -> None:
        _, _, _, _, audio_storage, bus, collector, _, passage = _setup(fail_feedback=True)

        task, _ = _emit_and_get_handler_task(bus, audio_storage, passage)
        await task

        assert FeedbackFailed in collector.types()


class TestJudgeRetry:
    async def test_correct_retry(self) -> None:
        service, _, feedback_repo, _, _, _, _, _, passage = _setup()
        sid = passage.sentences[0].id

        # Pre-save feedback (normally done by handle_sentence_recorded)
        feedback_repo.save_feedback(
            SentenceFeedback(
                sentence_id=sid,
                user_utterance="test",
                model_answer="I think this is very difficult.",
                is_acceptable=True,
            )
        )

        result = await service.judge_retry(sid, 1, _make_audio())
        assert result.correct is True

    async def test_incorrect_retry(self) -> None:
        service, _, feedback_repo, _, _, _, _, _, passage = _setup(
            retry_result=RetryResult(correct=False, reason="語句の欠落"),
        )
        sid = passage.sentences[0].id

        feedback_repo.save_feedback(
            SentenceFeedback(
                sentence_id=sid,
                user_utterance="test",
                model_answer="I think this is very difficult.",
                is_acceptable=True,
            )
        )

        result = await service.judge_retry(sid, 1, _make_audio())
        assert result.correct is False

    async def test_saves_practice_attempt(self) -> None:
        service, _, feedback_repo, _, _, _, _, _, passage = _setup()
        sid = passage.sentences[0].id

        feedback_repo.save_feedback(
            SentenceFeedback(
                sentence_id=sid,
                user_utterance="test",
                model_answer="test",
                is_acceptable=True,
            )
        )

        await service.judge_retry(sid, 1, _make_audio())

        attempts = feedback_repo.get_attempts_by_sentence(sid)
        assert len(attempts) == 1
        assert attempts[0].attempt_number == 1

    async def test_emits_retry_judged(self) -> None:
        service, _, feedback_repo, _, _, _, collector, _, passage = _setup()
        sid = passage.sentences[0].id

        feedback_repo.save_feedback(
            SentenceFeedback(
                sentence_id=sid,
                user_utterance="test",
                model_answer="test",
                is_acceptable=True,
            )
        )

        await service.judge_retry(sid, 2, _make_audio())

        judged = [e for e in collector.events if isinstance(e, RetryJudged)]
        assert len(judged) == 1
        assert judged[0].attempt == 2

    async def test_raises_when_no_feedback(self) -> None:
        service, _, _, _, _, _, _, _, passage = _setup()
        sid = passage.sentences[0].id

        with pytest.raises(ValueError, match="No feedback found"):
            await service.judge_retry(sid, 1, _make_audio())
