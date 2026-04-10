"""ViewModel for the Settings screen (SCREEN-C5)."""

from PySide6.QtCore import Signal

from parla.domain.events import SettingsChanged
from parla.domain.source import CEFRLevel, EnglishVariant
from parla.event_bus import EventBus
from parla.services.settings_service import SettingsService
from parla.ui.base_view_model import BaseViewModel


class SettingsViewModel(BaseViewModel):
    """Bridges SettingsService and the Settings View."""

    settings_changed = Signal(str, str, bool)  # cefr, variant, phonetic
    navigate_to_sources = Signal()

    def __init__(self, event_bus: EventBus, settings_service: SettingsService) -> None:
        super().__init__(event_bus)
        self._settings_service = settings_service
        self._cefr_level: CEFRLevel = CEFRLevel.B1
        self._english_variant: EnglishVariant = EnglishVariant.AMERICAN
        self._phonetic_display: bool = False
        self._register_sync(SettingsChanged, self._on_settings_changed)

    @property
    def cefr_level(self) -> CEFRLevel:
        return self._cefr_level

    @property
    def english_variant(self) -> EnglishVariant:
        return self._english_variant

    @property
    def phonetic_display(self) -> bool:
        return self._phonetic_display

    def load_settings(self) -> None:
        """Load current settings from service and emit settings_changed."""
        settings = self._settings_service.get_settings()
        self._cefr_level = settings.cefr_level
        self._english_variant = settings.english_variant
        self._phonetic_display = settings.phonetic_display
        self.settings_changed.emit(self._cefr_level, self._english_variant, self._phonetic_display)

    def update_cefr_level(self, level: CEFRLevel) -> None:
        self._settings_service.update_settings(cefr_level=level)

    def update_english_variant(self, variant: EnglishVariant) -> None:
        self._settings_service.update_settings(english_variant=variant)

    def update_phonetic_display(self, enabled: bool) -> None:
        self._settings_service.update_settings(phonetic_display=enabled)

    def open_sources(self) -> None:
        """Request navigation to source management screens."""
        self.navigate_to_sources.emit()

    def _on_settings_changed(self, event: SettingsChanged) -> None:
        self._cefr_level = event.cefr_level
        self._english_variant = event.english_variant
        self._phonetic_display = event.phonetic_display
        self.settings_changed.emit(self._cefr_level, self._english_variant, self._phonetic_display)
