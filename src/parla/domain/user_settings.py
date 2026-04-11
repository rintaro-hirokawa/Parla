"""User settings entity."""

from pydantic import BaseModel

from parla.domain.source import CEFRLevel, EnglishVariant


class UserSettings(BaseModel):
    """Application-level user settings (single-user desktop app)."""

    cefr_level: CEFRLevel = CEFRLevel.B1
    english_variant: EnglishVariant = EnglishVariant.AMERICAN
