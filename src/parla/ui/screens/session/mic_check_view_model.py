"""ViewModel for the mic check screen (SCREEN-E1)."""

from typing import Any

from PySide6.QtCore import QObject, Signal

LEVEL_THRESHOLD = 0.05


class MicCheckViewModel(QObject):
    """Manages mic device selection, level detection, and start gating.

    Does not inherit BaseViewModel because it has no EventBus event handlers.
    """

    start_enabled_changed = Signal(bool)
    level_warning = Signal()
    proceed = Signal()
    error = Signal(str)

    def __init__(
        self,
        *,
        recorder: Any,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._recorder = recorder
        self._start_enabled = False
        self._testing = False

        self._recorder.level_changed.connect(self._on_level)
        self._recorder.error_occurred.connect(self._on_error)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_start_enabled(self) -> bool:
        return self._start_enabled

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def device_names(self) -> list[str]:
        devices = self._recorder.available_devices()
        return [d.description() for d in devices]

    def select_device(self, index: int) -> None:
        devices = self._recorder.available_devices()
        if 0 <= index < len(devices):
            self._recorder.select_device(devices[index])

    def start_test(self) -> None:
        if not self._testing:
            self._testing = True
            self._recorder.start()

    def stop_test(self) -> None:
        if self._testing:
            self._testing = False
            self._recorder.cancel()

    def confirm_start(self) -> None:
        if not self._start_enabled:
            return
        if self._testing:
            self._testing = False
            self._recorder.cancel()
        self.proceed.emit()

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_level(self, rms: float) -> None:
        if rms >= LEVEL_THRESHOLD and not self._start_enabled:
            self._start_enabled = True
            self.start_enabled_changed.emit(True)
        elif rms < LEVEL_THRESHOLD and not self._start_enabled:
            self.level_warning.emit()

    def _on_error(self, message: str) -> None:
        self.error.emit(message)
