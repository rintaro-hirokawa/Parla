"""Pill-shaped status badge (correct / needs-review / loading)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from parla.ui import theme


class StatusBadgeWidget(QLabel):
    """Small pill badge showing status text with colour coding."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status("loading", "")

    def set_status(self, status: str, text: str) -> None:
        self.setText(text)
        if status == "correct":
            self.setStyleSheet(
                f"background: {theme.rgb(theme.CORRECT_BG)}; "
                f"color: {theme.rgb(theme.CORRECT_TEXT)}; "
                f"border: 1px solid {theme.rgb(theme.CORRECT_BORDER)}; "
                f"border-radius: 10px; padding: 4px 14px; "
                f"font-size: 12px; font-weight: 600;"
            )
        elif status == "needs-review":
            self.setStyleSheet(
                f"background: {theme.rgb(theme.REVIEW_BG)}; "
                f"color: {theme.rgb(theme.REVIEW_TEXT)}; "
                f"border: 1px solid {theme.rgb(theme.REVIEW_BORDER)}; "
                f"border-radius: 10px; padding: 4px 14px; "
                f"font-size: 12px; font-weight: 600;"
            )
        else:
            self.setStyleSheet(
                f"background: {theme.rgb(theme.BG_SURFACE)}; "
                f"color: {theme.rgb(theme.TEXT_TERTIARY)}; "
                f"border: 1px solid {theme.rgb(theme.BORDER)}; "
                f"border-radius: 10px; padding: 4px 14px; "
                f"font-size: 12px; font-weight: 600;"
            )
