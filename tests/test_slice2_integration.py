"""Slice 2 integration tests: Phase A recording → feedback generation → Phase B retry.

Verifies the full flow with real SQLite (:memory:), real EventBus wiring,
real LocalAudioStorage (tmp_path), and Fake LLM adapters.

record_sentence(audio) → emit(SentenceRecorded) → async handler → Fake LLM
  → feedback + learning items saved to SQLite → FeedbackReady

judge_retry(audio) → Fake LLM → RetryResult → practice attempt saved → RetryJudged
"""

from collections.abc import Sequence

from parla.adapters.local_audio_storage import LocalAudioStorage
from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_feedback_repository import SQLiteFeedbackRepository
from parla.adapters.sqlite_learning_item_repository import SQLiteLearningItemRepository
from parla.adapters.sqlite_source_repository import SQLiteSourceRepository
from parla.domain.audio import AudioData
from parla.domain.events import (
    FeedbackFailed,
    FeedbackReady,
    LearningItemStocked,
    RetryJudged,
    SentenceRecorded,
)
from parla.domain.feedback import RetryResult
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.source import Source
from parla.event_bus import Event, EventBus
from parla.ports.feedback_generation import (
    RawFeedback,
    RawLearningItem,
    StockedItemInfo,
)
from parla.services.feedback_service import FeedbackService

# --- Fake LLM adapters ---


