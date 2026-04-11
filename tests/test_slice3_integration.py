"""Slice 3 integration tests: Block 1 Review with SRS.

Verifies the full flow with real SQLite (:memory:), real EventBus wiring,
real AudioStorage (tmp_path), and Fake LLM adapters.

Variation generation:
  request_variation → emit(VariationGenerationRequested) → handler → Fake LLM
  → variation saved to SQLite → VariationReady

Review judgment + SRS update:
  judge_review(audio) → Fake LLM → ReviewResult → attempt saved
  → SRS state updated → ReviewAnswered + SRSUpdated

Review retry (no SRS impact):
  judge_review_retry(audio) → Fake LLM → ReviewResult → attempt saved
  → ReviewRetryJudged (SRS unchanged)
"""

from collections.abc import Sequence
from datetime import date

from parla.adapters.local_audio_storage import LocalAudioStorage
from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_learning_item_repository import SQLiteLearningItemRepository
from parla.adapters.sqlite_review_attempt_repository import SQLiteReviewAttemptRepository
from parla.adapters.sqlite_source_repository import SQLiteSourceRepository
from parla.adapters.sqlite_variation_repository import SQLiteVariationRepository
from parla.domain.audio import AudioData
from parla.domain.events import (
    ReviewAnswered,
    ReviewRetryJudged,
    SRSUpdated,
    VariationGenerationFailed,
    VariationGenerationRequested,
    VariationReady,
)
from parla.domain.learning_item import LearningItem
from parla.domain.review import ReviewResult
from parla.domain.source import Source
from parla.domain.srs import SRSConfig
from parla.event_bus import Event, EventBus
from parla.ports.variation_generation import PastVariationInfo, RawVariation
from parla.services.review_service import ReviewService
from tests.conftest import make_wav_audio

# --- Fake LLM adapters ---


class FakeVariationGenerator:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    async def generate_variation(
        self,
        learning_item_pattern: str,
        learning_item_explanation: str,
        cefr_level: str,
        english_variant: str,
        source_text: str,
        past_variations: Sequence[PastVariationInfo],
    ) -> RawVariation:
        if self._fail:
            msg = "Simulated LLM API error"
            raise RuntimeError(msg)
        return RawVariation(
            ja="この会社はAIの安全性を確保する責任を負っています。",
            en=f"This company is {learning_item_pattern.replace('~ing', 'ensuring')} the safety of AI systems.",
            hint1="This company ... responsible / ensuring",
            hint2="主語 + be動詞 + responsible for + 動名詞",
        )


class FakeReviewJudge:
    def __init__(self, correct: bool = True, item_used: bool = True) -> None:
        self._correct = correct
        self._item_used = item_used

    async def judge(
        self,
        audio_data: bytes,
        audio_format: str,
        target_pattern: str,
        reference_answer: str,
        ja_prompt: str,
        cefr_level: str,
    ) -> ReviewResult:
        return ReviewResult(
            correct=self._correct,
            item_used=self._item_used,
            reason="学習項目を正しく使用" if self._correct else "学習項目の不使用",
        )


class EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        bus.on_sync(VariationGenerationRequested)(self._collect)
        bus.on_sync(VariationReady)(self._collect)
        bus.on_sync(VariationGenerationFailed)(self._collect)
        bus.on_sync(ReviewAnswered)(self._collect)
        bus.on_sync(ReviewRetryJudged)(self._collect)
        bus.on_sync(SRSUpdated)(self._collect)

    def _collect(self, event: Event) -> None:
        self.events.append(event)

    def types(self) -> list[type[Event]]:
        return [type(e) for e in self.events]


def _make_audio() -> AudioData:
    return make_wav_audio(n_samples=1600, duration_seconds=0.1)


