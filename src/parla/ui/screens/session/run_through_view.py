"""View for run-through practice workspace (SCREEN-E6).

Segmented mode control, text card with IPA toggle, playback controls,
recording card, and results display matching the design mockup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from parla.ui import theme
from parla.ui.widgets.error_banner import ErrorBanner
from parla.ui.widgets.mode_segment_widget import ModeSegmentWidget
from parla.ui.widgets.playback_controls import PlaybackControlsWidget
from parla.ui.widgets.record_button_widget import RecordButtonWidget
from parla.ui.widgets.waveform_widget import WaveformWidget

if TYPE_CHECKING:
    from PySide6.QtGui import QHideEvent, QShowEvent

    from parla.services.query_models import LiveDeliverySummary, OverlappingSummary, PronunciationWordResult
    from parla.ui.audio.recorder import AudioRecorder
    from parla.ui.screens.session.run_through_view_model import RunThroughViewModel


class RunThroughView(QWidget):
    """Run-through practice — listening, overlapping, and live delivery modes."""

    def __init__(
        self,
        view_model: RunThroughViewModel,
        recorder: AudioRecorder,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._recorder = recorder
        self._prev_highlight_idx: int = -1

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Mode Segment ---
        mode_container = QWidget()
        mode_layout = QHBoxLayout(mode_container)
        mode_layout.setContentsMargins(28, 16, 28, 12)
        mode_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._mode_segment = ModeSegmentWidget([
            ("listening", "1  Listen"),
            ("overlapping", "2  Overlap"),
            ("live_delivery", "3  Speak"),
        ])
        mode_layout.addWidget(self._mode_segment)
        root.addWidget(mode_container)

        # --- Scrollable Content ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(32, 16, 32, 20)
        self._content_layout.setSpacing(16)

        # Text card
        self._text_card = QFrame()
        self._text_card.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        text_card_layout = QVBoxLayout(self._text_card)
        text_card_layout.setContentsMargins(24, 20, 24, 20)

        text_header = QHBoxLayout()
        self._text_title = QLabel("Model Text")
        self._text_title.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 12px; font-weight: 500;"
        )
        text_header.addWidget(self._text_title)
        text_header.addStretch()
        text_card_layout.addLayout(text_header)

        self._model_text_label = QLabel("")
        self._model_text_label.setTextFormat(Qt.TextFormat.RichText)
        self._model_text_label.setWordWrap(True)
        self._model_text_label.setStyleSheet(
            f"font-size: 16px; color: {theme.rgb(theme.TEXT_PRIMARY)}; line-height: 1.8;"
        )
        text_card_layout.addWidget(self._model_text_label)

        # Japanese text (for live delivery)
        self._ja_text_label = QLabel("")
        self._ja_text_label.setWordWrap(True)
        self._ja_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ja_text_label.setStyleSheet(
            f"font-size: 20px; font-weight: 600; color: {theme.rgb(theme.TEXT_PRIMARY)}; "
            f"padding: 28px; text-align: center;"
        )
        self._ja_text_label.setVisible(False)
        text_card_layout.addWidget(self._ja_text_label)

        self._content_layout.addWidget(self._text_card)

        # Playback card
        self._playback_card = QFrame()
        self._playback_card.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        pb_layout = QVBoxLayout(self._playback_card)
        pb_layout.setContentsMargins(24, 16, 24, 16)

        self._playback_controls = PlaybackControlsWidget(parent=self)
        pb_layout.addWidget(self._playback_controls)

        # Speed slider
        speed_section = QWidget()
        speed_layout = QHBoxLayout(speed_section)
        speed_layout.setContentsMargins(0, 12, 0, 0)
        speed_layout.setSpacing(12)
        speed_lbl = QLabel("Speed")
        speed_lbl.setStyleSheet(f"color: {theme.rgb(theme.TEXT_TERTIARY)}; font-size: 11px;")
        speed_layout.addWidget(speed_lbl)
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setMinimum(75)
        self._speed_slider.setMaximum(125)
        self._speed_slider.setValue(100)
        speed_layout.addWidget(self._speed_slider, stretch=1)
        self._speed_label = QLabel("1.0x")
        self._speed_label.setStyleSheet(
            f"color: {theme.rgb(theme.ACCENT)}; font-size: 12px; font-weight: 600;"
        )
        speed_layout.addWidget(self._speed_label)
        pb_layout.addWidget(speed_section)

        self._content_layout.addWidget(self._playback_card)

        # Overlap start button
        self._overlap_btn = QPushButton("▶ Start Overlap")
        self._overlap_btn.setStyleSheet(
            f"padding: 14px; background: {theme.rgb(theme.ACCENT)}; color: #ffffff; "
            f"border: none; border-radius: 10px; font-size: 15px; font-weight: 600;"
        )
        self._overlap_btn.setVisible(False)
        self._content_layout.addWidget(self._overlap_btn)

        # Recording card (for overlapping + live delivery)
        self._recording_card = QFrame()
        self._recording_card.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
            f"border: 1px solid {theme.rgb(theme.BORDER)}; "
            f"border-radius: 14px; }}"
        )
        rec_layout = QHBoxLayout(self._recording_card)
        rec_layout.setContentsMargins(24, 16, 24, 16)
        rec_layout.setSpacing(16)

        wave_container = QFrame()
        wave_container.setStyleSheet(
            f"QFrame {{ background: {theme.rgb(theme.WAVE_BG)}; "
            f"border-radius: 10px; border: 1px solid {theme.rgb(theme.BORDER_LIGHT)}; }}"
        )
        wv_layout = QVBoxLayout(wave_container)
        wv_layout.setContentsMargins(0, 0, 0, 0)
        self._waveform = WaveformWidget()
        wv_layout.addWidget(self._waveform)
        rec_layout.addWidget(wave_container, stretch=1)

        self._record_button = RecordButtonWidget(size=48)
        self._record_button.setVisible(False)  # hidden in listening/overlap modes
        rec_layout.addWidget(self._record_button)

        self._content_layout.addWidget(self._recording_card)

        # Status bar
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            f"color: {theme.rgb(theme.TEXT_SECONDARY)}; font-size: 13px;"
        )
        self._content_layout.addWidget(self._status_label)

        # Error banner
        self._error_banner = ErrorBanner(retryable=True)
        self._content_layout.addWidget(self._error_banner)

        self._content_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # --- Bottom Actions ---
        bottom = QWidget()
        bottom.setStyleSheet(f"background: {theme.rgb(theme.BG_PRIMARY)};")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(32, 0, 32, 24)
        self._complete_button = QPushButton("完了")
        self._complete_button.setEnabled(False)
        from PySide6.QtWidgets import QSizePolicy
        self._complete_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bottom_layout.addWidget(self._complete_button)
        root.addWidget(bottom)

        # --- Connections ---
        self._mode_segment.mode_changed.connect(self._on_mode_selected)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        self._complete_button.clicked.connect(self._vm.complete)

        # Playback controls
        self._playback_controls.play_pause_clicked.connect(self._vm.toggle_play_pause)
        self._playback_controls.seek_requested.connect(self._vm.seek)
        self._playback_controls.skip_requested.connect(self._vm.skip)
        self._playback_controls.reset_requested.connect(self._vm.reset_to_start)

        # Recording
        self._record_button.clicked.connect(self._on_record_click)

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

        # Playback transport
        self._vm.playback_position_changed.connect(self._on_position_changed)
        self._vm.playback_duration_changed.connect(self._playback_controls.set_duration)
        self._vm.playback_state_changed.connect(
            lambda state: self._playback_controls.set_playing(state == "playing")
        )

        # Model audio may already be ready
        if self._vm.is_model_audio_loaded:
            self._on_audio_ready()

        self._init_ja_text()
        self._update_mode_visibility(self._vm.current_mode)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._vm.activate()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._vm.deactivate()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------

    def _on_mode_selected(self, mode: str) -> None:
        self._vm.switch_mode(mode)  # type: ignore[arg-type]

    def _on_mode_changed(self, mode: str) -> None:
        self._status_label.setText("")
        self._update_mode_visibility(mode)

    def _update_mode_visibility(self, mode: str) -> None:
        is_listening = mode == "listening"
        is_overlapping = mode == "overlapping"
        is_live = mode == "live_delivery"

        self._model_text_label.setVisible(is_listening or is_overlapping)
        self._ja_text_label.setVisible(is_live)
        self._text_title.setText("Model Text" if not is_live else "")
        self._playback_card.setVisible(is_listening)
        self._overlap_btn.setVisible(is_overlapping)
        self._recording_card.setVisible(is_overlapping or is_live)
        self._record_button.setVisible(is_live)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_speed_changed(self, value: int) -> None:
        rate = value / 100.0
        self._speed_label.setText(f"{rate:.1f}x")
        self._vm.set_speed(rate)

    def _on_audio_ready(self) -> None:
        self._status_label.setText("モデル音声準備完了")
        self._error_banner.clear()
        self._init_model_text()

    def _on_audio_failed(self, message: str) -> None:
        self._error_banner.show_error(f"TTS エラー: {message}")

    def _init_model_text(self) -> None:
        texts = self._vm.sentence_texts
        if texts:
            self._model_text_label.setText("<br>".join(texts))
        self._prev_highlight_idx = -1

    def _init_ja_text(self) -> None:
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
                parts.append(
                    f'<span style="background-color: {theme.rgb(theme.REVIEW_BG)}; '
                    f'padding: 2px 6px;">{text}</span>'
                )
            else:
                parts.append(text)
        self._model_text_label.setText("<br>".join(parts))

    def _on_overlapping(self, score: float) -> None:
        self._status_label.setText(f"発音スコア: {score:.1f}")

    def _on_overlapping_words(self, summary: OverlappingSummary) -> None:
        self._render_word_results(summary.sentence_words)

    def _on_delivery(self, passed: bool, error_rate: float, threshold: float) -> None:
        result = "合格" if passed else "不合格"
        pct = error_rate * 100
        threshold_pct = threshold * 100
        self._status_label.setText(
            f"{result} — エラー率: {pct:.0f}% (基準: {threshold_pct:.0f}%未満)"
        )

    def _on_delivery_detail(self, summary: LiveDeliverySummary) -> None:
        self._render_word_results(summary.sentence_words)

    def _render_word_results(
        self,
        sentence_words: tuple[tuple[PronunciationWordResult, ...], ...],
    ) -> None:
        _STYLES = {
            "Mispronunciation": f"color: {theme.rgb(theme.ERROR)}; font-weight: bold;",
            "Omission": f"color: {theme.rgb(theme.TEXT_TERTIARY)}; text-decoration: line-through;",
        }
        _DEFAULT = f"color: {theme.rgb(theme.CORRECT_TEXT)};"

        parts: list[str] = []
        for sentence in sentence_words:
            word_spans = []
            for wr in sentence:
                style = _STYLES.get(wr.error_type, _DEFAULT)
                word_spans.append(f'<span style="{style}">{wr.word}</span>')
            parts.append(" ".join(word_spans))
        self._model_text_label.setText("<br>".join(parts))

    def _on_record_click(self) -> None:
        if self._record_button.recording:
            audio = self._recorder.stop()
            self._record_button.set_recording(False)
            self._recording_card.setStyleSheet(
                f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
                f"border: 1px solid {theme.rgb(theme.BORDER)}; "
                f"border-radius: 14px; }}"
            )
            if audio is not None:
                self._vm.on_recording_finished(audio)
        else:
            self._recorder.start()
            self._vm.on_recording_started()
            self._record_button.set_recording(True)
            self._recording_card.setStyleSheet(
                f"QFrame {{ background: {theme.rgb(theme.BG_CARD)}; "
                f"border: 1px solid {theme.rgb(theme.ACCENT_BORDER)}; "
                f"border-radius: 14px; }}"
            )
