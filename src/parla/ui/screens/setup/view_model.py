"""ViewModel for the Initial Setup screen (SCREEN-B)."""

from PySide6.QtCore import Signal

from parla.domain.source import CEFRLevel, EnglishVariant
from parla.event_bus import EventBus
from parla.services.settings_service import SettingsService
from parla.ui.base_view_model import BaseViewModel


class SetupViewModel(BaseViewModel):
    """Manages initial CEFR and English variant selection."""

    setup_completed = Signal()

    def __init__(self, event_bus: EventBus, settings_service: SettingsService) -> None:
        super().__init__(event_bus)
        self._settings_service = settings_service
        self._selected_cefr: CEFRLevel = "B1"
        self._selected_variant: EnglishVariant = "American"

    @property
    def selected_cefr(self) -> CEFRLevel:
        return self._selected_cefr

    @property
    def selected_variant(self) -> EnglishVariant:
        return self._selected_variant

    def select_cefr(self, level: CEFRLevel) -> None:
        self._selected_cefr = level

    def select_variant(self, variant: EnglishVariant) -> None:
        self._selected_variant = variant

    def confirm(self) -> None:
        """Save selected settings and signal completion."""
        self._settings_service.update_settings(
            cefr_level=self._selected_cefr,
            english_variant=self._selected_variant,
        )
        self.setup_completed.emit()
