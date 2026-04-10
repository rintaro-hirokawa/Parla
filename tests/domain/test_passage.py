"""Tests for Passage, Sentence, and Hint value objects."""

from uuid import uuid4

import pytest

from parla.domain.passage import Hint, Passage, Sentence


class TestHint:
    def test_hint_is_frozen(self) -> None:
        hint = Hint(hint1="Chairman ... test", hint2="主語 + 動詞")
        with pytest.raises(Exception):  # noqa: B017
            hint.hint1 = "changed"  # type: ignore[misc]


class TestSentence:
    def test_sentence_is_frozen(self) -> None:
        sentence = Sentence(
            order=0,
            ja="会長は自ら試験を行う",
            en="The chairman tests it himself",
            hints=Hint(hint1="The ... test / himself", hint2="主語 + 動詞(現在形) + 目的語"),
        )
        with pytest.raises(Exception):  # noqa: B017
            sentence.ja = "changed"  # type: ignore[misc]

    def test_sentence_has_auto_id(self) -> None:
        s1 = Sentence(order=0, ja="a", en="b", hints=Hint(hint1="x", hint2="y"))
        s2 = Sentence(order=1, ja="c", en="d", hints=Hint(hint1="x", hint2="y"))
        assert s1.id != s2.id


class TestPassage:
    def _make_sentence(self, order: int = 0) -> Sentence:
        return Sentence(
            order=order,
            ja="日本語",
            en="English",
            hints=Hint(hint1="hint1", hint2="hint2"),
        )

    def test_passage_is_frozen(self) -> None:
        passage = Passage(
            source_id=uuid4(),
            order=0,
            topic="テスト",
            passage_type="説明型",
            sentences=(self._make_sentence(),),
        )
        with pytest.raises(Exception):  # noqa: B017
            passage.topic = "changed"  # type: ignore[misc]

    def test_passage_has_auto_id(self) -> None:
        p1 = Passage(
            source_id=uuid4(),
            order=0,
            topic="a",
            passage_type="説明型",
            sentences=(self._make_sentence(),),
        )
        p2 = Passage(
            source_id=uuid4(),
            order=1,
            topic="b",
            passage_type="説明型",
            sentences=(self._make_sentence(),),
        )
        assert p1.id != p2.id

    def test_passage_requires_non_empty_sentences(self) -> None:
        with pytest.raises(ValueError, match="at least one sentence"):
            Passage(
                source_id=uuid4(),
                order=0,
                topic="a",
                passage_type="説明型",
                sentences=(),
            )

    def test_passage_with_multiple_sentences(self) -> None:
        sentences = tuple(self._make_sentence(i) for i in range(5))
        passage = Passage(
            source_id=uuid4(),
            order=0,
            topic="topic",
            passage_type="説明型",
            sentences=sentences,
        )
        assert len(passage.sentences) == 5
