"""Segmented mode control for RunThrough screen (Listen / Overlap / Speak)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from parla.ui import theme


class ModeSegmentWidget(QWidget):
    """Pill-shaped segment control with 3 mode buttons."""

    mode_changed = Signal(str)

    _BUTTON_QSS_INACTIVE = f"""
        QPushButton {{
            background: transparent;
            color: {theme.rgb(theme.TEXT_SECONDARY)};
            border: none;
            border-radius: 9px;
            padding: 9px 22px;
            font-size: 13px;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background: {theme.rgb(theme.BG_SURFACE)};
            color: {theme.rgb(theme.TEXT_PRIMARY)};
        }}
    """

    _BUTTON_QSS_ACTIVE = f"""
        QPushButton {{
            background: {theme.rgb(theme.ACCENT)};
            color: #ffffff;
            border: none;
            border-radius: 9px;
            padding: 9px 22px;
            font-size: 13px;
            font-weight: 500;
        }}
    """

    def __init__(
        self,
        modes: list[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        """Create segment control.

        Args:
            modes: List of (mode_key, display_label) tuples.
        """
        super().__init__(parent)
        self._current_mode = modes[0][0] if modes else ""
        self._buttons: dict[str, QPushButton] = {}

        self.setStyleSheet(
            f"background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 12px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        for key, label in modes:
            btn = QPushButton(label)
            btn.setCursor(self.cursor())
            btn.clicked.connect(lambda _checked, k=key: self._on_click(k))
            self._buttons[key] = btn
            layout.addWidget(btn)

        self._update_styles()

    @property
    def current_mode(self) -> str:
        return self._current_mode

    def set_mode(self, mode: str) -> None:
        if mode == self._current_mode:
            return
        self._current_mode = mode
        self._update_styles()
        self.mode_changed.emit(mode)

    def _on_click(self, mode: str) -> None:
        self.set_mode(mode)

    def _update_styles(self) -> None:
        for key, btn in self._buttons.items():
            if key == self._current_mode:
                btn.setStyleSheet(self._BUTTON_QSS_ACTIVE)
            else:
                btn.setStyleSheet(self._BUTTON_QSS_INACTIVE)
