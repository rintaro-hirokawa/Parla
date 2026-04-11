"""Tests for SQLiteUserSettingsRepository."""

import pytest

from parla.adapters.sqlite_db import create_connection, init_schema
from parla.adapters.sqlite_user_settings_repository import SQLiteUserSettingsRepository
from parla.domain.user_settings import UserSettings


@pytest.fixture
def repo():
    conn = create_connection()
    init_schema(conn)
    return SQLiteUserSettingsRepository(conn)


class TestSQLiteUserSettingsRepository:
    def test_get_returns_defaults_on_first_call(self, repo: SQLiteUserSettingsRepository) -> None:
        settings = repo.get()
        assert settings.cefr_level == "B1"
        assert settings.english_variant == "American"

    def test_save_and_get(self, repo: SQLiteUserSettingsRepository) -> None:
        repo.save(UserSettings(cefr_level="C1", english_variant="British"))
        settings = repo.get()
        assert settings.cefr_level == "C1"
        assert settings.english_variant == "British"

    def test_save_overwrites(self, repo: SQLiteUserSettingsRepository) -> None:
        repo.save(UserSettings(cefr_level="A1"))
        repo.save(UserSettings(cefr_level="C2", english_variant="Indian"))
        settings = repo.get()
        assert settings.cefr_level == "C2"
        assert settings.english_variant == "Indian"

    def test_partial_update_via_model_copy(self, repo: SQLiteUserSettingsRepository) -> None:
        original = repo.get()
        updated = original.model_copy(update={"cefr_level": "C1"})
        repo.save(updated)
        result = repo.get()
        assert result.cefr_level == "C1"
        assert result.english_variant == "American"  # unchanged

    def test_exists_false_before_save(self, repo: SQLiteUserSettingsRepository) -> None:
        assert repo.exists() is False

    def test_exists_true_after_save(self, repo: SQLiteUserSettingsRepository) -> None:
        repo.save(UserSettings())
        assert repo.exists() is True

    def test_exists_true_after_get_auto_creates(self, repo: SQLiteUserSettingsRepository) -> None:
        repo.get()  # auto-creates defaults
        assert repo.exists() is True

    def test_get_creates_row_only_once(self, repo: SQLiteUserSettingsRepository) -> None:
        repo.get()
        repo.get()
        # Should not raise — single-row constraint maintained
        settings = repo.get()
        assert settings.cefr_level == "B1"
