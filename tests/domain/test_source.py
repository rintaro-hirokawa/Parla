"""Tests for Source entity."""

import pytest
from pydantic import ValidationError

from parla.domain.errors import InvalidStatusTransition, SourceTextTooLong, SourceTextTooShort
from parla.domain.source import Source


class TestSourceValidation:
    def test_valid_source(self) -> None:
        source = Source(text="a" * 100, cefr_level="B1", english_variant="American")
        assert source.status == "registered"
        assert source.title == ""

    def test_text_too_short(self) -> None:
        with pytest.raises((SourceTextTooShort, ValidationError)):
            Source(text="a" * 99, cefr_level="B1", english_variant="American")

    def test_text_too_long(self) -> None:
        with pytest.raises((SourceTextTooLong, ValidationError)):
            Source(text="a" * 50_001, cefr_level="B1", english_variant="American")

    def test_text_at_minimum_boundary(self) -> None:
        source = Source(text="a" * 100, cefr_level="B1", english_variant="American")
        assert len(source.text) == 100

    def test_text_at_maximum_boundary(self) -> None:
        source = Source(text="a" * 50_000, cefr_level="B1", english_variant="American")
        assert len(source.text) == 50_000

    def test_title_defaults_to_empty(self) -> None:
        source = Source(text="a" * 100, cefr_level="B1", english_variant="American")
        assert source.title == ""

    def test_title_can_be_set(self) -> None:
        source = Source(
            text="a" * 100, cefr_level="B1", english_variant="American", title="My Source"
        )
        assert source.title == "My Source"

    def test_id_is_auto_generated(self) -> None:
        s1 = Source(text="a" * 100, cefr_level="B1", english_variant="American")
        s2 = Source(text="a" * 100, cefr_level="B1", english_variant="American")
        assert s1.id != s2.id

    def test_timestamps_are_auto_generated(self) -> None:
        source = Source(text="a" * 100, cefr_level="B1", english_variant="American")
        assert source.created_at is not None
        assert source.updated_at is not None


class TestSourceStatusTransitions:
    def _make_source(self) -> Source:
        return Source(text="a" * 100, cefr_level="B1", english_variant="American")

    def test_registered_to_generating(self) -> None:
        source = self._make_source()
        updated = source.start_generating()
        assert updated.status == "generating"
        assert updated.id == source.id

    def test_generating_to_not_started(self) -> None:
        source = self._make_source().start_generating()
        updated = source.complete_generation()
        assert updated.status == "not_started"

    def test_generating_to_generation_failed(self) -> None:
        source = self._make_source().start_generating()
        updated = source.fail_generation()
        assert updated.status == "generation_failed"

    def test_registered_to_not_started_is_invalid(self) -> None:
        source = self._make_source()
        with pytest.raises(InvalidStatusTransition):
            source.complete_generation()

    def test_registered_to_generation_failed_is_invalid(self) -> None:
        source = self._make_source()
        with pytest.raises(InvalidStatusTransition):
            source.fail_generation()

    def test_not_started_to_generating_is_invalid(self) -> None:
        source = self._make_source().start_generating().complete_generation()
        with pytest.raises(InvalidStatusTransition):
            source.start_generating()

    def test_transition_returns_new_instance(self) -> None:
        source = self._make_source()
        updated = source.start_generating()
        assert source is not updated
        assert source.status == "registered"

    def test_transition_updates_updated_at(self) -> None:
        source = self._make_source()
        updated = source.start_generating()
        assert updated.updated_at >= source.updated_at
