"""ViewModel for Source Registration screen (SCREEN-D1)."""

import uuid  # noqa: TC003 — used in runtime type annotation

from PySide6.QtCore import Signal

from parla.domain.events import (
    PassageGenerationCompleted,
    PassageGenerationFailed,
    PassageGenerationStarted,
)
from parla.domain.source import MAX_TEXT_LENGTH, MIN_TEXT_LENGTH, CEFRLevel, EnglishVariant
from parla.event_bus import EventBus
from parla.services.settings_service import SettingsService
from parla.services.source_service import SourceService
from parla.ui.base_view_model import BaseViewModel


class SourceRegistrationViewModel(BaseViewModel):
    """Manages source registration form state and generation progress."""

    validation_changed = Signal(bool, str)  # is_valid, error_message
    registration_started = Signal()
    generation_progress = Signal(str)
    generation_completed = Signal(int, int)  # passage_count, sentence_count
    generation_failed = Signal(str)
    navigate_back = Signal()
    cefr_level_loaded = Signal(str)

    def __init__(
        self,
        event_bus: EventBus,
        source_service: SourceService,
        settings_service: SettingsService,
    ) -> None:
        super().__init__(event_bus)
        self._source_service = source_service
        self._settings_service = settings_service
        self._cefr_level: CEFRLevel = CEFRLevel.B1
        self._english_variant: EnglishVariant = EnglishVariant.AMERICAN
        self._pending_source_id: uuid.UUID | None = None
        self._register_sync(PassageGenerationStarted, self._on_generation_started)
        self._register_sync(PassageGenerationCompleted, self._on_generation_completed)
        self._register_sync(PassageGenerationFailed, self._on_generation_failed)

    @property
    def cefr_level(self) -> CEFRLevel:
        return self._cefr_level

    @property
    def english_variant(self) -> EnglishVariant:
        return self._english_variant

    def load_settings(self) -> None:
        """Load CEFR level and variant from current user settings."""
        settings = self._settings_service.get_settings()
        self._cefr_level = settings.cefr_level
        self._english_variant = settings.english_variant
        self.cefr_level_loaded.emit(self._cefr_level)

    def validate(self, text: str, title: str) -> None:
        """Validate registration form and emit validation_changed."""
        text_len = len(text)
        if text_len < MIN_TEXT_LENGTH:
            self.validation_changed.emit(False, f"テキストは{MIN_TEXT_LENGTH}文字以上必要です（現在{text_len}文字）")
            return
        if text_len > MAX_TEXT_LENGTH:
            msg = f"テキストは{MAX_TEXT_LENGTH}文字以下にしてください（現在{text_len}文字）"
            self.validation_changed.emit(False, msg)
            return
        if not title.strip():
            self.validation_changed.emit(False, "タイトルを入力してください")
            return
        self.validation_changed.emit(True, "")

    def register(self, text: str, title: str) -> None:
        """Register a new source."""
        source = self._source_service.register_source(
            text=text,
            title=title,
            cefr_level=self._cefr_level,
            english_variant=self._english_variant,
        )
        self._pending_source_id = source.id
        self.registration_started.emit()

    def _on_generation_started(self, event: PassageGenerationStarted) -> None:
        if event.source_id == self._pending_source_id:
            self.generation_progress.emit("パッセージ生成中...")

    def _on_generation_completed(self, event: PassageGenerationCompleted) -> None:
        if event.source_id == self._pending_source_id:
            self.generation_completed.emit(event.passage_count, event.total_sentences)
            self.navigate_back.emit()

    def _on_generation_failed(self, event: PassageGenerationFailed) -> None:
        if event.source_id == self._pending_source_id:
            self.generation_failed.emit(event.error_message)
