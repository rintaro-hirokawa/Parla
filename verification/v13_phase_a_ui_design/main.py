"""Phase A Speaking Screen — PySide6 design reproduction of docs/design/phase_a_mockup.html."""

from __future__ import annotations

import math
import struct
import sys
from dataclasses import dataclass
from math import ceil

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ============================================================
# Data
# ============================================================

@dataclass
class Sentence:
    ja: str
    hint1: str
    hint2: str


SENTENCES = [
    Sentence(
        ja="豊田章男氏は、日本の有名な企業であるトヨタ自動車の会長です。",
        hint1="Akio ... chairman / corporation",
        hint2="主語 + be動詞 + 補語, 同格名詞句",
    ),
    Sentence(
        ja="現在69歳ですが、彼は今でも自社の車を自らテストしています。",
        hint1="Although ... still / by himself",
        hint2="although節[主語 + be動詞 + 補語 + 副詞], 主語 + 副詞 + 動詞(現在形) + 目的語 + 前置詞句",
    ),
    Sentence(
        ja="特別なテストコースで車を運転するために、彼はよくレーシングスーツとヘルメットを着用します。",
        hint1="He ... wears / helmet",
        hint2="主語 + 副詞 + 動詞(現在形) + 目的語 + to不定詞[動詞(原形) + 目的語 + 前置詞句]",
    ),
    Sentence(
        ja="そのコースは急な坂や急カーブがあるため、非常に厳しいです。",
        hint1="The ... extremely / steep / sharp",
        hint2="主語 + be動詞 + 副詞 + 補語 + because節[主語 + 動詞(現在形) + 目的語]",
    ),
    Sentence(
        ja="彼の基本的な哲学は、車が完全に壊れるまでテストすることです。",
        hint1="His ... philosophy / completely",
        hint2="主語 + be動詞 + 補語(to不定詞)[動詞(原形) + 目的語 + 前置詞句[主語 + 副詞 + 動詞(現在形)]]",
    ),
]

# ============================================================
# Colors
# ============================================================

CLR_PRIMARY = "#4f6ef7"
CLR_PRIMARY_HOVER = "#3b5de7"
CLR_TEXT = "#1a1a2e"
CLR_TEXT_SEC = "#6b7280"
CLR_TEXT_TER = "#9ca3af"
CLR_BG = "#f4f6fb"
CLR_CARD = "#ffffff"
CLR_BORDER = "#e8eaf0"
CLR_BORDER2 = "#e0e4ed"
CLR_RED = "#ef4444"
CLR_ORANGE = "#f59e0b"
CLR_TRACK = "#eef0f5"
CLR_DOT_UPCOMING = "#e8eaf0"
CLR_DOT_DONE = CLR_PRIMARY
CLR_PREV_TEXT = "#9ca3af"
CLR_NEXT_TEXT = "#a8b0bc"
CLR_HINT_BG1 = "#f0f2ff"
CLR_HINT_BG2 = "#f8f9fc"
CLR_HINT_TEXT2 = "#4b5563"
CLR_HINT_BORDER = "#d1d5e0"
CLR_WAVE_BG = "#f8f9fc"
CLR_WAVE_LINE = "#e0e4ed"
CLR_WAVE_ACTIVE = "#4f6ef7"
CLR_WAVE_IDLE = "#c7d0f7"

FONT_FAMILY = "Noto Sans JP, Yu Gothic UI, Meiryo, Segoe UI, sans-serif"

# ============================================================
# Global Stylesheet
# ============================================================

STYLESHEET = f"""
QMainWindow {{
    background: {CLR_BG};
}}

#centralWidget {{
    background: {CLR_BG};
}}

#topBar {{
    background: {CLR_CARD};
    border-bottom: 1px solid {CLR_BORDER};
}}

#backButton {{
    color: {CLR_TEXT_SEC};
    font-size: 13px;
    border: none;
    background: transparent;
    padding: 4px 8px;
}}

#backButton:hover {{
    color: {CLR_PRIMARY};
}}

#progressText {{
    color: {CLR_TEXT_TER};
    font-size: 12px;
    font-weight: 500;
}}

#hintButton {{
    border: 1px solid {CLR_HINT_BORDER};
    border-radius: 20px;
    padding: 6px 18px;
    font-size: 12px;
    font-weight: 500;
    color: {CLR_TEXT_SEC};
    background: transparent;
    letter-spacing: 0.03em;
}}

#hintButton:hover {{
    border-color: {CLR_PRIMARY};
    color: {CLR_PRIMARY};
    background: {CLR_HINT_BG1};
}}

#recordingCard {{
    background: {CLR_CARD};
    border: 1px solid {CLR_BORDER};
    border-radius: 14px;
}}

#statusLabel {{
    color: {CLR_TEXT_TER};
    font-size: 12px;
}}
"""