def _setup(
    tmp_path,
    *,
    fail_variation: bool = False,
    review_correct: bool = True,
    review_item_used: bool = True,
):
    """Wire the full system for slice 3."""
    bus = EventBus()
    conn = create_connection(":memory:")
    init_schema(conn)

    source_repo = SQLiteSourceRepository(conn)
    item_repo = SQLiteLearningItemRepository(conn)
    variation_repo = SQLiteVariationRepository(conn)
    attempt_repo = SQLiteReviewAttemptRepository(conn)
    audio_storage = LocalAudioStorage(tmp_path / "audio")

    variation_generator = FakeVariationGenerator(fail=fail_variation)
    review_judge = FakeReviewJudge(correct=review_correct, item_used=review_item_used)
    srs_config = SRSConfig()

    service = ReviewService(
        event_bus=bus,
        source_repo=source_repo,
        item_repo=item_repo,
        variation_repo=variation_repo,
        attempt_repo=attempt_repo,
        audio_storage=audio_storage,
        variation_generator=variation_generator,
        review_judge=review_judge,
        srs_config=srs_config,
    )

    # Register async handler
    bus.on_async(VariationGenerationRequested)(service.handle_variation_requested)

    # Set up test data: source + passage + sentence + learning item
    source = Source(text="a" * 200, cefr_level="B1", english_variant="American")
    source_repo.save_source(source)

    # We need a sentence for the learning item FK
    from parla.domain.passage import Hint, Passage, Sentence

    sentence = Sentence(
        order=0,
        ja="テスト文",
        en="Test sentence.",
        hints=Hint(hint1="Test...", hint2="主語 + 動詞"),
    )
    passage = Passage(
        source_id=source.id,
        order=0,
        topic="Test",
        passage_type="説明型",
        sentences=(sentence,),
    )
    source_repo.save_passages([passage])

    item = LearningItem(
        pattern="be responsible for ~ing",
        explanation="〜する責任がある",
        category="構文",
        priority=5,
        source_sentence_id=sentence.id,
        status="auto_stocked",
        next_review_date=date(2026, 4, 10),
    )
    item_repo.save_items([item])

    collector = EventCollector(bus)
    return service, source_repo, item_repo, variation_repo, attempt_repo, bus, collector, source, item


class TestVariationGeneration:
    """Variation generation flow: request → handler → Fake LLM → saved."""

    async def test_variation_saved_to_sqlite(self, tmp_path) -> None:
        service, source_repo, item_repo, variation_repo, _, bus, _, source, item = _setup(tmp_path)

        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        variations = variation_repo.get_variations_by_item(item.id)
        assert len(variations) == 1
        assert "responsible for" in variations[0].en
        assert variations[0].hint1 != ""
        assert variations[0].hint2 != ""

    async def test_variation_ready_event(self, tmp_path) -> None:
        service, _, _, _, _, bus, collector, source, item = _setup(tmp_path)

        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        assert collector.types() == [
            VariationGenerationRequested,
            VariationReady,
        ]

    async def test_variation_failed_event(self, tmp_path) -> None:
        service, _, _, _, _, bus, collector, source, item = _setup(
            tmp_path,
            fail_variation=True,
        )

        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        assert VariationGenerationFailed in collector.types()


