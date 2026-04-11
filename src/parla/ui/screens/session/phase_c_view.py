"""View for Phase C practice workspace (SCREEN-E6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from parla.ui.widgets.error_banner import ErrorBanner
from parla.ui.widgets.playback_controls import PlaybackControlsWidget
from parla.ui.widgets.recording_controls import RecordingControlsWidget

if TYPE_CHECKING:
    from parla.services.query_models import LiveDeliverySummary, OverlappingSummary
    from parla.ui.audio.recorder import AudioRecorder
    from parla.ui.screens.session.phase_c_view_model import PhaseCViewModel


class PhaseCView(QWidget):
    """Phase C — listening, overlapping, and live delivery modes."""

    def __init__(
        self,
        view_model: PhaseCViewModel,
        recorder: AudioRecorder,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._prev_highlight_idx: int = -1

        # --- Widgets ---
        self._mode_combo = QComboBox()
        for mode in self._vm.available_modes:
            label = {"listening": "リスニング", "overlapping": "オーバーラッピング", "live_delivery": "本番発話"}
            self._mode_combo.addItem(label.get(mode, mode), mode)

        self._model_text_label = QLabel("")
        self._model_text_label.setTextFormat(Qt.TextFormat.RichText)
        self._model_text_label.setWordWrap(True)

        self._ja_text_label = QLabel("")
        self._ja_text_label.setWordWrap(True)

        self._status_label = QLabel("")
        self._recording = RecordingControlsWidget(recorder, parent=self)
        self._playback_controls = PlaybackControlsWidget(parent=self)

        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setMinimum(75)
        self._speed_slider.setMaximum(125)
        self._speed_slider.setValue(100)
        self._speed_label = QLabel("1.0x")

        self._complete_button = QPushButton("完了")
        self._complete_button.setEnabled(False)
        self._error_banner = ErrorBanner(retryable=True)

        # --- Layout ---
        speed_row = QHBoxLayout()
        speed_row.setContentsMargins(0, 0, 0, 0)
        speed_row.addWidget(QLabel("速度"))
        speed_row.addWidget(self._speed_slider, 1)
        speed_row.addWidget(self._speed_label)

        layout = QVBoxLayout(self)
        layout.addWidget(self._mode_combo)
        layout.addWidget(self._model_text_label)
        layout.addWidget(self._ja_text_label)
        layout.addWidget(self._playback_controls)
        layout.addLayout(speed_row)
        layout.addWidget(self._recording)
        layout.addWidget(self._status_label)
        layout.addWidget(self._error_banner)
        layout.addWidget(self._complete_button)

        # --- Connections ---
        self._mode_combo.currentIndexChanged.connect(self._on_mode_selected)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        self._complete_button.clicked.connect(self._vm.complete)

        # Playback controls
        self._playback_controls.play_pause_clicked.connect(self._vm.toggle_play_pause)
        self._playback_controls.seek_requested.connect(self._vm.seek)
        self._playback_controls.skip_requested.connect(self._vm.skip)
        self._playback_controls.reset_requested.connect(self._vm.reset_to_start)

        # Recording controls
        recorder.recording_started.connect(self._vm.on_recording_started)
        self._recording.recording_finished.connect(self._vm.on_recording_finished)

        # ViewModel signals
        self._vm.mode_changed.connect(self._on_mode_changed)
        self._vm.model_audio_ready.connect(self._on_audio_ready)
        self._vm.model_audio_failed.connect(self._on_audio_failed)
        self._error_banner.retry_clicked.connect(self._vm.retry_model_audio)
        self._vm.overlapping_result.connect(self._on_overlapping)
        self._vm.overlapping_words_ready.connect(self._on_overlapping_words)
        self._vm.live_delivery_result.connect(self._on_delivery)
        self._vm.live_delivery_detail_ready.connect(self._on_delivery_detail)
        self._vm.complete_enabled_changed.connect(self._complete_button.setEnabled)

        # Playback transport signals
        self._vm.playback_position_changed.connect(self._on_position_changed)
        self._vm.playback_duration_changed.connect(self._playback_controls.set_duration)
        self._vm.playback_state_changed.connect(
            lambda state: self._playback_controls.set_playing(state == "playing")
        )

        # Model audio may already be ready (generated during Phase B)
        if self._vm.is_model_audio_loaded:
            self._on_audio_ready()

        # Initialize ja text and mode visibility
        self._init_ja_text()
        self._update_mode_visibility(self._vm.current_mode)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._vm.activate()

    def hideEvent(self, event: QHideEvent) -> None:
        self._vm.deactivate()
        super().hideEvent(event)

    def _on_mode_selected(self, index: int) -> None:
        mode = self._mode_combo.itemData(index)
        if mode:
            self._vm.switch_mode(mode)

    def _on_mode_changed(self, mode: str) -> None:
        self._status_label.setText("")
        self._update_mode_visibility(mode)

    def _update_mode_visibility(self, mode: str) -> None:
        is_listening = mode == "listening"
        is_overlapping = mode == "overlapping"
        is_live = mode == "live_delivery"

        self._model_text_label.setVisible(is_listening or is_overlapping or is_live)
        self._ja_text_label.setVisible(is_live)
        self._recording.setVisible(is_live)
        self._playback_controls.setVisible(is_listening or is_overlapping)
        self._speed_slider.parentWidget()  # speed_row is in layout, control individual widgets
        self._speed_slider.setVisible(is_listening or is_overlapping)
        self._speed_label.setVisible(is_listening or is_overlapping)

    def _on_speed_changed(self, value: int) -> None:
        rate = value / 100.0
        self._speed_label.setText(f"{rate:.2f}x")
        self._vm.set_speed(rate)

    def _on_audio_ready(self) -> None:
        self._status_label.setText("モデル音声準備完了")
        self._error_banner.clear()
        self._init_model_text()

    def _on_audio_failed(self, message: str) -> None:
        self._error_banner.show_error(f"TTS エラー: {message}")

    def _init_model_text(self) -> None:
        """Set up the model text display from sentence_texts."""
        texts = self._vm.sentence_texts
        if texts:
            self._model_text_label.setText("<br>".join(texts))
        self._prev_highlight_idx = -1

    def _init_ja_text(self) -> None:
        """Set up the Japanese text display for live delivery."""
        ja_texts = self._vm.sentence_ja_texts
        if ja_texts:
            self._ja_text_label.setText("<br>".join(ja_texts))

    def _on_position_changed(self, seconds: float) -> None:
        self._playback_controls.set_position(seconds)
        self._update_sentence_highlight(seconds)

    def _update_sentence_highlight(self, position: float) -> None:
        texts = self._vm.sentence_texts
        if not texts:
            return
        idx = self._vm.current_sentence_index(position)
        if idx == self._prev_highlight_idx:
            return
        self._prev_highlight_idx = idx
        parts = []
        for i, text in enumerate(texts):
            if i == idx:
                parts.append(f'<span style="background-color: #FFE082; color: #000;">{text}</span>')
            else:
                parts.append(text)
        self._model_text_label.setText("<br>".join(parts))

    def _on_overlapping(self, score: float) -> None:
        self._status_label.setText(f"発音スコア: {score:.1f}")

    def _on_overlapping_words(self, summary: OverlappingSummary) -> None:
        """Render per-word pronunciation highlights in _model_text_label."""
        _STYLES = {
            "Mispronunciation": 'color: #D32F2F; font-weight: bold;',
            "Omission": 'color: #9E9E9E; text-decoration: line-through;',
        }
        _DEFAULT_STYLE = 'color: #2E7D32;'

        parts: list[str] = []
        for sentence in summary.sentence_words:
            word_spans: list[str] = []
            for wr in sentence:
                style = _STYLES.get(wr.error_type, _DEFAULT_STYLE)
                word_spans.append(f'<span style="{style}">{wr.word}</span>')
            parts.append(" ".join(word_spans))
        self._model_text_label.setText("<br>".join(parts))

    def _on_delivery(self, passed: bool, error_rate: float, threshold: float, wpm: float) -> None:
        result = "合格" if passed else "不合格"
        pct = error_rate * 100
        threshold_pct = threshold * 100
        self._status_label.setText(
            f"{result} — エラー率: {pct:.0f}% (基準: {threshold_pct:.0f}%未満) — {wpm:.1f} WPM"
        )

    def _on_delivery_detail(self, summary: LiveDeliverySummary) -> None:
        """Show per-word pronunciation highlights after live delivery evaluation."""
        _STYLES = {
            "Mispronunciation": 'color: #D32F2F; font-weight: bold;',
            "Omission": 'color: #9E9E9E; text-decoration: line-through;',
        }
        _DEFAULT_STYLE = 'color: #2E7D32;'

        parts: list[str] = []
        for sentence in summary.sentence_words:
            word_spans: list[str] = []
            for wr in sentence:
                style = _STYLES.get(wr.error_type, _DEFAULT_STYLE)
                word_spans.append(f'<span style="{style}">{wr.word}</span>')
            parts.append(" ".join(word_spans))
        self._model_text_label.setText("<br>".join(parts))