# ============================================================
# TimeBarWidget
# ============================================================

class TimeBarWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(5)
        self._ratio = 1.0
        self._state = "normal"  # normal | caution | danger
        self._pulse_phase = 0.0

    def set_state(self, ratio: float, state: str) -> None:
        self._ratio = ratio
        self._state = state
        self.update()

    def advance_pulse(self, dt: float) -> None:
        self._pulse_phase += dt
        if self._state == "danger":
            self.update()

    def paintEvent(self, _event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Track
        p.fillRect(0, 0, w, h, QColor(CLR_TRACK))

        # Fill
        if self._state == "danger":
            color = QColor(CLR_RED)
            bar_h = 5
            opacity = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self._pulse_phase * 10))
            p.setOpacity(opacity)
        elif self._state == "caution":
            color = QColor(CLR_ORANGE)
            bar_h = 4
        else:
            color = QColor(CLR_PRIMARY)
            bar_h = 3

        fill_w = int(w * self._ratio)
        y = (h - bar_h) // 2
        p.fillRect(0, y, fill_w, bar_h, color)
        p.setOpacity(1.0)
        p.end()


# ============================================================
# WaveformWidget (real microphone input)
# ============================================================

class WaveformWidget(QWidget):
    BUF_LEN = 128
    BAR_W = 3
    GAP = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setMaximumHeight(64)
        self._buffer = [0.0] * self.BUF_LEN
        self._is_recording = False

        # Audio input setup
        self._audio_source: QAudioSource | None = None
        self._io_device = None
        self._setup_audio()

    def _setup_audio(self) -> None:
        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            return

        fmt = QAudioFormat()
        fmt.setSampleRate(16000)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        self._audio_source = QAudioSource(device, fmt)
        self._audio_source.setBufferSize(4096)

    def start_listening(self) -> None:
        self._is_recording = True
        if self._audio_source is not None and self._io_device is None:
            self._io_device = self._audio_source.start()

    def stop_listening(self) -> None:
        self._is_recording = False
        if self._audio_source is not None:
            self._audio_source.stop()
            self._io_device = None

    def update_buffer(self) -> None:
        if self._is_recording and self._io_device is not None:
            data = self._io_device.readAll()
            if data and len(data) >= 2:
                raw = bytes(data)
                n_samples = len(raw) // 2
                samples = struct.unpack(f"<{n_samples}h", raw[: n_samples * 2])
                # Compute RMS of chunks to feed into buffer
                chunk_size = max(1, n_samples // 4)
                for i in range(0, n_samples, chunk_size):
                    chunk = samples[i : i + chunk_size]
                    rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
                    # Scale up for visibility
                    val = min(1.0, rms * 5.0)
                    self._buffer.pop(0)
                    self._buffer.append(val)
        else:
            # Decay
            for i in range(len(self._buffer)):
                self._buffer[i] *= 0.92

    def paintEvent(self, _event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(CLR_WAVE_BG))

        # Center line
        mid_y = h / 2
        p.setPen(QPen(QColor(CLR_WAVE_LINE), 1))
        p.drawLine(0, int(mid_y), w, int(mid_y))

        # Bars
        step = self.BAR_W + self.GAP
        bars = w // step
        start_x = (w - bars * step) / 2
        color = QColor(CLR_WAVE_ACTIVE if self._is_recording else CLR_WAVE_IDLE)

        for i in range(bars):
            idx = int(i * len(self._buffer) / bars)
            val = self._buffer[idx] if idx < len(self._buffer) else 0.0
            bar_h = max(2, val * (h - 8))
            x = start_x + i * step

            path = QPainterPath()
            path.addRoundedRect(QRectF(x, mid_y - bar_h / 2, self.BAR_W, bar_h), 1.5, 1.5)
            p.fillPath(path, color)

        p.end()


# ============================================================
# RecordButtonWidget
# ============================================================

class RecordButtonWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(56, 56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._recording = False
        self._hovered = False
        self._pulse_phase = 0.0
        self._click_callback: object = None

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        self._pulse_phase = 0.0
        self.update()

    def set_click_callback(self, cb: object) -> None:
        self._click_callback = cb

    def advance_pulse(self, dt: float) -> None:
        if self._recording:
            self._pulse_phase += dt
            self.update()

    def enterEvent(self, _event: object) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, _event: object) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, _event: object) -> None:
        if self._click_callback:
            self._click_callback()

    def paintEvent(self, _event: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2

        # Pulse glow ring (recording)
        if self._recording:
            glow_r = 28 + 4 * math.sin(self._pulse_phase * 4.2)
            glow_color = QColor(239, 68, 68, 38)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow_color)
            p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # Outer circle
        border_color = QColor(CLR_RED) if (self._recording or self._hovered) else QColor(CLR_BORDER2)
        p.setPen(QPen(border_color, 3))
        p.setBrush(QColor(CLR_CARD))
        r = 25  # radius of outer circle (56/2 - 3 border)
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Hover ring
        if self._hovered and not self._recording:
            hover_ring = QColor(239, 68, 68, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hover_ring)
            p.drawEllipse(QRectF(cx - 30, cy - 30, 60, 60))

        # Inner shape
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(CLR_RED))
        if self._recording:
            # Rounded rectangle
            rect = QRectF(cx - 9, cy - 9, 18, 18)
            path = QPainterPath()
            path.addRoundedRect(rect, 4, 4)
            p.fillPath(path, QColor(CLR_RED))
        else:
            # Circle
            p.drawEllipse(QRectF(cx - 11, cy - 11, 22, 22))

        p.end()