class FakeFeedbackGenerator:
    """Returns realistic fixture data modeled after V2 verification."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def generate_feedback(
        self,
        audio_data: bytes,
        audio_format: str,
        ja_prompt: str,
        cefr_level: str,
        english_variant: str,
        stocked_items: Sequence[StockedItemInfo],
    ) -> RawFeedback:
        if self._fail:
            msg = "Simulated LLM API error"
            raise RuntimeError(msg)
        return RawFeedback(
            user_utterance=(
                "I think this is [pause] very hard"
                " because it has （急な坂がわからない） and sharp curves."
            ),
            model_answer=(
                "I think this is very tough because it has"
                " steep slopes and sharp curves."
            ),
            is_acceptable=False,
            items=(
                RawLearningItem(
                    pattern="steep",
                    explanation="「急な」を表す形容詞。例: The road has a steep hill.",
                    category="語彙",
                    sub_tag="形容詞",
                    priority=4,
                ),
                RawLearningItem(
                    pattern="slope",
                    explanation="「坂」「斜面」を表す名詞。例: We walked up the slope.",
                    category="語彙",
                    sub_tag="名詞",
                    priority=3,
                ),
            ),
        )


class FakeRetryJudge:
    def __init__(self, correct: bool = True) -> None:
        self._correct = correct

    async def judge(
        self,
        audio_data: bytes,
        audio_format: str,
        reference_answer: str,
    ) -> RetryResult:
        if self._correct:
            return RetryResult(correct=True, reason="一致しています")
        return RetryResult(correct=False, reason="語句の欠落")


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


def _make_audio() -> AudioData:
    return AudioData(
        data=b"\x00" * 3200,
        format="wav",
        sample_rate=16000,
        channels=1,
        sample_width=2,
        duration_seconds=0.1,
    )


def _setup(tmp_path, *, fail_feedback: bool = False, retry_correct: bool = True):
    """Wire the full system: real SQLite + real EventBus + real AudioStorage + Fake LLMs."""
    bus = EventBus()
    conn = create_connection(":memory:")
    init_schema(conn)

    source_repo = SQLiteSourceRepository(conn)
    feedback_repo = SQLiteFeedbackRepository(conn)
    item_repo = SQLiteLearningItemRepository(conn)
    audio_storage = LocalAudioStorage(tmp_path / "audio")
    generator = FakeFeedbackGenerator(fail=fail_feedback)
    judge = FakeRetryJudge(correct=retry_correct)

    service = FeedbackService(
        event_bus=bus,
        source_repo=source_repo,
        feedback_repo=feedback_repo,
        item_repo=item_repo,
        audio_storage=audio_storage,
        feedback_generator=generator,
        retry_judge=judge,
    )

    # Register async handler (production wiring)
    bus.on_async(SentenceRecorded)(service.handle_sentence_recorded)

    # Set up source + passage + sentences
    source = Source(text="a" * 200, cefr_level="B1", english_variant="American")
    source_repo.save_source(source)

    sentences = (
        Sentence(
            order=0,
            ja="そのコースは急な坂や急カーブがあるため、非常に厳しいです。",
            en="The course is very tough because it has steep slopes and sharp curves.",
            hints=Hint(hint1="The course ... steep / sharp", hint2="主語 + be動詞 + 補語"),
        ),
        Sentence(
            order=1,
            ja="この努力の結果として、トヨタは世界トップの自動車メーカーとなっています。",
            en="As a result of this effort, Toyota has become the top car maker in the world.",
            hints=Hint(hint1="As a result ... top", hint2="前置詞句, 主語 + 現在完了"),
        ),
    )
    passage = Passage(
        source_id=source.id,
        order=0,
        topic="Toyota",
        passage_type="説明型",
        sentences=sentences,
    )
    source_repo.save_passages([passage])

    collector = EventCollector(bus)
    return service, source_repo, feedback_repo, item_repo, audio_storage, bus, collector, passage


class TestSlice2HappyPath:
    """Full flow: SentenceRecorded → handler → Fake LLM → SQLite → FeedbackReady."""

    async def test_feedback_saved_to_sqlite(self, tmp_path) -> None:
        service, _, feedback_repo, _, audio_storage, bus, _, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        fb = feedback_repo.get_feedback_by_sentence(sid)
        assert fb is not None
        assert "steep slopes" in fb.model_answer
        assert fb.is_acceptable is False

    async def test_learning_items_persisted(self, tmp_path) -> None:
        service, _, _, item_repo, audio_storage, bus, _, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        items = item_repo.get_items_by_sentence(sid)
        assert len(items) == 2
        patterns = {i.pattern for i in items}
        assert patterns == {"steep", "slope"}

    async def test_priority_to_status_mapping(self, tmp_path) -> None:
        service, _, _, item_repo, audio_storage, bus, _, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        items = item_repo.get_items_by_sentence(sid)
        steep = next(i for i in items if i.pattern == "steep")
        slope = next(i for i in items if i.pattern == "slope")
        assert steep.status == "auto_stocked"  # priority 4
        assert slope.status == "review_later"  # priority 3

    async def test_event_sequence(self, tmp_path) -> None:
        service, _, _, _, audio_storage, bus, collector, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        assert collector.types() == [
            SentenceRecorded,
            LearningItemStocked,  # steep (priority 4 → auto_stocked)
            FeedbackReady,
        ]

    async def test_only_auto_stocked_items_emit_event(self, tmp_path) -> None:
        service, _, _, _, audio_storage, bus, collector, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        stocked = [e for e in collector.events if isinstance(e, LearningItemStocked)]
        assert len(stocked) == 1
        assert stocked[0].pattern == "steep"

    async def test_audio_persisted_on_disk(self, tmp_path) -> None:
        service, _, _, _, audio_storage, bus, _, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        loaded = audio_storage.load(sid)
        assert loaded is not None
        assert loaded.sample_rate == 16000


class TestSlice2RetryFlow:
    """Phase B: retry judgment after feedback is ready."""

    async def test_correct_retry(self, tmp_path) -> None:
        service, _, feedback_repo, _, audio_storage, bus, _, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        # Phase A: generate feedback
        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        # Phase B: retry
        result = await service.judge_retry(sid, 1, _make_audio())
        assert result.correct is True

    async def test_incorrect_retry(self, tmp_path) -> None:
        service, _, feedback_repo, _, audio_storage, bus, _, passage = _setup(
            tmp_path, retry_correct=False,
        )
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        result = await service.judge_retry(sid, 1, _make_audio())
        assert result.correct is False
        assert result.reason == "語句の欠落"

    async def test_practice_attempt_persisted(self, tmp_path) -> None:
        service, _, feedback_repo, _, audio_storage, bus, _, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        await service.judge_retry(sid, 1, _make_audio())
        await service.judge_retry(sid, 2, _make_audio())

        attempts = feedback_repo.get_attempts_by_sentence(sid)
        assert len(attempts) == 2
        assert attempts[0].attempt_number == 1
        assert attempts[1].attempt_number == 2

    async def test_retry_emits_event(self, tmp_path) -> None:
        service, _, _, _, audio_storage, bus, collector, passage = _setup(tmp_path)
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        await service.judge_retry(sid, 1, _make_audio())

        judged = [e for e in collector.events if isinstance(e, RetryJudged)]
        assert len(judged) == 1
        assert judged[0].correct is True


class TestSlice2ErrorPath:
    """LLM failure: emit → handler → fail → FeedbackFailed."""

    async def test_feedback_failed_event(self, tmp_path) -> None:
        service, _, _, _, audio_storage, bus, collector, passage = _setup(
            tmp_path, fail_feedback=True,
        )
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        assert FeedbackFailed in collector.types()

    async def test_no_feedback_saved_on_failure(self, tmp_path) -> None:
        service, _, feedback_repo, _, audio_storage, bus, _, passage = _setup(
            tmp_path, fail_feedback=True,
        )
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        assert feedback_repo.get_feedback_by_sentence(sid) is None

    async def test_no_items_saved_on_failure(self, tmp_path) -> None:
        service, _, _, item_repo, audio_storage, bus, _, passage = _setup(
            tmp_path, fail_feedback=True,
        )
        sid = passage.sentences[0].id

        audio_storage.save(sid, _make_audio())
        tasks = bus.emit(SentenceRecorded(passage_id=passage.id, sentence_id=sid))
        await tasks[0]

        assert item_repo.get_items_by_sentence(sid) == []
