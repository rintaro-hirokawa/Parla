"""Reusable playback transport controls widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


def _format_time(seconds: float) -> str:
    """Format seconds as m:ss."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


class PlaybackControlsWidget(QWidget):
    """Transport controls: seek bar, play/pause, reset, ±2s skip."""

    play_pause_clicked = Signal()
    seek_requested = Signal(float)  # seconds
    skip_requested = Signal(float)  # delta seconds
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # --- Buttons ---
        self._reset_btn = QPushButton("⏮")
        self._back_btn = QPushButton("-2s")
        self._play_pause_btn = QPushButton("▶")
        self._forward_btn = QPushButton("+2s")

        for btn in (self._reset_btn, self._back_btn, self._forward_btn):
            btn.setFixedWidth(48)
        self._play_pause_btn.setFixedWidth(56)

        # --- Seek bar ---
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setValue(0)

        self._time_label = QLabel("0:00 / 0:00")

        # --- State ---
        self._dragging = False
        self._duration: float = 0.0

        # --- Layout ---
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addWidget(self._reset_btn)
        btn_row.addWidget(self._back_btn)
        btn_row.addWidget(self._play_pause_btn)
        btn_row.addWidget(self._forward_btn)
        btn_row.addStretch()

        seek_row = QHBoxLayout()
        seek_row.setContentsMargins(0, 0, 0, 0)
        seek_row.addWidget(self._slider, 1)
        seek_row.addWidget(self._time_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(btn_row)
        layout.addLayout(seek_row)

        # --- Connections ---
        self._play_pause_btn.clicked.connect(self.play_pause_clicked)
        self._reset_btn.clicked.connect(self.reset_requested)
        self._back_btn.clicked.connect(lambda: self.skip_requested.emit(-2.0))
        self._forward_btn.clicked.connect(lambda: self.skip_requested.emit(2.0))

        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)

    # ------------------------------------------------------------------
    # Public slots
    # ------------------------------------------------------------------

    def set_position(self, seconds: float) -> None:
        """Update slider and time label from player position."""
        if not self._dragging:
            self._slider.setValue(int(seconds * 1000))
        self._time_label.setText(f"{_format_time(seconds)} / {_format_time(self._duration)}")

    def set_duration(self, seconds: float) -> None:
        """Set slider range and total time display."""
        self._duration = seconds
        self._slider.setRange(0, int(seconds * 1000))
        self._time_label.setText(f"0:00 / {_format_time(seconds)}")

    def set_playing(self, is_playing: bool) -> None:
        """Toggle button text between play and pause."""
        self._play_pause_btn.setText("⏸" if is_playing else "▶")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_slider_pressed(self) -> None:
        self._dragging = True

    def _on_slider_released(self) -> None:
        self._dragging = False
        self.seek_requested.emit(self._slider.value() / 1000.0)
