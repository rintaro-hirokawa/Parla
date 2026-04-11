"""Tests for LearningItemQueryService."""

from collections.abc import Sequence
from datetime import date
from uuid import UUID, uuid4

from parla.domain.feedback import SentenceFeedback
from parla.domain.learning_item import LearningItem
from parla.domain.passage import Hint, Passage, Sentence
from parla.domain.source import Source
from parla.services.learning_item_query_service import LearningItemQueryService
from parla.services.query_models import LearningItemFilter


def _make_source(title: str = "Test Source") -> Source:
    return Source(title=title, text="x" * 100, cefr_level="B1", english_variant="American")


def _make_passage(source_id: UUID) -> Passage:
    return Passage(
        source_id=source_id,
        order=0,
        topic="Topic",
        passage_type="dialogue",
        sentences=(
            Sentence(order=0, ja="こんにちは", en="Hello", hints=Hint(hint1="h1", hint2="h2")),
        ),
    )


def _make_item(
    sentence_id: UUID,
    *,
    pattern: str = "present perfect",
    category: str = "文法",
    status: str = "auto_stocked",
    srs_stage: int = 0,
    priority: int = 4,
) -> LearningItem:
    return LearningItem(
        pattern=pattern,
        explanation="explanation",
        category=category,
        priority=priority,
        source_sentence_id=sentence_id,
        status=status,
        srs_stage=srs_stage,
    )


class FakeSourceRepository:
    def __init__(self) -> None:
        self._sources: dict[UUID, Source] = {}
        self._passages: dict[UUID, list[Passage]] = {}
        self._sentence_to_source: dict[UUID, UUID] = {}

    def save_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def get_source(self, source_id: UUID) -> Source | None:
        return self._sources.get(source_id)

    def save_passages(self, passages: Sequence[Passage]) -> None:
        for p in passages:
            self._passages.setdefault(p.source_id, []).append(p)
            for s in p.sentences:
                self._sentence_to_source[s.id] = p.source_id

    def get_passages_by_source(self, source_id: UUID) -> Sequence[Passage]:
        return self._passages.get(source_id, [])

    def get_passage(self, passage_id: UUID) -> Passage | None:
        for passages in self._passages.values():
            for p in passages:
                if p.id == passage_id:
                    return p
        return None

    def get_source_by_sentence_id(self, sentence_id: UUID) -> Source | None:
        source_id = self._sentence_to_source.get(sentence_id)
        if source_id is None:
            return None
        return self._sources.get(source_id)

    def get_active_sources(self) -> Sequence[Source]:
        return [s for s in self._sources.values() if s.status in ("not_started", "in_progress")]

    def get_all_sources(self) -> Sequence[Source]:
        return list(self._sources.values())

    def update_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def get_sentence(self, sentence_id: UUID) -> Sentence | None:
        for passages in self._passages.values():
            for p in passages:
                for s in p.sentences:
                    if s.id == sentence_id:
                        return s
        return None

    def get_passage_by_sentence_id(self, sentence_id: UUID) -> Passage | None:
        for passages in self._passages.values():
            for p in passages:
                for s in p.sentences:
                    if s.id == sentence_id:
                        return p
        return None


class FakeLearningItemRepository:
    def __init__(self) -> None:
        self._items: list[LearningItem] = []

    def save_items(self, items: Sequence[LearningItem]) -> None:
        self._items.extend(items)

    def get_stocked_items(self) -> Sequence[LearningItem]:
        return [i for i in self._items if i.status == "auto_stocked"]

    def get_items_by_sentence(self, sentence_id: UUID) -> Sequence[LearningItem]:
        return [i for i in self._items if i.source_sentence_id == sentence_id]

    def get_item(self, item_id: UUID) -> LearningItem | None:
        for i in self._items:
            if i.id == item_id:
                return i
        return None

    def get_due_items(self, as_of: date, limit: int = 20) -> Sequence[LearningItem]:
        return []

    def count_due_items(self, as_of: date) -> int:
        return 0

    def update_item_status(self, item_id: UUID, status: str) -> None:
        pass

    def update_srs_state(self, *args: object, **kwargs: object) -> None:
        pass

    def get_all_items(self) -> Sequence[LearningItem]:
        return list(self._items)


class FakeFeedbackRepository:
    def __init__(self) -> None:
        self._feedbacks: dict[UUID, SentenceFeedback] = {}

    def save_feedback(self, feedback: SentenceFeedback) -> None:
        self._feedbacks[feedback.sentence_id] = feedback

    def get_feedback_by_sentence(self, sentence_id: UUID) -> SentenceFeedback | None:
        return self._feedbacks.get(sentence_id)

    def save_practice_attempt(self, attempt: object) -> None:
        pass

    def get_attempts_by_sentence(self, sentence_id: UUID) -> Sequence[object]:
        return []


def _make_service(
    *,
    item_repo: FakeLearningItemRepository | None = None,
    source_repo: FakeSourceRepository | None = None,
    feedback_repo: FakeFeedbackRepository | None = None,
) -> LearningItemQueryService:
    return LearningItemQueryService(
        item_repo=item_repo or FakeLearningItemRepository(),
        source_repo=source_repo or FakeSourceRepository(),
        feedback_repo=feedback_repo or FakeFeedbackRepository(),
    )