class TestReviewJudgment:
    """Review judgment + SRS update flow."""

    async def test_correct_review_advances_srs(self, tmp_path) -> None:
        service, _, item_repo, variation_repo, _, bus, _, source, item = _setup(tmp_path)

        # Generate variation
        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        variation = variation_repo.get_variations_by_item(item.id)[0]

        # Judge review (correct, no hint, timer 50%)
        result = await service.judge_review(
            variation_id=variation.id,
            audio=_make_audio(),
            hint_level=0,
            timer_ratio=0.5,
            today=date(2026, 4, 10),
        )
        assert result.correct is True

        # Check SRS advanced
        updated_item = item_repo.get_item(item.id)
        assert updated_item is not None
        assert updated_item.srs_stage == 1
        assert updated_item.next_review_date == date(2026, 4, 11)

    async def test_incorrect_review_regresses_srs(self, tmp_path) -> None:
        service, _, item_repo, variation_repo, _, bus, _, source, item = _setup(
            tmp_path,
            review_correct=False,
            review_item_used=False,
        )

        # Set item to stage 2 first
        item_repo.update_srs_state(
            item.id,
            srs_stage=2,
            ease_factor=1.0,
            next_review_date=date(2026, 4, 10),
            correct_context_count=0,
        )

        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        variation = variation_repo.get_variations_by_item(item.id)[0]

        result = await service.judge_review(
            variation_id=variation.id,
            audio=_make_audio(),
            hint_level=0,
            timer_ratio=0.5,
            today=date(2026, 4, 10),
        )
        assert result.correct is False

        updated_item = item_repo.get_item(item.id)
        assert updated_item is not None
        assert updated_item.srs_stage == 1

    async def test_review_events_emitted(self, tmp_path) -> None:
        service, _, _, variation_repo, _, bus, collector, source, item = _setup(tmp_path)

        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        variation = variation_repo.get_variations_by_item(item.id)[0]
        await service.judge_review(
            variation_id=variation.id,
            audio=_make_audio(),
            hint_level=0,
            timer_ratio=0.5,
            today=date(2026, 4, 10),
        )

        assert ReviewAnswered in collector.types()
        assert SRSUpdated in collector.types()

        srs_event = next(e for e in collector.events if isinstance(e, SRSUpdated))
        assert srs_event.old_stage == 0
        assert srs_event.new_stage == 1

    async def test_attempt_persisted(self, tmp_path) -> None:
        service, _, _, variation_repo, attempt_repo, bus, _, source, item = _setup(tmp_path)

        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        variation = variation_repo.get_variations_by_item(item.id)[0]
        await service.judge_review(
            variation_id=variation.id,
            audio=_make_audio(),
            hint_level=1,
            timer_ratio=0.6,
            today=date(2026, 4, 10),
        )

        attempts = attempt_repo.get_attempts_by_variation(variation.id)
        assert len(attempts) == 1
        assert attempts[0].attempt_number == 1
        assert attempts[0].hint_level == 1
        assert attempts[0].timer_ratio == 0.6


class TestReviewRetry:
    """Review retry: does NOT update SRS."""

    async def test_retry_does_not_change_srs(self, tmp_path) -> None:
        service, _, item_repo, variation_repo, _, bus, _, source, item = _setup(tmp_path)

        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        variation = variation_repo.get_variations_by_item(item.id)[0]

        # Call retry directly (without initial judge_review) — SRS must not change
        result = await service.judge_review_retry(
            variation_id=variation.id,
            attempt_number=2,
            audio=_make_audio(),
        )
        assert result.correct is True

        # SRS should still be at stage 0 (retry never updates SRS)
        loaded = item_repo.get_item(item.id)
        assert loaded is not None
        assert loaded.srs_stage == 0

    async def test_retry_emits_event(self, tmp_path) -> None:
        service, _, _, variation_repo, _, bus, collector, source, item = _setup(tmp_path)

        tasks = bus.emit(
            VariationGenerationRequested(
                learning_item_id=item.id,
                source_id=source.id,
            )
        )
        await tasks[0]

        variation = variation_repo.get_variations_by_item(item.id)[0]
        await service.judge_review_retry(
            variation_id=variation.id,
            attempt_number=2,
            audio=_make_audio(),
        )

        assert ReviewRetryJudged in collector.types()
        retry_event = next(e for e in collector.events if isinstance(e, ReviewRetryJudged))
        assert retry_event.attempt == 2
        assert retry_event.correct is True


class TestGetDueItems:
    """Due item retrieval."""

    def test_get_due_items(self, tmp_path) -> None:
        service, _, item_repo, _, _, _, _, _, item = _setup(tmp_path)

        due = service.get_due_items(as_of=date(2026, 4, 10))
        assert len(due) == 1
        assert due[0].id == item.id

    def test_no_due_items(self, tmp_path) -> None:
        service, _, item_repo, _, _, _, _, _, item = _setup(tmp_path)

        # Move review date to future
        item_repo.update_srs_state(
            item.id,
            srs_stage=1,
            ease_factor=1.0,
            next_review_date=date(2026, 4, 20),
            correct_context_count=0,
        )

        due = service.get_due_items(as_of=date(2026, 4, 10))
        assert len(due) == 0
