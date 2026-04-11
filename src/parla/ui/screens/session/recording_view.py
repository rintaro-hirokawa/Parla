"""View for recording screen (SCREEN-E3).

Carousel-style sentence display with progress dots, hints, timer bar,
and waveform recording card matching the design mockup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from parla.ui import theme
from parla.ui.widgets.progress_dots_widget import ProgressDotsWidget
from parla.ui.widgets.record_button_widget import RecordButtonWidget
from parla.ui.widgets.time_bar_widget import TimeBarWidget
from parla.ui.widgets.waveform_widget import WaveformWidget

if TYPE_CHECKING:
    from parla.ui.audio.recorder import AudioRecorder
    from parla.ui.screens.session.recording_view_model import RecordingViewModel


class RecordingView(QWidget):
    """Carousel-style sequential sentence recording with hints."""

    def __init__(
        self,
        view_model: RecordingViewModel,
        recorder: AudioRecorder,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._recorder = recorder

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Time Bar ---
        self._time_bar = TimeBarWidget()
        root.addWidget(self._time_bar)

        # --- Progress Dots ---
        dots_container = QWidget()
        dots_layout = QHBoxLayout(dots_container)
        dots_layout.setContentsMargins(28, 20, 28, 8)
        dots_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_dots = ProgressDotsWidget()
        self._progress_dots.set_count(self._vm.sentence_count)
        dots_layout.addWidget(self._progress_dots)
        root.addWidget(dots_container)

        # --- Sentence Carousel ---
        carousel = QWidget()
        carousel_layout = QVBoxLayout(carousel)
        carousel_layout.setContentsMargins(48, 12, 48, 12)
        carousel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        carousel_layout.setSpacing(0)

        self._prev_label = self._make_carousel_label(14, theme.TEXT_TERTIARY)
        carousel_layout.addWidget(self._prev_label)
        self._current_label = self._make_carousel_label(28, theme.TEXT_PRIMARY, bold=True)
        self._current_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_PRIMARY)}; padding: 20px 0px;"
        )
        carousel_layout.addWidget(self._current_label)
        self._next_label = self._make_carousel_label(14, theme.TEXT_DISABLED)
        carousel_layout.addWidget(self._next_label)
        root.addWidget(carousel, stretch=1)

        # --- Hint Area ---
        hint_container = QWidget()
        hint_layout = QVBoxLayout(hint_container)
        hint_layout.setContentsMargins(48, 0, 48, 8)
        hint_layout.setSpacing(12)

        # Hint trigger row
        self._hint_trigger = QWidget()
        trigger_layout = QHBoxLayout(self._hint_trigger)
        trigger_layout.setContentsMargins(0, 0, 0, 0)
        trigger_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trigger_layout.setSpacing(8)

        self._hint_button = QPushButton("Hint")
        self._hint_button.setStyleSheet(
            f"border: 1px solid {theme.rgb(theme.HINT_BORDER)}; "
            f"border-radius: 20px; padding: 6px 18px; font-size: 12px; "
            f"font-weight: 500; color: {theme.rgb(theme.TEXT_SECONDARY)}; "
            f"background: transparent;"
        )
        self._hint_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hint_button.clicked.connect(self._vm.reveal_hint)
        trigger_layout.addWidget(self._hint_button)

        self._hint_dot0 = self._make_hint_dot()
        self._hint_dot1 = self._make_hint_dot()
        trigger_layout.addWidget(self._hint_dot0)
        trigger_layout.addWidget(self._hint_dot1)
        hint_layout.addWidget(self._hint_trigger, alignment=Qt.AlignmentFlag.AlignCenter)

        # Hint cards stack
        self._hint_card1 = QLabel()
        self._hint_card1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_card1.setWordWrap(True)
        self._hint_card1.setMaximumWidth(600)
        self._hint_card1.setVisible(False)
        hint_layout.addWidget(self._hint_card1, alignment=Qt.AlignmentFlag.AlignCenter)

        self._hint_card2 = QLabel()
        self._hint_card2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_card2.setWordWrap(True)
        self._hint_card2.setMaximumWidth(600)
        self._hint_card2.setVisible(False)
        hint_layout.addWidget(self._hint_card2, alignment=Qt.AlignmentFlag.AlignCenter)

        root.addWidget(hint_container)

        # --- Recording Card ---
        rec_section = QWidget()
        rec_section_layout = QVBoxLayout(rec_section)
        rec_section_layout.setContentsMargins(28, 0, 28, 28)
        rec_section_layout.setSpacing(0)

        self._recording_card = QFrame()
        self._recording_card.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        card_layout = QHBoxLayout(self._recording_card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(20)

        wave_container = QFrame()
        wave_container.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.WAVE_BG)}; "
            f"border-radius: 10px; border: 1px solid {theme.rgb(theme.BORDER_LIGHT)}; }}"
        )
        wave_layout = QVBoxLayout(wave_container)
        wave_layout.setContentsMargins(0, 0, 0, 0)
        self._waveform = WaveformWidget()
        wave_layout.addWidget(self._waveform)
        card_layout.addWidget(wave_container, stretch=1)

        self._record_button = RecordButtonWidget()
        self._record_button.clicked.connect(self._on_record_click)
        card_layout.addWidget(self._record_button)

        rec_section_layout.addWidget(self._recording_card)

        self._status_label = QLabel("録音ボタンを押して発話してください")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; padding-top: 10px;"
        )
        rec_section_layout.addWidget(self._status_label)

        root.addWidget(rec_section)

        # --- Connections ---
        self._vm.current_sentence_changed.connect(self._on_sentence_changed)
        self._vm.hint_revealed.connect(self._on_hint)
        self._vm.timer_updated.connect(self._on_timer_updated)

        # Animation timer for waveform + record button pulse
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start()

        # Render initial state
        self._render_carousel()
        self._render_hints()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_carousel_label(
        pixel_size: int, color: object, *, bold: bool = False
    ) -> QLabel:
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(900)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        font = QFont()
        font.setFamilies(["Noto Sans JP", "Yu Gothic UI", "Meiryo", "Segoe UI"])
        font.setPixelSize(pixel_size)
        if bold:
            font.setWeight(QFont.Weight.Bold)
        lbl.setFont(font)
        lbl.setStyleSheet(
            f"color: {theme.rgb(color)}; padding: 6px 0px;"  # type: ignore[arg-type]
        )
        return lbl

    @staticmethod
    def _make_hint_dot() -> QLabel:
        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(
            f"background: {theme.rgb(theme.HINT_BORDER)}; border-radius: 3px;"
        )
        return dot

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def _render_carousel(self) -> None:
        self._progress_dots.set_current(self._vm.current_index)
        self._prev_label.setText(self._vm.prev_ja)
        self._prev_label.setVisible(bool(self._vm.prev_ja))
        self._current_label.setText(self._vm.current_ja)
        self._next_label.setText(self._vm.next_ja)
        self._next_label.setVisible(bool(self._vm.next_ja))

    def _render_hints(self) -> None:
        level = self._vm.hint_level
        filled = f"background: {theme.rgb(theme.ACCENT)}; border-radius: 3px;"
        unfilled = f"background: {theme.rgb(theme.HINT_BORDER)}; border-radius: 3px;"
        self._hint_dot0.setStyleSheet(filled if level >= 1 else unfilled)
        self._hint_dot1.setStyleSheet(filled if level >= 2 else unfilled)
        self._hint_trigger.setVisible(level < 2)
        self._hint_card1.setVisible(level >= 1)
        self._hint_card2.setVisible(level >= 2)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_sentence_changed(self, _index: int) -> None:
        self._render_carousel()
        self._render_hints()
        self._status_label.setText("録音ボタンを押して発話してください")
        self._status_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; padding-top: 10px;"
        )

    def _on_hint(self, level: int, text: str) -> None:
        if level == 1:
            self._hint_card1.setText(text)
            self._hint_card1.setStyleSheet(
                f"background: {theme.rgb(theme.HINT_BG1)}; "
                f"color: {theme.rgb(theme.ACCENT)}; "
                f"border-radius: 8px; padding: 8px 20px; "
                f"font-size: 15px; font-weight: 500;"
            )
        elif level == 2:
            self._hint_card2.setText(text)
            self._hint_card2.setStyleSheet(
                f"background: {theme.rgb(theme.HINT_BG2)}; "
                f"color: {theme.rgb(theme.HINT_TEXT2)}; "
                f"border: 1px solid {theme.rgb(theme.BORDER)}; "
                f"border-radius: 8px; padding: 8px 20px; font-size: 13px;"
            )
        self._render_hints()

    def _on_timer_updated(self, remaining: int, total: int, state: str) -> None:
        ratio = remaining / total if total > 0 else 1.0
        self._time_bar.set_state(ratio, state)

    def _on_record_click(self) -> None:
        if self._vm.is_recording:
            # Stop recording
            audio = self._recorder.stop()
            self._record_button.set_recording(False)
            self._recording_card.setStyleSheet(
                f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
                f"border: 1px solid {theme.rgb(theme.BORDER)}; "
                f"border-radius: 14px; }}"
            )
            self._status_label.setStyleSheet(
                f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; padding-top: 10px;"
            )
            if audio is not None:
                self._vm.stop_recording(audio)
        else:
            # Start recording
            self._recorder.start()
            self._vm.start_recording()
            self._record_button.set_recording(True)
            self._recording_card.setStyleSheet(
                f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
                f"border: 1px solid {theme.rgb(theme.ACCENT_BORDER)}; "
                f"border-radius: 14px; }}"
            )
            self._status_label.setText("録音中...")
            self._status_label.setStyleSheet(
                f"color: {theme.rgb(theme.ERROR)}; font-size: 12px; padding-top: 10px;"
            )

    def _on_anim_tick(self) -> None:
        dt = 0.033
        self._time_bar.advance_pulse(dt)
        self._record_button.advance_pulse(dt)
        self._waveform.update()