class TestListItems:
    def test_empty(self) -> None:
        service = _make_service()
        result = service.list_items()
        assert result == ()

    def test_returns_items_with_source_info(self) -> None:
        source_repo = FakeSourceRepository()
        item_repo = FakeLearningItemRepository()

        source = _make_source(title="My Source")
        source_repo.save_source(source)
        passage = _make_passage(source.id)
        source_repo.save_passages([passage])
        sentence = passage.sentences[0]

        item = _make_item(sentence.id)
        item_repo.save_items([item])

        service = _make_service(item_repo=item_repo, source_repo=source_repo)
        result = service.list_items()
        assert len(result) == 1
        row = result[0]
        assert row.id == item.id
        assert row.pattern == "present perfect"
        assert row.source_title == "My Source"
        assert row.source_sentence_ja == "こんにちは"

    def test_filter_by_category(self) -> None:
        source_repo = FakeSourceRepository()
        item_repo = FakeLearningItemRepository()

        source = _make_source()
        source_repo.save_source(source)
        passage = _make_passage(source.id)
        source_repo.save_passages([passage])
        sentence = passage.sentences[0]

        item1 = _make_item(sentence.id, category="文法")
        item2 = _make_item(sentence.id, category="語彙")
        item_repo.save_items([item1, item2])

        service = _make_service(item_repo=item_repo, source_repo=source_repo)
        result = service.list_items(filter=LearningItemFilter(category="語彙"))
        assert len(result) == 1
        assert result[0].category == "語彙"

    def test_filter_by_srs_stage(self) -> None:
        source_repo = FakeSourceRepository()
        item_repo = FakeLearningItemRepository()

        source = _make_source()
        source_repo.save_source(source)
        passage = _make_passage(source.id)
        source_repo.save_passages([passage])
        sentence = passage.sentences[0]

        item1 = _make_item(sentence.id, srs_stage=0)
        item2 = _make_item(sentence.id, srs_stage=3)
        item_repo.save_items([item1, item2])

        service = _make_service(item_repo=item_repo, source_repo=source_repo)
        result = service.list_items(filter=LearningItemFilter(srs_stage=3))
        assert len(result) == 1
        assert result[0].srs_stage == 3

    def test_filter_by_source_id(self) -> None:
        source_repo = FakeSourceRepository()
        item_repo = FakeLearningItemRepository()

        source1 = _make_source(title="Source 1")
        source2 = _make_source(title="Source 2")
        source_repo.save_source(source1)
        source_repo.save_source(source2)
        passage1 = _make_passage(source1.id)
        passage2 = _make_passage(source2.id)
        source_repo.save_passages([passage1, passage2])

        item1 = _make_item(passage1.sentences[0].id)
        item2 = _make_item(passage2.sentences[0].id)
        item_repo.save_items([item1, item2])

        service = _make_service(item_repo=item_repo, source_repo=source_repo)
        result = service.list_items(filter=LearningItemFilter(source_id=source1.id))
        assert len(result) == 1
        assert result[0].source_title == "Source 1"


class TestGetSentenceItems:
    def test_returns_items_for_sentence(self) -> None:
        source_repo = FakeSourceRepository()
        item_repo = FakeLearningItemRepository()

        source = _make_source()
        source_repo.save_source(source)
        passage = _make_passage(source.id)
        source_repo.save_passages([passage])
        sentence = passage.sentences[0]

        item = _make_item(sentence.id)
        item_repo.save_items([item])

        service = _make_service(item_repo=item_repo, source_repo=source_repo)
        result = service.get_sentence_items(sentence.id)
        assert len(result) == 1
        assert result[0].id == item.id
        assert result[0].pattern == "present perfect"

    def test_empty_for_unknown_sentence(self) -> None:
        service = _make_service()
        result = service.get_sentence_items(uuid4())
        assert result == ()


class TestGetItemDetail:
    def _make_service(
        self,
    ) -> tuple[
        LearningItemQueryService,
        FakeSourceRepository,
        FakeLearningItemRepository,
        FakeFeedbackRepository,
    ]:
        source_repo = FakeSourceRepository()
        item_repo = FakeLearningItemRepository()
        feedback_repo = FakeFeedbackRepository()
        service = LearningItemQueryService(
            item_repo=item_repo,
            source_repo=source_repo,
            feedback_repo=feedback_repo,
        )
        return service, source_repo, item_repo, feedback_repo

    def test_returns_none_for_unknown_item(self) -> None:
        service, *_ = self._make_service()
        result = service.get_item_detail(uuid4())
        assert result is None

    def test_basic_detail(self) -> None:
        service, source_repo, item_repo, *_ = self._make_service()
        source = _make_source(title="My Source")
        source_repo.save_source(source)
        passage = _make_passage(source.id)
        source_repo.save_passages([passage])
        sentence = passage.sentences[0]

        item = _make_item(sentence.id, pattern="past tense")
        item_repo.save_items([item])

        detail = service.get_item_detail(item.id)
        assert detail is not None
        assert detail.pattern == "past tense"
        assert detail.source_title == "My Source"
        assert detail.source_sentence_ja == "こんにちは"
        assert detail.source_sentence_en == "Hello"

    def test_includes_first_utterance(self) -> None:
        service, source_repo, item_repo, feedback_repo = self._make_service()
        source = _make_source()
        source_repo.save_source(source)
        passage = _make_passage(source.id)
        source_repo.save_passages([passage])
        sentence = passage.sentences[0]

        item = _make_item(sentence.id)
        item_repo.save_items([item])

        feedback = SentenceFeedback(
            sentence_id=sentence.id,
            user_utterance="I go to school yesterday",
            model_answer="I went to school yesterday",
            is_acceptable=False,
        )
        feedback_repo.save_feedback(feedback)

        detail = service.get_item_detail(item.id)
        assert detail is not None
        assert detail.first_utterance == "I go to school yesterday"

