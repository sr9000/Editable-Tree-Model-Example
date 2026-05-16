"""Shared helper for drawing a small severity badge in a cell corner."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter

from themes.spec import ThemeSpec

# Hard-coded fallbacks used when the theme palette has no explicit badge color.
_FALLBACK_ERROR = QColor("#d13438")
_FALLBACK_WARNING = QColor("#bf6900")

_BADGE_SIZE = 8  # px — diameter of the filled circle


def draw_severity_badge(
    painter: QPainter,
    rect: QRect,
    severity: str | None,
    theme: ThemeSpec,
) -> None:
    """Draw an 8×8 filled circle in the bottom-right corner of *rect*.

    Does nothing when *severity* is ``None`` or unrecognised.
    """
    if severity is None:
        return

    vs = theme.palette.validation
    if severity == "error":
        color = vs.error_badge or _FALLBACK_ERROR
    elif severity == "warning":
        color = vs.warning_badge or _FALLBACK_WARNING
    else:
        return

    x = rect.right() - _BADGE_SIZE - 1
    y = rect.bottom() - _BADGE_SIZE - 1

    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(x, y, _BADGE_SIZE, _BADGE_SIZE)
    finally:
        painter.restore()
