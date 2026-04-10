"""Initial setup screen view (SCREEN-B)."""

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from parla.domain.source import CEFRLevel, EnglishVariant
from parla.ui.screens.setup.view_model import SetupViewModel

CEFR_DESCRIPTIONS: list[tuple[CEFRLevel, str]] = [
    (CEFRLevel.A1, "簡単な自己紹介や日常のやりとりができるレベル"),
    (CEFRLevel.A2, "身近な話題について簡単な文でやりとりできるレベル"),
    (CEFRLevel.B1, "日常的な話題について意見を述べられるレベル"),
    (CEFRLevel.B2, "幅広い話題について明確に意見を述べられるレベル"),
    (CEFRLevel.C1, "複雑な話題でも流暢に自然なやりとりができるレベル"),
    (CEFRLevel.C2, "ネイティブに近い正確さと流暢さで表現できるレベル"),
]


class SetupView(QWidget):
    """Initial setup screen for CEFR level and English variant selection."""

    def __init__(self, view_model: SetupViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("英語レベルを選択してください"))

        self._cefr_group = QButtonGroup(self)
        self._cefr_radios: list[QRadioButton] = []
        for i, (level, desc) in enumerate(CEFR_DESCRIPTIONS):
            radio = QRadioButton(f"{level} — {desc}")
            self._cefr_radios.append(radio)
            self._cefr_group.addButton(radio, i)
            layout.addWidget(radio)

        # Default: B1 (index 2)
        self._cefr_radios[2].setChecked(True)
        self._cefr_group.idClicked.connect(self._on_cefr_selected)

        layout.addWidget(QLabel("英語バリエーション"))
        self._variant_combo = QComboBox()
        self._variant_combo.addItems(list(EnglishVariant))
        self._variant_combo.currentTextChanged.connect(self._on_variant_changed)
        layout.addWidget(self._variant_combo)

        self._confirm_button = QPushButton("始める")
        self._confirm_button.clicked.connect(self._vm.confirm)
        layout.addWidget(self._confirm_button)

        layout.addStretch()

    def _on_cefr_selected(self, button_id: int) -> None:
        level = CEFR_DESCRIPTIONS[button_id][0]
        self._vm.select_cefr(level)

    def _on_variant_changed(self, text: str) -> None:
        if text:
            self._vm.select_variant(text)
