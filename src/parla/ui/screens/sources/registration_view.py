"""Source registration screen view (SCREEN-D1)."""

from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from parla.ui.screens.sources.registration_view_model import SourceRegistrationViewModel


class SourceRegistrationView(QWidget):
    """Source registration form with text input, title, and progress display."""

    def __init__(self, view_model: SourceRegistrationViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model

        layout = QVBoxLayout(self)

        # --- CEFR level display ---
        self._cefr_label = QLabel()
        layout.addWidget(self._cefr_label)

        # --- Title input ---
        layout.addWidget(QLabel("タイトル"))
        self._title_edit = QLineEdit()
        self._title_edit.textChanged.connect(self._on_input_changed)
        layout.addWidget(self._title_edit)

        # --- Text input ---
        layout.addWidget(QLabel("テキスト（100〜50,000文字）"))
        self._text_edit = QPlainTextEdit()
        self._text_edit.textChanged.connect(self._on_input_changed)
        layout.addWidget(self._text_edit)

        # --- Char count ---
        self._char_count_label = QLabel("0文字")
        layout.addWidget(self._char_count_label)

        # --- Error message ---
        self._error_label = QLabel()
        layout.addWidget(self._error_label)

        # --- Register button ---
        self._register_button = QPushButton("登録")
        self._register_button.setEnabled(False)
        self._register_button.clicked.connect(self._on_register_clicked)
        layout.addWidget(self._register_button)

        # --- Progress display ---
        self._progress_label = QLabel()
        layout.addWidget(self._progress_label)

        layout.addStretch()

        # --- Signal connections ---
        self._vm.cefr_level_loaded.connect(self._on_cefr_loaded)
        self._vm.validation_changed.connect(self._on_validation_changed)
        self._vm.registration_started.connect(self._on_registration_started)
        self._vm.generation_progress.connect(self._on_progress)
        self._vm.generation_completed.connect(self._on_completed)
        self._vm.generation_failed.connect(self._on_failed)

    def _on_cefr_loaded(self, cefr: str) -> None:
        self._cefr_label.setText(f"CEFRレベル: {cefr}")

    def _on_input_changed(self) -> None:
        text = self._text_edit.toPlainText()
        self._char_count_label.setText(f"{len(text)}文字")
        self._vm.validate(text, self._title_edit.text())

    def _on_validation_changed(self, is_valid: bool, error_message: str) -> None:
        self._register_button.setEnabled(is_valid)
        self._error_label.setText(error_message)

    def _on_register_clicked(self) -> None:
        self._vm.register(self._text_edit.toPlainText(), self._title_edit.text())

    def _on_registration_started(self) -> None:
        self._register_button.setEnabled(False)
        self._text_edit.setEnabled(False)
        self._title_edit.setEnabled(False)
        self._progress_label.setText("登録完了。パッセージ生成を待っています...")

    def _on_progress(self, message: str) -> None:
        self._progress_label.setText(message)

    def _on_completed(self, passage_count: int, sentence_count: int) -> None:
        self._progress_label.setText(f"完了: {passage_count}パッセージ、{sentence_count}センテンス生成")

    def _on_failed(self, error_message: str) -> None:
        self._progress_label.setText(f"エラー: {error_message}")
