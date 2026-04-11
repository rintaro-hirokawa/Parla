"""Tests for UserSettings domain entity."""

import pytest
from pydantic import ValidationError

from parla.domain.user_settings import UserSettings


class TestUserSettings:
    def test_defaults(self) -> None:
        settings = UserSettings()
        assert settings.cefr_level == "B1"
        assert settings.english_variant == "American"

    def test_custom_values(self) -> None:
        settings = UserSettings(
            cefr_level="C1",
            english_variant="British",
        )
        assert settings.cefr_level == "C1"
        assert settings.english_variant == "British"

    def test_all_cefr_levels(self) -> None:
        for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
            settings = UserSettings(cefr_level=level)
            assert settings.cefr_level == level

    def test_all_english_variants(self) -> None:
        for variant in ("American", "British", "Australian", "Canadian", "Indian"):
            settings = UserSettings(english_variant=variant)
            assert settings.english_variant == variant

    def test_invalid_cefr_level(self) -> None:
        with pytest.raises(ValidationError):
            UserSettings(cefr_level="D1")  # type: ignore[arg-type]

    def test_invalid_english_variant(self) -> None:
        with pytest.raises(ValidationError):
            UserSettings(english_variant="Japanese")  # type: ignore[arg-type]

    def test_model_copy(self) -> None:
        settings = UserSettings()
        updated = settings.model_copy(update={"cefr_level": "C2"})
        assert updated.cefr_level == "C2"
        assert settings.cefr_level == "B1"  # original unchanged