# ============================================================
# Main Window
# ============================================================

class PhaseAWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Parla - Phase A Speaking Screen")
        self.setMinimumSize(800, 600)
        self.resize(1024, 768)

        # State
        self._current_index = 0
        self._hint_level = 0
        self._is_recording = False
        self._timer_remaining = 0
        self._timer_limit = 0

        self._build_ui()
        self._apply_font()
        self._reset_timer()
        self._render_all()

        # Timers
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start()

        self._wave_feed_timer = QTimer(self)
        self._wave_feed_timer.setInterval(50)
        self._wave_feed_timer.timeout.connect(self._waveform.update_buffer)
        self._wave_feed_timer.start()

    def _apply_font(self) -> None:
        font = QFont()
        font.setFamilies(["Noto Sans JP", "Yu Gothic UI", "Meiryo", "Segoe UI"])
        QApplication.instance().setFont(font)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Top Bar ---
        self._build_top_bar(root_layout)

        # --- Time Bar ---
        self._time_bar = TimeBarWidget()
        root_layout.addWidget(self._time_bar)

        # --- Sentence Progress Dots ---
        self._build_progress_dots(root_layout)

        # --- Sentence Carousel ---
        self._build_carousel(root_layout)

        # --- Hint Area ---
        self._build_hint_area(root_layout)

        # --- Recording Section ---
        self._build_recording_section(root_layout)

    # ---- Top Bar ----

    def _build_top_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QWidget()
        bar.setObjectName("topBar")
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 0, 28, 0)

        back_btn = QPushButton("\u2190 Back")
        back_btn.setObjectName("backButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(back_btn)

        layout.addStretch()

        progress = QLabel("Speaking")
        progress.setObjectName("progressText")
        progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(progress)

        layout.addStretch()

        self._timer_label = QLabel("00:00")
        self._timer_label.setObjectName("timerLabel")
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._timer_label.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
        layout.addWidget(self._timer_label)

        parent_layout.addWidget(bar)

    # ---- Progress Dots ----

    def _build_progress_dots(self, parent_layout: QVBoxLayout) -> None:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(28, 20, 28, 8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        self._dots: list[QLabel] = []
        for _ in SENTENCES:
            dot = QLabel()
            dot.setFixedSize(10, 10)
            layout.addWidget(dot)
            self._dots.append(dot)

        parent_layout.addWidget(container)

    def _render_dots(self) -> None:
        for i, dot in enumerate(self._dots):
            if i < self._current_index:
                dot.setStyleSheet(
                    f"background: {CLR_DOT_DONE}; border-radius: 5px;"
                )
            elif i == self._current_index:
                dot.setFixedSize(12, 12)
                dot.setStyleSheet(
                    f"background: {CLR_DOT_DONE}; border-radius: 6px; "
                    f"border: 2px solid rgba(79, 110, 247, 45%);"
                )
            else:
                dot.setFixedSize(10, 10)
                dot.setStyleSheet(
                    f"background: {CLR_DOT_UPCOMING}; border-radius: 5px;"
                )

    # ---- Carousel ----

    def _build_carousel(self, parent_layout: QVBoxLayout) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(48, 12, 48, 12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(0)

        self._prev_label = QLabel()
        self._prev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prev_label.setWordWrap(True)
        self._prev_label.setMaximumWidth(900)
        self._prev_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._prev_label)

        self._current_label = QLabel()
        self._current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._current_label.setWordWrap(True)
        self._current_label.setMaximumWidth(900)
        self._current_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._current_label)

        self._next_label = QLabel()
        self._next_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._next_label.setWordWrap(True)
        self._next_label.setMaximumWidth(900)
        self._next_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._next_label)

        parent_layout.addWidget(container, stretch=1)

    @staticmethod
    def _make_font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
        font = QFont()
        font.setFamilies(["Noto Sans JP", "Yu Gothic UI", "Meiryo", "Segoe UI"])
        font.setPixelSize(pixel_size)
        font.setWeight(weight)
        return font

    def _render_carousel(self) -> None:
        idx = self._current_index
        if idx >= len(SENTENCES):
            self._prev_label.setText("")
            self._prev_label.setVisible(False)
            self._current_label.setText("All done!")
            self._current_label.setFont(self._make_font(28, QFont.Weight.Bold))
            self._current_label.setStyleSheet(f"color: {CLR_TEXT}; padding: 20px 0px;")
            self._next_label.setText("")
            self._next_label.setVisible(False)
            return

        # Prev
        if idx > 0:
            self._prev_label.setText(SENTENCES[idx - 1].ja)
            self._prev_label.setFont(self._make_font(14))
            self._prev_label.setStyleSheet(f"color: {CLR_PREV_TEXT}; padding: 6px 0px;")
            self._prev_label.setVisible(True)
        else:
            self._prev_label.setText("")
            self._prev_label.setVisible(False)

        # Current
        self._current_label.setText(SENTENCES[idx].ja)
        self._current_label.setFont(self._make_font(28, QFont.Weight.Bold))
        self._current_label.setStyleSheet(f"color: {CLR_TEXT}; padding: 20px 0px;")

        # Next
        if idx < len(SENTENCES) - 1:
            self._next_label.setText(SENTENCES[idx + 1].ja)
            self._next_label.setFont(self._make_font(14))
            self._next_label.setStyleSheet(f"color: {CLR_NEXT_TEXT}; padding: 6px 0px;")
            self._next_label.setVisible(True)
        else:
            self._next_label.setText("")
            self._next_label.setVisible(False)

    # ---- Hint Area ----

    def _build_hint_area(self, parent_layout: QVBoxLayout) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(48, 0, 48, 8)
        layout.setSpacing(12)
        # Trigger row
        self._hint_trigger = QWidget()
        trigger_layout = QHBoxLayout(self._hint_trigger)
        trigger_layout.setContentsMargins(0, 0, 0, 0)
        trigger_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trigger_layout.setSpacing(8)

        self._hint_button = QPushButton("Hint")
        self._hint_button.setObjectName("hintButton")
        self._hint_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hint_button.clicked.connect(self._on_hint_click)
        trigger_layout.addWidget(self._hint_button)

        self._hint_dot0 = QLabel()
        self._hint_dot0.setFixedSize(6, 6)
        trigger_layout.addWidget(self._hint_dot0)

        self._hint_dot1 = QLabel()
        self._hint_dot1.setFixedSize(6, 6)
        trigger_layout.addWidget(self._hint_dot1)

        layout.addWidget(self._hint_trigger, alignment=Qt.AlignmentFlag.AlignCenter)

        # Hint stack — each card centered via HBoxLayout + stretch
        self._hint_stack = QWidget()
        stack_layout = QVBoxLayout(self._hint_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(6)

        # Card 1
        row1 = QHBoxLayout()
        row1.addStretch()
        self._hint_frame1 = QFrame()
        self._hint_frame1.setMinimumWidth(300)
        self._hint_frame1.setMaximumWidth(600)
        frame1_layout = QVBoxLayout(self._hint_frame1)
        frame1_layout.setContentsMargins(20, 8, 20, 8)
        self._hint_label1 = QLabel()
        self._hint_label1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label1.setWordWrap(True)
        frame1_layout.addWidget(self._hint_label1)
        self._hint_frame1.setVisible(False)
        row1.addWidget(self._hint_frame1)
        row1.addStretch()
        stack_layout.addLayout(row1)

        # Card 2
        row2 = QHBoxLayout()
        row2.addStretch()
        self._hint_frame2 = QFrame()
        self._hint_frame2.setMinimumWidth(300)
        self._hint_frame2.setMaximumWidth(600)
        frame2_layout = QVBoxLayout(self._hint_frame2)
        frame2_layout.setContentsMargins(20, 8, 20, 8)
        self._hint_label2 = QLabel()
        self._hint_label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label2.setWordWrap(True)
        frame2_layout.addWidget(self._hint_label2)
        self._hint_frame2.setVisible(False)
        row2.addWidget(self._hint_frame2)
        row2.addStretch()
        stack_layout.addLayout(row2)

        layout.addWidget(self._hint_stack)
        parent_layout.addWidget(container)

    def _render_hints(self) -> None:
        if self._current_index >= len(SENTENCES):
            self._hint_trigger.setVisible(False)
            self._hint_frame1.setVisible(False)
            self._hint_frame2.setVisible(False)
            return

        s = SENTENCES[self._current_index]

        # Dots
        dot_unfilled = f"background: {CLR_HINT_BORDER}; border-radius: 3px;"
        dot_filled = f"background: {CLR_PRIMARY}; border-radius: 3px;"
        self._hint_dot0.setStyleSheet(dot_filled if self._hint_level >= 1 else dot_unfilled)
        self._hint_dot1.setStyleSheet(dot_filled if self._hint_level >= 2 else dot_unfilled)

        # Trigger visibility
        self._hint_trigger.setVisible(self._hint_level < 2)

        # Cards
        if self._hint_level >= 1:
            self._hint_label1.setText(s.hint1)
            self._hint_frame1.setStyleSheet(
                f"QFrame {{ background: {CLR_HINT_BG1}; border-radius: 8px; }}"
            )
            self._hint_label1.setStyleSheet(
                f"color: {CLR_PRIMARY}; font-size: 15px; font-weight: 500; background: transparent;"
            )
            self._hint_frame1.setVisible(True)
        else:
            self._hint_frame1.setVisible(False)

        if self._hint_level >= 2:
            self._hint_label2.setText(s.hint2)
            self._hint_frame2.setStyleSheet(
                f"QFrame {{ background: {CLR_HINT_BG2}; border-radius: 8px; "
                f"border: 1px solid {CLR_BORDER}; }}"
            )
            self._hint_label2.setStyleSheet(
                f"color: {CLR_HINT_TEXT2}; font-size: 13px; background: transparent;"
            )
            self._hint_frame2.setVisible(True)
        else:
            self._hint_frame2.setVisible(False)

    def _on_hint_click(self) -> None:
        if self._current_index >= len(SENTENCES):
            return
        if self._hint_level >= 2:
            return
        self._hint_level += 1
        self._render_hints()

    # ---- Recording Section ----

    def _build_recording_section(self, parent_layout: QVBoxLayout) -> None:
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(28, 0, 28, 28)
        section_layout.setSpacing(0)

        # Recording card
        self._recording_card = QFrame()
        self._recording_card.setObjectName("recordingCard")
        card_layout = QHBoxLayout(self._recording_card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(20)

        # Waveform
        wave_container = QFrame()
        wave_container.setStyleSheet(
            f"background: {CLR_WAVE_BG}; border-radius: 10px; border: 1px solid {CLR_TRACK};"
        )
        wave_layout = QVBoxLayout(wave_container)
        wave_layout.setContentsMargins(0, 0, 0, 0)

        self._waveform = WaveformWidget()
        wave_layout.addWidget(self._waveform)

        card_layout.addWidget(wave_container, stretch=1)

        # Record button
        self._record_button = RecordButtonWidget()
        self._record_button.set_click_callback(self._toggle_recording)
        card_layout.addWidget(self._record_button)

        section_layout.addWidget(self._recording_card)

        # Status label
        self._status_label = QLabel("録音ボタンを押して発話してください")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"color: {CLR_TEXT_TER}; font-size: 12px; padding-top: 10px;"
        )
        section_layout.addWidget(self._status_label)

        parent_layout.addWidget(section)

    # ---- State Logic ----

    @staticmethod
    def _calc_time_limit(ja: str) -> int:
        return max(15, ceil(len(ja) / 10) * 3 + 10)

    def _reset_timer(self) -> None:
        self._countdown_timer.stop() if hasattr(self, "_countdown_timer") else None
        if self._current_index < len(SENTENCES):
            self._timer_limit = self._calc_time_limit(SENTENCES[self._current_index].ja)
            self._timer_remaining = self._timer_limit
        else:
            self._timer_limit = 0
            self._timer_remaining = 0
        self._render_timer()

    def _start_timer(self) -> None:
        if not self._countdown_timer.isActive():
            self._countdown_timer.start()

    def _on_countdown_tick(self) -> None:
        self._timer_remaining = max(0, self._timer_remaining - 1)
        self._render_timer()
        if self._timer_remaining <= 0 and self._is_recording:
            self._toggle_recording()

    def _render_timer(self) -> None:
        m = self._timer_remaining // 60
        s = self._timer_remaining % 60
        self._timer_label.setText(f"{m:02d}:{s:02d}")

        ratio = self._timer_remaining / self._timer_limit if self._timer_limit > 0 else 1.0

        if ratio <= 0.2:
            self._timer_label.setStyleSheet(f"color: {CLR_RED}; font-size: 15px; font-weight: 600;")
            self._time_bar.set_state(ratio, "danger")
        elif ratio <= 0.4:
            self._timer_label.setStyleSheet(f"color: {CLR_ORANGE}; font-size: 15px; font-weight: 600;")
            self._time_bar.set_state(ratio, "caution")
        else:
            self._timer_label.setStyleSheet(f"color: {CLR_TEXT}; font-size: 15px; font-weight: 600;")
            self._time_bar.set_state(ratio, "normal")

    def _toggle_recording(self) -> None:
        if self._current_index >= len(SENTENCES):
            return

        self._is_recording = not self._is_recording

        if self._is_recording:
            self._record_button.set_recording(True)
            self._recording_card.setStyleSheet(
                f"background: {CLR_CARD}; border: 1px solid #c7d0f7; "
                f"border-radius: 14px;"
            )
            self._status_label.setText("録音中...")
            self._status_label.setStyleSheet(
                f"color: {CLR_RED}; font-size: 12px; padding-top: 10px;"
            )
            self._waveform.start_listening()
            self._start_timer()
        else:
            self._record_button.set_recording(False)
            self._recording_card.setStyleSheet(
                f"background: {CLR_CARD}; border: 1px solid {CLR_BORDER}; "
                f"border-radius: 14px;"
            )
            self._status_label.setStyleSheet(
                f"color: {CLR_TEXT_TER}; font-size: 12px; padding-top: 10px;"
            )
            self._waveform.stop_listening()
            self._countdown_timer.stop()

            # Advance after 400ms
            QTimer.singleShot(400, self._advance_sentence)

    def _advance_sentence(self) -> None:
        self._current_index += 1
        self._hint_level = 0

        if self._current_index >= len(SENTENCES):
            self._status_label.setText("全文完了!")
            self._status_label.setStyleSheet(
                f"color: {CLR_TEXT_TER}; font-size: 12px; padding-top: 10px;"
            )
        else:
            self._status_label.setText("録音ボタンを押して発話してください")
            self._status_label.setStyleSheet(
                f"color: {CLR_TEXT_TER}; font-size: 12px; padding-top: 10px;"
            )

        self._reset_timer()
        self._render_all()

    def _render_all(self) -> None:
        self._render_dots()
        self._render_carousel()
        self._render_hints()
        self._render_timer()

    # ---- Animation Tick ----

    def _on_anim_tick(self) -> None:
        dt = 0.033
        self._time_bar.advance_pulse(dt)
        self._record_button.advance_pulse(dt)
        self._waveform.update()


# ============================================================
# Entry Point
# ============================================================

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = PhaseAWindow()
    window.show()

    sys.exit(app.exec())
