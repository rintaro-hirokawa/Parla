"""Settings screen view (SCREEN-C5)."""

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.domain.source import CEFRLevel, EnglishVariant
from parla.ui.screens.settings.view_model import SettingsViewModel


class SettingsView(QWidget):
    """Settings tab allowing users to change CEFR and variant."""

    def __init__(self, view_model: SettingsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._updating = False

        self._cefr_combo = QComboBox()
        self._cefr_combo.addItems(list(CEFRLevel))

        self._variant_combo = QComboBox()
        self._variant_combo.addItems(list(EnglishVariant))

        self._sources_button = QPushButton("ソース管理")

        form = QFormLayout()
        form.addRow("CEFRレベル", self._cefr_combo)
        form.addRow("英語バリエーション", self._variant_combo)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._sources_button)
        layout.addStretch()

        self._vm.settings_changed.connect(self._set_ui_values)
        self._cefr_combo.currentTextChanged.connect(self._on_cefr_changed)
        self._variant_combo.currentTextChanged.connect(self._on_variant_changed)
        self._sources_button.clicked.connect(self._vm.open_sources)

    def _set_ui_values(self, cefr: str, variant: str) -> None:
        """Update UI widgets without triggering service calls."""
        self._updating = True
        self._cefr_combo.setCurrentText(cefr)
        self._variant_combo.setCurrentText(variant)
        self._updating = False

    def _on_cefr_changed(self, text: str) -> None:
        if not self._updating and text:
            self._vm.update_cefr_level(CEFRLevel(text))

    def _on_variant_changed(self, text: str) -> None:
        if not self._updating and text:
            self._vm.update_english_variant(EnglishVariant(text))
