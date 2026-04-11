"""Vertical level meter widget with dB scale, peak hold, and clip indicator."""

import math
import time

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from parla.ui import theme

# dB constants
_DB_MIN = -60.0
_DB_MAX = 0.0
_DB_RANGE = _DB_MAX - _DB_MIN  # 60.0

# Zone boundaries (dBFS)
_ZONE_WARN = -6.0
_ZONE_DANGER = -3.0

# Clip detection
_CLIP_THRESHOLD_DB = -1.0
_CLIP_HOLD_SECONDS = 2.0

# Peak hold
_PEAK_HOLD_SECONDS = 0.5
_PEAK_DECAY_DB_PER_SEC = 20.0

# Animation
_TICK_MS = 30

# Scale labels
_SCALE_DB_MARKS = [0, -6, -12, -20, -40]


def _rms_to_db(rms: float) -> float:
    """Convert linear RMS (0-1) to dBFS, clamped to display range."""
    if rms <= 0.0:
        return _DB_MIN
    db = 20.0 * math.log10(rms)
    return max(_DB_MIN, min(_DB_MAX, db))


class LevelMeterWidget(QWidget):
    """Displays RMS audio level as a vertical bar with dB scale.

    Features:
    - 3-color zones: green (safe), yellow (caution), red (danger)
    - dB scale labels on the left
    - Peak hold line with decay
    - Clip indicator (red band at top)
    """

    _BG_COLOR = theme.BG_SURFACE
    _OK_COLOR = theme.ACCENT
    _WARN_COLOR = theme.WARNING
    _DANGER_COLOR = theme.ERROR
    _CLIP_COLOR = theme.ERROR
    _BORDER_COLOR = theme.BORDER
    _SCALE_COLOR = theme.TEXT_SECONDARY
    _PEAK_PEN = QPen(theme.TEXT_PRIMARY, 2)
    _ZONE_LINE_PEN = QPen(theme.GRID_LINE, 1)

    def __init__(
        self,
        warning_threshold: float = 0.1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._level: float = 0.0
        self._level_db: float = _DB_MIN
        self._warning_threshold = warning_threshold

        # Peak hold state
        self._peak_db: float = _DB_MIN
        self._peak_time: float = 0.0
        self._peak_decaying = False

        # Clip state
        self._clipping = False
        self._clip_time: float = 0.0

        # Animation timer
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def level(self) -> float:
        return self._level

    @property
    def level_db(self) -> float:
        return self._level_db

    @property
    def peak_db(self) -> float:
        return self._peak_db

    @property
    def is_warning(self) -> bool:
        return self._level < self._warning_threshold

    @property
    def is_clipping(self) -> bool:
        return self._clipping

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_level(self, rms: float) -> None:
        """Set the current RMS level (clamped to 0.0-1.0) and schedule repaint."""
        new_level = max(0.0, min(1.0, rms))
        if new_level == self._level:
            return
        self._level = new_level
        self._level_db = _rms_to_db(new_level)

        # Update peak
        now = time.monotonic()
        if self._level_db > self._peak_db:
            self._peak_db = self._level_db
            self._peak_time = now
            self._peak_decaying = False

        # Clip detection
        if self._level_db >= _CLIP_THRESHOLD_DB:
            self._clipping = True
            self._clip_time = now

        self._ensure_timer()
        self.update()

    # ------------------------------------------------------------------
    # Size hints
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        return QSize(60, 200)

    def minimumSizeHint(self) -> QSize:
        return QSize(40, 80)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Layout: [scale_labels | bar]
        label_width = 30
        bar_x = label_width
        bar_w = w - label_width
        if bar_w < 4:
            bar_w = w
            bar_x = 0
            label_width = 0

        # Background
        painter.fillRect(bar_x, 0, bar_w, h, self._BG_COLOR)

        # Draw level bar with zone colors
        if self._level_db > _DB_MIN:
            self._draw_bar(painter, bar_x, bar_w, h)

        # Zone boundary lines
        for zone_db in (_ZONE_WARN, _ZONE_DANGER):
            y = self._db_to_y(zone_db, h)
            painter.setPen(self._ZONE_LINE_PEN)
            painter.drawLine(bar_x, y, bar_x + bar_w, y)

        # Peak hold line
        if self._peak_db > _DB_MIN:
            peak_y = self._db_to_y(self._peak_db, h)
            painter.setPen(self._PEAK_PEN)
            painter.drawLine(bar_x, peak_y, bar_x + bar_w, peak_y)

        # Clip indicator (red band at top)
        if self._clipping:
            clip_h = max(4, h // 30)
            painter.fillRect(bar_x, 0, bar_w, clip_h, self._CLIP_COLOR)

        # Border
        painter.setPen(self._BORDER_COLOR)
        painter.drawRect(bar_x, 0, bar_w - 1, h - 1)

        # Scale labels
        if label_width > 0:
            self._draw_scale(painter, label_width, h)

        painter.end()

    def _draw_bar(self, painter: QPainter, x: int, w: int, h: int) -> None:
        """Draw the level bar with 3-color zones."""
        level_y = self._db_to_y(self._level_db, h)
        warn_y = self._db_to_y(_ZONE_WARN, h)
        danger_y = self._db_to_y(_ZONE_DANGER, h)

        # Green zone: from bottom up to min(level_y, warn_y)
        green_top = max(level_y, warn_y)
        if green_top < h:
            painter.fillRect(x, green_top, w, h - green_top, self._OK_COLOR)

        # Yellow zone: from warn_y up to min(level_y, danger_y)
        if self._level_db > _ZONE_WARN:
            yellow_top = max(level_y, danger_y)
            painter.fillRect(x, yellow_top, w, warn_y - yellow_top, self._WARN_COLOR)

        # Red zone: from danger_y up to level_y
        if self._level_db > _ZONE_DANGER:
            painter.fillRect(x, level_y, w, danger_y - level_y, self._DANGER_COLOR)

    def _draw_scale(self, painter: QPainter, label_w: int, h: int) -> None:
        """Draw dB scale labels on the left side."""
        font = QFont(theme.FONT_FAMILY)
        font.setPointSize(7)
        painter.setFont(font)
        painter.setPen(self._SCALE_COLOR)

        for db in _SCALE_DB_MARKS:
            y = self._db_to_y(float(db), h)
            text = str(db)
            painter.drawText(0, y - 6, label_w - 2, 12, 0x0082, text)  # AlignRight | AlignVCenter

    def _db_to_y(self, db: float, h: int) -> int:
        """Convert dB value to y pixel coordinate (0 dB at top, -60 dB at bottom)."""
        ratio = (db - _DB_MIN) / _DB_RANGE
        return int(h * (1.0 - ratio))

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        now = time.monotonic()
        changed = False

        # Peak decay
        if self._peak_db > _DB_MIN:
            elapsed = now - self._peak_time
            if elapsed >= _PEAK_HOLD_SECONDS:
                if not self._peak_decaying:
                    self._peak_decaying = True
                    self._peak_time = now
                else:
                    decayed = self._peak_db - _PEAK_DECAY_DB_PER_SEC * _TICK_MS / 1000.0
                    if decayed <= _DB_MIN:
                        self._peak_db = _DB_MIN
                        self._peak_decaying = False
                    else:
                        self._peak_db = decayed
                    changed = True

        # Clip hold expiry
        if self._clipping and now - self._clip_time >= _CLIP_HOLD_SECONDS:
                self._clipping = False
                changed = True

        if changed:
            self.update()

        # Stop timer if nothing to animate
        if self._peak_db <= _DB_MIN and not self._clipping:
            self._timer.stop()

    def _ensure_timer(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
