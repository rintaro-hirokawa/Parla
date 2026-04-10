"""Settings screen view (SCREEN-C5)."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.ui.screens.settings.view_model import SettingsViewModel

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
ENGLISH_VARIANTS = ("American", "British", "Australian", "Canadian", "Indian")


class SettingsView(QWidget):
    """Settings tab allowing users to change CEFR, variant, and phonetic display."""

    def __init__(self, view_model: SettingsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._updating = False

        # --- Widgets ---
        self._cefr_combo = QComboBox()
        self._cefr_combo.addItems(CEFR_LEVELS)

        self._variant_combo = QComboBox()
        self._variant_combo.addItems(ENGLISH_VARIANTS)

        self._phonetic_check = QCheckBox("発音記号を表示する")

        self._sources_button = QPushButton("ソース管理")

        # --- Layout ---
        form = QFormLayout()
        form.addRow("CEFRレベル", self._cefr_combo)
        form.addRow("英語バリエーション", self._variant_combo)
        form.addRow(self._phonetic_check)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._sources_button)
        layout.addStretch()

        # --- Signal connections ---
        self._vm.settings_loaded.connect(self._on_settings_loaded)
        self._vm.settings_updated.connect(self._on_settings_updated)

        self._cefr_combo.currentTextChanged.connect(self._on_cefr_changed)
        self._variant_combo.currentTextChanged.connect(self._on_variant_changed)
        self._phonetic_check.toggled.connect(self._on_phonetic_toggled)
        self._sources_button.clicked.connect(self._vm.open_sources)

    def _on_settings_loaded(self, cefr: str, variant: str, phonetic: bool) -> None:
        self._set_ui_values(cefr, variant, phonetic)

    def _on_settings_updated(self, cefr: str, variant: str, phonetic: bool) -> None:
        self._set_ui_values(cefr, variant, phonetic)

    def _set_ui_values(self, cefr: str, variant: str, phonetic: bool) -> None:
        """Update UI widgets without triggering service calls."""
        self._updating = True
        self._cefr_combo.setCurrentText(cefr)
        self._variant_combo.setCurrentText(variant)
        self._phonetic_check.setChecked(phonetic)
        self._updating = False

    def _on_cefr_changed(self, text: str) -> None:
        if not self._updating and text:
            self._vm.update_cefr_level(text)

    def _on_variant_changed(self, text: str) -> None:
        if not self._updating and text:
            self._vm.update_english_variant(text)

    def _on_phonetic_toggled(self, checked: bool) -> None:
        if not self._updating:
            self._vm.update_phonetic_display(checked)
